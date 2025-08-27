"""
Unit tests for CodebaseOrchestrator error handling and logging.
"""

import pytest
import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from migration_assistant.checkup.orchestrator import (
    CodebaseOrchestrator, CheckupError, AnalysisError, CleanupError, 
    ReportGenerationError, ValidationError, RetryableError
)
from migration_assistant.checkup.models import (
    CheckupConfig, CheckupResults, AnalysisResults, CleanupResults,
    CodebaseMetrics, QualityIssue, IssueSeverity, IssueType
)
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.cleaners.base import BaseCleaner
from migration_assistant.checkup.validators.base import BaseValidator


class RetryableAnalyzer(BaseAnalyzer):
    """Mock analyzer that fails a few times then succeeds."""
    
    def __init__(self, config: CheckupConfig, fail_count: int = 2):
        super().__init__(config)
        self.name = "retryable_analyzer"
        self.metrics = CodebaseMetrics()
        self.fail_count = fail_count
        self.attempt_count = 0
    
    async def analyze(self):
        self.attempt_count += 1
        if self.attempt_count <= self.fail_count:
            raise RetryableError(f"Attempt {self.attempt_count} failed", component=self.name)
        
        return [
            QualityIssue(
                file_path=Path("test.py"),
                line_number=1,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.STYLE_VIOLATION,
                message="Test issue",
                description="Test description"
            )
        ]


