"""
Integration tests for checkup CLI user interactions.

Tests progress display, user confirmations, and interactive features.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile
import yaml
import asyncio
import time

from migration_assistant.cli.main import main


class TestCheckupCLIInteractions:
    """Test cases for CLI user interactions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    @patch('migration_assistant.cli.main.Confirm.ask')
    def test_interactive_destructive_operation_confirmation(self, mock_confirm, mock_asyncio_run, mock_orchestrator):
        """Test user confirmation for destructive operations."""
        # Create config with destructive operations
        config_data = {
            'target_directory': str(self.temp_path),
            'auto_format': True,
            'auto_fix_imports': True,
            'auto_organize_files': True,
            'dry_run': False
        }
        config_file = self.temp_path / 'destructive-config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Mock user declining destructive operations
        mock_confirm.return_value = False
        
        # Mock orchestrator results
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        mock_asyncio_run.return_value = mock_results
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--config', str(config_file),
            '--interactive'
        ])
        
        assert result.exit_code == 0
        assert 'Destructive Operations Detected' in result.output
        assert 'Switching to analysis-only mode' in result.output
        mock_confirm.assert_called_once()
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    @patch('migration_assistant.cli.main.Confirm.ask')
    def test_interactive_destructive_operation_acceptance(self, mock_confirm, mock_asyncio_run, mock_orchestrator):
        """Test user accepting destructive operations."""
        # Create config with destructive operations
        config_data = {
            'target_directory': str(self.temp_path),
            'auto_format': True,
            'dry_run': False
        }
        config_file = self.temp_path / 'destructive-config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Mock user accepting destructive operations
        mock_confirm.return_value = True
        
        # Mock orchestrator results
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = Mock()
        mock_asyncio_run.return_value = mock_results
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--config', str(config_file),
            '--interactive'
        ])
        
        assert result.exit_code == 0
        assert 'Destructive Operations Detected' in result.output
        mock_confirm.assert_called_once()
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_non_interactive_mode_skips_confirmations(self, mock_asyncio_run, mock_orchestrator):
        """Test that non-interactive mode skips user confirmations."""
        # Create config with destructive operations
        config_data = {
            'target_directory': str(self.temp_path),
            'auto_format': True,
            'dry_run': False
        }
        config_file = self.temp_path / 'destructive-config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Mock orchestrator results
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = Mock()
        mock_asyncio_run.return_value = mock_results
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--config', str(config_file),
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        # Should not show destructive operations warning in non-interactive mode
        assert 'Destructive Operations Detected' not in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main._run_checkup_with_progress')
    def test_progress_display_modes(self, mock_progress_runner, mock_orchestrator):
        """Test different progress display modes."""
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        mock_progress_runner.return_value = asyncio.create_task(asyncio.coroutine(lambda: mock_results)())
        
        # Test verbose mode
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--verbose',
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        mock_progress_runner.assert_called()
        call_args = mock_progress_runner.call_args[0]
        assert call_args[1] == 'detailed'  # progress_display mode
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main._run_checkup_with_progress')
    def test_quiet_mode_progress(self, mock_progress_runner, mock_orchestrator):
        """Test quiet mode progress display."""
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        mock_progress_runner.return_value = asyncio.create_task(asyncio.coroutine(lambda: mock_results)())
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--quiet',
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        mock_progress_runner.assert_called()
        call_args = mock_progress_runner.call_args[0]
        assert call_args[1] == 'none'  # progress_display mode
    
    @patch('migration_assistant.cli.main.Prompt.ask')
    @patch('migration_assistant.cli.main.Confirm.ask')
    def test_interactive_configuration_flow(self, mock_confirm, mock_prompt):
        """Test interactive configuration with various user inputs."""
        # Mock user inputs for comprehensive configuration
        mock_prompt.side_effect = [
            str(self.temp_path),  # target_dir
            str(self.temp_path / 'reports')  # output_dir
        ]
        
        # Mock confirmation responses
        mock_confirm.side_effect = [
            True, False, True, False,  # Analysis options (mixed)
            True, False, True,         # Cleanup options (mixed)
            True, False, True          # Report options (mixed)
        ]
        
        config_file = self.temp_path / 'interactive-test-config.yaml'
        
        result = self.runner.invoke(main, [
            'checkup', 'configure',
            '--config', str(config_file),
            '--interactive'
        ])
        
        assert result.exit_code == 0
        assert 'Configuration saved' in result.output
        assert config_file.exists()
        
        # Verify mixed configuration was saved correctly
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert config_data['enable_quality_analysis'] is True
        assert config_data['enable_duplicate_detection'] is False
        assert config_data['enable_import_analysis'] is True
        assert config_data['enable_structure_analysis'] is False
    
    def test_configuration_validation_and_feedback(self):
        """Test configuration validation with user feedback."""
        # Create invalid configuration
        invalid_config = {
            'target_directory': '/nonexistent/path',
            'output_directory': '',
            'invalid_option': 'invalid_value'
        }
        config_file = self.temp_path / 'invalid-config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--config', str(config_file),
            '--non-interactive'
        ])
        
        # Should handle invalid configuration gracefully
        assert result.exit_code == 1
        assert 'Error during checkup' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_verbose_output_details(self, mock_asyncio_run, mock_orchestrator):
        """Test verbose output includes detailed information."""
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.analysis.quality_issues = [Mock(), Mock()]  # 2 issues
        mock_results.analysis.duplicates = [Mock()]  # 1 duplicate
        mock_results.analysis.import_issues = []  # No import issues
        mock_results.analysis.structure_issues = [Mock(), Mock(), Mock()]  # 3 issues
        mock_results.cleanup = None
        mock_asyncio_run.return_value = mock_results
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--verbose',
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        # Verbose mode should show configuration details
        assert 'Target directory:' in result.output
        assert 'Config file:' in result.output
        assert 'Report format:' in result.output
        assert 'Dry run:' in result.output
        assert 'Interactive:' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_results_display_with_issues(self, mock_asyncio_run, mock_orchestrator):
        """Test results display when issues are found."""
        mock_results = Mock()
        mock_results.success = False  # Has issues
        mock_results.analysis = Mock()
        mock_results.analysis.quality_issues = [Mock() for _ in range(5)]
        mock_results.analysis.duplicates = [Mock() for _ in range(3)]
        mock_results.analysis.import_issues = [Mock() for _ in range(2)]
        mock_results.analysis.structure_issues = [Mock() for _ in range(4)]
        mock_results.cleanup = Mock()
        mock_results.cleanup.formatting_changes = [Mock() for _ in range(10)]
        mock_results.cleanup.import_cleanups = [Mock() for _ in range(5)]
        mock_results.cleanup.file_moves = []
        mock_results.cleanup.removals = [Mock()]
        mock_asyncio_run.return_value = mock_results
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--non-interactive'
        ])
        
        assert result.exit_code == 1  # Should exit with error code for issues
        assert 'Checkup completed with issues' in result.output
        # Should display issue counts in results
        assert 'Analysis Results' in result.output
        assert 'Cleanup Results' in result.output
    
    def test_help_integration_with_checkup_commands(self):
        """Test that help system integrates with checkup commands."""
        result = self.runner.invoke(main, ['help', '--command', 'checkup'])
        
        # This test verifies the help command structure includes checkup
        # The actual help content would be implemented in the help system
        assert result.exit_code == 0


