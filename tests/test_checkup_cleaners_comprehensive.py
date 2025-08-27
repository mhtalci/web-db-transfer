"""
Comprehensive unit tests for checkup cleaners.

Tests all cleaner classes to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from migration_assistant.checkup.cleaners.formatter import CodeFormatter, FormattingResult
from migration_assistant.checkup.cleaners.imports import ImportCleaner
from migration_assistant.checkup.cleaners.files import FileOrganizer, ReorganizationPlan
from migration_assistant.checkup.cleaners.base import BaseCleaner, CleanupResult
from migration_assistant.checkup.models import (
    CheckupConfig, QualityIssue, ImportIssue, StructureIssue,
    IssueType, IssueSeverity, FormattingChange, FileMove, FileRemoval
)


class TestBaseCleaner:
    """Test cases for BaseCleaner abstract class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            auto_format=True,
            auto_fix_imports=True,
            dry_run=False,
            create_backup=True
        )
    
    def test_base_cleaner_initialization(self, config):
        """Test BaseCleaner initialization."""
        # Create a concrete implementation for testing
        class TestCleaner(BaseCleaner):
            def can_clean_issue(self, issue):
                return True
            
            async def clean(self, issues=None):
                return CleanupResult(success=True)
        
        cleaner = TestCleaner(config)
        assert cleaner.config == config
        assert cleaner.target_directory == config.target_directory
        assert cleaner.dry_run == config.dry_run
    
    def test_cleanup_result_creation(self):
        """Test CleanupResult creation."""
        result = CleanupResult(
            success=True,
            message="Test cleanup completed",
            files_modified=[Path("test.py")]
        )
        
        assert result.success is True
        assert result.message == "Test cleanup completed"
        assert len(result.files_modified) == 1
        assert result.files_modified[0] == Path("test.py")
    
    def test_get_python_files(self, config, tmp_path):
        """Test getting Python files from directory."""
        class TestCleaner(BaseCleaner):
            def can_clean_issue(self, issue):
                return True
            
            async def clean(self, issues=None):
                return CleanupResult(success=True)
        
        # Create test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test.txt").write_text("not python")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "test.pyc").write_text("compiled")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.py").write_text("print('nested')")
        
        config.target_directory = tmp_path
        cleaner = TestCleaner(config)
        
        python_files = cleaner.get_python_files()
        python_file_names = [f.name for f in python_files]
        
        assert "test.py" in python_file_names
        assert "nested.py" in python_file_names
        assert "test.txt" not in python_file_names
        assert "test.pyc" not in python_file_names


class TestCodeFormatter:
    """Test cases for CodeFormatter."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            auto_format=True,
            dry_run=False,
            black_config={
                "line_length": 88,
                "target_version": ["py311"]
            },
            isort_config={
                "profile": "black",
                "known_first_party": ["migration_assistant"]
            }
        )
    
    @pytest.fixture
    def formatter(self, config):
        """Create CodeFormatter instance."""
        return CodeFormatter(config)
    
    def test_initialization(self, formatter, config):
        """Test formatter initialization."""
        assert formatter.config == config
        assert formatter._black_config["line_length"] == 88
        assert formatter._isort_config["profile"] == "black"
    
    def test_get_black_config(self, formatter):
        """Test black configuration generation."""
        black_config = formatter._get_black_config()
        
        assert "line_length" in black_config
        assert "target_version" in black_config
        assert black_config["line_length"] == 88
    
    def test_get_isort_config(self, formatter):
        """Test isort configuration generation."""
        isort_config = formatter._get_isort_config()
        
        assert "profile" in isort_config
        assert "known_first_party" in isort_config
        assert isort_config["profile"] == "black"
    
    def test_can_clean_issue(self, formatter):
        """Test issue type checking."""
        style_issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            description="Line too long"
        )
        
        syntax_error = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            description="Invalid syntax"
        )
        
        assert formatter.can_clean_issue(style_issue) is True
        assert formatter.can_clean_issue(syntax_error) is False
    
    def test_generate_black_config(self, formatter):
        """Test black configuration file generation."""
        config_content = formatter._generate_black_config()
        
        assert "line-length = 88" in config_content
        assert "target-version" in config_content
        assert "skip-string-normalization = false" in config_content
    
    def test_parse_black_diff_no_changes(self, formatter):
        """Test parsing black diff with no changes."""
        diff_output = ""
        changes = formatter._parse_black_diff(diff_output, [Path("test.py")])
        
        assert len(changes) == 0
    
    def test_parse_black_diff_with_changes(self, formatter):
        """Test parsing black diff with changes."""
        diff_output = """--- test.py	2024-01-01 12:00:00.000000 +0000
+++ test.py	2024-01-01 12:00:01.000000 +0000
@@ -1,3 +1,3 @@
 def test():
