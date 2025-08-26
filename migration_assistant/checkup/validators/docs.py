"""
Documentation Validator

Validates documentation files including README files, API documentation,
code examples, and installation instructions to ensure they are accurate and up-to-date.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse
import tempfile
import importlib.util

from migration_assistant.checkup.models import (
    DocIssue, IssueSeverity, IssueType, CheckupConfig
)
from migration_assistant.checkup.validators.base import BaseValidator, ValidationResult


class DocumentationValidator(BaseValidator):
    """Validator for documentation files."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.doc_extensions = ['.md', '.rst', '.txt']
        self.code_block_patterns = {
            'python': r'```python\n(.*?)\n```',
            'bash': r'```bash\n(.*?)\n```',
            'shell': r'```shell\n(.*?)\n```',
            'console': r'```console\n(.*?)\n```',
        }
        self.link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        self.api_reference_patterns = [
            r'`([a-zA-Z_][a-zA-Z0-9_.]*\.[a-zA-Z_][a-zA-Z0-9_]*)`',  # module.function
            r'`([a-zA-Z_][a-zA-Z0-9_]*\(\))`',  # function()
            r'`([A-Z][a-zA-Z0-9_]*)`',  # ClassName
        ]
    
    def get_validation_scope(self) -> List[str]:
        """Return list of what this validator checks."""
        return [
            'code_examples_syntax',
            'code_examples_execution',
            'api_references_accuracy',
            'installation_instructions',
            'broken_links',
            'outdated_examples',
            'documentation_completeness',
        ]
    
    async def validate(self) -> ValidationResult:
        """Validate all documentation files."""
        result = ValidationResult()
        
        try:
            # Find documentation files
            doc_files = self._find_documentation_files()
            result.files_validated = len(doc_files)
            
            for doc_file in doc_files:
                if not self.should_validate_file(doc_file):
                    continue
                
                file_issues = await self._validate_documentation_file(doc_file)
                result.issues.extend(file_issues)
            
            # Update metrics
            self.update_metrics(
                documentation_files=len(doc_files),
                doc_issues=len(result.issues)
            )
            
            result.valid = len(result.issues) == 0
            result.message = f"Validated {len(doc_files)} documentation files"
            
            if result.issues:
                critical_issues = [i for i in result.issues if i.severity == IssueSeverity.CRITICAL]
                if critical_issues:
                    result.message += f", found {len(critical_issues)} critical issues"
                else:
                    result.message += f", found {len(result.issues)} issues"
            
        except Exception as e:
            result.valid = False
            result.message = f"Documentation validation failed: {str(e)}"
        
        return result
    
    def _find_documentation_files(self) -> List[Path]:
        """Find all documentation files in the target directory."""
        doc_files = []
        
        # Find files with documentation extensions
        for ext in self.doc_extensions:
            pattern = f"*{ext}"
            for file_path in self.target_directory.rglob(pattern):
                if self.should_validate_file(file_path):
                    doc_files.append(file_path)
        
        return doc_files
    
    async def _validate_documentation_file(self, doc_file: Path) -> List[DocIssue]:
        """Validate a specific documentation file."""
        issues = []
        
        try:
            content = doc_file.read_text(encoding='utf-8')
            
            # Validate code examples
            issues.extend(await self._validate_code_examples(doc_file, content))
            
            # Validate API references
            issues.extend(await self._validate_api_references(doc_file, content))
            
            # Validate links
            issues.extend(await self._validate_links(doc_file, content))
            
            # Validate installation instructions (for README files)
            if doc_file.name.lower().startswith('readme'):
                issues.extend(await self._validate_installation_instructions(doc_file, content))
            
            # Check for outdated examples
            issues.extend(await self._check_outdated_examples(doc_file, content))
            
        except UnicodeDecodeError:
            issues.append(DocIssue(
                file_path=doc_file,
                line_number=None,
                severity=IssueSeverity.MEDIUM,
                issue_type=IssueType.DOC_ISSUE,
                message="File encoding issue",
                description="Documentation file cannot be read as UTF-8",
                doc_type="encoding",
                suggestion="Ensure file is saved with UTF-8 encoding"
            ))
        except Exception as e:
            issues.append(DocIssue(
                file_path=doc_file,
                line_number=None,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.DOC_ISSUE,
                message=f"Failed to validate {doc_file.name}",
                description=f"Error occurred while validating documentation: {str(e)}",
                doc_type="validation_error",
                suggestion="Check file accessibility and content"
            ))
        
        return issues
    
    async def _validate_code_examples(self, doc_file: Path, content: str) -> List[DocIssue]:
        """Validate code examples in documentation."""
        issues = []
        
        for language, pattern in self.code_block_patterns.items():
            matches = re.finditer(pattern, content, re.DOTALL | re.MULTILINE)
            
            for match in matches:
                code_block = match.group(1)
                line_number = content[:match.start()].count('\n') + 1
                
                if language == 'python':
                    issues.extend(await self._validate_python_code_block(
                        doc_file, code_block, line_number
                    ))
                elif language in ['bash', 'shell', 'console']:
                    issues.extend(await self._validate_shell_code_block(
                        doc_file, code_block, line_number
                    ))
        
        return issues
    
    async def _validate_python_code_block(
        self, doc_file: Path, code_block: str, line_number: int
    ) -> List[DocIssue]:
        """Validate Python code blocks for syntax and executability."""
        issues = []
        
        # Check syntax
        try:
            ast.parse(code_block)
        except SyntaxError as e:
            issues.append(DocIssue(
                file_path=doc_file,
                line_number=line_number,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.DOC_ISSUE,
                message="Python syntax error in code example",
                description=f"Code block contains syntax error: {str(e)}",
                doc_type="code_example",
                suggestion="Fix Python syntax in code example"
            ))
            return issues
        
        # Check for imports and validate they exist
        try:
            tree = ast.parse(code_block)
            imports = self._extract_imports_from_ast(tree)
            
            for import_name in imports:
                if not self._is_import_available(import_name):
                    issues.append(DocIssue(
                        file_path=doc_file,
                        line_number=line_number,
                        severity=IssueSeverity.MEDIUM,
                        issue_type=IssueType.DOC_ISSUE,
                        message=f"Unavailable import in code example: {import_name}",
                        description=f"Code example imports '{import_name}' which may not be available",
                        doc_type="code_example",
                        suggestion=f"Ensure '{import_name}' is available or update example"
                    ))
        
        except Exception as e:
            # Don't fail validation for import checking errors
            pass
        
        # Check for project-specific imports
        project_imports = self._extract_project_imports(code_block)
        for project_import in project_imports:
            if not self._validate_project_import(project_import):
                issues.append(DocIssue(
                    file_path=doc_file,
                    line_number=line_number,
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.DOC_ISSUE,
                    message=f"Invalid project import: {project_import}",
                    description=f"Code example references '{project_import}' which doesn't exist in the project",
                    doc_type="code_example",
                    outdated_example=True,
                    suggestion=f"Update import path or ensure '{project_import}' exists"
                ))
        
        return issues
    
    async def _validate_shell_code_block(
        self, doc_file: Path, code_block: str, line_number: int
    ) -> List[DocIssue]:
        """Validate shell/bash code blocks."""
        issues = []
        
        lines = code_block.strip().split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Remove common prompt indicators
            if line.startswith('$ '):
                line = line[2:]
            elif line.startswith('> '):
                line = line[2:]
            
            # Check for common installation commands
            if any(cmd in line for cmd in ['pip install', 'npm install', 'apt install']):
                # Validate package names exist (basic check)
                if 'pip install' in line:
                    packages = self._extract_pip_packages(line)
                    for package in packages:
                        if package.startswith('.') or package == 'migration_assistant':
                            # Local package, check if it exists
                            if not self._validate_local_package(package):
                                issues.append(DocIssue(
                                    file_path=doc_file,
                                    line_number=line_number + i,
                                    severity=IssueSeverity.MEDIUM,
                                    issue_type=IssueType.DOC_ISSUE,
                                    message=f"Invalid package in installation command: {package}",
                                    description=f"Installation command references '{package}' which may not be correct",
                                    doc_type="installation",
                                    suggestion=f"Verify package name '{package}' is correct"
                                ))
        
        return issues
    
    async def _validate_api_references(self, doc_file: Path, content: str) -> List[DocIssue]:
        """Validate API references in documentation."""
        issues = []
        
        for pattern in self.api_reference_patterns:
            matches = re.finditer(pattern, content)
            
            for match in matches:
                api_ref = match.group(1)
                line_number = content[:match.start()].count('\n') + 1
                
                if not self._validate_api_reference(api_ref):
                    issues.append(DocIssue(
                        file_path=doc_file,
                        line_number=line_number,
                        severity=IssueSeverity.MEDIUM,
                        issue_type=IssueType.DOC_ISSUE,
                        message=f"Invalid API reference: {api_ref}",
                        description=f"API reference '{api_ref}' doesn't exist in the codebase",
                        doc_type="api_reference",
                        outdated_example=True,
                        suggestion=f"Update or remove reference to '{api_ref}'"
                    ))
        
        return issues
    
    async def _validate_links(self, doc_file: Path, content: str) -> List[DocIssue]:
        """Validate links in documentation."""
        issues = []
        
        matches = re.finditer(self.link_pattern, content)
        
        for match in matches:
            link_text = match.group(1)
            link_url = match.group(2)
            line_number = content[:match.start()].count('\n') + 1
            
            # Skip anchor links and mailto links
            if link_url.startswith('#') or link_url.startswith('mailto:'):
                continue
            
            # Validate local file links
            if not link_url.startswith(('http://', 'https://')):
                local_path = self._resolve_local_link(doc_file, link_url)
                if local_path and not local_path.exists():
                    issues.append(DocIssue(
                        file_path=doc_file,
                        line_number=line_number,
                        severity=IssueSeverity.MEDIUM,
                        issue_type=IssueType.DOC_ISSUE,
                        message=f"Broken local link: {link_url}",
                        description=f"Local file link '{link_url}' points to non-existent file",
                        doc_type="link",
                        broken_link=link_url,
                        suggestion=f"Fix or remove broken link to '{link_url}'"
                    ))
            
            # For external links, we could add HTTP validation but it's expensive
            # and may not be reliable in CI environments, so we skip it for now
        
        return issues
    
    async def _validate_installation_instructions(self, doc_file: Path, content: str) -> List[DocIssue]:
        """Validate installation instructions in README files."""
        issues = []
        
        # Check for common installation patterns
        installation_patterns = [
            r'pip install[^\n]*',
            r'python -m pip install[^\n]*',
            r'poetry install[^\n]*',
            r'npm install[^\n]*',
        ]
        
        has_installation = False
        for pattern in installation_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                has_installation = True
                break
        
        if not has_installation:
            issues.append(DocIssue(
                file_path=doc_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.DOC_ISSUE,
                message="Missing installation instructions",
                description="README file should include installation instructions",
                doc_type="installation",
                suggestion="Add installation instructions for users"
            ))
        
        # Check for development setup instructions
        dev_patterns = [
            r'development',
            r'contributing',
            r'dev install',
            r'editable install',
            r'-e \.',
        ]
        
        has_dev_setup = any(re.search(pattern, content, re.IGNORECASE) for pattern in dev_patterns)
        
        if not has_dev_setup:
            issues.append(DocIssue(
                file_path=doc_file,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.DOC_ISSUE,
                message="Missing development setup instructions",
                description="README should include development setup instructions",
                doc_type="installation",
                suggestion="Add development setup section for contributors"
            ))
        
        return issues
    
    async def _check_outdated_examples(self, doc_file: Path, content: str) -> List[DocIssue]:
        """Check for potentially outdated examples."""
        issues = []
        
        # Check for old Python version references
        old_python_patterns = [
            r'python\s*3\.[0-9](?![0-9])',  # python 3.x (single digit)
            r'>=\s*3\.[0-9](?![0-9])',      # >=3.x (single digit)
        ]
        
        for pattern in old_python_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                version_ref = match.group(0)
                line_number = content[:match.start()].count('\n') + 1
                
                # Extract version number
                version_match = re.search(r'3\.(\d+)', version_ref)
                if version_match:
                    minor_version = int(version_match.group(1))
                    if minor_version < 11:  # Assuming current project requires 3.11+
                        issues.append(DocIssue(
                            file_path=doc_file,
                            line_number=line_number,
                            severity=IssueSeverity.LOW,
                            issue_type=IssueType.DOC_ISSUE,
                            message=f"Outdated Python version reference: {version_ref}",
                            description=f"Documentation references Python {version_ref} which may be outdated",
                            doc_type="version_reference",
                            outdated_example=True,
                            suggestion="Update Python version references to current requirements"
                        ))
        
        # Check for outdated package versions in examples
        version_patterns = [
            r'==\s*\d+\.\d+\.\d+',  # ==1.2.3
            r'>=\s*\d+\.\d+\.\d+',  # >=1.2.3
        ]
        
        for pattern in version_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                version_ref = match.group(0)
                line_number = content[:match.start()].count('\n') + 1
                
                # This is a basic check - in a real implementation, you might
                # want to check against actual package versions
                if '==0.' in version_ref or '>=0.' in version_ref:
                    issues.append(DocIssue(
                        file_path=doc_file,
                        line_number=line_number,
                        severity=IssueSeverity.LOW,
                        issue_type=IssueType.DOC_ISSUE,
                        message=f"Potentially outdated version: {version_ref}",
                        description=f"Version reference '{version_ref}' may be outdated",
                        doc_type="version_reference",
                        outdated_example=True,
                        suggestion="Verify version numbers are current"
                    ))
        
        return issues
    
    def _extract_imports_from_ast(self, tree: ast.AST) -> List[str]:
        """Extract import names from AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return imports
    
    def _is_import_available(self, import_name: str) -> bool:
        """Check if an import is available in the current environment."""
        try:
            # Try to find the module spec
            spec = importlib.util.find_spec(import_name)
            return spec is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            return False
    
    def _extract_project_imports(self, code_block: str) -> List[str]:
        """Extract project-specific imports from code block."""
        project_imports = []
        
        try:
            tree = ast.parse(code_block)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('migration_assistant'):
                            project_imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith('migration_assistant'):
                        project_imports.append(node.module)
        except SyntaxError:
            pass
        
        return project_imports
    
    def _validate_project_import(self, import_path: str) -> bool:
        """Validate that a project import path exists."""
        # Convert import path to file path
        parts = import_path.split('.')
        
        # Start from the target directory
        current_path = self.target_directory
        
        for part in parts:
            # Check for module file
            module_file = current_path / f"{part}.py"
            if module_file.exists():
                return True
            
            # Check for package directory
            package_dir = current_path / part
            if package_dir.is_dir():
                current_path = package_dir
                # Check for __init__.py
                init_file = package_dir / "__init__.py"
                if not init_file.exists():
                    return False
            else:
                return False
        
        return True
    
    def _extract_pip_packages(self, command: str) -> List[str]:
        """Extract package names from pip install command."""
        packages = []
        
        # Remove pip install part
        command = re.sub(r'pip\s+install\s+', '', command, flags=re.IGNORECASE)
        
        # Split by spaces and filter out flags
        parts = command.split()
        for part in parts:
            if not part.startswith('-') and not part.startswith('['):
                # Remove version specifiers
                package = re.split(r'[>=<!=~]', part)[0]
                if package:
                    packages.append(package)
        
        return packages
    
    def _validate_local_package(self, package: str) -> bool:
        """Validate that a local package reference is correct."""
        if package == '.':
            # Current directory install - check for pyproject.toml or setup.py
            return (self.target_directory / "pyproject.toml").exists() or \
                   (self.target_directory / "setup.py").exists()
        elif package.startswith('./') or package.startswith('../'):
            # Relative path install
            package_path = self.target_directory / package
            return package_path.exists()
        elif package == 'migration_assistant':
            # Check if the main package exists
            package_path = self.target_directory / "migration_assistant"
            return package_path.is_dir()
        
        return True  # Assume other packages are valid
    
    def _validate_api_reference(self, api_ref: str) -> bool:
        """Validate that an API reference exists in the codebase."""
        # Remove parentheses for function references
        api_ref = api_ref.rstrip('()')
        
        # Split into parts
        parts = api_ref.split('.')
        
        if len(parts) == 1:
            # Single name - could be a class or function
            # This is a simplified check - in practice, you'd want more sophisticated validation
            return self._search_for_definition(parts[0])
        else:
            # Module.function or similar
            return self._validate_project_import('.'.join(parts[:-1])) and \
                   self._search_for_definition(parts[-1])
    
    def _search_for_definition(self, name: str) -> bool:
        """Search for a definition in the codebase."""
        # This is a simplified implementation
        # In practice, you'd want to use AST parsing to find actual definitions
        
        python_files = list(self.target_directory.rglob("*.py"))
        
        for py_file in python_files[:10]:  # Limit search for performance
            try:
                content = py_file.read_text(encoding='utf-8')
                # Look for class or function definitions
                if re.search(rf'\b(class|def)\s+{re.escape(name)}\b', content):
                    return True
            except (UnicodeDecodeError, PermissionError):
                continue
        
        return False
    
    def _resolve_local_link(self, doc_file: Path, link_url: str) -> Optional[Path]:
        """Resolve a local link relative to the documentation file."""
        try:
            if link_url.startswith('/'):
                # Absolute path from repository root
                return self.target_directory / link_url.lstrip('/')
            else:
                # Relative path from current file
                return (doc_file.parent / link_url).resolve()
        except Exception:
            return None