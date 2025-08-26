"""
Tests for Coverage Validator

Tests coverage analysis integration with pytest-cov.
"""

import ast
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

from migration_assistant.checkup.validators.coverage import (
    CoverageValidator, CoverageReport, TestQualityMetrics
)
from migration_assistant.checkup.validators.base import ValidationResult
from migration_assistant.checkup.models import (
    CheckupConfig, CoverageGap, IssueType, IssueSeverity
)


@pytest.fixture
def coverage_config():
    """Create test configuration for coverage validation."""
    return CheckupConfig(
        target_directory=Path("/test/project"),
        check_test_coverage=True,
        min_coverage_threshold=80.0
    )


@pytest.fixture
def coverage_validator(coverage_config):
    """Create CoverageValidator instance for testing."""
    return CoverageValidator(coverage_config)


@pytest.fixture
def sample_coverage_xml():
    """Sample coverage XML data."""
    return '''<?xml version="1.0" ?>
<coverage line-rate="0.75" branch-rate="0.65" version="6.5.0">
    <sources>
        <source>/test/project</source>
    </sources>
    <packages>
        <package name="migration_assistant" line-rate="0.75" branch-rate="0.65">
            <classes>
                <class name="migration_assistant/core/test_module.py" filename="migration_assistant/core/test_module.py" line-rate="0.80" branch-rate="0.70">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                        <line number="4" hits="1"/>
                        <line number="5" hits="0"/>
                    </lines>
                </class>
                <class name="migration_assistant/utils/helper.py" filename="migration_assistant/utils/helper.py" line-rate="0.60" branch-rate="0.50">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                        <line number="3" hits="0"/>
                        <line number="4" hits="1"/>
                        <line number="5" hits="1"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>'''


@pytest.fixture
def sample_coverage_json():
    """Sample coverage JSON data."""
    return {
        "meta": {
            "version": "6.5.0",
            "timestamp": "2024-01-01T12:00:00"
        },
        "files": {
            "migration_assistant/core/test_module.py": {
                "executed_lines": [1, 2, 4],
                "missing_lines": [3, 5],
                "excluded_lines": [],
                "summary": {
                    "covered_lines": 3,
                    "num_statements": 5,
                    "percent_covered": 60.0,
                    "missing_lines": 2
                }
            },
            "migration_assistant/utils/helper.py": {
                "executed_lines": [1, 4, 5],
                "missing_lines": [2, 3],
                "excluded_lines": [],
                "summary": {
                    "covered_lines": 3,
                    "num_statements": 5,
                    "percent_covered": 60.0,
                    "missing_lines": 2
                }
            }
        },
        "totals": {
            "covered_lines": 6,
            "num_statements": 10,
            "percent_covered": 60.0,
            "missing_lines": 4
        }
    }


@pytest.fixture
def sample_python_code():
    """Sample Python code for AST analysis."""
    return '''
def tested_function(x, y):
    """This function is tested."""
    return x + y

def untested_function(a, b):
    """This function is not tested."""
    result = a * b
    return result

class TestedClass:
    """This class is partially tested."""
    
    def tested_method(self):
        return "tested"
    
    def untested_method(self):
        return "untested"

class UntestedClass:
    """This class is not tested."""
    
    def method_one(self):
        return 1
    
    def method_two(self):
        return 2
'''


