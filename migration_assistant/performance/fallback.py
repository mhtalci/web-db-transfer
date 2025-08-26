"""
Python Fallback Engine - Pure Python implementations for when Go binary is unavailable.
"""

import asyncio
import hashlib
import logging
import os
import shutil
import time
import psutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .engine import CopyResult, ChecksumResult, SystemStats

logger = logging.getLogger(__name__)


class PythonFallbackEngine:
    """
    Pure Python implementation of performance operations.
    
    This class provides fallback implementations when the Go binary
    is not available, using standard Python libraries and psutil.
    """
    
    def __init__(self):
        """Initialize the Python Fallback Engine."""
        self.available = True
        logger.info("Using Python fallback engine for performance operations")
    
    async def copy_file(self, source: str, destination: str) -> Optional[CopyResult]:
        """
        Copy a file using Python's shutil with checksum calculation.
        
        Args:
            source: Source file path
            destination: Destination file path
            
        Returns:
            CopyResult with copy statistics or None if failed
        """
        try:
            start_time = time.time()
            
            # Ensure destination directory exists
            dest_dir = os.path.dirname(destination)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            
            # Get source file size
            source_size = os.path.getsize(source)
            
            # Copy file and calculate checksum
            hasher = hashlib.sha256()
            bytes_copied = 0
            
            with open(source, 'rb') as src, open(destination, 'wb') as dst:
                while True:
                    chunk = src.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    
                    dst.write(chunk)
                    hasher.update(chunk)
                    bytes_copied += len(chunk)
                    
                    # Yield control to allow other async operations
                    if bytes_copied % (10 * 1024 * 1024) == 0:  # Every 10MB
                        await asyncio.sleep(0)
            
            # Copy file permissions
            shutil.copystat(source, destination)
            
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Calculate transfer rate in MB/s
            transfer_rate_mbps = (bytes_copied / (1024 * 1024)) / (duration_ms / 1000) if duration_ms > 0 else 0
            
            return CopyResult(
                bytes_copied=bytes_copied,
                duration_ms=duration_ms,
                checksum=hasher.hexdigest(),
                transfer_rate_mbps=transfer_rate_mbps,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Python file copy failed: {e}")
            return None
    
    async def calculate_checksums(self, files: List[str]) -> Optional[List[ChecksumResult]]:
        """
        Calculate checksums for multiple files using Python.
        
        Args:
            files: List of file paths
            
        Returns:
            List of ChecksumResult objects or None if failed
        """
        results = []
        
        for file_path in files:
            try:
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Calculate multiple hashes in one pass
                md5_hasher = hashlib.md5()
                sha1_hasher = hashlib.sha1()
                sha256_hasher = hashlib.sha256()
                
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        
                        md5_hasher.update(chunk)
                        sha1_hasher.update(chunk)
                        sha256_hasher.update(chunk)
                        
                        # Yield control periodically
                        await asyncio.sleep(0)
                
                results.append(ChecksumResult(
                    file=file_path,
                    md5=md5_hasher.hexdigest(),
                    sha1=sha1_hasher.hexdigest(),
                    sha256=sha256_hasher.hexdigest(),
                    size=file_size
                ))
                
            except Exception as e:
                logger.error(f"Failed to calculate checksum for {file_path}: {e}")
                results.append(ChecksumResult(
                    file=file_path,
                    md5="",
                    sha1="",
                    sha256="",
                    size=0,
                    error=str(e)
                ))
        
        return results
    
    async def compress_file(self, source: str, destination: str) -> Optional[Dict[str, Any]]:
        """
        Compress a file using Python's gzip module.
        
        Args:
            source: Source file or directory path
            destination: Destination compressed file path
            
        Returns:
            Compression result dictionary or None if failed
        """
        try:
            import gzip
            import tarfile
            
            start_time = time.time()
            original_size = 0
            
            if os.path.isfile(source):
                # Single file compression
                original_size = os.path.getsize(source)
                
                with open(source, 'rb') as src, gzip.open(destination, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                    
            elif os.path.isdir(source):
                # Directory compression using tar.gz
                with tarfile.open(destination, 'w:gz') as tar:
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, source)
                            tar.add(file_path, arcname=arcname)
                            original_size += os.path.getsize(file_path)
                            
                            # Yield control periodically
                            await asyncio.sleep(0)
            else:
                raise FileNotFoundError(f"Source path does not exist: {source}")
            
            compressed_size = os.path.getsize(destination)
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            compression_ratio = compressed_size / original_size if original_size > 0 else 0
            
            return {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "duration_ms": duration_ms,
                "method": "gzip" if os.path.isfile(source) else "tar.gz",
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Python compression failed: {e}")
            return None
    
    async def get_system_stats(self) -> Optional[SystemStats]:
        """
        Get system statistics using psutil.
        
        Returns:
            SystemStats object or None if failed
        """
        try:
            # CPU stats
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory stats
            memory = psutil.virtual_memory()
            
            # Disk stats
            disk_partitions = psutil.disk_partitions()
            disk_stats = []
            
            for partition in disk_partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_stats.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": usage.total,
                        "free": usage.free,
                        "used": usage.used,
                        "used_percent": (usage.used / usage.total) * 100 if usage.total > 0 else 0
                    })
                except (PermissionError, OSError):
                    # Skip partitions we can't access
                    continue
            
            # Network stats
            network = psutil.net_io_counters()
            
            return SystemStats(
                timestamp=datetime.now(),
                cpu={
                    "usage_percent": cpu_percent,
                    "count": cpu_count,
                    "frequency_mhz": cpu_freq.current if cpu_freq else 0
                },
                memory={
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "used_percent": memory.percent,
                    "free": memory.free
                },
                disk=disk_stats,
                network={
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                go_runtime={
                    "python_version": f"{psutil.__version__}",
                    "process_count": len(psutil.pids()),
                    "boot_time": psutil.boot_time()
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return None
    
    async def transfer_files(self, source: str, destination: str, method: str = "copy") -> Optional[Dict[str, Any]]:
        """
        Transfer files using Python file operations.
        
        Args:
            source: Source path
            destination: Destination path
            method: Transfer method (ignored, always uses copy)
            
        Returns:
            Transfer result dictionary or None if failed
        """
        if os.path.isfile(source):
            # Single file transfer
            result = await self.copy_file(source, destination)
            if result:
                return {
                    "bytes_transferred": result.bytes_copied,
                    "duration_ms": result.duration_ms,
                    "transfer_rate_mbps": result.transfer_rate_mbps,
                    "method": "python_copy",
                    "success": result.success
                }
        elif os.path.isdir(source):
            # Directory transfer
            try:
                start_time = time.time()
                
                # Use shutil.copytree for directory copying
                if os.path.exists(destination):
                    shutil.rmtree(destination)
                
                shutil.copytree(source, destination)
                
                # Calculate total size
                total_size = 0
                for root, dirs, files in os.walk(destination):
                    for file in files:
                        total_size += os.path.getsize(os.path.join(root, file))
                        await asyncio.sleep(0)  # Yield control
                
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                transfer_rate_mbps = (total_size / (1024 * 1024)) / (duration_ms / 1000) if duration_ms > 0 else 0
                
                return {
                    "bytes_transferred": total_size,
                    "duration_ms": duration_ms,
                    "transfer_rate_mbps": transfer_rate_mbps,
                    "method": "python_copytree",
                    "success": True
                }
                
            except Exception as e:
                logger.error(f"Directory transfer failed: {e}")
                return None
        
        return None
    
    def is_available(self) -> bool:
        """Check if the Python fallback engine is available."""
        return self.available