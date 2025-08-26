"""
Unit tests for report generation functionality.

Tests the ReportGenerator class for creating migration summaries,
error reports, validation reports, and performance analysis.
"""

import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.monitoring.report_generator import (
    ReportGenerator, ReportFormat, ReportSeverity, ReportSection,
    ValidationReportData, MigrationSummaryData, ErrorReportData
)
from migration_assistant.models.session import (
    MigrationSession, MigrationStep, MigrationStatus, StepStatus,
    LogLevel, LogEntry, ErrorInfo, ErrorSeverity, ValidationResult,
    BackupInfo, BackupType, ReportType
)
from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, SystemType
)


class TestReportGenerator:
    """Test cases for ReportGenerator class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test reports."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def report_generator(self, temp_dir):
        """Create ReportGenerator instance for testing."""
        return ReportGenerator(output_directory=temp_dir)
    
    @pytest.fixture
    def sample_config(self):
        """Create sample migration configuration."""
        from migration_assistant.models.config import (
            AuthConfig, AuthType, PathConfig, TransferConfig, 
            TransferMethod, MigrationOptions
        )
        
        return MigrationConfig(
            name="Test Migration",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.example.com",
                authentication=AuthConfig(type=AuthType.PASSWORD, username="user", password="pass"),
                paths=PathConfig(root_path="/var/www/html")
            ),
            destination=SystemConfig(
                type=SystemType.STATIC_SITE,
                host="dest.example.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="user", ssh_key_path="/path/to/key"),
                paths=PathConfig(root_path="/var/www/static")
            ),
            transfer=TransferConfig(method=TransferMethod.SSH_SCP),
            options=MigrationOptions()
        )
    
    @pytest.fixture
    def sample_session(self, sample_config):
        """Create sample migration session."""
        session = MigrationSession(
            id="test-session-123",
            config=sample_config,
            status=MigrationStatus.COMPLETED,
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow(),
            duration=3600.0
        )
        
        # Add steps
        steps = [
            MigrationStep(
                id="validate",
                name="Validate Configuration",
                status=StepStatus.COMPLETED,
                duration=120.0
            ),
            MigrationStep(
                id="backup",
                name="Create Backup",
                status=StepStatus.COMPLETED,
                duration=300.0
            ),
            MigrationStep(
                id="transfer",
                name="Transfer Files",
                status=StepStatus.COMPLETED,
                duration=2400.0
            )
        ]
        
        for step in steps:
            session.add_step(step)
        
        # Add logs
        session.add_log(LogLevel.INFO, "Migration started")
        session.add_log(LogLevel.WARNING, "Large file detected", component="FileTransfer")
        session.add_log(LogLevel.INFO, "Migration completed successfully")
        
        # Add backup
        backup = BackupInfo(
            id="backup-123",
            type=BackupType.FULL,
            source_system="wordpress",
            location="/backups/backup-123.tar.gz",
            size=1024 * 1024 * 100,  # 100MB
            verified=True
        )
        session.add_backup(backup)
        
        return session
    
    @pytest.fixture
    def sample_validation_result(self):
        """Create sample validation result."""
        errors = [
            ErrorInfo(
                code="CONN_001",
                message="Cannot connect to source database",
                severity=ErrorSeverity.CRITICAL,
                component="DatabaseValidator",
                remediation_steps=["Check database credentials", "Verify network connectivity"]
            )
        ]
        
        return ValidationResult(
            passed=False,
            checks_performed=10,
            checks_passed=8,
            checks_failed=2,
            warnings=1,
            errors=errors,
            warnings_list=["SSL certificate will expire soon"],
            recommendations=["Update database credentials", "Renew SSL certificate"],
            estimated_duration=1800,  # 30 minutes
            details={"connectivity": "failed", "permissions": "passed"}
        )
    
    def test_generate_validation_report_json(self, report_generator, sample_session, sample_validation_result):
        """Test generating validation report in JSON format."""
        report_info = report_generator.generate_validation_report(
            session=sample_session,
            validation_result=sample_validation_result,
            format=ReportFormat.JSON
        )
        
        # Verify report info
        assert report_info.type == ReportType.VALIDATION
        assert report_info.format == "json"
        assert "Validation Report" in report_info.title
        assert report_info.location is not None
        assert report_info.size > 0
        
        # Verify summary
        assert report_info.summary["overall_result"] is False
        assert report_info.summary["checks_performed"] == 10
        assert report_info.summary["checks_failed"] == 2
        assert report_info.summary["warnings"] == 1
        
        # Verify file was created
        report_path = Path(report_info.location)
        assert report_path.exists()
        
        # Verify file content
        with open(report_path) as f:
            report_data = json.load(f)
        
        assert report_data["report_type"] == "validation"
        assert report_data["session_id"] == sample_session.id
        assert "validation_data" in report_data
        assert "sections" in report_data
    
    def test_generate_validation_report_html(self, report_generator, sample_session, sample_validation_result):
        """Test generating validation report in HTML format."""
        report_info = report_generator.generate_validation_report(
            session=sample_session,
            validation_result=sample_validation_result,
            format=ReportFormat.HTML
        )
        
        # Verify report info
        assert report_info.format == "html"
        
        # Verify file was created
        report_path = Path(report_info.location)
        assert report_path.exists()
        
        # Verify HTML content
        with open(report_path) as f:
            html_content = f.read()
        
        assert "<!DOCTYPE html>" in html_content
        assert "Validation Report" in html_content
        assert sample_session.id in html_content
    
    def test_generate_migration_summary_report(self, report_generator, sample_session):
        """Test generating migration summary report."""
        performance_data = {
            "transfer_metrics": {
                "files": {
                    "files_transferred": 150,
                    "bytes_transferred": 1024 * 1024 * 50,  # 50MB
                    "average_rate_mbps": 10.5
                }
            },
            "database_metrics": {
                "migration": {
                    "records_processed": 5000,
                    "average_rate_rps": 100.0
                }
            },
            "resource_usage": {
                "cpu_percent": 45.2,
                "memory_percent": 62.8
            }
        }
        
        report_info = report_generator.generate_migration_summary_report(
            session=sample_session,
            performance_data=performance_data,
            format=ReportFormat.JSON
        )
        
        # Verify report info
        assert report_info.type == ReportType.SUMMARY
        assert report_info.format == "json"
        assert "Migration Summary" in report_info.title
        
        # Verify summary
        assert report_info.summary["status"] == "completed"
        assert report_info.summary["steps_completed"] == 3
        assert report_info.summary["steps_total"] == 3
        assert report_info.summary["errors_count"] == 0
        
        # Verify file content
        report_path = Path(report_info.location)
        with open(report_path) as f:
            report_data = json.load(f)
        
        assert report_data["report_type"] == "migration_summary"
        assert "summary_data" in report_data
        
        # Verify performance data was included
        summary_data = report_data["summary_data"]
        assert summary_data["files_transferred"] == 150
        assert summary_data["data_transferred_mb"] == 50.0
    
    def test_generate_error_report(self, report_generator, sample_session):
        """Test generating error diagnostic report."""
        # Create failed session
        sample_session.status = MigrationStatus.FAILED
        sample_session.steps[2].status = StepStatus.FAILED
        
        primary_error = ErrorInfo(
            code="TRANSFER_001",
            message="File transfer failed due to network timeout",
            severity=ErrorSeverity.CRITICAL,
            component="FileTransfer",
            step_id="transfer",
            remediation_steps=[
                "Check network connectivity",
                "Increase timeout settings",
                "Retry the transfer"
            ],
            rollback_required=True
        )
        
        sample_session.steps[2].error = primary_error
        sample_session.add_log(LogLevel.ERROR, "Transfer failed", component="FileTransfer", step_id="transfer")
        
        report_info = report_generator.generate_error_report(
            session=sample_session,
            primary_error=primary_error,
            format=ReportFormat.HTML
        )
        
        # Verify report info
        assert report_info.type == ReportType.ERROR
        assert report_info.format == "html"
        assert "Error Report" in report_info.title
        
        # Verify summary
        assert report_info.summary["error_code"] == "TRANSFER_001"
        assert report_info.summary["severity"] == "critical"
        assert report_info.summary["affected_steps"] == 1
        
        # Verify file was created
        report_path = Path(report_info.location)
        assert report_path.exists()
    
    def test_generate_performance_report(self, report_generator):
        """Test generating performance analysis report."""
        performance_data = {
            "session_id": "perf-test-123",
            "transfer_metrics": {
                "operation_1": {
                    "files_transferred": 100,
                    "bytes_transferred": 1024 * 1024 * 25,  # 25MB
                    "average_rate_mbps": 8.5,
                    "peak_rate_mbps": 12.0,
                    "efficiency_percent": 85.0
                }
            },
            "database_metrics": {
                "migration_1": {
                    "records_processed": 10000,
                    "average_rate_rps": 150.0,
                    "query_time_avg_ms": 25.5
                }
            },
            "resource_usage": {
                "cpu_percent": 55.0,
                "memory_percent": 70.0,
                "disk_read_mb_per_sec": 15.2,
                "disk_write_mb_per_sec": 8.7
            }
        }
        
        report_info = report_generator.generate_performance_report(
            session_id="perf-test-123",
            performance_data=performance_data,
            format=ReportFormat.JSON
        )
        
        # Verify report info
        assert report_info.type == ReportType.PERFORMANCE
        assert report_info.format == "json"
        assert "Performance Report" in report_info.title
        
        # Verify file was created
        report_path = Path(report_info.location)
        assert report_path.exists()
        
        # Verify content
        with open(report_path) as f:
            report_data = json.load(f)
        
        assert report_data["report_type"] == "performance"
        assert report_data["session_id"] == "perf-test-123"
        assert "performance_data" in report_data
    
    def test_report_formats(self, report_generator, sample_session, sample_validation_result):
        """Test different report formats."""
        formats_to_test = [
            ReportFormat.JSON,
            ReportFormat.HTML,
            ReportFormat.MARKDOWN,
            ReportFormat.TEXT
        ]
        
        for format_type in formats_to_test:
            report_info = report_generator.generate_validation_report(
                session=sample_session,
                validation_result=sample_validation_result,
                format=format_type
            )
            
            # Verify file was created with correct extension
            report_path = Path(report_info.location)
            assert report_path.exists()
            assert report_path.suffix == f".{format_type.value}"
            
            # Verify file has content
            assert report_path.stat().st_size > 0
    
    def test_get_report(self, report_generator, sample_session, sample_validation_result):
        """Test retrieving generated report."""
        report_info = report_generator.generate_validation_report(
            session=sample_session,
            validation_result=sample_validation_result
        )
        
        # Retrieve report
        retrieved_report = report_generator.get_report(report_info.id)
        
        assert retrieved_report is not None
        assert retrieved_report.id == report_info.id
        assert retrieved_report.type == report_info.type
        assert retrieved_report.location == report_info.location
    
    def test_list_reports(self, report_generator, sample_session, sample_validation_result):
        """Test listing generated reports."""
        # Generate multiple reports
        validation_report = report_generator.generate_validation_report(
            session=sample_session,
            validation_result=sample_validation_result
        )
        
        summary_report = report_generator.generate_migration_summary_report(
            session=sample_session
        )
        
        # List all reports
        all_reports = report_generator.list_reports()
        assert len(all_reports) == 2
        
        # List validation reports only
        validation_reports = report_generator.list_reports(report_type=ReportType.VALIDATION)
        assert len(validation_reports) == 1
        assert validation_reports[0].id == validation_report.id
        
        # List summary reports only
        summary_reports = report_generator.list_reports(report_type=ReportType.SUMMARY)
        assert len(summary_reports) == 1
        assert summary_reports[0].id == summary_report.id
    
    def test_cleanup_old_reports(self, report_generator, sample_session, sample_validation_result):
        """Test cleaning up old reports."""
        # Generate a report
        report_info = report_generator.generate_validation_report(
            session=sample_session,
            validation_result=sample_validation_result
        )
        
        # Verify report exists
        report_path = Path(report_info.location)
        assert report_path.exists()
        assert report_generator.get_report(report_info.id) is not None
        
        # Mock the report as old by modifying its timestamp
        old_timestamp = datetime.utcnow() - timedelta(days=35)
        report_generator._generated_reports[report_info.id].generated_at = old_timestamp
        
        # Clean up old reports (older than 30 days)
        report_generator.cleanup_old_reports(days=30)
        
        # Verify report was cleaned up
        assert not report_path.exists()
        assert report_generator.get_report(report_info.id) is None
    
    def test_report_sections(self, report_generator):
        """Test report section creation."""
        # Test validation summary section
        validation_data = ValidationReportData(
            session_id="test",
            timestamp=datetime.utcnow(),
            overall_result=False,
            checks_performed=10,
            checks_passed=7,
            checks_failed=3,
            warnings_count=2,
            errors=[],
            warnings=[],
            recommendations=[],
            estimated_fix_time="15 minutes",
            details={}
        )
        
        section = report_generator._create_validation_summary_section(validation_data)
        
        assert isinstance(section, ReportSection)
        assert section.title == "Validation Summary"
        assert section.severity == ReportSeverity.ERROR  # Because overall_result is False
        assert section.content["overall_result"] is False
        assert section.content["checks_performed"] == 10
        assert section.content["success_rate"] == 70.0  # 7/10 * 100
    
    def test_duration_formatting(self, report_generator):
        """Test duration formatting utility."""
        # Test seconds
        assert report_generator._format_duration(30.5) == "30.5 seconds"
        
        # Test minutes
        assert report_generator._format_duration(120.0) == "2.0 minutes"
        
        # Test hours
        assert report_generator._format_duration(7200.0) == "2.0 hours"
        
        # Test None
        assert report_generator._format_duration(None) == "Unknown"
    
    def test_error_handling_in_html_rendering(self, report_generator, temp_dir):
        """Test error handling when HTML templates are missing."""
        # Create report generator with non-existent template directory
        generator = ReportGenerator(
            output_directory=temp_dir,
            template_directory="/non/existent/path"
        )
        
        content = {
            "report_type": "test",
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": "test-123",
            "sections": []
        }
        
        # Should fall back to basic HTML rendering
        html_content = generator._render_html_report(content)
        
        assert "<!DOCTYPE html>" in html_content
        assert "Test Report" in html_content
        assert "test-123" in html_content
    
    def test_performance_summary_extraction(self, report_generator):
        """Test performance summary extraction."""
        performance_data = {
            "transfer_metrics": {
                "op1": {
                    "files_transferred": 50,
                    "bytes_transferred": 1024 * 1024 * 10,  # 10MB
                    "average_rate_mbps": 5.0
                },
                "op2": {
                    "files_transferred": 30,
                    "bytes_transferred": 1024 * 1024 * 5,   # 5MB
                    "average_rate_mbps": 3.0
                }
            },
            "database_metrics": {
                "db1": {
                    "records_processed": 1000,
                    "average_rate_rps": 50.0
                }
            },
            "resource_usage": {
                "cpu_percent": 75.0,
                "memory_percent": 60.0
            }
        }
        
        summary = report_generator._extract_performance_summary(performance_data)
        
        assert summary["total_files_transferred"] == 80  # 50 + 30
        assert summary["total_data_transferred_mb"] == 15.0  # 10 + 5
        assert summary["total_records_processed"] == 1000
        assert summary["peak_cpu_percent"] == 75.0
        assert summary["peak_memory_percent"] == 60.0


class TestReportSections:
    """Test cases for report section creation."""
    
    @pytest.fixture
    def report_generator(self):
        """Create ReportGenerator instance."""
        return ReportGenerator()
    
    def test_error_analysis_section(self, report_generator):
        """Test error analysis section creation."""
        errors = [
            ErrorInfo(
                code="ERR_001",
                message="Critical error",
                severity=ErrorSeverity.CRITICAL,
                component="TestComponent"
            ),
            ErrorInfo(
                code="ERR_002",
                message="High priority error",
                severity=ErrorSeverity.HIGH,
                component="TestComponent"
            ),
            ErrorInfo(
                code="ERR_003",
                message="Medium priority error",
                severity=ErrorSeverity.MEDIUM,
                component="TestComponent"
            )
        ]
        
        section = report_generator._create_error_analysis_section(errors)
        
        assert section.title == "Error Analysis"
        assert section.severity == ReportSeverity.ERROR
        assert section.content["total_errors"] == 3
        assert section.content["critical_errors"] == 1
        assert section.content["high_errors"] == 1
        
        # Verify error grouping
        error_groups = section.content["error_groups"]
        assert "critical" in error_groups
        assert "high" in error_groups
        assert "medium" in error_groups
        assert len(error_groups["critical"]) == 1
        assert len(error_groups["high"]) == 1
        assert len(error_groups["medium"]) == 1
    
    def test_remediation_section(self, report_generator):
        """Test remediation section creation."""
        recommendations = [
            "Fix database connection",
            "Update SSL certificate",
            "Increase timeout values",
            "Check network connectivity",
            "Verify permissions"
        ]
        
        section = report_generator._create_remediation_section(recommendations)
        
        assert section.title == "Remediation Suggestions"
        assert section.severity == ReportSeverity.WARNING
        assert section.content["total_recommendations"] == 5
        assert len(section.content["priority_actions"]) == 3  # Top 3
        assert section.content["priority_actions"] == recommendations[:3]
    
    def test_steps_summary_section(self, report_generator):
        """Test steps summary section creation."""
        steps = [
            MigrationStep(
                id="step1",
                name="Validation",
                status=StepStatus.COMPLETED,
                duration=120.0
            ),
            MigrationStep(
                id="step2",
                name="Backup",
                status=StepStatus.COMPLETED,
                duration=300.0
            ),
            MigrationStep(
                id="step3",
                name="Transfer",
                status=StepStatus.FAILED,
                duration=180.0,
                error=ErrorInfo(
                    code="TRANSFER_FAIL",
                    message="Transfer failed",
                    severity=ErrorSeverity.HIGH,
                    component="FileTransfer"
                )
            )
        ]
        
        section = report_generator._create_steps_summary_section(steps)
        
        assert section.title == "Steps Summary"
        assert section.content["total_steps"] == 3
        assert section.content["completed_steps"] == 2
        assert section.content["failed_steps"] == 1
        
        # Verify step details
        step_details = section.content["steps"]
        assert len(step_details) == 3
        assert step_details[0]["status"] == "completed"
        assert step_details[2]["status"] == "failed"
        assert step_details[2]["error"] is not None