"""
Flexible preset registry system for the Migration Assistant.

This module provides a hierarchical, extensible preset system that supports
easy addition of new migration patterns without code changes.
"""

from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import json

from migration_assistant.models.config import (
    SystemType, AuthType, DatabaseType, TransferMethod, ControlPanelType
)


class SourceCategory(str, Enum):
    """Source system categories for hierarchical organization."""
    CONTROL_PANEL = "control_panel"
    VPS_SERVER = "vps_server"
    CLOUD_PLATFORM = "cloud_platform"
    CONTAINER = "container"
    STATIC_HOSTING = "static_hosting"
    CMS_PLATFORM = "cms_platform"
    FRAMEWORK = "framework"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"


class DestinationCategory(str, Enum):
    """Destination system categories for hierarchical organization."""
    VPS_SERVER = "vps_server"
    CLOUD_PLATFORM = "cloud_platform"
    CONTAINER_PLATFORM = "container_platform"
    STATIC_HOSTING = "static_hosting"
    MANAGED_HOSTING = "managed_hosting"
    DATABASE_SERVICE = "database_service"
    CDN_SERVICE = "cdn_service"


class ApplicationStack(str, Enum):
    """Application stack types for specific configurations."""
    GENERIC_WEBSITE = "generic_website"
    WORDPRESS = "wordpress"
    DRUPAL = "drupal"
    JOOMLA = "joomla"
    DJANGO = "django"
    LARAVEL = "laravel"
    NEXTJS = "nextjs"
    HUGO = "hugo"
    GATSBY = "gatsby"
    MAGENTO2 = "magento2"
    SHOPWARE = "shopware"
    PRESTASHOP = "prestashop"
    PHPBB = "phpbb"
    TYPO3 = "typo3"
    STATIC_SITE = "static_site"
    REACT_APP = "react_app"
    VUE_APP = "vue_app"
    ANGULAR_APP = "angular_app"
    FLASK_APP = "flask_app"
    FASTAPI_APP = "fastapi_app"
    RAILS_APP = "rails_app"
    SPRING_BOOT_APP = "spring_boot_app"


@dataclass
class PresetMetadata:
    """Metadata for a migration preset."""
    key: str
    name: str
    description: str
    source_category: SourceCategory
    destination_category: DestinationCategory
    application_stack: ApplicationStack
    complexity: str = "medium"  # simple, medium, complex
    estimated_time: str = "30-60 minutes"
    prerequisites: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0"
    author: str = "Migration Assistant"
    created_date: str = ""
    updated_date: str = ""


@dataclass
class PresetConfiguration:
    """Complete preset configuration including metadata and config."""
    metadata: PresetMetadata
    configuration: Dict[str, Any]


