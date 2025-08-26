"""
Unit tests for compatibility validation module.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from migration_assistant.models.config import (
    SystemType, DatabaseType, TransferMethod, MigrationConfig,
    SystemConfig, DatabaseConfig, TransferConfig, MigrationOptions,
    AuthConfig, PathConfig, AuthType
)
from migration_assistant.validation.compatibility import (
    CompatibilityValidator, CompatibilityCheck, CompatibilityResult
)


@pytest.fixture
def compatibility_validator():
    """Create a CompatibilityValidator instance for testing."""
    return CompatibilityValidator()


@pytest.fixture
def sample_migration_config():
    """Create a sample migration configuration for testing."""
    auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
    path_config = PathConfig(root_path="/var/www")
    
    source_db = DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="source.example.com",
        database_name="source_db",
        username="user",
        password="pass"
    )
    
    dest_db = DatabaseConfig(
        type=DatabaseType.POSTGRESQL,
        host="dest.example.com", 
        database_name="dest_db",
        username="user",
        password="pass"
    )
    
    source = SystemConfig(
        type=SystemType.WORDPRESS,
        host="source.example.com",
        authentication=auth_config,
        paths=path_config,
        database=source_db
    )
    
    destination = SystemConfig(
        type=SystemType.WORDPRESS,
        host="dest.example.com",
        authentication=auth_config,
        paths=path_config,
        database=dest_db
    )
    
    transfer = TransferConfig(method=TransferMethod.SSH_SFTP)
    options = MigrationOptions()
    
    return MigrationConfig(
        name="test_migration",
        source=source,
        destination=destination,
        transfer=transfer,
        options=options
    )


class TestCompatibilityValidator:
    """Test cases for CompatibilityValidator."""
    
    @pytest.mark.asyncio
    async def test_validate_compatibility_compatible_systems(self, compatibility_validator, sample_migration_config):
        """Test validation of compatible systems."""
        # WordPress to WordPress should be compatible
        sample_migration_config.source.type = SystemType.WORDPRESS
        sample_migration_config.destination.type = SystemType.WORDPRESS
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        # Should have system compatibility check
        system_checks = [c for c in checks if c.name == "System Compatibility"]
        assert len(system_checks) == 1
        assert system_checks[0].result == CompatibilityResult.COMPATIBLE
    
    @pytest.mark.asyncio
    async def test_validate_compatibility_requires_conversion(self, compatibility_validator, sample_migration_config):
        """Test validation of systems requiring conversion."""
        # WordPress to Drupal should require conversion
        sample_migration_config.source.type = SystemType.WORDPRESS
        sample_migration_config.destination.type = SystemType.DRUPAL
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        system_checks = [c for c in checks if c.name == "System Compatibility"]
        assert len(system_checks) == 1
        assert system_checks[0].result == CompatibilityResult.REQUIRES_CONVERSION
        assert system_checks[0].conversion_required is True
    
    @pytest.mark.asyncio
    async def test_validate_compatibility_incompatible_systems(self, compatibility_validator, sample_migration_config):
        """Test validation of incompatible systems."""
        # Static site to WordPress should be incompatible
        sample_migration_config.source.type = SystemType.STATIC_SITE
        sample_migration_config.destination.type = SystemType.WORDPRESS
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        system_checks = [c for c in checks if c.name == "System Compatibility"]
        assert len(system_checks) == 1
        assert system_checks[0].result == CompatibilityResult.INCOMPATIBLE
    
    @pytest.mark.asyncio
    async def test_database_compatibility_same_type(self, compatibility_validator, sample_migration_config):
        """Test database compatibility with same database types."""
        # MySQL to MySQL should be compatible
        sample_migration_config.source.database.type = DatabaseType.MYSQL
        sample_migration_config.destination.database.type = DatabaseType.MYSQL
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        db_checks = [c for c in checks if c.name == "Database Compatibility"]
        assert len(db_checks) == 1
        assert db_checks[0].result == CompatibilityResult.COMPATIBLE
    
    @pytest.mark.asyncio
    async def test_database_compatibility_requires_conversion(self, compatibility_validator, sample_migration_config):
        """Test database compatibility requiring conversion."""
        # MySQL to PostgreSQL should require conversion
        sample_migration_config.source.database.type = DatabaseType.MYSQL
        sample_migration_config.destination.database.type = DatabaseType.POSTGRESQL
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        db_checks = [c for c in checks if c.name == "Database Compatibility"]
        assert len(db_checks) == 1
        assert db_checks[0].result == CompatibilityResult.REQUIRES_CONVERSION
        assert db_checks[0].conversion_required is True
    
    @pytest.mark.asyncio
    async def test_database_compatibility_incompatible(self, compatibility_validator, sample_migration_config):
        """Test incompatible database types."""
        # MySQL to MongoDB should be incompatible
        sample_migration_config.source.database.type = DatabaseType.MYSQL
        sample_migration_config.destination.database.type = DatabaseType.MONGODB
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        db_checks = [c for c in checks if c.name == "Database Compatibility"]
        assert len(db_checks) == 1
        assert db_checks[0].result == CompatibilityResult.INCOMPATIBLE
    
    @pytest.mark.asyncio
    async def test_database_missing_warning(self, compatibility_validator, sample_migration_config):
        """Test warning when source has database but destination doesn't."""
        sample_migration_config.destination.database = None
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        db_checks = [c for c in checks if c.name == "Database Migration"]
        assert len(db_checks) == 1
        assert db_checks[0].result == CompatibilityResult.WARNING
        assert "Source has database but destination doesn't" in db_checks[0].message
    
    @pytest.mark.asyncio
    async def test_transfer_method_compatibility_supported(self, compatibility_validator, sample_migration_config):
        """Test transfer method compatibility when supported."""
        # SSH_SFTP should be supported for WordPress systems
        sample_migration_config.transfer.method = TransferMethod.SSH_SFTP
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        transfer_checks = [c for c in checks if c.name == "Transfer Method Compatibility"]
        assert len(transfer_checks) == 1
        assert transfer_checks[0].result == CompatibilityResult.COMPATIBLE
    
    @pytest.mark.asyncio
    async def test_transfer_method_compatibility_unsupported(self, compatibility_validator, sample_migration_config):
        """Test transfer method compatibility when unsupported."""
        # AWS_S3 should not be supported for WordPress to WordPress
        sample_migration_config.transfer.method = TransferMethod.AWS_S3
        sample_migration_config.source.type = SystemType.WORDPRESS
        sample_migration_config.destination.type = SystemType.WORDPRESS
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        transfer_checks = [c for c in checks if c.name == "Transfer Method Compatibility"]
        assert len(transfer_checks) == 1
        assert transfer_checks[0].result == CompatibilityResult.INCOMPATIBLE
    
    @pytest.mark.asyncio
    async def test_platform_compatibility_cms_to_cloud(self, compatibility_validator, sample_migration_config):
        """Test platform compatibility warnings for CMS to cloud storage."""
        sample_migration_config.source.type = SystemType.WORDPRESS
        sample_migration_config.destination.type = SystemType.AWS_S3
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        platform_checks = [c for c in checks if "CMS to Cloud Storage" in c.name]
        assert len(platform_checks) == 1
        assert platform_checks[0].result == CompatibilityResult.WARNING
        assert "static files" in platform_checks[0].message
    
    @pytest.mark.asyncio
    async def test_platform_compatibility_framework_to_cloud(self, compatibility_validator, sample_migration_config):
        """Test platform compatibility for framework to cloud storage."""
        sample_migration_config.source.type = SystemType.DJANGO
        sample_migration_config.destination.type = SystemType.AWS_S3
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        platform_checks = [c for c in checks if "Framework to Cloud Storage" in c.name]
        assert len(platform_checks) == 1
        assert platform_checks[0].result == CompatibilityResult.INCOMPATIBLE
    
    @pytest.mark.asyncio
    async def test_version_compatibility_same_version(self, compatibility_validator, sample_migration_config):
        """Test version compatibility with same versions."""
        sample_migration_config.source.custom_config = {"version": "5.8.0"}
        sample_migration_config.destination.custom_config = {"version": "5.8.0"}
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        version_checks = [c for c in checks if c.name == "Version Compatibility"]
        assert len(version_checks) == 1
        assert version_checks[0].result == CompatibilityResult.COMPATIBLE
    
    @pytest.mark.asyncio
    async def test_version_compatibility_upgrade(self, compatibility_validator, sample_migration_config):
        """Test version compatibility for upgrades."""
        sample_migration_config.source.custom_config = {"version": "5.7.0"}
        sample_migration_config.destination.custom_config = {"version": "5.8.0"}
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        version_checks = [c for c in checks if c.name == "Version Compatibility"]
        assert len(version_checks) == 1
        assert version_checks[0].result == CompatibilityResult.WARNING
        assert "Upgrading" in version_checks[0].message
    
    @pytest.mark.asyncio
    async def test_version_compatibility_downgrade(self, compatibility_validator, sample_migration_config):
        """Test version compatibility for downgrades."""
        sample_migration_config.source.custom_config = {"version": "5.8.0"}
        sample_migration_config.destination.custom_config = {"version": "5.7.0"}
        
        checks = await compatibility_validator.validate_compatibility(sample_migration_config)
        
        version_checks = [c for c in checks if c.name == "Version Compatibility"]
        assert len(version_checks) == 1
        assert version_checks[0].result == CompatibilityResult.WARNING
        assert "Downgrading" in version_checks[0].message
    
    def test_get_recommended_transfer_methods(self, compatibility_validator):
        """Test getting recommended transfer methods."""
        methods = compatibility_validator.get_recommended_transfer_methods(
            SystemType.WORDPRESS, SystemType.WORDPRESS
        )
        
        assert isinstance(methods, list)
        assert len(methods) > 0
        # Should prioritize faster methods
        assert TransferMethod.HYBRID_SYNC in methods or TransferMethod.RSYNC in methods
    
    def test_get_recommended_transfer_methods_cloud(self, compatibility_validator):
        """Test getting recommended transfer methods for cloud storage."""
        methods = compatibility_validator.get_recommended_transfer_methods(
            SystemType.STATIC_SITE, SystemType.AWS_S3
        )
        
        assert TransferMethod.AWS_S3 in methods
        assert TransferMethod.HYBRID_SYNC in methods
    
    def test_get_conversion_requirements_database(self, compatibility_validator):
        """Test getting conversion requirements for database migration."""
        auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
        path_config = PathConfig(root_path="/var/www")
        
        source_db = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="source.example.com",
            database_name="source_db"
        )
        
        dest_db = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="dest.example.com",
            database_name="dest_db"
        )
        
        source = SystemConfig(
            type=SystemType.WORDPRESS,
            host="source.example.com",
            authentication=auth_config,
            paths=path_config,
            database=source_db
        )
        
        destination = SystemConfig(
            type=SystemType.WORDPRESS,
            host="dest.example.com",
            authentication=auth_config,
            paths=path_config,
            database=dest_db
        )
        
        requirements = compatibility_validator.get_conversion_requirements(source, destination)
        
        assert requirements["database_conversion"] is True
        assert requirements["complexity"] == "medium"
        assert "SQL schema conversion script" in requirements["custom_scripts"]
    
    def test_get_conversion_requirements_system_type(self, compatibility_validator):
        """Test getting conversion requirements for system type changes."""
        auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
        path_config = PathConfig(root_path="/var/www")
        
        source = SystemConfig(
            type=SystemType.WORDPRESS,
            host="source.example.com",
            authentication=auth_config,
            paths=path_config
        )
        
        destination = SystemConfig(
            type=SystemType.STATIC_SITE,
            host="dest.example.com",
            authentication=auth_config,
            paths=path_config
        )
        
        requirements = compatibility_validator.get_conversion_requirements(source, destination)
        
        assert requirements["file_conversion"] is True
        assert "WordPress to static site generator" in requirements["custom_scripts"]
        assert "Configure static site hosting" in requirements["manual_steps"]


