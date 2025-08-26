"""
Tests for Migration Assistant CLI.

This module contains comprehensive unit and integration tests for the CLI interface
and command functionality, covering all commands, options, and error scenarios.
"""

import os
import json
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from migration_assistant.cli.main import main


class TestCLI:
    """Test CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_main_command_help(self):
        """Test main command shows help when no subcommand provided."""
        result = self.runner.invoke(main, [])
        assert result.exit_code == 0
        assert "Migration Assistant" in result.output
        assert "Use --help to see available commands" in result.output
        assert "migration-assistant migrate" in result.output
        assert "migration-assistant validate" in result.output
        assert "migration-assistant status" in result.output

    def test_version_flag(self):
        """Test version flag displays version information."""
        result = self.runner.invoke(main, ['--version'])
        assert result.exit_code == 0
        assert "Migration Assistant version" in result.output

    def test_help_command(self):
        """Test help command displays usage information."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "Web & Database Migration Assistant" in result.output
        assert "migrate" in result.output
        assert "validate" in result.output
        assert "status" in result.output
        assert "rollback" in result.output
        assert "configs" in result.output
        assert "presets" in result.output
        assert "serve" in result.output

    def test_verbose_flag(self):
        """Test verbose flag enables detailed output."""
        result = self.runner.invoke(main, ['--verbose', 'migrate', '--non-interactive'])
        assert result.exit_code == 0
        # Verbose output should include additional details
        assert "Config file: None" in result.output
        assert "Preset: None" in result.output
        assert "Dry run: False" in result.output
        assert "Interactive: False" in result.output


class TestMigrateCommand:
    """Test migrate command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_migrate_command_basic(self):
        """Test migrate command basic functionality."""
        result = self.runner.invoke(main, ['migrate', '--non-interactive'])
        assert result.exit_code == 0
        assert "Starting migration process" in result.output
        assert "Non-interactive mode without config file not yet supported" in result.output

    def test_migrate_command_with_options(self):
        """Test migrate command with various options."""
        result = self.runner.invoke(main, [
            '--verbose',
            'migrate',
            '--dry-run',
            '--non-interactive'
        ])
        assert result.exit_code == 0
        assert "Starting migration process" in result.output
        assert "Dry run: True" in result.output
        assert "Interactive: False" in result.output

    def test_migrate_command_with_preset(self):
        """Test migrate command with preset option."""
        with patch('migration_assistant.cli.config_collector.ConfigurationCollector') as mock_collector:
            mock_config = Mock()
            mock_config.name = "Test Migration"
            mock_collector.return_value.collect_configuration.return_value = mock_config
            
            result = self.runner.invoke(main, [
                'migrate',
                '--preset', 'wordpress-mysql',
                '--interactive'
            ], input='n\n')  # Don't save config
            
            assert result.exit_code == 0
            assert "Starting migration process" in result.output
            assert "Configuration collected successfully" in result.output

    def test_migrate_command_with_config_file(self):
        """Test migrate command with configuration file."""
        # Create a temporary config file
        config_data = {
            "name": "Test Migration",
            "source": {
                "type": "wordpress",
                "host": "source.example.com",
                "database": {
                    "type": "mysql",
                    "host": "db.example.com",
                    "username": "user",
                    "password": "pass",
                    "database": "wp_db"
                }
            },
            "destination": {
                "type": "aws-s3",
                "host": "s3.amazonaws.com"
            },
            "transfer": {
                "files": "s3_sync",
                "database": "dump_restore"
            },
            "options": {
                "maintenance_mode": True,
                "backup_before": True
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
                mock_config = Mock()
                mock_config.name = "Test Migration"
                mock_persistence.return_value.load_configuration.return_value = mock_config
                
                with patch('migration_assistant.cli.config_persistence.ConfigurationValidator') as mock_validator:
                    mock_validator.return_value.validate_configuration.return_value = {"valid": True}
                    mock_validator.return_value.display_validation_results.return_value = None
                    
                    result = self.runner.invoke(main, [
                        '--verbose',
                        'migrate',
                        '--config', config_file
                    ])
                    
                    assert result.exit_code == 0
                    assert "Configuration loaded: Test Migration" in result.output
        finally:
            os.unlink(config_file)

    def test_migrate_command_config_load_error(self):
        """Test migrate command with invalid config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            config_file = f.name
        
        try:
            result = self.runner.invoke(main, [
                'migrate',
                '--config', config_file
            ])
            
            assert result.exit_code == 1
            assert "Error loading configuration" in result.output or "Error during configuration" in result.output
        finally:
            os.unlink(config_file)

    def test_migrate_command_interactive_cancelled(self):
        """Test migrate command when user cancels interactive configuration."""
        with patch('migration_assistant.cli.config_collector.ConfigurationCollector') as mock_collector:
            mock_collector.return_value.collect_configuration.side_effect = KeyboardInterrupt()
            
            result = self.runner.invoke(main, ['migrate'])
            
            assert result.exit_code == 1
            assert "Migration cancelled by user" in result.output


