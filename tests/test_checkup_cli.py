"""
Unit tests for checkup CLI commands.

Tests the command-line interface for codebase checkup functionality.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import yaml

from migration_assistant.cli.main import main


class TestCheckupCLI:
    """Test cases for checkup CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_checkup_help(self):
        """Test checkup help command."""
        result = self.runner.invoke(main, ['checkup', '--help'])
        assert result.exit_code == 0
        assert 'Codebase checkup and cleanup commands' in result.output
    
    def test_checkup_run_help(self):
        """Test checkup run help command."""
        result = self.runner.invoke(main, ['checkup', 'run', '--help'])
        assert result.exit_code == 0
        assert 'Run comprehensive codebase checkup and cleanup' in result.output
        assert '--config' in result.output
        assert '--target' in result.output
        assert '--dry-run' in result.output
        assert '--interactive' in result.output
    
    def test_checkup_analyze_help(self):
        """Test checkup analyze help command."""
        result = self.runner.invoke(main, ['checkup', 'analyze', '--help'])
        assert result.exit_code == 0
        assert 'Run analysis only without cleanup' in result.output
        assert '--target' in result.output
        assert '--format' in result.output
    
    def test_checkup_configure_help(self):
        """Test checkup configure help command."""
        result = self.runner.invoke(main, ['checkup', 'configure', '--help'])
        assert result.exit_code == 0
        assert 'Create or modify checkup configuration' in result.output
        assert '--interactive' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_checkup_run_with_defaults(self, mock_asyncio_run, mock_orchestrator):
        """Test checkup run with default parameters."""
        # Mock the orchestrator and results
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        mock_asyncio_run.return_value = mock_results
        
        mock_orchestrator_instance = Mock()
        mock_orchestrator.return_value = mock_orchestrator_instance
        
        result = self.runner.invoke(main, ['checkup', 'run', '--non-interactive'])
        
        assert result.exit_code == 0
        assert 'Starting codebase checkup' in result.output
        assert 'Checkup completed successfully' in result.output
        mock_orchestrator.assert_called_once()
        mock_asyncio_run.assert_called_once()
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_checkup_run_with_config_file(self, mock_asyncio_run, mock_orchestrator):
        """Test checkup run with configuration file."""
        # Create a test config file
        config_data = {
            'target_directory': str(self.temp_path),
            'output_directory': str(self.temp_path / 'reports'),
            'dry_run': True,
            'generate_html_report': True
        }
        config_file = self.temp_path / 'test-config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Mock the orchestrator and results
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        mock_asyncio_run.return_value = mock_results
        
        mock_orchestrator_instance = Mock()
        mock_orchestrator.return_value = mock_orchestrator_instance
        
        result = self.runner.invoke(main, [
            'checkup', 'run', 
            '--config', str(config_file),
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        mock_orchestrator.assert_called_once()
        
        # Verify config was loaded
        call_args = mock_orchestrator.call_args[0][0]
        assert call_args.target_directory == Path(str(self.temp_path))
    
    def test_checkup_run_invalid_config(self):
        """Test checkup run with invalid configuration file."""
        invalid_config = self.temp_path / 'invalid.yaml'
        invalid_config.write_text('invalid: yaml: content: [')
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--config', str(invalid_config),
            '--non-interactive'
        ])
        
        assert result.exit_code == 1
        assert 'Error during checkup' in result.output
    
    def test_checkup_run_conflicting_options(self):
        """Test checkup run with conflicting options."""
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--verbose',
            '--quiet',
            '--non-interactive'
        ])
        
        assert result.exit_code == 1
        assert 'Cannot use both --quiet and --verbose' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_checkup_run_verbose_output(self, mock_asyncio_run, mock_orchestrator):
        """Test checkup run with verbose output."""
        mock_results = Mock()
        mock_results.success = True
        mock_results.analysis = Mock()
        mock_results.analysis.quality_issues = []
        mock_results.analysis.duplicates = []
        mock_results.analysis.import_issues = []
        mock_results.analysis.structure_issues = []
        mock_results.cleanup = None
        mock_asyncio_run.return_value = mock_results
        
        mock_orchestrator_instance = Mock()
        mock_orchestrator.return_value = mock_orchestrator_instance
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--verbose',
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        assert 'Target directory:' in result.output
        assert 'Config file:' in result.output
        assert 'Report format:' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_checkup_analyze_command(self, mock_asyncio_run, mock_orchestrator):
        """Test checkup analyze command."""
        mock_results = Mock()
        mock_results.quality_issues = []
        mock_results.duplicates = []
        mock_results.import_issues = []
        mock_results.structure_issues = []
        mock_asyncio_run.return_value = mock_results
        
        mock_orchestrator_instance = Mock()
        mock_orchestrator.return_value = mock_orchestrator_instance
        
        result = self.runner.invoke(main, ['checkup', 'analyze'])
        
        assert result.exit_code == 0
        assert 'Running codebase analysis' in result.output
        assert 'Analysis completed' in result.output
        mock_orchestrator.assert_called_once()
        
        # Verify analysis-only configuration
        call_args = mock_orchestrator.call_args[0][0]
        assert call_args.dry_run is True
    
    def test_checkup_configure_non_interactive(self):
        """Test checkup configure in non-interactive mode."""
        config_file = self.temp_path / 'generated-config.yaml'
        
        result = self.runner.invoke(main, [
            'checkup', 'configure',
            '--config', str(config_file),
            '--non-interactive'
        ])
        
        assert result.exit_code == 0
        assert 'Default configuration created' in result.output
        assert config_file.exists()
        
        # Verify config content
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert 'target_directory' in config_data
        assert 'enable_quality_analysis' in config_data
        assert config_data['enable_quality_analysis'] is True
    
    @patch('migration_assistant.cli.main.Prompt.ask')
    @patch('migration_assistant.cli.main.Confirm.ask')
    def test_checkup_configure_interactive(self, mock_confirm, mock_prompt):
        """Test checkup configure in interactive mode."""
        # Mock user inputs
        mock_prompt.side_effect = ['.', './reports']  # target_dir, output_dir
        mock_confirm.side_effect = [
            True, True, True, True,  # Analysis options
            False, False, False,     # Cleanup options
            True, True, False        # Report options
        ]
        
        config_file = self.temp_path / 'interactive-config.yaml'
        
        result = self.runner.invoke(main, [
            'checkup', 'configure',
            '--config', str(config_file),
            '--interactive'
        ], input='\n')
        
        assert result.exit_code == 0
        assert 'Configuration saved' in result.output
        assert config_file.exists()
        
        # Verify config content
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert config_data['enable_quality_analysis'] is True
        assert config_data['auto_format'] is False
        assert config_data['generate_html_report'] is True
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_checkup_run_with_failed_results(self, mock_asyncio_run, mock_orchestrator):
        """Test checkup run with failed results."""
        mock_results = Mock()
        mock_results.success = False
        mock_results.analysis = Mock()
        mock_results.cleanup = None
        mock_asyncio_run.return_value = mock_results
        
        mock_orchestrator_instance = Mock()
        mock_orchestrator.return_value = mock_orchestrator_instance
        
        result = self.runner.invoke(main, ['checkup', 'run', '--non-interactive'])
        
        assert result.exit_code == 1
        assert 'Checkup completed with issues' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_checkup_run_keyboard_interrupt(self, mock_asyncio_run, mock_orchestrator):
        """Test checkup run with keyboard interrupt."""
        mock_asyncio_run.side_effect = KeyboardInterrupt()
        
        result = self.runner.invoke(main, ['checkup', 'run', '--non-interactive'])
        
        assert result.exit_code == 1
        assert 'Checkup cancelled by user' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_checkup_run_exception_handling(self, mock_asyncio_run, mock_orchestrator):
        """Test checkup run with exception handling."""
        mock_asyncio_run.side_effect = Exception("Test error")
        
        result = self.runner.invoke(main, ['checkup', 'run', '--non-interactive'])
        
        assert result.exit_code == 1
        assert 'Error during checkup: Test error' in result.output
    
    def test_checkup_run_format_options(self):
        """Test checkup run with different format options."""
        formats = ['html', 'json', 'markdown', 'all']
        
        for fmt in formats:
            with patch('migration_assistant.cli.main.CodebaseOrchestrator') as mock_orchestrator:
                with patch('migration_assistant.cli.main.asyncio.run') as mock_asyncio_run:
                    mock_results = Mock()
                    mock_results.success = True
                    mock_results.analysis = Mock()
                    mock_results.cleanup = None
                    mock_asyncio_run.return_value = mock_results
                    
                    result = self.runner.invoke(main, [
                        'checkup', 'run',
                        '--format', fmt,
                        '--non-interactive'
                    ])
                    
                    assert result.exit_code == 0
                    
                    # Verify format configuration
                    call_args = mock_orchestrator.call_args[0][0]
                    if fmt == 'html' or fmt == 'all':
                        assert call_args.generate_html_report is True
                    if fmt == 'json' or fmt == 'all':
                        assert call_args.generate_json_report is True
                    if fmt == 'markdown' or fmt == 'all':
                        assert call_args.generate_markdown_report is True


