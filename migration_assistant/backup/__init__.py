"""
Backup and recovery system for the Migration Assistant.

This module provides comprehensive backup and recovery capabilities
for files, databases, and configurations during migration operations.
"""

from migration_assistant.backup.manager import BackupManager
from migration_assistant.backup.rollback import RollbackManager
from migration_assistant.backup.storage import BackupStorage
from migration_assistant.backup.validator import RecoveryValidator
from migration_assistant.backup.strategies import (
    BackupStrategy,
    FileBackupStrategy,
    DatabaseBackupStrategy,
    ConfigBackupStrategy,
    CloudBackupStrategy,
)

__all__ = [
    "BackupManager",
    "RollbackManager", 
    "BackupStorage",
    "RecoveryValidator",
    "BackupStrategy",
    "FileBackupStrategy",
    "DatabaseBackupStrategy",
    "ConfigBackupStrategy",
    "CloudBackupStrategy",
]