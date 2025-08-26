"""
Base Analyzer Interface

Defines the common interface for all code analyzers.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

from migration_assistant.checkup.models import (
    Issue, CheckupConfig, CodebaseMetrics
)


class BaseAnalyzer(ABC):
    """Abstract base class for all code analyzers."""
    
    def __init__(self, config: CheckupConfig):
        """Initialize the analyzer with configuration."""
        self.config = config
        self.target_directory = config.target_directory
        self._metrics = CodebaseMetrics()
    
    @property
    def name(self) -> str:
        """Return the analyzer name."""
        return self.__class__.__name__
    
    @property
    def metrics(self) -> CodebaseMetrics:
        """Return current metrics."""
        return self._metrics
    
    @abstractmethod
    async def analyze(self) -> List[Issue]:
        """
        Perform analysis and return list of issues found.
        
        Returns:
            List of issues discovered during analysis
        """
        pass
    
    @abstractmethod
    def get_supported_file_types(self) -> List[str]:
        """
        Return list of file extensions this analyzer supports.
        
        Returns:
            List of file extensions (e.g., ['.py', '.pyx'])
        """
        pass
    
    def should_analyze_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be analyzed.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file should be analyzed, False otherwise
        """
        # Check file extension
        if file_path.suffix not in self.get_supported_file_types():
            return False
        
        # Check exclusion patterns
        for pattern in self.config.exclude_patterns:
            if file_path.match(pattern):
                return False
        
        # Check if file is in excluded directory
        for exclude_dir in self.config.exclude_dirs:
            if exclude_dir in file_path.parts:
                return False
        
        return True
    
    def get_python_files(self) -> List[Path]:
        """
        Get all Python files in the target directory.
        
        Returns:
            List of Python file paths
        """
        python_files = []
        
        for file_path in self.target_directory.rglob("*.py"):
            if self.should_analyze_file(file_path):
                python_files.append(file_path)
        
        return python_files
    
    def update_metrics(self, **kwargs) -> None:
        """
        Update analyzer metrics.
        
        Args:
            **kwargs: Metric values to update
        """
        for key, value in kwargs.items():
            if hasattr(self._metrics, key):
                setattr(self._metrics, key, value)
    
    async def pre_analyze(self) -> None:
        """
        Perform any setup before analysis.
        Override in subclasses if needed.
        """
        pass
    
    async def post_analyze(self, issues: List[Issue]) -> None:
        """
        Perform any cleanup after analysis.
        Override in subclasses if needed.
        
        Args:
            issues: Issues found during analysis
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
        
        # This will be overridden in concrete analyzers to return specific issue types
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
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Get summary of analysis results.
        
        Returns:
            Dictionary with analysis summary
        """
        return {
            "analyzer": self.name,
            "files_analyzed": len(self.get_python_files()),
            "metrics": self._metrics,
        }