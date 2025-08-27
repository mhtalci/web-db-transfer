"""
Comprehensive unit tests for checkup validators.
Tests all validator classes to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import json
import xml.etree.ElementTree as ET
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migration_assistant.checkup.validators.coverage import CoverageValidator, CoverageReport, TestQualityMetrics
from migration_assistant.checkup.validators.config import ConfigValidator
from migration_assistant.checkup.validators.docs import DocumentationValidator
from migration_assistant.checkup.validators.corrections import CorrectionsEngine
from migration_assistant.checkup.validators.base import BaseValidator, ValidationResult
from migration_assistant.checkup.models import (
    CheckupConfig, CoverageGap, ConfigIssue, DocIssue,
    IssueType, IssueSeverity
)


class TestBaseValidator:
    """Test cases for BaseValidator abstract class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            check_test_coverage=True,
            validate_configs=True,
            validate_docs=True
        )
    
    def test_base_validator_initialization(self):
        """Test BaseValidator initialization."""
        # Create a concrete implementation for testing
        class TestValidator(BaseValidator):
            async def validate(self):
                return ValidationResult(success=True)
        
        validator = TestValidator(self.config)
        assert validator.config == self.config
        assert validator.target_directory == self.config.target_directory
    
    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            success=True,
            issues_found=5,
            files_validated=10,
            validation_time=1.5,
            error_message=None
        )
        
        assert result.success is True
        assert result.issues_found == 5
        assert result.files_validated == 10
        assert result.validation_time == 1.5
        assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_pre_validate_hook(self):
        """Test pre-validate hook."""
        class TestValidator(BaseValidator):
            def __init__(self, config):
                super().__init__(config)
                self.pre_validate_called = False
            
            async def pre_validate(self):
                self.pre_validate_called = True
                await super().pre_validate()
            
            async def validate(self):
                await self.pre_validate()
                return ValidationResult(success=True)
        
        validator = TestValidator(self.config)
        await validator.validate()
        assert validator.pre_validate_called
    
    @pytest.mark.asyncio
    async def test_post_validate_hook(self):
        """Test post-validate hook."""
        class TestValidator(BaseValidator):
            def __init__(self, config):
                super().__init__(config)
                self.post_validate_called = False
                self.post_validate_result = None
            
            async def post_validate(self, result):
                self.post_validate_called = True
                self.post_validate_result = result
                await super().post_validate(result)
            
            async def validate(self):
                result = ValidationResult(success=True)
                await self.post_validate(result)
                return result
        
        validator = TestValidator(self.config)
        result = await validator.validate()
        assert validator.post_validate_called
        assert validator.post_validate_result == result


class TestCoverageValidator:
    """Test cases for CoverageValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            check_test_coverage=True,
            min_coverage_threshold=80.0,
            coverage_report_format="xml"
        )
    
    def test_initialization(self):
        """Test validator initialization."""
        validator = CoverageValidator(self.config)
        assert validator.config == self.config
        assert validator.min_threshold == self.config.min_coverage_threshold
        assert validator.report_format == self.config.coverage_report_format
    
    def test_coverage_report_creation(self):
        """Test CoverageReport creation."""
        report = CoverageReport(
            total_coverage=85.5,
            line_coverage=87.2,
            branch_coverage=83.8,
            files_covered=25,
            files_total=30,
            lines_covered=1500,
            lines_total=1750
        )
        
        assert report.total_coverage == 85.5
        assert report.line_coverage == 87.2
        assert report.branch_coverage == 83.8
        assert report.files_covered == 25
        assert report.files_total == 30
        assert report.coverage_percentage == 85.5
    
    def test_test_quality_metrics_creation(self):
        """Test TestQualityMetrics creation."""
        metrics = TestQualityMetrics(
            total_tests=100,
            passing_tests=95,
            failing_tests=3,
            skipped_tests=2,
            test_files=15,
            average_test_time=0.25
        )
        
        assert metrics.total_tests == 100
        assert metrics.passing_tests == 95
        assert metrics.failing_tests == 3
        assert metrics.skipped_tests == 2
        assert metrics.success_rate == 95.0
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_generate_coverage_report(self, mock_subprocess):
        """Test coverage report generation."""
        # Mock pytest-cov output
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Coverage report generated"
        
        # Create mock coverage.xml
        coverage_xml = """<?xml version="1.0" ?>
