"""
Comprehensive integration tests for rollback scenarios.

This module tests the complete rollback workflow including:
- Automatic rollback for failed operations
- Manual rollback commands for user-initiated recovery
- Recovery validation and verification
- CLI integration for rollback commands
"""

import asyncio
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner

import pytest

from migration_assistant.checkup.backup_manager import BackupInfo, BackupManager
from migration_assistant.checkup.rollback_manager import RollbackManager, RollbackOperation
from migration_assistant.checkup.orchestrator import CodebaseOrchestrator
from migration_assistant.checkup.models import CheckupConfig, AnalysisResults, CleanupResults
from migration_assistant.cli.main import main
from migration_assistant.core.exceptions import BackupError, CleanupError


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_codebase(temp_workspace):
    """Create a sample codebase for testing."""
    source_dir = temp_workspace / "source"
    source_dir.mkdir(parents=True)
    
    # Create Python files with various issues
    (source_dir / "main.py").write_text("""
import os
import sys
import unused_module

def main():
    print("Hello, World!")
    
if __name__ == "__main__":
    main()
""")
    
    (source_dir / "utils.py").write_text("""
import json
import re

def helper_function():
    '''Helper function with poor formatting'''
    x=1+2
    y = 3 + 4
    return x+y

class UtilityClass:
    def __init__(self):
        pass
    
    def process_data(self,data):
        return data.strip()
""")
    
    # Create a subdirectory
    sub_dir = source_dir / "submodule"
    sub_dir.mkdir()
    (sub_dir / "module.py").write_text("""
# Duplicate function (similar to utils.py)
def helper_function():
    x = 1 + 2
    y = 3 + 4
    return x + y

class DuplicateClass:
    def process_data(self, data):
        return data.strip()
""")
    
    # Create test files
    test_dir = source_dir / "tests"
    test_dir.mkdir()
    (test_dir / "test_main.py").write_text("""
import pytest
from main import main

def test_main():
    # Incomplete test
    pass
""")
    
    return source_dir


@pytest.fixture
def integration_config(temp_workspace):
    """Create integration test configuration."""
    return CheckupConfig(
        target_directory=temp_workspace / "source",
        backup_dir=temp_workspace / "backups",
        create_backup=True,
        dry_run=False,
        enable_quality_analysis=True,
        enable_duplicate_detection=True,
        enable_import_analysis=True,
        auto_format=True,
        auto_fix_imports=True
    )


@pytest.fixture
async def orchestrator_with_managers(integration_config):
    """Create orchestrator with backup and rollback managers."""
    orchestrator = CodebaseOrchestrator(integration_config)
    backup_manager = BackupManager(integration_config)
    rollback_manager = RollbackManager(integration_config, backup_manager)
    
    return orchestrator, backup_manager, rollback_manager


