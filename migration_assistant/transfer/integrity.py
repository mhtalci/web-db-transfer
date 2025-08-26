"""
File integrity verification for transfer operations.

This module provides checksum validation and file comparison capabilities
to ensure data integrity during file transfers.
"""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class FileChecksum:
    """Checksum information for a file."""
    file_path: str
    size: int
    md5: Optional[str] = None
    sha1: Optional[str] = None
    sha256: Optional[str] = None
    modified_time: Optional[float] = None


@dataclass
class IntegrityResult:
    """Result of integrity verification."""
    success: bool
    total_files: int
    verified_files: int
    failed_files: List[str]
    mismatched_files: List[str]
    missing_files: List[str]
    error_message: Optional[str] = None
    checksums: Dict[str, FileChecksum] = None
    
    def __post_init__(self):
        if self.checksums is None:
            self.checksums = {}


class IntegrityVerifier:
    """
    File integrity verification using checksums and file comparison.
    
    This class provides methods to calculate checksums, compare files,
    and verify transfer integrity with progress reporting.
    """
    
    SUPPORTED_ALGORITHMS = ['md5', 'sha1', 'sha256']
    DEFAULT_CHUNK_SIZE = 8192  # 8KB chunks for file reading
    
    def __init__(self, algorithms: Optional[List[str]] = None, chunk_size: int = DEFAULT_CHUNK_SIZE):
        """
        Initialize the integrity verifier.
        
        Args:
            algorithms: List of hash algorithms to use (default: ['md5', 'sha256'])
            chunk_size: Size of chunks to read when calculating checksums
        """
        self.algorithms = algorithms or ['md5', 'sha256']
        self.chunk_size = chunk_size
        self._progress_callback: Optional[Callable[[int, int], None]] = None
        self._cancel_event = asyncio.Event()
        
        # Validate algorithms
        for algo in self.algorithms:
            if algo not in self.SUPPORTED_ALGORITHMS:
                raise ValueError(f"Unsupported algorithm: {algo}")
    
    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """
        Set a callback function to receive progress updates.
        
        Args:
            callback: Function that will be called with (processed_files, total_files)
        """
        self._progress_callback = callback
    
    async def cancel(self) -> None:
        """Cancel the ongoing verification operation."""
        logger.info("Integrity verification cancellation requested")
        self._cancel_event.set()
    
    def is_cancelled(self) -> bool:
        """Check if the verification has been cancelled."""
        return self._cancel_event.is_set()
    
    def _calculate_file_checksum(self, file_path: Union[str, Path]) -> FileChecksum:
        """
        Calculate checksums for a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileChecksum object with calculated hashes
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Initialize hash objects
        hash_objects = {}
        for algo in self.algorithms:
            hash_objects[algo] = hashlib.new(algo)
        
        file_size = file_path.stat().st_size
        modified_time = file_path.stat().st_mtime
        
        try:
            with open(file_path, 'rb') as f:
                while True:
                    if self.is_cancelled():
                        raise asyncio.CancelledError("Checksum calculation cancelled")
                    
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    for hash_obj in hash_objects.values():
                        hash_obj.update(chunk)
            
            # Create checksum result
            checksum = FileChecksum(
                file_path=str(file_path),
                size=file_size,
                modified_time=modified_time
            )
            
            # Set calculated hashes
            for algo, hash_obj in hash_objects.items():
                setattr(checksum, algo, hash_obj.hexdigest())
            
            return checksum
            
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            raise
    
    async def calculate_checksum(self, file_path: Union[str, Path]) -> FileChecksum:
        """
        Asynchronously calculate checksums for a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileChecksum object with calculated hashes
        """
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(
                executor, 
                self._calculate_file_checksum, 
                file_path
            )
    
    async def calculate_directory_checksums(
        self, 
        directory: Union[str, Path],
        recursive: bool = True,
        pattern: str = "*"
    ) -> Dict[str, FileChecksum]:
        """
        Calculate checksums for all files in a directory.
        
        Args:
            directory: Directory path
            recursive: Whether to process subdirectories
            pattern: File pattern to match (glob pattern)
            
        Returns:
            Dictionary mapping file paths to FileChecksum objects
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        # Find all files
        if recursive:
            files = list(directory.rglob(pattern))
        else:
            files = list(directory.glob(pattern))
        
        # Filter to only files
        files = [f for f in files if f.is_file()]
        
        checksums = {}
        total_files = len(files)
        
        logger.info(f"Calculating checksums for {total_files} files in {directory}")
        
        # Process files with progress reporting
        for i, file_path in enumerate(files):
            if self.is_cancelled():
                logger.info("Checksum calculation cancelled")
                break
            
            try:
                checksum = await self.calculate_checksum(file_path)
                checksums[str(file_path)] = checksum
                
                if self._progress_callback:
                    self._progress_callback(i + 1, total_files)
                    
            except Exception as e:
                logger.error(f"Failed to calculate checksum for {file_path}: {e}")
                continue
        
        logger.info(f"Calculated checksums for {len(checksums)} files")
        return checksums
    
    async def compare_files(
        self, 
        source_file: Union[str, Path], 
        destination_file: Union[str, Path]
    ) -> bool:
        """
        Compare two files using checksums.
        
        Args:
            source_file: Source file path
            destination_file: Destination file path
            
        Returns:
            True if files are identical, False otherwise
        """
        try:
            source_checksum = await self.calculate_checksum(source_file)
            dest_checksum = await self.calculate_checksum(destination_file)
            
            # Compare file sizes first (quick check)
            if source_checksum.size != dest_checksum.size:
                return False
            
            # Compare checksums
            for algo in self.algorithms:
                source_hash = getattr(source_checksum, algo)
                dest_hash = getattr(dest_checksum, algo)
                if source_hash != dest_hash:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to compare files {source_file} and {destination_file}: {e}")
            return False
    
    async def verify_transfer(
        self,
        source_checksums: Dict[str, FileChecksum],
        destination_directory: Union[str, Path],
        preserve_structure: bool = True
    ) -> IntegrityResult:
        """
        Verify transfer integrity by comparing source checksums with destination files.
        
        Args:
            source_checksums: Dictionary of source file checksums
            destination_directory: Destination directory to verify
            preserve_structure: Whether directory structure is preserved
            
        Returns:
            IntegrityResult with verification details
        """
        destination_directory = Path(destination_directory)
        
        if not destination_directory.exists():
            return IntegrityResult(
                success=False,
                total_files=len(source_checksums),
                verified_files=0,
                failed_files=[],
                mismatched_files=[],
                missing_files=list(source_checksums.keys()),
                error_message="Destination directory does not exist"
            )
        
        verified_files = 0
        failed_files = []
        mismatched_files = []
        missing_files = []
        destination_checksums = {}
        
        total_files = len(source_checksums)
        logger.info(f"Verifying transfer integrity for {total_files} files")
        
        for i, (source_path, source_checksum) in enumerate(source_checksums.items()):
            if self.is_cancelled():
                logger.info("Transfer verification cancelled")
                break
            
            # Determine destination file path
            if preserve_structure:
                # Preserve relative path structure
                source_path_obj = Path(source_path)
                relative_path = source_path_obj.name  # Just filename for now
                dest_file = destination_directory / relative_path
            else:
                # Flat structure - just filename
                dest_file = destination_directory / Path(source_path).name
            
            try:
                if not dest_file.exists():
                    missing_files.append(source_path)
                    continue
                
                # Calculate destination checksum
                dest_checksum = await self.calculate_checksum(dest_file)
                destination_checksums[str(dest_file)] = dest_checksum
                
                # Compare checksums
                match = True
                for algo in self.algorithms:
                    source_hash = getattr(source_checksum, algo)
                    dest_hash = getattr(dest_checksum, algo)
                    if source_hash != dest_hash:
                        match = False
                        break
                
                if match and source_checksum.size == dest_checksum.size:
                    verified_files += 1
                else:
                    mismatched_files.append(source_path)
                
                if self._progress_callback:
                    self._progress_callback(i + 1, total_files)
                    
            except Exception as e:
                logger.error(f"Failed to verify file {source_path}: {e}")
                failed_files.append(source_path)
        
        success = (
            len(missing_files) == 0 and 
            len(mismatched_files) == 0 and 
            len(failed_files) == 0
        )
        
        result = IntegrityResult(
            success=success,
            total_files=total_files,
            verified_files=verified_files,
            failed_files=failed_files,
            mismatched_files=mismatched_files,
            missing_files=missing_files,
            checksums=destination_checksums
        )
        
        logger.info(
            f"Transfer verification complete: {verified_files}/{total_files} verified, "
            f"{len(missing_files)} missing, {len(mismatched_files)} mismatched, "
            f"{len(failed_files)} failed"
        )
        
        return result
    
    async def create_checksum_file(
        self, 
        checksums: Dict[str, FileChecksum], 
        output_file: Union[str, Path],
        format_type: str = "md5sum"
    ) -> None:
        """
        Create a checksum file in standard format.
        
        Args:
            checksums: Dictionary of file checksums
            output_file: Output checksum file path
            format_type: Format type ('md5sum', 'sha1sum', 'sha256sum')
        """
        output_file = Path(output_file)
        
        # Determine algorithm from format type
        if format_type == "md5sum":
            algorithm = "md5"
        elif format_type == "sha1sum":
            algorithm = "sha1"
        elif format_type == "sha256sum":
            algorithm = "sha256"
        else:
            raise ValueError(f"Unsupported format type: {format_type}")
        
        if algorithm not in self.algorithms:
            raise ValueError(f"Algorithm {algorithm} not enabled in verifier")
        
        with open(output_file, 'w') as f:
            for file_path, checksum in checksums.items():
                hash_value = getattr(checksum, algorithm)
                f.write(f"{hash_value}  {file_path}\n")
        
        logger.info(f"Created {format_type} checksum file: {output_file}")
    
    async def load_checksum_file(
        self, 
        checksum_file: Union[str, Path],
        format_type: str = "md5sum"
    ) -> Dict[str, str]:
        """
        Load checksums from a standard checksum file.
        
        Args:
            checksum_file: Path to checksum file
            format_type: Format type ('md5sum', 'sha1sum', 'sha256sum')
            
        Returns:
            Dictionary mapping file paths to hash values
        """
        checksum_file = Path(checksum_file)
        
        if not checksum_file.exists():
            raise FileNotFoundError(f"Checksum file not found: {checksum_file}")
        
        checksums = {}
        
        with open(checksum_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Parse line: "hash  filename"
                parts = line.split('  ', 1)
                if len(parts) == 2:
                    hash_value, file_path = parts
                    checksums[file_path] = hash_value
        
        logger.info(f"Loaded {len(checksums)} checksums from {checksum_file}")
        return checksums