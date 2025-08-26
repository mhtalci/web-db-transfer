"""
Comprehensive test suite for the entire CMS migration codebase.
Tests all components, integrations, and advanced features.
"""

import pytest
import asyncio
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# Import all the modules we need to test
from migration_assistant.platforms.factory import PlatformAdapterFactory
from migration_assistant.platforms.cms import (
    WordPressAdapter, DrupalAdapter, JoomlaAdapter, MagentoAdapter,
    ShopwareAdapter, PrestaShopAdapter, OpenCartAdapter, GhostAdapter,
    CraftCMSAdapter, Typo3Adapter, Concrete5Adapter, UmbracoAdapter
)
from migration_assistant.core.cms_exceptions import (
    CMSError, CMSDetectionError, CMSVersionError, CMSConfigurationError,
    CMSDatabaseError, CMSMigrationError, CMSCompatibilityError
)
from migration_assistant.utils.cms_utils import (
    CMSVersionParser, CMSConfigParser, CMSFileAnalyzer, 
    CMSSecurityAnalyzer, CMSMigrationPlanner
)
from migration_assistant.validators.cms_validator import (
    CMSHealthChecker, CMSCompatibilityChecker, ValidationSeverity
)
from migration_assistant.orchestrators.cms_migration_orchestrator import (
    CMSMigrationOrchestrator, MigrationStage, MigrationStatus
)
from migration_assistant.monitoring.cms_metrics import (
    CMSPerformanceMonitor, CMSMetricsCollector, PerformanceMetric
)
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
def temp_cms_structure():
    """Create temporary CMS directory structures for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # WordPress structure
    wp_dir = temp_dir / "wordpress"
    wp_dir.mkdir()
    (wp_dir / "wp-config.php").write_text("""<?php
define('DB_NAME', 'wordpress_db');
define('DB_USER', 'wp_user');
define('DB_PASSWORD', 'wp_pass');
define('DB_HOST', 'localhost');
$table_prefix = 'wp_';
""")
    (wp_dir / "wp-includes").mkdir()
    (wp_dir / "wp-admin").mkdir()
    (wp_dir / "wp-includes" / "version.php").write_text("<?php\n$wp_version = '6.4.2';")
    
    # Magento structure
    magento_dir = temp_dir / "magento"
    magento_dir.mkdir()
    (magento_dir / "app").mkdir()
    (magento_dir / "app" / "etc").mkdir()
    (magento_dir / "bin").mkdir()
    (magento_dir / "lib").mkdir()
    (magento_dir / "pub").mkdir()
    (magento_dir / "var").mkdir()
    (magento_dir / "app" / "etc" / "env.php").write_text("""<?php
