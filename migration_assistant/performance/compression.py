"""Compression utilities with hybrid Python/Go implementations."""

import asyncio
import gzip
import bz2
import lzma
import zipfile
import tarfile
import logging
import os
import tempfile
import shutil
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import time

from .engine import GoPerformanceEngine

logger = logging.getLogger(__name__)

class CompressionFormat(Enum):
    """Supported compression formats."""
    GZIP = "gzip"
    BZIP2 = "bzip2"
    LZMA = "lzma"
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"

class CompressionLevel(Enum):
    """Compression levels."""
    FASTEST = 1
    FAST = 3
    BALANCED = 6
    BEST = 9

@dataclass
class CompressionResult:
    """Result of compression operation."""
    success: bool
    original_size: int
    compressed_size: int
    compression_ratio: float
    duration_ms: float
    format: CompressionFormat
    method: str  # "python" or "go"
    error: Optional[str] = None

@dataclass
class DecompressionResult:
    """Result of decompression operation."""
    success: bool
    compressed_size: int
    decompressed_size: int
    duration_ms: float
    format: CompressionFormat
    method: str  # "python" or "go"
    error: Optional[str] = None

class HybridCompressor:
    """Hybrid compressor using both Python and Go implementations."""
    
    def __init__(self, go_binary_path: Optional[str] = None, prefer_go: bool = True):
        """Initialize hybrid compressor.
        
        Args:
            go_binary_path: Path to Go binary
            prefer_go: Whether to prefer Go implementation
        """
        self.go_engine = GoPerformanceEngine(go_binary_path)
        self.prefer_go = prefer_go
        
        # Compression format mappings
        self.format_extensions = {
            CompressionFormat.GZIP: ".gz",
            CompressionFormat.BZIP2: ".bz2",
            CompressionFormat.LZMA: ".xz",
            CompressionFormat.ZIP: ".zip",
            CompressionFormat.TAR: ".tar",
            CompressionFormat.TAR_GZ: ".tar.gz",
            CompressionFormat.TAR_BZ2: ".tar.bz2",
            CompressionFormat.TAR_XZ: ".tar.xz"
        }
    
    async def compress_file(
        self,
        source_path: str,
        destination_path: Optional[str] = None,
        format: CompressionFormat = CompressionFormat.GZIP,
        level: CompressionLevel = CompressionLevel.BALANCED,
        use_go: Optional[bool] = None
    ) -> CompressionResult:
        """Compress a file.
        
        Args:
            source_path: Path to source file
            destination_path: Path to destination file (auto-generated if None)
            format: Compression format
            level: Compression level
            use_go: Force Go implementation (None for auto-select)
            
        Returns:
            CompressionResult
        """
        if not os.path.exists(source_path):
            return CompressionResult(
                success=False,
                original_size=0,
                compressed_size=0,
                compression_ratio=0.0,
                duration_ms=0.0,
                format=format,
                method="none",
                error=f"Source file not found: {source_path}"
            )
        
        # Auto-generate destination path if not provided
        if destination_path is None:
            destination_path = source_path + self.format_extensions[format]
        
        # Determine which implementation to use
        use_go_impl = self._should_use_go(use_go)
        
        original_size = os.path.getsize(source_path)
        start_time = time.time()
        
        try:
            if use_go_impl:
                result = await self._compress_with_go(source_path, destination_path, format, level)
                method = "go"
            else:
                result = await self._compress_with_python(source_path, destination_path, format, level)
                method = "python"
            
            duration_ms = (time.time() - start_time) * 1000
            
            if result and os.path.exists(destination_path):
                compressed_size = os.path.getsize(destination_path)
                compression_ratio = compressed_size / original_size if original_size > 0 else 0.0
                
                return CompressionResult(
                    success=True,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    compression_ratio=compression_ratio,
                    duration_ms=duration_ms,
                    format=format,
                    method=method
                )
            else:
                return CompressionResult(
                    success=False,
                    original_size=original_size,
                    compressed_size=0,
                    compression_ratio=0.0,
                    duration_ms=duration_ms,
                    format=format,
                    method=method,
                    error="Compression failed"
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Compression failed: {e}")
            
            return CompressionResult(
                success=False,
                original_size=original_size,
                compressed_size=0,
                compression_ratio=0.0,
                duration_ms=duration_ms,
                format=format,
                method="error",
                error=str(e)
            )
    
    async def compress_directory(
        self,
        source_path: str,
        destination_path: Optional[str] = None,
        format: CompressionFormat = CompressionFormat.TAR_GZ,
        level: CompressionLevel = CompressionLevel.BALANCED,
        use_go: Optional[bool] = None
    ) -> CompressionResult:
        """Compress a directory.
        
        Args:
            source_path: Path to source directory
            destination_path: Path to destination archive
            format: Compression format
            level: Compression level
            use_go: Force Go implementation
            
        Returns:
            CompressionResult
        """
        if not os.path.isdir(source_path):
            return CompressionResult(
                success=False,
                original_size=0,
                compressed_size=0,
                compression_ratio=0.0,
                duration_ms=0.0,
                format=format,
                method="none",
                error=f"Source directory not found: {source_path}"
            )
        
        # Auto-generate destination path if not provided
        if destination_path is None:
            destination_path = source_path.rstrip('/') + self.format_extensions[format]
        
        # Calculate original size
        original_size = await self._calculate_directory_size(source_path)
        
        # Determine which implementation to use
        use_go_impl = self._should_use_go(use_go)
        
        start_time = time.time()
        
        try:
            if use_go_impl:
                result = await self._compress_directory_with_go(source_path, destination_path, format, level)
                method = "go"
            else:
                result = await self._compress_directory_with_python(source_path, destination_path, format, level)
                method = "python"
            
            duration_ms = (time.time() - start_time) * 1000
            
            if result and os.path.exists(destination_path):
                compressed_size = os.path.getsize(destination_path)
                compression_ratio = compressed_size / original_size if original_size > 0 else 0.0
                
                return CompressionResult(
                    success=True,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    compression_ratio=compression_ratio,
                    duration_ms=duration_ms,
                    format=format,
                    method=method
                )
            else:
                return CompressionResult(
                    success=False,
                    original_size=original_size,
                    compressed_size=0,
                    compression_ratio=0.0,
                    duration_ms=duration_ms,
                    format=format,
                    method=method,
                    error="Directory compression failed"
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Directory compression failed: {e}")
            
            return CompressionResult(
                success=False,
                original_size=original_size,
                compressed_size=0,
                compression_ratio=0.0,
                duration_ms=duration_ms,
                format=format,
                method="error",
                error=str(e)
            )
    
    async def decompress_file(
        self,
        source_path: str,
        destination_path: Optional[str] = None,
        format: Optional[CompressionFormat] = None,
        use_go: Optional[bool] = None
    ) -> DecompressionResult:
        """Decompress a file.
        
        Args:
            source_path: Path to compressed file
            destination_path: Path to destination file
            format: Compression format (auto-detect if None)
            use_go: Force Go implementation
            
        Returns:
            DecompressionResult
        """
        if not os.path.exists(source_path):
            return DecompressionResult(
                success=False,
                compressed_size=0,
                decompressed_size=0,
                duration_ms=0.0,
                format=CompressionFormat.GZIP,
                method="none",
                error=f"Source file not found: {source_path}"
            )
        
        # Auto-detect format if not provided
        if format is None:
            format = self._detect_format(source_path)
        
        # Auto-generate destination path if not provided
        if destination_path is None:
            destination_path = self._generate_decompressed_path(source_path, format)
        
        compressed_size = os.path.getsize(source_path)
        use_go_impl = self._should_use_go(use_go)
        
        start_time = time.time()
        
        try:
            if use_go_impl:
                result = await self._decompress_with_go(source_path, destination_path, format)
                method = "go"
            else:
                result = await self._decompress_with_python(source_path, destination_path, format)
                method = "python"
            
            duration_ms = (time.time() - start_time) * 1000
            
            if result and os.path.exists(destination_path):
                decompressed_size = os.path.getsize(destination_path)
                
                return DecompressionResult(
                    success=True,
                    compressed_size=compressed_size,
                    decompressed_size=decompressed_size,
                    duration_ms=duration_ms,
                    format=format,
                    method=method
                )
            else:
                return DecompressionResult(
                    success=False,
                    compressed_size=compressed_size,
                    decompressed_size=0,
                    duration_ms=duration_ms,
                    format=format,
                    method=method,
                    error="Decompression failed"
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Decompression failed: {e}")
            
            return DecompressionResult(
                success=False,
                compressed_size=compressed_size,
                decompressed_size=0,
                duration_ms=duration_ms,
                format=format,
                method="error",
                error=str(e)
            )
    
    def _should_use_go(self, use_go: Optional[bool]) -> bool:
        """Determine whether to use Go implementation."""
        if use_go is not None:
            return use_go and self.go_engine.is_available()
        return self.prefer_go and self.go_engine.is_available()
    
    async def _compress_with_go(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat,
        level: CompressionLevel
    ) -> bool:
        """Compress using Go implementation."""
        try:
            result = await self.go_engine.compress_file(source_path, destination_path)
            return result is not None and result.get("success", False)
        except Exception as e:
            logger.error(f"Go compression failed: {e}")
            return False
    
    async def _compress_with_python(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat,
        level: CompressionLevel
    ) -> bool:
        """Compress using Python implementation."""
        try:
            await asyncio.to_thread(
                self._compress_file_sync,
                source_path,
                destination_path,
                format,
                level
            )
            return True
        except Exception as e:
            logger.error(f"Python compression failed: {e}")
            return False
    
    def _compress_file_sync(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat,
        level: CompressionLevel
    ):
        """Synchronous file compression."""
        level_value = level.value
        
        if format == CompressionFormat.GZIP:
            with open(source_path, 'rb') as f_in:
                with gzip.open(destination_path, 'wb', compresslevel=level_value) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        elif format == CompressionFormat.BZIP2:
            with open(source_path, 'rb') as f_in:
                with bz2.open(destination_path, 'wb', compresslevel=level_value) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        elif format == CompressionFormat.LZMA:
            with open(source_path, 'rb') as f_in:
                with lzma.open(destination_path, 'wb', preset=level_value) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        elif format == CompressionFormat.ZIP:
            with zipfile.ZipFile(destination_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=level_value) as zf:
                zf.write(source_path, os.path.basename(source_path))
        
        else:
            raise ValueError(f"Unsupported format for single file compression: {format}")
    
    async def _compress_directory_with_go(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat,
        level: CompressionLevel
    ) -> bool:
        """Compress directory using Go implementation."""
        try:
            result = await self.go_engine.compress_file(source_path, destination_path)
            return result is not None and result.get("success", False)
        except Exception as e:
            logger.error(f"Go directory compression failed: {e}")
            return False
    
    async def _compress_directory_with_python(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat,
        level: CompressionLevel
    ) -> bool:
        """Compress directory using Python implementation."""
        try:
            await asyncio.to_thread(
                self._compress_directory_sync,
                source_path,
                destination_path,
                format,
                level
            )
            return True
        except Exception as e:
            logger.error(f"Python directory compression failed: {e}")
            return False
    
    def _compress_directory_sync(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat,
        level: CompressionLevel
    ):
        """Synchronous directory compression."""
        level_value = level.value
        
        if format == CompressionFormat.ZIP:
            with zipfile.ZipFile(destination_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=level_value) as zf:
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, source_path)
                        zf.write(file_path, arc_path)
        
        elif format in [CompressionFormat.TAR, CompressionFormat.TAR_GZ, 
                       CompressionFormat.TAR_BZ2, CompressionFormat.TAR_XZ]:
            
            mode_map = {
                CompressionFormat.TAR: 'w',
                CompressionFormat.TAR_GZ: 'w:gz',
                CompressionFormat.TAR_BZ2: 'w:bz2',
                CompressionFormat.TAR_XZ: 'w:xz'
            }
            
            mode = mode_map[format]
            
            with tarfile.open(destination_path, mode) as tf:
                tf.add(source_path, arcname=os.path.basename(source_path))
        
        else:
            raise ValueError(f"Unsupported format for directory compression: {format}")
    
    async def _decompress_with_go(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat
    ) -> bool:
        """Decompress using Go implementation."""
        try:
            # Go implementation would handle decompression
            # For now, fall back to Python
            return await self._decompress_with_python(source_path, destination_path, format)
        except Exception as e:
            logger.error(f"Go decompression failed: {e}")
            return False
    
    async def _decompress_with_python(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat
    ) -> bool:
        """Decompress using Python implementation."""
        try:
            await asyncio.to_thread(
                self._decompress_file_sync,
                source_path,
                destination_path,
                format
            )
            return True
        except Exception as e:
            logger.error(f"Python decompression failed: {e}")
            return False
    
    def _decompress_file_sync(
        self,
        source_path: str,
        destination_path: str,
        format: CompressionFormat
    ):
        """Synchronous file decompression."""
        if format == CompressionFormat.GZIP:
            with gzip.open(source_path, 'rb') as f_in:
                with open(destination_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        elif format == CompressionFormat.BZIP2:
            with bz2.open(source_path, 'rb') as f_in:
                with open(destination_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        elif format == CompressionFormat.LZMA:
            with lzma.open(source_path, 'rb') as f_in:
                with open(destination_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        elif format == CompressionFormat.ZIP:
            with zipfile.ZipFile(source_path, 'r') as zf:
                zf.extractall(os.path.dirname(destination_path))
        
        elif format in [CompressionFormat.TAR, CompressionFormat.TAR_GZ,
                       CompressionFormat.TAR_BZ2, CompressionFormat.TAR_XZ]:
            
            mode_map = {
                CompressionFormat.TAR: 'r',
                CompressionFormat.TAR_GZ: 'r:gz',
                CompressionFormat.TAR_BZ2: 'r:bz2',
                CompressionFormat.TAR_XZ: 'r:xz'
            }
            
            mode = mode_map[format]
            
            with tarfile.open(source_path, mode) as tf:
                tf.extractall(os.path.dirname(destination_path))
        
        else:
            raise ValueError(f"Unsupported format for decompression: {format}")
    
    def _detect_format(self, file_path: str) -> CompressionFormat:
        """Detect compression format from file extension."""
        file_path_lower = file_path.lower()
        
        if file_path_lower.endswith('.tar.gz') or file_path_lower.endswith('.tgz'):
            return CompressionFormat.TAR_GZ
        elif file_path_lower.endswith('.tar.bz2') or file_path_lower.endswith('.tbz2'):
            return CompressionFormat.TAR_BZ2
        elif file_path_lower.endswith('.tar.xz') or file_path_lower.endswith('.txz'):
            return CompressionFormat.TAR_XZ
        elif file_path_lower.endswith('.tar'):
            return CompressionFormat.TAR
        elif file_path_lower.endswith('.gz'):
            return CompressionFormat.GZIP
        elif file_path_lower.endswith('.bz2'):
            return CompressionFormat.BZIP2
        elif file_path_lower.endswith('.xz'):
            return CompressionFormat.LZMA
        elif file_path_lower.endswith('.zip'):
            return CompressionFormat.ZIP
        else:
            # Default to gzip
            return CompressionFormat.GZIP
    
    def _generate_decompressed_path(self, compressed_path: str, format: CompressionFormat) -> str:
        """Generate decompressed file path."""
        extension = self.format_extensions[format]
        
        if compressed_path.endswith(extension):
            return compressed_path[:-len(extension)]
        else:
            # Add .decompressed suffix
            return compressed_path + ".decompressed"
    
    async def _calculate_directory_size(self, directory_path: str) -> int:
        """Calculate total size of directory."""
        def _calc_size():
            total_size = 0
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, IOError):
                        pass  # Skip files that can't be accessed
            return total_size
        
        return await asyncio.to_thread(_calc_size)
    
    async def benchmark_compression(
        self,
        test_file: str,
        formats: Optional[List[CompressionFormat]] = None,
        levels: Optional[List[CompressionLevel]] = None,
        iterations: int = 3
    ) -> Dict[str, Any]:
        """Benchmark compression performance.
        
        Args:
            test_file: Path to test file
            formats: Compression formats to test
            levels: Compression levels to test
            iterations: Number of iterations per test
            
        Returns:
            Benchmark results
        """
        if formats is None:
            formats = [CompressionFormat.GZIP, CompressionFormat.BZIP2, CompressionFormat.LZMA]
        
        if levels is None:
            levels = [CompressionLevel.FASTEST, CompressionLevel.BALANCED, CompressionLevel.BEST]
        
        results = {
            'test_file': test_file,
            'original_size': os.path.getsize(test_file) if os.path.exists(test_file) else 0,
            'results': {}
        }
        
        for format in formats:
            results['results'][format.value] = {}
            
            for level in levels:
                level_results = []
                
                for i in range(iterations):
                    # Test with Python
                    with tempfile.NamedTemporaryFile(suffix=self.format_extensions[format], delete=False) as tmp:
                        tmp_path = tmp.name
                    
                    try:
                        python_result = await self.compress_file(
                            test_file, tmp_path, format, level, use_go=False
                        )
                        level_results.append({
                            'iteration': i + 1,
                            'method': 'python',
                            'result': python_result
                        })
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    
                    # Test with Go if available
                    if self.go_engine.is_available():
                        with tempfile.NamedTemporaryFile(suffix=self.format_extensions[format], delete=False) as tmp:
                            tmp_path = tmp.name
                        
                        try:
                            go_result = await self.compress_file(
                                test_file, tmp_path, format, level, use_go=True
                            )
                            level_results.append({
                                'iteration': i + 1,
                                'method': 'go',
                                'result': go_result
                            })
                        finally:
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                
                results['results'][format.value][level.value] = level_results
        
        return results