"""
Unit tests for the backup manager.

Tests backup creation, management, and validation functionality.
"""

import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from migration_assistant.backup.manager import BackupManager
from migration_assistant.backup.storage import BackupStorage, RetentionPolicy
from migration_assistant.backup.strategies import FileBackupStrategy
from migration_assistant.core.exceptions import BackupError
from migration_assistant.models.config import DatabaseConfig, MigrationConfig, SystemConfig, AuthConfig, PathConfig, AuthType
from migration_assistant.models.session import BackupInfo, BackupType


class TestBackupManager:
    """Test cases for BackupManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def backup_storage(self, temp_dir):
        """Create a backup storage instance for testing."""
        retention_policy = RetentionPolicy(max_backups=5, max_age_days=30)
        return BackupStorage(temp_dir, retention_policy)
    
    @pytest.fixture
    def backup_manager(self, backup_storage):
        """Create a backup manager instance for testing."""
        return BackupManager(backup_storage)
    
    @pytest.fixture
    def system_config(self):
        """Create a system configuration for testing."""
        from migration_assistant.models.config import AuthConfig, PathConfig, AuthType
        
        return SystemConfig(
            type="wordpress",
            host="localhost",
            port=80,
            authentication=AuthConfig(type=AuthType.PASSWORD, username="test", password="test"),
            paths=PathConfig(root_path="/var/www")
        )
    
    @pytest.fixture
    def db_config(self):
        """Create a database configuration for testing."""
        return DatabaseConfig(
            type="mysql",
            name="test_db",
            host="localhost",
            port=3306,
            username="test_user",
            password="test_pass"
        )
    
    @pytest.fixture
    def migration_config(self, system_config, db_config):
        """Create a migration configuration for testing."""
        system_config.database = db_config
        return MigrationConfig(
            source=system_config,
            destination=system_config
        )
    
    @pytest.mark.asyncio
    async def test_create_file_backup(self, backup_manager, system_config, temp_dir):
        """Test creating a file backup."""
        # Create test files
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        options = {
            "source_paths": [test_file],
            "compression": "gzip"
        }
        
        backup_info = await backup_manager.create_backup(
            system_config, "files", options
        )
        
        assert backup_info.type == BackupType.FULL
        assert backup_info.source_system == "wordpress"
        assert backup_info.size > 0
        assert backup_info.checksum is not None
        assert backup_info.compression_used is True
        assert os.path.exists(backup_info.location)
    
    @pytest.mark.asyncio
    async def test_create_database_backup(self, backup_manager, system_config, db_config):
        """Test creating a database backup."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful mysqldump
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            backup_info = await backup_manager.create_backup(
                system_config, "database", {}, db_config
            )
            
            assert backup_info.type == BackupType.FULL
            assert backup_info.metadata["database_type"] == "mysql"
            assert backup_info.metadata["database_name"] == "test_db"
    
    @pytest.mark.asyncio
    async def test_create_config_backup(self, backup_manager, system_config, temp_dir):
        """Test creating a configuration backup."""
        # Create test config file
        config_file = os.path.join(temp_dir, "config.ini")
        with open(config_file, "w") as f:
            f.write("[section]\nkey=value\n")
        
        options = {
            "config_files": [config_file],
            "config_data": {"test": "data"}
        }
        
        backup_info = await backup_manager.create_backup(
            system_config, "config", options
        )
        
        assert backup_info.type == BackupType.FULL
        assert backup_info.metadata["backup_type"] == "configuration"
        
        # Verify backup content
        with open(backup_info.location, "r") as f:
            backup_data = json.load(f)
            assert "config_files" in backup_data
            assert config_file in backup_data["config_files"]
    
    @pytest.mark.asyncio
    async def test_create_full_system_backup(self, backup_manager, migration_config, temp_dir):
        """Test creating a full system backup."""
        # Create test files
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        backup_options = {
            "file_paths": [test_file],
            "backup_database": False,  # Skip database backup for this test
            "config_files": []
        }
        
        backups = await backup_manager.create_full_system_backup(
            migration_config, backup_options
        )
        
        assert len(backups) >= 2  # At least files and config backups
        
        # Check that different backup types were created
        backup_types = [b.metadata.get("backup_type") for b in backups]
        assert "file_archive" in backup_types
        assert "configuration" in backup_types
    
    @pytest.mark.asyncio
    async def test_verify_backup(self, backup_manager, system_config, temp_dir):
        """Test backup verification."""
        # Create test file backup
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        options = {"source_paths": [test_file]}
        backup_info = await backup_manager.create_backup(
            system_config, "files", options
        )
        
        # Verify the backup
        is_valid = await backup_manager.verify_backup(backup_info)
        assert is_valid is True
        assert backup_info.verified is True
        assert backup_info.verification_date is not None
    
    @pytest.mark.asyncio
    async def test_verify_corrupted_backup(self, backup_manager, system_config, temp_dir):
        """Test verification of corrupted backup."""
        # Create test file backup
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        options = {"source_paths": [test_file]}
        backup_info = await backup_manager.create_backup(
            system_config, "files", options
        )
        
        # Corrupt the backup file
        with open(backup_info.location, "w") as f:
            f.write("corrupted content")
        
        # Verify the backup
        is_valid = await backup_manager.verify_backup(backup_info)
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_verify_all_backups(self, backup_manager, system_config, temp_dir):
        """Test verification of multiple backups."""
        backups = []
        
        # Create multiple test backups
        for i in range(3):
            test_file = os.path.join(temp_dir, f"test_file_{i}.txt")
            with open(test_file, "w") as f:
                f.write(f"test content {i}")
            
            options = {"source_paths": [test_file]}
            backup_info = await backup_manager.create_backup(
                system_config, "files", options
            )
            backups.append(backup_info)
        
        # Verify all backups
        results = await backup_manager.verify_all_backups(backups)
        
        assert len(results) == 3
        assert all(results.values())  # All should be valid
    
    @pytest.mark.asyncio
    async def test_delete_backup(self, backup_manager, system_config, temp_dir):
        """Test backup deletion."""
        # Create test backup
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        options = {"source_paths": [test_file]}
        backup_info = await backup_manager.create_backup(
            system_config, "files", options
        )
        
        # Verify backup exists
        assert os.path.exists(backup_info.location)
        
        # Delete backup
        success = await backup_manager.delete_backup(backup_info)
        assert success is True
        assert not os.path.exists(backup_info.location)
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_backups(self, backup_manager, system_config, temp_dir):
        """Test cleanup of expired backups."""
        backups = []
        
        # Create test backups with different ages
        for i in range(3):
            test_file = os.path.join(temp_dir, f"test_file_{i}.txt")
            with open(test_file, "w") as f:
                f.write(f"test content {i}")
            
            options = {"source_paths": [test_file]}
            backup_info = await backup_manager.create_backup(
                system_config, "files", options
            )
            
            # Make some backups appear old
            if i < 2:
                backup_info.created_at = datetime.utcnow() - timedelta(days=35)
            
            backups.append(backup_info)
        
        # Cleanup expired backups
        deleted_backups = await backup_manager.cleanup_expired_backups(backups)
        
        # Should delete the old backups (retention policy: max_age_days=30)
        assert len(deleted_backups) == 2
    
    @pytest.mark.asyncio
    async def test_get_storage_stats(self, backup_manager, system_config, temp_dir):
        """Test getting storage statistics."""
        # Create test backup
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        options = {"source_paths": [test_file]}
        await backup_manager.create_backup(system_config, "files", options)
        
        # Get storage stats
        stats = await backup_manager.get_storage_stats()
        
        assert "total_backups" in stats
        assert "total_size" in stats
        assert "backup_types" in stats
        assert stats["total_backups"] >= 1
    
    @pytest.mark.asyncio
    async def test_estimate_backup_size(self, backup_manager, system_config, temp_dir):
        """Test backup size estimation."""
        # Create test files
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content" * 1000)  # Make it larger
        
        options = {"source_paths": [test_file], "compression": "gzip"}
        
        estimate = await backup_manager.estimate_backup_size(
            system_config, "files", options
        )
        
        assert "estimated_size" in estimate
        assert "estimated_duration" in estimate
        assert "compression_ratio" in estimate
        assert estimate["estimated_size"] > 0
        assert estimate["estimated_duration"] > 0
    
    def test_create_backup_strategy(self, backup_manager, system_config, db_config):
        """Test backup strategy creation."""
        # Test file strategy
        file_strategy = backup_manager._create_backup_strategy(system_config, "files")
        assert isinstance(file_strategy, FileBackupStrategy)
        
        # Test database strategy
        db_strategy = backup_manager._create_backup_strategy(system_config, "database", db_config)
        assert db_strategy is not None
        
        # Test unsupported strategy
        with pytest.raises(BackupError):
            backup_manager._create_backup_strategy(system_config, "unsupported")
    
    @pytest.mark.asyncio
    async def test_backup_error_handling(self, backup_manager, system_config):
        """Test error handling in backup operations."""
        # Test backup with invalid source paths
        options = {"source_paths": ["/nonexistent/path"]}
        
        with pytest.raises(BackupError):
            await backup_manager.create_backup(system_config, "files", options)
    
    def test_logging(self, backup_manager, system_config):
        """Test backup operation logging."""
        # Clear existing logs
        backup_manager.clear_logs()
        
        # Perform an operation that generates logs
        backup_manager._log("INFO", "Test log message", "test_backup_id")
        
        # Check logs
        logs = backup_manager.get_logs()
        assert len(logs) == 1
        assert logs[0].message == "Test log message"
        assert logs[0].details["backup_id"] == "test_backup_id"
        
        # Test filtered logs
        filtered_logs = backup_manager.get_logs("test_backup_id")
        assert len(filtered_logs) == 1
        
        # Clear logs
        backup_manager.clear_logs()
        assert len(backup_manager.get_logs()) == 0


