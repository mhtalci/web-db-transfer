"""
Go Performance Engine - Python wrapper for Go binary operations.
"""

import asyncio
import json
import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PerformanceResult:
    """Result from a performance operation."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    operation: Optional[str] = None


@dataclass
class CopyResult:
    """Result from a file copy operation."""
    bytes_copied: int
    duration_ms: float
    checksum: str
    transfer_rate_mbps: float
    success: bool


@dataclass
class ChecksumResult:
    """Result from a checksum calculation."""
    file: str
    md5: str
    sha1: str
    sha256: str
    size: int
    error: Optional[str] = None


@dataclass
class SystemStats:
    """System statistics from monitoring."""
    timestamp: datetime
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    disk: List[Dict[str, Any]]
    network: Dict[str, Any]
    go_runtime: Dict[str, Any]


class GoPerformanceEngine:
    """
    Python wrapper for Go-based high-performance operations.
    
    This class provides async interfaces to the Go binary for:
    - High-speed file copying
    - Parallel checksum calculation
    - File compression/decompression
    - System monitoring
    - Network transfer operations
    """
    
    def __init__(self, go_binary_path: Optional[str] = None):
        """
        Initialize the Go Performance Engine.
        
        Args:
            go_binary_path: Path to the Go binary. If None, will search for it.
        """
        self.go_binary_path = go_binary_path or self._find_go_binary()
        self.available = self._check_availability()
        
        if not self.available:
            logger.warning("Go binary not available, performance operations will be limited")
    
    def _find_go_binary(self) -> Optional[str]:
        """Find the Go binary in common locations."""
        possible_paths = [
            "go-engine/bin/migration-engine",
            "./go-engine/bin/migration-engine",
            "../go-engine/bin/migration-engine",
            "bin/migration-engine",
            "./bin/migration-engine",
        ]
        
        for path in possible_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return os.path.abspath(path)
        
        # Try to find in PATH
        binary_name = "migration-engine"
        if shutil.which(binary_name):
            return binary_name
            
        return None
    
    def _check_availability(self) -> bool:
        """Check if the Go binary is available and working."""
        if not self.go_binary_path:
            return False
            
        try:
            result = subprocess.run(
                [self.go_binary_path, "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return False
    
    async def _execute_command(self, command: List[str]) -> PerformanceResult:
        """
        Execute a Go binary command asynchronously.
        
        Args:
            command: Command arguments to pass to the Go binary
            
        Returns:
            PerformanceResult with the operation result
        """
        if not self.available:
            return PerformanceResult(
                success=False,
                error="Go binary not available"
            )
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Create the full command
            full_command = [self.go_binary_path] + command
            
            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Go command failed: {error_msg}")
                return PerformanceResult(
                    success=False,
                    error=error_msg,
                    duration_ms=duration_ms,
                    operation=" ".join(command)
                )
            
            # Parse JSON response
            try:
                response = json.loads(stdout.decode())
                return PerformanceResult(
                    success=response.get("success", False),
                    data=response.get("data"),
                    error=response.get("error"),
                    duration_ms=duration_ms,
                    operation=" ".join(command)
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Go response: {e}")
                return PerformanceResult(
                    success=False,
                    error=f"Failed to parse response: {e}",
                    duration_ms=duration_ms,
                    operation=" ".join(command)
                )
                
        except asyncio.TimeoutError:
            return PerformanceResult(
                success=False,
                error="Command timed out",
                duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                operation=" ".join(command)
            )
        except Exception as e:
            logger.error(f"Failed to execute Go command: {e}")
            return PerformanceResult(
                success=False,
                error=str(e),
                duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                operation=" ".join(command)
            )
    
    async def copy_file(self, source: str, destination: str) -> Optional[CopyResult]:
        """
        High-speed file copying using Go binary.
        
        Args:
            source: Source file path
            destination: Destination file path
            
        Returns:
            CopyResult with copy statistics or None if failed
        """
        command = ["copy", "--source", source, "--destination", destination]
        result = await self._execute_command(command)
        
        if not result.success or not result.data:
            logger.error(f"File copy failed: {result.error}")
            return None
        
        data = result.data
        return CopyResult(
            bytes_copied=data.get("bytes_copied", 0),
            duration_ms=data.get("duration_ms", 0),
            checksum=data.get("checksum", ""),
            transfer_rate_mbps=data.get("transfer_rate_mbps", 0.0),
            success=data.get("success", False)
        )
    
    async def calculate_checksums(self, files: List[str]) -> Optional[List[ChecksumResult]]:
        """
        Calculate checksums for multiple files in parallel.
        
        Args:
            files: List of file paths
            
        Returns:
            List of ChecksumResult objects or None if failed
        """
        command = ["checksum", "--files"] + files
        result = await self._execute_command(command)
        
        if not result.success or not result.data:
            logger.error(f"Checksum calculation failed: {result.error}")
            return None
        
        results = []
        for item in result.data.get("results", []):
            results.append(ChecksumResult(
                file=item.get("file", ""),
                md5=item.get("md5", ""),
                sha1=item.get("sha1", ""),
                sha256=item.get("sha256", ""),
                size=item.get("size", 0),
                error=item.get("error")
            ))
        
        return results
    
    async def compress_file(self, source: str, destination: str) -> Optional[Dict[str, Any]]:
        """
        Compress a file or directory using Go binary.
        
        Args:
            source: Source file or directory path
            destination: Destination compressed file path
            
        Returns:
            Compression result dictionary or None if failed
        """
        command = ["compress", "--source", source, "--destination", destination]
        result = await self._execute_command(command)
        
        if not result.success or not result.data:
            logger.error(f"Compression failed: {result.error}")
            return None
        
        return result.data
    
    async def get_system_stats(self) -> Optional[SystemStats]:
        """
        Get comprehensive system statistics.
        
        Returns:
            SystemStats object or None if failed
        """
        command = ["monitor"]
        result = await self._execute_command(command)
        
        if not result.success or not result.data:
            logger.error(f"System monitoring failed: {result.error}")
            return None
        
        data = result.data
        return SystemStats(
            timestamp=datetime.fromisoformat(data.get("timestamp", "").replace("Z", "+00:00")),
            cpu=data.get("cpu", {}),
            memory=data.get("memory", {}),
            disk=data.get("disk", []),
            network=data.get("network", {}),
            go_runtime=data.get("go_runtime", {})
        )
    
    async def transfer_files(self, source: str, destination: str, method: str = "concurrent") -> Optional[Dict[str, Any]]:
        """
        Transfer files using high-performance network operations.
        
        Args:
            source: Source path or URL
            destination: Destination path
            method: Transfer method (concurrent, chunked, http)
            
        Returns:
            Transfer result dictionary or None if failed
        """
        command = ["transfer", "--source", source, "--destination", destination, "--method", method]
        result = await self._execute_command(command)
        
        if not result.success or not result.data:
            logger.error(f"File transfer failed: {result.error}")
            return None
        
        return result.data
    
    def is_available(self) -> bool:
        """Check if the Go binary is available."""
        return self.available
    
    def get_binary_path(self) -> Optional[str]:
        """Get the path to the Go binary."""
        return self.go_binary_path
    
    async def benchmark_operation(self, operation: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Benchmark a specific operation.
        
        Args:
            operation: Operation name (copy, checksum, compress, etc.)
            *args, **kwargs: Operation arguments
            
        Returns:
            Benchmark results including timing and performance metrics
        """
        iterations = kwargs.pop('iterations', 1)
        results = []
        
        for i in range(iterations):
            start_time = asyncio.get_event_loop().time()
            
            if operation == "copy":
                result = await self.copy_file(*args, **kwargs)
            elif operation == "checksum":
                result = await self.calculate_checksums(*args, **kwargs)
            elif operation == "compress":
                result = await self.compress_file(*args, **kwargs)
            elif operation == "monitor":
                result = await self.get_system_stats()
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            end_time = asyncio.get_event_loop().time()
            duration = (end_time - start_time) * 1000  # Convert to milliseconds
            
            results.append({
                "iteration": i + 1,
                "duration_ms": duration,
                "success": result is not None,
                "result": result
            })
        
        # Calculate statistics
        durations = [r["duration_ms"] for r in results if r["success"]]
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "operation": operation,
            "iterations": iterations,
            "success_count": success_count,
            "success_rate": success_count / iterations * 100,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "results": results
        }