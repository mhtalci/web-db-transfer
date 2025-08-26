"""
Code Quality Analyzer

Analyzes Python code for syntax errors, style violations, complexity issues,
and common code smells using AST parsing and integration with linting tools.
"""

import ast
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re
import logging

from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import (
    QualityIssue, IssueSeverity, IssueType, CheckupConfig
)

logger = logging.getLogger(__name__)


class CodeQualityAnalyzer(BaseAnalyzer):
    """Analyzer for code quality issues including syntax, style, and complexity."""
    
    def __init__(self, config: CheckupConfig):
        """Initialize the quality analyzer."""
        super().__init__(config)
        self.syntax_errors = []
        self.style_violations = []
        self.complexity_issues = []
        self.code_smells = []
    
    def get_supported_file_types(self) -> List[str]:
        """Return supported file types."""
        return ['.py', '.pyx']
    
    async def analyze(self) -> List[QualityIssue]:
        """
        Perform comprehensive code quality analysis.
        
        Returns:
            List of quality issues found
        """
        await self.pre_analyze()
        
        all_issues = []
        python_files = self.get_python_files()
        
        logger.info(f"Analyzing {len(python_files)} Python files for quality issues")
        
        # Run batch analysis with external tools first
        if self.config.check_type_hints:
            mypy_issues = await self.analyze_with_mypy(python_files)
            all_issues.extend(mypy_issues)
        
        # Run flake8 on all files at once for better performance
        flake8_issues = await self.analyze_with_flake8_batch(python_files)
        all_issues.extend(flake8_issues)
        
        # Then run per-file analysis
        for file_path in python_files:
            try:
                # Analyze syntax errors
                syntax_issues = await self.analyze_syntax_errors(file_path)
                all_issues.extend(syntax_issues)
                
                # Only proceed with other analysis if no syntax errors
                if not syntax_issues:
                    # Analyze complexity
                    complexity_issues = await self.analyze_complexity(file_path)
                    all_issues.extend(complexity_issues)
                    
                    # Analyze code smells
                    smell_issues = await self.analyze_code_smells(file_path)
                    all_issues.extend(smell_issues)
                
            except Exception as e:
                logger.error(f"Error analyzing {file_path}: {e}")
                # Create an issue for the analysis error
                error_issue = self._create_quality_issue(
                    file_path=file_path,
                    issue_type=IssueType.SYNTAX_ERROR,
                    severity=IssueSeverity.HIGH,
                    message=f"Analysis error: {str(e)}",
                    description=f"Failed to analyze file due to: {str(e)}",
                    tool_name="quality_analyzer"
                )
                all_issues.append(error_issue)
        
        # Aggregate and normalize results
        all_issues = self._aggregate_and_normalize_issues(all_issues)
        
        # Update metrics
        self._update_quality_metrics(all_issues)
        
        await self.post_analyze(all_issues)
        return all_issues
    
    async def analyze_syntax_errors(self, file_path: Path) -> List[QualityIssue]:
        """
        Analyze file for syntax errors using Python's AST module.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of syntax error issues
        """
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to parse the AST
            ast.parse(content, filename=str(file_path))
            
        except SyntaxError as e:
            issue = self._create_quality_issue(
                file_path=file_path,
                issue_type=IssueType.SYNTAX_ERROR,
                severity=IssueSeverity.CRITICAL,
                message=f"Syntax error: {e.msg}",
                description=f"Python syntax error at line {e.lineno}: {e.msg}",
                line_number=e.lineno,
                suggestion="Fix the syntax error to make the code parseable",
                tool_name="ast"
            )
            issues.append(issue)
            
        except UnicodeDecodeError as e:
            issue = self._create_quality_issue(
                file_path=file_path,
                issue_type=IssueType.SYNTAX_ERROR,
                severity=IssueSeverity.HIGH,
                message="File encoding error",
                description=f"Unable to decode file: {str(e)}",
                suggestion="Ensure file is saved with UTF-8 encoding",
                tool_name="ast"
            )
            issues.append(issue)
            
        except Exception as e:
            logger.warning(f"Unexpected error parsing {file_path}: {e}")
        
        return issues
    
    async def analyze_style_violations(self, file_path: Path) -> List[QualityIssue]:
        """
        Analyze file for PEP 8 style violations using flake8.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of style violation issues
        """
        issues = []
        
        try:
            # Run flake8 on the file
            cmd = [
                sys.executable, '-m', 'flake8',
                '--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s',
                str(file_path)
            ]
            
            # Add flake8 config if specified
            if self.config.flake8_config:
                for key, value in self.config.flake8_config.items():
                    if key == 'max-line-length':
                        cmd.extend(['--max-line-length', str(value)])
                    elif key == 'ignore':
                        cmd.extend(['--ignore', ','.join(value) if isinstance(value, list) else str(value)])
                    elif key == 'select':
                        cmd.extend(['--select', ','.join(value) if isinstance(value, list) else str(value)])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # No violations found
                return issues
            
            # Parse flake8 output
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    issue = self._parse_flake8_output(line, file_path)
                    if issue:
                        issues.append(issue)
                        
        except subprocess.TimeoutExpired:
            logger.warning(f"Flake8 timeout for {file_path}")
        except FileNotFoundError:
            logger.warning("Flake8 not found, skipping style analysis")
        except Exception as e:
            logger.warning(f"Error running flake8 on {file_path}: {e}")
        
        return issues
    
    async def analyze_complexity(self, file_path: Path) -> List[QualityIssue]:
        """
        Analyze file for complexity issues.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of complexity issues
        """
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            # Analyze cyclomatic complexity
            complexity_issues = self._analyze_cyclomatic_complexity(tree, file_path)
            issues.extend(complexity_issues)
            
            # Analyze nesting depth
            nesting_issues = self._analyze_nesting_depth(tree, file_path)
            issues.extend(nesting_issues)
            
            # Analyze function/class length
            length_issues = self._analyze_code_length(tree, file_path, content)
            issues.extend(length_issues)
            
        except Exception as e:
            logger.warning(f"Error analyzing complexity for {file_path}: {e}")
        
        return issues
    
    async def analyze_code_smells(self, file_path: Path) -> List[QualityIssue]:
        """
        Analyze file for common code smells and anti-patterns.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of code smell issues
        """
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            # Check for various code smells
            issues.extend(self._check_long_parameter_lists(tree, file_path))
            issues.extend(self._check_duplicate_code_patterns(tree, file_path))
            issues.extend(self._check_magic_numbers(tree, file_path))
            issues.extend(self._check_empty_except_blocks(tree, file_path))
            issues.extend(self._check_unused_variables(tree, file_path, content))
            
        except Exception as e:
            logger.warning(f"Error analyzing code smells for {file_path}: {e}")
        
        return issues
    
    def _create_quality_issue(
        self,
        file_path: Path,
        issue_type: IssueType,
        severity: IssueSeverity,
        message: str,
        description: str,
        line_number: Optional[int] = None,
        suggestion: Optional[str] = None,
        confidence: float = 1.0,
        rule_name: Optional[str] = None,
        tool_name: Optional[str] = None
    ) -> QualityIssue:
        """Create a quality issue instance."""
        return QualityIssue(
            file_path=file_path,
            line_number=line_number,
            severity=severity,
            issue_type=issue_type,
            message=message,
            description=description,
            suggestion=suggestion,
            confidence=confidence,
            rule_name=rule_name,
            tool_name=tool_name
        )
    
    def _parse_flake8_output(self, line: str, file_path: Path) -> Optional[QualityIssue]:
        """Parse a line of flake8 output into a QualityIssue."""
        try:
            # Format: path:row:col:code:text
            parts = line.split(':', 4)
            if len(parts) < 5:
                return None
            
            line_num = int(parts[1])
            col_num = int(parts[2])
            error_code = parts[3]
            error_text = parts[4]
            
            # Determine severity based on error code
            severity = self._get_flake8_severity(error_code)
            
            return self._create_quality_issue(
                file_path=file_path,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=severity,
                message=f"{error_code}: {error_text}",
                description=f"Style violation at line {line_num}, column {col_num}: {error_text}",
                line_number=line_num,
                rule_name=error_code,
                tool_name="flake8",
                suggestion=self._get_flake8_suggestion(error_code)
            )
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse flake8 output: {line} - {e}")
            return None
    
    def _get_flake8_severity(self, error_code: str) -> IssueSeverity:
        """Determine severity based on flake8 error code."""
        if error_code.startswith('E9') or error_code.startswith('F'):
            return IssueSeverity.HIGH
        elif error_code.startswith('E1') or error_code.startswith('E2'):
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW
    
    def _get_flake8_suggestion(self, error_code: str) -> Optional[str]:
        """Get suggestion for fixing flake8 error."""
        suggestions = {
            'E501': 'Break long lines or use parentheses for line continuation',
            'E302': 'Add two blank lines before class or function definition',
            'E303': 'Remove extra blank lines',
            'E401': 'Put imports on separate lines',
            'F401': 'Remove unused import',
            'F841': 'Remove unused variable or use it',
            'W291': 'Remove trailing whitespace',
            'W292': 'Add newline at end of file',
        }
        return suggestions.get(error_code)
    
    def _analyze_cyclomatic_complexity(self, tree: ast.AST, file_path: Path) -> List[QualityIssue]:
        """Analyze cyclomatic complexity of functions and methods."""
        issues = []
        
        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.complexity_issues = []
            
            def visit_FunctionDef(self, node):
                complexity = self._calculate_cyclomatic_complexity(node)
                cognitive_complexity = self._calculate_cognitive_complexity(node)
                maintainability_index = self._calculate_maintainability_index(node, file_path)
                
                # Check cyclomatic complexity
                if complexity > self.config.max_complexity:
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.COMPLEXITY,
                        severity=IssueSeverity.MEDIUM if complexity <= 15 else IssueSeverity.HIGH,
                        message=f"High cyclomatic complexity: {complexity}",
                        description=f"Function '{node.name}' has cyclomatic complexity of {complexity}, "
                                   f"which exceeds the threshold of {self.config.max_complexity}",
                        line_number=node.lineno,
                        suggestion="Consider breaking this function into smaller functions",
                        rule_name="cyclomatic_complexity"
                    )
                    self.complexity_issues.append(issue)
                
                # Check cognitive complexity (higher threshold)
                if cognitive_complexity > 15:
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.COMPLEXITY,
                        severity=IssueSeverity.MEDIUM if cognitive_complexity <= 25 else IssueSeverity.HIGH,
                        message=f"High cognitive complexity: {cognitive_complexity}",
                        description=f"Function '{node.name}' has cognitive complexity of {cognitive_complexity}, "
                                   f"which makes it difficult to understand",
                        line_number=node.lineno,
                        suggestion="Simplify the logic flow and reduce nested conditions",
                        rule_name="cognitive_complexity"
                    )
                    self.complexity_issues.append(issue)
                
                # Check maintainability index (lower is worse)
                if maintainability_index < 20:
                    severity = IssueSeverity.HIGH if maintainability_index < 10 else IssueSeverity.MEDIUM
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.COMPLEXITY,
                        severity=severity,
                        message=f"Low maintainability index: {maintainability_index:.1f}",
                        description=f"Function '{node.name}' has maintainability index of {maintainability_index:.1f}, "
                                   f"indicating it may be difficult to maintain",
                        line_number=node.lineno,
                        suggestion="Reduce complexity, improve comments, and consider refactoring",
                        rule_name="maintainability_index"
                    )
                    self.complexity_issues.append(issue)
                
                self.generic_visit(node)
            
            def visit_AsyncFunctionDef(self, node):
                self.visit_FunctionDef(node)
            
            def _calculate_cyclomatic_complexity(self, node):
                """Calculate cyclomatic complexity for a function."""
                complexity = 1  # Base complexity
                
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                        complexity += 1
                    elif isinstance(child, ast.ExceptHandler):
                        complexity += 1
                    elif isinstance(child, (ast.And, ast.Or)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1
                    elif isinstance(child, ast.ListComp):
                        # List comprehensions add complexity
                        complexity += 1
                        for generator in child.generators:
                            if generator.ifs:
                                complexity += len(generator.ifs)
                    elif isinstance(child, (ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                        complexity += 1
                        for generator in child.generators:
                            if generator.ifs:
                                complexity += len(generator.ifs)
                
                return complexity
            
            def _calculate_cognitive_complexity(self, node):
                """Calculate cognitive complexity (focuses on readability)."""
                complexity = 0
                nesting_level = 0
                
                class CognitiveVisitor(ast.NodeVisitor):
                    def __init__(self):
                        self.complexity = 0
                        self.nesting = 0
                    
                    def visit_If(self, node):
                        self.complexity += 1 + self.nesting
                        self.nesting += 1
                        self.generic_visit(node)
                        self.nesting -= 1
                    
                    def visit_While(self, node):
                        self.complexity += 1 + self.nesting
                        self.nesting += 1
                        self.generic_visit(node)
                        self.nesting -= 1
                    
                    def visit_For(self, node):
                        self.complexity += 1 + self.nesting
                        self.nesting += 1
                        self.generic_visit(node)
                        self.nesting -= 1
                    
                    def visit_ExceptHandler(self, node):
                        self.complexity += 1 + self.nesting
                        self.nesting += 1
                        self.generic_visit(node)
                        self.nesting -= 1
                    
                    def visit_BoolOp(self, node):
                        if isinstance(node.op, (ast.And, ast.Or)):
                            self.complexity += len(node.values) - 1
                        self.generic_visit(node)
                
                visitor = CognitiveVisitor()
                visitor.visit(node)
                return visitor.complexity
            
            def _calculate_maintainability_index(self, node, file_path):
                """Calculate maintainability index (0-100, higher is better)."""
                try:
                    # Get function metrics
                    cyclomatic = self._calculate_cyclomatic_complexity(node)
                    
                    # Count lines of code (excluding comments and blank lines)
                    loc = 0
                    for child in ast.walk(node):
                        if hasattr(child, 'lineno'):
                            loc += 1
                    
                    # Estimate Halstead volume (simplified)
                    operators = 0
                    operands = 0
                    
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
                                            ast.Pow, ast.LShift, ast.RShift, ast.BitOr,
                                            ast.BitXor, ast.BitAnd, ast.FloorDiv)):
                            operators += 1
                        elif isinstance(child, (ast.Name, ast.Num, ast.Str, ast.Constant)):
                            operands += 1
                    
                    # Simplified Halstead volume calculation
                    vocabulary = operators + operands
                    length = operators + operands
                    volume = length * (vocabulary.bit_length() if vocabulary > 0 else 1)
                    
                    # Calculate maintainability index
                    # MI = 171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(LOC)
                    # Where V = Halstead Volume, G = Cyclomatic Complexity, LOC = Lines of Code
                    import math
                    
                    if volume > 0 and loc > 0:
                        mi = 171 - 5.2 * math.log(volume) - 0.23 * cyclomatic - 16.2 * math.log(loc)
                        return max(0, min(100, mi))  # Clamp between 0 and 100
                    else:
                        return 100  # Default for very simple functions
                        
                except Exception:
                    return 100  # Default on calculation error
        
        visitor = ComplexityVisitor()
        visitor.config = self.config
        visitor._create_quality_issue = self._create_quality_issue
        visitor.visit(tree)
        
        return visitor.complexity_issues
    
    def _analyze_nesting_depth(self, tree: ast.AST, file_path: Path) -> List[QualityIssue]:
        """Analyze nesting depth of code blocks."""
        issues = []
        max_depth = 4  # Configurable threshold
        
        class NestingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_depth = 0
                self.max_depth_found = 0
                self.nesting_issues = []
            
            def visit_nested_block(self, node):
                self.current_depth += 1
                self.max_depth_found = max(self.max_depth_found, self.current_depth)
                
                if self.current_depth > max_depth:
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.COMPLEXITY,
                        severity=IssueSeverity.MEDIUM,
                        message=f"Deep nesting: {self.current_depth} levels",
                        description=f"Code block at line {node.lineno} has nesting depth of "
                                   f"{self.current_depth}, which exceeds recommended maximum of {max_depth}",
                        line_number=node.lineno,
                        suggestion="Consider extracting nested logic into separate functions",
                        rule_name="nesting_depth"
                    )
                    self.nesting_issues.append(issue)
                
                self.generic_visit(node)
                self.current_depth -= 1
            
            def visit_If(self, node):
                self.visit_nested_block(node)
            
            def visit_For(self, node):
                self.visit_nested_block(node)
            
            def visit_While(self, node):
                self.visit_nested_block(node)
            
            def visit_With(self, node):
                self.visit_nested_block(node)
            
            def visit_Try(self, node):
                self.visit_nested_block(node)
        
        visitor = NestingVisitor()
        visitor._create_quality_issue = self._create_quality_issue
        visitor.visit(tree)
        
        return visitor.nesting_issues
    
    def _analyze_code_length(self, tree: ast.AST, file_path: Path, content: str) -> List[QualityIssue]:
        """Analyze length of functions and classes."""
        issues = []
        lines = content.split('\n')
        
        class LengthVisitor(ast.NodeVisitor):
            def __init__(self):
                self.length_issues = []
            
            def visit_FunctionDef(self, node):
                length = self._get_node_length(node, lines)
                if length > 50:  # Configurable threshold
                    severity = IssueSeverity.MEDIUM if length <= 100 else IssueSeverity.HIGH
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.CODE_SMELL,
                        severity=severity,
                        message=f"Long function: {length} lines",
                        description=f"Function '{node.name}' is {length} lines long, "
                                   f"which may indicate it's doing too much",
                        line_number=node.lineno,
                        suggestion="Consider breaking this function into smaller, more focused functions",
                        rule_name="function_length"
                    )
                    self.length_issues.append(issue)
                
                self.generic_visit(node)
            
            def visit_ClassDef(self, node):
                length = self._get_node_length(node, lines)
                if length > 200:  # Configurable threshold
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.CODE_SMELL,
                        severity=IssueSeverity.MEDIUM,
                        message=f"Large class: {length} lines",
                        description=f"Class '{node.name}' is {length} lines long, "
                                   f"which may indicate it has too many responsibilities",
                        line_number=node.lineno,
                        suggestion="Consider breaking this class into smaller, more focused classes",
                        rule_name="class_length"
                    )
                    self.length_issues.append(issue)
                
                self.generic_visit(node)
            
            def _get_node_length(self, node, lines):
                """Calculate the number of lines in a node."""
                if hasattr(node, 'end_lineno') and node.end_lineno:
                    return node.end_lineno - node.lineno + 1
                else:
                    # Fallback: estimate based on indentation
                    start_line = node.lineno - 1
                    current_line = start_line + 1
                    base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
                    
                    while current_line < len(lines):
                        line = lines[current_line]
                        if line.strip():  # Non-empty line
                            indent = len(line) - len(line.lstrip())
                            if indent <= base_indent:
                                break
                        current_line += 1
                    
                    return current_line - start_line
        
        visitor = LengthVisitor()
        visitor._create_quality_issue = self._create_quality_issue
        visitor.visit(tree)
        
        return visitor.length_issues
    
    def _check_long_parameter_lists(self, tree: ast.AST, file_path: Path) -> List[QualityIssue]:
        """Check for functions with too many parameters."""
        issues = []
        max_params = 5  # Configurable threshold
        
        class ParameterVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                param_count = len(node.args.args)
                if node.args.vararg:
                    param_count += 1
                if node.args.kwarg:
                    param_count += 1
                param_count += len(node.args.kwonlyargs)
                
                if param_count > max_params:
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.CODE_SMELL,
                        severity=IssueSeverity.MEDIUM,
                        message=f"Too many parameters: {param_count}",
                        description=f"Function '{node.name}' has {param_count} parameters, "
                                   f"which exceeds the recommended maximum of {max_params}",
                        line_number=node.lineno,
                        suggestion="Consider using a configuration object or breaking the function down",
                        rule_name="parameter_count"
                    )
                    issues.append(issue)
                
                self.generic_visit(node)
        
        visitor = ParameterVisitor()
        visitor._create_quality_issue = self._create_quality_issue
        visitor.visit(tree)
        
        return issues
    
    def _check_duplicate_code_patterns(self, tree: ast.AST, file_path: Path) -> List[QualityIssue]:
        """Check for simple duplicate code patterns within a file."""
        # This is a basic implementation - more sophisticated duplicate detection
        # will be handled by the dedicated duplicate analyzer
        return []
    
    def _check_magic_numbers(self, tree: ast.AST, file_path: Path) -> List[QualityIssue]:
        """Check for magic numbers in the code."""
        issues = []
        
        class MagicNumberVisitor(ast.NodeVisitor):
            def visit_Num(self, node):
                # Skip common acceptable numbers
                if isinstance(node.n, (int, float)) and node.n not in [0, 1, -1, 2, 10, 100]:
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.CODE_SMELL,
                        severity=IssueSeverity.LOW,
                        message=f"Magic number: {node.n}",
                        description=f"Magic number {node.n} found at line {node.lineno}. "
                                   f"Consider using a named constant",
                        line_number=node.lineno,
                        suggestion="Replace magic number with a named constant",
                        rule_name="magic_number"
                    )
                    issues.append(issue)
                
                self.generic_visit(node)
            
            def visit_Constant(self, node):
                # For Python 3.8+
                if isinstance(node.value, (int, float)) and node.value not in [0, 1, -1, 2, 10, 100]:
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.CODE_SMELL,
                        severity=IssueSeverity.LOW,
                        message=f"Magic number: {node.value}",
                        description=f"Magic number {node.value} found at line {node.lineno}. "
                                   f"Consider using a named constant",
                        line_number=node.lineno,
                        suggestion="Replace magic number with a named constant",
                        rule_name="magic_number"
                    )
                    issues.append(issue)
                
                self.generic_visit(node)
        
        visitor = MagicNumberVisitor()
        visitor._create_quality_issue = self._create_quality_issue
        visitor.visit(tree)
        
        return issues
    
    def _check_empty_except_blocks(self, tree: ast.AST, file_path: Path) -> List[QualityIssue]:
        """Check for empty except blocks."""
        issues = []
        
        class ExceptVisitor(ast.NodeVisitor):
            def visit_ExceptHandler(self, node):
                if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                    issue = self._create_quality_issue(
                        file_path=file_path,
                        issue_type=IssueType.CODE_SMELL,
                        severity=IssueSeverity.MEDIUM,
                        message="Empty except block",
                        description=f"Empty except block at line {node.lineno}. "
                                   f"This can hide errors and make debugging difficult",
                        line_number=node.lineno,
                        suggestion="Add proper error handling or at least log the exception",
                        rule_name="empty_except"
                    )
                    issues.append(issue)
                
                self.generic_visit(node)
        
        visitor = ExceptVisitor()
        visitor._create_quality_issue = self._create_quality_issue
        visitor.visit(tree)
        
        return issues
    
    def _check_unused_variables(self, tree: ast.AST, file_path: Path, content: str) -> List[QualityIssue]:
        """Check for unused variables (basic implementation)."""
        # This is a simplified check - more sophisticated analysis would be done by mypy
        issues = []
        
        class VariableVisitor(ast.NodeVisitor):
            def __init__(self):
                self.assigned_vars = set()
                self.used_vars = set()
            
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store):
                    self.assigned_vars.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    self.used_vars.add(node.id)
                
                self.generic_visit(node)
        
        visitor = VariableVisitor()
        visitor.visit(tree)
        
        # Find variables that are assigned but never used
        unused_vars = visitor.assigned_vars - visitor.used_vars
        
        # Filter out common patterns that are acceptable
        acceptable_patterns = {'_', '__', 'self', 'cls'}
        unused_vars = {var for var in unused_vars 
                      if not any(var.startswith(pattern) for pattern in acceptable_patterns)}
        
        for var in unused_vars:
            # This is a basic implementation - line numbers would need more sophisticated tracking
            issue = self._create_quality_issue(
                file_path=file_path,
                issue_type=IssueType.CODE_SMELL,
                severity=IssueSeverity.LOW,
                message=f"Unused variable: {var}",
                description=f"Variable '{var}' is assigned but never used",
                suggestion=f"Remove unused variable '{var}' or use it",
                rule_name="unused_variable",
                confidence=0.7  # Lower confidence for this basic implementation
            )
            issues.append(issue)
        
        return issues
    
    def _update_quality_metrics(self, issues: List[QualityIssue]) -> None:
        """Update quality metrics based on found issues."""
        syntax_errors = sum(1 for issue in issues if issue.issue_type == IssueType.SYNTAX_ERROR)
        style_violations = sum(1 for issue in issues if issue.issue_type == IssueType.STYLE_VIOLATION)
        code_smells = sum(1 for issue in issues if issue.issue_type == IssueType.CODE_SMELL)
        complexity_issues = sum(1 for issue in issues if issue.issue_type == IssueType.COMPLEXITY)
        
        self.update_metrics(
            syntax_errors=syntax_errors,
            style_violations=style_violations,
            code_smells=code_smells,
            complexity_issues=complexity_issues
        )
        
        logger.info(f"Quality analysis complete: {syntax_errors} syntax errors, "
                   f"{style_violations} style violations, {code_smells} code smells, "
                   f"{complexity_issues} complexity issues")
    
    async def analyze_with_mypy(self, python_files: List[Path]) -> List[QualityIssue]:
        """
        Analyze files with mypy for type checking issues.
        
        Args:
            python_files: List of Python files to analyze
            
        Returns:
            List of type checking issues
        """
        issues = []
        
        if not python_files:
            return issues
        
        try:
            # Prepare mypy command
            cmd = [sys.executable, '-m', 'mypy']
            
            # Add mypy configuration
            if self.config.mypy_config:
                for key, value in self.config.mypy_config.items():
                    if key == 'ignore-missing-imports' and value:
                        cmd.append('--ignore-missing-imports')
                    elif key == 'strict' and value:
                        cmd.append('--strict')
                    elif key == 'show-error-codes' and value:
                        cmd.append('--show-error-codes')
                    elif key == 'no-implicit-optional' and value:
                        cmd.append('--no-implicit-optional')
            else:
                # Default mypy settings
                cmd.extend([
                    '--ignore-missing-imports',
                    '--show-error-codes',
                    '--no-implicit-optional'
                ])
            
            # Add files to analyze
            cmd.extend([str(f) for f in python_files])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # Longer timeout for mypy
            )
            
            # Parse mypy output
            for line in result.stdout.strip().split('\n'):
                if line.strip() and ':' in line:
                    issue = self._parse_mypy_output(line)
                    if issue:
                        issues.append(issue)
                        
        except subprocess.TimeoutExpired:
            logger.warning("Mypy analysis timed out")
        except FileNotFoundError:
            logger.warning("Mypy not found, skipping type checking analysis")
        except Exception as e:
            logger.warning(f"Error running mypy: {e}")
        
        return issues
    
    async def analyze_with_flake8_batch(self, python_files: List[Path]) -> List[QualityIssue]:
        """
        Analyze multiple files with flake8 in batch mode for better performance.
        
        Args:
            python_files: List of Python files to analyze
            
        Returns:
            List of style violation issues
        """
        issues = []
        
        if not python_files:
            return issues
        
        try:
            # Run flake8 on all files at once
            cmd = [
                sys.executable, '-m', 'flake8',
                '--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s'
            ]
            
            # Add flake8 config if specified
            if self.config.flake8_config:
                for key, value in self.config.flake8_config.items():
                    if key == 'max-line-length':
                        cmd.extend(['--max-line-length', str(value)])
                    elif key == 'ignore':
                        cmd.extend(['--ignore', ','.join(value) if isinstance(value, list) else str(value)])
                    elif key == 'select':
                        cmd.extend(['--select', ','.join(value) if isinstance(value, list) else str(value)])
                    elif key == 'exclude':
                        cmd.extend(['--exclude', ','.join(value) if isinstance(value, list) else str(value)])
            
            # Add files
            cmd.extend([str(f) for f in python_files])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse flake8 output
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    # Extract file path from the line to create proper issue
                    parts = line.split(':', 4)
                    if len(parts) >= 5:
                        file_path = Path(parts[0])
                        issue = self._parse_flake8_output(line, file_path)
                        if issue:
                            issues.append(issue)
                            
        except subprocess.TimeoutExpired:
            logger.warning("Flake8 batch analysis timed out")
        except FileNotFoundError:
            logger.warning("Flake8 not found, skipping style analysis")
        except Exception as e:
            logger.warning(f"Error running flake8 batch analysis: {e}")
        
        return issues
    
    def _parse_mypy_output(self, line: str) -> Optional[QualityIssue]:
        """Parse a line of mypy output into a QualityIssue."""
        try:
            # Format: path:line: error: message [error-code]
            # or: path:line:col: error: message [error-code]
            parts = line.split(':', 3)
            if len(parts) < 4:
                return None
            
            file_path = Path(parts[0])
            line_num = int(parts[1])
            
            # Check if there's a column number
            if parts[2].strip().isdigit():
                col_num = int(parts[2])
                message_part = parts[3]
            else:
                col_num = None
                message_part = parts[2] + ':' + parts[3]
            
            # Extract error type and message
            if ' error: ' in message_part:
                error_type, message = message_part.split(' error: ', 1)
                severity = IssueSeverity.HIGH
            elif ' warning: ' in message_part:
                error_type, message = message_part.split(' warning: ', 1)
                severity = IssueSeverity.MEDIUM
            elif ' note: ' in message_part:
                error_type, message = message_part.split(' note: ', 1)
                severity = IssueSeverity.LOW
            else:
                error_type = "info"
                message = message_part
                severity = IssueSeverity.LOW
            
            # Extract error code if present
            error_code = None
            if '[' in message and ']' in message:
                code_start = message.rfind('[')
                code_end = message.rfind(']')
                if code_start < code_end:
                    error_code = message[code_start+1:code_end]
                    message = message[:code_start].strip()
            
            return self._create_quality_issue(
                file_path=file_path,
                issue_type=IssueType.STYLE_VIOLATION,  # Mypy issues are style/type related
                severity=severity,
                message=f"Type check: {message}",
                description=f"MyPy type checking issue at line {line_num}: {message}",
                line_number=line_num,
                rule_name=error_code or "mypy",
                tool_name="mypy",
                suggestion=self._get_mypy_suggestion(error_code, message)
            )
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse mypy output: {line} - {e}")
            return None
    
    def _get_mypy_suggestion(self, error_code: Optional[str], message: str) -> Optional[str]:
        """Get suggestion for fixing mypy error."""
        if not error_code:
            return None
        
        suggestions = {
            'import': 'Add proper import statement or install missing package',
            'name-defined': 'Define the variable or import it from the correct module',
            'attr-defined': 'Check if the attribute exists or add it to the class',
            'call-arg': 'Check function signature and provide correct arguments',
            'assignment': 'Ensure the assigned value matches the expected type',
            'return-value': 'Return a value of the expected type',
            'type-arg': 'Provide correct type arguments for generic types',
            'misc': 'Review the type annotations and fix any inconsistencies'
        }
        
        for key, suggestion in suggestions.items():
            if key in error_code.lower():
                return suggestion
        
        # Generic suggestions based on message content
        if 'incompatible type' in message.lower():
            return 'Check type compatibility and fix type annotations'
        elif 'missing' in message.lower():
            return 'Add the missing type annotation or import'
        elif 'undefined' in message.lower():
            return 'Define the variable or function before using it'
        
        return 'Review mypy documentation for this error type'
    
    def _aggregate_and_normalize_issues(self, issues: List[QualityIssue]) -> List[QualityIssue]:
        """
        Aggregate and normalize issues from different tools to avoid duplicates.
        
        Args:
            issues: List of all issues found
            
        Returns:
            Normalized list of issues with duplicates removed
        """
        # Group issues by file and line number
        issue_groups = {}
        
        for issue in issues:
            key = (issue.file_path, issue.line_number, issue.issue_type)
            if key not in issue_groups:
                issue_groups[key] = []
            issue_groups[key].append(issue)
        
        normalized_issues = []
        
        for key, group in issue_groups.items():
            if len(group) == 1:
                # Single issue, keep as is
                normalized_issues.append(group[0])
            else:
                # Multiple issues at same location, merge or prioritize
                merged_issue = self._merge_similar_issues(group)
                normalized_issues.append(merged_issue)
        
        return normalized_issues
    
    def _merge_similar_issues(self, issues: List[QualityIssue]) -> QualityIssue:
        """
        Merge similar issues from different tools into a single issue.
        
        Args:
            issues: List of similar issues to merge
            
        Returns:
            Merged issue
        """
        # Prioritize by tool reliability: mypy > flake8 > ast > custom
        tool_priority = {'mypy': 4, 'flake8': 3, 'ast': 2, 'quality_analyzer': 1}
        
        # Sort by priority (highest first)
        sorted_issues = sorted(issues, 
                             key=lambda x: tool_priority.get(x.tool_name or '', 0), 
                             reverse=True)
        
        primary_issue = sorted_issues[0]
        
        # Combine messages from all tools
        all_messages = [issue.message for issue in sorted_issues]
        all_tools = [issue.tool_name for issue in sorted_issues if issue.tool_name]
        
        # Create merged issue
        merged_issue = self._create_quality_issue(
            file_path=primary_issue.file_path,
            issue_type=primary_issue.issue_type,
            severity=primary_issue.severity,
            message=primary_issue.message,
            description=f"Multiple tools found issues: {'; '.join(all_messages)}",
            line_number=primary_issue.line_number,
            suggestion=primary_issue.suggestion,
            rule_name=primary_issue.rule_name,
            tool_name=f"multiple ({', '.join(set(all_tools))})",
            confidence=min(issue.confidence for issue in sorted_issues)
        )
        
        return merged_issue