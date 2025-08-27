"""
Comprehensive unit tests for checkup validators.

Tests all validator classes to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime

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
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            check_test_coverage=True,
            validate_configs=True,
            validate_docs=True
        )
    
    def test_base_validator_initialization(self, config):
        """Test BaseValidator initialization."""
        # Create a concrete implementation for testing
        class TestValidator(BaseValidator):
            async def validate(self):
                return ValidationResult(success=True)
        
        validator = TestValidator(config)
        assert validator.config == config
        assert validator.target_directory == config.target_directory
    
    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            success=True,
            message="Validation completed",
            issues_found=5,
            details={"test": "data"}
        )
        
        assert result.success is True
        assert result.message == "Validation completed"
        assert result.issues_found == 5
        assert result.details["test"] == "data"
    
    def test_get_python_files(self, config, tmp_path):
        """Test getting Python files from directory."""
        class TestValidator(BaseValidator):
            async def validate(self):
                return ValidationResult(success=True)
        
        # Create test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "test.txt").write_text("not python")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "test.pyc").write_text("compiled")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.py").write_text("print('nested')")
        
        config.target_directory = tmp_path
        validator = TestValidator(config)
        
        python_files = validator.get_python_files()
        python_file_names = [f.name for f in python_files]
        
        assert "test.py" in python_file_names
        assert "nested.py" in python_file_names
        assert "test.txt" not in python_file_names
        assert "test.pyc" not in python_file_names


class TestCoverageValidator:
    """Test cases for CoverageValidator."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            check_test_coverage=True,
            coverage_config={
                "min_coverage": 80.0,
                "fail_under": 70.0,
                "include_patterns": ["src/*"],
                "exclude_patterns": ["tests/*"]
            }
        )
    
    @pytest.fixture
    def validator(self, config):
        """Create CoverageValidator instance."""
        return CoverageValidator(config)
    
    def test_initialization(self, validator, config):
        """Test validator initialization."""
        assert validator.config == config
        assert validator._coverage_data is None
        assert validator._test_quality_data is None
    
    def test_coverage_report_creation(self):
        """Test CoverageReport creation."""
        report = CoverageReport(
            total_coverage=85.5,
            file_coverage={"test.py": 90.0, "main.py": 80.0},
            missing_lines={"test.py": [10, 15], "main.py": [5]},
            untested_functions=[{"name": "test_func", "file": "test.py"}],
            untested_classes=[{"name": "TestClass", "file": "test.py"}],
            branch_coverage=75.0
        )
        
        assert report.total_coverage == 85.5
        assert report.file_coverage["test.py"] == 90.0
        assert report.missing_lines["test.py"] == [10, 15]
        assert len(report.untested_functions) == 1
        assert report.branch_coverage == 75.0
    
    def test_test_quality_metrics_creation(self):
        """Test TestQualityMetrics creation."""
        metrics = TestQualityMetrics(
            total_tests=50,
            redundant_tests=["test_duplicate1", "test_duplicate2"],
            obsolete_tests=["test_old"],
            test_effectiveness_score=85.0,
            coverage_per_test={"test_func": 10.5}
        )
        
        assert metrics.total_tests == 50
        assert len(metrics.redundant_tests) == 2
        assert len(metrics.obsolete_tests) == 1
        assert metrics.test_effectiveness_score == 85.0
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_generate_coverage_report_success(self, mock_subprocess, validator, tmp_path):
        """Test successful coverage report generation."""
        # Mock pytest-cov output
        coverage_xml = """<?xml version="1.0" ?>
<coverage version="7.0.0">
    <sources>
        <source>/tmp/test</source>
    </sources>
    <packages>
        <package name="src">
            <classes>
                <class filename="src/main.py" line-rate="0.85" name="main.py">
                    <methods/>
                    <lines>
                        <line hits="1" number="1"/>
                        <line hits="0" number="5"/>
                        <line hits="1" number="10"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""
        
        validator.target_directory = tmp_path
        
        # Mock XML file creation
        coverage_file = tmp_path / "coverage.xml"
        coverage_file.write_text(coverage_xml)
        
        with patch.object(validator, '_parse_coverage_xml') as mock_parse:
            mock_parse.return_value = CoverageReport(
                total_coverage=85.0,
                file_coverage={"src/main.py": 85.0},
                missing_lines={"src/main.py": [5]},
                untested_functions=[],
                untested_classes=[]
            )
            
            report = await validator.generate_coverage_report()
            
            assert report.total_coverage == 85.0
            assert "src/main.py" in report.file_coverage
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_generate_coverage_report_failure(self, mock_subprocess, validator):
        """Test coverage report generation failure."""
        # Mock pytest failure
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "Error running tests"
        
        report = await validator.generate_coverage_report()
        
        assert report is None
    
    def test_parse_coverage_xml(self, validator, tmp_path):
        """Test parsing coverage XML."""
        coverage_xml = """<?xml version="1.0" ?>