return [
    'db' => [
        'connection' => [
            'default' => [
                'host' => 'localhost',
                'dbname' => 'magento_db',
                'username' => 'magento_user',
                'password' => 'magento_pass'
            ]
        ]
    ]
];
""")
    
    # Ghost structure
    ghost_dir = temp_dir / "ghost"
    ghost_dir.mkdir()
    (ghost_dir / "package.json").write_text("""{
    "name": "ghost",
    "version": "5.0.0",
    "description": "The professional publishing platform"
}""")
    (ghost_dir / "config.production.json").write_text("""{
    "database": {
        "client": "mysql",
        "connection": {
            "host": "localhost",
            "user": "ghost_user",
            "password": "ghost_pass",
            "database": "ghost_db"
        }
    }
}""")
    
    yield {
        'temp_dir': temp_dir,
        'wordpress': wp_dir,
        'magento': magento_dir,
        'ghost': ghost_dir
    }
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestPlatformFactory:
    """Test the platform adapter factory."""
    
    def test_get_available_platforms(self):
        """Test getting list of available platforms."""
        platforms = PlatformAdapterFactory.get_available_platforms()
        
        expected_cms_platforms = [
            "wordpress", "drupal", "joomla", "magento", "shopware",
            "prestashop", "opencart", "ghost", "craftcms", "typo3",
            "concrete5", "umbraco"
        ]
        
        for platform in expected_cms_platforms:
            assert platform in platforms, f"Platform {platform} not found in available platforms"
    
    def test_create_all_cms_adapters(self, system_config):
        """Test creating all CMS adapters."""
        cms_adapters = [
            ("wordpress", WordPressAdapter),
            ("drupal", DrupalAdapter),
            ("joomla", JoomlaAdapter),
            ("magento", MagentoAdapter),
            ("shopware", ShopwareAdapter),
            ("prestashop", PrestaShopAdapter),
            ("opencart", OpenCartAdapter),
            ("ghost", GhostAdapter),
            ("craftcms", CraftCMSAdapter),
            ("typo3", Typo3Adapter),
            ("concrete5", Concrete5Adapter),
            ("umbraco", UmbracoAdapter)
        ]
        
        for platform_type, expected_class in cms_adapters:
            adapter = PlatformAdapterFactory.create_adapter(platform_type, system_config)
            assert isinstance(adapter, expected_class)
            assert adapter.platform_type == platform_type
            assert len(adapter.supported_versions) > 0
    
    def test_compatibility_matrix(self):
        """Test the complete compatibility matrix."""
        # Test e-commerce platform compatibility
        ecommerce_platforms = ["magento", "shopware", "prestashop", "opencart"]
        for source in ecommerce_platforms:
            for dest in ecommerce_platforms:
                assert PlatformAdapterFactory.validate_platform_compatibility(source, dest)
        
        # Test CMS compatibility
        cms_compatible_pairs = [
            ("wordpress", "drupal"),
            ("wordpress", "ghost"),
            ("drupal", "wordpress"),
            ("ghost", "craftcms"),
            ("craftcms", "ghost")
        ]
        
        for source, dest in cms_compatible_pairs:
            assert PlatformAdapterFactory.validate_platform_compatibility(source, dest)
        
        # Test incompatible pairs
        incompatible_pairs = [
            ("magento", "ghost"),
            ("wordpress", "shopware"),
            ("umbraco", "opencart")
        ]
        
        for source, dest in incompatible_pairs:
            assert not PlatformAdapterFactory.validate_platform_compatibility(source, dest)
    
    @pytest.mark.asyncio
    async def test_platform_detection(self, system_config, temp_cms_structure):
        """Test automatic platform detection."""
        # Test WordPress detection
        wp_adapter = await PlatformAdapterFactory.detect_platform(
            temp_cms_structure['wordpress'], system_config
        )
        assert wp_adapter is not None
        assert wp_adapter.platform_type == "wordpress"
        
        # Test Magento detection
        magento_adapter = await PlatformAdapterFactory.detect_platform(
            temp_cms_structure['magento'], system_config
        )
        assert magento_adapter is not None
        assert magento_adapter.platform_type == "magento"
        
        # Test Ghost detection
        ghost_adapter = await PlatformAdapterFactory.detect_platform(
            temp_cms_structure['ghost'], system_config
        )
        assert ghost_adapter is not None
        assert ghost_adapter.platform_type == "ghost"


class TestCMSExceptions:
    """Test CMS-specific exceptions."""
    
    def test_cms_detection_error(self):
        """Test CMS detection error."""
        error = CMSDetectionError("/path/to/cms", ["wordpress", "drupal"])
        assert "Failed to detect CMS platform" in str(error)
        assert error.path == "/path/to/cms"
        assert error.attempted_platforms == ["wordpress", "drupal"]
    
    def test_cms_version_error(self):
        """Test CMS version error."""
        error = CMSVersionError("wordpress", "3.0", ["4.0", "5.0", "6.0"])
        assert "version 3.0 is not supported" in str(error)
        assert error.platform == "wordpress"
        assert error.version == "3.0"
    
    def test_cms_migration_error(self):
        """Test CMS migration error."""
        error = CMSMigrationError("wordpress", "drupal", "export_database", "Connection failed")
        assert "Migration failed from wordpress to drupal" in str(error)
        assert error.source_platform == "wordpress"
        assert error.destination_platform == "drupal"
        assert error.step == "export_database"


class TestCMSUtils:
    """Test CMS utility functions."""
    
    def test_version_parser(self):
        """Test version parsing and comparison."""
        # Test version parsing
        assert CMSVersionParser.parse_version("6.4.2") == (6, 4, 2)
        assert CMSVersionParser.parse_version("10.1") == (10, 1)
        assert CMSVersionParser.parse_version("invalid") == (0,)
        
        # Test version comparison
        assert CMSVersionParser.compare_versions("6.4.2", "6.4.1") == 1
        assert CMSVersionParser.compare_versions("6.4.1", "6.4.2") == -1
        assert CMSVersionParser.compare_versions("6.4.2", "6.4.2") == 0
        
        # Test version support checking
        supported_versions = ["6.0", "6.1", "6.2", "6.3", "6.4"]
        assert CMSVersionParser.is_version_supported("6.2", supported_versions)
        assert not CMSVersionParser.is_version_supported("5.9", supported_versions)
        
        # Test latest version
        latest = CMSVersionParser.get_latest_supported_version(supported_versions)
        assert latest == "6.4"
    
    def test_config_parser(self):
        """Test configuration file parsing."""
        # Test PHP config parsing
        php_content = """<?php