class TestCheckupCLIIntegration:
    """Integration tests for checkup CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_help_command_includes_checkup(self):
        """Test that main help includes checkup commands."""
        result = self.runner.invoke(main, ['help', '--command', 'checkup'])
        assert result.exit_code == 0
        # This would be implemented when help system is extended
    
    def test_checkup_command_structure(self):
        """Test that checkup command structure is properly set up."""
        result = self.runner.invoke(main, ['checkup'])
        assert result.exit_code == 0
        assert 'Usage:' in result.output
        assert 'Commands:' in result.output
        assert 'run' in result.output
        assert 'analyze' in result.output
        assert 'configure' in result.output


class TestCheckupCLIArgumentParsing:
    """Test argument parsing for checkup CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
    
    def test_checkup_run_argument_validation(self):
        """Test argument validation for checkup run command."""
        # Test invalid target directory
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--target', '/nonexistent/directory',
            '--non-interactive'
        ])
        assert result.exit_code == 2  # Click validation error
        assert 'does not exist' in result.output
    
    def test_checkup_run_format_validation(self):
        """Test format argument validation."""
        # Test invalid format
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--format', 'invalid_format',
            '--non-interactive'
        ])
        assert result.exit_code == 2  # Click validation error
        assert 'Invalid value' in result.output
    
    def test_checkup_analyze_format_validation(self):
        """Test format validation for analyze command."""
        result = self.runner.invoke(main, [
            'checkup', 'analyze',
            '--format', 'xml'  # Invalid format
        ])
        assert result.exit_code == 2
        assert 'Invalid value' in result.output


if __name__ == '__main__':
    pytest.main([__file__])