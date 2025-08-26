"""
Tests for Import Cleaner

Tests the ImportCleaner class functionality including isort integration,
unused import removal, and import organization.
"""

import ast
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest

from migration_assistant.checkup.cleaners.imports import ImportCleaner, ImportCleanupResult
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, ImportIssue, IssueType, IssueSeverity,
    ImportCleanup
)


@pytest.fixture
def config():
    """Create test configuration."""
    return CheckupConfig(
        target_directory=Path("."),
        auto_fix_imports=True,
        organize_imports=True,
        create_backup=False,  # Disable backup for tests
        dry_run=False,
        isort_config={"profile": "black", "line_length": 88}
    )


@pytest.fixture
def import_cleaner(config):
    """Create ImportCleaner instance."""
    return ImportCleaner(config)


@pytest.fixture
def temp_python_file_with_imports():
    """Create temporary Python file with various import patterns."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''import os
import sys
import unused_module
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

def main():
    """Main function."""
    path = Path(".")
    data: List[str] = []
    mapping: Dict[str, int] = defaultdict(int)
    return path, data, mapping
''')
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def temp_python_file_circular():
    """Create temporary Python file with circular import."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''# This file has a circular import
from other_module import some_function

def my_function():
    return some_function()
''')
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestImportCleaner:
    """Test cases for ImportCleaner class."""
    
    def test_init(self, config):
        """Test ImportCleaner initialization."""
        cleaner = ImportCleaner(config)
        
        assert cleaner.config == config
        assert cleaner._isort_config["profile"] == "black"
        assert cleaner._isort_config["line_length"] == 88
    
    def test_get_isort_config_defaults(self):
        """Test isort configuration defaults."""
        config = CheckupConfig()
        cleaner = ImportCleaner(config)
        
        isort_config = cleaner._get_isort_config()
        
        assert isort_config["profile"] == "black"
        assert isort_config["line_length"] == 88
        assert isort_config["known_first_party"] == ["migration_assistant"]
        assert isort_config["show_diff"] is True
    
    def test_get_isort_config_custom(self):
        """Test isort configuration with custom values."""
        config = CheckupConfig(
            isort_config={"line_length": 100, "profile": "django"}
        )
        cleaner = ImportCleaner(config)
        
        isort_config = cleaner._get_isort_config()
        
        assert isort_config["line_length"] == 100
        assert isort_config["profile"] == "django"
        assert isort_config["known_first_party"] == ["migration_assistant"]  # Default preserved
    
    def test_can_clean_issue(self, import_cleaner):
        """Test issue type checking."""
        unused_import = ImportIssue(
            file_path=Path("test.py"),
            line_number=1,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.UNUSED_IMPORT,
            message="Unused import",
            description="Test unused import",
            import_name="unused_module"
        )
        
        circular_import = ImportIssue(
            file_path=Path("test.py"),
            line_number=1,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CIRCULAR_IMPORT,
            message="Circular import",
            description="Test circular import",
            import_name="circular_module",
            is_circular=True
        )
        
        orphaned_module = ImportIssue(
            file_path=Path("test.py"),
            line_number=1,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.ORPHANED_MODULE,
            message="Orphaned module",
            description="Test orphaned module",
            import_name="orphaned_module"
        )
        
        assert import_cleaner.can_clean_issue(unused_import) is True
        assert import_cleaner.can_clean_issue(circular_import) is True
        assert import_cleaner.can_clean_issue(orphaned_module) is False
    
    def test_get_python_files(self, import_cleaner, tmp_path):
        """Test getting Python files from directory."""
        # Create test directory structure
        (tmp_path / "test1.py").write_text("import os")
        (tmp_path / "test2.py").write_text("import sys")
        (tmp_path / "test.txt").write_text("Not a Python file")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "test.pyc").write_text("Compiled Python")
        
        import_cleaner.target_directory = tmp_path
        python_files = import_cleaner._get_python_files()
        
        assert len(python_files) == 2
        assert all(f.suffix == ".py" for f in python_files)
        assert all("__pycache__" not in str(f) for f in python_files)
    
    def test_find_unused_imports(self, import_cleaner):
        """Test finding unused imports."""
        content = '''import os
import sys
import unused_module
from pathlib import Path
from typing import List

def main():
    path = Path(".")
    data: List[str] = []
    return path, data
