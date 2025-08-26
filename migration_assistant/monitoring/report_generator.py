"""
Comprehensive reporting engine for migration operations.

This module provides report generation for migration summaries, error diagnostics,
validation reports, and performance analysis with multiple output formats.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel

from migration_assistant.models.session import (
    MigrationSession, MigrationStep, MigrationStatus, StepStatus,
    LogLevel, ErrorInfo, ReportInfo, ReportType, ValidationResult
)
from migration_assistant.monitoring.progress_tracker import ProgressMetrics
from migration_assistant.monitoring.performance_monitor import (
    PerformanceMetric, TransferMetrics, DatabaseMetrics, ResourceUsage
)


class ReportFormat(str, Enum):
    """Supported report formats."""
    JSON = "json"
    HTML = "html"
    PDF = "pdf"
    CSV = "csv"
    MARKDOWN = "markdown"
    TEXT = "text"


class ReportSeverity(str, Enum):
    """Report severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ReportSection:
    """Individual report section."""
    title: str
    content: Dict[str, Any]
    severity: ReportSeverity = ReportSeverity.INFO
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReportData:
    """Validation report data structure."""
    session_id: str
    timestamp: datetime
    overall_result: bool
    checks_performed: int
    checks_passed: int
    checks_failed: int
    warnings_count: int
    errors: List[ErrorInfo]
    warnings: List[str]
    recommendations: List[str]
    estimated_fix_time: Optional[str]
    details: Dict[str, Any]


@dataclass
class MigrationSummaryData:
    """Migration summary report data."""
    session_id: str
    migration_name: str
    status: MigrationStatus
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]
    source_system: str
    destination_system: str
    steps_completed: int
    steps_total: int
    steps_failed: int
    files_transferred: Optional[int]
    data_transferred_mb: Optional[float]
    errors_count: int
    warnings_count: int
    performance_summary: Dict[str, Any]
    backup_info: List[Dict[str, Any]]


@dataclass
class ErrorReportData:
    """Error report data structure."""
    session_id: str
    timestamp: datetime
    error_summary: ErrorInfo
    affected_steps: List[str]
    error_timeline: List[Dict[str, Any]]
    remediation_steps: List[str]
    rollback_performed: bool
    recovery_options: List[str]
    support_info: Dict[str, Any]