class TestCoverageValidator:
    """Test cases for CoverageValidator."""
    
    def test_init(self, coverage_validator, coverage_config):
        """Test CoverageValidator initialization."""
        assert coverage_validator.config == coverage_config
        assert coverage_validator.target_directory == coverage_config.target_directory
        assert coverage_validator._coverage_data is None
        assert coverage_validator._test_quality_data is None
    
    def test_get_validation_scope(self, coverage_validator):
        """Test validation scope."""
        scope = coverage_validator.get_validation_scope()
        expected_scope = ['test_coverage', 'test_quality', 'untested_code', 'coverage_gaps']
        assert scope == expected_scope
    
    @pytest.mark.asyncio
    async def test_validate_success(self, coverage_validator):
        """Test successful validation."""
        # Mock coverage report generation
        mock_report = CoverageReport(
            total_coverage=85.0,
            file_coverage={"test_file.py": 85.0},
            missing_lines={"test_file.py": [10, 15]},
            untested_functions=[],
            untested_classes=[]
        )
        
        with patch.object(coverage_validator, 'generate_coverage_report', return_value=mock_report):
            with patch.object(coverage_validator, 'identify_untested_code', return_value=[]):
                result = await coverage_validator.validate()
        
        assert result.valid is True
        assert "85.0%" in result.message
        assert result.files_validated == 1
        assert result.validation_details["total_coverage"] == 85.0
        assert result.validation_details["meets_threshold"] is True
    
    @pytest.mark.asyncio
    async def test_validate_below_threshold(self, coverage_validator):
        """Test validation when coverage is below threshold."""
        # Mock coverage report generation
        mock_report = CoverageReport(
            total_coverage=70.0,
            file_coverage={"test_file.py": 70.0},
            missing_lines={"test_file.py": [10, 15, 20]},
            untested_functions=[],
            untested_classes=[]
        )
        
        with patch.object(coverage_validator, 'generate_coverage_report', return_value=mock_report):
            with patch.object(coverage_validator, 'identify_untested_code', return_value=[]):
                result = await coverage_validator.validate()
        
        assert result.valid is False
        assert "70.0%" in result.message
        assert "80.0%" in result.message
        assert result.validation_details["meets_threshold"] is False
    
    @pytest.mark.asyncio
    async def test_validate_failure(self, coverage_validator):
        """Test validation failure."""
        with patch.object(coverage_validator, 'generate_coverage_report', return_value=None):
            result = await coverage_validator.validate()
        
        assert result.valid is False
        assert "Failed to generate coverage report" in result.message
    
    @pytest.mark.asyncio
    async def test_generate_coverage_report_success(self, coverage_validator, sample_coverage_xml, sample_coverage_json):
        """Test successful coverage report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock subprocess.run
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            
            with patch('subprocess.run', return_value=mock_result):
                # Mock file creation and parsing
                with patch.object(coverage_validator, '_parse_coverage_data') as mock_parse:
                    mock_report = CoverageReport(
                        total_coverage=75.0,
                        file_coverage={"test_file.py": 75.0},
                        missing_lines={"test_file.py": [3, 5]},
                        untested_functions=[],
                        untested_classes=[]
                    )
                    mock_parse.return_value = mock_report
                    
                    with patch.object(coverage_validator, '_find_untested_functions', return_value=[]):
                        with patch.object(coverage_validator, '_find_untested_classes', return_value=[]):
                            result = await coverage_validator.generate_coverage_report()
            
            assert result is not None
            assert result.total_coverage == 75.0
            assert coverage_validator._coverage_data == result
    
    @pytest.mark.asyncio
    async def test_generate_coverage_report_timeout(self, coverage_validator):
        """Test coverage report generation timeout."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("pytest", 300)):
            result = await coverage_validator.generate_coverage_report()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_coverage_data_xml(self, coverage_validator, sample_coverage_xml):
        """Test parsing coverage data from XML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as xml_file:
            xml_file.write(sample_coverage_xml)
            xml_path = Path(xml_file.name)
        
        try:
            json_path = Path("nonexistent.json")  # JSON file doesn't exist
            result = await coverage_validator._parse_coverage_data(xml_path, json_path)
            
            assert result is not None
            assert result.total_coverage == 75.0
            assert result.branch_coverage == 65.0
            assert len(result.file_coverage) == 2
            assert "migration_assistant/core/test_module.py" in result.file_coverage
            assert result.file_coverage["migration_assistant/core/test_module.py"] == 60.0  # 3/5 lines covered
            
        finally:
            xml_path.unlink()
    
    @pytest.mark.asyncio
    async def test_parse_coverage_data_json(self, coverage_validator, sample_coverage_json):
        """Test parsing coverage data from JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as json_file:
            json.dump(sample_coverage_json, json_file)
            json_path = Path(json_file.name)
        
        try:
            xml_path = Path("nonexistent.xml")  # XML file doesn't exist
            result = await coverage_validator._parse_coverage_data(xml_path, json_path)
            
            assert result is not None
            assert result.total_coverage == 60.0
            assert len(result.file_coverage) == 2
            assert result.missing_lines["migration_assistant/core/test_module.py"] == [3, 5]
            
        finally:
            json_path.unlink()
    
    @pytest.mark.asyncio
    async def test_find_untested_functions(self, coverage_validator, sample_python_code):
        """Test finding untested functions."""
        file_coverage = {"test_module.py": 60.0}
        missing_lines = {"test_module.py": [6, 7, 8, 9, 16, 17]}  # Lines for untested_function and untested_method
        
        # Mock file system
        test_file = Path("/test/project/test_module.py")
        
        with patch.object(coverage_validator, 'get_target_files', return_value=[test_file]):
            with patch('builtins.open', mock_open(read_data=sample_python_code)):
                with patch.object(test_file, 'relative_to', return_value=Path("test_module.py")):
                    result = await coverage_validator._find_untested_functions(file_coverage, missing_lines)
        
        assert len(result) > 0
        
        # Find the untested function
        untested_func = next((f for f in result if f['function_name'] == 'untested_function'), None)
        assert untested_func is not None
        assert untested_func['file_path'] == test_file
        assert untested_func['coverage_percentage'] < 100
        assert 'args' in untested_func
        assert untested_func['args'] == ['a', 'b']
    
    @pytest.mark.asyncio
    async def test_find_untested_classes(self, coverage_validator, sample_python_code):
        """Test finding untested classes."""
        file_coverage = {"test_module.py": 60.0}
        missing_lines = {"test_module.py": [16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27]}  # Lines for UntestedClass
        
        # Mock file system
        test_file = Path("/test/project/test_module.py")
        
        with patch.object(coverage_validator, 'get_target_files', return_value=[test_file]):
            with patch('builtins.open', mock_open(read_data=sample_python_code)):
                with patch.object(test_file, 'relative_to', return_value=Path("test_module.py")):
                    result = await coverage_validator._find_untested_classes(file_coverage, missing_lines)
        
        assert len(result) > 0
        
        # Find the untested class
        untested_class = next((c for c in result if c['class_name'] == 'UntestedClass'), None)
        assert untested_class is not None
        assert untested_class['file_path'] == test_file
        assert untested_class['coverage_percentage'] < 100
        assert 'untested_methods' in untested_class
        assert len(untested_class['untested_methods']) > 0
    
    @pytest.mark.asyncio
    async def test_identify_untested_code(self, coverage_validator):
        """Test identifying untested code and creating CoverageGap issues."""
        # Mock coverage data
        mock_report = CoverageReport(
            total_coverage=70.0,
            file_coverage={"test_file.py": 60.0},
            missing_lines={"test_file.py": [5, 10]},
            untested_functions=[{
                'file_path': Path("/test/project/test_file.py"),
                'function_name': 'untested_func',
                'line_start': 5,
                'line_end': 8,
                'coverage_percentage': 0.0,
                'args': ['x', 'y']
            }],
            untested_classes=[{
                'file_path': Path("/test/project/test_file.py"),
                'class_name': 'UntestedClass',
                'line_start': 10,
                'line_end': 15,
                'coverage_percentage': 0.0,
                'untested_methods': ['method1', 'method2']
            }]
        )
        
        coverage_validator._coverage_data = mock_report
        
        result = await coverage_validator.identify_untested_code()
        
        assert len(result) >= 3  # At least function, class, and file issues
        
        # Check function issue
        func_issues = [gap for gap in result if gap.function_name == 'untested_func']
        assert len(func_issues) == 1
        assert func_issues[0].severity == IssueSeverity.MEDIUM
        assert func_issues[0].issue_type == IssueType.COVERAGE_GAP
        
        # Check class issue
        class_issues = [gap for gap in result if gap.class_name == 'UntestedClass']
        assert len(class_issues) == 1
        assert class_issues[0].severity == IssueSeverity.MEDIUM
        
        # Check file issue (below threshold)
        file_issues = [gap for gap in result if gap.function_name is None and gap.class_name is None]
        assert len(file_issues) >= 1
    
    def test_get_coverage_summary_no_data(self, coverage_validator):
        """Test coverage summary when no data is available."""
        result = coverage_validator.get_coverage_summary()
        assert result == {}
    
    def test_get_coverage_summary_with_data(self, coverage_validator):
        """Test coverage summary with data."""
        mock_report = CoverageReport(
            total_coverage=85.0,
            file_coverage={"file1.py": 80.0, "file2.py": 90.0},
            missing_lines={},
            untested_functions=[{"name": "func1"}],
            untested_classes=[{"name": "class1"}],
            branch_coverage=75.0
        )
        
        coverage_validator._coverage_data = mock_report
        
        result = coverage_validator.get_coverage_summary()
        
        assert result["total_coverage"] == 85.0
        assert result["files_analyzed"] == 2
        assert result["untested_functions"] == 1
        assert result["untested_classes"] == 1
        assert result["branch_coverage"] == 75.0
        assert result["meets_threshold"] is True