'''
        
        tree = ast.parse(content)
        unused_imports = import_cleaner._find_unused_imports(content, tree)
        
        # Should find unused_module and sys as unused
        assert "unused_module" in unused_imports
        assert "sys" in unused_imports
        # Should not find os, Path, or List as unused
        assert "os" not in unused_imports
        assert "pathlib.Path" not in unused_imports
        assert "typing.List" not in unused_imports
    
    def test_find_unused_imports_with_string_usage(self, import_cleaner):
        """Test finding unused imports when used in strings."""
        content = '''import some_module

def main():
    # This module is used in comments: some_module
    return "some_module is referenced in string"
'''
        
        tree = ast.parse(content)
        unused_imports = import_cleaner._find_unused_imports(content, tree)
        
        # Should not find some_module as unused due to string/comment usage
        assert "some_module" not in unused_imports
    
    def test_is_used_in_strings(self, import_cleaner):
        """Test checking if name is used in strings or comments."""
        content = '''# This uses some_module in comment
def test():
    return "some_module in string"
'''
        
        assert import_cleaner._is_used_in_strings(content, "some_module") is True
        assert import_cleaner._is_used_in_strings(content, "other_module") is False
    
    def test_remove_imports_from_content(self, import_cleaner):
        """Test removing imports from content."""
        content = '''import os
import sys
import unused_module
from pathlib import Path

def main():
    return Path(".")
'''
        
        unused_imports = ["sys", "unused_module"]
        modified_content = import_cleaner._remove_imports_from_content(content, unused_imports)
        
        assert "import sys" not in modified_content
        assert "import unused_module" not in modified_content
        assert "import os" in modified_content
        assert "from pathlib import Path" in modified_content
    
    def test_generate_isort_config(self, import_cleaner):
        """Test isort configuration generation."""
        config_content = import_cleaner._generate_isort_config()
        
        assert "[settings]" in config_content
        assert "profile=black" in config_content
        assert "line_length=88" in config_content
        assert "known_first_party=migration_assistant" in config_content
    
    def test_parse_isort_diff(self, import_cleaner):
        """Test parsing isort diff output."""
        diff_output = """Fixing test1.py
Fixing test2.py"""
        files = [Path("test1.py"), Path("test2.py"), Path("test3.py")]
        
        changes = import_cleaner._parse_isort_diff(diff_output, files)
        
        assert len(changes) == 2
        assert changes[0]['file_path'] == Path("test1.py")
        assert changes[1]['file_path'] == Path("test2.py")
        assert "Organized imports" in changes[0]['description']
    
    def test_group_circular_imports(self, import_cleaner):
        """Test grouping circular imports."""
        import1 = ImportIssue(
            file_path=Path("module1.py"),
            line_number=1,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CIRCULAR_IMPORT,
            message="Circular import",
            description="Test circular import 1",
            import_name="module2",
            is_circular=True,
            dependency_chain=["module1", "module2"]
        )
        
        import2 = ImportIssue(
            file_path=Path("module2.py"),
            line_number=1,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CIRCULAR_IMPORT,
            message="Circular import",
            description="Test circular import 2",
            import_name="module1",
            is_circular=True,
            dependency_chain=["module2", "module1"]
        )
        
        groups = import_cleaner._group_circular_imports([import1, import2])
        
        assert len(groups) == 1
        assert len(groups[0]) == 2
    
    def test_add_circular_import_comment(self, import_cleaner):
        """Test adding circular import comment."""
        content = '''from other_module import some_function

def main():
    return some_function()
