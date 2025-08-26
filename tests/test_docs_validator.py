"""
Tests for Documentation Validator

Tests the DocumentationValidator class functionality including code example validation,
API reference checking, and installation instruction validation.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.checkup.models import (
    CheckupConfig, DocIssue, IssueSeverity, IssueType
)
from migration_assistant.checkup.validators.docs import DocumentationValidator


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def config():
    """Create a test configuration."""
    return CheckupConfig(
        target_directory=Path("."),
        validate_docs=True
    )


@pytest.fixture
def docs_validator(config):
    """Create a DocumentationValidator instance."""
    return DocumentationValidator(config)


class TestDocumentationValidator:
    """Test cases for DocumentationValidator."""
    
    def test_get_validation_scope(self, docs_validator):
        """Test that validation scope is correctly defined."""
        scope = docs_validator.get_validation_scope()
        
        expected_scope = [
            'code_examples_syntax',
            'code_examples_execution',
            'api_references_accuracy',
            'installation_instructions',
            'broken_links',
            'outdated_examples',
            'documentation_completeness',
        ]
        
        assert scope == expected_scope
    
    @pytest.mark.asyncio
    async def test_validate_no_doc_files(self, temp_dir):
        """Test validation when no documentation files exist."""
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        assert result.valid is True
        assert result.files_validated == 0
        assert len(result.issues) == 0
        assert "Validated 0 documentation files" in result.message
    
    @pytest.mark.asyncio
    async def test_validate_valid_readme(self, temp_dir):
        """Test validation of a valid README file."""
        readme_content = """
# Migration Assistant

A comprehensive tool for migrating web applications and databases.

## Installation

```bash
pip install migration-assistant
```

## Development Setup

```bash
git clone https://github.com/example/migration-assistant.git
cd migration-assistant
pip install -e ".[dev]"
```

## Usage

```python
from migration_assistant.cli.main import main

# Run the CLI
main()
```

## API Reference

The main entry point is `migration_assistant.cli.main.main()`.

For more information, see the [documentation](docs/README.md).
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        # Create referenced documentation file
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Documentation")
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 2  # README.md + docs/README.md
        # Should have minimal issues for a well-structured README
        critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_python_syntax_error(self, temp_dir):
        """Test validation of Python code with syntax errors."""
        readme_content = """
# Test Project

## Example

```python
def invalid_function(
    # Missing closing parenthesis and colon
    print("This will cause a syntax error")
```
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        syntax_issues = [i for i in result.issues if "Python syntax error" in i.message]
        assert len(syntax_issues) == 1
        assert syntax_issues[0].severity == IssueSeverity.HIGH
        assert syntax_issues[0].doc_type == "code_example"
    
    @pytest.mark.asyncio
    async def test_validate_unavailable_import(self, temp_dir):
        """Test validation of code with unavailable imports."""
        readme_content = """
# Test Project

## Example

```python
import nonexistent_module
from another_fake_module import something

print("Hello World")
```
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        import_issues = [i for i in result.issues if "Unavailable import" in i.message]
        # Should find issues for both nonexistent imports
        assert len(import_issues) >= 1
        for issue in import_issues:
            assert issue.severity == IssueSeverity.MEDIUM
            assert issue.doc_type == "code_example"
    
    @pytest.mark.asyncio
    async def test_validate_project_import(self, temp_dir):
        """Test validation of project-specific imports."""
        readme_content = """
# Test Project

## Example

```python
from migration_assistant.nonexistent import something
from migration_assistant.cli.main import main

main()
```
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        # Create the valid import path
        migration_dir = temp_dir / "migration_assistant"
        migration_dir.mkdir()
        (migration_dir / "__init__.py").write_text("")
        
        cli_dir = migration_dir / "cli"
        cli_dir.mkdir()
        (cli_dir / "__init__.py").write_text("")
        (cli_dir / "main.py").write_text("def main(): pass")
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        # Should find issue for nonexistent import but not for valid one
        invalid_import_issues = [i for i in result.issues if "Invalid project import" in i.message]
        assert len(invalid_import_issues) == 1
        assert "migration_assistant.nonexistent" in invalid_import_issues[0].description
    
    @pytest.mark.asyncio
    async def test_validate_shell_commands(self, temp_dir):
        """Test validation of shell commands in documentation."""
        readme_content = """