class TestValidateCommand:
    """Test validate command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_validate_command_no_config(self):
        """Test validate command without config file."""
        result = self.runner.invoke(main, ['validate'])
        assert result.exit_code == 1
        assert "Configuration file path is required" in result.output

    def test_validate_command_with_config(self):
        """Test validate command with valid config file."""
        config_data = {
            "name": "Test Migration",
            "source": {"type": "wordpress", "host": "source.example.com"},
            "destination": {"type": "aws-s3", "host": "s3.amazonaws.com"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
                mock_persistence.return_value.validate_configuration_file.return_value = {"valid": True, "errors": [], "warnings": []}
                mock_config = Mock()
                mock_config.name = "Test Migration"
                mock_persistence.return_value.load_configuration.return_value = mock_config
                
                with patch('migration_assistant.cli.config_persistence.ConfigurationValidator') as mock_validator:
                    mock_validator.return_value.validate_configuration.return_value = {"valid": True}
                    mock_validator.return_value.display_validation_results.return_value = None
                    
                    result = self.runner.invoke(main, [
                        'validate',
                        '--config', config_file
                    ])
                    
                    assert result.exit_code == 0
                    assert "Validating migration configuration" in result.output
        finally:
            os.unlink(config_file)

    def test_validate_command_json_format(self):
        """Test validate command with JSON output format."""
        config_data = {"name": "Test Migration"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
                validation_result = {"valid": True, "errors": [], "warnings": []}
                mock_persistence.return_value.validate_configuration_file.return_value = validation_result
                
                result = self.runner.invoke(main, [
                    'validate',
                    '--config', config_file,
                    '--format', 'json'
                ])
                
                assert result.exit_code == 0
                assert '"valid": true' in result.output
        finally:
            os.unlink(config_file)

    def test_validate_command_invalid_config(self):
        """Test validate command with invalid config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            config_file = f.name
        
        try:
            result = self.runner.invoke(main, [
                'validate',
                '--config', config_file
            ])
            
            assert result.exit_code == 1
            assert ("Error during validation" in result.output or 
                   "Error loading configuration" in result.output or 
                   "Configuration file validation failed" in result.output)
        finally:
            os.unlink(config_file)


