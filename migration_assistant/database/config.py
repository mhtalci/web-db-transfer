"""Database configuration models using Pydantic."""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, Union
from enum import Enum


class DatabaseType(str, Enum):
    """Supported database types."""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"
    AWS_RDS_MYSQL = "aws_rds_mysql"
    AWS_RDS_POSTGRESQL = "aws_rds_postgresql"
    GOOGLE_CLOUD_SQL = "google_cloud_sql"
    AZURE_SQL = "azure_sql"


class DatabaseConfig(BaseModel):
    """Base database configuration."""
    type: DatabaseType
    host: str
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    ssl_enabled: bool = False
    connection_timeout: int = Field(default=30, ge=1, le=300)
    extra_params: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class MySQLConfig(DatabaseConfig):
    """MySQL database configuration."""
    type: DatabaseType = DatabaseType.MYSQL
    port: int = 3306
    charset: str = "utf8mb4"
    autocommit: bool = True
    
    @validator('port')
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('Port must be between 1 and 65535')
        return v


class PostgreSQLConfig(DatabaseConfig):
    """PostgreSQL database configuration."""
    type: DatabaseType = DatabaseType.POSTGRESQL
    port: int = 5432
    sslmode: str = "prefer"
    
    @validator('sslmode')
    def validate_sslmode(cls, v):
        valid_modes = ['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']
        if v not in valid_modes:
            raise ValueError(f'sslmode must be one of: {", ".join(valid_modes)}')
        return v


class SQLiteConfig(DatabaseConfig):
    """SQLite database configuration."""
    type: DatabaseType = DatabaseType.SQLITE
    host: str = "localhost"  # Not used for SQLite
    database_path: str
    timeout: float = 20.0
    check_same_thread: bool = False
    
    @validator('database_path')
    def validate_database_path(cls, v):
        if not v:
            raise ValueError('database_path is required for SQLite')
        return v


class MongoConfig(DatabaseConfig):
    """MongoDB database configuration."""
    type: DatabaseType = DatabaseType.MONGODB
    port: int = 27017
    auth_source: str = "admin"
    replica_set: Optional[str] = None
    read_preference: str = "primary"
    
    @validator('read_preference')
    def validate_read_preference(cls, v):
        valid_prefs = ['primary', 'primaryPreferred', 'secondary', 'secondaryPreferred', 'nearest']
        if v not in valid_prefs:
            raise ValueError(f'read_preference must be one of: {", ".join(valid_prefs)}')
        return v


class RedisConfig(DatabaseConfig):
    """Redis database configuration."""
    type: DatabaseType = DatabaseType.REDIS
    port: int = 6379
    db: int = 0
    decode_responses: bool = True
    max_connections: int = 50
    
    @validator('db')
    def validate_db(cls, v):
        if not (0 <= v <= 15):
            raise ValueError('Redis db must be between 0 and 15')
        return v


class CloudDatabaseConfig(DatabaseConfig):
    """Cloud database configuration base."""
    region: str
    cloud_provider: str
    instance_identifier: Optional[str] = None
    vpc_security_groups: Optional[list] = None
    subnet_group: Optional[str] = None


class AWSRDSConfig(CloudDatabaseConfig):
    """AWS RDS database configuration."""
    type: DatabaseType = DatabaseType.AWS_RDS_MYSQL  # Default, can be overridden
    cloud_provider: str = "aws"
    engine: str  # mysql, postgres, etc.
    engine_version: Optional[str] = None
    instance_class: Optional[str] = None
    multi_az: bool = False
    
    @validator('engine')
    def validate_engine(cls, v):
        valid_engines = ['mysql', 'postgres', 'mariadb', 'oracle-ee', 'sqlserver-ex']
        if v not in valid_engines:
            raise ValueError(f'engine must be one of: {", ".join(valid_engines)}')
        return v


class GoogleCloudSQLConfig(CloudDatabaseConfig):
    """Google Cloud SQL database configuration."""
    type: DatabaseType = DatabaseType.GOOGLE_CLOUD_SQL
    cloud_provider: str = "gcp"
    project_id: str
    instance_id: str
    database_version: str  # MYSQL_8_0, POSTGRES_13, etc.
    tier: Optional[str] = None
    
    @validator('database_version')
    def validate_database_version(cls, v):
        valid_versions = ['MYSQL_5_7', 'MYSQL_8_0', 'POSTGRES_11', 'POSTGRES_12', 'POSTGRES_13', 'POSTGRES_14']
        if v not in valid_versions:
            raise ValueError(f'database_version must be one of: {", ".join(valid_versions)}')
        return v


class AzureSQLConfig(CloudDatabaseConfig):
    """Azure SQL database configuration."""
    type: DatabaseType = DatabaseType.AZURE_SQL
    cloud_provider: str = "azure"
    server_name: str
    resource_group: str
    subscription_id: str
    service_tier: Optional[str] = None
    compute_tier: Optional[str] = None


# Union type for all database configurations
DatabaseConfigUnion = Union[
    MySQLConfig,
    PostgreSQLConfig,
    SQLiteConfig,
    MongoConfig,
    RedisConfig,
    AWSRDSConfig,
    GoogleCloudSQLConfig,
    AzureSQLConfig
]