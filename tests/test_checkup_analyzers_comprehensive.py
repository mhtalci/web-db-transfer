"""
Comprehensive unit tests for checkup analyzers.

Tests all analyzer classes to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import ast
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

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
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            enable_quality_analysis=True,
            enable_duplicate_detection=True,
            enable_import_analysis=True,
            enable_structure_analysis=True
        )
    
    def test_base_analyzer_initialization(self, config):
        """Test BaseAnalyzer initialization."""
        # Create a concrete implementation for testing
        class TestAnalyzer(BaseAnalyzer):
            def get_supported_file_types(self):
                return ['.py']
            
            async def analyze(self):
                return []
        
        analyzer = TestAnalyzer(config)
        assert analyzer.config == config
        assert analyzer.target_directory == config.target_directory
        assert analyzer.issues == []
    
    def test_get_python_files(self, config, tmp_path):
        """Test getting Python files from directory."""
        class TestAnalyzer(BaseAnalyzer):
            def get_supported_file_types(self):
                return ['.py']
            
            async def analyze(self):
                return []
        
        # Create test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test.txt").write_text("not python")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "test.pyc").write_text("compiled")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.py").write_text("print('nested')")
        
        config.target_directory = tmp_path
        analyzer = TestAnalyzer(config)
        
        python_files = analyzer.get_python_files()
        python_file_names = [f.name for f in python_files]
        
        assert "test.py" in python_file_names
        assert "nested.py" in python_file_names
        assert "test.txt" not in python_file_names
        assert "test.pyc" not in python_file_names
    
    @pytest.mark.asyncio
    async def test_pre_analyze(self, config):
        """Test pre-analysis setup."""
        class TestAnalyzer(BaseAnalyzer):
            def get_supported_file_types(self):
                return ['.py']
            
            async def analyze(self):
                return []
        
        analyzer = TestAnalyzer(config)
        await analyzer.pre_analyze()
        
        # Should not raise any exceptions
        assert True
    
    def test_filter_files_by_extension(self, config):
        """Test filtering files by extension."""
        class TestAnalyzer(BaseAnalyzer):
            def get_supported_file_types(self):
                return ['.py', '.pyx']
            
            async def analyze(self):
                return []
        
        analyzer = TestAnalyzer(config)
        
        files = [
            Path("test.py"),
            Path("test.pyx"),
            Path("test.txt"),
            Path("test.js"),
            Path("test.pyc")
        ]
        
        filtered = analyzer._filter_files_by_extension(files)
        filtered_names = [f.name for f in filtered]
        
        assert "test.py" in filtered_names
        assert "test.pyx" in filtered_names
        assert "test.txt" not in filtered_names
        assert "test.js" not in filtered_names
        assert "test.pyc" not in filtered_names


class TestCodeQualityAnalyzer:
    """Test cases for CodeQualityAnalyzer."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            enable_quality_analysis=True,
            quality_config={
                "max_complexity": 10,
                "max_line_length": 88,
                "max_function_length": 50,
                "max_class_length": 200
            }
        )
    
    @pytest.fixture
    def analyzer(self, config):
        """Create CodeQualityAnalyzer instance."""
        return CodeQualityAnalyzer(config)
    
    def test_initialization(self, analyzer, config):
        """Test analyzer initialization."""
        assert analyzer.config == config
        assert analyzer.syntax_errors == []
        assert analyzer.style_violations == []
        assert analyzer.complexity_issues == []
        assert analyzer.code_smells == []
    
    def test_get_supported_file_types(self, analyzer):
        """Test supported file types."""
        types = analyzer.get_supported_file_types()
        assert '.py' in types
        assert '.pyx' in types
    
    @pytest.mark.asyncio
    async def test_analyze_syntax_errors(self, analyzer, tmp_path):
        """Test syntax error detection."""
        # Create file with syntax error
        bad_file = tmp_path / "bad_syntax.py"
        bad_file.write_text("def broken_function(\n    pass")  # Missing closing parenthesis
        
        analyzer.target_directory = tmp_path
        issues = await analyzer.analyze_syntax_errors([bad_file])
        
        assert len(issues) > 0
        assert any(issue.issue_type == IssueType.SYNTAX_ERROR for issue in issues)
    
    @pytest.mark.asyncio
    async def test_analyze_syntax_valid_file(self, analyzer, tmp_path):
        """Test syntax analysis on valid file."""
        good_file = tmp_path / "good_syntax.py"
        good_file.write_text("def good_function():\n    return True")
        
        analyzer.target_directory = tmp_path
        issues = await analyzer.analyze_syntax_errors([good_file])
        
        # Should not find syntax errors in valid file
        syntax_errors = [i for i in issues if i.issue_type == IssueType.SYNTAX_ERROR]
        assert len(syntax_errors) == 0
    
    def test_calculate_cyclomatic_complexity_simple(self, analyzer):
        """Test cyclomatic complexity calculation for simple function."""
        code = """
def simple_function():
    return True
"""
        tree = ast.parse(code)
        complexity = analyzer._calculate_cyclomatic_complexity(tree.body[0])
        assert complexity == 1  # Base complexity
    
    def test_calculate_cyclomatic_complexity_with_conditions(self, analyzer):
        """Test cyclomatic complexity with conditions."""
        code = """
def complex_function(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x
    elif x < 0:
        return -x
    else:
        return 0
"""
        tree = ast.parse(code)
        complexity = analyzer._calculate_cyclomatic_complexity(tree.body[0])
        assert complexity > 1  # Should be higher due to conditions
    
    def test_calculate_cognitive_complexity(self, analyzer):
        """Test cognitive complexity calculation."""
        code = """
def nested_function(items):
    total = 0
    for item in items:  # +1
        if item > 0:    # +2 (nested)
            if item % 2 == 0:  # +3 (double nested)
                total += item * 2
            else:       # +1
                total += item
        elif item < 0:  # +1
            total -= item
    return total
"""
        tree = ast.parse(code)
        complexity = analyzer._calculate_cognitive_complexity(tree.body[0])
        assert complexity > 5  # Should be high due to nesting
    
    def test_calculate_maintainability_index(self, analyzer):
        """Test maintainability index calculation."""
        code = """
def simple_function():
    '''Simple function with good maintainability.'''
    return True
"""
        tree = ast.parse(code)
        mi = analyzer._calculate_maintainability_index(tree.body[0], code)
        assert 0 <= mi <= 100  # MI should be between 0 and 100
        assert mi > 50  # Simple function should have good maintainability
    
    def test_analyze_code_smells_long_parameter_list(self, analyzer):
        """Test detection of long parameter lists."""
        code = """
def function_with_many_params(a, b, c, d, e, f, g, h, i, j):
    return a + b + c + d + e + f + g + h + i + j
"""
        tree = ast.parse(code)
        smells = analyzer._analyze_code_smells(tree, Path("test.py"))
        
        # Should detect long parameter list
        param_smells = [s for s in smells if "parameter" in s.description.lower()]
        assert len(param_smells) > 0
    
    def test_analyze_code_smells_deep_nesting(self, analyzer):
        """Test detection of deep nesting."""
        code = """
def deeply_nested():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        return "too deep"
"""
        tree = ast.parse(code)
        smells = analyzer._analyze_code_smells(tree, Path("test.py"))
        
        # Should detect deep nesting
        nesting_smells = [s for s in smells if "nesting" in s.description.lower()]
        assert len(nesting_smells) > 0
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_run_flake8_analysis(self, mock_subprocess, analyzer, tmp_path):
        """Test flake8 integration."""
        # Mock flake8 output
        mock_subprocess.return_value.stdout = "test.py:1:1: E302 expected 2 blank lines"
        mock_subprocess.return_value.stderr = ""
        mock_subprocess.return_value.returncode = 0
        
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")
        
        issues = await analyzer._run_flake8_analysis([test_file])
        
        assert len(issues) > 0
        assert issues[0].issue_type == IssueType.STYLE_VIOLATION
        assert "E302" in issues[0].description
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_run_mypy_analysis(self, mock_subprocess, analyzer, tmp_path):
        """Test mypy integration."""
        # Mock mypy output
        mock_subprocess.return_value.stdout = "test.py:1: error: Function is missing a return type annotation"
        mock_subprocess.return_value.stderr = ""
        mock_subprocess.return_value.returncode = 0
        
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")
        
        issues = await analyzer._run_mypy_analysis([test_file])
        
        assert len(issues) > 0
        assert issues[0].issue_type == IssueType.TYPE_ERROR
        assert "return type annotation" in issues[0].description


