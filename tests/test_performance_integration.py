"""
Integration tests for Python-Go performance engine communication.
"""

import asyncio
import os
import tempfile
import pytest
from pathlib import Path

from migration_assistant.performance import (
    GoPerformanceEngine,
    PythonFallbackEngine,
    HybridPerformanceEngine
)


class TestGoPerformanceEngine:
    """Test Go Performance Engine integration."""
    
    @pytest.fixture
    def go_engine(self):
        """Create a Go performance engine instance."""
        return GoPerformanceEngine()
    
    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            source_file = Path(temp_dir) / "source.txt"
            dest_file = Path(temp_dir) / "dest.txt"
            
            # Write test content
            test_content = "Hello, World! This is a test file for Go performance engine testing.\n" * 100
            source_file.write_text(test_content)
            
            yield {
                "temp_dir": temp_dir,
                "source_file": str(source_file),
                "dest_file": str(dest_file),
                "test_content": test_content
            }
    
    def test_go_engine_availability(self, go_engine):
        """Test if Go engine is available."""
        # This test will pass regardless of Go binary availability
        # but will log the status
        is_available = go_engine.is_available()
        binary_path = go_engine.get_binary_path()
        
        print(f"Go engine available: {is_available}")
        print(f"Go binary path: {binary_path}")
        
        # Test should not fail if Go is not available
        assert isinstance(is_available, bool)
    
    @pytest.mark.asyncio
    async def test_go_file_copy(self, go_engine, temp_files):
        """Test Go-based file copying."""
        if not go_engine.is_available():
            pytest.skip("Go binary not available")
        
        result = await go_engine.copy_file(
            temp_files["source_file"],
            temp_files["dest_file"]
        )
        
        assert result is not None
        assert result.success
        assert result.bytes_copied > 0
        assert result.checksum != ""
        assert result.transfer_rate_mbps >= 0
        
        # Verify file was actually copied
        assert os.path.exists(temp_files["dest_file"])
        
        # Verify content matches
        with open(temp_files["dest_file"], 'r') as f:
            copied_content = f.read()
        assert copied_content == temp_files["test_content"]
    
    @pytest.mark.asyncio
    async def test_go_checksum_calculation(self, go_engine, temp_files):
        """Test Go-based checksum calculation."""
        if not go_engine.is_available():
            pytest.skip("Go binary not available")
        
        files = [temp_files["source_file"]]
        results = await go_engine.calculate_checksums(files)
        
        assert results is not None
        assert len(results) == 1
        
        result = results[0]
        assert result.file == temp_files["source_file"]
        assert result.md5 != ""
        assert result.sha1 != ""
        assert result.sha256 != ""
        assert result.size > 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_go_system_monitoring(self, go_engine):
        """Test Go-based system monitoring."""
        if not go_engine.is_available():
            pytest.skip("Go binary not available")
        
        stats = await go_engine.get_system_stats()
        
        assert stats is not None
        assert stats.cpu is not None
        assert stats.memory is not None
        assert stats.disk is not None
        assert stats.network is not None
        assert stats.go_runtime is not None
        
        # Verify CPU stats
        assert "usage_percent" in stats.cpu
        assert "count" in stats.cpu
        assert stats.cpu["count"] > 0
        
        # Verify memory stats
        assert "total" in stats.memory
        assert "used" in stats.memory
        assert stats.memory["total"] > 0


