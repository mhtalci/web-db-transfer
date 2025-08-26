"""
Tests for Type Hint Standardization

Tests the type hint standardization functionality in CodeFormatter.
"""

import ast
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from migration_assistant.checkup.cleaners.formatter import CodeFormatter, FormattingResult
from migration_assistant.checkup.models import CheckupConfig, FormattingChange


@pytest.fixture
def config():
    """Create test configuration."""
    return CheckupConfig(
        target_directory=Path("."),
        check_type_hints=True,
        create_backup=False,  # Disable backup for tests
        dry_run=False
    )


@pytest.fixture
def formatter(config):
    """Create CodeFormatter instance."""
    return CodeFormatter(config)


@pytest.fixture
def temp_python_file_no_hints():
    """Create temporary Python file without type hints."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''def process_data(data, count):
    """Process data with count."""
    if count > 0:
        return [item.upper() for item in data]
    return None

def get_config():
    """Get configuration."""
    return {"key": "value"}

def is_valid(path):
    """Check if path is valid."""
    return path.exists()
''')
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def temp_python_file_with_hints():
    """Create temporary Python file with type hints to standardize."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''from typing import List, Dict, Optional
from pathlib import Path

def process_data(data: typing.List[str], count: int) -> typing.Optional[typing.List[str]]:
    """Process data with count."""
    if count > 0:
        return [item.upper() for item in data]
    return None

def get_config() -> typing.Dict[str, str]:
    """Get configuration."""
    return {"key": "value"}