class TestProgressDisplayFunctionality:
    """Test progress display functionality in isolation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_detailed_progress_display(self):
        """Test detailed progress display functionality."""
        from migration_assistant.cli.main import _run_checkup_with_progress
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.config = Mock()
        mock_orchestrator.config.dry_run = True
        
        # Mock analysis results
        mock_analysis_results = Mock()
        mock_analysis_results.quality_issues = []
        mock_analysis_results.duplicates = []
        mock_analysis_results.import_issues = []
        mock_analysis_results.structure_issues = []
        
        mock_orchestrator.run_analysis_only = AsyncMock(return_value=mock_analysis_results)
        mock_orchestrator.run_full_checkup = AsyncMock(return_value=Mock(success=True))
        
        # Test detailed progress
        result = await _run_checkup_with_progress(mock_orchestrator, 'detailed', False)
        
        assert result is not None
        assert result.success is True
        mock_orchestrator.run_full_checkup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detailed_progress_with_interactive_cleanup_confirmation(self):
        """Test detailed progress with interactive cleanup confirmation."""
        from migration_assistant.cli.main import _run_checkup_with_progress
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.config = Mock()
        mock_orchestrator.config.dry_run = False
        
        # Mock analysis results with issues
        mock_analysis_results = Mock()
        mock_analysis_results.quality_issues = [Mock(), Mock()]  # 2 issues
        mock_analysis_results.duplicates = [Mock()]  # 1 duplicate
        mock_analysis_results.import_issues = [Mock()]  # 1 import issue
        mock_analysis_results.structure_issues = []
        
        mock_orchestrator.run_analysis_only = AsyncMock(return_value=mock_analysis_results)
        mock_orchestrator.run_full_checkup = AsyncMock(return_value=Mock(success=True))
        
        # Mock user confirming cleanup
        with patch('migration_assistant.cli.main.Confirm.ask', return_value=True):
            result = await _run_checkup_with_progress(mock_orchestrator, 'detailed', True)
        
        assert result is not None
        assert result.success is True
        mock_orchestrator.run_full_checkup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detailed_progress_with_cleanup_declined(self):
        """Test detailed progress when user declines cleanup."""
        from migration_assistant.cli.main import _run_checkup_with_progress
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.config = Mock()
        mock_orchestrator.config.dry_run = False
        
        # Mock analysis results with issues
        mock_analysis_results = Mock()
        mock_analysis_results.quality_issues = [Mock(), Mock()]
        mock_analysis_results.duplicates = []
        mock_analysis_results.import_issues = [Mock()]
        mock_analysis_results.structure_issues = []
        
        mock_orchestrator.run_analysis_only = AsyncMock(return_value=mock_analysis_results)
        mock_orchestrator.run_full_checkup = AsyncMock(return_value=Mock(success=True))
        
        # Mock user declining cleanup
        with patch('migration_assistant.cli.main.Confirm.ask', return_value=False):
            result = await _run_checkup_with_progress(mock_orchestrator, 'detailed', True)
        
        assert result is not None
        assert result.success is True
        mock_orchestrator.run_full_checkup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_normal_progress_display(self):
        """Test normal progress display functionality."""
        from migration_assistant.cli.main import _run_checkup_with_progress
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.run_full_checkup = AsyncMock(return_value=Mock(success=True))
        
        # Test normal progress
        result = await _run_checkup_with_progress(mock_orchestrator, 'normal', False)
        
        assert result is not None
        assert result.success is True
        mock_orchestrator.run_full_checkup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_quiet_progress_display(self):
        """Test quiet progress display functionality."""
        from migration_assistant.cli.main import _run_checkup_with_progress
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.run_full_checkup = AsyncMock(return_value=Mock(success=True))
        
        # Test quiet progress
        result = await _run_checkup_with_progress(mock_orchestrator, 'none', False)
        
        assert result is not None
        assert result.success is True
        mock_orchestrator.run_full_checkup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_progress_display_with_exception_handling(self):
        """Test progress display handles exceptions gracefully."""
        from migration_assistant.cli.main import _run_checkup_with_progress
        
        # Mock orchestrator that raises exception
        mock_orchestrator = Mock()
        mock_orchestrator.run_full_checkup = AsyncMock(side_effect=Exception("Test error"))
        
        # Should propagate the exception
        with pytest.raises(Exception, match="Test error"):
            await _run_checkup_with_progress(mock_orchestrator, 'normal', False)
    
    def test_has_cleanup_actions_detection(self):
        """Test detection of available cleanup actions."""
        from migration_assistant.cli.main import _has_cleanup_actions
        
        # Test with no issues
        mock_results_no_issues = Mock()
        mock_results_no_issues.quality_issues = []
        mock_results_no_issues.import_issues = []
        mock_results_no_issues.structure_issues = []
        
        assert not _has_cleanup_actions(mock_results_no_issues)
        
        # Test with quality issues
        mock_results_with_quality = Mock()
        mock_results_with_quality.quality_issues = [Mock(), Mock()]
        mock_results_with_quality.import_issues = []
        mock_results_with_quality.structure_issues = []
        
        assert _has_cleanup_actions(mock_results_with_quality)
        
        # Test with import issues
        mock_results_with_imports = Mock()
        mock_results_with_imports.quality_issues = []
        mock_results_with_imports.import_issues = [Mock()]
        mock_results_with_imports.structure_issues = []
        
        assert _has_cleanup_actions(mock_results_with_imports)
        
        # Test with structure issues
        mock_results_with_structure = Mock()
        mock_results_with_structure.quality_issues = []
        mock_results_with_structure.import_issues = []
        mock_results_with_structure.structure_issues = [Mock(), Mock(), Mock()]
        
        assert _has_cleanup_actions(mock_results_with_structure)
        
        # Test with None results
        assert not _has_cleanup_actions(None)
    
    def test_analysis_summary_display_for_confirmation(self):
        """Test analysis summary display for user confirmation."""
        from migration_assistant.cli.main import _display_analysis_summary_for_confirmation
        
        # Mock analysis results
        mock_results = Mock()
        mock_results.quality_issues = [Mock() for _ in range(5)]
        mock_results.duplicates = [Mock() for _ in range(2)]
        mock_results.import_issues = [Mock()]
        mock_results.structure_issues = []
        
        # Should not raise exception
        _display_analysis_summary_for_confirmation(mock_results)
        
        # Test with empty results
        mock_empty_results = Mock()
        mock_empty_results.quality_issues = []
        mock_empty_results.duplicates = []
        mock_empty_results.import_issues = []
        mock_empty_results.structure_issues = []
        
        _display_analysis_summary_for_confirmation(mock_empty_results)


class TestDestructiveOperationHandling:
    """Test destructive operation detection and confirmation."""
    
    def test_destructive_operation_detection(self):
        """Test detection of destructive operations in configuration."""
        from migration_assistant.cli.main import _check_destructive_operations
        
        # Mock config with destructive operations
        config = Mock()
        config.auto_format = True
        config.auto_fix_imports = True
        config.auto_organize_files = True
        
        destructive_ops = _check_destructive_operations(config)
        
        assert len(destructive_ops) == 3
        assert any(op['name'] == 'Automatic Code Formatting' for op in destructive_ops)
        assert any(op['name'] == 'Automatic Import Cleanup' for op in destructive_ops)
        assert any(op['name'] == 'Automatic File Organization' for op in destructive_ops)
        
        # Check severity levels
        file_org_op = next(op for op in destructive_ops if op['name'] == 'Automatic File Organization')
        assert file_org_op['severity'] == 'high'
        
        format_op = next(op for op in destructive_ops if op['name'] == 'Automatic Code Formatting')
        assert format_op['severity'] == 'medium'
        
        import_op = next(op for op in destructive_ops if op['name'] == 'Automatic Import Cleanup')
        assert import_op['severity'] == 'low'
    
    def test_no_destructive_operations(self):
        """Test when no destructive operations are configured."""
        from migration_assistant.cli.main import _check_destructive_operations
        
        # Mock config with no destructive operations
        config = Mock()
        config.auto_format = False
        config.auto_fix_imports = False
        config.auto_organize_files = False
        
        destructive_ops = _check_destructive_operations(config)
        
        assert len(destructive_ops) == 0
    
    def test_partial_destructive_operations(self):
        """Test detection of partial destructive operations."""
        from migration_assistant.cli.main import _check_destructive_operations
        
        # Mock config with only some destructive operations
        config = Mock()
        config.auto_format = True
        config.auto_fix_imports = False
        config.auto_organize_files = True
        
        destructive_ops = _check_destructive_operations(config)
        
        assert len(destructive_ops) == 2
        assert any(op['name'] == 'Automatic Code Formatting' for op in destructive_ops)
        assert any(op['name'] == 'Automatic File Organization' for op in destructive_ops)
        assert not any(op['name'] == 'Automatic Import Cleanup' for op in destructive_ops)
    
    def test_destructive_operation_confirmation_acceptance(self):
        """Test user accepting destructive operations."""
        from migration_assistant.cli.main import _confirm_destructive_operations
        
        destructive_ops = [
            {
                'name': 'Test Operation',
                'description': 'Test description',
                'details': ['Detail 1', 'Detail 2'],
                'severity': 'medium'
            }
        ]
        
        with patch('migration_assistant.cli.main.Confirm.ask', return_value=True):
            result = _confirm_destructive_operations(destructive_ops)
            assert result is True
    
    def test_destructive_operation_confirmation_decline(self):
        """Test user declining destructive operations."""
        from migration_assistant.cli.main import _confirm_destructive_operations
        
        destructive_ops = [
            {
                'name': 'Test Operation',
                'description': 'Test description',
                'details': ['Detail 1', 'Detail 2'],
                'severity': 'high'
            }
        ]
        
        with patch('migration_assistant.cli.main.Confirm.ask', return_value=False):
            result = _confirm_destructive_operations(destructive_ops)
            assert result is False
    
    def test_destructive_operation_confirmation_with_high_severity(self):
        """Test confirmation display for high-severity operations."""
        from migration_assistant.cli.main import _confirm_destructive_operations
        
        destructive_ops = [
            {
                'name': 'High Risk Operation',
                'description': 'This will make significant changes',
                'details': ['Change 1', 'Change 2', 'Change 3', 'Change 4', 'Change 5'],
                'severity': 'high'
            },
            {
                'name': 'Low Risk Operation',
                'description': 'This is safer',
                'details': ['Safe change'],
                'severity': 'low'
            }
        ]
        
        with patch('migration_assistant.cli.main.Confirm.ask', return_value=False):
            result = _confirm_destructive_operations(destructive_ops)
            assert result is False
    
    def test_destructive_operation_confirmation_with_many_details(self):
        """Test confirmation display with many operation details."""
        from migration_assistant.cli.main import _confirm_destructive_operations
        
        # Create operation with many details (should truncate display)
        many_details = [f'Detail {i}' for i in range(10)]
        destructive_ops = [
            {
                'name': 'Operation with Many Details',
                'description': 'Has many details',
                'details': many_details,
                'severity': 'medium'
            }
        ]
        
        with patch('migration_assistant.cli.main.Confirm.ask', return_value=True):
            result = _confirm_destructive_operations(destructive_ops)
            assert result is True


class TestVerboseAndQuietModes:
    """Test verbose and quiet mode functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main._run_checkup_with_progress')
    def test_verbose_mode_progress_display(self, mock_progress_runner, mock_orchestrator):
        """Test verbose mode uses detailed progress display."""
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        
        # Mock async coroutine properly
        async def mock_progress_coro(*args):
            return mock_results
        
        mock_progress_runner.return_value = mock_progress_coro(None, None, None)
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--verbose',
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        mock_progress_runner.assert_called_once()
        
        # Verify detailed progress mode was used
        call_args = mock_progress_runner.call_args[0]
        assert call_args[1] == 'detailed'  # progress_display mode
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main._run_checkup_with_progress')
    def test_quiet_mode_progress_display(self, mock_progress_runner, mock_orchestrator):
        """Test quiet mode uses minimal progress display."""
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        
        # Mock async coroutine properly
        async def mock_progress_coro(*args):
            return mock_results
        
        mock_progress_runner.return_value = mock_progress_coro(None, None, None)
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--quiet',
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        mock_progress_runner.assert_called_once()
        
        # Verify quiet progress mode was used
        call_args = mock_progress_runner.call_args[0]
        assert call_args[1] == 'none'  # progress_display mode
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main._run_checkup_with_progress')
    def test_normal_mode_progress_display(self, mock_progress_runner, mock_orchestrator):
        """Test normal mode uses standard progress display."""
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        
        # Mock async coroutine properly
        async def mock_progress_coro(*args):
            return mock_results
        
        mock_progress_runner.return_value = mock_progress_coro(None, None, None)
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        mock_progress_runner.assert_called_once()
        
        # Verify normal progress mode was used
        call_args = mock_progress_runner.call_args[0]
        assert call_args[1] == 'normal'  # progress_display mode
    
    def test_verbose_mode_info_display(self):
        """Test verbose mode information display."""
        from migration_assistant.cli.main import _show_verbose_mode_info
        
        # Should not raise exception
        _show_verbose_mode_info()
    
    def test_quiet_mode_info_display(self):
        """Test quiet mode information display."""
        from migration_assistant.cli.main import _show_quiet_mode_info
        
        # Should not raise exception
        _show_quiet_mode_info()


