"""
Preset management system for the Migration Assistant.

This module provides preset management for common platform configurations
like WordPress/MySQL, Django/Postgres, etc., with auto-population and
custom configuration support.
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import json
from pathlib import Path

from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, AuthConfig, PathConfig, DatabaseConfig,
    TransferConfig, MigrationOptions, SystemType, AuthType, DatabaseType,
    TransferMethod
)


class PresetType(str, Enum):
    """Available preset types."""
    WORDPRESS_MYSQL = "wordpress-mysql"
    WORDPRESS_MYSQL_TO_S3 = "wordpress-mysql-to-s3"
    DJANGO_POSTGRES = "django-postgres"
    DJANGO_POSTGRES_TO_GCS = "django-postgres-to-gcs"
    LARAVEL_MYSQL = "laravel-mysql"
    RAILS_POSTGRES = "rails-postgres"
    STATIC_TO_S3 = "static-to-s3"
    STATIC_TO_NETLIFY = "static-to-netlify"
    CPANEL_TO_AWS = "cpanel-to-aws"
    CPANEL_TO_DOCKER = "cpanel-to-docker"
    DOCKER_TO_K8S = "docker-to-k8s"
    NEXTJS_VERCEL = "nextjs-vercel"


class PresetManager:
    """Manages migration presets with auto-population and customization."""
    
    def __init__(self):
        self._presets = self._initialize_presets()
        self._custom_presets: Dict[str, Dict[str, Any]] = {}
    
    def get_available_presets(self) -> List[Tuple[str, str, str]]:
        """
        Get list of available presets.
        
        Returns:
            List of tuples: (preset_key, name, description)
        """
        presets = []
        
        # Built-in presets
        for preset_type in PresetType:
            preset_data = self._presets.get(preset_type.value, {})
            presets.append((
                preset_type.value,
                preset_data.get("name", preset_type.value),
                preset_data.get("description", "No description available")
            ))
        
        # Custom presets
        for key, preset_data in self._custom_presets.items():
            presets.append((
                key,
                preset_data.get("name", key),
                preset_data.get("description", "Custom preset")
            ))
        
        return presets
    
    def get_preset_config(self, preset_key: str) -> Optional[Dict[str, Any]]:
        """
        Get preset configuration by key.
        
        Args:
            preset_key: Preset identifier
            
        Returns:
            Preset configuration dictionary or None if not found
        """
        # Check built-in presets
        if preset_key in [p.value for p in PresetType]:
            return self._presets.get(preset_key)
        
        # Check custom presets
        return self._custom_presets.get(preset_key)
    
    def create_migration_config_from_preset(
        self, 
        preset_key: str, 
        overrides: Optional[Dict[str, Any]] = None
    ) -> Optional[MigrationConfig]:
        """
        Create a MigrationConfig from a preset with optional overrides.
        
        Args:
            preset_key: Preset identifier
            overrides: Dictionary of values to override in the preset
            
        Returns:
            MigrationConfig instance or None if preset not found
        """
        preset_data = self.get_preset_config(preset_key)
        if not preset_data:
            return None
        
        # Apply overrides if provided
        if overrides:
            preset_data = self._merge_overrides(preset_data.copy(), overrides)
        
        try:
            # Create configuration objects
            source_config = SystemConfig(**preset_data["source"])
            destination_config = SystemConfig(**preset_data["destination"])
            transfer_config = TransferConfig(**preset_data["transfer"])
            options_config = MigrationOptions(**preset_data["options"])
            
            return MigrationConfig(
                name=preset_data["name"],
                description=preset_data.get("description"),
                source=source_config,
                destination=destination_config,
                transfer=transfer_config,
                options=options_config
            )
        except Exception as e:
            raise ValueError(f"Failed to create migration config from preset: {e}")
    
    def save_custom_preset(
        self, 
        name: str, 
        config: MigrationConfig, 
        description: Optional[str] = None
    ) -> str:
        """
        Save a migration configuration as a custom preset.
        
        Args:
            name: Preset name
            config: MigrationConfig to save as preset
            description: Optional description
            
        Returns:
            Preset key for the saved preset
        """
        preset_key = name.lower().replace(" ", "-").replace("_", "-")
        
        preset_data = {
            "name": name,
            "description": description or f"Custom preset: {name}",
            "source": config.source.model_dump(),
            "destination": config.destination.model_dump(),
            "transfer": config.transfer.model_dump(),
            "options": config.options.model_dump(),
            "custom": True
        }
        
        self._custom_presets[preset_key] = preset_data
        return preset_key
    
    def delete_custom_preset(self, preset_key: str) -> bool:
        """
        Delete a custom preset.
        
        Args:
            preset_key: Preset identifier
            
        Returns:
            True if deleted, False if not found or is built-in preset
        """
        if preset_key in self._custom_presets:
            del self._custom_presets[preset_key]
            return True
        return False
    
    def get_preset_suggestions(self, source_type: SystemType, destination_type: SystemType) -> List[str]:
        """
        Get preset suggestions based on source and destination types.
        
        Args:
            source_type: Source system type
            destination_type: Destination system type
            
        Returns:
            List of suggested preset keys
        """
        suggestions = []
        
        # Define preset mappings
        preset_mappings = {
            (SystemType.WORDPRESS, SystemType.AWS_S3): [PresetType.WORDPRESS_MYSQL_TO_S3.value],
            (SystemType.WORDPRESS, SystemType.WORDPRESS): [PresetType.WORDPRESS_MYSQL.value],
            (SystemType.DJANGO, SystemType.GOOGLE_CLOUD_STORAGE): [PresetType.DJANGO_POSTGRES_TO_GCS.value],
            (SystemType.DJANGO, SystemType.DJANGO): [PresetType.DJANGO_POSTGRES.value],
            (SystemType.STATIC_SITE, SystemType.AWS_S3): [PresetType.STATIC_TO_S3.value],
            (SystemType.CPANEL, SystemType.AWS_S3): [PresetType.CPANEL_TO_AWS.value],
            (SystemType.CPANEL, SystemType.DOCKER_CONTAINER): [PresetType.CPANEL_TO_DOCKER.value],
            (SystemType.DOCKER_CONTAINER, SystemType.KUBERNETES_POD): [PresetType.DOCKER_TO_K8S.value],
            (SystemType.NEXTJS, SystemType.AWS_S3): [PresetType.NEXTJS_VERCEL.value],
        }
        
        # Get direct matches
        direct_matches = preset_mappings.get((source_type, destination_type), [])
        suggestions.extend(direct_matches)
        
        # Get partial matches (same source type)
        for (src, dst), presets in preset_mappings.items():
            if src == source_type and (source_type, destination_type) not in preset_mappings:
                suggestions.extend(presets)
        
        return list(set(suggestions))  # Remove duplicates
    
    def _initialize_presets(self) -> Dict[str, Dict[str, Any]]:
        """Initialize built-in presets."""
        return {
            PresetType.WORDPRESS_MYSQL.value: {
                "name": "WordPress with MySQL",
                "description": "Standard WordPress site with MySQL database migration",
                "source": {
                    "type": SystemType.WORDPRESS.value,
                    "host": "source.example.com",
                    "authentication": {
                        "type": AuthType.SSH_KEY.value,
                        "username": "www-data"
                    },
                    "paths": {
                        "root_path": "/var/www/html",
                        "web_root": "/var/www/html",
                        "config_path": "/var/www/html/wp-config.php"
                    },
                    "database": {
                        "type": DatabaseType.MYSQL.value,
                        "host": "localhost",
                        "port": 3306,
                        "database_name": "wordpress",
                        "username": "wp_user"
                    }
                },
                "destination": {
                    "type": SystemType.WORDPRESS.value,
                    "host": "destination.example.com",
                    "authentication": {
                        "type": AuthType.SSH_KEY.value,
                        "username": "www-data"
                    },
                    "paths": {
                        "root_path": "/var/www/html",
                        "web_root": "/var/www/html"
                    },
                    "database": {
                        "type": DatabaseType.MYSQL.value,
                        "host": "localhost",
                        "port": 3306,
                        "database_name": "wordpress",
                        "username": "wp_user"
                    }
                },
                "transfer": {
                    "method": TransferMethod.RSYNC.value,
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
            
            PresetType.WORDPRESS_MYSQL_TO_S3.value: {
                "name": "WordPress to AWS S3",
                "description": "Migrate WordPress site to AWS S3 static hosting",
                "source": {
                    "type": SystemType.WORDPRESS.value,
                    "host": "source.example.com",
                    "authentication": {
                        "type": AuthType.SSH_KEY.value,
                        "username": "www-data"
                    },
                    "paths": {
                        "root_path": "/var/www/html"
                    },
                    "database": {
                        "type": DatabaseType.MYSQL.value,
                        "host": "localhost",
                        "port": 3306,
                        "database_name": "wordpress",
                        "username": "wp_user"
                    }
                },
                "destination": {
                    "type": SystemType.AWS_S3.value,
                    "host": "s3.amazonaws.com",
                    "authentication": {
                        "type": AuthType.AWS_IAM.value
                    },
                    "paths": {
                        "root_path": "/"
                    },
                    "cloud_config": {
                        "provider": "aws",
                        "region": "us-east-1",
                        "bucket_name": "my-wordpress-site"
                    }
                },
                "transfer": {
                    "method": TransferMethod.AWS_S3.value,
                    "parallel_transfers": 8,
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
            
            PresetType.DJANGO_POSTGRES.value: {
                "name": "Django with PostgreSQL",
                "description": "Django application with PostgreSQL database migration",
                "source": {
                    "type": SystemType.DJANGO.value,
                    "host": "source.example.com",
                    "authentication": {
                        "type": AuthType.SSH_KEY.value,
                        "username": "django"
                    },
                    "paths": {
                        "root_path": "/opt/django-app",
                        "config_path": "/opt/django-app/settings.py"
                    },
                    "database": {
                        "type": DatabaseType.POSTGRESQL.value,
                        "host": "localhost",
                        "port": 5432,
                        "database_name": "django_db",
                        "username": "django_user"
                    }
                },
                "destination": {
                    "type": SystemType.DJANGO.value,
                    "host": "destination.example.com",
                    "authentication": {
                        "type": AuthType.SSH_KEY.value,
                        "username": "django"
                    },
                    "paths": {
                        "root_path": "/opt/django-app"
                    },
                    "database": {
                        "type": DatabaseType.POSTGRESQL.value,
                        "host": "localhost",
                        "port": 5432,
                        "database_name": "django_db",
                        "username": "django_user"
                    }
                },
                "transfer": {
                    "method": TransferMethod.SSH_SFTP.value,
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
            
            PresetType.STATIC_TO_S3.value: {
                "name": "Static Site to S3",
                "description": "Static website migration to AWS S3",
                "source": {
                    "type": SystemType.STATIC_SITE.value,
                    "host": "source.example.com",
                    "authentication": {
                        "type": AuthType.SSH_KEY.value,
                        "username": "www-data"
                    },
                    "paths": {
                        "root_path": "/var/www/html"
                    }
                },
                "destination": {
                    "type": SystemType.AWS_S3.value,
                    "host": "s3.amazonaws.com",
                    "authentication": {
                        "type": AuthType.AWS_IAM.value
                    },
                    "paths": {
                        "root_path": "/"
                    },
                    "cloud_config": {
                        "provider": "aws",
                        "region": "us-east-1",
                        "bucket_name": "my-static-site"
                    }
                },
                "transfer": {
                    "method": TransferMethod.AWS_S3.value,
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
            
            PresetType.CPANEL_TO_AWS.value: {
                "name": "cPanel to AWS",
                "description": "Migrate from cPanel hosting to AWS infrastructure",
                "source": {
                    "type": SystemType.CPANEL.value,
                    "host": "cpanel.example.com",
                    "authentication": {
                        "type": AuthType.API_KEY.value,
                        "username": "cpanel_user"
                    },
                    "paths": {
                        "root_path": "/home/cpanel_user/public_html"
                    },
                    "control_panel": {
                        "type": "cpanel",
                        "host": "cpanel.example.com",
                        "port": 2083,
                        "username": "cpanel_user",
                        "ssl_enabled": True
                    }
                },
                "destination": {
                    "type": SystemType.AWS_S3.value,
                    "host": "s3.amazonaws.com",
                    "authentication": {
                        "type": AuthType.AWS_IAM.value
                    },
                    "paths": {
                        "root_path": "/"
                    },
                    "cloud_config": {
                        "provider": "aws",
                        "region": "us-east-1",
                        "bucket_name": "migrated-cpanel-site"
                    }
                },
                "transfer": {
                    "method": TransferMethod.HYBRID_SYNC.value,
                    "parallel_transfers": 8,
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
            
            PresetType.DOCKER_TO_K8S.value: {
                "name": "Docker to Kubernetes",
                "description": "Migrate Docker container to Kubernetes deployment",
                "source": {
                    "type": SystemType.DOCKER_CONTAINER.value,
                    "host": "docker.example.com",
                    "authentication": {
                        "type": AuthType.SSH_KEY.value,
                        "username": "docker"
                    },
                    "paths": {
                        "root_path": "/var/lib/docker"
                    }
                },
                "destination": {
                    "type": SystemType.KUBERNETES_POD.value,
                    "host": "k8s.example.com",
                    "authentication": {
                        "type": AuthType.API_KEY.value,
                        "username": "k8s-admin"
                    },
                    "paths": {
                        "root_path": "/opt/k8s"
                    }
                },
                "transfer": {
                    "method": TransferMethod.KUBERNETES_VOLUME.value,
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
            }
        }
    
    def _merge_overrides(self, preset_data: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge override values into preset data.
        
        Args:
            preset_data: Original preset configuration
            overrides: Values to override
            
        Returns:
            Merged configuration
        """
        for key, value in overrides.items():
            if key in preset_data:
                if isinstance(preset_data[key], dict) and isinstance(value, dict):
                    preset_data[key] = self._merge_overrides(preset_data[key], value)
                else:
                    preset_data[key] = value
            else:
                preset_data[key] = value
        
        return preset_data
    
    def export_preset(self, preset_key: str, file_path: str) -> bool:
        """
        Export a preset to a JSON file.
        
        Args:
            preset_key: Preset identifier
            file_path: Path to save the preset file
            
        Returns:
            True if exported successfully, False otherwise
        """
        preset_data = self.get_preset_config(preset_key)
        if not preset_data:
            return False
        
        try:
            with open(file_path, 'w') as f:
                json.dump(preset_data, f, indent=2, default=str)
            return True
        except Exception:
            return False
    
    def import_preset(self, file_path: str, name: Optional[str] = None) -> Optional[str]:
        """
        Import a preset from a JSON file.
        
        Args:
            file_path: Path to the preset file
            name: Optional name for the imported preset
            
        Returns:
            Preset key if imported successfully, None otherwise
        """
        try:
            with open(file_path, 'r') as f:
                preset_data = json.load(f)
            
            preset_name = name or preset_data.get("name", Path(file_path).stem)
            preset_key = preset_name.lower().replace(" ", "-").replace("_", "-")
            
            # Validate the preset structure
            required_keys = ["source", "destination", "transfer", "options"]
            if not all(key in preset_data for key in required_keys):
                return None
            
            preset_data["name"] = preset_name
            preset_data["custom"] = True
            
            self._custom_presets[preset_key] = preset_data
            return preset_key
            
        except Exception:
            return None