"""
Data models for the Migration Assistant.

This module contains all Pydantic models used throughout the application
for configuration, session management, and data validation.
"""

from migration_assistant.models.config import (
    MigrationConfig,
    SystemConfig,
    AuthConfig,
    PathConfig,
    DatabaseConfig,
    CloudConfig,
    TransferConfig,
    MigrationOptions,
)
from migration_assistant.models.session import (
    MigrationSession,
    MigrationStatus,
    MigrationStep,
    StepStatus,
    LogEntry,
    ErrorInfo,
    BackupInfo,
    ReportInfo,
)

__all__ = [
    # Configuration models
    "MigrationConfig",
    "SystemConfig",
    "AuthConfig", 
    "PathConfig",
    "DatabaseConfig",
    "CloudConfig",
    "TransferConfig",
    "MigrationOptions",
    # Session models
    "MigrationSession",
    "MigrationStatus",
    "MigrationStep",
    "StepStatus",
    "LogEntry",
    "ErrorInfo",
    "BackupInfo",
    "ReportInfo",
]