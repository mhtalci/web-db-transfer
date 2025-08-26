"""
Factory for creating file transfer method instances.

This module provides the TransferMethodFactory class that creates
appropriate transfer method instances based on the transfer type
and configuration.
"""

from typing import Dict, Any, Type, Optional
import logging

from .base import TransferMethod

logger = logging.getLogger(__name__)


class TransferMethodFactory:
    """
    Factory class for creating file transfer method instances.
    
    This factory supports various transfer methods including SSH/SCP/SFTP,
    FTP/FTPS, cloud storage, rsync, and container-based transfers.
    """
    
    # Registry of available transfer methods
    _transfer_methods: Dict[str, Type[TransferMethod]] = {}
    
    @classmethod
    def register_method(cls, method_name: str, method_class: Type[TransferMethod]) -> None:
        """
        Register a transfer method class with the factory.
        
        Args:
            method_name: Name identifier for the transfer method
            method_class: Transfer method class to register
        """
        cls._transfer_methods[method_name.lower()] = method_class
        logger.debug(f"Registered transfer method: {method_name}")
    
    @classmethod
    def get_available_methods(cls) -> list[str]:
        """
        Get list of available transfer method names.
        
        Returns:
            List of registered transfer method names
        """
        return list(cls._transfer_methods.keys())
    
    @classmethod
    def create_transfer_method(
        cls, 
        method_type: str, 
        config: Dict[str, Any]
    ) -> TransferMethod:
        """
        Create a transfer method instance based on type and configuration.
        
        Args:
            method_type: Type of transfer method (e.g., 'ssh', 'ftp', 's3')
            config: Configuration dictionary for the transfer method
            
        Returns:
            Configured transfer method instance
            
        Raises:
            ValueError: If method_type is not supported
            TypeError: If config is invalid for the method type
        """
        method_type_lower = method_type.lower()
        
        if method_type_lower not in cls._transfer_methods:
            available = ", ".join(cls.get_available_methods())
            raise ValueError(
                f"Unsupported transfer method: {method_type}. "
                f"Available methods: {available}"
            )
        
        method_class = cls._transfer_methods[method_type_lower]
        
        try:
            instance = method_class(config)
            logger.info(f"Created transfer method instance: {method_type}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create transfer method {method_type}: {e}")
            raise TypeError(
                f"Failed to create transfer method {method_type} with provided config: {e}"
            )
    
    @classmethod
    def create_from_url(cls, url: str, config: Optional[Dict[str, Any]] = None) -> TransferMethod:
        """
        Create a transfer method instance from a URL.
        
        Args:
            url: URL indicating the transfer method and destination
            config: Additional configuration options
            
        Returns:
            Configured transfer method instance
            
        Raises:
            ValueError: If URL scheme is not supported
        """
        if config is None:
            config = {}
        
        # Parse URL to determine method type
        if url.startswith('ssh://') or url.startswith('sftp://') or url.startswith('scp://'):
            method_type = 'ssh'
        elif url.startswith('ftp://') or url.startswith('ftps://'):
            method_type = 'ftp'
        elif url.startswith('s3://'):
            method_type = 's3'
        elif url.startswith('gs://'):
            method_type = 'gcs'
        elif url.startswith('azure://') or url.startswith('https://') and 'blob.core.windows.net' in url:
            method_type = 'azure'
        elif url.startswith('docker://'):
            method_type = 'docker'
        elif url.startswith('k8s://') or url.startswith('kubernetes://'):
            method_type = 'kubernetes'
        else:
            raise ValueError(f"Unsupported URL scheme: {url}")
        
        # Add URL to config
        config['url'] = url
        
        return cls.create_transfer_method(method_type, config)
    
    @classmethod
    def get_method_info(cls, method_type: str) -> Dict[str, Any]:
        """
        Get information about a specific transfer method.
        
        Args:
            method_type: Type of transfer method
            
        Returns:
            Dictionary with method information
            
        Raises:
            ValueError: If method_type is not supported
        """
        method_type_lower = method_type.lower()
        
        if method_type_lower not in cls._transfer_methods:
            raise ValueError(f"Unsupported transfer method: {method_type}")
        
        method_class = cls._transfer_methods[method_type_lower]
        
        return {
            'name': method_type,
            'class': method_class.__name__,
            'module': method_class.__module__,
            'description': method_class.__doc__ or "No description available",
            'supported_schemes': getattr(method_class, 'SUPPORTED_SCHEMES', []),
            'required_config': getattr(method_class, 'REQUIRED_CONFIG', []),
            'optional_config': getattr(method_class, 'OPTIONAL_CONFIG', [])
        }


# Auto-registration function for transfer methods
def register_transfer_method(method_name: str):
    """
    Decorator to automatically register transfer methods with the factory.
    
    Args:
        method_name: Name identifier for the transfer method
    """
    def decorator(cls: Type[TransferMethod]) -> Type[TransferMethod]:
        TransferMethodFactory.register_method(method_name, cls)
        return cls
    return decorator