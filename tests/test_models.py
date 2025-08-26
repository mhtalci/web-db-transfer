"""
Tests for Migration Assistant data models.

This module contains unit tests for all Pydantic models
used in the Migration Assistant.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from migration_assistant.models.config import (
    MigrationConfig,
    SystemConfig,
    AuthConfig,
    PathConfig,
    DatabaseConfig,
    TransferConfig,
    MigrationOptions,
    AuthType,
    SystemType,
    DatabaseType,
    TransferMethod,
)
from migration_assistant.models.session import (
    MigrationSession,
    MigrationStatus,
    MigrationStep,
    StepStatus,
    LogEntry,
    LogLevel,
    ErrorInfo,
    ErrorSeverity,
)


class TestAuthConfig:
    """Test AuthConfig model."""

    def test_password_auth_valid(self):
        """Test valid password authentication configuration."""
        auth = AuthConfig(
            type=AuthType.PASSWORD,
            username="testuser",
            password="testpass"
        )
        assert auth.type == AuthType.PASSWORD
        assert auth.username == "testuser"
        assert auth.password == "testpass"

    def test_password_auth_missing_username(self):
        """Test password auth with missing username raises validation error."""
        with pytest.raises(ValidationError):
            AuthConfig(
                type=AuthType.PASSWORD,
                password="testpass"
            )

    def test_password_auth_missing_password(self):
        """Test password auth with missing password raises validation error."""
        with pytest.raises(ValidationError):
            AuthConfig(
                type=AuthType.PASSWORD,
                username="testuser"
            )

    def test_ssh_key_auth_valid(self):
        """Test valid SSH key authentication configuration."""
        auth = AuthConfig(
            type=AuthType.SSH_KEY,
            username="testuser",
            ssh_key_path="/path/to/key"
        )
        assert auth.type == AuthType.SSH_KEY
        assert auth.ssh_key_path == "/path/to/key"


class TestDatabaseConfig:
    """Test DatabaseConfig model."""

    def test_mysql_config_with_default_port(self):
        """Test MySQL config sets default port."""
        db = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            database_name="testdb",
            username="user",
            password="pass"
        )
        assert db.port == 3306

    def test_postgresql_config_with_default_port(self):
        """Test PostgreSQL config sets default port."""
        db = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="localhost",
            database_name="testdb",
            username="user",
            password="pass"
        )
        assert db.port == 5432

    def test_custom_port_override(self):
        """Test custom port overrides default."""
        db = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            port=3307,
            database_name="testdb",
            username="user",
            password="pass"
        )
        assert db.port == 3307


class TestSystemConfig:
    """Test SystemConfig model."""

    def test_wordpress_requires_database(self, sample_auth_config, sample_path_config):
        """Test WordPress system requires database configuration."""
        with pytest.raises(ValidationError):
            SystemConfig(
                type=SystemType.WORDPRESS,
                host="example.com",
                authentication=sample_auth_config,
                paths=sample_path_config
            )

    def test_static_site_no_database_required(self, sample_auth_config, sample_path_config):
        """Test static site doesn't require database configuration."""
        system = SystemConfig(
            type=SystemType.STATIC_SITE,
            host="example.com",
            authentication=sample_auth_config,
            paths=sample_path_config
        )
        assert system.database is None


class TestMigrationConfig:
    """Test MigrationConfig model."""

    def test_valid_migration_config(self, sample_migration_config):
        """Test valid migration configuration."""
        assert sample_migration_config.name == "Test Migration"
        assert sample_migration_config.source.type == SystemType.WORDPRESS
        assert sample_migration_config.destination.type == SystemType.AWS_S3

    def test_empty_name_validation(self, sample_system_config, sample_transfer_config, sample_migration_options):
        """Test empty name raises validation error."""
        with pytest.raises(ValidationError):
            MigrationConfig(
                name="",
                source=sample_system_config,
                destination=sample_system_config,
                transfer=sample_transfer_config,
                options=sample_migration_options
            )

    def test_update_timestamp(self, sample_migration_config):
        """Test update timestamp functionality."""
        original_time = sample_migration_config.updated_at
        sample_migration_config.update_timestamp()
        assert sample_migration_config.updated_at > original_time


