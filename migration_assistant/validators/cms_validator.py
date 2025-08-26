"""
CMS-specific validation and health check utilities.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..core.cms_exceptions import (
    CMSVersionError, CMSConfigurationError, CMSDatabaseError, 
    CMSCompatibilityError
)
from ..utils.cms_utils import CMSVersionParser, CMSFileAnalyzer, CMSSecurityAnalyzer


class ValidationSeverity(Enum):
    """Validation issue severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    severity: ValidationSeverity
    category: str
    message: str
    details: Optional[str] = None
    fix_suggestion: Optional[str] = None


class CMSHealthChecker:
    """Comprehensive CMS health checker."""
    
    def __init__(self, platform_type: str, path: Path):
        self.platform_type = platform_type
        self.path = path
        self.issues: List[ValidationIssue] = []
    
    async def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check."""
        self.issues.clear()
        
        # Run all health checks
        await self._check_file_structure()
        await self._check_permissions()
        await self._check_configuration()
        await self._check_dependencies()
        await self._check_security()
        await self._check_performance()
        
        # Categorize issues by severity
        severity_counts = {
            ValidationSeverity.INFO: 0,
            ValidationSeverity.WARNING: 0,
            ValidationSeverity.ERROR: 0,
            ValidationSeverity.CRITICAL: 0
        }
        
        for issue in self.issues:
            severity_counts[issue.severity] += 1
        
        # Calculate health score (0-100)
        total_issues = len(self.issues)
        critical_weight = severity_counts[ValidationSeverity.CRITICAL] * 4
        error_weight = severity_counts[ValidationSeverity.ERROR] * 2
        warning_weight = severity_counts[ValidationSeverity.WARNING] * 1
        
        penalty = critical_weight + error_weight + warning_weight
        health_score = max(0, 100 - penalty * 5)  # Each point reduces score by 5
        
        return {
            'platform': self.platform_type,
            'path': str(self.path),
            'health_score': health_score,
            'total_issues': total_issues,
            'severity_breakdown': {
                'critical': severity_counts[ValidationSeverity.CRITICAL],
                'error': severity_counts[ValidationSeverity.ERROR],
                'warning': severity_counts[ValidationSeverity.WARNING],
                'info': severity_counts[ValidationSeverity.INFO]
            },
            'issues': [
                {
                    'severity': issue.severity.value,
                    'category': issue.category,
                    'message': issue.message,
                    'details': issue.details,
                    'fix_suggestion': issue.fix_suggestion
                }
                for issue in self.issues
            ],
            'recommendations': self._generate_recommendations()
        }
    
    async def _check_file_structure(self):
        """Check file structure integrity."""
        required_files = self._get_required_files()
        
        for file_path in required_files:
            full_path = self.path / file_path
            if not full_path.exists():
                self.issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="File Structure",
                    message=f"Required file missing: {file_path}",
                    fix_suggestion=f"Restore or recreate {file_path}"
                ))
        
        # Check for suspicious files
        suspicious_patterns = ['*.bak', '*.tmp', '*.old', '*~']
        for pattern in suspicious_patterns:
            suspicious_files = list(self.path.rglob(pattern))
            if suspicious_files:
                self.issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="File Structure",
                    message=f"Found {len(suspicious_files)} suspicious files matching {pattern}",
                    details=f"Files: {', '.join(str(f.relative_to(self.path)) for f in suspicious_files[:5])}",
                    fix_suggestion="Review and remove unnecessary backup/temporary files"
                ))
    
    async def _check_permissions(self):
        """Check file and directory permissions."""
        permission_check = CMSSecurityAnalyzer.check_file_permissions(self.path)
        
        for issue in permission_check['issues']:
            self.issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="Permissions",
                message=issue,
                fix_suggestion="Set appropriate file permissions (644 for files, 755 for directories)"
            ))
    
    async def _check_configuration(self):
        """Check configuration file validity."""
        config_files = self._get_config_files()
        
        for config_file in config_files:
            full_path = self.path / config_file
            if full_path.exists():
                try:
                    await self._validate_config_file(full_path)
                except Exception as e:
                    self.issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="Configuration",
                        message=f"Invalid configuration in {config_file}",
                        details=str(e),
                        fix_suggestion="Review and fix configuration syntax"
                    ))
    
    async def _check_dependencies(self):
        """Check for missing dependencies."""
        dependencies = self._get_platform_dependencies()
        
        for dep_name, dep_info in dependencies.items():
            if not await self._check_dependency_available(dep_name, dep_info):
                severity = ValidationSeverity.CRITICAL if dep_info.get('required', True) else ValidationSeverity.WARNING
                self.issues.append(ValidationIssue(
                    severity=severity,
                    category="Dependencies",
                    message=f"Missing dependency: {dep_name}",
                    details=f"Required version: {dep_info.get('version', 'any')}",
                    fix_suggestion=dep_info.get('install_command', f"Install {dep_name}")
                ))
    
    async def _check_security(self):
        """Check for security issues."""
        # Check for exposed sensitive files
        sensitive_files = ['.env', 'wp-config.php', 'configuration.php', 'settings.php']
        
        for sensitive_file in sensitive_files:
            file_path = self.path / sensitive_file
            if file_path.exists():
                # Check if file is in web-accessible directory
                if self._is_web_accessible(file_path):
                    self.issues.append(ValidationIssue(
                        severity=ValidationSeverity.CRITICAL,
                        category="Security",
                        message=f"Sensitive file in web-accessible location: {sensitive_file}",
                        fix_suggestion="Move sensitive files outside web root or add .htaccess protection"
                    ))
        
        # Check for default credentials
        await self._check_default_credentials()
    
    async def _check_performance(self):
        """Check for performance issues."""
        # Check directory structure stats
        stats = CMSFileAnalyzer.analyze_directory_structure(self.path)
        
        # Check for too many files
        if stats.get('total_files', 0) > 50000:
            self.issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="Performance",
                message=f"Large number of files detected: {stats['total_files']}",
                fix_suggestion="Consider cleaning up unnecessary files or implementing file optimization"
            ))
        
        # Check for large files
        large_files = [f for f, size in stats.get('largest_files', []) if size > 100 * 1024 * 1024]  # 100MB
        if large_files:
            self.issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                category="Performance",
                message=f"Found {len(large_files)} files larger than 100MB",
                details=f"Largest files: {', '.join(large_files[:3])}",
                fix_suggestion="Consider optimizing or compressing large files"
            ))
    
    def _get_required_files(self) -> List[str]:
        """Get list of required files for the platform."""
        required_files_map = {
            'wordpress': ['wp-config.php', 'wp-includes/version.php'],
            'drupal': ['index.php', 'sites/default/settings.php'],
            'joomla': ['configuration.php', 'index.php'],
            'magento': ['app/etc/env.php', 'bin/magento'],
            'shopware': ['composer.json'],
            'prestashop': ['config/settings.inc.php'],
            'opencart': ['config.php', 'admin/config.php'],
            'ghost': ['package.json'],
            'craftcms': ['craft', 'composer.json'],
            'typo3': ['typo3conf/LocalConfiguration.php'],
            'concrete5': ['concrete/config/version.php'],
            'umbraco': ['web.config']
        }
        
        return required_files_map.get(self.platform_type, [])
    
    def _get_config_files(self) -> List[str]:
        """Get list of configuration files for the platform."""
        config_files_map = {
            'wordpress': ['wp-config.php'],
            'drupal': ['sites/default/settings.php'],
            'joomla': ['configuration.php'],
            'magento': ['app/etc/env.php', 'app/etc/config.php'],
            'shopware': ['.env', 'config/packages/framework.yaml'],
            'prestashop': ['config/settings.inc.php'],
            'opencart': ['config.php', 'admin/config.php'],
            'ghost': ['config.production.json', 'config.development.json'],
            'craftcms': ['.env', 'config/db.php'],
            'typo3': ['typo3conf/LocalConfiguration.php'],
            'concrete5': ['application/config/database.php'],
            'umbraco': ['web.config', 'appsettings.json']
        }
        
        return config_files_map.get(self.platform_type, [])
    
    def _get_platform_dependencies(self) -> Dict[str, Dict[str, Any]]:
        """Get platform-specific dependencies."""
        dependencies_map = {
            'wordpress': {
                'php': {'version': '>=7.4', 'required': True, 'install_command': 'apt-get install php'},
                'mysql': {'version': '>=5.7', 'required': True, 'install_command': 'apt-get install mysql-server'}
            },
            'drupal': {
                'php': {'version': '>=7.4', 'required': True},
                'mysql': {'version': '>=5.7', 'required': True},
                'composer': {'required': True}
            },
            'magento': {
                'php': {'version': '>=7.4', 'required': True},
                'mysql': {'version': '>=5.7', 'required': True},
                'elasticsearch': {'version': '>=7.0', 'required': True},
                'composer': {'required': True}
            },
            'ghost': {
                'nodejs': {'version': '>=14', 'required': True},
                'npm': {'required': True}
            },
            'umbraco': {
                '.net': {'version': '>=6.0', 'required': True},
                'sqlserver': {'required': True}
            }
        }
        
        return dependencies_map.get(self.platform_type, {})
    
    async def _validate_config_file(self, config_path: Path):
        """Validate specific configuration file."""
        content = config_path.read_text(encoding='utf-8')
        
        if config_path.suffix == '.json':
            # Validate JSON
            json.loads(content)
        elif config_path.suffix == '.php':
            # Basic PHP syntax check
            if not content.strip().startswith('<?php'):
                raise ValueError("PHP file should start with <?php")
        elif config_path.suffix in ['.yaml', '.yml']:
            # Basic YAML validation
            import yaml
            yaml.safe_load(content)
    
    async def _check_dependency_available(self, dep_name: str, dep_info: Dict[str, Any]) -> bool:
        """Check if dependency is available."""
        # This is a simplified check - in real implementation, you'd check actual system
        # For now, we'll assume dependencies are available
        return True
    
    def _is_web_accessible(self, file_path: Path) -> bool:
        """Check if file is in web-accessible directory."""
        web_dirs = ['public', 'www', 'htdocs', 'public_html', 'web']
        
        for part in file_path.parts:
            if part.lower() in web_dirs:
                return True
        
        return False
    
    async def _check_default_credentials(self):
        """Check for default or weak credentials."""
        # This would check for common default passwords in config files
        # Implementation would scan config files for known weak passwords
        pass
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on found issues."""
        recommendations = []
        
        critical_count = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.CRITICAL)
        error_count = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.ERROR)
        
        if critical_count > 0:
            recommendations.append(f"Address {critical_count} critical issues immediately before migration")
        
        if error_count > 0:
            recommendations.append(f"Fix {error_count} errors to ensure successful migration")
        
        # Category-specific recommendations
        categories = set(issue.category for issue in self.issues)
        
        if "Security" in categories:
            recommendations.append("Review and implement security best practices")
        
        if "Performance" in categories:
            recommendations.append("Optimize performance before migration for better results")
        
        if "Dependencies" in categories:
            recommendations.append("Install missing dependencies on destination server")
        
        return recommendations