class TestPythonFallbackEngine:
    """Test Python Fallback Engine."""
    
    @pytest.fixture
    def python_engine(self):
        """Create a Python fallback engine instance."""
        return PythonFallbackEngine()
    
    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            source_file = Path(temp_dir) / "source.txt"
            dest_file = Path(temp_dir) / "dest.txt"
            
            # Write test content
            test_content = "Hello, World! This is a test file for Python fallback engine testing.\n" * 100
            source_file.write_text(test_content)
            
            yield {
                "temp_dir": temp_dir,
                "source_file": str(source_file),
                "dest_file": str(dest_file),
                "test_content": test_content
            }
    
    def test_python_engine_availability(self, python_engine):
        """Test if Python engine is available."""
        assert python_engine.is_available()
    
    @pytest.mark.asyncio
    async def test_python_file_copy(self, python_engine, temp_files):
        """Test Python-based file copying."""
        result = await python_engine.copy_file(
            temp_files["source_file"],
            temp_files["dest_file"]
        )
        
        assert result is not None
        assert result.success
        assert result.bytes_copied > 0
        assert result.checksum != ""
        assert result.transfer_rate_mbps >= 0
        
        # Verify file was actually copied
        assert os.path.exists(temp_files["dest_file"])
        
        # Verify content matches
        with open(temp_files["dest_file"], 'r') as f:
            copied_content = f.read()
        assert copied_content == temp_files["test_content"]
    
    @pytest.mark.asyncio
    async def test_python_checksum_calculation(self, python_engine, temp_files):
        """Test Python-based checksum calculation."""
        files = [temp_files["source_file"]]
        results = await python_engine.calculate_checksums(files)
        
        assert results is not None
        assert len(results) == 1
        
        result = results[0]
        assert result.file == temp_files["source_file"]
        assert result.md5 != ""
        assert result.sha1 != ""
        assert result.sha256 != ""
        assert result.size > 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_python_system_monitoring(self, python_engine):
        """Test Python-based system monitoring."""
        stats = await python_engine.get_system_stats()
        
        assert stats is not None
        assert stats.cpu is not None
        assert stats.memory is not None
        assert stats.disk is not None
        assert stats.network is not None
        
        # Verify CPU stats
        assert "usage_percent" in stats.cpu
        assert "count" in stats.cpu
        assert stats.cpu["count"] > 0
        
        # Verify memory stats
        assert "total" in stats.memory
        assert "used" in stats.memory
        assert stats.memory["total"] > 0


class TestHybridPerformanceEngine:
    """Test Hybrid Performance Engine."""
    
    @pytest.fixture
    def hybrid_engine(self):
        """Create a hybrid performance engine instance."""
        return HybridPerformanceEngine()
    
    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            source_file = Path(temp_dir) / "source.txt"
            dest_file = Path(temp_dir) / "dest.txt"
            
            # Write test content
            test_content = "Hello, World! This is a test file for hybrid engine testing.\n" * 100
            source_file.write_text(test_content)
            
            yield {
                "temp_dir": temp_dir,
                "source_file": str(source_file),
                "dest_file": str(dest_file),
                "test_content": test_content
            }
    
    def test_hybrid_engine_availability(self, hybrid_engine):
        """Test if hybrid engine is available."""
        assert hybrid_engine.is_available()
        
        status = hybrid_engine.get_engine_status()
        assert "go_engine" in status
        assert "python_engine" in status
        assert "preferred_engine" in status
        
        # Python engine should always be available
        assert status["python_engine"]["available"]
    
    @pytest.mark.asyncio
    async def test_hybrid_file_copy(self, hybrid_engine, temp_files):
        """Test hybrid file copying with automatic fallback."""
        result = await hybrid_engine.copy_file(
            temp_files["source_file"],
            temp_files["dest_file"]
        )
        
        assert result is not None
        assert result.success
        assert result.bytes_copied > 0
        assert result.checksum != ""
        assert result.transfer_rate_mbps >= 0
        
        # Verify file was actually copied
        assert os.path.exists(temp_files["dest_file"])
        
        # Verify content matches
        with open(temp_files["dest_file"], 'r') as f:
            copied_content = f.read()
        assert copied_content == temp_files["test_content"]
    
    @pytest.mark.asyncio
    async def test_hybrid_checksum_calculation(self, hybrid_engine, temp_files):
        """Test hybrid checksum calculation with automatic fallback."""
        files = [temp_files["source_file"]]
        results = await hybrid_engine.calculate_checksums(files)
        
        assert results is not None
        assert len(results) == 1
        
        result = results[0]
        assert result.file == temp_files["source_file"]
        assert result.md5 != ""
        assert result.sha1 != ""
        assert result.sha256 != ""
        assert result.size > 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_hybrid_system_monitoring(self, hybrid_engine):
        """Test hybrid system monitoring with automatic fallback."""
        stats = await hybrid_engine.get_system_stats()
        
        assert stats is not None
        assert stats.cpu is not None
        assert stats.memory is not None
        assert stats.disk is not None
        assert stats.network is not None
        
        # Verify CPU stats
        assert "usage_percent" in stats.cpu
        assert "count" in stats.cpu
        assert stats.cpu["count"] > 0
        
        # Verify memory stats
        assert "total" in stats.memory
        assert "used" in stats.memory
        assert stats.memory["total"] > 0
    
    @pytest.mark.asyncio
    async def test_hybrid_fallback_behavior(self, temp_files):
        """Test that hybrid engine falls back correctly when Go is unavailable."""
        # Create hybrid engine with invalid Go binary path
        hybrid_engine = HybridPerformanceEngine(go_binary_path="/nonexistent/binary")
        
        # Should still work using Python fallback
        result = await hybrid_engine.copy_file(
            temp_files["source_file"],
            temp_files["dest_file"]
        )
        
        assert result is not None
        assert result.success
        
        # Verify the Python engine was used
        status = hybrid_engine.get_engine_status()
        assert not status["go_engine"]["available"]
        assert status["python_engine"]["available"]
    
    def test_engine_preference_switching(self, hybrid_engine):
        """Test switching engine preferences."""
        # Test initial preference
        status = hybrid_engine.get_engine_status()
        initial_preference = status["preferred_engine"]
        
        # Switch preference
        hybrid_engine.set_preference(prefer_go=False)
        status = hybrid_engine.get_engine_status()
        assert status["preferred_engine"] == "Python"
        
        # Switch back
        hybrid_engine.set_preference(prefer_go=True)
        status = hybrid_engine.get_engine_status()
        # Should be Go if available, otherwise Python
        expected = "Go" if status["go_engine"]["available"] else "Python"
        assert status["preferred_engine"] == expected


