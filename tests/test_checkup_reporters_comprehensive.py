"""
Comprehensive unit tests for checkup reporters.

Tests all reporter classes to ensure 90%+ code coverage.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

from migration_assistant.checkup.reporters.html import HTMLReportGenerator
from migration_assistant.checkup.reporters.json import JSONReportGenerator
from migration_assistant.checkup.reporters.markdown import MarkdownReportGenerator
from migration_assistant.checkup.reporters.base import ReportGenerator
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CleanupResults, CheckupResults,
    QualityIssue, Duplicate, ImportIssue, StructureIssue, CoverageGap,
    ConfigIssue, DocIssue, CodebaseMetrics, IssueType, IssueSeverity,
    FormattingChange, FileMove, FileRemoval
)


class TestReportGenerator:
    """Test cases for ReportGenerator abstract class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            generate_html_report=True,
            generate_json_report=True,
            generate_markdown_report=True,
            output_directory=Path("/tmp/reports")
        )
    
    def test_base_report_generator_initialization(self, config):
        """Test ReportGenerator initialization."""
        # Create a concrete implementation for testing
        class TestReportGenerator(ReportGenerator):
            def generate_summary_report(self, results):
                return "Summary report"
            
            def generate_detailed_report(self, results):
                return "Detailed report"
            
            def generate_comparison_report(self, before, after):
                return "Comparison report"
        
        generator = TestReportGenerator(config)
        assert generator.config == config
        assert generator.output_directory == config.output_directory
    
    def test_create_sample_analysis_results(self):
        """Test creating sample analysis results for testing."""
        metrics = CodebaseMetrics(
            total_files=10,
            total_lines=1000,
            python_files=8,
            test_files=5,
            syntax_errors=2,
            style_violations=15,
            complexity_issues=3,
            duplicate_blocks=4,
            unused_imports=8,
            circular_imports=1,
            orphaned_modules=2,
            test_coverage_percentage=75.0,
            untested_functions=10,
            config_issues=3,
            doc_issues=5
        )
        
        quality_issues = [
            QualityIssue(
                file_path=Path("test.py"),
                line_number=10,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Line too long"
            ),
            QualityIssue(
                file_path=Path("main.py"),
                line_number=25,
                issue_type=IssueType.COMPLEXITY_HIGH,
                severity=IssueSeverity.HIGH,
                description="Function too complex"
            )
        ]
        
        results = AnalysisResults(
            quality_issues=quality_issues,
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=metrics
        )
        
        assert len(results.quality_issues) == 2
        assert results.metrics.total_files == 10
        assert results.total_issues == 2