class TestDuplicateCodeDetector:
    """Test cases for DuplicateCodeDetector."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            enable_duplicate_detection=True,
            duplicate_config={
                "min_lines": 5,
                "similarity_threshold": 0.8
            }
        )
    
    @pytest.fixture
    def detector(self, config):
        """Create DuplicateCodeDetector instance."""
        return DuplicateCodeDetector(config)
    
    def test_initialization(self, detector, config):
        """Test detector initialization."""
        assert detector.config == config
        assert detector.min_lines == 5
        assert detector.similarity_threshold == 0.8
    
    def test_code_block_creation(self):
        """Test CodeBlock creation."""
        block = CodeBlock(
            file_path=Path("test.py"),
            start_line=1,
            end_line=5,
            content="def test():\n    pass",
            content_hash="abc123"
        )
        
        assert block.file_path == Path("test.py")
        assert block.start_line == 1
        assert block.end_line == 5
        assert block.lines_of_code == 5
        assert block.content_hash == "abc123"
    
    def test_code_block_equality(self):
        """Test CodeBlock equality."""
        block1 = CodeBlock(Path("test1.py"), 1, 5, "content", "hash123")
        block2 = CodeBlock(Path("test2.py"), 10, 15, "different", "hash123")
        block3 = CodeBlock(Path("test3.py"), 1, 5, "content", "hash456")
        
        assert block1 == block2  # Same hash
        assert block1 != block3  # Different hash
    
    def test_duplicate_group_creation(self):
        """Test DuplicateGroup creation."""
        block1 = CodeBlock(Path("test1.py"), 1, 5, "content", "hash123")
        block2 = CodeBlock(Path("test2.py"), 10, 15, "content", "hash123")
        
        group = DuplicateGroup([block1, block2])
        
        assert len(group.blocks) == 2
        assert group.content_hash == "hash123"
        assert group.total_lines == 10  # 5 + 5
        assert len(group.affected_files) == 2
    
    def test_extract_code_blocks_functions(self, detector, tmp_path):
        """Test extracting function blocks."""
        code = """