class CMSCompatibilityChecker:
    """Check compatibility between CMS platforms for migration."""
    
    @staticmethod
    async def check_migration_compatibility(
        source_platform: str,
        source_version: str,
        destination_platform: str,
        destination_version: str
    ) -> Dict[str, Any]:
        """Check comprehensive migration compatibility."""
        
        issues = []
        warnings = []
        
        # Version compatibility
        if source_platform == destination_platform:
            # Same platform migration
            version_compatibility = CMSCompatibilityChecker._check_version_compatibility(
                source_platform, source_version, destination_version
            )
            if not version_compatibility['compatible']:
                issues.extend(version_compatibility['issues'])
        else:
            # Cross-platform migration
            cross_platform_check = CMSCompatibilityChecker._check_cross_platform_compatibility(
                source_platform, destination_platform
            )
            if not cross_platform_check['compatible']:
                issues.extend(cross_platform_check['issues'])
            warnings.extend(cross_platform_check.get('warnings', []))
        
        # Database compatibility
        db_compatibility = CMSCompatibilityChecker._check_database_compatibility(
            source_platform, destination_platform
        )
        if not db_compatibility['compatible']:
            issues.extend(db_compatibility['issues'])
        
        is_compatible = len(issues) == 0
        
        return {
            'compatible': is_compatible,
            'issues': issues,
            'warnings': warnings,
            'migration_complexity': 'simple' if is_compatible and source_platform == destination_platform else 'complex',
            'estimated_success_rate': CMSCompatibilityChecker._calculate_success_rate(
                source_platform, destination_platform, len(issues), len(warnings)
            )
        }
    
    @staticmethod
    def _check_version_compatibility(platform: str, source_version: str, dest_version: str) -> Dict[str, Any]:
        """Check version compatibility for same-platform migration."""
        issues = []
        
        if not source_version or not dest_version:
            issues.append("Cannot determine version compatibility - version information missing")
            return {'compatible': False, 'issues': issues}
        
        version_comparison = CMSVersionParser.compare_versions(source_version, dest_version)
        
        # Generally, migrating to newer versions is safer
        if version_comparison > 0:  # source > destination
            issues.append(f"Downgrading from {source_version} to {dest_version} may cause compatibility issues")
        
        # Check for major version differences
        source_major = CMSVersionParser.parse_version(source_version)[0]
        dest_major = CMSVersionParser.parse_version(dest_version)[0]
        
        if abs(source_major - dest_major) > 1:
            issues.append(f"Major version difference detected ({source_major} -> {dest_major})")
        
        return {
            'compatible': len(issues) == 0,
            'issues': issues
        }
    
    @staticmethod
    def _check_cross_platform_compatibility(source_platform: str, destination_platform: str) -> Dict[str, Any]:
        """Check cross-platform migration compatibility."""
        issues = []
        warnings = []
        
        # Define compatibility matrix
        compatibility_matrix = {
            'wordpress': ['drupal', 'ghost', 'joomla'],
            'drupal': ['wordpress', 'ghost'],
            'joomla': ['wordpress'],
            'magento': ['shopware', 'prestashop', 'opencart'],
            'shopware': ['magento', 'prestashop', 'opencart'],
            'prestashop': ['magento', 'shopware', 'opencart'],
            'opencart': ['magento', 'shopware', 'prestashop'],
            'ghost': ['wordpress', 'drupal', 'craftcms'],
            'craftcms': ['wordpress', 'drupal', 'ghost'],
            'typo3': ['wordpress', 'drupal'],
            'concrete5': ['wordpress', 'drupal'],
            'umbraco': ['wordpress', 'drupal']
        }
        
        compatible_destinations = compatibility_matrix.get(source_platform, [])
        
        if destination_platform not in compatible_destinations:
            issues.append(f"Direct migration from {source_platform} to {destination_platform} is not supported")
        
        # Add platform-specific warnings
        if source_platform in ['magento', 'shopware'] and destination_platform in ['wordpress', 'drupal']:
            warnings.append("E-commerce to CMS migration will lose product catalog functionality")
        
        if source_platform == 'umbraco' and destination_platform != 'umbraco':
            warnings.append(".NET to PHP migration requires significant architectural changes")
        
        return {
            'compatible': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    @staticmethod
    def _check_database_compatibility(source_platform: str, destination_platform: str) -> Dict[str, Any]:
        """Check database compatibility between platforms."""
        issues = []
        
        # Define database requirements
        database_requirements = {
            'wordpress': ['mysql', 'mariadb'],
            'drupal': ['mysql', 'mariadb', 'postgresql'],
            'joomla': ['mysql', 'mariadb'],
            'magento': ['mysql', 'mariadb'],
            'shopware': ['mysql', 'mariadb'],
            'prestashop': ['mysql', 'mariadb'],
            'opencart': ['mysql', 'mariadb'],
            'ghost': ['mysql', 'mariadb', 'sqlite'],
            'craftcms': ['mysql', 'mariadb', 'postgresql'],
            'typo3': ['mysql', 'mariadb', 'postgresql'],
            'concrete5': ['mysql', 'mariadb'],
            'umbraco': ['sqlserver', 'sqlite']
        }
        
        source_dbs = set(database_requirements.get(source_platform, []))
        dest_dbs = set(database_requirements.get(destination_platform, []))
        
        common_dbs = source_dbs.intersection(dest_dbs)
        
        if not common_dbs:
            issues.append(f"No compatible database systems between {source_platform} and {destination_platform}")
        
        return {
            'compatible': len(issues) == 0,
            'issues': issues,
            'common_databases': list(common_dbs)
        }
    
    @staticmethod
    def _calculate_success_rate(source_platform: str, destination_platform: str, 
                              issue_count: int, warning_count: int) -> int:
        """Calculate estimated migration success rate."""
        base_rate = 95  # Start with 95% base success rate
        
        # Reduce rate based on issues and warnings
        base_rate -= issue_count * 20  # Each issue reduces by 20%
        base_rate -= warning_count * 5  # Each warning reduces by 5%
        
        # Platform-specific adjustments
        if source_platform == destination_platform:
            base_rate += 10  # Same platform is easier
        
        if source_platform in ['wordpress', 'drupal'] and destination_platform in ['wordpress', 'drupal']:
            base_rate += 5  # These platforms migrate well to each other
        
        return max(0, min(100, base_rate))