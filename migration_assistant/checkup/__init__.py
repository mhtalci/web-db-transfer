"""
Codebase Checkup and Cleanup Module

Provides comprehensive analysis and automated maintenance capabilities
for the migration assistant codebase.
"""

from migration_assistant.checkup.models import (
    AnalysisResults,
    CleanupResults,
    CheckupResults,
    CheckupConfig,
    CodebaseMetrics,
)
from migration_assistant.checkup.orchestrator import CodebaseOrchestrator

__all__ = [
    "AnalysisResults",
    "CleanupResults", 
    "CheckupResults",
    "CheckupConfig",
    "CodebaseMetrics",
    "CodebaseOrchestrator",
]