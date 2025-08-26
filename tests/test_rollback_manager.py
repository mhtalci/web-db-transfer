"""
Unit tests for the rollback manager.

Tests rollback plan creation, execution, and recovery functionality.
"""

import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from migration_assistant.backup.rollback import RollbackManager, RollbackPlan, RollbackStatus, RollbackStep
from migration_assistant.backup.validator import RecoveryValidator
from migration_assistant.core.exceptions import RollbackError
from migration_assistant.models.config import DatabaseConfig, MigrationConfig, SystemConfig, AuthConfig, PathConfig, AuthType
from migration_assistant.models.session import BackupInfo, BackupType, MigrationSession, MigrationStatus


class TestRollbackManager:
    """Test cases for RollbackManager."""
    
    @pytest.fixture
    def recovery_validator(self):
        """Create a recovery validator for testing."""
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
    def backup_info(self, temp_dir):
        """Create a backup info for testing."""
        backup_file = os.path.join(temp_dir, "test_backup.tar.gz")
        with open(backup_file, "w") as f:
            f.write("backup content")
        
        return BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=len("backup content"),
            checksum="test_checksum",
            metadata={"backup_type": "file_archive"}
        )
    
    @pytest.fixture
    def migration_session(self, migration_config, backup_info):
        """Create a migration session for testing."""
        session = MigrationSession(
            id=str(uuid.uuid4()),
            config=migration_config,
            status=MigrationStatus.FAILED
        )
        session.add_backup(backup_info)
        return session
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_create_rollback_plan(self, rollback_manager, migration_session):
        """Test rollback plan creation."""
        plan = await rollback_manager.create_rollback_plan(migration_session)
        
        assert isinstance(plan, RollbackPlan)
        assert plan.migration_session == migration_session
        assert len(plan.steps) == len(migration_session.backups)
        assert plan.status == RollbackStatus.PENDING
        assert plan.estimated_duration > 0
    
    @pytest.mark.asyncio
    async def test_create_rollback_plan_multiple_backups(self, rollback_manager, migration_session, temp_dir):
        """Test rollback plan creation with multiple backups."""
        # Add more backups
        for i in range(2):
            backup_file = os.path.join(temp_dir, f"backup_{i}.sql")
            with open(backup_file, "w") as f:
                f.write(f"database backup {i}")
            
            backup_info = BackupInfo(
                id=str(uuid.uuid4()),
                type=BackupType.FULL,
                source_system="wordpress",
                location=backup_file,
                metadata={"backup_type": "database_dump", "database_type": "mysql"}
            )
            migration_session.add_backup(backup_info)
        
        plan = await rollback_manager.create_rollback_plan(migration_session)
        
        assert len(plan.steps) == 3  # Original + 2 new backups
        
        # Check that steps are ordered by backup creation time (reverse)
        backup_times = [step.backup_info.created_at for step in plan.steps]
        assert backup_times == sorted(backup_times, reverse=True)
    
    @pytest.mark.asyncio
    async def test_validate_rollback_readiness(self, rollback_manager, migration_session):
        """Test rollback readiness validation."""
        with patch.object(rollback_manager.recovery_validator, 'validate_multiple_backups') as mock_validate:
            mock_validate.return_value = {
                migration_session.backups[0].id: MagicMock(is_valid=True)
            }
            
            results = await rollback_manager.validate_rollback_readiness(migration_session)
            
            assert len(results) == 1
            assert results[migration_session.backups[0].id].is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_rollback_readiness_no_backups(self, rollback_manager, migration_session):
        """Test rollback readiness validation with no backups."""
        migration_session.backups = []
        
        with pytest.raises(RollbackError, match="No backups available"):
            await rollback_manager.validate_rollback_readiness(migration_session)
    
    @pytest.mark.asyncio
    async def test_execute_rollback_success(self, rollback_manager, migration_session):
        """Test successful rollback execution."""
        with patch.object(rollback_manager, 'validate_rollback_readiness') as mock_validate:
            mock_validate.return_value = {
                migration_session.backups[0].id: MagicMock(is_valid=True)
            }
            
            with patch.object(rollback_manager, '_execute_rollback_step') as mock_execute:
                mock_execute.return_value = None  # Success
                
                plan = await rollback_manager.execute_rollback(migration_session)
                
                assert plan.status == RollbackStatus.COMPLETED
                assert all(step.status == RollbackStatus.COMPLETED for step in plan.steps)
    
    @pytest.mark.asyncio
    async def test_execute_rollback_with_failures(self, rollback_manager, migration_session):
        """Test rollback execution with step failures."""
        with patch.object(rollback_manager, 'validate_rollback_readiness') as mock_validate:
            mock_validate.return_value = {
                migration_session.backups[0].id: MagicMock(is_valid=True)
            }
            
            with patch.object(rollback_manager, '_execute_rollback_step') as mock_execute:
                mock_execute.side_effect = Exception("Rollback step failed")
                
                plan = await rollback_manager.execute_rollback(migration_session)
                
                assert plan.status == RollbackStatus.FAILED
                assert all(step.status == RollbackStatus.FAILED for step in plan.steps)
    
    @pytest.mark.asyncio
    async def test_execute_rollback_continue_on_failure(self, rollback_manager, migration_session, temp_dir):
        """Test rollback execution with continue on failure option."""
        # Add multiple backups
        backup_file = os.path.join(temp_dir, "backup_2.sql")
        with open(backup_file, "w") as f:
            f.write("database backup")
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            metadata={"backup_type": "database_dump"}
        )
        migration_session.add_backup(backup_info)
        
        with patch.object(rollback_manager, 'validate_rollback_readiness') as mock_validate:
            mock_validate.return_value = {
                backup.id: MagicMock(is_valid=True) for backup in migration_session.backups
            }
            
            with patch.object(rollback_manager, '_execute_rollback_step') as mock_execute:
                # First step fails, second succeeds
                mock_execute.side_effect = [Exception("First step failed"), None]
                
                rollback_options = {"continue_on_failure": True}
                plan = await rollback_manager.execute_rollback(migration_session, rollback_options)
                
                assert plan.status == RollbackStatus.PARTIAL
                assert plan.steps[0].status == RollbackStatus.FAILED
                assert plan.steps[1].status == RollbackStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_execute_rollback_skip_validation(self, rollback_manager, migration_session):
        """Test rollback execution with validation skipped."""
        with patch.object(rollback_manager, '_execute_rollback_step') as mock_execute:
            mock_execute.return_value = None  # Success
            
            rollback_options = {"skip_validation": True}
            plan = await rollback_manager.execute_rollback(migration_session, rollback_options)
            
            assert plan.status == RollbackStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_rollback_file_step(self, rollback_manager, temp_dir):
        """Test file rollback step execution."""
        # Create test backup file
        backup_file = os.path.join(temp_dir, "test_backup.tar.gz")
        with open(backup_file, "w") as f:
            f.write("backup content")
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            metadata={"backup_type": "file_archive"}
        )
        
        step = RollbackStep("test_step", "Test file rollback", backup_info)
        
        with patch('migration_assistant.backup.strategies.FileBackupStrategy.restore_backup') as mock_restore:
            mock_restore.return_value = True
            
            await rollback_manager._execute_rollback_step(step, {})
            
            assert "restore_location" in step.details
            mock_restore.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rollback_database_step(self, rollback_manager, temp_dir, db_config):
        """Test database rollback step execution."""
        # Create test database backup file
        backup_file = os.path.join(temp_dir, "test_backup.sql")
        with open(backup_file, "w") as f:
            f.write("CREATE TABLE test (id INT);")
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            metadata={"backup_type": "database_dump", "database_type": "mysql"}
        )
        
        step = RollbackStep("test_step", "Test database rollback", backup_info)
        
        with patch('migration_assistant.backup.strategies.DatabaseBackupStrategy.restore_backup') as mock_restore:
            mock_restore.return_value = True
            
            rollback_options = {"database_config": db_config.dict()}
            await rollback_manager._execute_rollback_step(step, rollback_options)
            
            assert step.details["database_restored"] is True
            mock_restore.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rollback_config_step(self, rollback_manager, temp_dir):
        """Test configuration rollback step execution."""
        # Create test config backup file
        backup_file = os.path.join(temp_dir, "config_backup.json")
        config_data = {
            "backup_id": "test",
            "timestamp": "2023-01-01T00:00:00",
            "system_config": {"type": "wordpress"},
            "config_files": {"config.ini": "[section]\nkey=value"}
        }
        with open(backup_file, "w") as f:
            json.dump(config_data, f)
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            metadata={"backup_type": "configuration"}
        )
        
        step = RollbackStep("test_step", "Test config rollback", backup_info)
        
        with patch('migration_assistant.backup.strategies.ConfigBackupStrategy.restore_backup') as mock_restore:
            mock_restore.return_value = True
            
            await rollback_manager._execute_rollback_step(step, {})
            
            assert step.details["config_restored"] is True
            mock_restore.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_rollback_status(self, rollback_manager, migration_session):
        """Test getting rollback status."""
        plan = await rollback_manager.create_rollback_plan(migration_session)
        
        status = await rollback_manager.get_rollback_status(migration_session.id)
        
        assert status is not None
        assert status["session_id"] == migration_session.id
        assert status["status"] == RollbackStatus.PENDING.value
        assert "progress" in status
        assert "steps" in status
    
    @pytest.mark.asyncio
    async def test_get_rollback_status_nonexistent(self, rollback_manager):
        """Test getting status for nonexistent rollback."""
        status = await rollback_manager.get_rollback_status("nonexistent_id")
        assert status is None
    
    @pytest.mark.asyncio
    async def test_cancel_rollback(self, rollback_manager, migration_session):
        """Test cancelling a rollback operation."""
        plan = await rollback_manager.create_rollback_plan(migration_session)
        plan.status = RollbackStatus.IN_PROGRESS
        plan.steps[0].start()
        
        success = await rollback_manager.cancel_rollback(migration_session.id)
        
        assert success is True
        assert plan.status == RollbackStatus.FAILED
        assert plan.steps[0].status == RollbackStatus.FAILED
        assert plan.steps[0].error == "Rollback cancelled by user"
    
    @pytest.mark.asyncio
    async def test_cancel_rollback_not_in_progress(self, rollback_manager, migration_session):
        """Test cancelling a rollback that's not in progress."""
        await rollback_manager.create_rollback_plan(migration_session)
        
        success = await rollback_manager.cancel_rollback(migration_session.id)
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_cleanup_rollback_artifacts(self, rollback_manager, migration_session):
        """Test cleanup of rollback artifacts."""
        plan = await rollback_manager.create_rollback_plan(migration_session)
        
        # Add some test artifacts
        plan.steps[0].details["restore_location"] = "/tmp/rollback_test"
        
        with patch('shutil.rmtree') as mock_rmtree:
            success = await rollback_manager.cleanup_rollback_artifacts(migration_session.id)
            
            assert success is True
            assert migration_session.id not in rollback_manager._active_rollbacks
    
    @pytest.mark.asyncio
    async def test_generate_rollback_guidance(self, rollback_manager, migration_session):
        """Test generation of rollback guidance."""
        guidance = await rollback_manager.generate_rollback_guidance(migration_session)
        
        assert "session_id" in guidance
        assert "automatic_rollback_possible" in guidance
        assert "manual_steps_required" in guidance
        assert "prerequisites" in guidance
        assert "estimated_complexity" in guidance
        assert guidance["session_id"] == migration_session.id
    
    @pytest.mark.asyncio
    async def test_generate_rollback_guidance_no_backups(self, rollback_manager, migration_session):
        """Test rollback guidance generation with no backups."""
        migration_session.backups = []
        
        guidance = await rollback_manager.generate_rollback_guidance(migration_session)
        
        assert guidance["automatic_rollback_possible"] is False
        assert guidance["estimated_complexity"] == "high"
        assert any("No backups available" in step for step in guidance["manual_steps_required"])
    
    @pytest.mark.asyncio
    async def test_get_rollback_statistics(self, rollback_manager, migration_session):
        """Test getting rollback statistics."""
        # Create some rollback plans
        await rollback_manager.create_rollback_plan(migration_session)
        
        stats = await rollback_manager.get_rollback_statistics()
        
        assert "total_rollbacks" in stats
        assert "rollback_status_counts" in stats
        assert "average_steps_per_rollback" in stats
        assert "success_rate" in stats
        assert stats["total_rollbacks"] >= 1
    
    def test_estimate_rollback_duration(self, rollback_manager):
        """Test rollback duration estimation."""
        backups = [
            BackupInfo(
                id="backup1",
                type=BackupType.FULL,
                source_system="test",
                location="/path/backup1",
                size=100 * 1024 * 1024  # 100MB
            ),
            BackupInfo(
                id="backup2",
                type=BackupType.FULL,
                source_system="test",
                location="/path/backup2",
                size=50 * 1024 * 1024   # 50MB
            )
        ]
        
        duration = rollback_manager._estimate_rollback_duration(backups)
        
        assert duration > 0
        assert isinstance(duration, int)
    
    def test_logging(self, rollback_manager):
        """Test rollback operation logging."""
        # Clear existing logs
        rollback_manager.clear_logs()
        
        # Perform an operation that generates logs
        rollback_manager._log("INFO", "Test log message", "test_session_id")
        
        # Check logs
        logs = rollback_manager.get_logs()
        assert len(logs) == 1
        assert logs[0].message == "Test log message"
        assert logs[0].details["session_id"] == "test_session_id"
        
        # Test filtered logs
        filtered_logs = rollback_manager.get_logs("test_session_id")
        assert len(filtered_logs) == 1
        
        # Clear logs
        rollback_manager.clear_logs()
        assert len(rollback_manager.get_logs()) == 0