class TestCoverageReport:
    """Test cases for CoverageReport data structure."""
    
    def test_coverage_report_creation(self):
        """Test CoverageReport creation."""
        report = CoverageReport(
            total_coverage=85.0,
            file_coverage={"file1.py": 80.0},
            missing_lines={"file1.py": [5, 10]},
            untested_functions=[],
            untested_classes=[]
        )
        
        assert report.total_coverage == 85.0
        assert len(report.file_coverage) == 1
        assert report.branch_coverage is None
    
    def test_coverage_report_with_branch_coverage(self):
        """Test CoverageReport with branch coverage."""
        report = CoverageReport(
            total_coverage=85.0,
            file_coverage={},
            missing_lines={},
            untested_functions=[],
            untested_classes=[],
            branch_coverage=75.0
        )
        
        assert report.branch_coverage == 75.0


class TestTestQualityMetrics:
    """Test cases for TestQualityMetrics data structure."""
    
    def test_test_quality_metrics_creation(self):
        """Test TestQualityMetrics creation."""
        metrics = TestQualityMetrics(
            total_tests=100,
            redundant_tests=["test1", "test2"],
            obsolete_tests=["test3"],
            test_effectiveness_score=0.85,
            coverage_per_test={"test1": 5.0, "test2": 3.0}
        )
        
        assert metrics.total_tests == 100
        assert len(metrics.redundant_tests) == 2
        assert len(metrics.obsolete_tests) == 1
        assert metrics.test_effectiveness_score == 0.85
        assert len(metrics.coverage_per_test) == 2


