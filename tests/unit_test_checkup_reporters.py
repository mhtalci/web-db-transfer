"""
Comprehensive unit tests for checkup reporters.
Tests all reporter classes to ensure 90%+ code coverage.
"""

import pytest
import tempfile
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migration_assistant.checkup.reporters.html import HTMLReportGenerator
from migration_assistant.checkup.reporters.json import JSONReportGenerator
from migration_assistant.checkup.reporters.markdown import MarkdownReportGenerator
from migration_assistant.checkup.reporters.base import BaseReportGenerator, ReportData
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CleanupResults, CheckupResults,
    QualityIssue, ImportIssue, StructureIssue, CoverageGap, ConfigIssue, DocIssue,
    IssueType, IssueSeverity, CodebaseMetrics, FormattingChange, FileMove
)


class TestBaseReportGenerator:
    """Test cases for BaseReportGenerator abstract class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            generate_html_report=True,
            generate_json_report=True,
            generate_markdown_report=True
        )
    
    def test_base_report_generator_initialization(self):
        """Test BaseReportGenerator initialization."""
        # Create a concrete implementation for testing
        class TestReportGenerator(BaseReportGenerator):
            def generate_summary_report(self, results):
                return "Summary report"
            
            def generate_detailed_report(self, results):
                return "Detailed report"
            
            def generate_comparison_report(self, before, after):
                return "Comparison report"
        
        generator = TestReportGenerator(self.config)
        assert generator.config == self.config
        assert generator.output_directory == self.config.target_directory
    
    def test_report_data_creation(self):
        """Test ReportData creation."""
        # Create sample analysis results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(
                    file_path=Path("test.py"),
                    issue_type=IssueType.STYLE_VIOLATION,
                    severity=IssueSeverity.LOW,
                    message="Line too long"
                )
            ],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=10,
                total_lines=1000,
                syntax_errors=0,
                style_violations=1
            )
        )
        
        report_data = ReportData(
            analysis_results=analysis_results,
            cleanup_results=None,
            generation_time=datetime.now(),
            report_type="summary"
        )
        
        assert report_data.analysis_results == analysis_results
        assert report_data.cleanup_results is None
        assert report_data.report_type == "summary"
        assert isinstance(report_data.generation_time, datetime)
    
    def test_format_timestamp(self):
        """Test timestamp formatting."""
        class TestReportGenerator(BaseReportGenerator):
            def generate_summary_report(self, results):
                return "Summary"
            def generate_detailed_report(self, results):
                return "Detailed"
            def generate_comparison_report(self, before, after):
                return "Comparison"
        
        generator = TestReportGenerator(self.config)
        
        test_time = datetime(2024, 1, 15, 14, 30, 45)
        formatted = generator._format_timestamp(test_time)
        
        assert "2024" in formatted
        assert "01" in formatted or "Jan" in formatted
        assert "15" in formatted
    
    def test_calculate_severity_distribution(self):
        """Test severity distribution calculation."""
        class TestReportGenerator(BaseReportGenerator):
            def generate_summary_report(self, results):
                return "Summary"
            def generate_detailed_report(self, results):
                return "Detailed"
            def generate_comparison_report(self, before, after):
                return "Comparison"
        
        generator = TestReportGenerator(self.config)
        
        issues = [
            QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Error 1"),
            QualityIssue(Path("test2.py"), IssueType.STYLE_VIOLATION, IssueSeverity.MEDIUM, "Error 2"),
            QualityIssue(Path("test3.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Error 3"),
            QualityIssue(Path("test4.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Error 4"),
        ]
        
        distribution = generator._calculate_severity_distribution(issues)
        
        assert distribution[IssueSeverity.HIGH] == 2
        assert distribution[IssueSeverity.MEDIUM] == 1
        assert distribution[IssueSeverity.LOW] == 1
    
    def test_group_issues_by_type(self):
        """Test issue grouping by type."""
        class TestReportGenerator(BaseReportGenerator):
            def generate_summary_report(self, results):
                return "Summary"
            def generate_detailed_report(self, results):
                return "Detailed"
            def generate_comparison_report(self, before, after):
                return "Comparison"
        
        generator = TestReportGenerator(self.config)
        
        issues = [
            QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Error 1"),
            QualityIssue(Path("test2.py"), IssueType.STYLE_VIOLATION, IssueSeverity.MEDIUM, "Error 2"),
            ImportIssue(Path("test3.py"), IssueType.UNUSED_IMPORT, IssueSeverity.LOW, "unused", "Error 3"),
            QualityIssue(Path("test4.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Error 4"),
        ]
        
        grouped = generator._group_issues_by_type(issues)
        
        assert IssueType.SYNTAX_ERROR in grouped
        assert IssueType.STYLE_VIOLATION in grouped
        assert IssueType.UNUSED_IMPORT in grouped
        assert len(grouped[IssueType.SYNTAX_ERROR]) == 2
        assert len(grouped[IssueType.STYLE_VIOLATION]) == 1
        assert len(grouped[IssueType.UNUSED_IMPORT]) == 1


class TestHTMLReportGenerator:
    """Test cases for HTMLReportGenerator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            generate_html_report=True,
            html_template_path=None
        )
    
    def test_initialization(self):
        """Test generator initialization."""
        generator = HTMLReportGenerator(self.config)
        assert generator.config == self.config
        assert generator.template_path == self.config.html_template_path
    
    def test_generate_summary_report(self):
        """Test HTML summary report generation."""
        # Create sample results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Line too long")
            ],
            import_issues=[
                ImportIssue(Path("test.py"), IssueType.UNUSED_IMPORT, IssueSeverity.LOW, "unused_module", "Unused import")
            ],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=10,
                total_lines=1000,
                syntax_errors=0,
                style_violations=1,
                unused_imports=1
            )
        )
        
        generator = HTMLReportGenerator(self.config)
        html_report = generator.generate_summary_report(analysis_results)
        
        assert isinstance(html_report, str)
        assert "<html>" in html_report
        assert "<head>" in html_report
        assert "<body>" in html_report
        assert "Checkup Summary" in html_report
        assert "test.py" in html_report
        assert "Line too long" in html_report
    
    def test_generate_detailed_report(self):
        """Test HTML detailed report generation."""
        # Create comprehensive results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Syntax error", line_number=10),
                QualityIssue(Path("test2.py"), IssueType.STYLE_VIOLATION, IssueSeverity.MEDIUM, "Style issue", line_number=5)
            ],
            import_issues=[
                ImportIssue(Path("test3.py"), IssueType.CIRCULAR_IMPORT, IssueSeverity.HIGH, "module1", "Circular import")
            ],
            structure_issues=[
                StructureIssue(Path("test4.py"), IssueType.MISPLACED_FILE, IssueSeverity.MEDIUM, "File in wrong location")
            ],
            coverage_gaps=[
                CoverageGap(Path("test5.py"), "uncovered_function", 1, 10, 0.0)
            ],
            config_issues=[
                ConfigIssue(Path("pyproject.toml"), IssueType.MISSING_CONFIG, IssueSeverity.LOW, "Missing field", "project")
            ],
            doc_issues=[
                DocIssue(Path("test6.py"), IssueType.MISSING_DOCSTRING, IssueSeverity.LOW, "Missing docstring", function_name="func")
            ],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=20,
                total_lines=2000,
                syntax_errors=1,
                style_violations=1,
                circular_imports=1,
                misplaced_files=1,
                coverage_percentage=75.0
            )
        )
        
        generator = HTMLReportGenerator(self.config)
        html_report = generator.generate_detailed_report(analysis_results)
        
        assert isinstance(html_report, str)
        assert "<html>" in html_report
        assert "Detailed Analysis Report" in html_report
        assert "Quality Issues" in html_report
        assert "Import Issues" in html_report
        assert "Structure Issues" in html_report
        assert "Coverage Gaps" in html_report
        assert "Configuration Issues" in html_report
        assert "Documentation Issues" in html_report
        
        # Check that all issues are included
        assert "test1.py" in html_report
        assert "test2.py" in html_report
        assert "test3.py" in html_report
        assert "test4.py" in html_report
        assert "test5.py" in html_report
        assert "test6.py" in html_report
    
    def test_generate_comparison_report(self):
        """Test HTML comparison report generation."""
        # Create before results
        before_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Issue 1"),
                QualityIssue(Path("test.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Issue 2")
            ],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now() - timedelta(hours=1),
            metrics=CodebaseMetrics(
                total_files=10,
                total_lines=1000,
                style_violations=2
            )
        )
        
        # Create after results (improved)
        after_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Issue 1")
            ],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=10,
                total_lines=1000,
                style_violations=1
            )
        )
        
        generator = HTMLReportGenerator(self.config)
        html_report = generator.generate_comparison_report(before_results, after_results)
        
        assert isinstance(html_report, str)
        assert "<html>" in html_report
        assert "Before vs After Comparison" in html_report
        assert "Improvements" in html_report
        assert "style_violations" in html_report.lower()
    
    def test_create_issue_table(self):
        """Test HTML issue table creation."""
        generator = HTMLReportGenerator(self.config)
        
        issues = [
            QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Error 1", line_number=10),
            QualityIssue(Path("test2.py"), IssueType.STYLE_VIOLATION, IssueSeverity.MEDIUM, "Error 2", line_number=5)
        ]
        
        table_html = generator._create_issue_table(issues, "Test Issues")
        
        assert "<table" in table_html
        assert "<thead>" in table_html
        assert "<tbody>" in table_html
        assert "Test Issues" in table_html
        assert "test1.py" in table_html
        assert "test2.py" in table_html
        assert "Error 1" in table_html
        assert "Error 2" in table_html
    
    def test_create_metrics_chart(self):
        """Test metrics chart creation."""
        generator = HTMLReportGenerator(self.config)
        
        metrics = CodebaseMetrics(
            total_files=100,
            total_lines=10000,
            syntax_errors=5,
            style_violations=20,
            unused_imports=10,
            circular_imports=2,
            coverage_percentage=85.0
        )
        
        chart_html = generator._create_metrics_chart(metrics)
        
        assert "chart" in chart_html.lower()
        assert "canvas" in chart_html.lower() or "svg" in chart_html.lower()
    
    def test_apply_severity_styling(self):
        """Test severity-based styling."""
        generator = HTMLReportGenerator(self.config)
        
        high_style = generator._apply_severity_styling(IssueSeverity.HIGH)
        medium_style = generator._apply_severity_styling(IssueSeverity.MEDIUM)
        low_style = generator._apply_severity_styling(IssueSeverity.LOW)
        
        assert "color" in high_style or "class" in high_style
        assert high_style != medium_style
        assert medium_style != low_style


