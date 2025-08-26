"""
Core Data Models for Codebase Checkup and Cleanup

Contains all data structures used throughout the checkup system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from abc import ABC


class IssueSeverity(Enum):
    """Severity levels for issues found during analysis."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueType(Enum):
    """Types of issues that can be detected."""
    SYNTAX_ERROR = "syntax_error"
    STYLE_VIOLATION = "style_violation"
    CODE_SMELL = "code_smell"
    COMPLEXITY = "complexity"
    DUPLICATE_CODE = "duplicate_code"
    UNUSED_IMPORT = "unused_import"
    CIRCULAR_IMPORT = "circular_import"
    ORPHANED_MODULE = "orphaned_module"
    COVERAGE_GAP = "coverage_gap"
    CONFIG_ISSUE = "config_issue"
    DOC_ISSUE = "doc_issue"
    STRUCTURE_ISSUE = "structure_issue"


@dataclass
class Issue(ABC):
    """Base class for all issues detected during analysis."""
    file_path: Path
    line_number: Optional[int]
    severity: IssueSeverity
    issue_type: IssueType
    message: str
    description: str
    suggestion: Optional[str] = None
    confidence: float = 1.0  # 0.0 to 1.0


@dataclass
class QualityIssue(Issue):
    """Issues related to code quality (syntax, style, complexity)."""
    rule_name: Optional[str] = None
    tool_name: Optional[str] = None


@dataclass
class Duplicate(Issue):
    """Duplicate or similar code blocks."""
    duplicate_files: List[Path] = field(default_factory=list)
    similarity_score: float = 1.0
    lines_of_code: int = 0
    refactoring_suggestion: Optional[str] = None


@dataclass
class ImportIssue(Issue):
    """Issues related to imports and dependencies."""
    import_name: str = ""
    is_circular: bool = False
    dependency_chain: List[str] = field(default_factory=list)


@dataclass
class StructureIssue(Issue):
    """Issues related to file and directory organization."""
    suggested_location: Optional[Path] = None
    impact_assessment: Optional[str] = None


@dataclass
class CoverageGap(Issue):
    """Gaps in test coverage."""
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    coverage_percentage: float = 0.0
    test_suggestion: Optional[str] = None


@dataclass
class ConfigIssue(Issue):
    """Issues with configuration files."""
    config_file: Path = Path()
    config_section: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None


@dataclass
class DocIssue(Issue):
    """Issues with documentation."""
    doc_type: str = ""  # "api", "example", "installation", etc.
    broken_link: Optional[str] = None
    outdated_example: bool = False


@dataclass
class CodebaseMetrics:
    """Metrics about the codebase."""
    total_files: int = 0
    total_lines: int = 0
    python_files: int = 0
    test_files: int = 0
    documentation_files: int = 0
    config_files: int = 0
    
    # Quality metrics
    syntax_errors: int = 0
    style_violations: int = 0
    code_smells: int = 0
    complexity_issues: int = 0
    
    # Import metrics
    unused_imports: int = 0
    circular_imports: int = 0
    orphaned_modules: int = 0
    
    # Coverage metrics
    test_coverage_percentage: float = 0.0
    untested_functions: int = 0
    
    # Duplicate metrics
    duplicate_blocks: int = 0
    duplicate_lines: int = 0
    
    # Structure metrics
    misplaced_files: int = 0
    empty_directories: int = 0
    
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AnalysisResults:
    """Results from code analysis."""
    quality_issues: List[QualityIssue] = field(default_factory=list)
    duplicates: List[Duplicate] = field(default_factory=list)
    import_issues: List[ImportIssue] = field(default_factory=list)
    structure_issues: List[StructureIssue] = field(default_factory=list)
    coverage_gaps: List[CoverageGap] = field(default_factory=list)
    config_issues: List[ConfigIssue] = field(default_factory=list)
    doc_issues: List[DocIssue] = field(default_factory=list)
    
    metrics: CodebaseMetrics = field(default_factory=CodebaseMetrics)
    timestamp: datetime = field(default_factory=datetime.now)
    duration: timedelta = field(default_factory=lambda: timedelta(0))
    
    @property
    def total_issues(self) -> int:
        """Total number of issues found."""
        return (len(self.quality_issues) + len(self.duplicates) + 
                len(self.import_issues) + len(self.structure_issues) +
                len(self.coverage_gaps) + len(self.config_issues) + 
                len(self.doc_issues))
    
    @property
    def critical_issues(self) -> List[Issue]:
        """All critical severity issues."""
        all_issues = (self.quality_issues + self.duplicates + 
                     self.import_issues + self.structure_issues +
                     self.coverage_gaps + self.config_issues + 
                     self.doc_issues)
        return [issue for issue in all_issues if issue.severity == IssueSeverity.CRITICAL]


@dataclass
class FormattingChange:
    """Record of a formatting change made."""
    file_path: Path
    change_type: str  # "black", "isort", "docstring"
    lines_changed: int = 0
    description: str = ""


@dataclass
class ImportCleanup:
    """Record of import cleanup performed."""
    file_path: Path
    removed_imports: List[str] = field(default_factory=list)
    reorganized_imports: bool = False
    circular_imports_resolved: List[str] = field(default_factory=list)


@dataclass
class FileMove:
    """Record of a file move operation."""
    source_path: Path
    destination_path: Path
    reason: str = ""
    success: bool = True