class TestTestQualityAnalysis:
    """Test cases for test quality analysis functionality."""
    
    @pytest.fixture
    def sample_test_code(self):
        """Sample test code with various quality issues."""
        return '''
import pytest
from unittest import mock
from src.module import function_to_test

def test_function_basic():
    """Test basic functionality."""
    result = function_to_test(1, 2)
    assert result == 3

def test_function_basic_1():
    """Test basic functionality."""  # Same docstring - redundant
    result = function_to_test(1, 2)
    assert result == 3

def test_function_basic_copy():
    """Test basic functionality copy."""
    result = function_to_test(1, 2)
    assert result == 3

def test_legacy_function():
    """Test legacy functionality that is deprecated."""
    # This test is obsolete
    pass

@pytest.mark.skip(reason="Obsolete test")
def test_old_behavior():
    """Test old behavior."""
    pass

def test_temp_function():
    """Temporary test - TODO: remove this."""
    pass

def test_comprehensive_function():
    """Comprehensive test with multiple assertions."""
    # This test has more lines and should be kept over redundant ones
    result1 = function_to_test(1, 2)
    result2 = function_to_test(3, 4)
    result3 = function_to_test(0, 0)
    
    assert result1 == 3
    assert result2 == 7
    assert result3 == 0
    
    # Additional validation
    with pytest.raises(ValueError):
        function_to_test(None, 1)
'''
    
    @pytest.mark.asyncio
    async def test_analyze_test_quality(self, coverage_validator, sample_test_code):
        """Test test quality analysis."""
        # Mock file system
        test_file = Path("/test/project/test_module.py")
        
        with patch.object(coverage_validator.target_directory, 'rglob') as mock_rglob:
            mock_rglob.return_value = [test_file]
            
            with patch.object(coverage_validator, 'should_validate_file', return_value=True):
                with patch('builtins.open', mock_open(read_data=sample_test_code)):
                    result = await coverage_validator._analyze_test_quality()
        
        assert result is not None
        assert result.total_tests > 0
        assert len(result.redundant_tests) > 0
        assert len(result.obsolete_tests) > 0
        assert 0.0 <= result.test_effectiveness_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_detect_redundant_tests(self, coverage_validator):
        """Test redundant test detection."""
        test_functions = [
            {
                'name': 'test_function_basic',
                'file': Path('test.py'),
                'line_start': 1,
                'line_end': 5,
                'docstring': 'Test basic functionality.',
                'body_lines': 4
            },
            {
                'name': 'test_function_basic_1',
                'file': Path('test.py'),
                'line_start': 6,
                'line_end': 10,
                'docstring': 'Test basic functionality.',  # Same docstring
                'body_lines': 4
            },
            {
                'name': 'test_function_basic_copy',
                'file': Path('test.py'),
                'line_start': 11,
                'line_end': 15,
                'docstring': 'Test basic functionality copy.',
                'body_lines': 4
            },
            {
                'name': 'test_comprehensive_function',
                'file': Path('test.py'),
                'line_start': 16,
                'line_end': 30,
                'docstring': 'Comprehensive test.',
                'body_lines': 14  # More comprehensive
            }
        ]
        
        result = await coverage_validator._detect_redundant_tests(test_functions)
        
        assert len(result) > 0
        # Should detect redundant tests but keep the comprehensive one
        assert 'test_comprehensive_function' not in result
    
    @pytest.mark.asyncio
    async def test_detect_obsolete_tests(self, coverage_validator, sample_test_code):
        """Test obsolete test detection."""
        test_file = Path("/test/project/test_module.py")
        
        result = await coverage_validator._detect_obsolete_tests(test_file, sample_test_code)
        
        assert len(result) > 0
        # Should detect tests with obsolete patterns
        obsolete_names = set(result)
        assert any('legacy' in name.lower() or 'old' in name.lower() or 'temp' in name.lower() 
                  for name in obsolete_names)
    
    @pytest.mark.asyncio
    async def test_calculate_test_effectiveness(self, coverage_validator):
        """Test test effectiveness calculation."""
        total_tests = 10
        redundant_tests = ['test1', 'test2']  # 20% redundant
        obsolete_tests = ['test3']  # 10% obsolete
        coverage_per_test = {f'test{i}': 5.0 for i in range(1, 11)}  # Consistent coverage
        
        result = await coverage_validator._calculate_test_effectiveness(
            total_tests, redundant_tests, obsolete_tests, coverage_per_test
        )
        
        assert 0.0 <= result <= 1.0
        # Should be penalized for redundant and obsolete tests
        assert result < 1.0
    
    @pytest.mark.asyncio
    async def test_validate_test_quality_success(self, coverage_validator):
        """Test successful test quality validation."""
        # Mock high-quality test metrics
        mock_metrics = TestQualityMetrics(
            total_tests=50,
            redundant_tests=['test1', 'test2'],  # Few redundant
            obsolete_tests=['test3'],  # Few obsolete
            test_effectiveness_score=0.85,  # High effectiveness
            coverage_per_test={'test1': 5.0, 'test2': 4.0}
        )
        
        with patch.object(coverage_validator, '_analyze_test_quality', return_value=mock_metrics):
            result = await coverage_validator.validate_test_quality()
        
        assert result.valid is True
        assert result.validation_details['high_quality'] is True
        assert result.validation_details['effectiveness_score'] == 0.85
        assert len(result.issues) == 3  # 2 redundant + 1 obsolete
    
    @pytest.mark.asyncio
    async def test_validate_test_quality_poor(self, coverage_validator):
        """Test test quality validation with poor quality."""
        # Mock poor-quality test metrics
        mock_metrics = TestQualityMetrics(
            total_tests=20,
            redundant_tests=[f'test{i}' for i in range(10)],  # Many redundant
            obsolete_tests=[f'old_test{i}' for i in range(5)],  # Many obsolete
            test_effectiveness_score=0.3,  # Low effectiveness
            coverage_per_test={}
        )
        
        with patch.object(coverage_validator, '_analyze_test_quality', return_value=mock_metrics):
            result = await coverage_validator.validate_test_quality()
        
        assert result.valid is False
        assert result.validation_details['high_quality'] is False
        assert result.validation_details['effectiveness_score'] == 0.3
        assert len(result.issues) == 15  # 10 redundant + 5 obsolete
    
    @pytest.mark.asyncio
    async def test_validate_test_quality_failure(self, coverage_validator):
        """Test test quality validation failure."""
        with patch.object(coverage_validator, '_analyze_test_quality', return_value=None):
            result = await coverage_validator.validate_test_quality()
        
        assert result.valid is False
        assert "Failed to analyze test quality" in result.message