class TestStatusCommand:
    """Test status command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_status_command_basic(self):
        """Test status command basic functionality."""
        result = self.runner.invoke(main, ['status'])
        assert result.exit_code == 0
        assert "Checking migration status" in result.output
        assert "Status functionality will be implemented" in result.output

    def test_status_command_with_session_id(self):
        """Test status command with session ID."""
        result = self.runner.invoke(main, ['--verbose', 'status', '--session-id', 'test123'])
        assert result.exit_code == 0
        assert "Checking migration status" in result.output
        assert "Session ID: test123" in result.output

    def test_status_command_with_format(self):
        """Test status command with different output formats."""
        for format_type in ['table', 'json', 'yaml']:
            result = self.runner.invoke(main, [
                'status',
                '--format', format_type
            ])
            assert result.exit_code == 0
            assert "Checking migration status" in result.output

    def test_status_command_watch_mode(self):
        """Test status command with watch mode."""
        result = self.runner.invoke(main, [
            '--verbose',
            'status',
            '--watch'
        ])
        assert result.exit_code == 0
        assert "Watch mode: True" in result.output


class TestRollbackCommand:
    """Test rollback command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_rollback_command_with_confirmation(self):
        """Test rollback command with user confirmation."""
        result = self.runner.invoke(main, [
            'rollback',
            '--session-id', 'test123'
        ], input='n\n')  # User says no to confirmation
        assert result.exit_code == 0
        assert "Rollback cancelled" in result.output

    def test_rollback_command_confirmed(self):
        """Test rollback command when user confirms."""
        result = self.runner.invoke(main, [
            'rollback',
            '--session-id', 'test123'
        ], input='y\n')  # User confirms
        assert result.exit_code == 0
        assert "Rolling back migration session: test123" in result.output

    def test_rollback_command_force(self):
        """Test rollback command with force flag."""
        result = self.runner.invoke(main, [
            'rollback',
            '--session-id', 'test123',
            '--force'
        ])
        assert result.exit_code == 0
        assert "Rolling back migration session: test123" in result.output

    def test_rollback_command_verbose(self):
        """Test rollback command with verbose output."""
        result = self.runner.invoke(main, [
            '--verbose',
            'rollback',
            '--session-id', 'test123',
            '--force'
        ])
        assert result.exit_code == 0
        assert "Session ID: test123" in result.output
        assert "Force: True" in result.output


class TestConfigsCommand:
    """Test configs command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_configs_command_empty(self):
        """Test configs command when no configurations exist."""
        with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
            mock_persistence.return_value.list_configurations.return_value = []
            
            result = self.runner.invoke(main, ['configs'])
            assert result.exit_code == 0
            assert "No saved configurations found" in result.output

    def test_configs_command_with_configs(self):
        """Test configs command with existing configurations."""
        from datetime import datetime
        
        mock_configs = [
            {
                'filename': 'test1.yaml',
                'name': 'Test Migration 1',
                'modified': datetime.now(),
                'size': 1024,
                'valid': True
            },
            {
                'filename': 'test2.yaml',
                'name': 'Test Migration 2',
                'modified': datetime.now(),
                'size': 2048,
                'valid': False
            }
        ]
        
        with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
            mock_persistence.return_value.list_configurations.return_value = mock_configs
            
            result = self.runner.invoke(main, ['configs'])
            assert result.exit_code == 0
            assert "Saved Migration Configurations" in result.output
            assert "test1.yaml" in result.output
            assert "test2.yaml" in result.output

    def test_configs_command_json_format(self):
        """Test configs command with JSON output format."""
        mock_configs = [{'filename': 'test.yaml', 'name': 'Test', 'valid': True}]
        
        with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
            mock_persistence.return_value.list_configurations.return_value = mock_configs
            
            result = self.runner.invoke(main, ['configs', '--format', 'json'])
            assert result.exit_code == 0
            assert '"filename": "test.yaml"' in result.output


class TestPresetsCommand:
    """Test presets command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_presets_command_basic(self):
        """Test presets command basic functionality."""
        with patch('migration_assistant.cli.preset_manager.PresetManager') as mock_preset_manager:
            mock_presets = [
                ('wordpress-mysql', 'WordPress with MySQL', 'Standard WordPress setup'),
                ('django-postgres', 'Django with PostgreSQL', 'Django application setup')
            ]
            mock_preset_manager.return_value.get_available_presets.return_value = mock_presets
            
            result = self.runner.invoke(main, ['presets'])
            assert result.exit_code == 0
            assert "Available Migration Presets" in result.output
            # Test that the preset manager was called correctly
            mock_preset_manager.return_value.get_available_presets.assert_called_once()
            # Test that the enhanced table formatting is working
            assert "Usage Examples" in result.output
            assert "How to Use Presets" in result.output

    def test_presets_command_json_format(self):
        """Test presets command with JSON output format."""
        with patch('migration_assistant.cli.preset_manager.PresetManager') as mock_preset_manager:
            mock_presets = [('test-preset', 'Test Preset', 'Test description')]
            mock_preset_manager.return_value.get_available_presets.return_value = mock_presets
            
            result = self.runner.invoke(main, ['presets', '--format', 'json'])
            assert result.exit_code == 0
            assert '"key": "test-preset"' in result.output

    def test_presets_command_error(self):
        """Test presets command with error."""
        with patch('migration_assistant.cli.preset_manager.PresetManager') as mock_preset_manager:
            mock_preset_manager.return_value.get_available_presets.side_effect = Exception("Test error")
            
            result = self.runner.invoke(main, ['presets'])
            assert result.exit_code == 1
            assert "Error listing presets" in result.output


