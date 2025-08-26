"""
Unit tests for transfer integrity verification.

Tests the IntegrityVerifier class and checksum validation functionality.
"""

import asyncio
import hashlib
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from migration_assistant.transfer.integrity import (
    IntegrityVerifier,
    FileChecksum,
    IntegrityResult
)


class TestFileChecksum:
    """Test FileChecksum data class."""
    
    def test_initialization(self):
        """Test FileChecksum initialization."""
        checksum = FileChecksum(
            file_path="/path/to/file.txt",
            size=1024,
            md5="d41d8cd98f00b204e9800998ecf8427e",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        
        assert checksum.file_path == "/path/to/file.txt"
        assert checksum.size == 1024
        assert checksum.md5 == "d41d8cd98f00b204e9800998ecf8427e"
        assert checksum.sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert checksum.sha1 is None
        assert checksum.modified_time is None


class TestIntegrityResult:
    """Test IntegrityResult data class."""
    
    def test_initialization(self):
        """Test IntegrityResult initialization."""
        result = IntegrityResult(
            success=True,
            total_files=10,
            verified_files=8,
            failed_files=["file1.txt"],
            mismatched_files=["file2.txt"],
            missing_files=[]
        )
        
        assert result.success is True
        assert result.total_files == 10
        assert result.verified_files == 8
        assert result.failed_files == ["file1.txt"]
        assert result.mismatched_files == ["file2.txt"]
        assert result.missing_files == []
        assert result.error_message is None
        assert isinstance(result.checksums, dict)


class TestIntegrityVerifier:
    """Test IntegrityVerifier class."""
    
    def test_initialization_default(self):
        """Test IntegrityVerifier initialization with defaults."""
        verifier = IntegrityVerifier()
        
        assert verifier.algorithms == ['md5', 'sha256']
        assert verifier.chunk_size == IntegrityVerifier.DEFAULT_CHUNK_SIZE
        assert verifier._progress_callback is None
        assert not verifier.is_cancelled()
    
    def test_initialization_custom(self):
        """Test IntegrityVerifier initialization with custom parameters."""
        algorithms = ['sha1', 'sha256']
        chunk_size = 4096
        
        verifier = IntegrityVerifier(algorithms=algorithms, chunk_size=chunk_size)
        
        assert verifier.algorithms == algorithms
        assert verifier.chunk_size == chunk_size
    
    def test_initialization_invalid_algorithm(self):
        """Test IntegrityVerifier initialization with invalid algorithm."""
        with pytest.raises(ValueError) as exc_info:
            IntegrityVerifier(algorithms=['invalid'])
        
        assert "Unsupported algorithm: invalid" in str(exc_info.value)
    
    def test_progress_callback(self):
        """Test progress callback functionality."""
        verifier = IntegrityVerifier()
        callback = MagicMock()
        
        verifier.set_progress_callback(callback)
        assert verifier._progress_callback == callback
    
    @pytest.mark.asyncio
    async def test_cancellation(self):
        """Test verification cancellation."""
        verifier = IntegrityVerifier()
        
        assert not verifier.is_cancelled()
        
        await verifier.cancel()
        
        assert verifier.is_cancelled()
    
    def test_calculate_file_checksum_success(self):
        """Test successful file checksum calculation."""
        verifier = IntegrityVerifier(algorithms=['md5', 'sha256'])
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = b"test content for checksum"
            temp_file.write(content)
            temp_file.flush()
            
            try:
                checksum = verifier._calculate_file_checksum(temp_file.name)
                
                assert checksum.file_path == temp_file.name
                assert checksum.size == len(content)
                assert checksum.md5 is not None
                assert checksum.sha256 is not None
                assert checksum.modified_time is not None
                
                # Verify checksums are correct
                expected_md5 = hashlib.md5(content).hexdigest()
                expected_sha256 = hashlib.sha256(content).hexdigest()
                
                assert checksum.md5 == expected_md5
                assert checksum.sha256 == expected_sha256
                
            finally:
                os.unlink(temp_file.name)
    
    def test_calculate_file_checksum_nonexistent(self):
        """Test checksum calculation for nonexistent file."""
        verifier = IntegrityVerifier()
        
        with pytest.raises(FileNotFoundError):
            verifier._calculate_file_checksum("/nonexistent/file.txt")
    
    def test_calculate_file_checksum_directory(self):
        """Test checksum calculation for directory."""
        verifier = IntegrityVerifier()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError) as exc_info:
                verifier._calculate_file_checksum(temp_dir)
            
            assert "Path is not a file" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_calculate_checksum_async(self):
        """Test async checksum calculation."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = b"async test content"
            temp_file.write(content)
            temp_file.flush()
            
            try:
                checksum = await verifier.calculate_checksum(temp_file.name)
                
                assert checksum.file_path == temp_file.name
                assert checksum.size == len(content)
                assert checksum.md5 == hashlib.md5(content).hexdigest()
                
            finally:
                os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_calculate_directory_checksums(self):
        """Test directory checksum calculation."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            file1 = temp_path / "file1.txt"
            file2 = temp_path / "file2.txt"
            subdir = temp_path / "subdir"
            subdir.mkdir()
            file3 = subdir / "file3.txt"
            
            file1.write_text("content1")
            file2.write_text("content2")
            file3.write_text("content3")
            
            # Test recursive
            checksums = await verifier.calculate_directory_checksums(temp_dir, recursive=True)
            
            assert len(checksums) == 3
            assert str(file1) in checksums
            assert str(file2) in checksums
            assert str(file3) in checksums
            
            # Test non-recursive
            checksums_flat = await verifier.calculate_directory_checksums(temp_dir, recursive=False)
            
            assert len(checksums_flat) == 2
            assert str(file1) in checksums_flat
            assert str(file2) in checksums_flat
            assert str(file3) not in checksums_flat
    
    @pytest.mark.asyncio
    async def test_calculate_directory_checksums_nonexistent(self):
        """Test directory checksum calculation for nonexistent directory."""
        verifier = IntegrityVerifier()
        
        with pytest.raises(FileNotFoundError):
            await verifier.calculate_directory_checksums("/nonexistent/directory")
    
    @pytest.mark.asyncio
    async def test_calculate_directory_checksums_not_directory(self):
        """Test directory checksum calculation for non-directory."""
        verifier = IntegrityVerifier()
        
        with tempfile.NamedTemporaryFile() as temp_file:
            with pytest.raises(ValueError) as exc_info:
                await verifier.calculate_directory_checksums(temp_file.name)
            
            assert "Path is not a directory" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_calculate_directory_checksums_with_progress(self):
        """Test directory checksum calculation with progress callback."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        progress_calls = []
        
        def progress_callback(processed, total):
            progress_calls.append((processed, total))
        
        verifier.set_progress_callback(progress_callback)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            for i in range(3):
                file_path = temp_path / f"file{i}.txt"
                file_path.write_text(f"content{i}")
            
            checksums = await verifier.calculate_directory_checksums(temp_dir)
            
            assert len(checksums) == 3
            assert len(progress_calls) == 3
            assert progress_calls[-1] == (3, 3)  # Final call should be (3, 3)
    
    @pytest.mark.asyncio
    async def test_compare_files_identical(self):
        """Test comparing identical files."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        content = b"identical content"
        
        with tempfile.NamedTemporaryFile(delete=False) as file1:
            file1.write(content)
            file1.flush()
            
            with tempfile.NamedTemporaryFile(delete=False) as file2:
                file2.write(content)
                file2.flush()
                
                try:
                    result = await verifier.compare_files(file1.name, file2.name)
                    assert result is True
                finally:
                    os.unlink(file1.name)
                    os.unlink(file2.name)
    
    @pytest.mark.asyncio
    async def test_compare_files_different_content(self):
        """Test comparing files with different content."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        with tempfile.NamedTemporaryFile(delete=False) as file1:
            file1.write(b"content1")
            file1.flush()
            
            with tempfile.NamedTemporaryFile(delete=False) as file2:
                file2.write(b"content2")
                file2.flush()
                
                try:
                    result = await verifier.compare_files(file1.name, file2.name)
                    assert result is False
                finally:
                    os.unlink(file1.name)
                    os.unlink(file2.name)
    
    @pytest.mark.asyncio
    async def test_compare_files_different_size(self):
        """Test comparing files with different sizes."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        with tempfile.NamedTemporaryFile(delete=False) as file1:
            file1.write(b"short")
            file1.flush()
            
            with tempfile.NamedTemporaryFile(delete=False) as file2:
                file2.write(b"much longer content")
                file2.flush()
                
                try:
                    result = await verifier.compare_files(file1.name, file2.name)
                    assert result is False
                finally:
                    os.unlink(file1.name)
                    os.unlink(file2.name)
    
    @pytest.mark.asyncio
    async def test_verify_transfer_success(self):
        """Test successful transfer verification."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_path = Path(source_dir)
                dest_path = Path(dest_dir)
                
                # Create source file and calculate checksum
                source_file = source_path / "test.txt"
                content = b"test content"
                source_file.write_bytes(content)
                
                source_checksum = await verifier.calculate_checksum(source_file)
                source_checksums = {str(source_file): source_checksum}
                
                # Create identical destination file
                dest_file = dest_path / "test.txt"
                dest_file.write_bytes(content)
                
                result = await verifier.verify_transfer(source_checksums, dest_dir)
                
                assert result.success is True
                assert result.total_files == 1
                assert result.verified_files == 1
                assert len(result.failed_files) == 0
                assert len(result.mismatched_files) == 0
                assert len(result.missing_files) == 0
    
    @pytest.mark.asyncio
    async def test_verify_transfer_missing_file(self):
        """Test transfer verification with missing destination file."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_path = Path(source_dir)
                
                # Create source file and calculate checksum
                source_file = source_path / "test.txt"
                source_file.write_text("test content")
                
                source_checksum = await verifier.calculate_checksum(source_file)
                source_checksums = {str(source_file): source_checksum}
                
                # Don't create destination file
                
                result = await verifier.verify_transfer(source_checksums, dest_dir)
                
                assert result.success is False
                assert result.total_files == 1
                assert result.verified_files == 0
                assert len(result.failed_files) == 0
                assert len(result.mismatched_files) == 0
                assert len(result.missing_files) == 1
                assert str(source_file) in result.missing_files
    
    @pytest.mark.asyncio
    async def test_verify_transfer_mismatched_file(self):
        """Test transfer verification with mismatched file."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_path = Path(source_dir)
                dest_path = Path(dest_dir)
                
                # Create source file and calculate checksum
                source_file = source_path / "test.txt"
                source_file.write_text("original content")
                
                source_checksum = await verifier.calculate_checksum(source_file)
                source_checksums = {str(source_file): source_checksum}
                
                # Create different destination file
                dest_file = dest_path / "test.txt"
                dest_file.write_text("modified content")
                
                result = await verifier.verify_transfer(source_checksums, dest_dir)
                
                assert result.success is False
                assert result.total_files == 1
                assert result.verified_files == 0
                assert len(result.failed_files) == 0
                assert len(result.mismatched_files) == 1
                assert len(result.missing_files) == 0
                assert str(source_file) in result.mismatched_files
    
    @pytest.mark.asyncio
    async def test_verify_transfer_nonexistent_destination(self):
        """Test transfer verification with nonexistent destination directory."""
        verifier = IntegrityVerifier()
        
        source_checksums = {"/source/file.txt": FileChecksum("/source/file.txt", 100)}
        
        result = await verifier.verify_transfer(source_checksums, "/nonexistent/dest")
        
        assert result.success is False
        assert result.error_message == "Destination directory does not exist"
        assert len(result.missing_files) == 1
    
    @pytest.mark.asyncio
    async def test_create_checksum_file_md5sum(self):
        """Test creating MD5 checksum file."""
        verifier = IntegrityVerifier(algorithms=['md5'])
        
        checksums = {
            "/path/file1.txt": FileChecksum("/path/file1.txt", 100, md5="abc123"),
            "/path/file2.txt": FileChecksum("/path/file2.txt", 200, md5="def456")
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            try:
                await verifier.create_checksum_file(checksums, temp_file.name, "md5sum")
                
                with open(temp_file.name, 'r') as f:
                    content = f.read()
                
                assert "abc123  /path/file1.txt" in content
                assert "def456  /path/file2.txt" in content
                
            finally:
                os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_create_checksum_file_unsupported_format(self):
        """Test creating checksum file with unsupported format."""
        verifier = IntegrityVerifier()
        
        with pytest.raises(ValueError) as exc_info:
            await verifier.create_checksum_file({}, "/tmp/test", "unsupported")
        
        assert "Unsupported format type: unsupported" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_checksum_file_algorithm_not_enabled(self):
        """Test creating checksum file for algorithm not enabled."""
        verifier = IntegrityVerifier(algorithms=['md5'])  # sha1 not enabled
        
        with pytest.raises(ValueError) as exc_info:
            await verifier.create_checksum_file({}, "/tmp/test", "sha1sum")
        
        assert "Algorithm sha1 not enabled in verifier" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_load_checksum_file(self):
        """Test loading checksum file."""
        verifier = IntegrityVerifier()
        
        checksum_content = """# Comment line
abc123  /path/file1.txt
def456  /path/file2.txt

# Another comment
ghi789  /path/file3.txt
"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(checksum_content)
            temp_file.flush()
            
            try:
                checksums = await verifier.load_checksum_file(temp_file.name)
                
                assert len(checksums) == 3
                assert checksums["/path/file1.txt"] == "abc123"
                assert checksums["/path/file2.txt"] == "def456"
                assert checksums["/path/file3.txt"] == "ghi789"
                
            finally:
                os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_load_checksum_file_nonexistent(self):
        """Test loading nonexistent checksum file."""
        verifier = IntegrityVerifier()
        
        with pytest.raises(FileNotFoundError):
            await verifier.load_checksum_file("/nonexistent/checksum.md5")