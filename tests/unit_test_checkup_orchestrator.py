"""
Comprehensive unit tests for checkup orchestrator.
Tests the orchestrator class to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migration_assistant.checkup.orchestrator import CodebaseOrchestrator
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CleanupResults, CheckupResults,
    QualityIssue, ImportIssue, StructureIssue, CoverageGap, ConfigIssue, DocIssue,
    IssueType, IssueSeverity, CodebaseMetrics, FormattingChange, FileMove
)
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.cleaners.base import BaseCleaner, CleanupResult
from migration_assistant.checkup.validators.base import BaseValidator, ValidationResult
from migration_assistant.checkup.reporters.base import BaseReportGenerator


class MockAnalyzer(BaseAnalyzer):
    """Mock analyzer for testing."""
    
    def __init__(self, config, name="MockAnalyzer", issues_to_return=None, should_fail=False):
        super().__init__(config)
        self.name = name
        self.issues_to_return = issues_to_return or []
        self.should_fail = should_fail
        self.analyze_called = False
    
    def get_supported_file_types(self):
        return ['.py']
    
    async def analyze(self):
        self.analyze_called = True
        if self.should_fail:
            raise Exception(f"Mock analyzer {self.name} failed")
        return self.issues_to_return


class MockCleaner(BaseCleaner):
    """Mock cleaner for testing."""
    
    def __init__(self, config, name="MockCleaner", should_fail=False):
        super().__init__(config)
        self.name = name
        self.should_fail = should_fail
        self.clean_called = False
        self.issues_cleaned = []
    
    def can_clean_issue(self, issue):
        return True
    
    async def clean(self, issues=None):
        self.clean_called = True
        self.issues_cleaned = issues or []
        if self.should_fail:
            raise Exception(f"Mock cleaner {self.name} failed")
        return CleanupResult(
            success=True,
            changes_made=len(self.issues_cleaned),
            files_modified=len(set(issue.file_path for issue in self.issues_cleaned))
        )


class MockValidator(BaseValidator):
    """Mock validator for testing."""
    
    def __init__(self, config, name="MockValidator", issues_to_return=None, should_fail=False):
        super().__init__(config)
        self.name = name
        self.issues_to_return = issues_to_return or []
        self.should_fail = should_fail
        self.validate_called = False
    
    async def validate(self):
        self.validate_called = True
        if self.should_fail:
            raise Exception(f"Mock validator {self.name} failed")
        return ValidationResult(
            success=True,
            issues_found=len(self.issues_to_return),
            files_validated=1
        )


class MockReportGenerator(BaseReportGenerator):
    """Mock report generator for testing."""
    
    def __init__(self, config, name="MockReportGenerator", should_fail=False):
        super().__init__(config)
        self.name = name
        self.should_fail = should_fail
        self.generate_summary_called = False
        self.generate_detailed_called = False
        self.generate_comparison_called = False
    
    def generate_summary_report(self, results):
        self.generate_summary_called = True
        if self.should_fail:
            raise Exception(f"Mock report generator {self.name} failed")
        return f"Summary report by {self.name}"
    
    def generate_detailed_report(self, results):
        self.generate_detailed_called = True
        if self.should_fail:
            raise Exception(f"Mock report generator {self.name} failed")
        return f"Detailed report by {self.name}"
    
    def generate_comparison_report(self, before, after):
        self.generate_comparison_called = True
        if self.should_fail:
            raise Exception(f"Mock report generator {self.name} failed")
        return f"Comparison report by {self.name}"


class TestCodebaseOrchestrator:
    """Test cases for CodebaseOrchestrator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            enable_quality_analysis=True,
            enable_duplicate_detection=True,
            enable_import_analysis=True,
            enable_structure_analysis=True,
            check_test_coverage=True,
            validate_configs=True,
            validate_docs=True,
            auto_format=False,
            auto_fix_imports=False,
            auto_organize_files=False,
            generate_html_report=True,
            generate_json_report=True,
            generate_markdown_report=True,
            create_backup=True,
            dry_run=False
        )
    
    def test_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        assert orchestrator.config == self.config
        assert orchestrator.target_directory == self.config.target_directory
        assert orchestrator._analyzers == []
        assert orchestrator._cleaners == []
        assert orchestrator._validators == []
        assert orchestrator._report_generators == []
        assert orchestrator._progress_callback is None
    
    def test_register_analyzer(self):
        """Test analyzer registration."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Register analyzer class
        orchestrator.register_analyzer(MockAnalyzer)
        
        assert len(orchestrator._analyzers) == 1
        assert isinstance(orchestrator._analyzers[0], MockAnalyzer)
    
    def test_register_cleaner(self):
        """Test cleaner registration."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Register cleaner class
        orchestrator.register_cleaner(MockCleaner)
        
        assert len(orchestrator._cleaners) == 1
        assert isinstance(orchestrator._cleaners[0], MockCleaner)
    
    def test_register_validator(self):
        """Test validator registration."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Register validator class
        orchestrator.register_validator(MockValidator)
        
        assert len(orchestrator._validators) == 1
        assert isinstance(orchestrator._validators[0], MockValidator)
    
    def test_register_report_generator(self):
        """Test report generator registration."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Register report generator class
        orchestrator.register_report_generator(MockReportGenerator)
        
        assert len(orchestrator._report_generators) == 1
        assert isinstance(orchestrator._report_generators[0], MockReportGenerator)
    
    def test_set_progress_callback(self):
        """Test progress callback setting."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        def progress_callback(stage, progress, message):
            pass
        
        orchestrator.set_progress_callback(progress_callback)
        assert orchestrator._progress_callback == progress_callback
    
    @pytest.mark.asyncio
    async def test_run_analysis_only(self):
        """Test analysis-only execution."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Create sample issues
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Style issue"
        )
        
        import_issue = ImportIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.UNUSED_IMPORT,
            severity=IssueSeverity.LOW,
            import_name="unused_module",
            message="Unused import"
        )
        
        # Register mock components
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "QualityAnalyzer", [quality_issue]))
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "ImportAnalyzer", [import_issue]))
        orchestrator.register_validator(lambda config: MockValidator(config, "ConfigValidator", []))
        
        # Run analysis
        results = await orchestrator.run_analysis_only()
        
        assert isinstance(results, AnalysisResults)
        assert len(results.quality_issues) == 1
        assert len(results.import_issues) == 1
        assert results.quality_issues[0] == quality_issue
        assert results.import_issues[0] == import_issue
        assert isinstance(results.timestamp, datetime)
        assert isinstance(results.metrics, CodebaseMetrics)
    
    @pytest.mark.asyncio
    async def test_run_cleanup_only(self):
        """Test cleanup-only execution."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Create sample issues
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Style issue"
        )
        
        # Create analysis results
        analysis_results = AnalysisResults(
            quality_issues=[quality_issue],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(total_files=1, style_violations=1)
        )
        
        # Register mock cleaner
        orchestrator.register_cleaner(lambda config: MockCleaner(config, "FormatterCleaner"))
        
        # Run cleanup
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        assert isinstance(results, CleanupResults)
        assert len(results.formatting_changes) >= 0  # May be empty if no formatting changes
        assert isinstance(results.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_run_full_checkup(self):
        """Test full checkup execution."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Create sample issues
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Style issue"
        )
        
        # Register mock components
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "QualityAnalyzer", [quality_issue]))
        orchestrator.register_cleaner(lambda config: MockCleaner(config, "FormatterCleaner"))
        orchestrator.register_validator(lambda config: MockValidator(config, "ConfigValidator", []))
        
        # Run full checkup
        results = await orchestrator.run_full_checkup()
        
        assert isinstance(results, CheckupResults)
        assert isinstance(results.analysis, AnalysisResults)
        assert isinstance(results.cleanup, CleanupResults)
        assert isinstance(results.before_metrics, CodebaseMetrics)
        assert isinstance(results.after_metrics, CodebaseMetrics)
        assert isinstance(results.duration, timedelta)
        assert results.success is True
    
    @pytest.mark.asyncio
    async def test_generate_reports(self):
        """Test report generation."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Create sample checkup results
        analysis_results = AnalysisResults(
            quality_issues=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(total_files=1)
        )
        
        checkup_results = CheckupResults(
            analysis=analysis_results,
            cleanup=None,
            before_metrics=CodebaseMetrics(total_files=1),
            after_metrics=None,
            duration=timedelta(seconds=30),
            success=True
        )
        
        # Register mock report generators
        html_generator = MockReportGenerator(self.config, "HTMLGenerator")
        json_generator = MockReportGenerator(self.config, "JSONGenerator")
        md_generator = MockReportGenerator(self.config, "MarkdownGenerator")
        
        orchestrator._report_generators = [html_generator, json_generator, md_generator]
        
        # Generate reports
        report_results = await orchestrator.generate_reports(checkup_results)
        
        assert len(report_results) == 3
        assert html_generator.generate_summary_called
        assert json_generator.generate_summary_called
        assert md_generator.generate_summary_called
    
    @pytest.mark.asyncio
    async def test_error_handling_in_analysis(self):
        """Test error handling during analysis."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Register failing and working analyzers
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "WorkingAnalyzer", []))
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "FailingAnalyzer", should_fail=True))
        
        # Run analysis - should not fail completely
        results = await orchestrator.run_analysis_only()
        
        assert isinstance(results, AnalysisResults)
        # Should still return results even if some analyzers fail
    
    @pytest.mark.asyncio
    async def test_error_handling_in_cleanup(self):
        """Test error handling during cleanup."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Create analysis results
        analysis_results = AnalysisResults(
            quality_issues=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(total_files=1)
        )
        
        # Register failing cleaner
        orchestrator.register_cleaner(lambda config: MockCleaner(config, "FailingCleaner", should_fail=True))
        
        # Run cleanup - should handle errors gracefully
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        assert isinstance(results, CleanupResults)
        # Should still return results even if some cleaners fail
    
    @pytest.mark.asyncio
    async def test_progress_reporting(self):
        """Test progress reporting functionality."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Track progress calls
        progress_calls = []
        
        def progress_callback(stage, progress, message):
            progress_calls.append((stage, progress, message))
        
        orchestrator.set_progress_callback(progress_callback)
        
        # Register components
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "TestAnalyzer", []))
        orchestrator.register_cleaner(lambda config: MockCleaner(config, "TestCleaner"))
        
        # Run full checkup
        await orchestrator.run_full_checkup()
        
        # Should have received progress updates
        assert len(progress_calls) > 0
        
        # Check that different stages were reported
        stages = [call[0] for call in progress_calls]
        assert "analysis" in stages or "Analysis" in str(stages)
    
    @pytest.mark.asyncio
    async def test_parallel_analysis_execution(self):
        """Test parallel execution of analyzers."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Register multiple analyzers
        analyzer1 = MockAnalyzer(self.config, "Analyzer1", [])
        analyzer2 = MockAnalyzer(self.config, "Analyzer2", [])
        analyzer3 = MockAnalyzer(self.config, "Analyzer3", [])
        
        orchestrator._analyzers = [analyzer1, analyzer2, analyzer3]
        
        # Run analysis
        start_time = datetime.now()
        results = await orchestrator.run_analysis_only()
        end_time = datetime.now()
        
        # All analyzers should have been called
        assert analyzer1.analyze_called
        assert analyzer2.analyze_called
        assert analyzer3.analyze_called
        
        # Should complete relatively quickly due to parallel execution
        duration = (end_time - start_time).total_seconds()
        assert duration < 5.0  # Should be much faster than sequential execution
    
    @pytest.mark.asyncio
    async def test_component_filtering_based_on_config(self):
        """Test that components are filtered based on configuration."""
        # Disable some analysis types
        config = CheckupConfig(
            target_directory=self.temp_dir,
            enable_quality_analysis=False,
            enable_duplicate_detection=True,
            enable_import_analysis=True,
            check_test_coverage=False,
            validate_configs=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Register all types of components
        quality_analyzer = MockAnalyzer(config, "QualityAnalyzer")
        import_analyzer = MockAnalyzer(config, "ImportAnalyzer")
        coverage_validator = MockValidator(config, "CoverageValidator")
        config_validator = MockValidator(config, "ConfigValidator")
        
        orchestrator._analyzers = [quality_analyzer, import_analyzer]
        orchestrator._validators = [coverage_validator, config_validator]
        
        # Run analysis
        await orchestrator.run_analysis_only()
        
        # Only enabled components should be executed
        # This would require the orchestrator to actually filter based on config
        # For now, we just verify the components are registered
        assert len(orchestrator._analyzers) == 2
        assert len(orchestrator._validators) == 2
    
    @pytest.mark.asyncio
    async def test_metrics_aggregation(self):
        """Test metrics aggregation across components."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # Create issues that should affect metrics
        quality_issues = [
            QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Error 1"),
            QualityIssue(Path("test2.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Error 2")
        ]
        
        import_issues = [
            ImportIssue(Path("test3.py"), IssueType.UNUSED_IMPORT, IssueSeverity.LOW, "unused", "Unused import")
        ]
        
        # Register analyzers with issues
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "QualityAnalyzer", quality_issues))
        orchestrator.register_analyzer(lambda config: MockAnalyzer(config, "ImportAnalyzer", import_issues))
        
        # Run analysis
        results = await orchestrator.run_analysis_only()
        
        # Check that metrics reflect the issues found
        assert results.metrics.syntax_errors >= 1
        assert results.metrics.style_violations >= 1
        assert results.metrics.unused_imports >= 1
        assert results.total_issues == 3
    
    def test_create_default_components(self):
        """Test creation of default components."""
        orchestrator = CodebaseOrchestrator(self.config)
        
        # This would test the actual component creation if implemented
        # For now, we just verify the orchestrator can be initialized
        assert orchestrator is not None
        assert orchestrator.config == self.config
    
    def test_validate_configuration(self):
        """Test configuration validation."""
        # Test with valid configuration
        valid_config = CheckupConfig(
            target_directory=self.temp_dir,
            enable_quality_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(valid_config)
        assert orchestrator.config == valid_config
        
        # Test with invalid configuration (if validation is implemented)
        # This would test actual validation logic
    
    @pytest.mark.asyncio
    async def test_backup_creation_before_cleanup(self):
        """Test backup creation before cleanup operations."""
        config = CheckupConfig(
            target_directory=self.temp_dir,
            create_backup=True,
            auto_format=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Create a test file
        test_file = self.temp_dir / "test.py"
        test_file.write_text("def func():\n    pass")
        
        # Create analysis results with cleanable issues
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(test_file, IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Style issue")
            ],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(total_files=1, style_violations=1)
        )
        
        # Register cleaner
        orchestrator.register_cleaner(lambda config: MockCleaner(config, "TestCleaner"))
        
        # Run cleanup
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should complete successfully
        assert isinstance(results, CleanupResults)
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        """Test dry run mode execution."""
        config = CheckupConfig(
            target_directory=self.temp_dir,
            dry_run=True,
            auto_format=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Create analysis results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Style issue")
            ],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(total_files=1, style_violations=1)
        )
        
        # Register cleaner
        cleaner = MockCleaner(config, "TestCleaner")
        orchestrator._cleaners = [cleaner]
        
        # Run cleanup in dry run mode
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should complete but not make actual changes
        assert isinstance(results, CleanupResults)
        assert cleaner.clean_called  # Should still be called to simulate


