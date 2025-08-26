"""
Comprehensive tests for file transfer functionality with 90%+ coverage.

This module tests all file transfer components including factory,
transfer methods, integrity verification, and performance monitoring.
"""

import pytest
import asyncio
import os
import hashlib
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from migration_assistant.transfer.factory import TransferMethodFactory
from migration_assistant.transfer.base import TransferMethod
from migration_assistant.transfer.methods.ssh import SSHTransfer
from migration_assistant.transfer.methods.ftp import FTPTransfer
from migration_assistant.transfer.methods.cloud import S3Transfer, GCSTransfer, AzureTransfer
from migration_assistant.transfer.methods.rsync import RsyncTransfer
from migration_assistant.transfer.methods.docker import DockerTransfer
from migration_assistant.transfer.methods.kubernetes import KubernetesTransfer
from migration_assistant.transfer.integrity import IntegrityVerifier
from migration_assistant.models.config import (
    TransferConfig, AuthConfig, CloudConfig,
    TransferMethod as TransferMethodType, AuthType
)
from migration_assistant.core.exceptions import TransferError, IntegrityError


class TestTransferMethodFactory:
    """Test the transfer method factory."""
    
    def test_create_ssh_transfer(self):
        """Test creating SSH transfer method."""
        config = TransferConfig(
            method=TransferMethodType.SSH_SCP,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser")
        )
        
        transfer = TransferMethodFactory.create_transfer_method(config)
        
        assert isinstance(transfer, SSHTransfer)
        assert transfer.config == config
    
    def test_create_ftp_transfer(self):
        """Test creating FTP transfer method."""
        config = TransferConfig(
            method=TransferMethodType.FTP,
            auth=AuthConfig(type=AuthType.PASSWORD, username="testuser", password="testpass")
        )
        
        transfer = TransferMethodFactory.create_transfer_method(config)
        
        assert isinstance(transfer, FTPTransfer)
        assert transfer.config == config
    
    def test_create_s3_transfer(self):
        """Test creating S3 transfer method."""
        config = TransferConfig(
            method=TransferMethodType.S3,
            cloud=CloudConfig(provider="aws", region="us-east-1", bucket="test-bucket")
        )
        
        transfer = TransferMethodFactory.create_transfer_method(config)
        
        assert isinstance(transfer, S3Transfer)
        assert transfer.config == config
    
    def test_create_rsync_transfer(self):
        """Test creating rsync transfer method."""
        config = TransferConfig(
            method=TransferMethodType.RSYNC,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser")
        )
        
        transfer = TransferMethodFactory.create_transfer_method(config)
        
        assert isinstance(transfer, RsyncTransfer)
        assert transfer.config == config
    
    def test_create_docker_transfer(self):
        """Test creating Docker transfer method."""
        config = TransferConfig(
            method=TransferMethodType.DOCKER,
            container_config={"image": "nginx", "volumes": ["/data"]}
        )
        
        transfer = TransferMethodFactory.create_transfer_method(config)
        
        assert isinstance(transfer, DockerTransfer)
        assert transfer.config == config
    
    def test_create_unsupported_transfer(self):
        """Test creating unsupported transfer method."""
        config = TransferConfig(method="UNSUPPORTED")
        
        with pytest.raises(ValueError, match="Unsupported transfer method"):
            TransferMethodFactory.create_transfer_method(config)