define('DB_NAME', 'test_db');
define('DB_USER', 'test_user');
$table_prefix = 'wp_';
"""
        php_config = CMSConfigParser.parse_php_config(php_content)
        assert php_config['DB_NAME'] == 'test_db'
        assert php_config['DB_USER'] == 'test_user'
        assert php_config['table_prefix'] == 'wp_'
        
        # Test connection string parsing
        conn_str = "mysql://user:pass@localhost:3306/database"
        parsed = CMSConfigParser.parse_connection_string(conn_str)
        assert parsed['type'] == 'mysql'
        assert parsed['username'] == 'user'
        assert parsed['password'] == 'pass'
        assert parsed['host'] == 'localhost'
        assert parsed['database'] == 'database'
    
    def test_file_analyzer(self, temp_cms_structure):
        """Test file analysis utilities."""
        wp_dir = temp_cms_structure['wordpress']
        
        # Test directory analysis
        stats = CMSFileAnalyzer.analyze_directory_structure(wp_dir)
        assert stats['total_files'] > 0
        assert stats['total_directories'] > 0
        assert 'file_types' in stats
        
        # Test CMS indicator detection
        indicators = CMSFileAnalyzer.detect_cms_indicators(wp_dir)
        assert 'wordpress' in indicators
        assert 'wp-config.php' in indicators['wordpress']
        
        # Test file hash
        config_file = wp_dir / "wp-config.php"
        hash1 = CMSFileAnalyzer.get_file_hash(config_file)
        hash2 = CMSFileAnalyzer.get_file_hash(config_file)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hash length
    
    def test_security_analyzer(self, temp_cms_structure):
        """Test security analysis utilities."""
        wp_dir = temp_cms_structure['wordpress']
        
        # Test permission checking
        permission_check = CMSSecurityAnalyzer.check_file_permissions(wp_dir)
        assert 'issues' in permission_check
        assert 'recommendations' in permission_check
        
        # Test sensitive data scanning
        sensitive_content = """
        define('DB_PASSWORD', 'secret123');
        $api_key = 'sk_test_123456789';
        """
        findings = CMSSecurityAnalyzer.scan_for_sensitive_data(sensitive_content)
        assert len(findings) > 0
        assert any('Password' in finding for finding in findings)
    
    def test_migration_planner(self, temp_cms_structure):
        """Test migration planning utilities."""
        wp_dir = temp_cms_structure['wordpress']
        stats = CMSFileAnalyzer.analyze_directory_structure(wp_dir)
        
        # Test time estimation
        time_estimate = CMSMigrationPlanner.estimate_migration_time(
            stats, "wordpress", "wordpress"
        )
        assert 'estimated_seconds' in time_estimate
        assert 'estimated_minutes' in time_estimate
        assert time_estimate['estimated_seconds'] > 0
        
        # Test checklist generation
        checklist = CMSMigrationPlanner.generate_migration_checklist(
            "wordpress", "drupal"
        )
        assert len(checklist) > 0
        assert all('category' in item for item in checklist)
        assert all('task' in item for item in checklist)
        assert all('priority' in item for item in checklist)


class TestCMSValidator:
    """Test CMS validation and health checking."""
    
    @pytest.mark.asyncio
    async def test_health_checker(self, temp_cms_structure):
        """Test comprehensive health checking."""
        wp_dir = temp_cms_structure['wordpress']
        
        checker = CMSHealthChecker("wordpress", wp_dir)
        health_result = await checker.run_health_check()
        
        assert 'health_score' in health_result
        assert 'total_issues' in health_result
        assert 'severity_breakdown' in health_result
        assert 'issues' in health_result
        assert 'recommendations' in health_result
        
        assert 0 <= health_result['health_score'] <= 100
        assert health_result['total_issues'] >= 0
        
        # Check severity breakdown
        severity_breakdown = health_result['severity_breakdown']
        assert 'critical' in severity_breakdown
        assert 'error' in severity_breakdown
        assert 'warning' in severity_breakdown
        assert 'info' in severity_breakdown
    
    @pytest.mark.asyncio
    async def test_compatibility_checker(self):
        """Test migration compatibility checking."""
        # Test same-platform compatibility
        same_platform_result = await CMSCompatibilityChecker.check_migration_compatibility(
            "wordpress", "6.4.2", "wordpress", "6.4.3"
        )
        assert same_platform_result['compatible']
        assert same_platform_result['migration_complexity'] == 'simple'
        
        # Test cross-platform compatibility
        cross_platform_result = await CMSCompatibilityChecker.check_migration_compatibility(
            "wordpress", "6.4.2", "drupal", "10.1"
        )
        assert 'compatible' in cross_platform_result
        assert 'migration_complexity' in cross_platform_result
        assert 'estimated_success_rate' in cross_platform_result
        
        # Test incompatible platforms
        incompatible_result = await CMSCompatibilityChecker.check_migration_compatibility(
            "magento", "2.4", "ghost", "5.0"
        )
        assert not incompatible_result['compatible']
        assert len(incompatible_result['issues']) > 0


class TestMigrationOrchestrator:
    """Test migration orchestration."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_creation(self):
        """Test orchestrator creation and configuration."""
        config = {
            'max_concurrent_steps': 5,
            'retry_attempts': 3,
            'retry_delay': 30
        }
        
        orchestrator = CMSMigrationOrchestrator(config)
        assert orchestrator.max_concurrent_steps == 5
        assert orchestrator.retry_attempts == 3
        assert orchestrator.retry_delay == 30
    
    @pytest.mark.asyncio
    async def test_migration_plan_creation(self, temp_cms_structure):
        """Test migration plan creation."""
        orchestrator = CMSMigrationOrchestrator()
        
        plan = await orchestrator.create_migration_plan(
            source_platform="wordpress",
            destination_platform="wordpress",
            source_path=temp_cms_structure['wordpress'],
            destination_path=temp_cms_structure['temp_dir'] / "destination",
            options={'create_backup': True}
        )
        
        assert plan.id.startswith("migration_")
        assert plan.source_platform == "wordpress"
        assert plan.destination_platform == "wordpress"
        assert len(plan.steps) > 0
        assert plan.total_estimated_duration > 0
        
        # Check step structure
        for step in plan.steps:
            assert hasattr(step, 'id')
            assert hasattr(step, 'name')
            assert hasattr(step, 'stage')
            assert hasattr(step, 'estimated_duration')
            assert step.status == MigrationStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_migration_status(self, temp_cms_structure):
        """Test migration status tracking."""
        orchestrator = CMSMigrationOrchestrator()
        
        plan = await orchestrator.create_migration_plan(
            source_platform="wordpress",
            destination_platform="wordpress",
            source_path=temp_cms_structure['wordpress'],
            destination_path=temp_cms_structure['temp_dir'] / "destination"
        )
        
        status = await orchestrator.get_migration_status(plan.id)
        assert status['migration_id'] == plan.id
        assert status['source_platform'] == "wordpress"
        assert status['destination_platform'] == "wordpress"
        assert status['overall_progress'] == 0
        assert status['completed_steps'] == 0
        assert status['total_steps'] == len(plan.steps)


