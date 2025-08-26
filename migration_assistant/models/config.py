"""
Configuration models for the Migration Assistant.

This module defines Pydantic models for migration configuration,
system configuration, and related data structures.
"""

from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, ConfigDict


class AuthType(str, Enum):
    """Authentication types supported by the system."""
    PASSWORD = "password"
    SSH_KEY = "ssh_key"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    AWS_IAM = "aws_iam"
    GOOGLE_SERVICE_ACCOUNT = "google_service_account"
    AZURE_AD = "azure_ad"


class DatabaseType(str, Enum):
    """Database types supported by the system."""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"
    CASSANDRA = "cassandra"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    AWS_RDS = "aws_rds"
    GOOGLE_CLOUD_SQL = "google_cloud_sql"
    AZURE_SQL = "azure_sql"


class TransferMethod(str, Enum):
    """File transfer methods supported by the system."""
    SSH_SCP = "ssh_scp"
    SSH_SFTP = "ssh_sftp"
    RSYNC = "rsync"
    FTP = "ftp"
    FTPS = "ftps"
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD_STORAGE = "google_cloud_storage"
    AZURE_BLOB = "azure_blob"
    DOCKER_VOLUME = "docker_volume"
    KUBERNETES_VOLUME = "kubernetes_volume"
    LOCAL_COPY = "local_copy"
    HYBRID_SYNC = "hybrid_sync"  # Uses Go for performance


class SystemType(str, Enum):
    """System types supported by the migration assistant."""
    WORDPRESS = "wordpress"
    DRUPAL = "drupal"
    JOOMLA = "joomla"
    DJANGO = "django"
    FLASK = "flask"
    FASTAPI = "fastapi"
    LARAVEL = "laravel"
    RAILS = "rails"
    SPRING_BOOT = "spring_boot"
    NEXTJS = "nextjs"
    STATIC_SITE = "static_site"
    DOCKER_CONTAINER = "docker_container"
    KUBERNETES_POD = "kubernetes_pod"
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD_STORAGE = "google_cloud_storage"
    AZURE_BLOB = "azure_blob"
    CPANEL = "cpanel"
    DIRECTADMIN = "directadmin"
    PLESK = "plesk"


class ControlPanelType(str, Enum):
    """Control panel types supported by the system."""
    CPANEL = "cpanel"
    DIRECTADMIN = "directadmin"
    PLESK = "plesk"


class AuthConfig(BaseModel):
    """Authentication configuration for system access."""
    type: AuthType
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    token: Optional[str] = None
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    service_account_path: Optional[str] = None
    additional_params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('username')
    @classmethod
    def username_required_for_password_auth(cls, v, info):
        if info.data.get('type') == AuthType.PASSWORD and not v:
            raise ValueError('Username is required for password authentication')
        return v

    @field_validator('password')
    @classmethod
    def password_required_for_password_auth(cls, v, info):
        if info.data.get('type') == AuthType.PASSWORD and not v:
            raise ValueError('Password is required for password authentication')
        return v


class PathConfig(BaseModel):
    """Path configuration for file system access."""
    root_path: str = Field(..., description="Root path for the system")
    web_root: Optional[str] = None
    config_path: Optional[str] = None
    logs_path: Optional[str] = None
    backup_path: Optional[str] = None
    temp_path: Optional[str] = None
    exclude_patterns: List[str] = Field(default_factory=list)
    include_patterns: List[str] = Field(default_factory=list)


class DatabaseConfig(BaseModel):
    """Database configuration."""
    type: DatabaseType
    host: str
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    connection_params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('port')
    @classmethod
    def set_default_port(cls, v, info):
        if v is None and 'type' in info.data:
            default_ports = {
                DatabaseType.MYSQL: 3306,
                DatabaseType.POSTGRESQL: 5432,
                DatabaseType.MONGODB: 27017,
                DatabaseType.REDIS: 6379,
                DatabaseType.CASSANDRA: 9042,
                DatabaseType.ORACLE: 1521,
                DatabaseType.SQLSERVER: 1433,
            }
            return default_ports.get(info.data['type'])
        return v


class CloudConfig(BaseModel):
    """Cloud provider configuration."""
    provider: str  # aws, gcp, azure, etc.
    region: Optional[str] = None
    bucket_name: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    project_id: Optional[str] = None
    service_account_path: Optional[str] = None
    subscription_id: Optional[str] = None
    resource_group: Optional[str] = None
    additional_config: Dict[str, Any] = Field(default_factory=dict)


class ControlPanelConfig(BaseModel):
    """Control panel configuration."""
    type: ControlPanelType
    host: str
    port: int = 2083
    username: str
    password: Optional[str] = None
    api_token: Optional[str] = None
    ssl_enabled: bool = True
    accounts: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)


class TransferConfig(BaseModel):
    """File transfer configuration."""
    method: TransferMethod
    parallel_transfers: int = Field(default=4, ge=1, le=16)
    chunk_size: int = Field(default=8192, ge=1024)
    compression_enabled: bool = False
    compression_level: int = Field(default=6, ge=1, le=9)
    verify_checksums: bool = True
    resume_on_failure: bool = True
    bandwidth_limit: Optional[int] = None  # KB/s
    timeout: int = Field(default=300, ge=30)  # seconds
    retry_attempts: int = Field(default=3, ge=0, le=10)
    use_go_acceleration: bool = True


class MigrationOptions(BaseModel):
    """Migration execution options."""
    maintenance_mode: bool = False
    backup_before: bool = True
    backup_destination: bool = False
    verify_after: bool = True
    rollback_on_failure: bool = True
    preserve_permissions: bool = True
    preserve_timestamps: bool = True
    preserve_email_accounts: bool = False
    migrate_dns_records: bool = False
    dry_run: bool = False
    force_overwrite: bool = False
    skip_existing: bool = False
    delete_source_after: bool = False
    notification_webhook: Optional[str] = None
    custom_scripts: Dict[str, str] = Field(default_factory=dict)


class SystemConfig(BaseModel):
    """System configuration for source or destination."""
    type: SystemType
    host: str
    port: Optional[int] = None
    authentication: AuthConfig
    paths: PathConfig
    database: Optional[DatabaseConfig] = None
    cloud_config: Optional[CloudConfig] = None
    control_panel: Optional[ControlPanelConfig] = None
    environment_variables: Dict[str, str] = Field(default_factory=dict)
    custom_config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('database')
    @classmethod
    def database_required_for_dynamic_systems(cls, v, info):
        dynamic_systems = {
            SystemType.WORDPRESS, SystemType.DRUPAL, SystemType.JOOMLA,
            SystemType.DJANGO, SystemType.LARAVEL, SystemType.RAILS
        }
        if info.data.get('type') in dynamic_systems and not v:
            raise ValueError(f'Database configuration is required for {info.data.get("type")} systems')
        return v


class MigrationConfig(BaseModel):
    """Complete migration configuration."""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    source: SystemConfig
    destination: SystemConfig
    transfer: TransferConfig
    options: MigrationOptions
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: Optional[str] = None
    tenant_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        # Use serializers instead of json_encoders for Pydantic v2
        ser_json_timedelta='iso8601'
    )

    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Migration name cannot be empty')
        return v.strip()

    @field_validator('source', 'destination')
    @classmethod
    def validate_system_configs(cls, v):
        if not v.host or not v.host.strip():
            raise ValueError('System host cannot be empty')
        return v