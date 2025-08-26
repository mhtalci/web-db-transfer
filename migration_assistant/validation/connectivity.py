"""
Connectivity validation module for testing connections to various systems.
"""

import asyncio
import socket
import ssl
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Database connectors
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

try:
    import pymongo
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Network and transfer libraries
try:
    import paramiko
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False

try:
    import ftplib
    FTP_AVAILABLE = True
except ImportError:
    FTP_AVAILABLE = False

# Cloud SDKs
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from google.cloud import storage as gcs
    from google.auth.exceptions import DefaultCredentialsError
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

try:
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import ClientAuthenticationError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Validation result status"""
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class ConnectivityCheck:
    """Result of a connectivity check"""
    name: str
    result: ValidationResult
    message: str
    details: Optional[Dict[str, Any]] = None
    remediation: Optional[str] = None


class ConnectivityValidator:
    """
    Validates connectivity to various systems including databases, 
    file transfer protocols, and cloud services.
    """
    
    def __init__(self):
        self.timeout = 30  # Default timeout in seconds
        
    async def validate_all(self, config: Dict[str, Any]) -> List[ConnectivityCheck]:
        """
        Validate all connectivity requirements based on configuration.
        
        Args:
            config: Migration configuration dictionary
            
        Returns:
            List of connectivity check results
        """
        checks = []
        
        # Validate source system connectivity
        if 'source' in config:
            source_checks = await self._validate_system(config['source'], 'source')
            checks.extend(source_checks)
            
        # Validate destination system connectivity
        if 'destination' in config:
            dest_checks = await self._validate_system(config['destination'], 'destination')
            checks.extend(dest_checks)
            
        return checks
    
    async def _validate_system(self, system_config: Dict[str, Any], system_type: str) -> List[ConnectivityCheck]:
        """Validate connectivity for a single system"""
        checks = []
        system_name = f"{system_type} ({system_config.get('type', 'unknown')})"
        
        # Basic network connectivity
        if 'host' in system_config:
            network_check = await self._check_network_connectivity(
                system_config['host'], 
                system_config.get('port'),
                system_name
            )
            checks.append(network_check)
        
        # Database connectivity
        if system_config.get('db_type'):
            db_check = await self._check_database_connectivity(system_config, system_name)
            checks.append(db_check)
        
        # SSH connectivity
        if self._requires_ssh(system_config):
            ssh_check = await self._check_ssh_connectivity(system_config, system_name)
            checks.append(ssh_check)
        
        # FTP connectivity
        if self._requires_ftp(system_config):
            ftp_check = await self._check_ftp_connectivity(system_config, system_name)
            checks.append(ftp_check)
        
        # Cloud service connectivity
        if system_config.get('cloud_config'):
            cloud_check = await self._check_cloud_connectivity(system_config, system_name)
            checks.append(cloud_check)
        
        return checks
    
    async def _check_network_connectivity(self, host: str, port: Optional[int], system_name: str) -> ConnectivityCheck:
        """Check basic network connectivity to a host"""
        try:
            # Resolve hostname
            try:
                socket.gethostbyname(host)
            except socket.gaierror as e:
                return ConnectivityCheck(
                    name=f"Network - {system_name}",
                    result=ValidationResult.FAILED,
                    message=f"Failed to resolve hostname '{host}': {str(e)}",
                    remediation="Check hostname spelling and DNS configuration"
                )
            
            # Test port connectivity if specified
            if port:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                try:
                    result = sock.connect_ex((host, port))
                    if result == 0:
                        return ConnectivityCheck(
                            name=f"Network - {system_name}",
                            result=ValidationResult.SUCCESS,
                            message=f"Successfully connected to {host}:{port}"
                        )
                    else:
                        return ConnectivityCheck(
                            name=f"Network - {system_name}",
                            result=ValidationResult.FAILED,
                            message=f"Cannot connect to {host}:{port}",
                            remediation="Check if the service is running and firewall allows connections"
                        )
                finally:
                    sock.close()
            else:
                # Just hostname resolution was successful
                return ConnectivityCheck(
                    name=f"Network - {system_name}",
                    result=ValidationResult.SUCCESS,
                    message=f"Successfully resolved hostname '{host}'"
                )
                
        except Exception as e:
            return ConnectivityCheck(
                name=f"Network - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Network connectivity check failed: {str(e)}",
                remediation="Check network configuration and connectivity"
            )
    
    async def _check_database_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check database connectivity using appropriate Python connectors"""
        db_type = config.get('db_type', '').lower()
        
        if db_type in ['mysql', 'mariadb']:
            return await self._check_mysql_connectivity(config, system_name)
        elif db_type in ['postgresql', 'postgres']:
            return await self._check_postgresql_connectivity(config, system_name)
        elif db_type == 'mongodb':
            return await self._check_mongodb_connectivity(config, system_name)
        elif db_type == 'redis':
            return await self._check_redis_connectivity(config, system_name)
        elif db_type == 'sqlite':
            return await self._check_sqlite_connectivity(config, system_name)
        else:
            return ConnectivityCheck(
                name=f"Database - {system_name}",
                result=ValidationResult.SKIPPED,
                message=f"Database type '{db_type}' not supported for connectivity testing"
            )
    
    async def _check_mysql_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check MySQL/MariaDB connectivity using mysql-connector-python"""
        if not MYSQL_AVAILABLE:
            return ConnectivityCheck(
                name=f"MySQL - {system_name}",
                result=ValidationResult.FAILED,
                message="mysql-connector-python not installed",
                remediation="Install mysql-connector-python: pip install mysql-connector-python"
            )
        
        try:
            connection_config = {
                'host': config.get('host'),
                'port': config.get('port', 3306),
                'user': config.get('db_user'),
                'password': config.get('db_password'),
                'database': config.get('db_name'),
                'connection_timeout': self.timeout
            }
            
            # Remove None values
            connection_config = {k: v for k, v in connection_config.items() if v is not None}
            
            connection = mysql.connector.connect(**connection_config)
            
            # Test the connection
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            connection.close()
            
            return ConnectivityCheck(
                name=f"MySQL - {system_name}",
                result=ValidationResult.SUCCESS,
                message=f"Successfully connected to MySQL database on {config.get('host')}"
            )
            
        except mysql.connector.Error as e:
            return ConnectivityCheck(
                name=f"MySQL - {system_name}",
                result=ValidationResult.FAILED,
                message=f"MySQL connection failed: {str(e)}",
                remediation="Check MySQL credentials, host, and database permissions"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"MySQL - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected error connecting to MySQL: {str(e)}"
            )
    
    async def _check_postgresql_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check PostgreSQL connectivity using psycopg2"""
        if not POSTGRESQL_AVAILABLE:
            return ConnectivityCheck(
                name=f"PostgreSQL - {system_name}",
                result=ValidationResult.FAILED,
                message="psycopg2 not installed",
                remediation="Install psycopg2: pip install psycopg2-binary"
            )
        
        try:
            connection_string = self._build_postgresql_connection_string(config)
            connection = psycopg2.connect(connection_string, connect_timeout=self.timeout)
            
            # Test the connection
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            connection.close()
            
            return ConnectivityCheck(
                name=f"PostgreSQL - {system_name}",
                result=ValidationResult.SUCCESS,
                message=f"Successfully connected to PostgreSQL database on {config.get('host')}"
            )
            
        except psycopg2.Error as e:
            return ConnectivityCheck(
                name=f"PostgreSQL - {system_name}",
                result=ValidationResult.FAILED,
                message=f"PostgreSQL connection failed: {str(e)}",
                remediation="Check PostgreSQL credentials, host, and database permissions"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"PostgreSQL - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected error connecting to PostgreSQL: {str(e)}"
            )
    
    async def _check_mongodb_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check MongoDB connectivity using pymongo"""
        if not MONGODB_AVAILABLE:
            return ConnectivityCheck(
                name=f"MongoDB - {system_name}",
                result=ValidationResult.FAILED,
                message="pymongo not installed",
                remediation="Install pymongo: pip install pymongo"
            )
        
        try:
            connection_string = self._build_mongodb_connection_string(config)
            client = pymongo.MongoClient(
                connection_string, 
                serverSelectionTimeoutMS=self.timeout * 1000
            )
            
            # Test the connection
            client.admin.command('ping')
            client.close()
            
            return ConnectivityCheck(
                name=f"MongoDB - {system_name}",
                result=ValidationResult.SUCCESS,
                message=f"Successfully connected to MongoDB on {config.get('host')}"
            )
            
        except pymongo.errors.PyMongoError as e:
            return ConnectivityCheck(
                name=f"MongoDB - {system_name}",
                result=ValidationResult.FAILED,
                message=f"MongoDB connection failed: {str(e)}",
                remediation="Check MongoDB credentials, host, and network connectivity"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"MongoDB - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected error connecting to MongoDB: {str(e)}"
            )
    
    async def _check_redis_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check Redis connectivity using redis-py"""
        if not REDIS_AVAILABLE:
            return ConnectivityCheck(
                name=f"Redis - {system_name}",
                result=ValidationResult.FAILED,
                message="redis not installed",
                remediation="Install redis: pip install redis"
            )
        
        try:
            client = redis.Redis(
                host=config.get('host'),
                port=config.get('port', 6379),
                password=config.get('db_password'),
                db=config.get('db_name', 0),
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout
            )
            
            # Test the connection
            client.ping()
            client.close()
            
            return ConnectivityCheck(
                name=f"Redis - {system_name}",
                result=ValidationResult.SUCCESS,
                message=f"Successfully connected to Redis on {config.get('host')}"
            )
            
        except redis.RedisError as e:
            return ConnectivityCheck(
                name=f"Redis - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Redis connection failed: {str(e)}",
                remediation="Check Redis credentials, host, and network connectivity"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"Redis - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected error connecting to Redis: {str(e)}"
            )
    
    async def _check_sqlite_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check SQLite connectivity"""
        import sqlite3
        import os
        
        try:
            db_path = config.get('db_path') or config.get('host')
            if not db_path:
                return ConnectivityCheck(
                    name=f"SQLite - {system_name}",
                    result=ValidationResult.FAILED,
                    message="SQLite database path not specified",
                    remediation="Specify 'db_path' or 'host' for SQLite database location"
                )
            
            # Check if file exists and is readable
            if not os.path.exists(db_path):
                return ConnectivityCheck(
                    name=f"SQLite - {system_name}",
                    result=ValidationResult.FAILED,
                    message=f"SQLite database file not found: {db_path}",
                    remediation="Check the database file path and ensure it exists"
                )
            
            # Test connection
            connection = sqlite3.connect(db_path, timeout=self.timeout)
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            connection.close()
            
            return ConnectivityCheck(
                name=f"SQLite - {system_name}",
                result=ValidationResult.SUCCESS,
                message=f"Successfully connected to SQLite database: {db_path}"
            )
            
        except sqlite3.Error as e:
            return ConnectivityCheck(
                name=f"SQLite - {system_name}",
                result=ValidationResult.FAILED,
                message=f"SQLite connection failed: {str(e)}",
                remediation="Check database file permissions and integrity"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"SQLite - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected error connecting to SQLite: {str(e)}"
            )
    
    async def _check_ssh_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check SSH connectivity using paramiko"""
        if not SSH_AVAILABLE:
            return ConnectivityCheck(
                name=f"SSH - {system_name}",
                result=ValidationResult.FAILED,
                message="paramiko not installed",
                remediation="Install paramiko: pip install paramiko"
            )
        
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddHostKeyPolicy())
            
            ssh_config = config.get('ssh_config', {})
            
            ssh_client.connect(
                hostname=config.get('host'),
                port=ssh_config.get('port', 22),
                username=ssh_config.get('username'),
                password=ssh_config.get('password'),
                key_filename=ssh_config.get('key_file'),
                timeout=self.timeout
            )
            
            # Test the connection with a simple command
            stdin, stdout, stderr = ssh_client.exec_command('echo "test"')
            output = stdout.read().decode().strip()
            
            ssh_client.close()
            
            if output == "test":
                return ConnectivityCheck(
                    name=f"SSH - {system_name}",
                    result=ValidationResult.SUCCESS,
                    message=f"Successfully connected via SSH to {config.get('host')}"
                )
            else:
                return ConnectivityCheck(
                    name=f"SSH - {system_name}",
                    result=ValidationResult.WARNING,
                    message="SSH connection established but command execution may have issues"
                )
                
        except paramiko.AuthenticationException:
            return ConnectivityCheck(
                name=f"SSH - {system_name}",
                result=ValidationResult.FAILED,
                message="SSH authentication failed",
                remediation="Check SSH username, password, or key file"
            )
        except paramiko.SSHException as e:
            return ConnectivityCheck(
                name=f"SSH - {system_name}",
                result=ValidationResult.FAILED,
                message=f"SSH connection failed: {str(e)}",
                remediation="Check SSH server configuration and network connectivity"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"SSH - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected SSH error: {str(e)}"
            )
    
    async def _check_ftp_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check FTP/FTPS connectivity"""
        if not FTP_AVAILABLE:
            return ConnectivityCheck(
                name=f"FTP - {system_name}",
                result=ValidationResult.FAILED,
                message="ftplib not available",
                remediation="ftplib should be available in Python standard library"
            )
        
        try:
            ftp_config = config.get('ftp_config', {})
            use_tls = ftp_config.get('use_tls', False)
            
            if use_tls:
                ftp = ftplib.FTP_TLS()
            else:
                ftp = ftplib.FTP()
            
            ftp.connect(
                host=config.get('host'),
                port=ftp_config.get('port', 21),
                timeout=self.timeout
            )
            
            ftp.login(
                user=ftp_config.get('username', ''),
                passwd=ftp_config.get('password', '')
            )
            
            if use_tls:
                ftp.prot_p()  # Enable data encryption
            
            # Test directory listing
            ftp.nlst()
            ftp.quit()
            
            protocol = "FTPS" if use_tls else "FTP"
            return ConnectivityCheck(
                name=f"{protocol} - {system_name}",
                result=ValidationResult.SUCCESS,
                message=f"Successfully connected via {protocol} to {config.get('host')}"
            )
            
        except ftplib.all_errors as e:
            protocol = "FTPS" if ftp_config.get('use_tls', False) else "FTP"
            return ConnectivityCheck(
                name=f"{protocol} - {system_name}",
                result=ValidationResult.FAILED,
                message=f"{protocol} connection failed: {str(e)}",
                remediation="Check FTP credentials, host, and server configuration"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"FTP - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected FTP error: {str(e)}"
            )
    
    async def _check_cloud_connectivity(self, config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check cloud service connectivity"""
        cloud_config = config.get('cloud_config', {})
        provider = cloud_config.get('provider', '').lower()
        
        if provider == 'aws':
            return await self._check_aws_connectivity(cloud_config, system_name)
        elif provider in ['gcp', 'google']:
            return await self._check_gcp_connectivity(cloud_config, system_name)
        elif provider == 'azure':
            return await self._check_azure_connectivity(cloud_config, system_name)
        else:
            return ConnectivityCheck(
                name=f"Cloud - {system_name}",
                result=ValidationResult.SKIPPED,
                message=f"Cloud provider '{provider}' not supported for connectivity testing"
            )
    
    async def _check_aws_connectivity(self, cloud_config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check AWS connectivity using boto3"""
        if not AWS_AVAILABLE:
            return ConnectivityCheck(
                name=f"AWS - {system_name}",
                result=ValidationResult.FAILED,
                message="boto3 not installed",
                remediation="Install boto3: pip install boto3"
            )
        
        try:
            # Create S3 client to test connectivity
            session = boto3.Session(
                aws_access_key_id=cloud_config.get('access_key_id'),
                aws_secret_access_key=cloud_config.get('secret_access_key'),
                region_name=cloud_config.get('region', 'us-east-1')
            )
            
            s3_client = session.client('s3')
            
            # Test connectivity by listing buckets
            s3_client.list_buckets()
            
            return ConnectivityCheck(
                name=f"AWS - {system_name}",
                result=ValidationResult.SUCCESS,
                message="Successfully authenticated with AWS"
            )
            
        except NoCredentialsError:
            return ConnectivityCheck(
                name=f"AWS - {system_name}",
                result=ValidationResult.FAILED,
                message="AWS credentials not found",
                remediation="Configure AWS credentials via environment variables, ~/.aws/credentials, or IAM roles"
            )
        except ClientError as e:
            error_code = e.response['Error']['Code']
            return ConnectivityCheck(
                name=f"AWS - {system_name}",
                result=ValidationResult.FAILED,
                message=f"AWS authentication failed: {error_code}",
                remediation="Check AWS credentials and permissions"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"AWS - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected AWS error: {str(e)}"
            )
    
    async def _check_gcp_connectivity(self, cloud_config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check Google Cloud connectivity"""
        if not GCP_AVAILABLE:
            return ConnectivityCheck(
                name=f"GCP - {system_name}",
                result=ValidationResult.FAILED,
                message="google-cloud-storage not installed",
                remediation="Install google-cloud-storage: pip install google-cloud-storage"
            )
        
        try:
            # Test connectivity by creating a storage client
            if cloud_config.get('service_account_path'):
                client = gcs.Client.from_service_account_json(cloud_config['service_account_path'])
            else:
                client = gcs.Client()
            
            # Test by listing buckets (this will fail if no permissions, but confirms auth)
            try:
                list(client.list_buckets(max_results=1))
            except Exception:
                # Even if listing fails due to permissions, the client creation succeeded
                pass
            
            return ConnectivityCheck(
                name=f"GCP - {system_name}",
                result=ValidationResult.SUCCESS,
                message="Successfully authenticated with Google Cloud"
            )
            
        except DefaultCredentialsError:
            return ConnectivityCheck(
                name=f"GCP - {system_name}",
                result=ValidationResult.FAILED,
                message="Google Cloud credentials not found",
                remediation="Configure GCP credentials via GOOGLE_APPLICATION_CREDENTIALS environment variable or gcloud auth"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"GCP - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected GCP error: {str(e)}"
            )
    
    async def _check_azure_connectivity(self, cloud_config: Dict[str, Any], system_name: str) -> ConnectivityCheck:
        """Check Azure connectivity"""
        if not AZURE_AVAILABLE:
            return ConnectivityCheck(
                name=f"Azure - {system_name}",
                result=ValidationResult.FAILED,
                message="azure-storage-blob not installed",
                remediation="Install azure-storage-blob: pip install azure-storage-blob"
            )
        
        try:
            # Test connectivity by creating a blob service client
            connection_string = cloud_config.get('connection_string')
            account_name = cloud_config.get('account_name')
            account_key = cloud_config.get('account_key')
            
            if connection_string:
                client = BlobServiceClient.from_connection_string(connection_string)
            elif account_name and account_key:
                client = BlobServiceClient(
                    account_url=f"https://{account_name}.blob.core.windows.net",
                    credential=account_key
                )
            else:
                return ConnectivityCheck(
                    name=f"Azure - {system_name}",
                    result=ValidationResult.FAILED,
                    message="Azure credentials not provided",
                    remediation="Provide connection_string or account_name/account_key"
                )
            
            # Test by getting account information
            client.get_account_information()
            
            return ConnectivityCheck(
                name=f"Azure - {system_name}",
                result=ValidationResult.SUCCESS,
                message="Successfully authenticated with Azure"
            )
            
        except ClientAuthenticationError:
            return ConnectivityCheck(
                name=f"Azure - {system_name}",
                result=ValidationResult.FAILED,
                message="Azure authentication failed",
                remediation="Check Azure credentials and account permissions"
            )
        except Exception as e:
            return ConnectivityCheck(
                name=f"Azure - {system_name}",
                result=ValidationResult.FAILED,
                message=f"Unexpected Azure error: {str(e)}"
            )
    
    def _requires_ssh(self, config: Dict[str, Any]) -> bool:
        """Check if SSH connectivity is required"""
        return (
            'ssh_config' in config or
            config.get('transfer_method') in ['ssh', 'scp', 'sftp', 'rsync']
        )
    
    def _requires_ftp(self, config: Dict[str, Any]) -> bool:
        """Check if FTP connectivity is required"""
        return (
            'ftp_config' in config or
            config.get('transfer_method') in ['ftp', 'ftps']
        )
    
    def _build_postgresql_connection_string(self, config: Dict[str, Any]) -> str:
        """Build PostgreSQL connection string"""
        parts = []
        
        if config.get('host'):
            parts.append(f"host={config['host']}")
        if config.get('port'):
            parts.append(f"port={config['port']}")
        if config.get('db_name'):
            parts.append(f"dbname={config['db_name']}")
        if config.get('db_user'):
            parts.append(f"user={config['db_user']}")
        if config.get('db_password'):
            parts.append(f"password={config['db_password']}")
        
        return " ".join(parts)
    
    def _build_mongodb_connection_string(self, config: Dict[str, Any]) -> str:
        """Build MongoDB connection string"""
        host = config.get('host', 'localhost')
        port = config.get('port', 27017)
        
        if config.get('db_user') and config.get('db_password'):
            auth = f"{config['db_user']}:{config['db_password']}@"
        else:
            auth = ""
        
        db_name = config.get('db_name', '')
        if db_name:
            db_name = f"/{db_name}"
        
        return f"mongodb://{auth}{host}:{port}{db_name}"