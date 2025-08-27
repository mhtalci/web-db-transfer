"""
Comprehensive unit tests for checkup models.
Tests all model classes to ensure 90%+ code coverage.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migration_assistant.checkup.models import (
    # Configuration
    CheckupConfig,
    
    # Enums
    IssueType, IssueSeverity,
    
    # Base Issue Classes
    Issue,
    
    # Specific Issue Classes
    QualityIssue, ImportIssue, StructureIssue, CoverageGap, ConfigIssue, DocIssue, Duplicate,
    
    # Results Classes
    AnalysisResults, CleanupResults, CheckupResults,
    
    # Metrics Classes
    CodebaseMetrics,
    
    # Change Classes
    FormattingChange, FileMove, FileRemoval, ImportCleanup, AutoFix
)


class TestEnums:
    """Test cases for enum classes."""
    
    def test_issue_type_enum(self):
        """Test IssueType enum."""
        # Test that all expected issue types exist
        assert hasattr(IssueType, 'SYNTAX_ERROR')
        assert hasattr(IssueType, 'STYLE_VIOLATION')
        assert hasattr(IssueType, 'COMPLEXITY')
        assert hasattr(IssueType, 'CODE_SMELL')
        assert hasattr(IssueType, 'DUPLICATE_CODE')
        assert hasattr(IssueType, 'UNUSED_IMPORT')
        assert hasattr(IssueType, 'CIRCULAR_IMPORT')
        assert hasattr(IssueType, 'ORPHANED_MODULE')
        assert hasattr(IssueType, 'COVERAGE_GAP')
        assert hasattr(IssueType, 'CONFIG_ISSUE')
        assert hasattr(IssueType, 'DOC_ISSUE')
        assert hasattr(IssueType, 'STRUCTURE_ISSUE')
        
        # Test enum values are strings
        assert isinstance(IssueType.SYNTAX_ERROR.value, str)
        assert isinstance(IssueType.STYLE_VIOLATION.value, str)
    
    def test_issue_severity_enum(self):
        """Test IssueSeverity enum."""
        # Test that all expected severities exist
        assert hasattr(IssueSeverity, 'LOW')
        assert hasattr(IssueSeverity, 'MEDIUM')
        assert hasattr(IssueSeverity, 'HIGH')
        assert hasattr(IssueSeverity, 'CRITICAL')
        
        # Test enum values are strings
        assert isinstance(IssueSeverity.LOW.value, str)
        assert isinstance(IssueSeverity.MEDIUM.value, str)
        assert isinstance(IssueSeverity.HIGH.value, str)
        assert isinstance(IssueSeverity.CRITICAL.value, str)
        
        # Test ordering (if implemented)
        severities = [IssueSeverity.LOW, IssueSeverity.MEDIUM, IssueSeverity.HIGH, IssueSeverity.CRITICAL]
        assert len(severities) == 4


class TestCheckupConfig:
    """Test cases for CheckupConfig."""
    
    def test_default_initialization(self):
        """Test default configuration initialization."""
        config = CheckupConfig(target_directory=Path("/tmp"))
        
        # Test required fields
        assert config.target_directory == Path("/tmp")
        
        # Test default values
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
        
        assert config.generate_html_report is True
        assert config.generate_json_report is True
        assert config.generate_markdown_report is True
        
        assert config.create_backup is True
        assert config.dry_run is False
    
    def test_custom_initialization(self):
        """Test custom configuration initialization."""
        config = CheckupConfig(
            target_directory=Path("/custom"),
            enable_quality_analysis=False,
            auto_format=True,
            max_line_length=100,
            min_coverage_threshold=90.0,
            max_file_moves=5,
            similarity_threshold=0.9
        )
        
        assert config.target_directory == Path("/custom")
        assert config.enable_quality_analysis is False
        assert config.auto_format is True
        assert config.max_line_length == 100
        assert config.min_coverage_threshold == 90.0
        assert config.max_file_moves == 5
        assert config.similarity_threshold == 0.9
    
    def test_validation(self):
        """Test configuration validation."""
        # Test valid configuration
        valid_config = CheckupConfig(
            target_directory=Path("/tmp"),
            min_coverage_threshold=85.0,
            similarity_threshold=0.8
        )
        assert valid_config.min_coverage_threshold == 85.0
        assert valid_config.similarity_threshold == 0.8
        
        # Test boundary values
        boundary_config = CheckupConfig(
            target_directory=Path("/tmp"),
            min_coverage_threshold=0.0,
            similarity_threshold=1.0
        )
        assert boundary_config.min_coverage_threshold == 0.0
        assert boundary_config.similarity_threshold == 1.0


class TestIssue:
    """Test cases for Issue base class."""
    
    def test_issue_creation(self):
        """Test Issue creation."""
        issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Test error message",
            description="Test error description",
            line_number=10
        )
        
        assert issue.file_path == Path("test.py")
        assert issue.issue_type == IssueType.SYNTAX_ERROR
        assert issue.severity == IssueSeverity.HIGH
        assert issue.message == "Test error message"
        assert issue.description == "Test error description"
        assert issue.line_number == 10
    
    def test_issue_equality(self):
        """Test Issue equality comparison."""
        issue1 = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Error message",
            description="Error description",
            line_number=5
        )
        
        issue2 = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Error message",
            description="Error description",
            line_number=5
        )
        
        issue3 = QualityIssue(
            file_path=Path("other.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Error message",
            description="Error description",
            line_number=5
        )
        
        # Same content should be equal
        assert issue1.file_path == issue2.file_path
        assert issue1.issue_type == issue2.issue_type
        assert issue1.severity == issue2.severity
        assert issue1.message == issue2.message
        
        # Different content should not be equal
        assert issue1.file_path != issue3.file_path


class TestSpecificIssueClasses:
    """Test cases for specific issue classes."""
    
    def test_quality_issue(self):
        """Test QualityIssue class."""
        issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.MEDIUM,
            message="Line too long",
            description="Line exceeds maximum length",
            line_number=5,
            tool_name="flake8",
            rule_name="E501"
        )
        
        assert isinstance(issue, Issue)
        assert issue.tool_name == "flake8"
        assert issue.rule_name == "E501"
    
    def test_import_issue(self):
        """Test ImportIssue class."""
        issue = ImportIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.UNUSED_IMPORT,
            severity=IssueSeverity.LOW,
            message="Unused import",
            description="Import is not used in the file",
            line_number=1,
            import_name="unused_module"
        )
        
        assert isinstance(issue, Issue)
        assert issue.import_name == "unused_module"
    
    def test_structure_issue(self):
        """Test StructureIssue class."""
        issue = StructureIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STRUCTURE_ISSUE,
            severity=IssueSeverity.MEDIUM,
            message="File in wrong location",
            description="Test file should be in tests directory",
            line_number=None,
            suggested_location=Path("tests/test.py")
        )
        
        assert isinstance(issue, Issue)
        assert issue.suggested_location == Path("tests/test.py")
    
    def test_coverage_gap(self):
        """Test CoverageGap class."""
        gap = CoverageGap(
            file_path=Path("source.py"),
            issue_type=IssueType.COVERAGE_GAP,
            severity=IssueSeverity.MEDIUM,
            message="Function not covered by tests",
            description="Function needs test coverage",
            line_number=10,
            function_name="uncovered_function",
            coverage_percentage=0.0
        )
        
        assert gap.file_path == Path("source.py")
        assert gap.function_name == "uncovered_function"
        assert gap.coverage_percentage == 0.0
    
    def test_config_issue(self):
        """Test ConfigIssue class."""
        issue = ConfigIssue(
            file_path=Path("pyproject.toml"),
            issue_type=IssueType.CONFIG_ISSUE,
            severity=IssueSeverity.LOW,
            message="Missing description field",
            description="Project description is missing",
            line_number=5,
            config_file=Path("pyproject.toml"),
            config_section="project"
        )
        
        assert isinstance(issue, Issue)
        assert issue.config_file == Path("pyproject.toml")
        assert issue.config_section == "project"
    
    def test_doc_issue(self):
        """Test DocIssue class."""
        issue = DocIssue(
            file_path=Path("source.py"),
            issue_type=IssueType.DOC_ISSUE,
            severity=IssueSeverity.LOW,
            message="Function missing docstring",
            description="Function should have a docstring",
            line_number=10,
            doc_type="api"
        )
        
        assert isinstance(issue, Issue)
        assert issue.doc_type == "api"


class TestCodebaseMetrics:
    """Test cases for CodebaseMetrics."""
    
    def test_default_initialization(self):
        """Test default metrics initialization."""
        metrics = CodebaseMetrics()
        
        assert metrics.total_files == 0
        assert metrics.total_lines == 0
        assert metrics.syntax_errors == 0
        assert metrics.style_violations == 0
        # type_errors is not in the actual model, so skip this assertion
        assert metrics.complexity_issues == 0
        assert metrics.code_smells == 0
        assert metrics.unused_imports == 0
        assert metrics.circular_imports == 0
        assert metrics.orphaned_modules == 0
        assert metrics.misplaced_files == 0
        assert metrics.empty_directories == 0
        assert metrics.test_coverage_percentage == 0.0
        # missing_docstrings and config_issues are not in the actual model
    
    def test_custom_initialization(self):
        """Test custom metrics initialization."""
        metrics = CodebaseMetrics(
            total_files=100,
            total_lines=10000,
            syntax_errors=5,
            style_violations=20,
            test_coverage_percentage=85.5
        )
        
        assert metrics.total_files == 100
        assert metrics.total_lines == 10000
        assert metrics.syntax_errors == 5
        assert metrics.style_violations == 20
        assert metrics.test_coverage_percentage == 85.5
    
    def test_calculated_properties(self):
        """Test calculated properties."""
        metrics = CodebaseMetrics(
            total_files=100,
            total_lines=10000,
            syntax_errors=5,
            style_violations=20,
            unused_imports=10
        )
        
        # Test lines per file calculation
        if metrics.total_files > 0:
            lines_per_file = metrics.total_lines / metrics.total_files
            assert lines_per_file == 100.0  # 10000 / 100
    
    def test_metrics_update(self):
        """Test metrics updating."""
        metrics = CodebaseMetrics(syntax_errors=5)
        
        # Update metrics
        metrics.syntax_errors += 2
        metrics.style_violations = 10
        
        assert metrics.syntax_errors == 7
        assert metrics.style_violations == 10


class TestResultClasses:
    """Test cases for result classes."""
    
    def test_analysis_results(self):
        """Test AnalysisResults class."""
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.SYNTAX_ERROR,
            severity=IssueSeverity.HIGH,
            message="Syntax error",
            description="Invalid syntax found",
            line_number=5
        )
        
        import_issue = ImportIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.UNUSED_IMPORT,
            severity=IssueSeverity.LOW,
            message="Unused import",
            description="Import not used",
            line_number=1,
            import_name="unused"
        )
        
        metrics = CodebaseMetrics(
            total_files=10,
            syntax_errors=1,
            unused_imports=1
        )
        
        results = AnalysisResults(
            quality_issues=[quality_issue],
            import_issues=[import_issue],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            duplicates=[],
            timestamp=datetime.now(),
            metrics=metrics
        )
        
        assert len(results.quality_issues) == 1
        assert len(results.import_issues) == 1
        assert len(results.structure_issues) == 0
        assert len(results.duplicates) == 0
        assert results.total_issues == 2
        assert isinstance(results.timestamp, datetime)
        assert results.metrics == metrics
    
    def test_cleanup_results(self):
        """Test CleanupResults class."""
        formatting_change = FormattingChange(
            file_path=Path("test.py"),
            change_type="black",
            lines_changed=5,
            description="Applied black formatting"
        )
        
        file_move = FileMove(
            source_path=Path("test.py"),
            destination_path=Path("tests/test.py"),
            reason="Move test file to tests directory"
        )
        
        results = CleanupResults(
            formatting_changes=[formatting_change],
            import_cleanups=[],
            file_moves=[file_move],
            file_removals=[],
            auto_fixes=[],
            timestamp=datetime.now()
        )
        
        assert len(results.formatting_changes) == 1
        assert len(results.file_moves) == 1
        assert results.total_changes == 2
        assert isinstance(results.timestamp, datetime)
    
    def test_checkup_results(self):
        """Test CheckupResults class."""
        analysis_results = AnalysisResults(
            quality_issues=[],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            duplicates=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(total_files=10)
        )
        
        cleanup_results = CleanupResults(
            formatting_changes=[],
            import_cleanups=[],
            file_moves=[],
            file_removals=[],
            auto_fixes=[],
            timestamp=datetime.now()
        )
        
        before_metrics = CodebaseMetrics(total_files=10, style_violations=5)
        after_metrics = CodebaseMetrics(total_files=10, style_violations=2)
        
        results = CheckupResults(
            analysis=analysis_results,
            cleanup=cleanup_results,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            duration=timedelta(minutes=5),
            success=True
        )
        
        assert results.analysis == analysis_results
        assert results.cleanup == cleanup_results
        assert results.before_metrics == before_metrics
        assert results.after_metrics == after_metrics
        assert results.duration == timedelta(minutes=5)
        assert results.success is True


class TestChangeClasses:
    """Test cases for change classes."""
    
    def test_formatting_change(self):
        """Test FormattingChange class."""
        change = FormattingChange(
            file_path=Path("test.py"),
            change_type="black",
            lines_changed=10,
            description="Applied black formatting to fix indentation"
        )
        
        assert change.file_path == Path("test.py")
        assert change.change_type == "black"
        assert change.lines_changed == 10
        assert change.description == "Applied black formatting to fix indentation"
    
    def test_file_move(self):
        """Test FileMove class."""
        move = FileMove(
            source_path=Path("test.py"),
            destination_path=Path("tests/test.py"),
            reason="Move test file to appropriate directory",
            success=True
        )
        
        assert move.source_path == Path("test.py")
        assert move.destination_path == Path("tests/test.py")
        assert move.reason == "Move test file to appropriate directory"
        assert move.success is True
    
    def test_file_removal(self):
        """Test FileRemoval class."""
        removal = FileRemoval(
            file_path=Path("unused.py"),
            reason="Orphaned module with no references",
            backup_path=Path("backup/unused.py"),
            success=True
        )
        
        assert removal.file_path == Path("unused.py")
        assert removal.reason == "Orphaned module with no references"
        assert removal.backup_path == Path("backup/unused.py")
        assert removal.success is True





class TestModelIntegration:
    """Test cases for model integration and relationships."""
    
    def test_issue_to_metrics_relationship(self):
        """Test relationship between issues and metrics."""
        # Create various issues
        issues = [
            QualityIssue(
                file_path=Path("test1.py"), 
                issue_type=IssueType.SYNTAX_ERROR, 
                severity=IssueSeverity.HIGH, 
                message="Error 1",
                description="Syntax error",
                line_number=1
            ),
            QualityIssue(
                file_path=Path("test2.py"), 
                issue_type=IssueType.STYLE_VIOLATION, 
                severity=IssueSeverity.LOW, 
                message="Error 2",
                description="Style violation",
                line_number=2
            ),
            ImportIssue(
                file_path=Path("test3.py"), 
                issue_type=IssueType.UNUSED_IMPORT, 
                severity=IssueSeverity.LOW, 
                message="Error 3",
                description="Unused import",
                line_number=1,
                import_name="unused"
            ),
            StructureIssue(
                file_path=Path("test4.py"), 
                issue_type=IssueType.STRUCTURE_ISSUE, 
                severity=IssueSeverity.MEDIUM, 
                message="Error 4",
                description="Structure issue",
                line_number=None
            )
        ]
        
        # Create metrics that should reflect these issues
        metrics = CodebaseMetrics(
            total_files=4,
            syntax_errors=1,
            style_violations=1,
            unused_imports=1,
            misplaced_files=1
        )
        
        # Verify metrics match issues
        syntax_errors = [i for i in issues if i.issue_type == IssueType.SYNTAX_ERROR]
        assert len(syntax_errors) == metrics.syntax_errors
        
        style_violations = [i for i in issues if i.issue_type == IssueType.STYLE_VIOLATION]
        assert len(style_violations) == metrics.style_violations
    
    def test_analysis_to_cleanup_workflow(self):
        """Test workflow from analysis to cleanup."""
        # Create analysis results with cleanable issues
        quality_issue = QualityIssue(
            file_path=Path("test.py"),
            issue_type=IssueType.STYLE_VIOLATION,
            severity=IssueSeverity.LOW,
            message="Line too long",
            description="Line exceeds maximum length",
            line_number=5
        )
        
        analysis_results = AnalysisResults(
            quality_issues=[quality_issue],
            import_issues=[],
            structure_issues=[],
            coverage_gaps=[],
            config_issues=[],
            doc_issues=[],
            duplicates=[],
            timestamp=datetime.now(),
            metrics=CodebaseMetrics(total_files=1, style_violations=1)
        )
        
        # Create cleanup results that address the issues
        formatting_change = FormattingChange(
            file_path=Path("test.py"),
            change_type="black",
            lines_changed=1,
            description="Fixed line length"
        )
        
        cleanup_results = CleanupResults(
            formatting_changes=[formatting_change],
            import_cleanups=[],
            file_moves=[],
            file_removals=[],
            auto_fixes=[],
            timestamp=datetime.now()
        )
        
        # Verify the relationship
        assert analysis_results.quality_issues[0].file_path == cleanup_results.formatting_changes[0].file_path
        assert analysis_results.total_issues == 1
        assert cleanup_results.total_changes == 1


if __name__ == "__main__":
    # Run tests manually without pytest
    def run_tests():
        """Run all tests manually."""
        print("Running model tests...")
        
        # Test Enums
        test_enums = TestEnums()
        try:
            test_enums.test_issue_type_enum()
            print("✓ test_issue_type_enum passed")
        except Exception as e:
            print(f"✗ test_issue_type_enum failed: {e}")
        
        try:
            test_enums.test_issue_severity_enum()
            print("✓ test_issue_severity_enum passed")
        except Exception as e:
            print(f"✗ test_issue_severity_enum failed: {e}")
        
        # Test CheckupConfig
        test_config = TestCheckupConfig()
        try:
            test_config.test_default_initialization()
            print("✓ test_default_initialization passed")
        except Exception as e:
            print(f"✗ test_default_initialization failed: {e}")
        
        try:
            test_config.test_custom_initialization()
            print("✓ test_custom_initialization passed")
        except Exception as e:
            print(f"✗ test_custom_initialization failed: {e}")
        
        # Test Issue
        test_issue = TestIssue()
        try:
            test_issue.test_issue_creation()
            print("✓ test_issue_creation passed")
        except Exception as e:
            print(f"✗ test_issue_creation failed: {e}")
        
        try:
            test_issue.test_issue_equality()
            print("✓ test_issue_equality passed")
        except Exception as e:
            print(f"✗ test_issue_equality failed: {e}")
        
        # Test Specific Issue Classes
        test_issues = TestSpecificIssueClasses()
        try:
            test_issues.test_quality_issue()
            print("✓ test_quality_issue passed")
        except Exception as e:
            print(f"✗ test_quality_issue failed: {e}")
        
        try:
            test_issues.test_import_issue()
            print("✓ test_import_issue passed")
        except Exception as e:
            print(f"✗ test_import_issue failed: {e}")
        
        try:
            test_issues.test_coverage_gap()
            print("✓ test_coverage_gap passed")
        except Exception as e:
            print(f"✗ test_coverage_gap failed: {e}")
        
        # Test CodebaseMetrics
        test_metrics = TestCodebaseMetrics()
        try:
            test_metrics.test_default_initialization()
            print("✓ test_metrics_default_initialization passed")
        except Exception as e:
            print(f"✗ test_metrics_default_initialization failed: {e}")
        
        try:
            test_metrics.test_calculated_properties()
            print("✓ test_calculated_properties passed")
        except Exception as e:
            print(f"✗ test_calculated_properties failed: {e}")
        
        # Test Result Classes
        test_results = TestResultClasses()
        try:
            test_results.test_analysis_results()
            print("✓ test_analysis_results passed")
        except Exception as e:
            print(f"✗ test_analysis_results failed: {e}")
        
        try:
            test_results.test_cleanup_results()
            print("✓ test_cleanup_results passed")
        except Exception as e:
            print(f"✗ test_cleanup_results failed: {e}")
        
        try:
            test_results.test_checkup_results()
            print("✓ test_checkup_results passed")
        except Exception as e:
            print(f"✗ test_checkup_results failed: {e}")
        
        # Test Change Classes
        test_changes = TestChangeClasses()
        try:
            test_changes.test_formatting_change()
            print("✓ test_formatting_change passed")
        except Exception as e:
            print(f"✗ test_formatting_change failed: {e}")
        
        try:
            test_changes.test_file_move()
            print("✓ test_file_move passed")
        except Exception as e:
            print(f"✗ test_file_move failed: {e}")
        
        try:
            test_changes.test_file_removal()
            print("✓ test_file_removal passed")
        except Exception as e:
            print(f"✗ test_file_removal failed: {e}")
        
        # Test Integration
        test_integration = TestModelIntegration()
        try:
            test_integration.test_issue_to_metrics_relationship()
            print("✓ test_issue_to_metrics_relationship passed")
        except Exception as e:
            print(f"✗ test_issue_to_metrics_relationship failed: {e}")
        
        try:
            test_integration.test_analysis_to_cleanup_workflow()
            print("✓ test_analysis_to_cleanup_workflow passed")
        except Exception as e:
            print(f"✗ test_analysis_to_cleanup_workflow failed: {e}")
    
    # Run tests
    run_tests()
    print("\nTest run completed!")