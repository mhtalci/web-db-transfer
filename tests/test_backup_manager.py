"""
Unit tests for the checkup backup manager.
"""

import asyncio
import json
import shutil
import tarfile
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from migration_assistant.checkup.backup_manager import (
    BackupInfo,
    BackupManager,
    IncrementalBackupStrategy,
)
from migration_assistant.checkup.models import CheckupConfig
from migration_assistant.core.exceptions import BackupError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_config(temp_dir):
    """Create a sample checkup configuration."""
    return CheckupConfig(
        target_directory=temp_dir / "source",
        backup_dir=temp_dir / "backups",
        create_backup=True,
        dry_run=False
    )


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing."""
    source_dir = temp_dir / "source"
    source_dir.mkdir(parents=True)
    
    # Create some Python files
    (source_dir / "main.py").write_text("print('Hello, World!')")
    (source_dir / "utils.py").write_text("def helper(): pass")
    
    # Create a subdirectory with files
    sub_dir = source_dir / "submodule"
    sub_dir.mkdir()
    (sub_dir / "module.py").write_text("class TestClass: pass")
    
    # Create some files that should be excluded
    (source_dir / "__pycache__").mkdir()
    (source_dir / "__pycache__" / "main.cpython-39.pyc").write_text("compiled")
    
    return source_dir


class TestBackupInfo:
    """Test BackupInfo class."""
    
    def test_backup_info_creation(self, temp_dir):
        """Test creating BackupInfo object."""
        backup_info = BackupInfo(
            backup_id="test_backup",
            backup_type="full",
            source_path=temp_dir / "source",
            backup_path=temp_dir / "backup.tar.gz",
            checksum="abc123",
            size=1024
        )
        
        assert backup_info.backup_id == "test_backup"
        assert backup_info.backup_type == "full"
        assert backup_info.source_path == temp_dir / "source"
        assert backup_info.backup_path == temp_dir / "backup.tar.gz"
        assert backup_info.checksum == "abc123"
        assert backup_info.size == 1024
        assert not backup_info.verified
        assert backup_info.verification_date is None
    
    def test_backup_info_to_dict(self, temp_dir):
        """Test converting BackupInfo to dictionary."""
        backup_info = BackupInfo(
            backup_id="test_backup",
            backup_type="full",
            source_path=temp_dir / "source",
            backup_path=temp_dir / "backup.tar.gz",
            checksum="abc123",
            size=1024,
            metadata={"test": "value"}
        )
        
        data = backup_info.to_dict()
        
        assert data["backup_id"] == "test_backup"
        assert data["backup_type"] == "full"
        assert data["source_path"] == str(temp_dir / "source")
        assert data["backup_path"] == str(temp_dir / "backup.tar.gz")
        assert data["checksum"] == "abc123"
        assert data["size"] == 1024
        assert data["metadata"] == {"test": "value"}
        assert not data["verified"]
        assert data["verification_date"] is None
    
    def test_backup_info_from_dict(self, temp_dir):
        """Test creating BackupInfo from dictionary."""
        data = {
            "backup_id": "test_backup",
            "backup_type": "full",
            "source_path": str(temp_dir / "source"),
            "backup_path": str(temp_dir / "backup.tar.gz"),
            "checksum": "abc123",
            "size": 1024,
            "created_at": "2023-01-01T12:00:00",
            "metadata": {"test": "value"},
            "verified": True,
            "verification_date": "2023-01-01T13:00:00"
        }
        
        backup_info = BackupInfo.from_dict(data)
        
        assert backup_info.backup_id == "test_backup"
        assert backup_info.backup_type == "full"
        assert backup_info.source_path == temp_dir / "source"
        assert backup_info.backup_path == temp_dir / "backup.tar.gz"
        assert backup_info.checksum == "abc123"
        assert backup_info.size == 1024
        assert backup_info.metadata == {"test": "value"}
        assert backup_info.verified
        assert backup_info.verification_date == datetime(2023, 1, 1, 13, 0, 0)


class TestIncrementalBackupStrategy:
    """Test IncrementalBackupStrategy class."""
    
    def test_calculate_file_checksum(self, temp_dir):
        """Test file checksum calculation."""
        strategy = IncrementalBackupStrategy(temp_dir)
        
        # Create a test file
        test_file = temp_dir / "test.py"
        test_file.write_text("print('test')")
        
        checksum = strategy._calculate_file_checksum(test_file)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 hex digest length
    
    def test_get_changed_files_initial(self, temp_dir, sample_files):
        """Test getting changed files on initial run."""
        strategy = IncrementalBackupStrategy(temp_dir)
        
        changed_files = strategy.get_changed_files(sample_files)
        
        # All Python files should be considered changed on first run
        python_files = list(sample_files.rglob("*.py"))
        assert len(changed_files) == len(python_files)
        assert all(f.suffix == ".py" for f in changed_files)
    
    def test_get_changed_files_no_changes(self, temp_dir, sample_files):
        """Test getting changed files when no changes occurred."""
        strategy = IncrementalBackupStrategy(temp_dir)
        
        # First run - all files are changed
        changed_files_1 = strategy.get_changed_files(sample_files)
        assert len(changed_files_1) > 0
        
        # Second run - no files changed
        changed_files_2 = strategy.get_changed_files(sample_files)
        assert len(changed_files_2) == 0
    
    def test_get_changed_files_with_modifications(self, temp_dir, sample_files):
        """Test getting changed files after modifications."""
        strategy = IncrementalBackupStrategy(temp_dir)
        
        # First run
        strategy.get_changed_files(sample_files)
        
        # Modify a file
        (sample_files / "main.py").write_text("print('Modified!')")
        
        # Second run - only modified file should be detected
        changed_files = strategy.get_changed_files(sample_files)
        assert len(changed_files) == 1
        assert changed_files[0].name == "main.py"
    
    def test_save_and_load_state(self, temp_dir, sample_files):
        """Test saving and loading strategy state."""
        strategy = IncrementalBackupStrategy(temp_dir)
        state_file = temp_dir / "state.json"
        
        # Get initial changed files
        strategy.get_changed_files(sample_files)
        
        # Save state
        strategy.save_state(state_file)
        assert state_file.exists()
        
        # Create new strategy and load state
        new_strategy = IncrementalBackupStrategy(temp_dir)
        new_strategy.load_state(state_file)
        
        # Should have no changed files since state was loaded
        changed_files = new_strategy.get_changed_files(sample_files)
        assert len(changed_files) == 0


class TestBackupManager:
    """Test BackupManager class."""
    
    def test_backup_manager_initialization(self, sample_config):
        """Test BackupManager initialization."""
        manager = BackupManager(sample_config)
        
        assert manager.config == sample_config
        assert manager.backup_dir == sample_config.backup_dir
        assert manager.backup_dir.exists()
        assert isinstance(manager.incremental_strategy, IncrementalBackupStrategy)
    
    def test_generate_backup_id(self, sample_config):
        """Test backup ID generation."""
        manager = BackupManager(sample_config)
        
        backup_id = manager._generate_backup_id()
        
        assert backup_id.startswith("checkup_backup_")
        assert len(backup_id) > len("checkup_backup_")
    
    def test_should_exclude(self, sample_config):
        """Test file exclusion logic."""
        manager = BackupManager(sample_config)
        
        # Should exclude __pycache__ files
        assert manager._should_exclude(Path("__pycache__/test.pyc"))
        
        # Should exclude .git files
        assert manager._should_exclude(Path(".git/config"))
        
        # Should not exclude regular Python files
        assert not manager._should_exclude(Path("main.py"))
        assert not manager._should_exclude(Path("src/utils.py"))
    
    @pytest.mark.asyncio
    async def test_create_full_backup(self, sample_config, sample_files):
        """Test creating a full backup."""
        manager = BackupManager(sample_config)
        
        backup_info = await manager.create_full_backup()
        
        assert backup_info is not None
        assert backup_info.backup_type == "full"
        assert backup_info.source_path == sample_config.target_directory
        assert backup_info.backup_path.exists()
        assert backup_info.backup_path.suffix == ".gz"
        assert backup_info.size > 0
        assert len(backup_info.checksum) == 64
        
        # Verify backup is in registry
        assert backup_info.backup_id in manager._backup_registry
    
    @pytest.mark.asyncio
    async def test_create_full_backup_dry_run(self, sample_config, sample_files):
        """Test creating backup in dry run mode."""
        sample_config.dry_run = True
        manager = BackupManager(sample_config)
        
        with pytest.raises(BackupError, match="Cannot create backup in dry run mode"):
            await manager.create_full_backup()
    
    @pytest.mark.asyncio
    async def test_create_incremental_backup_no_changes(self, sample_config, sample_files):
        """Test creating incremental backup with no changes."""
        manager = BackupManager(sample_config)
        
        # First incremental backup should contain all files
        backup_info_1 = await manager.create_incremental_backup()
        assert backup_info_1 is not None
        assert backup_info_1.backup_type == "incremental"
        
        # Second incremental backup should be None (no changes)
        backup_info_2 = await manager.create_incremental_backup()
        assert backup_info_2 is None
    
    @pytest.mark.asyncio
    async def test_create_incremental_backup_with_changes(self, sample_config, sample_files):
        """Test creating incremental backup with changes."""
        manager = BackupManager(sample_config)
        
        # First incremental backup
        await manager.create_incremental_backup()
        
        # Modify a file
        (sample_files / "main.py").write_text("print('Modified!')")
        
        # Second incremental backup should contain the changed file
        backup_info = await manager.create_incremental_backup()
        assert backup_info is not None
        assert backup_info.backup_type == "incremental"
        assert backup_info.metadata["changed_files"] == 1
        assert "main.py" in str(backup_info.metadata["changed_file_list"])
    
    @pytest.mark.asyncio
    async def test_verify_backup_valid(self, sample_config, sample_files):
        """Test verifying a valid backup."""
        manager = BackupManager(sample_config)
        
        # Create a backup
        backup_info = await manager.create_full_backup()
        
        # Verify the backup
        is_valid = await manager.verify_backup(backup_info.backup_id)
        assert is_valid
        
        # Check that backup is marked as verified
        updated_info = manager.get_backup_info(backup_info.backup_id)
        assert updated_info.verified
        assert updated_info.verification_date is not None
    
    @pytest.mark.asyncio
    async def test_verify_backup_invalid_checksum(self, sample_config, sample_files):
        """Test verifying backup with invalid checksum."""
        manager = BackupManager(sample_config)
        
        # Create a backup
        backup_info = await manager.create_full_backup()
        
        # Corrupt the checksum
        backup_info.checksum = "invalid_checksum"
        manager._backup_registry[backup_info.backup_id] = backup_info
        
        # Verify should fail
        is_valid = await manager.verify_backup(backup_info.backup_id)
        assert not is_valid
    
    @pytest.mark.asyncio
    async def test_verify_backup_missing_file(self, sample_config, sample_files):
        """Test verifying backup with missing file."""
        manager = BackupManager(sample_config)
        
        # Create a backup
        backup_info = await manager.create_full_backup()
        
        # Delete the backup file
        backup_info.backup_path.unlink()
        
        # Verify should fail
        is_valid = await manager.verify_backup(backup_info.backup_id)
        assert not is_valid
    
    @pytest.mark.asyncio
    async def test_verify_all_backups(self, sample_config, sample_files):
        """Test verifying all backups."""
        manager = BackupManager(sample_config)
        
        # Create multiple backups
        backup_1 = await manager.create_full_backup()
        backup_2 = await manager.create_incremental_backup()
        
        # Verify all backups
        results = await manager.verify_all_backups()
        
        assert len(results) == 2
        assert results[backup_1.backup_id] is True
        if backup_2:  # Incremental backup might be None if no changes
            assert results[backup_2.backup_id] is True
    
    def test_list_backups(self, sample_config):
        """Test listing backups."""
        manager = BackupManager(sample_config)
        
        # Initially no backups
        backups = manager.list_backups()
        assert len(backups) == 0
        
        # Add some mock backups to registry
        backup_1 = BackupInfo(
            "backup_1", "full", Path("/src"), Path("/backup1.tar.gz"), "checksum1", 1024
        )
        backup_2 = BackupInfo(
            "backup_2", "incremental", Path("/src"), Path("/backup2.tar.gz"), "checksum2", 512
        )
        backup_2.verified = True
        
        manager._backup_registry["backup_1"] = backup_1
        manager._backup_registry["backup_2"] = backup_2
        
        # List all backups
        all_backups = manager.list_backups()
        assert len(all_backups) == 2
        
        # List only full backups
        full_backups = manager.list_backups(backup_type="full")
        assert len(full_backups) == 1
        assert full_backups[0].backup_type == "full"
        
        # List only verified backups
        verified_backups = manager.list_backups(verified_only=True)
        assert len(verified_backups) == 1
        assert verified_backups[0].verified
    
    def test_get_backup_info(self, sample_config):
        """Test getting backup info by ID."""
        manager = BackupManager(sample_config)
        
        # Non-existent backup
        info = manager.get_backup_info("non_existent")
        assert info is None
        
        # Add a backup to registry
        backup_info = BackupInfo(
            "test_backup", "full", Path("/src"), Path("/backup.tar.gz"), "checksum", 1024
        )
        manager._backup_registry["test_backup"] = backup_info
        
        # Get existing backup
        retrieved_info = manager.get_backup_info("test_backup")
        assert retrieved_info == backup_info
    
    @pytest.mark.asyncio
    async def test_delete_backup(self, sample_config, sample_files):
        """Test deleting a backup."""
        manager = BackupManager(sample_config)
        
        # Create a backup
        backup_info = await manager.create_full_backup()
        backup_id = backup_info.backup_id
        
        # Verify backup exists
        assert backup_info.backup_path.exists()
        assert backup_id in manager._backup_registry
        
        # Delete the backup
        success = await manager.delete_backup(backup_id)
        assert success
        
        # Verify backup is gone
        assert not backup_info.backup_path.exists()
        assert backup_id not in manager._backup_registry
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_backup(self, sample_config):
        """Test deleting a non-existent backup."""
        manager = BackupManager(sample_config)
        
        success = await manager.delete_backup("non_existent")
        assert not success
    
    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, sample_config):
        """Test cleaning up old backups."""
        manager = BackupManager(sample_config)
        
        # Create mock old backups
        old_backup = BackupInfo(
            "old_backup", "full", Path("/src"), Path("/old.tar.gz"), "checksum", 1024,
            created_at=datetime.now() - timedelta(days=35)
        )
        recent_backup = BackupInfo(
            "recent_backup", "full", Path("/src"), Path("/recent.tar.gz"), "checksum", 1024,
            created_at=datetime.now() - timedelta(days=5)
        )
        
        # Create actual files for the mock backups
        old_backup.backup_path.parent.mkdir(parents=True, exist_ok=True)
        old_backup.backup_path.touch()
        recent_backup.backup_path.parent.mkdir(parents=True, exist_ok=True)
        recent_backup.backup_path.touch()
        
        manager._backup_registry["old_backup"] = old_backup
        manager._backup_registry["recent_backup"] = recent_backup
        
        # Cleanup backups older than 30 days
        deleted = await manager.cleanup_old_backups(max_age_days=30, max_backups=10)
        
        assert "old_backup" in deleted
        assert "recent_backup" not in deleted
        assert "old_backup" not in manager._backup_registry
        assert "recent_backup" in manager._backup_registry
    
    def test_get_backup_statistics_empty(self, sample_config):
        """Test getting backup statistics with no backups."""
        manager = BackupManager(sample_config)
        
        stats = manager.get_backup_statistics()
        
        assert stats["total_backups"] == 0
        assert stats["total_size"] == 0
        assert stats["verified_backups"] == 0
        assert stats["full_backups"] == 0
        assert stats["incremental_backups"] == 0
        assert stats["oldest_backup"] is None
        assert stats["newest_backup"] is None
    
    def test_get_backup_statistics_with_backups(self, sample_config):
        """Test getting backup statistics with backups."""
        manager = BackupManager(sample_config)
        
        # Add mock backups
        backup_1 = BackupInfo(
            "backup_1", "full", Path("/src"), Path("/backup1.tar.gz"), "checksum1", 1024,
            created_at=datetime(2023, 1, 1)
        )
        backup_1.verified = True
        
        backup_2 = BackupInfo(
            "backup_2", "incremental", Path("/src"), Path("/backup2.tar.gz"), "checksum2", 512,
            created_at=datetime(2023, 1, 2)
        )
        
        manager._backup_registry["backup_1"] = backup_1
        manager._backup_registry["backup_2"] = backup_2
        
        stats = manager.get_backup_statistics()
        
        assert stats["total_backups"] == 2
        assert stats["total_size"] == 1536
        assert stats["total_size_mb"] == 1536 / (1024 * 1024)
        assert stats["verified_backups"] == 1
        assert stats["full_backups"] == 1
        assert stats["incremental_backups"] == 1
        assert stats["oldest_backup"] == "2023-01-01T00:00:00"
        assert stats["newest_backup"] == "2023-01-02T00:00:00"
        assert stats["verification_rate"] == 0.5
    
    @pytest.mark.asyncio
    async def test_create_pre_cleanup_backup(self, sample_config, sample_files):
        """Test creating pre-cleanup backup."""
        manager = BackupManager(sample_config)
        
        # Files to be modified during cleanup
        files_to_modify = [
            sample_files / "main.py",
            sample_files / "utils.py"
        ]
        
        backup_info = await manager.create_pre_cleanup_backup(files_to_modify)
        
        assert backup_info is not None
        assert backup_info.backup_type == "pre_cleanup"
        assert backup_info.backup_path.exists()
        assert backup_info.metadata["backed_up_files"] == 2
        assert backup_info.metadata["backup_method"] == "targeted_files"
        
        # Verify files are in the backup
        file_list = backup_info.metadata["file_list"]
        assert any("main.py" in f for f in file_list)
        assert any("utils.py" in f for f in file_list)
    
    @pytest.mark.asyncio
    async def test_create_pre_cleanup_backup_no_files(self, sample_config):
        """Test creating pre-cleanup backup with no files."""
        manager = BackupManager(sample_config)
        
        backup_info = await manager.create_pre_cleanup_backup([])
        assert backup_info is None
    
    @pytest.mark.asyncio
    async def test_create_pre_cleanup_backup_dry_run(self, sample_config, sample_files):
        """Test creating pre-cleanup backup in dry run mode."""
        sample_config.dry_run = True
        manager = BackupManager(sample_config)
        
        files_to_modify = [sample_files / "main.py"]
        backup_info = await manager.create_pre_cleanup_backup(files_to_modify)
        
        assert backup_info is None
    
    def test_registry_persistence(self, sample_config, temp_dir):
        """Test backup registry persistence."""
        manager = BackupManager(sample_config)
        
        # Add a backup to registry
        backup_info = BackupInfo(
            "test_backup", "full", Path("/src"), Path("/backup.tar.gz"), "checksum", 1024
        )
        manager._backup_registry["test_backup"] = backup_info
        manager._save_registry()
        
        # Create new manager instance (should load registry)
        new_manager = BackupManager(sample_config)
        
        # Verify backup is loaded
        loaded_info = new_manager.get_backup_info("test_backup")
        assert loaded_info is not None
        assert loaded_info.backup_id == "test_backup"
        assert loaded_info.backup_type == "full"
    
    @pytest.mark.asyncio
    async def test_enhanced_backup_verification(self, sample_config, sample_files):
        """Test enhanced backup verification with restoration testing."""
        manager = BackupManager(sample_config)
        
        # Create a backup
        backup_info = await manager.create_full_backup()
        
        # Test basic verification
        is_valid_basic = await manager.verify_backup(backup_info.backup_id, test_restoration=False)
        assert is_valid_basic
        
        # Test verification with restoration
        is_valid_full = await manager.verify_backup(backup_info.backup_id, test_restoration=True)
        assert is_valid_full
        
        # Check verification metadata
        updated_info = manager.get_backup_info(backup_info.backup_id)
        assert updated_info.verified
        assert "verification_method" in updated_info.metadata
    
    @pytest.mark.asyncio
    async def test_backup_restoration_testing(self, sample_config, sample_files):
        """Test backup restoration testing functionality."""
        manager = BackupManager(sample_config)
        
        # Create a backup
        backup_info = await manager.create_full_backup()
        
        # Test restoration
        restoration_result = await manager.test_backup_restoration(backup_info.backup_id)
        
        assert restoration_result["success"]
        assert restoration_result["backup_id"] == backup_info.backup_id
        assert restoration_result["extracted_files"] > 0
        assert restoration_result["readable_files"] > 0
        assert "test_timestamp" in restoration_result
    
    @pytest.mark.asyncio
    async def test_backup_restoration_nonexistent(self, sample_config):
        """Test restoration testing with non-existent backup."""
        manager = BackupManager(sample_config)
        
        result = await manager.test_backup_restoration("nonexistent_backup")
        
        assert not result["success"]
        assert "not found" in result["error"].lower()
    
    def test_file_permission_checking(self, sample_config, temp_dir):
        """Test file permission checking functionality."""
        manager = BackupManager(sample_config)
        
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        # Check permissions
        perms = manager._check_file_permissions(test_file)
        
        assert perms["exists"]
        assert perms["readable"]
        assert perms["size"] > 0
    
    def test_backup_prerequisites_validation(self, sample_config, temp_dir):
        """Test backup prerequisites validation."""
        manager = BackupManager(sample_config)
        
        # Test with valid directory
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        (source_dir / "test.py").write_text("print('test')")
        
        issues = manager._validate_backup_prerequisites(source_dir)
        assert len(issues) == 0  # Should have no issues
        
        # Test with non-existent directory
        nonexistent_dir = temp_dir / "nonexistent"
        issues = manager._validate_backup_prerequisites(nonexistent_dir)
        assert len(issues) > 0
        assert "does not exist" in issues[0]
    
    @pytest.mark.asyncio
    async def test_backup_with_permission_issues(self, sample_config, temp_dir):
        """Test backup creation with permission issues."""
        manager = BackupManager(sample_config)
        
        # Create source directory with files
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        (source_dir / "readable.py").write_text("print('readable')")
        
        # Create backup (should handle permission issues gracefully)
        backup_info = await manager.create_full_backup(source_dir)
        
        assert backup_info is not None
        assert backup_info.backup_type == "full"
        assert "permission_issues" in backup_info.metadata
        assert "files_skipped" in backup_info.metadata


if __name__ == "__main__":
    pytest.main([__file__])