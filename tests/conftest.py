"""
Pytest configuration and fixtures for the Migration Assistant tests.

This module provides common fixtures and configuration for all tests including
Docker-based test environments, mock services, and comprehensive test data.
"""

import pytest
import docker
import asyncio
import tempfile
import shutil
import os
import time
import json
from datetime import datetime
from typing import Dict, Any, Generator, List, Optional
from unittest.mock import Mock, AsyncMock, MagicMock
from pathlib import Path

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
)


@pytest.fixture
def sample_auth_config() -> AuthConfig:
    """Sample authentication configuration."""
    return AuthConfig(
        type=AuthType.PASSWORD,
        username="testuser",
        password="testpass"
    )


@pytest.fixture
def sample_path_config() -> PathConfig:
    """Sample path configuration."""
    return PathConfig(
        root_path="/var/www/html",
        web_root="/var/www/html/public",
        config_path="/var/www/html/config",
        logs_path="/var/www/html/logs"
    )


@pytest.fixture
def sample_database_config() -> DatabaseConfig:
    """Sample database configuration."""
    return DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="localhost",
        port=3306,
        database_name="testdb",
        username="dbuser",
        password="dbpass"
    )


@pytest.fixture
def sample_system_config(
    sample_auth_config: AuthConfig,
    sample_path_config: PathConfig,
    sample_database_config: DatabaseConfig
) -> SystemConfig:
    """Sample system configuration."""
    return SystemConfig(
        type=SystemType.WORDPRESS,
        host="example.com",
        port=80,
        authentication=sample_auth_config,
        paths=sample_path_config,
        database=sample_database_config
    )


@pytest.fixture
def sample_transfer_config() -> TransferConfig:
    """Sample transfer configuration."""
    return TransferConfig(
        method=TransferMethod.SSH_SCP,
        parallel_transfers=2,
        chunk_size=4096,
        compression_enabled=True,
        verify_checksums=True
    )


@pytest.fixture
def sample_migration_options() -> MigrationOptions:
    """Sample migration options."""
    return MigrationOptions(
        maintenance_mode=True,
        backup_before=True,
        verify_after=True,
        rollback_on_failure=True
    )


@pytest.fixture
def sample_migration_config(
    sample_system_config: SystemConfig,
    sample_transfer_config: TransferConfig,
    sample_migration_options: MigrationOptions
) -> MigrationConfig:
    """Sample migration configuration."""
    destination_config = sample_system_config.copy()
    destination_config.host = "destination.com"
    destination_config.type = SystemType.AWS_S3
    
    return MigrationConfig(
        name="Test Migration",
        description="A test migration configuration",
        source=sample_system_config,
        destination=destination_config,
        transfer=sample_transfer_config,
        options=sample_migration_options
    )


@pytest.fixture
def sample_migration_step() -> MigrationStep:
    """Sample migration step."""
    return MigrationStep(
        id="step_1",
        name="Test Step",
        description="A test migration step",
        status=StepStatus.PENDING
    )


