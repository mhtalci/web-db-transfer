"""
FTP/FTPS transfer implementation.

This module provides FTP and FTPS file transfer capabilities using Python's
built-in ftplib with optional ftputil enhancement for advanced features.
"""

import asyncio
import os
import ssl
from ftplib import FTP, FTP_TLS, error_perm, error_temp
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
from urllib.parse import urlparse
import logging

try:
    import ftputil
    FTPUTIL_AVAILABLE = True
except ImportError:
    FTPUTIL_AVAILABLE = False

from ..base import TransferMethod, TransferResult, TransferStatus
from ..factory import register_transfer_method

logger = logging.getLogger(__name__)


@register_transfer_method('ftp')
class FtpTransfer(TransferMethod):
    """
    FTP/FTPS transfer implementation using ftplib and optional ftputil.
    
    Supports both plain FTP and secure FTPS connections with various
    authentication methods and transfer modes.
    """
    
    SUPPORTED_SCHEMES = ['ftp://', 'ftps://']
    REQUIRED_CONFIG = ['host']
    OPTIONAL_CONFIG = [
        'port', 'username', 'password', 'use_tls', 'passive_mode',
        'timeout', 'encoding', 'create_directories', 'preserve_times',
        'transfer_mode', 'ssl_context'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize FTP transfer method.
        
        Args:
            config: Configuration dictionary with FTP connection parameters
        """
        super().__init__(config)
        
        # Parse URL if provided
        if 'url' in config:
            self._parse_url(config['url'])
        
        # FTP connection parameters
        self.host = config['host']
        self.port = config.get('port', 21)
        self.username = config.get('username', 'anonymous')
        self.password = config.get('password', 'anonymous@')
        self.use_tls = config.get('use_tls', False)
        self.passive_mode = config.get('passive_mode', True)
        self.timeout = config.get('timeout', 30)
        self.encoding = config.get('encoding', 'utf-8')
        
        # Transfer options
        self.create_directories = config.get('create_directories', True)
        self.preserve_times = config.get('preserve_times', False)
        self.transfer_mode = config.get('transfer_mode', 'binary')  # 'binary' or 'ascii'
        
        # SSL context for FTPS
        self.ssl_context = config.get('ssl_context')
        if self.use_tls and not self.ssl_context:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Connection objects
        self._ftp_client: Optional[Union[FTP, FTP_TLS]] = None
        self._ftputil_host: Optional[Any] = None  # ftputil.FTPHost if available
    
    def _parse_url(self, url: str) -> None:
        """Parse FTP URL and update configuration."""
        parsed = urlparse(url)
        
        if parsed.hostname:
            self.config['host'] = parsed.hostname
        if parsed.port:
            self.config['port'] = parsed.port
        if parsed.username:
            self.config['username'] = parsed.username
        if parsed.password:
            self.config['password'] = parsed.password
        
        # Determine if TLS should be used
        if parsed.scheme == 'ftps':
            self.config['use_tls'] = True
    
    async def validate_config(self) -> bool:
        """
        Validate FTP configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required parameters
            if not self.host:
                self.logger.error("Host is required for FTP connection")
                return False
            
            # Validate port
            if not (1 <= self.port <= 65535):
                self.logger.error(f"Invalid port number: {self.port}")
                return False
            
            # Validate transfer mode
            if self.transfer_mode not in ['binary', 'ascii']:
                self.logger.error(f"Invalid transfer mode: {self.transfer_mode}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test FTP connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Create FTP client
            if self.use_tls:
                ftp_client = FTP_TLS(context=self.ssl_context)
            else:
                ftp_client = FTP()
            
            # Connect and login
            ftp_client.connect(self.host, self.port, self.timeout)
            ftp_client.login(self.username, self.password)
            
            # Set passive mode
            ftp_client.set_pasv(self.passive_mode)
            
            # For FTPS, secure the data connection
            if self.use_tls:
                ftp_client.prot_p()
            
            # Test directory listing
            ftp_client.nlst()
            
            ftp_client.quit()
            self.logger.info(f"FTP connection test successful to {self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"FTP connection test failed: {e}")
            return False
    
    async def _connect(self) -> None:
        """Establish FTP connection."""
        if self._ftp_client:
            try:
                # Test if connection is still alive
                self._ftp_client.voidcmd("NOOP")
                return
            except:
                # Connection is dead, reconnect
                self._ftp_client = None
        
        # Create FTP client
        if self.use_tls:
            self._ftp_client = FTP_TLS(context=self.ssl_context)
        else:
            self._ftp_client = FTP()
        
        # Connect and login
        self._ftp_client.connect(self.host, self.port, self.timeout)
        self._ftp_client.login(self.username, self.password)
        
        # Set passive mode
        self._ftp_client.set_pasv(self.passive_mode)
        
        # For FTPS, secure the data connection
        if self.use_tls:
            self._ftp_client.prot_p()
        
        # Set encoding
        if hasattr(self._ftp_client, 'encoding'):
            self._ftp_client.encoding = self.encoding
        
        # Initialize ftputil if available
        if FTPUTIL_AVAILABLE:
            try:
                session_factory = ftputil.session.session_factory(
                    use_passive_mode=self.passive_mode,
                    encrypt_data_channel=self.use_tls
                )
                
                self._ftputil_host = ftputil.FTPHost(
                    self.host,
                    self.username,
                    self.password,
                    port=self.port,
                    session_factory=session_factory
                )
            except Exception as e:
                self.logger.warning(f"Failed to initialize ftputil: {e}")
                self._ftputil_host = None
        
        self.logger.info(f"FTP connection established to {self.host}:{self.port}")
    
    async def _disconnect(self) -> None:
        """Close FTP connection."""
        if self._ftputil_host:
            try:
                self._ftputil_host.close()
            except:
                pass
            self._ftputil_host = None
        
        if self._ftp_client:
            try:
                self._ftp_client.quit()
            except:
                try:
                    self._ftp_client.close()
                except:
                    pass
            self._ftp_client = None
        
        self.logger.debug("FTP connection closed")
    
    def _ftp_progress_callback(self, data: bytes) -> None:
        """FTP progress callback for data transfer."""
        if self.is_cancelled():
            raise Exception("Transfer cancelled")
        
        # Update transferred bytes
        current_transferred = getattr(self, '_current_transferred', 0)
        current_transferred += len(data)
        setattr(self, '_current_transferred', current_transferred)
        
        self._update_progress(transferred_bytes=current_transferred)
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file using FTP/FTPS.
        
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
            
            # Create remote directory if needed
            if self.create_directories:
                remote_dir = os.path.dirname(str(destination))
                if remote_dir:
                    await self._create_remote_directory(remote_dir)
            
            # Transfer file
            if self._ftputil_host:
                await self._transfer_file_ftputil(source_path, str(destination))
            else:
                await self._transfer_file_ftplib(source_path, str(destination))
            
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
    
    async def _transfer_file_ftputil(self, source: Path, destination: str) -> None:
        """Transfer file using ftputil (if available)."""
        if not self._ftputil_host:
            raise Exception("ftputil host not available")
        
        loop = asyncio.get_event_loop()
        
        # Use ftputil's upload method
        await loop.run_in_executor(
            None,
            self._ftputil_host.upload,
            str(source),
            destination
        )
        
        # Preserve times if requested
        if self.preserve_times:
            source_stat = source.stat()
            await loop.run_in_executor(
                None,
                self._ftputil_host.utime,
                destination,
                (source_stat.st_atime, source_stat.st_mtime)
            )
    
    async def _transfer_file_ftplib(self, source: Path, destination: str) -> None:
        """Transfer file using ftplib."""
        if not self._ftp_client:
            raise Exception("FTP client not available")
        
        # Reset progress counter
        setattr(self, '_current_transferred', 0)
        
        # Open source file
        with open(source, 'rb') as f:
            # Set transfer mode
            if self.transfer_mode == 'binary':
                command = f"STOR {destination}"
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._ftp_client.storbinary,
                    command,
                    f,
                    callback=self._ftp_progress_callback
                )
            else:
                # ASCII mode
                with open(source, 'r', encoding=self.encoding) as text_file:
                    command = f"STOR {destination}"
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        self._ftp_client.storlines,
                        command,
                        text_file
                    )
    
    async def _create_remote_directory(self, remote_path: str) -> None:
        """Create remote directory."""
        if self._ftputil_host:
            # Use ftputil
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._ftputil_host.makedirs,
                remote_path,
                exist_ok=True
            )
        else:
            # Use ftplib
            await self._create_remote_directory_ftplib(remote_path)
    
    async def _create_remote_directory_ftplib(self, remote_path: str) -> None:
        """Create remote directory using ftplib."""
        if not self._ftp_client:
            return
        
        # Split path into components
        path_parts = remote_path.strip('/').split('/')
        current_path = ''
        
        for part in path_parts:
            if not part:
                continue
            
            current_path = f"{current_path}/{part}" if current_path else part
            
            try:
                # Try to change to directory
                self._ftp_client.cwd(current_path)
            except error_perm:
                # Directory doesn't exist, create it
                try:
                    self._ftp_client.mkd(current_path)
                except error_perm as e:
                    # Ignore if directory already exists
                    if "exists" not in str(e).lower():
                        raise
        
        # Return to root
        self._ftp_client.cwd('/')
    
    async def transfer_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        recursive: bool = True,
        **kwargs
    ) -> TransferResult:
        """
        Transfer a directory using FTP/FTPS.
        
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
                    
                    # Create remote directory if needed
                    remote_dir = os.path.dirname(remote_file_path)
                    if remote_dir and self.create_directories:
                        await self._create_remote_directory(remote_dir)
                    
                    # Transfer file
                    if self._ftputil_host:
                        await self._transfer_file_ftputil(file_path, remote_file_path)
                    else:
                        await self._transfer_file_ftplib(file_path, remote_file_path)
                    
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
        """Clean up FTP connections."""
        await self._disconnect()