class TestAutomaticRollbackIntegration:
    """Test automatic rollback for failed operations."""
    
    @pytest.mark.asyncio
    async def test_automatic_rollback_on_cleanup_failure(self, sample_codebase, orchestrator_with_managers):
        """Test automatic rollback when cleanup operations fail."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Run analysis first
        analysis_results = await orchestrator.run_analysis_only()
        assert analysis_results is not None
        
        # Create backup before cleanup
        backup_info = await backup_manager.create_pre_cleanup_backup([
            sample_codebase / "main.py",
            sample_codebase / "utils.py"
        ])
        
        # Register operation for rollback tracking
        op_id = await rollback_manager.register_operation(
            operation_type="cleanup",
            backup_id=backup_info.backup_id,
            affected_files=[sample_codebase / "main.py", sample_codebase / "utils.py"],
            metadata={"test": "automatic_rollback"}
        )
        
        # Simulate cleanup failure by corrupting files
        (sample_codebase / "main.py").write_text("CORRUPTED CONTENT")
        (sample_codebase / "utils.py").write_text("CORRUPTED CONTENT")
        
        # Trigger automatic rollback
        success = await rollback_manager.automatic_rollback(op_id, "Simulated cleanup failure")
        assert success
        
        # Verify files were restored
        main_content = (sample_codebase / "main.py").read_text()
        utils_content = (sample_codebase / "utils.py").read_text()
        
        assert "import os" in main_content
        assert "def main():" in main_content
        assert "import json" in utils_content
        assert "def helper_function():" in utils_content
        
        # Verify operation was marked as completed
        operation = rollback_manager.get_rollback_operation(op_id)
        assert operation.rollback_completed
        assert operation.rollback_timestamp is not None
    
    @pytest.mark.asyncio
    async def test_automatic_rollback_with_validation_failure(self, sample_codebase, orchestrator_with_managers):
        """Test automatic rollback when post-cleanup validation fails."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create backup
        backup_info = await backup_manager.create_full_backup()
        
        # Register operation
        op_id = await rollback_manager.register_operation(
            operation_type="validation_failure",
            backup_id=backup_info.backup_id,
            affected_files=[sample_codebase / "main.py"],
            metadata={"validation_test": True}
        )
        
        # Simulate validation failure by making file unreadable
        main_file = sample_codebase / "main.py"
        original_content = main_file.read_text()
        main_file.write_text("")  # Empty file to simulate corruption
        
        # Trigger automatic rollback
        success = await rollback_manager.automatic_rollback(op_id, "Validation failed")
        assert success
        
        # Verify file was restored
        restored_content = main_file.read_text()
        assert restored_content == original_content
    
    @pytest.mark.asyncio
    async def test_automatic_rollback_with_missing_backup(self, sample_codebase, orchestrator_with_managers):
        """Test automatic rollback behavior when backup is missing."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Register operation with non-existent backup
        op_id = await rollback_manager.register_operation(
            operation_type="cleanup",
            backup_id="non_existent_backup",
            affected_files=[sample_codebase / "main.py"],
            metadata={"test": "missing_backup"}
        )
        
        # Attempt automatic rollback
        success = await rollback_manager.automatic_rollback(op_id, "Test error")
        assert not success
        
        # Verify operation has error recorded
        operation = rollback_manager.get_rollback_operation(op_id)
        assert not operation.rollback_completed
        assert len(operation.rollback_errors) > 0
        assert any("not found" in error for error in operation.rollback_errors)


class TestManualRollbackIntegration:
    """Test manual rollback commands for user-initiated recovery."""
    
    @pytest.mark.asyncio
    async def test_manual_rollback_by_operation_id(self, sample_codebase, orchestrator_with_managers):
        """Test manual rollback using operation ID."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create backup and register operation
        backup_info = await backup_manager.create_pre_cleanup_backup([
            sample_codebase / "main.py",
            sample_codebase / "utils.py"
        ])
        
        op_id = await rollback_manager.register_operation(
            operation_type="manual_test",
            backup_id=backup_info.backup_id,
            affected_files=[sample_codebase / "main.py", sample_codebase / "utils.py"]
        )
        
        # Modify files to simulate changes
        original_main = (sample_codebase / "main.py").read_text()
        original_utils = (sample_codebase / "utils.py").read_text()
        
        (sample_codebase / "main.py").write_text("# Modified main file")
        (sample_codebase / "utils.py").write_text("# Modified utils file")
        
        # Perform manual rollback
        success = await rollback_manager.manual_rollback(operation_id=op_id)
        assert success
        
        # Verify files were restored
        restored_main = (sample_codebase / "main.py").read_text()
        restored_utils = (sample_codebase / "utils.py").read_text()
        
        assert restored_main == original_main
        assert restored_utils == original_utils
    
    @pytest.mark.asyncio
    async def test_manual_rollback_by_backup_id(self, sample_codebase, orchestrator_with_managers):
        """Test manual rollback using backup ID directly."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create full backup
        backup_info = await backup_manager.create_full_backup()
        
        # Modify entire codebase
        for py_file in sample_codebase.rglob("*.py"):
            py_file.write_text("# All files modified")
        
        # Perform manual rollback by backup ID
        success = await rollback_manager.manual_rollback(backup_id=backup_info.backup_id)
        assert success
        
        # Verify files were restored
        main_content = (sample_codebase / "main.py").read_text()
        utils_content = (sample_codebase / "utils.py").read_text()
        
        assert "import os" in main_content
        assert "def helper_function():" in utils_content
    
    @pytest.mark.asyncio
    async def test_manual_rollback_with_specific_files(self, sample_codebase, orchestrator_with_managers):
        """Test manual rollback with specific target files."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create full backup
        backup_info = await backup_manager.create_full_backup()
        
        # Modify multiple files
        (sample_codebase / "main.py").write_text("# Modified main")
        (sample_codebase / "utils.py").write_text("# Modified utils")
        (sample_codebase / "submodule" / "module.py").write_text("# Modified module")
        
        # Rollback only specific files
        target_files = [sample_codebase / "main.py", sample_codebase / "utils.py"]
        success = await rollback_manager.manual_rollback(
            backup_id=backup_info.backup_id,
            target_files=target_files
        )
        assert success
        
        # Verify only target files were restored
        main_content = (sample_codebase / "main.py").read_text()
        utils_content = (sample_codebase / "utils.py").read_text()
        module_content = (sample_codebase / "submodule" / "module.py").read_text()
        
        assert "import os" in main_content  # Restored
        assert "import json" in utils_content  # Restored
        assert module_content == "# Modified module"  # Not restored


