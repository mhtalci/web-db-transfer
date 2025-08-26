"""
Coverage Validator

Validates test coverage and identifies gaps using pytest-cov integration.
"""

import ast
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import xml.etree.ElementTree as ET

from migration_assistant.checkup.validators.base import BaseValidator, ValidationResult
from migration_assistant.checkup.models import (
    CoverageGap, IssueType, IssueSeverity, CheckupConfig
)


@dataclass
class CoverageReport:
    """Coverage report data structure."""
    total_coverage: float
    file_coverage: Dict[str, float]
    missing_lines: Dict[str, List[int]]
    untested_functions: List[Dict[str, Any]]
    untested_classes: List[Dict[str, Any]]
    branch_coverage: Optional[float] = None


@dataclass
class TestQualityMetrics:
    """Test quality analysis metrics."""
    total_tests: int
    redundant_tests: List[str]
    obsolete_tests: List[str]
    test_effectiveness_score: float
    coverage_per_test: Dict[str, float]


class CoverageValidator(BaseValidator):
    """Validator for test coverage analysis with pytest-cov integration."""
    
    def __init__(self, config: CheckupConfig):
        """Initialize coverage validator."""
        super().__init__(config)
        self._coverage_data: Optional[CoverageReport] = None
        self._test_quality_data: Optional[TestQualityMetrics] = None
    
    def get_validation_scope(self) -> List[str]:
        """Return validation scope."""
        return ['test_coverage', 'test_quality', 'untested_code', 'coverage_gaps']
    
    async def validate(self) -> ValidationResult:
        """
        Validate test coverage and generate comprehensive analysis.
        
        Returns:
            ValidationResult with coverage analysis and identified gaps
        """
        try:
            # Generate coverage report
            coverage_report = await self.generate_coverage_report()
            
            if not coverage_report:
                return ValidationResult(
                    valid=False,
                    message="Failed to generate coverage report"
                )
            
            # Identify untested code
            coverage_gaps = await self.identify_untested_code()
            
            # Update metrics
            self.update_metrics(
                test_coverage_percentage=coverage_report.total_coverage,
                untested_functions=len(coverage_report.untested_functions)
            )
            
            # Determine if coverage meets threshold
            meets_threshold = coverage_report.total_coverage >= self.config.min_coverage_threshold
            
            result = ValidationResult(
                valid=meets_threshold,
                message=f"Coverage: {coverage_report.total_coverage:.1f}% "
                       f"(threshold: {self.config.min_coverage_threshold}%)",
                issues=coverage_gaps
            )
            
            result.files_validated = len(coverage_report.file_coverage)
            result.validation_details = {
                "total_coverage": coverage_report.total_coverage,
                "file_coverage": coverage_report.file_coverage,
                "untested_functions": len(coverage_report.untested_functions),
                "untested_classes": len(coverage_report.untested_classes),
                "meets_threshold": meets_threshold
            }
            
            return result
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Coverage validation failed: {str(e)}"
            )
    
    async def generate_coverage_report(self) -> Optional[CoverageReport]:
        """
        Generate coverage report using pytest-cov.
        
        Returns:
            CoverageReport with detailed coverage information
        """
        try:
            # Create temporary directory for coverage files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                coverage_xml = temp_path / "coverage.xml"
                coverage_json = temp_path / "coverage.json"
                
                # Run pytest with coverage
                cmd = [
                    "python", "-m", "pytest",
                    "--cov=migration_assistant",
                    f"--cov-report=xml:{coverage_xml}",
                    f"--cov-report=json:{coverage_json}",
                    "--cov-report=term-missing",
                    "--no-cov-on-fail",
                    str(self.target_directory / "tests")
                ]
                
                result = subprocess.run(
                    cmd,
                    cwd=self.target_directory,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0 and not coverage_xml.exists():
                    # Tests failed but we might still have coverage data
                    print(f"Warning: Tests failed but continuing with coverage analysis")
                    print(f"STDERR: {result.stderr}")
                
                # Parse coverage data
                coverage_report = await self._parse_coverage_data(coverage_xml, coverage_json)
                
                if coverage_report:
                    # Analyze untested functions and classes
                    coverage_report.untested_functions = await self._find_untested_functions(
                        coverage_report.file_coverage, coverage_report.missing_lines
                    )
                    coverage_report.untested_classes = await self._find_untested_classes(
                        coverage_report.file_coverage, coverage_report.missing_lines
                    )
                
                self._coverage_data = coverage_report
                return coverage_report
                
        except subprocess.TimeoutExpired:
            print("Coverage generation timed out")
            return None
        except Exception as e:
            print(f"Error generating coverage report: {e}")
            return None
    
    async def _parse_coverage_data(
        self, 
        xml_path: Path, 
        json_path: Path
    ) -> Optional[CoverageReport]:
        """
        Parse coverage data from XML and JSON reports.
        
        Args:
            xml_path: Path to coverage XML file
            json_path: Path to coverage JSON file
            
        Returns:
            CoverageReport with parsed data
        """
        try:
            file_coverage = {}
            missing_lines = {}
            total_coverage = 0.0
            branch_coverage = None
            
            # Parse XML for detailed line coverage
            if xml_path.exists():
                tree = ET.parse(xml_path)
                root = tree.getroot()
                
                # Get overall coverage
                coverage_elem = root.find('.//coverage')
                if coverage_elem is not None:
                    total_coverage = float(coverage_elem.get('line-rate', 0)) * 100
                    branch_rate = coverage_elem.get('branch-rate')
                    if branch_rate:
                        branch_coverage = float(branch_rate) * 100
                
                # Get per-file coverage
                for package in root.findall('.//package'):
                    for class_elem in package.findall('.//class'):
                        filename = class_elem.get('filename', '')
                        if filename:
                            # Calculate line coverage for this file
                            lines = class_elem.findall('.//line')
                            if lines:
                                covered_lines = sum(1 for line in lines if line.get('hits', '0') != '0')
                                total_lines = len(lines)
                                if total_lines > 0:
                                    file_coverage[filename] = (covered_lines / total_lines) * 100
                                
                                # Get missing lines
                                missing = [
                                    int(line.get('number', 0)) 
                                    for line in lines 
                                    if line.get('hits', '0') == '0'
                                ]
                                if missing:
                                    missing_lines[filename] = missing
            
            # Parse JSON for additional details if available
            if json_path.exists():
                with open(json_path, 'r') as f:
                    json_data = json.load(f)
                    
                # Update with JSON data if more accurate
                if 'totals' in json_data:
                    totals = json_data['totals']
                    if 'percent_covered' in totals:
                        total_coverage = totals['percent_covered']
                
                # Update file coverage from JSON
                if 'files' in json_data:
                    for filepath, file_data in json_data['files'].items():
                        if 'summary' in file_data:
                            summary = file_data['summary']
                            if 'percent_covered' in summary:
                                file_coverage[filepath] = summary['percent_covered']
                        
                        # Get missing lines from JSON
                        if 'missing_lines' in file_data:
                            missing_lines[filepath] = file_data['missing_lines']
            
            return CoverageReport(
                total_coverage=total_coverage,
                file_coverage=file_coverage,
                missing_lines=missing_lines,
                untested_functions=[],
                untested_classes=[],
                branch_coverage=branch_coverage
            )
            
        except Exception as e:
            print(f"Error parsing coverage data: {e}")
            return None
    
    async def _find_untested_functions(
        self, 
        file_coverage: Dict[str, float], 
        missing_lines: Dict[str, List[int]]
    ) -> List[Dict[str, Any]]:
        """
        Find untested functions by analyzing AST and missing lines.
        
        Args:
            file_coverage: Coverage percentage per file
            missing_lines: Missing line numbers per file
            
        Returns:
            List of untested function information
        """
        untested_functions = []
        
        # Get Python files to analyze
        python_files = self.get_target_files(['.py'])
        
        for file_path in python_files:
            # Skip test files
            if 'test' in file_path.name.lower() or 'tests' in str(file_path):
                continue
            
            try:
                # Get relative path for coverage data lookup
                rel_path = str(file_path.relative_to(self.target_directory))
                file_missing_lines = missing_lines.get(rel_path, [])
                
                if not file_missing_lines:
                    continue
                
                # Parse AST to find functions
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Check if function lines are in missing lines
                        func_start = node.lineno
                        func_end = getattr(node, 'end_lineno', func_start)
                        
                        # Check if any function lines are missing coverage
                        func_lines = set(range(func_start, func_end + 1))
                        missing_func_lines = func_lines.intersection(set(file_missing_lines))
                        
                        if missing_func_lines:
                            # Calculate coverage for this function
                            covered_lines = func_lines - missing_func_lines
                            coverage_pct = (len(covered_lines) / len(func_lines)) * 100 if func_lines else 0
                            
                            untested_functions.append({
                                'file_path': file_path,
                                'function_name': node.name,
                                'line_start': func_start,
                                'line_end': func_end,
                                'coverage_percentage': coverage_pct,
                                'missing_lines': sorted(missing_func_lines),
                                'is_async': isinstance(node, ast.AsyncFunctionDef),
                                'args': [arg.arg for arg in node.args.args],
                                'decorators': [ast.unparse(dec) for dec in node.decorator_list]
                            })
                            
            except Exception as e:
                print(f"Error analyzing functions in {file_path}: {e}")
                continue
        
        return untested_functions
    
    async def _find_untested_classes(
        self, 
        file_coverage: Dict[str, float], 
        missing_lines: Dict[str, List[int]]
    ) -> List[Dict[str, Any]]:
        """
        Find untested classes by analyzing AST and missing lines.
        
        Args:
            file_coverage: Coverage percentage per file
            missing_lines: Missing line numbers per file
            
        Returns:
            List of untested class information
        """
        untested_classes = []
        
        # Get Python files to analyze
        python_files = self.get_target_files(['.py'])
        
        for file_path in python_files:
            # Skip test files
            if 'test' in file_path.name.lower() or 'tests' in str(file_path):
                continue
            
            try:
                # Get relative path for coverage data lookup
                rel_path = str(file_path.relative_to(self.target_directory))
                file_missing_lines = missing_lines.get(rel_path, [])
                
                if not file_missing_lines:
                    continue
                
                # Parse AST to find classes
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if class lines are in missing lines
                        class_start = node.lineno
                        class_end = getattr(node, 'end_lineno', class_start)
                        
                        # Check if any class lines are missing coverage
                        class_lines = set(range(class_start, class_end + 1))
                        missing_class_lines = class_lines.intersection(set(file_missing_lines))
                        
                        if missing_class_lines:
                            # Calculate coverage for this class
                            covered_lines = class_lines - missing_class_lines
                            coverage_pct = (len(covered_lines) / len(class_lines)) * 100 if class_lines else 0
                            
                            # Find untested methods
                            untested_methods = []
                            for method_node in node.body:
                                if isinstance(method_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    method_start = method_node.lineno
                                    method_end = getattr(method_node, 'end_lineno', method_start)
                                    method_lines = set(range(method_start, method_end + 1))
                                    
                                    if method_lines.intersection(set(file_missing_lines)):
                                        untested_methods.append(method_node.name)
                            
                            untested_classes.append({
                                'file_path': file_path,
                                'class_name': node.name,
                                'line_start': class_start,
                                'line_end': class_end,
                                'coverage_percentage': coverage_pct,
                                'missing_lines': sorted(missing_class_lines),
                                'untested_methods': untested_methods,
                                'base_classes': [ast.unparse(base) for base in node.bases],
                                'decorators': [ast.unparse(dec) for dec in node.decorator_list]
                            })
                            
            except Exception as e:
                print(f"Error analyzing classes in {file_path}: {e}")
                continue
        
        return untested_classes
    
    async def identify_untested_code(self) -> List[CoverageGap]:
        """
        Identify untested code and create CoverageGap issues.
        
        Returns:
            List of CoverageGap issues for untested code
        """
        if not self._coverage_data:
            await self.generate_coverage_report()
        
        if not self._coverage_data:
            return []
        
        coverage_gaps = []
        
        # Create issues for untested functions
        for func_info in self._coverage_data.untested_functions:
            gap = CoverageGap(
                file_path=func_info['file_path'],
                line_number=func_info['line_start'],
                severity=IssueSeverity.MEDIUM if func_info['coverage_percentage'] == 0 else IssueSeverity.LOW,
                issue_type=IssueType.COVERAGE_GAP,
                message=f"Function '{func_info['function_name']}' has {func_info['coverage_percentage']:.1f}% coverage",
                description=f"Function '{func_info['function_name']}' at lines {func_info['line_start']}-{func_info['line_end']} "
                           f"has insufficient test coverage ({func_info['coverage_percentage']:.1f}%)",
                function_name=func_info['function_name'],
                coverage_percentage=func_info['coverage_percentage'],
                test_suggestion=f"Add tests for function '{func_info['function_name']}' with args: {func_info['args']}"
            )
            coverage_gaps.append(gap)
        
        # Create issues for untested classes
        for class_info in self._coverage_data.untested_classes:
            gap = CoverageGap(
                file_path=class_info['file_path'],
                line_number=class_info['line_start'],
                severity=IssueSeverity.MEDIUM if class_info['coverage_percentage'] == 0 else IssueSeverity.LOW,
                issue_type=IssueType.COVERAGE_GAP,
                message=f"Class '{class_info['class_name']}' has {class_info['coverage_percentage']:.1f}% coverage",
                description=f"Class '{class_info['class_name']}' at lines {class_info['line_start']}-{class_info['line_end']} "
                           f"has insufficient test coverage ({class_info['coverage_percentage']:.1f}%)",
                class_name=class_info['class_name'],
                coverage_percentage=class_info['coverage_percentage'],
                test_suggestion=f"Add tests for class '{class_info['class_name']}' methods: {class_info['untested_methods']}"
            )
            coverage_gaps.append(gap)
        
        # Create issues for files with low coverage
        for file_path, coverage_pct in self._coverage_data.file_coverage.items():
            if coverage_pct < self.config.min_coverage_threshold:
                full_path = self.target_directory / file_path
                gap = CoverageGap(
                    file_path=full_path,
                    line_number=1,
                    severity=IssueSeverity.HIGH if coverage_pct < 50 else IssueSeverity.MEDIUM,
                    issue_type=IssueType.COVERAGE_GAP,
                    message=f"File has {coverage_pct:.1f}% coverage (below {self.config.min_coverage_threshold}% threshold)",
                    description=f"File '{file_path}' has insufficient overall test coverage",
                    coverage_percentage=coverage_pct,
                    test_suggestion=f"Increase test coverage for '{file_path}' to meet {self.config.min_coverage_threshold}% threshold"
                )
                coverage_gaps.append(gap)
        
        return coverage_gaps
    
    async def suggest_test_implementations(self) -> List[Dict[str, Any]]:
        """
        Suggest specific test implementations for untested code.
        
        Returns:
            List of test implementation suggestions with templates and priorities
        """
        if not self._coverage_data:
            await self.generate_coverage_report()
        
        if not self._coverage_data:
            return []
        
        suggestions = []
        
        # Generate suggestions for untested functions
        for func_info in self._coverage_data.untested_functions:
            suggestion = await self._generate_function_test_suggestion(func_info)
            if suggestion:
                suggestions.append(suggestion)
        
        # Generate suggestions for untested classes
        for class_info in self._coverage_data.untested_classes:
            suggestion = await self._generate_class_test_suggestion(class_info)
            if suggestion:
                suggestions.append(suggestion)
        
        # Sort suggestions by priority
        suggestions.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return suggestions
    
    async def validate_test_quality(self) -> ValidationResult:
        """
        Validate test quality and identify issues.
        
        Returns:
            ValidationResult with test quality analysis
        """
        try:
            # Analyze test quality
            test_quality_metrics = await self._analyze_test_quality()
            
            if not test_quality_metrics:
                return ValidationResult(
                    valid=False,
                    message="Failed to analyze test quality"
                )
            
            self._test_quality_data = test_quality_metrics
            
            # Create issues for quality problems
            quality_issues = []
            
            # Check for redundant tests
            for redundant_test in test_quality_metrics.redundant_tests:
                issue = self.create_issue(
                    file_path=Path(redundant_test),
                    issue_type=IssueType.CODE_SMELL,
                    severity=IssueSeverity.LOW,
                    message=f"Redundant test detected: {redundant_test}",
                    description=f"Test '{redundant_test}' appears to be redundant with other tests",
                    suggestion="Consider removing or consolidating redundant tests"
                )
                quality_issues.append(issue)
            
            # Check for obsolete tests
            for obsolete_test in test_quality_metrics.obsolete_tests:
                issue = self.create_issue(
                    file_path=Path(obsolete_test),
                    issue_type=IssueType.CODE_SMELL,
                    severity=IssueSeverity.MEDIUM,
                    message=f"Obsolete test detected: {obsolete_test}",
                    description=f"Test '{obsolete_test}' may be testing obsolete functionality",
                    suggestion="Review and update or remove obsolete tests"
                )
                quality_issues.append(issue)
            
            # Determine overall quality
            is_high_quality = (
                test_quality_metrics.test_effectiveness_score >= 0.7 and
                len(test_quality_metrics.redundant_tests) <= 5 and
                len(test_quality_metrics.obsolete_tests) <= 3
            )
            
            result = ValidationResult(
                valid=is_high_quality,
                message=f"Test effectiveness: {test_quality_metrics.test_effectiveness_score:.2f}, "
                       f"Redundant: {len(test_quality_metrics.redundant_tests)}, "
                       f"Obsolete: {len(test_quality_metrics.obsolete_tests)}",
                issues=quality_issues
            )
            
            result.validation_details = {
                "total_tests": test_quality_metrics.total_tests,
                "redundant_tests": len(test_quality_metrics.redundant_tests),
                "obsolete_tests": len(test_quality_metrics.obsolete_tests),
                "effectiveness_score": test_quality_metrics.test_effectiveness_score,
                "high_quality": is_high_quality
            }
            
            return result
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Test quality validation failed: {str(e)}"
            )
    
    async def _analyze_test_quality(self) -> Optional[TestQualityMetrics]:
        """
        Analyze test quality by examining test files.
        
        Returns:
            TestQualityMetrics with quality analysis results
        """
        try:
            # Get all test files
            test_files = []
            for pattern in ["test_*.py", "*_test.py"]:
                test_files.extend(self.target_directory.rglob(pattern))
            
            if not test_files:
                return TestQualityMetrics(
                    total_tests=0,
                    redundant_tests=[],
                    obsolete_tests=[],
                    test_effectiveness_score=0.0,
                    coverage_per_test={}
                )
            
            total_tests = 0
            redundant_tests = []
            obsolete_tests = []
            coverage_per_test = {}
            
            # Analyze each test file
            for test_file in test_files:
                if not self.should_validate_file(test_file):
                    continue
                
                try:
                    with open(test_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    
                    # Find test functions
                    test_functions = []
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.name.startswith('test_'):
                                test_functions.append({
                                    'name': node.name,
                                    'file': test_file,
                                    'line_start': node.lineno,
                                    'line_end': getattr(node, 'end_lineno', node.lineno),
                                    'docstring': ast.get_docstring(node),
                                    'body_lines': node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 1
                                })
                    
                    total_tests += len(test_functions)
                    
                    # Detect redundant tests (similar names or very similar structure)
                    redundant_in_file = await self._detect_redundant_tests(test_functions)
                    redundant_tests.extend([f"{test_file}::{test}" for test in redundant_in_file])
                    
                    # Detect obsolete tests (tests with outdated patterns or imports)
                    obsolete_in_file = await self._detect_obsolete_tests(test_file, content)
                    obsolete_tests.extend([f"{test_file}::{test}" for test in obsolete_in_file])
                    
                    # Calculate coverage contribution per test (simplified)
                    for test_func in test_functions:
                        # Estimate coverage contribution based on test complexity
                        coverage_contribution = min(test_func['body_lines'] * 0.5, 10.0)
                        coverage_per_test[f"{test_file}::{test_func['name']}"] = coverage_contribution
                
                except Exception as e:
                    print(f"Error analyzing test file {test_file}: {e}")
                    continue
            
            # Calculate test effectiveness score
            effectiveness_score = await self._calculate_test_effectiveness(
                total_tests, redundant_tests, obsolete_tests, coverage_per_test
            )
            
            return TestQualityMetrics(
                total_tests=total_tests,
                redundant_tests=redundant_tests,
                obsolete_tests=obsolete_tests,
                test_effectiveness_score=effectiveness_score,
                coverage_per_test=coverage_per_test
            )
            
        except Exception as e:
            print(f"Error analyzing test quality: {e}")
            return None
    
    async def _detect_redundant_tests(self, test_functions: List[Dict[str, Any]]) -> List[str]:
        """
        Detect redundant tests based on naming patterns and structure.
        
        Args:
            test_functions: List of test function information
            
        Returns:
            List of redundant test names
        """
        redundant = []
        
        # Group tests by similar names
        name_groups = {}
        for test_func in test_functions:
            # Extract base name (remove numbers, variations)
            base_name = test_func['name']
            # Remove common suffixes/prefixes that indicate variations
            for suffix in ['_1', '_2', '_alt', '_alternative', '_copy', '_duplicate']:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)]
                    break
            
            if base_name not in name_groups:
                name_groups[base_name] = []
            name_groups[base_name].append(test_func)
        
        # Find groups with multiple similar tests
        for base_name, group in name_groups.items():
            if len(group) > 1:
                # Sort by line count (keep the most comprehensive one)
                group.sort(key=lambda x: x['body_lines'], reverse=True)
                # Mark others as potentially redundant
                for test_func in group[1:]:
                    redundant.append(test_func['name'])
        
        # Detect tests with very similar docstrings
        docstring_groups = {}
        for test_func in test_functions:
            if test_func['docstring']:
                # Normalize docstring for comparison
                normalized = test_func['docstring'].lower().strip()
                if normalized not in docstring_groups:
                    docstring_groups[normalized] = []
                docstring_groups[normalized].append(test_func['name'])
        
        # Add tests with identical docstrings as redundant
        for docstring, tests in docstring_groups.items():
            if len(tests) > 1:
                redundant.extend(tests[1:])  # Keep first, mark others as redundant
        
        return list(set(redundant))  # Remove duplicates
    
    async def _detect_obsolete_tests(self, test_file: Path, content: str) -> List[str]:
        """
        Detect obsolete tests based on outdated patterns.
        
        Args:
            test_file: Path to test file
            content: File content
            
        Returns:
            List of obsolete test names
        """
        obsolete = []
        
        try:
            tree = ast.parse(content)
            
            # Patterns that might indicate obsolete tests
            obsolete_patterns = [
                'deprecated',
                'legacy',
                'old_',
                'temp_',
                'TODO',
                'FIXME',
                'skip',
                'xfail'
            ]
            
            # Check imports for obsolete modules
            obsolete_imports = [
                'unittest2',  # Obsolete unittest version
                'nose',       # Obsolete test framework
                'mock',       # Use unittest.mock instead
            ]
            
            # Find imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            
            # Check for obsolete imports
            has_obsolete_imports = any(imp in imports for imp in obsolete_imports)
            
            # Find test functions and check for obsolete patterns
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith('test_'):
                        # Check function name for obsolete patterns
                        name_lower = node.name.lower()
                        if any(pattern in name_lower for pattern in obsolete_patterns):
                            obsolete.append(node.name)
                            continue
                        
                        # Check docstring for obsolete indicators
                        docstring = ast.get_docstring(node)
                        if docstring:
                            docstring_lower = docstring.lower()
                            if any(pattern in docstring_lower for pattern in obsolete_patterns):
                                obsolete.append(node.name)
                                continue
                        
                        # Check for pytest skip/xfail decorators
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Name):
                                if decorator.id in ['skip', 'xfail']:
                                    obsolete.append(node.name)
                                    break
                            elif isinstance(decorator, ast.Attribute):
                                if decorator.attr in ['skip', 'xfail']:
                                    obsolete.append(node.name)
                                    break
                        
                        # If file has obsolete imports, mark all tests as potentially obsolete
                        if has_obsolete_imports:
                            obsolete.append(node.name)
            
        except Exception as e:
            print(f"Error detecting obsolete tests in {test_file}: {e}")
        
        return list(set(obsolete))  # Remove duplicates
    
    async def _calculate_test_effectiveness(
        self,
        total_tests: int,
        redundant_tests: List[str],
        obsolete_tests: List[str],
        coverage_per_test: Dict[str, float]
    ) -> float:
        """
        Calculate test effectiveness score.
        
        Args:
            total_tests: Total number of tests
            redundant_tests: List of redundant tests
            obsolete_tests: List of obsolete tests
            coverage_per_test: Coverage contribution per test
            
        Returns:
            Test effectiveness score (0.0 to 1.0)
        """
        if total_tests == 0:
            return 0.0
        
        # Base score starts at 1.0
        effectiveness = 1.0
        
        # Penalize for redundant tests
        redundancy_penalty = len(redundant_tests) / total_tests * 0.3
        effectiveness -= redundancy_penalty
        
        # Penalize for obsolete tests
        obsolete_penalty = len(obsolete_tests) / total_tests * 0.4
        effectiveness -= obsolete_penalty
        
        # Bonus for good coverage distribution
        if coverage_per_test:
            avg_coverage = sum(coverage_per_test.values()) / len(coverage_per_test)
            coverage_variance = sum(
                (cov - avg_coverage) ** 2 for cov in coverage_per_test.values()
            ) / len(coverage_per_test)
            
            # Lower variance (more consistent coverage) is better
            if coverage_variance < 5.0:  # Low variance threshold
                effectiveness += 0.1
        
        # Ensure score is between 0.0 and 1.0
        return max(0.0, min(1.0, effectiveness))
    
    def get_coverage_summary(self) -> Dict[str, Any]:
        """
        Get summary of coverage analysis.
        
        Returns:
            Dictionary with coverage summary
        """
        if not self._coverage_data:
            return {}
        
        summary = {
            "total_coverage": self._coverage_data.total_coverage,
            "files_analyzed": len(self._coverage_data.file_coverage),
            "untested_functions": len(self._coverage_data.untested_functions),
            "untested_classes": len(self._coverage_data.untested_classes),
            "branch_coverage": self._coverage_data.branch_coverage,
            "meets_threshold": self._coverage_data.total_coverage >= self.config.min_coverage_threshold
        }
        
        # Add test quality metrics if available
        if self._test_quality_data:
            summary.update({
                "total_tests": self._test_quality_data.total_tests,
                "redundant_tests": len(self._test_quality_data.redundant_tests),
                "obsolete_tests": len(self._test_quality_data.obsolete_tests),
                "test_effectiveness": self._test_quality_data.test_effectiveness_score
            })
        
        return summary
    
    async def _generate_function_test_suggestion(self, func_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate test suggestion for an untested function.
        
        Args:
            func_info: Function information from coverage analysis
            
        Returns:
            Dictionary with test suggestion details
        """
        try:
            file_path = func_info['file_path']
            function_name = func_info['function_name']
            args = func_info.get('args', [])
            is_async = func_info.get('is_async', False)
            decorators = func_info.get('decorators', [])
            
            # Analyze function to determine test type
            test_type = await self._determine_function_test_type(file_path, function_name)
            
            # Generate test template
            test_template = await self._generate_function_test_template(
                function_name, args, is_async, test_type, file_path
            )
            
            # Calculate priority score
            priority_score = await self._calculate_test_priority(
                func_info['coverage_percentage'],
                len(args),
                is_async,
                decorators,
                test_type
            )
            
            # Generate test file suggestion
            test_file_path = await self._suggest_test_file_path(file_path)
            
            return {
                'type': 'function',
                'target_file': file_path,
                'target_name': function_name,
                'test_file': test_file_path,
                'test_template': test_template,
                'priority_score': priority_score,
                'test_type': test_type,
                'description': f"Add tests for function '{function_name}' with {len(args)} parameters",
                'complexity': 'low' if len(args) <= 2 else 'medium' if len(args) <= 4 else 'high',
                'estimated_effort': self._estimate_test_effort(test_type, len(args), is_async),
                'suggestions': await self._generate_specific_test_cases(function_name, args, test_type)
            }
            
        except Exception as e:
            print(f"Error generating function test suggestion: {e}")
            return None
    
    async def _generate_class_test_suggestion(self, class_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate test suggestion for an untested class.
        
        Args:
            class_info: Class information from coverage analysis
            
        Returns:
            Dictionary with test suggestion details
        """
        try:
            file_path = class_info['file_path']
            class_name = class_info['class_name']
            untested_methods = class_info.get('untested_methods', [])
            base_classes = class_info.get('base_classes', [])
            
            # Analyze class to determine test type
            test_type = await self._determine_class_test_type(file_path, class_name, base_classes)
            
            # Generate test template
            test_template = await self._generate_class_test_template(
                class_name, untested_methods, test_type, file_path
            )
            
            # Calculate priority score
            priority_score = await self._calculate_class_test_priority(
                class_info['coverage_percentage'],
                len(untested_methods),
                base_classes,
                test_type
            )
            
            # Generate test file suggestion
            test_file_path = await self._suggest_test_file_path(file_path)
            
            return {
                'type': 'class',
                'target_file': file_path,
                'target_name': class_name,
                'test_file': test_file_path,
                'test_template': test_template,
                'priority_score': priority_score,
                'test_type': test_type,
                'description': f"Add tests for class '{class_name}' with {len(untested_methods)} untested methods",
                'complexity': 'low' if len(untested_methods) <= 3 else 'medium' if len(untested_methods) <= 6 else 'high',
                'estimated_effort': self._estimate_class_test_effort(test_type, len(untested_methods), base_classes),
                'untested_methods': untested_methods,
                'suggestions': await self._generate_class_test_cases(class_name, untested_methods, test_type)
            }
            
        except Exception as e:
            print(f"Error generating class test suggestion: {e}")
            return None
    
    async def _determine_function_test_type(self, file_path: Path, function_name: str) -> str:
        """
        Determine the type of test needed for a function.
        
        Args:
            file_path: Path to the file containing the function
            function_name: Name of the function
            
        Returns:
            Test type string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Analyze function characteristics
            if 'async def' in content and function_name in content:
                return 'async'
            elif any(keyword in content for keyword in ['requests.', 'httpx.', 'aiohttp.']):
                return 'api'
            elif any(keyword in content for keyword in ['open(', 'Path(', 'os.path']):
                return 'file_io'
            elif any(keyword in content for keyword in ['connect(', 'cursor(', 'session']):
                return 'database'
            elif 'raise' in content or 'except' in content:
                return 'exception_handling'
            elif any(keyword in content for keyword in ['return', 'yield']):
                return 'unit'
            else:
                return 'basic'
                
        except Exception:
            return 'basic'
    
    async def _determine_class_test_type(self, file_path: Path, class_name: str, base_classes: List[str]) -> str:
        """
        Determine the type of test needed for a class.
        
        Args:
            file_path: Path to the file containing the class
            class_name: Name of the class
            base_classes: List of base class names
            
        Returns:
            Test type string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Analyze class characteristics
            if any('Exception' in base for base in base_classes):
                return 'exception'
            elif any(keyword in content for keyword in ['__enter__', '__exit__']):
                return 'context_manager'
            elif any(keyword in content for keyword in ['__iter__', '__next__']):
                return 'iterator'
            elif any(keyword in content for keyword in ['async def']):
                return 'async_class'
            elif any(keyword in content for keyword in ['@property', '@staticmethod', '@classmethod']):
                return 'property_class'
            else:
                return 'standard'
                
        except Exception:
            return 'standard'
    
    async def _generate_function_test_template(
        self, 
        function_name: str, 
        args: List[str], 
        is_async: bool, 
        test_type: str, 
        file_path: Path
    ) -> str:
        """
        Generate test template for a function.
        
        Args:
            function_name: Name of the function
            args: Function arguments
            is_async: Whether function is async
            test_type: Type of test needed
            file_path: Path to source file
            
        Returns:
            Test template string
        """
        # Get module import path
        module_path = await self._get_module_import_path(file_path)
        
        # Generate test function name
        test_func_name = f"test_{function_name}"
        
        # Generate imports
        imports = [f"from {module_path} import {function_name}"]
        if is_async:
            imports.append("import pytest")
        if test_type == 'api':
            imports.extend(["import httpx", "from unittest.mock import patch"])
        elif test_type == 'file_io':
            imports.extend(["from pathlib import Path", "import tempfile"])
        elif test_type == 'database':
            imports.extend(["from unittest.mock import Mock, patch"])
        elif test_type == 'exception_handling':
            imports.append("import pytest")
        
        # Generate test body
        if test_type == 'async':
            test_body = f'''@pytest.mark.asyncio
async def {test_func_name}():
    """Test {function_name} function."""
    # Arrange
    {self._generate_test_args(args)}
    
    # Act
    result = await {function_name}({', '.join(args) if args else ''})
    
    # Assert
    assert result is not None
    # TODO: Add specific assertions'''
        
        elif test_type == 'api':
            test_body = f'''@patch('httpx.get')
def {test_func_name}(mock_get):
    """Test {function_name} API function."""
    # Arrange
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {{"data": "test"}}
    {self._generate_test_args(args)}
    
    # Act
    result = {function_name}({', '.join(args) if args else ''})
    
    # Assert
    assert result is not None
    mock_get.assert_called_once()'''
        
        elif test_type == 'file_io':
            test_body = f'''def {test_func_name}():
    """Test {function_name} file I/O function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Arrange
        test_file = Path(temp_dir) / "test_file.txt"
        {self._generate_test_args(args)}
        
        # Act
        result = {function_name}({', '.join(args) if args else ''})
        
        # Assert
        assert result is not None'''
        
        elif test_type == 'exception_handling':
            test_body = f'''def {test_func_name}():
    """Test {function_name} exception handling."""
    # Test normal case
    {self._generate_test_args(args)}
    result = {function_name}({', '.join(args) if args else ''})
    assert result is not None
    
    # Test exception case
    with pytest.raises(Exception):  # TODO: Specify exact exception type
        {function_name}(None)  # TODO: Provide invalid input'''
        
        else:  # basic/unit test
            test_body = f'''def {test_func_name}():
    """Test {function_name} function."""
    # Arrange
    {self._generate_test_args(args)}
    
    # Act
    result = {function_name}({', '.join(args) if args else ''})
    
    # Assert
    assert result is not None
    # TODO: Add specific assertions based on expected behavior'''
        
        return '\n'.join(imports) + '\n\n\n' + test_body
    
    async def _generate_class_test_template(
        self, 
        class_name: str, 
        untested_methods: List[str], 
        test_type: str, 
        file_path: Path
    ) -> str:
        """
        Generate test template for a class.
        
        Args:
            class_name: Name of the class
            untested_methods: List of untested method names
            test_type: Type of test needed
            file_path: Path to source file
            
        Returns:
            Test template string
        """
        # Get module import path
        module_path = await self._get_module_import_path(file_path)
        
        # Generate test class name
        test_class_name = f"Test{class_name}"
        
        # Generate imports
        imports = [f"from {module_path} import {class_name}"]
        if test_type == 'async_class':
            imports.append("import pytest")
        elif test_type == 'exception':
            imports.append("import pytest")
        elif test_type in ['context_manager', 'iterator']:
            imports.append("from unittest.mock import Mock")
        
        # Generate fixture for class instance
        fixture = f'''@pytest.fixture
def {class_name.lower()}_instance():
    """Create {class_name} instance for testing."""
    return {class_name}()'''
        
        # Generate test methods
        test_methods = []
        for method_name in untested_methods:
            if method_name.startswith('__') and method_name.endswith('__'):
                # Special method
                test_method = f'''    def test_{method_name.strip('_')}(self, {class_name.lower()}_instance):
        """Test {method_name} method."""
        # TODO: Implement test for special method {method_name}
        pass'''
            else:
                # Regular method
                test_method = f'''    def test_{method_name}(self, {class_name.lower()}_instance):
        """Test {method_name} method."""
        # Arrange
        # TODO: Set up test data
        
        # Act
        result = {class_name.lower()}_instance.{method_name}()
        
        # Assert
        assert result is not None
        # TODO: Add specific assertions'''
            
            test_methods.append(test_method)
        
        # Generate class test body
        class_body = f'''class {test_class_name}:
    """Test cases for {class_name} class."""

{chr(10).join(test_methods)}'''
        
        return '\n'.join(imports) + '\n\n\n' + fixture + '\n\n\n' + class_body
    
    def _generate_test_args(self, args: List[str]) -> str:
        """Generate test argument assignments."""
        if not args:
            return "# No arguments needed"
        
        arg_assignments = []
        for arg in args:
            if arg in ['self', 'cls']:
                continue
            # Generate appropriate test values based on argument name
            if 'id' in arg.lower():
                arg_assignments.append(f"{arg} = 1")
            elif 'name' in arg.lower():
                arg_assignments.append(f'{arg} = "test_name"')
            elif 'path' in arg.lower():
                arg_assignments.append(f'{arg} = Path("test_path")')
            elif 'data' in arg.lower():
                arg_assignments.append(f'{arg} = {{"key": "value"}}')
            elif 'count' in arg.lower() or 'num' in arg.lower():
                arg_assignments.append(f"{arg} = 5")
            elif 'flag' in arg.lower() or 'enable' in arg.lower():
                arg_assignments.append(f"{arg} = True")
            else:
                arg_assignments.append(f'{arg} = "test_value"')
        
        return '\n    '.join(arg_assignments)
    
    async def _calculate_test_priority(
        self, 
        coverage_percentage: float, 
        arg_count: int, 
        is_async: bool, 
        decorators: List[str], 
        test_type: str
    ) -> float:
        """
        Calculate priority score for test implementation.
        
        Args:
            coverage_percentage: Current coverage percentage
            arg_count: Number of function arguments
            is_async: Whether function is async
            decorators: List of decorators
            test_type: Type of test needed
            
        Returns:
            Priority score (0.0 to 10.0)
        """
        priority = 5.0  # Base priority
        
        # Higher priority for completely untested code
        if coverage_percentage == 0:
            priority += 3.0
        elif coverage_percentage < 25:
            priority += 2.0
        elif coverage_percentage < 50:
            priority += 1.0
        
        # Adjust for complexity
        if arg_count > 4:
            priority += 1.0  # Complex functions need tests more
        elif arg_count == 0:
            priority -= 0.5  # Simple functions are lower priority
        
        # Adjust for async functions
        if is_async:
            priority += 0.5  # Async functions are slightly higher priority
        
        # Adjust for decorators
        if any('property' in dec.lower() for dec in decorators):
            priority -= 0.5  # Properties are lower priority
        if any('staticmethod' in dec.lower() for dec in decorators):
            priority += 0.5  # Static methods are higher priority
        
        # Adjust for test type
        type_priorities = {
            'exception_handling': 2.0,
            'api': 1.5,
            'database': 1.5,
            'file_io': 1.0,
            'async': 1.0,
            'unit': 0.5,
            'basic': 0.0
        }
        priority += type_priorities.get(test_type, 0.0)
        
        return min(10.0, max(0.0, priority))
    
    async def _calculate_class_test_priority(
        self, 
        coverage_percentage: float, 
        untested_method_count: int, 
        base_classes: List[str], 
        test_type: str
    ) -> float:
        """
        Calculate priority score for class test implementation.
        
        Args:
            coverage_percentage: Current coverage percentage
            untested_method_count: Number of untested methods
            base_classes: List of base class names
            test_type: Type of test needed
            
        Returns:
            Priority score (0.0 to 10.0)
        """
        priority = 5.0  # Base priority
        
        # Higher priority for completely untested classes
        if coverage_percentage == 0:
            priority += 3.0
        elif coverage_percentage < 25:
            priority += 2.0
        
        # Adjust for number of untested methods
        if untested_method_count > 5:
            priority += 2.0
        elif untested_method_count > 2:
            priority += 1.0
        
        # Adjust for inheritance
        if base_classes:
            priority += 0.5  # Inherited classes need more testing
        
        # Adjust for test type
        type_priorities = {
            'exception': 2.0,
            'context_manager': 1.5,
            'iterator': 1.5,
            'async_class': 1.0,
            'property_class': 0.5,
            'standard': 0.0
        }
        priority += type_priorities.get(test_type, 0.0)
        
        return min(10.0, max(0.0, priority))
    
    def _estimate_test_effort(self, test_type: str, arg_count: int, is_async: bool) -> str:
        """
        Estimate effort required to implement test.
        
        Args:
            test_type: Type of test needed
            arg_count: Number of arguments
            is_async: Whether function is async
            
        Returns:
            Effort estimate string
        """
        base_effort = {
            'basic': 1,
            'unit': 1,
            'async': 2,
            'api': 3,
            'file_io': 2,
            'database': 3,
            'exception_handling': 2
        }.get(test_type, 1)
        
        # Adjust for complexity
        if arg_count > 4:
            base_effort += 1
        if is_async:
            base_effort += 1
        
        if base_effort <= 2:
            return 'low'
        elif base_effort <= 4:
            return 'medium'
        else:
            return 'high'
    
    def _estimate_class_test_effort(self, test_type: str, method_count: int, base_classes: List[str]) -> str:
        """
        Estimate effort required to implement class test.
        
        Args:
            test_type: Type of test needed
            method_count: Number of methods to test
            base_classes: List of base classes
            
        Returns:
            Effort estimate string
        """
        base_effort = {
            'standard': 1,
            'property_class': 1,
            'async_class': 2,
            'iterator': 2,
            'context_manager': 3,
            'exception': 2
        }.get(test_type, 1)
        
        # Adjust for method count
        base_effort += method_count // 3
        
        # Adjust for inheritance
        if base_classes:
            base_effort += 1
        
        if base_effort <= 3:
            return 'low'
        elif base_effort <= 6:
            return 'medium'
        else:
            return 'high'
    
    async def _suggest_test_file_path(self, source_file: Path) -> Path:
        """
        Suggest appropriate test file path for a source file.
        
        Args:
            source_file: Path to source file
            
        Returns:
            Suggested test file path
        """
        # Get relative path from target directory
        try:
            rel_path = source_file.relative_to(self.target_directory)
        except ValueError:
            rel_path = source_file
        
        # Generate test file name
        test_filename = f"test_{rel_path.stem}.py"
        
        # Suggest test directory structure
        test_dir = self.target_directory / "tests"
        
        # Maintain directory structure in tests
        if len(rel_path.parts) > 1:
            test_subdir = test_dir / Path(*rel_path.parts[:-1])
            return test_subdir / test_filename
        else:
            return test_dir / test_filename
    
    async def _get_module_import_path(self, file_path: Path) -> str:
        """
        Get module import path for a file.
        
        Args:
            file_path: Path to source file
            
        Returns:
            Module import path string
        """
        try:
            rel_path = file_path.relative_to(self.target_directory)
            # Remove .py extension and convert path separators to dots
            module_path = str(rel_path.with_suffix('')).replace('/', '.').replace('\\', '.')
            return module_path
        except ValueError:
            # Fallback to filename without extension
            return file_path.stem
    
    async def _generate_specific_test_cases(self, function_name: str, args: List[str], test_type: str) -> List[str]:
        """
        Generate specific test case suggestions.
        
        Args:
            function_name: Name of the function
            args: Function arguments
            test_type: Type of test needed
            
        Returns:
            List of specific test case suggestions
        """
        suggestions = []
        
        # Basic test cases
        suggestions.append(f"Test {function_name} with valid inputs")
        
        if args:
            suggestions.append(f"Test {function_name} with edge case inputs")
            suggestions.append(f"Test {function_name} with invalid inputs")
        
        # Type-specific suggestions
        if test_type == 'exception_handling':
            suggestions.extend([
                f"Test {function_name} exception handling",
                f"Test {function_name} error recovery"
            ])
        elif test_type == 'api':
            suggestions.extend([
                f"Test {function_name} with successful API response",
                f"Test {function_name} with API error response",
                f"Test {function_name} with network timeout"
            ])
        elif test_type == 'file_io':
            suggestions.extend([
                f"Test {function_name} with existing file",
                f"Test {function_name} with non-existent file",
                f"Test {function_name} with permission errors"
            ])
        elif test_type == 'database':
            suggestions.extend([
                f"Test {function_name} with valid database connection",
                f"Test {function_name} with database connection failure",
                f"Test {function_name} with transaction rollback"
            ])
        
        return suggestions
    
    async def _generate_class_test_cases(self, class_name: str, methods: List[str], test_type: str) -> List[str]:
        """
        Generate specific test case suggestions for a class.
        
        Args:
            class_name: Name of the class
            methods: List of method names
            test_type: Type of test needed
            
        Returns:
            List of specific test case suggestions
        """
        suggestions = []
        
        # Basic test cases
        suggestions.append(f"Test {class_name} initialization")
        
        for method in methods:
            suggestions.append(f"Test {class_name}.{method} method")
        
        # Type-specific suggestions
        if test_type == 'context_manager':
            suggestions.extend([
                f"Test {class_name} context manager entry",
                f"Test {class_name} context manager exit",
                f"Test {class_name} context manager exception handling"
            ])
        elif test_type == 'iterator':
            suggestions.extend([
                f"Test {class_name} iteration",
                f"Test {class_name} iterator exhaustion",
                f"Test {class_name} iterator reset"
            ])
        elif test_type == 'exception':
            suggestions.extend([
                f"Test {class_name} exception raising",
                f"Test {class_name} exception message",
                f"Test {class_name} exception inheritance"
            ])
        
        return suggestions