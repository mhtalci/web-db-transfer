"""Tests for database migration factory."""

import pytest
from unittest.mock import MagicMock

from migration_assistant.database.factory import DatabaseMigrationFactory, create_database_migrator
from migration_assistant.database.base import DatabaseMigrator, MigrationResult, MigrationStatus
from migration_assistant.database.config import (
    DatabaseType,
    MySQLConfig,
    PostgreSQLConfig,
    SQLiteConfig,
    MongoConfig,
    RedisConfig
)
from migration_assistant.core.exceptions import UnsupportedDatabaseError, IncompatibleDatabaseError


class MockMySQLMigrator(DatabaseMigrator):
    """Mock MySQL migrator for testing."""
    
    async def connect_source(self) -> bool:
        return True
    
    async def connect_destination(self) -> bool:
        return True
    
    async def disconnect(self) -> None:
        pass
    
    async def test_connectivity(self) -> dict:
        return {"source": True, "destination": True}
    
    async def get_schema_info(self, config) -> dict:
        return {"tables": ["users", "orders"]}
    
    async def validate_compatibility(self) -> list:
        return []
    
    async def estimate_migration_size(self) -> dict:
        return {"tables": 2, "estimated_records": 1000}
    
    async def migrate_schema(self) -> MigrationResult:
        return MigrationResult(status=MigrationStatus.COMPLETED, start_time=None)
    
    async def migrate_data(self, tables=None, batch_size=1000, method=None):
        yield None
    
    async def verify_migration(self, tables=None) -> dict:
        return {"success": True}
    
    async def get_supported_methods(self) -> list:
        return []


class MockPostgreSQLMigrator(DatabaseMigrator):
    """Mock PostgreSQL migrator for testing."""
    
    async def connect_source(self) -> bool:
        return True
    
    async def connect_destination(self) -> bool:
        return True
    
    async def disconnect(self) -> None:
        pass
    
    async def test_connectivity(self) -> dict:
        return {"source": True, "destination": True}
    
    async def get_schema_info(self, config) -> dict:
        return {"tables": ["users", "orders"]}
    
    async def validate_compatibility(self) -> list:
        return []
    
    async def estimate_migration_size(self) -> dict:
        return {"tables": 2, "estimated_records": 1000}
    
    async def migrate_schema(self) -> MigrationResult:
        return MigrationResult(status=MigrationStatus.COMPLETED, start_time=None)
    
    async def migrate_data(self, tables=None, batch_size=1000, method=None):
        yield None
    
    async def verify_migration(self, tables=None) -> dict:
        return {"success": True}
    
    async def get_supported_methods(self) -> list:
        return []


class MockGenericSQLMigrator(DatabaseMigrator):
    """Mock generic SQL migrator for testing."""
    
    async def connect_source(self) -> bool:
        return True
    
    async def connect_destination(self) -> bool:
        return True
    
    async def disconnect(self) -> None:
        pass
    
    async def test_connectivity(self) -> dict:
        return {"source": True, "destination": True}
    
    async def get_schema_info(self, config) -> dict:
        return {"tables": ["users", "orders"]}
    
    async def validate_compatibility(self) -> list:
        return []
    
    async def estimate_migration_size(self) -> dict:
        return {"tables": 2, "estimated_records": 1000}
    
    async def migrate_schema(self) -> MigrationResult:
        return MigrationResult(status=MigrationStatus.COMPLETED, start_time=None)
    
    async def migrate_data(self, tables=None, batch_size=1000, method=None):
        yield None
    
    async def verify_migration(self, tables=None) -> dict:
        return {"success": True}
    
    async def get_supported_methods(self) -> list:
        return []


