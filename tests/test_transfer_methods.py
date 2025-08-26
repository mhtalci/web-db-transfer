"""
Unit tests for transfer method implementations.

Tests the specific transfer method implementations including SSH, FTP,
cloud storage, rsync, Docker, and Kubernetes transfers.
"""

import asyncio
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from migration_assistant.transfer.methods.ssh import ParamikoTransfer
from migration_assistant.transfer.methods.ftp import FtpTransfer
from migration_assistant.transfer.methods.cloud import S3Transfer, GCSTransfer, AzureBlobTransfer
from migration_assistant.transfer.methods.rsync import RsyncTransfer
from migration_assistant.transfer.methods.docker import DockerTransfer
from migration_assistant.transfer.methods.kubernetes import KubernetesTransfer
from migration_assistant.transfer.base import TransferStatus


class TestParamikoTransfer:
    """Test ParamikoTransfer class."""
    
    def test_initialization_without_paramiko(self):
        """Test initialization when paramiko is not available."""
        with patch('migration_assistant.transfer.methods.ssh.PARAMIKO_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                ParamikoTransfer({'host': 'example.com'})
            
            assert "paramiko is required" in str(exc_info.value)
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'host': 'example.com',
            'port': 22,
            'username': 'testuser',
            'password': 'testpass'
        }
        
        with patch('migration_assistant.transfer.methods.ssh.PARAMIKO_AVAILABLE', True):
            transfer = ParamikoTransfer(config)
            
            assert transfer.host == 'example.com'
            assert transfer.port == 22
            assert transfer.username == 'testuser'
            assert transfer.password == 'testpass'
    
    def test_url_parsing(self):
        """Test URL parsing functionality."""
        config = {
            'url': 'ssh://user@example.com:2222/path/to/file',
            'host': 'default.com'  # Should be overridden
        }
        
        with patch('migration_assistant.transfer.methods.ssh.PARAMIKO_AVAILABLE', True):
            transfer = ParamikoTransfer(config)
            
            assert transfer.config['host'] == 'example.com'
            assert transfer.config['port'] == 2222
            assert transfer.config['username'] == 'user'
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'host': 'example.com',
            'port': 22,
            'password': 'testpass'
        }
        
        with patch('migration_assistant.transfer.methods.ssh.PARAMIKO_AVAILABLE', True):
            transfer = ParamikoTransfer(config)
            
            result = await transfer.validate_config()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_missing_host(self):
        """Test configuration validation with missing host."""
        config = {'port': 22}
        
        with patch('migration_assistant.transfer.methods.ssh.PARAMIKO_AVAILABLE', True):
            transfer = ParamikoTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_config_invalid_port(self):
        """Test configuration validation with invalid port."""
        config = {
            'host': 'example.com',
            'port': 70000,
            'password': 'testpass'
        }
        
        with patch('migration_assistant.transfer.methods.ssh.PARAMIKO_AVAILABLE', True):
            transfer = ParamikoTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False


class TestFtpTransfer:
    """Test FtpTransfer class."""
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'host': 'ftp.example.com',
            'port': 21,
            'username': 'testuser',
            'password': 'testpass'
        }
        
        transfer = FtpTransfer(config)
        
        assert transfer.host == 'ftp.example.com'
        assert transfer.port == 21
        assert transfer.username == 'testuser'
        assert transfer.password == 'testpass'
    
    def test_url_parsing_ftp(self):
        """Test FTP URL parsing."""
        config = {
            'url': 'ftp://user:pass@ftp.example.com:2121/path',
            'host': 'default.com'  # Should be overridden
        }
        
        transfer = FtpTransfer(config)
        
        assert transfer.config['host'] == 'ftp.example.com'
        assert transfer.config['port'] == 2121
        assert transfer.config['username'] == 'user'
        assert transfer.config['password'] == 'pass'
    
    def test_url_parsing_ftps(self):
        """Test FTPS URL parsing."""
        config = {
            'url': 'ftps://user@ftp.example.com/path',
            'host': 'default.com'
        }
        
        transfer = FtpTransfer(config)
        
        assert transfer.config['host'] == 'ftp.example.com'
        assert transfer.config['use_tls'] is True
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'host': 'ftp.example.com',
            'port': 21,
            'transfer_mode': 'binary'
        }
        
        transfer = FtpTransfer(config)
        
        result = await transfer.validate_config()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_invalid_transfer_mode(self):
        """Test configuration validation with invalid transfer mode."""
        config = {
            'host': 'ftp.example.com',
            'transfer_mode': 'invalid'
        }
        
        transfer = FtpTransfer(config)
        
        result = await transfer.validate_config()
        assert result is False