-    x=1
+    x = 1
     return x"""
        
        changes = formatter._parse_black_diff(diff_output, [Path("test.py")])
        
        assert len(changes) > 0
        assert changes[0].file_path == Path("test.py")
        assert changes[0].change_type == "formatting"
        assert changes[0].lines_changed > 0
    
    def test_standardize_single_docstring_function(self, formatter):
        """Test standardizing function docstrings."""
        # Test lowercase start
        result = formatter._standardize_single_docstring("does something", "function")
        assert result == "Does something."
        
        # Test already proper
        result = formatter._standardize_single_docstring("Does something.", "function")
        assert result == "Does something."
        
        # Test with period
        result = formatter._standardize_single_docstring("Does something", "function")
        assert result == "Does something."
    
    def test_standardize_single_docstring_class(self, formatter):
        """Test standardizing class docstrings."""
        # Test lowercase start
        result = formatter._standardize_single_docstring("test class", "class")
        assert result == "Test class."
        
        # Test already proper
        result = formatter._standardize_single_docstring("Test class.", "class")
        assert result == "Test class."
    
    def test_format_docstring_lines_single(self, formatter):
        """Test formatting single-line docstring."""
        lines = formatter._format_docstring_lines("Test docstring.", "    ")
        
        assert len(lines) == 1
        assert lines[0] == '    """Test docstring."""'
    
    def test_format_docstring_lines_multi(self, formatter):
        """Test formatting multi-line docstring."""
        lines = formatter._format_docstring_lines("Test docstring.\nWith multiple lines.", "    ")
        
        assert len(lines) == 3
        assert lines[0] == '    """'
        assert lines[1] == '    Test docstring.'
        assert lines[2] == '    """'
    
    @pytest.mark.asyncio
    async def test_clean_dry_run(self, formatter):
        """Test clean method in dry run mode."""
        formatter.config.dry_run = True
        
        result = await formatter.clean()
        
        assert result.success is True
        assert "dry run" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_clean_no_files(self, formatter, tmp_path):
        """Test clean method with no Python files."""
        formatter.target_directory = tmp_path
        
        result = await formatter.clean()
        
        assert result.success is True
        assert len(result.files_modified) == 0
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_format_with_black_success(self, mock_subprocess, formatter, tmp_path):
        """Test successful black formatting."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test():x=1;return x")
        
        # Mock subprocess for diff
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"--- test.py\n+++ test.py\n@@ -1 +1 @@\n-def test():x=1;return x\n+def test():\n+    x = 1\n+    return x",
            b""
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        result = await formatter.format_with_black([test_file])
        
        assert result.success is True
        assert len(result.formatting_changes) > 0
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_format_with_black_no_changes(self, mock_subprocess, formatter, tmp_path):
        """Test black formatting with no changes needed."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test():\n    return True")
        
        # Mock subprocess for diff (no output = no changes)
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        result = await formatter.format_with_black([test_file])
        
        assert result.success is True
        assert len(result.formatting_changes) == 0
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_format_with_black_error(self, mock_subprocess, formatter, tmp_path):
        """Test black formatting with error."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def broken_syntax(")
        
        # Mock subprocess failure
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"error: cannot use --safe with this file")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process
        
        result = await formatter.format_with_black([test_file])
        
        assert result.success is False
        assert "error" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_standardize_docstrings_success(self, formatter, tmp_path):
        """Test docstring standardization."""
        code = '''def test_function():
    """test docstring without proper capitalization"""
    return True

class TestClass:
    """test class docstring"""
    pass
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)
        
        result = await formatter.standardize_docstrings([test_file])
        
        assert result.success is True
        # Check that file was modified
        modified_content = test_file.read_text()
        assert "Test docstring" in modified_content or "Test class" in modified_content
    
    @pytest.mark.asyncio
    async def test_standardize_docstrings_syntax_error(self, formatter, tmp_path):
        """Test docstring standardization with syntax error file."""
        # Create file with syntax error
        test_file = tmp_path / "bad_syntax.py"
        test_file.write_text("def broken_function(\n    pass")
        
        result = await formatter.standardize_docstrings([test_file])
        
        # Should handle syntax errors gracefully
        assert result.success is True  # Should not fail completely
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_organize_imports_with_isort(self, mock_subprocess, formatter, tmp_path):
        """Test import organization with isort."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import sys\nimport os\nfrom pathlib import Path")
        
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        result = await formatter.organize_imports_with_isort([test_file])
        
        assert result.success is True