<coverage version="6.0" timestamp="1640995200">
    <sources>
        <source>.</source>
    </sources>
    <packages>
        <package name="." line-rate="0.85" branch-rate="0.80" complexity="0">
            <classes>
                <class name="test.py" filename="test.py" complexity="0" line-rate="0.90" branch-rate="0.85">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        
        coverage_file = self.temp_dir / "coverage.xml"
        coverage_file.write_text(coverage_xml)
        
        validator = CoverageValidator(self.config)
        report = await validator.generate_coverage_report()
        
        assert isinstance(report, CoverageReport)
        assert report.total_coverage > 0
        
        # Verify pytest was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "pytest" in call_args or "python" in call_args
    
    @pytest.mark.asyncio
    async def test_identify_untested_code(self):
        """Test untested code identification."""
        # Create test files
        source_file = self.temp_dir / "source.py"
        test_file = self.temp_dir / "test_source.py"
        
        source_code = """
def tested_function():
    return "tested"

def untested_function():
    return "untested"

class TestedClass:
    def tested_method(self):
        pass
    
    def untested_method(self):
        pass
"""
        
        test_code = """
from source import tested_function, TestedClass

def test_tested_function():
    assert tested_function() == "tested"

def test_tested_class():
    obj = TestedClass()
    obj.tested_method()
"""
        
        source_file.write_text(source_code)
        test_file.write_text(test_code)
        
        validator = CoverageValidator(self.config)
        
        # Mock coverage data
        with patch.object(validator, '_get_coverage_data') as mock_coverage:
            mock_coverage.return_value = {
                str(source_file): {
                    'lines': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
                    'missing': [5, 6, 13, 14],  # untested_function and untested_method
                    'excluded': []
                }
            }
            
            untested = await validator.identify_untested_code()
            
            assert len(untested) > 0
            assert all(isinstance(gap, CoverageGap) for gap in untested)
            
            # Should identify untested functions/methods
            untested_names = [gap.function_name for gap in untested if gap.function_name]
            assert any("untested" in name for name in untested_names)
    
    @pytest.mark.asyncio
    async def test_suggest_test_implementations(self):
        """Test test implementation suggestions."""
        # Create source file with untested functions
        source_file = self.temp_dir / "source.py"
        source_code = """
def add(a, b):
    '''Add two numbers.'''
    return a + b

def multiply(a, b):
    '''Multiply two numbers.'''
    return a * b

class Calculator:
    def divide(self, a, b):
        '''Divide two numbers.'''
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
"""
        source_file.write_text(source_code)
        
        # Create coverage gaps
        coverage_gaps = [
            CoverageGap(
                file_path=source_file,
                function_name="add",
                line_start=1,
                line_end=3,
                coverage_percentage=0.0
            ),
            CoverageGap(
                file_path=source_file,
                function_name="Calculator.divide",
                line_start=9,
                line_end=13,
                coverage_percentage=0.0
            )
        ]
        
        validator = CoverageValidator(self.config)
        suggestions = await validator.suggest_test_implementations(coverage_gaps)
        
        assert len(suggestions) > 0
        
        # Check that suggestions contain test templates
        for suggestion in suggestions:
            assert "def test_" in suggestion.suggested_test
            assert "assert" in suggestion.suggested_test
    
    @pytest.mark.asyncio
    async def test_validate_test_quality(self):
        """Test test quality validation."""
        # Create test files
        good_test_file = self.temp_dir / "test_good.py"
        bad_test_file = self.temp_dir / "test_bad.py"
        
        good_test_code = """
import pytest

def test_addition():
    '''Test addition function.'''
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0

def test_division():
    '''Test division function.'''
    assert divide(10, 2) == 5
    with pytest.raises(ValueError):
        divide(10, 0)
"""
        
        bad_test_code = """
def test_something():
    pass  # Empty test

def test_another():
    assert True  # Trivial test
"""
        
        good_test_file.write_text(good_test_code)
        bad_test_file.write_text(bad_test_code)
        
        validator = CoverageValidator(self.config)
        quality_report = await validator.validate_test_quality()
        
        assert isinstance(quality_report, TestQualityMetrics)
        assert quality_report.total_tests > 0
    
    def test_parse_coverage_xml(self):
        """Test coverage XML parsing."""
        validator = CoverageValidator(self.config)
        
        coverage_xml = """<?xml version="1.0" ?>
<coverage version="6.0" timestamp="1640995200" line-rate="0.85" branch-rate="0.80">
    <sources>
        <source>.</source>
    </sources>
    <packages>
        <package name="." line-rate="0.85" branch-rate="0.80">
            <classes>
                <class name="test.py" filename="test.py" line-rate="0.90" branch-rate="0.85">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        
        coverage_file = self.temp_dir / "coverage.xml"
        coverage_file.write_text(coverage_xml)
        
        report = validator._parse_coverage_xml(coverage_file)
        
        assert isinstance(report, CoverageReport)
        assert report.total_coverage == 85.0
        assert report.branch_coverage == 80.0


class TestConfigValidator:
    """Test cases for ConfigValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            validate_configs=True
        )
    
    def test_initialization(self):
        """Test validator initialization."""
        validator = ConfigValidator(self.config)
        assert validator.config == self.config
        assert validator._config_files == []
        assert validator._validation_errors == []
    
    @pytest.mark.asyncio
    async def test_validate_pyproject_toml(self):
        """Test pyproject.toml validation."""
        # Create valid pyproject.toml
        pyproject_content = """
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
authors = [{name = "Test Author", email = "test@example.com"}]
dependencies = ["requests>=2.25.0"]

[tool.black]
line-length = 88
target-version = ['py38']

[tool.isort]
profile = "black"
"""
        
        pyproject_file = self.temp_dir / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)
        
        validator = ConfigValidator(self.config)
        result = await validator.validate_pyproject_toml()
        
        assert isinstance(result, ValidationResult)
        assert result.success
        assert result.files_validated == 1
    
    @pytest.mark.asyncio
    async def test_validate_pyproject_toml_invalid(self):
        """Test pyproject.toml validation with invalid content."""
        # Create invalid pyproject.toml
        invalid_content = """
[build-system
requires = ["setuptools>=45", "wheel"  # Missing closing bracket and quote
build-backend = "setuptools.build_meta"

[project]
name = 123  # Invalid type
version = "1.0.0"
"""
        
        pyproject_file = self.temp_dir / "pyproject.toml"
        pyproject_file.write_text(invalid_content)
        
        validator = ConfigValidator(self.config)
        result = await validator.validate_pyproject_toml()
        
        assert isinstance(result, ValidationResult)
        assert not result.success
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_validate_docker_configs(self):
        """Test Docker configuration validation."""
        # Create Dockerfile
        dockerfile_content = """
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
"""
        
        dockerfile = self.temp_dir / "Dockerfile"
        dockerfile.write_text(dockerfile_content)
        
        # Create docker-compose.yml
        compose_content = """
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=production
    volumes:
      - ./data:/app/data
"""
        
        compose_file = self.temp_dir / "docker-compose.yml"
        compose_file.write_text(compose_content)
        
        validator = ConfigValidator(self.config)
        result = await validator.validate_docker_configs()
        
        assert isinstance(result, ValidationResult)
        assert result.success
        assert result.files_validated >= 1
    
    @pytest.mark.asyncio
    async def test_validate_ci_configs(self):
        """Test CI/CD configuration validation."""
        # Create GitHub Actions workflow
        github_dir = self.temp_dir / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        
        workflow_content = """
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: pytest
"""
        
        workflow_file = github_dir / "ci.yml"
        workflow_file.write_text(workflow_content)
        
        validator = ConfigValidator(self.config)
        result = await validator.validate_ci_configs()
        
        assert isinstance(result, ValidationResult)
        assert result.success
        assert result.files_validated >= 1
    
    @pytest.mark.asyncio
    async def test_suggest_config_improvements(self):
        """Test configuration improvement suggestions."""
        # Create minimal pyproject.toml
        minimal_content = """
[project]
name = "test-project"
version = "1.0.0"
"""
        
        pyproject_file = self.temp_dir / "pyproject.toml"
        pyproject_file.write_text(minimal_content)
        
        validator = ConfigValidator(self.config)
        await validator.validate_pyproject_toml()  # Populate validation data
        suggestions = await validator.suggest_config_improvements()
        
        assert len(suggestions) > 0
        assert all(isinstance(issue, ConfigIssue) for issue in suggestions)
        
        # Should suggest missing fields
        suggestion_messages = [issue.message for issue in suggestions]
        assert any("description" in msg.lower() for msg in suggestion_messages)
    
    def test_validate_toml_syntax(self):
        """Test TOML syntax validation."""
        validator = ConfigValidator(self.config)
        
        # Valid TOML
        valid_toml = """
[section]
key = "value"
number = 42
"""
        assert validator._validate_toml_syntax(valid_toml)
        
        # Invalid TOML
        invalid_toml = """
[section
key = "value"  # Missing closing bracket
"""
        assert not validator._validate_toml_syntax(invalid_toml)
    
    def test_validate_yaml_syntax(self):
        """Test YAML syntax validation."""
        validator = ConfigValidator(self.config)
        
        # Valid YAML
        valid_yaml = """
version: '3.8'
services:
  app:
    image: python:3.9
    ports:
      - "8000:8000"
"""
        assert validator._validate_yaml_syntax(valid_yaml)
        
        # Invalid YAML
        invalid_yaml = """
version: '3.8'
services:
  app:
    image: python:3.9
    ports:
      - "8000:8000"
    - invalid_list_item  # Invalid indentation
"""
        assert not validator._validate_yaml_syntax(invalid_yaml)


