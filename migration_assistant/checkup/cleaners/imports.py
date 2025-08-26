"""
Import Cleaner

Handles import cleanup and optimization using isort and custom logic.
"""

import ast
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import asyncio

from migration_assistant.checkup.cleaners.base import BaseCleaner, CleanupResult
from migration_assistant.checkup.models import (
    AnalysisResults, Issue, IssueType, ImportIssue, ImportCleanup
)


class ImportCleanupResult(CleanupResult):
    """Extended cleanup result for import operations."""
    
    def __init__(self, success: bool = True, message: str = "", 
                 files_modified: Optional[List[Path]] = None,
                 import_cleanups: Optional[List[ImportCleanup]] = None):
        super().__init__(success, message, files_modified)
        self.import_cleanups = import_cleanups or []
        self.changes_made = len(self.import_cleanups)


class ImportCleaner(BaseCleaner):
    """Cleaner for import-related operations."""
    
    def __init__(self, config):
        super().__init__(config)
        self._isort_config = self._get_isort_config()
    
    def _get_isort_config(self) -> Dict[str, Any]:
        """Get isort configuration from config or defaults."""
        default_config = {
            "profile": "black",
            "multi_line_output": 3,
            "line_length": 88,
            "known_first_party": ["migration_assistant"],
            "force_grid_wrap": 0,
            "use_parentheses": True,
            "ensure_newline_before_comments": True,
            "force_sort_within_sections": True,
            "show_diff": True,
        }
        return {**default_config, **self.config.isort_config}
    
    def can_clean_issue(self, issue: Issue) -> bool:
        """Check if this cleaner can fix the issue."""
        return issue.issue_type in [
            IssueType.UNUSED_IMPORT,
            IssueType.CIRCULAR_IMPORT,
        ]
    
    async def clean(self, analysis_results: AnalysisResults) -> ImportCleanupResult:
        """Perform import cleanup based on analysis results."""
        if self.config.dry_run:
            return ImportCleanupResult(
                success=True, 
                message="Dry run - no import changes made"
            )
        
        # Get Python files to clean
        python_files = self._get_python_files()
        
        if not python_files:
            return ImportCleanupResult(
                success=True,
                message="No Python files found to clean imports"
            )
        
        # Create backup if needed
        if not await self.create_backup(python_files):
            return ImportCleanupResult(
                success=False,
                message="Failed to create backup before import cleanup"
            )
        
        import_cleanups = []
        files_modified = []
        
        try:
            # Remove unused imports if enabled
            if self.config.auto_fix_imports:
                unused_result = await self.remove_unused_imports(python_files)
                if unused_result.success:
                    import_cleanups.extend(unused_result.import_cleanups)
                    files_modified.extend(unused_result.files_modified)
            
            # Organize imports with isort
            if self.config.organize_imports or self.config.auto_fix_imports:
                organize_result = await self.optimize_import_order(python_files)
                if organize_result.success:
                    import_cleanups.extend(organize_result.import_cleanups)
                    files_modified.extend(organize_result.files_modified)
            
            # Resolve circular imports (basic resolution)
            circular_imports = [issue for issue in analysis_results.import_issues 
                              if isinstance(issue, ImportIssue) and issue.is_circular]
            if circular_imports:
                circular_result = await self.resolve_circular_imports(circular_imports)
                if circular_result.success:
                    import_cleanups.extend(circular_result.import_cleanups)
                    files_modified.extend(circular_result.files_modified)
            
            return ImportCleanupResult(
                success=True,
                message=f"Successfully cleaned imports in {len(set(files_modified))} files",
                files_modified=list(set(files_modified)),
                import_cleanups=import_cleanups
            )
            
        except Exception as e:
            # Rollback changes on error
            await self.rollback_changes()
            return ImportCleanupResult(
                success=False,
                message=f"Import cleanup failed: {str(e)}"
            )
    
    def _get_python_files(self) -> List[Path]:
        """Get list of Python files to clean imports."""
        python_files = []
        
        for file_path in self.target_directory.rglob("*.py"):
            if self.should_clean_file(file_path):
                python_files.append(file_path)
        
        return python_files
    
    async def remove_unused_imports(self, files: List[Path]) -> ImportCleanupResult:
        """Remove unused imports from files."""
        import_cleanups = []
        files_modified = []
        
        for file_path in files:
            try:
                if not file_path.exists():
                    continue
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Parse AST to analyze imports
                try:
                    tree = ast.parse(original_content)
                except SyntaxError:
                    # Skip files with syntax errors
                    continue
                
                # Find unused imports
                unused_imports = self._find_unused_imports(original_content, tree)
                
                if unused_imports:
                    # Remove unused imports
                    modified_content = self._remove_imports_from_content(
                        original_content, unused_imports
                    )
                    
                    # Write modified content back
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    
                    files_modified.append(file_path)
                    import_cleanups.append(ImportCleanup(
                        file_path=file_path,
                        removed_imports=unused_imports,
                        reorganized_imports=False
                    ))
                
            except Exception as e:
                print(f"Failed to remove unused imports in {file_path}: {e}")
                continue
        
        return ImportCleanupResult(
            success=True,
            message=f"Removed unused imports from {len(files_modified)} files",
            files_modified=files_modified,
            import_cleanups=import_cleanups
        )
    
    def _find_unused_imports(self, content: str, tree: ast.AST) -> List[str]:
        """Find unused imports in the file."""
        # Get all imported names
        imported_names = set()
        import_statements = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imported_names.add(name)
                    import_statements.append((node, alias.name, name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name
                        imported_names.add(name)
                        import_statements.append((node, f"{node.module}.{alias.name}", name))
        
        # Get all used names
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Handle attribute access like module.function
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
        
        # Find unused imports
        unused_imports = []
        for _, full_name, local_name in import_statements:
            if local_name not in used_names:
                # Check if it's used in string annotations or comments
                if not self._is_used_in_strings(content, local_name):
                    unused_imports.append(full_name)
        
        return unused_imports
    
    def _is_used_in_strings(self, content: str, name: str) -> bool:
        """Check if name is used in string literals or comments."""
        # Simple check for usage in strings (type annotations, etc.)
        lines = content.split('\n')
        for line in lines:
            # Check in comments
            if '#' in line and name in line.split('#', 1)[1]:
                return True
            # Check in string literals (basic check)
            if ('"' in line or "'" in line) and name in line:
                # More sophisticated check would parse string literals properly
                return True
        return False
    
    def _remove_imports_from_content(self, content: str, unused_imports: List[str]) -> str:
        """Remove unused imports from file content."""
        lines = content.split('\n')
        modified_lines = []
        
        for line in lines:
            should_remove = False
            
            # Check if line contains an unused import
            for unused_import in unused_imports:
                # Handle different import patterns
                patterns = [
                    rf'^import\s+{re.escape(unused_import)}(\s|$)',
                    rf'^from\s+\S+\s+import\s+.*\b{re.escape(unused_import.split(".")[-1])}\b',
                ]
                
                for pattern in patterns:
                    if re.match(pattern, line.strip()):
                        should_remove = True
                        break
                
                if should_remove:
                    break
            
            if not should_remove:
                modified_lines.append(line)
        
        return '\n'.join(modified_lines)
    
    async def optimize_import_order(self, files: List[Path]) -> ImportCleanupResult:
        """Optimize import order and organization using isort."""
        if not files:
            return ImportCleanupResult(success=True, message="No files to organize")
        
        import_cleanups = []
        files_modified = []
        
        try:
            # Create temporary config file for isort
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
                config_content = self._generate_isort_config()
                f.write(config_content)
                config_file = Path(f.name)
            
            # Process files in batches
            batch_size = 50
            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]
                
                # Run isort on batch with diff to check changes
                cmd = [
                    "python", "-m", "isort",
                    "--settings-path", str(config_file),
                    "--diff",
                    "--check-only",
                ] + [str(f) for f in batch]
                
                # Check for changes first
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.target_directory
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode != 0:  # isort returns non-zero when changes are needed
                    # Parse diff output to track changes
                    diff_output = stdout.decode('utf-8')
                    changes = self._parse_isort_diff(diff_output, batch)
                    
                    # Apply isort formatting
                    cmd_apply = [
                        "python", "-m", "isort",
                        "--settings-path", str(config_file),
                    ] + [str(f) for f in batch]
                    
                    apply_result = await asyncio.create_subprocess_exec(
                        *cmd_apply,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=self.target_directory
                    )
                    await apply_result.communicate()
                    
                    if apply_result.returncode == 0:
                        # Track changes
                        for change in changes:
                            import_cleanups.append(ImportCleanup(
                                file_path=change['file_path'],
                                reorganized_imports=True
                            ))
                            files_modified.append(change['file_path'])
                    else:
                        print(f"isort apply failed for batch: {stderr.decode('utf-8')}")
            
            # Clean up temp config file
            config_file.unlink()
            
            return ImportCleanupResult(
                success=True,
                message=f"Organized imports in {len(files_modified)} files",
                files_modified=files_modified,
                import_cleanups=import_cleanups
            )
            
        except Exception as e:
            return ImportCleanupResult(
                success=False,
                message=f"Import organization failed: {str(e)}"
            )
    
    def _generate_isort_config(self) -> str:
        """Generate isort configuration content."""
        config_lines = ["[settings]"]
        
        for key, value in self._isort_config.items():
            if isinstance(value, str):
                config_lines.append(f'{key}={value}')
            elif isinstance(value, list):
                config_lines.append(f'{key}={",".join(value)}')
            elif isinstance(value, bool):
                config_lines.append(f'{key}={str(value).lower()}')
            else:
                config_lines.append(f'{key}={value}')
        
        return "\n".join(config_lines)
    
    def _parse_isort_diff(self, diff_output: str, files: List[Path]) -> List[Dict[str, Any]]:
        """Parse isort diff output to extract changes."""
        changes = []
        
        if not diff_output.strip():
            return changes
        
        # isort diff format: "Fixing {filename}"
        for line in diff_output.split('\n'):
            if line.startswith('Fixing '):
                filename = line.replace('Fixing ', '').strip()
                
                # Find matching file path
                for f in files:
                    if str(f).endswith(filename) or f.name == filename:
                        changes.append({
                            'file_path': f,
                            'description': f'Organized imports in {filename}'
                        })
                        break
        
        return changes
    
    async def resolve_circular_imports(self, circular_imports: List[ImportIssue]) -> ImportCleanupResult:
        """Resolve circular import issues with basic strategies."""
        import_cleanups = []
        files_modified = []
        
        # Group circular imports by dependency chain
        circular_groups = self._group_circular_imports(circular_imports)
        
        for group in circular_groups:
            try:
                # Apply basic resolution strategies
                resolved = await self._resolve_circular_group(group)
                if resolved:
                    import_cleanups.extend(resolved['cleanups'])
                    files_modified.extend(resolved['files'])
            except Exception as e:
                print(f"Failed to resolve circular import group: {e}")
                continue
        
        return ImportCleanupResult(
            success=True,
            message=f"Attempted to resolve circular imports in {len(files_modified)} files",
            files_modified=files_modified,
            import_cleanups=import_cleanups
        )
    
    def _group_circular_imports(self, circular_imports: List[ImportIssue]) -> List[List[ImportIssue]]:
        """Group circular imports by dependency chains."""
        groups = []
        processed = set()
        
        for import_issue in circular_imports:
            if id(import_issue) in processed:
                continue
            
            # Find all imports in the same circular chain
            chain = [import_issue]
            processed.add(id(import_issue))
            
            # Simple grouping by dependency chain
            for other_import in circular_imports:
                if (id(other_import) not in processed and 
                    any(dep in other_import.dependency_chain for dep in import_issue.dependency_chain)):
                    chain.append(other_import)
                    processed.add(id(other_import))
            
            if len(chain) > 1:
                groups.append(chain)
        
        return groups
    
    async def _resolve_circular_group(self, group: List[ImportIssue]) -> Optional[Dict[str, Any]]:
        """Resolve a group of circular imports."""
        # Basic resolution strategy: suggest moving imports to function level
        cleanups = []
        files = []
        
        for import_issue in group:
            try:
                file_path = import_issue.file_path
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Add comment suggesting resolution
                modified_content = self._add_circular_import_comment(
                    content, import_issue.import_name
                )
                
                if modified_content != content:
                    # Write modified content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    
                    files.append(file_path)
                    cleanups.append(ImportCleanup(
                        file_path=file_path,
                        circular_imports_resolved=[import_issue.import_name]
                    ))
                
            except Exception as e:
                print(f"Failed to resolve circular import in {import_issue.file_path}: {e}")
                continue
        
        return {'cleanups': cleanups, 'files': files} if cleanups else None
    
    def _add_circular_import_comment(self, content: str, import_name: str) -> str:
        """Add comment about circular import resolution."""
        lines = content.split('\n')
        
        # Find the problematic import line
        for i, line in enumerate(lines):
            if import_name in line and ('import' in line):
                # Add comment above the import
                comment = f"# TODO: Circular import detected for {import_name}. Consider moving to function level."
                if i > 0 and not lines[i-1].strip().startswith('#'):
                    lines.insert(i, comment)
                    return '\n'.join(lines)
                break
        
        return content