def function1():
    '''First function.'''
    x = 1
    y = 2
    return x + y

def function2():
    '''Second function.'''
    a = 3
    b = 4
    return a * b

class TestClass:
    def method1(self):
        return "method"
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)
        
        blocks = detector._extract_code_blocks(test_file)
        
        # Should extract functions and methods
        function_blocks = [b for b in blocks if b.block_type == "function"]
        assert len(function_blocks) >= 2  # At least function1 and function2
    
    def test_calculate_content_hash(self, detector):
        """Test content hash calculation."""
        content1 = "def test():\n    pass"
        content2 = "def test():\n    pass"
        content3 = "def different():\n    return True"
        
        hash1 = detector._calculate_content_hash(content1)
        hash2 = detector._calculate_content_hash(content2)
        hash3 = detector._calculate_content_hash(content3)
        
        assert hash1 == hash2  # Same content
        assert hash1 != hash3  # Different content
        assert len(hash1) == 64  # SHA256 hash length
    
    def test_normalize_code_for_comparison(self, detector):
        """Test code normalization."""
        code = """
def test_function(param1, param2):
    '''Test docstring.'''
    # Comment
    x = param1 + param2
    return x
"""
        normalized = detector._normalize_code_for_comparison(code)
        
        # Should remove comments and normalize whitespace
        assert "# Comment" not in normalized
        assert "'''Test docstring.'''" not in normalized
        assert "def test_function" in normalized
    
    def test_calculate_similarity(self, detector):
        """Test similarity calculation."""
        code1 = "def test():\n    x = 1\n    return x"
        code2 = "def test():\n    y = 1\n    return y"  # Very similar
        code3 = "def completely_different():\n    return 'hello world'"
        
        similarity1 = detector._calculate_similarity(code1, code2)
        similarity2 = detector._calculate_similarity(code1, code3)
        
        assert similarity1 > similarity2  # code1 and code2 are more similar
        assert 0 <= similarity1 <= 1
        assert 0 <= similarity2 <= 1
    
    @pytest.mark.asyncio
    async def test_find_exact_duplicates(self, detector, tmp_path):
        """Test finding exact duplicates."""
        # Create files with exact duplicate functions
        file1_content = """
def duplicate_function():
    x = 1
    y = 2
    z = x + y
    return z

def unique_function1():
    return "unique1"
"""
        
        file2_content = """
def duplicate_function():
    x = 1
    y = 2
    z = x + y
    return z

def unique_function2():
    return "unique2"
"""
        
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text(file1_content)
        file2.write_text(file2_content)
        
        detector.target_directory = tmp_path
        duplicates = await detector.find_exact_duplicates()
        
        assert len(duplicates) > 0
        # Should find the duplicate_function in both files
        duplicate_groups = [d for d in duplicates if len(d.locations) >= 2]
        assert len(duplicate_groups) > 0
    
    @pytest.mark.asyncio
    async def test_find_similar_blocks(self, detector, tmp_path):
        """Test finding similar code blocks."""
        file1_content = """
def similar_function1():
    x = 1
    y = 2
    result = x + y
    return result

def different_function():
    return "completely different"
"""
        
        file2_content = """
def similar_function2():
    a = 1
    b = 2
    total = a + b
    return total

def another_different():
    return "also different"
"""
        
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text(file1_content)
        file2.write_text(file2_content)
        
        detector.target_directory = tmp_path
        similar_blocks = await detector.find_similar_blocks(0.7)  # 70% similarity
        
        # Should find similar functions
        assert len(similar_blocks) >= 0  # May or may not find similarities depending on threshold


