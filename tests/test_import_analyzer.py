"""
Tests for Import Analyzer

Tests the import analysis functionality including unused import detection.
"""

import ast
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from tempfile import TemporaryDirectory

from migration_assistant.checkup.analyzers.imports import ImportAnalyzer
from migration_assistant.checkup.models import (
    CheckupConfig, ImportIssue, IssueType, IssueSeverity
)


class TestImportAnalyzer:
    """Test cases for ImportAnalyzer."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("."),
            enable_import_analysis=True
        )
    
    @pytest.fixture
    def analyzer(self, config):
        """Create ImportAnalyzer instance."""
        return ImportAnalyzer(config)
    
    def test_get_supported_file_types(self, analyzer):
        """Test supported file types."""
        file_types = analyzer.get_supported_file_types()
        assert file_types == ['.py']
    
    def test_extract_imports_simple(self, analyzer):
        """Test extracting simple imports."""
        code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
        tree = ast.parse(code)
        imports = analyzer._extract_imports(tree)
        
        assert len(imports) == 4
        
        # Check import os
        os_import = next(imp for imp in imports if imp['name'] == 'os')
        assert os_import['type'] == 'import'
        assert os_import['module'] == 'os'
        assert os_import['statement'] == 'import os'
        
        # Check from pathlib import Path
        path_import = next(imp for imp in imports if imp['name'] == 'Path')
        assert path_import['type'] == 'from'
        assert path_import['module'] == 'pathlib'
        assert path_import['statement'] == 'from pathlib import Path'
    
    def test_extract_imports_with_aliases(self, analyzer):
        """Test extracting imports with aliases."""
        code = """
import numpy as np
from matplotlib import pyplot as plt
"""
        tree = ast.parse(code)
        imports = analyzer._extract_imports(tree)
        
        assert len(imports) == 2
        
        # Check numpy alias
        np_import = next(imp for imp in imports if imp['name'] == 'np')
        assert np_import['type'] == 'import'
        assert np_import['module'] == 'numpy'
        assert np_import['statement'] == 'import numpy as np'
        
        # Check pyplot alias
        plt_import = next(imp for imp in imports if imp['name'] == 'plt')
        assert plt_import['type'] == 'from'
        assert plt_import['module'] == 'matplotlib'
        assert plt_import['statement'] == 'from matplotlib import pyplot as plt'
    
    def test_extract_imports_star_import(self, analyzer):
        """Test extracting star imports."""
        code = "from os import *"
        tree = ast.parse(code)
        imports = analyzer._extract_imports(tree)
        
        assert len(imports) == 1
        star_import = imports[0]
        assert star_import['type'] == 'from_star'
        assert star_import['name'] == '*'
        assert star_import['statement'] == 'from os import *'
    
    def test_extract_used_names(self, analyzer):
        """Test extracting used names from code."""
        code = """
import os
import sys
from pathlib import Path

def main():
    path = Path('/tmp')
    print(path)
    os.getcwd()
"""
        tree = ast.parse(code)
        used_names = analyzer._extract_used_names(tree, code)
        
        assert 'Path' in used_names
        assert 'os' in used_names
        assert 'print' in used_names
        assert 'path' in used_names
        assert 'main' in used_names
    
    def test_find_string_usage_all_definition(self, analyzer):
        """Test finding names in __all__ definition."""
        content = '__all__ = ["function1", "Class1", "CONSTANT"]'
        string_usage = analyzer._find_string_usage(content)
        
        assert 'function1' in string_usage
        assert 'Class1' in string_usage
        assert 'CONSTANT' in string_usage
    
    def test_is_import_used_direct_usage(self, analyzer):
        """Test detecting direct import usage."""
        import_info = {
            'name': 'os',
            'type': 'import',
            'full_name': 'os'
        }
        used_names = {'os', 'sys', 'Path'}
        content = "os.getcwd()"
        
        assert analyzer._is_import_used(import_info, used_names, content)
    
    def test_is_import_used_attribute_access(self, analyzer):
        """Test detecting import usage through attribute access."""
        import_info = {
            'name': 'os',
            'type': 'import',
            'full_name': 'os'
        }
        used_names = {'getcwd'}  # os not in used_names
        content = "result = os.getcwd()"
        
        assert analyzer._is_import_used(import_info, used_names, content)
    
    def test_is_import_used_not_used(self, analyzer):
        """Test detecting unused import."""
        import_info = {
            'name': 'unused_module',
            'type': 'import',
            'full_name': 'unused_module'
        }
        used_names = {'os', 'sys'}
        content = "print('hello')"
        
        assert not analyzer._is_import_used(import_info, used_names, content)
    
    def test_check_special_usage_decorator(self, analyzer):
        """Test detecting import usage in decorators."""
        import_info = {'name': 'pytest'}
        content = """