class PresetRegistry:
    """
    Hierarchical preset registry with dynamic loading and filtering capabilities.
    
    This registry supports:
    - Hierarchical organization (Source → Destination → Application)
    - Dynamic preset loading from files
    - Filtering and searching
    - Easy extension without code changes
    """
    
    def __init__(self, preset_dir: Optional[str] = None):
        """
        Initialize the preset registry.
        
        Args:
            preset_dir: Directory containing preset files. Defaults to built-in presets.
        """
        self.preset_dir = Path(preset_dir) if preset_dir else Path(__file__).parent / "presets"
        self.presets: Dict[str, PresetConfiguration] = {}
        self._load_presets()
    
    def _load_presets(self) -> None:
        """Load all presets from the preset directory and built-in definitions."""
        # Load built-in presets first
        self._load_builtin_presets()
        
        # Load external preset files if directory exists
        if self.preset_dir.exists():
            self._load_external_presets()
    
    def _load_builtin_presets(self) -> None:
        """Load built-in preset definitions."""
        builtin_presets = self._get_builtin_preset_definitions()
        
        for preset_data in builtin_presets:
            metadata = PresetMetadata(**preset_data["metadata"])
            config = PresetConfiguration(
                metadata=metadata,
                configuration=preset_data["configuration"]
            )
            self.presets[metadata.key] = config
    
    def _load_external_presets(self) -> None:
        """Load presets from external YAML/JSON files."""
        for preset_file in self.preset_dir.glob("*.yaml"):
            try:
                with open(preset_file, 'r') as f:
                    preset_data = yaml.safe_load(f)
                    self._register_preset_from_data(preset_data)
            except Exception as e:
                print(f"Warning: Failed to load preset from {preset_file}: {e}")
        
        for preset_file in self.preset_dir.glob("*.json"):
            try:
                with open(preset_file, 'r') as f:
                    preset_data = json.load(f)
                    self._register_preset_from_data(preset_data)
            except Exception as e:
                print(f"Warning: Failed to load preset from {preset_file}: {e}")
    
    def _register_preset_from_data(self, preset_data: Dict[str, Any]) -> None:
        """Register a preset from loaded data."""
        metadata = PresetMetadata(**preset_data["metadata"])
        config = PresetConfiguration(
            metadata=metadata,
            configuration=preset_data["configuration"]
        )
        self.presets[metadata.key] = config
    
    def get_preset(self, key: str) -> Optional[PresetConfiguration]:
        """Get a specific preset by key."""
        return self.presets.get(key)
    
    def list_presets(self) -> List[PresetConfiguration]:
        """Get all available presets."""
        return list(self.presets.values())
    
    def get_hierarchical_structure(self) -> Dict[str, Dict[str, Dict[str, List[PresetConfiguration]]]]:
        """
        Get presets organized in a hierarchical structure.
        
        Returns:
            Dict[source_category][destination_category][application_stack] = [presets]
        """
        structure = {}
        
        for preset in self.presets.values():
            source = preset.metadata.source_category.value
            dest = preset.metadata.destination_category.value
            app = preset.metadata.application_stack.value
            
            if source not in structure:
                structure[source] = {}
            if dest not in structure[source]:
                structure[source][dest] = {}
            if app not in structure[source][dest]:
                structure[source][dest][app] = []
            
            structure[source][dest][app].append(preset)
        
        return structure
    
    def filter_presets(
        self,
        source_category: Optional[SourceCategory] = None,
        destination_category: Optional[DestinationCategory] = None,
        application_stack: Optional[ApplicationStack] = None,
        complexity: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[PresetConfiguration]:
        """
        Filter presets based on criteria.
        
        Args:
            source_category: Filter by source category
            destination_category: Filter by destination category
            application_stack: Filter by application stack
            complexity: Filter by complexity level
            tags: Filter by tags (preset must have all specified tags)
            
        Returns:
            List of matching presets
        """
        filtered = []
        
        for preset in self.presets.values():
            # Check source category
            if source_category and preset.metadata.source_category != source_category:
                continue
            
            # Check destination category
            if destination_category and preset.metadata.destination_category != destination_category:
                continue
            
            # Check application stack
            if application_stack and preset.metadata.application_stack != application_stack:
                continue
            
            # Check complexity
            if complexity and preset.metadata.complexity != complexity:
                continue
            
            # Check tags
            if tags:
                preset_tags = set(preset.metadata.tags)
                required_tags = set(tags)
                if not required_tags.issubset(preset_tags):
                    continue
            
            filtered.append(preset)
        
        return filtered
    
    def search_presets(self, query: str) -> List[PresetConfiguration]:
        """
        Search presets by name, description, or tags.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching presets
        """
        query_lower = query.lower()
        results = []
        
        for preset in self.presets.values():
            # Search in name
            if query_lower in preset.metadata.name.lower():
                results.append(preset)
                continue
            
            # Search in description
            if query_lower in preset.metadata.description.lower():
                results.append(preset)
                continue
            
            # Search in tags
            if any(query_lower in tag.lower() for tag in preset.metadata.tags):
                results.append(preset)
                continue
        
        return results
    
    def get_suggestions(
        self,
        source_type: Optional[str] = None,
        destination_type: Optional[str] = None,
        application: Optional[str] = None
    ) -> List[PresetConfiguration]:
        """
        Get preset suggestions based on partial criteria.
        
        Args:
            source_type: Source system type hint
            destination_type: Destination system type hint
            application: Application type hint
            
        Returns:
            List of suggested presets
        """
        suggestions = []
        
        # Try exact matches first
        for preset in self.presets.values():
            score = 0
            
            # Score based on matches
            if source_type and source_type.lower() in preset.metadata.source_category.value.lower():
                score += 3
            if destination_type and destination_type.lower() in preset.metadata.destination_category.value.lower():
                score += 3
            if application and application.lower() in preset.metadata.application_stack.value.lower():
                score += 3
            
            # Also check name and description
            if source_type and source_type.lower() in preset.metadata.name.lower():
                score += 2
            if destination_type and destination_type.lower() in preset.metadata.name.lower():
                score += 2
            if application and application.lower() in preset.metadata.name.lower():
                score += 2
            
            if score > 0:
                suggestions.append((preset, score))
        
        # Sort by score and return presets
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return [preset for preset, _ in suggestions[:10]]  # Top 10 suggestions
    
    def add_preset(self, preset: PresetConfiguration) -> None:
        """Add a new preset to the registry."""
        self.presets[preset.metadata.key] = preset
    
    def remove_preset(self, key: str) -> bool:
        """Remove a preset from the registry."""
        if key in self.presets:
            del self.presets[key]
            return True
        return False
    
    def export_preset(self, key: str, file_path: str) -> bool:
        """Export a preset to a file."""
        preset = self.presets.get(key)
        if not preset:
            return False
        
        try:
            preset_data = {
                "metadata": {
                    "key": preset.metadata.key,
                    "name": preset.metadata.name,
                    "description": preset.metadata.description,
                    "source_category": preset.metadata.source_category.value,
                    "destination_category": preset.metadata.destination_category.value,
                    "application_stack": preset.metadata.application_stack.value,
                    "complexity": preset.metadata.complexity,
                    "estimated_time": preset.metadata.estimated_time,
                    "prerequisites": preset.metadata.prerequisites,
                    "tags": preset.metadata.tags,
                    "version": preset.metadata.version,
                    "author": preset.metadata.author,
                    "created_date": preset.metadata.created_date,
                    "updated_date": preset.metadata.updated_date
                },
                "configuration": preset.configuration
            }
            
            if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                with open(file_path, 'w') as f:
                    yaml.dump(preset_data, f, default_flow_style=False, indent=2)
            else:
                with open(file_path, 'w') as f:
                    json.dump(preset_data, f, indent=2)
            
            return True
        except Exception:
            return False
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Get all available categories."""
        return {
            "source_categories": [cat.value for cat in SourceCategory],
            "destination_categories": [cat.value for cat in DestinationCategory],
            "application_stacks": [stack.value for stack in ApplicationStack]
        }
    
    def _get_builtin_preset_definitions(self) -> List[Dict[str, Any]]:
        """Get built-in preset definitions."""
        return [
            # Control Panel to VPS
            {
                "metadata": {
                    "key": "cpanel-to-linux",
                    "name": "cPanel to Linux VPS",
                    "description": "Migrate websites from cPanel to Debian/Ubuntu VPS",
                    "source_category": SourceCategory.CONTROL_PANEL.value,
                    "destination_category": DestinationCategory.VPS_SERVER.value,
                    "application_stack": ApplicationStack.GENERIC_WEBSITE.value,
                    "complexity": "medium",
                    "estimated_time": "45-90 minutes",
                    "prerequisites": ["SSH access to destination VPS", "cPanel API access"],
                    "tags": ["cpanel", "vps", "linux", "migration"],
                    "version": "1.0"
                },
                "configuration": {
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
                }
            },
            
            {
                "metadata": {
                    "key": "directadmin-to-linux",
                    "name": "DirectAdmin to Linux VPS",
                    "description": "Migrate websites from DirectAdmin to Debian/Ubuntu VPS",
                    "source_category": SourceCategory.CONTROL_PANEL.value,
                    "destination_category": DestinationCategory.VPS_SERVER.value,
                    "application_stack": ApplicationStack.GENERIC_WEBSITE.value,
                    "complexity": "medium",
                    "estimated_time": "45-90 minutes",
                    "prerequisites": ["SSH access to destination VPS", "DirectAdmin API access"],
                    "tags": ["directadmin", "vps", "linux", "migration"]
                },
                "configuration": {
                    "source": {
                        "type": "directadmin",
                        "authentication": {"type": "password"},
                        "control_panel": {
                            "type": "directadmin",
                            "port": 2222,
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
                        "verify_checksums": True
                    },
                    "options": {
                        "maintenance_mode": True,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True
                    }
                }
            },
            
            # WordPress Presets
            {
                "metadata": {
                    "key": "wordpress-mysql",
                    "name": "WordPress with MySQL",
                    "description": "Standard WordPress site with MySQL database migration",
                    "source_category": SourceCategory.CMS_PLATFORM.value,
                    "destination_category": DestinationCategory.VPS_SERVER.value,
                    "application_stack": ApplicationStack.WORDPRESS.value,
                    "complexity": "medium",
                    "estimated_time": "30-60 minutes",
                    "prerequisites": ["MySQL database access", "WordPress file access"],
                    "tags": ["wordpress", "mysql", "cms", "php"]
                },
                "configuration": {
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
                            "database_name": "wordpress"
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
                            "database_name": "wordpress"
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
                }
            },
            
            {
                "metadata": {
                    "key": "wordpress-to-s3",
                    "name": "WordPress to AWS S3",
                    "description": "Migrate WordPress site to AWS S3 static hosting",
                    "source_category": SourceCategory.CMS_PLATFORM.value,
                    "destination_category": DestinationCategory.CLOUD_PLATFORM.value,
                    "application_stack": ApplicationStack.WORDPRESS.value,
                    "complexity": "complex",
                    "estimated_time": "60-120 minutes",
                    "prerequisites": ["AWS credentials", "WordPress static generation plugin"],
                    "tags": ["wordpress", "aws", "s3", "static", "cloud"]
                },
                "configuration": {
                    "source": {
                        "type": "wordpress",
                        "authentication": {"type": "ssh_key"},
                        "paths": {"root_path": "/var/www/html"},
                        "database": {
                            "type": "mysql",
                            "host": "localhost",
                            "database_name": "wordpress"
                        }
                    },
                    "destination": {
                        "type": "aws_s3",
                        "host": "s3.amazonaws.com",
                        "authentication": {"type": "aws_iam"},
                        "paths": {"root_path": "/"},
                        "cloud_config": {
                            "provider": "aws",
                            "region": "us-east-1",
                            "bucket_name": "wordpress-static-site"
                        }
                    },
                    "transfer": {
                        "method": "aws_s3",
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
                }
            },
            
            # Static Site Presets
            {
                "metadata": {
                    "key": "static-to-s3",
                    "name": "Static Site to AWS S3",
                    "description": "Deploy static website to AWS S3 with CloudFront CDN",
                    "source_category": SourceCategory.STATIC_HOSTING.value,
                    "destination_category": DestinationCategory.CLOUD_PLATFORM.value,
                    "application_stack": ApplicationStack.STATIC_SITE.value,
                    "complexity": "simple",
                    "estimated_time": "15-30 minutes",
                    "prerequisites": ["AWS credentials", "Static site files"],
                    "tags": ["static", "aws", "s3", "cloudfront", "cdn"]
                },
                "configuration": {
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
                }
            },
            
            {
                "metadata": {
                    "key": "hugo-to-s3",
                    "name": "Hugo Site to AWS S3",
                    "description": "Deploy Hugo static site to AWS S3 with build process",
                    "source_category": SourceCategory.STATIC_HOSTING.value,
                    "destination_category": DestinationCategory.CLOUD_PLATFORM.value,
                    "application_stack": ApplicationStack.HUGO.value,
                    "complexity": "simple",
                    "estimated_time": "20-40 minutes",
                    "prerequisites": ["Hugo installed", "AWS credentials", "Hugo source code"],
                    "tags": ["hugo", "static", "aws", "s3", "build"]
                },
                "configuration": {
                    "source": {
                        "type": "static_site",
                        "authentication": {"type": "ssh_key"},
                        "paths": {"root_path": "/var/www/hugo-site"}
                    },
                    "destination": {
                        "type": "aws_s3",
                        "host": "s3.amazonaws.com",
                        "authentication": {"type": "aws_iam"},
                        "paths": {"root_path": "/"},
                        "cloud_config": {
                            "provider": "aws",
                            "region": "us-east-1",
                            "bucket_name": "hugo-static-site"
                        }
                    },
                    "transfer": {
                        "method": "aws_s3",
                        "parallel_transfers": 8,
                        "compression_enabled": False,
                        "verify_checksums": True
                    },
                    "options": {
                        "maintenance_mode": False,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True
                    }
                }
            },
            
            # Framework Presets
            {
                "metadata": {
                    "key": "django-postgres",
                    "name": "Django with PostgreSQL",
                    "description": "Django application with PostgreSQL database migration",
                    "source_category": SourceCategory.FRAMEWORK.value,
                    "destination_category": DestinationCategory.VPS_SERVER.value,
                    "application_stack": ApplicationStack.DJANGO.value,
                    "complexity": "medium",
                    "estimated_time": "45-90 minutes",
                    "prerequisites": ["PostgreSQL access", "Python environment", "Django app"],
                    "tags": ["django", "python", "postgresql", "framework"]
                },
                "configuration": {
                    "source": {
                        "type": "django",
                        "authentication": {"type": "ssh_key", "username": "django"},
                        "paths": {
                            "root_path": "/opt/django-app",
                            "config_path": "/opt/django-app/settings.py"
                        },
                        "database": {
                            "type": "postgresql",
                            "host": "localhost",
                            "port": 5432,
                            "database_name": "django_db"
                        }
                    },
                    "destination": {
                        "type": "django",
                        "authentication": {"type": "ssh_key", "username": "django"},
                        "paths": {"root_path": "/opt/django-app"},
                        "database": {
                            "type": "postgresql",
                            "host": "localhost",
                            "port": 5432,
                            "database_name": "django_db"
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
                }
            },
            
            {
                "metadata": {
                    "key": "nextjs-vercel",
                    "name": "Next.js to Vercel",
                    "description": "Deploy Next.js application to Vercel platform",
                    "source_category": SourceCategory.FRAMEWORK.value,
                    "destination_category": DestinationCategory.MANAGED_HOSTING.value,
                    "application_stack": ApplicationStack.NEXTJS.value,
                    "complexity": "simple",
                    "estimated_time": "10-20 minutes",
                    "prerequisites": ["Vercel account", "Next.js project", "Git repository"],
                    "tags": ["nextjs", "react", "vercel", "serverless", "deployment"]
                },
                "configuration": {
                    "source": {
                        "type": "nextjs",
                        "authentication": {"type": "ssh_key"},
                        "paths": {"root_path": "/var/www/nextjs-app"}
                    },
                    "destination": {
                        "type": "aws_s3",  # Vercel uses S3-like storage
                        "host": "vercel.com",
                        "authentication": {"type": "api_key"},
                        "paths": {"root_path": "/"}
                    },
                    "transfer": {
                        "method": "hybrid_sync",
                        "parallel_transfers": 8,
                        "compression_enabled": True,
                        "verify_checksums": True
                    },
                    "options": {
                        "maintenance_mode": False,
                        "backup_before": True,
                        "verify_after": True,
                        "rollback_on_failure": True
                    }
                }
            },
            
            # Container Presets
            {
                "metadata": {
                    "key": "docker-to-k8s",
                    "name": "Docker to Kubernetes",
                    "description": "Migrate Docker container to Kubernetes deployment",
                    "source_category": SourceCategory.CONTAINER.value,
                    "destination_category": DestinationCategory.CONTAINER_PLATFORM.value,
                    "application_stack": ApplicationStack.GENERIC_WEBSITE.value,
                    "complexity": "complex",
                    "estimated_time": "60-120 minutes",
                    "prerequisites": ["Kubernetes cluster access", "Docker image", "kubectl configured"],
                    "tags": ["docker", "kubernetes", "container", "orchestration"]
                },
                "configuration": {
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
                }
            }
        ]