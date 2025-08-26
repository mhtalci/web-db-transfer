"""
Docker transfer implementation using docker-py.

This module provides Docker container and volume transfer capabilities
with support for copying files to/from containers and volumes.
"""

import asyncio
import io
import tarfile
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
import logging

try:
    import docker
    from docker.errors import DockerException, APIError, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from ..base import TransferMethod, TransferResult, TransferStatus
from ..factory import register_transfer_method

logger = logging.getLogger(__name__)


@register_transfer_method('docker')
class DockerTransfer(TransferMethod):
    """
    Docker transfer implementation using docker-py.
    
    Supports copying files to/from Docker containers and volumes
    with various authentication and connection options.
    """
    
    SUPPORTED_SCHEMES = ['docker://']
    REQUIRED_CONFIG = ['container_or_volume']
    OPTIONAL_CONFIG = [
        'docker_host', 'tls_config', 'api_version', 'timeout',
        'container_path', 'volume_name', 'workdir', 'user',
        'create_container', 'image', 'command'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Docker transfer method.
        
        Args:
            config: Configuration dictionary with Docker parameters
        """
        if not DOCKER_AVAILABLE:
            raise ImportError(
                "docker is required for Docker transfers. "
                "Install with: pip install docker"
            )
        
        super().__init__(config)
        
        # Parse URL if provided
        if 'url' in config:
            self._parse_url(config['url'])
        
        # Docker connection parameters
        self.docker_host = config.get('docker_host')
        self.tls_config = config.get('tls_config')
        self.api_version = config.get('api_version', 'auto')
        self.timeout = config.get('timeout', 60)
        
        # Container/Volume parameters
        self.container_or_volume = config['container_or_volume']
        self.container_path = config.get('container_path', '/tmp')
        self.volume_name = config.get('volume_name')
        self.workdir = config.get('workdir')
        self.user = config.get('user')
        
        # Container creation options
        self.create_container = config.get('create_container', False)
        self.image = config.get('image')  # No default, required when creating container
        self.command = config.get('command', 'sleep 3600')
        
        # Docker client
        self._docker_client: Optional[docker.DockerClient] = None
        self._created_container: Optional[str] = None
    
    def _parse_url(self, url: str) -> None:
        """Parse Docker URL and update configuration."""
        # Example: docker://container_name/path/to/file
        if url.startswith('docker://'):
            parts = url[9:].split('/', 1)
            self.config['container_or_volume'] = parts[0]
            if len(parts) > 1:
                self.config['container_path'] = '/' + parts[1]
    
    async def validate_config(self) -> bool:
        """
        Validate Docker configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required parameters
            if not self.container_or_volume:
                self.logger.error("Container or volume name is required")
                return False
            
            # If creating container, image is required
            if self.create_container and not self.image:
                self.logger.error("Image is required when creating container")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test Docker connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self._connect()
            
            # Test Docker daemon connection
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._docker_client.ping)
            
            self.logger.info("Docker connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Docker connection test failed: {e}")
            return False
    
    async def _connect(self) -> None:
        """Establish Docker connection."""
        if self._docker_client:
            return
        
        # Prepare client parameters
        client_params = {
            'version': self.api_version,
            'timeout': self.timeout
        }
        
        if self.docker_host:
            client_params['base_url'] = self.docker_host
        if self.tls_config:
            client_params['tls'] = self.tls_config
        
        # Create Docker client
        self._docker_client = docker.DockerClient(**client_params)
        
        self.logger.info("Docker connection established")
    
    async def _ensure_container_exists(self) -> str:
        """Ensure container exists, create if needed."""
        if self._created_container:
            return self._created_container
        
        loop = asyncio.get_event_loop()
        
        try:
            # Try to get existing container
            container = await loop.run_in_executor(
                None,
                self._docker_client.containers.get,
                self.container_or_volume
            )
            
            # Start container if not running
            if container.status != 'running':
                await loop.run_in_executor(None, container.start)
            
            return self.container_or_volume
            
        except NotFound:
            if not self.create_container:
                raise Exception(f"Container {self.container_or_volume} not found")
            
            # Create new container
            self.logger.info(f"Creating container {self.container_or_volume}")
            
            container_config = {
                'image': self.image,
                'command': self.command,
                'name': self.container_or_volume,
                'detach': True
            }
            
            if self.workdir:
                container_config['working_dir'] = self.workdir
            if self.user:
                container_config['user'] = self.user
            
            container = await loop.run_in_executor(
                None,
                self._docker_client.containers.run,
                **container_config
            )
            
            self._created_container = container.name
            return self._created_container
    
    async def _create_tar_archive(self, source_path: Path) -> io.BytesIO:
        """Create tar archive from source path."""
        tar_buffer = io.BytesIO()
        
        with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
            if source_path.is_file():
                tar.add(source_path, arcname=source_path.name)
            elif source_path.is_dir():
                for item in source_path.rglob('*'):
                    if item.is_file():
                        arcname = item.relative_to(source_path.parent)
                        tar.add(item, arcname=str(arcname))
        
        tar_buffer.seek(0)
        return tar_buffer
    
    async def _extract_tar_archive(self, tar_data: bytes, destination_path: Path) -> None:
        """Extract tar archive to destination path."""
        tar_buffer = io.BytesIO(tar_data)
        
        with tarfile.open(fileobj=tar_buffer, mode='r') as tar:
            tar.extractall(path=destination_path.parent)
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file to/from Docker container.
        
        Args:
            source: Source file path
            destination: Destination file path
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
            
            # Determine transfer direction
            is_to_container = kwargs.get('to_container', True)
            
            if is_to_container:
                # Transfer to container
                container_name = await self._ensure_container_exists()
                container = self._docker_client.containers.get(container_name)
                
                # Create tar archive
                tar_archive = await self._create_tar_archive(source_path)
                
                # Copy to container
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    container.put_archive,
                    self.container_path,
                    tar_archive.getvalue()
                )
                
            else:
                # Transfer from container
                container = self._docker_client.containers.get(self.container_or_volume)
                
                # Get archive from container
                loop = asyncio.get_event_loop()
                tar_data, _ = await loop.run_in_executor(
                    None,
                    container.get_archive,
                    str(destination)
                )
                
                # Extract archive
                tar_bytes = b''.join(tar_data)
                await self._extract_tar_archive(tar_bytes, Path(source))
            
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
            self.logger.error(f"Docker file transfer failed: {e}")
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
        Transfer a directory to/from Docker container.
        
        Args:
            source: Source directory path
            destination: Destination directory path
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
            
            # Determine transfer direction
            is_to_container = kwargs.get('to_container', True)
            
            if is_to_container:
                # Transfer to container
                container_name = await self._ensure_container_exists()
                container = self._docker_client.containers.get(container_name)
                
                # Create tar archive for entire directory
                tar_archive = await self._create_tar_archive(source_path)
                
                # Copy to container
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    container.put_archive,
                    self.container_path,
                    tar_archive.getvalue()
                )
                
            else:
                # Transfer from container
                container = self._docker_client.containers.get(self.container_or_volume)
                
                # Get archive from container
                loop = asyncio.get_event_loop()
                tar_data, _ = await loop.run_in_executor(
                    None,
                    container.get_archive,
                    str(destination)
                )
                
                # Extract archive
                tar_bytes = b''.join(tar_data)
                await self._extract_tar_archive(tar_bytes, Path(source))
            
            transferred_files = [str(f) for f in files_to_transfer]
            
            self._update_progress(
                transferred_files=len(transferred_files),
                transferred_bytes=total_size,
                status=TransferStatus.COMPLETED
            )
            
            return TransferResult(
                success=True,
                status=TransferStatus.COMPLETED,
                progress=self._progress,
                transferred_files=transferred_files,
                failed_files=[]
            )
            
        except Exception as e:
            self.logger.error(f"Docker directory transfer failed: {e}")
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
        """Clean up Docker resources."""
        if self._created_container and self._docker_client:
            try:
                container = self._docker_client.containers.get(self._created_container)
                container.stop()
                container.remove()
                self.logger.info(f"Cleaned up created container: {self._created_container}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup container: {e}")
        
        if self._docker_client:
            self._docker_client.close()
            self._docker_client = None