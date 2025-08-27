"""
Unit tests for CodebaseOrchestrator initialization and configuration.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from migration_assistant.checkup.orchestrator import (
    CodebaseOrchestrator, CheckupError, AnalysisError, CleanupError, 
    ReportGenerationError
)
from migration_assistant.checkup.models import (
    CheckupConfig, CheckupResults, AnalysisResults, CleanupResults,
    CodebaseMetrics, QualityIssue, IssueSeverity, IssueType
)
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.cleaners.base import BaseCleaner
from migration_assistant.checkup.validators.base import BaseValidator
from migration_assistant.checkup.reporters.base import ReportGenerator


class MockAnalyzer(BaseAnalyzer):
    """Mock analyzer for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "mock_analyzer"
        self.metrics = CodebaseMetrics()
    
    async def analyze(self):
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


class MockCleaner(BaseCleaner):
    """Mock cleaner for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "mock_cleaner"
    
    async def clean(self, analysis_results):
        return Mock(success=True, message="Cleaned successfully")


class MockValidator(BaseValidator):
    """Mock validator for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "mock_validator"
        self.metrics = CodebaseMetrics()
    
    async def validate(self):
        return Mock(issues=[], success=True)


class MockReporter(ReportGenerator):
    """Mock reporter for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "mock_reporter"
    
    async def generate_and_save_summary(self, results):
        return Path("summary.html")
    
    async def generate_and_save_detailed(self, results):
        return Path("detailed.html")


class TestCodebaseOrchestratorInitialization:
    """Test orchestrator initialization and basic functionality."""
    
    def test_orchestrator_initialization(self, tmp_path):
        """Test basic orchestrator initialization."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        assert orchestrator.config == config
        assert orchestrator._analyzers == []
        assert orchestrator._cleaners == []
        assert orchestrator._validators == []
        assert orchestrator._reporters == []
        assert orchestrator._analysis_results is None
        assert orchestrator._cleanup_results is None
    
    def test_configuration_validation_success(self, tmp_path):
        """Test successful configuration validation."""
        config = CheckupConfig(
            target_directory=tmp_path,
            similarity_threshold=0.8,
            min_coverage_threshold=80.0,
            max_file_moves=5
        )
        
        errors = config.validate()
        assert errors == []
    
    def test_configuration_validation_failures(self):
        """Test configuration validation with various errors."""
        config = CheckupConfig(
            target_directory=Path("/nonexistent"),
            similarity_threshold=1.5,  # Invalid
            min_coverage_threshold=150.0,  # Invalid
            max_file_moves=-1  # Invalid
        )
        
        errors = config.validate()
        assert len(errors) == 4
        assert any("does not exist" in error for error in errors)
        assert any("Similarity threshold" in error for error in errors)
        assert any("Coverage threshold" in error for error in errors)
        assert any("Max file moves" in error for error in errors)
    
    def test_register_analyzer(self, tmp_path):
        """Test analyzer registration."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        orchestrator.register_analyzer(MockAnalyzer)
        
        assert len(orchestrator._analyzers) == 1
        assert orchestrator._analyzers[0].name == "mock_analyzer"
        assert isinstance(orchestrator._analyzers[0], MockAnalyzer)
    
    def test_register_cleaner(self, tmp_path):
        """Test cleaner registration."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        orchestrator.register_cleaner(MockCleaner)
        
        assert len(orchestrator._cleaners) == 1
        assert orchestrator._cleaners[0].name == "mock_cleaner"
        assert isinstance(orchestrator._cleaners[0], MockCleaner)
    
    def test_register_validator(self, tmp_path):
        """Test validator registration."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        orchestrator.register_validator(MockValidator)
        
        assert len(orchestrator._validators) == 1
        assert orchestrator._validators[0].name == "mock_validator"
        assert isinstance(orchestrator._validators[0], MockValidator)
    
    def test_register_reporter(self, tmp_path):
        """Test reporter registration."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        orchestrator.register_reporter(MockReporter)
        
        assert len(orchestrator._reporters) == 1
        assert orchestrator._reporters[0].name == "mock_reporter"
        assert isinstance(orchestrator._reporters[0], MockReporter)
    
    def test_should_run_analyzer_logic(self, tmp_path):
        """Test analyzer execution logic based on configuration."""
        config = CheckupConfig(
            target_directory=tmp_path,
            enable_quality_analysis=True,
            enable_duplicate_detection=False,
            enable_import_analysis=True,
            enable_structure_analysis=False
        )
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock analyzers with different names
        quality_analyzer = Mock()
        quality_analyzer.name = "quality_analyzer"
        
        duplicate_analyzer = Mock()
        duplicate_analyzer.name = "duplicate_detector"
        
        import_analyzer = Mock()
        import_analyzer.name = "import_analyzer"
        
        structure_analyzer = Mock()
        structure_analyzer.name = "structure_analyzer"
        
        # Test logic
        assert orchestrator._should_run_analyzer(quality_analyzer) is True
        assert orchestrator._should_run_analyzer(duplicate_analyzer) is False
        assert orchestrator._should_run_analyzer(import_analyzer) is True
        assert orchestrator._should_run_analyzer(structure_analyzer) is False
    
    def test_should_run_cleaner_logic(self, tmp_path):
        """Test cleaner execution logic based on configuration."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            auto_fix_imports=False,
            auto_organize_files=True
        )
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock cleaners with different names
        formatter = Mock()
        formatter.name = "code_formatter"
        
        import_cleaner = Mock()
        import_cleaner.name = "import_cleaner"
        
        file_organizer = Mock()
        file_organizer.name = "file_organizer"
        
        # Test logic
        assert orchestrator._should_run_cleaner(formatter) is True
        assert orchestrator._should_run_cleaner(import_cleaner) is False
        assert orchestrator._should_run_cleaner(file_organizer) is True
    
    def test_should_run_validator_logic(self, tmp_path):
        """Test validator execution logic based on configuration."""
        config = CheckupConfig(
            target_directory=tmp_path,
            check_test_coverage=True,
            validate_configs=False,
            validate_docs=True
        )
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock validators with different names
        coverage_validator = Mock()
        coverage_validator.name = "coverage_validator"
        
        config_validator = Mock()
        config_validator.name = "config_validator"
        
        doc_validator = Mock()
        doc_validator.name = "doc_validator"
        
        # Test logic
        assert orchestrator._should_run_validator(coverage_validator) is True
        assert orchestrator._should_run_validator(config_validator) is False
        assert orchestrator._should_run_validator(doc_validator) is True
    
    def test_should_run_reporter_logic(self, tmp_path):
        """Test reporter execution logic based on configuration."""
        config = CheckupConfig(
            target_directory=tmp_path,
            generate_html_report=True,
            generate_json_report=False,
            generate_markdown_report=True
        )
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock reporters with different names
        html_reporter = Mock()
        html_reporter.name = "html_reporter"
        
        json_reporter = Mock()
        json_reporter.name = "json_reporter"
        
        markdown_reporter = Mock()
        markdown_reporter.name = "markdown_reporter"
        
        # Test logic
        assert orchestrator._should_run_reporter(html_reporter) is True
        assert orchestrator._should_run_reporter(json_reporter) is False
        assert orchestrator._should_run_reporter(markdown_reporter) is True
    
    @pytest.mark.asyncio
    async def test_capture_metrics(self, tmp_path):
        """Test metrics capture functionality."""
        # Create test files
        (tmp_path / "test.py").write_text("print('hello')\n" * 10)
        (tmp_path / "test_module.py").write_text("def test_func():\n    pass\n")
        (tmp_path / "README.md").write_text("# Test\n")
        (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
        
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        metrics = await orchestrator._capture_metrics()
        
        assert metrics.total_files == 4
        assert metrics.python_files == 2
        assert metrics.test_files == 1  # test_module.py contains 'test'
        assert metrics.documentation_files == 1
        assert metrics.config_files == 1
        assert metrics.total_lines > 0
    
    @pytest.mark.asyncio
    async def test_run_analyzer_success(self, tmp_path):
        """Test successful analyzer execution."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        analyzer = MockAnalyzer(config)
        
        with patch.object(analyzer, 'pre_analyze', new_callable=AsyncMock) as mock_pre, \
             patch.object(analyzer, 'post_analyze', new_callable=AsyncMock) as mock_post:
            
            issues, metrics = await orchestrator._run_analyzer(analyzer)
            
            mock_pre.assert_called_once()
            mock_post.assert_called_once()
            assert len(issues) == 1
            assert issues[0].message == "Test issue"
    
    @pytest.mark.asyncio
    async def test_run_analyzer_failure(self, tmp_path):
        """Test analyzer execution with failure."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        analyzer = MockAnalyzer(config)
        
        with patch.object(analyzer, 'analyze', side_effect=Exception("Test error")):
            with pytest.raises(AnalysisError, match="Analyzer mock_analyzer failed: Test error"):
                await orchestrator._run_analyzer(analyzer)
    
    @pytest.mark.asyncio
    async def test_run_validator_success(self, tmp_path):
        """Test successful validator execution."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        validator = MockValidator(config)
        
        with patch.object(validator, 'pre_validate', new_callable=AsyncMock) as mock_pre, \
             patch.object(validator, 'post_validate', new_callable=AsyncMock) as mock_post:
            
            result, metrics = await orchestrator._run_validator(validator)
            
            mock_pre.assert_called_once()
            mock_post.assert_called_once()
            assert result.success is True
    
    def test_merge_issues_into_results(self, tmp_path):
        """Test issue merging functionality."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        results = AnalysisResults()
        
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            severity=IssueSeverity.HIGH,
            issue_type=IssueType.SYNTAX_ERROR,
            message="Syntax error",
            description="Test syntax error"
        )
        
        issues = [quality_issue]
        orchestrator._merge_issues_into_results(results, issues, Mock())
        
        assert len(results.quality_issues) == 1
        assert results.quality_issues[0] == quality_issue
        assert results.total_issues == 1
    
    def test_merge_metrics(self, tmp_path):
        """Test metrics merging functionality."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        target_metrics = CodebaseMetrics(
            syntax_errors=5,
            style_violations=10,
            test_coverage_percentage=70.0
        )
        
        source_metrics = CodebaseMetrics(
            syntax_errors=3,
            style_violations=7,
            test_coverage_percentage=85.0
        )
        
        orchestrator._merge_metrics(target_metrics, source_metrics)
        
        assert target_metrics.syntax_errors == 8  # 5 + 3
        assert target_metrics.style_violations == 17  # 10 + 7
        assert target_metrics.test_coverage_percentage == 85.0  # Max of 70.0 and 85.0


