"""
Core module for the Migration Assistant.

This module contains the core functionality and base classes
used throughout the application.
"""

from migration_assistant.core.exceptions import (
    MigrationAssistantError,
    ConfigurationError,
    ValidationError,
    ConnectionError,
    TransferError,
    DatabaseError,
    BackupError,
    RollbackError,
    AuthenticationError,
    PermissionError,
    CompatibilityError,
    ResourceError,
)

__all__ = [
    "MigrationAssistantError",
    "ConfigurationError",
    "ValidationError",
    "ConnectionError",
    "TransferError",
    "DatabaseError",
    "BackupError",
    "RollbackError",
    "AuthenticationError",
    "PermissionError",
    "CompatibilityError",
    "ResourceError",
]