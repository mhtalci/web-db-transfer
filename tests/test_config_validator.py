"""
Tests for Configuration Validator

Tests the ConfigValidator class functionality including pyproject.toml,
Docker configurations, and CI/CD configuration validation.
"""

import pytest
import tempfile
import tomllib
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.checkup.models import (
    CheckupConfig, ConfigIssue, IssueSeverity, IssueType
)
from migration_assistant.checkup.validators.config import ConfigValidator


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
        validate_configs=True
    )


@pytest.fixture
def config_validator(config):
    """Create a ConfigValidator instance."""
    return ConfigValidator(config)


class TestConfigValidator:
    """Test cases for ConfigValidator."""
    
    def test_get_validation_scope(self, config_validator):
        """Test that validation scope is correctly defined."""
        scope = config_validator.get_validation_scope()
        
        expected_scope = [
            'pyproject_toml_structure',
            'pyproject_toml_dependencies',
            'pyproject_toml_tools',
            'docker_compose_structure',
            'docker_compose_services',
            'dockerfile_best_practices',
            'github_workflow_structure',
            'github_workflow_jobs',
        ]
        
        assert scope == expected_scope
    
    @pytest.mark.asyncio
    async def test_validate_no_config_files(self, temp_dir):
        """Test validation when no configuration files exist."""
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.valid is True
        assert result.files_validated == 0
        assert len(result.issues) == 0
        assert "Validated 0 configuration files" in result.message
    
    @pytest.mark.asyncio
    async def test_validate_valid_pyproject_toml(self, temp_dir):
        """Test validation of a valid pyproject.toml file."""
        pyproject_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
authors = [{name = "Test Author", email = "test@example.com"}]
requires-python = ">=3.11"
dependencies = [
    "click>=8.1.0",
    "fastapi>=0.104.0",
]

