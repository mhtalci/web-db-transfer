"""
Tests for Structure Analyzer

Tests directory organization analysis and misplaced file detection.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.checkup.analyzers.structure import StructureAnalyzer
from migration_assistant.checkup.models import (
    CheckupConfig, StructureIssue, IssueType, IssueSeverity
)


class TestStructureAnalyzer:
    """Test cases for StructureAnalyzer."""
    
    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create a sample project structure
        project_structure = {
            'README.md': '# Test Project',
            'pyproject.toml': '[tool.black]\nline-length = 88',
            'src/mypackage/__init__.py': '',
            'src/mypackage/main.py': 'def main(): pass',
            'src/mypackage/utils.py': 'def helper(): pass',
            'tests/__init__.py': '',
            'tests/test_main.py': 'def test_main(): pass',
            'docs/README.md': '# Documentation',
            'scripts/deploy.py': 'if __name__ == "__main__": pass',
            'config/settings.py': 'DEBUG = True',
            'wrongplace/README.md': '# Misplaced readme',
            'deep/very/deeply/nested/file.py': 'pass',
            'badname123/module.py': 'pass',
            'test_outside.py': 'def test_something(): pass',
            'script_outside.py': 'if __name__ == "__main__": pass',
            'config_outside.toml': '[section]\nkey = "value"',
        }
        
        # Create files and directories
        for file_path, content in project_structure.items():
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config(self, temp_project):
        """Create test configuration."""
        return CheckupConfig(target_directory=temp_project)
    
    @pytest.fixture
    def analyzer(self, config):
        """Create analyzer instance."""
        return StructureAnalyzer(config)
    
    def test_get_supported_file_types(self, analyzer):
        """Test supported file types."""
        supported = analyzer.get_supported_file_types()
        expected = ['.py', '.md', '.txt', '.toml', '.yml', '.yaml', '.cfg', '.ini']
        assert supported == expected
    
    def test_analyze_directory_organization(self, analyzer):
        """Test directory organization analysis."""
        issues = analyzer.analyze_directory_organization()
        
        # Should find non-standard directory names
        non_standard_issues = [i for i in issues if 'Non-standard directory name' in i.message]
        assert len(non_standard_issues) > 0
        
        # Should find deeply nested structures
        deep_nested_issues = [i for i in issues if 'Deeply nested directory' in i.message]
        assert len(deep_nested_issues) > 0
    
    def test_find_misplaced_files(self, analyzer):
        """Test misplaced file detection."""
        issues = analyzer.find_misplaced_files()
        
        # Should find misplaced README
        readme_issues = [i for i in issues if 'README.md' in str(i.file_path) and 'wrongplace' in str(i.file_path)]
        assert len(readme_issues) > 0
        
        # Should find test file outside tests directory
        test_issues = [i for i in issues if 'test_outside.py' in str(i.file_path)]
        assert len(test_issues) > 0
        
        # Should find script file outside scripts directory
        script_issues = [i for i in issues if 'script_outside.py' in str(i.file_path)]
        assert len(script_issues) > 0
    
    def test_is_non_standard_directory(self, analyzer):
        """Test non-standard directory detection."""
        # Standard directories should not be flagged
        assert not analyzer._is_non_standard_directory(Path('src'))
        assert not analyzer._is_non_standard_directory(Path('tests'))
        assert not analyzer._is_non_standard_directory(Path('docs'))
        
        # Non-standard directories should be flagged
        assert analyzer._is_non_standard_directory(Path('badname123'))
        assert analyzer._is_non_standard_directory(Path('WeirdName'))
    
    def test_is_valid_python_package_name(self, analyzer):
        """Test Python package name validation."""
        # Valid names
        assert analyzer._is_valid_python_package_name('mypackage')
        assert analyzer._is_valid_python_package_name('my_package')
        assert analyzer._is_valid_python_package_name('package123')
        
        # Invalid names
        assert not analyzer._is_valid_python_package_name('123package')
        assert not analyzer._is_valid_python_package_name('My-Package')
        assert not analyzer._is_valid_python_package_name('MyPackage')
    
    def test_suggest_directory_rename(self, analyzer):
        """Test directory rename suggestions."""
        suggestions = {
            Path('util'): 'utils',
            Path('helper'): 'helpers',
            Path('script'): 'scripts',
            Path('document'): 'docs',
        }
        
        for directory, expected in suggestions.items():
            suggestion = analyzer._suggest_directory_rename(directory)
            assert expected in suggestion
    
    def test_find_python_packages(self, analyzer):
        """Test Python package discovery."""
        packages = analyzer._find_python_packages()
        
        # Should find packages with __init__.py
        package_names = [p.name for p in packages]
        assert 'mypackage' in package_names
        assert 'tests' in package_names
    
    def test_is_test_file(self, analyzer):
        """Test test file detection."""
        # Test files
        assert analyzer._is_test_file(Path('test_main.py'))
        assert analyzer._is_test_file(Path('main_test.py'))
        assert analyzer._is_test_file(Path('test.py'))
        assert analyzer._is_test_file(Path('tests/test_something.py'))
        
        # Non-test files
        assert not analyzer._is_test_file(Path('main.py'))
        assert not analyzer._is_test_file(Path('utils.py'))
    
    def test_is_documentation_file(self, analyzer):
        """Test documentation file detection."""
        # Documentation files
        assert analyzer._is_documentation_file(Path('README.md'))
        assert analyzer._is_documentation_file(Path('CHANGELOG.md'))
        assert analyzer._is_documentation_file(Path('docs/guide.md'))
        
        # Non-documentation files
        assert not analyzer._is_documentation_file(Path('main.py'))
        assert not analyzer._is_documentation_file(Path('config.toml'))
    
    def test_is_config_file(self, analyzer):
        """Test configuration file detection."""
        # Configuration files
        assert analyzer._is_config_file(Path('pyproject.toml'))
        assert analyzer._is_config_file(Path('config.yaml'))
        assert analyzer._is_config_file(Path('settings.ini'))
        
        # Non-configuration files
        assert not analyzer._is_config_file(Path('main.py'))
        assert not analyzer._is_config_file(Path('README.md'))
    
    def test_contains_config_patterns(self, analyzer):
        """Test configuration pattern detection."""
        # Content with config patterns
        config_content = """
        class DatabaseConfig:
            host = 'localhost'
        
        SETTINGS = {
            'debug': True
        }
        """
        assert analyzer._contains_config_patterns(config_content)
        
        # Content without config patterns
        regular_content = """
        def main():
            print("Hello world")
        """
        assert not analyzer._contains_config_patterns(regular_content)
    
    def test_check_python_file_placement(self, analyzer, temp_project):
        """Test Python file placement checking."""
        # Create a script file outside scripts directory
        script_file = temp_project / 'misplaced_script.py'
        script_file.write_text('if __name__ == "__main__":\n    print("Hello")')
        
        issue = analyzer._check_python_file_placement(script_file)
        assert issue is not None
        assert 'Script file not in scripts directory' in issue.message
        assert issue.suggested_location == temp_project / 'scripts' / 'misplaced_script.py'
    
    def test_check_test_file_placement(self, analyzer, temp_project):
        """Test test file placement checking."""
        # Test file outside tests directory
        test_file = temp_project / 'test_misplaced.py'
        
        issue = analyzer._check_test_file_placement(test_file)
        assert issue is not None
        assert 'Test file not in tests directory' in issue.message
        assert issue.suggested_location == temp_project / 'tests' / 'test_misplaced.py'
    
    def test_check_documentation_placement(self, analyzer, temp_project):
        """Test documentation file placement checking."""
        # Documentation file in wrong location
        doc_file = temp_project / 'subdir' / 'guide.md'
        doc_file.parent.mkdir(exist_ok=True)
        doc_file.write_text('# Guide')
        
        issue = analyzer._check_documentation_placement(doc_file)
        assert issue is not None
        assert 'Documentation file not in docs directory' in issue.message
    
    def test_check_config_file_placement(self, analyzer, temp_project):
        """Test configuration file placement checking."""
        # Config file in wrong location
        config_file = temp_project / 'subdir' / 'config.yaml'
        config_file.parent.mkdir(exist_ok=True)
        config_file.write_text('key: value')
        
        issue = analyzer._check_config_file_placement(config_file)
        assert issue is not None
        assert 'Configuration file not in standard location' in issue.message
    
    def test_create_structure_issue(self, analyzer, temp_project):
        """Test structure issue creation."""
        file_path = temp_project / 'test.py'
        suggested_location = temp_project / 'tests' / 'test.py'
        
        issue = analyzer._create_structure_issue(
            file_path=file_path,
            issue_type=IssueType.STRUCTURE_ISSUE,
            severity=IssueSeverity.MEDIUM,
            message="Test message",
            description="Test description",
            suggestion="Test suggestion",
            suggested_location=suggested_location
        )
        
        assert isinstance(issue, StructureIssue)
        assert issue.file_path == file_path
        assert issue.severity == IssueSeverity.MEDIUM
        assert issue.message == "Test message"
        assert issue.suggested_location == suggested_location
        assert issue.confidence == 0.8
    
    @pytest.mark.asyncio
    async def test_full_analyze(self, analyzer):
        """Test full analysis workflow."""
        issues = await analyzer.analyze()
        
        # Should find various types of issues
        assert len(issues) > 0
        
        # Check that metrics are updated
        assert analyzer.metrics.structure_issues > 0
        assert analyzer.metrics.misplaced_files >= 0
        
        # Verify issue types
        issue_messages = [issue.message for issue in issues]
        assert any('Non-standard directory name' in msg for msg in issue_messages)
        assert any('Test file not in tests directory' in msg for msg in issue_messages)


class TestStructureAnalyzerEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def minimal_config(self):
        """Create minimal configuration."""
        temp_dir = Path(tempfile.mkdtemp())
        config = CheckupConfig(target_directory=temp_dir)
        yield config, temp_dir
        shutil.rmtree(temp_dir)
    
    def test_empty_directory(self, minimal_config):
        """Test analysis of empty directory."""
        config, temp_dir = minimal_config
        analyzer = StructureAnalyzer(config)
        
        issues = analyzer.analyze()
        assert len(issues) == 0
    
    def test_unreadable_file_handling(self, minimal_config):
        """Test handling of unreadable files."""
        config, temp_dir = minimal_config
        analyzer = StructureAnalyzer(config)
        
        # Create a file that will cause UnicodeDecodeError
        binary_file = temp_dir / 'binary.py'
        binary_file.write_bytes(b'\x80\x81\x82')
        
        # Should not raise exception
        issue = analyzer._check_python_file_placement(binary_file)
        assert issue is None
    
    def test_should_analyze_file_exclusions(self, minimal_config):
        """Test file exclusion logic."""
        config, temp_dir = minimal_config
        config.exclude_patterns = ['*.pyc', 'temp_*']
        config.exclude_dirs = ['__pycache__', '.git']
        
        analyzer = StructureAnalyzer(config)
        
        # Should exclude based on patterns
        assert not analyzer.should_analyze_file(temp_dir / 'file.pyc')
        assert not analyzer.should_analyze_file(temp_dir / 'temp_file.py')
        
        # Should exclude based on directory
        assert not analyzer.should_analyze_file(temp_dir / '__pycache__' / 'file.py')
        assert not analyzer.should_analyze_file(temp_dir / '.git' / 'config')
        
        # Should include valid files
        assert analyzer.should_analyze_file(temp_dir / 'valid.py')


if __name__ == '__main__':
    pytest.main([__file__])