@pytest.fixture
def sample_migration_session(
    sample_migration_config: MigrationConfig,
    sample_migration_step: MigrationStep
) -> MigrationSession:
    """Sample migration session."""
    session = MigrationSession(
        id="session_123",
        config=sample_migration_config,
        status=MigrationStatus.PENDING
    )
    session.add_step(sample_migration_step)
    return session


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing."""
    return datetime(2024, 1, 1, 12, 0, 0)


# Docker-based test environment fixtures
@pytest.fixture(scope="session")
def docker_client():
    """Docker client for managing test containers."""
    try:
        client = docker.from_env()
        # Test Docker connection
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.fixture(scope="session")
def test_databases(docker_client):
    """Spin up test databases in containers."""
    containers = {}
    
    try:
        # MySQL test database
        mysql_container = docker_client.containers.run(
            "mysql:8.0",
            environment={
                "MYSQL_ROOT_PASSWORD": "testpass",
                "MYSQL_DATABASE": "testdb",
                "MYSQL_USER": "testuser",
                "MYSQL_PASSWORD": "testpass"
            },
            ports={"3306/tcp": None},
            detach=True,
            remove=True,
            name="migration_test_mysql"
        )
        containers["mysql"] = mysql_container
        
        # PostgreSQL test database
        postgres_container = docker_client.containers.run(
            "postgres:15",
            environment={
                "POSTGRES_PASSWORD": "testpass",
                "POSTGRES_DB": "testdb",
                "POSTGRES_USER": "testuser"
            },
            ports={"5432/tcp": None},
            detach=True,
            remove=True,
            name="migration_test_postgres"
        )
        containers["postgres"] = postgres_container
        
        # MongoDB test database
        mongo_container = docker_client.containers.run(
            "mongo:6.0",
            ports={"27017/tcp": None},
            detach=True,
            remove=True,
            name="migration_test_mongo"
        )
        containers["mongo"] = mongo_container
        
        # Redis test database
        redis_container = docker_client.containers.run(
            "redis:7-alpine",
            ports={"6379/tcp": None},
            detach=True,
            remove=True,
            name="migration_test_redis"
        )
        containers["redis"] = redis_container
        
        # Wait for containers to be ready
        time.sleep(10)
        
        # Get container ports
        for name, container in containers.items():
            container.reload()
            if name == "mysql":
                port = container.attrs['NetworkSettings']['Ports']['3306/tcp'][0]['HostPort']
                containers[f"{name}_port"] = int(port)
            elif name == "postgres":
                port = container.attrs['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']
                containers[f"{name}_port"] = int(port)
            elif name == "mongo":
                port = container.attrs['NetworkSettings']['Ports']['27017/tcp'][0]['HostPort']
                containers[f"{name}_port"] = int(port)
            elif name == "redis":
                port = container.attrs['NetworkSettings']['Ports']['6379/tcp'][0]['HostPort']
                containers[f"{name}_port"] = int(port)
        
        yield containers
        
    finally:
        # Cleanup
        for name, container in containers.items():
            if isinstance(container, docker.models.containers.Container):
                try:
                    container.stop()
                    container.remove()
                except Exception:
                    pass


@pytest.fixture(scope="session")
def mock_cloud_services():
    """Mock cloud services for testing."""
    services = {}
    
    # Mock AWS S3
    class MockS3Client:
        def __init__(self):
            self.buckets = {}
            self.objects = {}
        
        def create_bucket(self, Bucket):
            self.buckets[Bucket] = {}
            return {"Location": f"/{Bucket}"}
        
        def put_object(self, Bucket, Key, Body):
            if Bucket not in self.buckets:
                self.buckets[Bucket] = {}
            self.objects[f"{Bucket}/{Key}"] = Body
            return {"ETag": "mock-etag"}
        
        def get_object(self, Bucket, Key):
            key = f"{Bucket}/{Key}"
            if key in self.objects:
                return {"Body": self.objects[key]}
            raise Exception("NoSuchKey")
        
        def list_objects_v2(self, Bucket, Prefix=""):
            objects = []
            for key in self.objects:
                if key.startswith(f"{Bucket}/{Prefix}"):
                    objects.append({"Key": key.split("/", 1)[1]})
            return {"Contents": objects}
    
    services["s3"] = MockS3Client()
    
    # Mock Google Cloud Storage
    class MockGCSClient:
        def __init__(self):
            self.buckets = {}
        
        def bucket(self, name):
            if name not in self.buckets:
                self.buckets[name] = MockGCSBucket(name)
            return self.buckets[name]
    
    class MockGCSBucket:
        def __init__(self, name):
            self.name = name
            self.blobs = {}
        
        def blob(self, name):
            return MockGCSBlob(name, self)
        
        def list_blobs(self, prefix=""):
            return [blob for name, blob in self.blobs.items() if name.startswith(prefix)]
    
    class MockGCSBlob:
        def __init__(self, name, bucket):
            self.name = name
            self.bucket = bucket
            self.data = None
        
        def upload_from_string(self, data):
            self.data = data
            self.bucket.blobs[self.name] = self
        
        def download_as_text(self):
            return self.data
    
    services["gcs"] = MockGCSClient()
    
    # Mock Azure Blob Storage
    class MockAzureBlobClient:
        def __init__(self):
            self.containers = {}
        
        def get_container_client(self, container):
            if container not in self.containers:
                self.containers[container] = MockAzureContainer(container)
            return self.containers[container]
    
    class MockAzureContainer:
        def __init__(self, name):
            self.name = name
            self.blobs = {}
        
        def upload_blob(self, name, data, overwrite=True):
            self.blobs[name] = data
        
        def download_blob(self, name):
            if name in self.blobs:
                return MockAzureBlob(self.blobs[name])
            raise Exception("BlobNotFound")
        
        def list_blobs(self, name_starts_with=""):
            return [MockAzureBlobInfo(name) for name in self.blobs if name.startswith(name_starts_with)]
    
    class MockAzureBlob:
        def __init__(self, data):
            self.data = data
        
        def readall(self):
            return self.data
    
    class MockAzureBlobInfo:
        def __init__(self, name):
            self.name = name
    
    services["azure"] = MockAzureBlobClient()
    
    return services


@pytest.fixture
def mock_control_panel_apis():
    """Mock control panel APIs for testing."""
    apis = {}
    
    # Mock cPanel API
    class MockCPanelAPI:
        def __init__(self):
            self.accounts = [
                {"user": "testuser1", "domain": "test1.com", "email": "user1@test1.com"},
                {"user": "testuser2", "domain": "test2.com", "email": "user2@test2.com"}
            ]
            self.databases = [
                {"name": "testuser1_db", "user": "testuser1", "size": 1024000},
                {"name": "testuser2_db", "user": "testuser2", "size": 2048000}
            ]
            self.email_accounts = [
                {"email": "admin@test1.com", "quota": 1000, "usage": 500},
                {"email": "info@test2.com", "quota": 2000, "usage": 1200}
            ]
        
        def list_accounts(self):
            return {"data": self.accounts}
        
        def list_databases(self):
            return {"data": self.databases}
        
        def list_email_accounts(self):
            return {"data": self.email_accounts}
        
        def get_account_info(self, username):
            for account in self.accounts:
                if account["user"] == username:
                    return {"data": account}
            return {"errors": ["Account not found"]}
        
        def backup_account(self, username):
            return {"data": {"backup_id": f"backup_{username}_{int(time.time())}"}}
    
    apis["cpanel"] = MockCPanelAPI()
    
    # Mock DirectAdmin API
    class MockDirectAdminAPI:
        def __init__(self):
            self.users = [
                {"username": "user1", "domain": "example1.com", "package": "basic"},
                {"username": "user2", "domain": "example2.com", "package": "premium"}
            ]
            self.databases = [
                {"name": "user1_main", "user": "user1", "size": 512000},
                {"name": "user2_main", "user": "user2", "size": 1024000}
            ]
        
        def list_users(self):
            return self.users
        
        def list_databases(self):
            return self.databases
        
        def get_user_info(self, username):
            for user in self.users:
                if user["username"] == username:
                    return user
            return None
    
    apis["directadmin"] = MockDirectAdminAPI()
    
    # Mock Plesk API
    class MockPleskAPI:
        def __init__(self):
            self.sites = [
                {"name": "site1.com", "status": "active", "hosting_type": "vrt_hst"},
                {"name": "site2.com", "status": "active", "hosting_type": "vrt_hst"}
            ]
            self.databases = [
                {"name": "site1_db", "type": "mysql", "server": "localhost"},
                {"name": "site2_db", "type": "mysql", "server": "localhost"}
            ]
        
        def list_sites(self):
            return {"sites": self.sites}
        
        def list_databases(self):
            return {"databases": self.databases}
        
        def get_site_info(self, site_name):
            for site in self.sites:
                if site["name"] == site_name:
                    return site
            return None
    
    apis["plesk"] = MockPleskAPI()
    
    return apis


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_test_files(temp_directory):
    """Create sample test files for migration testing."""
    files = {}
    
    # Create various file types
    test_files = {
        "index.html": "<html><body><h1>Test Site</h1></body></html>",
        "style.css": "body { font-family: Arial; }",
        "script.js": "console.log('Hello World');",
        "config.json": json.dumps({"database": "mysql", "host": "localhost"}),
        "data.txt": "Sample data file\nLine 2\nLine 3",
        "binary.bin": bytes([i % 256 for i in range(1000)]),
        "large.txt": "x" * 10000,  # 10KB file
    }
    
    for filename, content in test_files.items():
        file_path = os.path.join(temp_directory, filename)
        if isinstance(content, bytes):
            with open(file_path, "wb") as f:
                f.write(content)
        else:
            with open(file_path, "w") as f:
                f.write(content)
        files[filename] = file_path
    
    # Create subdirectory with files
    subdir = os.path.join(temp_directory, "subdir")
    os.makedirs(subdir)
    
    subdir_files = {
        "nested.txt": "Nested file content",
        "config.ini": "[section]\nkey=value\n"
    }
    
    for filename, content in subdir_files.items():
        file_path = os.path.join(subdir, filename)
        with open(file_path, "w") as f:
            f.write(content)
        files[f"subdir/{filename}"] = file_path
    
    return files


@pytest.fixture
def mock_ssh_client():
    """Mock SSH client for testing file transfers."""
    class MockSSHClient:
        def __init__(self):
            self.connected = False
            self.files = {}
        
        def connect(self, hostname, username, password=None, key_filename=None):
            self.connected = True
        
        def open_sftp(self):
            return MockSFTPClient(self.files)
        
        def exec_command(self, command):
            # Mock command execution
            if command.startswith("ls"):
                return None, Mock(read=lambda: b"file1.txt\nfile2.txt\n"), Mock(read=lambda: b"")
            return None, Mock(read=lambda: b""), Mock(read=lambda: b"")
        
        def close(self):
            self.connected = False
    
    class MockSFTPClient:
        def __init__(self, files):
            self.files = files
        
        def put(self, local_path, remote_path):
            with open(local_path, "rb") as f:
                self.files[remote_path] = f.read()
        
        def get(self, remote_path, local_path):
            if remote_path in self.files:
                with open(local_path, "wb") as f:
                    f.write(self.files[remote_path])
            else:
                raise FileNotFoundError(f"Remote file not found: {remote_path}")
        
        def listdir(self, path):
            return [f for f in self.files.keys() if f.startswith(path)]
        
        def close(self):
            pass
    
    return MockSSHClient()


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing container operations."""
    class MockDockerClient:
        def __init__(self):
            self.containers = MockContainerManager()
            self.volumes = MockVolumeManager()
        
        def ping(self):
            return True
    
    class MockContainerManager:
        def __init__(self):
            self.containers = {}
        
        def run(self, image, **kwargs):
            container_id = f"mock_{len(self.containers)}"
            container = MockContainer(container_id, image, kwargs)
            self.containers[container_id] = container
            return container
        
        def get(self, container_id):
            return self.containers.get(container_id)
        
        def list(self, **kwargs):
            return list(self.containers.values())
    
    class MockContainer:
        def __init__(self, container_id, image, config):
            self.id = container_id
            self.image = image
            self.config = config
            self.status = "running"
        
        def stop(self):
            self.status = "stopped"
        
        def remove(self):
            self.status = "removed"
        
        def exec_run(self, command):
            return Mock(exit_code=0, output=b"mock output")
    
    class MockVolumeManager:
        def __init__(self):
            self.volumes = {}
        
        def create(self, name, **kwargs):
            volume = MockVolume(name, kwargs)
            self.volumes[name] = volume
            return volume
        
        def get(self, name):
            return self.volumes.get(name)
    
    class MockVolume:
        def __init__(self, name, config):
            self.name = name
            self.config = config
        
        def remove(self):
            pass
    
    return MockDockerClient()


