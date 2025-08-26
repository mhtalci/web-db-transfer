"""
CMS platform adapters for WordPress, Drupal, Joomla, and other content management systems.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET

from .base import PlatformAdapter, PlatformInfo, DependencyInfo, EnvironmentConfig
from ..models.config import SystemConfig
from ..core.exceptions import PlatformError


class CMSAdapter(PlatformAdapter):
    """Base adapter for Content Management Systems."""
    
    @property
    def platform_type(self) -> str:
        return "cms"
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from CMS config files."""
        return {}
    
    async def get_theme_info(self, path: Path) -> Dict[str, Any]:
        """Get information about installed themes."""
        return {}
    
    async def get_plugin_info(self, path: Path) -> Dict[str, Any]:
        """Get information about installed plugins/modules."""
        return {}


class WordPressAdapter(CMSAdapter):
    """Adapter for WordPress CMS."""
    
    @property
    def platform_type(self) -> str:
        return "wordpress"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["4.0", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", 
                "5.0", "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9",
                "6.0", "6.1", "6.2", "6.3", "6.4", "6.5"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect WordPress installation."""
        wp_config = path / "wp-config.php"
        wp_includes = path / "wp-includes"
        wp_admin = path / "wp-admin"
        
        return wp_config.exists() and wp_includes.is_dir() and wp_admin.is_dir()
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze WordPress installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"WordPress not detected at {path}")
        
        # Get WordPress version
        version = await self._get_wordpress_version(path)
        
        # Get database configuration
        db_config = await self.get_database_config(path)
        
        # Get themes and plugins
        themes = await self.get_theme_info(path)
        plugins = await self.get_plugin_info(path)
        
        # Get environment variables from wp-config.php
        env_vars = await self._extract_wp_config_vars(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="wordpress",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql", "apache2"],
            config_files=["wp-config.php", ".htaccess"],
            environment_variables=env_vars
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get WordPress dependencies."""
        return [
            DependencyInfo(
                name="php",
                version=">=7.4",
                required=True,
                install_command="apt-get install php"
            ),
            DependencyInfo(
                name="mysql",
                version=">=5.7",
                required=True,
                install_command="apt-get install mysql-server"
            ),
            DependencyInfo(
                name="apache2",
                required=False,
                install_command="apt-get install apache2"
            ),
            DependencyInfo(
                name="nginx",
                required=False,
                install_command="apt-get install nginx"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract WordPress environment configuration."""
        env_vars = await self._extract_wp_config_vars(path)
        
        config_files = []
        for file_name in ["wp-config.php", ".htaccess", "wp-config-sample.php"]:
            if (path / file_name).exists():
                config_files.append(file_name)
        
        secrets = ["DB_PASSWORD", "AUTH_KEY", "SECURE_AUTH_KEY", "LOGGED_IN_KEY", 
                  "NONCE_KEY", "AUTH_SALT", "SECURE_AUTH_SALT", "LOGGED_IN_SALT", "NONCE_SALT"]
        
        return EnvironmentConfig(
            variables=env_vars,
            files=config_files,
            secrets=secrets
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare WordPress migration."""
        # Analyze source
        platform_info = await self.analyze_platform(source_path)
        
        # Get database configuration
        db_config = await self.get_database_config(source_path)
        
        # Get themes and plugins
        themes = await self.get_theme_info(source_path)
        plugins = await self.get_plugin_info(source_path)
        
        # Prepare migration steps
        migration_steps = [
            "backup_database",
            "export_content",
            "copy_themes",
            "copy_plugins",
            "copy_uploads",
            "update_config",
            "update_urls"
        ]
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "themes": themes,
            "plugins": plugins,
            "migration_steps": migration_steps,
            "files_to_copy": [
                "wp-content/themes",
                "wp-content/plugins",
                "wp-content/uploads",
                "wp-config.php",
                ".htaccess"
            ]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform WordPress post-migration setup."""
        try:
            # Update wp-config.php with new database settings
            await self._update_wp_config(destination_path, migration_info.get("database_config", {}))
            
            # Update file permissions
            await self._set_wordpress_permissions(destination_path)
            
            # Clear cache if cache plugins are detected
            await self._clear_wordpress_cache(destination_path)
            
            return True
        except Exception as e:
            self.logger.error(f"WordPress post-migration setup failed: {e}")
            return False
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from wp-config.php."""
        wp_config = path / "wp-config.php"
        if not wp_config.exists():
            return {}
        
        try:
            content = wp_config.read_text(encoding='utf-8')
            
            # Extract database constants
            db_config = {}
            patterns = {
                'host': r"define\s*\(\s*['\"]DB_HOST['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'name': r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'user': r"define\s*\(\s*['\"]DB_USER['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'password': r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'charset': r"define\s*\(\s*['\"]DB_CHARSET['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'prefix': r"\$table_prefix\s*=\s*['\"]([^'\"]+)['\"]"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    db_config[key] = match.group(1)
            
            db_config['type'] = 'mysql'  # WordPress uses MySQL
            return db_config
            
        except Exception as e:
            self.logger.error(f"Failed to parse wp-config.php: {e}")
            return {}
    
    async def get_theme_info(self, path: Path) -> Dict[str, Any]:
        """Get WordPress theme information."""
        themes_path = path / "wp-content" / "themes"
        if not themes_path.exists():
            return {}
        
        themes = {}
        for theme_dir in themes_path.iterdir():
            if theme_dir.is_dir():
                style_css = theme_dir / "style.css"
                if style_css.exists():
                    theme_info = await self._parse_theme_header(style_css)
                    themes[theme_dir.name] = theme_info
        
        return themes
    
    async def get_plugin_info(self, path: Path) -> Dict[str, Any]:
        """Get WordPress plugin information."""
        plugins_path = path / "wp-content" / "plugins"
        if not plugins_path.exists():
            return {}
        
        plugins = {}
        for plugin_item in plugins_path.iterdir():
            if plugin_item.is_dir():
                # Look for main plugin file
                for php_file in plugin_item.glob("*.php"):
                    plugin_info = await self._parse_plugin_header(php_file)
                    if plugin_info:
                        plugins[plugin_item.name] = plugin_info
                        break
            elif plugin_item.suffix == ".php":
                # Single file plugin
                plugin_info = await self._parse_plugin_header(plugin_item)
                if plugin_info:
                    plugins[plugin_item.stem] = plugin_info
        
        return plugins
    
    async def _get_wordpress_version(self, path: Path) -> Optional[str]:
        """Extract WordPress version."""
        version_file = path / "wp-includes" / "version.php"
        if not version_file.exists():
            return None
        
        try:
            content = version_file.read_text(encoding='utf-8')
            match = re.search(r"\$wp_version\s*=\s*['\"]([^'\"]+)['\"]", content)
            return match.group(1) if match else None
        except Exception:
            return None
    
    async def _extract_wp_config_vars(self, path: Path) -> Dict[str, str]:
        """Extract environment variables from wp-config.php."""
        wp_config = path / "wp-config.php"
        if not wp_config.exists():
            return {}
        
        try:
            content = wp_config.read_text(encoding='utf-8')
            env_vars = {}
            
            # Extract define statements
            define_pattern = r"define\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
            for match in re.finditer(define_pattern, content, re.IGNORECASE):
                key, value = match.groups()
                env_vars[key] = value
            
            return env_vars
        except Exception:
            return {}
    
    async def _parse_theme_header(self, style_css: Path) -> Dict[str, Any]:
        """Parse WordPress theme header information."""
        try:
            content = style_css.read_text(encoding='utf-8')
            
            # Extract theme information from header comment
            header_pattern = r"/\*\*(.*?)\*/"
            match = re.search(header_pattern, content, re.DOTALL)
            if not match:
                return {}
            
            header = match.group(1)
            theme_info = {}
            
            patterns = {
                'name': r"Theme Name:\s*(.+)",
                'version': r"Version:\s*(.+)",
                'description': r"Description:\s*(.+)",
                'author': r"Author:\s*(.+)",
                'template': r"Template:\s*(.+)"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, header, re.IGNORECASE)
                if match:
                    theme_info[key] = match.group(1).strip()
            
            return theme_info
        except Exception:
            return {}
    
    async def _parse_plugin_header(self, plugin_file: Path) -> Optional[Dict[str, Any]]:
        """Parse WordPress plugin header information."""
        try:
            content = plugin_file.read_text(encoding='utf-8')
            
            # Look for plugin header
            if "Plugin Name:" not in content:
                return None
            
            header_pattern = r"/\*\*(.*?)\*/"
            match = re.search(header_pattern, content, re.DOTALL)
            if not match:
                return None
            
            header = match.group(1)
            plugin_info = {}
            
            patterns = {
                'name': r"Plugin Name:\s*(.+)",
                'version': r"Version:\s*(.+)",
                'description': r"Description:\s*(.+)",
                'author': r"Author:\s*(.+)",
                'requires': r"Requires at least:\s*(.+)",
                'tested': r"Tested up to:\s*(.+)"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, header, re.IGNORECASE)
                if match:
                    plugin_info[key] = match.group(1).strip()
            
            return plugin_info
        except Exception:
            return None
    
    async def _update_wp_config(self, path: Path, db_config: Dict[str, Any]) -> None:
        """Update wp-config.php with new database configuration."""
        wp_config = path / "wp-config.php"
        if not wp_config.exists():
            return
        
        try:
            content = wp_config.read_text(encoding='utf-8')
            
            # Update database constants
            replacements = {
                'DB_HOST': db_config.get('host', 'localhost'),
                'DB_NAME': db_config.get('name', ''),
                'DB_USER': db_config.get('user', ''),
                'DB_PASSWORD': db_config.get('password', '')
            }
            
            for const, value in replacements.items():
                pattern = rf"(define\s*\(\s*['\"]){const}(['\"]\s*,\s*['\"])[^'\"]*(['\"])"
                replacement = rf"\1{const}\2{value}\3"
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            
            wp_config.write_text(content, encoding='utf-8')
        except Exception as e:
            self.logger.error(f"Failed to update wp-config.php: {e}")
    
    async def _set_wordpress_permissions(self, path: Path) -> None:
        """Set proper WordPress file permissions."""
        import os
        import stat
        
        try:
            # Set directory permissions to 755
            for root, dirs, files in os.walk(path):
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    dir_path.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                
                # Set file permissions to 644
                for file_name in files:
                    file_path = Path(root) / file_name
                    file_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            
            # Set wp-config.php to 600 for security
            wp_config = path / "wp-config.php"
            if wp_config.exists():
                wp_config.chmod(stat.S_IRUSR | stat.S_IWUSR)
                
        except Exception as e:
            self.logger.error(f"Failed to set WordPress permissions: {e}")
    
    async def _clear_wordpress_cache(self, path: Path) -> None:
        """Clear WordPress cache if cache plugins are detected."""
        cache_dirs = [
            path / "wp-content" / "cache",
            path / "wp-content" / "w3tc-cache",
            path / "wp-content" / "wp-rocket-cache"
        ]
        
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(cache_dir)
                    self.logger.info(f"Cleared cache directory: {cache_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to clear cache directory {cache_dir}: {e}")


class DrupalAdapter(CMSAdapter):
    """Adapter for Drupal CMS."""
    
    @property
    def platform_type(self) -> str:
        return "drupal"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["7.0", "8.0", "8.1", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8", "8.9",
                "9.0", "9.1", "9.2", "9.3", "9.4", "9.5", "10.0", "10.1"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Drupal installation."""
        # Check for Drupal 8+ (composer-based)
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                if "drupal/core" in content.get("require", {}):
                    return True
            except Exception:
                pass
        
        # Check for Drupal 7 and earlier
        index_php = path / "index.php"
        if index_php.exists():
            try:
                content = index_php.read_text()
                if "drupal_bootstrap" in content or "DRUPAL_ROOT" in content:
                    return True
            except Exception:
                pass
        
        # Check for common Drupal directories
        drupal_dirs = ["sites", "modules", "themes", "includes"]
        return all((path / d).exists() for d in drupal_dirs)
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Drupal installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Drupal not detected at {path}")
        
        version = await self._get_drupal_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="drupal",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql", "apache2"],
            config_files=["sites/default/settings.php", ".htaccess"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Drupal dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.4", required=True),
            DependencyInfo(name="mysql", version=">=5.7", required=True),
            DependencyInfo(name="composer", required=True),
            DependencyInfo(name="drush", required=False)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Drupal environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["sites/default/settings.php", ".htaccess"],
            secrets=["database_password", "hash_salt"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Drupal migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_settings"],
            "files_to_copy": ["sites", "modules", "themes", "libraries"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Drupal post-migration setup."""
        try:
            # Update settings.php
            await self._update_drupal_settings(destination_path, migration_info.get("database_config", {}))
            return True
        except Exception as e:
            self.logger.error(f"Drupal post-migration setup failed: {e}")
            return False
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Drupal settings."""
        settings_file = path / "sites" / "default" / "settings.php"
        if not settings_file.exists():
            return {}
        
        try:
            content = settings_file.read_text()
            # This is a simplified parser - real implementation would be more robust
            db_config = {}
            
            # Look for database array configuration
            if "$databases" in content:
                # Extract database configuration (simplified)
                patterns = {
                    'host': r"'host'\s*=>\s*'([^']+)'",
                    'database': r"'database'\s*=>\s*'([^']+)'",
                    'username': r"'username'\s*=>\s*'([^']+)'",
                    'password': r"'password'\s*=>\s*'([^']+)'",
                    'driver': r"'driver'\s*=>\s*'([^']+)'"
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, content)
                    if match:
                        db_config[key] = match.group(1)
            
            return db_config
        except Exception:
            return {}
    
    async def _get_drupal_version(self, path: Path) -> Optional[str]:
        """Get Drupal version."""
        # Try composer.json first (Drupal 8+)
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                drupal_core = content.get("require", {}).get("drupal/core")
                if drupal_core:
                    return drupal_core.strip("^~")
            except Exception:
                pass
        
        # Try system.info for Drupal 7
        system_info = path / "modules" / "system" / "system.info"
        if system_info.exists():
            try:
                content = system_info.read_text()
                match = re.search(r"version\s*=\s*['\"]?([^'\"]+)['\"]?", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        return None
    
    async def _update_drupal_settings(self, path: Path, db_config: Dict[str, Any]) -> None:
        """Update Drupal settings.php with new database configuration."""
        settings_file = path / "sites" / "default" / "settings.php"
        if not settings_file.exists():
            return
        
        # This would need a more sophisticated implementation
        # to properly update Drupal's database configuration
        pass


class JoomlaAdapter(CMSAdapter):
    """Adapter for Joomla CMS."""
    
    @property
    def platform_type(self) -> str:
        return "joomla"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["3.0", "3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "3.10",
                "4.0", "4.1", "4.2", "4.3", "4.4", "5.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Joomla installation."""
        config_file = path / "configuration.php"
        if not config_file.exists():
            return False
        
        try:
            content = config_file.read_text()
            return "JConfig" in content and "class JConfig" in content
        except Exception:
            return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Joomla installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Joomla not detected at {path}")
        
        version = await self._get_joomla_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="joomla",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql", "apache2"],
            config_files=["configuration.php", ".htaccess"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Joomla dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.2", required=True),
            DependencyInfo(name="mysql", version=">=5.6", required=True),
            DependencyInfo(name="apache2", required=False)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Joomla environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["configuration.php", ".htaccess"],
            secrets=["password", "secret"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Joomla migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_configuration"],
            "files_to_copy": ["administrator", "components", "modules", "plugins", "templates", "images"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Joomla post-migration setup."""
        try:
            await self._update_joomla_config(destination_path, migration_info.get("database_config", {}))
            return True
        except Exception as e:
            self.logger.error(f"Joomla post-migration setup failed: {e}")
            return False
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Joomla configuration.php."""
        config_file = path / "configuration.php"
        if not config_file.exists():
            return {}
        
        try:
            content = config_file.read_text()
            db_config = {}
            
            patterns = {
                'host': r"\$host\s*=\s*['\"]([^'\"]+)['\"]",
                'user': r"\$user\s*=\s*['\"]([^'\"]+)['\"]",
                'password': r"\$password\s*=\s*['\"]([^'\"]+)['\"]",
                'db': r"\$db\s*=\s*['\"]([^'\"]+)['\"]",
                'dbprefix': r"\$dbprefix\s*=\s*['\"]([^'\"]+)['\"]"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    db_config[key] = match.group(1)
            
            db_config['type'] = 'mysql'
            return db_config
        except Exception:
            return {}
    
    async def _get_joomla_version(self, path: Path) -> Optional[str]:
        """Get Joomla version."""
        # Try to get version from various files
        version_files = [
            path / "libraries" / "src" / "Version.php",  # Joomla 4+
            path / "libraries" / "cms" / "version" / "version.php",  # Joomla 3
            path / "includes" / "version.php"  # Older versions
        ]
        
        for version_file in version_files:
            if version_file.exists():
                try:
                    content = version_file.read_text()
                    patterns = [
                        r"RELEASE\s*=\s*['\"]([^'\"]+)['\"]",
                        r"const\s+MAJOR_VERSION\s*=\s*(\d+)",
                        r"\$RELEASE\s*=\s*['\"]([^'\"]+)['\"]"
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, content)
                        if match:
                            return match.group(1)
                except Exception:
                    continue
        
        return None
    
    async def _update_joomla_config(self, path: Path, db_config: Dict[str, Any]) -> None:
        """Update Joomla configuration.php with new database settings."""
        config_file = path / "configuration.php"
        if not config_file.exists():
            return
        
        try:
            content = config_file.read_text()
            
            replacements = {
                'host': db_config.get('host', 'localhost'),
                'user': db_config.get('user', ''),
                'password': db_config.get('password', ''),
                'db': db_config.get('db', '')
            }
            
            for var, value in replacements.items():
                pattern = rf"(\$public\s+\${var}\s*=\s*['\"])[^'\"]*(['\"])"
                replacement = rf"\1{value}\2"
                content = re.sub(pattern, replacement, content)
            
            config_file.write_text(content)
        except Exception as e:
            self.logger.error(f"Failed to update Joomla configuration: {e}")


class MagentoAdapter(CMSAdapter):
    """Adapter for Magento e-commerce platform."""
    
    @property
    def platform_type(self) -> str:
        return "magento"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["2.0", "2.1", "2.2", "2.3", "2.4"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Magento installation."""
        # Check for Magento 2
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                if "magento/product-community-edition" in content.get("require", {}):
                    return True
            except Exception:
                pass
        
        # Check for app/etc/env.php (Magento 2)
        env_php = path / "app" / "etc" / "env.php"
        if env_php.exists():
            return True
        
        # Check for typical Magento directory structure
        magento_dirs = ["app", "bin", "lib", "pub", "var"]
        return all((path / d).exists() for d in magento_dirs)
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Magento installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Magento not detected at {path}")
        
        version = await self._get_magento_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="magento",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql", "elasticsearch", "redis"],
            config_files=["app/etc/env.php", "app/etc/config.php"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Magento dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.4", required=True),
            DependencyInfo(name="mysql", version=">=5.7", required=True),
            DependencyInfo(name="elasticsearch", version=">=7.0", required=True),
            DependencyInfo(name="redis", required=False),
            DependencyInfo(name="composer", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Magento environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["app/etc/env.php", "app/etc/config.php"],
            secrets=["db_password", "crypt_key", "session_save_redis_password"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Magento migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_env", "reindex"],
            "files_to_copy": ["app", "pub/media", "var", "vendor"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Magento post-migration setup."""
        try:
            await self._update_magento_env(destination_path, migration_info.get("database_config", {}))
            return True
        except Exception as e:
            self.logger.error(f"Magento post-migration setup failed: {e}")
            return False
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Magento env.php."""
        env_file = path / "app" / "etc" / "env.php"
        if not env_file.exists():
            return {}
        
        try:
            content = env_file.read_text()
            # Parse PHP array (simplified)
            db_config = {}
            
            patterns = {
                'host': r"'host'\s*=>\s*'([^']+)'",
                'dbname': r"'dbname'\s*=>\s*'([^']+)'",
                'username': r"'username'\s*=>\s*'([^']+)'",
                'password': r"'password'\s*=>\s*'([^']+)'",
                'table_prefix': r"'table_prefix'\s*=>\s*'([^']+)'"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    db_config[key] = match.group(1)
            
            db_config['type'] = 'mysql'
            return db_config
        except Exception:
            return {}
    
    async def _get_magento_version(self, path: Path) -> Optional[str]:
        """Get Magento version."""
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                version = content.get("version")
                if version:
                    return version
            except Exception:
                pass
        return None
    
    async def _update_magento_env(self, path: Path, db_config: Dict[str, Any]) -> None:
        """Update Magento env.php with new database configuration."""
        # This would need proper PHP array manipulation
        pass


class ShopwareAdapter(CMSAdapter):
    """Adapter for Shopware e-commerce platform."""
    
    @property
    def platform_type(self) -> str:
        return "shopware"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["5.0", "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "6.0", "6.1", "6.2", "6.3", "6.4", "6.5"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Shopware installation."""
        # Check for Shopware 6
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                if "shopware/core" in content.get("require", {}):
                    return True
            except Exception:
                pass
        
        # Check for Shopware 5
        shopware_php = path / "shopware.php"
        if shopware_php.exists():
            return True
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Shopware installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Shopware not detected at {path}")
        
        version = await self._get_shopware_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="shopware",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql", "elasticsearch"],
            config_files=[".env", "config/packages/framework.yaml"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Shopware dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.4", required=True),
            DependencyInfo(name="mysql", version=">=5.7", required=True),
            DependencyInfo(name="elasticsearch", required=False),
            DependencyInfo(name="composer", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Shopware environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=[".env", "config/packages/framework.yaml"],
            secrets=["DATABASE_URL", "APP_SECRET"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Shopware migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_env"],
            "files_to_copy": ["config", "custom", "files", "public", "var"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Shopware post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Shopware .env."""
        env_file = path / ".env"
        if not env_file.exists():
            return {}
        
        try:
            content = env_file.read_text()
            env_vars = self._extract_environment_variables(content)
            
            # Parse DATABASE_URL
            db_url = env_vars.get("DATABASE_URL", "")
            if db_url:
                # Parse mysql://user:pass@host:port/dbname
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url)
                return {
                    'type': parsed.scheme,
                    'host': parsed.hostname,
                    'port': parsed.port,
                    'username': parsed.username,
                    'password': parsed.password,
                    'database': parsed.path.lstrip('/')
                }
        except Exception:
            pass
        
        return {}
    
    async def _get_shopware_version(self, path: Path) -> Optional[str]:
        """Get Shopware version."""
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                shopware_core = content.get("require", {}).get("shopware/core")
                if shopware_core:
                    return shopware_core.strip("^~")
            except Exception:
                pass
        return None


class PrestaShopAdapter(CMSAdapter):
    """Adapter for PrestaShop e-commerce platform."""
    
    @property
    def platform_type(self) -> str:
        return "prestashop"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["1.6", "1.7", "8.0", "8.1"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect PrestaShop installation."""
        config_file = path / "config" / "settings.inc.php"
        if config_file.exists():
            return True
        
        # Check for index.php with PrestaShop signature
        index_php = path / "index.php"
        if index_php.exists():
            try:
                content = index_php.read_text()
                return "PrestaShop" in content
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze PrestaShop installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"PrestaShop not detected at {path}")
        
        version = await self._get_prestashop_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="prestashop",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql"],
            config_files=["config/settings.inc.php"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get PrestaShop dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.2", required=True),
            DependencyInfo(name="mysql", version=">=5.6", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract PrestaShop environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["config/settings.inc.php"],
            secrets=["_DB_PASSWD_", "_COOKIE_KEY_"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare PrestaShop migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_config"],
            "files_to_copy": ["themes", "modules", "img", "upload", "download"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform PrestaShop post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from PrestaShop settings."""
        config_file = path / "config" / "settings.inc.php"
        if not config_file.exists():
            return {}
        
        try:
            content = config_file.read_text()
            db_config = {}
            
            patterns = {
                'server': r"define\s*\(\s*['\"]_DB_SERVER_['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'name': r"define\s*\(\s*['\"]_DB_NAME_['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'user': r"define\s*\(\s*['\"]_DB_USER_['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'passwd': r"define\s*\(\s*['\"]_DB_PASSWD_['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'prefix': r"define\s*\(\s*['\"]_DB_PREFIX_['\"]\s*,\s*['\"]([^'\"]+)['\"]"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    db_config[key] = match.group(1)
            
            db_config['type'] = 'mysql'
            return db_config
        except Exception:
            return {}
    
    async def _get_prestashop_version(self, path: Path) -> Optional[str]:
        """Get PrestaShop version."""
        config_file = path / "config" / "settings.inc.php"
        if config_file.exists():
            try:
                content = config_file.read_text()
                match = re.search(r"define\s*\(\s*['\"]_PS_VERSION_['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        return None


class OpenCartAdapter(CMSAdapter):
    """Adapter for OpenCart e-commerce platform."""
    
    @property
    def platform_type(self) -> str:
        return "opencart"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["2.0", "2.1", "2.2", "2.3", "3.0", "4.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect OpenCart installation."""
        config_file = path / "config.php"
        admin_config = path / "admin" / "config.php"
        
        if config_file.exists() and admin_config.exists():
            try:
                content = config_file.read_text()
                return "DIR_APPLICATION" in content and "DIR_SYSTEM" in content
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze OpenCart installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"OpenCart not detected at {path}")
        
        version = await self._get_opencart_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="opencart",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql"],
            config_files=["config.php", "admin/config.php"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get OpenCart dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.3", required=True),
            DependencyInfo(name="mysql", version=">=5.6", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract OpenCart environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["config.php", "admin/config.php"],
            secrets=["DB_PASSWORD"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare OpenCart migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_config"],
            "files_to_copy": ["catalog", "admin", "image", "system"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform OpenCart post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from OpenCart config."""
        config_file = path / "config.php"
        if not config_file.exists():
            return {}
        
        try:
            content = config_file.read_text()
            db_config = {}
            
            patterns = {
                'hostname': r"define\s*\(\s*['\"]DB_HOSTNAME['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'username': r"define\s*\(\s*['\"]DB_USERNAME['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'password': r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'database': r"define\s*\(\s*['\"]DB_DATABASE['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                'prefix': r"define\s*\(\s*['\"]DB_PREFIX['\"]\s*,\s*['\"]([^'\"]+)['\"]"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    db_config[key] = match.group(1)
            
            db_config['type'] = 'mysql'
            return db_config
        except Exception:
            return {}
    
    async def _get_opencart_version(self, path: Path) -> Optional[str]:
        """Get OpenCart version."""
        version_file = path / "admin" / "controller" / "common" / "dashboard.php"
        if version_file.exists():
            try:
                content = version_file.read_text()
                match = re.search(r"VERSION['\"]?\s*=>\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        return None


class GhostAdapter(CMSAdapter):
    """Adapter for Ghost CMS platform."""
    
    @property
    def platform_type(self) -> str:
        return "ghost"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["3.0", "4.0", "5.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Ghost installation."""
        package_json = path / "package.json"
        if package_json.exists():
            try:
                content = json.loads(package_json.read_text())
                return content.get("name") == "ghost"
            except Exception:
                pass
        
        # Check for Ghost binary
        ghost_bin = path / "ghost"
        return ghost_bin.exists()
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Ghost installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Ghost not detected at {path}")
        
        version = await self._get_ghost_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="ghost",
            database_type=db_config.get("type", "sqlite"),
            dependencies=["nodejs", "npm"],
            config_files=["config.production.json", "config.development.json"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Ghost dependencies."""
        return [
            DependencyInfo(name="nodejs", version=">=14", required=True),
            DependencyInfo(name="npm", required=True),
            DependencyInfo(name="mysql", required=False)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Ghost environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["config.production.json", "config.development.json"],
            secrets=["database.connection.password"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Ghost migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_config"],
            "files_to_copy": ["content", "config.production.json"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Ghost post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Ghost config."""
        config_files = [
            path / "config.production.json",
            path / "config.development.json"
        ]
        
        for config_file in config_files:
            if config_file.exists():
                try:
                    content = json.loads(config_file.read_text())
                    db_config = content.get("database", {}).get("connection", {})
                    if db_config:
                        return db_config
                except Exception:
                    continue
        
        return {}
    
    async def _get_ghost_version(self, path: Path) -> Optional[str]:
        """Get Ghost version."""
        package_json = path / "package.json"
        if package_json.exists():
            try:
                content = json.loads(package_json.read_text())
                return content.get("version")
            except Exception:
                pass
        return None


class CraftCMSAdapter(CMSAdapter):
    """Adapter for Craft CMS platform."""
    
    @property
    def platform_type(self) -> str:
        return "craftcms"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["3.0", "3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "4.0", "4.1", "4.2", "4.3", "4.4"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Craft CMS installation."""
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                if "craftcms/cms" in content.get("require", {}):
                    return True
            except Exception:
                pass
        
        # Check for craft executable
        craft_bin = path / "craft"
        return craft_bin.exists()
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Craft CMS installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Craft CMS not detected at {path}")
        
        version = await self._get_craftcms_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="craftcms",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql", "composer"],
            config_files=[".env", "config/db.php"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Craft CMS dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.2", required=True),
            DependencyInfo(name="mysql", version=">=5.7", required=True),
            DependencyInfo(name="composer", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Craft CMS environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=[".env", "config/db.php"],
            secrets=["DB_PASSWORD", "SECURITY_KEY"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Craft CMS migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_env"],
            "files_to_copy": ["config", "templates", "web/assets", "storage"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Craft CMS post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Craft CMS .env."""
        env_file = path / ".env"
        if not env_file.exists():
            return {}
        
        try:
            content = env_file.read_text()
            env_vars = self._extract_environment_variables(content)
            
            return {
                'type': 'mysql',
                'server': env_vars.get('DB_SERVER', 'localhost'),
                'database': env_vars.get('DB_DATABASE', ''),
                'user': env_vars.get('DB_USER', ''),
                'password': env_vars.get('DB_PASSWORD', ''),
                'port': env_vars.get('DB_PORT', '3306'),
                'table_prefix': env_vars.get('DB_TABLE_PREFIX', '')
            }
        except Exception:
            return {}
    
    async def _get_craftcms_version(self, path: Path) -> Optional[str]:
        """Get Craft CMS version."""
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                craft_version = content.get("require", {}).get("craftcms/cms")
                if craft_version:
                    return craft_version.strip("^~")
            except Exception:
                pass
        return None


class Typo3Adapter(CMSAdapter):
    """Adapter for TYPO3 CMS platform."""
    
    @property
    def platform_type(self) -> str:
        return "typo3"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["8.7", "9.5", "10.4", "11.5", "12.4"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect TYPO3 installation."""
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                if "typo3/cms-core" in content.get("require", {}):
                    return True
            except Exception:
                pass
        
        # Check for typo3conf directory
        typo3conf = path / "typo3conf"
        return typo3conf.exists()
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze TYPO3 installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"TYPO3 not detected at {path}")
        
        version = await self._get_typo3_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="typo3",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql", "composer"],
            config_files=["typo3conf/LocalConfiguration.php", ".env"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get TYPO3 dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.4", required=True),
            DependencyInfo(name="mysql", version=">=5.7", required=True),
            DependencyInfo(name="composer", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract TYPO3 environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["typo3conf/LocalConfiguration.php", ".env"],
            secrets=["DB_PASSWORD", "encryptionKey"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare TYPO3 migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_config"],
            "files_to_copy": ["typo3conf", "fileadmin", "uploads"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform TYPO3 post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from TYPO3 LocalConfiguration.php."""
        config_file = path / "typo3conf" / "LocalConfiguration.php"
        if not config_file.exists():
            return {}
        
        try:
            content = config_file.read_text()
            # This is a simplified parser for PHP arrays
            db_config = {}
            
            patterns = {
                'host': r"'host'\s*=>\s*'([^']+)'",
                'dbname': r"'dbname'\s*=>\s*'([^']+)'",
                'user': r"'user'\s*=>\s*'([^']+)'",
                'password': r"'password'\s*=>\s*'([^']+)'",
                'port': r"'port'\s*=>\s*'?([^',]+)'?"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    db_config[key] = match.group(1)
            
            db_config['type'] = 'mysql'
            return db_config
        except Exception:
            return {}
    
    async def _get_typo3_version(self, path: Path) -> Optional[str]:
        """Get TYPO3 version."""
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                typo3_version = content.get("require", {}).get("typo3/cms-core")
                if typo3_version:
                    return typo3_version.strip("^~")
            except Exception:
                pass
        return None


class Concrete5Adapter(CMSAdapter):
    """Adapter for Concrete5 CMS platform."""
    
    @property
    def platform_type(self) -> str:
        return "concrete5"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["8.0", "8.1", "8.2", "8.3", "8.4", "8.5", "9.0", "9.1", "9.2"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Concrete5 installation."""
        # Check for concrete directory
        concrete_dir = path / "concrete"
        if concrete_dir.exists():
            return True
        
        # Check for composer.json with concrete5
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                if "concrete5/concrete5" in content.get("require", {}):
                    return True
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Concrete5 installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Concrete5 not detected at {path}")
        
        version = await self._get_concrete5_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="concrete5",
            database_type=db_config.get("type", "mysql"),
            dependencies=["php", "mysql"],
            config_files=["application/config/database.php", "application/config/site.php"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Concrete5 dependencies."""
        return [
            DependencyInfo(name="php", version=">=7.3", required=True),
            DependencyInfo(name="mysql", version=">=5.7", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Concrete5 environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["application/config/database.php", "application/config/site.php"],
            secrets=["password"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Concrete5 migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_config"],
            "files_to_copy": ["application", "packages", "files"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Concrete5 post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Concrete5 config."""
        config_file = path / "application" / "config" / "database.php"
        if not config_file.exists():
            return {}
        
        try:
            content = config_file.read_text()
            db_config = {}
            
            patterns = {
                'server': r"'server'\s*=>\s*'([^']+)'",
                'database': r"'database'\s*=>\s*'([^']+)'",
                'username': r"'username'\s*=>\s*'([^']+)'",
                'password': r"'password'\s*=>\s*'([^']+)'"
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    db_config[key] = match.group(1)
            
            db_config['type'] = 'mysql'
            return db_config
        except Exception:
            return {}
    
    async def _get_concrete5_version(self, path: Path) -> Optional[str]:
        """Get Concrete5 version."""
        version_file = path / "concrete" / "config" / "version.php"
        if version_file.exists():
            try:
                content = version_file.read_text()
                match = re.search(r"'version'\s*=>\s*'([^']+)'", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        return None


class UmbracoAdapter(CMSAdapter):
    """Adapter for Umbraco CMS platform (.NET based)."""
    
    @property
    def platform_type(self) -> str:
        return "umbraco"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["8.0", "9.0", "10.0", "11.0", "12.0", "13.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Umbraco installation."""
        # Check for Umbraco specific files
        web_config = path / "web.config"
        if web_config.exists():
            try:
                content = web_config.read_text()
                if "Umbraco" in content:
                    return True
            except Exception:
                pass
        
        # Check for umbraco directory
        umbraco_dir = path / "umbraco"
        if umbraco_dir.exists():
            return True
        
        # Check for .csproj with Umbraco references
        for csproj_file in path.glob("*.csproj"):
            try:
                content = csproj_file.read_text()
                if "UmbracoCms" in content or "Umbraco.Cms" in content:
                    return True
            except Exception:
                continue
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Umbraco installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Umbraco not detected at {path}")
        
        version = await self._get_umbraco_version(path)
        db_config = await self.get_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="umbraco",
            database_type=db_config.get("type", "sqlserver"),
            dependencies=[".net", "sqlserver"],
            config_files=["web.config", "appsettings.json"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Umbraco dependencies."""
        return [
            DependencyInfo(name=".net", version=">=6.0", required=True),
            DependencyInfo(name="sqlserver", required=True),
            DependencyInfo(name="iis", required=False)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Umbraco environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["web.config", "appsettings.json"],
            secrets=["connectionString"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Umbraco migration."""
        platform_info = await self.analyze_platform(source_path)
        db_config = await self.get_database_config(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "database_config": db_config,
            "migration_steps": ["backup_database", "copy_files", "update_config"],
            "files_to_copy": ["Views", "App_Data", "media", "css", "scripts"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Umbraco post-migration setup."""
        return True
    
    async def get_database_config(self, path: Path) -> Dict[str, Any]:
        """Extract database configuration from Umbraco config."""
        # Try web.config first
        web_config = path / "web.config"
        if web_config.exists():
            try:
                content = web_config.read_text()
                # Parse connection string from web.config
                match = re.search(r'connectionString="([^"]+)"', content)
                if match:
                    conn_str = match.group(1)
                    return self._parse_connection_string(conn_str)
            except Exception:
                pass
        
        # Try appsettings.json for newer versions
        appsettings = path / "appsettings.json"
        if appsettings.exists():
            try:
                content = json.loads(appsettings.read_text())
                conn_strings = content.get("ConnectionStrings", {})
                if conn_strings:
                    umbraco_conn = conn_strings.get("umbracoDbDSN", "")
                    if umbraco_conn:
                        return self._parse_connection_string(umbraco_conn)
            except Exception:
                pass
        
        return {}
    
    def _parse_connection_string(self, conn_str: str) -> Dict[str, Any]:
        """Parse SQL Server connection string."""
        config = {'type': 'sqlserver'}
        
        # Parse connection string components
        parts = conn_str.split(';')
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ['server', 'data source']:
                    config['server'] = value
                elif key in ['database', 'initial catalog']:
                    config['database'] = value
                elif key in ['user id', 'uid']:
                    config['username'] = value
                elif key in ['password', 'pwd']:
                    config['password'] = value
        
        return config
    
    async def _get_umbraco_version(self, path: Path) -> Optional[str]:
        """Get Umbraco version."""
        # Try to find version in .csproj files
        for csproj_file in path.glob("*.csproj"):
            try:
                content = csproj_file.read_text()
                # Look for Umbraco package references
                patterns = [
                    r'<PackageReference Include="UmbracoCms[^"]*" Version="([^"]+)"',
                    r'<PackageReference Include="Umbraco\.Cms[^"]*" Version="([^"]+)"'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        return match.group(1)
            except Exception:
                continue
        
        return None