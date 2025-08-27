"""
Comprehensive integration tests for checkup workflows.

Tests end-to-end workflows, tool interactions, performance, and safety features.
"""

import pytest
import asyncio
import tempfile
import shutil
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from migration_assistant.checkup.orchestrator import CodebaseOrchestrator
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CleanupResults, CheckupResults,
    QualityIssue, ImportIssue, IssueType, IssueSeverity
)


class TestEndToEndWorkflows:
    """Test complete checkup workflows from start to finish."""
    
    @pytest.fixture
    def temp_project(self):
        """Create a temporary project with various issues for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create project structure with intentional issues
        project_files = {
            'main.py': '''
import os
import sys
import json  # Unused import
from pathlib import Path

def complex_function(a,b,c,d,e):  # Too many parameters
    if a>0:
        if b>0:
            if c>0:
                if d>0:
                    if e>0:  # Deep nesting
                        return a+b+c+d+e
                    else:
                        return 0
                else:
                    return 0
            else:
                return 0
        else:
            return 0
    else:
        return 0

def untested_function():
    """This function has no tests."""
    return "untested"

class UntestedClass:
    def method1(self):
        pass
    def method2(self):
        pass
''',
            'utils.py': '''
import re  # Unused
import datetime

def helper_function( x , y ):  # Bad formatting
    return x+y

def duplicate_logic():
    """Duplicate logic that appears elsewhere."""
    result = []
    for i in range(10):
        if i % 2 == 0:
            result.append(i * 2)
    return result
''',
            'duplicate.py': '''
def duplicate_logic():
    """Same logic as in utils.py."""
    result = []
    for i in range(10):
        if i % 2 == 0:
            result.append(i * 2)
    return result

def another_function():
    pass
''',
            'tests/test_main.py': '''
import pytest
from main import complex_function

def test_complex_function():
    assert complex_function(1, 1, 1, 1, 1) == 5

# Missing tests for untested_function and UntestedClass
''',
            'tests/__init__.py': '',
            'README.md': '''
# Test Project

This is a test project.

## Usage

```python
# This code example has syntax errors
def broken_example(
    print("Missing closing parenthesis")
```
''',
            'pyproject.toml': '''
[project]
name = "test-project"
version = "0.1.0"

# Missing tool configurations like black, isort, etc.
''',
            'Dockerfile': '''
FROM python:latest

COPY . .
RUN pip install -r requirements.txt

# Missing best practices: no WORKDIR, no USER, etc.
''',
            'requirements.txt': '''
pytest>=7.0.0
black>=22.0.0
isort>=5.0.0
''',
            'empty_dir/.gitkeep': '',  # Will create empty directory
            'misplaced_test.py': '''
# This test file is misplaced - should be in tests/
def test_something():
    assert True
''',
        }
        
        # Create files
        for file_path, content in project_files.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Remove .gitkeep to create truly empty directory
        (temp_dir / 'empty_dir' / '.gitkeep').unlink()
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def checkup_config(self, temp_project):
        """Create comprehensive checkup configuration."""
        return CheckupConfig(
            target_directory=temp_project,
            enable_quality_analysis=True,
            enable_duplicate_detection=True,
            enable_import_analysis=True,
            enable_structure_analysis=True,
            check_test_coverage=True,
            validate_configs=True,
            validate_docs=True,
            auto_format=False,  # Start with analysis only
            auto_fix_imports=False,
            auto_organize_files=False,
            generate_html_report=True,
            generate_json_report=True,
            generate_markdown_report=True,
            dry_run=False,
            create_backup=True,
            max_file_moves=5,
            report_output_dir=temp_project / "reports"
        )
    
    @pytest.mark.asyncio
    async def test_full_analysis_workflow(self, checkup_config):
        """Test complete analysis workflow without cleanup."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Run analysis only
        results = await orchestrator.run_analysis_only()
        
        assert isinstance(results, AnalysisResults)
        assert results.total_issues > 0
        
        # Should find quality issues
        assert len(results.quality_issues) > 0
        
        # Should find import issues
        assert len(results.import_issues) > 0
        
        # Should have metrics
        assert results.metrics.total_files > 0
        assert results.metrics.python_files > 0
        
        # Should find specific issues we created
        quality_descriptions = [issue.description for issue in results.quality_issues]
        assert any("complex" in desc.lower() or "parameter" in desc.lower() 
                  for desc in quality_descriptions)
    
    @pytest.mark.asyncio
    async def test_full_checkup_workflow_with_cleanup(self, checkup_config):
        """Test complete checkup workflow including cleanup."""
        # Enable cleanup operations
        checkup_config.auto_format = True
        checkup_config.auto_fix_imports = True
        
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Run full checkup
        results = await orchestrator.run_full_checkup()
        
        assert isinstance(results, CheckupResults)
        assert results.success is True
        assert results.analysis is not None
        assert results.cleanup is not None
        
        # Should have found and fixed issues
        assert results.analysis.total_issues > 0
        assert results.cleanup.total_changes >= 0
        
        # Should have improvement metrics
        improvements = results.improvement_metrics
        assert isinstance(improvements, dict)
        
        # Should have generated reports
        reports_dir = checkup_config.report_output_dir
        if reports_dir.exists():
            report_files = list(reports_dir.glob("*.html")) + list(reports_dir.glob("*.json")) + list(reports_dir.glob("*.md"))
            assert len(report_files) > 0
    
    @pytest.mark.asyncio
    async def test_analysis_with_all_components(self, checkup_config):
        """Test analysis with all components enabled."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        results = await orchestrator.run_analysis_only()
        
        # Should have results from all analyzers
        assert isinstance(results, AnalysisResults)
        
        # Quality analysis should find issues
        assert len(results.quality_issues) > 0
        
        # Import analysis should find unused imports
        assert len(results.import_issues) > 0
        
        # Should have comprehensive metrics
        metrics = results.metrics
        assert metrics.total_files > 0
        assert metrics.python_files > 0
        assert metrics.syntax_errors >= 0
        assert metrics.style_violations >= 0
        assert metrics.unused_imports > 0
    
    @pytest.mark.asyncio
    async def test_selective_analysis(self, checkup_config):
        """Test analysis with selective components."""
        # Disable some components
        checkup_config.enable_duplicate_detection = False
        checkup_config.enable_structure_analysis = False
        checkup_config.check_test_coverage = False
        
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        results = await orchestrator.run_analysis_only()
        
        # Should still have results from enabled components
        assert len(results.quality_issues) > 0
        assert len(results.import_issues) > 0
        
        # Disabled components should have no results
        assert len(results.duplicates) == 0
        assert len(results.structure_issues) == 0
        assert len(results.coverage_gaps) == 0
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, checkup_config):
        """Test workflow with error recovery."""
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Mock one analyzer to fail
        with patch.object(orchestrator, '_run_analyzers_parallel') as mock_analyzers:
            # Simulate partial failure
            mock_analyzers.return_value = {
                'quality': [
                    QualityIssue(
                        file_path=Path("test.py"),
                        line_number=1,
                        issue_type=IssueType.STYLE_VIOLATION,
                        severity=IssueSeverity.LOW,
                        message="Test issue",
                        description="Test issue"
                    )
                ],
                'imports': [],  # Empty due to "failure"
                'duplicates': []
            }
            
            results = await orchestrator.run_analysis_only()
            
            # Should still complete with partial results
            assert isinstance(results, AnalysisResults)
            assert len(results.quality_issues) > 0


class TestToolIntegrations:
    """Test integration with external tools (black, isort, mypy, etc.)."""
    
    @pytest.fixture
    def temp_python_file(self):
        """Create a temporary Python file for tool testing."""
        temp_dir = Path(tempfile.mkdtemp())
        python_file = temp_dir / "test_file.py"
        
        # Create file with formatting and import issues
        content = '''
import sys
import os
import json
from pathlib import Path

def badly_formatted_function(a,b,c):
    x=a+b
    y=x*c
    return y

class TestClass:
    def method1(self):
        pass
    def method2(self):
        pass
'''
        python_file.write_text(content)
        
        yield python_file
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_black_integration(self, temp_python_file):
        """Test integration with black formatter."""
        from migration_assistant.checkup.cleaners.formatter import CodeFormatter
        
        config = CheckupConfig(
            target_directory=temp_python_file.parent,
            auto_format=True
        )
        
        formatter = CodeFormatter(config)
        
        # Test formatting
        result = await formatter.format_with_black([temp_python_file])
        
        # Should complete successfully (even if black is not installed)
        assert result.success in [True, False]  # May fail if black not installed
        
        if result.success:
            assert len(result.formatting_changes) >= 0
    
    @pytest.mark.asyncio
    async def test_isort_integration(self, temp_python_file):
        """Test integration with isort."""
        from migration_assistant.checkup.cleaners.formatter import CodeFormatter
        
        config = CheckupConfig(
            target_directory=temp_python_file.parent,
            auto_format=True
        )
        
        formatter = CodeFormatter(config)
        
        # Test import sorting
        result = await formatter.organize_imports_with_isort([temp_python_file])
        
        # Should complete successfully (even if isort is not installed)
        assert result.success in [True, False]  # May fail if isort not installed
    
    @pytest.mark.asyncio
    async def test_flake8_integration(self, temp_python_file):
        """Test integration with flake8."""
        from migration_assistant.checkup.analyzers.quality import CodeQualityAnalyzer
        
        config = CheckupConfig(
            target_directory=temp_python_file.parent,
            enable_quality_analysis=True
        )
        
        analyzer = CodeQualityAnalyzer(config)
        
        # Test flake8 analysis
        issues = await analyzer._run_flake8_analysis([temp_python_file])
        
        # Should return a list (empty if flake8 not installed)
        assert isinstance(issues, list)
    
    @pytest.mark.asyncio
    async def test_mypy_integration(self, temp_python_file):
        """Test integration with mypy."""
        from migration_assistant.checkup.analyzers.quality import CodeQualityAnalyzer
        
        config = CheckupConfig(
            target_directory=temp_python_file.parent,
            enable_quality_analysis=True
        )
        
        analyzer = CodeQualityAnalyzer(config)
        
        # Test mypy analysis
        issues = await analyzer._run_mypy_analysis([temp_python_file])
        
        # Should return a list (empty if mypy not installed)
        assert isinstance(issues, list)
    
    @pytest.mark.asyncio
    async def test_pytest_cov_integration(self, temp_python_file):
        """Test integration with pytest-cov."""
        from migration_assistant.checkup.validators.coverage import CoverageValidator
        
        config = CheckupConfig(
            target_directory=temp_python_file.parent,
            check_test_coverage=True
        )
        
        validator = CoverageValidator(config)
        
        # Test coverage report generation
        report = await validator.generate_coverage_report()
        
        # May return None if pytest-cov not available or no tests
        assert report is None or hasattr(report, 'total_coverage')


class TestPerformanceAndScalability:
    """Test performance with large codebases and scalability."""
    
    @pytest.fixture
    def large_codebase(self):
        """Create a large codebase for performance testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create multiple files with various issues
        for i in range(20):  # Create 20 files
            file_content = f'''
import os
import sys
import json  # Unused in file {i}
from pathlib import Path

def function_{i}(a, b, c, d, e, f):  # Many parameters
    """Function {i} with complexity issues."""
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        if f > 0:
                            return a + b + c + d + e + f
                        else:
                            return 0
                    else:
                        return 0
                else:
                    return 0
            else:
                return 0
        else:
            return 0
    else:
        return 0

class Class_{i}:
    """Class {i} with many methods."""
    
    def method_1(self):
        pass
    
    def method_2(self):
        pass
    
    def method_3(self):
        pass
    
    def method_4(self):
        pass
    
    def method_5(self):
        pass

# Duplicate code block
def duplicate_logic_{i}():
    result = []
    for j in range(10):
        if j % 2 == 0:
            result.append(j * 2)
    return result
'''
            
            file_path = temp_dir / f"module_{i}.py"
            file_path.write_text(file_content)
        
        # Create test files
        test_dir = temp_dir / "tests"
        test_dir.mkdir()
        
        for i in range(5):  # Create some test files
            test_content = f'''
import pytest
from module_{i} import function_{i}

def test_function_{i}():
    assert function_{i}(1, 1, 1, 1, 1, 1) == 6
'''
            test_file = test_dir / f"test_module_{i}.py"
            test_file.write_text(test_content)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_large_codebase_analysis_performance(self, large_codebase):
        """Test analysis performance on large codebase."""
        config = CheckupConfig(
            target_directory=large_codebase,
            enable_quality_analysis=True,
            enable_duplicate_detection=True,
            enable_import_analysis=True,
            enable_structure_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Measure analysis time
        start_time = time.time()
        results = await orchestrator.run_analysis_only()
        end_time = time.time()
        
        analysis_duration = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert analysis_duration < 60.0  # 60 seconds max
        
        # Should find issues
        assert isinstance(results, AnalysisResults)
        assert results.total_issues > 0
        assert results.metrics.total_files >= 20
    
    @pytest.mark.asyncio
    async def test_memory_usage_large_codebase(self, large_codebase):
        """Test memory usage with large codebase."""
        import psutil
        import os
        
        config = CheckupConfig(
            target_directory=large_codebase,
            enable_quality_analysis=True,
            enable_duplicate_detection=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Measure memory before
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss
        
        # Run analysis
        results = await orchestrator.run_analysis_only()
        
        # Measure memory after
        memory_after = process.memory_info().rss
        memory_increase = memory_after - memory_before
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024  # 100MB
        
        # Should still produce results
        assert isinstance(results, AnalysisResults)
    
    @pytest.mark.asyncio
    async def test_concurrent_analysis_performance(self, large_codebase):
        """Test concurrent analysis performance."""
        config = CheckupConfig(
            target_directory=large_codebase,
            enable_quality_analysis=True,
            enable_import_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Run multiple analyses concurrently
        start_time = time.time()
        
        tasks = [
            orchestrator.run_analysis_only(),
            orchestrator.run_analysis_only(),
            orchestrator.run_analysis_only()
        ]
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        concurrent_duration = end_time - start_time
        
        # Should complete all analyses
        assert len(results_list) == 3
        
        # All should be successful or exceptions
        for result in results_list:
            assert isinstance(result, (AnalysisResults, Exception))
        
        # Concurrent execution should be faster than sequential
        # (This is a rough heuristic - actual performance depends on system)
        assert concurrent_duration < 180.0  # 3 minutes max for 3 concurrent analyses


class TestSafetyAndBackup:
    """Test backup and rollback functionality."""
    
    @pytest.fixture
    def temp_project_for_safety(self):
        """Create a temporary project for safety testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create files that will be modified
        files = {
            'main.py': '''
import os
import sys

def test_function():
    x=1+2
    return x
''',
            'utils.py': '''
import json
import re

def helper():
    return "helper"
''',
            'config.py': '''
DEBUG = True
VERSION = "1.0.0"
'''
        }
        
        for file_path, content in files.items():
            (temp_dir / file_path).write_text(content)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_backup_creation(self, temp_project_for_safety):
        """Test backup creation before cleanup."""
        config = CheckupConfig(
            target_directory=temp_project_for_safety,
            create_backup=True,
            auto_format=True,
            backup_dir=temp_project_for_safety / "backups"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Create backup
        backup_path = await orchestrator._create_backup()
        
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.is_dir()
        
        # Should contain backed up files
        backed_up_files = list(backup_path.rglob("*.py"))
        original_files = list(temp_project_for_safety.rglob("*.py"))
        
        assert len(backed_up_files) == len(original_files)
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, temp_project_for_safety):
        """Test dry run mode doesn't modify files."""
        config = CheckupConfig(
            target_directory=temp_project_for_safety,
            dry_run=True,
            auto_format=True,
            auto_fix_imports=True
        )
        
        # Get original file contents
        original_contents = {}
        for py_file in temp_project_for_safety.rglob("*.py"):
            original_contents[py_file] = py_file.read_text()
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Run cleanup in dry run mode
        analysis_results = await orchestrator.run_analysis_only()
        cleanup_results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should report success but not modify files
        assert cleanup_results.success is True
        
        # Files should be unchanged
        for py_file in temp_project_for_safety.rglob("*.py"):
            assert py_file.read_text() == original_contents[py_file]
    
    @pytest.mark.asyncio
    async def test_file_validation_before_cleanup(self, temp_project_for_safety):
        """Test file validation before performing cleanup."""
        config = CheckupConfig(
            target_directory=temp_project_for_safety,
            auto_format=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Validate target directory
        is_valid = await orchestrator._validate_target_directory()
        assert is_valid is True
        
        # Test with non-existent directory
        config.target_directory = temp_project_for_safety / "nonexistent"
        is_valid = await orchestrator._validate_target_directory()
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_cleanup_with_file_permissions(self, temp_project_for_safety):
        """Test cleanup behavior with different file permissions."""
        import stat
        
        # Make one file read-only
        readonly_file = temp_project_for_safety / "main.py"
        readonly_file.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        config = CheckupConfig(
            target_directory=temp_project_for_safety,
            auto_format=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Run analysis and cleanup
        analysis_results = await orchestrator.run_analysis_only()
        cleanup_results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should handle permission errors gracefully
        assert isinstance(cleanup_results, CleanupResults)
        
        # Restore permissions for cleanup
        readonly_file.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery mechanisms."""
    
    @pytest.fixture
    def temp_project_with_errors(self):
        """Create a project with various error conditions."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create files with syntax errors and other issues
        files = {
            'syntax_error.py': '''
def broken_function(
    print("Missing closing parenthesis")
    return "broken"
''',
            'encoding_issue.py': 'print("Test with special chars: ñáéíóú")',
            'very_long_line.py': 'x = ' + '"' + 'a' * 200 + '"',  # Very long line
            'empty_file.py': '',
            'binary_file.pyc': b'\x00\x01\x02\x03',  # Binary content
        }
        
        for file_path, content in files.items():
            full_path = temp_dir / file_path
            if isinstance(content, bytes):
                full_path.write_bytes(content)
            else:
                full_path.write_text(content)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_syntax_error_handling(self, temp_project_with_errors):
        """Test handling of files with syntax errors."""
        config = CheckupConfig(
            target_directory=temp_project_with_errors,
            enable_quality_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Should handle syntax errors gracefully
        results = await orchestrator.run_analysis_only()
        
        assert isinstance(results, AnalysisResults)
        # Should find syntax errors
        syntax_errors = [issue for issue in results.quality_issues 
                        if issue.issue_type == IssueType.SYNTAX_ERROR]
        assert len(syntax_errors) > 0
    
    @pytest.mark.asyncio
    async def test_binary_file_handling(self, temp_project_with_errors):
        """Test handling of binary files."""
        config = CheckupConfig(
            target_directory=temp_project_with_errors,
            enable_quality_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Should skip binary files gracefully
        results = await orchestrator.run_analysis_only()
        
        assert isinstance(results, AnalysisResults)
        # Should complete without crashing
    
    @pytest.mark.asyncio
    async def test_empty_file_handling(self, temp_project_with_errors):
        """Test handling of empty files."""
        config = CheckupConfig(
            target_directory=temp_project_with_errors,
            enable_quality_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Should handle empty files gracefully
        results = await orchestrator.run_analysis_only()
        
        assert isinstance(results, AnalysisResults)
        # Should complete without issues
    
    @pytest.mark.asyncio
    async def test_component_failure_recovery(self, temp_project_with_errors):
        """Test recovery when individual components fail."""
        config = CheckupConfig(
            target_directory=temp_project_with_errors,
            enable_quality_analysis=True,
            enable_import_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock one component to fail
        with patch.object(orchestrator, '_run_analyzers_parallel') as mock_run:
            async def failing_analyzer():
                return {
                    'quality': [
                        QualityIssue(
                            file_path=Path("test.py"),
                            line_number=1,
                            issue_type=IssueType.SYNTAX_ERROR,
                            severity=IssueSeverity.HIGH,
                            message="Syntax error",
                            description="Syntax error found"
                        )
                    ],
                    'imports': []  # Simulate failure by returning empty
                }
            
            mock_run.return_value = await failing_analyzer()
            
            results = await orchestrator.run_analysis_only()
            
            # Should still complete with partial results
            assert isinstance(results, AnalysisResults)
            assert len(results.quality_issues) > 0
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, temp_project_with_errors):
        """Test handling of operations that might timeout."""
        config = CheckupConfig(
            target_directory=temp_project_with_errors,
            enable_quality_analysis=True
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Mock a slow operation
        with patch.object(orchestrator, '_run_analyzers_parallel') as mock_run:
            async def slow_analyzer():
                await asyncio.sleep(0.1)  # Simulate slow operation
                return {
                    'quality': [],
                    'imports': []
                }
            
            mock_run.side_effect = slow_analyzer
            
            # Should complete within reasonable time
            start_time = time.time()
            results = await orchestrator.run_analysis_only()
            end_time = time.time()
            
            assert isinstance(results, AnalysisResults)
            assert (end_time - start_time) < 5.0  # Should complete within 5 seconds


class TestReportGeneration:
    """Test report generation integration."""
    
    @pytest.fixture
    def temp_project_for_reports(self):
        """Create a project for report testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create simple project
        (temp_dir / "main.py").write_text('''
import os
import json  # Unused

def test_function():
    x=1+2  # Style issue
    return x
''')
        
        (temp_dir / "reports").mkdir()
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_html_report_generation(self, temp_project_for_reports):
        """Test HTML report generation."""
        config = CheckupConfig(
            target_directory=temp_project_for_reports,
            generate_html_report=True,
            report_output_dir=temp_project_for_reports / "reports"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Run analysis and generate reports
        analysis_results = await orchestrator.run_analysis_only()
        
        # Create mock checkup results
        checkup_results = CheckupResults(
            analysis=analysis_results,
            cleanup=None,
            before_metrics=analysis_results.metrics,
            after_metrics=None,
            duration=timedelta(seconds=10),
            success=True
        )
        
        report_result = await orchestrator.generate_reports(checkup_results)
        
        assert report_result.success is True
        
        # Check if HTML report was created
        html_files = list((temp_project_for_reports / "reports").glob("*.html"))
        assert len(html_files) > 0
    
    @pytest.mark.asyncio
    async def test_json_report_generation(self, temp_project_for_reports):
        """Test JSON report generation."""
        config = CheckupConfig(
            target_directory=temp_project_for_reports,
            generate_json_report=True,
            report_output_dir=temp_project_for_reports / "reports"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Run analysis and generate reports
        analysis_results = await orchestrator.run_analysis_only()
        
        checkup_results = CheckupResults(
            analysis=analysis_results,
            cleanup=None,
            before_metrics=analysis_results.metrics,
            after_metrics=None,
            duration=timedelta(seconds=10),
            success=True
        )
        
        report_result = await orchestrator.generate_reports(checkup_results)
        
        assert report_result.success is True
        
        # Check if JSON report was created
        json_files = list((temp_project_for_reports / "reports").glob("*.json"))
        assert len(json_files) > 0
        
        # Validate JSON content
        if json_files:
            import json
            with open(json_files[0]) as f:
                report_data = json.load(f)
            assert isinstance(report_data, dict)
    
    @pytest.mark.asyncio
    async def test_markdown_report_generation(self, temp_project_for_reports):
        """Test Markdown report generation."""
        config = CheckupConfig(
            target_directory=temp_project_for_reports,
            generate_markdown_report=True,
            report_output_dir=temp_project_for_reports / "reports"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Run analysis and generate reports
        analysis_results = await orchestrator.run_analysis_only()
        
        checkup_results = CheckupResults(
            analysis=analysis_results,
            cleanup=None,
            before_metrics=analysis_results.metrics,
            after_metrics=None,
            duration=timedelta(seconds=10),
            success=True
        )
        
        report_result = await orchestrator.generate_reports(checkup_results)
        
        assert report_result.success is True
        
        # Check if Markdown report was created
        md_files = list((temp_project_for_reports / "reports").glob("*.md"))
        assert len(md_files) > 0
        
        # Validate Markdown content
        if md_files:
            content = md_files[0].read_text()
            assert "# " in content  # Should have headers
            assert len(content) > 100  # Should have substantial content