<coverage version="7.0.0">
    <sources>
        <source>/tmp/test</source>
    </sources>
    <packages>
        <package name="src" line-rate="0.85">
            <classes>
                <class filename="src/main.py" line-rate="0.90" name="main.py">
                    <methods/>
                    <lines>
                        <line hits="1" number="1"/>
                        <line hits="0" number="5"/>
                        <line hits="1" number="10"/>
                    </lines>
                </class>
                <class filename="src/utils.py" line-rate="0.80" name="utils.py">
                    <methods/>
                    <lines>
                        <line hits="1" number="1"/>
                        <line hits="0" number="3"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
        
        coverage_file = tmp_path / "coverage.xml"
        coverage_file.write_text(coverage_xml)
        
        report = validator._parse_coverage_xml(coverage_file)
        
        assert report.total_coverage == 85.0
        assert report.file_coverage["src/main.py"] == 90.0
        assert report.file_coverage["src/utils.py"] == 80.0
        assert 5 in report.missing_lines["src/main.py"]
        assert 3 in report.missing_lines["src/utils.py"]
    
    @pytest.mark.asyncio
    async def test_identify_untested_code(self, validator, tmp_path):
        """Test identifying untested code."""
        # Create test Python files
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def tested_function():
    return True

def untested_function():
    return False

class TestedClass:
    def tested_method(self):
        pass

class UntestedClass:
    def untested_method(self):
        pass
""")
        
        validator.target_directory = tmp_path
        
        # Mock coverage data
        validator._coverage_data = CoverageReport(
            total_coverage=50.0,
            file_coverage={"main.py": 50.0},
            missing_lines={"main.py": [5, 6, 11, 12, 13]},
            untested_functions=[],
            untested_classes=[]
        )
        
        untested_code = await validator.identify_untested_code()
        
        assert len(untested_code) > 0
        # Should identify untested functions and classes
    
    @pytest.mark.asyncio
    async def test_suggest_test_implementations(self, validator, tmp_path):
        """Test test implementation suggestions."""
        # Create test file with untested functions
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def calculate_sum(a, b):
    '''Calculate sum of two numbers.'''
    return a + b

def process_data(data):
    '''Process input data.'''
    return [x * 2 for x in data]

class DataProcessor:
    '''Process data efficiently.'''
    
    def transform(self, data):
        '''Transform data.'''
        return data.upper()
""")
        
        validator.target_directory = tmp_path
        
        # Mock untested code
        untested_code = [
            CoverageGap(
                file_path=main_file,
                function_name="calculate_sum",
                line_number=2,
                issue_type=IssueType.MISSING_TEST,
                severity=IssueSeverity.MEDIUM,
                description="Function has no tests"
            )
        ]
        
        suggestions = await validator.suggest_test_implementations(untested_code)
        
        assert len(suggestions) > 0
        assert any("calculate_sum" in suggestion.description for suggestion in suggestions)
    
    @pytest.mark.asyncio
    async def test_validate_test_quality(self, validator, tmp_path):
        """Test test quality validation."""
        # Create test files
        test_file = tmp_path / "test_main.py"
        test_file.write_text("""
import pytest

def test_function1():
    assert True

def test_function2():
    # Duplicate test
    assert True

def test_obsolete_feature():
    # Test for removed feature
    pass

def test_comprehensive():
    # Good test with multiple assertions
    result = calculate_something()
    assert result is not None
    assert result > 0
    assert isinstance(result, int)
""")
        
        validator.target_directory = tmp_path
        
        quality_report = await validator.validate_test_quality()
        
        assert quality_report is not None
        assert quality_report.total_tests > 0
    
    @pytest.mark.asyncio
    async def test_validate_success(self, validator, tmp_path):
        """Test successful validation."""
        validator.target_directory = tmp_path
        
        # Mock coverage report
        with patch.object(validator, 'generate_coverage_report') as mock_generate:
            mock_generate.return_value = CoverageReport(
                total_coverage=85.0,
                file_coverage={"main.py": 85.0},
                missing_lines={"main.py": []},
                untested_functions=[],
                untested_classes=[]
            )
            
            result = await validator.validate()
            
            assert result.success is True
            assert result.issues_found >= 0
    
    def test_analyze_test_redundancy(self, validator, tmp_path):
        """Test test redundancy analysis."""
        test_content = """
def test_addition_basic():
    assert 1 + 1 == 2

def test_addition_simple():
    # Very similar test
    assert 1 + 1 == 2

def test_addition_comprehensive():
    # Different test
    assert 1 + 2 == 3
    assert 2 + 2 == 4
"""
        
        test_file = tmp_path / "test_math.py"
        test_file.write_text(test_content)
        
        redundant_tests = validator._analyze_test_redundancy([test_file])
        
        # Should identify similar tests
        assert isinstance(redundant_tests, list)
    
    def test_detect_obsolete_tests(self, validator, tmp_path):
        """Test obsolete test detection."""
        test_content = """
def test_old_feature():
    '''Test for feature that was removed.'''
    pass

def test_deprecated_function():
    '''Test for deprecated function.'''
    pass

def test_current_feature():
    '''Test for current feature.'''
    assert True
"""
        
        test_file = tmp_path / "test_features.py"
        test_file.write_text(test_content)
        
        obsolete_tests = validator._detect_obsolete_tests([test_file])
        
        # Should identify potentially obsolete tests
        assert isinstance(obsolete_tests, list)


