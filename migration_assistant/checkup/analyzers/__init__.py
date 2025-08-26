"""
Code Analysis Modules

Contains analyzers for code quality, duplicates, imports, and structure.
"""

from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.analyzers.quality import CodeQualityAnalyzer
from migration_assistant.checkup.analyzers.duplicates import DuplicateCodeDetector
from migration_assistant.checkup.analyzers.imports import ImportAnalyzer
from migration_assistant.checkup.analyzers.structure import StructureAnalyzer

__all__ = [
    "BaseAnalyzer",
    "CodeQualityAnalyzer",
    "DuplicateCodeDetector", 
    "ImportAnalyzer",
    "StructureAnalyzer",
]