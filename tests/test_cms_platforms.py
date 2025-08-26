"""
Tests for CMS platform adapters.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from migration_assistant.platforms.factory import PlatformAdapterFactory
from migration_assistant.platforms.cms import (
    WordPressAdapter, DrupalAdapter, JoomlaAdapter, MagentoAdapter,
    ShopwareAdapter, PrestaShopAdapter, OpenCartAdapter, GhostAdapter,
    CraftCMSAdapter, Typo3Adapter, Concrete5Adapter, UmbracoAdapter
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
            assert platform in platforms
    
    def test_create_cms_adapters(self, system_config):
        """Test creating CMS adapters."""
        cms_platforms = [
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
        
        for platform_type, expected_class in cms_platforms:
            adapter = PlatformAdapterFactory.create_adapter(platform_type, system_config)
            assert isinstance(adapter, expected_class)
            assert adapter.platform_type == platform_type
    
    def test_cms_compatibility_matrix(self):
        """Test CMS platform compatibility."""
        # Test e-commerce platform compatibility
        ecommerce_platforms = ["magento", "shopware", "prestashop", "opencart"]
        for source in ecommerce_platforms:
            for dest in ecommerce_platforms:
                assert PlatformAdapterFactory.validate_platform_compatibility(source, dest)
        
        # Test CMS to CMS compatibility
        assert PlatformAdapterFactory.validate_platform_compatibility("wordpress", "drupal")
        assert PlatformAdapterFactory.validate_platform_compatibility("ghost", "wordpress")
        assert PlatformAdapterFactory.validate_platform_compatibility("craftcms", "ghost")
        
        # Test incompatible migrations
        assert not PlatformAdapterFactory.validate_platform_compatibility("magento", "ghost")
        assert not PlatformAdapterFactory.validate_platform_compatibility("umbraco", "shopware")


class TestWordPressAdapter:
    """Test WordPress adapter."""
    
    @pytest.fixture
    def wordpress_adapter(self, system_config):
        return WordPressAdapter(system_config)
    
    def test_wordpress_detection(self, wordpress_adapter):
        """Test WordPress detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create WordPress structure
            (temp_path / "wp-config.php").touch()
            (temp_path / "wp-includes").mkdir()
            (temp_path / "wp-admin").mkdir()
            
            # Should detect WordPress
            result = asyncio.run(wordpress_adapter.detect_platform(temp_path))
            assert result is True
            
            # Remove required file
            (temp_path / "wp-config.php").unlink()
            result = asyncio.run(wordpress_adapter.detect_platform(temp_path))
            assert result is False


