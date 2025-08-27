#!/usr/bin/env python3
"""
Custom Analyzer Demonstration for Codebase Checkup

This script demonstrates how to create and use custom analyzers
with the codebase checkup system.
"""

import ast
import asyncio
import re
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import Issue


@dataclass
class CustomIssue(Issue):
    """Custom issue type for our analyzer."""
    rule_id: str
    suggestion: Optional[str] = None
    auto_fixable: bool = False


class SecurityAnalyzer(BaseAnalyzer):
    """Custom analyzer that checks for common security issues."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "security"
        
        # Define security patterns to check
        self.security_patterns = {
            'hardcoded_password': {
                'pattern': r'password\s*=\s*["\'][^"\']+["\']',
                'message': 'Hardcoded password detected',
                'severity': 'critical'
            },
            'sql_injection': {
                'pattern': r'execute\s*\(\s*["\'].*%.*["\']',
                'message': 'Potential SQL injection vulnerability',
                'severity': 'critical'
            },
            'debug_mode': {
                'pattern': r'debug\s*=\s*True',
                'message': 'Debug mode enabled in production code',
                'severity': 'warning'
            },
            'insecure_random': {
                'pattern': r'random\.random\(\)',
                'message': 'Use secrets module for cryptographic randomness',
                'severity': 'warning'
            }
        }
    
    async def analyze(self, files: List[Path]) -> List[CustomIssue]:
        """Analyze files for security issues."""
        issues = []
        
        for file_path in files:
            if file_path.suffix == '.py':
                file_issues = await self.analyze_file(file_path)
                issues.extend(file_issues)
        
        return issues
    
    async def analyze_file(self, file_path: Path) -> List[CustomIssue]:
        """Analyze a single file for security issues."""
        issues = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines()
            
            # Check for pattern-based issues
            for line_num, line in enumerate(lines, 1):
                for rule_id, rule in self.security_patterns.items():
                    if re.search(rule['pattern'], line, re.IGNORECASE):
                        issues.append(CustomIssue(
                            file=file_path,
                            line=line_num,
                            column=1,
                            message=rule['message'],
                            rule=rule_id,
                            severity=rule['severity'],
                            category='security',
                            rule_id=rule_id,
                            suggestion=self._get_suggestion(rule_id)
                        ))
            
            # Check for AST-based issues
            try:
                tree = ast.parse(content)
                ast_issues = self._analyze_ast(tree, file_path)
                issues.extend(ast_issues)
            except SyntaxError:
                # Skip files with syntax errors
                pass
                
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
        
        return issues
    
    def _analyze_ast(self, tree: ast.AST, file_path: Path) -> List[CustomIssue]:
        """Analyze AST for security issues."""
        issues = []
        
        for node in ast.walk(tree):
            # Check for eval() usage
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'eval':
                    issues.append(CustomIssue(
                        file=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        message='Use of eval() is dangerous',
                        rule='dangerous_eval',
                        severity='critical',
                        category='security',
                        rule_id='dangerous_eval',
                        suggestion='Use ast.literal_eval() for safe evaluation'
                    ))
                
                # Check for exec() usage
                elif isinstance(node.func, ast.Name) and node.func.id == 'exec':
                    issues.append(CustomIssue(
                        file=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        message='Use of exec() is dangerous',
                        rule='dangerous_exec',
                        severity='critical',
                        category='security',
                        rule_id='dangerous_exec',
                        suggestion='Avoid dynamic code execution'
                    ))
            
            # Check for shell=True in subprocess calls
            elif isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Attribute) and 
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'subprocess'):
                    
                    for keyword in node.keywords:
                        if (keyword.arg == 'shell' and 
                            isinstance(keyword.value, ast.Constant) and
                            keyword.value.value is True):
                            
                            issues.append(CustomIssue(
                                file=file_path,
                                line=node.lineno,
                                column=node.col_offset,
                                message='subprocess with shell=True is dangerous',
                                rule='shell_injection',
                                severity='warning',
                                category='security',
                                rule_id='shell_injection',
                                suggestion='Use shell=False and pass command as list'
                            ))
        
        return issues
    
    def _get_suggestion(self, rule_id: str) -> Optional[str]:
        """Get suggestion for fixing a security issue."""
        suggestions = {
            'hardcoded_password': 'Use environment variables or secure configuration',
            'sql_injection': 'Use parameterized queries or ORM',
            'debug_mode': 'Use environment-based configuration',
            'insecure_random': 'Use secrets.SystemRandom() for cryptographic purposes'
        }
        return suggestions.get(rule_id)


class PerformanceAnalyzer(BaseAnalyzer):
    """Custom analyzer that checks for performance issues."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "performance"
    
    async def analyze(self, files: List[Path]) -> List[CustomIssue]:
        """Analyze files for performance issues."""
        issues = []
        
        for file_path in files:
            if file_path.suffix == '.py':
                file_issues = await self.analyze_file(file_path)
                issues.extend(file_issues)
        
        return issues
    
    async def analyze_file(self, file_path: Path) -> List[CustomIssue]:
        """Analyze a single file for performance issues."""
        issues = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Check for inefficient list comprehensions
                if isinstance(node, ast.ListComp):
                    # Look for nested loops
                    if len(node.generators) > 2:
                        issues.append(CustomIssue(
                            file=file_path,
                            line=node.lineno,
                            column=node.col_offset,
                            message='Complex list comprehension may be inefficient',
                            rule='complex_comprehension',
                            severity='info',
                            category='performance',
                            rule_id='complex_comprehension',
                            suggestion='Consider breaking into multiple steps'
                        ))
                
                # Check for string concatenation in loops
                elif isinstance(node, ast.For):
                    for child in ast.walk(node):
                        if (isinstance(child, ast.AugAssign) and
                            isinstance(child.op, ast.Add) and
                            isinstance(child.target, ast.Name)):
                            
                            issues.append(CustomIssue(
                                file=file_path,
                                line=child.lineno,
                                column=child.col_offset,
                                message='String concatenation in loop is inefficient',
                                rule='string_concat_loop',
                                severity='warning',
                                category='performance',
                                rule_id='string_concat_loop',
                                suggestion='Use join() or f-strings instead'
                            ))
                
                # Check for global variable access in functions
                elif isinstance(node, ast.FunctionDef):
                    for child in ast.walk(node):
                        if isinstance(child, ast.Global):
                            issues.append(CustomIssue(
                                file=file_path,
                                line=child.lineno,
                                column=child.col_offset,
                                message='Global variable access can impact performance',
                                rule='global_access',
                                severity='info',
                                category='performance',
                                rule_id='global_access',
                                suggestion='Pass values as parameters instead'
                            ))
                            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
        
        return issues