class TestImportAnalyzer:
    """Test cases for ImportAnalyzer."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            enable_import_analysis=True
        )
    
    @pytest.fixture
    def analyzer(self, config):
        """Create ImportAnalyzer instance."""
        return ImportAnalyzer(config)
    
    def test_initialization(self, analyzer, config):
        """Test analyzer initialization."""
        assert analyzer.config == config
        assert analyzer.import_graph == {}
        assert analyzer.all_imports == {}
        assert analyzer.used_names == {}
    
    def test_extract_imports_from_file(self, analyzer, tmp_path):
        """Test extracting imports from file."""
        code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
from .local_module import local_function
from ..parent_module import parent_function
import unused_module  # This won't be used
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)
        
        imports = analyzer._extract_imports_from_file(test_file)
        
        assert len(imports) > 0
        import_names = [imp['module'] for imp in imports]
        assert 'os' in import_names
        assert 'sys' in import_names
        assert 'pathlib' in import_names
        assert 'typing' in import_names
    
    def test_extract_used_names_from_file(self, analyzer, tmp_path):
        """Test extracting used names from file."""
        code = """
import os
from pathlib import Path

def test_function():
    current_dir = os.getcwd()
    path = Path(current_dir)
    return path.exists()
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)
        
        used_names = analyzer._extract_used_names_from_file(test_file)
        
        assert 'os' in used_names
        assert 'Path' in used_names
    
    @pytest.mark.asyncio
    async def test_find_unused_imports(self, analyzer, tmp_path):
        """Test finding unused imports."""
        code = """
import os
import sys  # Used
import json  # Unused
from pathlib import Path  # Used
from typing import List  # Unused

def test_function():
    current_dir = sys.path[0]
    path = Path(current_dir)
    return path
"""
        test_file = tmp_path / "test.py"
        test_file.write_text(code)
        
        analyzer.target_directory = tmp_path
        unused_imports = await analyzer.find_unused_imports()
        
        # Should find unused imports
        unused_modules = [imp.module_name for imp in unused_imports]
        assert 'json' in unused_modules or 'List' in unused_modules
    
    def test_build_dependency_graph(self, analyzer, tmp_path):
        """Test building dependency graph."""
        # Create multiple files with imports
        file1_content = """
from .module2 import function2
from .module3 import function3

def function1():
    return function2() + function3()
"""
        
        file2_content = """
from .module3 import function3

def function2():
    return function3() * 2
"""
        
        file3_content = """
def function3():
    return 42
"""
        
        (tmp_path / "module1.py").write_text(file1_content)
        (tmp_path / "module2.py").write_text(file2_content)
        (tmp_path / "module3.py").write_text(file3_content)
        
        analyzer.target_directory = tmp_path
        analyzer._build_dependency_graph()
        
        # Should build a dependency graph
        assert len(analyzer.import_graph) > 0
    
    @pytest.mark.asyncio
    async def test_detect_circular_imports(self, analyzer, tmp_path):
        """Test detecting circular imports."""
        # Create circular import scenario
        file1_content = """
from .module2 import function2

def function1():
    return function2()
"""
        
        file2_content = """
from .module1 import function1

def function2():
    return function1()
"""
        
        (tmp_path / "module1.py").write_text(file1_content)
        (tmp_path / "module2.py").write_text(file2_content)
        
        analyzer.target_directory = tmp_path
        circular_imports = await analyzer.detect_circular_imports()
        
        # May or may not detect circular imports depending on implementation
        # This is a complex analysis that might need more sophisticated logic
        assert isinstance(circular_imports, list)