class TestMagentoAdapter:
    """Test Magento adapter."""
    
    @pytest.fixture
    def magento_adapter(self, system_config):
        return MagentoAdapter(system_config)
    
    def test_magento_detection(self, magento_adapter):
        """Test Magento detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Magento structure
            (temp_path / "app").mkdir()
            (temp_path / "app" / "etc").mkdir()
            (temp_path / "bin").mkdir()
            (temp_path / "lib").mkdir()
            (temp_path / "pub").mkdir()
            (temp_path / "var").mkdir()
            (temp_path / "app" / "etc" / "env.php").touch()
            
            # Should detect Magento
            result = asyncio.run(magento_adapter.detect_platform(temp_path))
            assert result is True


class TestGhostAdapter:
    """Test Ghost adapter."""
    
    @pytest.fixture
    def ghost_adapter(self, system_config):
        return GhostAdapter(system_config)
    
    def test_ghost_detection_with_package_json(self, ghost_adapter):
        """Test Ghost detection with package.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Ghost package.json
            package_json = {
                "name": "ghost",
                "version": "5.0.0",
                "description": "The professional publishing platform"
            }
            
            (temp_path / "package.json").write_text(json.dumps(package_json))
            
            # Should detect Ghost
            result = asyncio.run(ghost_adapter.detect_platform(temp_path))
            assert result is True
    
    def test_ghost_detection_with_binary(self, ghost_adapter):
        """Test Ghost detection with ghost binary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create ghost binary
            (temp_path / "ghost").touch()
            
            # Should detect Ghost
            result = asyncio.run(ghost_adapter.detect_platform(temp_path))
            assert result is True


class TestShopwareAdapter:
    """Test Shopware adapter."""
    
    @pytest.fixture
    def shopware_adapter(self, system_config):
        return ShopwareAdapter(system_config)
    
    def test_shopware_detection_composer(self, shopware_adapter):
        """Test Shopware detection with composer.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Shopware composer.json
            composer_json = {
                "require": {
                    "shopware/core": "^6.4.0"
                }
            }
            
            (temp_path / "composer.json").write_text(json.dumps(composer_json))
            
            # Should detect Shopware
            result = asyncio.run(shopware_adapter.detect_platform(temp_path))
            assert result is True
    
    def test_shopware_detection_legacy(self, shopware_adapter):
        """Test Shopware 5 detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Shopware 5 structure
            (temp_path / "shopware.php").touch()
            
            # Should detect Shopware
            result = asyncio.run(shopware_adapter.detect_platform(temp_path))
            assert result is True


class TestCraftCMSAdapter:
    """Test Craft CMS adapter."""
    
    @pytest.fixture
    def craftcms_adapter(self, system_config):
        return CraftCMSAdapter(system_config)
    
    def test_craftcms_detection_composer(self, craftcms_adapter):
        """Test Craft CMS detection with composer.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Craft CMS composer.json
            composer_json = {
                "require": {
                    "craftcms/cms": "^4.0.0"
                }
            }
            
            (temp_path / "composer.json").write_text(json.dumps(composer_json))
            
            # Should detect Craft CMS
            result = asyncio.run(craftcms_adapter.detect_platform(temp_path))
            assert result is True
    
    def test_craftcms_detection_binary(self, craftcms_adapter):
        """Test Craft CMS detection with craft binary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create craft binary
            (temp_path / "craft").touch()
            
            # Should detect Craft CMS
            result = asyncio.run(craftcms_adapter.detect_platform(temp_path))
            assert result is True


class TestUmbracoAdapter:
    """Test Umbraco adapter."""
    
    @pytest.fixture
    def umbraco_adapter(self, system_config):
        return UmbracoAdapter(system_config)
    
    def test_umbraco_detection_web_config(self, umbraco_adapter):
        """Test Umbraco detection with web.config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create web.config with Umbraco reference
            web_config = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <appSettings>
    <add key="Umbraco.Core.ConfigurationStatus" value="8.0.0" />
  </appSettings>
</configuration>"""
            
            (temp_path / "web.config").write_text(web_config)
            
            # Should detect Umbraco
            result = asyncio.run(umbraco_adapter.detect_platform(temp_path))
            assert result is True
    
    def test_umbraco_detection_directory(self, umbraco_adapter):
        """Test Umbraco detection with umbraco directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create umbraco directory
            (temp_path / "umbraco").mkdir()
            
            # Should detect Umbraco
            result = asyncio.run(umbraco_adapter.detect_platform(temp_path))
            assert result is True


class TestDependencyManagement:
    """Test dependency management for CMS platforms."""
    
    @pytest.mark.asyncio
    async def test_wordpress_dependencies(self, system_config):
        """Test WordPress dependency requirements."""
        adapter = WordPressAdapter(system_config)
        dependencies = await adapter.get_dependencies()
        
        # Check required dependencies
        dep_names = [dep.name for dep in dependencies]
        assert "php" in dep_names
        assert "mysql" in dep_names
        
        # Check PHP version requirement
        php_dep = next(dep for dep in dependencies if dep.name == "php")
        assert php_dep.version == ">=7.4"
        assert php_dep.required is True
    
    @pytest.mark.asyncio
    async def test_magento_dependencies(self, system_config):
        """Test Magento dependency requirements."""
        adapter = MagentoAdapter(system_config)
        dependencies = await adapter.get_dependencies()
        
        # Check required dependencies
        dep_names = [dep.name for dep in dependencies]
        assert "php" in dep_names
        assert "mysql" in dep_names
        assert "elasticsearch" in dep_names
        assert "composer" in dep_names
        
        # Check Elasticsearch requirement
        es_dep = next(dep for dep in dependencies if dep.name == "elasticsearch")
        assert es_dep.version == ">=7.0"
        assert es_dep.required is True
    
    @pytest.mark.asyncio
    async def test_ghost_dependencies(self, system_config):
        """Test Ghost dependency requirements."""
        adapter = GhostAdapter(system_config)
        dependencies = await adapter.get_dependencies()
        
        # Check required dependencies
        dep_names = [dep.name for dep in dependencies]
        assert "nodejs" in dep_names
        assert "npm" in dep_names
        
        # Check Node.js version requirement
        node_dep = next(dep for dep in dependencies if dep.name == "nodejs")
        assert node_dep.version == ">=14"
        assert node_dep.required is True


if __name__ == "__main__":
    import asyncio
    pytest.main([__file__])