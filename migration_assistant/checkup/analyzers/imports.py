"""
Import Analyzer

Analyzes import dependencies and identifies issues.
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Union
from collections import defaultdict

from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import ImportIssue, IssueType, IssueSeverity


class ImportAnalyzer(BaseAnalyzer):
    """Analyzer for import-related issues."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._module_references: Dict[str, Set[str]] = defaultdict(set)
    
    def get_supported_file_types(self) -> List[str]:
        """Return supported file types."""
        return ['.py']
    
    async def analyze(self) -> List[ImportIssue]:
        """Analyze imports and return issues found."""
        issues = []
        
        # Find unused imports
        unused_issues = await self.find_unused_imports()
        issues.extend(unused_issues)
        
        # Detect circular imports
        circular_issues = await self.detect_circular_imports()
        issues.extend(circular_issues)
        
        # Find orphaned modules
        orphaned_issues = await self.find_orphaned_modules()
        issues.extend(orphaned_issues)
        
        # Update metrics
        self.update_metrics(
            unused_imports=len(unused_issues),
            circular_imports=len(set(issue.dependency_chain[0] for issue in circular_issues if issue.dependency_chain)),
            orphaned_modules=len(orphaned_issues)
        )
        
        return issues
    
    async def find_unused_imports(self) -> List[ImportIssue]:
        """Find unused import statements."""
        issues = []
        python_files = self.get_python_files()
        
        for file_path in python_files:
            try:
                file_issues = await self._analyze_file_imports(file_path)
                issues.extend(file_issues)
            except Exception as e:
                # Create an issue for files that can't be parsed
                issue = ImportIssue(
                    file_path=file_path,
                    line_number=None,
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.UNUSED_IMPORT,
                    message=f"Could not analyze imports: {str(e)}",
                    description=f"Failed to parse file for import analysis: {str(e)}",
                    import_name="",
                    confidence=0.5
                )
                issues.append(issue)
        
        return issues
    
    async def _analyze_file_imports(self, file_path: Path) -> List[ImportIssue]:
        """Analyze imports in a single file."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError) as e:
            return [ImportIssue(
                file_path=file_path,
                line_number=None,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.UNUSED_IMPORT,
                message=f"Could not read file: {str(e)}",
                description=f"File could not be read for import analysis: {str(e)}",
                import_name="",
                confidence=0.3
            )]
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return [ImportIssue(
                file_path=file_path,
                line_number=e.lineno,
                severity=IssueSeverity.HIGH,
                issue_type=IssueType.UNUSED_IMPORT,
                message=f"Syntax error prevents import analysis: {str(e)}",
                description=f"File has syntax errors that prevent import analysis: {str(e)}",
                import_name="",
                confidence=0.8
            )]
        
        # Extract imports and their usage
        imports = self._extract_imports(tree)
        used_names = self._extract_used_names(tree, content)
        
        # Check for unused imports
        for import_info in imports:
            if not self._is_import_used(import_info, used_names, content):
                # Check if it's a safe removal (not a side-effect import)
                is_safe = self._is_safe_to_remove(import_info, content)
                
                issue = ImportIssue(
                    file_path=file_path,
                    line_number=import_info['line_number'],
                    severity=IssueSeverity.LOW if is_safe else IssueSeverity.MEDIUM,
                    issue_type=IssueType.UNUSED_IMPORT,
                    message=f"Unused import: {import_info['name']}",
                    description=f"Import '{import_info['name']}' is not used in this file",
                    suggestion=f"Remove unused import: {import_info['statement']}" if is_safe else 
                              f"Consider removing unused import (check for side effects): {import_info['statement']}",
                    import_name=import_info['name'],
                    confidence=0.9 if is_safe else 0.7
                )
                issues.append(issue)
        
        return issues
    
    def _extract_imports(self, tree: ast.AST) -> List[Dict[str, Union[str, int]]]:
        """Extract all import statements from AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'type': 'import',
                        'module': alias.name,
                        'name': alias.asname or alias.name.split('.')[0],
                        'full_name': alias.name,
                        'statement': f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""),
                        'line_number': node.lineno
                    })
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    if alias.name == '*':
                        # Star imports are handled separately
                        imports.append({
                            'type': 'from_star',
                            'module': module,
                            'name': '*',
                            'full_name': f"{module}.*",
                            'statement': f"from {module} import *",
                            'line_number': node.lineno
                        })
                    else:
                        imports.append({
                            'type': 'from',
                            'module': module,
                            'name': alias.asname or alias.name,
                            'full_name': f"{module}.{alias.name}",
                            'statement': f"from {module} import {alias.name}" + 
                                       (f" as {alias.asname}" if alias.asname else ""),
                            'line_number': node.lineno
                        })
        
        return imports
    
    def _extract_used_names(self, tree: ast.AST, content: str) -> Set[str]:
        """Extract all names used in the code."""
        used_names = set()
        
        # Extract names from AST
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # For attribute access like 'module.function'
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
        
        # Also check for string-based usage (like in __all__, type annotations, etc.)
        string_usage = self._find_string_usage(content)
        used_names.update(string_usage)
        
        return used_names
    
    def _find_string_usage(self, content: str) -> Set[str]:
        """Find names used in strings that might reference imports."""
        string_usage = set()
        
        # Look for __all__ definitions
        all_pattern = r'__all__\s*=\s*\[(.*?)\]'
        all_matches = re.findall(all_pattern, content, re.DOTALL)
        for match in all_matches:
            # Extract quoted names
            names = re.findall(r'["\']([^"\']+)["\']', match)
            string_usage.update(names)
        
        # Look for type annotations in strings
        type_annotation_patterns = [
            r':\s*["\']([^"\']+)["\']',  # Type hints in quotes
            r'->\s*["\']([^"\']+)["\']',  # Return type hints in quotes
        ]
        
        for pattern in type_annotation_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Extract potential module names
                parts = match.split('.')
                if parts:
                    string_usage.add(parts[0])
        
        return string_usage
    
    def _is_import_used(self, import_info: Dict[str, Union[str, int]], 
                       used_names: Set[str], content: str) -> bool:
        """Check if an import is used in the code."""
        import_name = import_info['name']
        import_type = import_info['type']
        
        # Star imports are assumed to be used (too complex to analyze)
        if import_type == 'from_star':
            return True
        
        # Check direct usage
        if import_name in used_names:
            return True
        
        # For module imports, check if any submodule is used
        if import_type == 'import':
            module_name = import_info['full_name']
            # Check for attribute access patterns
            attr_pattern = rf'\b{re.escape(import_name)}\.'
            if re.search(attr_pattern, content):
                return True
        
        # Check for usage in special contexts
        special_usage = self._check_special_usage(import_info, content)
        if special_usage:
            return True
        
        return False
    
    def _check_special_usage(self, import_info: Dict[str, Union[str, int]], content: str) -> bool:
        """Check for special usage patterns that might not be caught by AST."""
        import_name = import_info['name']
        
        # Check for usage in decorators
        decorator_pattern = rf'@{re.escape(import_name)}'
        if re.search(decorator_pattern, content):
            return True
        
        # Check for usage in exception handling
        except_pattern = rf'except\s+{re.escape(import_name)}'
        if re.search(except_pattern, content):
            return True
        
        # Check for usage in isinstance/issubclass
        isinstance_pattern = rf'isinstance\([^,]+,\s*{re.escape(import_name)}'
        if re.search(isinstance_pattern, content):
            return True
        
        # Check for usage in class inheritance
        class_pattern = rf'class\s+\w+\([^)]*{re.escape(import_name)}'
        if re.search(class_pattern, content):
            return True
        
        return False
    
    def _is_safe_to_remove(self, import_info: Dict[str, Union[str, int]], content: str) -> bool:
        """Check if an import is safe to remove (no side effects)."""
        module_name = import_info.get('module', '') or import_info.get('full_name', '')
        
        # Known modules that might have side effects when imported
        side_effect_modules = {
            'matplotlib.pyplot', 'matplotlib', 'seaborn', 'pandas',
            'numpy', 'scipy', 'sklearn', 'tensorflow', 'torch',
            'django', 'flask', 'fastapi', 'requests', 'urllib',
            'logging', 'warnings', 'sys', 'os'
        }
        
        # Check if it's a known side-effect module
        for side_effect_module in side_effect_modules:
            if module_name.startswith(side_effect_module):
                return False
        
        # Check for common side-effect patterns in the import statement
        statement = import_info.get('statement', '')
        
        # Imports that modify global state
        if any(keyword in statement.lower() for keyword in ['patch', 'mock', 'monkey']):
            return False
        
        # Check if import is in a try/except block (might be optional)
        lines = content.split('\n')
        import_line = import_info.get('line_number', 1) - 1
        
        if import_line < len(lines):
            # Look for try/except context around the import
            context_start = max(0, import_line - 5)
            context_end = min(len(lines), import_line + 5)
            context = '\n'.join(lines[context_start:context_end])
            
            if 'try:' in context and ('except' in context or 'ImportError' in context):
                return False
        
        return True
    
    async def detect_circular_imports(self) -> List[ImportIssue]:
        """Detect circular import dependencies."""
        issues = []
        
        # Build dependency graph
        dependency_graph = await self.analyze_dependency_graph()
        
        # Find circular dependencies using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str, path: List[str]) -> Optional[List[str]]:
            """DFS to detect cycles and return the cycle path."""
            if node in rec_stack:
                # Found a cycle, return the cycle path
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            
            if node in visited:
                return None
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in dependency_graph.get(node, []):
                cycle = has_cycle(neighbor, path + [node])
                if cycle:
                    return cycle
            
            rec_stack.remove(node)
            return None
        
        # Check each module for cycles
        cycles_found = set()
        for module in dependency_graph:
            if module not in visited:
                cycle = has_cycle(module, [])
                if cycle:
                    # Create a canonical representation of the cycle
                    cycle_key = tuple(sorted(cycle[:-1]))  # Remove duplicate last element
                    if cycle_key not in cycles_found:
                        cycles_found.add(cycle_key)
                        
                        # Create issues for each module in the cycle
                        for i, module_name in enumerate(cycle[:-1]):
                            next_module = cycle[i + 1]
                            
                            # Find the file path for this module
                            module_path = self._find_module_path(module_name)
                            if module_path:
                                issue = ImportIssue(
                                    file_path=module_path,
                                    line_number=None,
                                    severity=IssueSeverity.HIGH,
                                    issue_type=IssueType.CIRCULAR_IMPORT,
                                    message=f"Circular import detected: {module_name} -> {next_module}",
                                    description=f"Module '{module_name}' is part of a circular import chain: {' -> '.join(cycle)}",
                                    suggestion=self._suggest_circular_import_resolution(cycle),
                                    import_name=next_module,
                                    is_circular=True,
                                    dependency_chain=cycle,
                                    confidence=0.9
                                )
                                issues.append(issue)
        
        return issues
    
    async def find_orphaned_modules(self) -> List[ImportIssue]:
        """Find orphaned modules with no references."""
        issues = []
        python_files = self.get_python_files()
        
        # Build module reference map
        module_references = defaultdict(set)
        module_to_path = {}
        
        # First pass: map all modules and collect their imports
        for file_path in python_files:
            module_name = self._get_module_name(file_path)
            module_to_path[module_name] = file_path
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                imports = self._extract_imports(tree)
                
                # Track what this module imports
                for import_info in imports:
                    imported_module = self._resolve_import_module(import_info, module_name)
                    if imported_module and imported_module in module_to_path:
                        # This module references the imported module
                        module_references[imported_module].add(module_name)
                
            except (IOError, UnicodeDecodeError, SyntaxError):
                # Skip files that can't be processed
                continue
        
        # Second pass: find modules with no references
        for module_name, file_path in module_to_path.items():
            if self._is_orphaned_module(module_name, file_path, module_references):
                # Check if it's safe to remove
                is_safe, reason = self._is_safe_to_remove_module(file_path)
                
                issue = ImportIssue(
                    file_path=file_path,
                    line_number=None,
                    severity=IssueSeverity.MEDIUM if is_safe else IssueSeverity.LOW,
                    issue_type=IssueType.ORPHANED_MODULE,
                    message=f"Orphaned module: {module_name}",
                    description=f"Module '{module_name}' is not imported by any other module in the codebase",
                    suggestion=self._suggest_orphaned_module_action(module_name, file_path, is_safe, reason),
                    import_name=module_name,
                    confidence=0.8 if is_safe else 0.6
                )
                issues.append(issue)
        
        return issues
    
    def _is_orphaned_module(self, module_name: str, file_path: Path, 
                           module_references: Dict[str, Set[str]]) -> bool:
        """Check if a module is orphaned (not referenced by other modules)."""
        # Module has no references from other modules
        if module_name not in module_references or not module_references[module_name]:
            # Check for special cases that shouldn't be considered orphaned
            
            # Entry points (main modules, CLI modules, API modules)
            if self._is_entry_point_module(file_path):
                return False
            
            # Test modules
            if self._is_test_module(file_path):
                return False
            
            # Configuration modules
            if self._is_config_module(file_path):
                return False
            
            # __init__.py files
            if file_path.name == '__init__.py':
                return False
            
            # Scripts and examples
            if self._is_script_or_example(file_path):
                return False
            
            return True
        
        return False
    
    def _is_entry_point_module(self, file_path: Path) -> bool:
        """Check if module is an entry point (main, CLI, API, etc.)."""
        entry_point_patterns = [
            'main.py',
            'cli.py', 
            'app.py',
            'server.py',
            'run.py',
            'start.py',
            'manage.py',
        ]
        
        # Check filename patterns
        if file_path.name in entry_point_patterns:
            return True
        
        # Check if file contains if __name__ == '__main__'
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '__name__' in content and '__main__' in content:
                    return True
        except (IOError, UnicodeDecodeError):
            pass
        
        # Check path patterns
        entry_point_dirs = ['cli', 'api', 'scripts', 'bin']
        for part in file_path.parts:
            if part in entry_point_dirs:
                return True
        
        return False
    
    def _is_test_module(self, file_path: Path) -> bool:
        """Check if module is a test module."""
        # Check filename patterns
        if (file_path.name.startswith('test_') or 
            file_path.name.endswith('_test.py') or
            file_path.name == 'conftest.py'):
            return True
        
        # Check directory patterns
        test_dirs = ['test', 'tests', 'testing']
        for part in file_path.parts:
            if part in test_dirs:
                return True
        
        return False
    
    def _is_config_module(self, file_path: Path) -> bool:
        """Check if module is a configuration module."""
        config_patterns = [
            'config.py',
            'settings.py',
            'configuration.py',
            'constants.py',
            'defaults.py',
        ]
        
        return file_path.name in config_patterns
    
    def _is_script_or_example(self, file_path: Path) -> bool:
        """Check if module is a script or example."""
        script_dirs = ['scripts', 'examples', 'demos', 'tools', 'utilities']
        
        for part in file_path.parts:
            if part in script_dirs:
                return True
        
        return False
    
    def _is_safe_to_remove_module(self, file_path: Path) -> Tuple[bool, str]:
        """Check if module is safe to remove and provide reason."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, UnicodeDecodeError):
            return False, "Could not read file content"
        
        # Check for side effects or important functionality
        
        # Check for class definitions
        if 'class ' in content:
            return False, "Contains class definitions"
        
        # Check for function definitions (excluding simple helper functions)
        function_count = content.count('def ')
        if function_count > 3:  # More than a few simple functions
            return False, f"Contains {function_count} function definitions"
        
        # Check for global variables or constants
        if any(pattern in content for pattern in ['= ', 'global ', 'nonlocal ']):
            # Simple heuristic: if it has assignments, it might define important data
            lines = content.split('\n')
            assignment_lines = [line for line in lines if '=' in line and not line.strip().startswith('#')]
            if len(assignment_lines) > 2:  # More than a couple of assignments
                return False, "Contains global variables or constants"
        
        # Check for imports that might indicate the module provides functionality
        if 'import ' in content:
            import_count = content.count('import ')
            if import_count > 5:  # Many imports might indicate complex functionality
                return False, f"Has {import_count} imports, might provide complex functionality"
        
        # Check file size - very small files are likely safe to remove
        if len(content.strip()) < 100:  # Very small file
            return True, "Very small file with minimal content"
        
        # Check for docstrings that might indicate purpose
        if '"""' in content or "'''" in content:
            return False, "Contains docstrings, might be documented functionality"
        
        # If we get here, it's probably safe but we're not certain
        return True, "Appears to contain only simple code"
    
    def _suggest_orphaned_module_action(self, module_name: str, file_path: Path, 
                                       is_safe: bool, reason: str) -> str:
        """Suggest action for orphaned module."""
        if is_safe:
            return f"Consider removing orphaned module '{module_name}' ({reason}). " \
                   f"Verify it's not used externally before deletion."
        else:
            return f"Orphaned module '{module_name}' detected ({reason}). " \
                   f"Review if this module should be imported elsewhere or if it serves a specific purpose."
    
    async def analyze_dependency_graph(self) -> Dict[str, List[str]]:
        """Analyze dependency graph."""
        dependency_graph = defaultdict(list)
        python_files = self.get_python_files()
        
        # Build module name to file path mapping
        module_to_path = {}
        for file_path in python_files:
            module_name = self._get_module_name(file_path)
            module_to_path[module_name] = file_path
        
        # Analyze each file's imports
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                imports = self._extract_imports(tree)
                
                current_module = self._get_module_name(file_path)
                
                for import_info in imports:
                    imported_module = self._resolve_import_module(import_info, current_module)
                    if imported_module and imported_module in module_to_path:
                        # Only track internal dependencies (within our codebase)
                        dependency_graph[current_module].append(imported_module)
                
            except (IOError, UnicodeDecodeError, SyntaxError):
                # Skip files that can't be processed
                continue
        
        # Convert to regular dict and remove duplicates
        result = {}
        for module, deps in dependency_graph.items():
            result[module] = list(set(deps))
        
        return result
    
    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        # Get relative path from target directory
        try:
            rel_path = file_path.relative_to(self.target_directory)
        except ValueError:
            # File is outside target directory
            return str(file_path.stem)
        
        # Convert path to module name
        parts = list(rel_path.parts[:-1])  # Remove filename
        if rel_path.stem != '__init__':
            parts.append(rel_path.stem)
        
        return '.'.join(parts) if parts else rel_path.stem
    
    def _resolve_import_module(self, import_info: Dict[str, Union[str, int]], current_module: str) -> Optional[str]:
        """Resolve import to module name within our codebase."""
        import_type = import_info['type']
        
        if import_type == 'import':
            # Direct import: import module.submodule
            module_name = import_info['full_name']
        elif import_type in ['from', 'from_star']:
            # From import: from module import something
            module_name = import_info['module']
        else:
            return None
        
        # Handle relative imports
        if module_name.startswith('.'):
            # Relative import - resolve relative to current module
            if not current_module:
                return None
            
            current_parts = current_module.split('.')
            
            # Count leading dots
            dots = 0
            for char in module_name:
                if char == '.':
                    dots += 1
                else:
                    break
            
            # Calculate base module
            if dots > len(current_parts):
                return None  # Invalid relative import
            
            base_parts = current_parts[:-dots] if dots > 0 else current_parts
            relative_part = module_name[dots:] if dots < len(module_name) else ''
            
            if relative_part:
                resolved_parts = base_parts + relative_part.split('.')
            else:
                resolved_parts = base_parts
            
            return '.'.join(resolved_parts)
        
        # Check if it's an internal module (starts with our package name)
        if self._is_internal_module(module_name):
            return module_name
        
        return None
    
    def _is_internal_module(self, module_name: str) -> bool:
        """Check if module is internal to our codebase."""
        # Check if module starts with known internal package names
        internal_prefixes = [
            'migration_assistant',
            # Add other internal package prefixes as needed
        ]
        
        for prefix in internal_prefixes:
            if module_name.startswith(prefix):
                return True
        
        # Also check if we have a file for this module
        module_path = self._find_module_path(module_name)
        return module_path is not None
    
    def _find_module_path(self, module_name: str) -> Optional[Path]:
        """Find file path for a given module name."""
        # Convert module name to potential file paths
        parts = module_name.split('.')
        
        # Try different combinations
        potential_paths = [
            self.target_directory / '/'.join(parts) / '__init__.py',
            self.target_directory / '/'.join(parts[:-1]) / f'{parts[-1]}.py',
            self.target_directory / f'{"/".join(parts)}.py',
        ]
        
        for path in potential_paths:
            if path.exists() and self.should_analyze_file(path):
                return path
        
        return None
    
    def _suggest_circular_import_resolution(self, cycle: List[str]) -> str:
        """Suggest resolution strategies for circular imports."""
        strategies = [
            "Move shared code to a separate module",
            "Use import statements inside functions instead of at module level",
            "Restructure code to eliminate the circular dependency",
            "Consider using dependency injection or factory patterns"
        ]
        
        cycle_str = ' -> '.join(cycle)
        return f"Circular import cycle: {cycle_str}. Suggested resolutions: {'; '.join(strategies)}"