async def demo_custom_analyzers():
    """Demonstrate custom analyzers."""
    print("🔍 Custom Analyzers Demonstration")
    print("=" * 50)
    
    # Create test files with issues
    test_dir = Path("custom_analyzer_test")
    test_dir.mkdir(exist_ok=True)
    
    # Create test file with security issues
    security_test = test_dir / "security_test.py"
    security_test.write_text('''
# Security issues for testing
import subprocess
import random

# Hardcoded password (security issue)
password = "secret123"

# SQL injection vulnerability
def unsafe_query(user_input):
    query = "SELECT * FROM users WHERE name = '%s'" % user_input
    cursor.execute(query)

# Debug mode enabled
DEBUG = True

# Insecure random
token = random.random()

# Dangerous eval
def process_input(user_input):
    result = eval(user_input)
    return result

# Shell injection
def run_command(cmd):
    subprocess.run(cmd, shell=True)
''')
    
    # Create test file with performance issues
    performance_test = test_dir / "performance_test.py"
    performance_test.write_text('''
# Performance issues for testing
global_var = "expensive_to_access"

def inefficient_function():
    # String concatenation in loop
    result = ""
    for i in range(1000):
        result += str(i)
    
    # Complex list comprehension
    complex_list = [x*y*z for x in range(10) for y in range(10) for z in range(10)]
    
    # Global variable access
    global global_var
    return global_var + result

# More performance issues
def another_function():
    # Nested loops in comprehension
    nested = [[x+y+z for x in range(5)] for y in range(5) for z in range(5)]
    return nested
''')
    
    try:
        # Create custom analyzers
        security_analyzer = SecurityAnalyzer()
        performance_analyzer = PerformanceAnalyzer()
        
        print("Created custom analyzers:")
        print(f"  - {security_analyzer.name}: Security issue detection")
        print(f"  - {performance_analyzer.name}: Performance issue detection")
        
        # Test security analyzer
        print(f"\n🔒 Security Analysis Results:")
        security_issues = await security_analyzer.analyze([security_test])
        
        for issue in security_issues:
            print(f"  {issue.severity.upper()}: {issue.file.name}:{issue.line}")
            print(f"    {issue.message}")
            if issue.suggestion:
                print(f"    💡 {issue.suggestion}")
            print()
        
        # Test performance analyzer
        print(f"⚡ Performance Analysis Results:")
        performance_issues = await performance_analyzer.analyze([performance_test])
        
        for issue in performance_issues:
            print(f"  {issue.severity.upper()}: {issue.file.name}:{issue.line}")
            print(f"    {issue.message}")
            if issue.suggestion:
                print(f"    💡 {issue.suggestion}")
            print()
        
        # Combine with standard checkup
        print(f"🔄 Integrating with Standard Checkup:")
        
        config = CheckupConfig(
            enable_quality_analysis=True,
            enable_import_analysis=False,  # Focus on custom analysis
            generate_json_report=True,
            output_directory="custom-analyzer-reports"
        )
        
        orchestrator = CodebaseOrchestrator(config, test_dir)
        
        # Add custom analyzers
        orchestrator.add_analyzer(security_analyzer)
        orchestrator.add_analyzer(performance_analyzer)
        
        # Run combined analysis
        results = await orchestrator.run_analysis_only()
        
        print(f"Combined analysis results:")
        print(f"  Files analyzed: {results.files_analyzed}")
        print(f"  Total issues: {results.total_issues}")
        print(f"  Security issues: {len(security_issues)}")
        print(f"  Performance issues: {len(performance_issues)}")
        
        # Generate reports
        await orchestrator.generate_reports(results)
        print(f"\nReports generated in: custom-analyzer-reports/")
        
        return len(security_issues) + len(performance_issues)
        
    finally:
        # Clean up test files
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\nCleaned up test directory: {test_dir}")


