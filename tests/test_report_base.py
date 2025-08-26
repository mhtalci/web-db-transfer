"""
Tests for Base Report Generator

Tests the base report generation framework and utilities.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from migration_assistant.checkup.reporters.base import (
    ReportGenerator, ReportUtils, ReportSection, ReportTemplate
)
from migration_assistant.checkup.models import (
    CheckupResults, AnalysisResults, CleanupResults, CheckupConfig,
    QualityIssue, ImportIssue, CodebaseMetrics, IssueSeverity, IssueType,
    FormattingChange, ImportCleanup
)


class TestReportGenerator(ReportGenerator):
    """Test implementation of ReportGenerator."""
    
    @property
    def file_extension(self) -> str:
        return '.test'
    
    async def generate_summary_report(self, results: CheckupResults) -> str:
        return "Test summary report"
    
    async def generate_detailed_report(self, results: CheckupResults) -> str:
        return "Test detailed report"
    
    async def generate_comparison_report(self, before: CheckupResults, after: CheckupResults) -> str:
        return "Test comparison report"


@pytest.fixture
def config():
    """Create test configuration."""
    return CheckupConfig(
        target_directory=Path("/test"),
        report_output_dir=Path("/test/reports")
    )


@pytest.fixture
def sample_analysis_results():
    """Create sample analysis results."""
    quality_issue = QualityIssue(
        file_path=Path("test.py"),
        line_number=10,
        severity=IssueSeverity.HIGH,
        issue_type=IssueType.STYLE_VIOLATION,
        message="Line too long",
        description="Line exceeds maximum length"
    )
    
    import_issue = ImportIssue(
        file_path=Path("main.py"),
        line_number=5,
        severity=IssueSeverity.MEDIUM,
        issue_type=IssueType.UNUSED_IMPORT,
        message="Unused import",
        description="Import is not used",
        import_name="unused_module"
    )
    
    metrics = CodebaseMetrics(
        total_files=100,
        total_lines=5000,
        python_files=80,
        test_files=20,
        syntax_errors=0,
        style_violations=5,
        unused_imports=3,
        test_coverage_percentage=85.5
    )
    
    return AnalysisResults(
        quality_issues=[quality_issue],
        import_issues=[import_issue],
        metrics=metrics,
        timestamp=datetime.now(),
        duration=timedelta(seconds=30)
    )


@pytest.fixture
def sample_cleanup_results():
    """Create sample cleanup results."""
    formatting_change = FormattingChange(
        file_path=Path("test.py"),
        change_type="black",
        lines_changed=5,
        description="Applied black formatting"
    )
    
    import_cleanup = ImportCleanup(
        file_path=Path("main.py"),
        removed_imports=["unused_module"],
        reorganized_imports=True
    )
    
    return CleanupResults(
        formatting_changes=[formatting_change],
        import_cleanups=[import_cleanup],
        timestamp=datetime.now(),
        duration=timedelta(seconds=10),
        backup_created=True,
        backup_path=Path("/test/backup")
    )


@pytest.fixture
def sample_checkup_results(sample_analysis_results, sample_cleanup_results):
    """Create sample checkup results."""
    return CheckupResults(
        analysis=sample_analysis_results,
        cleanup=sample_cleanup_results,
        before_metrics=sample_analysis_results.metrics,
        after_metrics=CodebaseMetrics(
            total_files=100,
            total_lines=5000,
            python_files=80,
            test_files=20,
            syntax_errors=0,
            style_violations=2,  # Improved
            unused_imports=1,    # Improved
            test_coverage_percentage=85.5
        ),
        duration=timedelta(seconds=40),
        success=True
    )


class TestReportUtils:
    """Test ReportUtils functionality."""
    
    def test_format_file_path(self):
        """Test file path formatting."""
        path = Path("/project/src/module.py")
        base_path = Path("/project")
        
        result = ReportUtils.format_file_path(path, base_path)
        assert result == "src/module.py"
        
        # Test without base path
        result = ReportUtils.format_file_path(path)
        assert result == str(path)
    
    def test_format_percentage(self):
        """Test percentage formatting."""
        assert ReportUtils.format_percentage(85.567) == "85.6%"
        assert ReportUtils.format_percentage(85.567, 2) == "85.57%"
        assert ReportUtils.format_percentage(100.0) == "100.0%"
    
    def test_format_number(self):
        """Test number formatting."""
        assert ReportUtils.format_number(1000) == "1,000"
        assert ReportUtils.format_number(1234567) == "1,234,567"
        assert ReportUtils.format_number(100) == "100"
    
    def test_get_severity_color(self):
        """Test severity color mapping."""
        assert ReportUtils.get_severity_color(IssueSeverity.LOW) == "#28a745"
        assert ReportUtils.get_severity_color(IssueSeverity.MEDIUM) == "#ffc107"
        assert ReportUtils.get_severity_color(IssueSeverity.HIGH) == "#fd7e14"
        assert ReportUtils.get_severity_color(IssueSeverity.CRITICAL) == "#dc3545"
    
    def test_get_severity_icon(self):
        """Test severity icon mapping."""
        assert ReportUtils.get_severity_icon(IssueSeverity.LOW) == "ℹ️"
        assert ReportUtils.get_severity_icon(IssueSeverity.MEDIUM) == "⚠️"
        assert ReportUtils.get_severity_icon(IssueSeverity.HIGH) == "🔶"
        assert ReportUtils.get_severity_icon(IssueSeverity.CRITICAL) == "🔴"
    
    def test_truncate_text(self):
        """Test text truncation."""
        long_text = "This is a very long text that should be truncated"
        result = ReportUtils.truncate_text(long_text, 20)
        assert len(result) <= 20
        assert result.endswith("...")
        
        short_text = "Short text"
        result = ReportUtils.truncate_text(short_text, 20)
        assert result == short_text
    
    def test_group_issues_by_file(self, sample_analysis_results):
        """Test grouping issues by file."""
        all_issues = sample_analysis_results.quality_issues + sample_analysis_results.import_issues
        grouped = ReportUtils.group_issues_by_file(all_issues)
        
        assert "test.py" in grouped
        assert "main.py" in grouped
        assert len(grouped["test.py"]) == 1
        assert len(grouped["main.py"]) == 1
    
    def test_group_issues_by_type(self, sample_analysis_results):
        """Test grouping issues by type."""
        all_issues = sample_analysis_results.quality_issues + sample_analysis_results.import_issues
        grouped = ReportUtils.group_issues_by_type(all_issues)
        
        assert IssueType.STYLE_VIOLATION in grouped
        assert IssueType.UNUSED_IMPORT in grouped
        assert len(grouped[IssueType.STYLE_VIOLATION]) == 1
        assert len(grouped[IssueType.UNUSED_IMPORT]) == 1
    
    def test_group_issues_by_severity(self, sample_analysis_results):
        """Test grouping issues by severity."""
        all_issues = sample_analysis_results.quality_issues + sample_analysis_results.import_issues
        grouped = ReportUtils.group_issues_by_severity(all_issues)
        
        assert IssueSeverity.HIGH in grouped
        assert IssueSeverity.MEDIUM in grouped
        assert len(grouped[IssueSeverity.HIGH]) == 1
        assert len(grouped[IssueSeverity.MEDIUM]) == 1
    
    def test_calculate_quality_score(self, sample_analysis_results):
        """Test quality score calculation."""
        score = ReportUtils.calculate_quality_score(sample_analysis_results)
        assert isinstance(score, float)
        assert 0 <= score <= 100
        
        # Test with no files
        empty_results = AnalysisResults(metrics=CodebaseMetrics(total_files=0))
        score = ReportUtils.calculate_quality_score(empty_results)
        assert score == 100.0


class TestReportGeneratorBase:
    """Test ReportGenerator base functionality."""
    
    def test_initialization(self, config, tmp_path):
        """Test report generator initialization."""
        config.report_output_dir = tmp_path / "reports"
        generator = TestReportGenerator(config)
        
        assert generator.config == config
        assert generator.output_dir == config.report_output_dir
        assert generator.output_dir.exists()
        assert isinstance(generator.utils, ReportUtils)
        assert isinstance(generator.template, ReportTemplate)
    
    def test_name_property(self, config):
        """Test name property."""
        generator = TestReportGenerator(config)
        assert generator.name == "TestReportGenerator"
    
    def test_file_extension_property(self, config):
        """Test file extension property."""
        generator = TestReportGenerator(config)
        assert generator.file_extension == ".test"
    
    @pytest.mark.asyncio
    async def test_save_report(self, config, tmp_path):
        """Test report saving."""
        config.report_output_dir = tmp_path / "reports"
        generator = TestReportGenerator(config)
        
        content = "Test report content"
        filename = "test_report"
        
        saved_path = await generator.save_report(content, filename)
        
        assert saved_path.exists()
        assert saved_path.name == "test_report.test"
        assert saved_path.read_text() == content
    
    @pytest.mark.asyncio
    async def test_generate_and_save_summary(self, config, tmp_path, sample_checkup_results):
        """Test summary report generation and saving."""
        config.report_output_dir = tmp_path / "reports"
        generator = TestReportGenerator(config)
        
        saved_path = await generator.generate_and_save_summary(sample_checkup_results)
        
        assert saved_path.exists()
        assert "checkup_summary_" in saved_path.name
        assert saved_path.read_text() == "Test summary report"
    
    @pytest.mark.asyncio
    async def test_generate_and_save_detailed(self, config, tmp_path, sample_checkup_results):
        """Test detailed report generation and saving."""
        config.report_output_dir = tmp_path / "reports"
        generator = TestReportGenerator(config)
        
        saved_path = await generator.generate_and_save_detailed(sample_checkup_results)
        
        assert saved_path.exists()
        assert "checkup_detailed_" in saved_path.name
        assert saved_path.read_text() == "Test detailed report"
    
    @pytest.mark.asyncio
    async def test_generate_and_save_comparison(self, config, tmp_path, sample_checkup_results):
        """Test comparison report generation and saving."""
        config.report_output_dir = tmp_path / "reports"
        generator = TestReportGenerator(config)
        
        saved_path = await generator.generate_and_save_comparison(
            sample_checkup_results, sample_checkup_results
        )
        
        assert saved_path.exists()
        assert "checkup_comparison_" in saved_path.name
        assert saved_path.read_text() == "Test comparison report"
    
    def test_get_report_metadata(self, config, sample_checkup_results):
        """Test report metadata generation."""
        generator = TestReportGenerator(config)
        metadata = generator.get_report_metadata(sample_checkup_results)
        
        assert metadata["generator"] == "TestReportGenerator"
        assert "generated_at" in metadata
        assert "checkup_timestamp" in metadata
        assert metadata["target_directory"] == str(config.target_directory)
        assert metadata["total_issues"] == sample_checkup_results.analysis.total_issues
        assert metadata["cleanup_performed"] is True
        assert metadata["success"] is True
    
    def test_format_duration(self, config):
        """Test duration formatting."""
        generator = TestReportGenerator(config)
        
        # Test hours, minutes, seconds
        duration = timedelta(hours=2, minutes=30, seconds=45)
        assert generator.format_duration(duration) == "2h 30m 45s"
        
        # Test minutes and seconds
        duration = timedelta(minutes=5, seconds=30)
        assert generator.format_duration(duration) == "5m 30s"
        
        # Test seconds only
        duration = timedelta(seconds=45)
        assert generator.format_duration(duration) == "45s"
    
    def test_get_severity_counts(self, config, sample_analysis_results):
        """Test severity counts calculation."""
        generator = TestReportGenerator(config)
        counts = generator.get_severity_counts(sample_analysis_results)
        
        assert counts["high"] == 1
        assert counts["medium"] == 1
        assert counts["low"] == 0
        assert counts["critical"] == 0
    
    def test_get_issue_type_counts(self, config, sample_analysis_results):
        """Test issue type counts calculation."""
        generator = TestReportGenerator(config)
        counts = generator.get_issue_type_counts(sample_analysis_results)
        
        assert counts["quality_issues"] == 1
        assert counts["import_issues"] == 1
        assert counts["duplicates"] == 0
        assert counts["structure_issues"] == 0
    
    def test_create_report_sections(self, config, sample_checkup_results):
        """Test report sections creation."""
        generator = TestReportGenerator(config)
        sections = generator.create_report_sections(sample_checkup_results)
        
        assert len(sections) == 4  # Summary, Analysis, Cleanup, Metrics
        assert sections[0].title == "Executive Summary"
        assert sections[1].title == "Analysis Results"
        assert sections[2].title == "Cleanup Results"
        assert sections[3].title == "Codebase Metrics"
    
    def test_get_all_issues(self, config, sample_analysis_results):
        """Test getting all issues."""
        generator = TestReportGenerator(config)
        all_issues = generator.get_all_issues(sample_analysis_results)
        
        assert len(all_issues) == 2
        assert any(issue.issue_type == IssueType.STYLE_VIOLATION for issue in all_issues)
        assert any(issue.issue_type == IssueType.UNUSED_IMPORT for issue in all_issues)
    
    def test_filter_issues_by_severity(self, config, sample_analysis_results):
        """Test filtering issues by severity."""
        generator = TestReportGenerator(config)
        all_issues = generator.get_all_issues(sample_analysis_results)
        
        high_issues = generator.filter_issues_by_severity(all_issues, IssueSeverity.HIGH)
        assert len(high_issues) == 1
        assert high_issues[0].severity == IssueSeverity.HIGH
        
        critical_issues = generator.filter_issues_by_severity(all_issues, IssueSeverity.CRITICAL)
        assert len(critical_issues) == 0
    
    def test_filter_issues_by_file(self, config, sample_analysis_results):
        """Test filtering issues by file."""
        generator = TestReportGenerator(config)
        all_issues = generator.get_all_issues(sample_analysis_results)
        
        test_py_issues = generator.filter_issues_by_file(all_issues, Path("test.py"))
        assert len(test_py_issues) == 1
        assert test_py_issues[0].file_path == Path("test.py")
        
        nonexistent_issues = generator.filter_issues_by_file(all_issues, Path("nonexistent.py"))
        assert len(nonexistent_issues) == 0


class TestReportSection:
    """Test ReportSection functionality."""
    
    def test_report_section_creation(self):
        """Test ReportSection creation."""
        section = ReportSection(
            title="Test Section",
            content="Test content",
            metadata={"key": "value"}
        )
        
        assert section.title == "Test Section"
        assert section.content == "Test content"
        assert section.metadata["key"] == "value"
        assert len(section.subsections) == 0
    
    def test_report_section_with_subsections(self):
        """Test ReportSection with subsections."""
        subsection = ReportSection(title="Subsection", content="Sub content")
        section = ReportSection(
            title="Main Section",
            content="Main content",
            subsections=[subsection]
        )
        
        assert len(section.subsections) == 1
        assert section.subsections[0].title == "Subsection"


class TestReportTemplate:
    """Test ReportTemplate functionality."""
    
    def test_report_template_creation(self):
        """Test ReportTemplate creation."""
        template = ReportTemplate(
            header_template="<header>",
            section_template="<section>",
            footer_template="</footer>",
            css_styles="body { margin: 0; }",
            javascript="console.log('test');"
        )
        
        assert template.header_template == "<header>"
        assert template.section_template == "<section>"
        assert template.footer_template == "</footer>"
        assert template.css_styles == "body { margin: 0; }"
        assert template.javascript == "console.log('test');"
    
    def test_default_report_template(self):
        """Test default ReportTemplate."""
        template = ReportTemplate()
        
        assert template.header_template == ""
        assert template.section_template == ""
        assert template.footer_template == ""
        assert template.css_styles == ""
        assert template.javascript == ""