class TestPerformanceMonitoring:
    """Test performance monitoring and metrics."""
    
    @pytest.mark.asyncio
    async def test_performance_monitor_creation(self):
        """Test performance monitor creation."""
        monitor = CMSPerformanceMonitor("test_migration")
        assert monitor.migration_id == "test_migration"
        assert monitor.metrics.migration_id == "test_migration"
        assert not monitor.monitoring_active
    
    @pytest.mark.asyncio
    async def test_metrics_recording(self):
        """Test metrics recording functionality."""
        monitor = CMSPerformanceMonitor("test_migration")
        
        # Test step recording
        await monitor.record_step_start("test_step")
        await monitor.record_step_end("test_step", success=True)
        
        # Test file processing
        test_file = Path("/test/file.txt")
        await monitor.record_file_processed(test_file, 1024)
        
        assert monitor.metrics.total_files_processed == 1
        assert monitor.metrics.total_bytes_processed == 1024
        
        # Test database operations
        await monitor.record_database_operation("export", 100)
        assert monitor.metrics.database_records_processed == 100
        
        # Test error recording
        await monitor.record_error("test_error", "Test error message")
        assert monitor.metrics.errors_encountered == 1
        
        # Test warning recording
        await monitor.record_warning("test_warning", "Test warning message")
        assert monitor.metrics.warnings_encountered == 1
    
    @pytest.mark.asyncio
    async def test_performance_reporting(self):
        """Test performance report generation."""
        monitor = CMSPerformanceMonitor("test_migration")
        
        # Add some test data
        await monitor.record_file_processed(Path("/test1.txt"), 1024)
        await monitor.record_file_processed(Path("/test2.txt"), 2048)
        await monitor.record_database_operation("export", 50)
        
        # Generate report
        report = monitor.generate_performance_report()
        
        assert 'migration_id' in report
        assert 'overall_metrics' in report
        assert 'performance_statistics' in report
        assert 'recommendations' in report
        
        # Check performance statistics
        perf_stats = report['performance_statistics']
        assert 'files_per_second' in perf_stats
        assert 'error_rate_percent' in perf_stats
        assert 'performance_grade' in perf_stats
        
        # Performance grade should be A-F
        assert perf_stats['performance_grade'] in ['A', 'B', 'C', 'D', 'F']
    
    def test_metrics_collector(self):
        """Test metrics collection and aggregation."""
        collector = CMSMetricsCollector()
        
        # Create test metrics
        from migration_assistant.monitoring.cms_metrics import MigrationMetrics
        metrics1 = MigrationMetrics("migration_1", datetime.now())
        metrics1.total_files_processed = 100
        metrics1.total_bytes_processed = 1024 * 1024  # 1MB
        metrics1.end_time = datetime.now()
        
        metrics2 = MigrationMetrics("migration_2", datetime.now())
        metrics2.total_files_processed = 200
        metrics2.total_bytes_processed = 2 * 1024 * 1024  # 2MB
        metrics2.end_time = datetime.now()
        
        # Add metrics
        collector.add_migration_metrics(metrics1, "wordpress", True)
        collector.add_migration_metrics(metrics2, "wordpress", True)
        
        # Get statistics
        platform_stats = collector.get_platform_statistics()
        assert 'wordpress' in platform_stats
        
        wp_stats = platform_stats['wordpress']
        assert wp_stats['total_migrations'] == 2
        assert wp_stats['successful_migrations'] == 2
        assert wp_stats['total_files_processed'] == 300
        assert wp_stats['total_bytes_processed'] == 3 * 1024 * 1024
        
        # Get global statistics
        global_stats = collector.get_global_statistics()
        assert global_stats['total_migrations'] == 2
        assert global_stats['successful_migrations'] == 2
        assert global_stats['success_rate_percent'] == 100.0