class TestJSONReportGenerator:
    """Test cases for JSONReportGenerator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            generate_json_report=True
        )
    
    def test_initialization(self):
        """Test generator initialization."""
        generator = JSONReportGenerator(self.config)
        assert generator.config == self.config
    
    def test_generate_summary_report(self):
        """Test JSON summary report generation."""
        # Create sample results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Line too long")
            ],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=10,
                total_lines=1000,
                style_violations=1
            )
        )
        
        generator = JSONReportGenerator(self.config)
        json_report = generator.generate_summary_report(analysis_results)
        
        assert isinstance(json_report, str)
        
        # Parse JSON to verify structure
        report_data = json.loads(json_report)
        
        assert "summary" in report_data
        assert "metrics" in report_data
        assert "timestamp" in report_data
        assert "total_issues" in report_data["summary"]
        assert report_data["summary"]["total_issues"] == 1
        assert report_data["metrics"]["total_files"] == 10
        assert report_data["metrics"]["style_violations"] == 1
    
    def test_generate_detailed_report(self):
        """Test JSON detailed report generation."""
        # Create comprehensive results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Syntax error", line_number=10)
            ],
            import_issues=[
                ImportIssue(Path("test2.py"), IssueType.UNUSED_IMPORT, IssueSeverity.LOW, "unused_module", "Unused import")
            ],
            structure_issues=[
                StructureIssue(Path("test3.py"), IssueType.MISPLACED_FILE, IssueSeverity.MEDIUM, "Misplaced file")
            ],
            coverage_gaps=[
                CoverageGap(Path("test4.py"), "uncovered_function", 1, 10, 0.0)
            ],
            config_issues=[
                ConfigIssue(Path("config.toml"), IssueType.MISSING_CONFIG, IssueSeverity.LOW, "Missing field", "section")
            ],
            doc_issues=[
                DocIssue(Path("test5.py"), IssueType.MISSING_DOCSTRING, IssueSeverity.LOW, "Missing docstring")
            ],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=20,
                total_lines=2000,
                syntax_errors=1,
                unused_imports=1,
                misplaced_files=1,
                coverage_percentage=75.0
            )
        )
        
        generator = JSONReportGenerator(self.config)
        json_report = generator.generate_detailed_report(analysis_results)
        
        assert isinstance(json_report, str)
        
        # Parse JSON to verify structure
        report_data = json.loads(json_report)
        
        assert "analysis_results" in report_data
        assert "quality_issues" in report_data["analysis_results"]
        assert "import_issues" in report_data["analysis_results"]
        assert "structure_issues" in report_data["analysis_results"]
        assert "coverage_gaps" in report_data["analysis_results"]
        assert "config_issues" in report_data["analysis_results"]
        assert "doc_issues" in report_data["analysis_results"]
        assert "metrics" in report_data["analysis_results"]
        
        # Verify issue counts
        assert len(report_data["analysis_results"]["quality_issues"]) == 1
        assert len(report_data["analysis_results"]["import_issues"]) == 1
        assert len(report_data["analysis_results"]["structure_issues"]) == 1
        assert len(report_data["analysis_results"]["coverage_gaps"]) == 1
        assert len(report_data["analysis_results"]["config_issues"]) == 1
        assert len(report_data["analysis_results"]["doc_issues"]) == 1
    
    def test_generate_comparison_report(self):
        """Test JSON comparison report generation."""
        # Create before and after results
        before_metrics = CodebaseMetrics(total_files=10, style_violations=5, unused_imports=3)
        after_metrics = CodebaseMetrics(total_files=10, style_violations=2, unused_imports=1)
        
        before_results = AnalysisResults(
            quality_issues=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now() - timedelta(hours=1),
            metrics=before_metrics
        )
        
        after_results = AnalysisResults(
            quality_issues=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=after_metrics
        )
        
        generator = JSONReportGenerator(self.config)
        json_report = generator.generate_comparison_report(before_results, after_results)
        
        assert isinstance(json_report, str)
        
        # Parse JSON to verify structure
        report_data = json.loads(json_report)
        
        assert "comparison" in report_data
        assert "before" in report_data["comparison"]
        assert "after" in report_data["comparison"]
        assert "improvements" in report_data["comparison"]
        
        # Check improvements calculation
        improvements = report_data["comparison"]["improvements"]
        assert "style_violations" in improvements
        assert improvements["style_violations"]["before"] == 5
        assert improvements["style_violations"]["after"] == 2
        assert improvements["style_violations"]["change"] == -3
    
    def test_serialize_issue(self):
        """Test issue serialization."""
        generator = JSONReportGenerator(self.config)
        
        issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Syntax error",
            description="Invalid syntax found",
            line_number=10,
            column_number=5
        )
        
        serialized = generator._serialize_issue(issue)
        
        assert isinstance(serialized, dict)
        assert serialized["file_path"] == "test.py"
        assert serialized["issue_type"] == "SYNTAX_ERROR"
        assert serialized["severity"] == "HIGH"
        assert serialized["message"] == "Syntax error"
        assert serialized["description"] == "Invalid syntax found"
        assert serialized["line_number"] == 10
        assert serialized["column_number"] == 5
    
    def test_serialize_metrics(self):
        """Test metrics serialization."""
        generator = JSONReportGenerator(self.config)
        
        metrics = CodebaseMetrics(
            total_files=100,
            total_lines=10000,
            syntax_errors=5,
            style_violations=20,
            unused_imports=10,
            coverage_percentage=85.5
        )
        
        serialized = generator._serialize_metrics(metrics)
        
        assert isinstance(serialized, dict)
        assert serialized["total_files"] == 100
        assert serialized["total_lines"] == 10000
        assert serialized["syntax_errors"] == 5
        assert serialized["style_violations"] == 20
        assert serialized["unused_imports"] == 10
        assert serialized["coverage_percentage"] == 85.5


class TestMarkdownReportGenerator:
    """Test cases for MarkdownReportGenerator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = CheckupConfig(
            target_directory=self.temp_dir,
            generate_markdown_report=True
        )
    
    def test_initialization(self):
        """Test generator initialization."""
        generator = MarkdownReportGenerator(self.config)
        assert generator.config == self.config
    
    def test_generate_summary_report(self):
        """Test Markdown summary report generation."""
        # Create sample results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test.py"), IssueType.STYLE_VIOLATION, IssueSeverity.LOW, "Line too long")
            ],
            import_issues=[
                ImportIssue(Path("test.py"), IssueType.UNUSED_IMPORT, IssueSeverity.LOW, "unused_module", "Unused import")
            ],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=10,
                total_lines=1000,
                style_violations=1,
                unused_imports=1
            )
        )
        
        generator = MarkdownReportGenerator(self.config)
        md_report = generator.generate_summary_report(analysis_results)
        
        assert isinstance(md_report, str)
        assert "# Codebase Checkup Summary" in md_report
        assert "## Overview" in md_report
        assert "## Issues Summary" in md_report
        assert "Total Issues: 2" in md_report
        assert "- Style Violations: 1" in md_report
        assert "- Unused Imports: 1" in md_report
    
    def test_generate_detailed_report(self):
        """Test Markdown detailed report generation."""
        # Create comprehensive results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Syntax error", line_number=10)
            ],
            import_issues=[
                ImportIssue(Path("test2.py"), IssueType.CIRCULAR_IMPORT, IssueSeverity.HIGH, "module1", "Circular import")
            ],
            structure_issues=[
                StructureIssue(Path("test3.py"), IssueType.MISPLACED_FILE, IssueSeverity.MEDIUM, "Misplaced file")
            ],
            coverage_gaps=[
                CoverageGap(Path("test4.py"), "uncovered_function", 1, 10, 0.0)
            ],
            config_issues=[
                ConfigIssue(Path("config.toml"), IssueType.MISSING_CONFIG, IssueSeverity.LOW, "Missing field", "section")
            ],
            doc_issues=[
                DocIssue(Path("test5.py"), IssueType.MISSING_DOCSTRING, IssueSeverity.LOW, "Missing docstring")
            ],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(
                total_files=20,
                total_lines=2000,
                syntax_errors=1,
                circular_imports=1,
                misplaced_files=1,
                coverage_percentage=75.0
            )
        )
        
        generator = MarkdownReportGenerator(self.config)
        md_report = generator.generate_detailed_report(analysis_results)
        
        assert isinstance(md_report, str)
        assert "# Detailed Codebase Analysis Report" in md_report
        assert "## Quality Issues" in md_report
        assert "## Import Issues" in md_report
        assert "## Structure Issues" in md_report
        assert "## Coverage Gaps" in md_report
        assert "## Configuration Issues" in md_report
        assert "## Documentation Issues" in md_report
        
        # Check that all issues are included
        assert "test1.py" in md_report
        assert "test2.py" in md_report
        assert "test3.py" in md_report
        assert "test4.py" in md_report
        assert "test5.py" in md_report
        assert "Syntax error" in md_report
        assert "Circular import" in md_report
    
    def test_generate_comparison_report(self):
        """Test Markdown comparison report generation."""
        # Create before and after results
        before_metrics = CodebaseMetrics(total_files=10, style_violations=5, unused_imports=3)
        after_metrics = CodebaseMetrics(total_files=10, style_violations=2, unused_imports=1)
        
        before_results = AnalysisResults(
            quality_issues=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now() - timedelta(hours=1),
            metrics=before_metrics
        )
        
        after_results = AnalysisResults(
            quality_issues=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=after_metrics
        )
        
        generator = MarkdownReportGenerator(self.config)
        md_report = generator.generate_comparison_report(before_results, after_results)
        
        assert isinstance(md_report, str)
        assert "# Before vs After Comparison" in md_report
        assert "## Improvements" in md_report
        assert "Style Violations: 5 → 2" in md_report
        assert "Unused Imports: 3 → 1" in md_report
    
    def test_create_issue_table(self):
        """Test Markdown issue table creation."""
        generator = MarkdownReportGenerator(self.config)
        
        issues = [
            QualityIssue(Path("test1.py"), IssueType.SYNTAX_ERROR, IssueSeverity.HIGH, "Error 1", line_number=10),
            QualityIssue(Path("test2.py"), IssueType.STYLE_VIOLATION, IssueSeverity.MEDIUM, "Error 2", line_number=5)
        ]
        
        table_md = generator._create_issue_table(issues)
        
        assert "| File | Line | Severity | Type | Message |" in table_md
        assert "|------|------|----------|------|---------|" in table_md
        assert "| test1.py | 10 | HIGH | SYNTAX_ERROR | Error 1 |" in table_md
        assert "| test2.py | 5 | MEDIUM | STYLE_VIOLATION | Error 2 |" in table_md
    
    def test_create_metrics_section(self):
        """Test metrics section creation."""
        generator = MarkdownReportGenerator(self.config)
        
        metrics = CodebaseMetrics(
            total_files=100,
            total_lines=10000,
            syntax_errors=5,
            style_violations=20,
            unused_imports=10,
            coverage_percentage=85.0
        )
        
        metrics_md = generator._create_metrics_section(metrics)
        
        assert "## Codebase Metrics" in metrics_md
        assert "- Total Files: 100" in metrics_md
        assert "- Total Lines: 10,000" in metrics_md
        assert "- Syntax Errors: 5" in metrics_md
        assert "- Style Violations: 20" in metrics_md
        assert "- Unused Imports: 10" in metrics_md
        assert "- Coverage: 85.0%" in metrics_md
    
    def test_format_severity_badge(self):
        """Test severity badge formatting."""
        generator = MarkdownReportGenerator(self.config)
        
        high_badge = generator._format_severity_badge(IssueSeverity.HIGH)
        medium_badge = generator._format_severity_badge(IssueSeverity.MEDIUM)
        low_badge = generator._format_severity_badge(IssueSeverity.LOW)
        
        assert "HIGH" in high_badge
        assert "MEDIUM" in medium_badge
        assert "LOW" in low_badge
        
        # Should include color or styling
        assert "red" in high_badge.lower() or "🔴" in high_badge
        assert "yellow" in medium_badge.lower() or "🟡" in medium_badge
        assert "green" in low_badge.lower() or "🟢" in low_badge