class TestS3Transfer:
    """Test S3Transfer class."""
    
    def test_initialization_without_boto3(self):
        """Test initialization when boto3 is not available."""
        with patch('migration_assistant.transfer.methods.cloud.BOTO3_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                S3Transfer({'bucket': 'test-bucket'})
            
            assert "boto3 is required" in str(exc_info.value)
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'bucket': 'test-bucket',
            'region': 'us-east-1',
            'access_key_id': 'AKIATEST',
            'secret_access_key': 'secret'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.BOTO3_AVAILABLE', True):
            transfer = S3Transfer(config)
            
            assert transfer.bucket == 'test-bucket'
            assert transfer.region == 'us-east-1'
            assert transfer.access_key_id == 'AKIATEST'
            assert transfer.secret_access_key == 'secret'
    
    def test_url_parsing(self):
        """Test S3 URL parsing."""
        config = {
            'url': 's3://my-bucket/path/to/object',
            'bucket': 'default-bucket'  # Should be overridden
        }
        
        with patch('migration_assistant.transfer.methods.cloud.BOTO3_AVAILABLE', True):
            transfer = S3Transfer(config)
            
            assert transfer.config['bucket'] == 'my-bucket'
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'bucket': 'test-bucket',
            'storage_class': 'STANDARD'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.BOTO3_AVAILABLE', True):
            transfer = S3Transfer(config)
            
            result = await transfer.validate_config()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_invalid_storage_class(self):
        """Test configuration validation with invalid storage class."""
        config = {
            'bucket': 'test-bucket',
            'storage_class': 'INVALID'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.BOTO3_AVAILABLE', True):
            transfer = S3Transfer(config)
            
            result = await transfer.validate_config()
            assert result is False


class TestRsyncTransfer:
    """Test RsyncTransfer class."""
    
    def test_initialization_without_rsync(self):
        """Test initialization when rsync is not available."""
        with patch('shutil.which', return_value=None):
            with pytest.raises(FileNotFoundError) as exc_info:
                RsyncTransfer({'destination': '/tmp'})
            
            assert "rsync not found" in str(exc_info.value)
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'destination': '/remote/path',
            'ssh_user': 'testuser',
            'ssh_host': 'example.com',
            'compress': True
        }
        
        with patch('shutil.which', return_value='/usr/bin/rsync'):
            transfer = RsyncTransfer(config)
            
            assert transfer.destination == '/remote/path'
            assert transfer.ssh_user == 'testuser'
            assert transfer.ssh_host == 'example.com'
            assert transfer.compress is True
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'destination': '/remote/path',
            'ssh_port': 22
        }
        
        with patch('shutil.which', return_value='/usr/bin/rsync'):
            transfer = RsyncTransfer(config)
            
            result = await transfer.validate_config()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_invalid_port(self):
        """Test configuration validation with invalid SSH port."""
        config = {
            'destination': '/remote/path',
            'ssh_port': 70000
        }
        
        with patch('shutil.which', return_value='/usr/bin/rsync'):
            transfer = RsyncTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False
    
    def test_build_rsync_command_basic(self):
        """Test building basic rsync command."""
        config = {
            'destination': '/remote/path',
            'archive': True,
            'verbose': True,
            'compress': True
        }
        
        with patch('shutil.which', return_value='/usr/bin/rsync'):
            transfer = RsyncTransfer(config)
            
            cmd = transfer._build_rsync_command('/local/path', '/remote/path')
            
            assert 'rsync' in cmd
            assert '-a' in cmd
            assert '-v' in cmd
            assert '-z' in cmd
            assert '/local/path' in cmd
            assert '/remote/path' in cmd
    
    def test_build_rsync_command_with_ssh(self):
        """Test building rsync command with SSH options."""
        config = {
            'destination': '/remote/path',
            'ssh_user': 'testuser',
            'ssh_host': 'example.com',
            'ssh_port': 2222,
            'ssh_key': '/path/to/key'
        }
        
        with patch('shutil.which', return_value='/usr/bin/rsync'):
            transfer = RsyncTransfer(config)
            
            cmd = transfer._build_rsync_command('/local/path', '/remote/path')
            
            assert '-e' in cmd
            ssh_cmd_index = cmd.index('-e') + 1
            ssh_cmd = cmd[ssh_cmd_index]
            
            assert 'ssh' in ssh_cmd
            assert '-p 2222' in ssh_cmd
            assert '-i /path/to/key' in ssh_cmd
            assert 'testuser@example.com:/remote/path' in cmd


