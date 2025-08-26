"""
Preset template system for easy creation of new migration presets.

This module provides templates and builders for common migration patterns,
making it easy to add new presets without writing configuration from scratch.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from migration_assistant.cli.preset_registry import (
    PresetMetadata, PresetConfiguration, SourceCategory, 
    DestinationCategory, ApplicationStack
)


@dataclass
class PresetTemplate:
    """Template for creating new presets with common patterns."""
    name: str
    description: str
    source_category: SourceCategory
    destination_category: DestinationCategory
    application_stack: ApplicationStack
    base_configuration: Dict[str, Any]
    customizable_fields: List[str]
    complexity: str = "medium"
    estimated_time: str = "30-60 minutes"
    tags: List[str] = None


class PresetTemplateBuilder:
    """Builder for creating preset templates and configurations."""
    
    def __init__(self):
        self.templates = self._initialize_templates()
    
    def _initialize_templates(self) -> Dict[str, PresetTemplate]:
        """Initialize built-in preset templates."""
        return {
            "control_panel_to_vps": PresetTemplate(
                name="Control Panel to VPS",
                description="Migrate from control panel hosting to VPS",
                source_category=SourceCategory.CONTROL_PANEL,
                destination_category=DestinationCategory.VPS_SERVER,
                application_stack=ApplicationStack.GENERIC_WEBSITE,
                base_configuration={
                    "source": {
                        "type": "cpanel",
                        "authentication": {"type": "api_key"},
                        "control_panel": {
                            "type": "cpanel",
                            "port": 2083,
                            "ssl_enabled": True
                        }
                    },
                    "destination": {
                        "type": "static_site",
                        "authentication": {"type": "ssh_key"},
                        "paths": {"root_path": "/var/www/html"}
                    },
                    "transfer": {
                        "method": "hybrid_sync",
                        "parallel_transfers": 6,
                        "compression_enabled": True,
                        "verify_checksums": True,
                        "use_go_acceleration": True
                    },
                    "options": {
                        "maintenance_mode": True,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True,
                        "preserve_email_accounts": True,
                        "migrate_dns_records": True
                    }
                },
                customizable_fields=[
                    "source.control_panel.type",
                    "source.control_panel.port",
                    "destination.paths.root_path",
                    "transfer.parallel_transfers"
                ],
                tags=["control_panel", "vps", "migration"]
            ),
            
            "cms_to_vps": PresetTemplate(
                name="CMS to VPS",
                description="Migrate CMS application to VPS",
                source_category=SourceCategory.CMS_PLATFORM,
                destination_category=DestinationCategory.VPS_SERVER,
                application_stack=ApplicationStack.WORDPRESS,
                base_configuration={
                    "source": {
                        "type": "wordpress",
                        "authentication": {"type": "ssh_key", "username": "www-data"},
                        "paths": {
                            "root_path": "/var/www/html",
                            "config_path": "/var/www/html/wp-config.php"
                        },
                        "database": {
                            "type": "mysql",
                            "host": "localhost",
                            "port": 3306,
                            "database_name": "cms_db"
                        }
                    },
                    "destination": {
                        "type": "wordpress",
                        "authentication": {"type": "ssh_key", "username": "www-data"},
                        "paths": {"root_path": "/var/www/html"},
                        "database": {
                            "type": "mysql",
                            "host": "localhost",
                            "port": 3306,
                            "database_name": "cms_db"
                        }
                    },
                    "transfer": {
                        "method": "rsync",
                        "parallel_transfers": 4,
                        "compression_enabled": True,
                        "verify_checksums": True
                    },
                    "options": {
                        "maintenance_mode": True,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True,
                        "preserve_permissions": True
                    }
                },
                customizable_fields=[
                    "source.type",
                    "destination.type",
                    "source.database.type",
                    "destination.database.type",
                    "source.database.database_name",
                    "destination.database.database_name"
                ],
                tags=["cms", "vps", "database"]
            ),
            
            "static_to_cloud": PresetTemplate(
                name="Static Site to Cloud",
                description="Deploy static site to cloud storage",
                source_category=SourceCategory.STATIC_HOSTING,
                destination_category=DestinationCategory.CLOUD_PLATFORM,
                application_stack=ApplicationStack.STATIC_SITE,
                base_configuration={
                    "source": {
                        "type": "static_site",
                        "authentication": {"type": "ssh_key"},
                        "paths": {"root_path": "/var/www/html"}
                    },
                    "destination": {
                        "type": "aws_s3",
                        "host": "s3.amazonaws.com",
                        "authentication": {"type": "aws_iam"},
                        "paths": {"root_path": "/"},
                        "cloud_config": {
                            "provider": "aws",
                            "region": "us-east-1",
                            "bucket_name": "static-website"
                        }
                    },
                    "transfer": {
                        "method": "aws_s3",
                        "parallel_transfers": 10,
                        "compression_enabled": False,
                        "verify_checksums": True
                    },
                    "options": {
                        "maintenance_mode": False,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True
                    }
                },
                customizable_fields=[
                    "destination.type",
                    "destination.cloud_config.provider",
                    "destination.cloud_config.region",
                    "destination.cloud_config.bucket_name",
                    "transfer.method"
                ],
                complexity="simple",
                estimated_time="15-30 minutes",
                tags=["static", "cloud", "storage"]
            ),
            
            "framework_to_vps": PresetTemplate(
                name="Framework to VPS",
                description="Migrate web framework application to VPS",
                source_category=SourceCategory.FRAMEWORK,
                destination_category=DestinationCategory.VPS_SERVER,
                application_stack=ApplicationStack.DJANGO,
                base_configuration={
                    "source": {
                        "type": "django",
                        "authentication": {"type": "ssh_key", "username": "app"},
                        "paths": {
                            "root_path": "/opt/app",
                            "config_path": "/opt/app/settings.py"
                        },
                        "database": {
                            "type": "postgresql",
                            "host": "localhost",
                            "port": 5432,
                            "database_name": "app_db"
                        }
                    },
                    "destination": {
                        "type": "django",
                        "authentication": {"type": "ssh_key", "username": "app"},
                        "paths": {"root_path": "/opt/app"},
                        "database": {
                            "type": "postgresql",
                            "host": "localhost",
                            "port": 5432,
                            "database_name": "app_db"
                        }
                    },
                    "transfer": {
                        "method": "ssh_sftp",
                        "parallel_transfers": 6,
                        "compression_enabled": True,
                        "verify_checksums": True
                    },
                    "options": {
                        "maintenance_mode": True,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True,
                        "preserve_permissions": True
                    }
                },
                customizable_fields=[
                    "source.type",
                    "destination.type",
                    "source.database.type",
                    "destination.database.type",
                    "source.authentication.username",
                    "destination.authentication.username"
                ],
                tags=["framework", "vps", "database"]
            ),
            
            "container_to_orchestrator": PresetTemplate(
                name="Container to Orchestrator",
                description="Migrate container to orchestration platform",
                source_category=SourceCategory.CONTAINER,
                destination_category=DestinationCategory.CONTAINER_PLATFORM,
                application_stack=ApplicationStack.GENERIC_WEBSITE,
                base_configuration={
                    "source": {
                        "type": "docker_container",
                        "authentication": {"type": "ssh_key", "username": "docker"},
                        "paths": {"root_path": "/var/lib/docker"}
                    },
                    "destination": {
                        "type": "kubernetes_pod",
                        "authentication": {"type": "api_key", "username": "k8s-admin"},
                        "paths": {"root_path": "/opt/k8s"}
                    },
                    "transfer": {
                        "method": "kubernetes_volume",
                        "parallel_transfers": 4,
                        "compression_enabled": True,
                        "verify_checksums": True
                    },
                    "options": {
                        "maintenance_mode": True,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True
                    }
                },
                customizable_fields=[
                    "source.type",
                    "destination.type",
                    "transfer.method",
                    "destination.authentication.username"
                ],
                complexity="complex",
                estimated_time="60-120 minutes",
                tags=["container", "orchestration", "kubernetes"]
            )
        }
    
    def get_template(self, template_name: str) -> Optional[PresetTemplate]:
        """Get a specific template by name."""
        return self.templates.get(template_name)
    
    def list_templates(self) -> List[PresetTemplate]:
        """Get all available templates."""
        return list(self.templates.values())
    
    def create_preset_from_template(
        self,
        template_name: str,
        preset_key: str,
        preset_name: str,
        customizations: Optional[Dict[str, Any]] = None,
        description_override: Optional[str] = None,
        tags_override: Optional[List[str]] = None
    ) -> Optional[PresetConfiguration]:
        """
        Create a new preset from a template with customizations.
        
        Args:
            template_name: Name of the template to use
            preset_key: Unique key for the new preset
            preset_name: Display name for the new preset
            customizations: Dictionary of field paths to new values
            description_override: Override the template description
            tags_override: Override the template tags
            
        Returns:
            PresetConfiguration if successful, None otherwise
        """
        template = self.templates.get(template_name)
        if not template:
            return None
        
        # Create metadata
        metadata = PresetMetadata(
            key=preset_key,
            name=preset_name,
            description=description_override or template.description,
            source_category=template.source_category,
            destination_category=template.destination_category,
            application_stack=template.application_stack,
            complexity=template.complexity,
            estimated_time=template.estimated_time,
            prerequisites=[],
            tags=tags_override or template.tags or [],
            version="1.0",
            author="Migration Assistant",
            created_date=datetime.now().isoformat(),
            updated_date=datetime.now().isoformat()
        )
        
        # Start with base configuration
        configuration = self._deep_copy_dict(template.base_configuration)
        
        # Apply customizations
        if customizations:
            for field_path, value in customizations.items():
                self._set_nested_value(configuration, field_path, value)
        
        return PresetConfiguration(
            metadata=metadata,
            configuration=configuration
        )
    
    def get_customizable_fields(self, template_name: str) -> List[str]:
        """Get the list of customizable fields for a template."""
        template = self.templates.get(template_name)
        return template.customizable_fields if template else []
    
    def validate_customizations(
        self, 
        template_name: str, 
        customizations: Dict[str, Any]
    ) -> List[str]:
        """
        Validate customizations against template.
        
        Returns:
            List of validation errors (empty if valid)
        """
        template = self.templates.get(template_name)
        if not template:
            return ["Template not found"]
        
        errors = []
        
        for field_path in customizations.keys():
            if field_path not in template.customizable_fields:
                errors.append(f"Field '{field_path}' is not customizable in this template")
        
        return errors
    
    def _deep_copy_dict(self, original: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of a dictionary."""
        import copy
        return copy.deepcopy(original)
    
    def _set_nested_value(self, dictionary: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested value in a dictionary using dot notation."""
        keys = path.split('.')
        current = dictionary
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = value


class PresetGenerator:
    """Generator for creating presets from common patterns."""
    
    def __init__(self):
        self.builder = PresetTemplateBuilder()
    
    def generate_control_panel_presets(self) -> List[PresetConfiguration]:
        """Generate presets for all control panel types."""
        presets = []
        
        control_panels = [
            ("cpanel", "cPanel", 2083),
            ("directadmin", "DirectAdmin", 2222),
            ("plesk", "Plesk", 8443)
        ]
        
        destinations = [
            ("linux", "Linux VPS", "static_site"),
            ("docker", "Docker Container", "docker_container"),
            ("aws", "AWS Cloud", "aws_s3")
        ]
        
        for cp_key, cp_name, cp_port in control_panels:
            for dest_key, dest_name, dest_type in destinations:
                preset_key = f"{cp_key}-to-{dest_key}"
                preset_name = f"{cp_name} to {dest_name}"
                
                customizations = {
                    "source.control_panel.type": cp_key,
                    "source.control_panel.port": cp_port,
                    "destination.type": dest_type
                }
                
                if dest_type == "aws_s3":
                    customizations.update({
                        "destination.cloud_config.provider": "aws",
                        "transfer.method": "aws_s3"
                    })
                elif dest_type == "docker_container":
                    customizations.update({
                        "transfer.method": "docker_volume"
                    })
                
                preset = self.builder.create_preset_from_template(
                    "control_panel_to_vps",
                    preset_key,
                    preset_name,
                    customizations,
                    tags_override=[cp_key, dest_key, "migration", "automated"]
                )
                
                if preset:
                    presets.append(preset)
        
        return presets
    
    def generate_cms_presets(self) -> List[PresetConfiguration]:
        """Generate presets for popular CMS platforms."""
        presets = []
        
        cms_configs = [
            ("wordpress", "WordPress", "mysql", "/var/www/html", "/var/www/html/wp-config.php"),
            ("drupal", "Drupal", "mysql", "/var/www/html", "/var/www/html/sites/default/settings.php"),
            ("joomla", "Joomla", "mysql", "/var/www/html", "/var/www/html/configuration.php"),
            ("magento2", "Magento 2", "mysql", "/var/www/html", "/var/www/html/app/etc/env.php"),
            ("prestashop", "PrestaShop", "mysql", "/var/www/html", "/var/www/html/config/settings.inc.php")
        ]
        
        for cms_key, cms_name, db_type, root_path, config_path in cms_configs:
            preset_key = f"{cms_key}-{db_type}"
            preset_name = f"{cms_name} with {db_type.upper()}"
            
            customizations = {
                "source.type": cms_key,
                "destination.type": cms_key,
                "source.database.type": db_type,
                "destination.database.type": db_type,
                "source.paths.root_path": root_path,
                "source.paths.config_path": config_path,
                "destination.paths.root_path": root_path
            }
            
            preset = self.builder.create_preset_from_template(
                "cms_to_vps",
                preset_key,
                preset_name,
                customizations,
                description_override=f"Standard {cms_name} site with {db_type.upper()} database migration",
                tags_override=[cms_key, db_type, "cms", "php" if cms_key != "django" else "python"]
            )
            
            if preset:
                presets.append(preset)
        
        return presets
    
    def generate_framework_presets(self) -> List[PresetConfiguration]:
        """Generate presets for web frameworks."""
        presets = []
        
        frameworks = [
            ("django", "Django", "postgresql", "python", "/opt/django-app", "django"),
            ("laravel", "Laravel", "mysql", "php", "/var/www/laravel", "www-data"),
            ("rails", "Ruby on Rails", "postgresql", "ruby", "/opt/rails-app", "rails"),
            ("flask", "Flask", "postgresql", "python", "/opt/flask-app", "flask"),
            ("fastapi", "FastAPI", "postgresql", "python", "/opt/fastapi-app", "fastapi"),
            ("spring_boot", "Spring Boot", "postgresql", "java", "/opt/spring-app", "spring")
        ]
        
        for fw_key, fw_name, db_type, lang, root_path, username in frameworks:
            preset_key = f"{fw_key}-{db_type}"
            preset_name = f"{fw_name} with {db_type.title()}"
            
            customizations = {
                "source.type": fw_key,
                "destination.type": fw_key,
                "source.database.type": db_type,
                "destination.database.type": db_type,
                "source.paths.root_path": root_path,
                "destination.paths.root_path": root_path,
                "source.authentication.username": username,
                "destination.authentication.username": username
            }
            
            preset = self.builder.create_preset_from_template(
                "framework_to_vps",
                preset_key,
                preset_name,
                customizations,
                description_override=f"{fw_name} application with {db_type.title()} database migration",
                tags_override=[fw_key, db_type, "framework", lang]
            )
            
            if preset:
                presets.append(preset)
        
        return presets
    
    def generate_all_presets(self) -> List[PresetConfiguration]:
        """Generate all available preset variations."""
        all_presets = []
        
        all_presets.extend(self.generate_control_panel_presets())
        all_presets.extend(self.generate_cms_presets())
        all_presets.extend(self.generate_framework_presets())
        
        return all_presets