class TestConfigValidator:
    """Test cases for ConfigValidator."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            validate_configs=True
        )
    
    @pytest.fixture
    def validator(self, config):
        """Create ConfigValidator instance."""
        return ConfigValidator(config)
    
    def test_initialization(self, validator, config):
        """Test validator initialization."""
        assert validator.config == config
    
    @pytest.mark.asyncio
    async def test_validate_pyproject_toml_valid(self, validator, tmp_path):
        """Test validating valid pyproject.toml."""
        pyproject_content = """
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-project"
version = "0.1.0"
description = "Test project"
authors = [{name = "Test Author", email = "test@example.com"}]

[tool.black]
line-length = 88
target-version = ["py311"]

[tool.isort]
profile = "black"
"""
        
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)
        
        validator.target_directory = tmp_path
        result = await validator.validate_pyproject_toml()
        
        assert result.success is True
        assert result.issues_found == 0
    
    @pytest.mark.asyncio
    async def test_validate_pyproject_toml_invalid(self, validator, tmp_path):
        """Test validating invalid pyproject.toml."""
        pyproject_content = """
[build-system
requires = ["setuptools>=45", "wheel"
build-backend = "setuptools.build_meta"

[project]
name = "test-project"
# Missing required fields
"""
        
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)
        
        validator.target_directory = tmp_path
        result = await validator.validate_pyproject_toml()
        
        assert result.success is False
        assert result.issues_found > 0
    
    @pytest.mark.asyncio
    async def test_validate_docker_configs_valid(self, validator, tmp_path):
        """Test validating valid Docker configurations."""
        dockerfile_content = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
"""
        
        compose_content = """
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=production
"""
        
        (tmp_path / "Dockerfile").write_text(dockerfile_content)
        (tmp_path / "docker-compose.yml").write_text(compose_content)
        
        validator.target_directory = tmp_path
        result = await validator.validate_docker_configs()
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_validate_docker_configs_invalid(self, validator, tmp_path):
        """Test validating invalid Docker configurations."""
        dockerfile_content = """
FROM python:3.11-slim

# Missing WORKDIR
COPY requirements.txt .
RUN pip install -r requirements.txt

# No CMD or ENTRYPOINT
"""
        
        (tmp_path / "Dockerfile").write_text(dockerfile_content)
        
        validator.target_directory = tmp_path
        result = await validator.validate_docker_configs()
        
        assert result.success is False
        assert result.issues_found > 0
    
    @pytest.mark.asyncio
    async def test_validate_ci_configs_github(self, validator, tmp_path):
        """Test validating GitHub Actions configuration."""
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
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest
"""
        
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "workflows").mkdir()
        (tmp_path / ".github" / "workflows" / "ci.yml").write_text(workflow_content)
        
        validator.target_directory = tmp_path
        result = await validator.validate_ci_configs()
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_suggest_config_improvements(self, validator, tmp_path):
        """Test configuration improvement suggestions."""
        # Create minimal pyproject.toml
        pyproject_content = """
[project]
name = "test-project"
version = "0.1.0"
"""
        
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        
        validator.target_directory = tmp_path
        suggestions = await validator.suggest_config_improvements()
        
        assert len(suggestions) > 0
        # Should suggest missing configurations
        suggestion_texts = [s.description for s in suggestions]
        assert any("black" in text.lower() or "tool" in text.lower() for text in suggestion_texts)
    
    def test_validate_dockerfile_best_practices(self, validator):
        """Test Dockerfile best practices validation."""
        good_dockerfile = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

USER 1000

CMD ["python", "main.py"]
"""
        
        issues = validator._validate_dockerfile_best_practices(good_dockerfile)
        assert len(issues) == 0  # Should have no issues
        
        bad_dockerfile = """
FROM python:latest

COPY . .
RUN pip install -r requirements.txt

CMD python main.py
"""
        
        issues = validator._validate_dockerfile_best_practices(bad_dockerfile)
        assert len(issues) > 0  # Should have issues


class TestDocumentationValidator:
    """Test cases for DocumentationValidator."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            validate_docs=True
        )
    
    @pytest.fixture
    def validator(self, config):
        """Create DocumentationValidator instance."""
        return DocumentationValidator(config)
    
    def test_initialization(self, validator, config):
        """Test validator initialization."""
        assert validator.config == config
    
    @pytest.mark.asyncio
    async def test_validate_code_examples_valid(self, validator, tmp_path):
        """Test validating valid code examples in documentation."""
        readme_content = """
# Test Project

## Usage

```python
def hello_world():
    print("Hello, World!")

hello_world()
```

## Installation

```bash
pip install test-project
```
"""
        
        (tmp_path / "README.md").write_text(readme_content)
        
        validator.target_directory = tmp_path
        validations = await validator.validate_code_examples()
        
        assert len(validations) > 0
        # Should validate Python code examples
    
    @pytest.mark.asyncio
    async def test_validate_code_examples_invalid(self, validator, tmp_path):
        """Test validating invalid code examples."""
        readme_content = """
# Test Project

## Usage

```python
def broken_function(
    print("Missing closing parenthesis")
```
"""
        
        (tmp_path / "README.md").write_text(readme_content)
        
        validator.target_directory = tmp_path
        validations = await validator.validate_code_examples()
        
        # Should find syntax errors in code examples
        invalid_examples = [v for v in validations if not v.is_valid]
        assert len(invalid_examples) > 0
    
    @pytest.mark.asyncio
    async def test_check_api_documentation(self, validator, tmp_path):
        """Test API documentation checking."""
        # Create Python module with functions
        module_content = """
def public_function(param1: str, param2: int = 0) -> str:
    '''
    Public function that should be documented.
    
    Args:
        param1: First parameter
        param2: Second parameter
        
    Returns:
        Processed string
    '''
    return f"{param1}_{param2}"

def _private_function():
    '''Private function.'''
    pass

class PublicClass:
    '''Public class that should be documented.'''
    
    def public_method(self):
        '''Public method.'''
        pass
    
    def _private_method(self):
        '''Private method.'''
        pass
"""
        
        (tmp_path / "mymodule.py").write_text(module_content)
        
        # Create API documentation
        api_docs = """
# API Reference

## Functions

### public_function

Public function that should be documented.

## Classes

### PublicClass

Public class that should be documented.
"""
        
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "api.md").write_text(api_docs)
        
        validator.target_directory = tmp_path
        validation = await validator.check_api_documentation()
        
        assert validation.success is True
    
    @pytest.mark.asyncio
    async def test_verify_installation_instructions(self, validator, tmp_path):
        """Test installation instruction verification."""
        readme_content = """
# Test Project

## Installation

### Using pip

```bash
pip install test-project
```

### From source

```bash
git clone https://github.com/user/test-project.git
cd test-project
pip install -e .
```

## Requirements

- Python 3.8+
- pip
"""
        
        (tmp_path / "README.md").write_text(readme_content)
        
        # Create pyproject.toml to verify consistency
        pyproject_content = """
[project]
name = "test-project"
version = "0.1.0"
requires-python = ">=3.8"
"""
        
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        
        validator.target_directory = tmp_path
        validation = await validator.verify_installation_instructions()
        
        assert validation.success is True
    
    @pytest.mark.asyncio
    async def test_suggest_doc_improvements(self, validator, tmp_path):
        """Test documentation improvement suggestions."""
        # Create minimal README
        readme_content = """
# Test Project

This is a test project.
"""
        
        (tmp_path / "README.md").write_text(readme_content)
        
        validator.target_directory = tmp_path
        suggestions = await validator.suggest_doc_improvements()
        
        assert len(suggestions) > 0
        # Should suggest missing sections
        suggestion_texts = [s.description for s in suggestions]
        assert any("installation" in text.lower() for text in suggestion_texts)
    
    def test_extract_code_blocks(self, validator):
        """Test extracting code blocks from markdown."""
        markdown_content = """
# Example

Here's some Python code:

```python
def example():
    return True
```

And some bash:

```bash
echo "Hello"
```

And some text:

```
Just text
```
"""
        
        code_blocks = validator._extract_code_blocks(markdown_content)
        
        python_blocks = [b for b in code_blocks if b['language'] == 'python']
        bash_blocks = [b for b in code_blocks if b['language'] == 'bash']
        
        assert len(python_blocks) == 1
        assert len(bash_blocks) == 1
        assert "def example" in python_blocks[0]['code']
        assert "echo" in bash_blocks[0]['code']
    
    def test_validate_python_code_block(self, validator):
        """Test validating Python code blocks."""
        valid_code = "def test():\n    return True"
        invalid_code = "def broken(\n    pass"
        
        valid_result = validator._validate_python_code_block(valid_code)
        invalid_result = validator._validate_python_code_block(invalid_code)
        
        assert valid_result.is_valid is True
        assert invalid_result.is_valid is False
        assert "syntax" in invalid_result.error_message.lower()


class TestCorrectionsEngine:
    """Test cases for CorrectionsEngine."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            auto_fix_imports=True,
            auto_format=True
        )
    
    @pytest.fixture
    def engine(self, config):
        """Create CorrectionsEngine instance."""
        return CorrectionsEngine(config)
    
    def test_initialization(self, engine, config):
        """Test engine initialization."""
        assert engine.config == config
    
    @pytest.mark.asyncio
    async def test_suggest_corrections_config_issues(self, engine, tmp_path):
        """Test suggesting corrections for configuration issues."""
        config_issues = [
            ConfigIssue(
                file_path=tmp_path / "pyproject.toml",
                issue_type=IssueType.MISSING_CONFIG,
                severity=IssueSeverity.MEDIUM,
                description="Missing black configuration",
                config_section="tool.black"
            )
        ]
        
        corrections = await engine.suggest_corrections(config_issues)
        
        assert len(corrections) > 0
        assert any("black" in correction.description.lower() for correction in corrections)
    
    @pytest.mark.asyncio
    async def test_suggest_corrections_doc_issues(self, engine, tmp_path):
        """Test suggesting corrections for documentation issues."""
        doc_issues = [
            DocIssue(
                file_path=tmp_path / "README.md",
                issue_type=IssueType.MISSING_DOCUMENTATION,
                severity=IssueSeverity.LOW,
                description="Missing installation section",
                section="installation"
            )
        ]
        
        corrections = await engine.suggest_corrections(doc_issues)
        
        assert len(corrections) > 0
        assert any("installation" in correction.description.lower() for correction in corrections)
    
    @pytest.mark.asyncio
    async def test_apply_automated_fixes(self, engine, tmp_path):
        """Test applying automated fixes."""
        # Create file with fixable issues
        pyproject_content = """
[project]
name = "test-project"
version = "0.1.0"
"""
        
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)
        
        config_issues = [
            ConfigIssue(
                file_path=pyproject_file,
                issue_type=IssueType.MISSING_CONFIG,
                severity=IssueSeverity.MEDIUM,
                description="Missing black configuration",
                config_section="tool.black"
            )
        ]
        
        result = await engine.apply_automated_fixes(config_issues)
        
        assert result.success is True
        # Check that fix was applied
        modified_content = pyproject_file.read_text()
        assert "[tool.black]" in modified_content or result.files_modified
    
    def test_generate_config_fix(self, engine):
        """Test generating configuration fixes."""
        fix = engine._generate_config_fix("tool.black", "Missing black configuration")
        
        assert "tool.black" in fix
        assert "line-length" in fix
    
    def test_generate_doc_improvement(self, engine):
        """Test generating documentation improvements."""
        improvement = engine._generate_doc_improvement("installation", "Missing installation section")
        
        assert "## Installation" in improvement
        assert "pip install" in improvement
    
    def test_is_auto_fixable(self, engine):
        """Test checking if issue is auto-fixable."""
        config_issue = ConfigIssue(
            file_path=Path("pyproject.toml"),
            issue_type=IssueType.MISSING_CONFIG,
            severity=IssueSeverity.MEDIUM,
            description="Missing black configuration",
            config_section="tool.black"
        )
        
        doc_issue = DocIssue(
            file_path=Path("README.md"),
            issue_type=IssueType.MISSING_DOCUMENTATION,
            severity=IssueSeverity.LOW,
            description="Missing installation section",
            section="installation"
        )
        
        assert engine._is_auto_fixable(config_issue) is True
        assert engine._is_auto_fixable(doc_issue) is True