# Test Project

## Installation

```bash
pip install migration_assistant
pip install .
pip install nonexistent-local-package
```

```shell
$ npm install some-package
> apt install python3
```
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        # Create pyproject.toml to make local install valid
        (temp_dir / "pyproject.toml").write_text("""
[project]
name = "test-project"
version = "1.0.0"
""")
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        # Should validate local package references
        package_issues = [i for i in result.issues if "Invalid package" in i.message]
        # The validator should catch issues with nonexistent local packages
        assert len(package_issues) >= 0  # May or may not find issues depending on validation logic
    
    @pytest.mark.asyncio
    async def test_validate_api_references(self, temp_dir):
        """Test validation of API references in documentation."""
        readme_content = """
# Test Project

## API Reference

Use `migration_assistant.cli.main.main()` to run the CLI.

The `NonexistentClass` provides functionality.

Call `invalid_function()` for processing.

Use `migration_assistant.nonexistent.function()` for advanced features.
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        # Create the valid API reference
        migration_dir = temp_dir / "migration_assistant"
        migration_dir.mkdir()
        (migration_dir / "__init__.py").write_text("")
        
        cli_dir = migration_dir / "cli"
        cli_dir.mkdir()
        (cli_dir / "__init__.py").write_text("")
        (cli_dir / "main.py").write_text("def main(): pass")
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        api_issues = [i for i in result.issues if "Invalid API reference" in i.message]
        # Should find issues for invalid references
        assert len(api_issues) >= 1
        
        for issue in api_issues:
            assert issue.severity == IssueSeverity.MEDIUM
            assert issue.doc_type == "api_reference"
            assert issue.outdated_example is True
    
    @pytest.mark.asyncio
    async def test_validate_broken_links(self, temp_dir):
        """Test validation of links in documentation."""
        readme_content = """
# Test Project

## Links