class TestTestSuggestionEngine:
    """Test cases for test suggestion engine functionality."""
    
    @pytest.mark.asyncio
    async def test_suggest_test_implementations(self, coverage_validator):
        """Test test implementation suggestions."""
        # Mock coverage data with untested functions and classes
        mock_report = CoverageReport(
            total_coverage=60.0,
            file_coverage={"test_module.py": 60.0},
            missing_lines={"test_module.py": [5, 10]},
            untested_functions=[{
                'file_path': Path("/test/project/src/module.py"),
                'function_name': 'calculate_sum',
                'line_start': 5,
                'line_end': 8,
                'coverage_percentage': 0.0,
                'args': ['a', 'b'],
                'is_async': False,
                'decorators': []
            }],
            untested_classes=[{
                'file_path': Path("/test/project/src/calculator.py"),
                'class_name': 'Calculator',
                'line_start': 10,
                'line_end': 20,
                'coverage_percentage': 0.0,
                'untested_methods': ['add', 'subtract'],
                'base_classes': []
            }]
        )
        
        coverage_validator._coverage_data = mock_report
        
        with patch.object(coverage_validator, '_generate_function_test_suggestion') as mock_func_suggest:
            with patch.object(coverage_validator, '_generate_class_test_suggestion') as mock_class_suggest:
                mock_func_suggest.return_value = {
                    'type': 'function',
                    'target_name': 'calculate_sum',
                    'priority_score': 8.0,
                    'test_template': 'def test_calculate_sum(): pass'
                }
                mock_class_suggest.return_value = {
                    'type': 'class',
                    'target_name': 'Calculator',
                    'priority_score': 7.0,
                    'test_template': 'class TestCalculator: pass'
                }
                
                result = await coverage_validator.suggest_test_implementations()
        
        assert len(result) == 2
        # Should be sorted by priority (function first with 8.0, then class with 7.0)
        assert result[0]['priority_score'] == 8.0
        assert result[1]['priority_score'] == 7.0
    
    @pytest.mark.asyncio
    async def test_generate_function_test_suggestion(self, coverage_validator):
        """Test function test suggestion generation."""
        func_info = {
            'file_path': Path("/test/project/src/module.py"),
            'function_name': 'calculate_sum',
            'args': ['a', 'b'],
            'is_async': False,
            'decorators': [],
            'coverage_percentage': 0.0
        }
        
        with patch.object(coverage_validator, '_determine_function_test_type', return_value='unit'):
            with patch.object(coverage_validator, '_generate_function_test_template', return_value='test template'):
                with patch.object(coverage_validator, '_calculate_test_priority', return_value=8.0):
                    with patch.object(coverage_validator, '_suggest_test_file_path', return_value=Path('tests/test_module.py')):
                        result = await coverage_validator._generate_function_test_suggestion(func_info)
        
        assert result is not None
        assert result['type'] == 'function'
        assert result['target_name'] == 'calculate_sum'
        assert result['priority_score'] == 8.0
        assert result['test_template'] == 'test template'
        assert 'complexity' in result
        assert 'estimated_effort' in result
    
    @pytest.mark.asyncio
    async def test_generate_class_test_suggestion(self, coverage_validator):
        """Test class test suggestion generation."""
        class_info = {
            'file_path': Path("/test/project/src/calculator.py"),
            'class_name': 'Calculator',
            'untested_methods': ['add', 'subtract'],
            'base_classes': [],
            'coverage_percentage': 0.0
        }
        
        with patch.object(coverage_validator, '_determine_class_test_type', return_value='standard'):
            with patch.object(coverage_validator, '_generate_class_test_template', return_value='test template'):
                with patch.object(coverage_validator, '_calculate_class_test_priority', return_value=7.0):
                    with patch.object(coverage_validator, '_suggest_test_file_path', return_value=Path('tests/test_calculator.py')):
                        result = await coverage_validator._generate_class_test_suggestion(class_info)
        
        assert result is not None
        assert result['type'] == 'class'
        assert result['target_name'] == 'Calculator'
        assert result['priority_score'] == 7.0
        assert result['untested_methods'] == ['add', 'subtract']
    
    @pytest.mark.asyncio
    async def test_determine_function_test_type(self, coverage_validator):
        """Test function test type determination."""
        test_file = Path("/test/project/test_module.py")
        
        # Test async function
        async_code = "async def test_function(): pass"
        with patch('builtins.open', mock_open(read_data=async_code)):
            result = await coverage_validator._determine_function_test_type(test_file, 'test_function')
        assert result == 'async'
        
        # Test API function
        api_code = "import requests\ndef api_function(): requests.get('url')"
        with patch('builtins.open', mock_open(read_data=api_code)):
            result = await coverage_validator._determine_function_test_type(test_file, 'api_function')
        assert result == 'api'
        
        # Test file I/O function
        file_code = "def file_function(): open('file.txt')"
        with patch('builtins.open', mock_open(read_data=file_code)):
            result = await coverage_validator._determine_function_test_type(test_file, 'file_function')
        assert result == 'file_io'
    
    @pytest.mark.asyncio
    async def test_determine_class_test_type(self, coverage_validator):
        """Test class test type determination."""
        test_file = Path("/test/project/test_class.py")
        
        # Test context manager
        context_code = "class TestClass:\n    def __enter__(self): pass\n    def __exit__(self): pass"
        with patch('builtins.open', mock_open(read_data=context_code)):
            result = await coverage_validator._determine_class_test_type(test_file, 'TestClass', [])
        assert result == 'context_manager'
        
        # Test iterator
        iterator_code = "class TestClass:\n    def __iter__(self): pass\n    def __next__(self): pass"
        with patch('builtins.open', mock_open(read_data=iterator_code)):
            result = await coverage_validator._determine_class_test_type(test_file, 'TestClass', [])
        assert result == 'iterator'
        
        # Test exception class
        result = await coverage_validator._determine_class_test_type(test_file, 'TestClass', ['Exception'])
        assert result == 'exception'
    
    @pytest.mark.asyncio
    async def test_generate_function_test_template(self, coverage_validator):
        """Test function test template generation."""
        with patch.object(coverage_validator, '_get_module_import_path', return_value='src.module'):
            result = await coverage_validator._generate_function_test_template(
                'calculate_sum', ['a', 'b'], False, 'unit', Path('/test/project/src/module.py')
            )
        
        assert 'from src.module import calculate_sum' in result
        assert 'def test_calculate_sum():' in result
        assert 'assert result is not None' in result
    
    @pytest.mark.asyncio
    async def test_generate_class_test_template(self, coverage_validator):
        """Test class test template generation."""
        with patch.object(coverage_validator, '_get_module_import_path', return_value='src.calculator'):
            result = await coverage_validator._generate_class_test_template(
                'Calculator', ['add', 'subtract'], 'standard', Path('/test/project/src/calculator.py')
            )
        
        assert 'from src.calculator import Calculator' in result
        assert 'class TestCalculator:' in result
        assert 'def test_add(' in result
        assert 'def test_subtract(' in result
    
    @pytest.mark.asyncio
    async def test_calculate_test_priority(self, coverage_validator):
        """Test test priority calculation."""
        # High priority: untested, complex function
        priority = await coverage_validator._calculate_test_priority(
            coverage_percentage=0.0,
            arg_count=5,
            is_async=True,
            decorators=[],
            test_type='exception_handling'
        )
        assert priority > 7.0
        
        # Low priority: well-tested, simple function
        priority = await coverage_validator._calculate_test_priority(
            coverage_percentage=90.0,
            arg_count=0,
            is_async=False,
            decorators=['@property'],
            test_type='basic'
        )
        assert priority < 5.0
    
    @pytest.mark.asyncio
    async def test_calculate_class_test_priority(self, coverage_validator):
        """Test class test priority calculation."""
        # High priority: untested class with many methods
        priority = await coverage_validator._calculate_class_test_priority(
            coverage_percentage=0.0,
            untested_method_count=8,
            base_classes=['BaseClass'],
            test_type='exception'
        )
        assert priority > 7.0
        
        # Low priority: well-tested class with few methods
        priority = await coverage_validator._calculate_class_test_priority(
            coverage_percentage=80.0,
            untested_method_count=1,
            base_classes=[],
            test_type='standard'
        )
        assert priority < 6.0
    
    def test_estimate_test_effort(self, coverage_validator):
        """Test test effort estimation."""
        # Low effort
        effort = coverage_validator._estimate_test_effort('basic', 2, False)
        assert effort == 'low'
        
        # High effort
        effort = coverage_validator._estimate_test_effort('database', 6, True)
        assert effort == 'high'
    
    def test_estimate_class_test_effort(self, coverage_validator):
        """Test class test effort estimation."""
        # Low effort
        effort = coverage_validator._estimate_class_test_effort('standard', 2, [])
        assert effort == 'low'
        
        # High effort
        effort = coverage_validator._estimate_class_test_effort('context_manager', 8, ['BaseClass'])
        assert effort == 'high'
    
    @pytest.mark.asyncio
    async def test_suggest_test_file_path(self, coverage_validator):
        """Test test file path suggestion."""
        source_file = Path("/test/project/src/utils/helper.py")
        
        result = await coverage_validator._suggest_test_file_path(source_file)
        
        expected = Path("/test/project/tests/src/utils/test_helper.py")
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_get_module_import_path(self, coverage_validator):
        """Test module import path generation."""
        file_path = Path("/test/project/src/utils/helper.py")
        
        result = await coverage_validator._get_module_import_path(file_path)
        
        assert result == "src.utils.helper"
    
    def test_generate_test_args(self, coverage_validator):
        """Test test argument generation."""
        args = ['user_id', 'name', 'data_path', 'count', 'enabled']
        
        result = coverage_validator._generate_test_args(args)
        
        assert 'user_id = 1' in result
        assert 'name = "test_name"' in result
        assert 'data_path = Path("test_path")' in result
        assert 'count = 5' in result
        assert 'enabled = True' in result
    
    @pytest.mark.asyncio
    async def test_generate_specific_test_cases(self, coverage_validator):
        """Test specific test case generation."""
        result = await coverage_validator._generate_specific_test_cases(
            'api_call', ['url', 'data'], 'api'
        )
        
        assert len(result) > 3
        assert any('valid inputs' in case for case in result)
        assert any('API response' in case for case in result)
        assert any('network timeout' in case for case in result)
    
    @pytest.mark.asyncio
    async def test_generate_class_test_cases(self, coverage_validator):
        """Test class test case generation."""
        result = await coverage_validator._generate_class_test_cases(
            'FileManager', ['open', 'close'], 'context_manager'
        )
        
        assert len(result) > 3
        assert any('initialization' in case for case in result)
        assert any('context manager' in case for case in result)
        assert any('FileManager.open' in case for case in result)


