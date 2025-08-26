"""
Integration tests for CodeQualityAnalyzer with external linting tools.
"""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from migration_assistant.checkup.analyzers.quality import CodeQualityAnalyzer
from migration_assistant.checkup.models import CheckupConfig, IssueType, IssueSeverity


@pytest.fixture
def quality_analyzer():
    """Create a quality analyzer instance for testing."""
    config = CheckupConfig(
        target_directory=Path("."),
        check_type_hints=True,
        enable_quality_analysis=True,
        flake8_config={
            'max-line-length': 88,
            'ignore': ['E203', 'W503']
        },
        mypy_config={
            'ignore-missing-imports': True,
            'show-error-codes': True
        }
    )
    return CodeQualityAnalyzer(config)


@pytest.fixture
def temp_python_files(tmp_path):
    """Create temporary Python files for testing."""
    def _create_files(file_contents: dict) -> dict:
        files = {}
        for filename, content in file_contents.items():
            file_path = tmp_path / filename
            file_path.write_text(content)
            files[filename] = file_path
        return files
    return _create_files


class TestFlake8Integration:
    """Test flake8 integration."""
    
    @pytest.mark.asyncio
    async def test_flake8_batch_analysis_success(self, quality_analyzer, temp_python_files):
        """Test successful flake8 batch analysis."""
        files = temp_python_files({
            'test1.py': '''
import os
import sys

def long_function_name_that_exceeds_line_length_limit_and_should_trigger_flake8_error():
    pass

def unused_variable_function():
    x = 1
    return 2
''',
            'test2.py': '''
def function_with_style_issues( x,y ):
    if x>0:
        return y+1
    else:
        return y-1
'''
        })
        
        # Mock subprocess.run to return flake8-like output
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = f'''{files['test1.py']}:4:1:E501:line too long (89 > 88 characters)
{files['test1.py']}:8:5:F841:local variable 'x' is assigned to but never used
{files['test2.py']}:1:25:E201:whitespace after '('
{files['test2.py']}:2:8:E225:missing whitespace around operator'''
        
        with patch('subprocess.run', return_value=mock_result):
            issues = await quality_analyzer.analyze_with_flake8_batch(list(files.values()))
        
        assert len(issues) == 4
        
        # Check that issues are properly parsed
        line_length_issues = [i for i in issues if 'E501' in i.message]
        assert len(line_length_issues) == 1
        assert line_length_issues[0].severity == IssueSeverity.LOW
        
        unused_var_issues = [i for i in issues if 'F841' in i.message]
        assert len(unused_var_issues) == 1
        assert unused_var_issues[0].severity == IssueSeverity.HIGH
    
    @pytest.mark.asyncio
    async def test_flake8_timeout_handling(self, quality_analyzer, temp_python_files):
        """Test flake8 timeout handling."""
        files = temp_python_files({'test.py': 'print("hello")'})
        
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('flake8', 60)):
            issues = await quality_analyzer.analyze_with_flake8_batch(list(files.values()))
        
        assert len(issues) == 0  # Should handle timeout gracefully
    
    @pytest.mark.asyncio
    async def test_flake8_not_found(self, quality_analyzer, temp_python_files):
        """Test handling when flake8 is not installed."""
        files = temp_python_files({'test.py': 'print("hello")'})
        
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            issues = await quality_analyzer.analyze_with_flake8_batch(list(files.values()))
        
        assert len(issues) == 0  # Should handle missing tool gracefully


