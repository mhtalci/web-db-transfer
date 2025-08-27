"""
Comprehensive unit tests for checkup analyzers.
Tests all analyzer classes to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import ast
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migration_assistant.checkup.analyzers.quality import CodeQualityAnalyzer
from migration_assistant.checkup.analyzers.duplicates import DuplicateCodeDetector, CodeBlock, DuplicateGroup
from migration_assistant.checkup.analyzers.imports import ImportAnalyzer
from migration_assistant.checkup.analyzers.structure import StructureAnalyzer
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import (
    CheckupConfig, QualityIssue, Duplicate, ImportIssue, StructureIssue,
    IssueType, IssueSeverity
)


class TestBaseAnalyzer:
    """Test cases for BaseAnalyzer abstract class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            enable_quality_analysis=True,
            enable_duplicate_detection=True,
            enable_import_analysis=True,
            enable_structure_analysis=True
        )
    
    def test_base_analyzer_initialization(self):
        """Test BaseAnalyzer initialization."""
        # Create a concrete implementation for testing
        class TestAnalyzer(BaseAnalyzer):
            def get_supported_file_types(self):
                return ['.py']
            
            async def analyze(self):
                return []
        
        analyzer = TestAnalyzer(self.config)
        assert analyzer.config == self.config
        assert analyzer.target_directory == self.config.target_directory
        assert analyzer.get_supported_file_types() == ['.py']
    
    def test_get_python_files(self):
        """Test getting Python files from directory."""
        class TestAnalyzer(BaseAnalyzer):
            def get_supported_file_types(self):
                return ['.py']
            
            async def analyze(self):
                return []
        
        # Create test Python files
        (self.temp_dir / "test1.py").write_text("print('hello')")
        (self.temp_dir / "test2.py").write_text("import os")
        (self.temp_dir / "not_python.txt").write_text("not python")
        
        # Create subdirectory with Python file
        subdir = self.temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "test3.py").write_text("def func(): pass")
        
        analyzer = TestAnalyzer(self.config)
        python_files = analyzer.get_python_files()
        
        assert len(python_files) == 3
        assert all(f.suffix == '.py' for f in python_files)
        assert any(f.name == 'test1.py' for f in python_files)
        assert any(f.name == 'test2.py' for f in python_files)
        assert any(f.name == 'test3.py' for f in python_files)
    
    @pytest.mark.asyncio
    async def test_pre_analyze_hook(self):
        """Test pre-analyze hook."""
        class TestAnalyzer(BaseAnalyzer):
            def __init__(self, config):
                super().__init__(config)
                self.pre_analyze_called = False
            
            def get_supported_file_types(self):
                return ['.py']
            
            async def pre_analyze(self):
                self.pre_analyze_called = True
                await super().pre_analyze()
            
            async def analyze(self):
                await self.pre_analyze()
                return []
        
        analyzer = TestAnalyzer(self.config)
        await analyzer.analyze()
        assert analyzer.pre_analyze_called
    
    @pytest.mark.asyncio
    async def test_post_analyze_hook(self):
        """Test post-analyze hook."""
        class TestAnalyzer(BaseAnalyzer):
            def __init__(self, config):
                super().__init__(config)
                self.post_analyze_called = False
                self.post_analyze_results = None
            
            def get_supported_file_types(self):
                return ['.py']
            
            async def post_analyze(self, results):
                self.post_analyze_called = True
                self.post_analyze_results = results
                await super().post_analyze(results)
            
            async def analyze(self):
                results = []
                await self.post_analyze(results)
                return results
        
        analyzer = TestAnalyzer(self.config)
        results = await analyzer.analyze()
        assert analyzer.post_analyze_called
        assert analyzer.post_analyze_results == results