class TestServeCommand:
    """Test serve command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_serve_command_basic(self):
        """Test serve command basic functionality."""
        with patch('uvicorn.run') as mock_uvicorn:
            result = self.runner.invoke(main, ['serve'])
            assert result.exit_code == 0
            assert "Starting API server on 127.0.0.1:8000" in result.output
            mock_uvicorn.assert_called_once()

    def test_serve_command_with_options(self):
        """Test serve command with custom options."""
        with patch('uvicorn.run') as mock_uvicorn:
            result = self.runner.invoke(main, [
                'serve',
                '--host', '0.0.0.0',
                '--port', '9000',
                '--reload'
            ])
            assert result.exit_code == 0
            assert "Starting API server on 0.0.0.0:9000" in result.output
            mock_uvicorn.assert_called_once_with(
                "migration_assistant.api.main:app",
                host="0.0.0.0",
                port=9000,
                reload=True,
                log_level="info"
            )

    def test_serve_command_missing_uvicorn(self):
        """Test serve command when uvicorn is not available."""
        # Mock the import to raise ImportError
        original_import = __builtins__['__import__']
        
        def mock_import(name, *args, **kwargs):
            if name == 'uvicorn':
                raise ImportError("No module named 'uvicorn'")
            return original_import(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            result = self.runner.invoke(main, ['serve'])
            assert result.exit_code == 1
            assert "uvicorn is required" in result.output

    def test_serve_command_server_error(self):
        """Test serve command when server fails to start."""
        with patch('uvicorn.run', side_effect=Exception("Server error")):
            result = self.runner.invoke(main, ['serve'])
            assert result.exit_code == 1
            assert "Error starting server" in result.output


class TestHelpCommand:
    """Test help command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_help_command_basic(self):
        """Test basic help command."""
        result = self.runner.invoke(main, ['help'])
        assert result.exit_code == 0
        assert "Migration Assistant Help" in result.output
        assert "--topic quick-start" in result.output

    def test_help_command_quick_start(self):
        """Test help command with quick-start topic."""
        result = self.runner.invoke(main, ['help', '--topic', 'quick-start'])
        assert result.exit_code == 0
        assert "Quick Start Guide" in result.output
        assert "migration-assistant presets" in result.output

    def test_help_command_examples(self):
        """Test help command with examples topic."""
        result = self.runner.invoke(main, ['help', '--topic', 'examples'])
        assert result.exit_code == 0
        assert "Examples" in result.output

    def test_help_command_specific_command(self):
        """Test help command for specific command."""
        result = self.runner.invoke(main, ['help', '--command', 'migrate'])
        assert result.exit_code == 0
        assert "Migration Examples" in result.output

    def test_help_command_templates(self):
        """Test help command with templates topic."""
        result = self.runner.invoke(main, ['help', '--topic', 'templates'])
        assert result.exit_code == 0
        assert "Configuration Templates" in result.output
        assert "WordPress to AWS S3" in result.output

    def test_help_command_presets(self):
        """Test help command with presets topic."""
        result = self.runner.invoke(main, ['help', '--topic', 'presets'])
        assert result.exit_code == 0
        assert "Available Presets" in result.output

    def test_help_command_troubleshooting(self):
        """Test help command with troubleshooting topic."""
        result = self.runner.invoke(main, ['help', '--topic', 'troubleshooting'])
        assert result.exit_code == 0
        assert "Troubleshooting Guide" in result.output
        assert "Common Issues" in result.output


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_full_migration_workflow_dry_run(self):
        """Test complete migration workflow in dry-run mode."""
        # Create a test configuration
        config_data = {
            "name": "Integration Test Migration",
            "source": {
                "type": "wordpress",
                "host": "source.example.com",
                "database": {
                    "type": "mysql",
                    "host": "db.source.com",
                    "username": "wp_user",
                    "password": "wp_pass",
                    "database": "wordpress"
                }
            },
            "destination": {
                "type": "aws-s3",
                "host": "s3.amazonaws.com",
                "bucket": "migration-dest"
            },
            "transfer": {
                "files": "s3_sync",
                "database": "dump_restore"
            },
            "options": {
                "maintenance_mode": True,
                "backup_before": True,
                "verify_after": True,
                "dry_run": True
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            # Mock all the dependencies
            with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
                mock_config = Mock()
                mock_config.name = "Integration Test Migration"
                mock_persistence.return_value.load_configuration.return_value = mock_config
                mock_persistence.return_value.validate_configuration_file.return_value = {"valid": True, "errors": [], "warnings": []}
                
                with patch('migration_assistant.cli.config_persistence.ConfigurationValidator') as mock_validator:
                    mock_validator.return_value.validate_configuration.return_value = {"valid": True}
                    mock_validator.return_value.display_validation_results.return_value = None
                    
                    # Test validation
                    validate_result = self.runner.invoke(main, [
                        '--verbose',
                        'validate',
                        '--config', config_file
                    ])
                    assert validate_result.exit_code == 0
                    
                    # Test migration with dry-run
                    migrate_result = self.runner.invoke(main, [
                        '--verbose',
                        'migrate',
                        '--config', config_file,
                        '--dry-run'
                    ])
                    assert migrate_result.exit_code == 0
                    assert "Configuration loaded: Integration Test Migration" in migrate_result.output
                    
        finally:
            os.unlink(config_file)

    def test_error_handling_and_recovery(self):
        """Test error handling and recovery scenarios."""
        # Test with invalid config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            invalid_config = f.name
        
        try:
            result = self.runner.invoke(main, [
                'validate',
                '--config', invalid_config
            ])
            assert result.exit_code == 1
            assert ("Error during validation" in result.output or 
                   "Error loading configuration" in result.output or 
                   "Configuration file validation failed" in result.output)
            
        finally:
            os.unlink(invalid_config)

    def test_command_chaining_and_workflow(self):
        """Test command chaining and typical workflow scenarios."""
        with patch('migration_assistant.cli.preset_manager.PresetManager') as mock_preset_manager:
            mock_presets = [('wordpress-mysql', 'WordPress with MySQL', 'Standard setup')]
            mock_preset_manager.return_value.get_available_presets.return_value = mock_presets
            
            # List available presets
            presets_result = self.runner.invoke(main, ['presets'])
            assert presets_result.exit_code == 0
            assert "wordpress-mysql" in presets_result.output
            
            # List saved configurations (should be empty)
            with patch('migration_assistant.cli.config_persistence.ConfigurationPersistence') as mock_persistence:
                mock_persistence.return_value.list_configurations.return_value = []
                
                configs_result = self.runner.invoke(main, ['configs'])
                assert configs_result.exit_code == 0
                assert "No saved configurations found" in configs_result.output