class ReportGenerator:
    """
    Comprehensive report generator for migration operations.
    
    Generates various types of reports in multiple formats including
    validation reports, migration summaries, error diagnostics, and
    performance analysis.
    """
    
    def __init__(
        self,
        output_directory: str = "./reports",
        template_directory: Optional[str] = None
    ):
        """
        Initialize report generator.
        
        Args:
            output_directory: Directory to save generated reports
            template_directory: Directory containing report templates
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        # Set up Jinja2 environment for HTML templates
        if template_directory:
            self.template_env = Environment(
                loader=FileSystemLoader(template_directory)
            )
        else:
            # Use built-in templates
            self.template_env = Environment(
                loader=FileSystemLoader(
                    Path(__file__).parent / "templates"
                )
            )
        
        # Report metadata
        self._generated_reports: Dict[str, ReportInfo] = {}
    
    def generate_validation_report(
        self,
        session: MigrationSession,
        validation_result: ValidationResult,
        format: ReportFormat = ReportFormat.HTML,
        include_remediation: bool = True
    ) -> ReportInfo:
        """
        Generate validation report with detailed diagnostics.
        
        Args:
            session: Migration session
            validation_result: Validation results
            format: Output format
            include_remediation: Include remediation suggestions
            
        Returns:
            Report information
        """
        report_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Prepare validation data
        validation_data = ValidationReportData(
            session_id=session.id,
            timestamp=timestamp,
            overall_result=validation_result.passed,
            checks_performed=validation_result.checks_performed,
            checks_passed=validation_result.checks_passed,
            checks_failed=validation_result.checks_failed,
            warnings_count=validation_result.warnings,
            errors=validation_result.errors,
            warnings=validation_result.warnings_list,
            recommendations=validation_result.recommendations,
            estimated_fix_time=self._format_duration(validation_result.estimated_duration),
            details=validation_result.details
        )
        
        # Create report sections
        sections = [
            self._create_validation_summary_section(validation_data),
            self._create_validation_details_section(validation_data),
        ]
        
        if validation_data.errors:
            sections.append(self._create_error_analysis_section(validation_data.errors))
        
        if include_remediation and validation_data.recommendations:
            sections.append(self._create_remediation_section(validation_data.recommendations))
        
        # Generate report
        report_content = {
            "report_id": report_id,
            "report_type": "validation",
            "session_id": session.id,
            "migration_name": session.config.name,
            "timestamp": timestamp.isoformat(),
            "validation_data": validation_data.__dict__,
            "sections": [section.__dict__ for section in sections]
        }
        
        # Save report
        filename = f"validation_report_{session.id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        file_path = self._save_report(report_content, filename, format)
        
        # Create report info
        report_info = ReportInfo(
            id=report_id,
            type=ReportType.VALIDATION,
            title=f"Validation Report - {session.config.name}",
            generated_at=timestamp,
            format=format.value,
            location=str(file_path),
            size=file_path.stat().st_size if file_path.exists() else 0,
            summary={
                "overall_result": validation_result.passed,
                "checks_performed": validation_result.checks_performed,
                "checks_failed": validation_result.checks_failed,
                "warnings": validation_result.warnings
            }
        )
        
        self._generated_reports[report_id] = report_info
        return report_info
    
    def generate_migration_summary_report(
        self,
        session: MigrationSession,
        performance_data: Optional[Dict[str, Any]] = None,
        format: ReportFormat = ReportFormat.HTML
    ) -> ReportInfo:
        """
        Generate comprehensive migration summary report.
        
        Args:
            session: Migration session
            performance_data: Optional performance metrics
            format: Output format
            
        Returns:
            Report information
        """
        report_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Calculate summary statistics
        steps_completed = sum(1 for step in session.steps if step.status == StepStatus.COMPLETED)
        steps_failed = sum(1 for step in session.steps if step.status == StepStatus.FAILED)
        errors_count = len([log for log in session.logs if log.level == LogLevel.ERROR])
        warnings_count = len([log for log in session.logs if log.level == LogLevel.WARNING])
        
        # Extract performance data
        files_transferred = None
        data_transferred_mb = None
        if performance_data:
            transfer_metrics = performance_data.get("transfer_metrics", {})
            if transfer_metrics:
                files_transferred = sum(
                    metrics.get("files_transferred", 0) 
                    for metrics in transfer_metrics.values()
                )
                data_transferred_mb = sum(
                    metrics.get("bytes_transferred", 0) 
                    for metrics in transfer_metrics.values()
                ) / (1024 * 1024)
        
        # Prepare summary data
        summary_data = MigrationSummaryData(
            session_id=session.id,
            migration_name=session.config.name,
            status=session.status,
            start_time=session.start_time or session.created_at,
            end_time=session.end_time,
            duration=session.duration,
            source_system=f"{session.config.source.type.value} ({session.config.source.host})",
            destination_system=f"{session.config.destination.type.value} ({session.config.destination.host})",
            steps_completed=steps_completed,
            steps_total=len(session.steps),
            steps_failed=steps_failed,
            files_transferred=files_transferred,
            data_transferred_mb=data_transferred_mb,
            errors_count=errors_count,
            warnings_count=warnings_count,
            performance_summary=performance_data or {},
            backup_info=[backup.__dict__ for backup in session.backups]
        )
        
        # Create report sections
        sections = [
            self._create_migration_overview_section(summary_data),
            self._create_steps_summary_section(session.steps),
            self._create_performance_section(summary_data.performance_summary),
        ]
        
        if session.backups:
            sections.append(self._create_backup_section(session.backups))
        
        if errors_count > 0 or warnings_count > 0:
            sections.append(self._create_issues_section(session.logs))
        
        # Generate report
        report_content = {
            "report_id": report_id,
            "report_type": "migration_summary",
            "session_id": session.id,
            "migration_name": session.config.name,
            "timestamp": timestamp.isoformat(),
            "summary_data": summary_data.__dict__,
            "sections": [section.__dict__ for section in sections]
        }
        
        # Save report
        filename = f"migration_summary_{session.id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        file_path = self._save_report(report_content, filename, format)
        
        # Create report info
        report_info = ReportInfo(
            id=report_id,
            type=ReportType.SUMMARY,
            title=f"Migration Summary - {session.config.name}",
            generated_at=timestamp,
            format=format.value,
            location=str(file_path),
            size=file_path.stat().st_size if file_path.exists() else 0,
            summary={
                "status": session.status.value,
                "steps_completed": steps_completed,
                "steps_total": len(session.steps),
                "duration": session.duration,
                "errors_count": errors_count
            }
        )
        
        self._generated_reports[report_id] = report_info
        return report_info
    
    def generate_error_report(
        self,
        session: MigrationSession,
        primary_error: ErrorInfo,
        format: ReportFormat = ReportFormat.HTML,
        include_logs: bool = True
    ) -> ReportInfo:
        """
        Generate detailed error diagnostic report.
        
        Args:
            session: Migration session
            primary_error: Primary error that caused failure
            format: Output format
            include_logs: Include detailed logs
            
        Returns:
            Report information
        """
        report_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Find affected steps
        affected_steps = []
        for step in session.steps:
            if step.error or step.status == StepStatus.FAILED:
                affected_steps.append(step.id)
        
        # Create error timeline
        error_timeline = []
        for log in session.logs:
            if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                error_timeline.append({
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level.value,
                    "message": log.message,
                    "component": log.component,
                    "step_id": log.step_id
                })
        
        # Prepare error data
        error_data = ErrorReportData(
            session_id=session.id,
            timestamp=timestamp,
            error_summary=primary_error,
            affected_steps=affected_steps,
            error_timeline=error_timeline,
            remediation_steps=primary_error.remediation_steps,
            rollback_performed=session.status == MigrationStatus.ROLLED_BACK,
            recovery_options=self._generate_recovery_options(session, primary_error),
            support_info=self._generate_support_info(session, primary_error)
        )
        
        # Create report sections
        sections = [
            self._create_error_summary_section(error_data),
            self._create_error_timeline_section(error_data.error_timeline),
            self._create_recovery_section(error_data.recovery_options),
        ]
        
        if include_logs:
            sections.append(self._create_logs_section(session.logs))
        
        # Generate report
        report_content = {
            "report_id": report_id,
            "report_type": "error_diagnostic",
            "session_id": session.id,
            "migration_name": session.config.name,
            "timestamp": timestamp.isoformat(),
            "error_data": error_data.__dict__,
            "sections": [section.__dict__ for section in sections]
        }
        
        # Save report
        filename = f"error_report_{session.id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        file_path = self._save_report(report_content, filename, format)
        
        # Create report info
        report_info = ReportInfo(
            id=report_id,
            type=ReportType.ERROR,
            title=f"Error Report - {session.config.name}",
            generated_at=timestamp,
            format=format.value,
            location=str(file_path),
            size=file_path.stat().st_size if file_path.exists() else 0,
            summary={
                "error_code": primary_error.code,
                "severity": primary_error.severity.value,
                "affected_steps": len(affected_steps),
                "rollback_performed": error_data.rollback_performed
            }
        )
        
        self._generated_reports[report_id] = report_info
        return report_info
    
    def generate_performance_report(
        self,
        session_id: str,
        performance_data: Dict[str, Any],
        format: ReportFormat = ReportFormat.HTML
    ) -> ReportInfo:
        """
        Generate performance analysis report.
        
        Args:
            session_id: Migration session ID
            performance_data: Performance metrics data
            format: Output format
            
        Returns:
            Report information
        """
        report_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Create report sections
        sections = [
            self._create_performance_overview_section(performance_data),
            self._create_transfer_performance_section(
                performance_data.get("transfer_metrics", {})
            ),
            self._create_database_performance_section(
                performance_data.get("database_metrics", {})
            ),
            self._create_resource_usage_section(
                performance_data.get("resource_usage", {})
            )
        ]
        
        # Generate report
        report_content = {
            "report_id": report_id,
            "report_type": "performance",
            "session_id": session_id,
            "timestamp": timestamp.isoformat(),
            "performance_data": performance_data,
            "sections": [section.__dict__ for section in sections]
        }
        
        # Save report
        filename = f"performance_report_{session_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        file_path = self._save_report(report_content, filename, format)
        
        # Create report info
        report_info = ReportInfo(
            id=report_id,
            type=ReportType.PERFORMANCE,
            title=f"Performance Report - {session_id}",
            generated_at=timestamp,
            format=format.value,
            location=str(file_path),
            size=file_path.stat().st_size if file_path.exists() else 0,
            summary=self._extract_performance_summary(performance_data)
        )
        
        self._generated_reports[report_id] = report_info
        return report_info
    
    def get_report(self, report_id: str) -> Optional[ReportInfo]:
        """Get report information by ID."""
        return self._generated_reports.get(report_id)
    
    def list_reports(
        self,
        session_id: Optional[str] = None,
        report_type: Optional[ReportType] = None
    ) -> List[ReportInfo]:
        """
        List generated reports with optional filtering.
        
        Args:
            session_id: Filter by session ID
            report_type: Filter by report type
            
        Returns:
            List of report information
        """
        reports = list(self._generated_reports.values())
        
        if session_id:
            reports = [r for r in reports if session_id in r.metadata.get("session_id", "")]
        
        if report_type:
            reports = [r for r in reports if r.type == report_type]
        
        return sorted(reports, key=lambda r: r.generated_at, reverse=True)
    
    def cleanup_old_reports(self, days: int = 30):
        """
        Clean up reports older than specified days.
        
        Args:
            days: Number of days to keep reports
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        reports_to_remove = []
        for report_id, report_info in self._generated_reports.items():
            if report_info.generated_at < cutoff_date:
                # Delete file if it exists
                if report_info.location and Path(report_info.location).exists():
                    Path(report_info.location).unlink()
                reports_to_remove.append(report_id)
        
        # Remove from tracking
        for report_id in reports_to_remove:
            del self._generated_reports[report_id]
    
    def _create_validation_summary_section(self, data: ValidationReportData) -> ReportSection:
        """Create validation summary section."""
        severity = ReportSeverity.ERROR if not data.overall_result else ReportSeverity.INFO
        
        content = {
            "overall_result": data.overall_result,
            "checks_performed": data.checks_performed,
            "checks_passed": data.checks_passed,
            "checks_failed": data.checks_failed,
            "warnings_count": data.warnings_count,
            "success_rate": (data.checks_passed / data.checks_performed * 100) if data.checks_performed > 0 else 0,
            "estimated_fix_time": data.estimated_fix_time
        }
        
        return ReportSection(
            title="Validation Summary",
            content=content,
            severity=severity
        )
    
    def _create_validation_details_section(self, data: ValidationReportData) -> ReportSection:
        """Create validation details section."""
        content = {
            "errors": [error.__dict__ for error in data.errors],
            "warnings": data.warnings,
            "details": data.details
        }
        
        return ReportSection(
            title="Validation Details",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _create_error_analysis_section(self, errors: List[ErrorInfo]) -> ReportSection:
        """Create error analysis section."""
        # Group errors by severity
        error_groups = {}
        for error in errors:
            severity = error.severity.value
            if severity not in error_groups:
                error_groups[severity] = []
            error_groups[severity].append(error.__dict__)
        
        content = {
            "error_groups": error_groups,
            "total_errors": len(errors),
            "critical_errors": len([e for e in errors if e.severity.value == "critical"]),
            "high_errors": len([e for e in errors if e.severity.value == "high"])
        }
        
        return ReportSection(
            title="Error Analysis",
            content=content,
            severity=ReportSeverity.ERROR
        )
    
    def _create_remediation_section(self, recommendations: List[str]) -> ReportSection:
        """Create remediation section."""
        content = {
            "recommendations": recommendations,
            "priority_actions": recommendations[:3],  # Top 3 recommendations
            "total_recommendations": len(recommendations)
        }
        
        return ReportSection(
            title="Remediation Suggestions",
            content=content,
            severity=ReportSeverity.WARNING
        )
    
    def _create_migration_overview_section(self, data: MigrationSummaryData) -> ReportSection:
        """Create migration overview section."""
        content = {
            "migration_name": data.migration_name,
            "status": data.status.value,
            "source_system": data.source_system,
            "destination_system": data.destination_system,
            "start_time": data.start_time.isoformat() if data.start_time else None,
            "end_time": data.end_time.isoformat() if data.end_time else None,
            "duration": self._format_duration(data.duration),
            "completion_rate": (data.steps_completed / data.steps_total * 100) if data.steps_total > 0 else 0
        }
        
        severity = ReportSeverity.ERROR if data.status == MigrationStatus.FAILED else ReportSeverity.INFO
        
        return ReportSection(
            title="Migration Overview",
            content=content,
            severity=severity
        )
    
    def _create_steps_summary_section(self, steps: List[MigrationStep]) -> ReportSection:
        """Create steps summary section."""
        step_summary = []
        for step in steps:
            step_summary.append({
                "id": step.id,
                "name": step.name,
                "status": step.status.value,
                "duration": self._format_duration(step.duration),
                "error": step.error.__dict__ if step.error else None
            })
        
        content = {
            "steps": step_summary,
            "total_steps": len(steps),
            "completed_steps": len([s for s in steps if s.status == StepStatus.COMPLETED]),
            "failed_steps": len([s for s in steps if s.status == StepStatus.FAILED])
        }
        
        return ReportSection(
            title="Steps Summary",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _create_performance_section(self, performance_data: Dict[str, Any]) -> ReportSection:
        """Create performance section."""
        content = {
            "transfer_summary": self._summarize_transfer_performance(
                performance_data.get("transfer_metrics", {})
            ),
            "database_summary": self._summarize_database_performance(
                performance_data.get("database_metrics", {})
            ),
            "resource_usage": performance_data.get("resource_usage", {})
        }
        
        return ReportSection(
            title="Performance Summary",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _save_report(
        self,
        content: Dict[str, Any],
        filename: str,
        format: ReportFormat
    ) -> Path:
        """Save report to file in specified format."""
        file_path = self.output_directory / f"{filename}.{format.value}"
        
        if format == ReportFormat.JSON:
            with open(file_path, 'w') as f:
                json.dump(content, f, indent=2, default=str)
        
        elif format == ReportFormat.HTML:
            html_content = self._render_html_report(content)
            with open(file_path, 'w') as f:
                f.write(html_content)
        
        elif format == ReportFormat.MARKDOWN:
            md_content = self._render_markdown_report(content)
            with open(file_path, 'w') as f:
                f.write(md_content)
        
        elif format == ReportFormat.TEXT:
            text_content = self._render_text_report(content)
            with open(file_path, 'w') as f:
                f.write(text_content)
        
        else:
            # Default to JSON for unsupported formats
            with open(file_path, 'w') as f:
                json.dump(content, f, indent=2, default=str)
        
        return file_path
    
    def _render_html_report(self, content: Dict[str, Any]) -> str:
        """Render report as HTML."""
        try:
            template = self.template_env.get_template(f"{content['report_type']}.html")
            return template.render(**content)
        except Exception:
            # Fallback to basic HTML template
            return self._render_basic_html_report(content)
    
    def _render_basic_html_report(self, content: Dict[str, Any]) -> str:
        """Render basic HTML report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{content.get('report_type', 'Report').title()} Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .error {{ background-color: #ffe6e6; }}
                .warning {{ background-color: #fff3cd; }}
                .info {{ background-color: #e6f3ff; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{content.get('report_type', 'Report').title()} Report</h1>
                <p><strong>Generated:</strong> {content.get('timestamp', 'Unknown')}</p>
                <p><strong>Session ID:</strong> {content.get('session_id', 'Unknown')}</p>
            </div>
        """
        
        # Add sections
        for section_data in content.get('sections', []):
            severity_class = section_data.get('severity', 'info')
            html += f"""
            <div class="section {severity_class}">
                <h2>{section_data.get('title', 'Section')}</h2>
                <pre>{json.dumps(section_data.get('content', {}), indent=2, default=str)}</pre>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _render_markdown_report(self, content: Dict[str, Any]) -> str:
        """Render report as Markdown."""
        md = f"# {content.get('report_type', 'Report').title()} Report\n\n"
        md += f"**Generated:** {content.get('timestamp', 'Unknown')}\n"
        md += f"**Session ID:** {content.get('session_id', 'Unknown')}\n\n"
        
        for section_data in content.get('sections', []):
            md += f"## {section_data.get('title', 'Section')}\n\n"
            md += f"```json\n{json.dumps(section_data.get('content', {}), indent=2, default=str)}\n```\n\n"
        
        return md
    
    def _render_text_report(self, content: Dict[str, Any]) -> str:
        """Render report as plain text."""
        text = f"{content.get('report_type', 'Report').upper()} REPORT\n"
        text += "=" * 50 + "\n\n"
        text += f"Generated: {content.get('timestamp', 'Unknown')}\n"
        text += f"Session ID: {content.get('session_id', 'Unknown')}\n\n"
        
        for section_data in content.get('sections', []):
            text += f"{section_data.get('title', 'Section').upper()}\n"
            text += "-" * 30 + "\n"
            text += json.dumps(section_data.get('content', {}), indent=2, default=str)
            text += "\n\n"
        
        return text
    
    def _format_duration(self, seconds: Optional[float]) -> str:
        """Format duration in human-readable format."""
        if seconds is None:
            return "Unknown"
        
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
    
    def _generate_recovery_options(
        self,
        session: MigrationSession,
        error: ErrorInfo
    ) -> List[str]:
        """Generate recovery options based on error and session state."""
        options = []
        
        if session.backups:
            options.append("Restore from backup and retry migration")
        
        if error.retry_possible:
            options.append("Retry the failed operation")
        
        options.extend([
            "Review error details and fix configuration",
            "Contact support for assistance",
            "Perform manual migration steps"
        ])
        
        return options
    
    def _generate_support_info(
        self,
        session: MigrationSession,
        error: ErrorInfo
    ) -> Dict[str, Any]:
        """Generate support information."""
        return {
            "error_code": error.code,
            "session_id": session.id,
            "migration_type": f"{session.config.source.type.value} -> {session.config.destination.type.value}",
            "documentation_links": error.documentation_links,
            "support_contact": "support@migration-assistant.com"
        }
    
    def _summarize_transfer_performance(self, transfer_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize transfer performance metrics."""
        if not transfer_metrics:
            return {}
        
        total_files = sum(m.get("files_transferred", 0) for m in transfer_metrics.values())
        total_bytes = sum(m.get("bytes_transferred", 0) for m in transfer_metrics.values())
        avg_rate = sum(m.get("average_rate_mbps", 0) for m in transfer_metrics.values()) / len(transfer_metrics)
        
        return {
            "total_files_transferred": total_files,
            "total_data_transferred_mb": total_bytes / (1024 * 1024),
            "average_transfer_rate_mbps": avg_rate,
            "transfer_operations": len(transfer_metrics)
        }
    
    def _summarize_database_performance(self, database_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize database performance metrics."""
        if not database_metrics:
            return {}
        
        total_records = sum(m.get("records_processed", 0) for m in database_metrics.values())
        avg_rate = sum(m.get("average_rate_rps", 0) for m in database_metrics.values()) / len(database_metrics)
        
        return {
            "total_records_processed": total_records,
            "average_processing_rate_rps": avg_rate,
            "database_operations": len(database_metrics)
        }
    
    def _extract_performance_summary(self, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance summary for report metadata."""
        summary = {}
        
        if "transfer_metrics" in performance_data:
            transfer_summary = self._summarize_transfer_performance(
                performance_data["transfer_metrics"]
            )
            summary.update(transfer_summary)
        
        if "database_metrics" in performance_data:
            db_summary = self._summarize_database_performance(
                performance_data["database_metrics"]
            )
            summary.update(db_summary)
        
        if "resource_usage" in performance_data:
            resource_usage = performance_data["resource_usage"]
            summary.update({
                "peak_cpu_percent": resource_usage.get("cpu_percent", 0),
                "peak_memory_percent": resource_usage.get("memory_percent", 0)
            })
        
        return summary
    
    def _create_performance_overview_section(self, performance_data: Dict[str, Any]) -> ReportSection:
        """Create performance overview section."""
        content = {
            "summary": self._extract_performance_summary(performance_data),
            "data_points_collected": len(performance_data.get("metrics_history", [])),
            "monitoring_duration": "N/A"  # Would need start/end times
        }
        
        return ReportSection(
            title="Performance Overview",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _create_transfer_performance_section(self, transfer_metrics: Dict[str, Any]) -> ReportSection:
        """Create transfer performance section."""
        content = {
            "transfer_operations": transfer_metrics,
            "summary": self._summarize_transfer_performance(transfer_metrics)
        }
        
        return ReportSection(
            title="Transfer Performance",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _create_database_performance_section(self, database_metrics: Dict[str, Any]) -> ReportSection:
        """Create database performance section."""
        content = {
            "database_operations": database_metrics,
            "summary": self._summarize_database_performance(database_metrics)
        }
        
        return ReportSection(
            title="Database Performance",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _create_resource_usage_section(self, resource_usage: Dict[str, Any]) -> ReportSection:
        """Create resource usage section."""
        content = {
            "current_usage": resource_usage,
            "recommendations": self._generate_resource_recommendations(resource_usage)
        }
        
        return ReportSection(
            title="Resource Usage",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _generate_resource_recommendations(self, resource_usage: Dict[str, Any]) -> List[str]:
        """Generate resource usage recommendations."""
        recommendations = []
        
        cpu_percent = resource_usage.get("cpu_percent", 0)
        memory_percent = resource_usage.get("memory_percent", 0)
        
        if cpu_percent > 80:
            recommendations.append("Consider reducing concurrent operations to lower CPU usage")
        
        if memory_percent > 80:
            recommendations.append("Monitor memory usage and consider increasing available RAM")
        
        if not recommendations:
            recommendations.append("Resource usage is within normal limits")
        
        return recommendations
    
    def _create_backup_section(self, backups: List[Any]) -> ReportSection:
        """Create backup information section."""
        backup_summary = []
        for backup in backups:
            backup_summary.append({
                "id": backup.id,
                "type": backup.type.value,
                "size_mb": (backup.size / (1024 * 1024)) if backup.size else 0,
                "created_at": backup.created_at.isoformat(),
                "verified": backup.verified
            })
        
        content = {
            "backups": backup_summary,
            "total_backups": len(backups),
            "total_size_mb": sum(b.get("size_mb", 0) for b in backup_summary),
            "verified_backups": len([b for b in backup_summary if b["verified"]])
        }
        
        return ReportSection(
            title="Backup Information",
            content=content,
            severity=ReportSeverity.INFO
        )
    
    def _create_issues_section(self, logs: List[Any]) -> ReportSection:
        """Create issues section from logs."""
        errors = [log for log in logs if log.level == LogLevel.ERROR]
        warnings = [log for log in logs if log.level == LogLevel.WARNING]
        
        content = {
            "errors": [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "message": log.message,
                    "component": log.component,
                    "step_id": log.step_id
                }
                for log in errors
            ],
            "warnings": [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "message": log.message,
                    "component": log.component,
                    "step_id": log.step_id
                }
                for log in warnings
            ],
            "total_errors": len(errors),
            "total_warnings": len(warnings)
        }
        
        severity = ReportSeverity.ERROR if errors else ReportSeverity.WARNING
        
        return ReportSection(
            title="Issues and Warnings",
            content=content,
            severity=severity
        )
    
    def _create_error_summary_section(self, error_data: ErrorReportData) -> ReportSection:
        """Create error summary section."""
        content = {
            "error_code": error_data.error_summary.code,
            "error_message": error_data.error_summary.message,
            "severity": error_data.error_summary.severity.value,
            "component": error_data.error_summary.component,
            "affected_steps": error_data.affected_steps,
            "rollback_performed": error_data.rollback_performed,
            "timestamp": error_data.timestamp.isoformat()
        }
        
        return ReportSection(
            title="Error Summary",
            content=content,
            severity=ReportSeverity.CRITICAL
        )
    
    def _create_error_timeline_section(self, error_timeline: List[Dict[str, Any]]) -> ReportSection:
        """Create error timeline section."""
        content = {
            "timeline": error_timeline,
            "total_events": len(error_timeline)
        }
        
        return ReportSection(
            title="Error Timeline",
            content=content,
            severity=ReportSeverity.ERROR
        )
    
    def _create_recovery_section(self, recovery_options: List[str]) -> ReportSection:
        """Create recovery options section."""
        content = {
            "recovery_options": recovery_options,
            "recommended_action": recovery_options[0] if recovery_options else "Contact support"
        }
        
        return ReportSection(
            title="Recovery Options",
            content=content,
            severity=ReportSeverity.WARNING
        )
    
    def _create_logs_section(self, logs: List[Any]) -> ReportSection:
        """Create detailed logs section."""
        log_entries = []
        for log in logs[-100:]:  # Last 100 log entries
            log_entries.append({
                "timestamp": log.timestamp.isoformat(),
                "level": log.level.value,
                "message": log.message,
                "component": log.component,
                "step_id": log.step_id
            })
        
        content = {
            "log_entries": log_entries,
            "total_logs": len(logs),
            "showing_recent": len(log_entries)
        }
        
        return ReportSection(
            title="Detailed Logs",
            content=content,
            severity=ReportSeverity.INFO
        )