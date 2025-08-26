"""
CMS-specific exceptions for better error handling and debugging.
"""

from typing import Optional, Dict, Any, List
from .exceptions import PlatformError


class CMSError(PlatformError):
    """Base exception for CMS-related errors."""
    pass


class CMSDetectionError(CMSError):
    """Raised when CMS platform detection fails."""
    
    def __init__(self, path: str, attempted_platforms: List[str], message: str = None):
        self.path = path
        self.attempted_platforms = attempted_platforms
        default_message = f"Failed to detect CMS platform at {path}. Attempted: {', '.join(attempted_platforms)}"
        super().__init__(message or default_message)


class CMSVersionError(CMSError):
    """Raised when CMS version is unsupported or cannot be determined."""
    
    def __init__(self, platform: str, version: Optional[str], supported_versions: List[str]):
        self.platform = platform
        self.version = version
        self.supported_versions = supported_versions
        
        if version:
            message = f"{platform} version {version} is not supported. Supported versions: {', '.join(supported_versions)}"
        else:
            message = f"Could not determine {platform} version. Supported versions: {', '.join(supported_versions)}"
        
        super().__init__(message)


class CMSConfigurationError(CMSError):
    """Raised when CMS configuration is invalid or cannot be parsed."""
    
    def __init__(self, platform: str, config_file: str, details: str = None):
        self.platform = platform
        self.config_file = config_file
        self.details = details
        
        message = f"Invalid {platform} configuration in {config_file}"
        if details:
            message += f": {details}"
        
        super().__init__(message)


class CMSDatabaseError(CMSError):
    """Raised when database configuration or connection fails."""
    
    def __init__(self, platform: str, database_type: str, error_details: str):
        self.platform = platform
        self.database_type = database_type
        self.error_details = error_details
        
        message = f"{platform} database error ({database_type}): {error_details}"
        super().__init__(message)


class CMSMigrationError(CMSError):
    """Raised when CMS migration fails."""
    
    def __init__(self, source_platform: str, destination_platform: str, step: str, details: str):
        self.source_platform = source_platform
        self.destination_platform = destination_platform
        self.step = step
        self.details = details
        
        message = f"Migration failed from {source_platform} to {destination_platform} at step '{step}': {details}"
        super().__init__(message)


class CMSCompatibilityError(CMSError):
    """Raised when platforms are incompatible for migration."""
    
    def __init__(self, source_platform: str, destination_platform: str, reasons: List[str]):
        self.source_platform = source_platform
        self.destination_platform = destination_platform
        self.reasons = reasons
        
        message = f"Incompatible migration from {source_platform} to {destination_platform}. Reasons: {'; '.join(reasons)}"
        super().__init__(message)


class CMSPluginError(CMSError):
    """Raised when plugin/extension/module handling fails."""
    
    def __init__(self, platform: str, plugin_name: str, operation: str, details: str):
        self.platform = platform
        self.plugin_name = plugin_name
        self.operation = operation
        self.details = details
        
        message = f"{platform} plugin '{plugin_name}' {operation} failed: {details}"
        super().__init__(message)


class CMSThemeError(CMSError):
    """Raised when theme/template handling fails."""
    
    def __init__(self, platform: str, theme_name: str, operation: str, details: str):
        self.platform = platform
        self.theme_name = theme_name
        self.operation = operation
        self.details = details
        
        message = f"{platform} theme '{theme_name}' {operation} failed: {details}"
        super().__init__(message)


class CMSPermissionError(CMSError):
    """Raised when file permission operations fail."""
    
    def __init__(self, platform: str, path: str, operation: str, details: str):
        self.platform = platform
        self.path = path
        self.operation = operation
        self.details = details
        
        message = f"{platform} permission {operation} failed for {path}: {details}"
        super().__init__(message)


class CMSBackupError(CMSError):
    """Raised when backup operations fail."""
    
    def __init__(self, platform: str, backup_type: str, details: str):
        self.platform = platform
        self.backup_type = backup_type
        self.details = details
        
        message = f"{platform} {backup_type} backup failed: {details}"
        super().__init__(message)