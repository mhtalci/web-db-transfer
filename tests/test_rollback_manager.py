"""
Integration tests for the rollback manager.
"""

import asyncio
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from migration_assistant.checkup.backup_manager import BackupInfo, BackupManager
from migration_assistant.checkup.rollback_manager import (
    RecoveryValidator,
    RollbackManager,
    RollbackOperation,
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
    
    return source_dir


@pytest.fixture
async def backup_manager_with_backup(sample_config, sample_files):
    """Create a backup manager with an existing backup."""
    manager = BackupManager(sample_config)
    backup_info = await manager.create_full_backup()
    return manager, backup_info


class TestRollbackOperation:
    """Test RollbackOperation class."""
    
    def test_rollback_operation_creation(self, temp_dir):
        """Test creating RollbackOperation object."""
        affected_files = [temp_dir / "file1.py", temp_dir / "file2.py"]
        
        operation = RollbackOperation(
            operation_id="test_op",
            operation_type="cleanup",
            backup_id="backup_123",
            affected_files=affected_files,
            metadata={"test": "value"}
        )
        
        assert operation.operation_id == "test_op"
        assert operation.operation_type == "cleanup"
        assert operation.backup_id == "backup_123"
        assert operation.affected_files == affected_files
        assert operation.metadata == {"test": "value"}
        assert not operation.rollback_completed
        assert operation.rollback_timestamp is None
        assert operation.rollback_errors == []
    
    def test_rollback_operation_to_dict(self, temp_dir):
        """Test converting RollbackOperation to dictionary."""
        affected_files = [temp_dir / "file1.py"]
        
        operation = RollbackOperation(
            operation_id="test_op",
            operation_type="cleanup",
            backup_id="backup_123",
            affected_files=affected_files
        )
        
        data = operation.to_dict()
        
        assert data["operation_id"] == "test_op"
        assert data["operation_type"] == "cleanup"
        assert data["backup_id"] == "backup_123"
        assert data["affected_files"] == [str(temp_dir / "file1.py")]
        assert not data["rollback_completed"]
        assert data["rollback_timestamp"] is None
    
    def test_rollback_operation_from_dict(self, temp_dir):
        """Test creating RollbackOperation from dictionary."""
        data = {
            "operation_id": "test_op",
            "operation_type": "cleanup",
            "backup_id": "backup_123",
            "affected_files": [str(temp_dir / "file1.py")],
            "timestamp": "2023-01-01T12:00:00",
            "metadata": {"test": "value"},
            "rollback_completed": True,
            "rollback_timestamp": "2023-01-01T13:00:00",
            "rollback_errors": ["error1"]
        }
        
        operation = RollbackOperation.from_dict(data)
        
        assert operation.operation_id == "test_op"
        assert operation.operation_type == "cleanup"
        assert operation.backup_id == "backup_123"
        assert operation.affected_files == [temp_dir / "file1.py"]
        assert operation.metadata == {"test": "value"}
        assert operation.rollback_completed
        assert operation.rollback_timestamp == datetime(2023, 1, 1, 13, 0, 0)
        assert operation.rollback_errors == ["error1"]


class TestRecoveryValidator:
    """Test RecoveryValidator class."""
    
    def test_recovery_validator_initialization(self, sample_config):
        """Test RecoveryValidator initialization."""
        validator = RecoveryValidator(sample_config)
        assert validator.config == sample_config
    
    def test_can_overwrite_file(self, sample_config, sample_files):
        """Test file overwrite capability check."""
        validator = RecoveryValidator(sample_config)
        
        # Existing writable file
        test_file = sample_files / "main.py"
        assert validator._can_overwrite_file(test_file)
        
        # Non-existent file
        non_existent = sample_files / "non_existent.py"
        assert not validator._can_overwrite_file(non_existent)
    
    @pytest.mark.asyncio
    async def test_verify_backup_integrity_valid(self, sample_config, backup_manager_with_backup):
        """Test backup integrity verification with valid backup."""
        manager, backup_info = backup_manager_with_backup
        validator = RecoveryValidator(sample_config)
        
        is_valid = await validator._verify_backup_integrity(backup_info)
        assert is_valid
    
    @pytest.mark.asyncio
    async def test_verify_backup_integrity_missing_file(self, sample_config, backup_manager_with_backup):
        """Test backup integrity verification with missing file."""
        manager, backup_info = backup_manager_with_backup
        validator = RecoveryValidator(sample_config)
        
        # Delete the backup file
        backup_info.backup_path.unlink()
        
        is_valid = await validator._verify_backup_integrity(backup_info)
        assert not is_valid
    
    @pytest.mark.asyncio
    async def test_check_disk_space(self, sample_config, backup_manager_with_backup):
        """Test disk space checking."""
        manager, backup_info = backup_manager_with_backup
        validator = RecoveryValidator(sample_config)
        
        has_space = await validator._check_disk_space(backup_info)
        assert has_space  # Should have enough space for small test backup
    
    @pytest.mark.asyncio
    async def test_validate_recovery_preconditions_valid(self, sample_config, backup_manager_with_backup, sample_files):
        """Test recovery preconditions validation with valid conditions."""
        manager, backup_info = backup_manager_with_backup
        validator = RecoveryValidator(sample_config)
        
        target_files = [sample_files / "main.py", sample_files / "utils.py"]
        
        is_valid, errors = await validator.validate_recovery_preconditions(backup_info, target_files)
        assert is_valid
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_recovery_preconditions_missing_backup(self, sample_config, sample_files):
        """Test recovery preconditions validation with missing backup."""
        validator = RecoveryValidator(sample_config)
        
        # Create fake backup info with non-existent file
        backup_info = BackupInfo(
            backup_id="fake",
            backup_type="full",
            source_path=sample_files,
            backup_path=Path("/non/existent/backup.tar.gz"),
            checksum="fake",
            size=1024
        )
        
        target_files = [sample_files / "main.py"]
        
        is_valid, errors = await validator.validate_recovery_preconditions(backup_info, target_files)
        assert not is_valid
        assert len(errors) > 0
        assert any("not found" in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_validate_post_recovery(self, sample_config, sample_files):
        """Test post-recovery validation."""
        validator = RecoveryValidator(sample_config)
        
        # Test with existing files
        recovered_files = [sample_files / "main.py", sample_files / "utils.py"]
        
        is_valid, errors = await validator.validate_post_recovery(recovered_files)
        assert is_valid
        assert len(errors) == 0
        
        # Test with missing files
        missing_files = [sample_files / "non_existent.py"]
        
        is_valid, errors = await validator.validate_post_recovery(missing_files)
        assert not is_valid
        assert len(errors) > 0


class TestRollbackManager:
    """Test RollbackManager class."""
    
    def test_rollback_manager_initialization(self, sample_config):
        """Test RollbackManager initialization."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        assert rollback_manager.config == sample_config
        assert rollback_manager.backup_manager == backup_manager
        assert isinstance(rollback_manager.validator, RecoveryValidator)
        assert rollback_manager.rollback_dir.exists()
    
    def test_generate_operation_id(self, sample_config):
        """Test operation ID generation."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        op_id = rollback_manager._generate_operation_id()
        assert op_id.startswith("rollback_op_")
        assert len(op_id) > len("rollback_op_")
    
    @pytest.mark.asyncio
    async def test_register_operation(self, sample_config, sample_files):
        """Test registering a rollback operation."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Create a backup first
        backup_info = await backup_manager.create_full_backup()
        
        affected_files = [sample_files / "main.py", sample_files / "utils.py"]
        metadata = {"test": "value"}
        
        op_id = await rollback_manager.register_operation(
            operation_type="cleanup",
            backup_id=backup_info.backup_id,
            affected_files=affected_files,
            metadata=metadata
        )
        
        assert op_id.startswith("rollback_op_")
        
        # Verify operation was registered
        operation = rollback_manager.get_rollback_operation(op_id)
        assert operation is not None
        assert operation.operation_type == "cleanup"
        assert operation.backup_id == backup_info.backup_id
        assert operation.affected_files == affected_files
        assert operation.metadata == metadata
    
    @pytest.mark.asyncio
    async def test_automatic_rollback_success(self, sample_config, sample_files):
        """Test successful automatic rollback."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Create a pre-cleanup backup
        files_to_modify = [sample_files / "main.py"]
        backup_info = await backup_manager.create_pre_cleanup_backup(files_to_modify)
        
        # Register operation
        op_id = await rollback_manager.register_operation(
            operation_type="cleanup",
            backup_id=backup_info.backup_id,
            affected_files=files_to_modify
        )
        
        # Modify the file to simulate cleanup
        (sample_files / "main.py").write_text("# Modified content")
        
        # Perform automatic rollback
        success = await rollback_manager.automatic_rollback(op_id, "Test error")
        assert success
        
        # Verify operation was marked as completed
        operation = rollback_manager.get_rollback_operation(op_id)
        assert operation.rollback_completed
        assert operation.rollback_timestamp is not None
        
        # Verify file was restored
        restored_content = (sample_files / "main.py").read_text()
        assert restored_content == "print('Hello, World!')"
    
    @pytest.mark.asyncio
    async def test_automatic_rollback_nonexistent_operation(self, sample_config):
        """Test automatic rollback with non-existent operation."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        success = await rollback_manager.automatic_rollback("non_existent_op")
        assert not success
    
    @pytest.mark.asyncio
    async def test_manual_rollback_by_operation_id(self, sample_config, sample_files):
        """Test manual rollback using operation ID."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Create a pre-cleanup backup
        files_to_modify = [sample_files / "main.py"]
        backup_info = await backup_manager.create_pre_cleanup_backup(files_to_modify)
        
        # Register operation
        op_id = await rollback_manager.register_operation(
            operation_type="cleanup",
            backup_id=backup_info.backup_id,
            affected_files=files_to_modify
        )
        
        # Modify the file
        (sample_files / "main.py").write_text("# Modified content")
        
        # Perform manual rollback
        success = await rollback_manager.manual_rollback(operation_id=op_id)
        assert success
        
        # Verify file was restored
        restored_content = (sample_files / "main.py").read_text()
        assert restored_content == "print('Hello, World!')"
    
    @pytest.mark.asyncio
    async def test_manual_rollback_by_backup_id(self, sample_config, sample_files):
        """Test manual rollback using backup ID."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Create a full backup
        backup_info = await backup_manager.create_full_backup()
        
        # Modify files
        (sample_files / "main.py").write_text("# Modified content")
        (sample_files / "utils.py").write_text("# Modified utils")
        
        # Perform manual rollback
        target_files = [sample_files / "main.py", sample_files / "utils.py"]
        success = await rollback_manager.manual_rollback(
            backup_id=backup_info.backup_id,
            target_files=target_files
        )
        assert success
        
        # Verify files were restored
        main_content = (sample_files / "main.py").read_text()
        utils_content = (sample_files / "utils.py").read_text()
        assert main_content == "print('Hello, World!')"
        assert utils_content == "def helper(): pass"
    
    def test_list_rollback_operations(self, sample_config):
        """Test listing rollback operations."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Initially no operations
        operations = rollback_manager.list_rollback_operations()
        assert len(operations) == 0
        
        # Add mock operations
        op1 = RollbackOperation(
            "op1", "cleanup", "backup1", [Path("/file1.py")]
        )
        op2 = RollbackOperation(
            "op2", "formatting", "backup2", [Path("/file2.py")]
        )
        op2.rollback_completed = True
        
        rollback_manager._rollback_operations["op1"] = op1
        rollback_manager._rollback_operations["op2"] = op2
        
        # List all operations
        all_ops = rollback_manager.list_rollback_operations()
        assert len(all_ops) == 2
        
        # List by operation type
        cleanup_ops = rollback_manager.list_rollback_operations(operation_type="cleanup")
        assert len(cleanup_ops) == 1
        assert cleanup_ops[0].operation_type == "cleanup"
        
        # List completed only
        completed_ops = rollback_manager.list_rollback_operations(completed_only=True)
        assert len(completed_ops) == 1
        assert completed_ops[0].rollback_completed
    
    def test_get_rollback_operation(self, sample_config):
        """Test getting rollback operation by ID."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Non-existent operation
        operation = rollback_manager.get_rollback_operation("non_existent")
        assert operation is None
        
        # Add mock operation
        mock_op = RollbackOperation(
            "test_op", "cleanup", "backup1", [Path("/file1.py")]
        )
        rollback_manager._rollback_operations["test_op"] = mock_op
        
        # Get existing operation
        retrieved_op = rollback_manager.get_rollback_operation("test_op")
        assert retrieved_op == mock_op
    
    @pytest.mark.asyncio
    async def test_cleanup_old_operations(self, sample_config):
        """Test cleaning up old rollback operations."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Add old and recent operations
        old_op = RollbackOperation(
            "old_op", "cleanup", "backup1", [Path("/file1.py")],
            timestamp=datetime.now() - timedelta(days=35)
        )
        recent_op = RollbackOperation(
            "recent_op", "cleanup", "backup2", [Path("/file2.py")],
            timestamp=datetime.now() - timedelta(days=5)
        )
        
        rollback_manager._rollback_operations["old_op"] = old_op
        rollback_manager._rollback_operations["recent_op"] = recent_op
        
        # Cleanup operations older than 30 days
        deleted = await rollback_manager.cleanup_old_operations(max_age_days=30)
        
        assert "old_op" in deleted
        assert "recent_op" not in deleted
        assert "old_op" not in rollback_manager._rollback_operations
        assert "recent_op" in rollback_manager._rollback_operations
    
    def test_get_rollback_statistics_empty(self, sample_config):
        """Test getting rollback statistics with no operations."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        stats = rollback_manager.get_rollback_statistics()
        
        assert stats["total_operations"] == 0
        assert stats["completed_rollbacks"] == 0
        assert stats["failed_rollbacks"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["operation_types"] == {}
        assert stats["recent_operations"] == 0
    
    def test_get_rollback_statistics_with_operations(self, sample_config):
        """Test getting rollback statistics with operations."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Add mock operations
        op1 = RollbackOperation(
            "op1", "cleanup", "backup1", [Path("/file1.py")],
            timestamp=datetime.now() - timedelta(days=1)
        )
        op1.rollback_completed = True
        
        op2 = RollbackOperation(
            "op2", "formatting", "backup2", [Path("/file2.py")],
            timestamp=datetime.now() - timedelta(days=2)
        )
        # op2 not completed (failed)
        
        rollback_manager._rollback_operations["op1"] = op1
        rollback_manager._rollback_operations["op2"] = op2
        
        stats = rollback_manager.get_rollback_statistics()
        
        assert stats["total_operations"] == 2
        assert stats["completed_rollbacks"] == 1
        assert stats["failed_rollbacks"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["operation_types"]["cleanup"]["total"] == 1
        assert stats["operation_types"]["cleanup"]["completed"] == 1
        assert stats["operation_types"]["formatting"]["total"] == 1
        assert stats["operation_types"]["formatting"]["completed"] == 0
        assert stats["recent_operations"] == 2  # Both within 7 days
    
    @pytest.mark.asyncio
    async def test_verify_rollback_capability_valid(self, sample_config, sample_files):
        """Test verifying rollback capability for valid operation."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Create backup and register operation
        backup_info = await backup_manager.create_full_backup()
        op_id = await rollback_manager.register_operation(
            "cleanup", backup_info.backup_id, [sample_files / "main.py"]
        )
        
        can_rollback, errors = await rollback_manager.verify_rollback_capability(op_id)
        assert can_rollback
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_verify_rollback_capability_nonexistent(self, sample_config):
        """Test verifying rollback capability for non-existent operation."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        can_rollback, errors = await rollback_manager.verify_rollback_capability("non_existent")
        assert not can_rollback
        assert "Operation not found" in errors
    
    @pytest.mark.asyncio
    async def test_create_recovery_plan(self, sample_config, sample_files):
        """Test creating recovery plan."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Create backup and register operation
        backup_info = await backup_manager.create_full_backup()
        op_id = await rollback_manager.register_operation(
            "cleanup", backup_info.backup_id, [sample_files / "main.py"]
        )
        
        plan = await rollback_manager.create_recovery_plan(op_id)
        
        assert plan is not None
        assert plan["operation_id"] == op_id
        assert plan["operation_type"] == "cleanup"
        assert plan["backup_id"] == backup_info.backup_id
        assert plan["backup_type"] == "full"
        assert plan["can_rollback"] is True
        assert "steps" in plan
        assert len(plan["steps"]) > 0
    
    @pytest.mark.asyncio
    async def test_create_recovery_plan_nonexistent(self, sample_config):
        """Test creating recovery plan for non-existent operation."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        plan = await rollback_manager.create_recovery_plan("non_existent")
        assert plan is None
    
    def test_estimate_rollback_duration(self, sample_config):
        """Test rollback duration estimation."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Small backup
        small_backup = BackupInfo(
            "small", "full", Path("/src"), Path("/backup.tar.gz"), "checksum", 1024 * 1024  # 1MB
        )
        duration = rollback_manager._estimate_rollback_duration(small_backup)
        assert duration >= 5  # Minimum 5 seconds
        
        # Large backup
        large_backup = BackupInfo(
            "large", "full", Path("/src"), Path("/backup.tar.gz"), "checksum", 100 * 1024 * 1024  # 100MB
        )
        duration = rollback_manager._estimate_rollback_duration(large_backup)
        assert duration > 5  # Should be more than minimum
    
    def test_operations_persistence(self, sample_config, temp_dir):
        """Test rollback operations persistence."""
        backup_manager = BackupManager(sample_config)
        rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Add an operation
        operation = RollbackOperation(
            "test_op", "cleanup", "backup1", [Path("/file1.py")]
        )
        rollback_manager._rollback_operations["test_op"] = operation
        rollback_manager._save_operations()
        
        # Create new manager instance (should load operations)
        new_rollback_manager = RollbackManager(sample_config, backup_manager)
        
        # Verify operation was loaded
        loaded_op = new_rollback_manager.get_rollback_operation("test_op")
        assert loaded_op is not None
        assert loaded_op.operation_id == "test_op"
        assert loaded_op.operation_type == "cleanup"


if __name__ == "__main__":
    pytest.main([__file__])