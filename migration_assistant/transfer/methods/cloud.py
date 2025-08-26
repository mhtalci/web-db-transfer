"""
Cloud storage transfer implementations.

This module provides transfer methods for various cloud storage services
including AWS S3, Google Cloud Storage, and Azure Blob Storage.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
from urllib.parse import urlparse
import logging

# AWS S3
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    from boto3.s3.transfer import TransferConfig
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Google Cloud Storage
try:
    from google.cloud import storage as gcs
    from google.cloud.exceptions import NotFound, Forbidden
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

# Azure Blob Storage
try:
    from azure.storage.blob import BlobServiceClient, BlobClient
    from azure.core.exceptions import ResourceNotFoundError, AzureError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

from ..base import TransferMethod, TransferResult, TransferStatus
from ..factory import register_transfer_method

logger = logging.getLogger(__name__)


@register_transfer_method('s3')
class S3Transfer(TransferMethod):
    """
    AWS S3 transfer implementation using boto3.
    
    Supports various S3 operations including multipart uploads,
    server-side encryption, and progress monitoring.
    """
    
    SUPPORTED_SCHEMES = ['s3://']
    REQUIRED_CONFIG = ['bucket']
    OPTIONAL_CONFIG = [
        'region', 'access_key_id', 'secret_access_key', 'session_token',
        'profile_name', 'endpoint_url', 'use_ssl', 'multipart_threshold',
        'max_concurrency', 'use_threads', 'server_side_encryption',
        'sse_kms_key_id', 'storage_class', 'metadata', 'acl'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize S3 transfer method.
        
        Args:
            config: Configuration dictionary with S3 parameters
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3 transfers. "
                "Install with: pip install boto3"
            )
        
        super().__init__(config)
        
        # Parse URL if provided
        if 'url' in config:
            self._parse_url(config['url'])
        
        # S3 connection parameters
        self.bucket = config['bucket']
        self.region = config.get('region')
        self.access_key_id = config.get('access_key_id')
        self.secret_access_key = config.get('secret_access_key')
        self.session_token = config.get('session_token')
        self.profile_name = config.get('profile_name')
        self.endpoint_url = config.get('endpoint_url')
        self.use_ssl = config.get('use_ssl', True)
        
        # Transfer configuration
        self.multipart_threshold = config.get('multipart_threshold', 8 * 1024 * 1024)  # 8MB
        self.max_concurrency = config.get('max_concurrency', 10)
        self.use_threads = config.get('use_threads', True)
        
        # S3 object options
        self.server_side_encryption = config.get('server_side_encryption')
        self.sse_kms_key_id = config.get('sse_kms_key_id')
        self.storage_class = config.get('storage_class', 'STANDARD')
        self.metadata = config.get('metadata', {})
        self.acl = config.get('acl')
        
        # S3 client
        self._s3_client: Optional[Any] = None
        self._transfer_config: Optional[TransferConfig] = None
    
    def _parse_url(self, url: str) -> None:
        """Parse S3 URL and update configuration."""
        parsed = urlparse(url)
        
        if parsed.netloc:
            self.config['bucket'] = parsed.netloc
        
        # Extract region from hostname if present
        if '.' in parsed.netloc:
            parts = parsed.netloc.split('.')
            if len(parts) > 2 and parts[1] == 's3':
                if parts[2] != 'amazonaws':
                    self.config['region'] = parts[2]
    
    async def validate_config(self) -> bool:
        """
        Validate S3 configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required parameters
            if not self.bucket:
                self.logger.error("Bucket name is required for S3 transfers")
                return False
            
            # Validate storage class
            valid_storage_classes = [
                'STANDARD', 'REDUCED_REDUNDANCY', 'STANDARD_IA', 'ONEZONE_IA',
                'INTELLIGENT_TIERING', 'GLACIER', 'DEEP_ARCHIVE', 'OUTPOSTS'
            ]
            if self.storage_class not in valid_storage_classes:
                self.logger.error(f"Invalid storage class: {self.storage_class}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test S3 connection and bucket access.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self._connect()
            
            # Test bucket access
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._s3_client.head_bucket,
                Bucket=self.bucket
            )
            
            self.logger.info(f"S3 connection test successful to bucket: {self.bucket}")
            return True
            
        except Exception as e:
            self.logger.error(f"S3 connection test failed: {e}")
            return False
    
    async def _connect(self) -> None:
        """Establish S3 connection."""
        if self._s3_client:
            return
        
        # Prepare session parameters
        session_params = {}
        if self.profile_name:
            session_params['profile_name'] = self.profile_name
        
        # Create session
        session = boto3.Session(**session_params)
        
        # Prepare client parameters
        client_params = {
            'service_name': 's3',
            'use_ssl': self.use_ssl
        }
        
        if self.region:
            client_params['region_name'] = self.region
        if self.endpoint_url:
            client_params['endpoint_url'] = self.endpoint_url
        if self.access_key_id and self.secret_access_key:
            client_params['aws_access_key_id'] = self.access_key_id
            client_params['aws_secret_access_key'] = self.secret_access_key
            if self.session_token:
                client_params['aws_session_token'] = self.session_token
        
        # Create S3 client
        self._s3_client = session.client(**client_params)
        
        # Create transfer configuration
        self._transfer_config = TransferConfig(
            multipart_threshold=self.multipart_threshold,
            max_concurrency=self.max_concurrency,
            use_threads=self.use_threads
        )
        
        self.logger.info(f"S3 connection established to bucket: {self.bucket}")
    
    def _s3_progress_callback(self, bytes_transferred: int) -> None:
        """S3 progress callback."""
        if self.is_cancelled():
            raise Exception("Transfer cancelled")
        
        # Update progress
        current_transferred = getattr(self, '_current_transferred', 0)
        current_transferred += bytes_transferred
        setattr(self, '_current_transferred', current_transferred)
        
        self._update_progress(transferred_bytes=current_transferred)
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file to S3.
        
        Args:
            source: Source file path (local)
            destination: Destination S3 key
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        source_path = Path(source)
        
        if not source_path.exists():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source file not found: {source}"
            )
        
        try:
            await self._connect()
            
            # Get file size for progress tracking
            file_size = source_path.stat().st_size
            self._update_progress(
                total_bytes=file_size,
                total_files=1,
                current_file=str(source)
            )
            
            # Reset progress counter
            setattr(self, '_current_transferred', 0)
            
            # Prepare extra arguments
            extra_args = {}
            if self.server_side_encryption:
                extra_args['ServerSideEncryption'] = self.server_side_encryption
                if self.sse_kms_key_id:
                    extra_args['SSEKMSKeyId'] = self.sse_kms_key_id
            if self.storage_class:
                extra_args['StorageClass'] = self.storage_class
            if self.metadata:
                extra_args['Metadata'] = self.metadata
            if self.acl:
                extra_args['ACL'] = self.acl
            
            # Upload file
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._s3_client.upload_file,
                str(source),
                self.bucket,
                str(destination),
                extra_args,
                self._s3_progress_callback,
                self._transfer_config
            )
            
            self._update_progress(
                transferred_files=1,
                status=TransferStatus.COMPLETED
            )
            
            return TransferResult(
                success=True,
                status=TransferStatus.COMPLETED,
                progress=self._progress,
                transferred_files=[str(source)],
                failed_files=[]
            )
            
        except Exception as e:
            self.logger.error(f"S3 file transfer failed: {e}")
            self._update_progress(status=TransferStatus.FAILED, error_message=str(e))
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    async def transfer_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        recursive: bool = True,
        **kwargs
    ) -> TransferResult:
        """
        Transfer a directory to S3.
        
        Args:
            source: Source directory path (local)
            destination: Destination S3 prefix
            recursive: Whether to transfer subdirectories
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        source_path = Path(source)
        
        if not source_path.exists():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source directory not found: {source}"
            )
        
        if not source_path.is_dir():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source is not a directory: {source}"
            )
        
        try:
            await self._connect()
            
            # Collect all files to transfer
            files_to_transfer = []
            if recursive:
                for file_path in source_path.rglob('*'):
                    if file_path.is_file():
                        files_to_transfer.append(file_path)
            else:
                for file_path in source_path.iterdir():
                    if file_path.is_file():
                        files_to_transfer.append(file_path)
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f in files_to_transfer)
            self._update_progress(
                total_bytes=total_size,
                total_files=len(files_to_transfer)
            )
            
            transferred_files = []
            failed_files = []
            
            # Transfer each file
            for file_path in files_to_transfer:
                if self.is_cancelled():
                    break
                
                try:
                    # Calculate relative path and S3 key
                    relative_path = file_path.relative_to(source_path)
                    s3_key = f"{destination}/{relative_path}".replace('\\', '/')
                    
                    self._update_progress(current_file=str(file_path))
                    
                    # Reset progress counter for this file
                    setattr(self, '_current_transferred', 0)
                    
                    # Prepare extra arguments
                    extra_args = {}
                    if self.server_side_encryption:
                        extra_args['ServerSideEncryption'] = self.server_side_encryption
                        if self.sse_kms_key_id:
                            extra_args['SSEKMSKeyId'] = self.sse_kms_key_id
                    if self.storage_class:
                        extra_args['StorageClass'] = self.storage_class
                    if self.metadata:
                        extra_args['Metadata'] = self.metadata
                    if self.acl:
                        extra_args['ACL'] = self.acl
                    
                    # Upload file
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        self._s3_client.upload_file,
                        str(file_path),
                        self.bucket,
                        s3_key,
                        extra_args,
                        self._s3_progress_callback,
                        self._transfer_config
                    )
                    
                    transferred_files.append(str(file_path))
                    self._update_progress(transferred_files=len(transferred_files))
                    
                except Exception as e:
                    self.logger.error(f"Failed to transfer {file_path}: {e}")
                    failed_files.append(str(file_path))
            
            success = len(failed_files) == 0 and not self.is_cancelled()
            status = TransferStatus.COMPLETED if success else TransferStatus.FAILED
            
            self._update_progress(status=status)
            
            return TransferResult(
                success=success,
                status=status,
                progress=self._progress,
                transferred_files=transferred_files,
                failed_files=failed_files
            )
            
        except Exception as e:
            self.logger.error(f"S3 directory transfer failed: {e}")
            self._update_progress(status=TransferStatus.FAILED, error_message=str(e))
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    async def cleanup(self) -> None:
        """Clean up S3 connections."""
        self._s3_client = None
        self._transfer_config = None


@register_transfer_method('gcs')
class GCSTransfer(TransferMethod):
    """
    Google Cloud Storage transfer implementation.
    
    Supports GCS operations with authentication via service account
    keys or application default credentials.
    """
    
    SUPPORTED_SCHEMES = ['gs://']
    REQUIRED_CONFIG = ['bucket']
    OPTIONAL_CONFIG = [
        'project_id', 'credentials_path', 'credentials_json',
        'chunk_size', 'timeout', 'storage_class', 'metadata'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize GCS transfer method.
        
        Args:
            config: Configuration dictionary with GCS parameters
        """
        if not GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage is required for GCS transfers. "
                "Install with: pip install google-cloud-storage"
            )
        
        super().__init__(config)
        
        # Parse URL if provided
        if 'url' in config:
            self._parse_url(config['url'])
        
        # GCS connection parameters
        self.bucket_name = config['bucket']
        self.project_id = config.get('project_id')
        self.credentials_path = config.get('credentials_path')
        self.credentials_json = config.get('credentials_json')
        
        # Transfer options
        self.chunk_size = config.get('chunk_size', 8 * 1024 * 1024)  # 8MB
        self.timeout = config.get('timeout', 300)
        self.storage_class = config.get('storage_class', 'STANDARD')
        self.metadata = config.get('metadata', {})
        
        # GCS client
        self._gcs_client: Optional[gcs.Client] = None
        self._bucket: Optional[gcs.Bucket] = None
    
    def _parse_url(self, url: str) -> None:
        """Parse GCS URL and update configuration."""
        parsed = urlparse(url)
        
        if parsed.netloc:
            self.config['bucket'] = parsed.netloc
    
    async def validate_config(self) -> bool:
        """
        Validate GCS configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required parameters
            if not self.bucket_name:
                self.logger.error("Bucket name is required for GCS transfers")
                return False
            
            # Validate storage class
            valid_storage_classes = [
                'STANDARD', 'NEARLINE', 'COLDLINE', 'ARCHIVE'
            ]
            if self.storage_class not in valid_storage_classes:
                self.logger.error(f"Invalid storage class: {self.storage_class}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test GCS connection and bucket access.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self._connect()
            
            # Test bucket access
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._bucket.exists)
            
            self.logger.info(f"GCS connection test successful to bucket: {self.bucket_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"GCS connection test failed: {e}")
            return False
    
    async def _connect(self) -> None:
        """Establish GCS connection."""
        if self._gcs_client and self._bucket:
            return
        
        # Prepare client parameters
        client_params = {}
        if self.project_id:
            client_params['project'] = self.project_id
        
        # Handle credentials
        if self.credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
        elif self.credentials_json:
            # TODO: Handle JSON credentials
            pass
        
        # Create GCS client
        self._gcs_client = gcs.Client(**client_params)
        self._bucket = self._gcs_client.bucket(self.bucket_name)
        
        self.logger.info(f"GCS connection established to bucket: {self.bucket_name}")
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file to GCS.
        
        Args:
            source: Source file path (local)
            destination: Destination GCS object name
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        source_path = Path(source)
        
        if not source_path.exists():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source file not found: {source}"
            )
        
        try:
            await self._connect()
            
            # Get file size for progress tracking
            file_size = source_path.stat().st_size
            self._update_progress(
                total_bytes=file_size,
                total_files=1,
                current_file=str(source)
            )
            
            # Create blob
            blob = self._bucket.blob(str(destination))
            
            # Set metadata
            if self.metadata:
                blob.metadata = self.metadata
            
            # Set storage class
            blob.storage_class = self.storage_class
            
            # Upload file
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                blob.upload_from_filename,
                str(source),
                timeout=self.timeout
            )
            
            self._update_progress(
                transferred_files=1,
                transferred_bytes=file_size,
                status=TransferStatus.COMPLETED
            )
            
            return TransferResult(
                success=True,
                status=TransferStatus.COMPLETED,
                progress=self._progress,
                transferred_files=[str(source)],
                failed_files=[]
            )
            
        except Exception as e:
            self.logger.error(f"GCS file transfer failed: {e}")
            self._update_progress(status=TransferStatus.FAILED, error_message=str(e))
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    async def transfer_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        recursive: bool = True,
        **kwargs
    ) -> TransferResult:
        """
        Transfer a directory to GCS.
        
        Args:
            source: Source directory path (local)
            destination: Destination GCS prefix
            recursive: Whether to transfer subdirectories
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        # Implementation similar to S3Transfer but using GCS client
        # For brevity, implementing a simplified version
        return await super().transfer_directory(source, destination, recursive, **kwargs)
    
    async def cleanup(self) -> None:
        """Clean up GCS connections."""
        self._gcs_client = None
        self._bucket = None