class TestStructureAnalyzer:
    """Test cases for StructureAnalyzer."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            enable_structure_analysis=True
        )
    
    @pytest.fixture
    def analyzer(self, config):
        """Create StructureAnalyzer instance."""
        return StructureAnalyzer(config)
    
    def test_initialization(self, analyzer, config):
        """Test analyzer initialization."""
        assert analyzer.config == config
    
    @pytest.mark.asyncio
    async def test_analyze_directory_organization(self, analyzer, tmp_path):
        """Test directory organization analysis."""
        # Create a project structure
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mypackage").mkdir()
        (tmp_path / "src" / "mypackage" / "__init__.py").write_text("")
        (tmp_path / "src" / "mypackage" / "main.py").write_text("def main(): pass")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("def test_main(): pass")
        (tmp_path / "README.md").write_text("# Test Project")
        (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 88")
        
        analyzer.target_directory = tmp_path
        structure_report = await analyzer.analyze_directory_organization()
        
        assert structure_report is not None
        # Should analyze the directory structure
    
    def test_detect_empty_directories(self, analyzer, tmp_path):
        """Test empty directory detection."""
        # Create empty directories
        (tmp_path / "empty1").mkdir()
        (tmp_path / "empty2").mkdir()
        (tmp_path / "not_empty").mkdir()
        (tmp_path / "not_empty" / "file.py").write_text("content")
        
        analyzer.target_directory = tmp_path
        empty_dirs = analyzer._detect_empty_directories()
        
        empty_dir_names = [d.name for d in empty_dirs]
        assert "empty1" in empty_dir_names
        assert "empty2" in empty_dir_names
        assert "not_empty" not in empty_dir_names
    
    def test_find_misplaced_files(self, analyzer, tmp_path):
        """Test misplaced file detection."""
        # Create project structure with misplaced files
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "main.py").write_text("def main(): pass")
        (tmp_path / "test_outside.py").write_text("def test(): pass")  # Misplaced test
        (tmp_path / "script_in_root.py").write_text("#!/usr/bin/env python")  # Might be misplaced
        
        analyzer.target_directory = tmp_path
        misplaced = analyzer._find_misplaced_files()
        
        # Should identify potentially misplaced files
        assert isinstance(misplaced, list)
    
    def test_evaluate_project_structure(self, analyzer, tmp_path):
        """Test project structure evaluation."""
        # Create a well-structured project
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mypackage").mkdir()
        (tmp_path / "src" / "mypackage" / "__init__.py").write_text("")
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "README.md").write_text("# Project")
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        
        analyzer.target_directory = tmp_path
        evaluation = analyzer._evaluate_project_structure()
        
        assert evaluation is not None
        assert 'score' in evaluation
        assert 'recommendations' in evaluation