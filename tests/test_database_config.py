"""Tests for database configuration models."""

import pytest
from pydantic import ValidationError

from migration_assistant.database.config import (
    DatabaseType,
    DatabaseConfig,
    MySQLConfig,
    PostgreSQLConfig,
    SQLiteConfig,
    MongoConfig,
    RedisConfig,
    AWSRDSConfig,
    GoogleCloudSQLConfig,
    AzureSQLConfig
)


class TestDatabaseConfig:
    """Test cases for base DatabaseConfig."""
    
    def test_basic_config_creation(self):
        """Test creating a basic database configuration."""
        config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="localhost",
            username="user",
            password="pass",
            database="testdb"
        )
        
        assert config.type == DatabaseType.MYSQL
        assert config.host == "localhost"
        assert config.username == "user"
        assert config.password == "pass"
        assert config.database == "testdb"
        assert config.ssl_enabled is False
        assert config.connection_timeout == 30
    
    def test_config_with_extra_params(self):
        """Test configuration with extra parameters."""
        config = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="localhost",
            extra_params={"application_name": "migration_tool"}
        )
        
        assert config.extra_params["application_name"] == "migration_tool"
    
    def test_invalid_connection_timeout(self):
        """Test validation of connection timeout."""
        with pytest.raises(ValidationError):
            DatabaseConfig(
                type=DatabaseType.MYSQL,
                host="localhost",
                connection_timeout=0  # Invalid: too low
            )
        
        with pytest.raises(ValidationError):
            DatabaseConfig(
                type=DatabaseType.MYSQL,
                host="localhost",
                connection_timeout=400  # Invalid: too high
            )


class TestMySQLConfig:
    """Test cases for MySQLConfig."""
    
    def test_mysql_config_defaults(self):
        """Test MySQL configuration with defaults."""
        config = MySQLConfig(
            host="localhost",
            username="root",
            password="secret",
            database="testdb"
        )
        
        assert config.type == DatabaseType.MYSQL
        assert config.port == 3306
        assert config.charset == "utf8mb4"
        assert config.autocommit is True
    
    def test_mysql_config_custom_port(self):
        """Test MySQL configuration with custom port."""
        config = MySQLConfig(
            host="localhost",
            port=3307,
            username="root",
            password="secret",
            database="testdb"
        )
        
        assert config.port == 3307
    
    def test_mysql_invalid_port(self):
        """Test MySQL configuration with invalid port."""
        with pytest.raises(ValidationError):
            MySQLConfig(
                host="localhost",
                port=70000,  # Invalid: too high
                username="root",
                password="secret",
                database="testdb"
            )


class TestPostgreSQLConfig:
    """Test cases for PostgreSQLConfig."""
    
    def test_postgresql_config_defaults(self):
        """Test PostgreSQL configuration with defaults."""
        config = PostgreSQLConfig(
            host="localhost",
            username="postgres",
            password="secret",
            database="testdb"
        )
        
        assert config.type == DatabaseType.POSTGRESQL
        assert config.port == 5432
        assert config.sslmode == "prefer"
    
    def test_postgresql_custom_sslmode(self):
        """Test PostgreSQL configuration with custom SSL mode."""
        config = PostgreSQLConfig(
            host="localhost",
            username="postgres",
            password="secret",
            database="testdb",
            sslmode="require"
        )
        
        assert config.sslmode == "require"
    
    def test_postgresql_invalid_sslmode(self):
        """Test PostgreSQL configuration with invalid SSL mode."""
        with pytest.raises(ValidationError):
            PostgreSQLConfig(
                host="localhost",
                username="postgres",
                password="secret",
                database="testdb",
                sslmode="invalid_mode"
            )


class TestSQLiteConfig:
    """Test cases for SQLiteConfig."""
    
    def test_sqlite_config(self):
        """Test SQLite configuration."""
        config = SQLiteConfig(
            database_path="/path/to/database.db"
        )
        
        assert config.type == DatabaseType.SQLITE
        assert config.host == "localhost"
        assert config.database_path == "/path/to/database.db"
        assert config.timeout == 20.0
        assert config.check_same_thread is False
    
    def test_sqlite_empty_database_path(self):
        """Test SQLite configuration with empty database path."""
        with pytest.raises(ValidationError):
            SQLiteConfig(database_path="")


