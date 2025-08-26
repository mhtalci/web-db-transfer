"""
Unit tests for the configuration persistence and validation system.

Tests configuration saving, loading, validation, and error handling.
"""

import pytest
import tempfile
import yaml
import toml
import json
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from migration_assistant.cli.config_persistence import (
    ConfigurationPersistence, ConfigurationValidator
)
from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, AuthConfig, PathConfig, DatabaseConfig,
    TransferConfig, MigrationOptions, SystemType, AuthType, DatabaseType,
    TransferMethod, CloudConfig
)


class TestConfigurationPersistence:
    """Test cases for ConfigurationPersistence class."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary directory for configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def persistence(self, temp_config_dir):
        """Create a ConfigurationPersistence instance with temp directory."""
        return ConfigurationPersistence(config_dir=temp_config_dir)
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample migration configuration for testing."""
        return MigrationConfig(
            name="Test Migration",
            description="Test migration configuration",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.example.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="www-data"),
                paths=PathConfig(root_path="/var/www/html"),
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="localhost",
                    database_name="wordpress",
                    username="wp_user",
                    password="wp_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                authentication=AuthConfig(type=AuthType.AWS_IAM),
                paths=PathConfig(root_path="/")
            ),
            transfer=TransferConfig(method=TransferMethod.AWS_S3),
            options=MigrationOptions(backup_before=True, verify_after=True)
        )
    
    def test_init_default_config_dir(self):
        """Test initialization with default config directory."""
        persistence = ConfigurationPersistence()
        expected_path = Path.home() / ".migration-assistant" / "configs"
        assert persistence.config_dir == expected_path
    
    def test_init_custom_config_dir(self, temp_config_dir):
        """Test initialization with custom config directory."""
        persistence = ConfigurationPersistence(config_dir=temp_config_dir)
        assert persistence.config_dir == Path(temp_config_dir)
    
    def test_save_configuration_yaml(self, persistence, sample_config):
        """Test saving configuration in YAML format."""
        saved_path = persistence.save_configuration(sample_config, format="yaml")
        
        assert Path(saved_path).exists()
        assert saved_path.endswith(".yaml")
        
        # Verify file content
        with open(saved_path, 'r') as f:
            loaded_data = yaml.safe_load(f)
        
        assert loaded_data["name"] == "Test Migration"
        assert loaded_data["source"]["type"] == "wordpress"
        assert loaded_data["destination"]["type"] == "aws_s3"
    
    def test_save_configuration_toml(self, persistence, sample_config):
        """Test saving configuration in TOML format."""
        saved_path = persistence.save_configuration(sample_config, format="toml")
        
        assert Path(saved_path).exists()
        assert saved_path.endswith(".toml")
        
        # Verify file content
        with open(saved_path, 'r') as f:
            loaded_data = toml.load(f)
        
        assert loaded_data["name"] == "Test Migration"
        assert loaded_data["source"]["type"] == "wordpress"
    
    def test_save_configuration_custom_filename(self, persistence, sample_config):
        """Test saving configuration with custom filename."""
        custom_filename = "my_custom_config"
        saved_path = persistence.save_configuration(
            sample_config, 
            filename=custom_filename, 
            format="yaml"
        )
        
        assert "my_custom_config.yaml" in saved_path
        assert Path(saved_path).exists()
    
    def test_save_configuration_invalid_format(self, persistence, sample_config):
        """Test saving configuration with invalid format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            persistence.save_configuration(sample_config, format="xml")
    
    def test_load_configuration_yaml(self, persistence, sample_config):
        """Test loading configuration from YAML file."""
        # Save first
        saved_path = persistence.save_configuration(sample_config, format="yaml")
        
        # Load
        loaded_config = persistence.load_configuration(saved_path)
        
        assert loaded_config.name == sample_config.name
        assert loaded_config.source.type == sample_config.source.type
        assert loaded_config.destination.type == sample_config.destination.type
    
    def test_load_configuration_toml(self, persistence, sample_config):
        """Test loading configuration from TOML file."""
        # Save first
        saved_path = persistence.save_configuration(sample_config, format="toml")
        
        # Load
        loaded_config = persistence.load_configuration(saved_path)
        
        assert loaded_config.name == sample_config.name
        assert loaded_config.source.type == sample_config.source.type
    
    def test_load_configuration_nonexistent_file(self, persistence):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            persistence.load_configuration("nonexistent.yaml")
    
    def test_load_configuration_invalid_format(self, persistence, temp_config_dir):
        """Test loading configuration with unsupported file extension."""
        invalid_file = Path(temp_config_dir) / "config.xml"
        invalid_file.write_text("<config></config>")
        
        with pytest.raises(ValueError, match="Unsupported file format"):
            persistence.load_configuration(str(invalid_file))
    
    def test_load_configuration_invalid_yaml(self, persistence, temp_config_dir):
        """Test loading configuration with invalid YAML."""
        invalid_yaml = Path(temp_config_dir) / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: content: [")
        
        with pytest.raises(ValueError, match="Invalid YAML format"):
            persistence.load_configuration(str(invalid_yaml))
    
    def test_load_configuration_empty_file(self, persistence, temp_config_dir):
        """Test loading configuration from empty file."""
        empty_file = Path(temp_config_dir) / "empty.yaml"
        empty_file.write_text("")
        
        with pytest.raises(ValueError, match="Configuration file is empty"):
            persistence.load_configuration(str(empty_file))
    
    def test_list_configurations(self, persistence, sample_config):
        """Test listing saved configurations."""
        # Save a few configurations
        persistence.save_configuration(sample_config, filename="config1", format="yaml")
        persistence.save_configuration(sample_config, filename="config2", format="toml")
        
        configs = persistence.list_configurations()
        
        assert len(configs) == 2
        assert any(c["filename"] == "config1.yaml" for c in configs)
        assert any(c["filename"] == "config2.toml" for c in configs)
        
        # Check metadata structure
        for config_info in configs:
            assert "filename" in config_info
            assert "path" in config_info
            assert "size" in config_info
            assert "modified" in config_info
            assert "format" in config_info
            assert "valid" in config_info
    
    def test_delete_configuration(self, persistence, sample_config):
        """Test deleting a saved configuration."""
        # Save configuration
        saved_path = persistence.save_configuration(sample_config, filename="to_delete", format="yaml")
        filename = Path(saved_path).name
        
        # Verify it exists
        assert Path(saved_path).exists()
        
        # Delete it
        result = persistence.delete_configuration(filename)
        assert result is True
        assert not Path(saved_path).exists()
    
    def test_delete_nonexistent_configuration(self, persistence):
        """Test deleting a non-existent configuration."""
        result = persistence.delete_configuration("nonexistent.yaml")
        assert result is False
    
    def test_validate_configuration_file_valid(self, persistence, sample_config):
        """Test validating a valid configuration file."""
        saved_path = persistence.save_configuration(sample_config, format="yaml")
        
        validation_result = persistence.validate_configuration_file(saved_path)
        
        assert validation_result["valid"] is True
        assert len(validation_result["errors"]) == 0
        assert "metadata" in validation_result
        assert validation_result["metadata"]["name"] == "Test Migration"
    
    def test_validate_configuration_file_missing(self, persistence):
        """Test validating a missing configuration file."""
        validation_result = persistence.validate_configuration_file("nonexistent.yaml")
        
        assert validation_result["valid"] is False
        assert any("File not found" in error for error in validation_result["errors"])
    
    def test_validate_configuration_file_invalid_format(self, persistence, temp_config_dir):
        """Test validating a file with invalid format."""
        invalid_file = Path(temp_config_dir) / "invalid.txt"
        invalid_file.write_text("some content")
        
        validation_result = persistence.validate_configuration_file(str(invalid_file))
        
        assert validation_result["valid"] is False
        assert any("Unsupported file format" in error for error in validation_result["errors"])
    
    def test_validate_configuration_file_missing_fields(self, persistence, temp_config_dir):
        """Test validating a configuration file with missing required fields."""
        incomplete_config = {"name": "Test", "source": {"type": "wordpress"}}
        
        incomplete_file = Path(temp_config_dir) / "incomplete.yaml"
        with open(incomplete_file, 'w') as f:
            yaml.dump(incomplete_config, f)
        
        validation_result = persistence.validate_configuration_file(str(incomplete_file))
        
        assert validation_result["valid"] is False
        assert any("Missing required field" in error for error in validation_result["errors"])
    
    def test_sanitize_filename(self, persistence):
        """Test filename sanitization."""
        # Test various problematic characters
        assert persistence._sanitize_filename("Test Config!") == "test_config"
        assert persistence._sanitize_filename("My/Config\\File") == "myconfigfile"
        assert persistence._sanitize_filename("Config with spaces") == "config_with_spaces"
        assert persistence._sanitize_filename("") == "migration_config"
        
        # Test length limiting
        long_name = "a" * 100
        sanitized = persistence._sanitize_filename(long_name)
        assert len(sanitized) <= 50
    
    def test_config_to_dict(self, persistence, sample_config):
        """Test converting MigrationConfig to dictionary."""
        config_dict = persistence._config_to_dict(sample_config)
        
        assert isinstance(config_dict, dict)
        assert config_dict["name"] == sample_config.name
        assert "source" in config_dict
        assert "destination" in config_dict
        assert "transfer" in config_dict
        assert "options" in config_dict
        assert "created_at" in config_dict
    
    def test_dict_to_config(self, persistence, sample_config):
        """Test converting dictionary to MigrationConfig."""
        config_dict = persistence._config_to_dict(sample_config)
        recreated_config = persistence._dict_to_config(config_dict)
        
        assert recreated_config.name == sample_config.name
        assert recreated_config.source.type == sample_config.source.type
        assert recreated_config.destination.type == sample_config.destination.type
    
    def test_dict_to_config_invalid(self, persistence):
        """Test converting invalid dictionary to MigrationConfig."""
        invalid_dict = {"name": ""}  # Empty name should fail validation
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            persistence._dict_to_config(invalid_dict)


class TestConfigurationValidator:
    """Test cases for ConfigurationValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a ConfigurationValidator instance."""
        return ConfigurationValidator()
    
    @pytest.fixture
    def valid_config(self):
        """Create a valid migration configuration."""
        return MigrationConfig(
            name="Valid Migration",
            description="A valid migration configuration",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.example.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="www-data"),
                paths=PathConfig(root_path="/var/www/html"),
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="localhost",
                    database_name="wordpress",
                    username="wp_user",
                    password="wp_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                authentication=AuthConfig(type=AuthType.AWS_IAM),
                paths=PathConfig(root_path="/"),
                cloud_config=CloudConfig(
                    provider="aws",
                    region="us-east-1",
                    bucket_name="test-bucket"
                )
            ),
            transfer=TransferConfig(
                method=TransferMethod.AWS_S3,
                parallel_transfers=4,
                verify_checksums=True
            ),
            options=MigrationOptions(
                backup_before=True,
                verify_after=True,
                rollback_on_failure=True,
                maintenance_mode=True  # Add this to avoid the suggestion
            )
        )
    
    def test_validate_configuration_valid(self, validator, valid_config):
        """Test validating a valid configuration."""
        result = validator.validate_configuration(valid_config)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_basic_info_short_name(self, validator):
        """Test validation with short migration name."""
        config = MigrationConfig(
            name="AB",  # Too short
            source=SystemConfig(
                type=SystemType.STATIC_SITE,
                host="test.com",
                authentication=AuthConfig(type=AuthType.PASSWORD, username="user", password="pass"),
                paths=PathConfig(root_path="/")
            ),
            destination=SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                authentication=AuthConfig(type=AuthType.AWS_IAM),
                paths=PathConfig(root_path="/")
            ),
            transfer=TransferConfig(method=TransferMethod.AWS_S3),
            options=MigrationOptions()
        )
        
        result = validator.validate_configuration(config)
        
        assert result["valid"] is False
        assert any("at least 3 characters" in error for error in result["errors"])
    
    def test_validate_basic_info_long_name(self, validator, valid_config):
        """Test validation with very long migration name."""
        valid_config.name = "A" * 150  # Very long name
        
        result = validator.validate_configuration(valid_config)
        
        assert any("very long" in warning for warning in result["warnings"])
    
    def test_validate_basic_info_no_description(self, validator, valid_config):
        """Test validation without description."""
        valid_config.description = None
        
        result = validator.validate_configuration(valid_config)
        
        assert any("Consider adding a description" in suggestion for suggestion in result["suggestions"])
    
    def test_validate_system_compatibility_same_system(self, validator):
        """Test validation with same source and destination."""
        config = MigrationConfig(
            name="Same System Migration",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="same.example.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="www-data"),
                paths=PathConfig(root_path="/var/www/html"),
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="localhost",
                    database_name="wordpress",
                    username="wp_user",
                    password="wp_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.WORDPRESS,
                host="same.example.com",  # Same host
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="www-data"),
                paths=PathConfig(root_path="/var/www/html"),
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="localhost",
                    database_name="wordpress",
                    username="wp_user",
                    password="wp_pass"
                )
            ),
            transfer=TransferConfig(method=TransferMethod.RSYNC),
            options=MigrationOptions()
        )
        
        result = validator.validate_configuration(config)
        
        assert any("same system" in warning for warning in result["warnings"])
    
    def test_validate_database_type_mismatch(self, validator):
        """Test validation with different database types."""
        config = MigrationConfig(
            name="DB Type Mismatch",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="source.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="www-data"),
                paths=PathConfig(root_path="/var/www/html"),
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="localhost",
                    database_name="wordpress",
                    username="wp_user",
                    password="wp_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.WORDPRESS,
                host="dest.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="www-data"),
                paths=PathConfig(root_path="/var/www/html"),
                database=DatabaseConfig(
                    type=DatabaseType.POSTGRESQL,  # Different DB type
                    host="localhost",
                    database_name="wordpress",
                    username="wp_user",
                    password="wp_pass"
                )
            ),
            transfer=TransferConfig(method=TransferMethod.RSYNC),
            options=MigrationOptions()
        )
        
        result = validator.validate_configuration(config)
        
        assert any("Database types differ" in warning for warning in result["warnings"])
    
    def test_validate_transfer_method_high_parallel(self, validator, valid_config):
        """Test validation with very high parallel transfers."""
        valid_config.transfer.parallel_transfers = 20  # Very high
        
        result = validator.validate_configuration(valid_config)
        
        assert any("Very high parallel transfer" in warning for warning in result["warnings"])
    
    def test_validate_transfer_method_low_parallel(self, validator, valid_config):
        """Test validation with low parallel transfers."""
        valid_config.transfer.parallel_transfers = 1  # Very low
        
        result = validator.validate_configuration(valid_config)
        
        assert any("Consider increasing parallel transfers" in suggestion for suggestion in result["suggestions"])
    
    def test_validate_security_password_auth(self, validator, valid_config):
        """Test validation with password authentication."""
        valid_config.source.authentication.type = AuthType.PASSWORD
        valid_config.destination.authentication.type = AuthType.PASSWORD
        
        result = validator.validate_configuration(valid_config)
        
        suggestions = result["suggestions"]
        assert any("SSH keys instead of passwords" in suggestion for suggestion in suggestions)
    
    def test_validate_security_no_backup(self, validator, valid_config):
        """Test validation with backup disabled."""
        valid_config.options.backup_before = False
        
        result = validator.validate_configuration(valid_config)
        
        assert any("Backup before migration is disabled" in warning for warning in result["warnings"])
    
    def test_validate_security_no_rollback(self, validator, valid_config):
        """Test validation with rollback disabled."""
        valid_config.options.rollback_on_failure = False
        
        result = validator.validate_configuration(valid_config)
        
        assert any("Automatic rollback is disabled" in warning for warning in result["warnings"])
    
    def test_validate_performance_no_checksums(self, validator, valid_config):
        """Test validation with checksum verification disabled."""
        valid_config.transfer.verify_checksums = False
        
        result = validator.validate_configuration(valid_config)
        
        assert any("Checksum verification is disabled" in warning for warning in result["warnings"])
    
    def test_validate_performance_no_maintenance_mode(self, validator, valid_config):
        """Test validation without maintenance mode."""
        valid_config.options.maintenance_mode = False
        
        result = validator.validate_configuration(valid_config)
        
        assert any("Consider enabling maintenance mode" in suggestion for suggestion in result["suggestions"])


class TestConfigurationPersistenceIntegration:
    """Integration tests for configuration persistence."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary directory for configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def persistence(self, temp_config_dir):
        """Create a ConfigurationPersistence instance with temp directory."""
        return ConfigurationPersistence(config_dir=temp_config_dir)
    
    def test_full_save_load_validate_cycle(self, persistence):
        """Test complete cycle of save, load, and validate."""
        # Create configuration
        original_config = MigrationConfig(
            name="Integration Test",
            description="Full cycle test",
            source=SystemConfig(
                type=SystemType.DJANGO,
                host="django.example.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="django"),
                paths=PathConfig(root_path="/opt/django"),
                database=DatabaseConfig(
                    type=DatabaseType.POSTGRESQL,
                    host="localhost",
                    database_name="django_db",
                    username="django_user",
                    password="django_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.KUBERNETES_POD,
                host="k8s.example.com",
                authentication=AuthConfig(type=AuthType.API_KEY, api_key="k8s-token"),
                paths=PathConfig(root_path="/app")
            ),
            transfer=TransferConfig(
                method=TransferMethod.KUBERNETES_VOLUME,
                parallel_transfers=6,
                compression_enabled=True,
                verify_checksums=True
            ),
            options=MigrationOptions(
                backup_before=True,
                verify_after=True,
                rollback_on_failure=True,
                maintenance_mode=True
            )
        )
        
        # Save configuration
        saved_path = persistence.save_configuration(original_config, format="yaml")
        assert Path(saved_path).exists()
        
        # Validate file
        file_validation = persistence.validate_configuration_file(saved_path)
        assert file_validation["valid"] is True
        
        # Load configuration
        loaded_config = persistence.load_configuration(saved_path)
        assert loaded_config.name == original_config.name
        assert loaded_config.source.type == original_config.source.type
        assert loaded_config.destination.type == original_config.destination.type
        
        # Validate loaded configuration
        validator = ConfigurationValidator()
        validation_result = validator.validate_configuration(loaded_config)
        assert validation_result["valid"] is True
        
        # List configurations
        configs = persistence.list_configurations()
        assert len(configs) == 1
        assert configs[0]["name"] == "Integration Test"
        assert configs[0]["valid"] is True
    
    def test_yaml_toml_format_compatibility(self, persistence):
        """Test that configurations can be saved in different formats and loaded correctly."""
        config = MigrationConfig(
            name="Format Test",
            source=SystemConfig(
                type=SystemType.STATIC_SITE,
                host="static.example.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="www-data"),
                paths=PathConfig(root_path="/var/www/html")
            ),
            destination=SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                authentication=AuthConfig(type=AuthType.AWS_IAM),
                paths=PathConfig(root_path="/")
            ),
            transfer=TransferConfig(method=TransferMethod.AWS_S3),
            options=MigrationOptions()
        )
        
        # Save in both formats
        yaml_path = persistence.save_configuration(config, filename="test_yaml", format="yaml")
        toml_path = persistence.save_configuration(config, filename="test_toml", format="toml")
        
        # Load both
        yaml_config = persistence.load_configuration(yaml_path)
        toml_config = persistence.load_configuration(toml_path)
        
        # Compare
        assert yaml_config.name == toml_config.name
        assert yaml_config.source.type == toml_config.source.type
        assert yaml_config.destination.type == toml_config.destination.type
        assert yaml_config.transfer.method == toml_config.transfer.method