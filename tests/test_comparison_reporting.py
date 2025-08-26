"""
Tests for Comparison Reporting

Tests the comparison and metrics reporting functionality across all report generators.
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path

from migration_assistant.checkup.reporters.html import HTMLReportGenerator
from migration_assistant.checkup.reporters.json import JSONReportGenerator
from migration_assistant.checkup.reporters.markdown import MarkdownReportGenerator
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
def before_results():
    """Create 'before' checkup results."""
    quality_issue = QualityIssue(
        file_path=Path("src/main.py"),
        line_number=42,
        severity=IssueSeverity.HIGH,
        issue_type=IssueType.STYLE_VIOLATION,
        message="Line too long (120 > 88 characters)",
        description="Line exceeds maximum length",
        suggestion="Break line into multiple lines"
    )
    
    import_issue = ImportIssue(
        file_path=Path("src/utils.py"),
        line_number=5,
        severity=IssueSeverity.MEDIUM,
        issue_type=IssueType.UNUSED_IMPORT,
        message="'os' imported but unused",
        description="Import is not used anywhere in the file",
        import_name="os"
    )
    
    metrics = CodebaseMetrics(
        total_files=100,
        total_lines=5000,
        python_files=80,
        test_files=20,
        syntax_errors=0,
        style_violations=10,
        code_smells=5,
        complexity_issues=3,
        unused_imports=8,
        circular_imports=1,
        orphaned_modules=2,
        test_coverage_percentage=75.0,
        untested_functions=25,
        duplicate_blocks=4,
        duplicate_lines=120,
        misplaced_files=3,
        empty_directories=1
    )
    
    analysis = AnalysisResults(
        quality_issues=[quality_issue],
        import_issues=[import_issue],
        metrics=metrics,
        timestamp=datetime(2023, 1, 1, 10, 0, 0),
        duration=timedelta(seconds=30)
    )
    
    return CheckupResults(
        analysis=analysis,
        before_metrics=metrics,
        duration=timedelta(seconds=30),
        success=True
    )


@pytest.fixture
def after_results():
    """Create 'after' checkup results (improved)."""
    quality_issue = QualityIssue(
        file_path=Path("src/helper.py"),  # Different file
        line_number=15,
        severity=IssueSeverity.MEDIUM,   # Lower severity
        issue_type=IssueType.STYLE_VIOLATION,
        message="Missing docstring",
        description="Function missing docstring",
        suggestion="Add docstring"
    )
    
    # Improved metrics
    metrics = CodebaseMetrics(
        total_files=100,
        total_lines=5000,
        python_files=80,
        test_files=20,
        syntax_errors=0,
        style_violations=5,    # Improved
        code_smells=2,         # Improved
        complexity_issues=3,
        unused_imports=3,      # Improved
        circular_imports=0,    # Improved
        orphaned_modules=2,
        test_coverage_percentage=82.0,  # Improved
        untested_functions=18,          # Improved
        duplicate_blocks=2,             # Improved
        duplicate_lines=60,             # Improved
        misplaced_files=1,              # Improved
        empty_directories=0             # Improved
    )
    
    analysis = AnalysisResults(
        quality_issues=[quality_issue],
        import_issues=[],  # Resolved import issues
        metrics=metrics,
        timestamp=datetime(2023, 1, 2, 10, 0, 0),  # Next day
        duration=timedelta(seconds=25)
    )
    
    cleanup = CleanupResults(
        formatting_changes=[
            FormattingChange(
                file_path=Path("src/main.py"),
                change_type="black",
                lines_changed=15,
                description="Applied black formatting"
            )
        ],
        import_cleanups=[
            ImportCleanup(
                file_path=Path("src/utils.py"),
                removed_imports=["os"],
                reorganized_imports=True
            )
        ],
        timestamp=datetime(2023, 1, 2, 10, 0, 0),
        duration=timedelta(seconds=10),
        backup_created=True,
        backup_path=Path("/tmp/backup")
    )
    
    return CheckupResults(
        analysis=analysis,
        cleanup=cleanup,
        before_metrics=metrics,  # This would be the before metrics in a real scenario
        after_metrics=metrics,   # This is the after metrics
        duration=timedelta(seconds=35),
        success=True
    )


class TestHTMLComparisonReporting:
    """Test HTML comparison reporting functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_comparison_report(self, config, before_results, after_results):
        """Test HTML comparison report generation."""
        generator = HTMLReportGenerator(config)
        
        html_content = await generator.generate_comparison_report(before_results, after_results)
        
        # Check HTML structure
        assert html_content.startswith('<!DOCTYPE html>')
        assert 'Codebase Checkup Comparison Report' in html_content
        assert '</html>' in html_content
        
        # Check comparison sections
        assert 'Comparison Overview' in html_content
        assert 'Metrics Comparison' in html_content
        assert 'Issues Comparison' in html_content
        assert 'Quality Trend Analysis' in html_content
        assert 'Improvement Summary' in html_content
        
        # Check specific content
        assert 'Quality Score Comparison' in html_content
        assert 'Time Between Checkups' in html_content
        assert 'Style Violations' in html_content
        assert 'Unused Imports' in html_content
    
    def test_create_comparison_overview(self, config, before_results, after_results):
        """Test comparison overview section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_comparison_overview(before_results, after_results)
        
        assert section.title == "Comparison Overview"
        assert "Quality Score Comparison" in section.content
        assert "score-comparison" in section.content
        assert "Time Between Checkups" in section.content
        
        # Check metadata
        assert "before_score" in section.metadata
        assert "after_score" in section.metadata
        assert "score_change" in section.metadata
    
    def test_create_metrics_comparison(self, config, before_results, after_results):
        """Test metrics comparison section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_metrics_comparison(before_results, after_results)
        
        assert section.title == "Metrics Comparison"
        assert "metrics-comparison" in section.content
        assert "comparison-table" in section.content
        assert "Style Violations" in section.content
        assert "Unused Imports" in section.content
        assert "Test Coverage" in section.content
        
        # Check for chart data
        assert "metricsComparisonData" in section.content
    
    def test_create_issues_comparison(self, config, before_results, after_results):
        """Test issues comparison section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_issues_comparison(before_results, after_results)
        
        assert section.title == "Issues Comparison"
        assert "issues-comparison" in section.content
        assert "severity-comparison" in section.content
        assert "Issues by Severity" in section.content
    
    def test_create_quality_trend_analysis(self, config, before_results, after_results):
        """Test quality trend analysis section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_quality_trend_analysis(before_results, after_results)
        
        assert section.title == "Quality Trend Analysis"
        assert "quality-trend" in section.content
        assert "Quality Trend Analysis" in section.content
        assert "Key Changes" in section.content
        
        # Should detect improvements
        assert "✅" in section.content  # Should have some improvements
    
    def test_create_improvement_summary(self, config, before_results, after_results):
        """Test improvement summary section creation."""
        generator = HTMLReportGenerator(config)
        
        section = generator._create_improvement_summary(before_results, after_results)
        
        assert section.title == "Improvement Summary"
        assert "improvement-summary" in section.content
        assert "improvements-grid" in section.content
        assert "Issues Fixed" in section.content
        assert "Style Improvements" in section.content
        assert "Import Cleanups" in section.content