@pytest.fixture
def my_fixture():
    pass
"""
        assert analyzer._check_special_usage(import_info, content)
    
    def test_check_special_usage_exception(self, analyzer):
        """Test detecting import usage in exception handling."""
        import_info = {'name': 'ValueError'}
        content = """
try:
    do_something()
except ValueError:
    pass
"""
        assert analyzer._check_special_usage(import_info, content)
    
    def test_is_safe_to_remove_safe_import(self, analyzer):
        """Test identifying safe-to-remove imports."""
        import_info = {
            'module': 'custom_module',
            'statement': 'import custom_module'
        }
        content = "import custom_module"
        
        assert analyzer._is_safe_to_remove(import_info, content)
    
    def test_is_safe_to_remove_side_effect_import(self, analyzer):
        """Test identifying imports with potential side effects."""
        import_info = {
            'module': 'matplotlib.pyplot',
            'statement': 'import matplotlib.pyplot'
        }
        content = "import matplotlib.pyplot"
        
        assert not analyzer._is_safe_to_remove(import_info, content)
    
    def test_is_safe_to_remove_try_except_import(self, analyzer):
        """Test identifying imports in try/except blocks."""
        import_info = {
            'module': 'optional_module',
            'statement': 'import optional_module',
            'line_number': 3
        }
        content = """try:
    import optional_module
except ImportError:
    optional_module = None"""
        
        assert not analyzer._is_safe_to_remove(import_info, content)
    
    @pytest.mark.asyncio
    async def test_analyze_file_imports_unused_import(self, analyzer):
        """Test analyzing file with unused imports."""
        code = """
import os
import sys
from pathlib import Path

def main():
    path = Path('/tmp')
    print(path)
"""
        
        with patch('builtins.open', mock_open(read_data=code)):
            issues = await analyzer._analyze_file_imports(Path('test.py'))
        
        # Should find unused imports: os and sys
        unused_issues = [issue for issue in issues if issue.issue_type == IssueType.UNUSED_IMPORT]
        assert len(unused_issues) >= 2
        
        unused_names = {issue.import_name for issue in unused_issues}
        assert 'os' in unused_names
        assert 'sys' in unused_names
    
    @pytest.mark.asyncio
    async def test_analyze_file_imports_all_used(self, analyzer):
        """Test analyzing file with all imports used."""
        code = """
import os
from pathlib import Path

def main():
    path = Path(os.getcwd())
    print(path)
"""
        
        with patch('builtins.open', mock_open(read_data=code)):
            issues = await analyzer._analyze_file_imports(Path('test.py'))
        
        # Should find no unused imports
        unused_issues = [issue for issue in issues if issue.issue_type == IssueType.UNUSED_IMPORT]
        assert len(unused_issues) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_file_imports_syntax_error(self, analyzer):
        """Test analyzing file with syntax errors."""
        code = """
