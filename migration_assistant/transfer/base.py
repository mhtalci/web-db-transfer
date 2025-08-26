"""
Base classes for file transfer operations.

This module defines the abstract base class and common data structures
for all transfer methods in the Migration Assistant.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
import asyncio
import logging

logger = logging.getLogger(__name__)


class TransferStatus(str, Enum):
    """Status of a transfer operation."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class TransferProgress:
    """Progress information for a transfer operation."""
    total_bytes: int = 0
    transferred_bytes: int = 0
    total_files: int = 0
    transferred_files: int = 0
    current_file: Optional[str] = None
    transfer_rate: float = 0.0  # bytes per second
    eta_seconds: Optional[float] = None
    status: TransferStatus = TransferStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage based on bytes transferred."""
        if self.total_bytes == 0:
            return 0.0
        return min(100.0, (self.transferred_bytes / self.total_bytes) * 100.0)
    
    @property
    def file_progress_percentage(self) -> float:
        """Calculate progress percentage based on files transferred."""
        if self.total_files == 0:
            return 0.0
        return min(100.0, (self.transferred_files / self.total_files) * 100.0)
    
    @property
    def elapsed_time(self) -> Optional[float]:
        """Calculate elapsed time in seconds."""
        if not self.start_time:
            return None
        end_time = self.end_time or datetime.now()
        return (end_time - self.start_time).total_seconds()


@dataclass
class TransferResult:
    """Result of a transfer operation."""
    success: bool
    status: TransferStatus
    progress: TransferProgress
    transferred_files: List[str]
    failed_files: List[str]
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TransferMethod(ABC):
    """
    Abstract base class for all file transfer methods.
    
    This class defines the common interface that all transfer implementations
    must follow, including progress monitoring and cancellation support.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the transfer method with configuration.
        
        Args:
            config: Configuration dictionary specific to the transfer method
        """
        self.config = config
        self._progress_callback: Optional[Callable[[TransferProgress], None]] = None
        self._cancel_event = asyncio.Event()
        self._progress = TransferProgress()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def set_progress_callback(self, callback: Callable[[TransferProgress], None]) -> None:
        """
        Set a callback function to receive progress updates.
        
        Args:
            callback: Function that will be called with TransferProgress updates
        """
        self._progress_callback = callback
    
    def _update_progress(self, **kwargs) -> None:
        """
        Update progress information and notify callback if set.
        
        Args:
            **kwargs: Progress fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self._progress, key):
                setattr(self._progress, key, value)
        
        if self._progress_callback:
            try:
                self._progress_callback(self._progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
    
    async def cancel(self) -> None:
        """Cancel the ongoing transfer operation."""
        self.logger.info("Transfer cancellation requested")
        self._cancel_event.set()
        self._update_progress(status=TransferStatus.CANCELLED)
    
    def is_cancelled(self) -> bool:
        """Check if the transfer has been cancelled."""
        return self._cancel_event.is_set()
    
    @abstractmethod
    async def validate_config(self) -> bool:
        """
        Validate the transfer configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test connectivity to the source/destination.
        
        Returns:
            True if connection is successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file.
        
        Args:
            source: Source file path
            destination: Destination file path
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        pass
    
    @abstractmethod
    async def transfer_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path], 
        recursive: bool = True,
        **kwargs
    ) -> TransferResult:
        """
        Transfer a directory and its contents.
        
        Args:
            source: Source directory path
            destination: Destination directory path
            recursive: Whether to transfer subdirectories
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        pass
    
    async def transfer(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer files or directories with automatic detection.
        
        Args:
            source: Source path (file or directory)
            destination: Destination path
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        source_path = Path(source)
        
        self._update_progress(
            status=TransferStatus.RUNNING,
            start_time=datetime.now()
        )
        
        try:
            if source_path.is_file():
                result = await self.transfer_file(source, destination, **kwargs)
            elif source_path.is_dir():
                result = await self.transfer_directory(source, destination, **kwargs)
            else:
                raise ValueError(f"Source path does not exist or is not accessible: {source}")
            
            self._update_progress(
                status=result.status,
                end_time=datetime.now()
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Transfer failed: {e}")
            self._update_progress(
                status=TransferStatus.FAILED,
                error_message=str(e),
                end_time=datetime.now()
            )
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Clean up resources used by the transfer method.
        """
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()