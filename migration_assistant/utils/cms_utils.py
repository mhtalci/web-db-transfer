"""
Utility functions for CMS platform operations.
"""

import re
import json
import hashlib
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET

from ..core.cms_exceptions import CMSConfigurationError, CMSVersionError


class CMSVersionParser:
    """Utility class for parsing and comparing CMS versions."""
    
    @staticmethod
    def parse_version(version_string: str) -> Tuple[int, ...]:
        """Parse version string into tuple of integers."""
        if not version_string:
            return (0,)
        
        # Remove non-numeric prefixes and suffixes
        clean_version = re.sub(r'[^\d.]', '', version_string)
        parts = clean_version.split('.')
        
        try:
            return tuple(int(part) for part in parts if part.isdigit())
        except ValueError:
            return (0,)
    
    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        v1_parts = CMSVersionParser.parse_version(version1)
        v2_parts = CMSVersionParser.parse_version(version2)
        
        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += (0,) * (max_len - len(v1_parts))
        v2_parts += (0,) * (max_len - len(v2_parts))
        
        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        else:
            return 0
    
    @staticmethod
    def is_version_supported(version: str, supported_versions: List[str]) -> bool:
        """Check if version is in supported versions list."""
        if not version or not supported_versions:
            return False
        
        for supported in supported_versions:
            if CMSVersionParser.compare_versions(version, supported) == 0:
                return True
        
        return False
    
    @staticmethod
    def get_latest_supported_version(supported_versions: List[str]) -> Optional[str]:
        """Get the latest version from supported versions list."""
        if not supported_versions:
            return None
        
        return max(supported_versions, key=lambda v: CMSVersionParser.parse_version(v))