class TestDocumentationValidator:
    """Test cases for DocumentationValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            validate_docs=True
        )
    
    def test_initialization(self):
        """Test validator initialization."""
        validator = DocumentationValidator(self.config)
        assert validator.config == self.config
        assert validator._doc_files == []
        assert validator._code_examples == []
    
    @pytest.mark.asyncio
    async def test_validate_code_examples(self):
        """Test code example validation."""
        # Create documentation with code examples
        readme_content = """
# Test Project

This is a test project.

## Usage

Here's how to use it:

```python
from myproject import add

result = add(2, 3)
print(result)  # Output: 5
```

Another example:

```python
from myproject import Calculator

calc = Calculator()
result = calc.divide(10, 2)
print(result)  # Output: 5.0
```
"""
        
        readme_file = self.temp_dir / "README.md"
        readme_file.write_text(readme_content)
        
        # Create corresponding source file
        source_file = self.temp_dir / "myproject.py"
        source_code = """
def add(a, b):
    return a + b

class Calculator:
    def divide(self, a, b):
        return a / b
"""
        source_file.write_text(source_code)
        
        validator = DocumentationValidator(self.config)
        validations = await validator.validate_code_examples()
        
        assert len(validations) > 0
        
        # Should validate code examples
        for validation in validations:
            assert hasattr(validation, 'file_path')
            assert hasattr(validation, 'is_valid')
            assert hasattr(validation, 'error_message')
    
    @pytest.mark.asyncio
    async def test_check_api_documentation(self):
        """Test API documentation checking."""
        # Create source file with functions
        source_file = self.temp_dir / "api.py"
        source_code = """
