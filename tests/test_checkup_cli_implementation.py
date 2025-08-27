"""
Unit tests for checkup CLI command structure implementation.

Tests the CLI argument parsing, command structure, and configuration handling.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import yaml
import os

from migration_assistant.cli.main import main


class TestCheckupCLICommandStructure:
    """Test cases for CLI command structure."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_main_cli_entry_point(self):
        """Test main CLI entry point includes checkup commands."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'checkup' in result.output
    
    def test_checkup_group_structure(self):
        """Test checkup command group structure."""
        result = self.runner.invoke(main, ['checkup', '--help'])
        assert result.exit_code == 0
        assert 'Codebase checkup and cleanup commands' in result.output
        
        # Verify all subcommands are present
        assert 'run' in result.output
        assert 'analyze' in result.output
        assert 'configure' in result.output
    
    def test_checkup_run_command_options(self):
        """Test checkup run command has all required options."""
        result = self.runner.invoke(main, ['checkup', 'run', '--help'])
        assert result.exit_code == 0
        
        # Verify all required options are present
        required_options = [
            '--config', '--target', '--output', '--format',
            '--dry-run', '--interactive', '--verbose', '--quiet'
        ]
        for option in required_options:
            assert option in result.output
        
        # Verify format choices
        assert 'html|json|markdown|all' in result.output
    
    def test_checkup_analyze_command_options(self):
        """Test checkup analyze command has required options."""
        result = self.runner.invoke(main, ['checkup', 'analyze', '--help'])
        assert result.exit_code == 0
        
        required_options = ['--target', '--output', '--format', '--verbose']
        for option in required_options:
            assert option in result.output
    
    def test_checkup_configure_command_options(self):
        """Test checkup configure command has required options."""
        result = self.runner.invoke(main, ['checkup', 'configure', '--help'])
        assert result.exit_code == 0
        
        required_options = ['--config', '--interactive']
        for option in required_options:
            assert option in result.output


class TestCheckupCLIArgumentParsing:
    """Test CLI argument parsing and validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_format_argument_validation(self):
        """Test format argument validation."""
        # Valid formats should not cause validation errors
        valid_formats = ['html', 'json', 'markdown', 'all']
        
        for fmt in valid_formats:
            with patch('migration_assistant.cli.main.CodebaseOrchestrator'):
                with patch('migration_assistant.cli.main.asyncio.run'):
                    result = self.runner.invoke(main, [
                        'checkup', 'run',
                        '--format', fmt,
                        '--non-interactive'
                    ])
                    # Should not fail due to format validation
                    assert result.exit_code != 2
    
    def test_invalid_format_argument(self):
        """Test invalid format argument."""
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--format', 'invalid_format',
            '--non-interactive'
        ])
        assert result.exit_code == 2  # Click validation error
        assert 'Invalid value' in result.output
    
    def test_conflicting_verbose_quiet_options(self):
        """Test conflicting verbose and quiet options."""
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--verbose',
            '--quiet',
            '--non-interactive'
        ])
        assert result.exit_code == 1
        assert 'Cannot use both --quiet and --verbose' in result.output
    
    def test_target_directory_validation(self):
        """Test target directory validation."""
        # Non-existent directory should cause validation error
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--target', '/nonexistent/directory',
            '--non-interactive'
        ])
        assert result.exit_code == 2  # Click validation error
        assert 'does not exist' in result.output
    
    def test_config_file_validation(self):
        """Test config file validation."""
        # Non-existent config file should cause validation error
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--config', '/nonexistent/config.yaml',
            '--non-interactive'
        ])
        assert result.exit_code == 2  # Click validation error
        assert 'does not exist' in result.output


