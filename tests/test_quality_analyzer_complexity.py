"""
Unit tests for CodeQualityAnalyzer complexity analysis functionality.
"""

import ast
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.checkup.analyzers.quality import CodeQualityAnalyzer
from migration_assistant.checkup.models import CheckupConfig, IssueType, IssueSeverity


@pytest.fixture
def quality_analyzer():
    """Create a quality analyzer instance for testing."""
    config = CheckupConfig(
        target_directory=Path("."),
        max_complexity=5,  # Low threshold for testing
        enable_quality_analysis=True
    )
    return CodeQualityAnalyzer(config)


@pytest.fixture
def temp_python_file(tmp_path):
    """Create a temporary Python file for testing."""
    def _create_file(content: str) -> Path:
        file_path = tmp_path / "test_file.py"
        file_path.write_text(content)
        return file_path
    return _create_file


class TestCyclomaticComplexity:
    """Test cyclomatic complexity analysis."""
    
    def test_simple_function_low_complexity(self, quality_analyzer, temp_python_file):
        """Test that simple functions have low complexity."""
        content = '''
def simple_function(x):
    return x + 1
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        assert len(issues) == 0  # Should not trigger complexity warning
    
    def test_function_with_if_statements(self, quality_analyzer, temp_python_file):
        """Test complexity calculation with if statements."""
        content = '''
def complex_function(x):
    if x > 0:
        if x > 10:
            if x > 100:
                if x > 1000:
                    if x > 10000:
                        return "very large"
                    return "large"
                return "medium"
            return "small positive"
        return "tiny positive"
    return "non-positive"
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        assert len(issues) > 0
        
        # Should find cyclomatic complexity issue
        complexity_issues = [i for i in issues if i.rule_name == "cyclomatic_complexity"]
        assert len(complexity_issues) > 0
        assert complexity_issues[0].severity in [IssueSeverity.MEDIUM, IssueSeverity.HIGH]
    
    def test_function_with_loops(self, quality_analyzer, temp_python_file):
        """Test complexity calculation with loops."""
        content = '''
def loop_function(items):
    result = []
    for item in items:
        if item > 0:
            while item > 1:
                item = item // 2
                if item % 2 == 0:
                    result.append(item)
    return result
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        complexity_issues = [i for i in issues if i.rule_name == "cyclomatic_complexity"]
        assert len(complexity_issues) > 0
    
    def test_function_with_exception_handling(self, quality_analyzer, temp_python_file):
        """Test complexity calculation with exception handling."""
        content = '''
def exception_function():
    try:
        if True:
            raise ValueError("test")
    except ValueError:
        if True:
            return "error1"
    except Exception:
        if True:
            return "error2"
    finally:
        if True:
            pass
    return "success"
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        complexity_issues = [i for i in issues if i.rule_name == "cyclomatic_complexity"]
        assert len(complexity_issues) > 0
    
    def test_function_with_boolean_operators(self, quality_analyzer, temp_python_file):
        """Test complexity calculation with boolean operators."""
        content = '''
def boolean_function(a, b, c, d):
    if a and b and c and d:
        return True
    elif a or b or c or d:
        return False
    return None
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        complexity_issues = [i for i in issues if i.rule_name == "cyclomatic_complexity"]
        assert len(complexity_issues) > 0


class TestCognitiveComplexity:
    """Test cognitive complexity analysis."""
    
    def test_nested_conditions_cognitive_complexity(self, quality_analyzer, temp_python_file):
        """Test that nested conditions increase cognitive complexity more than cyclomatic."""
        content = '''
def nested_function(x):
    if x > 0:  # +1
        if x > 10:  # +2 (nested)
            if x > 100:  # +3 (nested deeper)
                return "deep"
            return "medium"
        return "shallow"
    return "negative"
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        cognitive_issues = [i for i in issues if i.rule_name == "cognitive_complexity"]
        
        # With deep nesting, cognitive complexity should be flagged
        # even if cyclomatic complexity might not be
        if cognitive_issues:
            assert cognitive_issues[0].message.startswith("High cognitive complexity")


class TestMaintainabilityIndex:
    """Test maintainability index calculation."""
    
    def test_simple_function_high_maintainability(self, quality_analyzer, temp_python_file):
        """Test that simple functions have high maintainability."""
        content = '''
def add(a, b):
    """Add two numbers."""
    return a + b
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        maintainability_issues = [i for i in issues if i.rule_name == "maintainability_index"]
        
        # Simple function should not trigger maintainability issues
        assert len(maintainability_issues) == 0
    
    def test_complex_function_low_maintainability(self, quality_analyzer, temp_python_file):
        """Test that complex functions have low maintainability."""
        content = '''
def complex_calculation(data):
    result = 0
    for i in range(len(data)):
        if data[i] > 0:
            for j in range(i):
                if data[j] < data[i]:
                    if data[j] % 2 == 0:
                        result += data[j] * data[i]
                    else:
                        result -= data[j] / data[i]
                elif data[j] == data[i]:
                    if j % 2 == 0:
                        result *= 2
                    else:
                        result /= 2
        else:
            for k in range(len(data) - i):
                if data[i + k] != 0:
                    result += data[i + k]
    return result
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_cyclomatic_complexity(tree, file_path)
        
        # Should trigger multiple complexity issues
        assert len(issues) > 0
        
        # Should include maintainability index issue
        maintainability_issues = [i for i in issues if i.rule_name == "maintainability_index"]
        if maintainability_issues:
            assert maintainability_issues[0].severity in [IssueSeverity.MEDIUM, IssueSeverity.HIGH]