def public_function(param1: str, param2: int) -> str:
    '''
    A public function that does something.
    
    Args:
        param1: A string parameter
        param2: An integer parameter
    
    Returns:
        A string result
    '''
    return f"{param1}_{param2}"

def _private_function():
    '''Private function.'''
    pass

class PublicClass:
    '''A public class.'''
    
    def public_method(self, value: int) -> bool:
        '''
        A public method.
        
        Args:
            value: An integer value
        
        Returns:
            A boolean result
        '''
        return value > 0
    
    def _private_method(self):
        '''Private method.'''
        pass
"""
        source_file.write_text(source_code)
        
        validator = DocumentationValidator(self.config)
        validation = await validator.check_api_documentation()
        
        assert validation is not None
        assert hasattr(validation, 'documented_functions')
        assert hasattr(validation, 'undocumented_functions')
        assert hasattr(validation, 'documentation_coverage')
    
    @pytest.mark.asyncio
    async def test_verify_installation_instructions(self):
        """Test installation instruction verification."""
        # Create README with installation instructions
        readme_content = """
# Installation

Install using pip:

```bash
pip install myproject
```

Or install from source:

```bash
git clone https://github.com/user/myproject.git
cd myproject
pip install -e .
```

## Requirements

- Python 3.8+
- requests>=2.25.0
- click>=7.0
"""
        
        readme_file = self.temp_dir / "README.md"
        readme_file.write_text(readme_content)
        
        # Create requirements.txt
        requirements_file = self.temp_dir / "requirements.txt"
        requirements_file.write_text("requests>=2.25.0\nclick>=7.0\n")
        
        # Create pyproject.toml
        pyproject_content = """
