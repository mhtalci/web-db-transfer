"""
Integration tests for analysis workflow orchestration.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from migration_assistant.checkup.orchestrator import CodebaseOrchestrator, AnalysisError
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CodebaseMetrics, QualityIssue, 
    ImportIssue, StructureIssue, CoverageGap, ConfigIssue, DocIssue,
    IssueSeverity, IssueType
)
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.validators.base import BaseValidator


class MockQualityAnalyzer(BaseAnalyzer):
    """Mock quality analyzer for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "quality_analyzer"
        self.metrics = CodebaseMetrics(syntax_errors=2, style_violations=5)
    
    async def analyze(self):
        # Simulate some processing time
        await asyncio.sleep(0.1)
        return [
            QualityIssue(
                file_path=Path("test.py"),
                line_number=1,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.SYNTAX_ERROR,
                message="Syntax error found",
                description="Missing closing parenthesis"
            ),
            QualityIssue(
                file_path=Path("test.py"),
                line_number=5,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.STYLE_VIOLATION,
                message="Style violation",
                description="Line too long"
            )
        ]


class MockImportAnalyzer(BaseAnalyzer):
    """Mock import analyzer for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "import_analyzer"
        self.metrics = CodebaseMetrics(unused_imports=3, circular_imports=1)
    
    async def analyze(self):
        await asyncio.sleep(0.1)
        return [
            ImportIssue(
                file_path=Path("module.py"),
                line_number=2,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.UNUSED_IMPORT,
                message="Unused import",
                description="Import 'os' is not used",
                import_name="os"
            )
        ]


class MockStructureAnalyzer(BaseAnalyzer):
    """Mock structure analyzer for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "structure_analyzer"
        self.metrics = CodebaseMetrics(misplaced_files=2, empty_directories=1)
    
    async def analyze(self):
        await asyncio.sleep(0.1)
        return [
            StructureIssue(
                file_path=Path("misplaced.py"),
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.STRUCTURE_ISSUE,
                message="File in wrong location",
                description="This file should be in the utils directory",
                suggested_location=Path("utils/misplaced.py")
            )
        ]


class MockCoverageValidator(BaseValidator):
    """Mock coverage validator for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "coverage_validator"
        self.metrics = CodebaseMetrics(test_coverage_percentage=75.0, untested_functions=5)
    
    async def validate(self):
        await asyncio.sleep(0.1)
        result = Mock()
        result.issues = [
            CoverageGap(
                file_path=Path("uncovered.py"),
                line_number=10,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.COVERAGE_GAP,
                message="Function not covered by tests",
                description="Function 'process_data' has no test coverage",
                function_name="process_data",
                coverage_percentage=0.0
            )
        ]
        result.success = True
        return result


class MockConfigValidator(BaseValidator):
    """Mock config validator for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "config_validator"
        self.metrics = CodebaseMetrics()
    
    async def validate(self):
        await asyncio.sleep(0.1)
        result = Mock()
        result.issues = [
            ConfigIssue(
                file_path=Path("pyproject.toml"),
                line_number=15,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing configuration",
                description="Black configuration is missing",
                config_file=Path("pyproject.toml"),
                config_section="tool.black"
            )
        ]
        result.success = True
        return result