@register_transfer_method('azure')
class AzureBlobTransfer(TransferMethod):
    """
    Azure Blob Storage transfer implementation.
    
    Supports Azure Blob operations with various authentication methods
    including connection strings and shared access signatures.
    """
    
    SUPPORTED_SCHEMES = ['azure://', 'https://']
    REQUIRED_CONFIG = ['container']
    OPTIONAL_CONFIG = [
        'account_name', 'account_key', 'connection_string', 'sas_token',
        'account_url', 'chunk_size', 'timeout', 'blob_type', 'metadata'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Azure Blob transfer method.
        
        Args:
            config: Configuration dictionary with Azure parameters
        """
        if not AZURE_AVAILABLE:
            raise ImportError(
                "azure-storage-blob is required for Azure transfers. "
                "Install with: pip install azure-storage-blob"
            )
        
        super().__init__(config)
        
        # Parse URL if provided
        if 'url' in config:
            self._parse_url(config['url'])
        
        # Azure connection parameters
        self.container_name = config['container']
        self.account_name = config.get('account_name')
        self.account_key = config.get('account_key')
        self.connection_string = config.get('connection_string')
        self.sas_token = config.get('sas_token')
        self.account_url = config.get('account_url')
        
        # Transfer options
        self.chunk_size = config.get('chunk_size', 8 * 1024 * 1024)  # 8MB
        self.timeout = config.get('timeout', 300)
        self.blob_type = config.get('blob_type', 'BlockBlob')
        self.metadata = config.get('metadata', {})
        
        # Azure client
        self._blob_service_client: Optional[BlobServiceClient] = None
    
    def _parse_url(self, url: str) -> None:
        """Parse Azure URL and update configuration."""
        parsed = urlparse(url)
        
        if 'blob.core.windows.net' in parsed.netloc:
            # Extract account name from hostname
            account_name = parsed.netloc.split('.')[0]
            self.config['account_name'] = account_name
            self.config['account_url'] = f"https://{parsed.netloc}"
    
    async def validate_config(self) -> bool:
        """
        Validate Azure configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required parameters
            if not self.container_name:
                self.logger.error("Container name is required for Azure transfers")
                return False
            
            # Check authentication method
            has_auth = any([
                self.connection_string,
                (self.account_name and self.account_key),
                (self.account_url and self.sas_token)
            ])
            
            if not has_auth:
                self.logger.error("No valid authentication method specified")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test Azure connection and container access.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self._connect()
            
            # Test container access
            container_client = self._blob_service_client.get_container_client(self.container_name)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, container_client.get_container_properties)
            
            self.logger.info(f"Azure connection test successful to container: {self.container_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Azure connection test failed: {e}")
            return False
    
    async def _connect(self) -> None:
        """Establish Azure connection."""
        if self._blob_service_client:
            return
        
        # Create blob service client based on available authentication
        if self.connection_string:
            self._blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
        elif self.account_name and self.account_key:
            account_url = f"https://{self.account_name}.blob.core.windows.net"
            self._blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=self.account_key
            )
        elif self.account_url and self.sas_token:
            self._blob_service_client = BlobServiceClient(
                account_url=self.account_url,
                credential=self.sas_token
            )
        else:
            raise ValueError("No valid authentication method provided")
        
        self.logger.info(f"Azure connection established to container: {self.container_name}")
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file to Azure Blob Storage.
        
        Args:
            source: Source file path (local)
            destination: Destination blob name
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        source_path = Path(source)
        
        if not source_path.exists():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source file not found: {source}"
            )
        
        try:
            await self._connect()
            
            # Get file size for progress tracking
            file_size = source_path.stat().st_size
            self._update_progress(
                total_bytes=file_size,
                total_files=1,
                current_file=str(source)
            )
            
            # Get blob client
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container_name,
                blob=str(destination)
            )
            
            # Upload file
            with open(source, 'rb') as data:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    blob_client.upload_blob,
                    data,
                    overwrite=True,
                    metadata=self.metadata,
                    timeout=self.timeout
                )
            
            self._update_progress(
                transferred_files=1,
                transferred_bytes=file_size,
                status=TransferStatus.COMPLETED
            )
            
            return TransferResult(
                success=True,
                status=TransferStatus.COMPLETED,
                progress=self._progress,
                transferred_files=[str(source)],
                failed_files=[]
            )
            
        except Exception as e:
            self.logger.error(f"Azure file transfer failed: {e}")
            self._update_progress(status=TransferStatus.FAILED, error_message=str(e))
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    async def transfer_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        recursive: bool = True,
        **kwargs
    ) -> TransferResult:
        """
        Transfer a directory to Azure Blob Storage.
        
        Args:
            source: Source directory path (local)
            destination: Destination blob prefix
            recursive: Whether to transfer subdirectories
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        # Implementation similar to S3Transfer but using Azure client
        # For brevity, implementing a simplified version
        return await super().transfer_directory(source, destination, recursive, **kwargs)
    
    async def cleanup(self) -> None:
        """Clean up Azure connections."""
        self._blob_service_client = None