class TestCodeQualityAnalyzer:
    """Test cases for CodeQualityAnalyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            enable_quality_analysis=True,
            check_type_hints=True,
            max_complexity=10,
            max_line_length=88
        )
    
    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = CodeQualityAnalyzer(self.config)
        assert analyzer.config == self.config
        assert analyzer.syntax_errors == []
        assert analyzer.style_violations == []
        assert analyzer.complexity_issues == []
        assert analyzer.code_smells == []
    
    def test_get_supported_file_types(self):
        """Test supported file types."""
        analyzer = CodeQualityAnalyzer(self.config)
        supported = analyzer.get_supported_file_types()
        assert '.py' in supported
        assert '.pyx' in supported
    
    @pytest.mark.asyncio
    async def test_analyze_syntax_errors(self):
        """Test syntax error detection."""
        # Create file with syntax error
        bad_file = self.temp_dir / "bad_syntax.py"
        bad_file.write_text("def func(\n    pass")  # Missing closing parenthesis
        
        analyzer = CodeQualityAnalyzer(self.config)
        issues = await analyzer.analyze_syntax_errors(bad_file)
        
        assert len(issues) > 0
        assert all(isinstance(issue, QualityIssue) for issue in issues)
        assert all(issue.issue_type == IssueType.SYNTAX_ERROR for issue in issues)
        assert all(issue.severity == IssueSeverity.HIGH for issue in issues)
    
    @pytest.mark.asyncio
    async def test_analyze_syntax_errors_valid_file(self):
        """Test syntax analysis on valid file."""
        # Create file with valid syntax
        good_file = self.temp_dir / "good_syntax.py"
        good_file.write_text("def func():\n    pass")
        
        analyzer = CodeQualityAnalyzer(self.config)
        issues = await analyzer.analyze_syntax_errors(good_file)
        
        assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_complexity(self):
        """Test complexity analysis."""
        # Create file with high complexity
        complex_file = self.temp_dir / "complex.py"
        complex_code = """
def complex_function(x):
    if x > 10:
        if x > 20:
            if x > 30:
                if x > 40:
                    if x > 50:
                        return "very high"
                    else:
                        return "high"
                else:
                    return "medium-high"
            else:
                return "medium"
        else:
            return "low-medium"
    else:
        return "low"
"""
        complex_file.write_text(complex_code)
        
        analyzer = CodeQualityAnalyzer(self.config)
        issues = await analyzer.analyze_complexity(complex_file)
        
        # Should detect high complexity
        complexity_issues = [i for i in issues if i.issue_type == IssueType.COMPLEXITY]
        assert len(complexity_issues) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_code_smells(self):
        """Test code smell detection."""
        # Create file with code smells
        smelly_file = self.temp_dir / "smelly.py"
        smelly_code = """
# Long parameter list
def bad_function(a, b, c, d, e, f, g, h, i, j):
    pass

# Unused variable
def another_function():
    unused_var = "not used"
    return "something else"

# Long line
def long_line_function():
    very_long_variable_name = "this is a very long string that exceeds the maximum line length and should be flagged as a style violation"
    return very_long_variable_name
