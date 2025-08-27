"""
Integration tests for cleanup workflow orchestration.
"""

import pytest
import asyncio
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from migration_assistant.checkup.orchestrator import CodebaseOrchestrator, CleanupError
from migration_assistant.checkup.models import (
    CheckupConfig, AnalysisResults, CleanupResults, CodebaseMetrics,
    FormattingChange, ImportCleanup, FileMove, FileRemoval, AutoFix,
    QualityIssue, IssueSeverity, IssueType
)
from migration_assistant.checkup.cleaners.base import BaseCleaner


class MockFormatter(BaseCleaner):
    """Mock code formatter for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "code_formatter"
    
    async def clean(self, analysis_results):
        # Simulate some processing time
        await asyncio.sleep(0.1)
        
        result = Mock()
        result.success = True
        result.message = "Formatting completed"
        result.formatting_changes = [
            FormattingChange(
                file_path=Path("test.py"),
                change_type="black",
                lines_changed=5,
                description="Applied black formatting"
            )
        ]
        result.import_cleanups = []
        result.file_moves = []
        result.file_removals = []
        result.auto_fixes = []
        return result


class MockImportCleaner(BaseCleaner):
    """Mock import cleaner for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "import_cleaner"
    
    async def clean(self, analysis_results):
        await asyncio.sleep(0.1)
        
        result = Mock()
        result.success = True
        result.message = "Import cleanup completed"
        result.formatting_changes = []
        result.import_cleanups = [
            ImportCleanup(
                file_path=Path("module.py"),
                removed_imports=["os", "sys"],
                reorganized_imports=True
            )
        ]
        result.file_moves = []
        result.file_removals = []
        result.auto_fixes = []
        return result


class MockFileOrganizer(BaseCleaner):
    """Mock file organizer for testing."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "file_organizer"
    
    async def clean(self, analysis_results):
        await asyncio.sleep(0.1)
        
        result = Mock()
        result.success = True
        result.message = "File organization completed"
        result.formatting_changes = []
        result.import_cleanups = []
        result.file_moves = [
            FileMove(
                source_path=Path("misplaced.py"),
                destination_path=Path("utils/misplaced.py"),
                reason="Better organization",
                success=True
            )
        ]
        result.file_removals = [
            FileRemoval(
                file_path=Path("empty_dir"),
                reason="Empty directory",
                success=True
            )
        ]
        result.auto_fixes = []
        return result


class FailingCleaner(BaseCleaner):
    """Mock cleaner that fails for testing error handling."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "failing_cleaner"
    
    async def clean(self, analysis_results):
        raise Exception("Cleaner intentionally failed")


