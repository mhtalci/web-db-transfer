"""
Tests for Code Formatter

Tests the CodeFormatter class functionality including black integration,
docstring standardization, and formatting operations.
"""

import ast
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest

from migration_assistant.checkup.cleaners.formatter import CodeFormatter, FormattingResult
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, QualityIssue, IssueType, IssueSeverity,
    FormattingChange
)


@pytest.fixture
def config():
    """Create test configuration."""
    return CheckupConfig(
        target_directory=Path("."),
        auto_format=True,
        create_backup=False,  # Disable backup for tests
        dry_run=False,
        black_config={"line_length": 88},
        isort_config={"profile": "black"}
    )


@pytest.fixture
def formatter(config):
    """Create CodeFormatter instance."""
    return CodeFormatter(config)


@pytest.fixture
def temp_python_file():
    """Create temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''def test_function(  ):
    """this is a test function"""
    x=1+2
    return x
''')
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def temp_python_file_with_docstrings():
    """Create temporary Python file with various docstring formats."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''class TestClass:
    """test class"""
    
    def method_one(self):
        """does something"""
        pass
    
    def method_two(self):
        """
        does something else
        with multiple lines
        """
        pass

def function_one():
    """function without period"""
    pass

def function_two():
    """function with period."""
    pass
''')
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestCodeFormatter:
    """Test cases for CodeFormatter class."""
    
    def test_init(self, config):
        """Test CodeFormatter initialization."""
        formatter = CodeFormatter(config)
        
        assert formatter.config == config
        assert formatter._black_config["line_length"] == 88
        assert formatter._isort_config["profile"] == "black"
    
    def test_get_black_config_defaults(self):
        """Test black configuration defaults."""
        config = CheckupConfig()
        formatter = CodeFormatter(config)
        
        black_config = formatter._get_black_config()
        
        assert black_config["line_length"] == 88
        assert black_config["target_version"] == ["py311"]
        assert black_config["skip_string_normalization"] is False
    
    def test_get_black_config_custom(self):
        """Test black configuration with custom values."""
        config = CheckupConfig(
            black_config={"line_length": 100, "skip_string_normalization": True}
        )
        formatter = CodeFormatter(config)
        
        black_config = formatter._get_black_config()
        
        assert black_config["line_length"] == 100
        assert black_config["skip_string_normalization"] is True
        assert black_config["target_version"] == ["py311"]  # Default preserved
    
    def test_get_isort_config_defaults(self):
        """Test isort configuration defaults."""
        config = CheckupConfig()
        formatter = CodeFormatter(config)
        
        isort_config = formatter._get_isort_config()
        
        assert isort_config["profile"] == "black"
        assert isort_config["line_length"] == 88
        assert isort_config["known_first_party"] == ["migration_assistant"]
    
    def test_can_clean_issue(self, formatter):
        """Test issue type checking."""
        style_issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.STYLE_VIOLATION,
            message="Style violation",
            description="Test style issue"
        )
        
        code_smell = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CODE_SMELL,
            message="Code smell",
            description="Test code smell"
        )
        
        syntax_error = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            severity=IssueSeverity.HIGH,
            issue_type=IssueType.SYNTAX_ERROR,
            message="Syntax error",
            description="Test syntax error"
        )
        
        assert formatter.can_clean_issue(style_issue) is True
        assert formatter.can_clean_issue(code_smell) is True
        assert formatter.can_clean_issue(syntax_error) is False
    
    def test_get_python_files(self, formatter, tmp_path):
        """Test getting Python files from directory."""
        # Create test directory structure
        (tmp_path / "test1.py").write_text("# Test file 1")
        (tmp_path / "test2.py").write_text("# Test file 2")
        (tmp_path / "test.txt").write_text("Not a Python file")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "test.pyc").write_text("Compiled Python")
        
        formatter.target_directory = tmp_path
        python_files = formatter._get_python_files()
        
        assert len(python_files) == 2
        assert all(f.suffix == ".py" for f in python_files)
        assert all("__pycache__" not in str(f) for f in python_files)
    
    def test_generate_black_config(self, formatter):
        """Test black configuration generation."""
        config_content = formatter._generate_black_config()
        
        assert "[tool.black]" in config_content
        assert 'line_length = 88' in config_content
        assert 'target_version = ["py311"]' in config_content
        assert 'skip_string_normalization = false' in config_content
    
    def test_parse_black_diff_no_changes(self, formatter):
        """Test parsing black diff with no changes."""
        diff_output = ""
        files = [Path("test.py")]
        
        changes = formatter._parse_black_diff(diff_output, files)
        
        assert len(changes) == 0
    
    def test_parse_black_diff_with_changes(self, formatter):
        """Test parsing black diff with changes."""
        diff_output = """--- test.py	2024-01-01 12:00:00.000000 +0000
+++ test.py	2024-01-01 12:00:01.000000 +0000
@@ -1,3 +1,3 @@
 def test():
-    x=1+2
+    x = 1 + 2
     return x
"""
        files = [Path("test.py")]
        
        changes = formatter._parse_black_diff(diff_output, files)
        
        assert len(changes) == 1
        assert changes[0].file_path == Path("test.py")
        assert changes[0].change_type == "black"
        assert changes[0].lines_changed == 2  # One - and one +
    
    def test_standardize_single_docstring_function(self, formatter):
        """Test standardizing function docstrings."""
        # Test lowercase start
        result = formatter._standardize_single_docstring(
            "does something", 
            ast.FunctionDef(name="test", args=None, body=[], decorator_list=[])
        )
        assert result == "Does something."
        
        # Test already proper
        result = formatter._standardize_single_docstring(
            "Does something.", 
            ast.FunctionDef(name="test", args=None, body=[], decorator_list=[])
        )
        assert result == "Does something."
        
        # Test multiline
        result = formatter._standardize_single_docstring(
            "does something\nwith multiple lines", 
            ast.FunctionDef(name="test", args=None, body=[], decorator_list=[])
        )
        assert result == "Does something\nwith multiple lines"
    
    def test_standardize_single_docstring_class(self, formatter):
        """Test standardizing class docstrings."""
        # Test lowercase start
        result = formatter._standardize_single_docstring(
            "test class", 
            ast.ClassDef(name="Test", bases=[], keywords=[], body=[], decorator_list=[])
        )
        assert result == "Test class."
        
        # Test already proper
        result = formatter._standardize_single_docstring(
            "Test class.", 
            ast.ClassDef(name="Test", bases=[], keywords=[], body=[], decorator_list=[])
        )
        assert result == "Test class."
    
    def test_format_docstring_lines_single(self, formatter):
        """Test formatting single-line docstring."""
        lines = formatter._format_docstring_lines("Test docstring.", "    ")
        
        assert len(lines) == 1
        assert lines[0] == '    """Test docstring."""'
    
    def test_format_docstring_lines_multi(self, formatter):
        """Test formatting multi-line docstring."""
        lines = formatter._format_docstring_lines("Test docstring.\nWith multiple lines.", "    ")
        
        assert len(lines) == 4
        assert lines[0] == '    """'
        assert lines[1] == '    Test docstring.'
        assert lines[2] == '    With multiple lines.'
        assert lines[3] == '    """'
    
    @pytest.mark.asyncio
    async def test_clean_dry_run(self, formatter):
        """Test clean method in dry run mode."""
        formatter.config.dry_run = True
        analysis_results = AnalysisResults()
        
        result = await formatter.clean(analysis_results)
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert "Dry run" in result.message
    
    @pytest.mark.asyncio
    async def test_clean_no_files(self, formatter, tmp_path):
        """Test clean method with no Python files."""
        formatter.target_directory = tmp_path
        analysis_results = AnalysisResults()
        
        with patch.object(formatter, '_get_python_files', return_value=[]):
            result = await formatter.clean(analysis_results)
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert "No Python files found" in result.message
    
    @pytest.mark.asyncio
    async def test_standardize_docstrings_success(self, formatter, temp_python_file_with_docstrings):
        """Test docstring standardization."""
        files = [temp_python_file_with_docstrings]
        
        result = await formatter.standardize_docstrings(files)
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.files_modified) > 0
        assert len(result.formatting_changes) > 0
        
        # Check that docstrings were actually modified
        with open(temp_python_file_with_docstrings, 'r') as f:
            content = f.read()
        
        # Should have capitalized and added periods
        assert '"""Test class."""' in content
        assert '"""Does something."""' in content
        assert '"""Function without period."""' in content
    
    @pytest.mark.asyncio
    async def test_standardize_docstrings_syntax_error(self, formatter, tmp_path):
        """Test docstring standardization with syntax error file."""
        # Create file with syntax error
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def test(\n    # Missing closing parenthesis")
        
        result = await formatter.standardize_docstrings([bad_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.files_modified) == 0  # Should skip files with syntax errors
    
    @pytest.mark.asyncio
    async def test_standardize_docstrings_in_content(self, formatter):
        """Test standardizing docstrings in content."""
        content = '''def test_function():
    """test function"""
    pass