class TestAnalysisWorkflowIntegration:
    """Test complete analysis workflow integration."""
    
    @pytest.mark.asyncio
    async def test_full_analysis_workflow_success(self, tmp_path):
        """Test successful execution of complete analysis workflow."""
        config = CheckupConfig(
            target_directory=tmp_path,
            enable_quality_analysis=True,
            enable_import_analysis=True,
            enable_structure_analysis=True,
            check_test_coverage=True,
            validate_configs=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Register all analyzers and validators
        orchestrator.register_analyzer(MockQualityAnalyzer)
        orchestrator.register_analyzer(MockImportAnalyzer)
        orchestrator.register_analyzer(MockStructureAnalyzer)
        orchestrator.register_validator(MockCoverageValidator)
        orchestrator.register_validator(MockConfigValidator)
        
        # Run analysis
        results = await orchestrator.run_analysis_only()
        
        # Verify results
        assert isinstance(results, AnalysisResults)
        assert results.total_issues == 5  # 2 quality + 1 import + 1 structure + 1 coverage + 1 config
        
        # Verify specific issue types
        assert len(results.quality_issues) == 2
        assert len(results.import_issues) == 1
        assert len(results.structure_issues) == 1
        assert len(results.coverage_gaps) == 1
        assert len(results.config_issues) == 1
        
        # Verify metrics aggregation
        assert results.metrics.syntax_errors == 2
        assert results.metrics.style_violations == 5
        assert results.metrics.unused_imports == 3
        assert results.metrics.circular_imports == 1
        assert results.metrics.misplaced_files == 2
        assert results.metrics.empty_directories == 1
        assert results.metrics.test_coverage_percentage == 75.0
        assert results.metrics.untested_functions == 5
        
        # Verify timing
        assert results.duration > timedelta(0)
        assert results.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_parallel_analyzer_execution(self, tmp_path):
        """Test that analyzers run in parallel."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register multiple analyzers
        orchestrator.register_analyzer(MockQualityAnalyzer)
        orchestrator.register_analyzer(MockImportAnalyzer)
        orchestrator.register_analyzer(MockStructureAnalyzer)
        
        start_time = datetime.now()
        results = await orchestrator.run_analysis_only()
        end_time = datetime.now()
        
        # If run sequentially, would take ~0.3s (3 * 0.1s)
        # If run in parallel, should take ~0.1s plus overhead
        duration = (end_time - start_time).total_seconds()
        
        # Allow for some overhead but should be significantly less than sequential
        assert duration < 0.25, f"Expected parallel execution, but took {duration}s"
        assert results.total_issues == 3  # 2 quality + 1 import + 1 structure
    
    @pytest.mark.asyncio
    async def test_parallel_validator_execution(self, tmp_path):
        """Test that validators run in parallel."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register multiple validators
        orchestrator.register_validator(MockCoverageValidator)
        orchestrator.register_validator(MockConfigValidator)
        
        start_time = datetime.now()
        results = await orchestrator.run_analysis_only()
        end_time = datetime.now()
        
        # If run sequentially, would take ~0.2s (2 * 0.1s)
        # If run in parallel, should take ~0.1s plus overhead
        duration = (end_time - start_time).total_seconds()
        
        assert duration < 0.2, f"Expected parallel execution, but took {duration}s"
        assert results.total_issues == 2  # 1 coverage + 1 config
    
    @pytest.mark.asyncio
    async def test_analysis_with_disabled_components(self, tmp_path):
        """Test analysis workflow with some components disabled."""
        config = CheckupConfig(
            target_directory=tmp_path,
            enable_quality_analysis=True,
            enable_import_analysis=False,  # Disabled
            enable_structure_analysis=True,
            check_test_coverage=False,  # Disabled
            validate_configs=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Register all components
        orchestrator.register_analyzer(MockQualityAnalyzer)
        orchestrator.register_analyzer(MockImportAnalyzer)  # Should not run
        orchestrator.register_analyzer(MockStructureAnalyzer)
        orchestrator.register_validator(MockCoverageValidator)  # Should not run
        orchestrator.register_validator(MockConfigValidator)
        
        results = await orchestrator.run_analysis_only()
        
        # Should only have results from enabled components
        assert len(results.quality_issues) == 2  # Quality enabled
        assert len(results.import_issues) == 0   # Import disabled
        assert len(results.structure_issues) == 1  # Structure enabled
        assert len(results.coverage_gaps) == 0   # Coverage disabled
        assert len(results.config_issues) == 1   # Config enabled
        
        assert results.total_issues == 3
    
    @pytest.mark.asyncio
    async def test_analysis_with_component_failures(self, tmp_path):
        """Test analysis workflow with some component failures."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register working and failing components
        orchestrator.register_analyzer(MockQualityAnalyzer)
        
        # Add failing analyzer
        failing_analyzer = Mock()
        failing_analyzer.name = "failing_analyzer"
        failing_analyzer.analyze = AsyncMock(side_effect=Exception("Analyzer failed"))
        orchestrator._analyzers.append(failing_analyzer)
        
        orchestrator.register_validator(MockCoverageValidator)
        
        # Add failing validator
        failing_validator = Mock()
        failing_validator.name = "failing_validator"
        failing_validator.validate = AsyncMock(side_effect=Exception("Validator failed"))
        orchestrator._validators.append(failing_validator)
        
        with patch.object(orchestrator, '_should_run_analyzer', return_value=True), \
             patch.object(orchestrator, '_should_run_validator', return_value=True):
            
            results = await orchestrator.run_analysis_only()
        
        # Should still get results from working components
        assert len(results.quality_issues) == 2  # From working analyzer
        assert len(results.coverage_gaps) == 1   # From working validator
        assert results.total_issues == 3
    
    @pytest.mark.asyncio
    async def test_progress_tracking_logging(self, tmp_path, caplog):
        """Test that progress tracking produces appropriate log messages."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        orchestrator.register_analyzer(MockQualityAnalyzer)
        orchestrator.register_analyzer(MockImportAnalyzer)
        orchestrator.register_validator(MockCoverageValidator)
        
        with caplog.at_level("INFO"):
            await orchestrator.run_analysis_only()
        
        # Check for progress messages
        log_messages = [record.message for record in caplog.records]
        
        assert any("Running analysis with" in msg for msg in log_messages)
        assert any("Starting analyzer phase" in msg for msg in log_messages)
        assert any("Starting validator phase" in msg for msg in log_messages)
        assert any("Completed quality_analyzer" in msg for msg in log_messages)
        assert any("Completed import_analyzer" in msg for msg in log_messages)
        assert any("Completed coverage_validator" in msg for msg in log_messages)
        assert any("Progress:" in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, tmp_path):
        """Test that metrics are properly aggregated from all components."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Create analyzers with specific metrics
        analyzer1 = MockQualityAnalyzer(config)
        analyzer1.metrics = CodebaseMetrics(syntax_errors=3, style_violations=7)
        
        analyzer2 = MockImportAnalyzer(config)
        analyzer2.metrics = CodebaseMetrics(unused_imports=5, circular_imports=2)
        
        validator1 = MockCoverageValidator(config)
        validator1.metrics = CodebaseMetrics(test_coverage_percentage=80.0, untested_functions=10)
        
        orchestrator._analyzers = [analyzer1, analyzer2]
        orchestrator._validators = [validator1]
        
        with patch.object(orchestrator, '_should_run_analyzer', return_value=True), \
             patch.object(orchestrator, '_should_run_validator', return_value=True):
            
            results = await orchestrator.run_analysis_only()
        
        # Verify metrics aggregation
        assert results.metrics.syntax_errors == 3
        assert results.metrics.style_violations == 7
        assert results.metrics.unused_imports == 5
        assert results.metrics.circular_imports == 2
        assert results.metrics.test_coverage_percentage == 80.0  # Max value
        assert results.metrics.untested_functions == 10
    
    @pytest.mark.asyncio
    async def test_empty_analysis_workflow(self, tmp_path):
        """Test analysis workflow with no registered components."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # No components registered
        results = await orchestrator.run_analysis_only()
        
        assert isinstance(results, AnalysisResults)
        assert results.total_issues == 0
        assert len(results.quality_issues) == 0
        assert len(results.import_issues) == 0
        assert len(results.structure_issues) == 0
        assert len(results.coverage_gaps) == 0
        assert len(results.config_issues) == 0
        assert len(results.doc_issues) == 0
        
        # Should still have timing information
        assert results.duration > timedelta(0)
        assert results.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_analysis_error_handling(self, tmp_path):
        """Test error handling during analysis workflow."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Create analyzer that fails during pre_analyze
        failing_analyzer = Mock()
        failing_analyzer.name = "failing_analyzer"
        failing_analyzer.pre_analyze = AsyncMock(side_effect=Exception("Pre-analyze failed"))
        orchestrator._analyzers = [failing_analyzer]
        
        with patch.object(orchestrator, '_should_run_analyzer', return_value=True):
            results = await orchestrator.run_analysis_only()
        
        # Should complete despite failure
        assert isinstance(results, AnalysisResults)
        assert results.total_issues == 0  # No successful results
    
    @pytest.mark.asyncio
    async def test_issue_type_distribution(self, tmp_path):
        """Test that different issue types are properly distributed."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        orchestrator.register_analyzer(MockQualityAnalyzer)
        orchestrator.register_analyzer(MockImportAnalyzer)
        orchestrator.register_analyzer(MockStructureAnalyzer)
        orchestrator.register_validator(MockCoverageValidator)
        orchestrator.register_validator(MockConfigValidator)
        
        results = await orchestrator.run_analysis_only()
        
        # Verify issue distribution
        severity_counts = {}
        for issue_list in [results.quality_issues, results.import_issues, 
                          results.structure_issues, results.coverage_gaps, 
                          results.config_issues]:
            for issue in issue_list:
                severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        
        # Should have issues of different severities
        assert IssueSeverity.HIGH in severity_counts
        assert IssueSeverity.MEDIUM in severity_counts
        assert IssueSeverity.LOW in severity_counts
        
        # Verify critical issues property
        critical_issues = results.critical_issues
        assert isinstance(critical_issues, list)


if __name__ == "__main__":
    pytest.main([__file__])