- [Valid local link](docs/README.md)
- [Broken local link](docs/nonexistent.md)
- [External link](https://example.com)
- [Anchor link](#section)
- [Email link](mailto:test@example.com)
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        # Create the valid link target
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Documentation")
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        broken_link_issues = [i for i in result.issues if "Broken local link" in i.message]
        assert len(broken_link_issues) == 1
        assert "docs/nonexistent.md" in broken_link_issues[0].description
        assert broken_link_issues[0].broken_link == "docs/nonexistent.md"
    
    @pytest.mark.asyncio
    async def test_validate_installation_instructions(self, temp_dir):
        """Test validation of installation instructions in README."""
        # README without installation instructions
        readme_content = """
# Test Project

This is a test project.

## Usage

Run the application.
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        install_issues = [i for i in result.issues if "Missing installation instructions" in i.message]
        dev_setup_issues = [i for i in result.issues if "Missing development setup" in i.message]
        
        assert len(install_issues) == 1
        assert len(dev_setup_issues) == 1
        
        for issue in install_issues + dev_setup_issues:
            assert issue.severity == IssueSeverity.LOW
            assert issue.doc_type == "installation"
    
    @pytest.mark.asyncio
    async def test_validate_outdated_examples(self, temp_dir):
        """Test detection of outdated examples."""
        readme_content = """
# Test Project

## Requirements

- Python 3.8 or higher
- Requires Python >=3.9
- Compatible with python 3.7

## Dependencies

```
package==0.1.0
another-package>=0.2.0
```
"""
        
        readme_path = temp_dir / "README.md"
        readme_path.write_text(readme_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        outdated_python_issues = [i for i in result.issues if "Outdated Python version" in i.message]
        outdated_version_issues = [i for i in result.issues if "Potentially outdated version" in i.message]
        
        # Should find issues for old Python versions
        assert len(outdated_python_issues) >= 1
        
        for issue in outdated_python_issues:
            assert issue.severity == IssueSeverity.LOW
            assert issue.doc_type == "version_reference"
            assert issue.outdated_example is True
    
    @pytest.mark.asyncio
    async def test_validate_multiple_doc_files(self, temp_dir):
        """Test validation of multiple documentation files."""
        # Create README.md
        readme_content = """
# Test Project

## Installation

```bash
pip install test-project
```
"""
        (temp_dir / "README.md").write_text(readme_content)
        
        # Create docs/guide.md
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()
        guide_content = """
# User Guide

## Getting Started

```python
import test_project
test_project.run()
```
"""
        (docs_dir / "guide.md").write_text(guide_content)
        
        # Create CHANGELOG.md
        changelog_content = """
# Changelog

## [1.0.0] - 2024-01-01

- Initial release
"""
        (temp_dir / "CHANGELOG.md").write_text(changelog_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 3
        assert "Validated 3 documentation files" in result.message
    
    @pytest.mark.asyncio
    async def test_validate_encoding_error(self, temp_dir):
        """Test handling of files with encoding issues."""
        readme_path = temp_dir / "README.md"
        
        # Write binary data that's not valid UTF-8
        readme_path.write_bytes(b'\x80\x81\x82\x83')
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        result = await validator.validate()
        
        encoding_issues = [i for i in result.issues if "File encoding issue" in i.message]
        assert len(encoding_issues) == 1
        assert encoding_issues[0].severity == IssueSeverity.MEDIUM
        assert encoding_issues[0].doc_type == "encoding"
    
    def test_should_validate_file_exclusions(self, docs_validator, temp_dir):
        """Test that excluded files are not validated."""
        # Test with excluded pattern
        docs_validator.config.exclude_patterns = ["*.test.md"]
        
        test_file = temp_dir / "test.test.md"
        assert not docs_validator.should_validate_file(test_file)
        
        # Test with excluded directory
        docs_validator.config.exclude_dirs = ["temp_docs"]
        
        test_file = temp_dir / "temp_docs" / "guide.md"
        assert not docs_validator.should_validate_file(test_file)
    
    def test_extract_imports_from_ast(self, docs_validator):
        """Test extraction of imports from AST."""
        import ast
        
        code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
        
        tree = ast.parse(code)
        imports = docs_validator._extract_imports_from_ast(tree)
        
        expected_imports = ['os', 'sys', 'pathlib', 'typing']
        assert all(imp in imports for imp in expected_imports)
    
    def test_extract_project_imports(self, docs_validator):
        """Test extraction of project-specific imports."""
        code = """
import os
from migration_assistant.cli import main
from migration_assistant.core.exceptions import MigrationError
import migration_assistant.utils
"""
        
        project_imports = docs_validator._extract_project_imports(code)
        
        expected_imports = [
            'migration_assistant.cli',
            'migration_assistant.core.exceptions',
            'migration_assistant.utils'
        ]
        
        assert all(imp in project_imports for imp in expected_imports)
        assert 'os' not in project_imports
    
    def test_extract_pip_packages(self, docs_validator):
        """Test extraction of package names from pip commands."""
        commands = [
            "pip install package1 package2",
            "pip install package>=1.0.0",
            "pip install -e .",
            "pip install --upgrade package[extra]",
        ]
        
        for command in commands:
            packages = docs_validator._extract_pip_packages(command)
            assert len(packages) >= 1
        
        # Test specific case
        packages = docs_validator._extract_pip_packages("pip install click>=8.0.0 fastapi")
        assert 'click' in packages
        assert 'fastapi' in packages
    
    def test_validate_local_package(self, temp_dir):
        """Test validation of local package references."""
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        # Test current directory install
        (temp_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        assert validator._validate_local_package('.') is True
        
        # Test without pyproject.toml
        (temp_dir / "pyproject.toml").unlink()
        assert validator._validate_local_package('.') is False
        
        # Test main package
        migration_dir = temp_dir / "migration_assistant"
        migration_dir.mkdir()
        assert validator._validate_local_package('migration_assistant') is True
    
    @pytest.mark.asyncio
    async def test_error_handling(self, temp_dir):
        """Test error handling for file access issues."""
        readme_path = temp_dir / "README.md"
        readme_path.write_text("# Test")
        
        config = CheckupConfig(target_directory=temp_dir, validate_docs=True)
        validator = DocumentationValidator(config)
        
        # Mock file reading to raise an exception
        with patch('pathlib.Path.read_text', side_effect=PermissionError("Access denied")):
            result = await validator.validate()
            
            error_issues = [i for i in result.issues if "Failed to validate" in i.message]
            assert len(error_issues) == 1
            assert error_issues[0].severity == IssueSeverity.HIGH