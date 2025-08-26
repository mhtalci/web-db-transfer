"""
Web & Database Migration Assistant

A comprehensive Python-based tool for migrating web applications and databases
between different systems, platforms, and environments.
"""

__version__ = "0.1.0"
__author__ = "Migration Assistant Team"
__email__ = "team@migration-assistant.com"

from migration_assistant.models.config import MigrationConfig, SystemConfig
from migration_assistant.models.session import MigrationSession, MigrationStatus

__all__ = [
    "MigrationConfig",
    "SystemConfig", 
    "MigrationSession",
    "MigrationStatus",
]