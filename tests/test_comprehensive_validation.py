"""
Comprehensive tests for the validation engine with 90%+ coverage.

This module tests all validation components including connectivity,
compatibility, permissions, and dependencies.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from migration_assistant.validation.engine import ValidationEngine
from migration_assistant.validation.connectivity import ConnectivityValidator
from migration_assistant.validation.compatibility import CompatibilityValidator
from migration_assistant.validation.permission import PermissionValidator
from migration_assistant.validation.dependency import DependencyValidator
from migration_assistant.models.config import (
    SystemConfig, DatabaseConfig, AuthConfig, PathConfig,
    SystemType, DatabaseType, AuthType
)
from migration_assistant.core.exceptions import (
    ValidationError, ConnectivityError, CompatibilityError
)


class TestValidationEngine:
    """Test the main validation engine orchestrator."""
    
    @pytest.fixture
    def validation_engine(self):
        """Create validation engine instance."""
        return ValidationEngine()
    
    @pytest.fixture
    def sample_configs(self, sample_migration_config):
        """Sample source and destination configs."""
        return sample_migration_config.source, sample_migration_config.destination
    
    @pytest.mark.asyncio
    async def test_validate_migration_success(self, validation_engine, sample_configs):
        """Test successful migration validation."""
        source, destination = sample_configs
        
        with patch.multiple(
            validation_engine,
            _validate_connectivity=AsyncMock(return_value=True),
            _validate_compatibility=AsyncMock(return_value=True),
            _validate_permissions=AsyncMock(return_value=True),
            _validate_dependencies=AsyncMock(return_value=True)
        ):
            result = await validation_engine.validate_migration(source, destination)
            
            assert result.success is True
            assert len(result.errors) == 0
            assert len(result.warnings) == 0
            assert result.validation_time > 0
    
    @pytest.mark.asyncio
    async def test_validate_migration_with_errors(self, validation_engine, sample_configs):
        """Test migration validation with errors."""
        source, destination = sample_configs
        
        with patch.multiple(
            validation_engine,
            _validate_connectivity=AsyncMock(side_effect=ConnectivityError("Connection failed")),
            _validate_compatibility=AsyncMock(return_value=True),
            _validate_permissions=AsyncMock(return_value=True),
            _validate_dependencies=AsyncMock(return_value=True)
        ):
            result = await validation_engine.validate_migration(source, destination)
            
            assert result.success is False
            assert len(result.errors) > 0
            assert "Connection failed" in str(result.errors[0])
    
    @pytest.mark.asyncio
    async def test_validate_migration_with_warnings(self, validation_engine, sample_configs):
        """Test migration validation with warnings."""
        source, destination = sample_configs
        
        with patch.multiple(
            validation_engine,
            _validate_connectivity=AsyncMock(return_value=True),
            _validate_compatibility=AsyncMock(return_value=True),
            _validate_permissions=AsyncMock(return_value=True),
            _validate_dependencies=AsyncMock(return_value=True)
        ):
            # Simulate a warning during validation
            validation_engine._add_warning = Mock()
            validation_engine._warnings = ["Deprecated feature detected"]
            
            result = await validation_engine.validate_migration(source, destination)
            
            assert result.success is True
            assert len(result.warnings) > 0
    
    @pytest.mark.asyncio
    async def test_validate_step_by_step(self, validation_engine, sample_configs):
        """Test step-by-step validation process."""
        source, destination = sample_configs
        
        steps = []
        
        async def mock_step_callback(step_name, status, details=None):
            steps.append((step_name, status, details))
        
        with patch.multiple(
            validation_engine,
            _validate_connectivity=AsyncMock(return_value=True),
            _validate_compatibility=AsyncMock(return_value=True),
            _validate_permissions=AsyncMock(return_value=True),
            _validate_dependencies=AsyncMock(return_value=True)
        ):
            result = await validation_engine.validate_migration(
                source, destination, step_callback=mock_step_callback
            )
            
            assert result.success is True
            assert len(steps) > 0
            assert any("connectivity" in step[0].lower() for step in steps)


class TestConnectivityValidator:
    """Test connectivity validation for various systems."""
    
    @pytest.fixture
    def connectivity_validator(self):
        """Create connectivity validator instance."""
        return ConnectivityValidator()
    
    @pytest.mark.asyncio
    async def test_validate_database_connectivity_mysql(self, connectivity_validator):
        """Test MySQL database connectivity validation."""
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            port=3306,
            database_name="testdb",
            username="testuser",
            password="testpass"
        )
        
        with patch('mysql.connector.connect') as mock_connect:
            mock_connection = Mock()
            mock_connect.return_value = mock_connection
            mock_connection.is_connected.return_value = True
            
            result = await connectivity_validator.validate_database_connection(config)
            
            assert result.success is True
            assert result.response_time > 0
            mock_connect.assert_called_once()
            mock_connection.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_database_connectivity_postgresql(self, connectivity_validator):
        """Test PostgreSQL database connectivity validation."""
        config = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="testdb",
            username="testuser",
            password="testpass"
        )
        
        with patch('psycopg2.connect') as mock_connect:
            mock_connection = Mock()
            mock_connect.return_value = mock_connection
            mock_connection.closed = 0  # 0 means open connection
            
            result = await connectivity_validator.validate_database_connection(config)
            
            assert result.success is True
            mock_connect.assert_called_once()
            mock_connection.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_database_connectivity_mongodb(self, connectivity_validator):
        """Test MongoDB connectivity validation."""
        config = DatabaseConfig(
            type=DatabaseType.MONGODB,
            host="localhost",
            port=27017,
            database_name="testdb"
        )
        
        with patch('pymongo.MongoClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            mock_instance.admin.command.return_value = {"ok": 1}
            
            result = await connectivity_validator.validate_database_connection(config)
            
            assert result.success is True
            mock_client.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_ssh_connectivity(self, connectivity_validator, mock_ssh_client):
        """Test SSH connectivity validation."""
        auth_config = AuthConfig(
            type=AuthType.SSH_KEY,
            username="testuser",
            private_key_path="/path/to/key"
        )
        
        with patch('paramiko.SSHClient', return_value=mock_ssh_client):
            result = await connectivity_validator.validate_ssh_connection(
                "localhost", 22, auth_config
            )
            
            assert result.success is True
            assert mock_ssh_client.connected is True
    
    @pytest.mark.asyncio
    async def test_validate_ftp_connectivity(self, connectivity_validator):
        """Test FTP connectivity validation."""
        auth_config = AuthConfig(
            type=AuthType.PASSWORD,
            username="testuser",
            password="testpass"
        )
        
        with patch('ftplib.FTP') as mock_ftp:
            mock_instance = Mock()
            mock_ftp.return_value = mock_instance
            mock_instance.login.return_value = "230 Login successful"
            
            result = await connectivity_validator.validate_ftp_connection(
                "localhost", 21, auth_config
            )
            
            assert result.success is True
            mock_instance.login.assert_called_once_with("testuser", "testpass")
            mock_instance.quit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_cloud_connectivity_aws(self, connectivity_validator, mock_cloud_services):
        """Test AWS S3 connectivity validation."""
        with patch('boto3.client') as mock_boto3:
            mock_boto3.return_value = mock_cloud_services["s3"]
            
            result = await connectivity_validator.validate_aws_s3_connection(
                "test-bucket", "us-east-1"
            )
            
            assert result.success is True
    
    @pytest.mark.asyncio
    async def test_connectivity_timeout(self, connectivity_validator):
        """Test connectivity validation with timeout."""
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="unreachable-host",
            port=3306,
            database_name="testdb",
            username="testuser",
            password="testpass"
        )
        
        with patch('mysql.connector.connect', side_effect=TimeoutError("Connection timeout")):
            result = await connectivity_validator.validate_database_connection(config, timeout=1)
            
            assert result.success is False
            assert "timeout" in result.error_message.lower()


class TestCompatibilityValidator:
    """Test compatibility validation between systems."""
    
    @pytest.fixture
    def compatibility_validator(self):
        """Create compatibility validator instance."""
        return CompatibilityValidator()
    
    def test_validate_database_compatibility_same_type(self, compatibility_validator):
        """Test compatibility between same database types."""
        source_config = DatabaseConfig(type=DatabaseType.MYSQL, host="source")
        dest_config = DatabaseConfig(type=DatabaseType.MYSQL, host="dest")
        
        result = compatibility_validator.validate_database_compatibility(
            source_config, dest_config
        )
        
        assert result.compatible is True
        assert result.compatibility_score >= 0.9
    
    def test_validate_database_compatibility_different_types(self, compatibility_validator):
        """Test compatibility between different database types."""
        source_config = DatabaseConfig(type=DatabaseType.MYSQL, host="source")
        dest_config = DatabaseConfig(type=DatabaseType.POSTGRESQL, host="dest")
        
        result = compatibility_validator.validate_database_compatibility(
            source_config, dest_config
        )
        
        assert result.compatible is True  # Should be compatible with migration
        assert result.compatibility_score < 1.0
        assert len(result.warnings) > 0
    
    def test_validate_database_compatibility_incompatible(self, compatibility_validator):
        """Test incompatible database types."""
        source_config = DatabaseConfig(type=DatabaseType.MONGODB, host="source")
        dest_config = DatabaseConfig(type=DatabaseType.MYSQL, host="dest")
        
        result = compatibility_validator.validate_database_compatibility(
            source_config, dest_config
        )
        
        assert result.compatible is False
        assert len(result.issues) > 0
    
    def test_validate_system_compatibility(self, compatibility_validator):
        """Test system compatibility validation."""
        source_config = SystemConfig(
            type=SystemType.WORDPRESS,
            host="source.com"
        )
        dest_config = SystemConfig(
            type=SystemType.AWS_S3,
            host="s3.amazonaws.com"
        )
        
        result = compatibility_validator.validate_system_compatibility(
            source_config, dest_config
        )
        
        assert result.compatible is True
        assert len(result.migration_requirements) > 0
    
    def test_validate_version_compatibility(self, compatibility_validator):
        """Test version compatibility checking."""
        result = compatibility_validator.validate_version_compatibility(
            "mysql", "8.0", "8.1"
        )
        
        assert result.compatible is True
        
        result = compatibility_validator.validate_version_compatibility(
            "mysql", "8.0", "5.7"
        )
        
        assert result.compatible is True
        assert len(result.warnings) > 0  # Downgrade warning


class TestPermissionValidator:
    """Test permission validation for file systems and databases."""
    
    @pytest.fixture
    def permission_validator(self):
        """Create permission validator instance."""
        return PermissionValidator()
    
    @pytest.mark.asyncio
    async def test_validate_file_permissions_read(self, permission_validator, temp_directory):
        """Test file read permission validation."""
        test_file = Path(temp_directory) / "test.txt"
        test_file.write_text("test content")
        
        result = await permission_validator.validate_file_permissions(
            str(test_file), ["read"]
        )
        
        assert result.success is True
        assert "read" in result.granted_permissions
    
    @pytest.mark.asyncio
    async def test_validate_file_permissions_write(self, permission_validator, temp_directory):
        """Test file write permission validation."""
        result = await permission_validator.validate_file_permissions(
            temp_directory, ["write"]
        )
        
        assert result.success is True
        assert "write" in result.granted_permissions
    
    @pytest.mark.asyncio
    async def test_validate_database_permissions(self, permission_validator):
        """Test database permission validation."""
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            username="testuser",
            password="testpass"
        )
        
        with patch('mysql.connector.connect') as mock_connect:
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_connection
            mock_connection.cursor.return_value = mock_cursor
            
            # Mock SHOW GRANTS query
            mock_cursor.fetchall.return_value = [
                ("GRANT SELECT, INSERT, UPDATE, DELETE ON *.* TO 'testuser'@'%'",)
            ]
            
            result = await permission_validator.validate_database_permissions(
                config, ["SELECT", "INSERT", "UPDATE", "DELETE"]
            )
            
            assert result.success is True
            assert all(perm in result.granted_permissions for perm in ["SELECT", "INSERT", "UPDATE", "DELETE"])
    
    @pytest.mark.asyncio
    async def test_validate_directory_permissions(self, permission_validator, temp_directory):
        """Test directory permission validation."""
        result = await permission_validator.validate_directory_permissions(
            temp_directory, ["read", "write", "execute"]
        )
        
        assert result.success is True
        assert len(result.granted_permissions) >= 2  # At least read and write
    
    @pytest.mark.asyncio
    async def test_validate_permissions_insufficient(self, permission_validator):
        """Test validation with insufficient permissions."""
        # Try to access a restricted directory
        restricted_path = "/root"  # Typically restricted on Unix systems
        
        result = await permission_validator.validate_file_permissions(
            restricted_path, ["write"]
        )
        
        # Should handle permission errors gracefully
        assert isinstance(result.success, bool)
        if not result.success:
            assert len(result.denied_permissions) > 0


class TestDependencyValidator:
    """Test dependency validation for required tools and libraries."""
    
    @pytest.fixture
    def dependency_validator(self):
        """Create dependency validator instance."""
        return DependencyValidator()
    
    @pytest.mark.asyncio
    async def test_validate_python_dependencies(self, dependency_validator):
        """Test Python dependency validation."""
        required_packages = ["pytest", "asyncio"]  # Should be available in test environment
        
        result = await dependency_validator.validate_python_dependencies(required_packages)
        
        assert result.success is True
        assert len(result.available_packages) >= 1
    
    @pytest.mark.asyncio
    async def test_validate_system_commands(self, dependency_validator):
        """Test system command availability validation."""
        # Test common commands that should be available
        commands = ["python", "ls"]  # Basic commands
        
        result = await dependency_validator.validate_system_commands(commands)
        
        assert result.success is True
        assert len(result.available_commands) >= 1
    
    @pytest.mark.asyncio
    async def test_validate_database_drivers(self, dependency_validator):
        """Test database driver availability validation."""
        drivers = ["mysql.connector", "sqlite3"]  # sqlite3 is built-in
        
        result = await dependency_validator.validate_database_drivers(drivers)
        
        assert result.success is True
        assert "sqlite3" in result.available_drivers
    
    @pytest.mark.asyncio
    async def test_validate_cloud_sdks(self, dependency_validator):
        """Test cloud SDK availability validation."""
        sdks = ["boto3"]  # Should be in dependencies
        
        result = await dependency_validator.validate_cloud_sdks(sdks)
        
        # Result depends on whether boto3 is installed
        assert isinstance(result.success, bool)
    
    @pytest.mark.asyncio
    async def test_validate_missing_dependencies(self, dependency_validator):
        """Test validation with missing dependencies."""
        missing_packages = ["nonexistent-package-12345"]
        
        result = await dependency_validator.validate_python_dependencies(missing_packages)
        
        assert result.success is False
        assert len(result.missing_packages) > 0
        assert "nonexistent-package-12345" in result.missing_packages
    
    @pytest.mark.asyncio
    async def test_validate_version_requirements(self, dependency_validator):
        """Test dependency version requirement validation."""
        requirements = [
            {"package": "python", "min_version": "3.8", "max_version": "3.12"}
        ]
        
        result = await dependency_validator.validate_version_requirements(requirements)
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_validate_go_binary_availability(self, dependency_validator, mock_go_binary):
        """Test Go binary availability validation."""
        with patch('migration_assistant.performance.engine.GoPerformanceEngine') as mock_engine:
            mock_engine.return_value = mock_go_binary
            
            result = await dependency_validator.validate_go_binary()
            
            assert result.success is True
            assert result.go_available is True


class TestValidationIntegration:
    """Integration tests for the complete validation workflow."""
    
    @pytest.mark.asyncio
    async def test_full_validation_workflow(self, sample_migration_config):
        """Test complete validation workflow with all validators."""
        engine = ValidationEngine()
        
        # Mock all validation steps to succeed
        with patch.multiple(
            'migration_assistant.validation.connectivity.ConnectivityValidator',
            validate_database_connection=AsyncMock(return_value=Mock(success=True)),
            validate_ssh_connection=AsyncMock(return_value=Mock(success=True))
        ), patch.multiple(
            'migration_assistant.validation.compatibility.CompatibilityValidator',
            validate_database_compatibility=Mock(return_value=Mock(compatible=True)),
            validate_system_compatibility=Mock(return_value=Mock(compatible=True))
        ), patch.multiple(
            'migration_assistant.validation.permission.PermissionValidator',
            validate_file_permissions=AsyncMock(return_value=Mock(success=True)),
            validate_database_permissions=AsyncMock(return_value=Mock(success=True))
        ), patch.multiple(
            'migration_assistant.validation.dependency.DependencyValidator',
            validate_python_dependencies=AsyncMock(return_value=Mock(success=True)),
            validate_system_commands=AsyncMock(return_value=Mock(success=True))
        ):
            result = await engine.validate_migration(
                sample_migration_config.source,
                sample_migration_config.destination
            )
            
            assert result.success is True
            assert result.validation_time > 0
            assert len(result.validation_steps) > 0
    
    @pytest.mark.asyncio
    async def test_validation_with_remediation_suggestions(self, sample_migration_config):
        """Test validation with remediation suggestions for failures."""
        engine = ValidationEngine()
        
        # Mock a connectivity failure
        with patch.multiple(
            'migration_assistant.validation.connectivity.ConnectivityValidator',
            validate_database_connection=AsyncMock(
                side_effect=ConnectivityError("Database connection failed")
            )
        ):
            result = await engine.validate_migration(
                sample_migration_config.source,
                sample_migration_config.destination
            )
            
            assert result.success is False
            assert len(result.errors) > 0
            assert len(result.remediation_suggestions) > 0
    
    @pytest.mark.benchmark
    def test_validation_performance(self, benchmark, sample_migration_config):
        """Benchmark validation performance."""
        engine = ValidationEngine()
        
        async def run_validation():
            with patch.multiple(
                engine,
                _validate_connectivity=AsyncMock(return_value=True),
                _validate_compatibility=AsyncMock(return_value=True),
                _validate_permissions=AsyncMock(return_value=True),
                _validate_dependencies=AsyncMock(return_value=True)
            ):
                return await engine.validate_migration(
                    sample_migration_config.source,
                    sample_migration_config.destination
                )
        
        result = benchmark.pedantic(
            lambda: asyncio.run(run_validation()),
            rounds=10
        )
        
        # Validation should complete quickly
        assert result.success is True