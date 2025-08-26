"""
Base Cleaner Interface

Defines the common interface for all code cleaners.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, Issue
)


class CleanupResult:
    """Base class for cleanup operation results."""
    
    def __init__(self, success: bool = True, message: str = "", 
                 files_modified: Optional[List[Path]] = None):
        self.success = success
        self.message = message
        self.files_modified = files_modified or []
        self.changes_made = 0


class BaseCleaner(ABC):
    """Abstract base class for all code cleaners."""
    
    def __init__(self, config: CheckupConfig):
        """Initialize the cleaner with configuration."""
        self.config = config
        self.target_directory = config.target_directory
        self._backup_created = False
        self._backup_path: Optional[Path] = None
    
    @property
    def name(self) -> str:
        """Return the cleaner name."""
        return self.__class__.__name__
    
    @abstractmethod
    async def clean(self, analysis_results: AnalysisResults) -> CleanupResult:
        """
        Perform cleanup operations based on analysis results.
        
        Args:
            analysis_results: Results from code analysis
            
        Returns:
            CleanupResult with details of operations performed
        """
        pass
    
    @abstractmethod
    def can_clean_issue(self, issue: Issue) -> bool:
        """
        Determine if this cleaner can fix a specific issue.
        
        Args:
            issue: Issue to check
            
        Returns:
            True if this cleaner can fix the issue, False otherwise
        """
        pass
    
    def should_clean_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be cleaned.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file should be cleaned, False otherwise
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
    
    async def create_backup(self, files_to_modify: List[Path]) -> bool:
        """
        Create backup of files before modification.
        
        Args:
            files_to_modify: List of files that will be modified
            
        Returns:
            True if backup was created successfully, False otherwise
        """
        if not self.config.create_backup or self.config.dry_run:
            return True
        
        try:
            import shutil
            from datetime import datetime
            
            # Create backup directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.config.backup_dir / f"backup_{timestamp}_{self.name}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files to backup
            for file_path in files_to_modify:
                if file_path.exists():
                    relative_path = file_path.relative_to(self.target_directory)
                    backup_file = backup_dir / relative_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, backup_file)
            
            self._backup_created = True
            self._backup_path = backup_dir
            return True
            
        except Exception as e:
            print(f"Failed to create backup: {e}")
            return False
    
    async def rollback_changes(self) -> bool:
        """
        Rollback changes using backup.
        
        Returns:
            True if rollback was successful, False otherwise
        """
        if not self._backup_created or not self._backup_path:
            return False
        
        try:
            import shutil
            
            # Restore files from backup
            for backup_file in self._backup_path.rglob("*"):
                if backup_file.is_file():
                    relative_path = backup_file.relative_to(self._backup_path)
                    original_file = self.target_directory / relative_path
                    original_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, original_file)
            
            return True
            
        except Exception as e:
            print(f"Failed to rollback changes: {e}")
            return False
    
    async def pre_clean(self, analysis_results: AnalysisResults) -> bool:
        """
        Perform any setup before cleaning.
        Override in subclasses if needed.
        
        Args:
            analysis_results: Analysis results
            
        Returns:
            True if setup was successful, False otherwise
        """
        return True
    
    async def post_clean(self, result: CleanupResult) -> None:
        """
        Perform any cleanup after cleaning operations.
        Override in subclasses if needed.
        
        Args:
            result: Result of cleanup operations
        """
        pass
    
    def get_applicable_issues(self, analysis_results: AnalysisResults) -> List[Issue]:
        """
        Get list of issues this cleaner can handle.
        
        Args:
            analysis_results: Analysis results
            
        Returns:
            List of issues this cleaner can fix
        """
        applicable_issues = []
        
        # Check all issue types
        all_issues = (
            analysis_results.quality_issues +
            analysis_results.duplicates +
            analysis_results.import_issues +
            analysis_results.structure_issues +
            analysis_results.coverage_gaps +
            analysis_results.config_issues +
            analysis_results.doc_issues
        )
        
        for issue in all_issues:
            if self.can_clean_issue(issue):
                applicable_issues.append(issue)
        
        return applicable_issues
    
    def get_cleanup_summary(self, result: CleanupResult) -> Dict[str, Any]:
        """
        Get summary of cleanup results.
        
        Args:
            result: Cleanup result
            
        Returns:
            Dictionary with cleanup summary
        """
        return {
            "cleaner": self.name,
            "success": result.success,
            "files_modified": len(result.files_modified),
            "changes_made": result.changes_made,
            "message": result.message,
            "backup_created": self._backup_created,
            "backup_path": str(self._backup_path) if self._backup_path else None,
        }