import os
def main(
    # Syntax error - missing closing parenthesis
"""
        
        with patch('builtins.open', mock_open(read_data=code)):
            issues = await analyzer._analyze_file_imports(Path('test.py'))
        
        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.HIGH
        assert "syntax error" in issues[0].message.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_file_imports_read_error(self, analyzer):
        """Test analyzing file that can't be read."""
        with patch('builtins.open', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid')):
            issues = await analyzer._analyze_file_imports(Path('test.py'))
        
        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.LOW
        assert "could not read file" in issues[0].message.lower()
    
    @pytest.mark.asyncio
    async def test_find_unused_imports_integration(self, analyzer):
        """Test the complete unused imports detection workflow."""
        # Create temporary files for testing
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test file with unused imports
            test_file = temp_path / 'test_module.py'
            test_file.write_text("""
import os
import sys
import json
from pathlib import Path
from typing import List

def process_path():
    path = Path('/tmp')
    data = json.loads('{}')
    return path, data
""")
            
            # Update analyzer config to point to temp directory
            analyzer.config.target_directory = temp_path
            
            # Run analysis
            issues = await analyzer.find_unused_imports()
            
            # Should find unused imports: os, sys, List
            unused_names = {issue.import_name for issue in issues}
            assert 'os' in unused_names
            assert 'sys' in unused_names
            assert 'List' in unused_names
            
            # Should not flag used imports: json, Path
            assert 'json' not in unused_names
            assert 'Path' not in unused_names
    
    @pytest.mark.asyncio
    async def test_analyze_main_workflow(self, analyzer):
        """Test the main analyze workflow."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test file
            test_file = temp_path / 'test.py'
            test_file.write_text("""
import unused_module
from pathlib import Path

path = Path('/tmp')
""")
            
            analyzer.config.target_directory = temp_path
            
            # Run main analysis
            issues = await analyzer.analyze()
            
            # Should find unused import
            assert len(issues) >= 1
            unused_issue = next(issue for issue in issues if issue.import_name == 'unused_module')
            assert unused_issue.issue_type == IssueType.UNUSED_IMPORT
            
            # Check metrics were updated
            assert analyzer.metrics.unused_imports >= 1


    @pytest.mark.asyncio
    async def test_analyze_includes_circular_imports(self, analyzer):
        """Test that main analyze includes circular import detection."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create files with circular imports
            file_a = temp_path / 'module_a.py'
            file_a.write_text("""
import unused_module
from . import module_b

def function_a():
    return module_b.function_b()
""")
            
            file_b = temp_path / 'module_b.py'
            file_b.write_text("""
from . import module_a

def function_b():
    return module_a.function_a()
""")
            
            analyzer.config.target_directory = temp_path
            
            # Run main analysis
            issues = await analyzer.analyze()
            
            # Should find both unused imports and circular imports
            unused_issues = [issue for issue in issues if issue.issue_type == IssueType.UNUSED_IMPORT]
            circular_issues = [issue for issue in issues if issue.issue_type == IssueType.CIRCULAR_IMPORT]
            
            assert len(unused_issues) >= 1  # unused_module
            assert len(circular_issues) >= 1  # circular dependency


class TestCircularImportDetection:
    """Test cases for circular import detection."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer for circular import testing."""
        config = CheckupConfig(target_directory=Path("."))
        return ImportAnalyzer(config)
    
    def test_get_module_name(self, analyzer):
        """Test converting file path to module name."""
        analyzer.config.target_directory = Path("/project")
        
        # Test regular module
        file_path = Path("/project/package/module.py")
        module_name = analyzer._get_module_name(file_path)
        assert module_name == "package.module"
        
        # Test __init__.py
        init_path = Path("/project/package/__init__.py")
        init_module = analyzer._get_module_name(init_path)
        assert init_module == "package"
        
        # Test root level module
        root_path = Path("/project/module.py")
        root_module = analyzer._get_module_name(root_path)
        assert root_module == "module"
    
    def test_resolve_import_module_absolute(self, analyzer):
        """Test resolving absolute imports."""
        import_info = {
            'type': 'import',
            'full_name': 'migration_assistant.core.exceptions'
        }
        
        resolved = analyzer._resolve_import_module(import_info, 'current.module')
        assert resolved == 'migration_assistant.core.exceptions'
    
    def test_resolve_import_module_relative(self, analyzer):
        """Test resolving relative imports."""
        # Test relative import from same package
        import_info = {
            'type': 'from',
            'module': '.sibling'
        }
        
        resolved = analyzer._resolve_import_module(import_info, 'package.current')
        assert resolved == 'package.sibling'
        
        # Test relative import from parent package
        parent_import = {
            'type': 'from',
            'module': '..parent'
        }
        
        resolved_parent = analyzer._resolve_import_module(parent_import, 'package.sub.current')
        assert resolved_parent == 'package.parent'
    
    def test_is_internal_module(self, analyzer):
        """Test identifying internal modules."""
        # Internal module
        assert analyzer._is_internal_module('migration_assistant.core')
        
        # External module
        assert not analyzer._is_internal_module('os')
        assert not analyzer._is_internal_module('numpy')
    
    @pytest.mark.asyncio
    async def test_analyze_dependency_graph_simple(self, analyzer):
        """Test building dependency graph."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create module A that imports B
            module_a = temp_path / 'module_a.py'
            module_a.write_text("""
from . import module_b
import os  # External import, should be ignored

def use_b():
    return module_b.function()
""")
            
            # Create module B
            module_b = temp_path / 'module_b.py'
            module_b.write_text("""
def function():
    return "hello"
""")
            
            analyzer.config.target_directory = temp_path
            
            # Build dependency graph
            graph = await analyzer.analyze_dependency_graph()
            
            # Should show module_a depends on module_b
            assert 'module_a' in graph
            assert 'module_b' in graph['module_a']
            
            # module_b should have no internal dependencies
            assert graph.get('module_b', []) == []
    
    @pytest.mark.asyncio
    async def test_detect_circular_imports_simple_cycle(self, analyzer):
        """Test detecting simple circular imports."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create circular dependency: A -> B -> A
            module_a = temp_path / 'module_a.py'
            module_a.write_text("""
from . import module_b

def function_a():
    return module_b.function_b()
""")
            
            module_b = temp_path / 'module_b.py'
            module_b.write_text("""
from . import module_a

def function_b():
    return module_a.function_a()
""")
            
            analyzer.config.target_directory = temp_path
            
            # Detect circular imports
            issues = await analyzer.detect_circular_imports()
            
            # Should find circular import issues
            assert len(issues) >= 2  # One for each module in the cycle
            
            circular_issue = issues[0]
            assert circular_issue.issue_type == IssueType.CIRCULAR_IMPORT
            assert circular_issue.severity == IssueSeverity.HIGH
            assert circular_issue.is_circular
            assert len(circular_issue.dependency_chain) >= 3  # A -> B -> A
    
    @pytest.mark.asyncio
    async def test_detect_circular_imports_complex_cycle(self, analyzer):
        """Test detecting complex circular imports (A -> B -> C -> A)."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create complex circular dependency: A -> B -> C -> A
            module_a = temp_path / 'module_a.py'
            module_a.write_text("from . import module_b")
            
            module_b = temp_path / 'module_b.py'
            module_b.write_text("from . import module_c")
            
            module_c = temp_path / 'module_c.py'
            module_c.write_text("from . import module_a")
            
            analyzer.config.target_directory = temp_path
            
            # Detect circular imports
            issues = await analyzer.detect_circular_imports()
            
            # Should find circular import issues
            assert len(issues) >= 3  # One for each module in the cycle
            
            # Check that all modules are identified as part of the cycle
            modules_in_cycle = {issue.file_path.stem for issue in issues}
            assert 'module_a' in modules_in_cycle
            assert 'module_b' in modules_in_cycle
            assert 'module_c' in modules_in_cycle
    
    @pytest.mark.asyncio
    async def test_detect_circular_imports_no_cycle(self, analyzer):
        """Test that no issues are found when there are no circular imports."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create linear dependency: A -> B -> C (no cycle)
            module_a = temp_path / 'module_a.py'
            module_a.write_text("from . import module_b")
            
            module_b = temp_path / 'module_b.py'
            module_b.write_text("from . import module_c")
            
            module_c = temp_path / 'module_c.py'
            module_c.write_text("# No imports")
            
            analyzer.config.target_directory = temp_path
            
            # Detect circular imports
            issues = await analyzer.detect_circular_imports()
            
            # Should find no circular import issues
            assert len(issues) == 0
    
    def test_suggest_circular_import_resolution(self, analyzer):
        """Test circular import resolution suggestions."""
        cycle = ['module_a', 'module_b', 'module_a']
        suggestion = analyzer._suggest_circular_import_resolution(cycle)
        
        assert 'module_a -> module_b -> module_a' in suggestion
        assert 'Move shared code' in suggestion
        assert 'import statements inside functions' in suggestion


class TestOrphanedModuleDetection:
    """Test cases for orphaned module detection."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer for orphaned module testing."""
        config = CheckupConfig(target_directory=Path("."))
        return ImportAnalyzer(config)
    
    def test_is_entry_point_module(self, analyzer):
        """Test identifying entry point modules."""
        # Test main.py
        assert analyzer._is_entry_point_module(Path("main.py"))
        assert analyzer._is_entry_point_module(Path("cli.py"))
        assert analyzer._is_entry_point_module(Path("app.py"))
        
        # Test regular module
        assert not analyzer._is_entry_point_module(Path("utils.py"))
    
    def test_is_test_module(self, analyzer):
        """Test identifying test modules."""
        # Test various test patterns
        assert analyzer._is_test_module(Path("test_something.py"))
        assert analyzer._is_test_module(Path("something_test.py"))
        assert analyzer._is_test_module(Path("conftest.py"))
        assert analyzer._is_test_module(Path("tests/test_module.py"))
        
        # Test regular module
        assert not analyzer._is_test_module(Path("module.py"))
    
    def test_is_config_module(self, analyzer):
        """Test identifying configuration modules."""
        # Test config patterns
        assert analyzer._is_config_module(Path("config.py"))
        assert analyzer._is_config_module(Path("settings.py"))
        assert analyzer._is_config_module(Path("constants.py"))
        
        # Test regular module
        assert not analyzer._is_config_module(Path("module.py"))
    
    def test_is_safe_to_remove_module_safe(self, analyzer):
        """Test identifying modules safe to remove."""
        # Very small file
        is_safe, reason = analyzer._is_safe_to_remove_module(Path("dummy"))
        
        # Mock file content for testing
        with patch('builtins.open', mock_open(read_data="# Small comment\npass")):
            is_safe, reason = analyzer._is_safe_to_remove_module(Path("small.py"))
            assert is_safe
            assert "Very small file" in reason
    
    def test_is_safe_to_remove_module_unsafe(self, analyzer):
        """Test identifying modules unsafe to remove."""
        # File with class definition
        class_content = """
class MyClass:
    def method(self):
        pass
"""
        with patch('builtins.open', mock_open(read_data=class_content)):
            is_safe, reason = analyzer._is_safe_to_remove_module(Path("class_module.py"))
            assert not is_safe
            assert "class definitions" in reason
    
    @pytest.mark.asyncio
    async def test_find_orphaned_modules_simple(self, analyzer):
        """Test finding simple orphaned modules."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create used module
            used_module = temp_path / 'used_module.py'
            used_module.write_text("""
def useful_function():
    return "useful"
""")
            
            # Create module that uses it
            main_module = temp_path / 'main.py'
            main_module.write_text("""
from used_module import useful_function

def main():
    print(useful_function())

if __name__ == '__main__':
    main()
""")
            
            # Create orphaned module
            orphaned_module = temp_path / 'orphaned.py'
            orphaned_module.write_text("""
# This module is not imported by anyone
def unused_function():
    return "unused"
""")
            
            analyzer.config.target_directory = temp_path
            
            # Find orphaned modules
            issues = await analyzer.find_orphaned_modules()
            
            # Should find the orphaned module but not the used one or main
            orphaned_names = {issue.import_name for issue in issues}
            assert 'orphaned' in orphaned_names
            assert 'used_module' not in orphaned_names
            assert 'main' not in orphaned_names  # Entry point
    
    @pytest.mark.asyncio
    async def test_find_orphaned_modules_no_orphans(self, analyzer):
        """Test when no orphaned modules exist."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create modules that reference each other
            module_a = temp_path / 'module_a.py'
            module_a.write_text("from module_b import function_b")
            
            module_b = temp_path / 'module_b.py'
            module_b.write_text("def function_b(): pass")
            
            analyzer.config.target_directory = temp_path
            
            # Find orphaned modules
            issues = await analyzer.find_orphaned_modules()
            
            # Should find no orphaned modules
            assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_find_orphaned_modules_excludes_special(self, analyzer):
        """Test that special modules are not considered orphaned."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create special modules that shouldn't be flagged
            init_file = temp_path / '__init__.py'
            init_file.write_text("# Package init")
            
            config_file = temp_path / 'config.py'
            config_file.write_text("CONFIG_VALUE = 'test'")
            
            test_file = temp_path / 'test_something.py'
            test_file.write_text("def test_function(): pass")
            
            analyzer.config.target_directory = temp_path
            
            # Find orphaned modules
            issues = await analyzer.find_orphaned_modules()
            
            # Should not flag special modules as orphaned
            orphaned_names = {issue.import_name for issue in issues}
            assert '__init__' not in orphaned_names
            assert 'config' not in orphaned_names
            assert 'test_something' not in orphaned_names
    
    def test_suggest_orphaned_module_action(self, analyzer):
        """Test orphaned module action suggestions."""
        # Safe to remove
        suggestion_safe = analyzer._suggest_orphaned_module_action(
            'test_module', Path('test.py'), True, 'Very small file'
        )
        assert 'Consider removing' in suggestion_safe
        assert 'Very small file' in suggestion_safe
        
        # Not safe to remove
        suggestion_unsafe = analyzer._suggest_orphaned_module_action(
            'complex_module', Path('complex.py'), False, 'Contains class definitions'
        )
        assert 'Review if this module' in suggestion_unsafe
        assert 'Contains class definitions' in suggestion_unsafe


class TestImportAnalyzerEdgeCases:
    """Test edge cases for ImportAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer for edge case testing."""
        config = CheckupConfig(target_directory=Path("."))
        return ImportAnalyzer(config)
    
    def test_extract_imports_complex_from_import(self, analyzer):
        """Test extracting complex from imports."""
        code = """
from package.subpackage import (
    function1,
    Class1 as MyClass,
    CONSTANT
)
"""
        tree = ast.parse(code)
        imports = analyzer._extract_imports(tree)
        
        assert len(imports) == 3
        
        # Check each import
        names = {imp['name'] for imp in imports}
        assert 'function1' in names
        assert 'MyClass' in names  # Aliased name
        assert 'CONSTANT' in names
    
    def test_is_import_used_in_type_annotation(self, analyzer):
        """Test detecting import usage in type annotations."""
        import_info = {
            'name': 'List',
            'type': 'from',
            'full_name': 'typing.List'
        }
        used_names = {'function', 'str'}  # List not in direct usage
        content = """
from typing import List

def function(items: List[str]) -> None:
    pass
"""
        
        # This should be detected through string usage analysis
        string_usage = analyzer._find_string_usage(content)
        all_used = used_names.union(string_usage)
        
        # The current implementation might not catch this perfectly,
        # but it should be detected through AST analysis
        tree = ast.parse(content)
        ast_used = analyzer._extract_used_names(tree, content)
        
        # List should be in the AST-extracted names
        assert 'List' in ast_used
    
    def test_star_import_always_considered_used(self, analyzer):
        """Test that star imports are always considered used."""
        import_info = {
            'name': '*',
            'type': 'from_star',
            'module': 'os'
        }
        used_names = set()  # Empty used names
        content = "from os import *"
        
        assert analyzer._is_import_used(import_info, used_names, content)
    
    def test_import_in_class_inheritance(self, analyzer):
        """Test detecting import usage in class inheritance."""
        import_info = {'name': 'BaseClass'}
        content = """
from base_module import BaseClass

class MyClass(BaseClass):
    pass
"""
        assert analyzer._check_special_usage(import_info, content)
    
    def test_import_in_isinstance_check(self, analyzer):
        """Test detecting import usage in isinstance checks."""
        import_info = {'name': 'MyType'}
        content = """
from types_module import MyType

def check_type(obj):
    return isinstance(obj, MyType)
"""
        assert analyzer._check_special_usage(import_info, content)