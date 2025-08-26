"""
Tests for HTML Report Generator

Tests the HTML report generation with interactive features.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from migration_assistant.checkup.reporters.html import HTMLReportGenerator
from migration_assistant.checkup.models import (
    CheckupResults, AnalysisResults, CleanupResults, CheckupConfig,
    QualityIssue, ImportIssue, CodebaseMetrics, IssueSeverity, IssueType,
    FormattingChange, ImportCleanup
)


@pytest.fixture
def config(tmp_path):
    """Create test configuration."""
    return CheckupConfig(
        target_directory=Path("/test"),
        report_output_dir=tmp_path / "reports"
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
        description="Line exceeds maximum length",
        suggestion="Break line into multiple lines"
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


class TestHTMLReportGenerator:
    """Test HTML report generator functionality."""
    
    def test_initialization(self, config):
        """Test HTML report generator initialization."""
        generator = HTMLReportGenerator(config)
        
        assert generator.config == config
        assert generator.file_extension == '.html'
        assert generator.name == "HTMLReportGenerator"
        assert generator.output_dir.exists()
    
    def test_template_initialization(self, config):
        """Test HTML template initialization."""
        generator = HTMLReportGenerator(config)
        
        assert generator.template.css_styles != ""
        assert generator.template.javascript != ""
        assert "body" in generator.template.css_styles
        assert "Chart" in generator.template.javascript or "chart" in generator.template.javascript.lower()
    
    @pytest.mark.asyncio
    async def test_generate_summary_report(self, config, sample_checkup_results):
        """Test HTML summary report generation."""
        generator = HTMLReportGenerator(config)
        
        html_content = await generator.generate_summary_report(sample_checkup_results)
        
        # Check HTML structure
        assert html_content.startswith('<!DOCTYPE html>')
        assert '<html lang="en">' in html_content
        assert '</html>' in html_content
        
        # Check title
        assert 'Codebase Checkup Summary' in html_content
        
        # Check CSS inclusion
        assert '<style>' in html_content
        assert 'font-family' in html_content
        
        # Check content sections
        assert 'Overview' in html_content
        assert 'Quality Score' in html_content
        assert 'Total Issues' in html_content
        assert 'Files Analyzed' in html_content
        
        # Check metrics
        assert str(sample_checkup_results.analysis.total_issues) in html_content
        assert str(sample_checkup_results.analysis.metrics.total_files) in html_content
    
    @pytest.mark.asyncio
    async def test_generate_detailed_report(self, config, sample_checkup_results):
        """Test HTML detailed report generation."""
        generator = HTMLReportGenerator(config)
        
        html_content = await generator.generate_detailed_report(sample_checkup_results)
        
        # Check HTML structure
        assert html_content.startswith('<!DOCTYPE html>')
        assert 'Detailed Codebase Checkup Report' in html_content
        
        # Check detailed sections
        assert 'Detailed Analysis' in html_content
        assert 'Issues by File' in html_content
        assert 'Issues by Type' in html_content
        
        # Check issue details
        assert 'test.py' in html_content
        assert 'main.py' in html_content
        assert 'Line too long' in html_content
        assert 'Unused import' in html_content
        
        # Check interactive features
        assert 'Chart' in html_content or 'chart' in html_content
        assert 'canvas' in html_content
        assert 'severity-chart' in html_content
        assert 'type-chart' in html_content
    
    @pytest.mark.asyncio
    async def test_generate_comparison_report(self, config, sample_checkup_results):
        """Test HTML comparison report generation."""
        generator = HTMLReportGenerator(config)
        
        html_content = await generator.generate_comparison_report(
            sample_checkup_results, sample_checkup_results
        )
        
        # Check HTML structure
        assert html_content.startswith('<!DOCTYPE html>')
        assert 'Checkup Comparison Report' in html_content
        
        # Note: Full comparison implementation will be in task 9.4
        assert 'Comparison' in html_content
    
    def test_create_overview_section(self, config, sample_checkup_results):
        """Test overview section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_overview_section(sample_checkup_results)
        
        assert section.title == "Overview"
        assert "Quality Score" in section.content
        assert "Total Issues" in section.content
        assert "Files Analyzed" in section.content
        assert "Analysis Duration" in section.content
        
        # Check HTML structure
        assert "overview-grid" in section.content
        assert "metric-card" in section.content
        assert "score-bar" in section.content
    
    def test_create_metrics_dashboard(self, config, sample_checkup_results):
        """Test metrics dashboard creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_metrics_dashboard(sample_checkup_results)
        
        assert section.title == "Metrics Dashboard"
        assert "Issues by Severity" in section.content
        assert "Issues by Type" in section.content
        assert "Codebase Statistics" in section.content
        
        # Check chart elements
        assert "severity-chart" in section.content
        assert "type-chart" in section.content
        assert "canvas" in section.content
        
        # Check statistics table
        assert str(sample_checkup_results.analysis.metrics.python_files) in section.content
        assert str(sample_checkup_results.analysis.metrics.test_files) in section.content
    
    def test_create_issues_summary(self, config, sample_analysis_results):
        """Test issues summary creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_issues_summary(sample_analysis_results)
        
        assert section.title == "Issues Summary"
        assert "issues-summary" in section.content
        assert "severity-group" in section.content
        
        # Check severity groups
        assert "High Severity" in section.content
        assert "Medium Severity" in section.content
        
        # Check issue details
        assert "test.py" in section.content
        assert "main.py" in section.content
        assert "Line too long" in section.content
    
    def test_create_cleanup_summary(self, config, sample_cleanup_results):
        """Test cleanup summary creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_cleanup_summary(sample_cleanup_results)
        
        assert section.title == "Cleanup Summary"
        assert "cleanup-summary" in section.content
        assert "Total Changes" in section.content
        assert "Successful" in section.content
        
        # Check change details
        assert "Formatting:" in section.content
        assert "Import cleanup:" in section.content
        assert str(len(sample_cleanup_results.formatting_changes)) in section.content
        assert str(len(sample_cleanup_results.import_cleanups)) in section.content
    
    def test_create_issues_by_file(self, config, sample_analysis_results):
        """Test issues by file section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_issues_by_file(sample_analysis_results)
        
        assert section.title == "Issues by File"
        assert "issues-by-file" in section.content
        assert "file-group" in section.content
        
        # Check file groups
        assert "test.py" in section.content
        assert "main.py" in section.content
        
        # Check issue details
        assert "Line 10" in section.content
        assert "Line 5" in section.content
        assert "high" in section.content.lower()
        assert "medium" in section.content.lower()
    
    def test_create_issues_by_type(self, config, sample_analysis_results):
        """Test issues by type section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_issues_by_type(sample_analysis_results)
        
        assert section.title == "Issues by Type"
        assert "issues-by-type" in section.content
        assert "type-group" in section.content
        
        # Check issue types
        assert "Style Violation" in section.content
        assert "Unused Import" in section.content
    
    def test_create_before_after_comparison(self, config, sample_checkup_results):
        """Test before/after comparison creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_before_after_comparison(sample_checkup_results)
        
        assert section.title == "Before/After Comparison"
        assert "before-after-comparison" in section.content
        assert "comparison-grid" in section.content
        
        # Check improvement metrics
        assert "Issues Fixed" in section.content
        assert "Imports Cleaned" in section.content
        assert "Files Organized" in section.content
    
    def test_css_styles_completeness(self, config):
        """Test CSS styles completeness."""
        generator = HTMLReportGenerator(config)
        css = generator._get_css_styles()
        
        # Check essential CSS classes
        essential_classes = [
            '.container', '.report-header', '.report-section',
            '.overview-grid', '.metric-card', '.dashboard-grid',
            '.issues-summary', '.severity-group', '.file-group',
            '.issue-detail', '.cleanup-summary'
        ]
        
        for css_class in essential_classes:
            assert css_class in css, f"Missing CSS class: {css_class}"
        
        # Check responsive design
        assert '@media' in css
        assert 'max-width: 768px' in css
    
    def test_javascript_functionality(self, config):
        """Test JavaScript functionality."""
        generator = HTMLReportGenerator(config)
        js = generator._get_javascript()
        
        # Check essential JavaScript functions
        assert 'initializeInteractivity' in js
        assert 'addSeverityFiltering' in js
        assert 'addEventListener' in js
        
        # Check chart initialization
        interactive_js = generator._get_interactive_scripts()
        assert 'initializeCharts' in interactive_js
        assert 'Chart' in interactive_js
        assert 'doughnut' in interactive_js
        assert 'bar' in interactive_js
    
    def test_chart_libraries_inclusion(self, config):
        """Test chart libraries inclusion."""
        generator = HTMLReportGenerator(config)
        chart_libs = generator._get_chart_libraries()
        
        assert 'chart.js' in chart_libs
        assert '<script' in chart_libs
        assert 'cdn.jsdelivr.net' in chart_libs
    
    @pytest.mark.asyncio
    async def test_save_html_report(self, config, sample_checkup_results, tmp_path):
        """Test saving HTML report to file."""
        config.report_output_dir = tmp_path / "reports"
        generator = HTMLReportGenerator(config)
        
        # Generate and save summary report
        saved_path = await generator.generate_and_save_summary(sample_checkup_results)
        
        assert saved_path.exists()
        assert saved_path.suffix == '.html'
        
        # Check file content
        content = saved_path.read_text()
        assert content.startswith('<!DOCTYPE html>')
        assert 'Codebase Checkup Summary' in content
        assert 'Quality Score' in content
    
    def test_html_structure_validity(self, config, sample_checkup_results):
        """Test HTML structure validity."""
        generator = HTMLReportGenerator(config)
        
        # Test with minimal data
        minimal_results = CheckupResults(
            analysis=AnalysisResults(
                metrics=CodebaseMetrics(total_files=1),
                timestamp=datetime.now(),
                duration=timedelta(seconds=1)
            ),
            duration=timedelta(seconds=1),
            success=True
        )
        
        sections = generator.create_report_sections(minimal_results)
        html_content = generator._build_html_document(
            title="Test Report",
            sections=sections,
            metadata=generator.get_report_metadata(minimal_results)
        )
        
        # Check basic HTML structure
        assert html_content.startswith('<!DOCTYPE html>')
        assert '<html lang="en">' in html_content
        assert '<head>' in html_content
        assert '<body>' in html_content
        assert '</body>' in html_content
        assert '</html>' in html_content
        
        # Check meta tags
        assert '<meta charset="UTF-8">' in html_content
        assert '<meta name="viewport"' in html_content
        
        # Check title
        assert '<title>Test Report</title>' in html_content
    
    def test_responsive_design_elements(self, config):
        """Test responsive design elements."""
        generator = HTMLReportGenerator(config)
        css = generator._get_css_styles()
        
        # Check grid layouts
        assert 'display: grid' in css
        assert 'grid-template-columns' in css
        assert 'repeat(auto-fit' in css
        
        # Check media queries
        assert '@media (max-width: 768px)' in css
        
        # Check flexible layouts
        assert 'minmax(' in css
        assert 'flex' in css
    
    def test_accessibility_features(self, config):
        """Test accessibility features."""
        generator = HTMLReportGenerator(config)
        css = generator._get_css_styles()
        
        # Check color contrast considerations
        assert '#333' in css  # Dark text
        assert '#666' in css  # Medium gray
        
        # Check focus states and interactive elements
        js = generator._get_javascript()
        assert 'cursor: pointer' in css
        assert 'addEventListener' in js
    
    def test_error_handling_in_sections(self, config):
        """Test error handling in section creation."""
        generator = HTMLReportGenerator(config)
        
        # Test with empty results
        empty_results = CheckupResults(
            analysis=AnalysisResults(
                metrics=CodebaseMetrics(),
                timestamp=datetime.now(),
                duration=timedelta(seconds=0)
            ),
            duration=timedelta(seconds=0),
            success=True
        )
        
        # Should not raise exceptions
        sections = generator.create_report_sections(empty_results)
        assert len(sections) >= 2  # At least summary and metrics
        
        overview = generator._create_overview_section(empty_results)
        assert overview.title == "Overview"
        assert overview.content != ""
    
    def test_large_dataset_handling(self, config):
        """Test handling of large datasets."""
        generator = HTMLReportGenerator(config)
        
        # Create analysis with many issues
        many_issues = []
        for i in range(100):
            issue = QualityIssue(
                file_path=Path(f"file_{i}.py"),
                line_number=i,
                severity=IssueSeverity.LOW,
                issue_type=IssueType.STYLE_VIOLATION,
                message=f"Issue {i}",
                description=f"Description {i}"
            )
            many_issues.append(issue)
        
        large_analysis = AnalysisResults(
            quality_issues=many_issues,
            metrics=CodebaseMetrics(total_files=100),
            timestamp=datetime.now(),
            duration=timedelta(seconds=30)
        )
        
        large_results = CheckupResults(
            analysis=large_analysis,
            duration=timedelta(seconds=30),
            success=True
        )
        
        # Should handle large datasets without issues
        section = generator._create_issues_by_file(large_analysis)
        assert section.title == "Issues by File"
        assert len(section.content) > 0
        
        # Check truncation is applied
        type_section = generator._create_issues_by_type(large_analysis)
        assert "... and" in type_section.content  # Should show truncation message