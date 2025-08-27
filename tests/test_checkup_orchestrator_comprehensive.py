"""
Comprehensive unit tests for checkup orchestrator.

Tests the main orchestration engine to ensure 90%+ code coverage.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from migration_assistant.checkup.orchestrator import CodebaseOrchestrator
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CleanupResults, CheckupResults,
    QualityIssue, Duplicate, ImportIssue, StructureIssue, CoverageGap,
    ConfigIssue, DocIssue, CodebaseMetrics, IssueType, IssueSeverity,
    FormattingChange, FileMove, FileRemoval
)


class TestCodebaseOrchestrator:
    """Test cases for CodebaseOrchestrator."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
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
            dry_run=False,
            create_backup=True,
            output_directory=Path("/tmp/reports")
        )
    
    @pytest.fixture
    def orchestrator(self, config):
        """Create CodebaseOrchestrator instance."""
        return CodebaseOrchestrator(config)
    
    @pytest.fixture
    def sample_metrics(self):
        """Create sample codebase metrics."""
        return CodebaseMetrics(
            total_files=10,
            total_lines=1000,
            python_files=8,
            test_files=4,
            syntax_errors=2,
            style_violations=15,
            complexity_issues=3,
            duplicate_blocks=4,
            unused_imports=8,
            circular_imports=1,
            orphaned_modules=2,
            test_coverage_percentage=75.0,
            untested_functions=10,
            config_issues=3,
            doc_issues=5
        )
    
    @pytest.fixture
    def sample_analysis_results(self, sample_metrics):
        """Create sample analysis results."""
        quality_issues = [
            QualityIssue(
                file_path=Path("test.py"),
                line_number=10,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Line too long"
            ),
            QualityIssue(
                file_path=Path("main.py"),
                line_number=25,
                issue_type=IssueType.COMPLEXITY_HIGH,
                severity=IssueSeverity.HIGH,
                description="Function too complex"
            )
        ]
        
        import_issues = [
            ImportIssue(
                file_path=Path("utils.py"),
                line_number=5,
                issue_type=IssueType.UNUSED_IMPORT,
                severity=IssueSeverity.LOW,
                module_name="unused_module",
                description="Unused import"
            )
        ]
        
        return AnalysisResults(
            quality_issues=quality_issues,
            duplicates=[],
            import_issues=import_issues,
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=sample_metrics
        )
    
    def test_initialization(self, orchestrator, config):
        """Test orchestrator initialization."""
        assert orchestrator.config == config
        assert orchestrator.target_directory == config.target_directory
        assert orchestrator.analyzers == {}
        assert orchestrator.cleaners == {}
        assert orchestrator.validators == {}
        assert orchestrator.reporters == {}
    
    @pytest.mark.asyncio
    async def test_initialize_components(self, orchestrator):
        """Test component initialization."""
        await orchestrator._initialize_components()
        
        # Check that components were initialized
        assert len(orchestrator.analyzers) > 0
        assert len(orchestrator.cleaners) > 0
        assert len(orchestrator.validators) > 0
        assert len(orchestrator.reporters) > 0
        
        # Check specific components based on config
        if orchestrator.config.enable_quality_analysis:
            assert 'quality' in orchestrator.analyzers
        if orchestrator.config.enable_duplicate_detection:
            assert 'duplicates' in orchestrator.analyzers
        if orchestrator.config.enable_import_analysis:
            assert 'imports' in orchestrator.analyzers
        if orchestrator.config.enable_structure_analysis:
            assert 'structure' in orchestrator.analyzers
    
    @pytest.mark.asyncio
    async def test_run_analysis_only(self, orchestrator, sample_analysis_results):
        """Test running analysis only."""
        # Mock analyzers and validators
        mock_quality_analyzer = AsyncMock()
        mock_quality_analyzer.analyze.return_value = sample_analysis_results.quality_issues
        
        mock_import_analyzer = AsyncMock()
        mock_import_analyzer.analyze.return_value = sample_analysis_results.import_issues
        
        mock_coverage_validator = AsyncMock()
        mock_coverage_validator.validate.return_value = Mock(success=True, issues_found=0)
        
        orchestrator.analyzers = {
            'quality': mock_quality_analyzer,
            'imports': mock_import_analyzer
        }
        orchestrator.validators = {
            'coverage': mock_coverage_validator
        }
        
        with patch.object(orchestrator, '_calculate_metrics') as mock_metrics:
            mock_metrics.return_value = sample_analysis_results.metrics
            
            results = await orchestrator.run_analysis_only()
            
            assert isinstance(results, AnalysisResults)
            assert len(results.quality_issues) == 2
            assert len(results.import_issues) == 1
            assert results.metrics.total_files == 10
    
    @pytest.mark.asyncio
    async def test_run_cleanup_only(self, orchestrator, sample_analysis_results):
        """Test running cleanup only."""
        # Mock cleaners
        mock_formatter = AsyncMock()
        mock_formatter.can_clean_issue.return_value = True
        mock_formatter.clean.return_value = Mock(
            success=True,
            files_modified=[Path("test.py")],
            formatting_changes=[
                FormattingChange(
                    file_path=Path("test.py"),
                    change_type="formatting",
                    lines_changed=5,
                    description="Applied black formatting"
                )
            ]
        )
        
        mock_import_cleaner = AsyncMock()
        mock_import_cleaner.can_clean_issue.return_value = True
        mock_import_cleaner.clean.return_value = Mock(
            success=True,
            files_modified=[Path("utils.py")],
            import_cleanups=[]
        )
        
        orchestrator.cleaners = {
            'formatter': mock_formatter,
            'imports': mock_import_cleaner
        }
        
        results = await orchestrator.run_cleanup_only(sample_analysis_results)
        
        assert isinstance(results, CleanupResults)
        assert results.success is True
        assert len(results.files_modified) > 0
    
    @pytest.mark.asyncio
    async def test_run_full_checkup(self, orchestrator, sample_analysis_results):
        """Test running full checkup workflow."""
        # Mock the analysis and cleanup methods
        with patch.object(orchestrator, 'run_analysis_only') as mock_analysis:
            with patch.object(orchestrator, 'run_cleanup_only') as mock_cleanup:
                with patch.object(orchestrator, 'generate_reports') as mock_reports:
                    
                    mock_analysis.return_value = sample_analysis_results
                    mock_cleanup.return_value = CleanupResults(
                        success=True,
                        files_modified=[Path("test.py")],
                        formatting_changes=[],
                        import_cleanups=[],
                        file_moves=[],
                        removals=[],
                        fixes_applied=[],
                        timestamp=datetime.now()
                    )
                    mock_reports.return_value = Mock(success=True)
                    
                    results = await orchestrator.run_full_checkup()
                    
                    assert isinstance(results, CheckupResults)
                    assert results.success is True
                    assert results.analysis is not None
                    assert results.cleanup is not None
                    assert isinstance(results.duration, timedelta)
    
    @pytest.mark.asyncio
    async def test_generate_reports(self, orchestrator, sample_analysis_results):
        """Test report generation."""
        # Create checkup results
        cleanup_results = CleanupResults(
            success=True,
            files_modified=[Path("test.py")],
            formatting_changes=[],
            import_cleanups=[],
            file_moves=[],
            removals=[],
            fixes_applied=[],
            timestamp=datetime.now()
        )
        
        checkup_results = CheckupResults(
            analysis=sample_analysis_results,
            cleanup=cleanup_results,
            before_metrics=sample_analysis_results.metrics,
            after_metrics=sample_analysis_results.metrics,
            duration=timedelta(seconds=30),
            success=True
        )
        
        # Mock reporters
        mock_html_reporter = Mock()
        mock_html_reporter.generate_summary_report.return_value = "<html>Summary</html>"
        mock_html_reporter.generate_detailed_report.return_value = "<html>Details</html>"
        
        mock_json_reporter = Mock()
        mock_json_reporter.generate_summary_report.return_value = '{"summary": true}'
        mock_json_reporter.generate_detailed_report.return_value = '{"details": true}'
        
        mock_markdown_reporter = Mock()
        mock_markdown_reporter.generate_summary_report.return_value = "# Summary"
        mock_markdown_reporter.generate_detailed_report.return_value = "# Details"
        
        orchestrator.reporters = {
            'html': mock_html_reporter,
            'json': mock_json_reporter,
            'markdown': mock_markdown_reporter
        }
        
        with patch('pathlib.Path.write_text') as mock_write:
            result = await orchestrator.generate_reports(checkup_results)
            
            assert result.success is True
            assert mock_write.call_count >= 3  # At least one report per format
    
    def test_calculate_metrics(self, orchestrator, tmp_path):
        """Test metrics calculation."""
        # Create test files
        (tmp_path / "main.py").write_text("def main():\n    print('hello')\n    return True")
        (tmp_path / "utils.py").write_text("def helper():\n    pass")
        (tmp_path / "test_main.py").write_text("def test_main():\n    assert True")
        (tmp_path / "README.md").write_text("# Test Project")
        
        orchestrator.target_directory = tmp_path
        
        # Mock analysis results
        quality_issues = [
            QualityIssue(
                file_path=tmp_path / "main.py",
                line_number=1,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Missing docstring"
            )
        ]
        
        metrics = orchestrator._calculate_metrics(
            quality_issues=quality_issues,
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[]
        )
        
        assert isinstance(metrics, CodebaseMetrics)
        assert metrics.total_files >= 3  # At least the Python files
        assert metrics.python_files >= 2  # main.py and utils.py
        assert metrics.test_files >= 1  # test_main.py
        assert metrics.style_violations == 1
    
    def test_filter_components_by_config(self, orchestrator):
        """Test filtering components based on configuration."""
        # Disable some analysis types
        orchestrator.config.enable_quality_analysis = False
        orchestrator.config.enable_duplicate_detection = False
        orchestrator.config.check_test_coverage = False
        
        # Mock components
        all_analyzers = {
            'quality': Mock(),
            'duplicates': Mock(),
            'imports': Mock(),
            'structure': Mock()
        }
        
        all_validators = {
            'coverage': Mock(),
            'config': Mock(),
            'docs': Mock()
        }
        
        filtered_analyzers = orchestrator._filter_components_by_config(all_analyzers, 'analyzers')
        filtered_validators = orchestrator._filter_components_by_config(all_validators, 'validators')
        
        # Should exclude disabled components
        assert 'quality' not in filtered_analyzers
        assert 'duplicates' not in filtered_analyzers
        assert 'imports' in filtered_analyzers  # Still enabled
        assert 'structure' in filtered_analyzers  # Still enabled
        
        assert 'coverage' not in filtered_validators
        assert 'config' in filtered_validators  # Still enabled
        assert 'docs' in filtered_validators  # Still enabled
    
    @pytest.mark.asyncio
    async def test_run_analyzers_parallel(self, orchestrator):
        """Test running analyzers in parallel."""
        # Mock analyzers
        mock_analyzer1 = AsyncMock()
        mock_analyzer1.analyze.return_value = [
            QualityIssue(
                file_path=Path("test1.py"),
                line_number=1,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Issue 1"
            )
        ]
        
        mock_analyzer2 = AsyncMock()
        mock_analyzer2.analyze.return_value = [
            QualityIssue(
                file_path=Path("test2.py"),
                line_number=1,
                issue_type=IssueType.COMPLEXITY_HIGH,
                severity=IssueSeverity.HIGH,
                description="Issue 2"
            )
        ]
        
        orchestrator.analyzers = {
            'analyzer1': mock_analyzer1,
            'analyzer2': mock_analyzer2
        }
        
        results = await orchestrator._run_analyzers_parallel()
        
        assert 'analyzer1' in results
        assert 'analyzer2' in results
        assert len(results['analyzer1']) == 1
        assert len(results['analyzer2']) == 1
        
        # Verify analyzers were called
        mock_analyzer1.analyze.assert_called_once()
        mock_analyzer2.analyze.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_validators_parallel(self, orchestrator):
        """Test running validators in parallel."""
        # Mock validators
        mock_validator1 = AsyncMock()
        mock_validator1.validate.return_value = Mock(
            success=True,
            issues_found=2,
            details={'coverage': 80.0}
        )
        
        mock_validator2 = AsyncMock()
        mock_validator2.validate.return_value = Mock(
            success=True,
            issues_found=1,
            details={'config_errors': 1}
        )
        
        orchestrator.validators = {
            'validator1': mock_validator1,
            'validator2': mock_validator2
        }
        
        results = await orchestrator._run_validators_parallel()
        
        assert 'validator1' in results
        assert 'validator2' in results
        assert results['validator1'].success is True
        assert results['validator2'].success is True
        
        # Verify validators were called
        mock_validator1.validate.assert_called_once()
        mock_validator2.validate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_cleaners_sequential(self, orchestrator, sample_analysis_results):
        """Test running cleaners sequentially."""
        # Mock cleaners
        mock_cleaner1 = AsyncMock()
        mock_cleaner1.can_clean_issue.return_value = True
        mock_cleaner1.clean.return_value = Mock(
            success=True,
            files_modified=[Path("test1.py")],
            message="Cleaner 1 completed"
        )
        
        mock_cleaner2 = AsyncMock()
        mock_cleaner2.can_clean_issue.return_value = True
        mock_cleaner2.clean.return_value = Mock(
            success=True,
            files_modified=[Path("test2.py")],
            message="Cleaner 2 completed"
        )
        
        orchestrator.cleaners = {
            'cleaner1': mock_cleaner1,
            'cleaner2': mock_cleaner2
        }
        
        results = await orchestrator._run_cleaners_sequential(sample_analysis_results)
        
        assert 'cleaner1' in results
        assert 'cleaner2' in results
        assert results['cleaner1'].success is True
        assert results['cleaner2'].success is True
        
        # Verify cleaners were called
        mock_cleaner1.clean.assert_called_once()
        mock_cleaner2.clean.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_analyzer_failure(self, orchestrator):
        """Test error handling when analyzer fails."""
        # Mock analyzer that raises exception
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.side_effect = Exception("Analyzer failed")
        
        orchestrator.analyzers = {'failing_analyzer': mock_analyzer}
        
        # Should handle the error gracefully
        results = await orchestrator._run_analyzers_parallel()
        
        assert 'failing_analyzer' in results
        assert results['failing_analyzer'] == []  # Should return empty list on failure
    
    @pytest.mark.asyncio
    async def test_error_handling_validator_failure(self, orchestrator):
        """Test error handling when validator fails."""
        # Mock validator that raises exception
        mock_validator = AsyncMock()
        mock_validator.validate.side_effect = Exception("Validator failed")
        
        orchestrator.validators = {'failing_validator': mock_validator}
        
        # Should handle the error gracefully
        results = await orchestrator._run_validators_parallel()
        
        assert 'failing_validator' in results
        assert results['failing_validator'].success is False
    
    @pytest.mark.asyncio
    async def test_error_handling_cleaner_failure(self, orchestrator, sample_analysis_results):
        """Test error handling when cleaner fails."""
        # Mock cleaner that raises exception
        mock_cleaner = AsyncMock()
        mock_cleaner.can_clean_issue.return_value = True
        mock_cleaner.clean.side_effect = Exception("Cleaner failed")
        
        orchestrator.cleaners = {'failing_cleaner': mock_cleaner}
        
        # Should handle the error gracefully
        results = await orchestrator._run_cleaners_sequential(sample_analysis_results)
        
        assert 'failing_cleaner' in results
        assert results['failing_cleaner'].success is False
    
    def test_aggregate_analysis_results(self, orchestrator):
        """Test aggregating analysis results from multiple analyzers."""
        analyzer_results = {
            'quality': [
                QualityIssue(
                    file_path=Path("test.py"),
                    line_number=1,
                    issue_type=IssueType.STYLE_VIOLATION,
                    severity=IssueSeverity.LOW,
                    description="Style issue"
                )
            ],
            'imports': [
                ImportIssue(
                    file_path=Path("utils.py"),
                    line_number=5,
                    issue_type=IssueType.UNUSED_IMPORT,
                    severity=IssueSeverity.LOW,
                    module_name="unused",
                    description="Unused import"
                )
            ]
        }
        
        validator_results = {
            'coverage': Mock(success=True, issues_found=0),
            'config': Mock(success=True, issues_found=1)
        }
        
        results = orchestrator._aggregate_analysis_results(analyzer_results, validator_results)
        
        assert isinstance(results, AnalysisResults)
        assert len(results.quality_issues) == 1
        assert len(results.import_issues) == 1
        assert results.metrics is not None
    
    def test_aggregate_cleanup_results(self, orchestrator):
        """Test aggregating cleanup results from multiple cleaners."""
        cleaner_results = {
            'formatter': Mock(
                success=True,
                files_modified=[Path("test.py")],
                formatting_changes=[
                    FormattingChange(
                        file_path=Path("test.py"),
                        change_type="formatting",
                        lines_changed=5,
                        description="Applied formatting"
                    )
                ]
            ),
            'imports': Mock(
                success=True,
                files_modified=[Path("utils.py")],
                import_cleanups=[]
            )
        }
        
        results = orchestrator._aggregate_cleanup_results(cleaner_results)
        
        assert isinstance(results, CleanupResults)
        assert results.success is True
        assert len(results.files_modified) == 2
        assert len(results.formatting_changes) == 1
    
    @pytest.mark.asyncio
    async def test_create_backup(self, orchestrator, tmp_path):
        """Test backup creation."""
        # Create test files
        (tmp_path / "main.py").write_text("def main(): pass")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        
        orchestrator.target_directory = tmp_path
        orchestrator.config.create_backup = True
        
        backup_path = await orchestrator._create_backup()
        
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.is_dir()
        # Should contain backed up files
        assert (backup_path / "main.py").exists()
        assert (backup_path / "utils.py").exists()
    
    @pytest.mark.asyncio
    async def test_validate_target_directory(self, orchestrator, tmp_path):
        """Test target directory validation."""
        # Test valid directory
        orchestrator.target_directory = tmp_path
        is_valid = await orchestrator._validate_target_directory()
        assert is_valid is True
        
        # Test non-existent directory
        orchestrator.target_directory = tmp_path / "nonexistent"
        is_valid = await orchestrator._validate_target_directory()
        assert is_valid is False
        
        # Test file instead of directory
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        orchestrator.target_directory = test_file
        is_valid = await orchestrator._validate_target_directory()
        assert is_valid is False
    
    def test_get_progress_callback(self, orchestrator):
        """Test progress callback functionality."""
        progress_updates = []
        
        def progress_callback(stage, progress, message):
            progress_updates.append((stage, progress, message))
        
        orchestrator.progress_callback = progress_callback
        callback = orchestrator._get_progress_callback()
        
        # Test callback
        callback("analysis", 50, "Analyzing files...")
        
        assert len(progress_updates) == 1
        assert progress_updates[0] == ("analysis", 50, "Analyzing files...")
    
    def test_estimate_duration(self, orchestrator, tmp_path):
        """Test duration estimation."""
        # Create test files
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass")
        
        orchestrator.target_directory = tmp_path
        
        estimated_duration = orchestrator._estimate_duration()
        
        assert isinstance(estimated_duration, timedelta)
        assert estimated_duration.total_seconds() > 0
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, orchestrator, sample_analysis_results):
        """Test dry run mode."""
        orchestrator.config.dry_run = True
        
        # Mock cleaners
        mock_cleaner = AsyncMock()
        mock_cleaner.can_clean_issue.return_value = True
        mock_cleaner.clean.return_value = Mock(
            success=True,
            files_modified=[],
            message="Dry run - no changes made"
        )
        
        orchestrator.cleaners = {'test_cleaner': mock_cleaner}
        
        results = await orchestrator.run_cleanup_only(sample_analysis_results)
        
        assert results.success is True
        # In dry run mode, no files should be modified
        assert len(results.files_modified) == 0
    
    def test_configuration_validation(self, orchestrator):
        """Test configuration validation."""
        # Test valid configuration
        is_valid = orchestrator._validate_configuration()
        assert is_valid is True
        
        # Test invalid configuration
        orchestrator.config.target_directory = None
        is_valid = orchestrator._validate_configuration()
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_cleanup_temporary_files(self, orchestrator, tmp_path):
        """Test cleanup of temporary files."""
        # Create temporary files
        temp_file1 = tmp_path / "temp1.tmp"
        temp_file2 = tmp_path / "temp2.tmp"
        temp_file1.write_text("temp")
        temp_file2.write_text("temp")
        
        orchestrator.temp_files = [temp_file1, temp_file2]
        
        await orchestrator._cleanup_temporary_files()
        
        # Temporary files should be removed
        assert not temp_file1.exists()
        assert not temp_file2.exists()
        assert len(orchestrator.temp_files) == 0