"""
        smelly_file.write_text(smelly_code)
        
        analyzer = CodeQualityAnalyzer(self.config)
        issues = await analyzer.analyze_code_smells(smelly_file)
        
        # Should detect various code smells
        assert len(issues) > 0
        assert all(isinstance(issue, QualityIssue) for issue in issues)
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_analyze_with_flake8_batch(self, mock_subprocess):
        """Test flake8 batch analysis."""
        # Mock flake8 output
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "test.py:1:1: E302 expected 2 blank lines\ntest.py:5:80: E501 line too long"
        
        # Create test file
        test_file = self.temp_dir / "test.py"
        test_file.write_text("def func():\n    pass")
        
        analyzer = CodeQualityAnalyzer(self.config)
        issues = await analyzer.analyze_with_flake8_batch([test_file])
        
        assert len(issues) == 2
        assert all(isinstance(issue, QualityIssue) for issue in issues)
        assert issues[0].issue_type == IssueType.STYLE_VIOLATION
        assert "E302" in issues[0].message
        assert "E501" in issues[1].message
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_analyze_with_mypy(self, mock_subprocess):
        """Test mypy type checking."""
        # Mock mypy output
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = "test.py:1: error: Function is missing a return type annotation"
        
        # Create test file
        test_file = self.temp_dir / "test.py"
        test_file.write_text("def func():\n    pass")
        
        analyzer = CodeQualityAnalyzer(self.config)
        issues = await analyzer.analyze_with_mypy([test_file])
        
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.TYPE_ERROR
        assert "missing a return type annotation" in issues[0].message
    
    def test_create_quality_issue(self):
        """Test quality issue creation."""
        analyzer = CodeQualityAnalyzer(self.config)
        
        issue = analyzer._create_quality_issue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Test error",
            description="Test description",
            line_number=10,
            column_number=5,
            tool_name="test_tool"
        )
        
        assert isinstance(issue, QualityIssue)
        assert issue.file_path == Path("test.py")
        assert issue.issue_type == IssueType.SYNTAX_ERROR
        assert issue.severity == IssueSeverity.HIGH
        assert issue.message == "Test error"
        assert issue.description == "Test description"
        assert issue.line_number == 10
        assert issue.column_number == 5
        assert issue.tool_name == "test_tool"
    
    def test_aggregate_and_normalize_issues(self):
        """Test issue aggregation and normalization."""
        analyzer = CodeQualityAnalyzer(self.config)
        
        # Create duplicate issues
        issue1 = analyzer._create_quality_issue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Test error",
            description="Test description",
            line_number=10
        )
        issue2 = analyzer._create_quality_issue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Test error",
            description="Test description",
            line_number=10
        )
        issue3 = analyzer._create_quality_issue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.MEDIUM,
            message="Different error",
            description="Different description",
            line_number=20
        )
        
        issues = [issue1, issue2, issue3]
        normalized = analyzer._aggregate_and_normalize_issues(issues)
        
        # Should remove duplicates
        assert len(normalized) == 2
        assert any(issue.issue_type == IssueType.SYNTAX_ERROR for issue in normalized)
        assert any(issue.issue_type == IssueType.STYLE_VIOLATION for issue in normalized)


class TestDuplicateCodeDetector:
    """Test cases for DuplicateCodeDetector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            min_duplicate_lines=3,
            similarity_threshold=0.8
        )
    
    def test_initialization(self):
        """Test detector initialization."""
        detector = DuplicateCodeDetector(self.config)
        assert detector.config == self.config
        assert detector.min_lines == self.config.min_duplicate_lines
        assert detector.similarity_threshold == self.config.similarity_threshold
        assert detector._file_contents == {}
        assert detector._file_lines == {}
        assert detector._code_blocks == []
    
    def test_code_block_creation(self):
        """Test CodeBlock creation and properties."""
        block = CodeBlock(
            file_path=Path("test.py"),
            start_line=1,
            end_line=5,
            content="def func():\n    pass",
            content_hash="hash123",
            block_type="function"
        )
        
        assert block.file_path == Path("test.py")
        assert block.start_line == 1
        assert block.end_line == 5
        assert block.lines_of_code == 5
        assert block.content_hash == "hash123"
        assert block.block_type == "function"
    
    def test_code_block_equality(self):
        """Test CodeBlock equality comparison."""
        block1 = CodeBlock(
            file_path=Path("test1.py"),
            start_line=1,
            end_line=5,
            content="def func():\n    pass",
            content_hash="hash123"
        )
        block2 = CodeBlock(
            file_path=Path("test2.py"),
            start_line=10,
            end_line=14,
            content="def func():\n    pass",
            content_hash="hash123"
        )
        block3 = CodeBlock(
            file_path=Path("test3.py"),
            start_line=1,
            end_line=5,
            content="def other():\n    pass",
            content_hash="hash456"
        )
        
        assert block1 == block2  # Same hash
        assert block1 != block3  # Different hash
        assert hash(block1) == hash(block2)
        assert hash(block1) != hash(block3)
    
    def test_duplicate_group_creation(self):
        """Test DuplicateGroup creation and properties."""
        blocks = [
            CodeBlock(Path("test1.py"), 1, 5, "code", "hash1"),
            CodeBlock(Path("test2.py"), 1, 5, "code", "hash1"),
            CodeBlock(Path("test3.py"), 1, 5, "code", "hash1")
        ]
        
        group = DuplicateGroup(blocks, similarity_score=0.95)
        
        assert group.blocks == blocks
        assert group.similarity_score == 0.95
        assert group.total_lines == 15  # 5 lines * 3 blocks
        assert group.duplicate_count == 3
        assert group.representative_block == blocks[0]
        assert len(group.duplicate_files) == 3
    
    @pytest.mark.asyncio
    async def test_load_file_contents(self):
        """Test loading file contents."""
        # Create test files
        file1 = self.temp_dir / "test1.py"
        file2 = self.temp_dir / "test2.py"
        file1.write_text("def func1():\n    pass")
        file2.write_text("def func2():\n    return True")
        
        detector = DuplicateCodeDetector(self.config)
        await detector._load_file_contents()
        
        assert len(detector._file_contents) == 2
        assert file1 in detector._file_contents
        assert file2 in detector._file_contents
        assert "def func1():" in detector._file_contents[file1]
        assert "def func2():" in detector._file_contents[file2]
        
        assert len(detector._file_lines) == 2
        assert len(detector._file_lines[file1]) == 2
        assert len(detector._file_lines[file2]) == 2
    
    @pytest.mark.asyncio
    async def test_extract_code_blocks(self):
        """Test code block extraction."""
        # Create test file with functions
        test_file = self.temp_dir / "test.py"
        test_code = """
def function1():
    print("hello")
    return True

def function2():
    print("world")
    return False

class TestClass:
    def method1(self):
        pass
"""
        test_file.write_text(test_code)
        
        detector = DuplicateCodeDetector(self.config)
        await detector._load_file_contents()
        await detector._extract_code_blocks()
        
        assert len(detector._code_blocks) > 0
        
        # Check that we have different types of blocks
        block_types = {block.block_type for block in detector._code_blocks}
        assert len(block_types) > 0
    
    @pytest.mark.asyncio
    async def test_find_exact_duplicates(self):
        """Test exact duplicate detection."""
        # Create files with exact duplicates
        file1 = self.temp_dir / "test1.py"
        file2 = self.temp_dir / "test2.py"
        
        duplicate_code = """
def duplicate_function():
    print("This is a duplicate")
    return True
"""
        
        file1.write_text(f"# File 1\n{duplicate_code}")
        file2.write_text(f"# File 2\n{duplicate_code}")
        
        detector = DuplicateCodeDetector(self.config)
        await detector._load_file_contents()
        await detector._extract_code_blocks()
        
        duplicates = await detector._find_exact_duplicates()
        
        # Should find the duplicate function
        assert len(duplicates) > 0
        assert all(isinstance(dup, DuplicateGroup) for dup in duplicates)
        
        # Check that duplicates span multiple files
        for dup_group in duplicates:
            if dup_group.duplicate_count > 1:
                files = dup_group.duplicate_files
                assert len(set(files)) > 1  # Multiple different files
    
    def test_calculate_similarity(self):
        """Test similarity calculation."""
        detector = DuplicateCodeDetector(self.config)
        
        # Identical blocks
        block1 = CodeBlock(Path("test1.py"), 1, 3, "def func():\n    pass", "hash1")
        block2 = CodeBlock(Path("test2.py"), 1, 3, "def func():\n    pass", "hash1")
        
        similarity = detector._calculate_similarity(block1, block2)
        assert similarity == 1.0
        
        # Similar blocks
        block3 = CodeBlock(Path("test3.py"), 1, 3, "def func():\n    return", "hash2")
        similarity = detector._calculate_similarity(block1, block3)
        assert 0.0 <= similarity <= 1.0
        
        # Different blocks
        block4 = CodeBlock(Path("test4.py"), 1, 3, "class Test:\n    pass", "hash3")
        similarity = detector._calculate_similarity(block1, block4)
        assert similarity < 1.0