class TestIntegration:
    """Test integration between different components."""
    
    @pytest.mark.asyncio
    async def test_full_detection_and_health_check(self, system_config, temp_cms_structure):
        """Test full detection and health check workflow."""
        wp_dir = temp_cms_structure['wordpress']
        
        # 1. Detect platform
        adapter = await PlatformAdapterFactory.detect_platform(wp_dir, system_config)
        assert adapter is not None
        assert adapter.platform_type == "wordpress"
        
        # 2. Analyze platform
        platform_info = await adapter.analyze_platform(wp_dir)
        assert platform_info.platform_type == "wordpress"
        assert platform_info.version == "6.4.2"
        
        # 3. Health check
        checker = CMSHealthChecker(adapter.platform_type, wp_dir)
        health_result = await checker.run_health_check()
        assert health_result['platform'] == "wordpress"
        assert 0 <= health_result['health_score'] <= 100
    
    @pytest.mark.asyncio
    async def test_migration_workflow_integration(self, temp_cms_structure):
        """Test complete migration workflow integration."""
        # 1. Create orchestrator
        orchestrator = CMSMigrationOrchestrator({
            'max_concurrent_steps': 2,
            'retry_attempts': 1
        })
        
        # 2. Create migration plan
        plan = await orchestrator.create_migration_plan(
            source_platform="wordpress",
            destination_platform="wordpress",
            source_path=temp_cms_structure['wordpress'],
            destination_path=temp_cms_structure['temp_dir'] / "destination",
            options={'create_backup': False}  # Skip backup for testing
        )
        
        # 3. Check initial status
        status = await orchestrator.get_migration_status(plan.id)
        assert status['overall_progress'] == 0
        assert status['completed_steps'] == 0
        
        # 4. Test migration control
        await orchestrator.pause_migration(plan.id)
        await orchestrator.resume_migration(plan.id)
        await orchestrator.cancel_migration(plan.id)
        
        # Check that steps are cancelled
        final_status = await orchestrator.get_migration_status(plan.id)
        cancelled_steps = [s for s in final_status['steps'] if s['status'] == 'cancelled']
        assert len(cancelled_steps) > 0


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_platform_creation(self, system_config):
        """Test error handling for invalid platform types."""
        with pytest.raises(Exception):  # Should raise PlatformError
            PlatformAdapterFactory.create_adapter("invalid_platform", system_config)
    
    @pytest.mark.asyncio
    async def test_detection_on_nonexistent_path(self, system_config):
        """Test detection on non-existent paths."""
        nonexistent_path = Path("/nonexistent/path")
        adapter = await PlatformAdapterFactory.detect_platform(nonexistent_path, system_config)
        assert adapter is None
    
    @pytest.mark.asyncio
    async def test_health_check_on_invalid_path(self):
        """Test health check on invalid paths."""
        checker = CMSHealthChecker("wordpress", Path("/nonexistent"))
        health_result = await checker.run_health_check()
        
        # Should handle gracefully and return issues
        assert health_result['health_score'] < 100
        assert health_result['total_issues'] > 0
    
    def test_version_parser_edge_cases(self):
        """Test version parser with edge cases."""
        # Empty version
        assert CMSVersionParser.parse_version("") == (0,)
        
        # Version with letters
        assert CMSVersionParser.parse_version("v6.4.2-beta") == (6, 4, 2)
        
        # Invalid version
        assert CMSVersionParser.parse_version("invalid.version") == (0,)
        
        # Single number
        assert CMSVersionParser.parse_version("6") == (6,)


