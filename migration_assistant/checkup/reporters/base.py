"""
Base Report Generator Interface

Defines the common interface for all report generators.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from dataclasses import dataclass, field

from migration_assistant.checkup.models import (
    CheckupResults, AnalysisResults, CleanupResults, CheckupConfig,
    Issue, IssueSeverity, IssueType
)


@dataclass
class ReportSection:
    """Represents a section in a report."""
    title: str
    content: str
    subsections: List['ReportSection'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportTemplate:
    """Template for consistent report formatting."""
    header_template: str = ""
    section_template: str = ""
    footer_template: str = ""
    css_styles: str = ""
    javascript: str = ""


class ReportUtils:
    """Utility functions for report generation."""
    
    @staticmethod
    def format_file_path(path: Path, base_path: Optional[Path] = None) -> str:
        """Format file path for display."""
        if base_path:
            try:
                return str(path.relative_to(base_path))
            except ValueError:
                return str(path)
        return str(path)
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """Format percentage for display."""
        return f"{value:.{decimals}f}%"
    
    @staticmethod
    def format_number(value: int) -> str:
        """Format number with thousands separator."""
        return f"{value:,}"
    
    @staticmethod
    def get_severity_color(severity: IssueSeverity) -> str:
        """Get color code for severity level."""
        colors = {
            IssueSeverity.LOW: "#28a745",      # Green
            IssueSeverity.MEDIUM: "#ffc107",   # Yellow
            IssueSeverity.HIGH: "#fd7e14",     # Orange
            IssueSeverity.CRITICAL: "#dc3545"  # Red
        }
        return colors.get(severity, "#6c757d")  # Default gray
    
    @staticmethod
    def get_severity_icon(severity: IssueSeverity) -> str:
        """Get icon for severity level."""
        icons = {
            IssueSeverity.LOW: "ℹ️",
            IssueSeverity.MEDIUM: "⚠️",
            IssueSeverity.HIGH: "🔶",
            IssueSeverity.CRITICAL: "🔴"
        }
        return icons.get(severity, "❓")
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100) -> str:
        """Truncate text to specified length."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    @staticmethod
    def group_issues_by_file(issues: List[Issue]) -> Dict[str, List[Issue]]:
        """Group issues by file path."""
        grouped = {}
        for issue in issues:
            file_path = str(issue.file_path)
            if file_path not in grouped:
                grouped[file_path] = []
            grouped[file_path].append(issue)
        return grouped
    
    @staticmethod
    def group_issues_by_type(issues: List[Issue]) -> Dict[IssueType, List[Issue]]:
        """Group issues by type."""
        grouped = {}
        for issue in issues:
            if issue.issue_type not in grouped:
                grouped[issue.issue_type] = []
            grouped[issue.issue_type].append(issue)
        return grouped
    
    @staticmethod
    def group_issues_by_severity(issues: List[Issue]) -> Dict[IssueSeverity, List[Issue]]:
        """Group issues by severity."""
        grouped = {}
        for issue in issues:
            if issue.severity not in grouped:
                grouped[issue.severity] = []
            grouped[issue.severity].append(issue)
        return grouped
    
    @staticmethod
    def calculate_quality_score(results: AnalysisResults) -> float:
        """Calculate overall quality score (0-100)."""
        if results.metrics.total_files == 0:
            return 100.0
        
        # Weight different issue types
        weights = {
            'critical': 10,
            'high': 5,
            'medium': 2,
            'low': 1
        }
        
        severity_counts = {}
        all_issues = (
            results.quality_issues + results.duplicates + 
            results.import_issues + results.structure_issues +
            results.coverage_gaps + results.config_issues + 
            results.doc_issues
        )
        
        for issue in all_issues:
            severity = issue.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Calculate weighted penalty
        penalty = sum(
            severity_counts.get(severity, 0) * weight 
            for severity, weight in weights.items()
        )
        
        # Normalize by file count and convert to score
        max_penalty = results.metrics.total_files * 20  # Assume max 20 points penalty per file
        if max_penalty == 0:
            return 100.0
        
        score = max(0, 100 - (penalty / max_penalty * 100))
        return round(score, 1)