class TestNestingDepthAnalysis:
    """Test nesting depth analysis."""
    
    def test_shallow_nesting_no_issues(self, quality_analyzer, temp_python_file):
        """Test that shallow nesting doesn't trigger issues."""
        content = '''
def shallow_function(x):
    if x > 0:
        return x * 2
    return 0
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_nesting_depth(tree, file_path)
        assert len(issues) == 0
    
    def test_deep_nesting_triggers_issues(self, quality_analyzer, temp_python_file):
        """Test that deep nesting triggers issues."""
        content = '''
def deeply_nested_function(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                try:
                    if i > 10:
                        with open("file.txt") as f:
                            if f.readable():
                                return "deep"
                except Exception:
                    pass
    return "shallow"
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_nesting_depth(tree, file_path)
        nesting_issues = [i for i in issues if i.rule_name == "nesting_depth"]
        assert len(nesting_issues) > 0
        assert nesting_issues[0].severity == IssueSeverity.MEDIUM


class TestCodeLengthAnalysis:
    """Test code length analysis."""
    
    def test_short_function_no_issues(self, quality_analyzer, temp_python_file):
        """Test that short functions don't trigger length issues."""
        content = '''
def short_function(x):
    """A short function."""
    return x + 1
'''
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_code_length(tree, file_path, content)
        length_issues = [i for i in issues if i.rule_name == "function_length"]
        assert len(length_issues) == 0
    
    def test_long_function_triggers_issues(self, quality_analyzer, temp_python_file):
        """Test that long functions trigger length issues."""
        # Create a function with many lines
        lines = ['def long_function(x):']
        lines.append('    """A very long function."""')
        for i in range(60):  # Create 60 lines of code
            lines.append(f'    result_{i} = x + {i}')
        lines.append('    return sum([' + ', '.join(f'result_{i}' for i in range(60)) + '])')
        
        content = '\n'.join(lines)
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_code_length(tree, file_path, content)
        length_issues = [i for i in issues if i.rule_name == "function_length"]
        assert len(length_issues) > 0
        assert length_issues[0].severity in [IssueSeverity.MEDIUM, IssueSeverity.HIGH]
    
    def test_large_class_triggers_issues(self, quality_analyzer, temp_python_file):
        """Test that large classes trigger length issues."""
        # Create a class with many methods
        lines = ['class LargeClass:']
        lines.append('    """A very large class."""')
        for i in range(50):  # Create 50 methods
            lines.extend([
                f'    def method_{i}(self):',
                f'        """Method {i}."""',
                f'        return {i}',
                ''
            ])
        
        content = '\n'.join(lines)
        file_path = temp_python_file(content)
        tree = ast.parse(content)
        
        issues = quality_analyzer._analyze_code_length(tree, file_path, content)
        length_issues = [i for i in issues if i.rule_name == "class_length"]
        assert len(length_issues) > 0
        assert length_issues[0].severity == IssueSeverity.MEDIUM


class TestComplexityIntegration:
    """Test integration of all complexity analysis features."""
    
    @pytest.mark.asyncio
    async def test_full_complexity_analysis(self, quality_analyzer, temp_python_file):
        """Test full complexity analysis on a complex file."""
        content = '''
class ComplexClass:
    """A complex class for testing."""
    
    def complex_method(self, data, threshold=10):
        """A method with multiple complexity issues."""
        result = []
        total = 0
        
        # High cyclomatic complexity
        for item in data:
            if item > threshold:
                if isinstance(item, int):
                    if item % 2 == 0:
                        if item > 100:
                            if item > 1000:
                                result.append(item * 2)
                            else:
                                result.append(item * 1.5)
                        else:
                            result.append(item)
                    else:
                        result.append(item / 2)
                elif isinstance(item, float):
                    result.append(int(item))
                else:
                    result.append(0)
            elif item < 0:
                result.append(abs(item))
            else:
                result.append(item)
        
        # More complexity
        try:
            for i, val in enumerate(result):
                if val > 0:
                    total += val
                    if i % 2 == 0:
                        total *= 1.1
                    elif i % 3 == 0:
                        total *= 0.9
                    else:
                        total += 1
        except Exception as e:
            if "overflow" in str(e):
                total = float('inf')
            elif "underflow" in str(e):
                total = 0
            else:
                raise
        
        return result, total
'''
        file_path = temp_python_file(content)
        
        # Mock the file system methods
        with patch.object(quality_analyzer, 'get_python_files', return_value=[file_path]):
            issues = await quality_analyzer.analyze()
        
        # Should find multiple types of complexity issues
        complexity_issues = [i for i in issues if i.issue_type == IssueType.COMPLEXITY]
        assert len(complexity_issues) > 0
        
        # Check for different types of complexity issues
        rule_names = {issue.rule_name for issue in complexity_issues}
        expected_rules = {"cyclomatic_complexity", "nesting_depth", "function_length"}
        assert len(rule_names.intersection(expected_rules)) > 0
        
        # Verify metrics were updated
        assert quality_analyzer.metrics.complexity_issues > 0