class TestJSONComparisonReporting:
    """Test JSON comparison reporting functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_comparison_report(self, config, before_results, after_results):
        """Test JSON comparison report generation."""
        generator = JSONReportGenerator(config)
        
        json_content = await generator.generate_comparison_report(before_results, after_results)
        
        # Parse JSON to verify structure
        data = json.loads(json_content)
        
        # Check top-level structure
        assert data["report_type"] == "comparison"
        assert "metadata" in data
        assert "quality_scores" in data
        assert "metrics_comparison" in data
        assert "issues_comparison" in data
        assert "improvements" in data
        assert "trend_analysis" in data
        assert "detailed_changes" in data
        
        # Check metadata
        metadata = data["metadata"]
        assert "before" in metadata
        assert "after" in metadata
        assert "comparison_generated_at" in metadata
        assert "time_between_checkups" in metadata
        
        # Check quality scores
        quality_scores = data["quality_scores"]
        assert "before" in quality_scores
        assert "after" in quality_scores
        assert "change" in quality_scores
        assert isinstance(quality_scores["change"], (int, float))
        
        # Check improvements
        improvements = data["improvements"]
        assert "issues_fixed" in improvements
        assert "style_improvements" in improvements
        assert "import_cleanups" in improvements
        assert "coverage_improvement" in improvements
    
    def test_create_metrics_comparison_data(self, config, before_results, after_results):
        """Test metrics comparison data creation."""
        generator = JSONReportGenerator(config)
        
        comparison_data = generator._create_metrics_comparison_data(before_results, after_results)
        
        # Check structure
        assert "before" in comparison_data
        assert "after" in comparison_data
        assert "changes" in comparison_data
        
        # Check changes structure
        changes = comparison_data["changes"]
        assert "quality" in changes
        assert "imports" in changes
        assert "testing" in changes
        
        # Check specific changes
        assert changes["quality"]["style_violations"] < 0  # Should be negative (improvement)
        assert changes["imports"]["unused"] < 0  # Should be negative (improvement)
    
    def test_create_issues_comparison_data(self, config, before_results, after_results):
        """Test issues comparison data creation."""
        generator = JSONReportGenerator(config)
        
        comparison_data = generator._create_issues_comparison_data(before_results, after_results)
        
        # Check structure
        assert "total_issues" in comparison_data
        assert "by_severity" in comparison_data
        assert "by_type" in comparison_data
        
        # Check total issues
        total_issues = comparison_data["total_issues"]
        assert "before" in total_issues
        assert "after" in total_issues
        assert "change" in total_issues
        
        # Check severity breakdown
        severity_data = comparison_data["by_severity"]
        assert "before" in severity_data
        assert "after" in severity_data
        assert "changes" in severity_data
    
    def test_calculate_improvements(self, config, before_results, after_results):
        """Test improvement calculation."""
        generator = JSONReportGenerator(config)
        
        improvements = generator._calculate_improvements(before_results, after_results)
        
        # Check all improvement metrics are present
        expected_keys = [
            "issues_fixed", "style_improvements", "import_cleanups",
            "coverage_improvement", "code_smell_reduction", "complexity_reduction",
            "duplicate_reduction", "structure_improvements"
        ]
        
        for key in expected_keys:
            assert key in improvements
            assert isinstance(improvements[key], (int, float))
        
        # Check that improvements are positive (indicating actual improvements)
        assert improvements["style_improvements"] > 0  # Style violations decreased
        assert improvements["import_cleanups"] > 0     # Unused imports decreased
        assert improvements["coverage_improvement"] > 0 # Coverage increased
    
    def test_create_trend_analysis(self, config, before_results, after_results):
        """Test trend analysis creation."""
        generator = JSONReportGenerator(config)
        
        trend_analysis = generator._create_trend_analysis(before_results, after_results)
        
        # Check structure
        assert "overall_direction" in trend_analysis
        assert "quality_score_change" in trend_analysis
        assert "specific_trends" in trend_analysis
        assert "improvement_areas" in trend_analysis
        assert "concern_areas" in trend_analysis
        
        # Check overall direction
        assert trend_analysis["overall_direction"] in ["improving", "declining", "stable"]
        
        # Check specific trends
        specific_trends = trend_analysis["specific_trends"]
        assert isinstance(specific_trends, list)
        
        # Should have some improvements based on our test data
        improvement_areas = trend_analysis["improvement_areas"]
        assert len(improvement_areas) > 0
    
    def test_find_new_issues(self, config, before_results, after_results):
        """Test finding new issues."""
        generator = JSONReportGenerator(config)
        
        new_issues = generator._find_new_issues(before_results, after_results)
        
        assert isinstance(new_issues, list)
        # Should find the new issue in helper.py
        assert len(new_issues) > 0
        
        # Check issue structure
        if new_issues:
            issue = new_issues[0]
            assert "file_path" in issue
            assert "severity" in issue
            assert "issue_type" in issue
            assert "message" in issue
    
    def test_find_resolved_issues(self, config, before_results, after_results):
        """Test finding resolved issues."""
        generator = JSONReportGenerator(config)
        
        resolved_issues = generator._find_resolved_issues(before_results, after_results)
        
        assert isinstance(resolved_issues, list)
        # Should find resolved issues (import issue was resolved)
        assert len(resolved_issues) > 0


class TestMarkdownComparisonReporting:
    """Test Markdown comparison reporting functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_comparison_report(self, config, before_results, after_results):
        """Test Markdown comparison report generation."""
        generator = MarkdownReportGenerator(config)
        
        md_content = await generator.generate_comparison_report(before_results, after_results)
        
        # Check Markdown structure
        assert md_content.startswith("# Codebase Checkup Comparison Report")
        assert "## 📊 Comparison Overview" in md_content
        assert "## 🎯 Quality Score Comparison" in md_content
        assert "## 📈 Detailed Metrics Comparison" in md_content
        assert "## 🚨 Issues Comparison" in md_content
        assert "## 📊 Trend Analysis" in md_content
        assert "## 🔍 Detailed Changes" in md_content
        assert "## 💡 Recommendations Based on Comparison" in md_content
        
        # Check content
        assert "Overall Trend" in md_content
        assert "Quality Score Change" in md_content
        assert "Time Between Checkups" in md_content
        
        # Check tables
        assert "|" in md_content  # Table formatting
        assert "Before | After | Change" in md_content
    
    def test_create_comparison_overview_section(self, config, before_results, after_results):
        """Test comparison overview section creation."""
        generator = MarkdownReportGenerator(config)
        time_between = after_results.analysis.timestamp - before_results.analysis.timestamp
        
        overview = generator._create_comparison_overview_section(before_results, after_results, time_between)
        
        assert "## 📊 Comparison Overview" in overview
        assert "Overall Trend" in overview
        assert "Time Between Checkups" in overview
        assert "Quality Score Change" in overview
        assert "Issues Change" in overview
        
        # Should show improvement
        assert "Improving" in overview or "📈" in overview
    
    def test_create_quality_score_comparison_section(self, config, before_results, after_results):
        """Test quality score comparison section creation."""
        generator = MarkdownReportGenerator(config)
        
        score_section = generator._create_quality_score_comparison_section(before_results, after_results)
        
        assert "## 🎯 Quality Score Comparison" in score_section
        assert "| Metric | Before | After | Change |" in score_section
        assert "Quality Score" in score_section
        assert "/100" in score_section
        
        # Should show improvement indicators
        assert "✅" in score_section or "improvement" in score_section.lower()
    
    def test_create_metrics_comparison_section(self, config, before_results, after_results):
        """Test metrics comparison section creation."""
        generator = MarkdownReportGenerator(config)
        
        metrics_section = generator._create_metrics_comparison_section(before_results, after_results)
        
        assert "## 📈 Detailed Metrics Comparison" in metrics_section
        assert "### Code Quality Metrics" in metrics_section
        assert "### Import and Structure Metrics" in metrics_section
        assert "### Testing and Duplication Metrics" in metrics_section
        
        # Check specific metrics
        assert "Style Violations" in metrics_section
        assert "Unused Imports" in metrics_section
        assert "Test Coverage" in metrics_section
        assert "Code Smells" in metrics_section
        
        # Should show improvements
        assert "✅" in metrics_section
    
    def test_create_issues_comparison_section(self, config, before_results, after_results):
        """Test issues comparison section creation."""
        generator = MarkdownReportGenerator(config)
        
        issues_section = generator._create_issues_comparison_section(before_results, after_results)
        
        assert "## 🚨 Issues Comparison" in issues_section
        assert "### Issues by Severity" in issues_section
        assert "### Issues by Type" in issues_section
        
        # Check severity icons
        assert "🔶" in issues_section or "⚠️" in issues_section  # High/Medium severity icons
        
        # Check table structure
        assert "| Severity | Before | After | Change |" in issues_section
        assert "| Issue Type | Before | After | Change |" in issues_section
    
    def test_create_trend_analysis_section(self, config, before_results, after_results):
        """Test trend analysis section creation."""
        generator = MarkdownReportGenerator(config)
        
        trend_section = generator._create_trend_analysis_section(before_results, after_results)
        
        assert "## 📊 Trend Analysis" in trend_section
        assert "Overall Trend" in trend_section
        assert "Quality Score Change" in trend_section
        
        # Should have improvements section
        assert "### ✅ Improvements" in trend_section
        
        # Should list specific improvements
        assert "Style violations reduced" in trend_section or "Unused imports cleaned" in trend_section
    
    def test_create_recommendations_from_comparison(self, config, before_results, after_results):
        """Test recommendations creation from comparison."""
        generator = MarkdownReportGenerator(config)
        
        recommendations = generator._create_recommendations_from_comparison(before_results, after_results)
        
        assert "## 💡 Recommendations Based on Comparison" in recommendations
        
        # Should have positive recommendations since we have improvements
        assert "🎉" in recommendations  # Should have some positive feedback
        
        # Check for specific recommendation types
        assert "Great Work" in recommendations or "Excellent" in recommendations
    
    def test_format_score_change(self, config):
        """Test score change formatting."""
        generator = MarkdownReportGenerator(config)
        
        # Test positive change
        assert generator._format_score_change(5.5) == "✅ +5.5"
        
        # Test negative change
        assert generator._format_score_change(-3.2) == "❌ -3.2"
        
        # Test no change
        assert generator._format_score_change(0.05) == "→ 0.0"
        assert generator._format_score_change(-0.05) == "→ 0.0"