class TestResultsDisplayFunctionality:
    """Test results display functionality."""
    
    def test_display_checkup_results_with_all_data(self):
        """Test displaying complete checkup results."""
        from migration_assistant.cli.main import _display_checkup_results
        
        # Mock complete results
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.analysis.quality_issues = [Mock() for _ in range(5)]
        mock_results.analysis.duplicates = [Mock() for _ in range(2)]
        mock_results.analysis.import_issues = [Mock()]
        mock_results.analysis.structure_issues = [Mock() for _ in range(3)]
        
        mock_results.cleanup = Mock()
        mock_results.cleanup.formatting_changes = [Mock() for _ in range(10)]
        mock_results.cleanup.import_cleanups = [Mock() for _ in range(3)]
        mock_results.cleanup.file_moves = [Mock()]
        mock_results.cleanup.removals = []
        
        mock_results.duration = "2m 30s"
        
        # Should not raise exception
        _display_checkup_results(mock_results, verbose=False, quiet=False)
        _display_checkup_results(mock_results, verbose=True, quiet=False)
    
    def test_display_checkup_results_quiet_mode(self):
        """Test displaying results in quiet mode."""
        from migration_assistant.cli.main import _display_checkup_results
        
        mock_results = Mock()
        mock_results.success = True
        
        # Quiet mode should not display anything
        _display_checkup_results(mock_results, verbose=False, quiet=True)
    
    def test_display_checkup_results_with_no_cleanup(self):
        """Test displaying results when no cleanup was performed."""
        from migration_assistant.cli.main import _display_checkup_results
        
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.analysis.quality_issues = []
        mock_results.analysis.duplicates = []
        mock_results.analysis.import_issues = []
        mock_results.analysis.structure_issues = []
        mock_results.cleanup = None  # No cleanup performed
        
        _display_checkup_results(mock_results, verbose=False, quiet=False)
    
    def test_display_analysis_results(self):
        """Test displaying analysis-only results."""
        from migration_assistant.cli.main import _display_analysis_results
        
        mock_results = Mock()
        mock_results.quality_issues = [Mock() for _ in range(3)]
        mock_results.duplicates = [Mock()]
        mock_results.import_issues = [Mock() for _ in range(2)]
        mock_results.structure_issues = []
        
        # Should not raise exception
        _display_analysis_results(mock_results, verbose=False)
        _display_analysis_results(mock_results, verbose=True)
    
    def test_display_detailed_issues(self):
        """Test displaying detailed issue breakdown."""
        from migration_assistant.cli.main import _display_detailed_issues
        
        # Mock analysis results with detailed issues
        mock_results = Mock()
        
        # Mock quality issues with file and message attributes
        quality_issue_1 = Mock()
        quality_issue_1.file = "test_file1.py"
        quality_issue_1.message = "Line too long"
        
        quality_issue_2 = Mock()
        quality_issue_2.file = "test_file2.py"
        quality_issue_2.message = "Missing docstring"
        
        mock_results.quality_issues = [quality_issue_1, quality_issue_2]
        
        # Mock duplicates with description
        duplicate_1 = Mock()
        duplicate_1.description = "Duplicate function in module A and B"
        
        mock_results.duplicates = [duplicate_1]
        
        # Should not raise exception
        _display_detailed_issues(mock_results)
    
    def test_display_detailed_issues_with_many_issues(self):
        """Test displaying detailed issues when there are many issues."""
        from migration_assistant.cli.main import _display_detailed_issues
        
        mock_results = Mock()
        
        # Create many quality issues (should truncate display)
        quality_issues = []
        for i in range(10):
            issue = Mock()
            issue.file = f"test_file{i}.py"
            issue.message = f"Issue {i}"
            quality_issues.append(issue)
        
        mock_results.quality_issues = quality_issues
        
        # Create many duplicates (should truncate display)
        duplicates = []
        for i in range(5):
            duplicate = Mock()
            duplicate.description = f"Duplicate {i}"
            duplicates.append(duplicate)
        
        mock_results.duplicates = duplicates
        
        # Should not raise exception and should handle truncation
        _display_detailed_issues(mock_results)