[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
"""
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 1
        # Should have minimal or no issues for a well-structured file
        critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_invalid_toml_syntax(self, temp_dir):
        """Test validation of pyproject.toml with invalid TOML syntax."""
        invalid_toml = """
[project
name = "test-project"
version = "1.0.0"
"""
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text(invalid_toml)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 1
        assert len(result.issues) > 0
        
        syntax_issues = [i for i in result.issues if "Invalid TOML syntax" in i.message]
        assert len(syntax_issues) == 1
        assert syntax_issues[0].severity == IssueSeverity.CRITICAL
    
    @pytest.mark.asyncio
    async def test_validate_missing_project_section(self, temp_dir):
        """Test validation when [project] section is missing."""
        pyproject_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.black]
line-length = 88
"""
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        project_issues = [i for i in result.issues if "Missing [project] section" in i.message]
        assert len(project_issues) == 1
        assert project_issues[0].severity == IssueSeverity.HIGH
    
    @pytest.mark.asyncio
    async def test_validate_missing_required_project_fields(self, temp_dir):
        """Test validation when required project fields are missing."""
        pyproject_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
# Missing version and description
"""
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        missing_version = [i for i in result.issues if "Missing required field: version" in i.message]
        missing_description = [i for i in result.issues if "Missing required field: description" in i.message]
        
        assert len(missing_version) == 1
        assert len(missing_description) == 1
        assert missing_version[0].severity == IssueSeverity.MEDIUM
        assert missing_description[0].severity == IssueSeverity.MEDIUM
    
    @pytest.mark.asyncio
    async def test_validate_docker_compose(self, temp_dir):
        """Test validation of docker-compose.yml file."""
        compose_content = """
version: '3.8'

services:
  migration-assistant:
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped
"""
        
        compose_path = temp_dir / "docker-compose.yml"
        compose_path.write_text(compose_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 1
        # Should have minimal issues for a well-structured compose file
        critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_docker_compose_missing_version(self, temp_dir):
        """Test validation when docker-compose version is missing."""
        compose_content = """
services:
  app:
    build: .
    ports:
      - "8000:8000"
"""
        
        compose_path = temp_dir / "docker-compose.yml"
        compose_path.write_text(compose_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        version_issues = [i for i in result.issues if "Missing docker-compose version" in i.message]
        assert len(version_issues) == 1
        assert version_issues[0].severity == IssueSeverity.MEDIUM
    
    @pytest.mark.asyncio
    async def test_validate_docker_compose_no_services(self, temp_dir):
        """Test validation when docker-compose has no services."""
        compose_content = """
version: '3.8'
"""
        
        compose_path = temp_dir / "docker-compose.yml"
        compose_path.write_text(compose_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        service_issues = [i for i in result.issues if "No services defined" in i.message]
        assert len(service_issues) == 1
        assert service_issues[0].severity == IssueSeverity.HIGH
    
    @pytest.mark.asyncio
    async def test_validate_dockerfile(self, temp_dir):
        """Test validation of Dockerfile."""
        dockerfile_content = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

USER 1000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "migration_assistant.api.main"]
"""
        
        dockerfile_path = temp_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 1
        # Should have minimal issues for a well-structured Dockerfile
        critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_dockerfile_missing_from(self, temp_dir):
        """Test validation when Dockerfile is missing FROM instruction."""
        dockerfile_content = """
WORKDIR /app
COPY . .
CMD ["python", "app.py"]
"""
        
        dockerfile_path = temp_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        from_issues = [i for i in result.issues if "Missing FROM instruction" in i.message]
        assert len(from_issues) == 1
        assert from_issues[0].severity == IssueSeverity.CRITICAL
    
    @pytest.mark.asyncio
    async def test_validate_dockerfile_security_issues(self, temp_dir):
        """Test validation of Dockerfile security best practices."""
        dockerfile_content = """
FROM python:3.11-slim

WORKDIR /app
COPY . .

# Missing USER instruction - runs as root
# Missing HEALTHCHECK

CMD ["python", "app.py"]
"""
        
        dockerfile_path = temp_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        user_issues = [i for i in result.issues if "Running as root user" in i.message]
        healthcheck_issues = [i for i in result.issues if "Missing HEALTHCHECK instruction" in i.message]
        
        assert len(user_issues) == 1
        assert len(healthcheck_issues) == 1
        assert user_issues[0].severity == IssueSeverity.MEDIUM
        assert healthcheck_issues[0].severity == IssueSeverity.LOW
    
    @pytest.mark.asyncio
    async def test_validate_github_workflow(self, temp_dir):
        """Test validation of GitHub Actions workflow."""
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        
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
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev,test]"
    
    - name: Run tests
      run: |
        python -m pytest tests/ -v
"""
        
        workflow_path = workflows_dir / "ci.yml"
        workflow_path.write_text(workflow_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 1
        # Should have minimal issues for a well-structured workflow
        critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_github_workflow_missing_fields(self, temp_dir):
        """Test validation when GitHub workflow is missing required fields."""
        workflows_dir = temp_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        
        workflow_content = """
# Missing name, on, and jobs fields
steps:
  - run: echo "hello"
"""
        
        workflow_path = workflows_dir / "invalid.yml"
        workflow_path.write_text(workflow_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        name_issues = [i for i in result.issues if "Missing required field: name" in i.message]
        on_issues = [i for i in result.issues if "Missing required field: on" in i.message]
        jobs_issues = [i for i in result.issues if "Missing required field: jobs" in i.message]
        
        assert len(name_issues) == 1
        assert len(on_issues) == 1
        assert len(jobs_issues) == 1
        
        for issue in [name_issues[0], on_issues[0], jobs_issues[0]]:
            assert issue.severity == IssueSeverity.HIGH
    
    @pytest.mark.asyncio
    async def test_validate_multiple_config_files(self, temp_dir):
        """Test validation of multiple configuration files."""
        # Create pyproject.toml
        pyproject_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
"""
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        
        # Create docker-compose.yml
        compose_content = """
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped
"""
        compose_path = temp_dir / "docker-compose.yml"
        compose_path.write_text(compose_content)
        
        # Create Dockerfile
        dockerfile_content = """
FROM python:3.11-slim
WORKDIR /app
COPY . .
USER 1000
CMD ["python", "app.py"]
"""
        dockerfile_path = temp_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 3
        assert "Validated 3 configuration files" in result.message
    
    def test_should_validate_file_exclusions(self, config_validator, temp_dir):
        """Test that excluded files are not validated."""
        # Test with excluded pattern
        config_validator.config.exclude_patterns = ["*.test.toml"]
        
        test_file = temp_dir / "config.test.toml"
        assert not config_validator.should_validate_file(test_file)
        
        # Test with excluded directory
        config_validator.config.exclude_dirs = ["test_configs"]
        
        test_file = temp_dir / "test_configs" / "config.toml"
        assert not config_validator.should_validate_file(test_file)
    
    @pytest.mark.asyncio
    async def test_validate_tool_configurations(self, temp_dir):
        """Test validation of tool configurations in pyproject.toml."""
        pyproject_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "1.0.0"
description = "A test project"

[tool.black]
line-length = 120  # Unusual line length

[tool.isort]
profile = "django"  # Not compatible with black

[tool.mypy]
python_version = "3.11"
# Missing strict settings

[tool.pytest]
# Missing ini_options
"""
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        # Check for tool configuration issues
        black_issues = [i for i in result.issues if "Unusual black line length" in i.message]
        isort_issues = [i for i in result.issues if "isort profile not compatible" in i.message]
        mypy_issues = [i for i in result.issues if "Missing strict mypy settings" in i.message]
        pytest_issues = [i for i in result.issues if "Missing pytest ini_options" in i.message]
        
        assert len(black_issues) == 1
        assert len(isort_issues) == 1
        assert len(mypy_issues) == 1
        assert len(pytest_issues) == 1
    
    @pytest.mark.asyncio
    async def test_validate_dependencies_unpinned(self, temp_dir):
        """Test validation of unpinned dependencies."""
        pyproject_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
dependencies = [
    "click",  # Unpinned
    "fastapi>=0.104.0",  # Pinned
    "pydantic",  # Unpinned
]
"""
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        unpinned_issues = [i for i in result.issues if "Unpinned dependencies found" in i.message]
        assert len(unpinned_issues) == 1
        assert "click" in unpinned_issues[0].description
        assert "pydantic" in unpinned_issues[0].description
    
    @pytest.mark.asyncio
    async def test_error_handling(self, temp_dir):
        """Test error handling for corrupted files."""
        # Create a file that will cause an error during validation
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_bytes(b'\x00\x01\x02\x03')  # Binary data
        
        config = CheckupConfig(target_directory=temp_dir, validate_configs=True)
        validator = ConfigValidator(config)
        
        result = await validator.validate()
        
        assert result.files_validated == 1
        assert len(result.issues) > 0
        
        # Should have an error issue
        error_issues = [i for i in result.issues if "Failed to validate" in i.message]
        assert len(error_issues) == 1