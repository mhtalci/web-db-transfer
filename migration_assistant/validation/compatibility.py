"""
Compatibility validation module for checking source/destination compatibility.
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from migration_assistant.models.config import (
    SystemType, DatabaseType, TransferMethod, MigrationConfig,
    SystemConfig, DatabaseConfig
)

logger = logging.getLogger(__name__)


class CompatibilityResult(Enum):
    """Compatibility check result status"""
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    WARNING = "warning"
    REQUIRES_CONVERSION = "requires_conversion"


@dataclass
class CompatibilityCheck:
    """Result of a compatibility check"""
    name: str
    result: CompatibilityResult
    message: str
    details: Optional[Dict[str, Any]] = None
    remediation: Optional[str] = None
    conversion_required: bool = False
    estimated_complexity: str = "low"  # low, medium, high


class CompatibilityValidator:
    """
    Validates compatibility between source and destination systems,
    including database types, file systems, and platform-specific requirements.
    """
    
    def __init__(self):
        self._init_compatibility_matrices()
    
    def _init_compatibility_matrices(self):
        """Initialize compatibility matrices for different system components"""
        
        # Database compatibility matrix
        self.database_compatibility = {
            DatabaseType.MYSQL: {
                DatabaseType.MYSQL: CompatibilityResult.COMPATIBLE,
                DatabaseType.POSTGRESQL: CompatibilityResult.REQUIRES_CONVERSION,
                DatabaseType.SQLITE: CompatibilityResult.REQUIRES_CONVERSION,
                DatabaseType.MONGODB: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.REDIS: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.AWS_RDS: CompatibilityResult.COMPATIBLE,
                DatabaseType.GOOGLE_CLOUD_SQL: CompatibilityResult.COMPATIBLE,
                DatabaseType.AZURE_SQL: CompatibilityResult.REQUIRES_CONVERSION,
            },
            DatabaseType.POSTGRESQL: {
                DatabaseType.MYSQL: CompatibilityResult.REQUIRES_CONVERSION,
                DatabaseType.POSTGRESQL: CompatibilityResult.COMPATIBLE,
                DatabaseType.SQLITE: CompatibilityResult.REQUIRES_CONVERSION,
                DatabaseType.MONGODB: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.REDIS: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.AWS_RDS: CompatibilityResult.COMPATIBLE,
                DatabaseType.GOOGLE_CLOUD_SQL: CompatibilityResult.COMPATIBLE,
                DatabaseType.AZURE_SQL: CompatibilityResult.COMPATIBLE,
            },
            DatabaseType.SQLITE: {
                DatabaseType.MYSQL: CompatibilityResult.REQUIRES_CONVERSION,
                DatabaseType.POSTGRESQL: CompatibilityResult.REQUIRES_CONVERSION,
                DatabaseType.SQLITE: CompatibilityResult.COMPATIBLE,
                DatabaseType.MONGODB: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.REDIS: CompatibilityResult.INCOMPATIBLE,
            },
            DatabaseType.MONGODB: {
                DatabaseType.MONGODB: CompatibilityResult.COMPATIBLE,
                DatabaseType.MYSQL: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.POSTGRESQL: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.SQLITE: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.REDIS: CompatibilityResult.INCOMPATIBLE,
            },
            DatabaseType.REDIS: {
                DatabaseType.REDIS: CompatibilityResult.COMPATIBLE,
                DatabaseType.MONGODB: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.MYSQL: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.POSTGRESQL: CompatibilityResult.INCOMPATIBLE,
                DatabaseType.SQLITE: CompatibilityResult.INCOMPATIBLE,
            }
        }
        
        # System type compatibility matrix
        self.system_compatibility = {
            SystemType.WORDPRESS: {
                SystemType.WORDPRESS: CompatibilityResult.COMPATIBLE,
                SystemType.DRUPAL: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.STATIC_SITE: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.AWS_S3: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.DOCKER_CONTAINER: CompatibilityResult.COMPATIBLE,
            },
            SystemType.DRUPAL: {
                SystemType.DRUPAL: CompatibilityResult.COMPATIBLE,
                SystemType.WORDPRESS: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.STATIC_SITE: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.AWS_S3: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.DOCKER_CONTAINER: CompatibilityResult.COMPATIBLE,
            },
            SystemType.DJANGO: {
                SystemType.DJANGO: CompatibilityResult.COMPATIBLE,
                SystemType.FLASK: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.FASTAPI: CompatibilityResult.REQUIRES_CONVERSION,
                SystemType.DOCKER_CONTAINER: CompatibilityResult.COMPATIBLE,
                SystemType.KUBERNETES_POD: CompatibilityResult.COMPATIBLE,
                SystemType.AWS_S3: CompatibilityResult.WARNING,  # Static files only
            },
            SystemType.STATIC_SITE: {
                SystemType.STATIC_SITE: CompatibilityResult.COMPATIBLE,
                SystemType.AWS_S3: CompatibilityResult.COMPATIBLE,
                SystemType.GOOGLE_CLOUD_STORAGE: CompatibilityResult.COMPATIBLE,
                SystemType.AZURE_BLOB: CompatibilityResult.COMPATIBLE,
                SystemType.DOCKER_CONTAINER: CompatibilityResult.COMPATIBLE,
                SystemType.WORDPRESS: CompatibilityResult.INCOMPATIBLE,
                SystemType.DJANGO: CompatibilityResult.INCOMPATIBLE,
            },
            SystemType.DOCKER_CONTAINER: {
                SystemType.DOCKER_CONTAINER: CompatibilityResult.COMPATIBLE,
                SystemType.KUBERNETES_POD: CompatibilityResult.COMPATIBLE,
                SystemType.AWS_S3: CompatibilityResult.WARNING,
                SystemType.WORDPRESS: CompatibilityResult.COMPATIBLE,
                SystemType.DJANGO: CompatibilityResult.COMPATIBLE,
            }
        }
        
        # Transfer method compatibility with system types
        self.transfer_compatibility = {
            SystemType.WORDPRESS: {
                TransferMethod.SSH_SCP, TransferMethod.SSH_SFTP, TransferMethod.RSYNC,
                TransferMethod.FTP, TransferMethod.FTPS, TransferMethod.HYBRID_SYNC
            },
            SystemType.STATIC_SITE: {
                TransferMethod.SSH_SCP, TransferMethod.SSH_SFTP, TransferMethod.RSYNC,
                TransferMethod.FTP, TransferMethod.FTPS, TransferMethod.AWS_S3,
                TransferMethod.GOOGLE_CLOUD_STORAGE, TransferMethod.AZURE_BLOB,
                TransferMethod.HYBRID_SYNC
            },
            SystemType.DOCKER_CONTAINER: {
                TransferMethod.DOCKER_VOLUME, TransferMethod.SSH_SCP,
                TransferMethod.SSH_SFTP, TransferMethod.HYBRID_SYNC
            },
            SystemType.KUBERNETES_POD: {
                TransferMethod.KUBERNETES_VOLUME, TransferMethod.SSH_SCP,
                TransferMethod.SSH_SFTP, TransferMethod.HYBRID_SYNC
            },
            SystemType.AWS_S3: {
                TransferMethod.AWS_S3, TransferMethod.HYBRID_SYNC
            },
            SystemType.GOOGLE_CLOUD_STORAGE: {
                TransferMethod.GOOGLE_CLOUD_STORAGE, TransferMethod.HYBRID_SYNC
            },
            SystemType.AZURE_BLOB: {
                TransferMethod.AZURE_BLOB, TransferMethod.HYBRID_SYNC
            }
        }
    
    async def validate_compatibility(self, config: MigrationConfig) -> List[CompatibilityCheck]:
        """
        Validate compatibility between source and destination systems.
        
        Args:
            config: Migration configuration
            
        Returns:
            List of compatibility check results
        """
        checks = []
        
        # System type compatibility
        system_check = await self._check_system_compatibility(
            config.source, config.destination
        )
        checks.append(system_check)
        
        # Database compatibility
        if config.source.database and config.destination.database:
            db_check = await self._check_database_compatibility(
                config.source.database, config.destination.database
            )
            checks.append(db_check)
        elif config.source.database and not config.destination.database:
            checks.append(CompatibilityCheck(
                name="Database Migration",
                result=CompatibilityResult.WARNING,
                message="Source has database but destination doesn't - database will be ignored",
                remediation="Configure destination database or use database export"
            ))
        elif not config.source.database and config.destination.database:
            checks.append(CompatibilityCheck(
                name="Database Migration",
                result=CompatibilityResult.WARNING,
                message="Destination has database but source doesn't - destination database will remain empty",
                remediation="Ensure this is intended behavior"
            ))
        
        # Transfer method compatibility
        transfer_check = await self._check_transfer_compatibility(
            config.source, config.destination, config.transfer.method
        )
        checks.append(transfer_check)
        
        # Platform-specific compatibility
        platform_checks = await self._check_platform_compatibility(
            config.source, config.destination
        )
        checks.extend(platform_checks)
        
        # Version compatibility (if available)
        version_checks = await self._check_version_compatibility(
            config.source, config.destination
        )
        checks.extend(version_checks)
        
        return checks
    
    async def _check_system_compatibility(
        self, source: SystemConfig, destination: SystemConfig
    ) -> CompatibilityCheck:
        """Check compatibility between source and destination system types"""
        
        source_type = source.type
        dest_type = destination.type
        
        # Get compatibility from matrix
        compatibility = self.system_compatibility.get(source_type, {}).get(
            dest_type, CompatibilityResult.INCOMPATIBLE
        )
        
        if compatibility == CompatibilityResult.COMPATIBLE:
            return CompatibilityCheck(
                name="System Compatibility",
                result=compatibility,
                message=f"Direct migration from {source_type.value} to {dest_type.value} is supported"
            )
        elif compatibility == CompatibilityResult.REQUIRES_CONVERSION:
            return CompatibilityCheck(
                name="System Compatibility",
                result=compatibility,
                message=f"Migration from {source_type.value} to {dest_type.value} requires data conversion",
                remediation="Review conversion requirements and test thoroughly",
                conversion_required=True,
                estimated_complexity="medium"
            )
        elif compatibility == CompatibilityResult.WARNING:
            return CompatibilityCheck(
                name="System Compatibility",
                result=compatibility,
                message=f"Migration from {source_type.value} to {dest_type.value} has limitations",
                remediation="Review migration limitations and plan accordingly",
                estimated_complexity="low"
            )
        else:
            return CompatibilityCheck(
                name="System Compatibility",
                result=compatibility,
                message=f"Direct migration from {source_type.value} to {dest_type.value} is not supported",
                remediation="Consider intermediate conversion steps or alternative migration paths",
                estimated_complexity="high"
            )
    
    async def _check_database_compatibility(
        self, source_db: DatabaseConfig, dest_db: DatabaseConfig
    ) -> CompatibilityCheck:
        """Check compatibility between source and destination databases"""
        
        source_type = source_db.type
        dest_type = dest_db.type
        
        # Get compatibility from matrix
        compatibility = self.database_compatibility.get(source_type, {}).get(
            dest_type, CompatibilityResult.INCOMPATIBLE
        )
        
        details = {
            "source_type": source_type.value,
            "destination_type": dest_type.value,
            "source_host": source_db.host,
            "destination_host": dest_db.host
        }
        
        if compatibility == CompatibilityResult.COMPATIBLE:
            return CompatibilityCheck(
                name="Database Compatibility",
                result=compatibility,
                message=f"Direct database migration from {source_type.value} to {dest_type.value} is supported",
                details=details
            )
        elif compatibility == CompatibilityResult.REQUIRES_CONVERSION:
            return CompatibilityCheck(
                name="Database Compatibility",
                result=compatibility,
                message=f"Database migration from {source_type.value} to {dest_type.value} requires schema conversion",
                details=details,
                remediation="Use database migration tools or export/import with schema conversion",
                conversion_required=True,
                estimated_complexity="medium"
            )
        else:
            return CompatibilityCheck(
                name="Database Compatibility",
                result=compatibility,
                message=f"Database migration from {source_type.value} to {dest_type.value} is not supported",
                details=details,
                remediation="Consider exporting data to compatible format or using ETL tools",
                estimated_complexity="high"
            )
    
    async def _check_transfer_compatibility(
        self, source: SystemConfig, dest: SystemConfig, transfer_method: TransferMethod
    ) -> CompatibilityCheck:
        """Check if transfer method is compatible with source and destination systems"""
        
        # Check source compatibility
        source_compatible_methods = self.transfer_compatibility.get(source.type, set())
        dest_compatible_methods = self.transfer_compatibility.get(dest.type, set())
        
        # If no specific restrictions, assume basic methods are supported
        if not source_compatible_methods:
            source_compatible_methods = {
                TransferMethod.SSH_SCP, TransferMethod.SSH_SFTP, 
                TransferMethod.RSYNC, TransferMethod.FTP, TransferMethod.FTPS,
                TransferMethod.HYBRID_SYNC
            }
        
        if not dest_compatible_methods:
            dest_compatible_methods = {
                TransferMethod.SSH_SCP, TransferMethod.SSH_SFTP,
                TransferMethod.RSYNC, TransferMethod.FTP, TransferMethod.FTPS,
                TransferMethod.HYBRID_SYNC
            }
        
        # Check if method is supported by both systems
        if (transfer_method in source_compatible_methods and 
            transfer_method in dest_compatible_methods):
            return CompatibilityCheck(
                name="Transfer Method Compatibility",
                result=CompatibilityResult.COMPATIBLE,
                message=f"Transfer method {transfer_method.value} is supported for both systems",
                details={
                    "transfer_method": transfer_method.value,
                    "source_type": source.type.value,
                    "destination_type": dest.type.value
                }
            )
        elif transfer_method in source_compatible_methods:
            return CompatibilityCheck(
                name="Transfer Method Compatibility",
                result=CompatibilityResult.INCOMPATIBLE,
                message=f"Transfer method {transfer_method.value} is not supported by destination system {dest.type.value}",
                details={
                    "transfer_method": transfer_method.value,
                    "supported_by_destination": list(dest_compatible_methods)
                },
                remediation=f"Use one of the supported methods: {', '.join(m.value for m in dest_compatible_methods)}"
            )
        elif transfer_method in dest_compatible_methods:
            return CompatibilityCheck(
                name="Transfer Method Compatibility",
                result=CompatibilityResult.INCOMPATIBLE,
                message=f"Transfer method {transfer_method.value} is not supported by source system {source.type.value}",
                details={
                    "transfer_method": transfer_method.value,
                    "supported_by_source": list(source_compatible_methods)
                },
                remediation=f"Use one of the supported methods: {', '.join(m.value for m in source_compatible_methods)}"
            )
        else:
            return CompatibilityCheck(
                name="Transfer Method Compatibility",
                result=CompatibilityResult.INCOMPATIBLE,
                message=f"Transfer method {transfer_method.value} is not supported by either system",
                details={
                    "transfer_method": transfer_method.value,
                    "supported_by_source": list(source_compatible_methods),
                    "supported_by_destination": list(dest_compatible_methods)
                },
                remediation="Choose a transfer method supported by both systems"
            )
    
    async def _check_platform_compatibility(
        self, source: SystemConfig, dest: SystemConfig
    ) -> List[CompatibilityCheck]:
        """Check platform-specific compatibility requirements"""
        checks = []
        
        # CMS-specific checks
        if source.type in [SystemType.WORDPRESS, SystemType.DRUPAL, SystemType.JOOMLA]:
            if dest.type in [SystemType.AWS_S3, SystemType.GOOGLE_CLOUD_STORAGE, SystemType.AZURE_BLOB]:
                checks.append(CompatibilityCheck(
                    name="CMS to Cloud Storage",
                    result=CompatibilityResult.WARNING,
                    message=f"Migrating {source.type.value} to cloud storage will only transfer static files",
                    remediation="Database and dynamic functionality will be lost. Consider containerized deployment instead."
                ))
        
        # Framework-specific checks
        if source.type in [SystemType.DJANGO, SystemType.FLASK, SystemType.FASTAPI]:
            if dest.type in [SystemType.AWS_S3, SystemType.GOOGLE_CLOUD_STORAGE, SystemType.AZURE_BLOB]:
                checks.append(CompatibilityCheck(
                    name="Framework to Cloud Storage",
                    result=CompatibilityResult.INCOMPATIBLE,
                    message=f"Cannot migrate {source.type.value} application to static cloud storage",
                    remediation="Use containerized deployment or cloud application services instead"
                ))
        
        # Control panel compatibility
        if source.control_panel and dest.type not in [
            SystemType.CPANEL, SystemType.DIRECTADMIN, SystemType.PLESK,
            SystemType.DOCKER_CONTAINER, SystemType.KUBERNETES_POD
        ]:
            checks.append(CompatibilityCheck(
                name="Control Panel Migration",
                result=CompatibilityResult.WARNING,
                message="Control panel configurations may not be fully transferable to destination system",
                remediation="Manual configuration may be required on destination system"
            ))
        
        # Cloud-specific checks
        if (source.cloud_config and dest.cloud_config and 
            source.cloud_config.provider != dest.cloud_config.provider):
            checks.append(CompatibilityCheck(
                name="Cross-Cloud Migration",
                result=CompatibilityResult.REQUIRES_CONVERSION,
                message=f"Migrating between different cloud providers ({source.cloud_config.provider} to {dest.cloud_config.provider})",
                remediation="Review cloud-specific configurations and adapt for destination provider",
                conversion_required=True,
                estimated_complexity="medium"
            ))
        
        return checks
    
    async def _check_version_compatibility(
        self, source: SystemConfig, dest: SystemConfig
    ) -> List[CompatibilityCheck]:
        """Check version compatibility between systems"""
        checks = []
        
        # Extract version information from custom_config if available
        source_version = source.custom_config.get('version')
        dest_version = dest.custom_config.get('version')
        
        if source_version and dest_version and source.type == dest.type:
            # Simple version comparison (this could be enhanced with proper semver)
            if source_version == dest_version:
                checks.append(CompatibilityCheck(
                    name="Version Compatibility",
                    result=CompatibilityResult.COMPATIBLE,
                    message=f"Source and destination versions match ({source_version})"
                ))
            else:
                # Determine if it's an upgrade or downgrade
                try:
                    source_parts = [int(x) for x in source_version.split('.')]
                    dest_parts = [int(x) for x in dest_version.split('.')]
                    
                    if source_parts < dest_parts:
                        checks.append(CompatibilityCheck(
                            name="Version Compatibility",
                            result=CompatibilityResult.WARNING,
                            message=f"Upgrading from {source_version} to {dest_version}",
                            remediation="Test migration thoroughly and review upgrade notes"
                        ))
                    else:
                        checks.append(CompatibilityCheck(
                            name="Version Compatibility",
                            result=CompatibilityResult.WARNING,
                            message=f"Downgrading from {source_version} to {dest_version}",
                            remediation="Downgrade may cause compatibility issues. Consider keeping same version."
                        ))
                except ValueError:
                    checks.append(CompatibilityCheck(
                        name="Version Compatibility",
                        result=CompatibilityResult.WARNING,
                        message=f"Cannot compare versions {source_version} and {dest_version}",
                        remediation="Manually verify version compatibility"
                    ))
        
        return checks
    
    def get_recommended_transfer_methods(
        self, source_type: SystemType, dest_type: SystemType
    ) -> List[TransferMethod]:
        """Get recommended transfer methods for given source and destination types"""
        
        source_methods = self.transfer_compatibility.get(source_type, set())
        dest_methods = self.transfer_compatibility.get(dest_type, set())
        
        # If no specific restrictions, use default methods
        if not source_methods:
            source_methods = {
                TransferMethod.SSH_SCP, TransferMethod.SSH_SFTP,
                TransferMethod.RSYNC, TransferMethod.HYBRID_SYNC
            }
        
        if not dest_methods:
            dest_methods = {
                TransferMethod.SSH_SCP, TransferMethod.SSH_SFTP,
                TransferMethod.RSYNC, TransferMethod.HYBRID_SYNC
            }
        
        # Return intersection of supported methods, prioritizing performance
        compatible_methods = source_methods.intersection(dest_methods)
        
        # Priority order (fastest/most reliable first)
        priority_order = [
            TransferMethod.HYBRID_SYNC,
            TransferMethod.RSYNC,
            TransferMethod.SSH_SFTP,
            TransferMethod.SSH_SCP,
            TransferMethod.AWS_S3,
            TransferMethod.GOOGLE_CLOUD_STORAGE,
            TransferMethod.AZURE_BLOB,
            TransferMethod.DOCKER_VOLUME,
            TransferMethod.KUBERNETES_VOLUME,
            TransferMethod.FTPS,
            TransferMethod.FTP,
            TransferMethod.LOCAL_COPY
        ]
        
        return [method for method in priority_order if method in compatible_methods]
    
    def get_conversion_requirements(
        self, source: SystemConfig, dest: SystemConfig
    ) -> Dict[str, Any]:
        """Get detailed conversion requirements for incompatible systems"""
        
        requirements = {
            "database_conversion": False,
            "file_conversion": False,
            "config_conversion": False,
            "custom_scripts": [],
            "manual_steps": [],
            "estimated_time": "unknown",
            "complexity": "low"
        }
        
        # Database conversion requirements
        if (source.database and dest.database and 
            source.database.type != dest.database.type):
            requirements["database_conversion"] = True
            requirements["complexity"] = "medium"
            
            if source.database.type in [DatabaseType.MYSQL, DatabaseType.POSTGRESQL]:
                if dest.database.type in [DatabaseType.MYSQL, DatabaseType.POSTGRESQL]:
                    requirements["custom_scripts"].append("SQL schema conversion script")
                    requirements["estimated_time"] = "2-4 hours"
                else:
                    requirements["manual_steps"].append("Export data to compatible format")
                    requirements["complexity"] = "high"
                    requirements["estimated_time"] = "4-8 hours"
        
        # System type conversion requirements
        if source.type != dest.type:
            if (source.type == SystemType.WORDPRESS and 
                dest.type in [SystemType.STATIC_SITE, SystemType.AWS_S3]):
                requirements["file_conversion"] = True
                requirements["custom_scripts"].append("WordPress to static site generator")
                requirements["manual_steps"].append("Configure static site hosting")
                requirements["estimated_time"] = "4-6 hours"
            
            elif (source.type in [SystemType.DJANGO, SystemType.FLASK] and
                  dest.type == SystemType.DOCKER_CONTAINER):
                requirements["config_conversion"] = True
                requirements["custom_scripts"].append("Dockerfile generation")
                requirements["custom_scripts"].append("Docker Compose configuration")
                requirements["estimated_time"] = "2-3 hours"
        
        return requirements