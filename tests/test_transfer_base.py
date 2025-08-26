"""
Unit tests for transfer base classes.

Tests the abstract base class TransferMethod and related data structures.
"""

import asyncio
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from migration_assistant.transfer.base import (
    TransferMethod,
    TransferResult,
    TransferProgress,
    TransferStatus
)


class MockTransferMethod(TransferMethod):
    """Mock implementation of TransferMethod for testing."""
    
    def __init__(self, config):
        super().__init__(config)
        self.validate_config_result = True
        self.test_connection_result = True
        self.transfer_file_result = None
        self.transfer_directory_result = None
        self.cleanup_called = False
    
    async def validate_config(self) -> bool:
        return self.validate_config_result
    
    async def test_connection(self) -> bool:
        return self.test_connection_result
    
    async def transfer_file(self, source, destination, **kwargs) -> TransferResult:
        if self.transfer_file_result:
            return self.transfer_file_result
        
        return TransferResult(
            success=True,
            status=TransferStatus.COMPLETED,
            progress=self._progress,
            transferred_files=[str(source)],
            failed_files=[]
        )
    
    async def transfer_directory(self, source, destination, recursive=True, **kwargs) -> TransferResult:
        if self.transfer_directory_result:
            return self.transfer_directory_result
        
        return TransferResult(
            success=True,
            status=TransferStatus.COMPLETED,
            progress=self._progress,
            transferred_files=[str(source)],
            failed_files=[]
        )
    
    async def cleanup(self) -> None:
        self.cleanup_called = True


class TestTransferProgress:
    """Test TransferProgress data class."""
    
    def test_progress_percentage_calculation(self):
        """Test progress percentage calculation."""
        progress = TransferProgress(total_bytes=1000, transferred_bytes=250)
        assert progress.progress_percentage == 25.0
        
        # Test edge cases
        progress_zero = TransferProgress(total_bytes=0, transferred_bytes=0)
        assert progress_zero.progress_percentage == 0.0
        
        progress_complete = TransferProgress(total_bytes=100, transferred_bytes=100)
        assert progress_complete.progress_percentage == 100.0
        
        # Test over 100%
        progress_over = TransferProgress(total_bytes=100, transferred_bytes=150)
        assert progress_over.progress_percentage == 100.0
    
    def test_file_progress_percentage_calculation(self):
        """Test file progress percentage calculation."""
        progress = TransferProgress(total_files=10, transferred_files=3)
        assert progress.file_progress_percentage == 30.0
        
        # Test edge cases
        progress_zero = TransferProgress(total_files=0, transferred_files=0)
        assert progress_zero.file_progress_percentage == 0.0
    
    def test_elapsed_time_calculation(self):
        """Test elapsed time calculation."""
        start_time = datetime.now()
        progress = TransferProgress(start_time=start_time)
        
        # Without end time (should use current time)
        elapsed = progress.elapsed_time
        assert elapsed is not None
        assert elapsed >= 0
        
        # With end time
        end_time = datetime.now()
        progress.end_time = end_time
        elapsed = progress.elapsed_time
        assert elapsed is not None
        assert elapsed >= 0
        
        # Without start time
        progress_no_start = TransferProgress()
        assert progress_no_start.elapsed_time is None


class TestTransferResult:
    """Test TransferResult data class."""
    
    def test_initialization(self):
        """Test TransferResult initialization."""
        progress = TransferProgress()
        result = TransferResult(
            success=True,
            status=TransferStatus.COMPLETED,
            progress=progress,
            transferred_files=["file1.txt"],
            failed_files=[]
        )
        
        assert result.success is True
        assert result.status == TransferStatus.COMPLETED
        assert result.progress == progress
        assert result.transferred_files == ["file1.txt"]
        assert result.failed_files == []
        assert result.metadata == {}
    
    def test_metadata_initialization(self):
        """Test metadata is properly initialized."""
        result = TransferResult(
            success=True,
            status=TransferStatus.COMPLETED,
            progress=TransferProgress(),
            transferred_files=[],
            failed_files=[]
        )
        
        assert isinstance(result.metadata, dict)
        assert result.metadata == {}