class TestImportCleaner:
    """Test cases for ImportCleaner."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            auto_fix_imports=True,
            dry_run=False
        )
    
    @pytest.fixture
    def cleaner(self, config):
        """Create ImportCleaner instance."""
        return ImportCleaner(config)
    
    def test_initialization(self, cleaner, config):
        """Test cleaner initialization."""
        assert cleaner.config == config
    
    def test_can_clean_issue(self, cleaner):
        """Test issue type checking."""
        import_issue = ImportIssue(
            file_path=Path("test.py"),
            line_number=1,
            issue_type=IssueType.UNUSED_IMPORT,
            severity=IssueSeverity.LOW,
            module_name="unused_module",
            description="Unused import"
        )
        
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            description="Style issue"
        )
        
        assert cleaner.can_clean_issue(import_issue) is True
        assert cleaner.can_clean_issue(quality_issue) is False
    
    @pytest.mark.asyncio
    async def test_remove_unused_imports(self, cleaner, tmp_path):
        """Test removing unused imports."""
        code = """import os
import sys  # Used
import json  # Unused
from pathlib import Path  # Used

def test_function():
    current_dir = sys.path[0]
    path = Path(current_dir)
    return path
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)
        
        # Create mock unused import issues
        unused_imports = [
            ImportIssue(
                file_path=test_file,
                line_number=3,
                issue_type=IssueType.UNUSED_IMPORT,
                severity=IssueSeverity.LOW,
                module_name="json",
                description="Unused import: json"
            )
        ]
        
        result = await cleaner.remove_unused_imports([test_file], unused_imports)
        
        assert result.success is True
        # Check that unused import was removed
        modified_content = test_file.read_text()
        assert "import json" not in modified_content
        assert "import sys" in modified_content  # Should keep used imports
    
    @pytest.mark.asyncio
    async def test_clean_dry_run(self, cleaner):
        """Test clean method in dry run mode."""
        cleaner.config.dry_run = True
        
        result = await cleaner.clean()
        
        assert result.success is True
        assert "dry run" in result.message.lower()
    
    def test_is_import_used_in_content(self, cleaner):
        """Test checking if import is used in content."""
        content = """
import os
from pathlib import Path

def test_function():
    current_dir = os.getcwd()
    path = Path(current_dir)
    return path.exists()
"""
        
        assert cleaner._is_import_used_in_content("os", content) is True
        assert cleaner._is_import_used_in_content("Path", content) is True
        assert cleaner._is_import_used_in_content("json", content) is False
    
    def test_remove_import_line(self, cleaner):
        """Test removing specific import line."""
        content = """import os
import sys
import json
from pathlib import Path

def test():
    pass
"""
        
        modified = cleaner._remove_import_line(content, "import json")
        
        assert "import json" not in modified
        assert "import os" in modified
        assert "import sys" in modified
        assert "from pathlib import Path" in modified


