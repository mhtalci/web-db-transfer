"""
Code Formatter

Handles code formatting using black, isort, and other tools.
"""

import ast
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import asyncio

from migration_assistant.checkup.cleaners.base import BaseCleaner, CleanupResult
from migration_assistant.checkup.models import (
    AnalysisResults, Issue, IssueType, FormattingChange, QualityIssue
)


class FormattingResult(CleanupResult):
    """Extended cleanup result for formatting operations."""
    
    def __init__(self, success: bool = True, message: str = "", 
                 files_modified: Optional[List[Path]] = None,
                 formatting_changes: Optional[List[FormattingChange]] = None):
        super().__init__(success, message, files_modified)
        self.formatting_changes = formatting_changes or []
        self.changes_made = len(self.formatting_changes)


class CodeFormatter(BaseCleaner):
    """Cleaner for code formatting operations."""
    
    def __init__(self, config):
        super().__init__(config)
        self._black_config = self._get_black_config()
        self._isort_config = self._get_isort_config()
    
    def _get_black_config(self) -> Dict[str, Any]:
        """Get black configuration from config or defaults."""
        default_config = {
            "line_length": 88,
            "target_version": ["py311"],
            "skip_string_normalization": False,
            "skip_magic_trailing_comma": False,
        }
        return {**default_config, **self.config.black_config}
    
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
        }
        return {**default_config, **self.config.isort_config}
    
    def can_clean_issue(self, issue: Issue) -> bool:
        """Check if this cleaner can fix the issue."""
        return issue.issue_type in [
            IssueType.STYLE_VIOLATION,
            IssueType.CODE_SMELL,  # Some code smells can be fixed by formatting
        ]
    
    async def clean(self, analysis_results: AnalysisResults) -> FormattingResult:
        """Perform formatting cleanup based on analysis results."""
        if self.config.dry_run:
            return FormattingResult(
                success=True, 
                message="Dry run - no formatting changes made"
            )
        
        # Get Python files to format
        python_files = self._get_python_files()
        
        if not python_files:
            return FormattingResult(
                success=True,
                message="No Python files found to format"
            )
        
        # Create backup if needed
        if not await self.create_backup(python_files):
            return FormattingResult(
                success=False,
                message="Failed to create backup before formatting"
            )
        
        formatting_changes = []
        files_modified = []
        
        try:
            # Apply black formatting
            if self.config.auto_format:
                black_result = await self.format_with_black(python_files)
                if black_result.success:
                    formatting_changes.extend(black_result.formatting_changes)
                    files_modified.extend(black_result.files_modified)
            
            # Standardize docstrings
            docstring_result = await self.standardize_docstrings(python_files)
            if docstring_result.success:
                formatting_changes.extend(docstring_result.formatting_changes)
                files_modified.extend(docstring_result.files_modified)
            
            # Standardize type hints if enabled
            if self.config.check_type_hints:
                type_hint_result = await self.standardize_type_hints(python_files)
                if type_hint_result.success:
                    formatting_changes.extend(type_hint_result.formatting_changes)
                    files_modified.extend(type_hint_result.files_modified)
            
            return FormattingResult(
                success=True,
                message=f"Successfully formatted {len(set(files_modified))} files",
                files_modified=list(set(files_modified)),
                formatting_changes=formatting_changes
            )
            
        except Exception as e:
            # Rollback changes on error
            await self.rollback_changes()
            return FormattingResult(
                success=False,
                message=f"Formatting failed: {str(e)}"
            )
    
    def _get_python_files(self) -> List[Path]:
        """Get list of Python files to format."""
        python_files = []
        
        for file_path in self.target_directory.rglob("*.py"):
            if self.should_clean_file(file_path):
                python_files.append(file_path)
        
        return python_files
    
    async def format_with_black(self, files: List[Path]) -> FormattingResult:
        """Format files using black."""
        if not files:
            return FormattingResult(success=True, message="No files to format")
        
        formatting_changes = []
        files_modified = []
        
        try:
            # Create temporary config file for black
            with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
                config_content = self._generate_black_config()
                f.write(config_content)
                config_file = Path(f.name)
            
            # Process files in batches to avoid command line length limits
            batch_size = 50
            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]
                
                # Run black on batch
                cmd = [
                    "python", "-m", "black",
                    "--config", str(config_file),
                    "--diff",  # Get diff to track changes
                ] + [str(f) for f in batch]
                
                # Get diff first to track changes
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.target_directory
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    # Parse diff output to track changes
                    diff_output = stdout.decode('utf-8')
                    changes = self._parse_black_diff(diff_output, batch)
                    formatting_changes.extend(changes)
                    
                    # Now actually apply formatting
                    cmd_apply = [
                        "python", "-m", "black",
                        "--config", str(config_file),
                    ] + [str(f) for f in batch]
                    
                    apply_result = await asyncio.create_subprocess_exec(
                        *cmd_apply,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=self.target_directory
                    )
                    await apply_result.communicate()
                    
                    if apply_result.returncode == 0:
                        files_modified.extend(batch)
                    else:
                        # Log error but continue with other files
                        print(f"Black formatting failed for batch: {stderr.decode('utf-8')}")
                else:
                    print(f"Black diff failed: {stderr.decode('utf-8')}")
            
            # Clean up temp config file
            config_file.unlink()
            
            return FormattingResult(
                success=True,
                message=f"Black formatting applied to {len(files_modified)} files",
                files_modified=files_modified,
                formatting_changes=formatting_changes
            )
            
        except Exception as e:
            return FormattingResult(
                success=False,
                message=f"Black formatting failed: {str(e)}"
            )
    
    def _generate_black_config(self) -> str:
        """Generate black configuration content."""
        config_lines = ["[tool.black]"]
        
        for key, value in self._black_config.items():
            if isinstance(value, str):
                config_lines.append(f'{key} = "{value}"')
            elif isinstance(value, list):
                formatted_list = "[" + ", ".join(f'"{v}"' for v in value) + "]"
                config_lines.append(f'{key} = {formatted_list}')
            elif isinstance(value, bool):
                config_lines.append(f'{key} = {str(value).lower()}')
            else:
                config_lines.append(f'{key} = {value}')
        
        return "\n".join(config_lines)
    
    def _parse_black_diff(self, diff_output: str, files: List[Path]) -> List[FormattingChange]:
        """Parse black diff output to extract formatting changes."""
        changes = []
        
        if not diff_output.strip():
            return changes
        
        # Split diff by file
        file_diffs = re.split(r'^--- ', diff_output, flags=re.MULTILINE)[1:]
        
        for file_diff in file_diffs:
            lines = file_diff.split('\n')
            if not lines:
                continue
            
            # Extract filename from first line
            filename_match = re.match(r'(.+?)\s+\d{4}-\d{2}-\d{2}', lines[0])
            if not filename_match:
                continue
            
            filename = filename_match.group(1)
            file_path = None
            
            # Find matching file path
            for f in files:
                if str(f).endswith(filename) or f.name == filename:
                    file_path = f
                    break
            
            if not file_path:
                continue
            
            # Count changed lines
            changed_lines = sum(1 for line in lines if line.startswith(('+', '-')) 
                              and not line.startswith(('+++', '---')))
            
            if changed_lines > 0:
                changes.append(FormattingChange(
                    file_path=file_path,
                    change_type="black",
                    lines_changed=changed_lines,
                    description=f"Applied black formatting ({changed_lines} lines changed)"
                ))
        
        return changes
    
    async def standardize_docstrings(self, files: List[Path]) -> FormattingResult:
        """Standardize docstring formats across files."""
        formatting_changes = []
        files_modified = []
        
        for file_path in files:
            try:
                if not file_path.exists():
                    continue
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Parse AST to find docstrings
                try:
                    tree = ast.parse(original_content)
                except SyntaxError:
                    # Skip files with syntax errors
                    continue
                
                # Standardize docstrings
                modified_content, changes_made = self._standardize_docstrings_in_content(
                    original_content, tree
                )
                
                if changes_made > 0:
                    # Write modified content back
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    
                    files_modified.append(file_path)
                    formatting_changes.append(FormattingChange(
                        file_path=file_path,
                        change_type="docstring",
                        lines_changed=changes_made,
                        description=f"Standardized {changes_made} docstrings"
                    ))
                
            except Exception as e:
                print(f"Failed to standardize docstrings in {file_path}: {e}")
                continue
        
        return FormattingResult(
            success=True,
            message=f"Standardized docstrings in {len(files_modified)} files",
            files_modified=files_modified,
            formatting_changes=formatting_changes
        )
    
    def _standardize_docstrings_in_content(self, content: str, tree: ast.AST) -> Tuple[str, int]:
        """Standardize docstrings in file content."""
        lines = content.split('\n')
        changes_made = 0
        
        # Find all docstrings in the AST
        docstring_locations = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                if (node.body and 
                    isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and 
                    isinstance(node.body[0].value.value, str)):
                    
                    docstring_node = node.body[0]
                    docstring_locations.append({
                        'node': node,
                        'docstring_node': docstring_node,
                        'start_line': docstring_node.lineno - 1,  # Convert to 0-based
                        'end_line': docstring_node.end_lineno - 1 if docstring_node.end_lineno else docstring_node.lineno - 1,
                        'docstring': docstring_node.value.value
                    })
        
        # Process docstrings from bottom to top to maintain line numbers
        docstring_locations.sort(key=lambda x: x['start_line'], reverse=True)
        
        for doc_info in docstring_locations:
            start_line = doc_info['start_line']
            end_line = doc_info['end_line']
            original_docstring = doc_info['docstring']
            
            # Standardize the docstring
            standardized = self._standardize_single_docstring(
                original_docstring, 
                doc_info['node']
            )
            
            if standardized != original_docstring:
                # Calculate indentation from the line before docstring
                indent = ""
                if start_line > 0:
                    prev_line = lines[start_line - 1] if start_line - 1 < len(lines) else ""
                    # Get indentation from function/class definition
                    base_indent = len(prev_line) - len(prev_line.lstrip())
                    indent = " " * (base_indent + 4)  # Add 4 spaces for docstring
                
                # Format standardized docstring with proper indentation
                docstring_lines = self._format_docstring_lines(standardized, indent)
                
                # Replace lines
                lines[start_line:end_line + 1] = docstring_lines
                changes_made += 1
        
        return '\n'.join(lines), changes_made
    
    def _standardize_single_docstring(self, docstring: str, node: ast.AST) -> str:
        """Standardize a single docstring."""
        # Clean up the docstring
        cleaned = docstring.strip()
        
        if not cleaned:
            return docstring
        
        # For functions, ensure it starts with a verb and describes what it does
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # If it's a single line, ensure it ends with a period
            if '\n' not in cleaned and not cleaned.endswith('.'):
                cleaned += '.'
            
            # Ensure first letter is capitalized
            if cleaned and cleaned[0].islower():
                cleaned = cleaned[0].upper() + cleaned[1:]
        
        # For classes, ensure proper format
        elif isinstance(node, ast.ClassDef):
            # Ensure first letter is capitalized
            if cleaned and cleaned[0].islower():
                cleaned = cleaned[0].upper() + cleaned[1:]
            
            # If single line, ensure it ends with a period
            if '\n' not in cleaned and not cleaned.endswith('.'):
                cleaned += '.'
        
        return cleaned
    
    def _format_docstring_lines(self, docstring: str, indent: str) -> List[str]:
        """Format docstring with proper indentation and quotes."""
        if '\n' in docstring:
            # Multi-line docstring
            lines = [f'{indent}"""']
            for line in docstring.split('\n'):
                if line.strip():
                    lines.append(f'{indent}{line}')
                else:
                    lines.append('')
            lines.append(f'{indent}"""')
        else:
            # Single-line docstring
            lines = [f'{indent}"""{docstring}"""']
        
        return lines
    
    async def standardize_type_hints(self, files: List[Path]) -> FormattingResult:
        """Standardize type hints across files."""
        formatting_changes = []
        files_modified = []
        
        for file_path in files:
            try:
                if not file_path.exists():
                    continue
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Parse AST to analyze type hints
                try:
                    tree = ast.parse(original_content)
                except SyntaxError:
                    # Skip files with syntax errors
                    continue
                
                # Standardize type hints
                modified_content, changes_made = self._standardize_type_hints_in_content(
                    original_content, tree
                )
                
                if changes_made > 0:
                    # Write modified content back
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    
                    files_modified.append(file_path)
                    formatting_changes.append(FormattingChange(
                        file_path=file_path,
                        change_type="type_hints",
                        lines_changed=changes_made,
                        description=f"Standardized {changes_made} type hints"
                    ))
                
            except Exception as e:
                print(f"Failed to standardize type hints in {file_path}: {e}")
                continue
        
        return FormattingResult(
            success=True,
            message=f"Standardized type hints in {len(files_modified)} files",
            files_modified=files_modified,
            formatting_changes=formatting_changes
        )
    
    def _standardize_type_hints_in_content(self, content: str, tree: ast.AST) -> Tuple[str, int]:
        """Standardize type hints in file content."""
        lines = content.split('\n')
        changes_made = 0
        
        # Find functions and methods that need type hints
        functions_to_update = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if function needs type hint improvements
                improvements = self._analyze_function_type_hints(node, lines)
                if improvements:
                    functions_to_update.append({
                        'node': node,
                        'improvements': improvements
                    })
        
        # Apply improvements from bottom to top to maintain line numbers
        functions_to_update.sort(key=lambda x: x['node'].lineno, reverse=True)
        
        for func_info in functions_to_update:
            node = func_info['node']
            improvements = func_info['improvements']
            
            # Apply each improvement
            for improvement in improvements:
                if improvement['type'] == 'add_return_type':
                    lines = self._add_return_type_hint(lines, node, improvement['hint'])
                    changes_made += 1
                elif improvement['type'] == 'add_parameter_type':
                    lines = self._add_parameter_type_hint(
                        lines, node, improvement['param'], improvement['hint']
                    )
                    changes_made += 1
                elif improvement['type'] == 'standardize_type':
                    lines = self._standardize_existing_type_hint(
                        lines, node, improvement['old_hint'], improvement['new_hint']
                    )
                    changes_made += 1
        
        return '\n'.join(lines), changes_made
    
    def _analyze_function_type_hints(self, node: ast.FunctionDef, lines: List[str]) -> List[Dict[str, Any]]:
        """Analyze function for type hint improvements."""
        improvements = []
        
        # Check return type annotation
        if not node.returns:
            # Suggest return type based on function analysis
            suggested_return_type = self._suggest_return_type(node, lines)
            if suggested_return_type:
                improvements.append({
                    'type': 'add_return_type',
                    'hint': suggested_return_type
                })
        else:
            # Check if existing return type can be standardized
            current_return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
            standardized_type = self._standardize_type_annotation(current_return_type)
            if standardized_type != current_return_type:
                improvements.append({
                    'type': 'standardize_type',
                    'old_hint': current_return_type,
                    'new_hint': standardized_type
                })
        
        # Check parameter type annotations
        for arg in node.args.args:
            if not arg.annotation and arg.arg != 'self' and arg.arg != 'cls':
                # Suggest parameter type based on usage analysis
                suggested_type = self._suggest_parameter_type(node, arg.arg, lines)
                if suggested_type:
                    improvements.append({
                        'type': 'add_parameter_type',
                        'param': arg.arg,
                        'hint': suggested_type
                    })
            elif arg.annotation:
                # Check if existing type can be standardized
                current_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
                standardized_type = self._standardize_type_annotation(current_type)
                if standardized_type != current_type:
                    improvements.append({
                        'type': 'standardize_type',
                        'old_hint': current_type,
                        'new_hint': standardized_type
                    })
        
        return improvements
    
    def _suggest_return_type(self, node: ast.FunctionDef, lines: List[str]) -> Optional[str]:
        """Suggest return type based on function analysis."""
        # Analyze return statements
        return_types = set()
        
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                if child.value is None:
                    return_types.add('None')
                elif isinstance(child.value, ast.Constant):
                    if isinstance(child.value.value, bool):
                        return_types.add('bool')
                    elif isinstance(child.value.value, int):
                        return_types.add('int')
                    elif isinstance(child.value.value, float):
                        return_types.add('float')
                    elif isinstance(child.value.value, str):
                        return_types.add('str')
                elif isinstance(child.value, ast.List):
                    return_types.add('List')
                elif isinstance(child.value, ast.Dict):
                    return_types.add('Dict')
                elif isinstance(child.value, ast.Tuple):
                    return_types.add('Tuple')
        
        # Simple heuristics for return type suggestion
        if len(return_types) == 1:
            return_type = list(return_types)[0]
            if return_type in ['bool', 'int', 'float', 'str', 'None']:
                return return_type
            elif return_type == 'List':
                return 'List[Any]'
            elif return_type == 'Dict':
                return 'Dict[str, Any]'
            elif return_type == 'Tuple':
                return 'Tuple[Any, ...]'
        elif 'None' in return_types and len(return_types) == 2:
            # Optional type
            other_type = next(t for t in return_types if t != 'None')
            if other_type in ['bool', 'int', 'float', 'str']:
                return f'Optional[{other_type}]'
        
        return None
    
    def _suggest_parameter_type(self, node: ast.FunctionDef, param_name: str, lines: List[str]) -> Optional[str]:
        """Suggest parameter type based on usage analysis."""
        # Analyze parameter usage in function body
        usage_patterns = set()
        
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == param_name:
                # Check the context of usage
                parent = getattr(child, 'parent', None)
                if isinstance(parent, ast.Call):
                    usage_patterns.add('callable')
                elif isinstance(parent, ast.Subscript):
                    usage_patterns.add('subscriptable')
                elif isinstance(parent, ast.Attribute):
                    usage_patterns.add('has_attributes')
        
        # Simple heuristics for parameter type suggestion
        if 'subscriptable' in usage_patterns:
            return 'List[Any]'  # Could be List, Dict, etc.
        elif 'callable' in usage_patterns:
            return 'Callable'
        elif 'has_attributes' in usage_patterns:
            return 'Any'  # Could be any object with attributes
        
        # Check parameter name patterns
        if param_name.endswith('_path') or param_name == 'path':
            return 'Path'
        elif param_name.endswith('_file') or param_name == 'file':
            return 'Path'
        elif param_name.endswith('_list') or param_name.endswith('s'):
            return 'List[Any]'
        elif param_name.endswith('_dict') or param_name == 'config':
            return 'Dict[str, Any]'
        elif param_name.endswith('_count') or param_name.endswith('_size'):
            return 'int'
        elif param_name.startswith('is_') or param_name.startswith('has_'):
            return 'bool'
        
        return None
    
    def _standardize_type_annotation(self, type_annotation: str) -> str:
        """Standardize type annotation format."""
        # Common standardizations
        standardizations = {
            # Use modern typing syntax
            'typing.List': 'List',
            'typing.Dict': 'Dict',
            'typing.Tuple': 'Tuple',
            'typing.Set': 'Set',
            'typing.Optional': 'Optional',
            'typing.Union': 'Union',
            'typing.Callable': 'Callable',
            'typing.Any': 'Any',
            
            # Use built-in types where possible (Python 3.9+)
            'List[str]': 'list[str]',
            'List[int]': 'list[int]',
            'Dict[str, Any]': 'dict[str, Any]',
            'Tuple[str, ...]': 'tuple[str, ...]',
            'Set[str]': 'set[str]',
            
            # Standardize None
            'typing.None': 'None',
            'type(None)': 'None',
        }
        
        # Apply standardizations
        standardized = type_annotation
        for old, new in standardizations.items():
            standardized = standardized.replace(old, new)
        
        # Clean up extra spaces
        standardized = re.sub(r'\s+', ' ', standardized.strip())
        
        return standardized
    
    def _add_return_type_hint(self, lines: List[str], node: ast.FunctionDef, return_type: str) -> List[str]:
        """Add return type hint to function definition."""
        func_line_idx = node.lineno - 1  # Convert to 0-based index
        
        if func_line_idx < len(lines):
            line = lines[func_line_idx]
            
            # Find the colon that ends the function definition
            colon_idx = line.rfind(':')
            if colon_idx != -1:
                # Insert return type before the colon
                new_line = line[:colon_idx] + f' -> {return_type}' + line[colon_idx:]
                lines[func_line_idx] = new_line
        
        return lines
    
    def _add_parameter_type_hint(self, lines: List[str], node: ast.FunctionDef, param_name: str, param_type: str) -> List[str]:
        """Add type hint to function parameter."""
        func_line_idx = node.lineno - 1  # Convert to 0-based index
        
        if func_line_idx < len(lines):
            line = lines[func_line_idx]
            
            # Find the parameter in the function definition
            # This is a simple approach - more sophisticated parsing might be needed
            param_pattern = rf'\b{re.escape(param_name)}\b'
            match = re.search(param_pattern, line)
            
            if match:
                # Insert type hint after parameter name
                start_pos = match.end()
                # Check if there's already a type hint or default value
                if ':' not in line[start_pos:line.find(',', start_pos)] and '=' not in line[start_pos:line.find(',', start_pos)]:
                    # Add type hint
                    new_line = line[:start_pos] + f': {param_type}' + line[start_pos:]
                    lines[func_line_idx] = new_line
        
        return lines
    
    def _standardize_existing_type_hint(self, lines: List[str], node: ast.FunctionDef, old_hint: str, new_hint: str) -> List[str]:
        """Standardize existing type hint."""
        func_line_idx = node.lineno - 1  # Convert to 0-based index
        
        if func_line_idx < len(lines):
            line = lines[func_line_idx]
            
            # Replace old hint with new hint
            if old_hint in line:
                new_line = line.replace(old_hint, new_hint)
                lines[func_line_idx] = new_line
        
        return lines