class TestPerformanceAndScalability:
    """Test performance and scalability aspects."""
    
    @pytest.mark.asyncio
    async def test_concurrent_platform_detection(self, system_config, temp_cms_structure):
        """Test concurrent platform detection."""
        paths = [
            temp_cms_structure['wordpress'],
            temp_cms_structure['magento'],
            temp_cms_structure['ghost']
        ]
        
        # Run detections concurrently
        tasks = [
            PlatformAdapterFactory.detect_platform(path, system_config)
            for path in paths
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(result is not None for result in results)
        assert results[0].platform_type == "wordpress"
        assert results[1].platform_type == "magento"
        assert results[2].platform_type == "ghost"
    
    @pytest.mark.asyncio
    async def test_large_file_analysis(self, temp_cms_structure):
        """Test file analysis with larger directory structures."""
        wp_dir = temp_cms_structure['wordpress']
        
        # Create many test files
        test_files_dir = wp_dir / "test_files"
        test_files_dir.mkdir()
        
        for i in range(100):
            test_file = test_files_dir / f"test_file_{i}.txt"
            test_file.write_text(f"Test content {i}" * 100)  # Make files larger
        
        # Analyze directory
        stats = CMSFileAnalyzer.analyze_directory_structure(wp_dir)
        
        assert stats['total_files'] >= 100
        assert stats['total_size'] > 0
        assert len(stats['largest_files']) > 0
    
    def test_memory_usage_monitoring(self):
        """Test memory usage during operations."""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Create many objects
        monitors = []
        for i in range(100):
            monitor = CMSPerformanceMonitor(f"test_{i}")
            monitors.append(monitor)
        
        # Check memory increase is reasonable
        current_memory = process.memory_info().rss
        memory_increase = current_memory - initial_memory
        
        # Should not increase by more than 50MB for 100 monitors
        assert memory_increase < 50 * 1024 * 1024
        
        # Cleanup
        del monitors
        gc.collect()


@pytest.mark.asyncio
async def test_full_system_integration(system_config, temp_cms_structure):
    """Test complete system integration from detection to monitoring."""
    
    print("\n🚀 Running Full System Integration Test")
    
    # 1. Platform Detection
    print("1️⃣ Testing Platform Detection...")
    wp_dir = temp_cms_structure['wordpress']
    adapter = await PlatformAdapterFactory.detect_platform(wp_dir, system_config)
    assert adapter is not None
    print(f"   ✅ Detected: {adapter.platform_type}")
    
    # 2. Platform Analysis
    print("2️⃣ Testing Platform Analysis...")
    platform_info = await adapter.analyze_platform(wp_dir)
    dependencies = await adapter.get_dependencies()
    env_config = await adapter.get_environment_config(wp_dir)
    print(f"   ✅ Version: {platform_info.version}")
    print(f"   ✅ Dependencies: {len(dependencies)}")
    print(f"   ✅ Config files: {len(platform_info.config_files)}")
    
    # 3. Health Check
    print("3️⃣ Testing Health Check...")
    checker = CMSHealthChecker(adapter.platform_type, wp_dir)
    health_result = await checker.run_health_check()
    print(f"   ✅ Health Score: {health_result['health_score']}/100")
    print(f"   ✅ Issues: {health_result['total_issues']}")
    
    # 4. Compatibility Check
    print("4️⃣ Testing Compatibility Check...")
    compatibility = await CMSCompatibilityChecker.check_migration_compatibility(
        adapter.platform_type, platform_info.version,
        adapter.platform_type, platform_info.version
    )
    print(f"   ✅ Compatible: {compatibility['compatible']}")
    print(f"   ✅ Success Rate: {compatibility['estimated_success_rate']}%")
    
    # 5. Migration Planning
    print("5️⃣ Testing Migration Planning...")
    orchestrator = CMSMigrationOrchestrator()
    plan = await orchestrator.create_migration_plan(
        source_platform=adapter.platform_type,
        destination_platform=adapter.platform_type,
        source_path=wp_dir,
        destination_path=temp_cms_structure['temp_dir'] / "destination",
        options={'create_backup': False}
    )
    print(f"   ✅ Migration Plan: {plan.id}")
    print(f"   ✅ Steps: {len(plan.steps)}")
    print(f"   ✅ Estimated Duration: {plan.total_estimated_duration // 60}m")
    
    # 6. Performance Monitoring Setup
    print("6️⃣ Testing Performance Monitoring...")
    monitor = CMSPerformanceMonitor(plan.id)
    
    # Simulate some activity
    await monitor.record_step_start("test_step")
    await monitor.record_file_processed(Path("test.txt"), 1024)
    await monitor.record_database_operation("export", 100)
    await monitor.record_step_end("test_step", success=True)
    
    metrics = monitor.get_current_metrics()
    print(f"   ✅ Files Processed: {metrics['files_processed']}")
    print(f"   ✅ DB Records: {metrics['database_records']}")
    
    # 7. Generate Performance Report
    print("7️⃣ Testing Performance Reporting...")
    report = monitor.generate_performance_report()
    print(f"   ✅ Performance Grade: {report['performance_statistics']['performance_grade']}")
    print(f"   ✅ Recommendations: {len(report['recommendations'])}")
    
    # 8. Migration Status
    print("8️⃣ Testing Migration Status...")
    status = await orchestrator.get_migration_status(plan.id)
    print(f"   ✅ Migration ID: {status['migration_id']}")
    print(f"   ✅ Total Steps: {status['total_steps']}")
    print(f"   ✅ Current Stage: {status['current_stage']}")
    
    print("\n🎉 Full System Integration Test Completed Successfully!")
    print("   All components working together correctly!")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])