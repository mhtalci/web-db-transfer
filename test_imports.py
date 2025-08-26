#!/usr/bin/env python3
"""
Test basic imports to verify all modules are working correctly.
"""

import sys
from pathlib import Path

def test_basic_imports():
    """Test basic module imports."""
    print("🔍 Testing Basic Module Imports...")
    
    try:
        # Test platform factory
        from migration_assistant.platforms.factory import PlatformAdapterFactory
        print("  ✅ PlatformAdapterFactory imported successfully")
        
        # Test CMS adapters
        from migration_assistant.platforms.cms import (
            WordPressAdapter, DrupalAdapter, JoomlaAdapter, MagentoAdapter
        )
        print("  ✅ CMS adapters imported successfully")
        
        # Test exceptions
        from migration_assistant.core.cms_exceptions import CMSError, CMSDetectionError
        print("  ✅ CMS exceptions imported successfully")
        
        # Test utilities
        from migration_assistant.utils.cms_utils import CMSVersionParser, CMSFileAnalyzer
        print("  ✅ CMS utilities imported successfully")
        
        # Test validators
        from migration_assistant.validators.cms_validator import CMSHealthChecker
        print("  ✅ CMS validators imported successfully")
        
        # Test orchestrator
        from migration_assistant.orchestrators.cms_migration_orchestrator import CMSMigrationOrchestrator
        print("  ✅ Migration orchestrator imported successfully")
        
        # Test monitoring
        from migration_assistant.monitoring.cms_metrics import CMSPerformanceMonitor
        print("  ✅ Performance monitoring imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False


def test_platform_creation():
    """Test creating platform adapters."""
    print("\n🏭 Testing Platform Adapter Creation...")
    
    try:
        from migration_assistant.platforms.factory import PlatformAdapterFactory
        from migration_assistant.models.config import SystemConfig, DatabaseConfig
        
        # Create basic config
        config = SystemConfig(
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
        
        # Test creating different adapters
        platforms_to_test = ["wordpress", "drupal", "magento", "ghost"]
        
        for platform in platforms_to_test:
            adapter = PlatformAdapterFactory.create_adapter(platform, config)
            assert adapter.platform_type == platform
            print(f"  ✅ {platform} adapter created successfully")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Platform creation failed: {e}")
        return False


def test_utility_functions():
    """Test utility functions."""
    print("\n🔧 Testing Utility Functions...")
    
    try:
        from migration_assistant.utils.cms_utils import CMSVersionParser
        
        # Test version parsing
        version = CMSVersionParser.parse_version("6.4.2")
        assert version == (6, 4, 2)
        print("  ✅ Version parsing works correctly")
        
        # Test version comparison
        result = CMSVersionParser.compare_versions("6.4.2", "6.4.1")
        assert result == 1
        print("  ✅ Version comparison works correctly")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Utility function test failed: {e}")
        return False


def test_exception_handling():
    """Test exception classes."""
    print("\n⚠️  Testing Exception Handling...")
    
    try:
        from migration_assistant.core.cms_exceptions import (
            CMSDetectionError, CMSVersionError, CMSMigrationError
        )
        
        # Test creating exceptions
        detection_error = CMSDetectionError("/test/path", ["wordpress", "drupal"])
        assert "/test/path" in str(detection_error)
        print("  ✅ CMSDetectionError works correctly")
        
        version_error = CMSVersionError("wordpress", "3.0", ["4.0", "5.0"])
        assert "version 3.0 is not supported" in str(version_error)
        print("  ✅ CMSVersionError works correctly")
        
        migration_error = CMSMigrationError("wordpress", "drupal", "export", "Test error")
        assert "Migration failed" in str(migration_error)
        print("  ✅ CMSMigrationError works correctly")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Exception handling test failed: {e}")
        return False


def main():
    """Run all import tests."""
    print("🚀 CMS Migration Assistant - Import Test Suite")
    print("=" * 60)
    
    tests = [
        ("Basic Imports", test_basic_imports),
        ("Platform Creation", test_platform_creation),
        ("Utility Functions", test_utility_functions),
        ("Exception Handling", test_exception_handling)
    ]
    
    all_passed = True
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            if not success:
                all_passed = False
        except Exception as e:
            print(f"  ❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
            all_passed = False
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 IMPORT TEST SUMMARY")
    print("=" * 60)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:<20} {status}")
    
    if all_passed:
        print(f"\n🎉 ALL IMPORT TESTS PASSED!")
        print("   All modules are properly importable and functional!")
    else:
        print(f"\n⚠️  SOME IMPORT TESTS FAILED")
        print("   Please check the error messages above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())