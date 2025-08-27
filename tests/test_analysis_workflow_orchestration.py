"""
Integration Tests for Analysis Workflow Orchestration

Tests the complete analysis pipeline with parallel processing and progress tracking.
"""

import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from migration_assistant.checkup.orchestrator import CodebaseOrchestrator
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, QualityIssue, ImportIssue, 
    IssueSeverity, IssueType, CodebaseMetrics
)
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.validators.base import BaseValidator


class MockAnalyzer(BaseAnalyzer):
    """Mock analyzer for testing."""
    
    def __init__(self, config: CheckupConfig, name: str = "MockAnalyzer", 
                 issues_to_return: list = None, delay: float = 0.1):
        super().__init__(config)
        self._name = name
        self._issues_to_return = issues_to_return or []
        self._delay = delay
        self._analyze_called = False
        self._pre_analyze_called = False
        self._post_analyze_called = False
    
    @property
    def name(self) -> str:
        return self._name
    
    def get_supported_file_types(self) -> list:
        return ['.py']
    
    async def analyze(self) -> list:
        """Mock analysis that returns predefined issues."""
        await asyncio.sleep(self._delay)  # Simulate work
        self._analyze_called = True
        
        # Update metrics
        self.update_metrics(syntax_errors=len(self._issues_to_return))
        
        return self._issues_to_return
    
    async def pre_analyze(self) -> None:
        self._pre_analyze_called = True
    
    async def post_analyze(self, issues: list) -> None:
        self._post_analyze_called = True


class MockValidator(BaseValidator):
    """Mock validator for testing."""
    
    def __init__(self, config: CheckupConfig, name: str = "MockValidator", 
                 issues_to_return: list = None, delay: float = 0.1):
        super().__init__(config)
        self._name = name
        self._issues_to_return = issues_to_return or []
        self._delay = delay
        self._validate_called = False
        self._pre_validate_called = False
        self._post_validate_called = False
    
    @property
    def name(self) -> str:
        return self._name
    
    async def validate(self):
        """Mock validation that returns predefined issues."""
        await asyncio.sleep(self._delay)  # Simulate work
        self._validate_called = True
        
        # Update metrics
        self.update_metrics(config_issues=len(self._issues_to_return))
        
        # Return mock validation result
        result = Mock()
        result.issues = self._issues_to_return
        return result
    
    async def pre_validate(self) -> None:
        self._pre_validate_called = True
    
    async def post_validate(self, result) -> None:
        self._post_validate_called = True


class FailingAnalyzer(BaseAnalyzer):
    """Analyzer that always fails for testing error handling."""
    
    def __init__(self, config: CheckupConfig, name: str = "FailingAnalyzer"):
        super().__init__(config)
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
    def get_supported_file_types(self) -> list:
        return ['.py']
    
    async def analyze(self) -> list:
        raise Exception("Simulated analyzer failure")


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with sample files."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create sample Python files
    (temp_dir / "main.py").write_text("""
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
""")
    
    (temp_dir / "utils.py").write_text("""
import os
import sys

def get_project_root():
    return os.path.dirname(__file__)
""")
    
    (temp_dir / "tests").mkdir()
    (temp_dir / "tests" / "test_main.py").write_text("""
import unittest
from main import hello_world

class TestMain(unittest.TestCase):
    def test_hello_world(self):
        # This should not raise an exception
        hello_world()
""")
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def checkup_config(temp_project_dir):
    """Create a checkup configuration for testing."""
    return CheckupConfig(
        target_directory=temp_project_dir,
        enable_quality_analysis=True,
        enable_duplicate_detection=True,
        enable_import_analysis=True,
        enable_structure_analysis=True,
        check_test_coverage=True,
        validate_configs=True,
        validate_docs=True,
        dry_run=True,  # Don't make actual changes during tests
        create_backup=False,  # Don't create backups during tests
    )