class TestMypyIntegration:
    """Test mypy integration."""
    
    @pytest.mark.asyncio
    async def test_mypy_analysis_success(self, quality_analyzer, temp_python_files):
        """Test successful mypy analysis."""
        files = temp_python_files({
            'test_types.py': '''
def add_numbers(a, b):
    return a + b

def type_error_function():
    x: int = "string"  # Type error
    return x

def missing_return_annotation(x):
    if x > 0:
        return x
    # Missing return in some paths
'''
        })
        
        # Mock subprocess.run to return mypy-like output
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = f'''{files['test_types.py']}:5: error: Incompatible types in assignment (expression has type "str", variable has type "int") [assignment]
{files['test_types.py']}:8: error: Missing return statement [return-value]
{files['test_types.py']}:2: note: Consider adding type annotations'''
        
        with patch('subprocess.run', return_value=mock_result):
            issues = await quality_analyzer.analyze_with_mypy(list(files.values()))
        
        assert len(issues) == 3
        
        # Check error types
        assignment_errors = [i for i in issues if 'assignment' in (i.rule_name or '')]
        assert len(assignment_errors) == 1
        assert assignment_errors[0].severity == IssueSeverity.HIGH
        
        return_errors = [i for i in issues if 'return-value' in (i.rule_name or '')]
        assert len(return_errors) == 1
        
        notes = [i for i in issues if i.severity == IssueSeverity.LOW]
        assert len(notes) == 1
    
    @pytest.mark.asyncio
    async def test_mypy_with_custom_config(self, quality_analyzer, temp_python_files):
        """Test mypy with custom configuration."""
        quality_analyzer.config.mypy_config = {
            'strict': True,
            'ignore-missing-imports': False,
            'show-error-codes': True
        }
        
        files = temp_python_files({'test.py': 'import nonexistent_module'})
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ''
            
            await quality_analyzer.analyze_with_mypy(list(files.values()))
            
            # Check that correct arguments were passed
            call_args = mock_run.call_args[0][0]
            assert '--strict' in call_args
            assert '--ignore-missing-imports' not in call_args
            assert '--show-error-codes' in call_args
    
    @pytest.mark.asyncio
    async def test_mypy_timeout_handling(self, quality_analyzer, temp_python_files):
        """Test mypy timeout handling."""
        files = temp_python_files({'test.py': 'print("hello")'})
        
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('mypy', 120)):
            issues = await quality_analyzer.analyze_with_mypy(list(files.values()))
        
        assert len(issues) == 0  # Should handle timeout gracefully


class TestIssueAggregation:
    """Test issue aggregation and normalization."""
    
    def test_merge_similar_issues(self, quality_analyzer):
        """Test merging similar issues from different tools."""
        file_path = Path("test.py")
        
        # Create similar issues from different tools
        flake8_issue = quality_analyzer._create_quality_issue(
            file_path=file_path,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.MEDIUM,
            message="E501: line too long",
            description="Line exceeds maximum length",
            line_number=10,
            tool_name="flake8",
            rule_name="E501"
        )
        
        mypy_issue = quality_analyzer._create_quality_issue(
            file_path=file_path,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.HIGH,
            message="Type annotation missing",
            description="Function lacks type annotation",
            line_number=10,
            tool_name="mypy",
            rule_name="annotation"
        )
        
        merged = quality_analyzer._merge_similar_issues([flake8_issue, mypy_issue])
        
        # Should prioritize mypy (higher priority tool)
        assert merged.tool_name == "multiple (mypy, flake8)"
        assert merged.severity == IssueSeverity.HIGH  # From mypy
        assert "Multiple tools found issues" in merged.description
    
    def test_aggregate_and_normalize_issues(self, quality_analyzer):
        """Test full issue aggregation and normalization."""
        file_path = Path("test.py")
        
        issues = [
            # Duplicate issues at same location
            quality_analyzer._create_quality_issue(
                file_path=file_path, issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW, message="Style issue 1",
                description="Description 1", line_number=5, tool_name="flake8"
            ),
            quality_analyzer._create_quality_issue(
                file_path=file_path, issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.MEDIUM, message="Style issue 2",
                description="Description 2", line_number=5, tool_name="mypy"
            ),
            # Unique issue
            quality_analyzer._create_quality_issue(
                file_path=file_path, issue_type=IssueType.COMPLEXITY,
                severity=IssueSeverity.HIGH, message="Complex function",
                description="Function too complex", line_number=10, tool_name="ast"
            )
        ]
        
        normalized = quality_analyzer._aggregate_and_normalize_issues(issues)
        
        assert len(normalized) == 2  # Two unique locations
        
        # Check that duplicate was merged
        style_issues = [i for i in normalized if i.issue_type == IssueType.STYLE_VIOLATION]
        assert len(style_issues) == 1
        assert "multiple" in style_issues[0].tool_name