class TestInteractiveConfigurationFlow:
    """Test interactive configuration functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_interactive_configuration_full_flow(self):
        """Test complete interactive configuration flow."""
        from migration_assistant.cli.main import _interactive_configuration
        
        config_file = self.temp_path / 'interactive-config.yaml'
        
        # Mock all user inputs
        with patch('migration_assistant.cli.main.Prompt.ask') as mock_prompt:
            with patch('migration_assistant.cli.main.Confirm.ask') as mock_confirm:
                # Mock prompt responses
                mock_prompt.side_effect = [
                    str(self.temp_path),  # target_dir
                    str(self.temp_path / 'reports')  # output_dir
                ]
                
                # Mock confirmation responses
                mock_confirm.side_effect = [
                    True, False, True, False,  # Analysis options
                    True, False, True,         # Cleanup options
                    True, True, False          # Report options
                ]
                
                _interactive_configuration(str(config_file))
        
        # Verify config file was created
        assert config_file.exists()
        
        # Verify config content
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert config_data['target_directory'] == str(self.temp_path)
        assert config_data['enable_quality_analysis'] is True
        assert config_data['enable_duplicate_detection'] is False
        assert config_data['auto_format'] is True
        assert config_data['auto_fix_imports'] is False
        assert config_data['generate_html_report'] is True
        assert config_data['generate_json_report'] is True
        assert config_data['generate_markdown_report'] is False
    
    def test_create_default_configuration(self):
        """Test creating default configuration."""
        from migration_assistant.cli.main import _create_default_configuration
        
        config_file = self.temp_path / 'default-config.yaml'
        
        _create_default_configuration(str(config_file))
        
        # Verify config file was created
        assert config_file.exists()
        
        # Verify default config content
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Check required default values
        assert config_data['target_directory'] == '.'
        assert config_data['enable_quality_analysis'] is True
        assert config_data['enable_duplicate_detection'] is True
        assert config_data['auto_format'] is False
        assert config_data['create_backup'] is True
        assert config_data['dry_run'] is False
        assert config_data['max_file_moves'] == 10
    
    def test_create_default_configuration_without_filename(self):
        """Test creating default configuration without specifying filename."""
        from migration_assistant.cli.main import _create_default_configuration
        
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(self.temp_path)
        
        try:
            _create_default_configuration(None)
            
            # Should create checkup-config.yaml in current directory
            default_config_file = self.temp_path / 'checkup-config.yaml'
            assert default_config_file.exists()
        finally:
            os.chdir(original_cwd)


if __name__ == '__main__':
    pytest.main([__file__])