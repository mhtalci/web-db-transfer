"""
SSH/SCP/SFTP transfer implementation using paramiko.

This module provides secure file transfer capabilities using SSH protocols
including SCP and SFTP with support for various authentication methods.
"""

import asyncio
import os
import stat
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
from urllib.parse import urlparse
import logging

try:
    import paramiko
    from paramiko import SSHClient, SFTPClient, AutoAddPolicy
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False

from ..base import TransferMethod, TransferResult, TransferStatus
from ..factory import register_transfer_method

logger = logging.getLogger(__name__)


@register_transfer_method('ssh')
class ParamikoTransfer(TransferMethod):
    """
    SSH/SCP/SFTP transfer implementation using paramiko.
    
    Supports various authentication methods including password, key-based,
    and agent authentication. Provides both SCP and SFTP transfer modes.
    """
    
    SUPPORTED_SCHEMES = ['ssh://', 'sftp://', 'scp://']
    REQUIRED_CONFIG = ['host']
    OPTIONAL_CONFIG = [
        'port', 'username', 'password', 'key_filename', 'key_data',
        'timeout', 'compress', 'look_for_keys', 'allow_agent',
        'host_key_policy', 'transfer_mode', 'preserve_permissions',
        'preserve_times', 'create_directories'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SSH transfer method.
        
        Args:
            config: Configuration dictionary with SSH connection parameters
        """
        if not PARAMIKO_AVAILABLE:
            raise ImportError(
                "paramiko is required for SSH transfers. "
                "Install with: pip install paramiko"
            )
        
        super().__init__(config)
        
        # Parse URL if provided
        if 'url' in config:
            self._parse_url(config['url'])
        
        # SSH connection parameters
        self.host = config.get('host', '')
        self.port = config.get('port', 22)
        self.username = config.get('username', os.getenv('USER'))
        self.password = config.get('password')
        self.key_filename = config.get('key_filename')
        self.key_data = config.get('key_data')
        self.timeout = config.get('timeout', 30)
        self.compress = config.get('compress', True)
        self.look_for_keys = config.get('look_for_keys', True)
        self.allow_agent = config.get('allow_agent', True)
        
        # Host key policy
        host_key_policy = config.get('host_key_policy', 'auto_add')
        if host_key_policy == 'auto_add':
            self.host_key_policy = AutoAddPolicy()
        elif host_key_policy == 'reject':
            self.host_key_policy = paramiko.RejectPolicy()
        else:
            self.host_key_policy = AutoAddPolicy()
        
        # Transfer options
        self.transfer_mode = config.get('transfer_mode', 'sftp')  # 'sftp' or 'scp'
        self.preserve_permissions = config.get('preserve_permissions', True)
        self.preserve_times = config.get('preserve_times', True)
        self.create_directories = config.get('create_directories', True)
        
        # Connection objects
        self._ssh_client: Optional[SSHClient] = None
        self._sftp_client: Optional[SFTPClient] = None
    
    def _parse_url(self, url: str) -> None:
        """Parse SSH URL and update configuration."""
        parsed = urlparse(url)
        
        if parsed.hostname:
            self.config['host'] = parsed.hostname
        if parsed.port:
            self.config['port'] = parsed.port
        if parsed.username:
            self.config['username'] = parsed.username
        if parsed.password:
            self.config['password'] = parsed.password
        
        # Determine transfer mode from scheme
        if parsed.scheme == 'scp':
            self.config['transfer_mode'] = 'scp'
        elif parsed.scheme in ['ssh', 'sftp']:
            self.config['transfer_mode'] = 'sftp'
    
    async def validate_config(self) -> bool:
        """
        Validate SSH configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required parameters
            if not self.host:
                self.logger.error("Host is required for SSH connection")
                return False
            
            # Validate port
            if not (1 <= self.port <= 65535):
                self.logger.error(f"Invalid port number: {self.port}")
                return False
            
            # Check authentication method
            has_auth = any([
                self.password,
                self.key_filename,
                self.key_data,
                self.look_for_keys,
                self.allow_agent
            ])
            
            if not has_auth:
                self.logger.error("No authentication method specified")
                return False
            
            # Validate key file if specified
            if self.key_filename and not os.path.exists(self.key_filename):
                self.logger.error(f"Key file not found: {self.key_filename}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test SSH connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            ssh_client = SSHClient()
            ssh_client.set_missing_host_key_policy(self.host_key_policy)
            
            # Prepare connection parameters
            connect_params = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': self.timeout,
                'compress': self.compress,
                'look_for_keys': self.look_for_keys,
                'allow_agent': self.allow_agent
            }
            
            # Add authentication parameters
            if self.password:
                connect_params['password'] = self.password
            if self.key_filename:
                connect_params['key_filename'] = self.key_filename
            if self.key_data:
                connect_params['pkey'] = paramiko.RSAKey.from_private_key_file(
                    io.StringIO(self.key_data)
                )
            
            # Test connection
            ssh_client.connect(**connect_params)
            
            # Test SFTP if using SFTP mode
            if self.transfer_mode == 'sftp':
                sftp = ssh_client.open_sftp()
                sftp.close()
            
            ssh_client.close()
            self.logger.info(f"SSH connection test successful to {self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"SSH connection test failed: {e}")
            return False
    
    async def _connect(self) -> None:
        """Establish SSH connection."""
        if self._ssh_client and self._ssh_client.get_transport() and self._ssh_client.get_transport().is_active():
            return
        
        self._ssh_client = SSHClient()
        self._ssh_client.set_missing_host_key_policy(self.host_key_policy)
        
        # Prepare connection parameters
        connect_params = {
            'hostname': self.host,
            'port': self.port,
            'username': self.username,
            'timeout': self.timeout,
            'compress': self.compress,
            'look_for_keys': self.look_for_keys,
            'allow_agent': self.allow_agent
        }
        
        # Add authentication parameters
        if self.password:
            connect_params['password'] = self.password
        if self.key_filename:
            connect_params['key_filename'] = self.key_filename
        if self.key_data:
            import io
            connect_params['pkey'] = paramiko.RSAKey.from_private_key_file(
                io.StringIO(self.key_data)
            )
        
        # Connect
        self._ssh_client.connect(**connect_params)
        
        # Open SFTP if using SFTP mode
        if self.transfer_mode == 'sftp':
            self._sftp_client = self._ssh_client.open_sftp()
        
        self.logger.info(f"SSH connection established to {self.host}:{self.port}")
    
    async def _disconnect(self) -> None:
        """Close SSH connection."""
        if self._sftp_client:
            self._sftp_client.close()
            self._sftp_client = None
        
        if self._ssh_client:
            self._ssh_client.close()
            self._ssh_client = None
        
        self.logger.debug("SSH connection closed")
    
    def _sftp_progress_callback(self, transferred: int, total: int) -> None:
        """SFTP progress callback."""
        if self.is_cancelled():
            raise Exception("Transfer cancelled")
        
        self._update_progress(
            transferred_bytes=transferred,
            total_bytes=total,
            transfer_rate=0.0  # TODO: Calculate transfer rate
        )
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file using SSH/SFTP/SCP.
        
        Args:
            source: Source file path (local)
            destination: Destination file path (remote)
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
            
            if self.transfer_mode == 'sftp':
                await self._transfer_file_sftp(source_path, destination)
            else:
                await self._transfer_file_scp(source_path, destination)
            
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
            self.logger.error(f"File transfer failed: {e}")
            self._update_progress(status=TransferStatus.FAILED, error_message=str(e))
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    async def _transfer_file_sftp(self, source: Path, destination: str) -> None:
        """Transfer file using SFTP."""
        if not self._sftp_client:
            raise Exception("SFTP client not available")
        
        # Create remote directory if needed
        if self.create_directories:
            remote_dir = os.path.dirname(destination)
            if remote_dir:
                await self._create_remote_directory_sftp(remote_dir)
        
        # Transfer file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._sftp_client.put,
            str(source),
            destination,
            self._sftp_progress_callback
        )
        
        # Preserve permissions and times if requested
        if self.preserve_permissions or self.preserve_times:
            source_stat = source.stat()
            
            if self.preserve_permissions:
                self._sftp_client.chmod(destination, source_stat.st_mode)
            
            if self.preserve_times:
                self._sftp_client.utime(destination, (source_stat.st_atime, source_stat.st_mtime))
    
    async def _transfer_file_scp(self, source: Path, destination: str) -> None:
        """Transfer file using SCP."""
        if not self._ssh_client:
            raise Exception("SSH client not available")
        
        # Create remote directory if needed
        if self.create_directories:
            remote_dir = os.path.dirname(destination)
            if remote_dir:
                await self._create_remote_directory_scp(remote_dir)
        
        # Use SCP command
        scp_command = f"scp -t {destination}"
        transport = self._ssh_client.get_transport()
        channel = transport.open_session()
        
        try:
            channel.exec_command(scp_command)
            
            # Send file via SCP protocol
            source_stat = source.stat()
            file_size = source_stat.st_size
            
            # Send file header
            file_mode = oct(source_stat.st_mode)[-4:]
            header = f"C{file_mode} {file_size} {source.name}\n"
            channel.send(header.encode())
            
            # Wait for acknowledgment
            response = channel.recv(1)
            if response != b'\x00':
                raise Exception(f"SCP error: {response}")
            
            # Send file content
            with open(source, 'rb') as f:
                transferred = 0
                while transferred < file_size:
                    if self.is_cancelled():
                        raise Exception("Transfer cancelled")
                    
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    
                    channel.send(chunk)
                    transferred += len(chunk)
                    
                    self._update_progress(transferred_bytes=transferred)
            
            # Send end marker
            channel.send(b'\x00')
            
            # Wait for final acknowledgment
            response = channel.recv(1)
            if response != b'\x00':
                raise Exception(f"SCP error: {response}")
            
        finally:
            channel.close()
    
    async def _create_remote_directory_sftp(self, remote_path: str) -> None:
        """Create remote directory using SFTP."""
        if not self._sftp_client:
            return
        
        try:
            self._sftp_client.stat(remote_path)
        except FileNotFoundError:
            # Directory doesn't exist, create it
            parent_dir = os.path.dirname(remote_path)
            if parent_dir and parent_dir != remote_path:
                await self._create_remote_directory_sftp(parent_dir)
            
            self._sftp_client.mkdir(remote_path)
    
    async def _create_remote_directory_scp(self, remote_path: str) -> None:
        """Create remote directory using SSH command."""
        if not self._ssh_client:
            return
        
        command = f"mkdir -p {remote_path}"
        stdin, stdout, stderr = self._ssh_client.exec_command(command)
        
        # Wait for command completion
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_msg = stderr.read().decode()
            raise Exception(f"Failed to create directory {remote_path}: {error_msg}")
    
    async def transfer_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        recursive: bool = True,
        **kwargs
    ) -> TransferResult:
        """
        Transfer a directory using SSH/SFTP/SCP.
        
        Args:
            source: Source directory path (local)
            destination: Destination directory path (remote)
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
                    # Calculate relative path
                    relative_path = file_path.relative_to(source_path)
                    remote_file_path = f"{destination}/{relative_path}".replace('\\', '/')
                    
                    self._update_progress(current_file=str(file_path))
                    
                    if self.transfer_mode == 'sftp':
                        await self._transfer_file_sftp(file_path, remote_file_path)
                    else:
                        await self._transfer_file_scp(file_path, remote_file_path)
                    
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
            self.logger.error(f"Directory transfer failed: {e}")
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
        """Clean up SSH connections."""
        await self._disconnect()