@pytest.mark.asyncio
class TestAnalysisWorkflowOrchestration:
    """Test suite for analysis workflow orchestration."""
    
    async def test_parallel_analysis_with_multiple_analyzers(self, checkup_config):
        """Test parallel execution of multiple analyzers."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Create sample issues
        quality_issue = QualityIssue(
            file_path=Path("main.py"),
            line_number=1,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.STYLE_VIOLATION,
            message="Line too long",
            description="Line exceeds maximum length"
        )
        
        import_issue = ImportIssue(
            file_path=Path("utils.py"),
            line_number=2,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.UNUSED_IMPORT,
            message="Unused import",
            description="Import 'sys' is not used",
            import_name="sys"
        )
        
        # Register mock analyzers with different delays
        analyzer1 = MockAnalyzer(checkup_config, "QualityAnalyzer", [quality_issue], delay=0.1)
        analyzer2 = MockAnalyzer(checkup_config, "ImportAnalyzer", [import_issue], delay=0.2)
        analyzer3 = MockAnalyzer(checkup_config, "StructureAnalyzer", [], delay=0.15)
        
        orchestrator.register_analyzer(type(analyzer1))
        orchestrator.register_analyzer(type(analyzer2))
        orchestrator.register_analyzer(type(analyzer3))
        
        # Replace registered analyzers with our mocks
        orchestrator._analyzers = [analyzer1, analyzer2, analyzer3]
        
        # Run analysis
        start_time = datetime.now()
        results = await orchestrator.run_analysis_only()
        end_time = datetime.now()
        
        # Verify parallel execution (should be faster than sequential)
        total_delay = 0.1 + 0.2 + 0.15  # 0.45 seconds if sequential
        actual_duration = (end_time - start_time).total_seconds()
        assert actual_duration < total_delay, f"Expected parallel execution, but took {actual_duration}s"
        
        # Verify all analyzers were called
        assert analyzer1._analyze_called
        assert analyzer2._analyze_called
        assert analyzer3._analyze_called
        
        # Verify pre/post analyze hooks were called
        assert analyzer1._pre_analyze_called
        assert analyzer1._post_analyze_called
        
        # Verify results contain issues from all analyzers
        assert len(results.quality_issues) == 1
        assert len(results.import_issues) == 1
        assert results.total_issues == 2
        
        # Verify metrics were merged
        assert results.metrics.syntax_errors == 2  # 1 from each analyzer with issues
    
    async def test_parallel_analysis_with_validators(self, checkup_config):
        """Test parallel execution of analyzers and validators."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Create sample issues
        quality_issue = QualityIssue(
            file_path=Path("main.py"),
            line_number=1,
            severity=IssueSeverity.HIGH,
            issue_type=IssueType.CODE_SMELL,
            message="Code smell detected",
            description="Complex function detected"
        )
        
        # Register mock components
        analyzer = MockAnalyzer(checkup_config, "QualityAnalyzer", [quality_issue], delay=0.1)
        validator = MockValidator(checkup_config, "ConfigValidator", [], delay=0.1)
        
        orchestrator._analyzers = [analyzer]
        orchestrator._validators = [validator]
        
        # Run analysis
        results = await orchestrator.run_analysis_only()
        
        # Verify both components were executed
        assert analyzer._analyze_called
        assert validator._validate_called
        
        # Verify hooks were called
        assert analyzer._pre_analyze_called
        assert analyzer._post_analyze_called
        assert validator._pre_validate_called
        assert validator._post_validate_called
        
        # Verify results
        assert len(results.quality_issues) == 1
        assert results.total_issues == 1
    
    async def test_error_handling_in_parallel_analysis(self, checkup_config):
        """Test error handling when some analyzers fail."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Create mix of working and failing analyzers
        working_analyzer = MockAnalyzer(checkup_config, "WorkingAnalyzer", [], delay=0.1)
        failing_analyzer = FailingAnalyzer(checkup_config, "FailingAnalyzer")
        
        orchestrator._analyzers = [working_analyzer, failing_analyzer]
        
        # Run analysis - should not raise exception
        results = await orchestrator.run_analysis_only()
        
        # Verify working analyzer completed
        assert working_analyzer._analyze_called
        
        # Verify results are still returned despite failure
        assert isinstance(results, AnalysisResults)
        assert results.total_issues == 0  # No issues from working analyzer
    
    async def test_progress_tracking_and_status_reporting(self, checkup_config):
        """Test progress tracking and status reporting functionality."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Register multiple components with different delays
        analyzers = [
            MockAnalyzer(checkup_config, f"Analyzer{i}", [], delay=0.1) 
            for i in range(3)
        ]
        validators = [
            MockValidator(checkup_config, f"Validator{i}", [], delay=0.1) 
            for i in range(2)
        ]
        
        orchestrator._analyzers = analyzers
        orchestrator._validators = validators
        
        # Get initial status
        initial_status = orchestrator.get_analysis_status()
        assert initial_status["components"]["analyzers"] == [
            {"name": f"Analyzer{i}", "type": "MockAnalyzer"} for i in range(3)
        ]
        assert initial_status["components"]["validators"] == [
            {"name": f"Validator{i}", "type": "MockValidator"} for i in range(2)
        ]
        assert not initial_status["current_state"]["analysis_results"]
        
        # Run analysis and verify progress tracking
        with patch.object(orchestrator, '_log_structured') as mock_log:
            results = await orchestrator.run_analysis_only()
            
            # Verify progress logging calls were made
            progress_calls = [
                call for call in mock_log.call_args_list 
                if len(call[0]) > 1 and "progress" in str(call[0][1])
            ]
            assert len(progress_calls) > 0, "Expected progress tracking log calls"
        
        # Verify final results
        assert isinstance(results, AnalysisResults)
        assert results.duration > timedelta(0)
        
        # Get final status
        orchestrator._analysis_results = results
        final_status = orchestrator.get_analysis_status()
        assert final_status["current_state"]["analysis_results"]
    
    async def test_component_filtering_based_on_config(self, checkup_config):
        """Test that components are filtered based on configuration."""
        # Disable some analysis types
        checkup_config.enable_quality_analysis = False
        checkup_config.check_test_coverage = False
        
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Register analyzers and validators
        quality_analyzer = MockAnalyzer(checkup_config, "QualityAnalyzer")
        import_analyzer = MockAnalyzer(checkup_config, "ImportAnalyzer")
        coverage_validator = MockValidator(checkup_config, "CoverageValidator")
        config_validator = MockValidator(checkup_config, "ConfigValidator")
        
        orchestrator._analyzers = [quality_analyzer, import_analyzer]
        orchestrator._validators = [coverage_validator, config_validator]
        
        # Run analysis
        results = await orchestrator.run_analysis_only()
        
        # Verify only enabled components ran
        assert not quality_analyzer._analyze_called  # Quality analysis disabled
        assert import_analyzer._analyze_called  # Import analysis enabled
        assert not coverage_validator._validate_called  # Coverage validation disabled
        assert config_validator._validate_called  # Config validation enabled
    
    async def test_metrics_aggregation_across_components(self, checkup_config):
        """Test that metrics are properly aggregated across all components."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Create analyzers that will update different metrics
        analyzer1 = MockAnalyzer(checkup_config, "Analyzer1", [], delay=0.05)
        analyzer2 = MockAnalyzer(checkup_config, "Analyzer2", [], delay=0.05)
        
        # Mock the analyze methods to update specific metrics
        async def analyzer1_analyze():
            analyzer1.update_metrics(syntax_errors=2, style_violations=3)
            return []
        
        async def analyzer2_analyze():
            analyzer2.update_metrics(syntax_errors=1, unused_imports=4)
            return []
        
        analyzer1.analyze = analyzer1_analyze
        analyzer2.analyze = analyzer2_analyze
        
        orchestrator._analyzers = [analyzer1, analyzer2]
        
        # Run analysis
        results = await orchestrator.run_analysis_only()
        
        # Verify metrics were aggregated correctly
        assert results.metrics.syntax_errors == 3  # 2 + 1
        assert results.metrics.style_violations == 3  # 3 + 0
        assert results.metrics.unused_imports == 4  # 0 + 4
    
    async def test_full_analysis_workflow_integration(self, checkup_config):
        """Test the complete analysis workflow from start to finish."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Create comprehensive test scenario
        quality_issues = [
            QualityIssue(
                file_path=Path("main.py"),
                line_number=1,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.COMPLEXITY,
                message="High complexity",
                description="Function has high cyclomatic complexity"
            )
        ]
        
        import_issues = [
            ImportIssue(
                file_path=Path("utils.py"),
                line_number=1,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.CIRCULAR_IMPORT,
                message="Circular import",
                description="Circular import detected",
                import_name="circular_module",
                is_circular=True
            )
        ]
        
        # Register comprehensive set of components
        quality_analyzer = MockAnalyzer(checkup_config, "QualityAnalyzer", quality_issues)
        import_analyzer = MockAnalyzer(checkup_config, "ImportAnalyzer", import_issues)
        structure_analyzer = MockAnalyzer(checkup_config, "StructureAnalyzer", [])
        
        coverage_validator = MockValidator(checkup_config, "CoverageValidator", [])
        config_validator = MockValidator(checkup_config, "ConfigValidator", [])
        
        orchestrator._analyzers = [quality_analyzer, import_analyzer, structure_analyzer]
        orchestrator._validators = [coverage_validator, config_validator]
        
        # Run complete analysis workflow
        start_time = datetime.now()
        results = await orchestrator.run_analysis_only()
        end_time = datetime.now()
        
        # Verify comprehensive results
        assert isinstance(results, AnalysisResults)
        assert results.total_issues == 2
        assert len(results.quality_issues) == 1
        assert len(results.import_issues) == 1
        assert len(results.critical_issues) == 0  # No critical issues in test data
        
        # Verify timing information
        assert results.duration > timedelta(0)
        assert results.timestamp >= start_time
        assert results.timestamp <= end_time
        
        # Verify all components were executed
        for analyzer in [quality_analyzer, import_analyzer, structure_analyzer]:
            assert analyzer._analyze_called
            assert analyzer._pre_analyze_called
            assert analyzer._post_analyze_called
        
        for validator in [coverage_validator, config_validator]:
            assert validator._validate_called
            assert validator._pre_validate_called
            assert validator._post_validate_called
        
        # Verify metrics aggregation
        assert results.metrics.syntax_errors >= 0
        assert results.metrics.timestamp <= datetime.now()


if __name__ == "__main__":
    pytest.main([__file__])