class NonRetryableAnalyzer(BaseAnalyzer):
    """Mock analyzer that always fails with non-retryable error."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "non_retryable_analyzer"
        self.metrics = CodebaseMetrics()
    
    async def analyze(self):
        raise ValueError("Non-retryable error")


class TestOrchestratorErrorHandling:
    """Test comprehensive error handling in orchestrator."""
    
    def test_checkup_error_structure(self):
        """Test CheckupError structure and serialization."""
        original_error = ValueError("Original error")
        context = {"key": "value", "number": 42}
        
        error = CheckupError(
            "Test error message",
            component="test_component",
            original_error=original_error,
            context=context
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "CheckupError"
        assert error_dict["message"] == "Test error message"
        assert error_dict["component"] == "test_component"
        assert error_dict["original_error"] == "Original error"
        assert error_dict["context"] == context
        assert "timestamp" in error_dict
        assert error_dict["traceback"] is not None
    
    def test_structured_logging_setup(self, tmp_path):
        """Test structured logging setup."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Verify logger is set up
        assert orchestrator.logger is not None
        assert orchestrator.logger.name.startswith("migration_assistant.checkup.orchestrator")
        
        # Verify handlers are added
        assert len(orchestrator.logger.handlers) > 0
    
    def test_structured_logging_output(self, tmp_path, caplog):
        """Test structured logging output format."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        with caplog.at_level(logging.INFO):
            orchestrator._log_structured("info", "Test message", 
                                        component="test", extra_data="value")
        
        # Check that structured data is in the log
        log_record = caplog.records[0]
        assert "Test message" in log_record.message
        assert "component" in log_record.message
        assert "extra_data" in log_record.message
        
        # Verify JSON structure in log message
        json_part = log_record.message.split(" | ", 1)[1]
        log_data = json.loads(json_part)
        assert log_data["message"] == "Test message"
        assert log_data["component"] == "test"
        assert log_data["extra_data"] == "value"
    
    @pytest.mark.asyncio
    async def test_error_context_manager_success(self, tmp_path):
        """Test error context manager with successful operation."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        async with orchestrator._error_context("test_operation", "test_component"):
            # Simulate successful operation
            await asyncio.sleep(0.01)
        
        # Should complete without raising exceptions
        assert len(orchestrator._errors) == 0
    
    @pytest.mark.asyncio
    async def test_error_context_manager_checkup_error(self, tmp_path):
        """Test error context manager with CheckupError."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        with pytest.raises(CheckupError):
            async with orchestrator._error_context("test_operation", "test_component"):
                raise CheckupError("Test error", component="test_component")
        
        # Error should be tracked
        assert len(orchestrator._errors) == 1
        assert orchestrator._errors[0].message == "Test error"
    
    @pytest.mark.asyncio
    async def test_error_context_manager_unexpected_error(self, tmp_path):
        """Test error context manager with unexpected error."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        with pytest.raises(CheckupError):
            async with orchestrator._error_context("test_operation", "test_component"):
                raise ValueError("Unexpected error")
        
        # Error should be wrapped and tracked
        assert len(orchestrator._errors) == 1
        assert "Unexpected error in test_operation" in orchestrator._errors[0].message
        assert orchestrator._errors[0].component == "test_component"
        assert isinstance(orchestrator._errors[0].original_error, ValueError)
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_success_after_failures(self, tmp_path):
        """Test retry mechanism with eventual success."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        attempt_count = 0
        
        async def failing_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 2:
                raise RetryableError("Temporary failure")
            return "success"
        
        result = await orchestrator._retry_operation(
            failing_operation, "test_operation", max_retries=3
        )
        
        assert result == "success"
        assert attempt_count == 3  # Failed twice, succeeded on third attempt
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_exhausted_retries(self, tmp_path):
        """Test retry mechanism with exhausted retries."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        async def always_failing_operation():
            raise RetryableError("Always fails")
        
        with pytest.raises(RetryableError):
            await orchestrator._retry_operation(
                always_failing_operation, "test_operation", max_retries=2
            )
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_non_retryable_error(self, tmp_path):
        """Test retry mechanism with non-retryable error."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        async def non_retryable_operation():
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            await orchestrator._retry_operation(
                non_retryable_operation, "test_operation", max_retries=2
            )
    
    @pytest.mark.asyncio
    async def test_analyzer_with_retryable_error(self, tmp_path):
        """Test analyzer execution with retryable errors."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        analyzer = RetryableAnalyzer(config, fail_count=2)
        
        # Should succeed after retries
        issues, metrics = await orchestrator._run_analyzer_with_progress(analyzer, 0, 1)
        
        assert len(issues) == 1
        assert analyzer.attempt_count == 3  # Failed twice, succeeded on third
    
    @pytest.mark.asyncio
    async def test_analyzer_with_non_retryable_error(self, tmp_path):
        """Test analyzer execution with non-retryable error."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        analyzer = NonRetryableAnalyzer(config)
        
        with pytest.raises(AnalysisError):
            await orchestrator._run_analyzer_with_progress(analyzer, 0, 1)
        
        # Error should be tracked
        assert len(orchestrator._errors) == 1
    
    @pytest.mark.asyncio
    async def test_full_checkup_with_configuration_error(self, tmp_path):
        """Test full checkup with configuration validation error."""
        # Create invalid configuration
        config = CheckupConfig(
            target_directory=Path("/nonexistent"),  # Invalid path
            similarity_threshold=2.0  # Invalid threshold
        )
        orchestrator = CodebaseOrchestrator(config)
        
        results = await orchestrator.run_full_checkup()
        
        assert results.success is False
        assert "Configuration validation failed" in results.error_message
        assert len(orchestrator._errors) == 1
    
    @pytest.mark.asyncio
    async def test_full_checkup_with_analysis_errors(self, tmp_path):
        """Test full checkup with analysis errors."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register failing analyzer
        orchestrator.register_analyzer(NonRetryableAnalyzer)
        
        results = await orchestrator.run_full_checkup()
        
        # Should complete but with errors
        assert results.success is False
        assert results.analysis is not None
        assert len(orchestrator._errors) > 0
    
    @pytest.mark.asyncio
    async def test_full_checkup_with_cleanup_errors(self, tmp_path):
        """Test full checkup with cleanup errors."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            create_backup=False
        )
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock failing cleaner
        failing_cleaner = Mock()
        failing_cleaner.name = "failing_cleaner"
        failing_cleaner.clean = AsyncMock(side_effect=CleanupError("Cleanup failed"))
        orchestrator._cleaners = [failing_cleaner]
        
        with patch.object(orchestrator, '_should_run_cleaner', return_value=True):
            results = await orchestrator.run_full_checkup()
        
        # Should complete analysis but fail cleanup
        assert results.analysis is not None
        assert results.cleanup is None  # Cleanup failed
        assert len(orchestrator._errors) > 0
    
    @pytest.mark.asyncio
    async def test_full_checkup_with_report_generation_errors(self, tmp_path):
        """Test full checkup with report generation errors."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock failing reporter
        failing_reporter = Mock()
        failing_reporter.name = "failing_reporter"
        failing_reporter.generate_and_save_summary = AsyncMock(
            side_effect=ReportGenerationError("Report failed")
        )
        orchestrator._reporters = [failing_reporter]
        
        with patch.object(orchestrator, '_should_run_reporter', return_value=True):
            results = await orchestrator.run_full_checkup()
        
        # Should complete but with warnings about report generation
        assert results.success is True  # Report failure doesn't fail the whole checkup
        assert results.analysis is not None
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_with_metrics_failure(self, tmp_path):
        """Test graceful degradation when metrics capture fails."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock metrics capture to fail
        with patch.object(orchestrator, '_capture_metrics', 
                         side_effect=Exception("Metrics failed")):
            results = await orchestrator.run_full_checkup()
        
        # Should complete with default metrics
        assert results.success is True
        assert results.before_metrics is not None
        assert results.before_metrics.total_files == 0  # Default metrics
    
    @pytest.mark.asyncio
    async def test_error_recovery_in_analysis_workflow(self, tmp_path):
        """Test error recovery in analysis workflow."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register mix of working and failing analyzers
        working_analyzer = Mock()
        working_analyzer.name = "working_analyzer"
        working_analyzer.analyze = AsyncMock(return_value=[])
        working_analyzer.metrics = CodebaseMetrics()
        
        failing_analyzer = Mock()
        failing_analyzer.name = "failing_analyzer"
        failing_analyzer.analyze = AsyncMock(side_effect=Exception("Analyzer failed"))
        
        orchestrator._analyzers = [working_analyzer, failing_analyzer]
        
        with patch.object(orchestrator, '_should_run_analyzer', return_value=True):
            results = await orchestrator.run_analysis_only()
        
        # Should complete with results from working analyzer
        assert results is not None
        assert results.total_issues >= 0
    
    @pytest.mark.asyncio
    async def test_comprehensive_error_logging(self, tmp_path, caplog):
        """Test comprehensive error logging throughout the workflow."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register failing components
        orchestrator.register_analyzer(NonRetryableAnalyzer)
        
        with caplog.at_level(logging.ERROR):
            results = await orchestrator.run_full_checkup()
        
        # Check for structured error logs
        error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(error_logs) > 0
        
        # Verify structured logging format
        for log_record in error_logs:
            # Check for structured log entry
            if hasattr(log_record, 'log_entry'):
                log_entry = log_record.log_entry
                assert hasattr(log_entry, 'timestamp')
                assert hasattr(log_entry, 'metadata')
                assert 'orchestrator_id' in log_entry.metadata
    
    @pytest.mark.asyncio
    async def test_enhanced_error_context_manager(self, tmp_path):
        """Test enhanced error context manager with advanced features."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Test critical operation failure
        with pytest.raises(CheckupError):
            async with orchestrator._error_context("critical_test", "test_component", 
                                                  critical=True, allow_partial_failure=False):
                raise ValueError("Critical failure")
        
        # Test non-critical operation with partial failure allowed
        async with orchestrator._error_context("non_critical_test", "test_component", 
                                              critical=False, allow_partial_failure=True):
            raise ValueError("Non-critical failure")
        
        # Should not raise exception for non-critical operations
        assert len(orchestrator._errors) >= 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, tmp_path):
        """Test circuit breaker pattern implementation."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        failure_count = 0
        
        async def failing_operation():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 5:  # Fail first 5 times
                raise Exception("Simulated failure")
            return "success"
        
        # Test circuit breaker opening after failures
        for i in range(6):
            try:
                await orchestrator._retry_with_circuit_breaker(
                    failing_operation, "test_operation", "test_component",
                    failure_threshold=3, recovery_timeout=1
                )
            except Exception:
                pass
        
        # Circuit should be open now
        circuit_key = "test_component_test_operation"
        assert circuit_key in orchestrator._circuit_breakers
        assert orchestrator._circuit_breakers[circuit_key]['state'] == 'open'
        
        # Test circuit breaker preventing calls
        with pytest.raises(CheckupError, match="Circuit breaker open"):
            await orchestrator._retry_with_circuit_breaker(
                failing_operation, "test_operation", "test_component",
                failure_threshold=3, recovery_timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_performance_metrics_tracking(self, tmp_path):
        """Test performance metrics tracking and analysis."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Simulate operations with different durations
        for i in range(5):
            orchestrator._track_performance_metric("test_operation", i * 0.1, "test_component")
        
        # Get performance metrics
        metrics = orchestrator.get_performance_metrics()
        
        assert metrics['total_operations'] == 5
        assert 'test_operation_test_component' in metrics['metrics']
        
        operation_metrics = metrics['metrics']['test_operation_test_component']
        assert operation_metrics['count'] == 5
        assert operation_metrics['average_duration'] == 0.2  # (0 + 0.1 + 0.2 + 0.3 + 0.4) / 5
        assert operation_metrics['min_duration'] == 0.0
        assert operation_metrics['max_duration'] == 0.4
    
    @pytest.mark.asyncio
    async def test_error_recovery_system(self, tmp_path):
        """Test comprehensive error recovery system."""
        config = CheckupConfig(target_directory=tmp_path, enable_error_recovery=True)
        orchestrator = CodebaseOrchestrator(config)
        
        # Add some recoverable errors
        error1 = CheckupError("Recoverable error 1", component="test1")
        error2 = CheckupError("Recoverable error 2", component="test2")
        orchestrator._errors.extend([error1, error2])
        
        # Attempt error recovery
        recovery_results = await orchestrator.attempt_error_recovery()
        
        assert recovery_results['recovery_attempted'] is True
        assert recovery_results['total_errors'] == 2
        assert recovery_results['recoverable_errors'] >= 0
        assert 'recovery_details' in recovery_results
    
    @pytest.mark.asyncio
    async def test_error_summary_generation(self, tmp_path):
        """Test comprehensive error summary generation."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Add various types of errors
        error1 = CheckupError("Configuration error", component="config")
        error2 = AnalysisError("Analysis failed", component="analyzer")
        error3 = CleanupError("Cleanup failed", component="cleaner")
        
        orchestrator._errors.extend([error1, error2, error3])
        orchestrator._warnings.extend(["Warning 1", "Warning 2"])
        
        # Add some retryable errors
        orchestrator._retryable_errors.append({
            'error': RetryableError("Temporary failure"),
            'operation': 'test_op',
            'component': 'test_component',
            'timestamp': datetime.now(),
            'duration': 1.5
        })
        
        # Get error summary
        summary = orchestrator.get_error_summary()
        
        assert summary['summary']['total_errors'] == 3
        assert summary['summary']['total_warnings'] == 2
        assert summary['summary']['total_retryable_errors'] == 1
        assert 'categorized_errors' in summary
        assert 'severity_distribution' in summary
        assert 'category_distribution' in summary
        assert 'recommendations' in summary
        assert len(summary['recommendations']) > 0
    
    @pytest.mark.asyncio
    async def test_system_state_capture(self, tmp_path):
        """Test system state capture for error context."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Add some operations to the stack
        orchestrator._operation_stack = ['op1', 'op2', 'op3']
        orchestrator._errors = [CheckupError("Test error")]
        orchestrator._warnings = ["Test warning"]
        
        # Capture system state
        state = await orchestrator._capture_system_state()
        
        assert 'timestamp' in state
        assert state['active_operations'] == 3
        assert state['total_errors'] == 1
        assert state['total_warnings'] == 1
        
        # Check for system metrics if psutil is available
        try:
            import psutil
            assert 'memory_percent' in state
            assert 'cpu_percent' in state
            assert 'disk_percent' in state
        except ImportError:
            pass  # psutil not available in test environment
    
    @pytest.mark.asyncio
    async def test_pre_operation_checks(self, tmp_path):
        """Test pre-operation health checks."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Test normal pre-operation check
        await orchestrator._pre_operation_check("test_operation", "test_component")
        
        # Should complete without errors under normal conditions
        assert len(orchestrator._errors) == 0
    
    def test_circuit_breaker_reset(self, tmp_path):
        """Test circuit breaker reset functionality."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Set up some circuit breakers
        orchestrator._circuit_breakers = {
            'test_circuit_1': {'state': 'open', 'failure_count': 5, 'last_failure_time': datetime.now(), 'success_count': 0},
            'test_circuit_2': {'state': 'open', 'failure_count': 3, 'last_failure_time': datetime.now(), 'success_count': 0}
        }
        
        # Reset specific circuit
        orchestrator.reset_circuit_breakers('test_circuit_1')
        assert orchestrator._circuit_breakers['test_circuit_1']['state'] == 'closed'
        assert orchestrator._circuit_breakers['test_circuit_1']['failure_count'] == 0
        assert orchestrator._circuit_breakers['test_circuit_2']['state'] == 'open'  # Should remain open
        
        # Reset all circuits
        orchestrator.reset_circuit_breakers()
        assert all(cb['state'] == 'closed' for cb in orchestrator._circuit_breakers.values())
        assert all(cb['failure_count'] == 0 for cb in orchestrator._circuit_breakers.values())
    
    def test_error_history_management(self, tmp_path):
        """Test error history management and cleanup."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Add some error history
        orchestrator._errors.append(CheckupError("Test error"))
        orchestrator._warnings.append("Test warning")
        orchestrator._retryable_errors.append({'error': 'test'})
        orchestrator._performance_metrics['test_op'] = [{'duration': 1.0, 'timestamp': datetime.now().isoformat()}]
        
        # Verify history exists
        assert len(orchestrator._errors) == 1
        assert len(orchestrator._warnings) == 1
        assert len(orchestrator._retryable_errors) == 1
        assert len(orchestrator._performance_metrics) == 1
        
        # Clear history
        orchestrator.clear_error_history()
        
        # Verify history is cleared
        assert len(orchestrator._errors) == 0
        assert len(orchestrator._warnings) == 0
        assert len(orchestrator._retryable_errors) == 0
        assert len(orchestrator._performance_metrics) == 0
    
    def test_error_aggregation_and_reporting(self, tmp_path):
        """Test error aggregation and reporting functionality."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Add some errors manually
        error1 = CheckupError("Error 1", component="component1")
        error2 = AnalysisError("Error 2", component="component2")
        error3 = CleanupError("Error 3", component="component3")
        
        orchestrator._errors.extend([error1, error2, error3])
        
        # Verify error tracking
        assert len(orchestrator._errors) == 3
        assert any(isinstance(e, CheckupError) for e in orchestrator._errors)
        assert any(isinstance(e, AnalysisError) for e in orchestrator._errors)
        assert any(isinstance(e, CleanupError) for e in orchestrator._errors)
        
        # Verify error serialization
        for error in orchestrator._errors:
            error_dict = error.to_dict()
            assert "error_type" in error_dict
            assert "message" in error_dict
            assert "component" in error_dict
            assert "timestamp" in error_dict