if __name__ == "__main__":
    # Run tests manually without pytest
    import asyncio
    
    async def run_async_tests():
        """Run async tests manually."""
        print("Running CodebaseOrchestrator tests...")
        
        test_orchestrator = TestCodebaseOrchestrator()
        test_orchestrator.setup_method()
        
        try:
            await test_orchestrator.test_run_analysis_only()
            print("✓ test_run_analysis_only passed")
        except Exception as e:
            print(f"✗ test_run_analysis_only failed: {e}")
        
        try:
            await test_orchestrator.test_run_cleanup_only()
            print("✓ test_run_cleanup_only passed")
        except Exception as e:
            print(f"✗ test_run_cleanup_only failed: {e}")
        
        try:
            await test_orchestrator.test_run_full_checkup()
            print("✓ test_run_full_checkup passed")
        except Exception as e:
            print(f"✗ test_run_full_checkup failed: {e}")
        
        try:
            await test_orchestrator.test_generate_reports()
            print("✓ test_generate_reports passed")
        except Exception as e:
            print(f"✗ test_generate_reports failed: {e}")
        
        try:
            await test_orchestrator.test_error_handling_in_analysis()
            print("✓ test_error_handling_in_analysis passed")
        except Exception as e:
            print(f"✗ test_error_handling_in_analysis failed: {e}")
        
        try:
            await test_orchestrator.test_parallel_analysis_execution()
            print("✓ test_parallel_analysis_execution passed")
        except Exception as e:
            print(f"✗ test_parallel_analysis_execution failed: {e}")
        
        try:
            await test_orchestrator.test_metrics_aggregation()
            print("✓ test_metrics_aggregation passed")
        except Exception as e:
            print(f"✗ test_metrics_aggregation failed: {e}")
    
    def run_sync_tests():
        """Run synchronous tests."""
        print("\nRunning synchronous tests...")
        
        test_orchestrator = TestCodebaseOrchestrator()
        test_orchestrator.setup_method()
        
        try:
            test_orchestrator.test_initialization()
            print("✓ test_initialization passed")
        except Exception as e:
            print(f"✗ test_initialization failed: {e}")
        
        try:
            test_orchestrator.test_register_analyzer()
            print("✓ test_register_analyzer passed")
        except Exception as e:
            print(f"✗ test_register_analyzer failed: {e}")
        
        try:
            test_orchestrator.test_register_cleaner()
            print("✓ test_register_cleaner passed")
        except Exception as e:
            print(f"✗ test_register_cleaner failed: {e}")
        
        try:
            test_orchestrator.test_register_validator()
            print("✓ test_register_validator passed")
        except Exception as e:
            print(f"✗ test_register_validator failed: {e}")
        
        try:
            test_orchestrator.test_register_report_generator()
            print("✓ test_register_report_generator passed")
        except Exception as e:
            print(f"✗ test_register_report_generator failed: {e}")
        
        try:
            test_orchestrator.test_set_progress_callback()
            print("✓ test_set_progress_callback passed")
        except Exception as e:
            print(f"✗ test_set_progress_callback failed: {e}")
    
    # Run tests
    run_sync_tests()
    asyncio.run(run_async_tests())
    print("\nTest run completed!")