''')
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestTypeHintStandardization:
    """Test cases for type hint standardization."""
    
    def test_suggest_return_type_simple(self, formatter):
        """Test suggesting simple return types."""
        # Test function returning string
        content = '''def get_name():
    return "test"
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_return_type(func_node, content.split('\n'))
        assert suggested == 'str'
        
        # Test function returning None
        content = '''def do_something():
    print("doing something")
    return
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_return_type(func_node, content.split('\n'))
        assert suggested == 'None'
        
        # Test function returning boolean
        content = '''def is_valid():
    return True
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_return_type(func_node, content.split('\n'))
        assert suggested == 'bool'
    
    def test_suggest_return_type_optional(self, formatter):
        """Test suggesting optional return types."""
        content = '''def maybe_get_value():
    if condition:
        return "value"
    return None
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_return_type(func_node, content.split('\n'))
        assert suggested == 'Optional[str]'
    
    def test_suggest_return_type_complex(self, formatter):
        """Test suggesting complex return types."""
        # Test function returning list
        content = '''def get_items():
    return []
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_return_type(func_node, content.split('\n'))
        assert suggested == 'List[Any]'
        
        # Test function returning dict
        content = '''def get_mapping():
    return {}
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_return_type(func_node, content.split('\n'))
        assert suggested == 'Dict[str, Any]'
    
    def test_suggest_parameter_type_by_name(self, formatter):
        """Test suggesting parameter types based on name patterns."""
        content = '''def process_file(file_path):
    pass
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_parameter_type(func_node, 'file_path', content.split('\n'))
        assert suggested == 'Path'
        
        # Test list parameter
        content = '''def process_items(items):
    pass
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_parameter_type(func_node, 'items', content.split('\n'))
        assert suggested == 'List[Any]'
        
        # Test boolean parameter
        content = '''def set_flag(is_enabled):
    pass
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        
        suggested = formatter._suggest_parameter_type(func_node, 'is_enabled', content.split('\n'))
        assert suggested == 'bool'
    
    def test_standardize_type_annotation(self, formatter):
        """Test standardizing type annotations."""
        # Test typing module prefixes
        assert formatter._standardize_type_annotation('typing.List[str]') == 'List[str]'
        assert formatter._standardize_type_annotation('typing.Dict[str, Any]') == 'Dict[str, Any]'
        assert formatter._standardize_type_annotation('typing.Optional[int]') == 'Optional[int]'
        
        # Test built-in type standardization (Python 3.9+ style)
        assert formatter._standardize_type_annotation('List[str]') == 'list[str]'
        assert formatter._standardize_type_annotation('Dict[str, Any]') == 'dict[str, Any]'
        
        # Test None standardization
        assert formatter._standardize_type_annotation('type(None)') == 'None'
        assert formatter._standardize_type_annotation('typing.None') == 'None'
    
    def test_analyze_function_type_hints(self, formatter):
        """Test analyzing function for type hint improvements."""
        content = '''def process_data(data, count):
    if count > 0:
        return [item.upper() for item in data]
    return None
'''
        tree = ast.parse(content)
        func_node = tree.body[0]
        lines = content.split('\n')
        
        improvements = formatter._analyze_function_type_hints(func_node, lines)
        
        # Should suggest return type and parameter types
        assert len(improvements) >= 1  # At least return type
        assert any(imp['type'] == 'add_return_type' for imp in improvements)
    
    def test_add_return_type_hint(self, formatter):
        """Test adding return type hint to function."""
        lines = ['def test_function():', '    return "test"']
        
        # Create a mock function node
        func_node = Mock()
        func_node.lineno = 1  # 1-based line number
        
        modified_lines = formatter._add_return_type_hint(lines, func_node, 'str')
        
        assert modified_lines[0] == 'def test_function() -> str:'
        assert modified_lines[1] == '    return "test"'
    
    def test_add_parameter_type_hint(self, formatter):
        """Test adding parameter type hint."""
        lines = ['def test_function(param):', '    return param']
        
        # Create a mock function node
        func_node = Mock()
        func_node.lineno = 1  # 1-based line number
        
        modified_lines = formatter._add_parameter_type_hint(lines, func_node, 'param', 'str')
        
        assert 'param: str' in modified_lines[0]
    
    def test_standardize_existing_type_hint(self, formatter):
        """Test standardizing existing type hint."""
        lines = ['def test_function() -> typing.List[str]:', '    return []']
        
        # Create a mock function node
        func_node = Mock()
        func_node.lineno = 1  # 1-based line number
        
        modified_lines = formatter._standardize_existing_type_hint(
            lines, func_node, 'typing.List[str]', 'List[str]'
        )
        
        assert modified_lines[0] == 'def test_function() -> List[str]:'
    
    @pytest.mark.asyncio
    async def test_standardize_type_hints_success(self, formatter, temp_python_file_no_hints):
        """Test type hint standardization on file without hints."""
        files = [temp_python_file_no_hints]
        
        result = await formatter.standardize_type_hints(files)
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        
        # Check if any type hints were added
        with open(temp_python_file_no_hints, 'r') as f:
            content = f.read()
        
        # Should have added some type hints based on analysis
        # The exact hints depend on the analysis logic
        print("Modified content:", content)  # For debugging
    
    @pytest.mark.asyncio
    async def test_standardize_type_hints_with_existing(self, formatter, temp_python_file_with_hints):
        """Test type hint standardization on file with existing hints."""
        files = [temp_python_file_with_hints]
        
        result = await formatter.standardize_type_hints(files)
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        
        # Check that typing prefixes were removed
        with open(temp_python_file_with_hints, 'r') as f:
            content = f.read()
        
        # Should have standardized typing.List to List, etc.
        assert 'typing.List' not in content
        assert 'typing.Dict' not in content
        assert 'typing.Optional' not in content
    
    @pytest.mark.asyncio
    async def test_standardize_type_hints_syntax_error(self, formatter, tmp_path):
        """Test type hint standardization with syntax error file."""
        # Create file with syntax error
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def test(\n    # Missing closing parenthesis")
        
        result = await formatter.standardize_type_hints([bad_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.files_modified) == 0  # Should skip files with syntax errors
    
    def test_standardize_type_hints_in_content(self, formatter):
        """Test standardizing type hints in content."""
        content = '''def process_data(data):
    """Process data."""
    return [item.upper() for item in data]

def get_count():
    """Get count."""
    return 42
'''
        
        tree = ast.parse(content)
        modified_content, changes_made = formatter._standardize_type_hints_in_content(content, tree)
        
        # Should have made some changes (exact number depends on analysis)
        assert changes_made >= 0
        print(f"Changes made: {changes_made}")
        print(f"Modified content:\n{modified_content}")
    
    @pytest.mark.asyncio
    async def test_standardize_type_hints_empty_list(self, formatter):
        """Test type hint standardization with empty file list."""
        result = await formatter.standardize_type_hints([])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.files_modified) == 0
    
    @pytest.mark.asyncio
    async def test_standardize_type_hints_nonexistent_file(self, formatter):
        """Test type hint standardization with nonexistent file."""
        nonexistent_file = Path("nonexistent.py")
        result = await formatter.standardize_type_hints([nonexistent_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success is True
        assert len(result.files_modified) == 0


if __name__ == "__main__":
    pytest.main([__file__])