class TestHTMLReportGenerator:
    """Test cases for HTMLReportGenerator."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            generate_html_report=True,
            output_directory=Path("/tmp/reports")
        )
    
    @pytest.fixture
    def generator(self, config):
        """Create HTMLReportGenerator instance."""
        return HTMLReportGenerator(config)
    
    @pytest.fixture
    def sample_results(self):
        """Create sample analysis results."""
        metrics = CodebaseMetrics(
            total_files=10,
            total_lines=1000,
            python_files=8,
            test_files=5,
            syntax_errors=1,
            style_violations=5,
            complexity_issues=2,
            duplicate_blocks=3,
            unused_imports=4,
            circular_imports=0,
            orphaned_modules=1,
            test_coverage_percentage=80.0,
            untested_functions=8,
            config_issues=2,
            doc_issues=3
        )
        
        quality_issues = [
            QualityIssue(
                file_path=Path("test.py"),
                line_number=10,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Line too long (90 > 88 characters)"
            ),
            QualityIssue(
                file_path=Path("main.py"),
                line_number=25,
                issue_type=IssueType.COMPLEXITY_HIGH,
                severity=IssueSeverity.HIGH,
                description="Cyclomatic complexity too high (15 > 10)"
            )
        ]
        
        duplicates = [
            Duplicate(
                content_hash="abc123",
                locations=[
                    {"file": Path("file1.py"), "start_line": 10, "end_line": 15},
                    {"file": Path("file2.py"), "start_line": 20, "end_line": 25}
                ],
                lines_of_code=6,
                duplicate_type="exact",
                confidence_score=1.0
            )
        ]
        
        return AnalysisResults(
            quality_issues=quality_issues,
            duplicates=duplicates,
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=metrics
        )
    
    def test_initialization(self, generator, config):
        """Test generator initialization."""
        assert generator.config == config
        assert generator.template_dir is not None
    
    def test_generate_summary_report(self, generator, sample_results):
        """Test generating summary HTML report."""
        html_content = generator.generate_summary_report(sample_results)
        
        assert isinstance(html_content, str)
        assert "<html" in html_content
        assert "<!DOCTYPE html>" in html_content
        assert "Summary Report" in html_content or "summary" in html_content.lower()
        assert str(sample_results.metrics.total_files) in html_content
    
    def test_generate_detailed_report(self, generator, sample_results):
        """Test generating detailed HTML report."""
        html_content = generator.generate_detailed_report(sample_results)
        
        assert isinstance(html_content, str)
        assert "<html" in html_content
        assert "<!DOCTYPE html>" in html_content
        assert "Line too long" in html_content
        assert "Cyclomatic complexity" in html_content
    
    def test_generate_comparison_report(self, generator, sample_results):
        """Test generating comparison HTML report."""
        # Create "after" results with improvements
        after_metrics = CodebaseMetrics(
            total_files=10,
            total_lines=1000,
            python_files=8,
            test_files=5,
            syntax_errors=0,  # Improved
            style_violations=2,  # Improved
            complexity_issues=1,  # Improved
            duplicate_blocks=2,  # Improved
            unused_imports=2,  # Improved
            circular_imports=0,
            orphaned_modules=0,  # Improved
            test_coverage_percentage=85.0,  # Improved
            untested_functions=5,  # Improved
            config_issues=1,  # Improved
            doc_issues=1  # Improved
        )
        
        after_results = AnalysisResults(
            quality_issues=[],  # All fixed
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=after_metrics
        )
        
        html_content = generator.generate_comparison_report(sample_results, after_results)
        
        assert isinstance(html_content, str)
        assert "<html" in html_content
        assert "<!DOCTYPE html>" in html_content
        assert "comparison" in html_content.lower() or "before" in html_content.lower()
    
    def test_create_metrics_chart_data(self, generator, sample_results):
        """Test creating chart data for metrics."""
        chart_data = generator._create_metrics_chart_data(sample_results.metrics)
        
        assert isinstance(chart_data, dict)
        assert "labels" in chart_data
        assert "data" in chart_data
        assert len(chart_data["labels"]) == len(chart_data["data"])
    
    def test_create_severity_distribution(self, generator, sample_results):
        """Test creating severity distribution data."""
        distribution = generator._create_severity_distribution(sample_results.quality_issues)
        
        assert isinstance(distribution, dict)
        assert "HIGH" in distribution or "MEDIUM" in distribution or "LOW" in distribution
        assert sum(distribution.values()) == len(sample_results.quality_issues)
    
    def test_create_file_issues_map(self, generator, sample_results):
        """Test creating file issues mapping."""
        file_map = generator._create_file_issues_map(sample_results.quality_issues)
        
        assert isinstance(file_map, dict)
        assert Path("test.py") in file_map or "test.py" in str(file_map)
        assert Path("main.py") in file_map or "main.py" in str(file_map)
    
    def test_format_issue_for_html(self, generator):
        """Test formatting issue for HTML display."""
        issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            description="Line too long"
        )
        
        formatted = generator._format_issue_for_html(issue)
        
        assert isinstance(formatted, dict)
        assert "file_path" in formatted
        assert "line_number" in formatted
        assert "severity" in formatted
        assert "description" in formatted
    
    def test_generate_css_styles(self, generator):
        """Test generating CSS styles."""
        css = generator._generate_css_styles()
        
        assert isinstance(css, str)
        assert "body" in css or ".container" in css
        assert "{" in css and "}" in css  # Valid CSS structure
    
    def test_generate_javascript(self, generator):
        """Test generating JavaScript code."""
        js = generator._generate_javascript()
        
        assert isinstance(js, str)
        assert "function" in js or "chart" in js.lower()
    
    def test_create_html_template(self, generator):
        """Test creating HTML template."""
        template = generator._create_html_template(
            title="Test Report",
            content="<p>Test content</p>",
            include_charts=True
        )
        
        assert isinstance(template, str)
        assert "<!DOCTYPE html>" in template
        assert "<html" in template
        assert "Test Report" in template
        assert "Test content" in template


class TestJSONReportGenerator:
    """Test cases for JSONReportGenerator."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            generate_json_report=True,
            output_directory=Path("/tmp/reports")
        )
    
    @pytest.fixture
    def generator(self, config):
        """Create JSONReportGenerator instance."""
        return JSONReportGenerator(config)
    
    @pytest.fixture
    def sample_results(self):
        """Create sample analysis results."""
        metrics = CodebaseMetrics(
            total_files=5,
            total_lines=500,
            python_files=4,
            test_files=2,
            syntax_errors=0,
            style_violations=3,
            complexity_issues=1,
            duplicate_blocks=2,
            unused_imports=2,
            circular_imports=0,
            orphaned_modules=0,
            test_coverage_percentage=90.0,
            untested_functions=3,
            config_issues=1,
            doc_issues=2
        )
        
        quality_issues = [
            QualityIssue(
                file_path=Path("test.py"),
                line_number=5,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Missing docstring"
            )
        ]
        
        return AnalysisResults(
            quality_issues=quality_issues,
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=metrics
        )
    
    def test_initialization(self, generator, config):
        """Test generator initialization."""
        assert generator.config == config
    
    def test_generate_summary_report(self, generator, sample_results):
        """Test generating summary JSON report."""
        json_content = generator.generate_summary_report(sample_results)
        
        assert isinstance(json_content, str)
        
        # Parse JSON to verify structure
        data = json.loads(json_content)
        assert "summary" in data
        assert "metrics" in data
        assert "timestamp" in data
        assert data["metrics"]["total_files"] == 5
    
    def test_generate_detailed_report(self, generator, sample_results):
        """Test generating detailed JSON report."""
        json_content = generator.generate_detailed_report(sample_results)
        
        assert isinstance(json_content, str)
        
        # Parse JSON to verify structure
        data = json.loads(json_content)
        assert "analysis_results" in data
        assert "quality_issues" in data["analysis_results"]
        assert "metrics" in data["analysis_results"]
        assert len(data["analysis_results"]["quality_issues"]) == 1
    
    def test_generate_comparison_report(self, generator, sample_results):
        """Test generating comparison JSON report."""
        # Create "after" results
        after_metrics = CodebaseMetrics(
            total_files=5,
            total_lines=500,
            python_files=4,
            test_files=2,
            syntax_errors=0,
            style_violations=1,  # Improved
            complexity_issues=0,  # Improved
            duplicate_blocks=1,  # Improved
            unused_imports=0,  # Improved
            circular_imports=0,
            orphaned_modules=0,
            test_coverage_percentage=95.0,  # Improved
            untested_functions=1,  # Improved
            config_issues=0,  # Improved
            doc_issues=1  # Improved
        )
        
        after_results = AnalysisResults(
            quality_issues=[],
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=after_metrics
        )
        
        json_content = generator.generate_comparison_report(sample_results, after_results)
        
        assert isinstance(json_content, str)
        
        # Parse JSON to verify structure
        data = json.loads(json_content)
        assert "comparison" in data
        assert "before" in data["comparison"]
        assert "after" in data["comparison"]
        assert "improvements" in data["comparison"]
    
    def test_serialize_analysis_results(self, generator, sample_results):
        """Test serializing analysis results to dict."""
        serialized = generator._serialize_analysis_results(sample_results)
        
        assert isinstance(serialized, dict)
        assert "quality_issues" in serialized
        assert "metrics" in serialized
        assert "timestamp" in serialized
        assert len(serialized["quality_issues"]) == 1
    
    def test_serialize_issue(self, generator):
        """Test serializing individual issue."""
        issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            description="Test issue"
        )
        
        serialized = generator._serialize_issue(issue)
        
        assert isinstance(serialized, dict)
        assert serialized["file_path"] == "test.py"
        assert serialized["line_number"] == 10
        assert serialized["issue_type"] == "STYLE_VIOLATION"
        assert serialized["severity"] == "LOW"
        assert serialized["description"] == "Test issue"
    
    def test_serialize_metrics(self, generator, sample_results):
        """Test serializing metrics."""
        serialized = generator._serialize_metrics(sample_results.metrics)
        
        assert isinstance(serialized, dict)
        assert serialized["total_files"] == 5
        assert serialized["python_files"] == 4
        assert serialized["test_coverage_percentage"] == 90.0
    
    def test_calculate_improvements(self, generator, sample_results):
        """Test calculating improvements between results."""
        # Create improved results
        after_metrics = CodebaseMetrics(
            total_files=5,
            total_lines=500,
            python_files=4,
            test_files=2,
            syntax_errors=0,
            style_violations=1,  # Improved from 3
            complexity_issues=0,  # Improved from 1
            duplicate_blocks=1,  # Improved from 2
            unused_imports=0,  # Improved from 2
            circular_imports=0,
            orphaned_modules=0,
            test_coverage_percentage=95.0,  # Improved from 90.0
            untested_functions=1,  # Improved from 3
            config_issues=0,  # Improved from 1
            doc_issues=1  # Improved from 2
        )
        
        after_results = AnalysisResults(
            quality_issues=[],
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=after_metrics
        )
        
        improvements = generator._calculate_improvements(sample_results, after_results)
        
        assert isinstance(improvements, dict)
        assert improvements["style_violations_fixed"] == 2  # 3 - 1
        assert improvements["complexity_issues_fixed"] == 1  # 1 - 0
        assert improvements["coverage_improvement"] == 5.0  # 95.0 - 90.0