class TestDatabaseMigrationFactory:
    """Test cases for DatabaseMigrationFactory."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear the registry before each test
        DatabaseMigrationFactory._migrator_registry.clear()
    
    def test_register_migrator(self):
        """Test registering a migrator."""
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL,
            MockMySQLMigrator
        )
        
        key = (DatabaseType.MYSQL, DatabaseType.POSTGRESQL)
        assert key in DatabaseMigrationFactory._migrator_registry
        assert DatabaseMigrationFactory._migrator_registry[key] == MockMySQLMigrator
    
    def test_create_migrator_exact_match(self):
        """Test creating migrator with exact type match."""
        # Register a specific migrator
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL,
            MockMySQLMigrator
        )
        
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = PostgreSQLConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        migrator = DatabaseMigrationFactory.create_migrator(source_config, destination_config)
        
        assert isinstance(migrator, MockMySQLMigrator)
        assert migrator.source_config == source_config
        assert migrator.destination_config == destination_config
    
    def test_create_migrator_same_type(self):
        """Test creating migrator for same database types."""
        # Register a same-type migrator
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.MYSQL,
            MockMySQLMigrator
        )
        
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = MySQLConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        migrator = DatabaseMigrationFactory.create_migrator(source_config, destination_config)
        
        assert isinstance(migrator, MockMySQLMigrator)
    
    def test_create_migrator_unsupported(self):
        """Test creating migrator for unsupported combination."""
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = MongoConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        with pytest.raises(UnsupportedDatabaseError):
            DatabaseMigrationFactory.create_migrator(source_config, destination_config)
    
    def test_get_supported_migrations(self):
        """Test getting supported migration combinations."""
        # Register some migrators
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL,
            MockMySQLMigrator
        )
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.POSTGRESQL,
            DatabaseType.MYSQL,
            MockPostgreSQLMigrator
        )
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.SQLITE,
            DatabaseType.MYSQL,
            MockGenericSQLMigrator
        )
        
        supported = DatabaseMigrationFactory.get_supported_migrations()
        
        assert "mysql" in supported
        assert "postgresql" in supported["mysql"]
        assert "postgresql" in supported
        assert "mysql" in supported["postgresql"]
        assert "sqlite" in supported
        assert "mysql" in supported["sqlite"]
    
    def test_is_migration_supported(self):
        """Test checking if migration is supported."""
        # Register a migrator
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL,
            MockMySQLMigrator
        )
        
        # Supported migration
        assert DatabaseMigrationFactory.is_migration_supported(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL
        ) is True
        
        # Unsupported migration
        assert DatabaseMigrationFactory.is_migration_supported(
            DatabaseType.MYSQL,
            DatabaseType.MONGODB
        ) is False
    
    def test_validate_migration_compatibility(self):
        """Test migration compatibility validation."""
        # Register a migrator
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL,
            MockMySQLMigrator
        )
        
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = PostgreSQLConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        is_compatible, issues = DatabaseMigrationFactory.validate_migration_compatibility(
            source_config, destination_config
        )
        
        assert is_compatible is True
        assert len(issues) == 0
    
    def test_validate_migration_compatibility_unsupported(self):
        """Test compatibility validation for unsupported migration."""
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = MongoConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        is_compatible, issues = DatabaseMigrationFactory.validate_migration_compatibility(
            source_config, destination_config
        )
        
        assert is_compatible is False
        assert len(issues) > 0
        assert any("not supported" in issue for issue in issues)
    
    def test_validate_migration_compatibility_sql_to_nosql(self):
        """Test compatibility validation for SQL to NoSQL migration."""
        # Register the migration to make it "supported" but still flag the issue
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.MONGODB,
            MockGenericSQLMigrator
        )
        
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = MongoConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        is_compatible, issues = DatabaseMigrationFactory.validate_migration_compatibility(
            source_config, destination_config
        )
        
        assert is_compatible is False
        assert any("schema transformation" in issue for issue in issues)
    
    def test_get_recommended_method(self):
        """Test getting recommended migration method."""
        # Same type migration
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = MySQLConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        method = DatabaseMigrationFactory.get_recommended_method(source_config, destination_config)
        assert method == "dump_restore"
        
        # SQL to SQL migration
        destination_config = PostgreSQLConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        method = DatabaseMigrationFactory.get_recommended_method(source_config, destination_config)
        assert method == "direct_transfer"
        
        # NoSQL migration
        source_config = MongoConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = RedisConfig(
            host="dest.example.com",
            password="pass"
        )
        
        method = DatabaseMigrationFactory.get_recommended_method(source_config, destination_config)
        assert method == "bulk_copy"
    
    def test_is_compatible_type(self):
        """Test type compatibility checking."""
        # Exact match
        assert DatabaseMigrationFactory._is_compatible_type(
            DatabaseType.MYSQL,
            DatabaseType.MYSQL
        ) is True
        
        # MySQL variants
        assert DatabaseMigrationFactory._is_compatible_type(
            DatabaseType.MYSQL,
            DatabaseType.AWS_RDS_MYSQL
        ) is True
        
        assert DatabaseMigrationFactory._is_compatible_type(
            DatabaseType.AWS_RDS_MYSQL,
            DatabaseType.MYSQL
        ) is True
        
        # PostgreSQL variants
        assert DatabaseMigrationFactory._is_compatible_type(
            DatabaseType.POSTGRESQL,
            DatabaseType.AWS_RDS_POSTGRESQL
        ) is True
        
        # Incompatible types
        assert DatabaseMigrationFactory._is_compatible_type(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL
        ) is False


class TestCreateDatabaseMigrator:
    """Test cases for the convenience function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear the registry before each test
        DatabaseMigrationFactory._migrator_registry.clear()
    
    def test_create_database_migrator_function(self):
        """Test the convenience function for creating migrators."""
        # Register a migrator
        DatabaseMigrationFactory.register_migrator(
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL,
            MockMySQLMigrator
        )
        
        source_config = MySQLConfig(
            host="source.example.com",
            username="user",
            password="pass",
            database="sourcedb"
        )
        
        destination_config = PostgreSQLConfig(
            host="dest.example.com",
            username="user",
            password="pass",
            database="destdb"
        )
        
        migrator = create_database_migrator(source_config, destination_config)
        
        assert isinstance(migrator, MockMySQLMigrator)
        assert migrator.source_config == source_config
        assert migrator.destination_config == destination_config