class TestFullIntegration:
    """Test full integration with all tools."""
    
    @pytest.mark.asyncio
    async def test_full_analysis_integration(self, quality_analyzer, temp_python_files):
        """Test full analysis with all tools integrated."""
        files = temp_python_files({
            'complex_file.py': '''
import os
import sys
import unused_module

def complex_function_with_many_issues(a,b,c,d,e,f):
    x = 1  # Unused variable
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        if f > 0:
                            return "deeply nested"
                        return "level 5"
                    return "level 4"
                return "level 3"
            return "level 2"
        return "level 1"
    return "negative"

class VeryLongClassNameThatExceedsReasonableLimitsAndShouldTriggerStyleWarnings:
    def method_without_type_hints(self, param):
        return param + 1
'''
        })
        
        # Mock external tool calls
        flake8_output = f'''{files['complex_file.py']}:6:1:E501:line too long
{files['complex_file.py']}:7:5:F841:local variable 'x' is assigned to but never used
{files['complex_file.py']}:3:1:F401:unused import'''
        
        mypy_output = f'''{files['complex_file.py']}:6: error: Function is missing type annotation [no-untyped-def]
{files['complex_file.py']}:22: error: Function is missing return type annotation [no-untyped-def]'''
        
        with patch('subprocess.run') as mock_run:
            def side_effect(*args, **kwargs):
                result = MagicMock()
                if 'flake8' in args[0]:
                    result.returncode = 1
                    result.stdout = flake8_output
                elif 'mypy' in args[0]:
                    result.returncode = 1
                    result.stdout = mypy_output
                else:
                    result.returncode = 0
                    result.stdout = ''
                return result
            
            mock_run.side_effect = side_effect
            
            # Mock get_python_files to return our test files
            with patch.object(quality_analyzer, 'get_python_files', return_value=list(files.values())):
                issues = await quality_analyzer.analyze()
        
        # Should find multiple types of issues
        assert len(issues) > 0
        
        # Check for different issue types
        issue_types = {issue.issue_type for issue in issues}
        expected_types = {IssueType.STYLE_VIOLATION, IssueType.COMPLEXITY, IssueType.CODE_SMELL}
        assert len(issue_types.intersection(expected_types)) > 0
        
        # Check for different tools
        tools = {issue.tool_name for issue in issues if issue.tool_name}
        # Should include at least some of our integrated tools
        assert len(tools) > 0
        
        # Verify metrics were updated
        assert quality_analyzer.metrics.style_violations > 0 or quality_analyzer.metrics.complexity_issues > 0
    
    @pytest.mark.asyncio
    async def test_analysis_with_syntax_errors(self, quality_analyzer, temp_python_files):
        """Test that analysis handles syntax errors gracefully."""
        files = temp_python_files({
            'syntax_error.py': '''
def broken_function(
    # Missing closing parenthesis and colon
    return "broken"
'''
        })
        
        with patch.object(quality_analyzer, 'get_python_files', return_value=list(files.values())):
            issues = await quality_analyzer.analyze()
        
        # Should find syntax error
        syntax_errors = [i for i in issues if i.issue_type == IssueType.SYNTAX_ERROR]
        assert len(syntax_errors) > 0
        assert syntax_errors[0].severity == IssueSeverity.CRITICAL
    
    @pytest.mark.asyncio
    async def test_analysis_with_no_external_tools(self, quality_analyzer, temp_python_files):
        """Test analysis when external tools are not available."""
        files = temp_python_files({
            'simple.py': '''
def simple_function():
    return "hello"
'''
        })
        
        # Mock all external tools as not found
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            with patch.object(quality_analyzer, 'get_python_files', return_value=list(files.values())):
                issues = await quality_analyzer.analyze()
        
        # Should still work with built-in analysis
        # May have no issues for simple code, but should not crash
        assert isinstance(issues, list)