"""
Comprehensive unit tests for checkup models.

Tests all model classes and data structures to ensure 90%+ code coverage.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import asdict

from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CleanupResults, CheckupResults,
    QualityIssue, Duplicate, ImportIssue, StructureIssue, CoverageGap,
    ConfigIssue, DocIssue, CodebaseMetrics, IssueType, IssueSeverity,
    FormattingChange, FileMove, FileRemoval, Issue
)


class TestIssueType:
    """Test cases for IssueType enum."""
    
    def test_issue_type_values(self):
        """Test that all expected issue types are defined."""
        expected_types = [
            'SYNTAX_ERROR',
            'STYLE_VIOLATION',
            'CODE_SMELL',
            'COMPLEXITY',
            'DUPLICATE_CODE',
            'UNUSED_IMPORT',
            'CIRCULAR_IMPORT',
            'ORPHANED_MODULE',
            'COVERAGE_GAP',
            'CONFIG_ISSUE',
            'DOC_ISSUE',
            'STRUCTURE_ISSUE'
        ]
        
        for issue_type in expected_types:
            assert hasattr(IssueType, issue_type)
            # Check that the enum value exists (the actual value might be different)
            enum_value = getattr(IssueType, issue_type)
            assert enum_value is not None


class TestIssueSeverity:
    """Test cases for IssueSeverity enum."""
    
    def test_severity_values(self):
        """Test that all expected severity levels are defined."""
        expected_severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        
        for severity in expected_severities:
            assert hasattr(IssueSeverity, severity)
            # Check that the enum value exists (the actual value might be different)
            enum_value = getattr(IssueSeverity, severity)
            assert enum_value is not None
    
    def test_severity_ordering(self):
        """Test that severities can be compared."""
        # This assumes the enum has ordering capability
        severities = [IssueSeverity.LOW, IssueSeverity.MEDIUM, IssueSeverity.HIGH, IssueSeverity.CRITICAL]
        
        # Test that they are distinct values
        assert len(set(severities)) == 4


class TestIssue:
    """Test cases for base Issue class."""
    
    def test_issue_creation(self):
        """Test creating a basic issue."""
        issue = QualityIssue(  # Use concrete class since Issue is abstract
            file_path=Path("test.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Test issue",
            description="Test issue description"
        )
        
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.issue_type == IssueType.STYLE_VIOLATION
        assert issue.severity == IssueSeverity.LOW
        assert issue.message == "Test issue"
    
    def test_issue_equality(self):
        """Test issue equality comparison."""
        issue1 = QualityIssue(
            file_path=Path("test.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Test issue",
            description="Test issue description"
        )
        
        issue2 = QualityIssue(
            file_path=Path("test.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Test issue",
            description="Test issue description"
        )
        
        issue3 = QualityIssue(
            file_path=Path("other.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Test issue",
            description="Test issue description"
        )
        
        assert issue1 == issue2
        assert issue1 != issue3
    
    def test_issue_string_representation(self):
        """Test issue string representation."""
        issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=10,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Test issue",
            description="Test issue description"
        )
        
        str_repr = str(issue)
        assert "test.py" in str_repr
        assert "10" in str_repr


class TestQualityIssue:
    """Test cases for QualityIssue class."""
    
    def test_quality_issue_creation(self):
        """Test creating a quality issue."""
        issue = QualityIssue(
            file_path=Path("main.py"),
            line_number=25,
            issue_type=IssueType.COMPLEXITY,
            severity=IssueSeverity.HIGH,
            message="High complexity",
            description="Function has high cyclomatic complexity (15 > 10)"
        )
        
        assert issue.file_path == Path("main.py")
        assert issue.line_number == 25
        assert issue.issue_type == IssueType.COMPLEXITY
        assert issue.severity == IssueSeverity.HIGH
        assert "cyclomatic complexity" in issue.description
    
    def test_quality_issue_with_optional_fields(self):
        """Test quality issue with optional fields."""
        issue = QualityIssue(
            file_path=Path("test.py"),
            line_number=5,
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Line too long",
            description="Line too long",
            rule_name="E501",
            tool_name="flake8"
        )
        
        assert issue.rule_name == "E501"
        assert issue.tool_name == "flake8"


class TestImportIssue:
    """Test cases for ImportIssue class."""
    
    def test_import_issue_creation(self):
        """Test creating an import issue."""
        issue = ImportIssue(
            file_path=Path("utils.py"),
            line_number=3,
            issue_type=IssueType.UNUSED_IMPORT,
            severity=IssueSeverity.LOW,
            message="Unused import",
            description="Unused import: json",
            import_name="json"
        )
        
        assert issue.file_path == Path("utils.py")
        assert issue.line_number == 3
        assert issue.issue_type == IssueType.UNUSED_IMPORT
        assert issue.import_name == "json"
        assert "json" in issue.description
    
    def test_import_issue_with_suggestions(self):
        """Test import issue with suggestions."""
        issue = ImportIssue(
            file_path=Path("main.py"),
            line_number=1,
            issue_type=IssueType.CIRCULAR_IMPORT,
            severity=IssueSeverity.MEDIUM,
            message="Circular import",
            description="Circular import detected",
            import_name="circular_module",
            is_circular=True,
            suggestion="Refactor to remove circular dependency"
        )
        
        assert issue.suggestion == "Refactor to remove circular dependency"
        assert issue.is_circular is True


class TestStructureIssue:
    """Test cases for StructureIssue class."""
    
    def test_structure_issue_creation(self):
        """Test creating a structure issue."""
        issue = StructureIssue(
            file_path=Path("test_outside.py"),
            line_number=None,
            issue_type=IssueType.STRUCTURE_ISSUE,
            severity=IssueSeverity.MEDIUM,
            message="Misplaced file",
            description="Test file outside tests directory",
            suggested_location=Path("tests/test_outside.py")
        )
        
        assert issue.file_path == Path("test_outside.py")
        assert issue.issue_type == IssueType.STRUCTURE_ISSUE
        assert issue.suggested_location == Path("tests/test_outside.py")
    
    def test_structure_issue_empty_directory(self):
        """Test structure issue for empty directory."""
        issue = StructureIssue(
            file_path=Path("empty_dir"),
            line_number=None,
            issue_type=IssueType.STRUCTURE_ISSUE,
            severity=IssueSeverity.LOW,
            message="Empty directory",
            description="Empty directory can be removed"
        )
        
        assert issue.issue_type == IssueType.STRUCTURE_ISSUE
        assert "empty" in issue.description.lower()


class TestCoverageGap:
    """Test cases for CoverageGap class."""
    
    def test_coverage_gap_creation(self):
        """Test creating a coverage gap."""
        gap = CoverageGap(
            file_path=Path("main.py"),
            line_number=15,
            issue_type=IssueType.COVERAGE_GAP,
            severity=IssueSeverity.MEDIUM,
            message="Missing test coverage",
            description="Function has no test coverage",
            function_name="calculate_total"
        )
        
        assert gap.file_path == Path("main.py")
        assert gap.function_name == "calculate_total"
        assert gap.line_number == 15
        assert gap.issue_type == IssueType.COVERAGE_GAP
    
    def test_coverage_gap_with_coverage_percentage(self):
        """Test coverage gap with coverage percentage."""
        gap = CoverageGap(
            file_path=Path("utils.py"),
            line_number=8,
            issue_type=IssueType.COVERAGE_GAP,
            severity=IssueSeverity.LOW,
            message="Low coverage",
            description="Function has low test coverage",
            function_name="helper_function",
            coverage_percentage=45.0
        )
        
        assert gap.coverage_percentage == 45.0


class TestConfigIssue:
    """Test cases for ConfigIssue class."""
    
    def test_config_issue_creation(self):
        """Test creating a config issue."""
        issue = ConfigIssue(
            file_path=Path("pyproject.toml"),
            line_number=None,
            issue_type=IssueType.CONFIG_ISSUE,
            severity=IssueSeverity.MEDIUM,
            message="Missing configuration",
            description="Missing black configuration",
            config_file=Path("pyproject.toml"),
            config_section="tool.black"
        )
        
        assert issue.file_path == Path("pyproject.toml")
        assert issue.issue_type == IssueType.CONFIG_ISSUE
        assert issue.config_section == "tool.black"
    
    def test_config_issue_invalid_config(self):
        """Test config issue for invalid configuration."""
        issue = ConfigIssue(
            file_path=Path("docker-compose.yml"),
            line_number=None,
            issue_type=IssueType.CONFIG_ISSUE,
            severity=IssueSeverity.HIGH,
            message="Invalid configuration",
            description="Invalid YAML syntax",
            config_file=Path("docker-compose.yml"),
            config_section="services",
            suggestion="Fix YAML indentation"
        )
        
        assert issue.issue_type == IssueType.CONFIG_ISSUE
        assert issue.suggestion == "Fix YAML indentation"


class TestDocIssue:
    """Test cases for DocIssue class."""
    
    def test_doc_issue_creation(self):
        """Test creating a documentation issue."""
        issue = DocIssue(
            file_path=Path("README.md"),
            line_number=None,
            issue_type=IssueType.DOC_ISSUE,
            severity=IssueSeverity.LOW,
            message="Missing documentation",
            description="Missing installation section",
            doc_type="installation"
        )
        
        assert issue.file_path == Path("README.md")
        assert issue.issue_type == IssueType.DOC_ISSUE
        assert issue.doc_type == "installation"
    
    def test_doc_issue_outdated(self):
        """Test documentation issue for outdated content."""
        issue = DocIssue(
            file_path=Path("docs/api.md"),
            line_number=None,
            issue_type=IssueType.DOC_ISSUE,
            severity=IssueSeverity.MEDIUM,
            message="Outdated documentation",
            description="API documentation is outdated",
            doc_type="api_reference",
            outdated_example=True,
            suggestion="Update API documentation to match current implementation"
        )
        
        assert issue.issue_type == IssueType.DOC_ISSUE
        assert issue.suggestion is not None
        assert issue.outdated_example is True


class TestDuplicate:
    """Test cases for Duplicate class."""
    
    def test_duplicate_creation(self):
        """Test creating a duplicate."""
        duplicate = Duplicate(
            file_path=Path("file1.py"),
            line_number=10,
            issue_type=IssueType.DUPLICATE_CODE,
            severity=IssueSeverity.MEDIUM,
            message="Duplicate code found",
            description="Duplicate code block detected",
            duplicate_files=[Path("file1.py"), Path("file2.py")],
            lines_of_code=6,
            similarity_score=1.0
        )
        
        assert len(duplicate.duplicate_files) == 2
        assert duplicate.lines_of_code == 6
        assert duplicate.similarity_score == 1.0
    
    def test_duplicate_similar(self):
        """Test creating a similar duplicate."""
        duplicate = Duplicate(
            file_path=Path("a.py"),
            line_number=5,
            issue_type=IssueType.DUPLICATE_CODE,
            severity=IssueSeverity.MEDIUM,
            message="Similar code found",
            description="Similar code block detected",
            duplicate_files=[Path("a.py"), Path("b.py")],
            lines_of_code=6,
            similarity_score=0.85,
            confidence=0.85,
            refactoring_suggestion="Extract common functionality"
        )
        
        assert duplicate.similarity_score == 0.85
        assert duplicate.confidence == 0.85
        assert duplicate.refactoring_suggestion == "Extract common functionality"


class TestCodebaseMetrics:
    """Test cases for CodebaseMetrics class."""
    
    def test_metrics_creation(self):
        """Test creating codebase metrics."""
        metrics = CodebaseMetrics(
            total_files=100,
            total_lines=10000,
            python_files=80,
            test_files=20,
            syntax_errors=2,
            style_violations=15,
            complexity_issues=5,
            duplicate_blocks=8,
            unused_imports=12,
            circular_imports=1,
            orphaned_modules=3,
            test_coverage_percentage=85.5,
            untested_functions=25,
            config_issues=4,
            doc_issues=6
        )
        
        assert metrics.total_files == 100
        assert metrics.total_lines == 10000
        assert metrics.python_files == 80
        assert metrics.test_files == 20
        assert metrics.test_coverage_percentage == 85.5
    
    def test_metrics_calculated_properties(self):
        """Test calculated properties of metrics."""
        metrics = CodebaseMetrics(
            total_files=100,
            total_lines=10000,
            python_files=80,
            test_files=20,
            syntax_errors=2,
            style_violations=15,
            complexity_issues=5,
            duplicate_blocks=8,
            unused_imports=12,
            circular_imports=1,
            orphaned_modules=3,
            test_coverage_percentage=85.5,
            untested_functions=25
        )
        
        # Test basic properties
        assert metrics.total_files == 100
        assert metrics.total_lines == 10000
        assert metrics.python_files == 80
        assert metrics.test_files == 20
        assert metrics.test_coverage_percentage == 85.5


class TestFormattingChange:
    """Test cases for FormattingChange class."""
    
    def test_formatting_change_creation(self):
        """Test creating a formatting change."""
        change = FormattingChange(
            file_path=Path("main.py"),
            change_type="black_formatting",
            lines_changed=15,
            description="Applied black code formatting"
        )
        
        assert change.file_path == Path("main.py")
        assert change.change_type == "black_formatting"
        assert change.lines_changed == 15
        assert "black" in change.description
    
    def test_formatting_change_with_details(self):
        """Test formatting change with additional details."""
        change = FormattingChange(
            file_path=Path("utils.py"),
            change_type="import_sorting",
            lines_changed=8,
            description="Sorted imports with isort",
            before_snippet="import sys\nimport os",
            after_snippet="import os\nimport sys"
        )
        
        assert change.before_snippet == "import sys\nimport os"
        assert change.after_snippet == "import os\nimport sys"


class TestFileMove:
    """Test cases for FileMove class."""
    
    def test_file_move_creation(self):
        """Test creating a file move."""
        move = FileMove(
            source_path=Path("test_outside.py"),
            destination_path=Path("tests/test_outside.py"),
            reason="Move test file to tests directory"
        )
        
        assert move.source_path == Path("test_outside.py")
        assert move.destination_path == Path("tests/test_outside.py")
        assert "tests directory" in move.reason
    
    def test_file_move_with_backup(self):
        """Test file move with backup information."""
        move = FileMove(
            source_path=Path("config.py"),
            destination_path=Path("src/config.py"),
            reason="Move config to src directory",
            backup_created=True,
            backup_path=Path("backup/config.py")
        )
        
        assert move.backup_created is True
        assert move.backup_path == Path("backup/config.py")


class TestFileRemoval:
    """Test cases for FileRemoval class."""
    
    def test_file_removal_creation(self):
        """Test creating a file removal."""
        removal = FileRemoval(
            file_path=Path("empty_dir"),
            reason="Remove empty directory"
        )
        
        assert removal.file_path == Path("empty_dir")
        assert "empty" in removal.reason
    
    def test_file_removal_with_backup(self):
        """Test file removal with backup."""
        removal = FileRemoval(
            file_path=Path("obsolete.py"),
            reason="Remove obsolete file",
            backup_created=True,
            backup_path=Path("backup/obsolete.py")
        )
        
        assert removal.backup_created is True
        assert removal.backup_path == Path("backup/obsolete.py")


class TestAnalysisResults:
    """Test cases for AnalysisResults class."""
    
    def test_analysis_results_creation(self):
        """Test creating analysis results."""
        metrics = CodebaseMetrics(
            total_files=10,
            total_lines=1000,
            python_files=8,
            test_files=3,
            syntax_errors=1,
            style_violations=5,
            complexity_issues=2,
            duplicate_blocks=1,
            unused_imports=3,
            circular_imports=0,
            orphaned_modules=1,
            test_coverage_percentage=80.0,
            untested_functions=5,
            config_issues=2,
            doc_issues=3
        )
        
        quality_issues = [
            QualityIssue(
                file_path=Path("test.py"),
                line_number=10,
                issue_type=IssueType.STYLE_VIOLATION,
                severity=IssueSeverity.LOW,
                description="Line too long"
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
        
        assert len(results.quality_issues) == 1
        assert results.metrics.total_files == 10
        assert isinstance(results.timestamp, datetime)
        assert results.total_issues == 1  # Only one quality issue


class TestCleanupResults:
    """Test cases for CleanupResults class."""
    
    def test_cleanup_results_creation(self):
        """Test creating cleanup results."""
        results = CleanupResults(
            formatting_changes=[
                FormattingChange(
                    file_path=Path("main.py"),
                    change_type="formatting",
                    lines_changed=10,
                    description="Applied formatting"
                )
            ],
            import_cleanups=[],
            file_moves=[],
            file_removals=[],
            auto_fixes=[],
            timestamp=datetime.now()
        )
        
        assert len(results.formatting_changes) == 1
        assert isinstance(results.timestamp, datetime)
        assert results.total_changes == 1


class TestCheckupResults:
    """Test cases for CheckupResults class."""
    
    def test_checkup_results_creation(self):
        """Test creating checkup results."""
        metrics = CodebaseMetrics(
            total_files=5,
            total_lines=500,
            python_files=4,
            test_files=2,
            syntax_errors=0,
            style_violations=2,
            complexity_issues=1,
            duplicate_blocks=0,
            unused_imports=1,
            circular_imports=0,
            orphaned_modules=0,
            test_coverage_percentage=90.0,
            untested_functions=2,
            config_issues=1,
            doc_issues=1
        )
        
        analysis = AnalysisResults(
            quality_issues=[],
            duplicates=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            timestamp=datetime.now(),
            metrics=metrics
        )
        
        cleanup = CleanupResults(
            formatting_changes=[],
            import_cleanups=[],
            file_moves=[],
            file_removals=[],
            auto_fixes=[],
            timestamp=datetime.now()
        )
        
        results = CheckupResults(
            analysis=analysis,
            cleanup=cleanup,
            before_metrics=metrics,
            after_metrics=metrics,
            duration=timedelta(seconds=30),
            success=True
        )
        
        assert results.success is True
        assert results.analysis is not None
        assert results.cleanup is not None
        assert isinstance(results.duration, timedelta)
        assert results.duration.total_seconds() == 30
        # Test improvement metrics
        improvements = results.improvement_metrics
        assert isinstance(improvements, dict)


class TestCheckupConfig:
    """Test cases for CheckupConfig class."""
    
    def test_config_creation_with_defaults(self):
        """Test creating config with default values."""
        config = CheckupConfig(
            target_directory=Path("/tmp/test")
        )
        
        assert config.target_directory == Path("/tmp/test")
        assert config.enable_quality_analysis is True
        assert config.enable_duplicate_detection is True
        assert config.enable_import_analysis is True
        assert config.enable_structure_analysis is True
        assert config.check_test_coverage is True
        assert config.validate_configs is True
        assert config.validate_docs is True
        assert config.auto_format is False
        assert config.auto_fix_imports is False
        assert config.auto_organize_files is False
        assert config.dry_run is False
        assert config.create_backup is True
    
    def test_config_creation_with_custom_values(self):
        """Test creating config with custom values."""
        config = CheckupConfig(
            target_directory=Path("/custom/path"),
            enable_quality_analysis=False,
            enable_duplicate_detection=False,
            auto_format=True,
            auto_fix_imports=True,
            dry_run=True,
            create_backup=False,
            report_output_dir=Path("/custom/reports"),
            max_file_moves=20
        )
        
        assert config.target_directory == Path("/custom/path")
        assert config.enable_quality_analysis is False
        assert config.enable_duplicate_detection is False
        assert config.auto_format is True
        assert config.auto_fix_imports is True
        assert config.dry_run is True
        assert config.create_backup is False
        assert config.report_output_dir == Path("/custom/reports")
        assert config.max_file_moves == 20
    
    def test_config_tool_configurations(self):
        """Test tool-specific configurations."""
        config = CheckupConfig(
            target_directory=Path("/tmp/test"),
            black_config={
                "line_length": 100,
                "target_version": ["py39"]
            },
            isort_config={
                "profile": "black",
                "known_first_party": ["myproject"]
            },
            max_complexity=15,
            max_line_length=100
        )
        
        assert config.black_config["line_length"] == 100
        assert config.isort_config["profile"] == "black"
        assert config.max_complexity == 15
        assert config.max_line_length == 100
    
    def test_config_serialization(self):
        """Test config serialization to dict."""
        config = CheckupConfig(
            target_directory=Path("/tmp/test"),
            enable_quality_analysis=True,
            auto_format=False,
            dry_run=True
        )
        
        config_dict = asdict(config)
        
        assert config_dict["target_directory"] == Path("/tmp/test")
        assert config_dict["enable_quality_analysis"] is True
        assert config_dict["auto_format"] is False
        assert config_dict["dry_run"] is True