class TestClass:
    """test class"""
    pass
'''
        
        tree = ast.parse(content)
        modified_content, changes_made = formatter._standardize_docstrings_in_content(content, tree)
        
        assert changes_made == 2
        assert '"""Test function."""' in modified_content
        assert '"""Test class."""' in modified_content
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_format_with_black_success(self, mock_subprocess, formatter, temp_python_file):
        """Test successful black formatting."""
        # Mock subprocess for diff
        mock_process_diff = AsyncMock()
        mock_process_diff.communicate.return_value = (
            b'--- test.py\t2024-01-01 12:00:00.000000 +0000\n+++ test.py\t2024-01-01 12:00:01.000000 +0000\n@@ -1,2 +1,2 @@\n-x=1+2\n+x = 1 + 2\n',
            b''
        )
        mock_process_diff.returncode = 0
        
        # Mock subprocess for apply
        mock_process_apply = AsyncMock()
        mock_process_apply.communicate.return_value = (b'', b'')
        mock_process_apply.returncode = 0
        
        mock_subprocess.side_effect = [mock_process_diff, mock_process_apply]
        
        result = await formatter.format_with_black([temp_python_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.files_modified) == 1
        assert len(result.formatting_changes) == 1
        assert result.formatting_changes[0].change_type == "black"
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_format_with_black_no_changes(self, mock_subprocess, formatter, temp_python_file):
        """Test black formatting with no changes needed."""
        # Mock subprocess for diff (no output = no changes)
        mock_process_diff = AsyncMock()
        mock_process_diff.communicate.return_value = (b'', b'')
        mock_process_diff.returncode = 0
        
        # Mock subprocess for apply
        mock_process_apply = AsyncMock()
        mock_process_apply.communicate.return_value = (b'', b'')
        mock_process_apply.returncode = 0
        
        mock_subprocess.side_effect = [mock_process_diff, mock_process_apply]
        
        result = await formatter.format_with_black([temp_python_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.formatting_changes) == 0  # No changes detected
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_format_with_black_error(self, mock_subprocess, formatter, temp_python_file):
        """Test black formatting with error."""
        # Mock subprocess failure
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'', b'Black formatting error')
        mock_process.returncode = 1
        
        mock_subprocess.return_value = mock_process
        
        result = await formatter.format_with_black([temp_python_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True  # Should continue despite errors
        assert len(result.files_modified) == 0
    
    @pytest.mark.asyncio
    async def test_format_with_black_empty_list(self, formatter):
        """Test black formatting with empty file list."""
        result = await formatter.format_with_black([])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert "No files to format" in result.message
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_clean_full_workflow(self, mock_subprocess, formatter, tmp_path):
        """Test complete clean workflow."""
        # Create test Python file
        test_file = tmp_path / "test.py"
        test_file.write_text('''def test():
    """test function"""
    x=1+2
    return x
''')
        
        formatter.target_directory = tmp_path
        formatter.config.auto_format = True
        
        # Mock black subprocess calls
        mock_process_diff = AsyncMock()
        mock_process_diff.communicate.return_value = (b'', b'')  # No changes
        mock_process_diff.returncode = 0
        
        mock_process_apply = AsyncMock()
        mock_process_apply.communicate.return_value = (b'', b'')
        mock_process_apply.returncode = 0
        
        mock_subprocess.side_effect = [mock_process_diff, mock_process_apply]
        
        analysis_results = AnalysisResults()
        result = await formatter.clean(analysis_results)
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.files_modified) > 0  # Should have modified files for docstrings
        
        # Check that docstring was standardized
        content = test_file.read_text()
        assert '"""Test function."""' in content


if __name__ == "__main__":
    pytest.main([__file__])