class TestComparisonIntegration:
    """Test integration between different comparison report formats."""
    
    @pytest.mark.asyncio
    async def test_all_formats_consistency(self, config, before_results, after_results, tmp_path):
        """Test that all report formats provide consistent information."""
        config.report_output_dir = tmp_path / "reports"
        
        # Generate all three report types
        html_generator = HTMLReportGenerator(config)
        json_generator = JSONReportGenerator(config)
        md_generator = MarkdownReportGenerator(config)
        
        html_content = await html_generator.generate_comparison_report(before_results, after_results)
        json_content = await json_generator.generate_comparison_report(before_results, after_results)
        md_content = await md_generator.generate_comparison_report(before_results, after_results)
        
        # Parse JSON for comparison
        json_data = json.loads(json_content)
        
        # Check that key metrics are consistent across formats
        quality_change = json_data["quality_scores"]["change"]
        
        # All formats should indicate improvement (positive change)
        assert quality_change > 0
        
        # HTML should show improvement indicators
        assert "positive" in html_content or "✅" in html_content
        
        # Markdown should show improvement indicators
        assert "✅" in md_content or "Improving" in md_content
        
        # All should mention key metrics
        for content in [html_content, json_content, md_content]:
            assert "style" in content.lower()
            assert "import" in content.lower()
            assert "coverage" in content.lower()
    
    @pytest.mark.asyncio
    async def test_save_comparison_reports(self, config, before_results, after_results, tmp_path):
        """Test saving comparison reports to files."""
        config.report_output_dir = tmp_path / "reports"
        
        generators = [
            HTMLReportGenerator(config),
            JSONReportGenerator(config),
            MarkdownReportGenerator(config)
        ]
        
        for generator in generators:
            # Generate and save comparison report
            saved_path = await generator.generate_and_save_comparison(
                before_results, after_results, "test_comparison"
            )
            
            assert saved_path.exists()
            assert saved_path.name.startswith("test_comparison")
            assert saved_path.suffix == generator.file_extension
            
            # Check file content
            content = saved_path.read_text()
            assert len(content) > 0
            assert "comparison" in content.lower()
    
    def test_edge_cases(self, config):
        """Test edge cases in comparison reporting."""
        # Test with identical results (no change)
        identical_metrics = CodebaseMetrics(
            total_files=50,
            total_lines=2500,
            python_files=40,
            test_files=10,
            test_coverage_percentage=80.0
        )
        
        identical_analysis = AnalysisResults(
            metrics=identical_metrics,
            timestamp=datetime.now(),
            duration=timedelta(seconds=15)
        )
        
        identical_results = CheckupResults(
            analysis=identical_analysis,
            before_metrics=identical_metrics,
            duration=timedelta(seconds=15),
            success=True
        )
        
        # Test JSON generator with identical results
        json_generator = JSONReportGenerator(config)
        improvements = json_generator._calculate_improvements(identical_results, identical_results)
        
        # All improvements should be zero
        for key, value in improvements.items():
            assert value == 0
        
        # Test trend analysis with no change
        trend_analysis = json_generator._create_trend_analysis(identical_results, identical_results)
        assert trend_analysis["overall_direction"] == "stable"
        assert trend_analysis["quality_score_change"] == 0