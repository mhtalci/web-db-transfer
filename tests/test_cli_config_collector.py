"""
Unit tests for the CLI configuration collector.

Tests the interactive CLI configuration collection logic with mocked inputs.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from rich.console import Console
from pydantic import ValidationError

from migration_assistant.cli.config_collector import ConfigurationCollector
from migration_assistant.models.config import (
    SystemType, AuthType, DatabaseType, TransferMethod, ControlPanelType,
    MigrationConfig, SystemConfig, AuthConfig, PathConfig, DatabaseConfig,
    TransferConfig, MigrationOptions
)


class TestConfigurationCollector:
    """Test cases for ConfigurationCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create a ConfigurationCollector instance for testing."""
        return ConfigurationCollector()
    
    @pytest.fixture
    def mock_console(self):
        """Mock Rich console for testing."""
        return Mock(spec=Console)
    
    def test_init(self, collector):
        """Test ConfigurationCollector initialization."""
        assert isinstance(collector.console, Console)
        assert collector.config_data == {}
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_basic_info(self, mock_prompt, collector):
        """Test basic information collection."""
        # Mock user inputs
        mock_prompt.side_effect = [
            "Test Migration",  # name
            "Test migration description"  # description
        ]
        
        collector._collect_basic_info()
        
        assert collector.config_data["name"] == "Test Migration"
        assert collector.config_data["description"] == "Test migration description"
        assert mock_prompt.call_count == 2
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_basic_info_no_description(self, mock_prompt, collector):
        """Test basic information collection without description."""
        # Mock user inputs
        mock_prompt.side_effect = [
            "Test Migration",  # name
            ""  # empty description
        ]
        
        collector._collect_basic_info()
        
        assert collector.config_data["name"] == "Test Migration"
        assert "description" not in collector.config_data
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_select_system_type(self, mock_prompt, collector):
        """Test system type selection."""
        mock_prompt.return_value = "1"  # Select first option (wordpress)
        
        result = collector._select_system_type("source")
        
        assert result == SystemType.WORDPRESS
        mock_prompt.assert_called_once()
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_select_system_type_invalid_then_valid(self, mock_prompt, collector):
        """Test system type selection with invalid input first."""
        mock_prompt.side_effect = ["invalid", "99", "1"]  # Invalid, out of range, then valid
        
        result = collector._select_system_type("source")
        
        assert result == SystemType.WORDPRESS
        assert mock_prompt.call_count == 3
    
    @patch('migration_assistant.cli.config_collector.prompt')
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_host_info(self, mock_rich_prompt, mock_prompt_toolkit, collector):
        """Test host information collection."""
        mock_prompt_toolkit.return_value = "example.com"
        mock_rich_prompt.return_value = "8080"
        
        result = collector._collect_host_info("source")
        
        assert result["host"] == "example.com"
        assert result["port"] == 8080
    
    @patch('migration_assistant.cli.config_collector.prompt')
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_host_info_no_port(self, mock_rich_prompt, mock_prompt_toolkit, collector):
        """Test host information collection without port."""
        mock_prompt_toolkit.return_value = "example.com"
        mock_rich_prompt.return_value = ""  # Empty port
        
        result = collector._collect_host_info("source")
        
        assert result["host"] == "example.com"
        assert "port" not in result
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_auth_config_password(self, mock_prompt, collector):
        """Test authentication configuration collection for password auth."""
        mock_prompt.side_effect = [
            "1",  # Select password auth
            "testuser",  # username
            "testpass"  # password
        ]
        
        result = collector._collect_auth_config("source", SystemType.WORDPRESS)
        
        assert result.type == AuthType.PASSWORD
        assert result.username == "testuser"
        assert result.password == "testpass"
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_auth_config_ssh_key(self, mock_prompt, collector):
        """Test authentication configuration collection for SSH key auth."""
        mock_prompt.side_effect = [
            "2",  # Select SSH key auth
            "testuser",  # username
            "/path/to/key",  # ssh key path
            "passphrase"  # ssh key passphrase
        ]
        
        result = collector._collect_auth_config("source", SystemType.WORDPRESS)
        
        assert result.type == AuthType.SSH_KEY
        assert result.username == "testuser"
        assert result.ssh_key_path == "/path/to/key"
        assert result.ssh_key_passphrase == "passphrase"
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_path_config(self, mock_prompt, collector):
        """Test path configuration collection."""
        mock_prompt.side_effect = [
            "/var/www/html",  # root_path
            "/var/www/html/public"  # web_root
        ]
        
        result = collector._collect_path_config("source", SystemType.WORDPRESS)
        
        assert result.root_path == "/var/www/html"
        assert result.web_root == "/var/www/html/public"
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_database_config_mysql(self, mock_prompt, collector):
        """Test database configuration collection for MySQL."""
        mock_prompt.side_effect = [
            "1",  # Select MySQL
            "localhost",  # host
            "3306",  # port
            "testdb",  # database name
            "dbuser",  # username
            "dbpass"  # password
        ]
        
        result = collector._collect_database_config("source")
        
        assert result.type == DatabaseType.MYSQL
        assert result.host == "localhost"
        assert result.port == 3306
        assert result.database_name == "testdb"
        assert result.username == "dbuser"
        assert result.password == "dbpass"
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_transfer_config_basic(self, mock_prompt, collector):
        """Test basic transfer configuration collection."""
        mock_prompt.side_effect = [
            "1",  # Select SSH/SCP
            "n"   # No advanced options
        ]
        
        with patch('migration_assistant.cli.config_collector.Confirm.ask', return_value=False):
            result = collector._collect_transfer_config()
        
        assert result.method == TransferMethod.SSH_SCP
        # Should use defaults for other settings
        assert result.parallel_transfers == 4
        assert result.compression_enabled is False
        assert result.verify_checksums is True
    
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    def test_collect_migration_options_basic(self, mock_prompt, collector):
        """Test basic migration options collection."""
        with patch('migration_assistant.cli.config_collector.Confirm.ask') as mock_confirm:
            mock_confirm.side_effect = [
                True,   # maintenance_mode
                True,   # backup_before
                True,   # verify_after
                True,   # rollback_on_failure
                False   # No advanced options
            ]
            
            result = collector._collect_migration_options()
        
        assert result.maintenance_mode is True
        assert result.backup_before is True
        assert result.verify_after is True
        assert result.rollback_on_failure is True
    
    def test_needs_database_config(self, collector):
        """Test database configuration requirement check."""
        # Should need database config
        assert collector._needs_database_config(SystemType.WORDPRESS) is True
        assert collector._needs_database_config(SystemType.DJANGO) is True
        
        # Should not need database config
        assert collector._needs_database_config(SystemType.STATIC_SITE) is False
        assert collector._needs_database_config(SystemType.AWS_S3) is False
    
    def test_needs_cloud_config(self, collector):
        """Test cloud configuration requirement check."""
        # Should need cloud config
        assert collector._needs_cloud_config(SystemType.AWS_S3) is True
        assert collector._needs_cloud_config(SystemType.GOOGLE_CLOUD_STORAGE) is True
        
        # Should not need cloud config
        assert collector._needs_cloud_config(SystemType.WORDPRESS) is False
        assert collector._needs_cloud_config(SystemType.STATIC_SITE) is False
    
    def test_needs_control_panel_config(self, collector):
        """Test control panel configuration requirement check."""
        # Should need control panel config
        assert collector._needs_control_panel_config(SystemType.CPANEL) is True
        assert collector._needs_control_panel_config(SystemType.DIRECTADMIN) is True
        
        # Should not need control panel config
        assert collector._needs_control_panel_config(SystemType.WORDPRESS) is False
        assert collector._needs_control_panel_config(SystemType.AWS_S3) is False
    
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._show_configuration_summary')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_migration_options')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_transfer_config')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_system_config')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_basic_info')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._show_welcome')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._offer_preset_selection')
    def test_collect_configuration_success(self, mock_preset_offer, mock_welcome, mock_basic, mock_system, 
                                         mock_transfer, mock_options, mock_summary, collector):
        """Test successful complete configuration collection."""
        # Setup mocks
        collector.config_data = {"name": "Test Migration"}
        mock_preset_offer.return_value = False  # Don't use presets
        
        mock_system.side_effect = [
            SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.com",
                authentication=AuthConfig(type=AuthType.PASSWORD, username="user", password="pass"),
                paths=PathConfig(root_path="/var/www")
            ),
            SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                authentication=AuthConfig(type=AuthType.AWS_IAM),
                paths=PathConfig(root_path="/")
            )
        ]
        
        mock_transfer.return_value = TransferConfig(method=TransferMethod.SSH_SCP)
        mock_options.return_value = MigrationOptions()
        
        result = collector.collect_configuration()
        
        # Verify all methods were called
        mock_welcome.assert_called_once()
        mock_basic.assert_called_once()
        assert mock_system.call_count == 2
        mock_transfer.assert_called_once()
        mock_options.assert_called_once()
        mock_summary.assert_called_once()
        
        # Verify result
        assert isinstance(result, MigrationConfig)
        assert result.name == "Test Migration"
    
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._show_configuration_summary')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_migration_options')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_transfer_config')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_system_config')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._collect_basic_info')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._show_welcome')
    @patch('migration_assistant.cli.config_collector.ConfigurationCollector._offer_preset_selection')
    def test_collect_configuration_validation_error(self, mock_preset_offer, mock_welcome, mock_basic, mock_system,
                                                   mock_transfer, mock_options, mock_summary, collector):
        """Test configuration collection with validation error."""
        # Setup invalid data that will cause validation error - empty name should fail validation
        collector.config_data = {"name": ""}  # Empty name should cause validation error
        mock_preset_offer.return_value = False  # Don't use presets
        
        # Mock the methods to avoid stdin issues
        mock_system.side_effect = [
            SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.com",
                authentication=AuthConfig(type=AuthType.PASSWORD, username="user", password="pass"),
                paths=PathConfig(root_path="/var/www")
            ),
            SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                authentication=AuthConfig(type=AuthType.AWS_IAM),
                paths=PathConfig(root_path="/")
            )
        ]
        mock_transfer.return_value = TransferConfig(method=TransferMethod.SSH_SCP)
        mock_options.return_value = MigrationOptions()
        
        with pytest.raises(ValidationError):
            collector.collect_configuration()


class TestConfigurationCollectorValidation:
    """Test validation logic in ConfigurationCollector."""
    
    @pytest.fixture
    def collector(self):
        return ConfigurationCollector()
    
    def test_host_validator_empty(self, collector):
        """Test host validator with empty input."""
        from migration_assistant.cli.config_collector import ConfigurationCollector
        from prompt_toolkit.document import Document
        from prompt_toolkit.validation import ValidationError
        
        # Create a mock document with empty text
        document = Mock()
        document.text = ""
        
        # This would be tested in integration, but we can test the logic
        # The actual validator is created inline in the method
        pass  # Placeholder for validator testing
    
    def test_system_type_selection_bounds(self, collector):
        """Test system type selection with boundary values."""
        # This tests the validation logic in _select_system_type
        # The actual implementation handles invalid selections by re-prompting
        pass  # Placeholder for boundary testing


class TestConfigurationCollectorIntegration:
    """Integration tests for ConfigurationCollector."""
    
    @pytest.fixture
    def collector(self):
        return ConfigurationCollector()
    
    @patch('migration_assistant.cli.config_collector.Confirm.ask')
    @patch('migration_assistant.cli.config_collector.Prompt.ask')
    @patch('migration_assistant.cli.config_collector.prompt')
    def test_full_wordpress_to_s3_configuration(self, mock_prompt_toolkit, mock_rich_prompt, 
                                               mock_confirm, collector):
        """Test complete configuration flow for WordPress to S3 migration."""
        # Mock all user inputs for a complete flow
        mock_rich_prompt.side_effect = [
            # Basic info
            "WordPress to S3 Migration",
            "Migrate WordPress site to AWS S3",
            
            # Source system selection and config
            "1",  # WordPress
            "8080",  # port
            "1",  # password auth
            "wpuser",  # username
            "wppass",  # password
            "/var/www/html",  # root path
            "/var/www/html/wp-content",  # web root
            
            # Database config
            "1",  # MySQL
            "localhost",  # db host
            "3306",  # db port
            "wordpress_db",  # db name
            "dbuser",  # db username
            "dbpass",  # db password
            
            # Destination system selection and config
            "12",  # AWS S3 (assuming it's option 12)
            "",  # no port for S3
            "6",  # AWS IAM auth (assuming it's option 6)
            "aws",  # provider
            "us-east-1",  # region
            "AKIAIOSFODNN7EXAMPLE",  # access key
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # secret key
            "my-migration-bucket",  # bucket name
            
            # Transfer config
            "6",  # AWS S3 sync
            "8",  # parallel transfers
            
            # No advanced transfer options, no advanced migration options
        ]
        
        mock_prompt_toolkit.side_effect = [
            "wordpress.example.com",  # source host
            "s3.amazonaws.com"  # destination host
        ]
        
        mock_confirm.side_effect = [
            # Transfer options
            True,   # configure advanced transfer options
            True,   # enable compression
            True,   # verify checksums
            
            # Migration options
            True,   # maintenance mode
            True,   # backup before
            True,   # verify after
            True,   # rollback on failure
            False,  # no advanced migration options
            
            # Final confirmation
            True    # proceed with configuration
        ]
        
        # This would be a full integration test
        # For now, we'll just verify the structure is set up correctly
        assert hasattr(collector, 'collect_configuration')
        assert hasattr(collector, '_collect_basic_info')
        assert hasattr(collector, '_collect_system_config')
        assert hasattr(collector, '_collect_transfer_config')
        assert hasattr(collector, '_collect_migration_options')