if __name__ == "__main__":
    # Run tests manually without pytest
    def run_sync_tests():
        """Run synchronous tests."""
        print("Running BaseReportGenerator tests...")
        
        # Test BaseReportGenerator
        test_base = TestBaseReportGenerator()
        test_base.setup_method()
        
        try:
            test_base.test_base_report_generator_initialization()
            print("✓ test_base_report_generator_initialization passed")
        except Exception as e:
            print(f"✗ test_base_report_generator_initialization failed: {e}")
        
        try:
            test_base.test_report_data_creation()
            print("✓ test_report_data_creation passed")
        except Exception as e:
            print(f"✗ test_report_data_creation failed: {e}")
        
        try:
            test_base.test_calculate_severity_distribution()
            print("✓ test_calculate_severity_distribution passed")
        except Exception as e:
            print(f"✗ test_calculate_severity_distribution failed: {e}")
        
        # Test HTMLReportGenerator
        print("\nRunning HTMLReportGenerator tests...")
        test_html = TestHTMLReportGenerator()
        test_html.setup_method()
        
        try:
            test_html.test_generate_summary_report()
            print("✓ test_generate_summary_report passed")
        except Exception as e:
            print(f"✗ test_generate_summary_report failed: {e}")
        
        try:
            test_html.test_generate_detailed_report()
            print("✓ test_generate_detailed_report passed")
        except Exception as e:
            print(f"✗ test_generate_detailed_report failed: {e}")
        
        try:
            test_html.test_create_issue_table()
            print("✓ test_create_issue_table passed")
        except Exception as e:
            print(f"✗ test_create_issue_table failed: {e}")
        
        # Test JSONReportGenerator
        print("\nRunning JSONReportGenerator tests...")
        test_json = TestJSONReportGenerator()
        test_json.setup_method()
        
        try:
            test_json.test_generate_summary_report()
            print("✓ test_json_generate_summary_report passed")
        except Exception as e:
            print(f"✗ test_json_generate_summary_report failed: {e}")
        
        try:
            test_json.test_serialize_issue()
            print("✓ test_serialize_issue passed")
        except Exception as e:
            print(f"✗ test_serialize_issue failed: {e}")
        
        try:
            test_json.test_serialize_metrics()
            print("✓ test_serialize_metrics passed")
        except Exception as e:
            print(f"✗ test_serialize_metrics failed: {e}")
        
        # Test MarkdownReportGenerator
        print("\nRunning MarkdownReportGenerator tests...")
        test_md = TestMarkdownReportGenerator()
        test_md.setup_method()
        
        try:
            test_md.test_generate_summary_report()
            print("✓ test_md_generate_summary_report passed")
        except Exception as e:
            print(f"✗ test_md_generate_summary_report failed: {e}")
        
        try:
            test_md.test_create_issue_table()
            print("✓ test_md_create_issue_table passed")
        except Exception as e:
            print(f"✗ test_md_create_issue_table failed: {e}")
        
        try:
            test_md.test_create_metrics_section()
            print("✓ test_create_metrics_section passed")
        except Exception as e:
            print(f"✗ test_create_metrics_section failed: {e}")
    
    # Run tests
    run_sync_tests()
    print("\nTest run completed!")