class TestDockerTransfer:
    """Test DockerTransfer class."""
    
    def test_initialization_without_docker(self):
        """Test initialization when docker is not available."""
        with patch('migration_assistant.transfer.methods.docker.DOCKER_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                DockerTransfer({'container_or_volume': 'test-container'})
            
            assert "docker is required" in str(exc_info.value)
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'container_or_volume': 'test-container',
            'container_path': '/app',
            'docker_host': 'unix:///var/run/docker.sock'
        }
        
        with patch('migration_assistant.transfer.methods.docker.DOCKER_AVAILABLE', True):
            transfer = DockerTransfer(config)
            
            assert transfer.container_or_volume == 'test-container'
            assert transfer.container_path == '/app'
            assert transfer.docker_host == 'unix:///var/run/docker.sock'
    
    def test_url_parsing(self):
        """Test Docker URL parsing."""
        config = {
            'url': 'docker://my-container/app/data',
            'container_or_volume': 'default'  # Should be overridden
        }
        
        with patch('migration_assistant.transfer.methods.docker.DOCKER_AVAILABLE', True):
            transfer = DockerTransfer(config)
            
            assert transfer.config['container_or_volume'] == 'my-container'
            assert transfer.config['container_path'] == '/app/data'
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'container_or_volume': 'test-container'
        }
        
        with patch('migration_assistant.transfer.methods.docker.DOCKER_AVAILABLE', True):
            transfer = DockerTransfer(config)
            
            result = await transfer.validate_config()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_create_container_without_image(self):
        """Test configuration validation when creating container without image."""
        config = {
            'container_or_volume': 'test-container',
            'create_container': True
            # Missing 'image'
        }
        
        with patch('migration_assistant.transfer.methods.docker.DOCKER_AVAILABLE', True):
            transfer = DockerTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False


class TestKubernetesTransfer:
    """Test KubernetesTransfer class."""
    
    def test_initialization_without_kubernetes(self):
        """Test initialization when kubernetes is not available."""
        with patch('migration_assistant.transfer.methods.kubernetes.KUBERNETES_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                KubernetesTransfer({'pod_name': 'test-pod'})
            
            assert "kubernetes is required" in str(exc_info.value)
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'pod_name': 'test-pod',
            'namespace': 'test-namespace',
            'container_name': 'main',
            'pod_path': '/app'
        }
        
        with patch('migration_assistant.transfer.methods.kubernetes.KUBERNETES_AVAILABLE', True):
            transfer = KubernetesTransfer(config)
            
            assert transfer.pod_name == 'test-pod'
            assert transfer.namespace == 'test-namespace'
            assert transfer.container_name == 'main'
            assert transfer.pod_path == '/app'
    
    def test_url_parsing(self):
        """Test Kubernetes URL parsing."""
        config = {
            'url': 'k8s://my-namespace/my-pod/main/app/data',
            'pod_name': 'default'  # Should be overridden
        }
        
        with patch('migration_assistant.transfer.methods.kubernetes.KUBERNETES_AVAILABLE', True):
            transfer = KubernetesTransfer(config)
            
            assert transfer.config['namespace'] == 'my-namespace'
            assert transfer.config['pod_name'] == 'my-pod'
            assert transfer.config['container_name'] == 'main'
            assert transfer.config['pod_path'] == '/app/data'
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'pod_name': 'test-pod',
            'namespace': 'test-namespace'
        }
        
        with patch('migration_assistant.transfer.methods.kubernetes.KUBERNETES_AVAILABLE', True):
            transfer = KubernetesTransfer(config)
            
            result = await transfer.validate_config()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_missing_pod_name(self):
        """Test configuration validation with missing pod name."""
        config = {
            'namespace': 'test-namespace'
            # Missing 'pod_name'
        }
        
        with patch('migration_assistant.transfer.methods.kubernetes.KUBERNETES_AVAILABLE', True):
            transfer = KubernetesTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_config_create_pod_without_image(self):
        """Test configuration validation when creating pod without image."""
        config = {
            'pod_name': 'test-pod',
            'namespace': 'test-namespace',
            'create_pod': True
            # Missing 'image'
        }
        
        with patch('migration_assistant.transfer.methods.kubernetes.KUBERNETES_AVAILABLE', True):
            transfer = KubernetesTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False