async def demo_analyzer_configuration():
    """Demonstrate configurable custom analyzers."""
    print("\n⚙️  Configurable Custom Analyzer Demo")
    print("=" * 50)
    
    class ConfigurableAnalyzer(BaseAnalyzer):
        """Analyzer with configurable rules."""
        
        def __init__(self, config=None):
            super().__init__(config)
            self.name = "configurable"
            
            # Default configuration
            self.rules = {
                'max_function_args': 5,
                'max_return_statements': 3,
                'check_docstrings': True,
                'check_type_hints': True
            }
            
            # Override with provided config
            if config:
                self.rules.update(config)
        
        async def analyze(self, files: List[Path]) -> List[CustomIssue]:
            issues = []
            
            for file_path in files:
                if file_path.suffix == '.py':
                    file_issues = await self.analyze_file(file_path)
                    issues.extend(file_issues)
            
            return issues
        
        async def analyze_file(self, file_path: Path) -> List[CustomIssue]:
            issues = []
            
            try:
                content = file_path.read_text(encoding='utf-8')
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check function arguments
                        if len(node.args.args) > self.rules['max_function_args']:
                            issues.append(CustomIssue(
                                file=file_path,
                                line=node.lineno,
                                column=node.col_offset,
                                message=f'Function has {len(node.args.args)} arguments (max: {self.rules["max_function_args"]})',
                                rule='too_many_args',
                                severity='warning',
                                category='design',
                                rule_id='too_many_args'
                            ))
                        
                        # Check return statements
                        return_count = sum(1 for child in ast.walk(node) 
                                         if isinstance(child, ast.Return))
                        if return_count > self.rules['max_return_statements']:
                            issues.append(CustomIssue(
                                file=file_path,
                                line=node.lineno,
                                column=node.col_offset,
                                message=f'Function has {return_count} return statements (max: {self.rules["max_return_statements"]})',
                                rule='too_many_returns',
                                severity='info',
                                category='design',
                                rule_id='too_many_returns'
                            ))
                        
                        # Check docstrings
                        if self.rules['check_docstrings']:
                            if not ast.get_docstring(node):
                                issues.append(CustomIssue(
                                    file=file_path,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    message='Function missing docstring',
                                    rule='missing_docstring',
                                    severity='info',
                                    category='documentation',
                                    rule_id='missing_docstring'
                                ))
                        
                        # Check type hints
                        if self.rules['check_type_hints']:
                            if not node.returns and node.name != '__init__':
                                issues.append(CustomIssue(
                                    file=file_path,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    message='Function missing return type hint',
                                    rule='missing_return_type',
                                    severity='info',
                                    category='typing',
                                    rule_id='missing_return_type'
                                ))
                            
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
            
            return issues
    
    # Test with different configurations
    configs = [
        {
            'name': 'Strict',
            'config': {
                'max_function_args': 3,
                'max_return_statements': 1,
                'check_docstrings': True,
                'check_type_hints': True
            }
        },
        {
            'name': 'Relaxed',
            'config': {
                'max_function_args': 8,
                'max_return_statements': 5,
                'check_docstrings': False,
                'check_type_hints': False
            }
        }
    ]
    
    # Create test file
    test_file = Path("configurable_test.py")
    test_file.write_text('''
def complex_function(a, b, c, d, e, f):
    """A function with many parameters and returns."""
    if a > b:
        return a + b
    elif c > d:
        return c + d
    else:
        return e + f

def undocumented_function(x, y):
    if x:
        return x
    return y

def no_type_hints(value):
    return str(value)
''')
    
    try:
        for config_info in configs:
            print(f"\n📋 {config_info['name']} Configuration:")
            for key, value in config_info['config'].items():
                print(f"  {key}: {value}")
            
            analyzer = ConfigurableAnalyzer(config_info['config'])
            issues = await analyzer.analyze([test_file])
            
            print(f"\nIssues found: {len(issues)}")
            for issue in issues:
                print(f"  {issue.severity.upper()}: {issue.message}")
    
    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()


async def main():
    """Run custom analyzer demonstrations."""
    print("🚀 Custom Analyzer Demonstration")
    print("=" * 60)
    
    total_issues = await demo_custom_analyzers()
    await demo_analyzer_configuration()
    
    print(f"\n✅ Custom analyzer demo completed!")
    print(f"Found {total_issues} custom issues in test files")
    print("\nKey takeaways:")
    print("  - Custom analyzers can check for domain-specific issues")
    print("  - Analyzers can be configured for different strictness levels")
    print("  - Custom analyzers integrate seamlessly with standard checkup")
    print("  - Both pattern-based and AST-based analysis are supported")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()