class CMSConfigParser:
    """Utility class for parsing various CMS configuration formats."""
    
    @staticmethod
    def parse_php_config(content: str) -> Dict[str, Any]:
        """Parse PHP configuration file content."""
        config = {}
        
        # Parse define statements
        define_pattern = r"define\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(define_pattern, content, re.IGNORECASE):
            key, value = match.groups()
            config[key] = value
        
        # Parse variable assignments
        var_pattern = r"\$([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(var_pattern, content):
            key, value = match.groups()
            config[key] = value
        
        # Parse array assignments (simplified)
        array_pattern = r"\$([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(array_pattern, content):
            array_name, key, value = match.groups()
            if array_name not in config:
                config[array_name] = {}
            config[array_name][key] = value
        
        return config
    
    @staticmethod
    def parse_connection_string(conn_str: str) -> Dict[str, str]:
        """Parse database connection string."""
        config = {}
        
        # Handle different connection string formats
        if conn_str.startswith(('mysql://', 'postgresql://', 'sqlite://')):
            # URL format
            parsed = urlparse(conn_str)
            config.update({
                'type': parsed.scheme,
                'host': parsed.hostname or 'localhost',
                'port': str(parsed.port) if parsed.port else '',
                'username': parsed.username or '',
                'password': parsed.password or '',
                'database': parsed.path.lstrip('/') if parsed.path else ''
            })
        else:
            # Key-value format
            parts = conn_str.split(';')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    # Map common connection string keys
                    key_mapping = {
                        'server': 'host',
                        'data source': 'host',
                        'database': 'database',
                        'initial catalog': 'database',
                        'user id': 'username',
                        'uid': 'username',
                        'password': 'password',
                        'pwd': 'password'
                    }
                    
                    mapped_key = key_mapping.get(key, key)
                    config[mapped_key] = value
        
        return config
    
    @staticmethod
    def extract_urls_from_content(content: str, base_url: str = '') -> Set[str]:
        """Extract URLs from content for migration URL mapping."""
        urls = set()
        
        # Common URL patterns
        patterns = [
            r'https?://[^\s<>"\']+',  # HTTP/HTTPS URLs
            r'www\.[^\s<>"\']+',      # www URLs
            r'/[^\s<>"\']*\.[a-z]{2,4}',  # Relative URLs with extensions
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            urls.update(matches)
        
        # Convert relative URLs to absolute if base_url provided
        if base_url:
            absolute_urls = set()
            for url in urls:
                if not url.startswith(('http://', 'https://')):
                    absolute_urls.add(urljoin(base_url, url))
                else:
                    absolute_urls.add(url)
            urls = absolute_urls
        
        return urls


class CMSFileAnalyzer:
    """Utility class for analyzing CMS files and directories."""
    
    @staticmethod
    def get_file_hash(file_path: Path) -> str:
        """Get SHA256 hash of file for integrity checking."""
        if not file_path.exists() or not file_path.is_file():
            return ''
        
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception:
            return ''
    
    @staticmethod
    def analyze_directory_structure(path: Path) -> Dict[str, Any]:
        """Analyze directory structure and return statistics."""
        if not path.exists() or not path.is_dir():
            return {}
        
        stats = {
            'total_files': 0,
            'total_directories': 0,
            'total_size': 0,
            'file_types': {},
            'largest_files': [],
            'empty_directories': []
        }
        
        try:
            for item in path.rglob('*'):
                if item.is_file():
                    stats['total_files'] += 1
                    file_size = item.stat().st_size
                    stats['total_size'] += file_size
                    
                    # Track file types
                    mime_type, _ = mimetypes.guess_type(str(item))
                    if mime_type:
                        stats['file_types'][mime_type] = stats['file_types'].get(mime_type, 0) + 1
                    
                    # Track largest files (top 10)
                    stats['largest_files'].append((str(item.relative_to(path)), file_size))
                    stats['largest_files'].sort(key=lambda x: x[1], reverse=True)
                    stats['largest_files'] = stats['largest_files'][:10]
                
                elif item.is_dir():
                    stats['total_directories'] += 1
                    
                    # Check for empty directories
                    try:
                        if not any(item.iterdir()):
                            stats['empty_directories'].append(str(item.relative_to(path)))
                    except PermissionError:
                        pass
        
        except Exception:
            pass
        
        return stats
    
    @staticmethod
    def find_config_files(path: Path, patterns: List[str]) -> List[Path]:
        """Find configuration files matching given patterns."""
        config_files = []
        
        if not path.exists() or not path.is_dir():
            return config_files
        
        try:
            for pattern in patterns:
                config_files.extend(path.rglob(pattern))
        except Exception:
            pass
        
        return config_files
    
    @staticmethod
    def detect_cms_indicators(path: Path) -> Dict[str, List[str]]:
        """Detect CMS indicators in directory structure."""
        indicators = {
            'wordpress': ['wp-config.php', 'wp-includes/', 'wp-admin/', 'wp-content/'],
            'drupal': ['sites/', 'modules/', 'themes/', 'core/', 'composer.json'],
            'joomla': ['configuration.php', 'administrator/', 'components/', 'modules/'],
            'magento': ['app/etc/env.php', 'bin/magento', 'pub/', 'var/'],
            'shopware': ['shopware.php', 'composer.json', 'config/', 'custom/'],
            'prestashop': ['config/settings.inc.php', 'admin/', 'themes/'],
            'opencart': ['config.php', 'admin/config.php', 'catalog/', 'system/'],
            'ghost': ['package.json', 'config.production.json', 'content/'],
            'craftcms': ['craft', 'composer.json', 'config/', 'templates/'],
            'typo3': ['typo3conf/', 'typo3/', 'fileadmin/', 'composer.json'],
            'concrete5': ['concrete/', 'application/', 'packages/'],
            'umbraco': ['web.config', 'umbraco/', 'Views/', 'App_Data/']
        }
        
        detected = {}
        
        for cms, files in indicators.items():
            found_indicators = []
            for indicator in files:
                indicator_path = path / indicator.rstrip('/')
                if indicator_path.exists():
                    found_indicators.append(indicator)
            
            if found_indicators:
                detected[cms] = found_indicators
        
        return detected


class CMSSecurityAnalyzer:
    """Utility class for analyzing CMS security configurations."""
    
    @staticmethod
    def check_file_permissions(path: Path) -> Dict[str, Any]:
        """Check file permissions for security issues."""
        issues = []
        recommendations = []
        
        if not path.exists():
            return {'issues': ['Path does not exist'], 'recommendations': []}
        
        try:
            # Check for overly permissive files
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    stat_info = file_path.stat()
                    mode = oct(stat_info.st_mode)[-3:]
                    
                    # Check for world-writable files
                    if mode.endswith(('2', '3', '6', '7')):
                        issues.append(f"World-writable file: {file_path.relative_to(path)}")
                    
                    # Check for executable config files
                    if file_path.suffix in ['.php', '.conf', '.config'] and mode.startswith('7'):
                        issues.append(f"Executable config file: {file_path.relative_to(path)}")
        
        except Exception as e:
            issues.append(f"Permission check failed: {str(e)}")
        
        # Generate recommendations
        if issues:
            recommendations.extend([
                "Set proper file permissions (644 for files, 755 for directories)",
                "Remove execute permissions from configuration files",
                "Ensure sensitive files are not world-readable"
            ])
        
        return {
            'issues': issues,
            'recommendations': recommendations
        }
    
    @staticmethod
    def scan_for_sensitive_data(content: str) -> List[str]:
        """Scan content for potentially sensitive data."""
        sensitive_patterns = [
            (r'password\s*[=:]\s*["\']([^"\']+)["\']', 'Password'),
            (r'api[_-]?key\s*[=:]\s*["\']([^"\']+)["\']', 'API Key'),
            (r'secret[_-]?key\s*[=:]\s*["\']([^"\']+)["\']', 'Secret Key'),
            (r'token\s*[=:]\s*["\']([^"\']+)["\']', 'Token'),
            (r'mysql://[^:]+:([^@]+)@', 'Database Password'),
            (r'postgresql://[^:]+:([^@]+)@', 'Database Password'),
        ]
        
        findings = []
        
        for pattern, data_type in sensitive_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                findings.append(f"{data_type} found: {match.group(1)[:10]}...")
        
        return findings


class CMSMigrationPlanner:
    """Utility class for planning CMS migrations."""
    
    @staticmethod
    def estimate_migration_time(source_stats: Dict[str, Any], 
                              source_platform: str, 
                              destination_platform: str) -> Dict[str, Any]:
        """Estimate migration time based on various factors."""
        base_time = 300  # 5 minutes base time
        
        # Factor in file count and size
        file_factor = min(source_stats.get('total_files', 0) / 1000, 10)  # Max 10x multiplier
        size_factor = min(source_stats.get('total_size', 0) / (1024**3), 5)  # Max 5x for size in GB
        
        # Platform complexity factor
        complexity_factors = {
            ('wordpress', 'wordpress'): 1.0,
            ('drupal', 'drupal'): 1.2,
            ('joomla', 'joomla'): 1.1,
            ('magento', 'magento'): 2.0,
            ('wordpress', 'drupal'): 3.0,
            ('drupal', 'wordpress'): 3.0,
        }
        
        platform_factor = complexity_factors.get((source_platform, destination_platform), 2.5)
        
        estimated_seconds = base_time * (1 + file_factor + size_factor) * platform_factor
        
        return {
            'estimated_seconds': int(estimated_seconds),
            'estimated_minutes': int(estimated_seconds / 60),
            'factors': {
                'file_factor': file_factor,
                'size_factor': size_factor,
                'platform_factor': platform_factor
            }
        }
    
    @staticmethod
    def generate_migration_checklist(source_platform: str, 
                                   destination_platform: str) -> List[Dict[str, Any]]:
        """Generate a comprehensive migration checklist."""
        checklist = []
        
        # Pre-migration checks
        checklist.extend([
            {
                'category': 'Pre-Migration',
                'task': 'Create full backup of source site',
                'priority': 'critical',
                'estimated_time': 30
            },
            {
                'category': 'Pre-Migration',
                'task': 'Verify destination server requirements',
                'priority': 'critical',
                'estimated_time': 15
            },
            {
                'category': 'Pre-Migration',
                'task': 'Test database connectivity',
                'priority': 'high',
                'estimated_time': 10
            }
        ])
        
        # Platform-specific checks
        if source_platform == 'wordpress':
            checklist.extend([
                {
                    'category': 'WordPress Specific',
                    'task': 'Export WordPress content (XML)',
                    'priority': 'high',
                    'estimated_time': 15
                },
                {
                    'category': 'WordPress Specific',
                    'task': 'Document active plugins and themes',
                    'priority': 'medium',
                    'estimated_time': 20
                }
            ])
        
        if source_platform == 'magento':
            checklist.extend([
                {
                    'category': 'Magento Specific',
                    'task': 'Export product catalog',
                    'priority': 'critical',
                    'estimated_time': 60
                },
                {
                    'category': 'Magento Specific',
                    'task': 'Document custom extensions',
                    'priority': 'high',
                    'estimated_time': 45
                }
            ])
        
        # Post-migration checks
        checklist.extend([
            {
                'category': 'Post-Migration',
                'task': 'Verify site functionality',
                'priority': 'critical',
                'estimated_time': 30
            },
            {
                'category': 'Post-Migration',
                'task': 'Update DNS records',
                'priority': 'high',
                'estimated_time': 15
            },
            {
                'category': 'Post-Migration',
                'task': 'Set up SSL certificate',
                'priority': 'high',
                'estimated_time': 20
            }
        ])
        
        return checklist