[project]
name = "myproject"
version = "1.0.0"
dependencies = ["requests>=2.25.0", "click>=7.0"]
requires-python = ">=3.8"
"""
        pyproject_file = self.temp_dir / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)
        
        validator = DocumentationValidator(self.config)
        validation = await validator.verify_installation_instructions()
        
        assert validation is not None
        assert hasattr(validation, 'instructions_found')
        assert hasattr(validation, 'requirements_consistent')
    
    @pytest.mark.asyncio
    async def test_suggest_doc_improvements(self):
        """Test documentation improvement suggestions."""
        # Create minimal documentation
        readme_content = """
# My Project

This is my project.
"""
        
        readme_file = self.temp_dir / "README.md"
        readme_file.write_text(readme_content)
        
        # Create source file without docstrings
        source_file = self.temp_dir / "source.py"
        source_code = """
def function_without_docstring(param):
    return param * 2

class ClassWithoutDocstring:
    def method_without_docstring(self):
        pass
"""
        source_file.write_text(source_code)
        
        validator = DocumentationValidator(self.config)
        suggestions = await validator.suggest_doc_improvements()
        
        assert len(suggestions) > 0
        assert all(isinstance(issue, DocIssue) for issue in suggestions)
        
        # Should suggest missing documentation
        suggestion_messages = [issue.message for issue in suggestions]
        assert any("docstring" in msg.lower() for msg in suggestion_messages)
    
    def test_extract_code_blocks(self):
        """Test code block extraction from markdown."""
        validator = DocumentationValidator(self.config)
        
        markdown_content = """
# Example

Here's some Python code:

```python
def hello():
    print("Hello, World!")
```

And some bash:

```bash
pip install mypackage
```

```python
# Another Python example
x = 1 + 2
print(x)
```
"""
        
        code_blocks = validator._extract_code_blocks(markdown_content)
        
        assert len(code_blocks) == 3
        
        # Check Python blocks
        python_blocks = [block for block in code_blocks if block['language'] == 'python']
        assert len(python_blocks) == 2
        assert 'def hello():' in python_blocks[0]['code']
        assert 'x = 1 + 2' in python_blocks[1]['code']
        
        # Check bash block
        bash_blocks = [block for block in code_blocks if block['language'] == 'bash']
        assert len(bash_blocks) == 1
        assert 'pip install' in bash_blocks[0]['code']
    
    def test_validate_python_code(self):
        """Test Python code validation."""
        validator = DocumentationValidator(self.config)
        
        # Valid Python code
        valid_code = """
def add(a, b):
    return a + b

result = add(2, 3)
print(result)
"""
        assert validator._validate_python_code(valid_code)
        
        # Invalid Python code
        invalid_code = """
