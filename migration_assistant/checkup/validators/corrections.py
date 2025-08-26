"""
Correction Recommendation Engine

Provides specific correction suggestions and automated fix capabilities
for configuration and documentation issues found during validation.
"""

import re
import tomllib
import toml
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass

from migration_assistant.checkup.models import (
    ConfigIssue, DocIssue, IssueSeverity, IssueType, CheckupConfig
)


@dataclass
class CorrectionSuggestion:
    """A specific correction suggestion for an issue."""
    issue_type: str
    file_path: Path
    line_number: Optional[int]
    original_content: Optional[str]
    suggested_content: str
    description: str
    confidence: float  # 0.0 to 1.0
    auto_fixable: bool = False
    backup_required: bool = True


@dataclass
class AutoFixResult:
    """Result of an automated fix operation."""
    success: bool
    file_path: Path
    changes_made: List[str]
    backup_path: Optional[Path] = None
    error_message: Optional[str] = None


class CorrectionEngine:
    """Engine for generating correction suggestions and automated fixes."""
    
    def __init__(self, config: CheckupConfig):
        self.config = config
        self.target_directory = config.target_directory
        
        # Configuration templates and best practices
        self.config_templates = {
            'pyproject_project_section': {
                'name': 'your-project-name',
                'version': '0.1.0',
                'description': 'A brief description of your project',
                'authors': [{'name': 'Your Name', 'email': 'your.email@example.com'}],
                'requires-python': '>=3.11',
            },
            'pyproject_build_system': {
                'requires': ['hatchling'],
                'build-backend': 'hatchling.build',
            },
            'tool_black': {
                'line-length': 88,
                'target-version': ['py311'],
            },
            'tool_isort': {
                'profile': 'black',
                'line_length': 88,
            },
            'tool_mypy': {
                'python_version': '3.11',
                'disallow_untyped_defs': True,
                'disallow_incomplete_defs': True,
                'check_untyped_defs': True,
            },
            'tool_pytest': {
                'ini_options': {
                    'testpaths': ['tests'],
                    'addopts': '-ra -q --strict-markers',
                }
            },
        }
        
        self.docker_templates = {
            'healthcheck': {
                'test': ['CMD', 'curl', '-f', 'http://localhost:8000/health'],
                'interval': '30s',
                'timeout': '10s',
                'retries': 3,
                'start_period': '40s',
            },
            'restart_policy': 'unless-stopped',
        }
    
    def generate_config_corrections(self, issues: List[ConfigIssue]) -> List[CorrectionSuggestion]:
        """Generate correction suggestions for configuration issues."""
        corrections = []
        
        for issue in issues:
            if issue.config_file.name == 'pyproject.toml':
                corrections.extend(self._generate_pyproject_corrections(issue))
            elif issue.config_file.name.startswith('docker-compose'):
                corrections.extend(self._generate_docker_compose_corrections(issue))
            elif issue.config_file.name == 'Dockerfile':
                corrections.extend(self._generate_dockerfile_corrections(issue))
            elif issue.config_file.parent.name == 'workflows':
                corrections.extend(self._generate_workflow_corrections(issue))
        
        return corrections
    
    def generate_doc_corrections(self, issues: List[DocIssue]) -> List[CorrectionSuggestion]:
        """Generate correction suggestions for documentation issues."""
        corrections = []
        
        for issue in issues:
            if issue.doc_type == 'code_example':
                corrections.extend(self._generate_code_example_corrections(issue))
            elif issue.doc_type == 'api_reference':
                corrections.extend(self._generate_api_reference_corrections(issue))
            elif issue.doc_type == 'installation':
                corrections.extend(self._generate_installation_corrections(issue))
            elif issue.doc_type == 'link':
                corrections.extend(self._generate_link_corrections(issue))
            elif issue.doc_type == 'version_reference':
                corrections.extend(self._generate_version_corrections(issue))
        
        return corrections
    
    async def apply_auto_fixes(self, corrections: List[CorrectionSuggestion]) -> List[AutoFixResult]:
        """Apply automated fixes for corrections that support it."""
        results = []
        
        for correction in corrections:
            if not correction.auto_fixable:
                continue
            
            try:
                result = await self._apply_single_fix(correction)
                results.append(result)
            except Exception as e:
                results.append(AutoFixResult(
                    success=False,
                    file_path=correction.file_path,
                    changes_made=[],
                    error_message=str(e)
                ))
        
        return results
    
    def _generate_pyproject_corrections(self, issue: ConfigIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for pyproject.toml issues."""
        corrections = []
        
        if "Missing [project] section" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='missing_project_section',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=self._format_toml_section('project', self.config_templates['pyproject_project_section']),
                description="Add [project] section with required metadata",
                confidence=0.9,
                auto_fixable=True
            ))
        
        elif "Missing [build-system] section" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='missing_build_system',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=self._format_toml_section('build-system', self.config_templates['pyproject_build_system']),
                description="Add [build-system] section with build configuration",
                confidence=0.9,
                auto_fixable=True
            ))
        
        elif "Missing required field:" in issue.message:
            field_name = issue.message.split(": ")[1]
            if field_name in self.config_templates['pyproject_project_section']:
                template_value = self.config_templates['pyproject_project_section'][field_name]
                corrections.append(CorrectionSuggestion(
                    issue_type='missing_project_field',
                    file_path=issue.file_path,
                    line_number=None,
                    original_content=None,
                    suggested_content=f'{field_name} = {self._format_toml_value(template_value)}',
                    description=f"Add missing {field_name} field to [project] section",
                    confidence=0.8,
                    auto_fixable=True
                ))
        
        elif "Unusual black line length" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='black_line_length',
                file_path=issue.file_path,
                line_number=None,
                original_content=f'line-length = {issue.actual_value}',
                suggested_content='line-length = 88',
                description="Set black line length to standard 88 characters",
                confidence=0.7,
                auto_fixable=True
            ))
        
        elif "isort profile not compatible" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='isort_profile',
                file_path=issue.file_path,
                line_number=None,
                original_content=f'profile = "{issue.actual_value}"',
                suggested_content='profile = "black"',
                description="Set isort profile to 'black' for compatibility",
                confidence=0.9,
                auto_fixable=True
            ))
        
        elif "Missing strict mypy settings" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='mypy_strict_settings',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=self._format_toml_section('tool.mypy', self.config_templates['tool_mypy']),
                description="Add strict type checking settings to mypy configuration",
                confidence=0.8,
                auto_fixable=True
            ))
        
        elif "Missing pytest ini_options" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='pytest_ini_options',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=self._format_toml_section('tool.pytest.ini_options', self.config_templates['tool_pytest']['ini_options']),
                description="Add pytest ini_options configuration",
                confidence=0.8,
                auto_fixable=True
            ))
        
        return corrections
    
    def _generate_docker_compose_corrections(self, issue: ConfigIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for docker-compose issues."""
        corrections = []
        
        if "Missing docker-compose version" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='docker_compose_version',
                file_path=issue.file_path,
                line_number=1,
                original_content=None,
                suggested_content="version: '3.8'",
                description="Add version field to docker-compose.yml",
                confidence=0.9,
                auto_fixable=True
            ))
        
        elif "Missing healthcheck" in issue.message:
            service_name = self._extract_service_name_from_message(issue.message)
            healthcheck_yaml = yaml.dump({'healthcheck': self.docker_templates['healthcheck']}, default_flow_style=False)
            corrections.append(CorrectionSuggestion(
                issue_type='docker_healthcheck',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=healthcheck_yaml.strip(),
                description=f"Add healthcheck configuration to {service_name} service",
                confidence=0.7,
                auto_fixable=False  # Requires manual placement in YAML structure
            ))
        
        elif "Missing restart policy" in issue.message:
            service_name = self._extract_service_name_from_message(issue.message)
            corrections.append(CorrectionSuggestion(
                issue_type='docker_restart_policy',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=f"restart: {self.docker_templates['restart_policy']}",
                description=f"Add restart policy to {service_name} service",
                confidence=0.8,
                auto_fixable=False  # Requires manual placement in YAML structure
            ))
        
        return corrections
    
    def _generate_dockerfile_corrections(self, issue: ConfigIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for Dockerfile issues."""
        corrections = []
        
        if "Missing FROM instruction" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='dockerfile_from',
                file_path=issue.file_path,
                line_number=1,
                original_content=None,
                suggested_content="FROM python:3.11-slim",
                description="Add FROM instruction with base image",
                confidence=0.8,
                auto_fixable=True
            ))
        
        elif "Running as root user" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='dockerfile_user',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content="USER 1000",
                description="Add USER instruction to run as non-root user",
                confidence=0.9,
                auto_fixable=False  # Requires careful placement
            ))
        
        elif "Missing HEALTHCHECK instruction" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='dockerfile_healthcheck',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content='HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\\n  CMD curl -f http://localhost:8000/health || exit 1',
                description="Add HEALTHCHECK instruction for container monitoring",
                confidence=0.7,
                auto_fixable=False  # Requires manual placement
            ))
        
        elif "Missing .dockerignore file" in issue.message:
            dockerignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
.venv/
env/
.env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Git
.git/
.gitignore

# Testing
.pytest_cache/
.coverage
htmlcov/

# Documentation
docs/_build/
""".strip()
            
            corrections.append(CorrectionSuggestion(
                issue_type='dockerignore_file',
                file_path=issue.file_path.parent / '.dockerignore',
                line_number=None,
                original_content=None,
                suggested_content=dockerignore_content,
                description="Create .dockerignore file to optimize build context",
                confidence=0.9,
                auto_fixable=True
            ))
        
        return corrections
    
    def _generate_workflow_corrections(self, issue: ConfigIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for GitHub workflow issues."""
        corrections = []
        
        if "Missing required field:" in issue.message:
            field_name = issue.message.split(": ")[1]
            
            if field_name == 'name':
                corrections.append(CorrectionSuggestion(
                    issue_type='workflow_name',
                    file_path=issue.file_path,
                    line_number=1,
                    original_content=None,
                    suggested_content="name: CI",
                    description="Add name field to workflow",
                    confidence=0.9,
                    auto_fixable=True
                ))
            
            elif field_name == 'on':
                on_config = """on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]"""
                corrections.append(CorrectionSuggestion(
                    issue_type='workflow_on',
                    file_path=issue.file_path,
                    line_number=None,
                    original_content=None,
                    suggested_content=on_config,
                    description="Add trigger configuration to workflow",
                    confidence=0.8,
                    auto_fixable=True
                ))
        
        elif "Missing runs-on" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='workflow_runs_on',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content="runs-on: ubuntu-latest",
                description="Add runs-on field to job",
                confidence=0.9,
                auto_fixable=False  # Requires proper job context
            ))
        
        return corrections
    
    def _generate_code_example_corrections(self, issue: DocIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for code example issues."""
        corrections = []
        
        if "Python syntax error" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='code_syntax_error',
                file_path=issue.file_path,
                line_number=issue.line_number,
                original_content=None,
                suggested_content="# Fix syntax error in code example",
                description="Review and fix Python syntax in code example",
                confidence=0.5,
                auto_fixable=False  # Requires manual review
            ))
        
        elif "Unavailable import" in issue.message:
            import_name = self._extract_import_name_from_message(issue.message)
            corrections.append(CorrectionSuggestion(
                issue_type='unavailable_import',
                file_path=issue.file_path,
                line_number=issue.line_number,
                original_content=None,
                suggested_content=f"# Note: Ensure '{import_name}' is installed: pip install {import_name}",
                description=f"Add installation note for '{import_name}' or use available alternative",
                confidence=0.6,
                auto_fixable=False
            ))
        
        elif "Invalid project import" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='invalid_project_import',
                file_path=issue.file_path,
                line_number=issue.line_number,
                original_content=None,
                suggested_content="# Update import path to match current project structure",
                description="Update import path to match current project structure",
                confidence=0.7,
                auto_fixable=False
            ))
        
        return corrections
    
    def _generate_api_reference_corrections(self, issue: DocIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for API reference issues."""
        corrections = []
        
        if "Invalid API reference" in issue.message:
            api_ref = self._extract_api_reference_from_message(issue.message)
            corrections.append(CorrectionSuggestion(
                issue_type='invalid_api_reference',
                file_path=issue.file_path,
                line_number=issue.line_number,
                original_content=f"`{api_ref}`",
                suggested_content="# Update API reference to match current codebase",
                description=f"Update or remove API reference '{api_ref}'",
                confidence=0.6,
                auto_fixable=False
            ))
        
        return corrections
    
    def _generate_installation_corrections(self, issue: DocIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for installation instruction issues."""
        corrections = []
        
        if "Missing installation instructions" in issue.message:
            installation_section = """
## Installation

```bash
pip install migration-assistant
```

### Development Installation

```bash
git clone https://github.com/your-org/migration-assistant.git
cd migration-assistant
pip install -e ".[dev]"
```
""".strip()
            
            corrections.append(CorrectionSuggestion(
                issue_type='missing_installation',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=installation_section,
                description="Add installation instructions section",
                confidence=0.8,
                auto_fixable=False  # Requires manual placement
            ))
        
        elif "Missing development setup" in issue.message:
            dev_section = """
## Development Setup

```bash
git clone https://github.com/your-org/migration-assistant.git
cd migration-assistant
pip install -e ".[dev]"
```
""".strip()
            
            corrections.append(CorrectionSuggestion(
                issue_type='missing_dev_setup',
                file_path=issue.file_path,
                line_number=None,
                original_content=None,
                suggested_content=dev_section,
                description="Add development setup instructions",
                confidence=0.8,
                auto_fixable=False
            ))
        
        return corrections
    
    def _generate_link_corrections(self, issue: DocIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for broken link issues."""
        corrections = []
        
        if "Broken local link" in issue.message and issue.broken_link:
            corrections.append(CorrectionSuggestion(
                issue_type='broken_link',
                file_path=issue.file_path,
                line_number=issue.line_number,
                original_content=None,
                suggested_content=f"# Fix or remove broken link: {issue.broken_link}",
                description=f"Fix or remove broken link to '{issue.broken_link}'",
                confidence=0.9,
                auto_fixable=False
            ))
        
        return corrections
    
    def _generate_version_corrections(self, issue: DocIssue) -> List[CorrectionSuggestion]:
        """Generate corrections for version reference issues."""
        corrections = []
        
        if "Outdated Python version" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='outdated_python_version',
                file_path=issue.file_path,
                line_number=issue.line_number,
                original_content=None,
                suggested_content="Python >=3.11",
                description="Update Python version requirement to current standard",
                confidence=0.8,
                auto_fixable=False  # Requires context-aware replacement
            ))
        
        elif "Potentially outdated version" in issue.message:
            corrections.append(CorrectionSuggestion(
                issue_type='outdated_version',
                file_path=issue.file_path,
                line_number=issue.line_number,
                original_content=None,
                suggested_content="# Review and update version numbers",
                description="Review and update version numbers to current releases",
                confidence=0.6,
                auto_fixable=False
            ))
        
        return corrections
    
    async def _apply_single_fix(self, correction: CorrectionSuggestion) -> AutoFixResult:
        """Apply a single automated fix."""
        if not correction.auto_fixable:
            return AutoFixResult(
                success=False,
                file_path=correction.file_path,
                changes_made=[],
                error_message="Fix is not auto-fixable"
            )
        
        backup_path = None
        if correction.backup_required:
            backup_path = await self._create_backup(correction.file_path)
        
        try:
            if correction.issue_type in ['missing_project_section', 'missing_build_system']:
                success = await self._fix_toml_section(correction)
            elif correction.issue_type in ['missing_project_field', 'black_line_length', 'isort_profile']:
                success = await self._fix_toml_field(correction)
            elif correction.issue_type == 'docker_compose_version':
                success = await self._fix_yaml_field(correction)
            elif correction.issue_type == 'dockerfile_from':
                success = await self._fix_dockerfile_from(correction)
            elif correction.issue_type == 'dockerignore_file':
                success = await self._create_dockerignore(correction)
            elif correction.issue_type in ['workflow_name', 'workflow_on']:
                success = await self._fix_yaml_field(correction)
            else:
                success = False
            
            return AutoFixResult(
                success=success,
                file_path=correction.file_path,
                changes_made=[correction.description] if success else [],
                backup_path=backup_path
            )
        
        except Exception as e:
            return AutoFixResult(
                success=False,
                file_path=correction.file_path,
                changes_made=[],
                backup_path=backup_path,
                error_message=str(e)
            )
    
    async def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of the file before modification."""
        backup_dir = self.target_directory / '.checkup_backups'
        backup_dir.mkdir(exist_ok=True)
        
        backup_path = backup_dir / f"{file_path.name}.backup"
        backup_path.write_bytes(file_path.read_bytes())
        
        return backup_path
    
    async def _fix_toml_section(self, correction: CorrectionSuggestion) -> bool:
        """Fix TOML section issues."""
        try:
            if correction.file_path.exists():
                with open(correction.file_path, 'rb') as f:
                    data = tomllib.load(f)
            else:
                data = {}
            
            # Add the missing section
            if correction.issue_type == 'missing_project_section':
                data['project'] = self.config_templates['pyproject_project_section'].copy()
            elif correction.issue_type == 'missing_build_system':
                data['build-system'] = self.config_templates['pyproject_build_system'].copy()
            
            # Write back to file
            with open(correction.file_path, 'w') as f:
                toml.dump(data, f)
            
            return True
        except Exception:
            return False
    
    async def _fix_toml_field(self, correction: CorrectionSuggestion) -> bool:
        """Fix individual TOML field issues."""
        try:
            with open(correction.file_path, 'rb') as f:
                data = tomllib.load(f)
            
            # Apply specific field fixes
            if correction.issue_type == 'black_line_length':
                if 'tool' not in data:
                    data['tool'] = {}
                if 'black' not in data['tool']:
                    data['tool']['black'] = {}
                data['tool']['black']['line-length'] = 88
            
            elif correction.issue_type == 'isort_profile':
                if 'tool' not in data:
                    data['tool'] = {}
                if 'isort' not in data['tool']:
                    data['tool']['isort'] = {}
                data['tool']['isort']['profile'] = 'black'
            
            # Write back to file
            with open(correction.file_path, 'w') as f:
                toml.dump(data, f)
            
            return True
        except Exception:
            return False
    
    async def _fix_yaml_field(self, correction: CorrectionSuggestion) -> bool:
        """Fix YAML field issues."""
        try:
            if correction.file_path.exists():
                with open(correction.file_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}
            
            # Apply specific fixes
            if correction.issue_type == 'docker_compose_version':
                data['version'] = '3.8'
            elif correction.issue_type == 'workflow_name':
                data['name'] = 'CI'
            elif correction.issue_type == 'workflow_on':
                data['on'] = {
                    'push': {'branches': ['main']},
                    'pull_request': {'branches': ['main']}
                }
            
            # Write back to file
            with open(correction.file_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
            
            return True
        except Exception:
            return False
    
    async def _fix_dockerfile_from(self, correction: CorrectionSuggestion) -> bool:
        """Fix Dockerfile FROM instruction."""
        try:
            if correction.file_path.exists():
                content = correction.file_path.read_text()
            else:
                content = ""
            
            # Add FROM instruction at the beginning
            lines = content.split('\n')
            lines.insert(0, "FROM python:3.11-slim")
            
            correction.file_path.write_text('\n'.join(lines))
            return True
        except Exception:
            return False
    
    async def _create_dockerignore(self, correction: CorrectionSuggestion) -> bool:
        """Create .dockerignore file."""
        try:
            correction.file_path.write_text(correction.suggested_content)
            return True
        except Exception:
            return False
    
    def _format_toml_section(self, section_name: str, data: Dict[str, Any]) -> str:
        """Format a TOML section for insertion."""
        lines = [f"[{section_name}]"]
        for key, value in data.items():
            lines.append(f"{key} = {self._format_toml_value(value)}")
        return '\n'.join(lines)
    
    def _format_toml_value(self, value: Any) -> str:
        """Format a value for TOML."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, list):
            if all(isinstance(item, str) for item in value):
                return '[' + ', '.join(f'"{item}"' for item in value) + ']'
            else:
                return str(value)
        else:
            return str(value)
    
    def _extract_service_name_from_message(self, message: str) -> str:
        """Extract service name from issue message."""
        # Look for pattern like "Missing healthcheck for service_name"
        match = re.search(r'for (\w+)', message)
        return match.group(1) if match else 'service'
    
    def _extract_import_name_from_message(self, message: str) -> str:
        """Extract import name from issue message."""
        # Look for pattern like "Unavailable import in code example: import_name"
        match = re.search(r': ([a-zA-Z_][a-zA-Z0-9_.]*)', message)
        return match.group(1) if match else 'unknown'
    
    def _extract_api_reference_from_message(self, message: str) -> str:
        """Extract API reference from issue message."""
        # Look for pattern like "Invalid API reference: api_ref"
        match = re.search(r': ([a-zA-Z_][a-zA-Z0-9_.()]*)', message)
        return match.group(1) if match else 'unknown'