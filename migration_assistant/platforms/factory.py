"""
Platform adapter factory for creating appropriate platform adapters.
"""

from typing import Dict, Type, Optional, List
from pathlib import Path

from .base import PlatformAdapter
from .cms import CMSAdapter, WordPressAdapter, DrupalAdapter, JoomlaAdapter
from .framework import FrameworkAdapter, DjangoAdapter, LaravelAdapter, RailsAdapter, SpringBootAdapter, NextJSAdapter
from .container import ContainerAdapter, DockerAdapter, KubernetesAdapter
from .cloud import CloudAdapter, AWSAdapter, AzureAdapter, GCPAdapter, NetlifyAdapter, VercelAdapter
from .control_panel import ControlPanelAdapter, CPanelAdapter, DirectAdminAdapter, PleskAdapter
from ..models.config import SystemConfig
from ..core.exceptions import PlatformError


class PlatformAdapterFactory:
    """
    Factory class for creating platform-specific adapters.
    
    Automatically detects platform types and creates appropriate adapters
    for CMS systems, web frameworks, containers, cloud platforms, and control panels.
    """
    
    # Registry of available adapters
    _adapters: Dict[str, Type[PlatformAdapter]] = {
        # CMS Adapters
        "wordpress": WordPressAdapter,
        "drupal": DrupalAdapter,
        "joomla": JoomlaAdapter,
        
        # Framework Adapters
        "django": DjangoAdapter,
        "laravel": LaravelAdapter,
        "rails": RailsAdapter,
        "springboot": SpringBootAdapter,
        "nextjs": NextJSAdapter,
        
        # Container Adapters
        "docker": DockerAdapter,
        "kubernetes": KubernetesAdapter,
        
        # Cloud Adapters
        "aws": AWSAdapter,
        "azure": AzureAdapter,
        "gcp": GCPAdapter,
        "netlify": NetlifyAdapter,
        "vercel": VercelAdapter,
        
        # Control Panel Adapters
        "cpanel": CPanelAdapter,
        "directadmin": DirectAdminAdapter,
        "plesk": PleskAdapter,
    }
    
    @classmethod
    def register_adapter(cls, platform_type: str, adapter_class: Type[PlatformAdapter]) -> None:
        """
        Register a new platform adapter.
        
        Args:
            platform_type: Platform type identifier
            adapter_class: Adapter class to register
        """
        cls._adapters[platform_type] = adapter_class
    
    @classmethod
    def get_available_platforms(cls) -> List[str]:
        """
        Get list of available platform types.
        
        Returns:
            List of supported platform type identifiers
        """
        return list(cls._adapters.keys())
    
    @classmethod
    def create_adapter(cls, platform_type: str, config: SystemConfig) -> PlatformAdapter:
        """
        Create a platform adapter for the specified type.
        
        Args:
            platform_type: Platform type identifier
            config: System configuration
            
        Returns:
            Platform adapter instance
            
        Raises:
            PlatformError: If platform type is not supported
        """
        if platform_type not in cls._adapters:
            raise PlatformError(f"Unsupported platform type: {platform_type}")
        
        adapter_class = cls._adapters[platform_type]
        return adapter_class(config)
    
    @classmethod
    async def detect_platform(cls, path: Path, config: SystemConfig) -> Optional[PlatformAdapter]:
        """
        Automatically detect platform type at the given path.
        
        Args:
            path: Path to analyze
            config: System configuration
            
        Returns:
            Platform adapter if detected, None otherwise
        """
        # Define detection order (more specific platforms first)
        detection_order = [
            # CMS platforms
            "wordpress",
            "drupal", 
            "joomla",
            
            # Web frameworks
            "django",
            "laravel",
            "rails",
            "springboot",
            "nextjs",
            
            # Container platforms
            "docker",
            "kubernetes",
            
            # Cloud platforms
            "aws",
            "azure",
            "gcp",
            "netlify",
            "vercel",
            
            # Control panels
            "cpanel",
            "directadmin",
            "plesk",
        ]
        
        for platform_type in detection_order:
            try:
                adapter = cls.create_adapter(platform_type, config)
                if await adapter.detect_platform(path):
                    return adapter
            except Exception as e:
                # Log detection failure but continue with other platforms
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Failed to detect {platform_type} at {path}: {e}")
                continue
        
        return None
    
    @classmethod
    async def analyze_directory(cls, path: Path, config: SystemConfig) -> List[PlatformAdapter]:
        """
        Analyze directory and return all detected platforms.
        
        Args:
            path: Path to analyze
            config: System configuration
            
        Returns:
            List of detected platform adapters
        """
        detected_platforms = []
        
        for platform_type in cls._adapters.keys():
            try:
                adapter = cls.create_adapter(platform_type, config)
                if await adapter.detect_platform(path):
                    detected_platforms.append(adapter)
            except Exception:
                # Continue with other platforms if one fails
                continue
        
        return detected_platforms
    
    @classmethod
    def get_adapter_info(cls, platform_type: str) -> Dict[str, any]:
        """
        Get information about a platform adapter.
        
        Args:
            platform_type: Platform type identifier
            
        Returns:
            Dictionary with adapter information
            
        Raises:
            PlatformError: If platform type is not supported
        """
        if platform_type not in cls._adapters:
            raise PlatformError(f"Unsupported platform type: {platform_type}")
        
        adapter_class = cls._adapters[platform_type]
        
        # Create a temporary instance to get information
        from ..models.config import SystemConfig
        temp_config = SystemConfig(type=platform_type, host="localhost")
        temp_adapter = adapter_class(temp_config)
        
        return {
            "platform_type": temp_adapter.platform_type,
            "supported_versions": temp_adapter.supported_versions,
            "class_name": adapter_class.__name__,
            "module": adapter_class.__module__
        }
    
    @classmethod
    def get_all_adapter_info(cls) -> Dict[str, Dict[str, any]]:
        """
        Get information about all registered adapters.
        
        Returns:
            Dictionary mapping platform types to adapter information
        """
        info = {}
        for platform_type in cls._adapters.keys():
            try:
                info[platform_type] = cls.get_adapter_info(platform_type)
            except Exception:
                # Skip adapters that fail to provide info
                continue
        
        return info
    
    @classmethod
    def validate_platform_compatibility(cls, source_platform: str, destination_platform: str) -> bool:
        """
        Check if migration between two platform types is supported.
        
        Args:
            source_platform: Source platform type
            destination_platform: Destination platform type
            
        Returns:
            True if migration is supported, False otherwise
        """
        # Basic compatibility rules
        compatibility_matrix = {
            # CMS to CMS migrations
            "wordpress": ["wordpress", "drupal", "joomla"],
            "drupal": ["drupal", "wordpress"],
            "joomla": ["joomla", "wordpress"],
            
            # Framework to framework migrations
            "django": ["django"],
            "laravel": ["laravel"],
            "rails": ["rails"],
            "springboot": ["springboot"],
            "nextjs": ["nextjs"],
            
            # Container migrations
            "docker": ["docker", "kubernetes"],
            "kubernetes": ["kubernetes", "docker"],
            
            # Cloud migrations (most cloud platforms can migrate to each other)
            "aws": ["aws", "azure", "gcp"],
            "azure": ["azure", "aws", "gcp"],
            "gcp": ["gcp", "aws", "azure"],
            "netlify": ["netlify", "vercel"],
            "vercel": ["vercel", "netlify"],
            
            # Control panel migrations (can migrate to any platform)
            "cpanel": ["cpanel", "directadmin", "plesk", "aws", "azure", "gcp"],
            "directadmin": ["directadmin", "cpanel", "plesk", "aws", "azure", "gcp"],
            "plesk": ["plesk", "cpanel", "directadmin", "aws", "azure", "gcp"],
        }
        
        if source_platform not in compatibility_matrix:
            return False
        
        return destination_platform in compatibility_matrix[source_platform]
    
    @classmethod
    def get_migration_complexity(cls, source_platform: str, destination_platform: str) -> str:
        """
        Get migration complexity level between two platforms.
        
        Args:
            source_platform: Source platform type
            destination_platform: Destination platform type
            
        Returns:
            Complexity level: "simple", "moderate", "complex", or "unsupported"
        """
        if not cls.validate_platform_compatibility(source_platform, destination_platform):
            return "unsupported"
        
        # Same platform migrations are simple
        if source_platform == destination_platform:
            return "simple"
        
        # Define complexity rules
        complexity_rules = {
            # CMS migrations
            ("wordpress", "drupal"): "complex",
            ("wordpress", "joomla"): "complex",
            ("drupal", "wordpress"): "complex",
            ("joomla", "wordpress"): "complex",
            
            # Framework migrations (same platform only for now)
            ("django", "django"): "simple",
            ("laravel", "laravel"): "simple",
            ("rails", "rails"): "simple",
            ("springboot", "springboot"): "simple",
            ("nextjs", "nextjs"): "simple",
        }
        
        return complexity_rules.get((source_platform, destination_platform), "moderate")
    
    @classmethod
    def get_recommended_migration_steps(cls, source_platform: str, destination_platform: str) -> List[str]:
        """
        Get recommended migration steps for platform migration.
        
        Args:
            source_platform: Source platform type
            destination_platform: Destination platform type
            
        Returns:
            List of recommended migration steps
        """
        if not cls.validate_platform_compatibility(source_platform, destination_platform):
            return ["Migration not supported between these platforms"]
        
        # Common steps for all migrations
        common_steps = [
            "analyze_source_platform",
            "validate_compatibility",
            "create_backup",
            "prepare_destination"
        ]
        
        # Platform-specific steps
        if source_platform == destination_platform:
            # Same platform migration
            platform_steps = [
                "copy_files",
                "migrate_database",
                "update_configuration",
                "verify_migration"
            ]
        else:
            # Cross-platform migration
            platform_steps = [
                "export_content",
                "transform_data",
                "import_content",
                "configure_destination",
                "verify_migration"
            ]
        
        return common_steps + platform_steps