class TestMarkdownReportGenerator:
    """Test cases for MarkdownReportGenerator."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("/tmp/test"),
            generate_markdown_report=True,
            output_directory=Path("/tmp/reports")
        )
    
    @pytest.fixture
    def generator(self, config):
        """Create MarkdownReportGenerator instance."""
        return MarkdownReportGenerator(config)
    
    @pytest.fixture
    def sample_results(self):
        """Create sample analysis results."""
        metrics = CodebaseMetrics(
            total_files=8,
            total_lines=800,
            python_files=6,
            test_files=3,
            syntax_errors=1,
            style_violations=4,
            complexity_issues=2,
            duplicate_blocks=1,
            unused_imports=3,
            circular_imports=0,
            orphaned_modules=1,
            test_coverage_percentage=75.0,
            untested_functions=5,
            config_issues=2,
            doc_issues=3
        )
        
        quality_issues = [
            QualityIssue(
                file_path=Path("main.py"),
                line_number=15,
                issue_type=IssueType.COMPLEXITY_HIGH,
                severity=IssueSeverity.HIGH,
                description="Function has high cyclomatic complexity"
            ),
            QualityIssue(
                file_path=Path("utils.py"),
                line_number=8,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Missing blank line"
            )
        ]
        
        import_issues = [
            ImportIssue(
                file_path=Path("test.py"),
                line_number=2,
                issue_type=IssueType.UNUSED_IMPORT,
                severity=IssueSeverity.LOW,
                module_name="unused_module",
                description="Unused import: unused_module"
            )
        ]
        
        return AnalysisResults(
            quality_issues=quality_issues,
            duplicates=[],
            import_issues=import_issues,
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=metrics
        )
    
    def test_initialization(self, generator, config):
        """Test generator initialization."""
        assert generator.config == config
    
    def test_generate_summary_report(self, generator, sample_results):
        """Test generating summary Markdown report."""
        markdown_content = generator.generate_summary_report(sample_results)
        
        assert isinstance(markdown_content, str)
        assert "# Codebase Checkup Summary" in markdown_content
        assert "## Metrics Overview" in markdown_content
        assert "Total Files: 8" in markdown_content
        assert "Test Coverage: 75.0%" in markdown_content
    
    def test_generate_detailed_report(self, generator, sample_results):
        """Test generating detailed Markdown report."""
        markdown_content = generator.generate_detailed_report(sample_results)
        
        assert isinstance(markdown_content, str)
        assert "# Detailed Codebase Analysis Report" in markdown_content
        assert "## Quality Issues" in markdown_content
        assert "## Import Issues" in markdown_content
        assert "Function has high cyclomatic complexity" in markdown_content
        assert "Unused import: unused_module" in markdown_content
    
    def test_generate_comparison_report(self, generator, sample_results):
        """Test generating comparison Markdown report."""
        # Create "after" results with improvements
        after_metrics = CodebaseMetrics(
            total_files=8,
            total_lines=800,
            python_files=6,
            test_files=3,
            syntax_errors=0,  # Improved
            style_violations=2,  # Improved
            complexity_issues=1,  # Improved
            duplicate_blocks=0,  # Improved
            unused_imports=1,  # Improved
            circular_imports=0,
            orphaned_modules=0,  # Improved
            test_coverage_percentage=85.0,  # Improved
            untested_functions=3,  # Improved
            config_issues=1,  # Improved
            doc_issues=1  # Improved
        )
        
        after_results = AnalysisResults(
            quality_issues=[],
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=after_metrics
        )
        
        markdown_content = generator.generate_comparison_report(sample_results, after_results)
        
        assert isinstance(markdown_content, str)
        assert "# Before vs After Comparison" in markdown_content
        assert "## Improvements Summary" in markdown_content
        assert "✅" in markdown_content  # Should show improvements
    
    def test_create_metrics_table(self, generator, sample_results):
        """Test creating metrics table."""
        table = generator._create_metrics_table(sample_results.metrics)
        
        assert isinstance(table, str)
        assert "|" in table  # Markdown table format
        assert "Total Files" in table
        assert "8" in table  # The value
        assert "Test Coverage" in table
        assert "75.0%" in table
    
    def test_create_issues_section(self, generator, sample_results):
        """Test creating issues section."""
        section = generator._create_issues_section(
            "Quality Issues",
            sample_results.quality_issues
        )
        
        assert isinstance(section, str)
        assert "## Quality Issues" in section
        assert "main.py:15" in section
        assert "HIGH" in section
        assert "Function has high cyclomatic complexity" in section
    
    def test_format_issue_for_markdown(self, generator):
        """Test formatting issue for Markdown."""
        issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.MEDIUM,
            description="Line too long"
        )
        
        formatted = generator._format_issue_for_markdown(issue)
        
        assert isinstance(formatted, str)
        assert "test.py:10" in formatted
        assert "MEDIUM" in formatted
        assert "Line too long" in formatted
        assert "**" in formatted  # Bold formatting
    
    def test_create_severity_badge(self, generator):
        """Test creating severity badges."""
        high_badge = generator._create_severity_badge(IssueSeverity.HIGH)
        medium_badge = generator._create_severity_badge(IssueSeverity.MEDIUM)
        low_badge = generator._create_severity_badge(IssueSeverity.LOW)
        
        assert "🔴" in high_badge or "HIGH" in high_badge
        assert "🟡" in medium_badge or "MEDIUM" in medium_badge
        assert "🟢" in low_badge or "LOW" in low_badge
    
    def test_create_improvement_indicators(self, generator):
        """Test creating improvement indicators."""
        # Test improvement
        improved = generator._create_improvement_indicator(10, 5)
        assert "✅" in improved or "↓" in improved
        
        # Test regression
        regressed = generator._create_improvement_indicator(5, 10)
        assert "❌" in regressed or "↑" in regressed
        
        # Test no change
        no_change = generator._create_improvement_indicator(5, 5)
        assert "➖" in no_change or "=" in no_change
    
    def test_create_progress_bar(self, generator):
        """Test creating progress bars."""
        progress_bar = generator._create_progress_bar(75.0, 100.0)
        
        assert isinstance(progress_bar, str)
        assert "75%" in progress_bar
        # Should contain some visual representation
        assert "█" in progress_bar or "▓" in progress_bar or "[" in progress_bar
    
    def test_generate_table_of_contents(self, generator):
        """Test generating table of contents."""
        sections = [
            "Metrics Overview",
            "Quality Issues",
            "Import Issues",
            "Recommendations"
        ]
        
        toc = generator._generate_table_of_contents(sections)
        
        assert isinstance(toc, str)
        assert "## Table of Contents" in toc
        assert "- [Metrics Overview]" in toc
        assert "- [Quality Issues]" in toc
    
    def test_create_recommendations_section(self, generator, sample_results):
        """Test creating recommendations section."""
        recommendations = generator._create_recommendations_section(sample_results)
        
        assert isinstance(recommendations, str)
        assert "## Recommendations" in recommendations
        # Should contain actionable recommendations based on issues found
        assert len(recommendations) > 50  # Should be substantial content