cl
ass TestDatabaseMigrationFactoryEnhanced:
    """Test cases for enhanced DatabaseMigrationFactory functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear the registry before each test
        DatabaseMigrationFactory._migrator_registry.clear()
    
    @pytest.mark.asyncio
    async def test_analyze_and_recommend_method_basic(self):
        """Test basic method analysis without schema analysis."""
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        result = await DatabaseMigrationFactory.analyze_and_recommend_method(
            mysql_config, mysql_config, analyze_schema=False
        )
        
        assert result['recommended_method'] == "dump_restore"
        assert result['alternative_methods'] == []
        assert result['compatibility_analysis'] is None
        assert result['schema_analysis'] is None
        assert len(result['requirements']) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_and_recommend_method_with_schema(self):
        """Test method analysis with schema analysis."""
        from unittest.mock import Mock, patch
        from migration_assistant.database.base import MigrationMethod
        
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        # Mock schema analyzer
        mock_analyzer = Mock()
        mock_schema_result = Mock()
        mock_schema_result.get_table_count.return_value = 5
        mock_schema_result.get_total_rows.return_value = 10000
        mock_schema_result.get_total_size_bytes.return_value = 1048576  # 1MB
        mock_schema_result.views = {}
        mock_schema_result.functions = []
        mock_schema_result.sequences = []
        
        mock_compatibility = Mock()
        mock_compatibility.compatible = True
        mock_compatibility.migration_complexity = "simple"
        mock_compatibility.recommended_method = MigrationMethod.DUMP_RESTORE
        mock_compatibility.issues = []
        mock_compatibility.warnings = []
        mock_compatibility.recommendations = ["Use dump and restore"]
        mock_compatibility.unsupported_features = []
        
        mock_analyzer.analyze_schema.return_value = mock_schema_result
        mock_analyzer.analyze_compatibility.return_value = mock_compatibility
        mock_analyzer.get_migration_method_recommendations.return_value = [
            MigrationMethod.DUMP_RESTORE, MigrationMethod.DIRECT_TRANSFER
        ]
        
        with patch.object(DatabaseMigrationFactory, '_schema_analyzer', mock_analyzer):
            result = await DatabaseMigrationFactory.analyze_and_recommend_method(
                mysql_config, mysql_config, analyze_schema=True
            )
            
            assert result['recommended_method'] == "dump_restore"
            assert "dump_restore" in result['alternative_methods']
            assert "direct_transfer" in result['alternative_methods']
            assert result['schema_analysis'] is not None
            assert result['schema_analysis']['source_tables'] == 5
            assert result['schema_analysis']['source_rows'] == 10000
            assert result['schema_analysis']['source_size_mb'] == 1.0
            assert result['compatibility_analysis'] is not None
            assert result['compatibility_analysis']['compatible'] is True
    
    def test_get_method_requirements_dump_restore(self):
        """Test getting requirements for dump_restore method."""
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        requirements = DatabaseMigrationFactory._get_method_requirements(
            "dump_restore", mysql_config, mysql_config
        )
        
        assert len(requirements) > 0
        assert any("disk space" in req.lower() for req in requirements)
        assert any("dump" in req.lower() for req in requirements)
        assert any("mysql" in req.lower() for req in requirements)
    
    def test_get_method_requirements_direct_transfer(self):
        """Test getting requirements for direct_transfer method."""
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        requirements = DatabaseMigrationFactory._get_method_requirements(
            "direct_transfer", mysql_config, mysql_config
        )
        
        assert len(requirements) > 0
        assert any("simultaneous connections" in req.lower() for req in requirements)
        assert any("compatible data types" in req.lower() for req in requirements)
    
    def test_get_supported_methods_for_migration(self):
        """Test getting supported methods for a migration."""
        from unittest.mock import Mock, patch
        from migration_assistant.database.base import MigrationMethod
        
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        postgres_config = PostgreSQLConfig(
            host="localhost",
            username="postgres",
            password="secret",
            database="mydb"
        )
        
        # Mock migrator
        mock_migrator = Mock()
        mock_migrator.get_supported_methods.return_value = [
            MigrationMethod.DUMP_RESTORE,
            MigrationMethod.DIRECT_TRANSFER,
            MigrationMethod.BULK_COPY
        ]
        
        with patch.object(DatabaseMigrationFactory, 'create_migrator', return_value=mock_migrator):
            methods = DatabaseMigrationFactory.get_supported_methods_for_migration(
                mysql_config, postgres_config
            )
            
            assert MigrationMethod.DUMP_RESTORE in methods
            assert MigrationMethod.DIRECT_TRANSFER in methods
            assert MigrationMethod.BULK_COPY in methods
    
    def test_estimate_migration_time_with_data(self):
        """Test migration time estimation with data characteristics."""
        from migration_assistant.database.base import MigrationMethod
        
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        postgres_config = PostgreSQLConfig(
            host="localhost",
            username="postgres",
            password="secret",
            database="mydb"
        )
        
        estimate = DatabaseMigrationFactory.estimate_migration_time(
            mysql_config, postgres_config,
            MigrationMethod.DIRECT_TRANSFER,
            data_size_mb=1024,  # 1GB
            row_count=1000000
        )
        
        assert estimate['estimated_hours'] > 0
        assert estimate['min_hours'] < estimate['estimated_hours']
        assert estimate['max_hours'] > estimate['estimated_hours']
        assert len(estimate['factors']) > 0
        assert len(estimate['assumptions']) > 0
        assert "1024.0 MB" in estimate['assumptions'][0]
    
    def test_estimate_migration_time_same_type(self):
        """Test migration time estimation for same database type."""
        from migration_assistant.database.base import MigrationMethod
        
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        estimate = DatabaseMigrationFactory.estimate_migration_time(
            mysql_config, mysql_config,
            MigrationMethod.DUMP_RESTORE,
            data_size_mb=512
        )
        
        # Same type should not have cross-database penalty
        assert not any("Cross-database" in factor for factor in estimate['factors'])
    
    def test_estimate_migration_time_large_dataset(self):
        """Test migration time estimation with large dataset."""
        from migration_assistant.database.base import MigrationMethod
        
        mysql_config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="mydb"
        )
        
        estimate = DatabaseMigrationFactory.estimate_migration_time(
            mysql_config, mysql_config,
            MigrationMethod.BULK_COPY,
            data_size_mb=2048,
            row_count=5000000  # Large row count
        )
        
        # Should have large row count penalty
        assert any("Large row count" in factor for factor in estimate['factors'])
    
    def test_estimate_migration_time_network_transfer(self):
        """Test migration time estimation with network transfer."""
        from migration_assistant.database.base import MigrationMethod
        
        source_config = MySQLConfig(
            host="source.example.com",
            username="root",
            password="secret",
            database="mydb"
        )
        
        dest_config = MySQLConfig(
            host="dest.example.com",
            username="root",
            password="secret",
            database="mydb"
        )
        
        estimate = DatabaseMigrationFactory.estimate_migration_time(
            source_config, dest_config,
            MigrationMethod.DIRECT_TRANSFER,
            data_size_mb=1024
        )
        
        # Should have network transfer penalty
        assert any("Network transfer" in factor for factor in estimate['factors'])