class TestFileOrganizer:
    """Test cases for FileOrganizer."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            auto_organize_files=True,
            dry_run=False,
            max_file_moves=10
        )
    
    @pytest.fixture
    def organizer(self, config):
        """Create FileOrganizer instance."""
        return FileOrganizer(config)
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project structure for testing."""
        # Create a sample project structure with issues
        project_structure = {
            'README.md': '# Test Project',
            'pyproject.toml': '[tool.black]\nline-length = 88',
            'src/mypackage/__init__.py': '',
            'src/mypackage/main.py': 'def main(): pass',
            'tests/test_main.py': 'def test_main(): pass',
            'test_outside.py': 'def test_something(): pass',  # Misplaced
            'script_outside.py': 'if __name__ == "__main__": pass',  # Misplaced
            'empty_dir1/.gitkeep': '',  # Will be empty after removing .gitkeep
            'empty_dir2/nested_empty/.gitkeep': '',  # Nested empty
            'config_outside.yaml': 'key: value',  # Misplaced config
        }
        
        # Create files and directories
        for file_path, content in project_structure.items():
            full_path = tmp_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Remove .gitkeep files to create truly empty directories
        (tmp_path / 'empty_dir1' / '.gitkeep').unlink()
        (tmp_path / 'empty_dir2' / 'nested_empty' / '.gitkeep').unlink()
        
        return tmp_path
    
    def test_initialization(self, organizer, config):
        """Test organizer initialization."""
        assert organizer.config == config
        assert organizer.max_moves == 10
    
    def test_can_clean_issue(self, organizer):
        """Test issue type checking."""
        structure_issue = StructureIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.MISPLACED_FILE,
            severity=IssueSeverity.MEDIUM,
            description="File is misplaced",
            suggested_location=Path("tests/test.py")
        )
        
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=1,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            description="Style issue"
        )
        
        assert organizer.can_clean_issue(structure_issue) is True
        assert organizer.can_clean_issue(quality_issue) is False
    
    def test_detect_empty_directories(self, organizer, temp_project):
        """Test empty directory detection."""
        organizer.target_directory = temp_project
        
        empty_dirs = organizer._detect_empty_directories()
        empty_dir_names = [d.name for d in empty_dirs]
        
        assert "empty_dir1" in empty_dir_names
        assert "nested_empty" in empty_dir_names
    
    def test_create_reorganization_plan(self, organizer, temp_project):
        """Test reorganization plan creation."""
        organizer.target_directory = temp_project
        
        # Create mock structure issues
        issues = [
            StructureIssue(
                file_path=temp_project / "test_outside.py",
                issue_type=IssueType.MISPLACED_FILE,
                severity=IssueSeverity.MEDIUM,
                description="Test file outside tests directory",
                suggested_location=temp_project / "tests" / "test_outside.py"
            )
        ]
        
        plan = organizer._create_reorganization_plan(issues)
        
        assert isinstance(plan, ReorganizationPlan)
        assert len(plan.file_moves) > 0
        assert plan.file_moves[0].source_path == temp_project / "test_outside.py"
        assert plan.file_moves[0].destination_path == temp_project / "tests" / "test_outside.py"
    
    @pytest.mark.asyncio
    async def test_remove_empty_directories(self, organizer, temp_project):
        """Test empty directory removal."""
        organizer.target_directory = temp_project
        
        # Ensure empty directories exist
        empty_dirs = organizer._detect_empty_directories()
        assert len(empty_dirs) > 0
        
        result = await organizer.remove_empty_directories(empty_dirs)
        
        assert result.success is True
        assert len(result.files_modified) > 0
        
        # Check that empty directories were removed
        remaining_empty = organizer._detect_empty_directories()
        assert len(remaining_empty) < len(empty_dirs)
    
    @pytest.mark.asyncio
    async def test_move_misplaced_files(self, organizer, temp_project):
        """Test moving misplaced files."""
        organizer.target_directory = temp_project
        
        # Create file moves
        file_moves = [
            FileMove(
                source_path=temp_project / "test_outside.py",
                destination_path=temp_project / "tests" / "test_outside.py",
                reason="Test file should be in tests directory"
            )
        ]
        
        result = await organizer.move_misplaced_files(file_moves)
        
        assert result.success is True
        assert len(result.files_modified) > 0
        
        # Check that file was moved
        assert not (temp_project / "test_outside.py").exists()
        assert (temp_project / "tests" / "test_outside.py").exists()
    
    @pytest.mark.asyncio
    async def test_clean_dry_run(self, organizer):
        """Test clean method in dry run mode."""
        organizer.config.dry_run = True
        
        result = await organizer.clean()
        
        assert result.success is True
        assert "dry run" in result.message.lower()
    
    def test_reorganization_plan_creation(self):
        """Test ReorganizationPlan creation."""
        file_moves = [
            FileMove(
                source_path=Path("source.py"),
                destination_path=Path("dest.py"),
                reason="Test move"
            )
        ]
        
        removals = [
            FileRemoval(
                file_path=Path("remove.py"),
                reason="Empty file"
            )
        ]
        
        plan = ReorganizationPlan(
            file_moves=file_moves,
            directory_removals=removals,
            estimated_impact="Low"
        )
        
        assert len(plan.file_moves) == 1
        assert len(plan.directory_removals) == 1
        assert plan.estimated_impact == "Low"
        assert plan.total_operations == 2
    
    def test_validate_file_move_safety(self, organizer, temp_project):
        """Test file move safety validation."""
        organizer.target_directory = temp_project
        
        # Test safe move
        safe_move = FileMove(
            source_path=temp_project / "test_outside.py",
            destination_path=temp_project / "tests" / "test_moved.py",
            reason="Safe move"
        )
        
        is_safe = organizer._validate_file_move_safety(safe_move)
        assert is_safe is True
        
        # Test unsafe move (destination exists)
        (temp_project / "tests" / "existing.py").write_text("existing content")
        unsafe_move = FileMove(
            source_path=temp_project / "test_outside.py",
            destination_path=temp_project / "tests" / "existing.py",
            reason="Unsafe move"
        )
        
        is_safe = organizer._validate_file_move_safety(unsafe_move)
        assert is_safe is False
    
    def test_estimate_reorganization_impact(self, organizer):
        """Test reorganization impact estimation."""
        # Small reorganization
        small_plan = ReorganizationPlan(
            file_moves=[
                FileMove(Path("a.py"), Path("b.py"), "test")
            ],
            directory_removals=[],
            estimated_impact=""
        )
        
        impact = organizer._estimate_reorganization_impact(small_plan)
        assert impact in ["Low", "Medium", "High"]
        
        # Large reorganization
        large_moves = [
            FileMove(Path(f"file{i}.py"), Path(f"new/file{i}.py"), "test")
            for i in range(20)
        ]
        large_plan = ReorganizationPlan(
            file_moves=large_moves,
            directory_removals=[],
            estimated_impact=""
        )
        
        impact = organizer._estimate_reorganization_impact(large_plan)
        assert impact in ["Medium", "High"]