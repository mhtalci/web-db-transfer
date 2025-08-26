"""
Structure Analyzer

Analyzes file and directory organization against Python project best practices.
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import StructureIssue, IssueType, IssueSeverity


class StructureAnalyzer(BaseAnalyzer):
    """Analyzer for file and directory structure issues."""
    
    # Python project structure best practices
    STANDARD_DIRECTORIES = {
        'src', 'lib', 'package', 'app',  # Source code
        'tests', 'test',  # Tests
        'docs', 'doc', 'documentation',  # Documentation
        'scripts', 'bin',  # Scripts
        'examples', 'samples',  # Examples
        'config', 'configs', 'settings',  # Configuration
        'data', 'assets', 'resources',  # Data/assets
        'migrations',  # Database migrations
        'templates',  # Templates
        'static',  # Static files
    }
    
    # Files that should be in root
    ROOT_FILES = {
        'README.md', 'README.rst', 'README.txt',
        'LICENSE', 'LICENSE.txt', 'LICENSE.md',
        'CHANGELOG.md', 'CHANGELOG.rst', 'CHANGELOG.txt',
        'CONTRIBUTING.md', 'CONTRIBUTING.rst',
        'pyproject.toml', 'setup.py', 'setup.cfg',
        'requirements.txt', 'requirements-dev.txt',
        'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
        '.gitignore', '.gitattributes',
        'Makefile', 'tox.ini', '.pre-commit-config.yaml',
        'pytest.ini', '.flake8', 'mypy.ini',
    }
    
    # Configuration files that should be in root or .config/
    CONFIG_FILES = {
        'pyproject.toml', 'setup.cfg', 'tox.ini', 'pytest.ini',
        '.flake8', 'mypy.ini', '.pre-commit-config.yaml',
        '.github', '.gitlab-ci.yml', '.travis.yml',
    }
    
    def get_supported_file_types(self) -> List[str]:
        """Return supported file types."""
        return ['.py', '.md', '.txt', '.toml', '.yml', '.yaml', '.cfg', '.ini']
    
    async def analyze(self) -> List[StructureIssue]:
        """Analyze structure and return issues found."""
        issues = []
        
        # Analyze directory organization
        org_issues = await self.analyze_directory_organization()
        issues.extend(org_issues)
        
        # Find misplaced files
        misplaced_issues = await self.find_misplaced_files()
        issues.extend(misplaced_issues)
        
        # Detect empty directories
        empty_dir_issues = await self.detect_empty_directories()
        issues.extend(empty_dir_issues)
        
        # Update metrics
        self.update_metrics(
            misplaced_files=len([i for i in issues if 'misplaced' in i.message.lower() or 'not in' in i.message.lower()]),
            empty_directories=len([i for i in issues if 'Empty directory' in i.message])
        )
        
        return issues
    
    async def detect_empty_directories(self) -> List[StructureIssue]:
        """Detect empty directories that can be safely removed."""
        issues = []
        
        # Get all directories
        directories = self._get_all_directories()
        
        for directory in directories:
            if self._is_empty_directory(directory):
                try:
                    relative_path = directory.relative_to(self.target_directory)
                    issues.append(self._create_structure_issue(
                        directory,
                        IssueType.STRUCTURE_ISSUE,
                        IssueSeverity.LOW,
                        f"Empty directory: {relative_path}",
                        f"Directory '{directory.name}' is empty and can be safely removed to clean up the project structure.",
                        suggestion="Remove empty directory"
                    ))
                except ValueError:
                    # Skip directories not under target directory
                    continue
        
        return issues
    
    def _is_empty_directory(self, directory: Path) -> bool:
        """Check if directory is empty or contains only empty subdirectories."""
        try:
            # Check if directory has any files
            for item in directory.rglob("*"):
                if item.is_file():
                    return False
            
            # If we get here, directory contains no files
            # Check if it has any non-empty subdirectories
            for item in directory.iterdir():
                if item.is_dir() and not self._is_empty_directory(item):
                    return False
            
            return True
        except (PermissionError, OSError):
            # If we can't read the directory, assume it's not empty
            return False
    
    async def analyze_directory_organization(self) -> List[StructureIssue]:
        """Analyze directory organization against Python best practices."""
        issues = []
        
        # Get all directories
        directories = self._get_all_directories()
        
        # Check for non-standard directory names
        for directory in directories:
            if self._is_non_standard_directory(directory):
                issues.append(self._create_structure_issue(
                    directory,
                    IssueType.STRUCTURE_ISSUE,
                    IssueSeverity.LOW,
                    f"Non-standard directory name: {directory.name}",
                    f"Directory '{directory.name}' doesn't follow Python project conventions. "
                    f"Consider using standard names like: {', '.join(sorted(self.STANDARD_DIRECTORIES))}",
                    suggestion=self._suggest_directory_rename(directory)
                ))
        
        # Check for deeply nested structures
        for directory in directories:
            try:
                relative_path = directory.relative_to(self.target_directory)
                depth = len(relative_path.parts)
                if depth > 4:  # More than 4 levels deep
                    issues.append(self._create_structure_issue(
                        directory,
                        IssueType.STRUCTURE_ISSUE,
                        IssueSeverity.MEDIUM,
                        f"Deeply nested directory: {relative_path}",
                        f"Directory is {depth} levels deep. Consider flattening the structure "
                        f"to improve maintainability and import paths.",
                        suggestion="Consider reorganizing into a flatter structure"
                    ))
            except ValueError:
                # Skip directories not under target directory
                continue
        
        # Check for package structure issues
        package_issues = self._analyze_package_structure()
        issues.extend(package_issues)
        
        return issues
    
    async def find_misplaced_files(self) -> List[StructureIssue]:
        """Find misplaced files based on content and naming conventions."""
        issues = []
        
        # Get all files
        all_files = self._get_all_files()
        
        for file_path in all_files:
            # Check if root files are in correct location
            if file_path.name in self.ROOT_FILES:
                if file_path.parent != self.target_directory:
                    issues.append(self._create_structure_issue(
                        file_path,
                        IssueType.STRUCTURE_ISSUE,
                        IssueSeverity.MEDIUM,
                        f"Root file in wrong location: {file_path.name}",
                        f"File '{file_path.name}' should be in the project root directory",
                        suggested_location=self.target_directory / file_path.name
                    ))
            
            # Check Python files for misplacement
            if file_path.suffix == '.py':
                misplacement_issue = self._check_python_file_placement(file_path)
                if misplacement_issue:
                    issues.append(misplacement_issue)
            
            # Check test files
            if self._is_test_file(file_path):
                test_issue = self._check_test_file_placement(file_path)
                if test_issue:
                    issues.append(test_issue)
            
            # Check documentation files
            if self._is_documentation_file(file_path):
                doc_issue = self._check_documentation_placement(file_path)
                if doc_issue:
                    issues.append(doc_issue)
            
            # Check configuration files
            if self._is_config_file(file_path):
                config_issue = self._check_config_file_placement(file_path)
                if config_issue:
                    issues.append(config_issue)
        
        return issues
    
    def _get_all_directories(self) -> List[Path]:
        """Get all directories in the target directory."""
        directories = []
        for item in self.target_directory.rglob("*"):
            if item.is_dir() and not self._should_exclude_directory(item):
                directories.append(item)
        return directories
    
    def _should_exclude_directory(self, directory: Path) -> bool:
        """Check if directory should be excluded from analysis."""
        # Skip hidden directories and common exclusions
        if directory.name.startswith('.'):
            return True
        
        # Check if directory is in excluded directories
        if directory.name in self.config.exclude_dirs:
            return True
        
        # Check if any parent directory is excluded
        for exclude_dir in self.config.exclude_dirs:
            if exclude_dir in directory.parts:
                return True
        
        return False
    
    def _get_all_files(self) -> List[Path]:
        """Get all files in the target directory."""
        files = []
        for item in self.target_directory.rglob("*"):
            if item.is_file() and self.should_analyze_file(item):
                files.append(item)
        return files
    
    def _is_non_standard_directory(self, directory: Path) -> bool:
        """Check if directory name follows Python conventions."""
        dir_name = directory.name
        dir_name_lower = dir_name.lower()
        
        # Skip hidden directories and common exclusions
        if dir_name_lower.startswith('.') or dir_name_lower in self.config.exclude_dirs:
            return False
        
        # Check if it's a standard directory name
        if dir_name_lower in self.STANDARD_DIRECTORIES:
            return False
        
        # Check if it's a version-like directory (e.g., v1, api_v2)
        if re.match(r'^(v\d+|api_v\d+|version_\d+)$', dir_name_lower):
            return False
        
        # Check for CamelCase (non-standard for Python)
        if re.match(r'^[A-Z][a-zA-Z]*$', dir_name):
            return True
        
        # Check if it's a valid Python package name (but not too generic)
        if self._is_valid_python_package_name(dir_name_lower):
            # Allow valid package names, but flag obviously bad ones
            if re.match(r'^[a-z]+\d+$', dir_name_lower):  # e.g., badname123
                return True
            if len(dir_name_lower) < 3:  # Very short names
                return True
            return False
        
        # If it doesn't match Python naming conventions, it's non-standard
        return True
    
    def _is_valid_python_package_name(self, name: str) -> bool:
        """Check if name is a valid Python package name."""
        return re.match(r'^[a-z][a-z0-9_]*$', name) is not None
    
    def _suggest_directory_rename(self, directory: Path) -> str:
        """Suggest a better name for a directory."""
        dir_name = directory.name.lower()
        
        # Common mappings
        suggestions = {
            'util': 'utils',
            'helper': 'helpers',
            'tool': 'tools',
            'script': 'scripts',
            'document': 'docs',
            'documentation': 'docs',
            'example': 'examples',
            'sample': 'examples',
            'test_': 'tests',
            'testing': 'tests',
        }
        
        for pattern, suggestion in suggestions.items():
            if pattern in dir_name:
                return f"Consider renaming to '{suggestion}'"
        
        return "Consider using a more standard directory name"
    
    def _analyze_package_structure(self) -> List[StructureIssue]:
        """Analyze Python package structure."""
        issues = []
        
        # Find Python packages (directories with __init__.py)
        packages = self._find_python_packages()
        
        for package_dir in packages:
            # Check for missing __init__.py in subdirectories
            for subdir in package_dir.iterdir():
                if (subdir.is_dir() and 
                    not subdir.name.startswith('.') and
                    subdir.name not in self.config.exclude_dirs and
                    any(f.suffix == '.py' for f in subdir.iterdir() if f.is_file()) and
                    not (subdir / '__init__.py').exists()):
                    
                    issues.append(self._create_structure_issue(
                        subdir,
                        IssueType.STRUCTURE_ISSUE,
                        IssueSeverity.LOW,
                        f"Missing __init__.py in package directory: {subdir.name}",
                        f"Directory '{subdir.name}' contains Python files but lacks __init__.py. "
                        f"This may cause import issues.",
                        suggestion="Add __init__.py file to make it a proper Python package"
                    ))
        
        return issues
    
    def _find_python_packages(self) -> List[Path]:
        """Find all Python packages (directories with __init__.py)."""
        packages = []
        for init_file in self.target_directory.rglob("__init__.py"):
            if self.should_analyze_file(init_file):
                packages.append(init_file.parent)
        return packages
    
    def _check_python_file_placement(self, file_path: Path) -> Optional[StructureIssue]:
        """Check if a Python file is in the correct location."""
        # Skip __init__.py files
        if file_path.name == '__init__.py':
            return None
        
        # Analyze file content to determine its purpose
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if it's a script (has if __name__ == '__main__')
            if 'if __name__ == "__main__"' in content:
                # Scripts should be in scripts/ or bin/ directory
                if not any(part in ['scripts', 'bin'] for part in file_path.parts):
                    return self._create_structure_issue(
                        file_path,
                        IssueType.STRUCTURE_ISSUE,
                        IssueSeverity.LOW,
                        f"Script file not in scripts directory: {file_path.name}",
                        f"File '{file_path.name}' appears to be a script but is not in a scripts/ or bin/ directory",
                        suggested_location=self.target_directory / 'scripts' / file_path.name
                    )
            
            # Check if it's a configuration file
            if self._contains_config_patterns(content):
                if not any(part in ['config', 'configs', 'settings'] for part in file_path.parts):
                    return self._create_structure_issue(
                        file_path,
                        IssueType.STRUCTURE_ISSUE,
                        IssueSeverity.LOW,
                        f"Configuration file not in config directory: {file_path.name}",
                        f"File '{file_path.name}' appears to contain configuration but is not in a config directory",
                        suggested_location=self.target_directory / 'config' / file_path.name
                    )
        
        except (UnicodeDecodeError, IOError):
            # Skip files that can't be read
            pass
        
        return None
    
    def _contains_config_patterns(self, content: str) -> bool:
        """Check if content contains configuration patterns."""
        config_patterns = [
            r'class.*Config\b',
            r'SETTINGS\s*=',
            r'CONFIG\s*=',
            r'DEFAULT_.*=',
            r'from.*config',
            r'import.*config',
        ]
        
        for pattern in config_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _is_test_file(self, file_path: Path) -> bool:
        """Check if file is a test file."""
        name = file_path.name.lower()
        return (name.startswith('test_') or 
                name.endswith('_test.py') or 
                name == 'test.py' or
                'test' in file_path.parts)
    
    def _check_test_file_placement(self, file_path: Path) -> Optional[StructureIssue]:
        """Check if test file is in correct location."""
        # Test files should be in tests/ directory or test/ directory
        if not any(part in ['tests', 'test'] for part in file_path.parts):
            return self._create_structure_issue(
                file_path,
                IssueType.STRUCTURE_ISSUE,
                IssueSeverity.MEDIUM,
                f"Test file not in tests directory: {file_path.name}",
                f"Test file '{file_path.name}' should be in a tests/ directory for better organization",
                suggested_location=self.target_directory / 'tests' / file_path.name
            )
        
        return None
    
    def _is_documentation_file(self, file_path: Path) -> bool:
        """Check if file is a documentation file."""
        name = file_path.name.lower()
        return (file_path.suffix in ['.md', '.rst', '.txt'] and
                (name.startswith('readme') or 
                 name.startswith('doc') or
                 name in ['changelog', 'contributing', 'license', 'authors'] or
                 'doc' in file_path.parts))
    
    def _check_documentation_placement(self, file_path: Path) -> Optional[StructureIssue]:
        """Check if documentation file is in correct location."""
        name = file_path.name.lower()
        
        # Root documentation files should be in root
        if any(name.startswith(root_name.lower()) for root_name in self.ROOT_FILES):
            if file_path.parent != self.target_directory:
                return self._create_structure_issue(
                    file_path,
                    IssueType.STRUCTURE_ISSUE,
                    IssueSeverity.MEDIUM,
                    f"Root documentation file in wrong location: {file_path.name}",
                    f"Documentation file '{file_path.name}' should be in the project root",
                    suggested_location=self.target_directory / file_path.name
                )
        
        # Other documentation should be in docs/
        elif not any(part in ['docs', 'doc', 'documentation'] for part in file_path.parts):
            return self._create_structure_issue(
                file_path,
                IssueType.STRUCTURE_ISSUE,
                IssueSeverity.LOW,
                f"Documentation file not in docs directory: {file_path.name}",
                f"Documentation file '{file_path.name}' should be in a docs/ directory",
                suggested_location=self.target_directory / 'docs' / file_path.name
            )
        
        return None
    
    def _is_config_file(self, file_path: Path) -> bool:
        """Check if file is a configuration file."""
        name = file_path.name.lower()
        return (file_path.suffix in ['.toml', '.cfg', '.ini', '.yaml', '.yml', '.json'] or
                name in self.CONFIG_FILES or
                name.startswith('.') and file_path.suffix in ['.yaml', '.yml'])
    
    def _check_config_file_placement(self, file_path: Path) -> Optional[StructureIssue]:
        """Check if configuration file is in correct location."""
        # Root config files should stay in root
        if file_path.name in self.CONFIG_FILES:
            return None
        
        # Other config files should be in config/ or root
        if (not any(part in ['config', 'configs', 'settings'] for part in file_path.parts) and
            file_path.parent != self.target_directory):
            
            return self._create_structure_issue(
                file_path,
                IssueType.STRUCTURE_ISSUE,
                IssueSeverity.LOW,
                f"Configuration file not in standard location: {file_path.name}",
                f"Configuration file '{file_path.name}' should be in root or config/ directory",
                suggested_location=self.target_directory / 'config' / file_path.name
            )
        
        return None
    
    def _create_structure_issue(
        self,
        file_path: Path,
        issue_type: IssueType,
        severity: IssueSeverity,
        message: str,
        description: str,
        suggestion: Optional[str] = None,
        suggested_location: Optional[Path] = None
    ) -> StructureIssue:
        """Create a structure issue."""
        return StructureIssue(
            file_path=file_path,
            line_number=None,
            severity=severity,
            issue_type=issue_type,
            message=message,
            description=description,
            suggestion=suggestion,
            suggested_location=suggested_location,
            confidence=0.8
        )
    
    async def suggest_reorganization(self) -> List[str]:
        """Suggest reorganization improvements based on analysis."""
        suggestions = []
        
        # Analyze current structure
        issues = await self.analyze()
        
        if not issues:
            suggestions.append("Project structure follows Python best practices")
            return suggestions
        
        # Group issues by type
        misplaced_files = [i for i in issues if i.suggested_location and i.file_path.is_file()]
        empty_dirs = [i for i in issues if "Empty directory" in i.message]
        non_standard_dirs = [i for i in issues if "Non-standard directory name" in i.message]
        deeply_nested = [i for i in issues if "Deeply nested directory" in i.message]
        
        # Generate suggestions
        if misplaced_files:
            suggestions.append(f"Move {len(misplaced_files)} misplaced files to appropriate directories")
            
            # Specific suggestions for common patterns
            test_files = [i for i in misplaced_files if 'test' in i.message.lower()]
            if test_files:
                suggestions.append(f"  - Move {len(test_files)} test files to tests/ directory")
            
            script_files = [i for i in misplaced_files if 'script' in i.message.lower()]
            if script_files:
                suggestions.append(f"  - Move {len(script_files)} script files to scripts/ directory")
            
            config_files = [i for i in misplaced_files if 'config' in i.message.lower()]
            if config_files:
                suggestions.append(f"  - Move {len(config_files)} configuration files to config/ directory")
        
        if empty_dirs:
            suggestions.append(f"Remove {len(empty_dirs)} empty directories to clean up structure")
        
        if non_standard_dirs:
            suggestions.append(f"Rename {len(non_standard_dirs)} directories to follow Python naming conventions")
            for issue in non_standard_dirs[:3]:  # Show first 3 examples
                suggestions.append(f"  - Consider renaming '{issue.file_path.name}' to follow snake_case")
        
        if deeply_nested:
            suggestions.append(f"Flatten {len(deeply_nested)} deeply nested directory structures")
            suggestions.append("  - Consider reorganizing to reduce import path complexity")
        
        # Add package structure suggestions
        package_suggestions = self._suggest_package_improvements()
        suggestions.extend(package_suggestions)
        
        return suggestions
    
    def _suggest_package_improvements(self) -> List[str]:
        """Suggest improvements to Python package structure."""
        suggestions = []
        
        # Find Python packages
        packages = self._find_python_packages()
        
        if not packages:
            suggestions.append("Consider organizing Python modules into packages with __init__.py files")
            return suggestions
        
        # Check for common package structure improvements
        src_packages = [p for p in packages if 'src' in p.parts]
        if not src_packages and len(packages) > 1:
            suggestions.append("Consider using src/ layout for better package organization")
        
        # Check for test organization
        test_packages = [p for p in packages if any(part in ['tests', 'test'] for part in p.parts)]
        if not test_packages:
            suggestions.append("Consider organizing tests into a dedicated tests/ package")
        
        return suggestions