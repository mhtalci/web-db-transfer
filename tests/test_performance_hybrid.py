"""Tests for hybrid performance optimizations."""

import pytest
import asyncio
import tempfile
import os
import time
from unittest.mock import patch, MagicMock, AsyncMock

from migration_assistant.performance.async_pool import (
    AsyncConnectionPool, DatabaseConnectionPool, ResourceMonitor,
    PoolState, PoolStats, resource_monitor
)
from migration_assistant.performance.compression import (
    HybridCompressor, CompressionFormat, CompressionLevel
)
from migration_assistant.performance.monitoring import (
    ResourceMonitor as AdvancedResourceMonitor, MetricCollector,
    SystemMetrics, ProcessMetrics, Alert, AlertLevel, Threshold
)


class TestAsyncConnectionPool:
    """Test async connection pool functionality."""
    
    @pytest.fixture
    def mock_connection_factory(self):
        """Mock connection factory."""
        def factory():
            return MagicMock()
        return factory
    
    @pytest.fixture
    def mock_health_check(self):
        """Mock health check function."""
        def health_check(connection):
            return True
        return health_check
    
    @pytest.fixture
    def mock_cleanup(self):
        """Mock cleanup function."""
        def cleanup(connection):
            pass
        return cleanup
    
    @pytest.fixture
    async def connection_pool(self, mock_connection_factory, mock_health_check, mock_cleanup):
        """Create a test connection pool."""
        pool = AsyncConnectionPool(
            connection_factory=mock_connection_factory,
            min_size=2,
            max_size=5,
            max_idle_time=60.0,
            health_check_interval=10.0,
            health_check_func=mock_health_check,
            cleanup_func=mock_cleanup
        )
        await pool.initialize()
        yield pool
        await pool.close()
    
    async def test_pool_initialization(self, connection_pool):
        """Test pool initialization."""
        assert connection_pool.state == PoolState.ACTIVE
        stats = connection_pool.get_stats()
        assert stats.total_connections >= 2  # min_size
        assert stats.total_created >= 2
    
    async def test_acquire_and_return_connection(self, connection_pool):
        """Test acquiring and returning connections."""
        # Acquire connection
        async with await connection_pool.acquire() as conn:
            assert conn is not None
            stats = connection_pool.get_stats()
            assert stats.active_connections >= 1
        
        # Connection should be returned automatically
        await asyncio.sleep(0.1)  # Allow time for return
        stats = connection_pool.get_stats()
        assert stats.active_connections == 0
    
    async def test_connection_timeout(self, mock_connection_factory):
        """Test connection acquisition timeout."""
        # Create pool with max size 1
        pool = AsyncConnectionPool(
            connection_factory=mock_connection_factory,
            min_size=1,
            max_size=1
        )
        await pool.initialize()
        
        try:
            # Acquire the only connection
            conn1 = await pool.acquire()
            
            # Try to acquire another with timeout
            with pytest.raises(asyncio.TimeoutError):
                await pool.acquire(timeout=0.1)
            
            # Return connection
            await pool._return_connection(conn1._info)
            
        finally:
            await pool.close()
    
    async def test_pool_stats(self, connection_pool):
        """Test pool statistics."""
        stats = connection_pool.get_stats()
        
        assert isinstance(stats, PoolStats)
        assert stats.total_connections >= 0
        assert stats.active_connections >= 0
        assert stats.idle_connections >= 0
        assert stats.total_created >= 0
        assert stats.total_destroyed >= 0
    
    async def test_pool_close(self, connection_pool):
        """Test pool closure."""
        await connection_pool.close()
        assert connection_pool.state == PoolState.CLOSED
    
    async def test_resource_monitor_integration(self, connection_pool):
        """Test resource monitor integration."""
        monitor = ResourceMonitor()
        monitor.register_pool("test_pool", connection_pool)
        
        await monitor.start_monitoring(interval=0.1)
        await asyncio.sleep(0.2)  # Let it collect some metrics
        await monitor.stop_monitoring()
        
        metrics = monitor.get_pool_metrics("test_pool")
        assert len(metrics) > 0
        
        summary = monitor.get_summary()
        assert "test_pool" in summary['pools']
        
        monitor.unregister_pool("test_pool")