class TestTransferMethod:
    """Test TransferMethod abstract base class."""
    
    def test_initialization(self):
        """Test TransferMethod initialization."""
        config = {"host": "example.com", "port": 22}
        method = MockTransferMethod(config)
        
        assert method.config == config
        assert method._progress_callback is None
        assert not method.is_cancelled()
        assert isinstance(method._progress, TransferProgress)
    
    def test_progress_callback(self):
        """Test progress callback functionality."""
        method = MockTransferMethod({})
        callback = MagicMock()
        
        method.set_progress_callback(callback)
        assert method._progress_callback == callback
        
        # Test progress update calls callback
        method._update_progress(transferred_bytes=100)
        callback.assert_called_once()
        assert method._progress.transferred_bytes == 100
    
    def test_progress_callback_exception_handling(self):
        """Test progress callback exception handling."""
        method = MockTransferMethod({})
        
        # Callback that raises exception
        def failing_callback(progress):
            raise Exception("Callback failed")
        
        method.set_progress_callback(failing_callback)
        
        # Should not raise exception
        method._update_progress(transferred_bytes=100)
        assert method._progress.transferred_bytes == 100
    
    @pytest.mark.asyncio
    async def test_cancellation(self):
        """Test transfer cancellation."""
        method = MockTransferMethod({})
        
        assert not method.is_cancelled()
        
        await method.cancel()
        
        assert method.is_cancelled()
        assert method._progress.status == TransferStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_transfer_file_success(self):
        """Test successful file transfer."""
        method = MockTransferMethod({})
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()
            
            try:
                result = await method.transfer(temp_file.name, "/tmp/dest.txt")
                
                assert result.success is True
                assert result.status == TransferStatus.COMPLETED
                assert temp_file.name in result.transferred_files
                assert len(result.failed_files) == 0
            finally:
                os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_transfer_directory_success(self):
        """Test successful directory transfer."""
        method = MockTransferMethod({})
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file in the directory
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")
            
            result = await method.transfer(temp_dir, "/tmp/dest_dir")
            
            assert result.success is True
            assert result.status == TransferStatus.COMPLETED
            assert temp_dir in result.transferred_files
            assert len(result.failed_files) == 0
    
    @pytest.mark.asyncio
    async def test_transfer_nonexistent_source(self):
        """Test transfer with nonexistent source."""
        method = MockTransferMethod({})
        
        result = await method.transfer("/nonexistent/path", "/tmp/dest")
        
        assert result.success is False
        assert result.status == TransferStatus.FAILED
        assert "/nonexistent/path" in result.failed_files
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_transfer_with_exception(self):
        """Test transfer when underlying method raises exception."""
        method = MockTransferMethod({})
        
        # Make transfer_file raise an exception
        async def failing_transfer_file(source, destination, **kwargs):
            raise Exception("Transfer failed")
        
        method.transfer_file = failing_transfer_file
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            try:
                result = await method.transfer(temp_file.name, "/tmp/dest.txt")
                
                assert result.success is False
                assert result.status == TransferStatus.FAILED
                assert result.error_message == "Transfer failed"
            finally:
                os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        method = MockTransferMethod({})
        
        async with method as ctx_method:
            assert ctx_method == method
            assert not method.cleanup_called
        
        assert method.cleanup_called
    
    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self):
        """Test async context manager with exception."""
        method = MockTransferMethod({})
        
        try:
            async with method:
                raise Exception("Test exception")
        except Exception:
            pass
        
        assert method.cleanup_called
    
    def test_progress_update(self):
        """Test progress update functionality."""
        method = MockTransferMethod({})
        
        method._update_progress(
            total_bytes=1000,
            transferred_bytes=250,
            status=TransferStatus.RUNNING
        )
        
        assert method._progress.total_bytes == 1000
        assert method._progress.transferred_bytes == 250
        assert method._progress.status == TransferStatus.RUNNING
    
    def test_progress_update_invalid_field(self):
        """Test progress update with invalid field."""
        method = MockTransferMethod({})
        
        # Should not raise exception for invalid fields
        method._update_progress(invalid_field="value")
        
        # Valid fields should still work
        method._update_progress(total_bytes=1000)
        assert method._progress.total_bytes == 1000