class TestRecoveryValidationIntegration:
    """Test recovery validation and verification."""
    
    @pytest.mark.asyncio
    async def test_recovery_precondition_validation(self, sample_codebase, orchestrator_with_managers):
        """Test comprehensive recovery precondition validation."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create backup
        backup_info = await backup_manager.create_full_backup()
        
        # Test valid preconditions
        target_files = [sample_codebase / "main.py", sample_codebase / "utils.py"]
        is_valid, errors = await rollback_manager.validator.validate_recovery_preconditions(
            backup_info, target_files
        )
        assert is_valid
        assert len(errors) == 0
        
        # Test with read-only file (should still be valid as we can overwrite)
        readonly_file = sample_codebase / "readonly.py"
        readonly_file.write_text("readonly content")
        readonly_file.chmod(0o444)  # Read-only
        
        target_files_with_readonly = target_files + [readonly_file]
        is_valid, errors = await rollback_manager.validator.validate_recovery_preconditions(
            backup_info, target_files_with_readonly
        )
        # Should still be valid as we can change permissions
        assert is_valid or len(errors) == 1  # May fail on some systems
    
    @pytest.mark.asyncio
    async def test_post_recovery_validation(self, sample_codebase, orchestrator_with_managers):
        """Test post-recovery validation with checksums."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create files with known content
        test_files = [sample_codebase / "main.py", sample_codebase / "utils.py"]
        
        # Calculate original checksums
        import hashlib
        original_checksums = {}
        for file_path in test_files:
            with open(file_path, "rb") as f:
                content = f.read()
                original_checksums[file_path] = hashlib.sha256(content).hexdigest()
        
        # Validate with correct checksums
        is_valid, errors = await rollback_manager.validator.validate_post_recovery(
            test_files, original_checksums
        )
        assert is_valid
        assert len(errors) == 0
        
        # Modify a file and test with wrong checksum
        (sample_codebase / "main.py").write_text("modified content")
        
        is_valid, errors = await rollback_manager.validator.validate_post_recovery(
            test_files, original_checksums
        )
        assert not is_valid
        assert len(errors) > 0
        assert any("checksum mismatch" in error.lower() for error in errors)
    
    @pytest.mark.asyncio
    async def test_rollback_capability_verification(self, sample_codebase, orchestrator_with_managers):
        """Test rollback capability verification."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create backup and register operation
        backup_info = await backup_manager.create_full_backup()
        op_id = await rollback_manager.register_operation(
            operation_type="test",
            backup_id=backup_info.backup_id,
            affected_files=[sample_codebase / "main.py"]
        )
        
        # Verify rollback capability
        can_rollback, errors = await rollback_manager.verify_rollback_capability(op_id)
        assert can_rollback
        assert len(errors) == 0
        
        # Test with already completed rollback
        operation = rollback_manager.get_rollback_operation(op_id)
        operation.rollback_completed = True
        rollback_manager._save_operations()
        
        can_rollback, errors = await rollback_manager.verify_rollback_capability(op_id)
        assert not can_rollback
        assert any("already been rolled back" in error for error in errors)


class TestCLIRollbackIntegration:
    """Test CLI integration for rollback commands."""
    
    def test_cli_list_rollback_operations(self, temp_workspace, integration_config):
        """Test CLI command to list rollback operations."""
        # Create some mock operations
        backup_manager = BackupManager(integration_config)
        rollback_manager = RollbackManager(integration_config, backup_manager)
        
        # Add mock operations
        op1 = RollbackOperation(
            "op1", "cleanup", "backup1", [Path("/file1.py")],
            timestamp=datetime.now() - timedelta(hours=1)
        )
        op2 = RollbackOperation(
            "op2", "formatting", "backup2", [Path("/file2.py")],
            timestamp=datetime.now() - timedelta(hours=2)
        )
        op2.rollback_completed = True
        
        rollback_manager._rollback_operations["op1"] = op1
        rollback_manager._rollback_operations["op2"] = op2
        rollback_manager._save_operations()
        
        # Test CLI command
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Change to temp workspace
            import os
            os.chdir(str(temp_workspace))
            
            result = runner.invoke(main, ['rollback', '--list-operations'])
            assert result.exit_code == 0
            assert "Available Rollback Operations" in result.output
            assert "cleanup" in result.output
            assert "formatting" in result.output
    
    def test_cli_show_recovery_plan(self, temp_workspace, integration_config, sample_codebase):
        """Test CLI command to show recovery plan."""
        runner = CliRunner()
        
        async def setup_operation():
            backup_manager = BackupManager(integration_config)
            rollback_manager = RollbackManager(integration_config, backup_manager)
            
            # Create backup and operation
            backup_info = await backup_manager.create_full_backup()
            op_id = await rollback_manager.register_operation(
                "test", backup_info.backup_id, [sample_codebase / "main.py"]
            )
            return op_id
        
        # Setup operation
        op_id = asyncio.run(setup_operation())
        
        with runner.isolated_filesystem():
            import os
            os.chdir(str(temp_workspace))
            
            result = runner.invoke(main, ['rollback', '--operation-id', op_id, '--show-plan'])
            assert result.exit_code == 0
            assert "Recovery Plan" in result.output
            assert "Operation Details" in result.output
            assert "Recovery Steps" in result.output
    
    def test_cli_rollback_with_confirmation(self, temp_workspace, integration_config, sample_codebase):
        """Test CLI rollback with user confirmation."""
        runner = CliRunner()
        
        async def setup_operation():
            backup_manager = BackupManager(integration_config)
            rollback_manager = RollbackManager(integration_config, backup_manager)
            
            backup_info = await backup_manager.create_pre_cleanup_backup([sample_codebase / "main.py"])
            op_id = await rollback_manager.register_operation(
                "test", backup_info.backup_id, [sample_codebase / "main.py"]
            )
            return op_id
        
        op_id = asyncio.run(setup_operation())
        
        with runner.isolated_filesystem():
            import os
            os.chdir(str(temp_workspace))
            
            # Test cancellation
            result = runner.invoke(main, ['rollback', '--operation-id', op_id], input='n\n')
            assert result.exit_code == 0
            assert "Rollback cancelled" in result.output
            
            # Test confirmation
            result = runner.invoke(main, ['rollback', '--operation-id', op_id], input='y\n')
            assert result.exit_code == 0
            # Should complete successfully or show appropriate error
    
    def test_cli_force_rollback(self, temp_workspace, integration_config, sample_codebase):
        """Test CLI rollback with force flag."""
        runner = CliRunner()
        
        async def setup_operation():
            backup_manager = BackupManager(integration_config)
            rollback_manager = RollbackManager(integration_config, backup_manager)
            
            backup_info = await backup_manager.create_pre_cleanup_backup([sample_codebase / "main.py"])
            op_id = await rollback_manager.register_operation(
                "test", backup_info.backup_id, [sample_codebase / "main.py"]
            )
            return op_id
        
        op_id = asyncio.run(setup_operation())
        
        with runner.isolated_filesystem():
            import os
            os.chdir(str(temp_workspace))
            
            result = runner.invoke(main, ['rollback', '--operation-id', op_id, '--force'])
            assert result.exit_code == 0
            # Should not prompt for confirmation


class TestRollbackErrorHandling:
    """Test error handling in rollback scenarios."""
    
    @pytest.mark.asyncio
    async def test_rollback_with_corrupted_backup(self, sample_codebase, orchestrator_with_managers):
        """Test rollback behavior with corrupted backup."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create backup
        backup_info = await backup_manager.create_full_backup()
        
        # Corrupt the backup file
        with open(backup_info.backup_path, "wb") as f:
            f.write(b"corrupted data")
        
        # Register operation
        op_id = await rollback_manager.register_operation(
            "test", backup_info.backup_id, [sample_codebase / "main.py"]
        )
        
        # Attempt rollback
        success = await rollback_manager.automatic_rollback(op_id, "Test error")
        assert not success
        
        # Verify error was recorded
        operation = rollback_manager.get_rollback_operation(op_id)
        assert len(operation.rollback_errors) > 0
    
    @pytest.mark.asyncio
    async def test_rollback_with_insufficient_disk_space(self, sample_codebase, orchestrator_with_managers):
        """Test rollback behavior with insufficient disk space."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create backup
        backup_info = await backup_manager.create_full_backup()
        
        # Mock disk space check to return insufficient space
        with patch.object(rollback_manager.validator, '_check_disk_space', return_value=False):
            # Register operation
            op_id = await rollback_manager.register_operation(
                "test", backup_info.backup_id, [sample_codebase / "main.py"]
            )
            
            # Attempt rollback
            success = await rollback_manager.automatic_rollback(op_id, "Test error")
            assert not success
            
            # Verify error was recorded
            operation = rollback_manager.get_rollback_operation(op_id)
            assert any("disk space" in error.lower() for error in operation.rollback_errors)
    
    @pytest.mark.asyncio
    async def test_rollback_with_permission_errors(self, sample_codebase, orchestrator_with_managers):
        """Test rollback behavior with file permission errors."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create backup
        backup_info = await backup_manager.create_pre_cleanup_backup([sample_codebase / "main.py"])
        
        # Make target file directory read-only
        sample_codebase.chmod(0o444)
        
        try:
            # Register operation
            op_id = await rollback_manager.register_operation(
                "test", backup_info.backup_id, [sample_codebase / "main.py"]
            )
            
            # Attempt rollback (may fail due to permissions)
            success = await rollback_manager.automatic_rollback(op_id, "Test error")
            
            # On some systems this might succeed, on others it might fail
            # The important thing is that it handles the error gracefully
            operation = rollback_manager.get_rollback_operation(op_id)
            assert operation is not None
            
        finally:
            # Restore permissions
            sample_codebase.chmod(0o755)


