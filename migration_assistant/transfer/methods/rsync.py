"""
Rsync transfer implementation using subprocess.

This module provides rsync-based file transfer capabilities with
support for various rsync options and progress monitoring.
"""

import asyncio
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
import logging

from ..base import TransferMethod, TransferResult, TransferStatus
from ..factory import register_transfer_method

logger = logging.getLogger(__name__)


@register_transfer_method('rsync')
class RsyncTransfer(TransferMethod):
    """
    Rsync transfer implementation using subprocess.
    
    Supports various rsync options including SSH transport,
    compression, and detailed progress monitoring.
    """
    
    SUPPORTED_SCHEMES = ['rsync://', 'ssh://']
    REQUIRED_CONFIG = ['destination']
    OPTIONAL_CONFIG = [
        'rsync_path', 'ssh_user', 'ssh_host', 'ssh_port', 'ssh_key',
        'compress', 'archive', 'verbose', 'dry_run', 'delete',
        'exclude', 'include', 'timeout', 'bandwidth_limit',
        'checksum', 'partial', 'progress', 'stats'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize rsync transfer method.
        
        Args:
            config: Configuration dictionary with rsync parameters
        """
        super().__init__(config)
        
        # Check if rsync is available
        self.rsync_path = config.get('rsync_path', 'rsync')
        if not shutil.which(self.rsync_path):
            raise FileNotFoundError(
                f"rsync not found at {self.rsync_path}. "
                "Please install rsync or specify correct path."
            )
        
        # Connection parameters
        self.destination = config['destination']
        self.ssh_user = config.get('ssh_user')
        self.ssh_host = config.get('ssh_host')
        self.ssh_port = config.get('ssh_port', 22)
        self.ssh_key = config.get('ssh_key')
        
        # Rsync options
        self.compress = config.get('compress', True)
        self.archive = config.get('archive', True)
        self.verbose = config.get('verbose', True)
        self.dry_run = config.get('dry_run', False)
        self.delete = config.get('delete', False)
        self.exclude = config.get('exclude', [])
        self.include = config.get('include', [])
        self.timeout = config.get('timeout', 300)
        self.bandwidth_limit = config.get('bandwidth_limit')  # KB/s
        self.checksum = config.get('checksum', False)
        self.partial = config.get('partial', True)
        self.progress = config.get('progress', True)
        self.stats = config.get('stats', True)
        
        # Progress tracking
        self._total_files = 0
        self._transferred_files = 0
        self._total_bytes = 0
        self._transferred_bytes = 0
        self._current_file = ""
    
    async def validate_config(self) -> bool:
        """
        Validate rsync configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check if rsync is available
            if not shutil.which(self.rsync_path):
                self.logger.error(f"rsync not found at {self.rsync_path}")
                return False
            
            # Check required parameters
            if not self.destination:
                self.logger.error("Destination is required for rsync transfers")
                return False
            
            # Validate SSH key if specified
            if self.ssh_key and not Path(self.ssh_key).exists():
                self.logger.error(f"SSH key file not found: {self.ssh_key}")
                return False
            
            # Validate port
            if not (1 <= self.ssh_port <= 65535):
                self.logger.error(f"Invalid SSH port: {self.ssh_port}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test rsync connection with dry run.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Build rsync command for connection test
            cmd = [self.rsync_path, '--dry-run', '--list-only']
            
            # Add SSH options if needed
            if self.ssh_user and self.ssh_host:
                ssh_cmd = ['ssh']
                if self.ssh_port != 22:
                    ssh_cmd.extend(['-p', str(self.ssh_port)])
                if self.ssh_key:
                    ssh_cmd.extend(['-i', self.ssh_key])
                
                cmd.extend(['-e', ' '.join(ssh_cmd)])
                test_dest = f"{self.ssh_user}@{self.ssh_host}:/"
            else:
                test_dest = self.destination
            
            cmd.append(test_dest)
            
            # Run test command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.logger.info("Rsync connection test successful")
                return True
            else:
                self.logger.error(f"Rsync connection test failed: {stderr.decode()}")
                return False
            
        except Exception as e:
            self.logger.error(f"Rsync connection test failed: {e}")
            return False
    
    def _build_rsync_command(self, source: str, destination: str) -> List[str]:
        """Build rsync command with options."""
        cmd = [self.rsync_path]
        
        # Basic options
        if self.archive:
            cmd.append('-a')
        if self.verbose:
            cmd.append('-v')
        if self.compress:
            cmd.append('-z')
        if self.dry_run:
            cmd.append('--dry-run')
        if self.delete:
            cmd.append('--delete')
        if self.checksum:
            cmd.append('--checksum')
        if self.partial:
            cmd.append('--partial')
        if self.progress:
            cmd.append('--progress')
        if self.stats:
            cmd.append('--stats')
        
        # Timeout
        if self.timeout:
            cmd.extend(['--timeout', str(self.timeout)])
        
        # Bandwidth limit
        if self.bandwidth_limit:
            cmd.extend(['--bwlimit', str(self.bandwidth_limit)])
        
        # Exclude patterns
        for pattern in self.exclude:
            cmd.extend(['--exclude', pattern])
        
        # Include patterns
        for pattern in self.include:
            cmd.extend(['--include', pattern])
        
        # SSH options
        if self.ssh_user and self.ssh_host:
            ssh_cmd = ['ssh']
            if self.ssh_port != 22:
                ssh_cmd.extend(['-p', str(self.ssh_port)])
            if self.ssh_key:
                ssh_cmd.extend(['-i', self.ssh_key])
            
            cmd.extend(['-e', ' '.join(ssh_cmd)])
            
            # Modify destination for SSH
            if not destination.startswith(f"{self.ssh_user}@{self.ssh_host}:"):
                destination = f"{self.ssh_user}@{self.ssh_host}:{destination}"
        
        # Add source and destination
        cmd.extend([source, destination])
        
        return cmd
    
    def _parse_progress_line(self, line: str) -> None:
        """Parse rsync progress output."""
        line = line.strip()
        
        if not line:
            return
        
        # Parse file transfer progress
        # Example: "    1,234,567  45%  123.45kB/s    0:00:12  filename.txt"
        progress_match = re.match(
            r'\s*(\d+(?:,\d+)*)\s+(\d+)%\s+([0-9.]+[kMG]?B/s)\s+(\d+:\d+:\d+)\s+(.+)',
            line
        )
        
        if progress_match:
            transferred_str, percent_str, rate_str, eta_str, filename = progress_match.groups()
            
            # Parse transferred bytes
            transferred = int(transferred_str.replace(',', ''))
            percent = int(percent_str)
            
            # Parse transfer rate
            rate_match = re.match(r'([0-9.]+)([kMG]?)B/s', rate_str)
            if rate_match:
                rate_value, rate_unit = rate_match.groups()
                rate = float(rate_value)
                if rate_unit == 'k':
                    rate *= 1024
                elif rate_unit == 'M':
                    rate *= 1024 * 1024
                elif rate_unit == 'G':
                    rate *= 1024 * 1024 * 1024
            else:
                rate = 0.0
            
            # Update progress
            self._transferred_bytes = transferred
            self._current_file = filename.strip()
            
            self._update_progress(
                transferred_bytes=self._transferred_bytes,
                current_file=self._current_file,
                transfer_rate=rate
            )
        
        # Parse summary statistics
        elif 'Number of files:' in line:
            # Example: "Number of files: 1,234 (reg: 1,000, dir: 234)"
            files_match = re.search(r'Number of files:\s*(\d+(?:,\d+)*)', line)
            if files_match:
                self._total_files = int(files_match.group(1).replace(',', ''))
                self._update_progress(total_files=self._total_files)
        
        elif 'Total file size:' in line:
            # Example: "Total file size: 12,345,678 bytes"
            size_match = re.search(r'Total file size:\s*(\d+(?:,\d+)*)', line)
            if size_match:
                self._total_bytes = int(size_match.group(1).replace(',', ''))
                self._update_progress(total_bytes=self._total_bytes)
        
        elif 'Total transferred file size:' in line:
            # Example: "Total transferred file size: 12,345,678 bytes"
            transferred_match = re.search(r'Total transferred file size:\s*(\d+(?:,\d+)*)', line)
            if transferred_match:
                final_transferred = int(transferred_match.group(1).replace(',', ''))
                self._update_progress(transferred_bytes=final_transferred)
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file using rsync.
        
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
            # Reset progress counters
            self._total_files = 1
            self._transferred_files = 0
            self._total_bytes = source_path.stat().st_size
            self._transferred_bytes = 0
            self._current_file = str(source)
            
            self._update_progress(
                total_files=self._total_files,
                total_bytes=self._total_bytes,
                current_file=self._current_file
            )
            
            # Build rsync command
            cmd = self._build_rsync_command(str(source), str(destination))
            
            self.logger.info(f"Running rsync command: {' '.join(cmd)}")
            
            # Run rsync
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            # Monitor progress
            while True:
                if self.is_cancelled():
                    process.terminate()
                    await process.wait()
                    raise Exception("Transfer cancelled")
                
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode('utf-8', errors='ignore')
                self._parse_progress_line(line_str)
            
            # Wait for process completion
            await process.wait()
            
            if process.returncode == 0:
                self._transferred_files = 1
                self._update_progress(
                    transferred_files=self._transferred_files,
                    status=TransferStatus.COMPLETED
                )
                
                return TransferResult(
                    success=True,
                    status=TransferStatus.COMPLETED,
                    progress=self._progress,
                    transferred_files=[str(source)],
                    failed_files=[]
                )
            else:
                error_msg = f"Rsync failed with exit code {process.returncode}"
                self._update_progress(status=TransferStatus.FAILED, error_message=error_msg)
                
                return TransferResult(
                    success=False,
                    status=TransferStatus.FAILED,
                    progress=self._progress,
                    transferred_files=[],
                    failed_files=[str(source)],
                    error_message=error_msg
                )
            
        except Exception as e:
            self.logger.error(f"Rsync file transfer failed: {e}")
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
        Transfer a directory using rsync.
        
        Args:
            source: Source directory path
            destination: Destination directory path
            recursive: Whether to transfer subdirectories (always True for rsync)
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
            # Reset progress counters
            self._total_files = 0
            self._transferred_files = 0
            self._total_bytes = 0
            self._transferred_bytes = 0
            self._current_file = ""
            
            # Ensure source path ends with / for directory sync
            source_str = str(source)
            if not source_str.endswith('/'):
                source_str += '/'
            
            # Build rsync command
            cmd = self._build_rsync_command(source_str, str(destination))
            
            self.logger.info(f"Running rsync command: {' '.join(cmd)}")
            
            # Run rsync
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            # Monitor progress
            output_lines = []
            while True:
                if self.is_cancelled():
                    process.terminate()
                    await process.wait()
                    raise Exception("Transfer cancelled")
                
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode('utf-8', errors='ignore')
                output_lines.append(line_str)
                self._parse_progress_line(line_str)
            
            # Wait for process completion
            await process.wait()
            
            if process.returncode == 0:
                self._update_progress(status=TransferStatus.COMPLETED)
                
                # Collect transferred files from output
                transferred_files = []
                for line in output_lines:
                    if line.strip() and not line.startswith(' ') and '/' in line:
                        # This is a rough heuristic to identify file paths
                        file_path = line.strip()
                        if not any(keyword in file_path for keyword in [
                            'Number of files', 'Total file size', 'sent', 'received'
                        ]):
                            transferred_files.append(file_path)
                
                return TransferResult(
                    success=True,
                    status=TransferStatus.COMPLETED,
                    progress=self._progress,
                    transferred_files=transferred_files,
                    failed_files=[]
                )
            else:
                error_msg = f"Rsync failed with exit code {process.returncode}"
                self._update_progress(status=TransferStatus.FAILED, error_message=error_msg)
                
                return TransferResult(
                    success=False,
                    status=TransferStatus.FAILED,
                    progress=self._progress,
                    transferred_files=[],
                    failed_files=[str(source)],
                    error_message=error_msg
                )
            
        except Exception as e:
            self.logger.error(f"Rsync directory transfer failed: {e}")
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
        """Clean up rsync resources."""
        # No persistent connections to clean up
        pass