class TestCompatibilityCheck:
    """Test cases for CompatibilityCheck dataclass."""
    
    def test_compatibility_check_creation(self):
        """Test creating a CompatibilityCheck instance."""
        check = CompatibilityCheck(
            name="Test Check",
            result=CompatibilityResult.COMPATIBLE,
            message="Test message"
        )
        
        assert check.name == "Test Check"
        assert check.result == CompatibilityResult.COMPATIBLE
        assert check.message == "Test message"
        assert check.details is None
        assert check.remediation is None
        assert check.conversion_required is False
        assert check.estimated_complexity == "low"
    
    def test_compatibility_check_with_details(self):
        """Test creating a CompatibilityCheck with all fields."""
        details = {"source": "mysql", "destination": "postgresql"}
        
        check = CompatibilityCheck(
            name="Database Check",
            result=CompatibilityResult.REQUIRES_CONVERSION,
            message="Conversion needed",
            details=details,
            remediation="Use conversion tool",
            conversion_required=True,
            estimated_complexity="high"
        )
        
        assert check.details == details
        assert check.remediation == "Use conversion tool"
        assert check.conversion_required is True
        assert check.estimated_complexity == "high"


class TestCompatibilityResult:
    """Test cases for CompatibilityResult enum."""
    
    def test_compatibility_result_values(self):
        """Test CompatibilityResult enum values."""
        assert CompatibilityResult.COMPATIBLE.value == "compatible"
        assert CompatibilityResult.INCOMPATIBLE.value == "incompatible"
        assert CompatibilityResult.WARNING.value == "warning"
        assert CompatibilityResult.REQUIRES_CONVERSION.value == "requires_conversion"