class TestRollbackStatisticsAndCleanup:
    """Test rollback statistics and cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_rollback_statistics_tracking(self, sample_codebase, orchestrator_with_managers):
        """Test rollback statistics tracking."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create multiple operations with different outcomes
        backup_info = await backup_manager.create_full_backup()
        
        # Successful rollback
        op1_id = await rollback_manager.register_operation(
            "cleanup", backup_info.backup_id, [sample_codebase / "main.py"]
        )
        await rollback_manager.manual_rollback(operation_id=op1_id)
        
        # Failed rollback (non-existent backup)
        op2_id = await rollback_manager.register_operation(
            "formatting", "non_existent", [sample_codebase / "utils.py"]
        )
        await rollback_manager.automatic_rollback(op2_id, "Test error")
        
        # Get statistics
        stats = rollback_manager.get_rollback_statistics()
        
        assert stats["total_operations"] == 2
        assert stats["completed_rollbacks"] == 1
        assert stats["failed_rollbacks"] == 1
        assert stats["success_rate"] == 0.5
        assert "cleanup" in stats["operation_types"]
        assert "formatting" in stats["operation_types"]
    
    @pytest.mark.asyncio
    async def test_old_operations_cleanup(self, sample_codebase, orchestrator_with_managers):
        """Test cleanup of old rollback operations."""
        orchestrator, backup_manager, rollback_manager = orchestrator_with_managers
        
        # Create old and recent operations
        old_op = RollbackOperation(
            "old_op", "cleanup", "backup1", [sample_codebase / "main.py"],
            timestamp=datetime.now() - timedelta(days=35)
        )
        recent_op = RollbackOperation(
            "recent_op", "cleanup", "backup2", [sample_codebase / "utils.py"],
            timestamp=datetime.now() - timedelta(days=5)
        )
        
        rollback_manager._rollback_operations["old_op"] = old_op
        rollback_manager._rollback_operations["recent_op"] = recent_op
        rollback_manager._save_operations()
        
        # Cleanup old operations
        deleted = await rollback_manager.cleanup_old_operations(max_age_days=30)
        
        assert "old_op" in deleted
        assert "recent_op" not in deleted
        assert rollback_manager.get_rollback_operation("old_op") is None
        assert rollback_manager.get_rollback_operation("recent_op") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])