class TestHybridCompressor:
    """Test hybrid compression functionality."""
    
    @pytest.fixture
    def compressor(self):
        """Create hybrid compressor."""
        return HybridCompressor(prefer_go=False)  # Use Python for testing
    
    @pytest.fixture
    def test_file(self):
        """Create a test file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("This is test content for compression testing. " * 100)
            test_file_path = f.name
        
        yield test_file_path
        
        # Cleanup
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)
    
    @pytest.fixture
    def test_directory(self):
        """Create a test directory."""
        import tempfile
        import shutil
        
        test_dir = tempfile.mkdtemp()
        
        # Create some test files
        for i in range(3):
            with open(os.path.join(test_dir, f"file_{i}.txt"), 'w') as f:
                f.write(f"Test content for file {i}. " * 50)
        
        yield test_dir
        
        # Cleanup
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
    
    async def test_file_compression_gzip(self, compressor, test_file):
        """Test GZIP file compression."""
        result = await compressor.compress_file(
            test_file,
            format=CompressionFormat.GZIP,
            level=CompressionLevel.BALANCED
        )
        
        assert result.success is True
        assert result.original_size > 0
        assert result.compressed_size > 0
        assert result.compression_ratio < 1.0  # Should be compressed
        assert result.format == CompressionFormat.GZIP
        assert result.method == "python"
        
        # Cleanup compressed file
        compressed_path = test_file + ".gz"
        if os.path.exists(compressed_path):
            os.unlink(compressed_path)
    
    async def test_file_compression_bzip2(self, compressor, test_file):
        """Test BZIP2 file compression."""
        result = await compressor.compress_file(
            test_file,
            format=CompressionFormat.BZIP2,
            level=CompressionLevel.FAST
        )
        
        assert result.success is True
        assert result.format == CompressionFormat.BZIP2
        
        # Cleanup
        compressed_path = test_file + ".bz2"
        if os.path.exists(compressed_path):
            os.unlink(compressed_path)
    
    async def test_file_compression_lzma(self, compressor, test_file):
        """Test LZMA file compression."""
        result = await compressor.compress_file(
            test_file,
            format=CompressionFormat.LZMA,
            level=CompressionLevel.FASTEST
        )
        
        assert result.success is True
        assert result.format == CompressionFormat.LZMA
        
        # Cleanup
        compressed_path = test_file + ".xz"
        if os.path.exists(compressed_path):
            os.unlink(compressed_path)
    
    async def test_directory_compression_zip(self, compressor, test_directory):
        """Test ZIP directory compression."""
        result = await compressor.compress_directory(
            test_directory,
            format=CompressionFormat.ZIP,
            level=CompressionLevel.BALANCED
        )
        
        assert result.success is True
        assert result.original_size > 0
        assert result.compressed_size > 0
        assert result.format == CompressionFormat.ZIP
        
        # Cleanup
        compressed_path = test_directory + ".zip"
        if os.path.exists(compressed_path):
            os.unlink(compressed_path)
    
    async def test_directory_compression_tar_gz(self, compressor, test_directory):
        """Test TAR.GZ directory compression."""
        result = await compressor.compress_directory(
            test_directory,
            format=CompressionFormat.TAR_GZ,
            level=CompressionLevel.BALANCED
        )
        
        assert result.success is True
        assert result.format == CompressionFormat.TAR_GZ
        
        # Cleanup
        compressed_path = test_directory + ".tar.gz"
        if os.path.exists(compressed_path):
            os.unlink(compressed_path)
    
    async def test_file_decompression(self, compressor, test_file):
        """Test file decompression."""
        # First compress the file
        compress_result = await compressor.compress_file(
            test_file,
            format=CompressionFormat.GZIP
        )
        
        assert compress_result.success is True
        compressed_path = test_file + ".gz"
        
        # Then decompress it
        decompress_result = await compressor.decompress_file(
            compressed_path,
            format=CompressionFormat.GZIP
        )
        
        assert decompress_result.success is True
        assert decompress_result.compressed_size > 0
        assert decompress_result.decompressed_size > 0
        assert decompress_result.format == CompressionFormat.GZIP
        
        # Cleanup
        decompressed_path = compressed_path[:-3]  # Remove .gz
        for path in [compressed_path, decompressed_path]:
            if os.path.exists(path):
                os.unlink(path)
    
    async def test_format_detection(self, compressor):
        """Test compression format detection."""
        test_cases = [
            ("file.gz", CompressionFormat.GZIP),
            ("file.bz2", CompressionFormat.BZIP2),
            ("file.xz", CompressionFormat.LZMA),
            ("file.zip", CompressionFormat.ZIP),
            ("file.tar", CompressionFormat.TAR),
            ("file.tar.gz", CompressionFormat.TAR_GZ),
            ("file.tar.bz2", CompressionFormat.TAR_BZ2),
            ("file.tar.xz", CompressionFormat.TAR_XZ),
        ]
        
        for filename, expected_format in test_cases:
            detected_format = compressor._detect_format(filename)
            assert detected_format == expected_format
    
    async def test_compression_levels(self, compressor, test_file):
        """Test different compression levels."""
        results = {}
        
        for level in [CompressionLevel.FASTEST, CompressionLevel.BALANCED, CompressionLevel.BEST]:
            result = await compressor.compress_file(
                test_file,
                format=CompressionFormat.GZIP,
                level=level
            )
            
            assert result.success is True
            results[level] = result
            
            # Cleanup
            compressed_path = test_file + ".gz"
            if os.path.exists(compressed_path):
                os.unlink(compressed_path)
        
        # Generally, higher compression levels should result in smaller files
        # (though this might not always be true for small test files)
        assert all(r.compression_ratio > 0 for r in results.values())
    
    async def test_nonexistent_file_compression(self, compressor):
        """Test compression of non-existent file."""
        result = await compressor.compress_file(
            "/nonexistent/file.txt",
            format=CompressionFormat.GZIP
        )
        
        assert result.success is False
        assert "not found" in result.error.lower()
    
    async def test_benchmark_compression(self, compressor, test_file):
        """Test compression benchmarking."""
        benchmark_result = await compressor.benchmark_compression(
            test_file,
            formats=[CompressionFormat.GZIP],
            levels=[CompressionLevel.FAST],
            iterations=2
        )
        
        assert "test_file" in benchmark_result
        assert "original_size" in benchmark_result
        assert "results" in benchmark_result
        assert CompressionFormat.GZIP.value in benchmark_result["results"]
        
        gzip_results = benchmark_result["results"][CompressionFormat.GZIP.value]
        assert CompressionLevel.FAST.value in gzip_results
        
        level_results = gzip_results[CompressionLevel.FAST.value]
        assert len(level_results) >= 2  # 2 iterations


class TestAdvancedResourceMonitor:
    """Test advanced resource monitoring."""
    
    @pytest.fixture
    def monitor(self):
        """Create resource monitor."""
        return AdvancedResourceMonitor(
            collection_interval=0.1,
            history_size=10,
            enable_alerts=True
        )
    
    @pytest.fixture
    def mock_psutil(self):
        """Mock psutil for testing."""
        with patch('migration_assistant.performance.monitoring.psutil') as mock:
            # Mock virtual_memory
            mock.virtual_memory.return_value = MagicMock(
                total=8000000000,
                available=4000000000,
                percent=50.0,
                used=4000000000,
                free=4000000000
            )
            
            # Mock cpu_percent
            mock.cpu_percent.return_value = 25.0
            
            # Mock cpu_count
            mock.cpu_count.return_value = 4
            
            # Mock swap_memory
            mock.swap_memory.return_value = MagicMock(
                total=2000000000,
                used=500000000,
                percent=25.0
            )
            
            # Mock disk_partitions and disk_usage
            mock.disk_partitions.return_value = [
                MagicMock(mountpoint='/')
            ]
            mock.disk_usage.return_value = MagicMock(
                total=100000000000,
                used=50000000000,
                free=50000000000,
                percent=50.0
            )
            
            # Mock other functions
            mock.net_io_counters.return_value = MagicMock(
                bytes_sent=1000000,
                bytes_recv=2000000,
                packets_sent=1000,
                packets_recv=2000,
                errin=0,
                errout=0,
                dropin=0,
                dropout=0
            )
            
            mock.boot_time.return_value = time.time() - 3600  # 1 hour ago
            mock.pids.return_value = list(range(1, 101))  # 100 processes
            mock.getloadavg.return_value = [1.0, 1.5, 2.0]
            
            yield mock
    
    async def test_metric_collection(self, monitor, mock_psutil):
        """Test metric collection."""
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            collector = MetricCollector()
            metrics = collector.collect_system_metrics()
            
            assert metrics is not None
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_percent == 25.0
            assert metrics.memory_percent == 50.0
            assert metrics.cpu_count == 4
            assert metrics.process_count == 100
    
    async def test_process_metrics_collection(self, monitor, mock_psutil):
        """Test process metrics collection."""
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            # Mock Process
            mock_process = MagicMock()
            mock_process.pid = 1234
            mock_process.name.return_value = "test_process"
            mock_process.status.return_value = "running"
            mock_process.cpu_percent.return_value = 10.0
            mock_process.memory_percent.return_value = 5.0
            mock_process.memory_info.return_value = MagicMock(rss=1000000, vms=2000000)
            mock_process.num_threads.return_value = 4
            mock_process.create_time.return_value = time.time() - 3600
            
            with patch('migration_assistant.performance.monitoring.psutil.Process', return_value=mock_process):
                collector = MetricCollector()
                metrics = collector.collect_process_metrics(1234)
                
                assert metrics is not None
                assert isinstance(metrics, ProcessMetrics)
                assert metrics.pid == 1234
                assert metrics.name == "test_process"
                assert metrics.cpu_percent == 10.0
                assert metrics.memory_percent == 5.0
    
    async def test_monitoring_start_stop(self, monitor, mock_psutil):
        """Test starting and stopping monitoring."""
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            assert not monitor._monitoring
            
            await monitor.start_monitoring()
            assert monitor._monitoring
            
            # Let it collect some metrics
            await asyncio.sleep(0.2)
            
            await monitor.stop_monitoring()
            assert not monitor._monitoring
    
    async def test_threshold_alerts(self, monitor, mock_psutil):
        """Test threshold-based alerting."""
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            # Add a threshold that should trigger
            threshold = Threshold(
                metric="cpu_percent",
                warning_value=20.0,  # Lower than mocked 25.0
                critical_value=30.0
            )
            monitor.add_threshold(threshold)
            
            # Mock high CPU usage
            mock_psutil.cpu_percent.return_value = 85.0
            
            await monitor.start_monitoring()
            await asyncio.sleep(0.2)  # Let it collect and check
            await monitor.stop_monitoring()
            
            alerts = monitor.get_alerts(resolved=False)
            assert len(alerts) > 0
            
            # Check alert properties
            alert = alerts[0]
            assert isinstance(alert, Alert)
            assert alert.level in [AlertLevel.WARNING, AlertLevel.CRITICAL]
            assert alert.metric == "cpu_percent"
    
    async def test_metrics_history(self, monitor, mock_psutil):
        """Test metrics history management."""
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            await monitor.start_monitoring()
            await asyncio.sleep(0.3)  # Collect multiple metrics
            await monitor.stop_monitoring()
            
            historical_metrics = monitor.get_historical_metrics()
            assert len(historical_metrics) > 0
            
            # Test limit
            limited_metrics = monitor.get_historical_metrics(limit=2)
            assert len(limited_metrics) <= 2
            
            # Test current metrics
            current = monitor.get_current_metrics()
            assert current is not None
            assert isinstance(current, SystemMetrics)
    
    async def test_summary_generation(self, monitor, mock_psutil):
        """Test monitoring summary generation."""
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            await monitor.start_monitoring()
            await asyncio.sleep(0.2)
            await monitor.stop_monitoring()
            
            summary = monitor.get_summary()
            
            assert isinstance(summary, dict)
            assert 'monitoring_active' in summary
            assert 'collection_interval' in summary
            assert 'metrics_collected' in summary
            assert 'current_metrics' in summary
    
    async def test_metrics_export(self, monitor, mock_psutil):
        """Test metrics export functionality."""
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            await monitor.start_monitoring()
            await asyncio.sleep(0.2)
            await monitor.stop_monitoring()
            
            # Test JSON export
            json_export = monitor.export_metrics('json')
            assert isinstance(json_export, str)
            assert 'system_metrics' in json_export
            
            # Test CSV export
            csv_export = monitor.export_metrics('csv')
            assert isinstance(csv_export, str)
            assert 'timestamp,cpu_percent' in csv_export
            
            # Test invalid format
            with pytest.raises(ValueError):
                monitor.export_metrics('invalid_format')
    
    def test_threshold_management(self, monitor):
        """Test threshold management."""
        initial_count = len(monitor.thresholds)
        
        # Add threshold
        threshold = Threshold(
            metric="test_metric",
            warning_value=50.0,
            critical_value=80.0
        )
        monitor.add_threshold(threshold)
        assert len(monitor.thresholds) == initial_count + 1
        
        # Remove threshold
        monitor.remove_threshold("test_metric")
        assert len(monitor.thresholds) == initial_count
    
    def test_alert_resolution(self, monitor):
        """Test alert resolution."""
        # Create a test alert
        alert = Alert(
            timestamp=time.time(),
            level=AlertLevel.WARNING,
            metric="test_metric",
            value=75.0,
            threshold=70.0,
            message="Test alert"
        )
        monitor.alerts.append(alert)
        
        # Check unresolved alerts
        unresolved = monitor.get_alerts(resolved=False)
        assert len(unresolved) == 1
        
        # Resolve alert
        monitor.resolve_alert(0)
        
        # Check resolved alerts
        resolved = monitor.get_alerts(resolved=True)
        assert len(resolved) == 1
        assert resolved[0].resolved is True
        assert resolved[0].resolved_at is not None


class TestPerformanceIntegration:
    """Integration tests for performance components."""
    
    async def test_resource_monitor_with_connection_pool(self):
        """Test resource monitor integration with connection pool."""
        # Create connection pool
        def mock_factory():
            return MagicMock()
        
        pool = AsyncConnectionPool(
            connection_factory=mock_factory,
            min_size=1,
            max_size=3
        )
        await pool.initialize()
        
        try:
            # Register with resource monitor
            resource_monitor.register_pool("integration_test", pool)
            
            # Start monitoring
            await resource_monitor.start_monitoring(interval=0.1)
            
            # Use the pool
            async with await pool.acquire() as conn:
                await asyncio.sleep(0.1)
            
            # Let monitor collect metrics
            await asyncio.sleep(0.2)
            
            # Stop monitoring
            await resource_monitor.stop_monitoring()
            
            # Check metrics
            metrics = resource_monitor.get_pool_metrics("integration_test")
            assert len(metrics) > 0
            
            summary = resource_monitor.get_summary()
            assert "integration_test" in summary['pools']
            
        finally:
            resource_monitor.unregister_pool("integration_test")
            await pool.close()
    
    async def test_compression_with_monitoring(self):
        """Test compression with resource monitoring."""
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test content for compression monitoring. " * 1000)
            test_file = f.name
        
        try:
            # Create compressor and monitor
            compressor = HybridCompressor(prefer_go=False)
            monitor = AdvancedResourceMonitor(collection_interval=0.1)
            
            # Start monitoring
            with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
                await monitor.start_monitoring()
                
                # Perform compression
                result = await compressor.compress_file(
                    test_file,
                    format=CompressionFormat.GZIP
                )
                
                # Let monitor collect metrics
                await asyncio.sleep(0.2)
                
                await monitor.stop_monitoring()
                
                # Check results
                assert result.success is True
                
                metrics = monitor.get_historical_metrics()
                assert len(metrics) > 0
                
                # Cleanup compressed file
                compressed_path = test_file + ".gz"
                if os.path.exists(compressed_path):
                    os.unlink(compressed_path)
                
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_with_monitoring(self):
        """Test concurrent operations with resource monitoring."""
        async def mock_operation(duration: float):
            """Mock async operation."""
            await asyncio.sleep(duration)
            return f"completed in {duration}s"
        
        # Start resource monitoring
        monitor = AdvancedResourceMonitor(collection_interval=0.05)
        
        with patch('migration_assistant.performance.monitoring.PSUTIL_AVAILABLE', True):
            await monitor.start_monitoring()
            
            # Run concurrent operations
            tasks = [
                mock_operation(0.1),
                mock_operation(0.15),
                mock_operation(0.2)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Let monitor collect final metrics
            await asyncio.sleep(0.1)
            await monitor.stop_monitoring()
            
            # Check results
            assert len(results) == 3
            assert all("completed" in result for result in results)
            
            # Check monitoring data
            metrics = monitor.get_historical_metrics()
            assert len(metrics) > 0
            
            summary = monitor.get_summary()
            assert summary['monitoring_active'] is False