class TestGCSTransfer:
    """Test GCSTransfer class."""
    
    def test_initialization_without_gcs(self):
        """Test initialization when google-cloud-storage is not available."""
        with patch('migration_assistant.transfer.methods.cloud.GCS_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                GCSTransfer({'bucket': 'test-bucket'})
            
            assert "google-cloud-storage is required" in str(exc_info.value)
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'bucket': 'test-bucket',
            'project_id': 'my-project',
            'storage_class': 'STANDARD'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.GCS_AVAILABLE', True):
            transfer = GCSTransfer(config)
            
            assert transfer.bucket_name == 'test-bucket'
            assert transfer.project_id == 'my-project'
            assert transfer.storage_class == 'STANDARD'
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'bucket': 'test-bucket',
            'storage_class': 'NEARLINE'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.GCS_AVAILABLE', True):
            transfer = GCSTransfer(config)
            
            result = await transfer.validate_config()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_invalid_storage_class(self):
        """Test configuration validation with invalid storage class."""
        config = {
            'bucket': 'test-bucket',
            'storage_class': 'INVALID'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.GCS_AVAILABLE', True):
            transfer = GCSTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False


class TestAzureBlobTransfer:
    """Test AzureBlobTransfer class."""
    
    def test_initialization_without_azure(self):
        """Test initialization when azure-storage-blob is not available."""
        with patch('migration_assistant.transfer.methods.cloud.AZURE_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                AzureBlobTransfer({'container': 'test-container'})
            
            assert "azure-storage-blob is required" in str(exc_info.value)
    
    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'container': 'test-container',
            'account_name': 'myaccount',
            'account_key': 'mykey'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.AZURE_AVAILABLE', True):
            transfer = AzureBlobTransfer(config)
            
            assert transfer.container_name == 'test-container'
            assert transfer.account_name == 'myaccount'
            assert transfer.account_key == 'mykey'
    
    def test_url_parsing(self):
        """Test Azure URL parsing."""
        config = {
            'url': 'https://myaccount.blob.core.windows.net/container/blob',
            'container': 'default'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.AZURE_AVAILABLE', True):
            transfer = AzureBlobTransfer(config)
            
            assert transfer.config['account_name'] == 'myaccount'
            assert transfer.config['account_url'] == 'https://myaccount.blob.core.windows.net'
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful configuration validation."""
        config = {
            'container': 'test-container',
            'account_name': 'myaccount',
            'account_key': 'mykey'
        }
        
        with patch('migration_assistant.transfer.methods.cloud.AZURE_AVAILABLE', True):
            transfer = AzureBlobTransfer(config)
            
            result = await transfer.validate_config()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_config_no_auth(self):
        """Test configuration validation without authentication."""
        config = {
            'container': 'test-container'
            # Missing authentication
        }
        
        with patch('migration_assistant.transfer.methods.cloud.AZURE_AVAILABLE', True):
            transfer = AzureBlobTransfer(config)
            
            result = await transfer.validate_config()
            assert result is False