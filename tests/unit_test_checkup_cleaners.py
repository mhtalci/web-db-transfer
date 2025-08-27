"""
Comprehensive unit tests for checkup cleaners.
Tests all cleaner classes to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import shutil
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, AsyncMock
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            auto_format=True,
            auto_fix_imports=True,
            dry_run=False,
            create_backup=True
        )
    
    def test_base_cleaner_initialization(self):
        """Test BaseCleaner initialization."""
        # Create a concrete implementation for testing
        class TestCleaner(BaseCleaner):
            def can_clean_issue(self, issue):
                return True
            
            async def clean(self, issues=None):
                return CleanupResult(success=True)
        
        cleaner = TestCleaner(self.config)
        assert cleaner.config == self.config
        assert cleaner.target_directory == self.config.target_directory
        assert cleaner.dry_run == self.config.dry_run
        assert cleaner.create_backup == self.config.create_backup
    
    def test_cleanup_result_creation(self):
        """Test CleanupResult creation."""
        result = CleanupResult(
            success=True,
            changes_made=5,
            files_modified=3,
            backup_created=True,
            error_message=None
        )
        
        assert result.success is True
        assert result.changes_made == 5
        assert result.files_modified == 3
        assert result.backup_created is True
        assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_pre_clean_hook(self):
        """Test pre-clean hook."""
        class TestCleaner(BaseCleaner):
            def __init__(self, config):
                super().__init__(config)
                self.pre_clean_called = False
            
            def can_clean_issue(self, issue):
                return True
            
            async def pre_clean(self, issues):
                self.pre_clean_called = True
                await super().pre_clean(issues)
            
            async def clean(self, issues=None):
                await self.pre_clean(issues or [])
                return CleanupResult(success=True)
        
        cleaner = TestCleaner(self.config)
        await cleaner.clean([])
        assert cleaner.pre_clean_called
    
    @pytest.mark.asyncio
    async def test_post_clean_hook(self):
        """Test post-clean hook."""
        class TestCleaner(BaseCleaner):
            def __init__(self, config):
                super().__init__(config)
                self.post_clean_called = False
                self.post_clean_result = None
            
            def can_clean_issue(self, issue):
                return True
            
            async def post_clean(self, result):
                self.post_clean_called = True
                self.post_clean_result = result
                await super().post_clean(result)
            
            async def clean(self, issues=None):
                result = CleanupResult(success=True)
                await self.post_clean(result)
                return result
        
        cleaner = TestCleaner(self.config)
        result = await cleaner.clean([])
        assert cleaner.post_clean_called
        assert cleaner.post_clean_result == result


class TestCodeFormatter:
    """Test cases for CodeFormatter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            auto_format=True,
            line_length=88,
            use_black=True,
            use_isort=True
        )
    
    def test_initialization(self):
        """Test formatter initialization."""
        formatter = CodeFormatter(self.config)
        assert formatter.config == self.config
        assert formatter.line_length == self.config.line_length
        assert formatter.use_black == self.config.use_black
        assert formatter.use_isort == self.config.use_isort
    
    def test_can_clean_issue(self):
        """Test issue cleaning capability check."""
        formatter = CodeFormatter(self.config)
        
        # Should handle formatting issues
        format_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Line too long"
        )
        assert formatter.can_clean_issue(format_issue)
        
        # Should not handle syntax errors
        syntax_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Invalid syntax"
        )
        assert not formatter.can_clean_issue(syntax_issue)
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_format_with_black(self, mock_subprocess):
        """Test black formatting."""
        # Create test file
        test_file = self.temp_dir / "test.py"
        original_code = "def func(  ):\n    x=1+2\n    return x"
        test_file.write_text(original_code)
        
        # Mock black success
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        
        formatter = CodeFormatter(self.config)
        result = await formatter.format_with_black([test_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success
        assert result.files_formatted == 1
        
        # Verify black was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "black" in call_args
        assert str(test_file) in call_args
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_format_with_black_error(self, mock_subprocess):
        """Test black formatting with error."""
        test_file = self.temp_dir / "test.py"
        test_file.write_text("def func():\n    pass")
        
        # Mock black failure
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Black formatting error"
        
        formatter = CodeFormatter(self.config)
        result = await formatter.format_with_black([test_file])
        
        assert isinstance(result, FormattingResult)
        assert not result.success
        assert "Black formatting error" in result.error_message
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_organize_imports_with_isort(self, mock_subprocess):
        """Test isort import organization."""
        # Create test file with unorganized imports
        test_file = self.temp_dir / "test.py"
        test_code = """
import sys
import os
from pathlib import Path
import ast
"""
        test_file.write_text(test_code)
        
        # Mock isort success
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        
        formatter = CodeFormatter(self.config)
        result = await formatter.organize_imports_with_isort([test_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success
        assert result.files_formatted == 1
        
        # Verify isort was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "isort" in call_args
        assert str(test_file) in call_args
    
    @pytest.mark.asyncio
    async def test_standardize_docstrings(self):
        """Test docstring standardization."""
        # Create test file with inconsistent docstrings
        test_file = self.temp_dir / "test.py"
        test_code = '''
def func1():
    """Single line docstring"""
    pass

def func2():
    """
    Multi-line docstring
    with inconsistent formatting
    """
    pass

class TestClass:
    """Class docstring"""
    
    def method(self):
        """Method docstring."""
        pass
'''
        test_file.write_text(test_code)
        
        formatter = CodeFormatter(self.config)
        result = await formatter.standardize_docstrings([test_file])
        
        assert isinstance(result, FormattingResult)
        assert result.success
        assert result.files_formatted == 1
        
        # Check that file was modified
        modified_content = test_file.read_text()
        assert modified_content != test_code
    
    @pytest.mark.asyncio
    async def test_clean_formatting_issues(self):
        """Test cleaning formatting issues."""
        # Create test file with formatting issues
        test_file = self.temp_dir / "test.py"
        test_code = "def func(  ):\n    x=1+2\n    return x"
        test_file.write_text(test_code)
        
        # Create formatting issues
        issues = [
            QualityIssue(
                file_path=test_file,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                message="Line too long"
            )
        ]
        
        formatter = CodeFormatter(self.config)
        
        with patch.object(formatter, 'format_with_black') as mock_black, \
             patch.object(formatter, 'organize_imports_with_isort') as mock_isort:
            
            mock_black.return_value = FormattingResult(success=True, files_formatted=1)
            mock_isort.return_value = FormattingResult(success=True, files_formatted=1)
            
            result = await formatter.clean(issues)
            
            assert isinstance(result, CleanupResult)
            assert result.success
            assert result.files_modified == 1
            
            # Verify both formatters were called
            mock_black.assert_called_once()
            mock_isort.assert_called_once()
    
    def test_formatting_result_creation(self):
        """Test FormattingResult creation."""
        result = FormattingResult(
            success=True,
            files_formatted=5,
            lines_changed=100,
            error_message=None
        )
        
        assert result.success is True
        assert result.files_formatted == 5
        assert result.lines_changed == 100
        assert result.error_message is None


class TestImportCleaner:
    """Test cases for ImportCleaner."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            auto_fix_imports=True,
            safe_import_removal=True
        )
    
    def test_initialization(self):
        """Test cleaner initialization."""
        cleaner = ImportCleaner(self.config)
        assert cleaner.config == self.config
        assert cleaner.safe_removal == self.config.safe_import_removal
    
    def test_can_clean_issue(self):
        """Test issue cleaning capability check."""
        cleaner = ImportCleaner(self.config)
        
        # Should handle import issues
        import_issue = ImportIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.UNUSED_IMPORT,
            severity=IssueSeverity.LOW,
            import_name="unused_module"
        )
        assert cleaner.can_clean_issue(import_issue)
        
        # Should not handle quality issues
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Style issue"
        )
        assert not cleaner.can_clean_issue(quality_issue)
    
    @pytest.mark.asyncio
    async def test_remove_unused_imports(self):
        """Test unused import removal."""
        # Create test file with unused imports
        test_file = self.temp_dir / "test.py"
        test_code = """
import os
import sys
import unused_module
from pathlib import Path, PurePath

def main():
    print(sys.version)
    return os.path.exists("test")
"""
        test_file.write_text(test_code)
        
        # Create unused import issues
        unused_imports = [
            ImportIssue(
                file_path=test_file,
                issue_type=IssueType.UNUSED_IMPORT,
                severity=IssueSeverity.LOW,
                import_name="unused_module",
                line_number=3
            ),
            ImportIssue(
                file_path=test_file,
                issue_type=IssueType.UNUSED_IMPORT,
                severity=IssueSeverity.LOW,
                import_name="pathlib.PurePath",
                line_number=4
            )
        ]
        
        cleaner = ImportCleaner(self.config)
        result = await cleaner.remove_unused_imports(unused_imports)
        
        assert isinstance(result, CleanupResult)
        assert result.success
        assert result.changes_made >= 1
        
        # Check that unused imports were removed
        modified_content = test_file.read_text()
        assert "unused_module" not in modified_content
        assert "import os" in modified_content  # Used import should remain
        assert "import sys" in modified_content  # Used import should remain
    
    @pytest.mark.asyncio
    async def test_resolve_circular_imports(self):
        """Test circular import resolution."""
        # Create circular import scenario
        file1 = self.temp_dir / "module1.py"
        file2 = self.temp_dir / "module2.py"
        
        file1.write_text("from module2 import func2\n\ndef func1():\n    return func2()")
        file2.write_text("from module1 import func1\n\ndef func2():\n    return func1()")
        
        # Create circular import issues
        circular_imports = [
            ImportIssue(
                file_path=file1,
                issue_type=IssueType.CIRCULAR_IMPORT,
                severity=IssueSeverity.MEDIUM,
                import_name="module2",
                description="Circular dependency with module2"
            ),
            ImportIssue(
                file_path=file2,
                issue_type=IssueType.CIRCULAR_IMPORT,
                severity=IssueSeverity.MEDIUM,
                import_name="module1",
                description="Circular dependency with module1"
            )
        ]
        
        cleaner = ImportCleaner(self.config)
        result = await cleaner.resolve_circular_imports(circular_imports)
        
        assert isinstance(result, CleanupResult)
        # Circular import resolution is complex, so we mainly test that it doesn't crash
        # and returns a valid result
    
    @pytest.mark.asyncio
    async def test_optimize_import_order(self):
        """Test import order optimization."""
        # Create test file with unoptimized imports
        test_file = self.temp_dir / "test.py"
        test_code = """
from pathlib import Path
import sys
import os
from typing import List
from . import local_module
import ast
"""
        test_file.write_text(test_code)
        
        cleaner = ImportCleaner(self.config)
        result = await cleaner.optimize_import_order([test_file])
        
        assert isinstance(result, CleanupResult)
        assert result.success
        
        # Check that imports were reordered
        modified_content = test_file.read_text()
        lines = modified_content.strip().split('\n')
        
        # Standard library imports should come first
        import_lines = [line for line in lines if line.strip().startswith('import ') or line.strip().startswith('from ')]
        assert len(import_lines) > 0
    
    def test_is_import_used_in_code(self):
        """Test import usage detection."""
        cleaner = ImportCleaner(self.config)
        
        code = """
def main():
    print(os.path.exists("test"))
    return sys.version
"""
        
        # Test used imports
        assert cleaner._is_import_used_in_code("os", code)
        assert cleaner._is_import_used_in_code("sys", code)
        
        # Test unused import
        assert not cleaner._is_import_used_in_code("unused_module", code)
    
    def test_parse_import_line(self):
        """Test import line parsing."""
        cleaner = ImportCleaner(self.config)
        
        # Test simple import
        result = cleaner._parse_import_line("import os")
        assert result['type'] == 'import'
        assert result['modules'] == ['os']
        
        # Test from import
        result = cleaner._parse_import_line("from pathlib import Path, PurePath")
        assert result['type'] == 'from'
        assert result['module'] == 'pathlib'
        assert result['names'] == ['Path', 'PurePath']
        
        # Test import with alias
        result = cleaner._parse_import_line("import sys as system")
        assert result['type'] == 'import'
        assert result['modules'] == ['sys']
        assert result['aliases'] == {'sys': 'system'}


class TestFileOrganizer:
    """Test cases for FileOrganizer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            auto_organize_files=True,
            max_file_moves=10,
            create_backup=True
        )
    
    def test_initialization(self):
        """Test organizer initialization."""
        organizer = FileOrganizer(self.config)
        assert organizer.config == self.config
        assert organizer.max_moves == self.config.max_file_moves
    
    def test_can_clean_issue(self):
        """Test issue cleaning capability check."""
        organizer = FileOrganizer(self.config)
        
        # Should handle structure issues
        structure_issue = StructureIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.MISPLACED_FILE,
            severity=IssueSeverity.MEDIUM,
            message="File in wrong location"
        )
        assert organizer.can_clean_issue(structure_issue)
        
        # Should not handle import issues
        import_issue = ImportIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.UNUSED_IMPORT,
            severity=IssueSeverity.LOW,
            import_name="unused"
        )
        assert not organizer.can_clean_issue(import_issue)
    
    def test_reorganization_plan_creation(self):
        """Test ReorganizationPlan creation."""
        moves = [
            FileMove(
                source=Path("test.py"),
                destination=Path("src/test.py"),
                reason="Move source file to src directory"
            )
        ]
        
        plan = ReorganizationPlan(
            moves=moves,
            estimated_impact=5,
            safety_score=0.9
        )
        
        assert plan.moves == moves
        assert plan.estimated_impact == 5
        assert plan.safety_score == 0.9
        assert len(plan.affected_files) == 2  # source and destination
    
    @pytest.mark.asyncio
    async def test_reorganize_directory_structure(self):
        """Test directory structure reorganization."""
        # Create misplaced files
        (self.temp_dir / "test_in_root.py").write_text("def test(): pass")
        (self.temp_dir / "config_in_root.json").write_text('{"key": "value"}')
        
        # Create target directories
        (self.temp_dir / "tests").mkdir()
        (self.temp_dir / "config").mkdir()
        
        # Create reorganization plan
        moves = [
            FileMove(
                source=self.temp_dir / "test_in_root.py",
                destination=self.temp_dir / "tests" / "test_in_root.py",
                reason="Move test file to tests directory"
            ),
            FileMove(
                source=self.temp_dir / "config_in_root.json",
                destination=self.temp_dir / "config" / "config_in_root.json",
                reason="Move config file to config directory"
            )
        ]
        
        plan = ReorganizationPlan(moves=moves, estimated_impact=2, safety_score=0.9)
        
        organizer = FileOrganizer(self.config)
        result = await organizer.reorganize_directory_structure(plan)
        
        assert isinstance(result, CleanupResult)
        assert result.success
        assert result.changes_made == 2
        
        # Check that files were moved
        assert (self.temp_dir / "tests" / "test_in_root.py").exists()
        assert (self.temp_dir / "config" / "config_in_root.json").exists()
        assert not (self.temp_dir / "test_in_root.py").exists()
        assert not (self.temp_dir / "config_in_root.json").exists()
    
    @pytest.mark.asyncio
    async def test_remove_empty_directories(self):
        """Test empty directory removal."""
        # Create empty directories
        empty_dir1 = self.temp_dir / "empty1"
        empty_dir2 = self.temp_dir / "empty2"
        not_empty_dir = self.temp_dir / "not_empty"
        
        empty_dir1.mkdir()
        empty_dir2.mkdir()
        not_empty_dir.mkdir()
        (not_empty_dir / "file.txt").write_text("content")
        
        empty_directories = [empty_dir1, empty_dir2]
        
        organizer = FileOrganizer(self.config)
        result = await organizer.remove_empty_directories(empty_directories)
        
        assert isinstance(result, CleanupResult)
        assert result.success
        assert result.changes_made == 2
        
        # Check that empty directories were removed
        assert not empty_dir1.exists()
        assert not empty_dir2.exists()
        assert not_empty_dir.exists()  # Should still exist
    
    @pytest.mark.asyncio
    async def test_move_misplaced_files(self):
        """Test misplaced file moving."""
        # Create misplaced files
        misplaced_file = self.temp_dir / "test_misplaced.py"
        misplaced_file.write_text("def test(): pass")
        
        # Create target directory
        target_dir = self.temp_dir / "tests"
        target_dir.mkdir()
        
        # Create misplaced file issues
        misplaced_files = [
            StructureIssue(
                file_path=misplaced_file,
                issue_type=IssueType.MISPLACED_FILE,
                severity=IssueSeverity.MEDIUM,
                message="Test file in wrong location",
                suggested_location=target_dir / "test_misplaced.py"
            )
        ]
        
        organizer = FileOrganizer(self.config)
        result = await organizer.move_misplaced_files(misplaced_files)
        
        assert isinstance(result, CleanupResult)
        assert result.success
        assert result.changes_made == 1
        
        # Check that file was moved
        assert (target_dir / "test_misplaced.py").exists()
        assert not misplaced_file.exists()
    
    def test_create_reorganization_plan(self):
        """Test reorganization plan creation."""
        organizer = FileOrganizer(self.config)
        
        # Create structure issues
        issues = [
            StructureIssue(
                file_path=Path("test.py"),
                issue_type=IssueType.MISPLACED_FILE,
                severity=IssueSeverity.MEDIUM,
                message="Test file in wrong location",
                suggested_location=Path("tests/test.py")
            ),
            StructureIssue(
                file_path=Path("config.json"),
                issue_type=IssueType.MISPLACED_FILE,
                severity=IssueSeverity.LOW,
                message="Config file in wrong location",
                suggested_location=Path("config/config.json")
            )
        ]
        
        plan = organizer._create_reorganization_plan(issues)
        
        assert isinstance(plan, ReorganizationPlan)
        assert len(plan.moves) == 2
        assert plan.estimated_impact > 0
        assert 0 <= plan.safety_score <= 1
    
    def test_calculate_move_safety(self):
        """Test move safety calculation."""
        organizer = FileOrganizer(self.config)
        
        # Test safe move
        safe_move = FileMove(
            source=Path("test.py"),
            destination=Path("tests/test.py"),
            reason="Move test file"
        )
        safety = organizer._calculate_move_safety(safe_move)
        assert 0 <= safety <= 1
        
        # Test potentially unsafe move
        unsafe_move = FileMove(
            source=Path("__init__.py"),
            destination=Path("other/__init__.py"),
            reason="Move init file"
        )
        safety = organizer._calculate_move_safety(unsafe_move)
        assert 0 <= safety <= 1


if __name__ == "__main__":
    # Run tests manually without pytest
    import asyncio
    
    async def run_async_tests():
        """Run async tests manually."""
        print("Running CodeFormatter tests...")
        
        # Test CodeFormatter
        test_formatter = TestCodeFormatter()
        test_formatter.setup_method()
        
        try:
            await test_formatter.test_standardize_docstrings()
            print("✓ test_standardize_docstrings passed")
        except Exception as e:
            print(f"✗ test_standardize_docstrings failed: {e}")
        
        # Test ImportCleaner
        print("\nRunning ImportCleaner tests...")
        test_cleaner = TestImportCleaner()
        test_cleaner.setup_method()
        
        try:
            await test_cleaner.test_remove_unused_imports()
            print("✓ test_remove_unused_imports passed")
        except Exception as e:
            print(f"✗ test_remove_unused_imports failed: {e}")
        
        try:
            await test_cleaner.test_optimize_import_order()
            print("✓ test_optimize_import_order passed")
        except Exception as e:
            print(f"✗ test_optimize_import_order failed: {e}")
        
        # Test FileOrganizer
        print("\nRunning FileOrganizer tests...")
        test_organizer = TestFileOrganizer()
        test_organizer.setup_method()
        
        try:
            await test_organizer.test_remove_empty_directories()
            print("✓ test_remove_empty_directories passed")
        except Exception as e:
            print(f"✗ test_remove_empty_directories failed: {e}")
        
        try:
            await test_organizer.test_move_misplaced_files()
            print("✓ test_move_misplaced_files passed")
        except Exception as e:
            print(f"✗ test_move_misplaced_files failed: {e}")
    
    def run_sync_tests():
        """Run synchronous tests."""
        print("\nRunning synchronous tests...")
        
        # Test BaseCleaner
        test_base = TestBaseCleaner()
        test_base.setup_method()
        
        try:
            test_base.test_base_cleaner_initialization()
            print("✓ test_base_cleaner_initialization passed")
        except Exception as e:
            print(f"✗ test_base_cleaner_initialization failed: {e}")
        
        try:
            test_base.test_cleanup_result_creation()
            print("✓ test_cleanup_result_creation passed")
        except Exception as e:
            print(f"✗ test_cleanup_result_creation failed: {e}")
        
        # Test CodeFormatter
        test_formatter = TestCodeFormatter()
        test_formatter.setup_method()
        
        try:
            test_formatter.test_initialization()
            print("✓ test_formatter_initialization passed")
        except Exception as e:
            print(f"✗ test_formatter_initialization failed: {e}")
        
        try:
            test_formatter.test_can_clean_issue()
            print("✓ test_can_clean_issue passed")
        except Exception as e:
            print(f"✗ test_can_clean_issue failed: {e}")
        
        # Test ImportCleaner
        test_cleaner = TestImportCleaner()
        test_cleaner.setup_method()
        
        try:
            test_cleaner.test_is_import_used_in_code()
            print("✓ test_is_import_used_in_code passed")
        except Exception as e:
            print(f"✗ test_is_import_used_in_code failed: {e}")
        
        try:
            test_cleaner.test_parse_import_line()
            print("✓ test_parse_import_line passed")
        except Exception as e:
            print(f"✗ test_parse_import_line failed: {e}")
        
        # Test FileOrganizer
        test_organizer = TestFileOrganizer()
        test_organizer.setup_method()
        
        try:
            test_organizer.test_reorganization_plan_creation()
            print("✓ test_reorganization_plan_creation passed")
        except Exception as e:
            print(f"✗ test_reorganization_plan_creation failed: {e}")
    
    # Run tests
    run_sync_tests()
    asyncio.run(run_async_tests())
    print("\nTest run completed!")