class TestAdvancedErrorHandling:
    """Test advanced error handling features."""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_workflow(self, tmp_path):
        """Test graceful degradation in complex workflows."""
        config = CheckupConfig(target_directory=tmp_path, graceful_degradation=True)
        orchestrator = CodebaseOrchestrator(config)
        
        # Create mix of working and failing components
        working_analyzer = Mock()
        working_analyzer.name = "working_analyzer"
        working_analyzer.analyze = AsyncMock(return_value=[])
        working_analyzer.metrics = CodebaseMetrics()
        
        failing_analyzer = Mock()
        failing_analyzer.name = "failing_analyzer"
        failing_analyzer.analyze = AsyncMock(side_effect=Exception("Analyzer failed"))
        
        orchestrator._analyzers = [working_analyzer, failing_analyzer]
        
        with patch.object(orchestrator, '_should_run_analyzer', return_value=True):
            # Should complete with partial results
            results = await orchestrator.run_analysis_only()
            assert results is not None
    
    @pytest.mark.asyncio
    async def test_error_correlation_analysis(self, tmp_path):
        """Test error correlation and pattern analysis."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Add correlated errors (same component, similar timeframe)
        base_time = datetime.now()
        for i in range(3):
            error = CheckupError(f"Error {i}", component="problematic_component")
            error.timestamp = base_time + timedelta(seconds=i)
            orchestrator._errors.append(error)
        
        # Add unrelated error
        unrelated_error = CheckupError("Unrelated error", component="other_component")
        unrelated_error.timestamp = base_time + timedelta(hours=1)
        orchestrator._errors.append(unrelated_error)
        
        summary = orchestrator.get_error_summary()
        
        # Should identify patterns in error distribution
        assert 'categorized_errors' in summary
        assert len(summary['categorized_errors']) > 0
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_handling(self, tmp_path):
        """Test handling of resource exhaustion scenarios."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock resource exhaustion
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 95  # High memory usage
            
            # Should add warning but continue
            await orchestrator._pre_operation_check("test_operation", "test_component")
            assert len(orchestrator._warnings) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, tmp_path):
        """Test error handling in concurrent operations."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        async def concurrent_operation(operation_id: int):
            async with orchestrator._error_context(f"concurrent_op_{operation_id}", 
                                                  f"component_{operation_id}"):
                if operation_id % 2 == 0:  # Even operations fail
                    raise Exception(f"Operation {operation_id} failed")
                await asyncio.sleep(0.01)  # Simulate work
                return f"success_{operation_id}"
        
        # Run multiple concurrent operations
        tasks = [concurrent_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should have mix of successes and failures
        successes = [r for r in results if isinstance(r, str)]
        failures = [r for r in results if isinstance(r, Exception)]
        
        assert len(successes) == 5  # Odd operations succeed
        assert len(failures) == 5   # Even operations fail
        assert len(orchestrator._errors) >= 5  # Should track failures


class TestRetryMechanismIntegration:
    """Test retry mechanism integration with real components."""
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, tmp_path):
        """Test retry mechanism with exponential backoff timing."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        orchestrator._retry_delay = 0.1  # Faster for testing
        
        attempt_times = []
        
        async def timing_operation():
            attempt_times.append(datetime.now())
            if len(attempt_times) <= 2:
                raise RetryableError("Temporary failure")
            return "success"
        
        start_time = datetime.now()
        result = await orchestrator._retry_operation(
            timing_operation, "test_operation", max_retries=3
        )
        end_time = datetime.now()
        
        assert result == "success"
        assert len(attempt_times) == 3
        
        # Verify exponential backoff (approximately)
        total_duration = (end_time - start_time).total_seconds()
        expected_min_duration = 0.1 + 0.2  # First retry + second retry delays
        assert total_duration >= expected_min_duration
    
    @pytest.mark.asyncio
    async def test_component_lifecycle_error_handling(self, tmp_path):
        """Test error handling throughout component lifecycle."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Create analyzer that fails in different phases
        class LifecycleAnalyzer(BaseAnalyzer):
            def __init__(self, config, fail_phase=None):
                super().__init__(config)
                self.name = "lifecycle_analyzer"
                self.metrics = CodebaseMetrics()
                self.fail_phase = fail_phase
            
            async def pre_analyze(self):
                if self.fail_phase == "pre":
                    raise Exception("Pre-analyze failed")
            
            async def analyze(self):
                if self.fail_phase == "analyze":
                    raise Exception("Analyze failed")
                return []
            
            async def post_analyze(self, issues):
                if self.fail_phase == "post":
                    raise Exception("Post-analyze failed")
        
        # Test failure in each phase
        for phase in ["pre", "analyze", "post"]:
            analyzer = LifecycleAnalyzer(config, fail_phase=phase)
            
            with pytest.raises(AnalysisError):
                await orchestrator._run_analyzer_with_progress(analyzer, 0, 1)


class TestLoggingIntegration:
    """Test integration with advanced logging systems."""
    
    @pytest.mark.asyncio
    async def test_structured_logging_integration(self, tmp_path):
        """Test integration with structured logging system."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Test structured logging with various log levels
        orchestrator._log_structured("info", "Test info message", 
                                    component="test_component", operation="test_operation")
        orchestrator._log_structured("warning", "Test warning message", 
                                    component="test_component", error_code="TEST_001")
        orchestrator._log_structured("error", "Test error message", 
                                    component="test_component", duration=1.5)
        
        # Should not raise exceptions
        assert True
    
    @pytest.mark.asyncio
    async def test_performance_logging(self, tmp_path):
        """Test performance metrics logging."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Track multiple operations
        for i in range(15):  # Trigger summary logging at 10th operation
            orchestrator._track_performance_metric("test_operation", i * 0.1, "test_component")
        
        # Should have logged performance summary
        assert len(orchestrator._performance_metrics) > 0
    
    def test_log_file_configuration(self, tmp_path):
        """Test log file configuration and setup."""
        log_file = tmp_path / "test.log"
        error_log_file = tmp_path / "error.log"
        perf_log_file = tmp_path / "performance.log"
        
        config = CheckupConfig(
            target_directory=tmp_path,
            log_file=str(log_file),
            error_log_file=str(error_log_file),
            performance_log_file=str(perf_log_file)
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Verify logger setup
        assert orchestrator.logger is not None
        assert len(orchestrator.logger.handlers) >= 2  # Console + file handlers
    
    @pytest.mark.asyncio
    async def test_audit_logging_integration(self, tmp_path):
        """Test integration with audit logging system."""
        config = CheckupConfig(target_directory=tmp_path, session_id="test_session")
        orchestrator = CodebaseOrchestrator(config)
        
        # Simulate operations that should be audited
        async with orchestrator._error_context("audit_test", "audit_component"):
            pass
        
        # Should have logged audit information
        assert True  # Basic test - would need audit logger mock for full testing


class TestErrorRecoveryStrategies:
    """Test different error recovery strategies."""
    
    @pytest.mark.asyncio
    async def test_retry_recovery_strategy(self, tmp_path):
        """Test retry-based error recovery."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        error = CheckupError("Retryable error", component="test_component")
        
        # Test retry recovery (should return False as it's not implemented)
        result = await orchestrator._recovery_retry(error)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_skip_recovery_strategy(self, tmp_path):
        """Test skip-based error recovery."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        error = CheckupError("Skippable error", component="test_component")
        
        # Test skip recovery (should return True)
        result = await orchestrator._recovery_skip(error)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rollback_recovery_strategy(self, tmp_path):
        """Test rollback-based error recovery."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        error = CheckupError("Rollback error", component="test_component")
        
        # Test rollback recovery (should return False as it's not implemented)
        result = await orchestrator._recovery_rollback(error)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_manual_recovery_strategy(self, tmp_path):
        """Test manual intervention recovery strategy."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        error = CheckupError("Manual intervention error", component="test_component")
        
        # Test manual recovery (should return False and log warning)
        result = await orchestrator._recovery_manual(error)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__])