"""
Unit tests for the preset management system.

Tests preset creation, management, customization, and integration.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.cli.preset_manager import PresetManager, PresetType
from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, AuthConfig, PathConfig, DatabaseConfig,
    TransferConfig, MigrationOptions, SystemType, AuthType, DatabaseType,
    TransferMethod
)


class TestPresetManager:
    """Test cases for PresetManager class."""
    
    @pytest.fixture
    def preset_manager(self):
        """Create a PresetManager instance for testing."""
        return PresetManager()
    
    def test_init(self, preset_manager):
        """Test PresetManager initialization."""
        assert isinstance(preset_manager._presets, dict)
        assert isinstance(preset_manager._custom_presets, dict)
        assert len(preset_manager._presets) > 0  # Should have built-in presets
    
    def test_get_available_presets(self, preset_manager):
        """Test getting list of available presets."""
        presets = preset_manager.get_available_presets()
        
        assert isinstance(presets, list)
        assert len(presets) > 0
        
        # Check structure of preset entries
        for preset_key, name, description in presets:
            assert isinstance(preset_key, str)
            assert isinstance(name, str)
            assert isinstance(description, str)
            assert len(preset_key) > 0
            assert len(name) > 0
    
    def test_get_preset_config_builtin(self, preset_manager):
        """Test getting built-in preset configuration."""
        # Test with a known built-in preset
        config = preset_manager.get_preset_config(PresetType.WORDPRESS_MYSQL.value)
        
        assert config is not None
        assert isinstance(config, dict)
        assert "name" in config
        assert "source" in config
        assert "destination" in config
        assert "transfer" in config
        assert "options" in config
    
    def test_get_preset_config_nonexistent(self, preset_manager):
        """Test getting non-existent preset configuration."""
        config = preset_manager.get_preset_config("nonexistent-preset")
        assert config is None
    
    def test_create_migration_config_from_preset(self, preset_manager):
        """Test creating MigrationConfig from preset."""
        config = preset_manager.create_migration_config_from_preset(
            PresetType.WORDPRESS_MYSQL.value
        )
        
        assert isinstance(config, MigrationConfig)
        assert config.name is not None
        assert config.source.type == SystemType.WORDPRESS
        assert config.destination.type == SystemType.WORDPRESS
        assert config.transfer.method == TransferMethod.RSYNC
    
    def test_create_migration_config_with_overrides(self, preset_manager):
        """Test creating MigrationConfig from preset with overrides."""
        overrides = {
            "name": "Custom WordPress Migration",
            "source": {
                "host": "custom-source.com"
            },
            "transfer": {
                "parallel_transfers": 8
            }
        }
        
        config = preset_manager.create_migration_config_from_preset(
            PresetType.WORDPRESS_MYSQL.value,
            overrides=overrides
        )
        
        assert config.name == "Custom WordPress Migration"
        assert config.source.host == "custom-source.com"
        assert config.transfer.parallel_transfers == 8
    
    def test_create_migration_config_nonexistent_preset(self, preset_manager):
        """Test creating MigrationConfig from non-existent preset."""
        config = preset_manager.create_migration_config_from_preset("nonexistent")
        assert config is None
    
    def test_save_custom_preset(self, preset_manager):
        """Test saving a custom preset."""
        # Create a sample migration config
        migration_config = MigrationConfig(
            name="Test Migration",
            description="Test description",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="test.com",
                authentication=AuthConfig(type=AuthType.PASSWORD, username="user", password="pass"),
                paths=PathConfig(root_path="/test")
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
        
        preset_key = preset_manager.save_custom_preset(
            "My Custom Preset",
            migration_config,
            "Custom preset description"
        )
        
        assert preset_key == "my-custom-preset"
        assert preset_key in preset_manager._custom_presets
        
        # Verify the saved preset
        saved_config = preset_manager.get_preset_config(preset_key)
        assert saved_config is not None
        assert saved_config["name"] == "My Custom Preset"
        assert saved_config["description"] == "Custom preset description"
        assert saved_config["custom"] is True
    
    def test_delete_custom_preset(self, preset_manager):
        """Test deleting a custom preset."""
        # First create a custom preset
        migration_config = MigrationConfig(
            name="Test Migration",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="test.com",
                authentication=AuthConfig(type=AuthType.PASSWORD, username="user", password="pass"),
                paths=PathConfig(root_path="/test")
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
        
        preset_key = preset_manager.save_custom_preset("Test Preset", migration_config)
        
        # Verify it exists
        assert preset_manager.get_preset_config(preset_key) is not None
        
        # Delete it
        result = preset_manager.delete_custom_preset(preset_key)
        assert result is True
        
        # Verify it's gone
        assert preset_manager.get_preset_config(preset_key) is None
    
    def test_delete_builtin_preset(self, preset_manager):
        """Test attempting to delete a built-in preset."""
        result = preset_manager.delete_custom_preset(PresetType.WORDPRESS_MYSQL.value)
        assert result is False
    
    def test_delete_nonexistent_preset(self, preset_manager):
        """Test deleting a non-existent preset."""
        result = preset_manager.delete_custom_preset("nonexistent")
        assert result is False
    
    def test_get_preset_suggestions(self, preset_manager):
        """Test getting preset suggestions based on system types."""
        # Test WordPress to S3 suggestion
        suggestions = preset_manager.get_preset_suggestions(
            SystemType.WORDPRESS, 
            SystemType.AWS_S3
        )
        assert PresetType.WORDPRESS_MYSQL_TO_S3.value in suggestions
        
        # Test Django to GCS suggestion
        suggestions = preset_manager.get_preset_suggestions(
            SystemType.DJANGO,
            SystemType.GOOGLE_CLOUD_STORAGE
        )
        assert PresetType.DJANGO_POSTGRES_TO_GCS.value in suggestions
        
        # Test static site to S3
        suggestions = preset_manager.get_preset_suggestions(
            SystemType.STATIC_SITE,
            SystemType.AWS_S3
        )
        assert PresetType.STATIC_TO_S3.value in suggestions
    
    def test_get_preset_suggestions_no_matches(self, preset_manager):
        """Test getting preset suggestions with no direct matches."""
        suggestions = preset_manager.get_preset_suggestions(
            SystemType.FLASK,  # No direct presets for Flask
            SystemType.AZURE_BLOB
        )
        # Should return empty list or partial matches
        assert isinstance(suggestions, list)
    
    def test_export_preset(self, preset_manager):
        """Test exporting a preset to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            result = preset_manager.export_preset(
                PresetType.WORDPRESS_MYSQL.value,
                temp_path
            )
            assert result is True
            
            # Verify the file was created and contains valid JSON
            with open(temp_path, 'r') as f:
                exported_data = json.load(f)
            
            assert "name" in exported_data
            assert "source" in exported_data
            assert "destination" in exported_data
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_export_nonexistent_preset(self, preset_manager):
        """Test exporting a non-existent preset."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            result = preset_manager.export_preset("nonexistent", temp_path)
            assert result is False
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_preset(self, preset_manager):
        """Test importing a preset from file."""
        # Create a test preset file
        preset_data = {
            "name": "Imported Preset",
            "description": "Test imported preset",
            "source": {
                "type": SystemType.WORDPRESS.value,
                "host": "imported.com",
                "authentication": {
                    "type": AuthType.PASSWORD.value,
                    "username": "user",
                    "password": "pass"
                },
                "paths": {
                    "root_path": "/var/www"
                }
            },
            "destination": {
                "type": SystemType.AWS_S3.value,
                "host": "s3.amazonaws.com",
                "authentication": {
                    "type": AuthType.AWS_IAM.value
                },
                "paths": {
                    "root_path": "/"
                }
            },
            "transfer": {
                "method": TransferMethod.AWS_S3.value
            },
            "options": {
                "backup_before": True
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(preset_data, f)
            temp_path = f.name
        
        try:
            preset_key = preset_manager.import_preset(temp_path)
            assert preset_key is not None
            assert preset_key == "imported-preset"
            
            # Verify the preset was imported
            imported_config = preset_manager.get_preset_config(preset_key)
            assert imported_config is not None
            assert imported_config["name"] == "Imported Preset"
            assert imported_config["custom"] is True
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_preset_with_custom_name(self, preset_manager):
        """Test importing a preset with a custom name."""
        preset_data = {
            "name": "Original Name",
            "source": {
                "type": SystemType.STATIC_SITE.value,
                "host": "test.com",
                "authentication": {"type": AuthType.PASSWORD.value},
                "paths": {"root_path": "/"}
            },
            "destination": {
                "type": SystemType.AWS_S3.value,
                "host": "s3.amazonaws.com",
                "authentication": {"type": AuthType.AWS_IAM.value},
                "paths": {"root_path": "/"}
            },
            "transfer": {"method": TransferMethod.AWS_S3.value},
            "options": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(preset_data, f)
            temp_path = f.name
        
        try:
            preset_key = preset_manager.import_preset(temp_path, "Custom Import Name")
            assert preset_key == "custom-import-name"
            
            imported_config = preset_manager.get_preset_config(preset_key)
            assert imported_config["name"] == "Custom Import Name"
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_import_invalid_preset(self, preset_manager):
        """Test importing an invalid preset file."""
        # Create invalid preset data (missing required keys)
        invalid_data = {
            "name": "Invalid Preset",
            "source": {"type": "wordpress"}
            # Missing destination, transfer, options
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_data, f)
            temp_path = f.name
        
        try:
            preset_key = preset_manager.import_preset(temp_path)
            assert preset_key is None
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_merge_overrides_simple(self, preset_manager):
        """Test merging simple overrides."""
        original = {"name": "Original", "value": 1}
        overrides = {"name": "Updated", "new_key": "new_value"}
        
        result = preset_manager._merge_overrides(original, overrides)
        
        assert result["name"] == "Updated"
        assert result["value"] == 1
        assert result["new_key"] == "new_value"
    
    def test_merge_overrides_nested(self, preset_manager):
        """Test merging nested overrides."""
        original = {
            "config": {
                "host": "original.com",
                "port": 80,
                "nested": {"value": 1}
            }
        }
        overrides = {
            "config": {
                "host": "updated.com",
                "nested": {"value": 2, "new": "added"}
            }
        }
        
        result = preset_manager._merge_overrides(original, overrides)
        
        assert result["config"]["host"] == "updated.com"
        assert result["config"]["port"] == 80  # Preserved
        assert result["config"]["nested"]["value"] == 2  # Updated
        assert result["config"]["nested"]["new"] == "added"  # Added


class TestPresetManagerIntegration:
    """Integration tests for PresetManager."""
    
    @pytest.fixture
    def preset_manager(self):
        return PresetManager()
    
    def test_wordpress_to_s3_preset_complete_flow(self, preset_manager):
        """Test complete flow with WordPress to S3 preset."""
        # Get the preset
        config = preset_manager.create_migration_config_from_preset(
            PresetType.WORDPRESS_MYSQL_TO_S3.value
        )
        
        assert config is not None
        assert config.source.type == SystemType.WORDPRESS
        assert config.destination.type == SystemType.AWS_S3
        assert config.transfer.method == TransferMethod.AWS_S3
        
        # Test with overrides
        overrides = {
            "source": {"host": "my-wordpress.com"},
            "destination": {
                "cloud_config": {"bucket_name": "my-custom-bucket"}
            }
        }
        
        custom_config = preset_manager.create_migration_config_from_preset(
            PresetType.WORDPRESS_MYSQL_TO_S3.value,
            overrides=overrides
        )
        
        assert custom_config.source.host == "my-wordpress.com"
        assert custom_config.destination.cloud_config.bucket_name == "my-custom-bucket"
    
    def test_preset_roundtrip_export_import(self, preset_manager):
        """Test exporting and importing a preset."""
        original_preset_key = PresetType.STATIC_TO_S3.value
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Export
            export_result = preset_manager.export_preset(original_preset_key, temp_path)
            assert export_result is True
            
            # Import with new name
            imported_key = preset_manager.import_preset(temp_path, "Imported Static to S3")
            assert imported_key is not None
            
            # Compare configurations
            original_config = preset_manager.create_migration_config_from_preset(original_preset_key)
            imported_config = preset_manager.create_migration_config_from_preset(imported_key)
            
            assert original_config.source.type == imported_config.source.type
            assert original_config.destination.type == imported_config.destination.type
            assert original_config.transfer.method == imported_config.transfer.method
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_custom_preset_lifecycle(self, preset_manager):
        """Test complete lifecycle of custom preset."""
        # Create a migration config
        migration_config = MigrationConfig(
            name="Lifecycle Test",
            description="Testing preset lifecycle",
            source=SystemConfig(
                type=SystemType.DJANGO,
                host="django-app.com",
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
                host="k8s.cluster.com",
                authentication=AuthConfig(type=AuthType.API_KEY, api_key="k8s-token"),
                paths=PathConfig(root_path="/app")
            ),
            transfer=TransferConfig(method=TransferMethod.KUBERNETES_VOLUME),
            options=MigrationOptions(backup_before=True, verify_after=True)
        )
        
        # Save as custom preset
        preset_key = preset_manager.save_custom_preset(
            "Django to K8s",
            migration_config,
            "Django application to Kubernetes migration"
        )
        
        # Verify it appears in available presets
        available_presets = preset_manager.get_available_presets()
        preset_keys = [key for key, _, _ in available_presets]
        assert preset_key in preset_keys
        
        # Create new config from preset
        recreated_config = preset_manager.create_migration_config_from_preset(preset_key)
        assert recreated_config.name == "Django to K8s"
        assert recreated_config.source.type == SystemType.DJANGO
        assert recreated_config.destination.type == SystemType.KUBERNETES_POD
        
        # Delete the preset
        delete_result = preset_manager.delete_custom_preset(preset_key)
        assert delete_result is True
        
        # Verify it's gone
        final_presets = preset_manager.get_available_presets()
        final_keys = [key for key, _, _ in final_presets]
        assert preset_key not in final_keys