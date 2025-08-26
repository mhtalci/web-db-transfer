"""
Tests for JSON and Markdown Report Generators

Tests the JSON and Markdown report generation functionality.
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path

from migration_assistant.checkup.reporters.json import JSONReportGenerator
from migration_assistant.checkup.reporters.markdown import MarkdownReportGenerator
from migration_assistant.checkup.models import (
    CheckupResults, AnalysisResults, CleanupResults, CheckupConfig,
    QualityIssue, ImportIssue, CodebaseMetrics, IssueSeverity, IssueType,
    FormattingChange, ImportCleanup, FileMove, AutoFix
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
        file_path=Path("src/main.py"),
        line_number=42,
        severity=IssueSeverity.HIGH,
        issue_type=IssueType.STYLE_VIOLATION,
        message="Line too long (120 > 88 characters)",
        description="Line exceeds maximum length",
        suggestion="Break line into multiple lines",
        rule_name="E501",
        tool_name="flake8"
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
        total_files=150,
        total_lines=8500,
        python_files=120,
        test_files=30,
        documentation_files=5,
        config_files=3,
        syntax_errors=0,
        style_violations=8,
        code_smells=2,
        complexity_issues=1,
        unused_imports=5,
        circular_imports=0,
        orphaned_modules=1,
        test_coverage_percentage=87.3,
        untested_functions=15,
        duplicate_blocks=2,
        duplicate_lines=45,
        misplaced_files=1,
        empty_directories=0
    )
    
    return AnalysisResults(
        quality_issues=[quality_issue],
        import_issues=[import_issue],
        metrics=metrics,
        timestamp=datetime.now(),
        duration=timedelta(seconds=45)
    )


@pytest.fixture
def sample_cleanup_results():
    """Create sample cleanup results."""
    formatting_change = FormattingChange(
        file_path=Path("src/main.py"),
        change_type="black",
        lines_changed=12,
        description="Applied black formatting"
    )
    
    import_cleanup = ImportCleanup(
        file_path=Path("src/utils.py"),
        removed_imports=["os"],
        reorganized_imports=True
    )
    
    file_move = FileMove(
        source_path=Path("old/location.py"),
        destination_path=Path("new/location.py"),
        reason="Better organization",
        success=True
    )
    
    auto_fix = AutoFix(
        file_path=Path("src/helper.py"),
        issue_type=IssueType.STYLE_VIOLATION,
        fix_description="Fixed indentation",
        success=True
    )
    
    return CleanupResults(
        formatting_changes=[formatting_change],
        import_cleanups=[import_cleanup],
        file_moves=[file_move],
        auto_fixes=[auto_fix],
        timestamp=datetime.now(),
        duration=timedelta(seconds=15),
        backup_created=True,
        backup_path=Path("/tmp/backup")
    )


@pytest.fixture
def sample_checkup_results(sample_analysis_results, sample_cleanup_results):
    """Create sample checkup results."""
    after_metrics = CodebaseMetrics(
        total_files=150,
        total_lines=8500,
        python_files=120,
        test_files=30,
        documentation_files=5,
        config_files=3,
        syntax_errors=0,
        style_violations=3,  # Improved
        code_smells=1,       # Improved
        complexity_issues=1,
        unused_imports=2,    # Improved
        circular_imports=0,
        orphaned_modules=1,
        test_coverage_percentage=87.3,
        untested_functions=15,
        duplicate_blocks=2,
        duplicate_lines=45,
        misplaced_files=0,   # Improved
        empty_directories=0
    )
    
    return CheckupResults(
        analysis=sample_analysis_results,
        cleanup=sample_cleanup_results,
        before_metrics=sample_analysis_results.metrics,
        after_metrics=after_metrics,
        duration=timedelta(seconds=60),
        success=True
    )


class TestJSONReportGenerator:
    """Test JSON report generator functionality."""
    
    def test_initialization(self, config):
        """Test JSON report generator initialization."""
        generator = JSONReportGenerator(config)
        
        assert generator.config == config
        assert generator.file_extension == '.json'
        assert generator.name == "JSONReportGenerator"
        assert generator.output_dir.exists()
    
    @pytest.mark.asyncio
    async def test_generate_summary_report(self, config, sample_checkup_results):
        """Test JSON summary report generation."""
        generator = JSONReportGenerator(config)
        
        json_content = await generator.generate_summary_report(sample_checkup_results)
        
        # Parse JSON to verify structure
        data = json.loads(json_content)
        
        # Check top-level structure
        assert data["report_type"] == "summary"
        assert "metadata" in data
        assert "overview" in data
        assert "metrics" in data
        assert "issue_counts" in data
        assert "severity_breakdown" in data
        assert "type_breakdown" in data
        assert "quality_score" in data
        assert "cleanup_summary" in data
        assert "improvements" in data
        
        # Check metadata
        metadata = data["metadata"]
        assert metadata["generator"] == "JSONReportGenerator"
        assert metadata["total_issues"] == sample_checkup_results.analysis.total_issues
        assert metadata["cleanup_performed"] is True
        
        # Check overview
        overview = data["overview"]
        assert overview["success"] is True
        assert overview["total_issues"] == sample_checkup_results.analysis.total_issues
        assert overview["files_analyzed"] == sample_checkup_results.analysis.metrics.total_files
        assert "quality_score" in overview
        
        # Check metrics structure
        metrics = data["metrics"]
        assert "files" in metrics
        assert "quality" in metrics
        assert "imports" in metrics
        assert "testing" in metrics
        
        # Check issue counts
        issue_counts = data["issue_counts"]
        assert issue_counts["total"] == sample_checkup_results.analysis.total_issues
        assert issue_counts["quality_issues"] == len(sample_checkup_results.analysis.quality_issues)
        assert issue_counts["import_issues"] == len(sample_checkup_results.analysis.import_issues)
    
    @pytest.mark.asyncio
    async def test_generate_detailed_report(self, config, sample_checkup_results):
        """Test JSON detailed report generation."""
        generator = JSONReportGenerator(config)
        
        json_content = await generator.generate_detailed_report(sample_checkup_results)
        
        # Parse JSON to verify structure
        data = json.loads(json_content)
        
        # Check top-level structure
        assert data["report_type"] == "detailed"
        assert "metadata" in data
        assert "overview" in data
        assert "analysis" in data
        assert "issues" in data
        assert "cleanup" in data
        assert "before_after" in data
        
        # Check analysis section
        analysis = data["analysis"]
        assert "metrics" in analysis
        assert "duration" in analysis
        assert "timestamp" in analysis
        assert "total_issues" in analysis
        
        # Check issues section
        issues = data["issues"]
        assert "by_severity" in issues
        assert "by_type" in issues
        assert "by_file" in issues
        assert "all_issues" in issues
        
        # Check all_issues structure
        all_issues = issues["all_issues"]
        assert len(all_issues) == sample_checkup_results.analysis.total_issues
        
        # Check individual issue structure
        if all_issues:
            issue = all_issues[0]
            assert "file_path" in issue
            assert "severity" in issue
            assert "issue_type" in issue
            assert "message" in issue
            assert "description" in issue
        
        # Check cleanup section
        cleanup = data["cleanup"]
        assert "summary" in cleanup
        assert "details" in cleanup
        
        cleanup_details = cleanup["details"]
        assert "formatting_changes" in cleanup_details
        assert "import_cleanups" in cleanup_details
        assert "file_moves" in cleanup_details
        assert "auto_fixes" in cleanup_details
    
    def test_serialize_metrics(self, config, sample_analysis_results):
        """Test metrics serialization."""
        generator = JSONReportGenerator(config)
        
        serialized = generator._serialize_metrics(sample_analysis_results.metrics)
        
        # Check structure
        assert "files" in serialized
        assert "quality" in serialized
        assert "imports" in serialized
        assert "testing" in serialized
        assert "duplicates" in serialized
        assert "structure" in serialized
        
        # Check values
        assert serialized["files"]["total"] == sample_analysis_results.metrics.total_files
        assert serialized["files"]["python"] == sample_analysis_results.metrics.python_files
        assert serialized["quality"]["style_violations"] == sample_analysis_results.metrics.style_violations
        assert serialized["testing"]["coverage_percentage"] == sample_analysis_results.metrics.test_coverage_percentage
    
    def test_serialize_issue(self, config):
        """Test issue serialization."""
        generator = JSONReportGenerator(config)
        
        issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=10,
            severity=IssueSeverity.HIGH,
            issue_type=IssueType.STYLE_VIOLATION,
            message="Test message",
            description="Test description",
            suggestion="Test suggestion",
            rule_name="E501",
            tool_name="flake8"
        )
        
        serialized = generator._serialize_issue(issue)
        
        # Check base fields
        assert serialized["file_path"] == "test.py"
        assert serialized["line_number"] == 10
        assert serialized["severity"] == "high"
        assert serialized["issue_type"] == "style_violation"
        assert serialized["message"] == "Test message"
        assert serialized["description"] == "Test description"
        assert serialized["suggestion"] == "Test suggestion"
        
        # Check type-specific fields
        assert serialized["rule_name"] == "E501"
        assert serialized["tool_name"] == "flake8"
    
    def test_json_serializer(self, config):
        """Test custom JSON serializer."""
        generator = JSONReportGenerator(config)
        
        # Test Path serialization
        path_result = generator._json_serializer(Path("/test/path"))
        assert path_result == "/test/path"
        
        # Test datetime serialization
        dt = datetime(2023, 1, 1, 12, 0, 0)
        dt_result = generator._json_serializer(dt)
        assert dt_result == "2023-01-01T12:00:00"
        
        # Test enum serialization
        severity_result = generator._json_serializer(IssueSeverity.HIGH)
        assert severity_result == "high"


class TestMarkdownReportGenerator:
    """Test Markdown report generator functionality."""
    
    def test_initialization(self, config):
        """Test Markdown report generator initialization."""
        generator = MarkdownReportGenerator(config)
        
        assert generator.config == config
        assert generator.file_extension == '.md'
        assert generator.name == "MarkdownReportGenerator"
        assert generator.output_dir.exists()
    
    @pytest.mark.asyncio
    async def test_generate_summary_report(self, config, sample_checkup_results):
        """Test Markdown summary report generation."""
        generator = MarkdownReportGenerator(config)
        
        md_content = await generator.generate_summary_report(sample_checkup_results)
        
        # Check Markdown structure
        assert md_content.startswith("# Codebase Checkup Summary Report")
        assert "## 📊 Overview" in md_content
        assert "## 📈 Codebase Metrics" in md_content
        assert "## 🚨 Issues Summary" in md_content
        assert "## 🧹 Cleanup Summary" in md_content
        assert "## 📈 Improvements" in md_content
        assert "## 📋 Report Metadata" in md_content
        
        # Check content
        assert "Quality Score" in md_content
        assert "Total Issues" in md_content
        assert "Files Analyzed" in md_content
        assert str(sample_checkup_results.analysis.total_issues) in md_content
        assert str(sample_checkup_results.analysis.metrics.total_files) in md_content
        
        # Check tables
        assert "|" in md_content  # Table formatting
        assert "Metric | Value" in md_content
        assert "Severity | Count" in md_content
    
    @pytest.mark.asyncio
    async def test_generate_detailed_report(self, config, sample_checkup_results):
        """Test Markdown detailed report generation."""
        generator = MarkdownReportGenerator(config)
        
        md_content = await generator.generate_detailed_report(sample_checkup_results)
        
        # Check Markdown structure
        assert md_content.startswith("# Detailed Codebase Checkup Report")
        assert "## 📊 Overview" in md_content
        assert "## 🔍 Detailed Analysis" in md_content
        assert "## 🚨 Issues by Severity" in md_content
        assert "## 📁 Issues by File" in md_content
        assert "## 🏷️ Issues by Type" in md_content
        assert "## 🧹 Detailed Cleanup Results" in md_content
        assert "## 🔧 Cleanup Details" in md_content
        assert "## 📊 Before vs After Comparison" in md_content
        assert "## 💡 Recommendations" in md_content
        
        # Check issue details
        assert "src/main.py" in md_content
        assert "Line too long" in md_content
        assert "High Severity" in md_content
        
        # Check cleanup details
        assert "black" in md_content
        assert "Import Cleanup" in md_content
    
    def test_create_overview_section(self, config, sample_checkup_results):
        """Test overview section creation."""
        generator = MarkdownReportGenerator(config)
        quality_score = generator.utils.calculate_quality_score(sample_checkup_results.analysis)
        
        overview = generator._create_overview_section(sample_checkup_results, quality_score)
        
        assert "## 📊 Overview" in overview
        assert "✅ **Status**: Success" in overview
        assert f"**Quality Score**: {quality_score}/100" in overview
        assert f"**Total Issues**: {sample_checkup_results.analysis.total_issues}" in overview
        assert "🧹 **Cleanup Performed**: Yes" in overview
    
    def test_create_metrics_section(self, config, sample_analysis_results):
        """Test metrics section creation."""
        generator = MarkdownReportGenerator(config)
        
        metrics_section = generator._create_metrics_section(sample_analysis_results.metrics)
        
        assert "## 📈 Codebase Metrics" in metrics_section
        assert "| Metric | Value |" in metrics_section
        assert str(sample_analysis_results.metrics.total_files) in metrics_section
        assert str(sample_analysis_results.metrics.python_files) in metrics_section
        assert "87.3%" in metrics_section  # Test coverage
    
    def test_create_issues_summary_section(self, config, sample_analysis_results):
        """Test issues summary section creation."""
        generator = MarkdownReportGenerator(config)
        
        issues_section = generator._create_issues_summary_section(sample_analysis_results)
        
        assert "## 🚨 Issues Summary" in issues_section
        assert "### By Severity" in issues_section
        assert "### By Type" in issues_section
        assert "| Severity | Count | Icon |" in issues_section
        assert "| Issue Type | Count |" in issues_section
        assert "High | 1 |" in issues_section
        assert "Medium | 1 |" in issues_section
    
    def test_create_cleanup_summary_section(self, config, sample_cleanup_results):
        """Test cleanup summary section creation."""
        generator = MarkdownReportGenerator(config)
        
        cleanup_section = generator._create_cleanup_summary_section(sample_cleanup_results)
        
        assert "## 🧹 Cleanup Summary" in cleanup_section
        assert f"**Total Changes**: {sample_cleanup_results.total_changes}" in cleanup_section
        assert f"**Successful**: {sample_cleanup_results.successful_changes}" in cleanup_section
        assert "**Backup Created**: Yes" in cleanup_section
        assert "🎨 **Formatting**: 1 files" in cleanup_section
        assert "📦 **Import Cleanup**: 1 files" in cleanup_section
    
    def test_create_issues_by_severity_section(self, config, sample_analysis_results):
        """Test issues by severity section creation."""
        generator = MarkdownReportGenerator(config)
        
        severity_section = generator._create_issues_by_severity_section(sample_analysis_results)
        
        assert "## 🚨 Issues by Severity" in severity_section
        assert "### 🔶 High Severity (1 issues)" in severity_section
        assert "### ⚠️ Medium Severity (1 issues)" in severity_section
        assert "**src/main.py:42**: Line too long" in severity_section
        assert "*Suggestion: Break line into multiple lines*" in severity_section
    
    def test_create_issues_by_file_section(self, config, sample_analysis_results):
        """Test issues by file section creation."""
        generator = MarkdownReportGenerator(config)
        
        file_section = generator._create_issues_by_file_section(sample_analysis_results)
        
        assert "## 📁 Issues by File" in file_section
        assert "### `src/main.py` (1 issues)" in file_section
        assert "### `src/utils.py` (1 issues)" in file_section
        assert "🔶 **High** (Line 42): Line too long" in file_section
        assert "⚠️ **Medium** (Line 5): 'os' imported but unused" in file_section
    
    def test_create_recommendations_section(self, config, sample_analysis_results):
        """Test recommendations section creation."""
        generator = MarkdownReportGenerator(config)
        
        recommendations = generator._create_recommendations_section(sample_analysis_results)
        
        assert "## 💡 Recommendations" in recommendations
        # Should have recommendations based on the metrics
        assert "🟡" in recommendations  # Should have some warnings
    
    def test_format_change_methods(self, config):
        """Test change formatting methods."""
        generator = MarkdownReportGenerator(config)
        
        # Test numeric change formatting
        assert generator._format_change(10, 5) == "✅ -5"
        assert generator._format_change(5, 10) == "❌ +5"
        assert generator._format_change(5, 5) == "→ 0"
        
        # Test percentage change formatting
        assert generator._format_percentage_change(80.0, 85.0) == "✅ +5.0%"
        assert generator._format_percentage_change(85.0, 80.0) == "❌ -5.0%"
        assert generator._format_percentage_change(80.0, 80.05) == "→ 0.0%"
    
    def test_get_score_emoji(self, config):
        """Test score emoji selection."""
        generator = MarkdownReportGenerator(config)
        
        assert generator._get_score_emoji(95.0) == "🟢"
        assert generator._get_score_emoji(75.0) == "🟡"
        assert generator._get_score_emoji(55.0) == "🟠"
        assert generator._get_score_emoji(35.0) == "🔴"
    
    def test_calculate_success_rate(self, config, sample_cleanup_results):
        """Test success rate calculation."""
        generator = MarkdownReportGenerator(config)
        
        # Test with all successful items
        rate = generator._calculate_success_rate(sample_cleanup_results.file_moves)
        assert rate == 100
        
        # Test with empty list
        rate = generator._calculate_success_rate([])
        assert rate == 100
    
    def test_markdown_formatting(self, config, sample_checkup_results):
        """Test Markdown formatting consistency."""
        generator = MarkdownReportGenerator(config)
        
        # Test that all sections use consistent formatting
        sections = [
            generator._create_overview_section(sample_checkup_results, 85.0),
            generator._create_metrics_section(sample_checkup_results.analysis.metrics),
            generator._create_issues_summary_section(sample_checkup_results.analysis),
            generator._create_cleanup_summary_section(sample_checkup_results.cleanup)
        ]
        
        for section in sections:
            # Check that sections start with ##
            assert section.startswith("##")
            # Check that tables use proper formatting
            if "|" in section:
                lines = section.split('\n')
                table_lines = [line for line in lines if "|" in line]
                if len(table_lines) > 1:
                    # Check header separator
                    assert any("---" in line for line in table_lines)
    
    @pytest.mark.asyncio
    async def test_empty_results_handling(self, config):
        """Test handling of empty results."""
        generator = MarkdownReportGenerator(config)
        
        # Create empty results
        empty_results = CheckupResults(
            analysis=AnalysisResults(
                metrics=CodebaseMetrics(total_files=0),
                timestamp=datetime.now(),
                duration=timedelta(seconds=1)
            ),
            duration=timedelta(seconds=1),
            success=True
        )
        
        # Should not raise exceptions
        summary = await generator.generate_summary_report(empty_results)
        assert "# Codebase Checkup Summary Report" in summary
        assert "🎉 **No issues found!**" in summary
        
        detailed = await generator.generate_detailed_report(empty_results)
        assert "# Detailed Codebase Checkup Report" in detailed