class TestMongoConfig:
    """Test cases for MongoConfig."""
    
    def test_mongo_config_defaults(self):
        """Test MongoDB configuration with defaults."""
        config = MongoConfig(
            host="localhost",
            username="admin",
            password="secret",
            database="testdb"
        )
        
        assert config.type == DatabaseType.MONGODB
        assert config.port == 27017
        assert config.auth_source == "admin"
        assert config.read_preference == "primary"
    
    def test_mongo_config_with_replica_set(self):
        """Test MongoDB configuration with replica set."""
        config = MongoConfig(
            host="localhost",
            username="admin",
            password="secret",
            database="testdb",
            replica_set="rs0"
        )
        
        assert config.replica_set == "rs0"
    
    def test_mongo_invalid_read_preference(self):
        """Test MongoDB configuration with invalid read preference."""
        with pytest.raises(ValidationError):
            MongoConfig(
                host="localhost",
                username="admin",
                password="secret",
                database="testdb",
                read_preference="invalid_preference"
            )


class TestRedisConfig:
    """Test cases for RedisConfig."""
    
    def test_redis_config_defaults(self):
        """Test Redis configuration with defaults."""
        config = RedisConfig(
            host="localhost",
            password="secret"
        )
        
        assert config.type == DatabaseType.REDIS
        assert config.port == 6379
        assert config.db == 0
        assert config.decode_responses is True
        assert config.max_connections == 50
    
    def test_redis_custom_db(self):
        """Test Redis configuration with custom database number."""
        config = RedisConfig(
            host="localhost",
            password="secret",
            db=5
        )
        
        assert config.db == 5
    
    def test_redis_invalid_db(self):
        """Test Redis configuration with invalid database number."""
        with pytest.raises(ValidationError):
            RedisConfig(
                host="localhost",
                password="secret",
                db=20  # Invalid: too high
            )


class TestAWSRDSConfig:
    """Test cases for AWSRDSConfig."""
    
    def test_aws_rds_config(self):
        """Test AWS RDS configuration."""
        config = AWSRDSConfig(
            host="mydb.cluster-xyz.us-east-1.rds.amazonaws.com",
            region="us-east-1",
            engine="mysql",
            username="admin",
            password="secret",
            database="testdb"
        )
        
        assert config.cloud_provider == "aws"
        assert config.region == "us-east-1"
        assert config.engine == "mysql"
        assert config.multi_az is False
    
    def test_aws_rds_invalid_engine(self):
        """Test AWS RDS configuration with invalid engine."""
        with pytest.raises(ValidationError):
            AWSRDSConfig(
                host="mydb.cluster-xyz.us-east-1.rds.amazonaws.com",
                region="us-east-1",
                engine="invalid_engine",
                username="admin",
                password="secret",
                database="testdb"
            )


class TestGoogleCloudSQLConfig:
    """Test cases for GoogleCloudSQLConfig."""
    
    def test_gcp_sql_config(self):
        """Test Google Cloud SQL configuration."""
        config = GoogleCloudSQLConfig(
            host="10.0.0.1",
            region="us-central1",
            project_id="my-project",
            instance_id="my-instance",
            database_version="MYSQL_8_0",
            username="root",
            password="secret",
            database="testdb"
        )
        
        assert config.cloud_provider == "gcp"
        assert config.project_id == "my-project"
        assert config.instance_id == "my-instance"
        assert config.database_version == "MYSQL_8_0"
    
    def test_gcp_sql_invalid_version(self):
        """Test Google Cloud SQL configuration with invalid version."""
        with pytest.raises(ValidationError):
            GoogleCloudSQLConfig(
                host="10.0.0.1",
                region="us-central1",
                project_id="my-project",
                instance_id="my-instance",
                database_version="INVALID_VERSION",
                username="root",
                password="secret",
                database="testdb"
            )


class TestAzureSQLConfig:
    """Test cases for AzureSQLConfig."""
    
    def test_azure_sql_config(self):
        """Test Azure SQL configuration."""
        config = AzureSQLConfig(
            host="myserver.database.windows.net",
            region="East US",
            server_name="myserver",
            resource_group="myresourcegroup",
            subscription_id="12345678-1234-1234-1234-123456789012",
            username="admin",
            password="secret",
            database="testdb"
        )
        
        assert config.cloud_provider == "azure"
        assert config.server_name == "myserver"
        assert config.resource_group == "myresourcegroup"
        assert config.subscription_id == "12345678-1234-1234-1234-123456789012"