class TestCheckupCLIConfiguration:
    """Test CLI configuration handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_non_interactive_configuration_creation(self):
        """Test non-interactive configuration creation."""
        config_file = self.temp_path / 'test-config.yaml'
        
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
        
        # Check required configuration keys
        required_keys = [
            'target_directory', 'enable_quality_analysis',
            'enable_duplicate_detection', 'enable_import_analysis',
            'enable_structure_analysis', 'generate_html_report'
        ]
        for key in required_keys:
            assert key in config_data
    
    def test_interactive_configuration_creation(self):
        """Test interactive configuration creation."""
        config_file = self.temp_path / 'interactive-config.yaml'
        
        # Simulate user inputs
        user_inputs = '\n'.join([
            '.',  # target directory
            './reports',  # output directory
            'y', 'y', 'y', 'y',  # analysis options
            'n', 'n', 'n',  # cleanup options
            'y', 'n', 'y'   # report options
        ])
        
        result = self.runner.invoke(main, [
            'checkup', 'configure',
            '--config', str(config_file),
            '--interactive'
        ], input=user_inputs)
        
        assert result.exit_code == 0
        assert 'Configuration saved' in result.output
        assert config_file.exists()
        
        # Verify config content matches user inputs
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert config_data['enable_quality_analysis'] is True
        assert config_data['auto_format'] is False
        assert config_data['generate_html_report'] is True
        assert config_data['generate_json_report'] is False
        assert config_data['generate_markdown_report'] is True
    
    def test_configuration_file_loading(self):
        """Test loading configuration from file."""
        # Create a test config file
        config_data = {
            'target_directory': str(self.temp_path),
            'enable_quality_analysis': True,
            'dry_run': True,
            'generate_html_report': True
        }
        config_file = self.temp_path / 'load-test-config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        with patch('migration_assistant.cli.main.CodebaseOrchestrator') as mock_orchestrator:
            with patch('migration_assistant.cli.main.asyncio.run') as mock_asyncio_run:
                mock_results = Mock()
                mock_results.success = True
                mock_results.analysis = Mock()
                mock_results.cleanup = None
                mock_asyncio_run.return_value = mock_results
                
                result = self.runner.invoke(main, [
                    'checkup', 'run',
                    '--config', str(config_file),
                    '--non-interactive'
                ])
                
                assert result.exit_code == 0
                mock_orchestrator.assert_called_once()
                
                # Verify config was loaded correctly
                call_args = mock_orchestrator.call_args[0][0]
                assert call_args.target_directory == Path(str(self.temp_path))
                assert call_args.dry_run is True


class TestCheckupCLIInteractiveMode:
    """Test CLI interactive mode functionality."""
    
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
    def test_interactive_destructive_operations_confirmation(self, mock_confirm, mock_asyncio_run, mock_orchestrator):
        """Test interactive confirmation for destructive operations."""
        # Create config with destructive operations
        config_data = {
            'target_directory': str(self.temp_path),
            'auto_format': True,
            'auto_fix_imports': True,
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
    def test_non_interactive_mode_skips_confirmations(self, mock_asyncio_run, mock_orchestrator):
        """Test non-interactive mode skips confirmations."""
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


class TestCheckupCLIErrorHandling:
    """Test CLI error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_invalid_yaml_config_handling(self):
        """Test handling of invalid YAML configuration."""
        invalid_config = self.temp_path / 'invalid.yaml'
        invalid_config.write_text('invalid: yaml: content: [')
        
        result = self.runner.invoke(main, [
            'checkup', 'run',
            '--config', str(invalid_config),
            '--non-interactive'
        ])
        
        assert result.exit_code == 1
        assert 'Error during checkup' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_keyboard_interrupt_handling(self, mock_asyncio_run, mock_orchestrator):
        """Test keyboard interrupt handling."""
        mock_asyncio_run.side_effect = KeyboardInterrupt()
        
        result = self.runner.invoke(main, ['checkup', 'run', '--non-interactive'])
        
        assert result.exit_code == 1
        assert 'Checkup cancelled by user' in result.output
    
    @patch('migration_assistant.cli.main.CodebaseOrchestrator')
    @patch('migration_assistant.cli.main.asyncio.run')
    def test_general_exception_handling(self, mock_asyncio_run, mock_orchestrator):
        """Test general exception handling."""
        mock_asyncio_run.side_effect = Exception("Test error")
        
        result = self.runner.invoke(main, ['checkup', 'run', '--non-interactive'])
        
        assert result.exit_code == 1
        assert 'Error during checkup: Test error' in result.output
    
    def test_configuration_error_handling(self):
        """Test configuration error handling."""
        result = self.runner.invoke(main, [
            'checkup', 'configure',
            '--config', '/invalid/path/config.yaml',
            '--non-interactive'
        ])
        
        assert result.exit_code == 1
        assert 'Error during configuration' in result.output


if __name__ == '__main__':
    pytest.main([__file__])