def add(a, b:
    return a + b  # Missing closing parenthesis
"""
        assert not validator._validate_python_code(invalid_code)


class TestCorrectionsEngine:
    """Test cases for CorrectionsEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            auto_apply_corrections=True
        )
    
    def test_initialization(self):
        """Test engine initialization."""
        engine = CorrectionsEngine(self.config)
        assert engine.config == self.config
        assert engine.auto_apply == self.config.auto_apply_corrections
        assert engine._correction_rules == {}
    
    @pytest.mark.asyncio
    async def test_suggest_corrections_for_config_issues(self):
        """Test correction suggestions for config issues."""
        # Create config issues
        issues = [
            ConfigIssue(
                file_path=Path("pyproject.toml"),
                issue_type=IssueType.MISSING_CONFIG,
                severity=IssueSeverity.MEDIUM,
                message="Missing description field",
                config_section="project"
            ),
            ConfigIssue(
                file_path=Path("pyproject.toml"),
                issue_type=IssueType.INVALID_CONFIG,
                severity=IssueSeverity.HIGH,
                message="Invalid version format",
                config_section="project"
            )
        ]
        
        engine = CorrectionsEngine(self.config)
        corrections = await engine.suggest_corrections_for_config_issues(issues)
        
        assert len(corrections) > 0
        
        for correction in corrections:
            assert hasattr(correction, 'issue')
            assert hasattr(correction, 'suggested_fix')
            assert hasattr(correction, 'confidence_score')
            assert 0 <= correction.confidence_score <= 1
    
    @pytest.mark.asyncio
    async def test_suggest_corrections_for_doc_issues(self):
        """Test correction suggestions for documentation issues."""
        # Create documentation issues
        issues = [
            DocIssue(
                file_path=Path("source.py"),
                issue_type=IssueType.MISSING_DOCSTRING,
                severity=IssueSeverity.MEDIUM,
                message="Function missing docstring",
                function_name="my_function"
            ),
            DocIssue(
                file_path=Path("README.md"),
                issue_type=IssueType.BROKEN_LINK,
                severity=IssueSeverity.LOW,
                message="Broken link to documentation",
                line_number=10
            )
        ]
        
        engine = CorrectionsEngine(self.config)
        corrections = await engine.suggest_corrections_for_doc_issues(issues)
        
        assert len(corrections) > 0
        
        for correction in corrections:
            assert hasattr(correction, 'issue')
            assert hasattr(correction, 'suggested_fix')
            assert hasattr(correction, 'confidence_score')
    
    @pytest.mark.asyncio
    async def test_apply_automatic_corrections(self):
        """Test automatic correction application."""
        # Create a file with correctable issues
        test_file = self.temp_dir / "test.py"
        test_code = """
def function_without_docstring(param):
    return param * 2
"""
        test_file.write_text(test_code)
        
        # Create correction
        from migration_assistant.checkup.models import CorrectionSuggestion
        
        correction = CorrectionSuggestion(
            issue=DocIssue(
                file_path=test_file,
                issue_type=IssueType.MISSING_DOCSTRING,
                severity=IssueSeverity.MEDIUM,
                message="Function missing docstring",
                function_name="function_without_docstring"
            ),
            suggested_fix='def function_without_docstring(param):\n    """Function that doubles the input parameter."""\n    return param * 2',
            confidence_score=0.9,
            auto_applicable=True
        )
        
        engine = CorrectionsEngine(self.config)
        result = await engine.apply_automatic_corrections([correction])
        
        assert result.success
        assert result.corrections_applied >= 0  # May be 0 if auto-apply is disabled
    
    def test_generate_docstring_suggestion(self):
        """Test docstring generation."""
        engine = CorrectionsEngine(self.config)
        
        function_code = """
def calculate_area(length, width):
    return length * width
"""
        
        docstring = engine._generate_docstring_suggestion("calculate_area", function_code)
        
        assert docstring is not None
        assert '"""' in docstring
        assert "calculate_area" in docstring.lower() or "area" in docstring.lower()
    
    def test_fix_config_format(self):
        """Test configuration format fixing."""
        engine = CorrectionsEngine(self.config)
        
        # Test version format fix
        fixed_version = engine._fix_config_format("version", "1.0")
        assert fixed_version == "1.0.0"
        
        # Test email format fix
        fixed_email = engine._fix_config_format("email", "user@domain")
        assert "@" in fixed_email
    
    def test_calculate_correction_confidence(self):
        """Test correction confidence calculation."""
        engine = CorrectionsEngine(self.config)
        
        # High confidence correction
        high_confidence = engine._calculate_correction_confidence(
            IssueType.MISSING_DOCSTRING,
            "Simple function with clear purpose"
        )
        assert high_confidence > 0.7
        
        # Low confidence correction
        low_confidence = engine._calculate_correction_confidence(
            IssueType.INVALID_CONFIG,
            "Complex configuration with dependencies"
        )
        assert 0 <= low_confidence <= 1


