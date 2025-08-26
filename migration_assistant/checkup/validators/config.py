"""
Configuration File Validator

Validates various configuration files including pyproject.toml, Docker configurations,
and CI/CD configurations to ensure they are properly structured and contain required settings.
"""

import json
import re
import subprocess
import tomllib
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

from migration_assistant.checkup.models import (
    ConfigIssue, IssueSeverity, IssueType, CheckupConfig
)
from migration_assistant.checkup.validators.base import BaseValidator, ValidationResult


class ConfigValidator(BaseValidator):
    """Validator for configuration files."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.supported_config_files = {
            'pyproject.toml': self._validate_pyproject_toml,
            'docker-compose.yml': self._validate_docker_compose,
            'docker-compose.yaml': self._validate_docker_compose,
            'Dockerfile': self._validate_dockerfile,
            '.github/workflows/*.yml': self._validate_github_workflow,
            '.github/workflows/*.yaml': self._validate_github_workflow,
        }
    
    def get_validation_scope(self) -> List[str]:
        """Return list of what this validator checks."""
        return [
            'pyproject_toml_structure',
            'pyproject_toml_dependencies',
            'pyproject_toml_tools',
            'docker_compose_structure',
            'docker_compose_services',
            'dockerfile_best_practices',
            'github_workflow_structure',
            'github_workflow_jobs',
        ]
    
    async def validate(self) -> ValidationResult:
        """Validate all configuration files."""
        result = ValidationResult()
        
        try:
            # Find and validate configuration files
            config_files = self._find_config_files()
            result.files_validated = len(config_files)
            
            for config_file in config_files:
                if not self.should_validate_file(config_file):
                    continue
                
                file_issues = await self._validate_config_file(config_file)
                result.issues.extend(file_issues)
            
            # Update metrics
            self.update_metrics(
                config_files=len(config_files),
                config_issues=len(result.issues)
            )
            
            result.valid = len(result.issues) == 0
            result.message = f"Validated {len(config_files)} configuration files"
            
            if result.issues:
                critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
                if critical_issues:
                    result.message += f", found {len(critical_issues)} critical issues"
                else:
                    result.message += f", found {len(result.issues)} issues"
            
        except Exception as e:
            result.valid = False
            result.message = f"Configuration validation failed: {str(e)}"
        
        return result
    
    def _find_config_files(self) -> List[Path]:
        """Find all configuration files in the target directory."""
        config_files = []
        
        # pyproject.toml
        pyproject_path = self.target_directory / "pyproject.toml"
        if pyproject_path.exists():
            config_files.append(pyproject_path)
        
        # Docker files
        for docker_file in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]:
            docker_path = self.target_directory / docker_file
            if docker_path.exists():
                config_files.append(docker_path)
        
        # GitHub workflows
        workflows_dir = self.target_directory / ".github" / "workflows"
        if workflows_dir.exists():
            for workflow_file in workflows_dir.glob("*.yml"):
                config_files.append(workflow_file)
            for workflow_file in workflows_dir.glob("*.yaml"):
                config_files.append(workflow_file)
        
        return config_files
    
    async def _validate_config_file(self, config_file: Path) -> List[ConfigIssue]:
        """Validate a specific configuration file."""
        issues = []
        
        try:
            if config_file.name == "pyproject.toml":
                issues.extend(await self._validate_pyproject_toml(config_file))
            elif config_file.name.startswith("docker-compose"):
                issues.extend(await self._validate_docker_compose(config_file))
            elif config_file.name == "Dockerfile":
                issues.extend(await self._validate_dockerfile(config_file))
            elif config_file.parent.name == "workflows":
                issues.extend(await self._validate_github_workflow(config_file))
        
        except Exception as e:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.CONFIG_ISSUE,
                message=f"Failed to validate {config_file.name}",
                description=f"Error occurred while validating configuration file: {str(e)}",
                config_file=config_file,
                suggestion="Check file syntax and structure"
            ))
        
        return issues
    
    async def _validate_pyproject_toml(self, config_file: Path) -> List[ConfigIssue]:
        """Validate pyproject.toml file."""
        issues = []
        
        try:
            with open(config_file, 'rb') as f:
                config_data = tomllib.load(f)
            
            # Validate project section
            issues.extend(self._validate_project_section(config_file, config_data))
            
            # Validate build system
            issues.extend(self._validate_build_system(config_file, config_data))
            
            # Validate tool configurations
            issues.extend(self._validate_tool_configurations(config_file, config_data))
            
            # Validate dependencies
            issues.extend(self._validate_dependencies(config_file, config_data))
            
        except tomllib.TOMLDecodeError as e:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.CRITICAL,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Invalid TOML syntax",
                description=f"pyproject.toml contains invalid TOML syntax: {str(e)}",
                config_file=config_file,
                suggestion="Fix TOML syntax errors"
            ))
        
        return issues
    
    def _validate_project_section(self, config_file: Path, config_data: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate the [project] section of pyproject.toml."""
        issues = []
        
        if 'project' not in config_data:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing [project] section",
                description="pyproject.toml should contain a [project] section with project metadata",
                config_file=config_file,
                suggestion="Add [project] section with name, version, description, and authors"
            ))
            return issues
        
        project = config_data['project']
        required_fields = ['name', 'version', 'description']
        
        for field in required_fields:
            if field not in project:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message=f"Missing required field: {field}",
                    description=f"The [project] section should contain a '{field}' field",
                    config_file=config_file,
                    config_section="project",
                    suggestion=f"Add '{field}' field to [project] section"
                ))
        
        # Validate Python version requirement
        if 'requires-python' in project:
            python_req = project['requires-python']
            if not re.match(r'>=\d+\.\d+', python_req):
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.LOW,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message="Invalid Python version requirement format",
                    description=f"Python version requirement '{python_req}' should follow format '>=X.Y'",
                    config_file=config_file,
                    config_section="project",
                    actual_value=python_req,
                    expected_value=">=3.11",
                    suggestion="Use format '>=X.Y' for Python version requirement"
                ))
        
        return issues
    
    def _validate_build_system(self, config_file: Path, config_data: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate the [build-system] section."""
        issues = []
        
        if 'build-system' not in config_data:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing [build-system] section",
                description="pyproject.toml should contain a [build-system] section",
                config_file=config_file,
                suggestion="Add [build-system] section with requires and build-backend"
            ))
            return issues
        
        build_system = config_data['build-system']
        
        if 'requires' not in build_system:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing build requirements",
                description="[build-system] section should contain 'requires' field",
                config_file=config_file,
                config_section="build-system",
                suggestion="Add 'requires' field with build dependencies"
            ))
        
        if 'build-backend' not in build_system:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing build backend",
                description="[build-system] section should contain 'build-backend' field",
                config_file=config_file,
                config_section="build-system",
                suggestion="Add 'build-backend' field (e.g., 'hatchling.build')"
            ))
        
        return issues
    
    def _validate_tool_configurations(self, config_file: Path, config_data: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate tool configurations in pyproject.toml."""
        issues = []
        
        if 'tool' not in config_data:
            return issues
        
        tool_config = config_data['tool']
        
        # Validate black configuration
        if 'black' in tool_config:
            issues.extend(self._validate_black_config(config_file, tool_config['black']))
        
        # Validate isort configuration
        if 'isort' in tool_config:
            issues.extend(self._validate_isort_config(config_file, tool_config['isort']))
        
        # Validate mypy configuration
        if 'mypy' in tool_config:
            issues.extend(self._validate_mypy_config(config_file, tool_config['mypy']))
        
        # Validate pytest configuration
        if 'pytest' in tool_config:
            issues.extend(self._validate_pytest_config(config_file, tool_config['pytest']))
        
        return issues
    
    def _validate_black_config(self, config_file: Path, black_config: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate black tool configuration."""
        issues = []
        
        # Check line length consistency
        if 'line-length' in black_config:
            line_length = black_config['line-length']
            if not isinstance(line_length, int) or line_length < 60 or line_length > 120:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.LOW,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message="Unusual black line length",
                    description=f"Black line length of {line_length} is outside typical range (60-120)",
                    config_file=config_file,
                    config_section="tool.black",
                    actual_value=str(line_length),
                    expected_value="88",
                    suggestion="Consider using standard line length of 88"
                ))
        
        return issues
    
    def _validate_isort_config(self, config_file: Path, isort_config: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate isort tool configuration."""
        issues = []
        
        # Check profile compatibility with black
        if 'profile' in isort_config and isort_config['profile'] != 'black':
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.CONFIG_ISSUE,
                message="isort profile not compatible with black",
                description="isort profile should be 'black' for compatibility with black formatter",
                config_file=config_file,
                config_section="tool.isort",
                actual_value=isort_config['profile'],
                expected_value="black",
                suggestion="Set profile = 'black' for black compatibility"
            ))
        
        return issues
    
    def _validate_mypy_config(self, config_file: Path, mypy_config: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate mypy tool configuration."""
        issues = []
        
        # Check for strict type checking settings
        strict_settings = [
            'disallow_untyped_defs',
            'disallow_incomplete_defs',
            'check_untyped_defs'
        ]
        
        missing_strict = [setting for setting in strict_settings if setting not in mypy_config]
        if missing_strict:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing strict mypy settings",
                description=f"Consider enabling strict type checking: {', '.join(missing_strict)}",
                config_file=config_file,
                config_section="tool.mypy",
                suggestion="Add strict type checking settings for better code quality"
            ))
        
        return issues
    
    def _validate_pytest_config(self, config_file: Path, pytest_config: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate pytest tool configuration."""
        issues = []
        
        # Check for ini_options section
        if 'ini_options' not in pytest_config:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing pytest ini_options",
                description="Consider adding [tool.pytest.ini_options] section for test configuration",
                config_file=config_file,
                config_section="tool.pytest",
                suggestion="Add ini_options section with testpaths and addopts"
            ))
        else:
            ini_options = pytest_config['ini_options']
            
            # Check for testpaths
            if 'testpaths' not in ini_options:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.LOW,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message="Missing pytest testpaths",
                    description="Consider specifying testpaths in pytest configuration",
                    config_file=config_file,
                    config_section="tool.pytest.ini_options",
                    suggestion="Add testpaths = ['tests'] to specify test directory"
                ))
        
        return issues
    
    def _validate_dependencies(self, config_file: Path, config_data: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate project dependencies."""
        issues = []
        
        if 'project' not in config_data:
            return issues
        
        project = config_data['project']
        
        # Check for dependencies
        if 'dependencies' not in project:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.CONFIG_ISSUE,
                message="No dependencies specified",
                description="Project should specify its dependencies",
                config_file=config_file,
                config_section="project",
                suggestion="Add dependencies list to [project] section"
            ))
            return issues
        
        dependencies = project['dependencies']
        
        # Check for version pinning
        unpinned_deps = []
        for dep in dependencies:
            if isinstance(dep, str) and not any(op in dep for op in ['>=', '<=', '==', '>', '<', '~=']):
                unpinned_deps.append(dep)
        
        if unpinned_deps:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Unpinned dependencies found",
                description=f"Consider pinning versions for: {', '.join(unpinned_deps[:5])}",
                config_file=config_file,
                config_section="project",
                suggestion="Pin dependency versions for reproducible builds"
            ))
        
        return issues
    
    async def _validate_docker_compose(self, config_file: Path) -> List[ConfigIssue]:
        """Validate docker-compose.yml file."""
        issues = []
        
        try:
            with open(config_file, 'r') as f:
                compose_data = yaml.safe_load(f)
            
            # Validate version
            if 'version' not in compose_data:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message="Missing docker-compose version",
                    description="docker-compose.yml should specify a version",
                    config_file=config_file,
                    suggestion="Add version field (e.g., version: '3.8')"
                ))
            
            # Validate services
            if 'services' not in compose_data:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.HIGH,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message="No services defined",
                    description="docker-compose.yml should define at least one service",
                    config_file=config_file,
                    suggestion="Add services section with service definitions"
                ))
            else:
                services = compose_data['services']
                issues.extend(self._validate_docker_services(config_file, services))
        
        except yaml.YAMLError as e:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.CRITICAL,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Invalid YAML syntax",
                description=f"docker-compose.yml contains invalid YAML: {str(e)}",
                config_file=config_file,
                suggestion="Fix YAML syntax errors"
            ))
        
        return issues
    
    def _validate_docker_services(self, config_file: Path, services: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate Docker Compose services."""
        issues = []
        
        for service_name, service_config in services.items():
            if not isinstance(service_config, dict):
                continue
            
            # Check for health checks on main services
            if service_name in ['app', 'web', 'api', 'migration-assistant']:
                if 'healthcheck' not in service_config:
                    issues.append(ConfigIssue(
                        file_path=config_file,
                        line_number=None,
                        severity=IssueSeverity.LOW,
                        issue_type=IssueType.CONFIG_ISSUE,
                        message=f"Missing healthcheck for {service_name}",
                        description=f"Service '{service_name}' should have a healthcheck",
                        config_file=config_file,
                        config_section=f"services.{service_name}",
                        suggestion="Add healthcheck configuration for better reliability"
                    ))
            
            # Check for restart policy
            if 'restart' not in service_config:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.LOW,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message=f"Missing restart policy for {service_name}",
                    description=f"Service '{service_name}' should have a restart policy",
                    config_file=config_file,
                    config_section=f"services.{service_name}",
                    suggestion="Add restart policy (e.g., 'unless-stopped')"
                ))
        
        return issues
    
    async def _validate_dockerfile(self, config_file: Path) -> List[ConfigIssue]:
        """Validate Dockerfile."""
        issues = []
        
        try:
            with open(config_file, 'r') as f:
                dockerfile_content = f.read()
            
            lines = dockerfile_content.split('\n')
            
            # Check for FROM instruction
            has_from = any(line.strip().upper().startswith('FROM') for line in lines)
            if not has_from:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.CRITICAL,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message="Missing FROM instruction",
                    description="Dockerfile must start with a FROM instruction",
                    config_file=config_file,
                    suggestion="Add FROM instruction with base image"
                ))
            
            # Check for best practices
            issues.extend(self._validate_dockerfile_best_practices(config_file, lines))
        
        except Exception as e:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Failed to read Dockerfile",
                description=f"Error reading Dockerfile: {str(e)}",
                config_file=config_file,
                suggestion="Check Dockerfile exists and is readable"
            ))
        
        return issues
    
    def _validate_dockerfile_best_practices(self, config_file: Path, lines: List[str]) -> List[ConfigIssue]:
        """Validate Dockerfile best practices."""
        issues = []
        
        # Check for non-root user
        has_user = any(line.strip().upper().startswith('USER') for line in lines)
        if not has_user:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Running as root user",
                description="Dockerfile should specify a non-root user for security",
                config_file=config_file,
                suggestion="Add USER instruction to run as non-root user"
            ))
        
        # Check for HEALTHCHECK
        has_healthcheck = any(line.strip().upper().startswith('HEALTHCHECK') for line in lines)
        if not has_healthcheck:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing HEALTHCHECK instruction",
                description="Consider adding HEALTHCHECK instruction for better monitoring",
                config_file=config_file,
                suggestion="Add HEALTHCHECK instruction to monitor container health"
            ))
        
        # Check for .dockerignore reference
        dockerignore_path = config_file.parent / ".dockerignore"
        if not dockerignore_path.exists():
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Missing .dockerignore file",
                description="Consider creating .dockerignore to exclude unnecessary files",
                config_file=config_file,
                suggestion="Create .dockerignore file to optimize build context"
            ))
        
        return issues
    
    async def _validate_github_workflow(self, config_file: Path) -> List[ConfigIssue]:
        """Validate GitHub Actions workflow file."""
        issues = []
        
        try:
            with open(config_file, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            # Validate required fields
            required_fields = ['name', 'on', 'jobs']
            for field in required_fields:
                if field not in workflow_data:
                    issues.append(ConfigIssue(
                        file_path=config_file,
                        line_number=None,
                        severity=IssueSeverity.HIGH,
                        issue_type=IssueType.CONFIG_ISSUE,
                        message=f"Missing required field: {field}",
                        description=f"GitHub workflow must contain '{field}' field",
                        config_file=config_file,
                        suggestion=f"Add '{field}' field to workflow"
                    ))
            
            # Validate jobs
            if 'jobs' in workflow_data:
                jobs = workflow_data['jobs']
                issues.extend(self._validate_workflow_jobs(config_file, jobs))
        
        except yaml.YAMLError as e:
            issues.append(ConfigIssue(
                file_path=config_file,
                line_number=None,
                severity=IssueSeverity.CRITICAL,
                issue_type=IssueType.CONFIG_ISSUE,
                message="Invalid YAML syntax",
                description=f"Workflow file contains invalid YAML: {str(e)}",
                config_file=config_file,
                suggestion="Fix YAML syntax errors"
            ))
        
        return issues
    
    def _validate_workflow_jobs(self, config_file: Path, jobs: Dict[str, Any]) -> List[ConfigIssue]:
        """Validate GitHub workflow jobs."""
        issues = []
        
        for job_name, job_config in jobs.items():
            if not isinstance(job_config, dict):
                continue
            
            # Check for runs-on
            if 'runs-on' not in job_config:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.HIGH,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message=f"Missing runs-on for job {job_name}",
                    description=f"Job '{job_name}' must specify runs-on",
                    config_file=config_file,
                    config_section=f"jobs.{job_name}",
                    suggestion="Add runs-on field (e.g., 'ubuntu-latest')"
                ))
            
            # Check for steps
            if 'steps' not in job_config:
                issues.append(ConfigIssue(
                    file_path=config_file,
                    line_number=None,
                    severity=IssueSeverity.HIGH,
                    issue_type=IssueType.CONFIG_ISSUE,
                    message=f"Missing steps for job {job_name}",
                    description=f"Job '{job_name}' must define steps",
                    config_file=config_file,
                    config_section=f"jobs.{job_name}",
                    suggestion="Add steps array with job actions"
                ))
        
        return issues