'''
        
        modified_content = import_cleaner._add_circular_import_comment(content, "some_function")
        
        assert "# TODO: Circular import detected" in modified_content
        assert "some_function" in modified_content
    
    @pytest.mark.asyncio
    async def test_clean_dry_run(self, import_cleaner):
        """Test clean method in dry run mode."""
        import_cleaner.config.dry_run = True
        analysis_results = AnalysisResults()
        
        result = await import_cleaner.clean(analysis_results)
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        assert "Dry run" in result.message
    
    @pytest.mark.asyncio
    async def test_clean_no_files(self, import_cleaner, tmp_path):
        """Test clean method with no Python files."""
        import_cleaner.target_directory = tmp_path
        analysis_results = AnalysisResults()
        
        with patch.object(import_cleaner, '_get_python_files', return_value=[]):
            result = await import_cleaner.clean(analysis_results)
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        assert "No Python files found" in result.message
    
    @pytest.mark.asyncio
    async def test_remove_unused_imports_success(self, import_cleaner, temp_python_file_with_imports):
        """Test removing unused imports."""
        files = [temp_python_file_with_imports]
        
        result = await import_cleaner.remove_unused_imports(files)
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        
        # Check that unused imports were removed
        with open(temp_python_file_with_imports, 'r') as f:
            content = f.read()
        
        # unused_module should be removed, but used imports should remain
        assert "import unused_module" not in content
        assert "from pathlib import Path" in content
        assert "from typing import List" in content
    
    @pytest.mark.asyncio
    async def test_remove_unused_imports_syntax_error(self, import_cleaner, tmp_path):
        """Test removing unused imports with syntax error file."""
        # Create file with syntax error
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("import os\ndef test(\n    # Missing closing parenthesis")
        
        result = await import_cleaner.remove_unused_imports([bad_file])
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        assert len(result.files_modified) == 0  # Should skip files with syntax errors
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_optimize_import_order_success(self, mock_subprocess, import_cleaner, temp_python_file_with_imports):
        """Test successful import organization with isort."""
        # Mock subprocess for diff check (returns non-zero when changes needed)
        mock_process_diff = AsyncMock()
        mock_process_diff.communicate.return_value = (
            b'Fixing test.py\n',
            b''
        )
        mock_process_diff.returncode = 1  # Non-zero indicates changes needed
        
        # Mock subprocess for apply
        mock_process_apply = AsyncMock()
        mock_process_apply.communicate.return_value = (b'', b'')
        mock_process_apply.returncode = 0
        
        mock_subprocess.side_effect = [mock_process_diff, mock_process_apply]
        
        result = await import_cleaner.optimize_import_order([temp_python_file_with_imports])
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        assert len(result.files_modified) == 1
        assert len(result.import_cleanups) == 1
        assert result.import_cleanups[0].reorganized_imports is True
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_optimize_import_order_no_changes(self, mock_subprocess, import_cleaner, temp_python_file_with_imports):
        """Test import organization with no changes needed."""
        # Mock subprocess for diff check (returns zero when no changes needed)
        mock_process_diff = AsyncMock()
        mock_process_diff.communicate.return_value = (b'', b'')
        mock_process_diff.returncode = 0  # Zero indicates no changes needed
        
        mock_subprocess.return_value = mock_process_diff
        
        result = await import_cleaner.optimize_import_order([temp_python_file_with_imports])
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        assert len(result.import_cleanups) == 0  # No changes made
    
    @pytest.mark.asyncio
    async def test_optimize_import_order_empty_list(self, import_cleaner):
        """Test import organization with empty file list."""
        result = await import_cleaner.optimize_import_order([])
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        assert "No files to organize" in result.message
    
    @pytest.mark.asyncio
    async def test_resolve_circular_imports(self, import_cleaner, temp_python_file_circular):
        """Test resolving circular imports."""
        circular_import = ImportIssue(
            file_path=temp_python_file_circular,
            line_number=2,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CIRCULAR_IMPORT,
            message="Circular import",
            description="Test circular import",
            import_name="some_function",
            is_circular=True,
            dependency_chain=["other_module", "current_module"]
        )
        
        result = await import_cleaner.resolve_circular_imports([circular_import])
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        
        # Check that comment was added
        with open(temp_python_file_circular, 'r') as f:
            content = f.read()
        
        assert "# TODO: Circular import detected" in content
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_clean_full_workflow(self, mock_subprocess, import_cleaner, tmp_path):
        """Test complete clean workflow."""
        # Create test Python file
        test_file = tmp_path / "test.py"
        test_file.write_text('''import os
import unused_module
from pathlib import Path

def main():
    return Path(".")
''')
        
        import_cleaner.target_directory = tmp_path
        import_cleaner.config.auto_fix_imports = True
        import_cleaner.config.organize_imports = True
        
        # Mock isort subprocess calls
        mock_process_diff = AsyncMock()
        mock_process_diff.communicate.return_value = (b'', b'')  # No changes needed
        mock_process_diff.returncode = 0
        
        mock_subprocess.return_value = mock_process_diff
        
        analysis_results = AnalysisResults()
        result = await import_cleaner.clean(analysis_results)
        
        assert isinstance(result, ImportCleanupResult)
        assert result.success is True
        assert len(result.files_modified) > 0  # Should have modified files for unused imports
        
        # Check that unused import was removed
        content = test_file.read_text()
        assert "import unused_module" not in content
        assert "from pathlib import Path" in content


if __name__ == "__main__":
    pytest.main([__file__])