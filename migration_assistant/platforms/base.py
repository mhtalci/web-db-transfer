"""
Base platform adapter interface and common functionality.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging
from pydantic import BaseModel

from ..models.config import SystemConfig
from ..core.exceptions import PlatformError, ValidationError


class PlatformInfo(BaseModel):
    """Information about a detected platform."""
    platform_type: str
    version: Optional[str] = None
    framework: Optional[str] = None
    database_type: Optional[str] = None
    dependencies: List[str] = []
    config_files: List[str] = []
    environment_variables: Dict[str, str] = {}


class DependencyInfo(BaseModel):
    """Information about platform dependencies."""
    name: str
    version: Optional[str] = None
    required: bool = True
    installed: bool = False
    install_command: Optional[str] = None


class EnvironmentConfig(BaseModel):
    """Environment configuration for a platform."""
    variables: Dict[str, str] = {}
    files: List[str] = []
    secrets: List[str] = []


class PlatformAdapter(ABC):
    """
    Base class for all platform-specific adapters.
    
    Provides common interface for detecting, analyzing, and migrating
    different types of platforms (CMS, frameworks, containers, etc.).
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._platform_info: Optional[PlatformInfo] = None
    
    @property
    @abstractmethod
    def platform_type(self) -> str:
        """Return the platform type identifier."""
        pass
    
    @property
    @abstractmethod
    def supported_versions(self) -> List[str]:
        """Return list of supported platform versions."""
        pass
    
    @abstractmethod
    async def detect_platform(self, path: Path) -> bool:
        """
        Detect if this platform exists at the given path.
        
        Args:
            path: Path to check for platform presence
            
        Returns:
            True if platform is detected, False otherwise
        """
        pass
    
    @abstractmethod
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """
        Analyze the platform and return detailed information.
        
        Args:
            path: Path to the platform installation
            
        Returns:
            PlatformInfo with detected platform details
        """
        pass
    
    @abstractmethod
    async def get_dependencies(self) -> List[DependencyInfo]:
        """
        Get list of platform dependencies.
        
        Returns:
            List of dependency information
        """
        pass
    
    @abstractmethod
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """
        Extract environment configuration from the platform.
        
        Args:
            path: Path to the platform installation
            
        Returns:
            Environment configuration
        """
        pass
    
    @abstractmethod
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """
        Prepare platform-specific migration steps.
        
        Args:
            source_path: Source platform path
            destination_path: Destination path
            
        Returns:
            Migration preparation information
        """
        pass
    
    @abstractmethod
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """
        Perform platform-specific post-migration setup.
        
        Args:
            destination_path: Destination path
            migration_info: Information from prepare_migration
            
        Returns:
            True if setup successful, False otherwise
        """
        pass
    
    async def validate_compatibility(self, source_info: PlatformInfo, destination_config: SystemConfig) -> Tuple[bool, List[str]]:
        """
        Validate compatibility between source and destination.
        
        Args:
            source_info: Source platform information
            destination_config: Destination system configuration
            
        Returns:
            Tuple of (is_compatible, list_of_issues)
        """
        issues = []
        
        # Check version compatibility
        if source_info.version and source_info.version not in self.supported_versions:
            issues.append(f"Version {source_info.version} is not supported")
        
        # Check database compatibility
        if source_info.database_type and destination_config.database:
            if source_info.database_type != destination_config.database.db_type:
                issues.append(f"Database type mismatch: {source_info.database_type} -> {destination_config.database.db_type}")
        
        return len(issues) == 0, issues
    
    async def check_dependencies(self, dependencies: List[DependencyInfo]) -> Tuple[bool, List[str]]:
        """
        Check if all required dependencies are available.
        
        Args:
            dependencies: List of dependencies to check
            
        Returns:
            Tuple of (all_satisfied, list_of_missing)
        """
        missing = []
        
        for dep in dependencies:
            if dep.required and not dep.installed:
                missing.append(f"{dep.name} (install: {dep.install_command or 'manual'})")
        
        return len(missing) == 0, missing
    
    def _read_config_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Read and parse a configuration file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            Parsed configuration data
        """
        try:
            if not file_path.exists():
                return {}
            
            content = file_path.read_text(encoding='utf-8')
            
            # Handle different file formats
            if file_path.suffix.lower() in ['.json']:
                import json
                return json.loads(content)
            elif file_path.suffix.lower() in ['.yaml', '.yml']:
                import yaml
                return yaml.safe_load(content)
            elif file_path.suffix.lower() in ['.toml']:
                import tomli
                return tomli.loads(content)
            elif file_path.suffix.lower() in ['.ini', '.cfg']:
                import configparser
                config = configparser.ConfigParser()
                config.read_string(content)
                return {section: dict(config[section]) for section in config.sections()}
            else:
                # Try to parse as key=value pairs
                config = {}
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
                return config
                
        except Exception as e:
            self.logger.warning(f"Failed to read config file {file_path}: {e}")
            return {}
    
    def _extract_environment_variables(self, content: str) -> Dict[str, str]:
        """
        Extract environment variables from file content.
        
        Args:
            content: File content to parse
            
        Returns:
            Dictionary of environment variables
        """
        env_vars = {}
        
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env_vars[key] = value
        
        return env_vars
    
    async def get_platform_info(self, path: Path) -> PlatformInfo:
        """
        Get cached platform information or analyze if not cached.
        
        Args:
            path: Path to analyze
            
        Returns:
            Platform information
        """
        if self._platform_info is None:
            self._platform_info = await self.analyze_platform(path)
        return self._platform_info