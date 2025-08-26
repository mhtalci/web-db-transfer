"""
Validation and Testing Modules

Contains validators for test coverage, configuration files, and documentation,
as well as correction recommendation engine.
"""

from migration_assistant.checkup.validators.base import BaseValidator
from migration_assistant.checkup.validators.coverage import CoverageValidator
from migration_assistant.checkup.validators.config import ConfigValidator
from migration_assistant.checkup.validators.docs import DocumentationValidator
from migration_assistant.checkup.validators.corrections import CorrectionEngine

__all__ = [
    "BaseValidator",
    "CoverageValidator",
    "ConfigValidator",
    "DocumentationValidator",
    "CorrectionEngine",
]