@pytest.fixture
def performance_test_data():
    """Generate test data for performance benchmarking."""
    data = {}
    
    # Small files (1KB each)
    data["small_files"] = []
    for i in range(100):
        content = f"Small file {i} content " * 20  # ~1KB
        data["small_files"].append(content)
    
    # Medium files (100KB each)
    data["medium_files"] = []
    for i in range(10):
        content = f"Medium file {i} content " * 2000  # ~100KB
        data["medium_files"].append(content)
    
    # Large file (1MB)
    data["large_file"] = "Large file content " * 50000  # ~1MB
    
    # Database records
    data["database_records"] = []
    for i in range(1000):
        record = {
            "id": i,
            "name": f"Record {i}",
            "email": f"user{i}@example.com",
            "data": f"Sample data for record {i}" * 10
        }
        data["database_records"].append(record)
    
    return data


@pytest.fixture
def mock_go_binary():
    """Mock Go binary for testing hybrid operations."""
    class MockGoBinary:
        def __init__(self):
            self.available = True
        
        async def execute(self, operation, **kwargs):
            # Simulate Go binary execution
            await asyncio.sleep(0.01)  # Simulate processing time
            
            if operation == "copy":
                return {
                    "success": True,
                    "bytes_copied": kwargs.get("size", 1000),
                    "duration_ms": 10,
                    "checksum": "mock_checksum_123"
                }
            elif operation == "checksum":
                return {
                    "success": True,
                    "checksums": {
                        file: f"checksum_{hash(file)}" for file in kwargs.get("files", [])
                    }
                }
            elif operation == "compress":
                return {
                    "success": True,
                    "original_size": kwargs.get("size", 1000),
                    "compressed_size": kwargs.get("size", 1000) // 2,
                    "compression_ratio": 0.5
                }
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
    
    return MockGoBinary()


# Test configuration
pytest_plugins = []

# Async test support
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()