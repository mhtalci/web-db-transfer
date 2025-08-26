"""
Integration tests for the backup and recovery system.

Tests the complete backup and recovery workflow including
backup creation, validation, and rollback operations.
"""

import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from migration_assistant.backup.manager import BackupManager
from migration_assistant.backup.rollback import RollbackManager
from migration_assistant.backup.storage import BackupStorage, RetentionPolicy
from migration_assistant.backup.validator import RecoveryValidator
from migration_assistant.models.config import DatabaseConfig, MigrationConfig, SystemConfig, AuthConfig, PathConfig, AuthType
from migration_assistant.models.session import MigrationSession, MigrationStatus


class TestBackupIntegration:
    """Integration tests for the complete backup system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def backup_storage(self, temp_dir):
        """Create a backup storage instance for testing."""
        retention_policy = RetentionPolicy(max_backups=10, max_age_days=30)
        return BackupStorage(temp_dir, retention_policy)
    
    @pytest.fixture
    def backup_manager(self, backup_storage):
        """Create a backup manager instance for testing."""
        return BackupManager(backup_storage)
    
    @pytest.fixture
    def recovery_validator(self):
        """Create a recovery validator instance for testing."""
        return RecoveryValidator()
    
    @pytest.fixture
    def rollback_manager(self, recovery_validator):
        """Create a rollback manager instance for testing."""
        return RollbackManager(recovery_validator)
    
    @pytest.fixture
    def system_config(self):
        """Create a system configuration for testing."""
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
    
    @pytest.fixture
    def test_files(self, temp_dir):
        """Create test files for backup testing."""
        files = []
        
        # Create various test files
        for i in range(3):
            file_path = os.path.join(temp_dir, f"test_file_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"Test content for file {i}\n" * 100)
            files.append(file_path)
        
        # Create a subdirectory with files
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)
        
        for i in range(2):
            file_path = os.path.join(subdir, f"sub_file_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"Sub file {i} content\n" * 50)
            files.append(file_path)
        
        return files
    
    @pytest.mark.asyncio
    async def test_complete_backup_workflow(self, backup_manager, recovery_validator, migration_config, test_files, temp_dir):
        """Test complete backup creation and validation workflow."""
        # Create backup options
        backup_options = {
            "file_paths": test_files[:2],  # Backup first 2 files
            "backup_database": False,  # Skip database for this test
            "config_files": [os.path.join(temp_dir, "config.ini")],
            "compression": "gzip"
        }
        
        # Create config file
        config_file = os.path.join(temp_dir, "config.ini")
        with open(config_file, "w") as f:
            f.write("[section]\nkey=value\ndebug=true\n")
        
        # Create full system backup
        backups = await backup_manager.create_full_system_backup(migration_config, backup_options)
        
        # Verify backups were created
        assert len(backups) >= 2  # At least files and config backups
        
        # Verify all backup files exist
        for backup in backups:
            assert os.path.exists(backup.location)
            assert backup.size > 0
            assert backup.checksum is not None
        
        # Validate all backups
        validation_results = await recovery_validator.validate_multiple_backups(backups)
        
        # All backups should be valid
        for backup_id, result in validation_results.items():
            assert result.is_valid is True, f"Backup {backup_id} validation failed: {result.errors}"
        
        # Generate validation report
        report = await recovery_validator.generate_validation_report(validation_results)
        
        assert report["validation_summary"]["valid_backups"] == len(backups)
        assert report["validation_summary"]["invalid_backups"] == 0
    
    @pytest.mark.asyncio
    async def test_backup_and_rollback_workflow(self, backup_manager, rollback_manager, migration_config, test_files, temp_dir):
        """Test complete backup creation and rollback workflow."""
        # Create migration session
        session = MigrationSession(
            id=str(uuid.uuid4()),
            config=migration_config,
            status=MigrationStatus.FAILED
        )
        
        # Create backups
        backup_options = {
            "file_paths": test_files,
            "backup_database": False,
            "config_files": []
        }
        
        backups = await backup_manager.create_full_system_backup(migration_config, backup_options)
        
        # Add backups to session
        for backup in backups:
            session.add_backup(backup)
        
        # Create rollback plan
        rollback_plan = await rollback_manager.create_rollback_plan(session)
        
        assert len(rollback_plan.steps) == len(backups)
        assert rollback_plan.estimated_duration > 0
        
        # Validate rollback readiness
        validation_results = await rollback_manager.validate_rollback_readiness(session)
        
        # All backups should be valid for rollback
        for backup_id, result in validation_results.items():
            assert result.is_valid is True
        
        # Execute rollback (with mocked restore operations)
        with patch('migration_assistant.backup.strategies.FileBackupStrategy.restore_backup') as mock_restore:
            with patch('migration_assistant.backup.strategies.ConfigBackupStrategy.restore_backup') as mock_config_restore:
                mock_restore.return_value = True
                mock_config_restore.return_value = True
                
                executed_plan = await rollback_manager.execute_rollback(session)
                
                assert executed_plan.status.value in ["completed", "partial"]
                
                # Check that restore was called for each backup
                total_restore_calls = mock_restore.call_count + mock_config_restore.call_count
                assert total_restore_calls == len(backups)
    
    @pytest.mark.asyncio
    async def test_backup_retention_and_cleanup(self, backup_manager, system_config, test_files, temp_dir):
        """Test backup retention policy and cleanup."""
        # Create multiple backups
        backups = []
        
        for i in range(5):
            options = {
                "source_paths": [test_files[0]],
                "compression": "gzip"
            }
            
            backup = await backup_manager.create_backup(system_config, "files", options)
            backups.append(backup)
            
            # Simulate different creation times
            if i < 3:
                backup.created_at = datetime.utcnow() - timedelta(days=35)  # Old backups
        
        # Test cleanup of expired backups
        deleted_backups = await backup_manager.cleanup_expired_backups(backups)
        
        # Should delete old backups (retention policy: max_age_days=30)
        assert len(deleted_backups) >= 3
        
        # Verify deleted backup files no longer exist
        for backup_location in deleted_backups:
            assert not os.path.exists(backup_location)
    
    @pytest.mark.asyncio
    async def test_backup_corruption_detection(self, backup_manager, recovery_validator, system_config, test_files):
        """Test detection of corrupted backups."""
        # Create a backup
        options = {"source_paths": [test_files[0]]}
        backup = await backup_manager.create_backup(system_config, "files", options)
        
        # Verify backup is initially valid
        result = await recovery_validator.validate_backup(backup)
        assert result.is_valid is True
        
        # Corrupt the backup file
        with open(backup.location, "w") as f:
            f.write("corrupted content")
        
        # Validate corrupted backup
        result = await recovery_validator.validate_backup(backup)
        assert result.is_valid is False
        assert any("checksum" in error.lower() for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_database_backup_integration(self, backup_manager, recovery_validator, system_config, db_config):
        """Test database backup integration with mocked database operations."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful mysqldump
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            # Create database backup
            backup = await backup_manager.create_backup(system_config, "database", {}, db_config)
            
            assert backup.metadata["database_type"] == "mysql"
            assert backup.metadata["database_name"] == "test_db"
            
            # Validate database backup
            result = await recovery_validator.validate_backup(backup)
            assert result.is_valid is True
    
    @pytest.mark.asyncio
    async def test_storage_statistics_and_integrity(self, backup_manager, system_config, test_files):
        """Test storage statistics and integrity verification."""
        # Create multiple backups
        for i in range(3):
            options = {"source_paths": [test_files[i % len(test_files)]]}
            await backup_manager.create_backup(system_config, "files", options)
        
        # Get storage statistics
        stats = await backup_manager.get_storage_stats()
        
        assert stats["total_backups"] >= 3
        assert stats["total_size"] > 0
        assert "backup_types" in stats
        assert "file_archive" in stats["backup_types"]
        
        # Verify storage integrity
        integrity_report = await backup_manager.verify_storage_integrity()
        
        assert integrity_report["storage_healthy"] is True
        assert integrity_report["total_files_checked"] >= 3
        assert len(integrity_report["corrupted_files"]) == 0
        assert len(integrity_report["missing_files"]) == 0
    
    @pytest.mark.asyncio
    async def test_rollback_guidance_generation(self, rollback_manager, migration_config, test_files, temp_dir):
        """Test rollback guidance generation for complex scenarios."""
        # Create migration session with various backup types
        session = MigrationSession(
            id=str(uuid.uuid4()),
            config=migration_config,
            status=MigrationStatus.FAILED
        )
        
        # Add different types of backups
        backup_types = [
            {"backup_type": "file_archive"},
            {"backup_type": "database_dump", "database_type": "mysql"},
            {"backup_type": "configuration"},
            {"backup_type": "cloud_resources"}
        ]
        
        for i, metadata in enumerate(backup_types):
            backup_file = os.path.join(temp_dir, f"backup_{i}")
            with open(backup_file, "w") as f:
                f.write(f"backup content {i}")
            
            backup = BackupInfo(
                id=str(uuid.uuid4()),
                type=BackupType.FULL,
                source_system="wordpress",
                location=backup_file,
                metadata=metadata
            )
            session.add_backup(backup)
        
        # Generate rollback guidance
        guidance = await rollback_manager.generate_rollback_guidance(session)
        
        assert guidance["automatic_rollback_possible"] is True
        assert len(guidance["manual_steps_required"]) > 0
        assert len(guidance["prerequisites"]) > 0
        
        # Should have high complexity due to cloud resources
        assert guidance["estimated_complexity"] == "high"
        
        # Should include database-specific guidance
        assert any("database" in step.lower() for step in guidance["prerequisites"])
    
    @pytest.mark.asyncio
    async def test_concurrent_backup_operations(self, backup_manager, system_config, test_files):
        """Test concurrent backup operations."""
        # Create multiple backup tasks concurrently
        backup_tasks = []
        
        for i in range(3):
            options = {"source_paths": [test_files[i % len(test_files)]]}
            task = backup_manager.create_backup(system_config, "files", options)
            backup_tasks.append(task)
        
        # Execute all backup tasks concurrently
        backups = await asyncio.gather(*backup_tasks)
        
        # Verify all backups were created successfully
        assert len(backups) == 3
        for backup in backups:
            assert os.path.exists(backup.location)
            assert backup.size > 0
            assert backup.checksum is not None
        
        # Verify all backups have unique IDs and locations
        backup_ids = [backup.id for backup in backups]
        backup_locations = [backup.location for backup in backups]
        
        assert len(set(backup_ids)) == 3  # All unique IDs
        assert len(set(backup_locations)) == 3  # All unique locations
    
    @pytest.mark.asyncio
    async def test_backup_size_estimation_accuracy(self, backup_manager, system_config, test_files):
        """Test backup size estimation accuracy."""
        options = {
            "source_paths": test_files,
            "compression": "gzip"
        }
        
        # Get size estimate
        estimate = await backup_manager.estimate_backup_size(system_config, "files", options)
        
        # Create actual backup
        backup = await backup_manager.create_backup(system_config, "files", options)
        
        # Compare estimate with actual size
        estimated_size = estimate["estimated_size"]
        actual_size = backup.size
        
        # Estimate should be reasonably close (within 50% margin)
        size_difference = abs(estimated_size - actual_size) / actual_size
        assert size_difference < 0.5, f"Size estimate too far off: estimated={estimated_size}, actual={actual_size}"
        
        # Duration estimate should be positive
        assert estimate["estimated_duration"] > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, backup_manager, rollback_manager, system_config):
        """Test error handling and recovery in backup operations."""
        # Test backup creation with invalid source paths
        options = {"source_paths": ["/nonexistent/path"]}
        
        with pytest.raises(Exception):  # Should raise BackupError
            await backup_manager.create_backup(system_config, "files", options)
        
        # Test rollback with no backups
        session = MigrationSession(
            id=str(uuid.uuid4()),
            config=MigrationConfig(
                source=system_config,
                destination=system_config
            ),
            status=MigrationStatus.FAILED
        )
        
        with pytest.raises(Exception):  # Should raise RollbackError
            await rollback_manager.validate_rollback_readiness(session)
        
        # Verify system remains in consistent state after errors
        stats = await backup_manager.get_storage_stats()
        assert isinstance(stats, dict)
        assert "total_backups" in stats