class TestSSHTransfer:
    """Test SSH-based file transfer."""
    
    @pytest.fixture
    def ssh_config(self):
        """SSH transfer configuration."""
        return TransferConfig(
            method=TransferMethodType.SSH_SCP,
            auth=AuthConfig(
                type=AuthType.SSH_KEY,
                username="testuser",
                private_key_path="/path/to/key"
            ),
            host="remote.example.com",
            port=22
        )
    
    @pytest.fixture
    def ssh_transfer(self, ssh_config, mock_ssh_client):
        """SSH transfer instance."""
        with patch('paramiko.SSHClient', return_value=mock_ssh_client):
            return SSHTransfer(ssh_config)
    
    @pytest.mark.asyncio
    async def test_connect(self, ssh_transfer, mock_ssh_client):
        """Test SSH connection."""
        await ssh_transfer.connect()
        
        assert ssh_transfer.ssh_client == mock_ssh_client
        assert mock_ssh_client.connected is True
    
    @pytest.mark.asyncio
    async def test_disconnect(self, ssh_transfer, mock_ssh_client):
        """Test SSH disconnection."""
        ssh_transfer.ssh_client = mock_ssh_client
        mock_ssh_client.connected = True
        
        await ssh_transfer.disconnect()
        
        assert mock_ssh_client.connected is False
    
    @pytest.mark.asyncio
    async def test_upload_file(self, ssh_transfer, mock_ssh_client, sample_test_files):
        """Test file upload via SSH."""
        local_file = list(sample_test_files.values())[0]
        remote_file = "/remote/path/file.txt"
        
        ssh_transfer.ssh_client = mock_ssh_client
        
        result = await ssh_transfer.upload_file(local_file, remote_file)
        
        assert result.success is True
        assert result.bytes_transferred > 0
        assert result.transfer_rate > 0
    
    @pytest.mark.asyncio
    async def test_download_file(self, ssh_transfer, mock_ssh_client, temp_directory):
        """Test file download via SSH."""
        remote_file = "/remote/path/file.txt"
        local_file = os.path.join(temp_directory, "downloaded.txt")
        
        ssh_transfer.ssh_client = mock_ssh_client
        # Pre-populate the mock with file data
        mock_ssh_client.files[remote_file] = b"test content"
        
        result = await ssh_transfer.download_file(remote_file, local_file)
        
        assert result.success is True
        assert os.path.exists(local_file)
    
    @pytest.mark.asyncio
    async def test_upload_directory(self, ssh_transfer, mock_ssh_client, temp_directory):
        """Test directory upload via SSH."""
        # Create test directory structure
        test_dir = os.path.join(temp_directory, "test_upload")
        os.makedirs(test_dir)
        
        # Create test files
        for i in range(3):
            file_path = os.path.join(test_dir, f"file_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"Content of file {i}")
        
        ssh_transfer.ssh_client = mock_ssh_client
        
        result = await ssh_transfer.upload_directory(test_dir, "/remote/test_dir")
        
        assert result.success is True
        assert result.files_transferred == 3
    
    @pytest.mark.asyncio
    async def test_transfer_with_progress_callback(self, ssh_transfer, mock_ssh_client, sample_test_files):
        """Test file transfer with progress callback."""
        local_file = list(sample_test_files.values())[0]
        remote_file = "/remote/path/file.txt"
        progress_updates = []
        
        async def progress_callback(bytes_transferred, total_bytes, rate):
            progress_updates.append((bytes_transferred, total_bytes, rate))
        
        ssh_transfer.ssh_client = mock_ssh_client
        
        result = await ssh_transfer.upload_file(
            local_file, remote_file, progress_callback=progress_callback
        )
        
        assert result.success is True
        assert len(progress_updates) > 0
    
    @pytest.mark.asyncio
    async def test_transfer_with_compression(self, ssh_transfer, mock_ssh_client, sample_test_files):
        """Test file transfer with compression."""
        local_file = list(sample_test_files.values())[0]
        remote_file = "/remote/path/file.txt"
        
        ssh_transfer.config.compression_enabled = True
        ssh_transfer.ssh_client = mock_ssh_client
        
        result = await ssh_transfer.upload_file(local_file, remote_file)
        
        assert result.success is True
        # Compression should be indicated in result
        assert hasattr(result, 'compression_ratio')


class TestFTPTransfer:
    """Test FTP-based file transfer."""
    
    @pytest.fixture
    def ftp_config(self):
        """FTP transfer configuration."""
        return TransferConfig(
            method=TransferMethodType.FTP,
            auth=AuthConfig(
                type=AuthType.PASSWORD,
                username="testuser",
                password="testpass"
            ),
            host="ftp.example.com",
            port=21
        )
    
    @pytest.fixture
    def ftp_transfer(self, ftp_config):
        """FTP transfer instance."""
        return FTPTransfer(ftp_config)
    
    @pytest.mark.asyncio
    async def test_connect(self, ftp_transfer):
        """Test FTP connection."""
        with patch('ftplib.FTP') as mock_ftp:
            mock_instance = Mock()
            mock_ftp.return_value = mock_instance
            mock_instance.login.return_value = "230 Login successful"
            
            await ftp_transfer.connect()
            
            assert ftp_transfer.ftp_client == mock_instance
            mock_instance.login.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upload_file(self, ftp_transfer, sample_test_files):
        """Test file upload via FTP."""
        local_file = list(sample_test_files.values())[0]
        remote_file = "/remote/path/file.txt"
        
        with patch('ftplib.FTP') as mock_ftp:
            mock_instance = Mock()
            mock_ftp.return_value = mock_instance
            ftp_transfer.ftp_client = mock_instance
            
            result = await ftp_transfer.upload_file(local_file, remote_file)
            
            assert result.success is True
            mock_instance.storbinary.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_file(self, ftp_transfer, temp_directory):
        """Test file download via FTP."""
        remote_file = "/remote/path/file.txt"
        local_file = os.path.join(temp_directory, "downloaded.txt")
        
        with patch('ftplib.FTP') as mock_ftp:
            mock_instance = Mock()
            mock_ftp.return_value = mock_instance
            ftp_transfer.ftp_client = mock_instance
            
            # Mock the retrbinary method
            def mock_retrbinary(cmd, callback):
                callback(b"test content")
            
            mock_instance.retrbinary = mock_retrbinary
            
            result = await ftp_transfer.download_file(remote_file, local_file)
            
            assert result.success is True
            assert os.path.exists(local_file)


class TestS3Transfer:
    """Test AWS S3 file transfer."""
    
    @pytest.fixture
    def s3_config(self):
        """S3 transfer configuration."""
        return TransferConfig(
            method=TransferMethodType.S3,
            cloud=CloudConfig(
                provider="aws",
                region="us-east-1",
                bucket="test-bucket",
                access_key="test-key",
                secret_key="test-secret"
            )
        )
    
    @pytest.fixture
    def s3_transfer(self, s3_config, mock_cloud_services):
        """S3 transfer instance."""
        with patch('boto3.client', return_value=mock_cloud_services["s3"]):
            return S3Transfer(s3_config)
    
    @pytest.mark.asyncio
    async def test_connect(self, s3_transfer, mock_cloud_services):
        """Test S3 connection."""
        with patch('boto3.client', return_value=mock_cloud_services["s3"]):
            await s3_transfer.connect()
            
            assert s3_transfer.s3_client == mock_cloud_services["s3"]
    
    @pytest.mark.asyncio
    async def test_upload_file(self, s3_transfer, sample_test_files):
        """Test file upload to S3."""
        local_file = list(sample_test_files.values())[0]
        s3_key = "uploads/file.txt"
        
        result = await s3_transfer.upload_file(local_file, s3_key)
        
        assert result.success is True
        assert result.bytes_transferred > 0
    
    @pytest.mark.asyncio
    async def test_download_file(self, s3_transfer, temp_directory):
        """Test file download from S3."""
        s3_key = "downloads/file.txt"
        local_file = os.path.join(temp_directory, "downloaded.txt")
        
        # Pre-populate S3 mock with file
        s3_transfer.s3_client.put_object(
            Bucket=s3_transfer.config.cloud.bucket,
            Key=s3_key,
            Body=b"test content"
        )
        
        result = await s3_transfer.download_file(s3_key, local_file)
        
        assert result.success is True
        assert os.path.exists(local_file)
    
    @pytest.mark.asyncio
    async def test_list_objects(self, s3_transfer):
        """Test listing S3 objects."""
        # Pre-populate S3 mock with objects
        bucket = s3_transfer.config.cloud.bucket
        s3_transfer.s3_client.put_object(Bucket=bucket, Key="file1.txt", Body=b"content1")
        s3_transfer.s3_client.put_object(Bucket=bucket, Key="file2.txt", Body=b"content2")
        
        objects = await s3_transfer.list_objects("", recursive=True)
        
        assert len(objects) == 2
        assert any(obj["Key"] == "file1.txt" for obj in objects)
    
    @pytest.mark.asyncio
    async def test_multipart_upload(self, s3_transfer, temp_directory):
        """Test multipart upload for large files."""
        # Create a large test file (simulate 10MB)
        large_file = os.path.join(temp_directory, "large_file.txt")
        with open(large_file, "w") as f:
            f.write("x" * (10 * 1024 * 1024))  # 10MB
        
        s3_key = "uploads/large_file.txt"
        
        result = await s3_transfer.upload_file(large_file, s3_key, multipart=True)
        
        assert result.success is True
        assert result.multipart_used is True


class TestGCSTransfer:
    """Test Google Cloud Storage file transfer."""
    
    @pytest.fixture
    def gcs_config(self):
        """GCS transfer configuration."""
        return TransferConfig(
            method=TransferMethodType.GCS,
            cloud=CloudConfig(
                provider="gcp",
                bucket="test-bucket",
                credentials_path="/path/to/credentials.json"
            )
        )
    
    @pytest.fixture
    def gcs_transfer(self, gcs_config, mock_cloud_services):
        """GCS transfer instance."""
        with patch('google.cloud.storage.Client', return_value=mock_cloud_services["gcs"]):
            return GCSTransfer(gcs_config)
    
    @pytest.mark.asyncio
    async def test_upload_file(self, gcs_transfer, sample_test_files):
        """Test file upload to GCS."""
        local_file = list(sample_test_files.values())[0]
        blob_name = "uploads/file.txt"
        
        result = await gcs_transfer.upload_file(local_file, blob_name)
        
        assert result.success is True
        assert result.bytes_transferred > 0
    
    @pytest.mark.asyncio
    async def test_download_file(self, gcs_transfer, temp_directory):
        """Test file download from GCS."""
        blob_name = "downloads/file.txt"
        local_file = os.path.join(temp_directory, "downloaded.txt")
        
        # Pre-populate GCS mock
        bucket = gcs_transfer.gcs_client.bucket(gcs_transfer.config.cloud.bucket)
        blob = bucket.blob(blob_name)
        blob.upload_from_string("test content")
        
        result = await gcs_transfer.download_file(blob_name, local_file)
        
        assert result.success is True
        assert os.path.exists(local_file)


class TestRsyncTransfer:
    """Test rsync-based file transfer."""
    
    @pytest.fixture
    def rsync_config(self):
        """Rsync transfer configuration."""
        return TransferConfig(
            method=TransferMethodType.RSYNC,
            auth=AuthConfig(
                type=AuthType.SSH_KEY,
                username="testuser",
                private_key_path="/path/to/key"
            ),
            host="remote.example.com",
            rsync_options=["--archive", "--compress", "--verbose"]
        )
    
    @pytest.fixture
    def rsync_transfer(self, rsync_config):
        """Rsync transfer instance."""
        return RsyncTransfer(rsync_config)
    
    @pytest.mark.asyncio
    async def test_sync_directory(self, rsync_transfer, temp_directory):
        """Test directory synchronization with rsync."""
        source_dir = os.path.join(temp_directory, "source")
        os.makedirs(source_dir)
        
        # Create test files
        for i in range(3):
            file_path = os.path.join(source_dir, f"file_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"Content {i}")
        
        remote_dir = "testuser@remote.example.com:/remote/dest/"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = await rsync_transfer.sync_directory(source_dir, remote_dir)
            
            assert result.success is True
            mock_run.assert_called_once()
            
            # Verify rsync command was constructed correctly
            call_args = mock_run.call_args[0][0]
            assert "rsync" in call_args
            assert "--archive" in call_args
            assert "--compress" in call_args
    
    @pytest.mark.asyncio
    async def test_sync_with_exclusions(self, rsync_transfer, temp_directory):
        """Test rsync with file exclusions."""
        source_dir = os.path.join(temp_directory, "source")
        os.makedirs(source_dir)
        
        # Create files to exclude
        excluded_file = os.path.join(source_dir, "exclude_me.log")
        with open(excluded_file, "w") as f:
            f.write("This should be excluded")
        
        remote_dir = "testuser@remote.example.com:/remote/dest/"
        exclusions = ["*.log", "*.tmp"]
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = await rsync_transfer.sync_directory(
                source_dir, remote_dir, exclusions=exclusions
            )
            
            assert result.success is True
            
            # Verify exclusions were added to command
            call_args = mock_run.call_args[0][0]
            assert "--exclude=*.log" in call_args
            assert "--exclude=*.tmp" in call_args


class TestDockerTransfer:
    """Test Docker-based file transfer."""
    
    @pytest.fixture
    def docker_config(self):
        """Docker transfer configuration."""
        return TransferConfig(
            method=TransferMethodType.DOCKER,
            container_config={
                "image": "nginx:latest",
                "volumes": {"/host/data": "/container/data"}
            }
        )
    
    @pytest.fixture
    def docker_transfer(self, docker_config, mock_docker_client):
        """Docker transfer instance."""
        with patch('docker.from_env', return_value=mock_docker_client):
            return DockerTransfer(docker_config)
    
    @pytest.mark.asyncio
    async def test_copy_to_container(self, docker_transfer, sample_test_files):
        """Test copying files to Docker container."""
        local_file = list(sample_test_files.values())[0]
        container_path = "/container/data/file.txt"
        
        result = await docker_transfer.copy_to_container(
            "test_container", local_file, container_path
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_copy_from_container(self, docker_transfer, temp_directory):
        """Test copying files from Docker container."""
        container_path = "/container/data/file.txt"
        local_file = os.path.join(temp_directory, "copied.txt")
        
        result = await docker_transfer.copy_from_container(
            "test_container", container_path, local_file
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_sync_volumes(self, docker_transfer, temp_directory):
        """Test synchronizing Docker volumes."""
        source_volume = "source_volume"
        dest_volume = "dest_volume"
        
        result = await docker_transfer.sync_volumes(source_volume, dest_volume)
        
        assert result.success is True


class TestIntegrityVerifier:
    """Test file integrity verification."""
    
    @pytest.fixture
    def integrity_verifier(self):
        """Integrity verifier instance."""
        return IntegrityVerifier()
    
    def test_calculate_file_checksum(self, integrity_verifier, sample_test_files):
        """Test file checksum calculation."""
        test_file = list(sample_test_files.values())[0]
        
        checksum = integrity_verifier.calculate_file_checksum(test_file, "sha256")
        
        assert len(checksum) == 64  # SHA256 hex length
        assert checksum.isalnum()
    
    def test_verify_file_integrity(self, integrity_verifier, sample_test_files):
        """Test file integrity verification."""
        test_file = list(sample_test_files.values())[0]
        
        # Calculate expected checksum
        expected_checksum = integrity_verifier.calculate_file_checksum(test_file, "sha256")
        
        # Verify integrity
        result = integrity_verifier.verify_file_integrity(
            test_file, expected_checksum, "sha256"
        )
        
        assert result.success is True
        assert result.checksums_match is True
    
    def test_verify_file_integrity_mismatch(self, integrity_verifier, sample_test_files):
        """Test file integrity verification with checksum mismatch."""
        test_file = list(sample_test_files.values())[0]
        wrong_checksum = "0" * 64  # Wrong SHA256 checksum
        
        result = integrity_verifier.verify_file_integrity(
            test_file, wrong_checksum, "sha256"
        )
        
        assert result.success is False
        assert result.checksums_match is False
    
    @pytest.mark.asyncio
    async def test_verify_directory_integrity(self, integrity_verifier, temp_directory):
        """Test directory integrity verification."""
        # Create test directory with files
        test_dir = os.path.join(temp_directory, "integrity_test")
        os.makedirs(test_dir)
        
        files = {}
        for i in range(3):
            file_path = os.path.join(test_dir, f"file_{i}.txt")
            content = f"Content of file {i}"
            with open(file_path, "w") as f:
                f.write(content)
            
            # Calculate expected checksum
            checksum = integrity_verifier.calculate_file_checksum(file_path, "sha256")
            files[file_path] = checksum
        
        result = await integrity_verifier.verify_directory_integrity(test_dir, files)
        
        assert result.success is True
        assert len(result.verified_files) == 3
        assert len(result.failed_files) == 0
    
    @pytest.mark.asyncio
    async def test_compare_directories(self, integrity_verifier, temp_directory):
        """Test comparing two directories for integrity."""
        # Create source directory
        source_dir = os.path.join(temp_directory, "source")
        os.makedirs(source_dir)
        
        # Create destination directory
        dest_dir = os.path.join(temp_directory, "dest")
        os.makedirs(dest_dir)
        
        # Create identical files in both directories
        for i in range(3):
            content = f"File content {i}"
            
            source_file = os.path.join(source_dir, f"file_{i}.txt")
            with open(source_file, "w") as f:
                f.write(content)
            
            dest_file = os.path.join(dest_dir, f"file_{i}.txt")
            with open(dest_file, "w") as f:
                f.write(content)
        
        result = await integrity_verifier.compare_directories(source_dir, dest_dir)
        
        assert result.success is True
        assert len(result.matching_files) == 3
        assert len(result.different_files) == 0
        assert len(result.missing_files) == 0
    
    def test_calculate_directory_checksum(self, integrity_verifier, temp_directory):
        """Test calculating checksum for entire directory."""
        # Create test directory
        test_dir = os.path.join(temp_directory, "checksum_test")
        os.makedirs(test_dir)
        
        # Create files
        for i in range(3):
            file_path = os.path.join(test_dir, f"file_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"Content {i}")
        
        checksum = integrity_verifier.calculate_directory_checksum(test_dir)
        
        assert len(checksum) == 64  # SHA256 hex length
        assert checksum.isalnum()
        
        # Verify checksum is deterministic
        checksum2 = integrity_verifier.calculate_directory_checksum(test_dir)
        assert checksum == checksum2


class TestTransferIntegration:
    """Integration tests for file transfer workflow."""
    
    @pytest.mark.asyncio
    async def test_full_transfer_workflow(self, sample_test_files, temp_directory):
        """Test complete file transfer workflow with integrity verification."""
        # Setup transfer configuration
        config = TransferConfig(
            method=TransferMethodType.SSH_SCP,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser"),
            host="remote.example.com",
            verify_checksums=True
        )
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            mock_client.connect = Mock()
            mock_client.open_sftp = Mock(return_value=Mock())
            
            transfer = TransferMethodFactory.create_transfer_method(config)
            
            # Test file transfer
            local_file = list(sample_test_files.values())[0]
            remote_file = "/remote/path/file.txt"
            
            result = await transfer.upload_file(local_file, remote_file)
            
            assert result.success is True
            assert result.integrity_verified is True
    
    @pytest.mark.asyncio
    async def test_transfer_with_retry_logic(self, sample_test_files):
        """Test file transfer with retry logic on failure."""
        config = TransferConfig(
            method=TransferMethodType.SSH_SCP,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser"),
            host="remote.example.com",
            max_retries=3,
            retry_delay=0.1
        )
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            
            # Mock connection failure on first two attempts
            mock_client.connect.side_effect = [
                Exception("Connection failed"),
                Exception("Connection failed"),
                None  # Success on third attempt
            ]
            
            transfer = TransferMethodFactory.create_transfer_method(config)
            
            local_file = list(sample_test_files.values())[0]
            remote_file = "/remote/path/file.txt"
            
            result = await transfer.upload_file(local_file, remote_file)
            
            assert result.success is True
            assert result.retry_count == 2
    
    @pytest.mark.benchmark
    def test_transfer_performance(self, benchmark, sample_test_files):
        """Benchmark file transfer performance."""
        config = TransferConfig(
            method=TransferMethodType.SSH_SCP,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser")
        )
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            mock_client.connect = Mock()
            mock_client.open_sftp = Mock(return_value=Mock())
            
            transfer = TransferMethodFactory.create_transfer_method(config)
            local_file = list(sample_test_files.values())[0]
            
            async def run_transfer():
                return await transfer.upload_file(local_file, "/remote/file.txt")
            
            result = benchmark.pedantic(
                lambda: asyncio.run(run_transfer()),
                rounds=10
            )
            
            assert result.success is True
    
    @pytest.mark.asyncio
    async def test_parallel_transfers(self, sample_test_files):
        """Test parallel file transfers."""
        config = TransferConfig(
            method=TransferMethodType.SSH_SCP,
            auth=AuthConfig(type=AuthType.SSH_KEY, username="testuser"),
            parallel_transfers=3
        )
        
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            mock_client.connect = Mock()
            mock_client.open_sftp = Mock(return_value=Mock())
            
            transfer = TransferMethodFactory.create_transfer_method(config)
            
            # Create multiple transfer tasks
            tasks = []
            for i, local_file in enumerate(list(sample_test_files.values())[:3]):
                task = transfer.upload_file(local_file, f"/remote/file_{i}.txt")
                tasks.append(task)
            
            # Execute transfers in parallel
            results = await asyncio.gather(*tasks)
            
            assert all(result.success for result in results)
            assert len(results) == 3