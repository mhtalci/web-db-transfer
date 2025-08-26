"""
Tests for Correction Recommendation Engine

Tests the CorrectionEngine class functionality including correction generation
and automated fix capabilities for configuration and documentation issues.
"""

import pytest
import tempfile
import tomllib
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.checkup.models import (
    CheckupConfig, ConfigIssue, DocIssue, IssueSeverity, IssueType
)
from migration_assistant.checkup.validators.corrections import (
    CorrectionEngine, CorrectionSuggestion, AutoFixResult
)


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
        validate_configs=True,
        validate_docs=True
    )


@pytest.fixture
def correction_engine(config):
    """Create a CorrectionEngine instance."""
    return CorrectionEngine(config)


class TestCorrectionEngine:
    """Test cases for CorrectionEngine."""
    
    def test_initialization(self, correction_engine):
        """Test that CorrectionEngine initializes correctly."""
        assert correction_engine.config is not None
        assert correction_engine.target_directory is not None
        assert 'pyproject_project_section' in correction_engine.config_templates
        assert 'healthcheck' in correction_engine.docker_templates
    
    def test_generate_pyproject_missing_section_correction(self, temp_dir, correction_engine):
        """Test correction generation for missing pyproject.toml sections."""
        pyproject_path = temp_dir / "pyproject.toml"
        
        issue = ConfigIssue(
            file_path=pyproject_path,
            line_number=None,
            severity=IssueSeverity.HIGH,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Missing [project] section",
            description="pyproject.toml should contain a [project] section",
            config_file=pyproject_path
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'missing_project_section'
        assert correction.auto_fixable is True
        assert correction.confidence >= 0.8
        assert '[project]' in correction.suggested_content
        assert 'name' in correction.suggested_content
    
    def test_generate_pyproject_missing_field_correction(self, temp_dir, correction_engine):
        """Test correction generation for missing pyproject.toml fields."""
        pyproject_path = temp_dir / "pyproject.toml"
        
        issue = ConfigIssue(
            file_path=pyproject_path,
            line_number=None,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Missing required field: version",
            description="The [project] section should contain a 'version' field",
            config_file=pyproject_path,
            config_section="project"
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'missing_project_field'
        assert correction.auto_fixable is True
        assert 'version' in correction.suggested_content
    
    def test_generate_black_line_length_correction(self, temp_dir, correction_engine):
        """Test correction generation for black line length issues."""
        pyproject_path = temp_dir / "pyproject.toml"
        
        issue = ConfigIssue(
            file_path=pyproject_path,
            line_number=None,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Unusual black line length",
            description="Black line length of 120 is outside typical range",
            config_file=pyproject_path,
            config_section="tool.black",
            actual_value="120",
            expected_value="88"
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'black_line_length'
        assert correction.auto_fixable is True
        assert 'line-length = 88' in correction.suggested_content
    
    def test_generate_isort_profile_correction(self, temp_dir, correction_engine):
        """Test correction generation for isort profile issues."""
        pyproject_path = temp_dir / "pyproject.toml"
        
        issue = ConfigIssue(
            file_path=pyproject_path,
            line_number=None,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.CONFIG_ISSUE,
            message="isort profile not compatible with black",
            description="isort profile should be 'black' for compatibility",
            config_file=pyproject_path,
            config_section="tool.isort",
            actual_value="django",
            expected_value="black"
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'isort_profile'
        assert correction.auto_fixable is True
        assert 'profile = "black"' in correction.suggested_content
    
    def test_generate_docker_compose_version_correction(self, temp_dir, correction_engine):
        """Test correction generation for docker-compose version issues."""
        compose_path = temp_dir / "docker-compose.yml"
        
        issue = ConfigIssue(
            file_path=compose_path,
            line_number=None,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Missing docker-compose version",
            description="docker-compose.yml should specify a version",
            config_file=compose_path
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'docker_compose_version'
        assert correction.auto_fixable is True
        assert "version: '3.8'" in correction.suggested_content
    
    def test_generate_dockerfile_from_correction(self, temp_dir, correction_engine):
        """Test correction generation for Dockerfile FROM issues."""
        dockerfile_path = temp_dir / "Dockerfile"
        
        issue = ConfigIssue(
            file_path=dockerfile_path,
            line_number=None,
            severity=IssueSeverity.CRITICAL,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Missing FROM instruction",
            description="Dockerfile must start with a FROM instruction",
            config_file=dockerfile_path
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'dockerfile_from'
        assert correction.auto_fixable is True
        assert 'FROM python:3.11-slim' in correction.suggested_content
    
    def test_generate_dockerfile_user_correction(self, temp_dir, correction_engine):
        """Test correction generation for Dockerfile USER issues."""
        dockerfile_path = temp_dir / "Dockerfile"
        
        issue = ConfigIssue(
            file_path=dockerfile_path,
            line_number=None,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Running as root user",
            description="Dockerfile should specify a non-root user for security",
            config_file=dockerfile_path
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'dockerfile_user'
        assert correction.auto_fixable is False  # Requires manual placement
        assert 'USER 1000' in correction.suggested_content
    
    def test_generate_dockerignore_correction(self, temp_dir, correction_engine):
        """Test correction generation for missing .dockerignore."""
        dockerfile_path = temp_dir / "Dockerfile"
        
        issue = ConfigIssue(
            file_path=dockerfile_path,
            line_number=None,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Missing .dockerignore file",
            description="Consider creating .dockerignore to exclude unnecessary files",
            config_file=dockerfile_path
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'dockerignore_file'
        assert correction.auto_fixable is True
        assert correction.file_path.name == '.dockerignore'
        assert '__pycache__' in correction.suggested_content
    
    def test_generate_workflow_corrections(self, temp_dir, correction_engine):
        """Test correction generation for GitHub workflow issues."""
        workflow_path = temp_dir / ".github" / "workflows" / "ci.yml"
        workflow_path.parent.mkdir(parents=True)
        
        issue = ConfigIssue(
            file_path=workflow_path,
            line_number=None,
            severity=IssueSeverity.HIGH,
            issue_type=IssueType.CONFIG_ISSUE,
            message="Missing required field: name",
            description="GitHub workflow must contain 'name' field",
            config_file=workflow_path
        )
        
        corrections = correction_engine.generate_config_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'workflow_name'
        assert correction.auto_fixable is True
        assert 'name: CI' in correction.suggested_content
    
    def test_generate_doc_code_example_corrections(self, temp_dir, correction_engine):
        """Test correction generation for documentation code example issues."""
        readme_path = temp_dir / "README.md"
        
        issue = DocIssue(
            file_path=readme_path,
            line_number=10,
            severity=IssueSeverity.HIGH,
            issue_type=IssueType.DOC_ISSUE,
            message="Python syntax error in code example",
            description="Code block contains syntax error",
            doc_type="code_example"
        )
        
        corrections = correction_engine.generate_doc_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'code_syntax_error'
        assert correction.auto_fixable is False  # Requires manual review
        assert 'Fix syntax error' in correction.suggested_content
    
    def test_generate_doc_unavailable_import_corrections(self, temp_dir, correction_engine):
        """Test correction generation for unavailable import issues."""
        readme_path = temp_dir / "README.md"
        
        issue = DocIssue(
            file_path=readme_path,
            line_number=15,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.DOC_ISSUE,
            message="Unavailable import in code example: nonexistent_module",
            description="Code example imports 'nonexistent_module' which may not be available",
            doc_type="code_example"
        )
        
        corrections = correction_engine.generate_doc_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'unavailable_import'
        assert correction.auto_fixable is False
        assert 'nonexistent_module' in correction.suggested_content
    
    def test_generate_doc_installation_corrections(self, temp_dir, correction_engine):
        """Test correction generation for missing installation instructions."""
        readme_path = temp_dir / "README.md"
        
        issue = DocIssue(
            file_path=readme_path,
            line_number=None,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.DOC_ISSUE,
            message="Missing installation instructions",
            description="README file should include installation instructions",
            doc_type="installation"
        )
        
        corrections = correction_engine.generate_doc_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'missing_installation'
        assert correction.auto_fixable is False  # Requires manual placement
        assert '## Installation' in correction.suggested_content
        assert 'pip install' in correction.suggested_content
    
    def test_generate_doc_broken_link_corrections(self, temp_dir, correction_engine):
        """Test correction generation for broken link issues."""
        readme_path = temp_dir / "README.md"
        
        issue = DocIssue(
            file_path=readme_path,
            line_number=20,
            severity=IssueSeverity.MEDIUM,
            issue_type=IssueType.DOC_ISSUE,
            message="Broken local link: docs/nonexistent.md",
            description="Local file link 'docs/nonexistent.md' points to non-existent file",
            doc_type="link",
            broken_link="docs/nonexistent.md"
        )
        
        corrections = correction_engine.generate_doc_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'broken_link'
        assert correction.auto_fixable is False
        assert 'docs/nonexistent.md' in correction.suggested_content
    
    def test_generate_doc_version_corrections(self, temp_dir, correction_engine):
        """Test correction generation for outdated version references."""
        readme_path = temp_dir / "README.md"
        
        issue = DocIssue(
            file_path=readme_path,
            line_number=5,
            severity=IssueSeverity.LOW,
            issue_type=IssueType.DOC_ISSUE,
            message="Outdated Python version reference: Python 3.8",
            description="Documentation references Python 3.8 which may be outdated",
            doc_type="version_reference",
            outdated_example=True
        )
        
        corrections = correction_engine.generate_doc_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.issue_type == 'outdated_python_version'
        assert correction.auto_fixable is False
        assert 'Python >=3.11' in correction.suggested_content
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_toml_section(self, temp_dir):
        """Test applying automated fixes for TOML sections."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text("")  # Empty file
        
        correction = CorrectionSuggestion(
            issue_type='missing_project_section',
            file_path=pyproject_path,
            line_number=None,
            original_content=None,
            suggested_content="[project]\nname = 'test'",
            description="Add [project] section",
            confidence=0.9,
            auto_fixable=True
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        assert len(results) == 1
        result = results[0]
        assert result.success is True
        assert result.file_path == pyproject_path
        assert len(result.changes_made) == 1
        
        # Verify the file was modified
        with open(pyproject_path, 'rb') as f:
            data = tomllib.load(f)
        assert 'project' in data
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_toml_field(self, temp_dir):
        """Test applying automated fixes for TOML fields."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        pyproject_path = temp_dir / "pyproject.toml"
        pyproject_path.write_text("""
[tool.black]
line-length = 120
""")
        
        correction = CorrectionSuggestion(
            issue_type='black_line_length',
            file_path=pyproject_path,
            line_number=None,
            original_content='line-length = 120',
            suggested_content='line-length = 88',
            description="Fix black line length",
            confidence=0.9,
            auto_fixable=True
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        assert len(results) == 1
        result = results[0]
        assert result.success is True
        
        # Verify the file was modified
        with open(pyproject_path, 'rb') as f:
            data = tomllib.load(f)
        assert data['tool']['black']['line-length'] == 88
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_yaml_field(self, temp_dir):
        """Test applying automated fixes for YAML fields."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        compose_path = temp_dir / "docker-compose.yml"
        compose_path.write_text("""
services:
  app:
    build: .
""")
        
        correction = CorrectionSuggestion(
            issue_type='docker_compose_version',
            file_path=compose_path,
            line_number=1,
            original_content=None,
            suggested_content="version: '3.8'",
            description="Add version field",
            confidence=0.9,
            auto_fixable=True
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        assert len(results) == 1
        result = results[0]
        assert result.success is True
        
        # Verify the file was modified
        with open(compose_path, 'r') as f:
            data = yaml.safe_load(f)
        assert data['version'] == '3.8'
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_dockerfile(self, temp_dir):
        """Test applying automated fixes for Dockerfile."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        dockerfile_path = temp_dir / "Dockerfile"
        dockerfile_path.write_text("WORKDIR /app\nCOPY . .")
        
        correction = CorrectionSuggestion(
            issue_type='dockerfile_from',
            file_path=dockerfile_path,
            line_number=1,
            original_content=None,
            suggested_content="FROM python:3.11-slim",
            description="Add FROM instruction",
            confidence=0.9,
            auto_fixable=True
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        assert len(results) == 1
        result = results[0]
        assert result.success is True
        
        # Verify the file was modified
        content = dockerfile_path.read_text()
        assert content.startswith("FROM python:3.11-slim")
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_create_file(self, temp_dir):
        """Test applying automated fixes that create new files."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        dockerignore_path = temp_dir / ".dockerignore"
        
        correction = CorrectionSuggestion(
            issue_type='dockerignore_file',
            file_path=dockerignore_path,
            line_number=None,
            original_content=None,
            suggested_content="__pycache__/\n*.pyc\n.git/",
            description="Create .dockerignore file",
            confidence=0.9,
            auto_fixable=True
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        assert len(results) == 1
        result = results[0]
        assert result.success is True
        
        # Verify the file was created
        assert dockerignore_path.exists()
        content = dockerignore_path.read_text()
        assert '__pycache__' in content
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_non_fixable(self, temp_dir):
        """Test that non-auto-fixable corrections are skipped."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        correction = CorrectionSuggestion(
            issue_type='manual_fix_required',
            file_path=temp_dir / "test.md",
            line_number=10,
            original_content=None,
            suggested_content="Manual fix required",
            description="This requires manual intervention",
            confidence=0.5,
            auto_fixable=False
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        # Should return empty list since correction is not auto-fixable
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_with_backup(self, temp_dir):
        """Test that backups are created when applying fixes."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        pyproject_path = temp_dir / "pyproject.toml"
        original_content = "[tool.black]\nline-length = 120"
        pyproject_path.write_text(original_content)
        
        correction = CorrectionSuggestion(
            issue_type='black_line_length',
            file_path=pyproject_path,
            line_number=None,
            original_content='line-length = 120',
            suggested_content='line-length = 88',
            description="Fix black line length",
            confidence=0.9,
            auto_fixable=True,
            backup_required=True
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        assert len(results) == 1
        result = results[0]
        assert result.success is True
        assert result.backup_path is not None
        assert result.backup_path.exists()
        
        # Verify backup contains original content
        backup_content = result.backup_path.read_text()
        assert "line-length = 120" in backup_content
    
    @pytest.mark.asyncio
    async def test_apply_auto_fixes_error_handling(self, temp_dir):
        """Test error handling during auto-fix application."""
        config = CheckupConfig(target_directory=temp_dir)
        engine = CorrectionEngine(config)
        
        # Create a correction for a non-existent file
        nonexistent_path = temp_dir / "nonexistent.toml"
        
        correction = CorrectionSuggestion(
            issue_type='black_line_length',
            file_path=nonexistent_path,
            line_number=None,
            original_content=None,
            suggested_content='line-length = 88',
            description="Fix black line length",
            confidence=0.9,
            auto_fixable=True
        )
        
        results = await engine.apply_auto_fixes([correction])
        
        assert len(results) == 1
        result = results[0]
        assert result.success is False
        assert result.error_message is not None
    
    def test_format_toml_value(self, correction_engine):
        """Test TOML value formatting."""
        assert correction_engine._format_toml_value("test") == '"test"'
        assert correction_engine._format_toml_value(True) == 'true'
        assert correction_engine._format_toml_value(False) == 'false'
        assert correction_engine._format_toml_value(42) == '42'
        assert correction_engine._format_toml_value(["a", "b"]) == '["a", "b"]'
    
    def test_extract_service_name_from_message(self, correction_engine):
        """Test service name extraction from messages."""
        message = "Missing healthcheck for migration-assistant"
        service_name = correction_engine._extract_service_name_from_message(message)
        assert service_name == "migration-assistant"
        
        message = "Missing restart policy for redis"
        service_name = correction_engine._extract_service_name_from_message(message)
        assert service_name == "redis"
    
    def test_extract_import_name_from_message(self, correction_engine):
        """Test import name extraction from messages."""
        message = "Unavailable import in code example: nonexistent_module"
        import_name = correction_engine._extract_import_name_from_message(message)
        assert import_name == "nonexistent_module"
    
    def test_extract_api_reference_from_message(self, correction_engine):
        """Test API reference extraction from messages."""
        message = "Invalid API reference: migration_assistant.cli.main"
        api_ref = correction_engine._extract_api_reference_from_message(message)
        assert api_ref == "migration_assistant.cli.main"