class TestOrchestratorErrorHandling:
    """Test error handling in orchestrator."""
    
    @pytest.mark.asyncio
    async def test_full_checkup_with_config_error(self, tmp_path):
        """Test full checkup with configuration errors."""
        config = CheckupConfig(
            target_directory=Path("/nonexistent"),
            similarity_threshold=2.0  # Invalid
        )
        orchestrator = CodebaseOrchestrator(config)
        
        results = await orchestrator.run_full_checkup()
        
        assert results.success is False
        assert "Configuration errors" in results.error_message
        assert results.analysis is not None
        assert results.cleanup is None
    
    @pytest.mark.asyncio
    async def test_analysis_with_partial_failures(self, tmp_path):
        """Test analysis with some analyzers failing."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register working and failing analyzers
        orchestrator.register_analyzer(MockAnalyzer)
        
        failing_analyzer = Mock()
        failing_analyzer.name = "failing_analyzer"
        failing_analyzer.analyze = AsyncMock(side_effect=Exception("Test failure"))
        orchestrator._analyzers.append(failing_analyzer)
        
        with patch.object(orchestrator, '_should_run_analyzer', return_value=True):
            results = await orchestrator.run_analysis_only()
        
        # Should still get results from working analyzer
        assert len(results.quality_issues) == 1
        assert results.total_issues == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_with_failures(self, tmp_path):
        """Test cleanup with some cleaners failing."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register working and failing cleaners
        orchestrator.register_cleaner(MockCleaner)
        
        failing_cleaner = Mock()
        failing_cleaner.name = "failing_cleaner"
        failing_cleaner.clean = AsyncMock(side_effect=Exception("Cleanup failed"))
        orchestrator._cleaners.append(failing_cleaner)
        
        analysis_results = AnalysisResults()
        
        with patch.object(orchestrator, '_should_run_cleaner', return_value=True):
            results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should still complete despite failures
        assert results is not None
        assert results.total_changes >= 0
    
    @pytest.mark.asyncio
    async def test_report_generation_with_failures(self, tmp_path):
        """Test report generation with some reporters failing."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register working and failing reporters
        orchestrator.register_reporter(MockReporter)
        
        failing_reporter = Mock()
        failing_reporter.name = "failing_reporter"
        failing_reporter.generate_and_save_summary = AsyncMock(side_effect=Exception("Report failed"))
        orchestrator._reporters.append(failing_reporter)
        
        checkup_results = CheckupResults(
            analysis=AnalysisResults(),
            success=True
        )
        
        with patch.object(orchestrator, '_should_run_reporter', return_value=True):
            report_files = await orchestrator.generate_reports(checkup_results)
        
        # Should still get reports from working reporter
        assert len(report_files) == 2  # summary and detailed from MockReporter
        assert "mock_reporter_summary" in report_files
        assert "mock_reporter_detailed" in report_files


if __name__ == "__main__":
    pytest.main([__file__])