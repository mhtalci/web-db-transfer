"""
Custom exceptions for the Migration Assistant.

This module defines custom exception classes used throughout
the application for better error handling and reporting.
"""

from typing import Any, Dict, List, Optional


class MigrationAssistantError(Exception):
    """Base exception class for Migration Assistant errors."""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


class ConfigurationError(MigrationAssistantError):
    """Raised when there's an error in configuration."""
    pass


class ValidationError(MigrationAssistantError):
    """Raised when validation fails."""
    
    def __init__(
        self,
        message: str,
        failed_checks: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.failed_checks = failed_checks or []


class ConnectionError(MigrationAssistantError):
    """Raised when connection to a system fails."""
    pass


class TransferError(MigrationAssistantError):
    """Raised when file transfer fails."""
    pass


class DatabaseError(MigrationAssistantError):
    """Raised when database operations fail."""
    pass


class BackupError(MigrationAssistantError):
    """Raised when backup operations fail."""
    pass


class RollbackError(MigrationAssistantError):
    """Raised when rollback operations fail."""
    pass


class AuthenticationError(MigrationAssistantError):
    """Raised when authentication fails."""
    pass


class PermissionError(MigrationAssistantError):
    """Raised when permission checks fail."""
    pass


class CompatibilityError(MigrationAssistantError):
    """Raised when systems are incompatible."""
    pass


class ResourceError(MigrationAssistantError):
    """Raised when resource constraints are violated."""
    pass


class UnsupportedDatabaseError(DatabaseError):
    """Raised when a database type is not supported."""
    pass


class IncompatibleDatabaseError(DatabaseError):
    """Raised when source and destination databases are incompatible."""
    pass


class SchemaError(DatabaseError):
    """Raised when there are schema-related errors."""
    pass


class DataIntegrityError(DatabaseError):
    """Raised when data integrity checks fail."""
    pass


class PlatformError(MigrationAssistantError):
    """Raised when platform-specific operations fail."""
    pass