class TestImportAnalyzer:
    """Test cases for ImportAnalyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            enable_import_analysis=True
        )
    
    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = ImportAnalyzer(self.config)
        assert analyzer.config == self.config
        assert analyzer._import_graph == {}
        assert analyzer._file_imports == {}
        assert analyzer._unused_imports == []
        assert analyzer._circular_imports == []
    
    @pytest.mark.asyncio
    async def test_find_unused_imports(self):
        """Test unused import detection."""
        # Create file with unused import
        test_file = self.temp_dir / "test.py"
        test_code = """
import os
import sys
import unused_module

def main():
    print(sys.version)
    return os.path.exists("test")
"""
        test_file.write_text(test_code)
        
        analyzer = ImportAnalyzer(self.config)
        unused = await analyzer.find_unused_imports()
        
        assert len(unused) > 0
        assert all(isinstance(issue, ImportIssue) for issue in unused)
        
        # Should detect unused_module as unused
        unused_names = [issue.import_name for issue in unused]
        assert "unused_module" in unused_names
    
    @pytest.mark.asyncio
    async def test_detect_circular_imports(self):
        """Test circular import detection."""
        # Create circular import scenario
        file1 = self.temp_dir / "module1.py"
        file2 = self.temp_dir / "module2.py"
        
        file1.write_text("from module2 import func2\n\ndef func1():\n    return func2()")
        file2.write_text("from module1 import func1\n\ndef func2():\n    return func1()")
        
        analyzer = ImportAnalyzer(self.config)
        await analyzer._build_import_graph()
        circular = await analyzer.detect_circular_imports()
        
        # Should detect circular dependency
        assert len(circular) > 0
        assert all(isinstance(issue, ImportIssue) for issue in circular)
    
    @pytest.mark.asyncio
    async def test_find_orphaned_modules(self):
        """Test orphaned module detection."""
        # Create orphaned module
        main_file = self.temp_dir / "main.py"
        used_file = self.temp_dir / "used_module.py"
        orphaned_file = self.temp_dir / "orphaned_module.py"
        
        main_file.write_text("from used_module import func\n\nfunc()")
        used_file.write_text("def func():\n    pass")
        orphaned_file.write_text("def orphaned_func():\n    pass")
        
        analyzer = ImportAnalyzer(self.config)
        await analyzer._build_import_graph()
        orphaned = await analyzer.find_orphaned_modules()
        
        # Should detect orphaned module
        assert len(orphaned) > 0
        orphaned_files = [issue.file_path.name for issue in orphaned]
        assert "orphaned_module.py" in orphaned_files
    
    def test_parse_imports_from_ast(self):
        """Test import parsing from AST."""
        analyzer = ImportAnalyzer(self.config)
        
        code = """
