"""Integration tests for database migrators."""

import pytest
from migration_assistant.database.factory import DatabaseMigrationFactory
from migration_assistant.database.config import (
    MySQLConfig,
    PostgreSQLConfig,
    SQLiteConfig,
    MongoConfig,
    RedisConfig,
    DatabaseType
)
from migration_assistant.database.migrators import (
    MySQLMigrator,
    PostgreSQLMigrator,
    SQLiteMigrator,
    MongoMigrator,
    RedisMigrator
)


class TestMigratorIntegration:
    """Test migrator integration with factory."""
    
    def test_create_mysql_migrator(self):
        """Test creating MySQL migrator through factory."""
        source_config = MySQLConfig(
            host="localhost",
            port=3306,
            username="test",
            password="test",
            database="source_db"
        )
        
        dest_config = MySQLConfig(
            host="localhost",
            port=3307,
            username="test",
            password="test",
            database="dest_db"
        )
        
        migrator = DatabaseMigrationFactory.create_migrator(source_config, dest_config)
        
        assert isinstance(migrator, MySQLMigrator)
        assert migrator.source_config == source_config
        assert migrator.destination_config == dest_config
    
    def test_create_postgresql_migrator(self):
        """Test creating PostgreSQL migrator through factory."""
        source_config = PostgreSQLConfig(
            host="localhost",
            port=5432,
            username="test",
            password="test",
            database="source_db"
        )
        
        dest_config = PostgreSQLConfig(
            host="localhost",
            port=5433,
            username="test",
            password="test",
            database="dest_db"
        )
        
        migrator = DatabaseMigrationFactory.create_migrator(source_config, dest_config)
        
        assert isinstance(migrator, PostgreSQLMigrator)
        assert migrator.source_config == source_config
        assert migrator.destination_config == dest_config
    
    def test_create_sqlite_migrator(self):
        """Test creating SQLite migrator through factory."""
        source_config = SQLiteConfig(database_path="/tmp/source.db")
        dest_config = SQLiteConfig(database_path="/tmp/dest.db")
        
        migrator = DatabaseMigrationFactory.create_migrator(source_config, dest_config)
        
        assert isinstance(migrator, SQLiteMigrator)
        assert migrator.source_config == source_config
        assert migrator.destination_config == dest_config
    
    def test_create_mongo_migrator(self):
        """Test creating MongoDB migrator through factory."""
        source_config = MongoConfig(
            host="localhost",
            port=27017,
            username="test",
            password="test",
            database="source_db"
        )
        
        dest_config = MongoConfig(
            host="localhost",
            port=27018,
            username="test",
            password="test",
            database="dest_db"
        )
        
        migrator = DatabaseMigrationFactory.create_migrator(source_config, dest_config)
        
        assert isinstance(migrator, MongoMigrator)
        assert migrator.source_config == source_config
        assert migrator.destination_config == dest_config
    
    def test_create_redis_migrator(self):
        """Test creating Redis migrator through factory."""
        source_config = RedisConfig(
            host="localhost",
            port=6379,
            db=0,
            username="test",
            password="test"
        )
        
        dest_config = RedisConfig(
            host="localhost",
            port=6380,
            db=0,
            username="test",
            password="test"
        )
        
        migrator = DatabaseMigrationFactory.create_migrator(source_config, dest_config)
        
        assert isinstance(migrator, RedisMigrator)
        assert migrator.source_config == source_config
        assert migrator.destination_config == dest_config
    
    def test_get_supported_migrations(self):
        """Test getting supported migration combinations."""
        supported = DatabaseMigrationFactory.get_supported_migrations()
        
        # Check that all expected database types are supported
        assert 'mysql' in supported
        assert 'postgresql' in supported
        assert 'sqlite' in supported
        assert 'mongodb' in supported
        assert 'redis' in supported
        
        # Check that MySQL can migrate to MySQL and AWS RDS MySQL
        assert 'mysql' in supported['mysql']
        assert 'aws_rds_mysql' in supported['mysql']
    
    def test_is_migration_supported(self):
        """Test checking if specific migrations are supported."""
        # Same type migrations
        assert DatabaseMigrationFactory.is_migration_supported(
            DatabaseType.MYSQL, DatabaseType.MYSQL
        )
        
        # Cross-platform MySQL migrations
        assert DatabaseMigrationFactory.is_migration_supported(
            DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL
        )
        
        # PostgreSQL migrations
        assert DatabaseMigrationFactory.is_migration_supported(
            DatabaseType.POSTGRESQL, DatabaseType.POSTGRESQL
        )
        
        # NoSQL migrations
        assert DatabaseMigrationFactory.is_migration_supported(
            DatabaseType.MONGODB, DatabaseType.MONGODB
        )
        
        assert DatabaseMigrationFactory.is_migration_supported(
            DatabaseType.REDIS, DatabaseType.REDIS
        )
    
    def test_validate_migration_compatibility(self):
        """Test migration compatibility validation."""
        mysql_config = MySQLConfig(
            host="localhost",
            port=3306,
            username="test",
            password="test",
            database="test_db"
        )
        
        postgres_config = PostgreSQLConfig(
            host="localhost",
            port=5432,
            username="test",
            password="test",
            database="test_db"
        )
        
        # Same type should be compatible
        is_compatible, issues = DatabaseMigrationFactory.validate_migration_compatibility(
            mysql_config, mysql_config
        )
        assert is_compatible is True
        assert len(issues) == 0
        
        # Different types should have compatibility issues
        is_compatible, issues = DatabaseMigrationFactory.validate_migration_compatibility(
            mysql_config, postgres_config
        )
        assert is_compatible is False
        assert len(issues) > 0
    
    def test_get_recommended_method(self):
        """Test getting recommended migration methods."""
        mysql_config = MySQLConfig(
            host="localhost",
            port=3306,
            username="test",
            password="test",
            database="test_db"
        )
        
        postgres_config = PostgreSQLConfig(
            host="localhost",
            port=5432,
            username="test",
            password="test",
            database="test_db"
        )
        
        mongo_config = MongoConfig(
            host="localhost",
            port=27017,
            database="test_db"
        )
        
        # Same type migrations should recommend dump_restore
        method = DatabaseMigrationFactory.get_recommended_method(mysql_config, mysql_config)
        assert method == "dump_restore"
        
        # SQL to SQL should recommend direct_transfer
        method = DatabaseMigrationFactory.get_recommended_method(mysql_config, postgres_config)
        assert method == "direct_transfer"
        
        # Same type NoSQL should recommend dump_restore
        method = DatabaseMigrationFactory.get_recommended_method(mongo_config, mongo_config)
        assert method == "dump_restore"