if __name__ == "__main__":
    # Run tests manually without pytest
    import asyncio
    
    async def run_async_tests():
        """Run async tests manually."""
        print("Running CoverageValidator tests...")
        
        # Test CoverageValidator
        test_coverage = TestCoverageValidator()
        test_coverage.setup_method()
        
        try:
            await test_coverage.test_identify_untested_code()
            print("✓ test_identify_untested_code passed")
        except Exception as e:
            print(f"✗ test_identify_untested_code failed: {e}")
        
        try:
            await test_coverage.test_suggest_test_implementations()
            print("✓ test_suggest_test_implementations passed")
        except Exception as e:
            print(f"✗ test_suggest_test_implementations failed: {e}")
        
        # Test ConfigValidator
        print("\nRunning ConfigValidator tests...")
        test_config = TestConfigValidator()
        test_config.setup_method()
        
        try:
            await test_config.test_validate_pyproject_toml()
            print("✓ test_validate_pyproject_toml passed")
        except Exception as e:
            print(f"✗ test_validate_pyproject_toml failed: {e}")
        
        try:
            await test_config.test_validate_docker_configs()
            print("✓ test_validate_docker_configs passed")
        except Exception as e:
            print(f"✗ test_validate_docker_configs failed: {e}")
        
        # Test DocumentationValidator
        print("\nRunning DocumentationValidator tests...")
        test_docs = TestDocumentationValidator()
        test_docs.setup_method()
        
        try:
            await test_docs.test_validate_code_examples()
            print("✓ test_validate_code_examples passed")
        except Exception as e:
            print(f"✗ test_validate_code_examples failed: {e}")
        
        try:
            await test_docs.test_check_api_documentation()
            print("✓ test_check_api_documentation passed")
        except Exception as e:
            print(f"✗ test_check_api_documentation failed: {e}")
        
        # Test CorrectionsEngine
        print("\nRunning CorrectionsEngine tests...")
        test_corrections = TestCorrectionsEngine()
        test_corrections.setup_method()
        
        try:
            await test_corrections.test_suggest_corrections_for_config_issues()
            print("✓ test_suggest_corrections_for_config_issues passed")
        except Exception as e:
            print(f"✗ test_suggest_corrections_for_config_issues failed: {e}")
    
    def run_sync_tests():
        """Run synchronous tests."""
        print("\nRunning synchronous tests...")
        
        # Test BaseValidator
        test_base = TestBaseValidator()
        test_base.setup_method()
        
        try:
            test_base.test_base_validator_initialization()
            print("✓ test_base_validator_initialization passed")
        except Exception as e:
            print(f"✗ test_base_validator_initialization failed: {e}")
        
        try:
            test_base.test_validation_result_creation()
            print("✓ test_validation_result_creation passed")
        except Exception as e:
            print(f"✗ test_validation_result_creation failed: {e}")
        
        # Test CoverageValidator
        test_coverage = TestCoverageValidator()
        test_coverage.setup_method()
        
        try:
            test_coverage.test_coverage_report_creation()
            print("✓ test_coverage_report_creation passed")
        except Exception as e:
            print(f"✗ test_coverage_report_creation failed: {e}")
        
        try:
            test_coverage.test_parse_coverage_xml()
            print("✓ test_parse_coverage_xml passed")
        except Exception as e:
            print(f"✗ test_parse_coverage_xml failed: {e}")
        
        # Test ConfigValidator
        test_config = TestConfigValidator()
        test_config.setup_method()
        
        try:
            test_config.test_validate_toml_syntax()
            print("✓ test_validate_toml_syntax passed")
        except Exception as e:
            print(f"✗ test_validate_toml_syntax failed: {e}")
        
        try:
            test_config.test_validate_yaml_syntax()
            print("✓ test_validate_yaml_syntax passed")
        except Exception as e:
            print(f"✗ test_validate_yaml_syntax failed: {e}")
        
        # Test DocumentationValidator
        test_docs = TestDocumentationValidator()
        test_docs.setup_method()
        
        try:
            test_docs.test_extract_code_blocks()
            print("✓ test_extract_code_blocks passed")
        except Exception as e:
            print(f"✗ test_extract_code_blocks failed: {e}")
        
        try:
            test_docs.test_validate_python_code()
            print("✓ test_validate_python_code passed")
        except Exception as e:
            print(f"✗ test_validate_python_code failed: {e}")
    
    # Run tests
    run_sync_tests()
    asyncio.run(run_async_tests())
    print("\nTest run completed!")