import os
import sys as system
from pathlib import Path, PurePath
from typing import List, Dict, Optional
from . import local_module
from ..parent import parent_module
"""
        
        tree = ast.parse(code)
        imports = analyzer._parse_imports_from_ast(tree, Path("test.py"))
        
        assert len(imports) > 0
        
        # Check different import types
        import_names = [imp['name'] for imp in imports]
        assert 'os' in import_names
        assert 'sys' in import_names
        assert 'pathlib.Path' in import_names
        assert 'pathlib.PurePath' in import_names
        assert 'typing.List' in import_names


class TestStructureAnalyzer:
    """Test cases for StructureAnalyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            enable_structure_analysis=True
        )
    
    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = StructureAnalyzer(self.config)
        assert analyzer.config == self.config
        assert analyzer._directory_structure == {}
        assert analyzer._file_classifications == {}
        assert analyzer._structure_issues == []
    
    @pytest.mark.asyncio
    async def test_analyze_directory_organization(self):
        """Test directory organization analysis."""
        # Create test directory structure
        (self.temp_dir / "src").mkdir()
        (self.temp_dir / "tests").mkdir()
        (self.temp_dir / "docs").mkdir()
        (self.temp_dir / "scripts").mkdir()
        
        # Create files in appropriate locations
        (self.temp_dir / "src" / "main.py").write_text("def main(): pass")
        (self.temp_dir / "tests" / "test_main.py").write_text("def test_main(): pass")
        (self.temp_dir / "docs" / "README.md").write_text("# Documentation")
        
        # Create misplaced files
        (self.temp_dir / "test_misplaced.py").write_text("def test(): pass")  # Test in root
        (self.temp_dir / "src" / "README.md").write_text("# Docs in src")  # Doc in src
        
        analyzer = StructureAnalyzer(self.config)
        report = await analyzer.analyze_directory_organization()
        
        assert report is not None
        assert hasattr(report, 'total_files')
        assert hasattr(report, 'total_directories')
    
    @pytest.mark.asyncio
    async def test_find_misplaced_files(self):
        """Test misplaced file detection."""
        # Create directory structure
        (self.temp_dir / "src").mkdir()
        (self.temp_dir / "tests").mkdir()
        
        # Create misplaced files
        (self.temp_dir / "test_in_root.py").write_text("def test(): pass")
        (self.temp_dir / "src" / "config.ini").write_text("[section]\nkey=value")
        
        analyzer = StructureAnalyzer(self.config)
        await analyzer._analyze_directory_structure()
        misplaced = await analyzer.find_misplaced_files()
        
        assert len(misplaced) > 0
        assert all(isinstance(issue, StructureIssue) for issue in misplaced)
    
    @pytest.mark.asyncio
    async def test_detect_empty_directories(self):
        """Test empty directory detection."""
        # Create empty directories
        (self.temp_dir / "empty1").mkdir()
        (self.temp_dir / "empty2").mkdir()
        (self.temp_dir / "not_empty").mkdir()
        (self.temp_dir / "not_empty" / "file.txt").write_text("content")
        
        analyzer = StructureAnalyzer(self.config)
        await analyzer._analyze_directory_structure()
        empty_dirs = await analyzer.detect_empty_directories()
        
        assert len(empty_dirs) >= 2
        empty_dir_names = [issue.file_path.name for issue in empty_dirs]
        assert "empty1" in empty_dir_names
        assert "empty2" in empty_dir_names
        assert "not_empty" not in empty_dir_names
    
    def test_classify_file_type(self):
        """Test file type classification."""
        analyzer = StructureAnalyzer(self.config)
        
        # Test different file types
        assert analyzer._classify_file_type(Path("test.py")) == "source"
        assert analyzer._classify_file_type(Path("test_something.py")) == "test"
        assert analyzer._classify_file_type(Path("README.md")) == "documentation"
        assert analyzer._classify_file_type(Path("config.json")) == "configuration"
        assert analyzer._classify_file_type(Path("script.sh")) == "script"
        assert analyzer._classify_file_type(Path("data.csv")) == "data"
        assert analyzer._classify_file_type(Path("unknown.xyz")) == "other"
    
    def test_get_expected_directory(self):
        """Test expected directory determination."""
        analyzer = StructureAnalyzer(self.config)
        
        # Test file type to directory mapping
        assert "src" in analyzer._get_expected_directory("source")
        assert "test" in analyzer._get_expected_directory("test")
        assert "doc" in analyzer._get_expected_directory("documentation")
        assert "config" in analyzer._get_expected_directory("configuration")
        assert "script" in analyzer._get_expected_directory("script")


