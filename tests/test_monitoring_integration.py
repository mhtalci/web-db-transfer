"""
Integration tests for monitoring and reporting components.

Tests the integration between ProgressTracker, PerformanceMonitor,
and ReportGenerator components.
"""

import asyncio
import pytest
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock

from migration_assistant.monitoring.progress_tracker import (
    ProgressTracker, SessionProgressTracker, ProgressUnit
)
from migration_assistant.monitoring.performance_monitor import PerformanceMonitor
from migration_assistant.monitoring.report_generator import ReportGenerator, ReportFormat
from migration_assistant.models.session import (
    MigrationSession, MigrationStep, MigrationStatus, StepStatus,
    ValidationResult, ErrorInfo, ErrorSeverity
)
from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, SystemType, AuthConfig, AuthType,
    PathConfig, TransferConfig, TransferMethod, MigrationOptions
)


class TestMonitoringIntegration:
    """Integration tests for monitoring components."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test reports."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def progress_tracker(self):
        """Create ProgressTracker instance."""
        return ProgressTracker()
    
    @pytest.fixture
    def performance_monitor(self):
        """Create PerformanceMonitor instance."""
        return PerformanceMonitor(collection_interval=0.1)
    
    @pytest.fixture
    def report_generator(self, temp_dir):
        """Create ReportGenerator instance."""
        return ReportGenerator(output_directory=temp_dir)
    
    @pytest.fixture
    def sample_session(self):
        """Create sample migration session."""
        config = MigrationConfig(
            name="Integration Test Migration",
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
        
        session = MigrationSession(
            id="integration-test-session",
            config=config,
            status=MigrationStatus.RUNNING
        )
        
        # Add steps
        steps = [
            MigrationStep(id="validate", name="Validate Configuration"),
            MigrationStep(id="transfer", name="Transfer Files"),
            MigrationStep(id="verify", name="Verify Migration")
        ]
        
        for step in steps:
            session.add_step(step)
        
        return session
    
    def test_progress_tracking_integration(self, progress_tracker, sample_session):
        """Test progress tracking integration with session."""
        session_tracker = SessionProgressTracker(progress_tracker)
        
        # Track session
        session_tracker.track_session(sample_session)
        
        # Simulate step progress
        for i, step in enumerate(sample_session.steps):
            # Start step tracking
            session_tracker.track_step(sample_session, step, total=100, unit=ProgressUnit.FILES)
            
            # Simulate step progress
            for progress in [25, 50, 75, 100]:
                progress_tracker.update_progress(
                    sample_session.id,
                    current=progress,
                    step_id=step.id,
                    message=f"Processing {progress}% of files"
                )
            
            # Complete step
            progress_tracker.complete_tracking(sample_session.id, step_id=step.id)
            step.status = StepStatus.COMPLETED
            
            # Update session progress
            session_tracker.update_session_progress(sample_session)
        
        # Complete session
        session_tracker.complete_session(sample_session)
        
        # Verify final session metrics
        session_metrics = progress_tracker.get_progress_metrics(sample_session.id)
        assert session_metrics is None  # Should be cleaned up after completion
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, performance_monitor, sample_session):
        """Test performance monitoring integration."""
        # Start monitoring
        await performance_monitor.start_monitoring(sample_session.id)
        
        # Start transfer tracking
        performance_monitor.start_transfer_tracking(
            sample_session.id,
            step_id="transfer",
            total_bytes=1024 * 1024 * 10,  # 10MB
            total_files=100
        )
        
        # Simulate transfer progress
        for i in range(1, 6):
            bytes_transferred = i * 1024 * 1024 * 2  # 2MB increments
            files_transferred = i * 20  # 20 files increments
            
            performance_monitor.update_transfer_progress(
                sample_session.id,
                bytes_transferred=bytes_transferred,
                files_transferred=files_transferred,
                step_id="transfer"
            )
            
            await asyncio.sleep(0.1)  # Small delay
        
        # Get transfer metrics
        transfer_metrics = performance_monitor.get_transfer_metrics(sample_session.id, "transfer")
        assert transfer_metrics is not None
        assert transfer_metrics.bytes_transferred == 10 * 1024 * 1024  # 10MB
        assert transfer_metrics.files_transferred == 100
        assert transfer_metrics.average_rate_mbps > 0
        
        # Stop monitoring
        await performance_monitor.stop_monitoring()
        
        # Get performance summary
        summary = performance_monitor.get_performance_summary(sample_session.id)
        assert "transfer_metrics" in summary
        assert "resource_usage" in summary
    
    def test_report_generation_integration(
        self, 
        report_generator, 
        sample_session, 
        progress_tracker,
        performance_monitor
    ):
        """Test report generation with real data."""
        # Create validation result
        validation_result = ValidationResult(
            passed=True,
            checks_performed=5,
            checks_passed=5,
            checks_failed=0,
            warnings=1,
            errors=[],
            warnings_list=["Minor configuration issue"],
            recommendations=["Update SSL certificate"],
            estimated_duration=300,
            details={"connectivity": "passed", "permissions": "passed"}
        )
        
        # Generate validation report
        validation_report = report_generator.generate_validation_report(
            session=sample_session,
            validation_result=validation_result,
            format=ReportFormat.JSON
        )
        
        assert validation_report is not None
        assert validation_report.summary["overall_result"] is True
        assert validation_report.summary["checks_performed"] == 5
        
        # Create performance data
        performance_data = {
            "transfer_metrics": {
                "transfer": {
                    "files_transferred": 100,
                    "bytes_transferred": 1024 * 1024 * 10,  # 10MB
                    "average_rate_mbps": 5.0,
                    "peak_rate_mbps": 8.0,
                    "efficiency_percent": 75.0,
                    "errors_count": 0
                }
            },
            "resource_usage": {
                "cpu_percent": 45.0,
                "memory_percent": 60.0,
                "disk_read_mb_per_sec": 10.0,
                "disk_write_mb_per_sec": 8.0
            }
        }
        
        # Complete session for summary report
        sample_session.status = MigrationStatus.COMPLETED
        for step in sample_session.steps:
            step.status = StepStatus.COMPLETED
        
        # Generate migration summary report
        summary_report = report_generator.generate_migration_summary_report(
            session=sample_session,
            performance_data=performance_data,
            format=ReportFormat.HTML
        )
        
        assert summary_report is not None
        assert summary_report.summary["status"] == "completed"
        assert summary_report.summary["steps_completed"] == 3
        
        # Generate performance report
        performance_report = report_generator.generate_performance_report(
            session_id=sample_session.id,
            performance_data=performance_data,
            format=ReportFormat.JSON
        )
        
        assert performance_report is not None
        assert "total_files_transferred" in performance_report.summary
        assert performance_report.summary["total_files_transferred"] == 100
        
        # List all reports
        all_reports = report_generator.list_reports()
        assert len(all_reports) == 3  # validation, summary, performance
        
        # Verify report files exist
        for report in all_reports:
            from pathlib import Path
            assert Path(report.location).exists()
    
    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(
        self,
        progress_tracker,
        performance_monitor,
        report_generator,
        sample_session
    ):
        """Test complete monitoring workflow."""
        # Start all monitoring
        session_tracker = SessionProgressTracker(progress_tracker)
        session_tracker.track_session(sample_session)
        
        await performance_monitor.start_monitoring(sample_session.id)
        
        # Simulate migration workflow
        for i, step in enumerate(sample_session.steps):
            step.start()
            
            # Track step progress
            session_tracker.track_step(sample_session, step, total=50, unit=ProgressUnit.OPERATIONS)
            
            # Start performance tracking for this step
            if step.id == "transfer":
                performance_monitor.start_transfer_tracking(
                    sample_session.id,
                    step_id=step.id,
                    total_bytes=1024 * 1024 * 5,  # 5MB
                    total_files=50
                )
            
            # Simulate step execution
            for progress in range(10, 51, 10):
                progress_tracker.update_progress(
                    sample_session.id,
                    current=progress,
                    step_id=step.id
                )
                
                if step.id == "transfer":
                    performance_monitor.update_transfer_progress(
                        sample_session.id,
                        bytes_transferred=progress * 1024 * 100,  # Scale bytes
                        files_transferred=progress,
                        step_id=step.id
                    )
                
                await asyncio.sleep(0.05)  # Small delay
            
            # Complete step
            progress_tracker.complete_tracking(sample_session.id, step_id=step.id)
            step.complete()
            session_tracker.update_session_progress(sample_session)
        
        # Complete session
        sample_session.complete()
        session_tracker.complete_session(sample_session)
        await performance_monitor.stop_monitoring()
        
        # Generate comprehensive report
        performance_data = performance_monitor.get_performance_summary(sample_session.id)
        
        final_report = report_generator.generate_migration_summary_report(
            session=sample_session,
            performance_data=performance_data,
            format=ReportFormat.HTML
        )
        
        # Verify final report
        assert final_report is not None
        assert final_report.summary["status"] == "completed"
        assert final_report.summary["steps_completed"] == 3
        assert final_report.summary["errors_count"] == 0
        
        # Verify performance data was included
        from pathlib import Path
        import json
        
        # Read the generated report file to verify content
        report_path = Path(final_report.location)
        assert report_path.exists()
        assert report_path.stat().st_size > 0
    
    def test_error_reporting_integration(self, report_generator, sample_session):
        """Test error reporting integration."""
        # Simulate failed migration
        sample_session.status = MigrationStatus.FAILED
        
        # Create error
        error = ErrorInfo(
            code="INTEGRATION_TEST_ERROR",
            message="Integration test error for reporting",
            severity=ErrorSeverity.HIGH,
            component="TestComponent",
            remediation_steps=["Check test configuration", "Retry operation"],
            rollback_required=True
        )
        
        sample_session.fail(error)
        
        # Generate error report
        error_report = report_generator.generate_error_report(
            session=sample_session,
            primary_error=error,
            format=ReportFormat.JSON
        )
        
        assert error_report is not None
        assert error_report.summary["error_code"] == "INTEGRATION_TEST_ERROR"
        assert error_report.summary["severity"] == "high"
        
        # Verify error report file
        from pathlib import Path
        report_path = Path(error_report.location)
        assert report_path.exists()
        
        # Read and verify JSON content
        with open(report_path) as f:
            report_data = json.loads(f.read())
        
        assert report_data["report_type"] == "error_diagnostic"
        assert report_data["session_id"] == sample_session.id
        assert "error_data" in report_data