@pytest.mark.integration
class TestCoverageValidatorIntegration:
    """Integration tests for CoverageValidator."""
    
    @pytest.mark.asyncio
    async def test_full_coverage_analysis_workflow(self, tmp_path):
        """Test complete coverage analysis workflow."""
        # Create a temporary project structure
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # Create source files
        src_dir = project_dir / "src"
        src_dir.mkdir()
        
        source_file = src_dir / "module.py"
        source_file.write_text('''
def covered_function():
    return "covered"

def uncovered_function():
    return "uncovered"
''')
        
        # Create test files
        test_dir = project_dir / "tests"
        test_dir.mkdir()
        
        test_file = test_dir / "test_module.py"
        test_file.write_text('''
from src.module import covered_function

def test_covered_function():
    assert covered_function() == "covered"
''')
        
        # Create configuration
        config = CheckupConfig(
            target_directory=project_dir,
            min_coverage_threshold=80.0
        )
        
        validator = CoverageValidator(config)
        
        # Mock subprocess call since we don't want to actually run pytest
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch('subprocess.run', return_value=mock_result):
            with patch.object(validator, '_parse_coverage_data') as mock_parse:
                mock_report = CoverageReport(
                    total_coverage=50.0,  # Below threshold
                    file_coverage={"src/module.py": 50.0},
                    missing_lines={"src/module.py": [5, 6]},
                    untested_functions=[],
                    untested_classes=[]
                )
                mock_parse.return_value = mock_report
                
                result = await validator.validate()
        
        # Verify results
        assert result is not None
        assert result.valid is False  # Below threshold
        assert "50.0%" in result.message
        assert result.validation_details["meets_threshold"] is False