class TestPerformanceComparison:
    """Test performance comparison between Go and Python implementations."""
    
    @pytest.fixture
    def hybrid_engine(self):
        """Create a hybrid performance engine instance."""
        return HybridPerformanceEngine()
    
    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            source_file = Path(temp_dir) / "source.txt"
            
            # Write test content (larger for meaningful performance comparison)
            test_content = "Hello, World! This is a test file for performance comparison.\n" * 1000
            source_file.write_text(test_content)
            
            yield {
                "temp_dir": temp_dir,
                "source_file": str(source_file),
                "test_content": test_content
            }
    
    @pytest.mark.asyncio
    async def test_performance_comparison_copy(self, hybrid_engine, temp_files):
        """Test performance comparison for file copying."""
        if not hybrid_engine.go_engine.is_available():
            pytest.skip("Go binary not available for comparison")
        
        dest_file = os.path.join(temp_files["temp_dir"], "comparison_dest.txt")
        
        comparison = await hybrid_engine.compare_performance(
            "copy",
            temp_files["source_file"],
            dest_file,
            iterations=2
        )
        
        assert "go" in comparison
        assert "python" in comparison
        assert "comparison" in comparison
        
        # Clean up
        if os.path.exists(dest_file):
            os.remove(dest_file)
    
    @pytest.mark.asyncio
    async def test_performance_comparison_checksum(self, hybrid_engine, temp_files):
        """Test performance comparison for checksum calculation."""
        if not hybrid_engine.go_engine.is_available():
            pytest.skip("Go binary not available for comparison")
        
        comparison = await hybrid_engine.compare_performance(
            "checksum",
            [temp_files["source_file"]],
            iterations=2
        )
        
        assert "go" in comparison
        assert "python" in comparison
        assert "comparison" in comparison


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def hybrid_engine(self):
        """Create a hybrid performance engine instance."""
        return HybridPerformanceEngine()
    
    @pytest.mark.asyncio
    async def test_nonexistent_file_copy(self, hybrid_engine):
        """Test copying a non-existent file."""
        result = await hybrid_engine.copy_file(
            "/nonexistent/source.txt",
            "/tmp/dest.txt"
        )
        
        # Should fail gracefully
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalid_checksum_files(self, hybrid_engine):
        """Test checksum calculation with invalid files."""
        results = await hybrid_engine.calculate_checksums([
            "/nonexistent/file1.txt",
            "/nonexistent/file2.txt"
        ])
        
        # Should return results with errors
        assert results is not None
        assert len(results) == 2
        
        for result in results:
            assert result.error is not None or (result.md5 == "" and result.sha1 == "" and result.sha256 == "")
    
    @pytest.mark.asyncio
    async def test_permission_denied_scenarios(self, hybrid_engine):
        """Test handling of permission denied scenarios."""
        # Try to copy to a restricted location (this may not fail on all systems)
        result = await hybrid_engine.copy_file(
            __file__,  # Use this test file as source
            "/root/restricted.txt"  # Restricted destination
        )
        
        # Should either succeed (if running as root) or fail gracefully
        if result is None:
            # Failed as expected due to permissions
            pass
        else:
            # Succeeded (running with sufficient permissions)
            assert result.success