class TestCleanupWorkflowIntegration:
    """Test complete cleanup workflow integration."""
    
    @pytest.mark.asyncio
    async def test_full_cleanup_workflow_success(self, tmp_path):
        """Test successful execution of complete cleanup workflow."""
        # Create test files
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")
        
        module_file = tmp_path / "module.py"
        module_file.write_text("import os\nimport sys\nprint('test')")
        
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            auto_fix_imports=True,
            auto_organize_files=True,
            create_backup=True,
            backup_dir=tmp_path / "backups"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Register cleaners
        orchestrator.register_cleaner(MockFormatter)
        orchestrator.register_cleaner(MockImportCleaner)
        orchestrator.register_cleaner(MockFileOrganizer)
        
        # Create analysis results
        analysis_results = AnalysisResults(
            quality_issues=[
                QualityIssue(
                    file_path=test_file,
                    line_number=1,
                    severity=IssueSeverity.MEDIUM,
                    issue_type=IssueType.STYLE_VIOLATION,
                    message="Style issue",
                    description="Test issue"
                )
            ]
        )
        
        # Run cleanup
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Verify results
        assert isinstance(results, CleanupResults)
        assert results.backup_created is True
        assert results.backup_path is not None
        assert results.backup_path.exists()
        
        # Verify changes were recorded
        assert len(results.formatting_changes) == 1
        assert len(results.import_cleanups) == 1
        assert len(results.file_moves) == 1
        assert len(results.file_removals) == 1
        
        assert results.total_changes == 4
        assert results.successful_changes == 4
        
        # Verify timing
        assert results.duration > timedelta(0)
        assert results.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_cleanup_with_backup_creation(self, tmp_path):
        """Test cleanup workflow with backup creation."""
        # Create test files
        (tmp_path / "important.py").write_text("# Important file")
        (tmp_path / "data.txt").write_text("Important data")
        
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            create_backup=True,
            backup_dir=tmp_path / "backups"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        orchestrator.register_cleaner(MockFormatter)
        
        analysis_results = AnalysisResults()
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Verify backup was created
        assert results.backup_created is True
        assert results.backup_path is not None
        assert results.backup_path.exists()
        
        # Verify backup contains original files
        backup_important = results.backup_path / "important.py"
        backup_data = results.backup_path / "data.txt"
        
        assert backup_important.exists()
        assert backup_data.exists()
        assert backup_important.read_text() == "# Important file"
        assert backup_data.read_text() == "Important data"
    
    @pytest.mark.asyncio
    async def test_cleanup_without_backup(self, tmp_path):
        """Test cleanup workflow without backup creation."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            create_backup=False  # Disabled
        )
        
        orchestrator = CodebaseOrchestrator(config)
        orchestrator.register_cleaner(MockFormatter)
        
        analysis_results = AnalysisResults()
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Verify no backup was created
        assert results.backup_created is False
        assert results.backup_path is None
    
    @pytest.mark.asyncio
    async def test_cleanup_dry_run(self, tmp_path):
        """Test cleanup workflow in dry run mode."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            create_backup=True,
            dry_run=True  # Dry run mode
        )
        
        orchestrator = CodebaseOrchestrator(config)
        orchestrator.register_cleaner(MockFormatter)
        
        analysis_results = AnalysisResults()
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Verify no backup was created in dry run
        assert results.backup_created is False
        assert results.backup_path is None
    
    @pytest.mark.asyncio
    async def test_cleanup_with_disabled_cleaners(self, tmp_path):
        """Test cleanup workflow with some cleaners disabled."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,      # Enabled
            auto_fix_imports=False, # Disabled
            auto_organize_files=True, # Enabled
            create_backup=False
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Register all cleaners
        orchestrator.register_cleaner(MockFormatter)
        orchestrator.register_cleaner(MockImportCleaner)  # Should not run
        orchestrator.register_cleaner(MockFileOrganizer)
        
        analysis_results = AnalysisResults()
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should only have results from enabled cleaners
        assert len(results.formatting_changes) == 1  # From formatter
        assert len(results.import_cleanups) == 0     # Import cleaner disabled
        assert len(results.file_moves) == 1          # From file organizer
        assert len(results.file_removals) == 1       # From file organizer
        
        assert results.total_changes == 3
    
    @pytest.mark.asyncio
    async def test_cleanup_with_no_enabled_cleaners(self, tmp_path):
        """Test cleanup workflow with no cleaners enabled."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=False,
            auto_fix_imports=False,
            auto_organize_files=False,
            create_backup=False
        )
        
        orchestrator = CodebaseOrchestrator(config)
        orchestrator.register_cleaner(MockFormatter)
        orchestrator.register_cleaner(MockImportCleaner)
        orchestrator.register_cleaner(MockFileOrganizer)
        
        analysis_results = AnalysisResults()
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should have no changes
        assert results.total_changes == 0
        assert len(results.formatting_changes) == 0
        assert len(results.import_cleanups) == 0
        assert len(results.file_moves) == 0
        assert len(results.file_removals) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_with_partial_failures(self, tmp_path):
        """Test cleanup workflow with some cleaners failing."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            create_backup=False
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Register working and failing cleaners
        orchestrator.register_cleaner(MockFormatter)
        orchestrator.register_cleaner(FailingCleaner)
        
        # Mock the should_run_cleaner to return True for both
        with patch.object(orchestrator, '_should_run_cleaner', return_value=True):
            analysis_results = AnalysisResults()
            results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should still get results from working cleaner
        assert len(results.formatting_changes) == 1
        assert results.total_changes == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_with_majority_failures_triggers_rollback(self, tmp_path):
        """Test cleanup workflow with majority of cleaners failing triggers rollback."""
        # Create test files
        (tmp_path / "test.py").write_text("print('test')")
        
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            create_backup=True,
            backup_dir=tmp_path / "backups"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Register mostly failing cleaners
        orchestrator.register_cleaner(FailingCleaner)
        
        failing_cleaner2 = FailingCleaner(config)
        failing_cleaner2.name = "failing_cleaner2"
        orchestrator._cleaners.append(failing_cleaner2)
        
        # Mock the should_run_cleaner to return True for all
        with patch.object(orchestrator, '_should_run_cleaner', return_value=True):
            analysis_results = AnalysisResults()
            
            with pytest.raises(CleanupError, match="Too many cleaners failed"):
                await orchestrator.run_cleanup_only(analysis_results)
    
    @pytest.mark.asyncio
    async def test_cleanup_validation_success(self, tmp_path):
        """Test successful cleanup validation."""
        # Create test files that will pass validation
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello world')")
        
        (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 88")
        
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            create_backup=False
        )
        
        orchestrator = CodebaseOrchestrator(config)
        orchestrator.register_cleaner(MockFormatter)
        
        analysis_results = AnalysisResults()
        results = await orchestrator.run_cleanup_only(analysis_results)
        
        # Should complete successfully
        assert results.total_changes == 1
        assert len(results.formatting_changes) == 1
    
    @pytest.mark.asyncio
    async def test_rollback_functionality(self, tmp_path):
        """Test rollback functionality."""
        # Create original files
        original_file = tmp_path / "original.py"
        original_content = "# Original content"
        original_file.write_text(original_content)
        
        config = CheckupConfig(
            target_directory=tmp_path,
            backup_dir=tmp_path / "backups"
        )
        
        orchestrator = CodebaseOrchestrator(config)
        
        # Create a backup
        backup_path = await orchestrator._create_backup()
        
        # Modify the original file
        original_file.write_text("# Modified content")
        
        # Perform rollback
        await orchestrator._rollback_changes(backup_path)
        
        # Verify rollback restored original content
        assert original_file.read_text() == original_content
    
    @pytest.mark.asyncio
    async def test_cleanup_validation_detects_syntax_errors(self, tmp_path):
        """Test that cleanup validation detects syntax errors."""
        # Create a file with valid syntax initially
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")
        
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Create cleanup results with a formatting change
        cleanup_results = CleanupResults(
            formatting_changes=[
                FormattingChange(
                    file_path=test_file,
                    change_type="black",
                    lines_changed=1
                )
            ]
        )
        
        # Introduce syntax error
        test_file.write_text("print('hello'")  # Missing closing parenthesis
        
        analysis_results = AnalysisResults()
        validation_passed = await orchestrator._validate_cleanup_results(cleanup_results, analysis_results)
        
        assert validation_passed is False
    
    @pytest.mark.asyncio
    async def test_cleanup_validation_detects_missing_moved_files(self, tmp_path):
        """Test that cleanup validation detects missing moved files."""
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Create cleanup results with a file move
        cleanup_results = CleanupResults(
            file_moves=[
                FileMove(
                    source_path=tmp_path / "source.py",
                    destination_path=tmp_path / "dest.py",
                    success=True
                )
            ]
        )
        
        # Don't create the destination file
        analysis_results = AnalysisResults()
        validation_passed = await orchestrator._validate_cleanup_results(cleanup_results, analysis_results)
        
        assert validation_passed is False
    
    @pytest.mark.asyncio
    async def test_cleanup_validation_protects_critical_files(self, tmp_path):
        """Test that cleanup validation protects critical files."""
        # Create critical file
        critical_file = tmp_path / "pyproject.toml"
        critical_file.write_text("[tool.black]\n")
        
        config = CheckupConfig(target_directory=tmp_path)
        orchestrator = CodebaseOrchestrator(config)
        
        # Create cleanup results that removed a critical file
        cleanup_results = CleanupResults(
            file_removals=[
                FileRemoval(
                    file_path=critical_file,
                    success=True,
                    reason="Accidentally removed"
                )
            ]
        )
        
        analysis_results = AnalysisResults()
        validation_passed = await orchestrator._validate_cleanup_results(cleanup_results, analysis_results)
        
        assert validation_passed is False
    
    @pytest.mark.asyncio
    async def test_progress_tracking_in_cleanup(self, tmp_path, caplog):
        """Test that cleanup workflow provides progress tracking."""
        config = CheckupConfig(
            target_directory=tmp_path,
            auto_format=True,
            auto_fix_imports=True,
            create_backup=False
        )
        
        orchestrator = CodebaseOrchestrator(config)
        orchestrator.register_cleaner(MockFormatter)
        orchestrator.register_cleaner(MockImportCleaner)
        
        with caplog.at_level("INFO"):
            analysis_results = AnalysisResults()
            await orchestrator.run_cleanup_only(analysis_results)
        
        # Check for progress messages
        log_messages = [record.message for record in caplog.records]
        
        assert any("Running cleanup with" in msg for msg in log_messages)
        assert any("Running cleaner: code_formatter" in msg for msg in log_messages)
        assert any("Running cleaner: import_cleaner" in msg for msg in log_messages)
        assert any("Completed code_formatter successfully" in msg for msg in log_messages)
        assert any("Completed import_cleaner successfully" in msg for msg in log_messages)
        assert any("Progress:" in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_sequential_cleaner_execution(self, tmp_path):
        """Test that cleaners run sequentially to avoid conflicts."""
        execution_order = []
        
        class OrderTrackingCleaner(BaseCleaner):
            def __init__(self, config, name):
                super().__init__(config)
                self.name = name
            
            async def clean(self, analysis_results):
                execution_order.append(self.name)
                await asyncio.sleep(0.1)  # Simulate work
                result = Mock()
                result.success = True
                result.formatting_changes = []
                result.import_cleanups = []
                result.file_moves = []
                result.file_removals = []
                result.auto_fixes = []
                return result
        
        config = CheckupConfig(target_directory=tmp_path, create_backup=False)
        orchestrator = CodebaseOrchestrator(config)
        
        # Register cleaners
        cleaner1 = OrderTrackingCleaner(config, "cleaner1")
        cleaner2 = OrderTrackingCleaner(config, "cleaner2")
        cleaner3 = OrderTrackingCleaner(config, "cleaner3")
        
        orchestrator._cleaners = [cleaner1, cleaner2, cleaner3]
        
        with patch.object(orchestrator, '_should_run_cleaner', return_value=True):
            analysis_results = AnalysisResults()
            await orchestrator.run_cleanup_only(analysis_results)
        
        # Verify sequential execution
        assert execution_order == ["cleaner1", "cleaner2", "cleaner3"]


if __name__ == "__main__":
    pytest.main([__file__])