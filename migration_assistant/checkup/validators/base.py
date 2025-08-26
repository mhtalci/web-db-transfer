"""
Base Validator Interface

Defines the common interface for all validators.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

from migration_assistant.checkup.models import (
    Issue, CheckupConfig, CodebaseMetrics
)


class ValidationResult:
    """Result of a validation operation."""
    
    def __init__(self, valid: bool = True, message: str = "", 
                 issues: Optional[List[Issue]] = None):
        self.valid = valid
        self.message = message
        self.issues = issues or []
        self.files_validated = 0
        self.validation_details: Dict[str, Any] = {}


class BaseValidator(ABC):
    """Abstract base class for all validators."""
    
    def __init__(self, config: CheckupConfig):
        """Initialize the validator with configuration."""
        self.config = config
        self.target_directory = config.target_directory
        self._metrics = CodebaseMetrics()
    
    @property
    def name(self) -> str:
        """Return the validator name."""
        return self.__class__.__name__
    
    @property
    def metrics(self) -> CodebaseMetrics:
        """Return current metrics."""
        return self._metrics
    
    @abstractmethod
    async def validate(self) -> ValidationResult:
        """
        Perform validation and return results.
        
        Returns:
            ValidationResult with validation details and any issues found
        """
        pass
    
    @abstractmethod
    def get_validation_scope(self) -> List[str]:
        """
        Return list of what this validator checks.
        
        Returns:
            List of validation scope items (e.g., ['test_coverage', 'test_quality'])
        """
        pass
    
    def should_validate_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be validated.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file should be validated, False otherwise
        """
        # Check exclusion patterns
        for pattern in self.config.exclude_patterns:
            if file_path.match(pattern):
                return False
        
        # Check if file is in excluded directory
        for exclude_dir in self.config.exclude_dirs:
            if exclude_dir in file_path.parts:
                return False
        
        return True
    
    def get_target_files(self, extensions: List[str]) -> List[Path]:
        """
        Get all files with specified extensions in the target directory.
        
        Args:
            extensions: List of file extensions to include (e.g., ['.py', '.toml'])
            
        Returns:
            List of file paths
        """
        target_files = []
        
        for ext in extensions:
            pattern = f"*{ext}"
            for file_path in self.target_directory.rglob(pattern):
                if self.should_validate_file(file_path):
                    target_files.append(file_path)
        
        return target_files
    
    def update_metrics(self, **kwargs) -> None:
        """
        Update validator metrics.
        
        Args:
            **kwargs: Metric values to update
        """
        for key, value in kwargs.items():
            if hasattr(self._metrics, key):
                setattr(self._metrics, key, value)
    
    async def pre_validate(self) -> bool:
        """
        Perform any setup before validation.
        Override in subclasses if needed.
        
        Returns:
            True if setup was successful, False otherwise
        """
        return True
    
    async def post_validate(self, result: ValidationResult) -> None:
        """
        Perform any cleanup after validation.
        Override in subclasses if needed.
        
        Args:
            result: Validation result
        """
        pass
    
    def create_issue(
        self,
        file_path: Path,
        issue_type: Any,  # IssueType enum
        severity: Any,    # IssueSeverity enum
        message: str,
        description: str,
        line_number: Optional[int] = None,
        suggestion: Optional[str] = None,
        confidence: float = 1.0,
        **kwargs
    ) -> Issue:
        """
        Create an issue instance with common fields.
        
        Args:
            file_path: Path to the file with the issue
            issue_type: Type of issue (from IssueType enum)
            severity: Severity level (from IssueSeverity enum)
            message: Short message describing the issue
            description: Detailed description of the issue
            line_number: Line number where issue occurs
            suggestion: Suggested fix for the issue
            confidence: Confidence level (0.0 to 1.0)
            **kwargs: Additional issue-specific fields
            
        Returns:
            Issue instance
        """
        from migration_assistant.checkup.models import Issue
        
        # This will be overridden in concrete validators to return specific issue types
        return Issue(
            file_path=file_path,
            line_number=line_number,
            severity=severity,
            issue_type=issue_type,
            message=message,
            description=description,
            suggestion=suggestion,
            confidence=confidence
        )
    
    def get_validation_summary(self, result: ValidationResult) -> Dict[str, Any]:
        """
        Get summary of validation results.
        
        Args:
            result: Validation result
            
        Returns:
            Dictionary with validation summary
        """
        return {
            "validator": self.name,
            "valid": result.valid,
            "files_validated": result.files_validated,
            "issues_found": len(result.issues),
            "validation_scope": self.get_validation_scope(),
            "metrics": self._metrics,
            "message": result.message,
        }