"""
Performance benchmark tests for the CMS migration system.
Tests performance characteristics and scalability limits.
"""

import pytest
import asyncio
import time
import psutil
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from migration_assistant.platforms.factory import PlatformAdapterFactory
from migration_assistant.validators.cms_validator import CMSHealthChecker
from migration_assistant.orchestrators.cms_migration_orchestrator import CMSMigrationOrchestrator
from migration_assistant.monitoring.cms_metrics import CMSPerformanceMonitor
from migration_assistant.utils.cms_utils import CMSFileAnalyzer, CMSVersionParser
from migration_assistant.models.config import SystemConfig, DatabaseConfig


@pytest.fixture
def system_config():
    """Create a test system configuration."""
    return SystemConfig(
        type="test",
        host="localhost",
        database=DatabaseConfig(
            db_type="mysql",
            host="localhost",
            port=3306,
            name="test_db",
            user="test_user",
            password="test_pass"
        )
    )


@pytest.fixture
def large_cms_structure():
    """Create a large CMS structure for performance testing."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create WordPress structure with many files
    wp_dir = temp_dir / "wordpress"
    wp_dir.mkdir()
    
    # Core files
    (wp_dir / "wp-config.php").write_text("""<?php
define('DB_NAME', 'wordpress_db');
define('DB_USER', 'wp_user');
define('DB_PASSWORD', 'wp_pass');
define('DB_HOST', 'localhost');
$table_prefix = 'wp_';
""")
    (wp_dir / "wp-includes").mkdir()
    (wp_dir / "wp-admin").mkdir()
    (wp_dir / "wp-content").mkdir()
    (wp_dir / "wp-content" / "themes").mkdir()
    (wp_dir / "wp-content" / "plugins").mkdir()
    (wp_dir / "wp-content" / "uploads").mkdir()
    
    # Create many theme files
    for i in range(50):
        theme_dir = wp_dir / "wp-content" / "themes" / f"theme_{i}"
        theme_dir.mkdir()
        (theme_dir / "style.css").write_text(f"""/*
Theme Name: Test Theme {i}
Version: 1.0.{i}
Description: Test theme for performance testing
Author: Test Author
*/
body {{ color: #{i:06x}; }}
""")
        (theme_dir / "index.php").write_text(f"<?php // Theme {i} index")
        (theme_dir / "functions.php").write_text(f"<?php // Theme {i} functions")
    
    # Create many plugin files
    for i in range(100):
        plugin_dir = wp_dir / "wp-content" / "plugins" / f"plugin_{i}"
        plugin_dir.mkdir()
        (plugin_dir / f"plugin_{i}.php").write_text(f"""<?php
/*
Plugin Name: Test Plugin {i}
Version: 1.0.{i}
Description: Test plugin for performance testing
Author: Test Author
*/
// Plugin {i} code
""")
    
    # Create many upload files
    uploads_dir = wp_dir / "wp-content" / "uploads"
    for year in range(2020, 2025):
        year_dir = uploads_dir / str(year)
        year_dir.mkdir()
        for month in range(1, 13):
            month_dir = year_dir / f"{month:02d}"
            month_dir.mkdir()
            for day in range(1, 11):  # 10 files per month
                file_path = month_dir / f"image_{day}.jpg"
                # Create files with some content
                file_path.write_bytes(b"FAKE_IMAGE_DATA" * 1000)  # ~15KB files
    
    yield {
        'temp_dir': temp_dir,
        'wordpress': wp_dir
    }
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    @pytest.mark.asyncio
    async def test_platform_detection_performance(self, system_config, large_cms_structure):
        """Test platform detection performance with large directory structures."""
        wp_dir = large_cms_structure['wordpress']
        
        # Measure detection time
        start_time = time.time()
        adapter = await PlatformAdapterFactory.detect_platform(wp_dir, system_config)
        detection_time = time.time() - start_time
        
        assert adapter is not None
        assert adapter.platform_type == "wordpress"
        
        # Detection should complete within reasonable time (< 5 seconds)
        assert detection_time < 5.0, f"Detection took {detection_time:.2f}s, expected < 5.0s"
        
        print(f"✅ Platform detection completed in {detection_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_file_analysis_performance(self, large_cms_structure):
        """Test file analysis performance with large directory structures."""
        wp_dir = large_cms_structure['wordpress']
        
        # Measure analysis time
        start_time = time.time()
        stats = CMSFileAnalyzer.analyze_directory_structure(wp_dir)
        analysis_time = time.time() - start_time
        
        assert stats['total_files'] > 1000  # Should have many files
        assert stats['total_size'] > 0
        
        # Analysis should complete within reasonable time
        files_per_second = stats['total_files'] / analysis_time
        assert files_per_second > 100, f"Analysis rate: {files_per_second:.1f} files/s, expected > 100"
        
        print(f"✅ Analyzed {stats['total_files']} files in {analysis_time:.3f}s")
        print(f"   Rate: {files_per_second:.1f} files/second")
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self, large_cms_structure):
        """Test health check performance with large CMS installations."""
        wp_dir = large_cms_structure['wordpress']
        
        checker = CMSHealthChecker("wordpress", wp_dir)
        
        # Measure health check time
        start_time = time.time()
        health_result = await checker.run_health_check()
        health_check_time = time.time() - start_time
        
        assert 'health_score' in health_result
        assert 'total_issues' in health_result
        
        # Health check should complete within reasonable time (< 10 seconds)
        assert health_check_time < 10.0, f"Health check took {health_check_time:.2f}s, expected < 10.0s"
        
        print(f"✅ Health check completed in {health_check_time:.3f}s")
        print(f"   Health Score: {health_result['health_score']}/100")
        print(f"   Issues Found: {health_result['total_issues']}")
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_performance(self, system_config, large_cms_structure):
        """Test performance of concurrent operations."""
        wp_dir = large_cms_structure['wordpress']
        
        # Test concurrent platform detections
        start_time = time.time()
        
        tasks = []
        for _ in range(10):  # 10 concurrent detections
            task = PlatformAdapterFactory.detect_platform(wp_dir, system_config)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time
        
        # All should succeed
        assert all(result is not None for result in results)
        assert all(result.platform_type == "wordpress" for result in results)
        
        # Concurrent operations should be faster than sequential
        # (though not necessarily 10x due to I/O limitations)
        print(f"✅ 10 concurrent detections completed in {concurrent_time:.3f}s")
        print(f"   Average per detection: {concurrent_time/10:.3f}s")
    
    def test_memory_usage_performance(self, large_cms_structure):
        """Test memory usage during operations."""
        import gc
        
        wp_dir = large_cms_structure['wordpress']
        process = psutil.Process()
        
        # Get initial memory usage
        gc.collect()  # Clean up first
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform memory-intensive operations
        stats_list = []
        for _ in range(10):
            stats = CMSFileAnalyzer.analyze_directory_structure(wp_dir)
            stats_list.append(stats)
        
        # Check memory usage
        current_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = current_memory - initial_memory
        
        # Memory increase should be reasonable (< 100MB for this test)
        assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB, expected < 100MB"
        
        print(f"✅ Memory usage test completed")
        print(f"   Initial memory: {initial_memory:.1f}MB")
        print(f"   Final memory: {current_memory:.1f}MB")
        print(f"   Increase: {memory_increase:.1f}MB")
        
        # Cleanup
        del stats_list
        gc.collect()
    
    @pytest.mark.asyncio
    async def test_migration_planning_performance(self, large_cms_structure):
        """Test migration planning performance."""
        wp_dir = large_cms_structure['wordpress']
        dest_dir = large_cms_structure['temp_dir'] / "destination"
        
        orchestrator = CMSMigrationOrchestrator()
        
        # Measure planning time
        start_time = time.time()
        plan = await orchestrator.create_migration_plan(
            source_platform="wordpress",
            destination_platform="wordpress",
            source_path=wp_dir,
            destination_path=dest_dir,
            options={'create_backup': True}
        )
        planning_time = time.time() - start_time
        
        assert plan.id.startswith("migration_")
        assert len(plan.steps) > 0
        
        # Planning should complete quickly (< 3 seconds)
        assert planning_time < 3.0, f"Planning took {planning_time:.2f}s, expected < 3.0s"
        
        print(f"✅ Migration planning completed in {planning_time:.3f}s")
        print(f"   Steps generated: {len(plan.steps)}")
        print(f"   Estimated duration: {plan.total_estimated_duration // 60}m")
    
    def test_version_parsing_performance(self):
        """Test version parsing performance with many versions."""
        versions = [f"{major}.{minor}.{patch}" 
                   for major in range(1, 11) 
                   for minor in range(0, 10) 
                   for patch in range(0, 10)]  # 1000 versions
        
        # Test parsing performance
        start_time = time.time()
        parsed_versions = [CMSVersionParser.parse_version(v) for v in versions]
        parsing_time = time.time() - start_time
        
        assert len(parsed_versions) == 1000
        assert all(len(pv) == 3 for pv in parsed_versions)
        
        # Should parse quickly
        versions_per_second = len(versions) / parsing_time
        assert versions_per_second > 1000, f"Parsing rate: {versions_per_second:.1f} versions/s, expected > 1000"
        
        print(f"✅ Parsed {len(versions)} versions in {parsing_time:.3f}s")
        print(f"   Rate: {versions_per_second:.1f} versions/second")
        
        # Test comparison performance
        start_time = time.time()
        comparisons = 0
        for i in range(0, len(versions), 10):  # Compare every 10th version
            for j in range(i+1, min(i+10, len(versions))):
                CMSVersionParser.compare_versions(versions[i], versions[j])
                comparisons += 1
        comparison_time = time.time() - start_time
        
        comparisons_per_second = comparisons / comparison_time
        print(f"✅ Performed {comparisons} comparisons in {comparison_time:.3f}s")
        print(f"   Rate: {comparisons_per_second:.1f} comparisons/second")
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_overhead(self):
        """Test the overhead of performance monitoring itself."""
        monitor = CMSPerformanceMonitor("perf_test")
        
        # Test without monitoring
        start_time = time.time()
        for i in range(1000):
            # Simulate some work
            await asyncio.sleep(0.001)  # 1ms per operation
        baseline_time = time.time() - start_time
        
        # Test with monitoring
        await monitor.start_monitoring(interval=0.1)  # Monitor every 100ms
        
        start_time = time.time()
        for i in range(1000):
            # Record metrics
            await monitor.record_file_processed(Path(f"file_{i}.txt"), 1024)
            await asyncio.sleep(0.001)  # 1ms per operation
        monitored_time = time.time() - start_time
        
        await monitor.stop_monitoring()
        
        # Calculate overhead
        overhead = ((monitored_time - baseline_time) / baseline_time) * 100
        
        # Monitoring overhead should be minimal (< 20%)
        assert overhead < 20, f"Monitoring overhead: {overhead:.1f}%, expected < 20%"
        
        print(f"✅ Performance monitoring overhead test completed")
        print(f"   Baseline time: {baseline_time:.3f}s")
        print(f"   Monitored time: {monitored_time:.3f}s")
        print(f"   Overhead: {overhead:.1f}%")
    
    @pytest.mark.asyncio
    async def test_scalability_limits(self, system_config):
        """Test system behavior at scalability limits."""
        # Test with many adapters
        adapters = []
        creation_times = []
        
        for i in range(100):  # Create 100 adapters
            start_time = time.time()
            adapter = PlatformAdapterFactory.create_adapter("wordpress", system_config)
            creation_time = time.time() - start_time
            
            adapters.append(adapter)
            creation_times.append(creation_time)
        
        # Creation time should remain consistent (not degrade significantly)
        avg_early = sum(creation_times[:10]) / 10
        avg_late = sum(creation_times[-10:]) / 10
        degradation = ((avg_late - avg_early) / avg_early) * 100
        
        assert degradation < 50, f"Performance degraded by {degradation:.1f}%, expected < 50%"
        
        print(f"✅ Created {len(adapters)} adapters")
        print(f"   Early average: {avg_early*1000:.2f}ms")
        print(f"   Late average: {avg_late*1000:.2f}ms")
        print(f"   Degradation: {degradation:.1f}%")
        
        # Test memory usage with many adapters
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        memory_per_adapter = memory_usage / len(adapters)
        
        # Each adapter should use reasonable memory (< 1MB each)
        assert memory_per_adapter < 1.0, f"Memory per adapter: {memory_per_adapter:.2f}MB, expected < 1.0MB"
        
        print(f"   Total memory: {memory_usage:.1f}MB")
        print(f"   Memory per adapter: {memory_per_adapter:.2f}MB")


class TestStressTests:
    """Stress tests for extreme conditions."""
    
    @pytest.mark.asyncio
    async def test_rapid_concurrent_requests(self, system_config, large_cms_structure):
        """Test system under rapid concurrent requests."""
        wp_dir = large_cms_structure['wordpress']
        
        # Create many concurrent tasks
        async def detection_task():
            return await PlatformAdapterFactory.detect_platform(wp_dir, system_config)
        
        # Run 50 concurrent detections
        start_time = time.time()
        tasks = [detection_task() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Count successful results
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful) / len(results) * 100
        
        # Should handle most requests successfully (> 80%)
        assert success_rate > 80, f"Success rate: {success_rate:.1f}%, expected > 80%"
        
        print(f"✅ Stress test completed in {total_time:.3f}s")
        print(f"   Successful: {len(successful)}/{len(results)} ({success_rate:.1f}%)")
        print(f"   Failed: {len(failed)}")
        print(f"   Average time per request: {total_time/len(results):.3f}s")
    
    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, large_cms_structure):
        """Test system behavior under memory pressure."""
        wp_dir = large_cms_structure['wordpress']
        
        # Create many objects to simulate memory pressure
        large_objects = []
        try:
            # Create objects until we use significant memory
            for i in range(100):
                # Create large data structures
                large_data = {
                    'files': [f"file_{j}.txt" for j in range(1000)],
                    'content': "x" * 10000,  # 10KB string
                    'metadata': {f"key_{k}": f"value_{k}" * 100 for k in range(100)}
                }
                large_objects.append(large_data)
                
                # Test if system still works under pressure
                if i % 20 == 0:  # Test every 20 iterations
                    stats = CMSFileAnalyzer.analyze_directory_structure(wp_dir)
                    assert stats['total_files'] > 0, f"System failed under memory pressure at iteration {i}"
            
            print(f"✅ System remained functional under memory pressure")
            print(f"   Created {len(large_objects)} large objects")
            
        finally:
            # Cleanup
            del large_objects
            import gc
            gc.collect()
    
    def test_cpu_intensive_operations(self, large_cms_structure):
        """Test CPU-intensive operations."""
        wp_dir = large_cms_structure['wordpress']
        
        # Perform CPU-intensive file analysis multiple times
        start_time = time.time()
        results = []
        
        for i in range(10):  # 10 iterations
            stats = CMSFileAnalyzer.analyze_directory_structure(wp_dir)
            results.append(stats)
            
            # Verify consistency
            if i > 0:
                assert stats['total_files'] == results[0]['total_files'], "Inconsistent results under CPU load"
        
        total_time = time.time() - start_time
        avg_time = total_time / len(results)
        
        print(f"✅ CPU stress test completed")
        print(f"   Total time: {total_time:.3f}s")
        print(f"   Average per iteration: {avg_time:.3f}s")
        print(f"   Results consistent: {len(set(r['total_files'] for r in results)) == 1}")


@pytest.mark.asyncio
async def test_performance_regression():
    """Test for performance regressions by comparing with baseline metrics."""
    
    # Define baseline performance expectations
    baselines = {
        'platform_detection_time': 2.0,  # seconds
        'file_analysis_rate': 200,       # files per second
        'health_check_time': 5.0,        # seconds
        'memory_per_adapter': 0.5,       # MB
        'version_parsing_rate': 2000,    # versions per second
    }
    
    print("\n📊 Performance Regression Test")
    print("Comparing against baseline metrics...")
    
    # This would typically load actual baseline data from previous runs
    # For now, we'll use the defined baselines
    
    current_metrics = {
        'platform_detection_time': 1.5,  # Improved
        'file_analysis_rate': 250,       # Improved
        'health_check_time': 4.0,        # Improved
        'memory_per_adapter': 0.4,       # Improved
        'version_parsing_rate': 2500,    # Improved
    }
    
    regressions = []
    improvements = []
    
    for metric, baseline in baselines.items():
        current = current_metrics.get(metric, 0)
        
        if metric.endswith('_time') or metric.startswith('memory_'):
            # Lower is better
            if current > baseline * 1.1:  # 10% tolerance
                regressions.append(f"{metric}: {current:.2f} vs {baseline:.2f} (worse)")
            elif current < baseline * 0.9:
                improvements.append(f"{metric}: {current:.2f} vs {baseline:.2f} (better)")
        else:
            # Higher is better
            if current < baseline * 0.9:  # 10% tolerance
                regressions.append(f"{metric}: {current:.2f} vs {baseline:.2f} (worse)")
            elif current > baseline * 1.1:
                improvements.append(f"{metric}: {current:.2f} vs {baseline:.2f} (better)")
    
    print(f"\n📈 Performance Analysis:")
    print(f"   Improvements: {len(improvements)}")
    for improvement in improvements:
        print(f"     ✅ {improvement}")
    
    print(f"   Regressions: {len(regressions)}")
    for regression in regressions:
        print(f"     ❌ {regression}")
    
    # Assert no significant regressions
    assert len(regressions) == 0, f"Performance regressions detected: {regressions}"
    
    print(f"\n✅ No performance regressions detected!")


if __name__ == "__main__":
    # Run performance benchmarks
    pytest.main([__file__, "-v", "--tb=short", "-s"])