@dataclass
class FileRemoval:
    """Record of a file removal operation."""
    file_path: Path
    reason: str = ""
    backup_path: Optional[Path] = None
    success: bool = True


@dataclass
class AutoFix:
    """Record of an automated fix applied."""
    file_path: Path
    issue_type: IssueType
    fix_description: str
    success: bool = True
    original_content: Optional[str] = None


@dataclass
class CleanupResults:
    """Results from cleanup operations."""
    formatting_changes: List[FormattingChange] = field(default_factory=list)
    import_cleanups: List[ImportCleanup] = field(default_factory=list)
    file_moves: List[FileMove] = field(default_factory=list)
    file_removals: List[FileRemoval] = field(default_factory=list)
    auto_fixes: List[AutoFix] = field(default_factory=list)
    
    timestamp: datetime = field(default_factory=datetime.now)
    duration: timedelta = field(default_factory=lambda: timedelta(0))
    backup_created: bool = False
    backup_path: Optional[Path] = None
    
    @property
    def total_changes(self) -> int:
        """Total number of changes made."""
        return (len(self.formatting_changes) + len(self.import_cleanups) +
                len(self.file_moves) + len(self.file_removals) + 
                len(self.auto_fixes))
    
    @property
    def successful_changes(self) -> int:
        """Number of successful changes."""
        successful = len(self.formatting_changes) + len(self.import_cleanups)
        successful += sum(1 for move in self.file_moves if move.success)
        successful += sum(1 for removal in self.file_removals if removal.success)
        successful += sum(1 for fix in self.auto_fixes if fix.success)
        return successful


@dataclass
class CheckupResults:
    """Complete results from a checkup operation."""
    analysis: AnalysisResults
    cleanup: Optional[CleanupResults] = None
    before_metrics: CodebaseMetrics = field(default_factory=CodebaseMetrics)
    after_metrics: Optional[CodebaseMetrics] = None
    
    duration: timedelta = field(default_factory=lambda: timedelta(0))
    success: bool = True
    error_message: Optional[str] = None
    
    @property
    def improvement_metrics(self) -> Dict[str, Union[int, float]]:
        """Calculate improvement metrics if cleanup was performed."""
        if not self.cleanup or not self.after_metrics:
            return {}
        
        return {
            "issues_fixed": self.before_metrics.syntax_errors + 
                           self.before_metrics.style_violations - 
                           (self.after_metrics.syntax_errors + 
                            self.after_metrics.style_violations),
            "imports_cleaned": self.before_metrics.unused_imports - 
                              self.after_metrics.unused_imports,
            "files_organized": len(self.cleanup.file_moves),
            "coverage_improvement": self.after_metrics.test_coverage_percentage - 
                                   self.before_metrics.test_coverage_percentage,
        }


@dataclass
class CheckupConfig:
    """Configuration for checkup operations."""
    # Target directory
    target_directory: Path = Path(".")
    
    # Analysis settings
    enable_quality_analysis: bool = True
    enable_duplicate_detection: bool = True
    enable_import_analysis: bool = True
    enable_structure_analysis: bool = True
    
    # Quality analysis settings
    max_complexity: int = 10
    max_line_length: int = 88
    check_type_hints: bool = True
    
    # Duplicate detection settings
    similarity_threshold: float = 0.8
    min_duplicate_lines: int = 5
    
    # Import analysis settings
    remove_unused_imports: bool = False
    organize_imports: bool = False
    
    # Cleanup settings
    auto_format: bool = False
    auto_fix_imports: bool = False
    auto_organize_files: bool = False
    
    # Validation settings
    check_test_coverage: bool = True
    min_coverage_threshold: float = 80.0
    validate_configs: bool = True
    validate_docs: bool = True
    
    # Reporting settings
    generate_html_report: bool = True
    generate_json_report: bool = True
    generate_markdown_report: bool = True
    report_output_dir: Path = Path("checkup_reports")
    
    # Safety settings
    create_backup: bool = True
    backup_dir: Path = Path("checkup_backups")
    dry_run: bool = False
    max_file_moves: int = 10
    
    # Tool configurations
    black_config: Dict[str, Any] = field(default_factory=dict)
    isort_config: Dict[str, Any] = field(default_factory=dict)
    flake8_config: Dict[str, Any] = field(default_factory=dict)
    mypy_config: Dict[str, Any] = field(default_factory=dict)
    
    # Exclusion patterns
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "*.pyc", "__pycache__", ".git", ".pytest_cache", "node_modules"
    ])
    exclude_dirs: List[str] = field(default_factory=lambda: [
        ".git", "__pycache__", ".pytest_cache", "venv", ".venv"
    ])
    
    def validate(self) -> List[str]:
        """Validate configuration and return any errors."""
        errors = []
        
        if not self.target_directory.exists():
            errors.append(f"Target directory does not exist: {self.target_directory}")
        
        if self.similarity_threshold < 0.0 or self.similarity_threshold > 1.0:
            errors.append("Similarity threshold must be between 0.0 and 1.0")
        
        if self.min_coverage_threshold < 0.0 or self.min_coverage_threshold > 100.0:
            errors.append("Coverage threshold must be between 0.0 and 100.0")
        
        if self.max_file_moves < 0:
            errors.append("Max file moves must be non-negative")
        
        return errors