class TestBackupStorage:
    """Test cases for BackupStorage."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def retention_policy(self):
        """Create a retention policy for testing."""
        return RetentionPolicy(max_backups=3, max_age_days=7)
    
    @pytest.fixture
    def backup_storage(self, temp_dir, retention_policy):
        """Create a backup storage instance for testing."""
        return BackupStorage(temp_dir, retention_policy)
    
    def test_get_backup_path(self, backup_storage):
        """Test backup path generation."""
        path = backup_storage.get_backup_path("files", "wordpress")
        assert "files" in path
        assert "wordpress" in path
        assert os.path.exists(path)
    
    def test_get_temp_path(self, backup_storage):
        """Test temporary path generation."""
        temp_path = backup_storage.get_temp_path()
        assert "temp" in temp_path
        assert os.path.exists(temp_path)
    
    @pytest.mark.asyncio
    async def test_store_backup(self, backup_storage, temp_dir):
        """Test backup storage."""
        # Create a test backup file
        test_backup = os.path.join(temp_dir, "test_backup.tar.gz")
        with open(test_backup, "w") as f:
            f.write("backup content")
        
        # Create backup info
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=test_backup,
            metadata={"backup_type": "files"}
        )
        
        # Store backup
        stored_path = await backup_storage.store_backup(backup_info, test_backup)
        
        assert os.path.exists(stored_path)
        assert backup_info.location == stored_path
    
    @pytest.mark.asyncio
    async def test_list_backups(self, backup_storage, temp_dir):
        """Test backup listing."""
        # Create test backup files
        backup_dir = backup_storage.get_backup_path("files", "wordpress")
        test_backup1 = os.path.join(backup_dir, "backup1.tar.gz")
        test_backup2 = os.path.join(backup_dir, "backup2.tar.gz")
        
        with open(test_backup1, "w") as f:
            f.write("backup1")
        with open(test_backup2, "w") as f:
            f.write("backup2")
        
        # List backups
        backups = await backup_storage.list_backups("files", "wordpress")
        
        assert len(backups) == 2
        assert any("backup1.tar.gz" in b for b in backups)
        assert any("backup2.tar.gz" in b for b in backups)
    
    @pytest.mark.asyncio
    async def test_get_storage_stats(self, backup_storage, temp_dir):
        """Test storage statistics."""
        # Create test backup files
        backup_dir = backup_storage.get_backup_path("files", "wordpress")
        test_backup = os.path.join(backup_dir, "backup.tar.gz")
        
        with open(test_backup, "w") as f:
            f.write("backup content")
        
        # Get stats
        stats = await backup_storage.get_storage_stats()
        
        assert "total_backups" in stats
        assert "total_size" in stats
        assert "backup_types" in stats
        assert stats["total_backups"] >= 1
    
    @pytest.mark.asyncio
    async def test_cleanup_temp_files(self, backup_storage):
        """Test temporary file cleanup."""
        import time
        
        # Create temporary files
        temp_dir = backup_storage.get_temp_path()
        temp_file = os.path.join(temp_dir, "temp_file.txt")
        
        with open(temp_file, "w") as f:
            f.write("temp content")
        
        # Make the file appear old by modifying its timestamp
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        os.utime(temp_file, (old_time, old_time))
        
        # Verify file exists and has old timestamp
        assert os.path.exists(temp_file)
        file_stat = os.stat(temp_file)
        assert file_stat.st_mtime < (time.time() - 24 * 3600)
        
        # Cleanup temp files
        deleted_count = await backup_storage.cleanup_temp_files(max_age_hours=24)
        
        assert deleted_count >= 1
        assert not os.path.exists(temp_file)


class TestRetentionPolicy:
    """Test cases for RetentionPolicy."""
    
    def test_should_retain_max_backups(self):
        """Test retention based on maximum backup count."""
        policy = RetentionPolicy(max_backups=2)
        
        # Create test backups
        backups = []
        for i in range(3):
            backup = BackupInfo(
                id=f"backup_{i}",
                type=BackupType.FULL,
                source_system="test",
                location=f"/path/backup_{i}",
                created_at=datetime.utcnow() - timedelta(hours=i)
            )
            backups.append(backup)
        
        # Test retention (should keep 2 newest)
        assert policy.should_retain(backups[0], backups) is True  # Newest
        assert policy.should_retain(backups[1], backups) is True  # Second newest
        assert policy.should_retain(backups[2], backups) is False  # Oldest
    
    def test_should_retain_max_age(self):
        """Test retention based on maximum age."""
        policy = RetentionPolicy(max_age_days=7)
        
        # Create test backups
        old_backup = BackupInfo(
            id="old_backup",
            type=BackupType.FULL,
            source_system="test",
            location="/path/old_backup",
            created_at=datetime.utcnow() - timedelta(days=10)
        )
        
        new_backup = BackupInfo(
            id="new_backup",
            type=BackupType.FULL,
            source_system="test",
            location="/path/new_backup",
            created_at=datetime.utcnow() - timedelta(days=3)
        )
        
        backups = [old_backup, new_backup]
        
        # Test retention
        assert policy.should_retain(old_backup, backups) is False  # Too old
        assert policy.should_retain(new_backup, backups) is True   # Within age limit