class TestRollbackPlan:
    """Test cases for RollbackPlan."""
    
    @pytest.fixture
    def migration_session(self):
        """Create a migration session for testing."""
        config = MigrationConfig(
            source=SystemConfig(type="wordpress", host="localhost"),
            destination=SystemConfig(type="wordpress", host="remote")
        )
        return MigrationSession(id=str(uuid.uuid4()), config=config)
    
    @pytest.fixture
    def rollback_plan(self, migration_session):
        """Create a rollback plan for testing."""
        return RollbackPlan(migration_session)
    
    @pytest.fixture
    def rollback_step(self):
        """Create a rollback step for testing."""
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location="/path/backup",
            metadata={"backup_type": "file_archive"}
        )
        return RollbackStep("step1", "Test step", backup_info)
    
    def test_add_step(self, rollback_plan, rollback_step):
        """Test adding a step to rollback plan."""
        rollback_plan.add_step(rollback_step)
        
        assert len(rollback_plan.steps) == 1
        assert rollback_plan.steps[0] == rollback_step
    
    def test_get_step(self, rollback_plan, rollback_step):
        """Test getting a step by ID."""
        rollback_plan.add_step(rollback_step)
        
        retrieved_step = rollback_plan.get_step("step1")
        assert retrieved_step == rollback_step
        
        nonexistent_step = rollback_plan.get_step("nonexistent")
        assert nonexistent_step is None
    
    def test_get_progress(self, rollback_plan, rollback_step):
        """Test getting rollback progress."""
        rollback_plan.add_step(rollback_step)
        
        progress = rollback_plan.get_progress()
        
        assert progress["total_steps"] == 1
        assert progress["completed_steps"] == 0
        assert progress["failed_steps"] == 0
        assert progress["progress_percentage"] == 0
        
        # Complete the step
        rollback_step.complete()
        progress = rollback_plan.get_progress()
        
        assert progress["completed_steps"] == 1
        assert progress["progress_percentage"] == 100


class TestRollbackStep:
    """Test cases for RollbackStep."""
    
    @pytest.fixture
    def rollback_step(self):
        """Create a rollback step for testing."""
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location="/path/backup",
            metadata={"backup_type": "file_archive"}
        )
        return RollbackStep("step1", "Test step", backup_info)
    
    def test_start(self, rollback_step):
        """Test starting a rollback step."""
        rollback_step.start()
        
        assert rollback_step.status == RollbackStatus.IN_PROGRESS
        assert rollback_step.start_time is not None
    
    def test_complete(self, rollback_step):
        """Test completing a rollback step."""
        rollback_step.start()
        rollback_step.complete()
        
        assert rollback_step.status == RollbackStatus.COMPLETED
        assert rollback_step.end_time is not None
    
    def test_fail(self, rollback_step):
        """Test failing a rollback step."""
        rollback_step.start()
        rollback_step.fail("Test error")
        
        assert rollback_step.status == RollbackStatus.FAILED
        assert rollback_step.error == "Test error"
        assert rollback_step.end_time is not None