class ReportGenerator(ABC):
    """Abstract base class for all report generators."""
    
    def __init__(self, config: CheckupConfig):
        """Initialize the report generator with configuration."""
        self.config = config
        self.output_dir = config.report_output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.utils = ReportUtils()
        self.template = self._get_default_template()
    
    @property
    def name(self) -> str:
        """Return the report generator name."""
        return self.__class__.__name__
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return the file extension for this report type."""
        pass
    
    @abstractmethod
    async def generate_summary_report(self, results: CheckupResults) -> str:
        """
        Generate a summary report of checkup results.
        
        Args:
            results: Complete checkup results
            
        Returns:
            Report content as string
        """
        pass
    
    @abstractmethod
    async def generate_detailed_report(self, results: CheckupResults) -> str:
        """
        Generate a detailed report of checkup results.
        
        Args:
            results: Complete checkup results
            
        Returns:
            Report content as string
        """
        pass
    
    @abstractmethod
    async def generate_comparison_report(
        self, 
        before: CheckupResults, 
        after: CheckupResults
    ) -> str:
        """
        Generate a comparison report between two checkup results.
        
        Args:
            before: Results from before cleanup
            after: Results from after cleanup
            
        Returns:
            Report content as string
        """
        pass
    
    async def save_report(self, content: str, filename: str) -> Path:
        """
        Save report content to file.
        
        Args:
            content: Report content to save
            filename: Name of the file (without extension)
            
        Returns:
            Path to the saved report file
        """
        report_file = self.output_dir / f"{filename}{self.file_extension}"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(content)
            return report_file
        except Exception as e:
            raise RuntimeError(f"Failed to save report to {report_file}: {e}")
    
    async def generate_and_save_summary(
        self, 
        results: CheckupResults, 
        filename: Optional[str] = None
    ) -> Path:
        """
        Generate and save summary report.
        
        Args:
            results: Checkup results
            filename: Optional custom filename
            
        Returns:
            Path to saved report
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"checkup_summary_{timestamp}"
        
        content = await self.generate_summary_report(results)
        return await self.save_report(content, filename)
    
    async def generate_and_save_detailed(
        self, 
        results: CheckupResults, 
        filename: Optional[str] = None
    ) -> Path:
        """
        Generate and save detailed report.
        
        Args:
            results: Checkup results
            filename: Optional custom filename
            
        Returns:
            Path to saved report
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"checkup_detailed_{timestamp}"
        
        content = await self.generate_detailed_report(results)
        return await self.save_report(content, filename)
    
    async def generate_and_save_comparison(
        self, 
        before: CheckupResults, 
        after: CheckupResults, 
        filename: Optional[str] = None
    ) -> Path:
        """
        Generate and save comparison report.
        
        Args:
            before: Results from before cleanup
            after: Results from after cleanup
            filename: Optional custom filename
            
        Returns:
            Path to saved report
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"checkup_comparison_{timestamp}"
        
        content = await self.generate_comparison_report(before, after)
        return await self.save_report(content, filename)
    
    def get_report_metadata(self, results: CheckupResults) -> Dict[str, Any]:
        """
        Get metadata for the report.
        
        Args:
            results: Checkup results
            
        Returns:
            Dictionary with report metadata
        """
        return {
            "generator": self.name,
            "generated_at": datetime.now().isoformat(),
            "checkup_timestamp": results.analysis.timestamp.isoformat(),
            "target_directory": str(self.config.target_directory),
            "total_issues": results.analysis.total_issues,
            "cleanup_performed": results.cleanup is not None,
            "success": results.success,
        }
    
    def format_duration(self, duration) -> str:
        """
        Format duration for display.
        
        Args:
            duration: timedelta object
            
        Returns:
            Formatted duration string
        """
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_severity_counts(self, results: AnalysisResults) -> Dict[str, int]:
        """
        Get count of issues by severity.
        
        Args:
            results: Analysis results
            
        Returns:
            Dictionary with severity counts
        """
        from migration_assistant.checkup.models import IssueSeverity
        
        severity_counts = {severity.value: 0 for severity in IssueSeverity}
        
        all_issues = (
            results.quality_issues + results.duplicates + 
            results.import_issues + results.structure_issues +
            results.coverage_gaps + results.config_issues + 
            results.doc_issues
        )
        
        for issue in all_issues:
            severity_counts[issue.severity.value] += 1
        
        return severity_counts
    
    def get_issue_type_counts(self, results: AnalysisResults) -> Dict[str, int]:
        """
        Get count of issues by type.
        
        Args:
            results: Analysis results
            
        Returns:
            Dictionary with issue type counts
        """
        return {
            "quality_issues": len(results.quality_issues),
            "duplicates": len(results.duplicates),
            "import_issues": len(results.import_issues),
            "structure_issues": len(results.structure_issues),
            "coverage_gaps": len(results.coverage_gaps),
            "config_issues": len(results.config_issues),
            "doc_issues": len(results.doc_issues),
        }
    
    def _get_default_template(self) -> ReportTemplate:
        """
        Get default template for this report type.
        
        Returns:
            Default report template
        """
        return ReportTemplate()
    
    def create_report_sections(self, results: CheckupResults) -> List[ReportSection]:
        """
        Create structured report sections from results.
        
        Args:
            results: Checkup results
            
        Returns:
            List of report sections
        """
        sections = []
        
        # Executive Summary
        sections.append(self._create_summary_section(results))
        
        # Analysis Results
        if results.analysis.total_issues > 0:
            sections.append(self._create_analysis_section(results.analysis))
        
        # Cleanup Results
        if results.cleanup:
            sections.append(self._create_cleanup_section(results.cleanup))
        
        # Metrics and Statistics
        sections.append(self._create_metrics_section(results))
        
        return sections
    
    def _create_summary_section(self, results: CheckupResults) -> ReportSection:
        """Create executive summary section."""
        quality_score = self.utils.calculate_quality_score(results.analysis)
        
        return ReportSection(
            title="Executive Summary",
            content=f"Quality Score: {quality_score}/100",
            metadata={
                "quality_score": quality_score,
                "total_issues": results.analysis.total_issues,
                "duration": self.format_duration(results.duration),
                "success": results.success
            }
        )
    
    def _create_analysis_section(self, analysis: AnalysisResults) -> ReportSection:
        """Create analysis results section."""
        subsections = []
        
        if analysis.quality_issues:
            subsections.append(ReportSection(
                title="Code Quality Issues",
                content=f"Found {len(analysis.quality_issues)} quality issues",
                metadata={"count": len(analysis.quality_issues)}
            ))
        
        if analysis.duplicates:
            subsections.append(ReportSection(
                title="Duplicate Code",
                content=f"Found {len(analysis.duplicates)} duplicate code blocks",
                metadata={"count": len(analysis.duplicates)}
            ))
        
        if analysis.import_issues:
            subsections.append(ReportSection(
                title="Import Issues",
                content=f"Found {len(analysis.import_issues)} import-related issues",
                metadata={"count": len(analysis.import_issues)}
            ))
        
        if analysis.structure_issues:
            subsections.append(ReportSection(
                title="Structure Issues",
                content=f"Found {len(analysis.structure_issues)} structure issues",
                metadata={"count": len(analysis.structure_issues)}
            ))
        
        if analysis.coverage_gaps:
            subsections.append(ReportSection(
                title="Coverage Gaps",
                content=f"Found {len(analysis.coverage_gaps)} coverage gaps",
                metadata={"count": len(analysis.coverage_gaps)}
            ))
        
        return ReportSection(
            title="Analysis Results",
            content=f"Total issues found: {analysis.total_issues}",
            subsections=subsections,
            metadata={"total_issues": analysis.total_issues}
        )
    
    def _create_cleanup_section(self, cleanup: CleanupResults) -> ReportSection:
        """Create cleanup results section."""
        subsections = []
        
        if cleanup.formatting_changes:
            subsections.append(ReportSection(
                title="Formatting Changes",
                content=f"Applied {len(cleanup.formatting_changes)} formatting changes",
                metadata={"count": len(cleanup.formatting_changes)}
            ))
        
        if cleanup.import_cleanups:
            subsections.append(ReportSection(
                title="Import Cleanups",
                content=f"Cleaned up imports in {len(cleanup.import_cleanups)} files",
                metadata={"count": len(cleanup.import_cleanups)}
            ))
        
        if cleanup.file_moves:
            subsections.append(ReportSection(
                title="File Reorganization",
                content=f"Moved {len(cleanup.file_moves)} files",
                metadata={"count": len(cleanup.file_moves)}
            ))
        
        if cleanup.auto_fixes:
            subsections.append(ReportSection(
                title="Automated Fixes",
                content=f"Applied {len(cleanup.auto_fixes)} automated fixes",
                metadata={"count": len(cleanup.auto_fixes)}
            ))
        
        return ReportSection(
            title="Cleanup Results",
            content=f"Total changes made: {cleanup.total_changes}",
            subsections=subsections,
            metadata={
                "total_changes": cleanup.total_changes,
                "successful_changes": cleanup.successful_changes,
                "backup_created": cleanup.backup_created
            }
        )
    
    def _create_metrics_section(self, results: CheckupResults) -> ReportSection:
        """Create metrics and statistics section."""
        metrics = results.analysis.metrics
        
        return ReportSection(
            title="Codebase Metrics",
            content=f"Analyzed {metrics.total_files} files",
            metadata={
                "total_files": metrics.total_files,
                "total_lines": metrics.total_lines,
                "python_files": metrics.python_files,
                "test_files": metrics.test_files,
                "test_coverage": metrics.test_coverage_percentage
            }
        )
    
    def get_all_issues(self, results: AnalysisResults) -> List[Issue]:
        """
        Get all issues from analysis results.
        
        Args:
            results: Analysis results
            
        Returns:
            List of all issues
        """
        return (
            results.quality_issues + results.duplicates + 
            results.import_issues + results.structure_issues +
            results.coverage_gaps + results.config_issues + 
            results.doc_issues
        )
    
    def filter_issues_by_severity(
        self, 
        issues: List[Issue], 
        severity: IssueSeverity
    ) -> List[Issue]:
        """
        Filter issues by severity level.
        
        Args:
            issues: List of issues to filter
            severity: Severity level to filter by
            
        Returns:
            Filtered list of issues
        """
        return [issue for issue in issues if issue.severity == severity]
    
    def filter_issues_by_file(
        self, 
        issues: List[Issue], 
        file_path: Path
    ) -> List[Issue]:
        """
        Filter issues by file path.
        
        Args:
            issues: List of issues to filter
            file_path: File path to filter by
            
        Returns:
            Filtered list of issues
        """
        return [issue for issue in issues if issue.file_path == file_path]