class TestMigrationStep:
    """Test MigrationStep model."""

    def test_step_lifecycle(self):
        """Test migration step lifecycle methods."""
        step = MigrationStep(
            id="test_step",
            name="Test Step"
        )
        
        # Initial state
        assert step.status == StepStatus.PENDING
        assert step.start_time is None
        assert step.end_time is None
        
        # Start step
        step.start()
        assert step.status == StepStatus.RUNNING
        assert step.start_time is not None
        
        # Complete step
        step.complete()
        assert step.status == StepStatus.COMPLETED
        assert step.end_time is not None
        assert step.duration is not None

    def test_step_failure(self):
        """Test migration step failure handling."""
        step = MigrationStep(
            id="test_step",
            name="Test Step"
        )
        
        error = ErrorInfo(
            code="TEST_ERROR",
            message="Test error message",
            severity=ErrorSeverity.HIGH
        )
        
        step.start()
        step.fail(error)
        
        assert step.status == StepStatus.FAILED
        assert step.error == error
        assert step.end_time is not None

    def test_add_log_entry(self):
        """Test adding log entries to step."""
        step = MigrationStep(
            id="test_step",
            name="Test Step"
        )
        
        step.add_log(LogLevel.INFO, "Test log message")
        
        assert len(step.logs) == 1
        assert step.logs[0].level == LogLevel.INFO
        assert step.logs[0].message == "Test log message"
        assert step.logs[0].step_id == "test_step"


class TestMigrationSession:
    """Test MigrationSession model."""

    def test_session_lifecycle(self, sample_migration_session):
        """Test migration session lifecycle methods."""
        session = sample_migration_session
        
        # Initial state
        assert session.status == MigrationStatus.PENDING
        assert session.start_time is None
        
        # Start session
        session.start()
        assert session.status == MigrationStatus.RUNNING
        assert session.start_time is not None
        
        # Complete session
        session.complete()
        assert session.status == MigrationStatus.COMPLETED
        assert session.end_time is not None
        assert session.duration is not None

    def test_session_failure(self, sample_migration_session):
        """Test migration session failure handling."""
        session = sample_migration_session
        
        error = ErrorInfo(
            code="SESSION_ERROR",
            message="Session failed",
            severity=ErrorSeverity.CRITICAL
        )
        
        session.start()
        session.fail(error)
        
        assert session.status == MigrationStatus.FAILED
        assert session.error == error

    def test_add_step(self, sample_migration_session):
        """Test adding steps to session."""
        session = sample_migration_session
        initial_count = len(session.steps)
        
        new_step = MigrationStep(
            id="new_step",
            name="New Step"
        )
        
        session.add_step(new_step)
        
        assert len(session.steps) == initial_count + 1
        assert session.get_step("new_step") == new_step

    def test_overall_progress_calculation(self, sample_migration_session):
        """Test overall progress calculation."""
        session = sample_migration_session
        
        # Add more steps
        for i in range(3):
            step = MigrationStep(
                id=f"step_{i}",
                name=f"Step {i}"
            )
            session.add_step(step)
        
        # Complete some steps
        session.steps[0].status = StepStatus.COMPLETED
        session.steps[1].status = StepStatus.COMPLETED
        
        progress = session.get_overall_progress()
        expected_progress = (2 / len(session.steps)) * 100
        
        assert progress == expected_progress

    def test_add_log_entry(self, sample_migration_session):
        """Test adding log entries to session."""
        session = sample_migration_session
        
        session.add_log(LogLevel.INFO, "Session started")
        
        assert len(session.logs) == 1
        assert session.logs[0].message == "Session started"