if __name__ == "__main__":
    # Run tests manually without pytest
    import asyncio
    
    async def run_async_tests():
        """Run async tests manually."""
        print("Running CodeQualityAnalyzer tests...")
        
        # Test CodeQualityAnalyzer
        test_quality = TestCodeQualityAnalyzer()
        test_quality.setup_method()
        
        try:
            await test_quality.test_analyze_syntax_errors_valid_file()
            print("✓ test_analyze_syntax_errors_valid_file passed")
        except Exception as e:
            print(f"✗ test_analyze_syntax_errors_valid_file failed: {e}")
        
        try:
            await test_quality.test_analyze_complexity()
            print("✓ test_analyze_complexity passed")
        except Exception as e:
            print(f"✗ test_analyze_complexity failed: {e}")
        
        # Test DuplicateCodeDetector
        print("\nRunning DuplicateCodeDetector tests...")
        test_duplicates = TestDuplicateCodeDetector()
        test_duplicates.setup_method()
        
        try:
            await test_duplicates.test_load_file_contents()
            print("✓ test_load_file_contents passed")
        except Exception as e:
            print(f"✗ test_load_file_contents failed: {e}")
        
        # Test ImportAnalyzer
        print("\nRunning ImportAnalyzer tests...")
        test_imports = TestImportAnalyzer()
        test_imports.setup_method()
        
        try:
            await test_imports.test_find_unused_imports()
            print("✓ test_find_unused_imports passed")
        except Exception as e:
            print(f"✗ test_find_unused_imports failed: {e}")
        
        # Test StructureAnalyzer
        print("\nRunning StructureAnalyzer tests...")
        test_structure = TestStructureAnalyzer()
        test_structure.setup_method()
        
        try:
            await test_structure.test_analyze_directory_organization()
            print("✓ test_analyze_directory_organization passed")
        except Exception as e:
            print(f"✗ test_analyze_directory_organization failed: {e}")
    
    def run_sync_tests():
        """Run synchronous tests."""
        print("\nRunning synchronous tests...")
        
        # Test BaseAnalyzer
        test_base = TestBaseAnalyzer()
        test_base.setup_method()
        
        try:
            test_base.test_base_analyzer_initialization()
            print("✓ test_base_analyzer_initialization passed")
        except Exception as e:
            print(f"✗ test_base_analyzer_initialization failed: {e}")
        
        try:
            test_base.test_get_python_files()
            print("✓ test_get_python_files passed")
        except Exception as e:
            print(f"✗ test_get_python_files failed: {e}")
        
        # Test CodeBlock
        test_duplicates = TestDuplicateCodeDetector()
        test_duplicates.setup_method()
        
        try:
            test_duplicates.test_code_block_creation()
            print("✓ test_code_block_creation passed")
        except Exception as e:
            print(f"✗ test_code_block_creation failed: {e}")
        
        try:
            test_duplicates.test_duplicate_group_creation()
            print("✓ test_duplicate_group_creation passed")
        except Exception as e:
            print(f"✗ test_duplicate_group_creation failed: {e}")
    
    # Run tests
    run_sync_tests()
    asyncio.run(run_async_tests())
    print("\nTest run completed!")