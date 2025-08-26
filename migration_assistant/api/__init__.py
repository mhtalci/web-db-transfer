"""
API module for the Migration Assistant.

This module provides REST API functionality using FastAPI
for programmatic access to migration capabilities.
"""

from migration_assistant.api.main import app, start_server

__all__ = ["app", "start_server"]