"""
Configuration persistence and validation system for the Migration Assistant.

This module provides functionality to save/load migration configurations
in YAML/TOML format with comprehensive validation and error handling.
"""

import os
import yaml
import toml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from migration_assistant.models.config import MigrationConfig


class ConfigurationPersistence:
    """Handles saving and loading migration configurations."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration persistence.
        
        Args:
            config_dir: Directory to store configuration files. 
                       Defaults to ~/.migration-assistant/configs
        """
        self.console = Console()
        
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".migration-assistant" / "configs"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def save_configuration(
        self, 
        config: MigrationConfig, 
        filename: Optional[str] = None,
        format: str = "yaml"
    ) -> str:
        """
        Save migration configuration to file.
        
        Args:
            config: MigrationConfig to save
            filename: Optional filename. If not provided, generates from config name
            format: File format ('yaml' or 'toml')
            
        Returns:
            Path to saved configuration file
            
        Raises:
            ValueError: If format is not supported
            IOError: If file cannot be written
        """
        if format not in ["yaml", "toml"]:
            raise ValueError(f"Unsupported format: {format}. Use 'yaml' or 'toml'")
        
        # Generate filename if not provided
        if not filename:
            safe_name = self._sanitize_filename(config.name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.{format}"
        
        # Ensure filename has correct extension
        if not filename.endswith(f".{format}"):
            filename = f"{filename}.{format}"
        
        file_path = self.config_dir / filename
        
        # Convert config to dictionary
        config_dict = self._config_to_dict(config)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if format == "yaml":
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                elif format == "toml":
                    toml.dump(config_dict, f)
            
            self.console.print(f"[green]Configuration saved to: {file_path}[/green]")
            return str(file_path)
            
        except Exception as e:
            raise IOError(f"Failed to save configuration: {e}")
    
    def load_configuration(self, file_path: str) -> MigrationConfig:
        """
        Load migration configuration from file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            MigrationConfig instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid or unsupported
            ValidationError: If configuration is invalid
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        # Determine format from extension
        if path.suffix.lower() == '.yaml' or path.suffix.lower() == '.yml':
            format = 'yaml'
        elif path.suffix.lower() == '.toml':
            format = 'toml'
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if format == 'yaml':
                    config_dict = yaml.safe_load(f)
                elif format == 'toml':
                    config_dict = toml.load(f)
            
            if not config_dict:
                raise ValueError("Configuration file is empty")
            
            # Validate and create MigrationConfig
            return self._dict_to_config(config_dict)
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
        except toml.TomlDecodeError as e:
            raise ValueError(f"Invalid TOML format: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
    
    def list_configurations(self) -> List[Dict[str, Any]]:
        """
        List all saved configurations.
        
        Returns:
            List of configuration metadata dictionaries
        """
        configs = []
        
        for file_path in self.config_dir.glob("*.yaml"):
            configs.append(self._get_config_metadata(file_path))
        
        for file_path in self.config_dir.glob("*.yml"):
            configs.append(self._get_config_metadata(file_path))
        
        for file_path in self.config_dir.glob("*.toml"):
            configs.append(self._get_config_metadata(file_path))
        
        # Sort by modification time (newest first)
        configs.sort(key=lambda x: x['modified'], reverse=True)
        
        return configs
    
    def delete_configuration(self, filename: str) -> bool:
        """
        Delete a saved configuration.
        
        Args:
            filename: Name of configuration file to delete
            
        Returns:
            True if deleted successfully, False if file not found
        """
        file_path = self.config_dir / filename
        
        if file_path.exists():
            try:
                file_path.unlink()
                self.console.print(f"[green]Configuration deleted: {filename}[/green]")
                return True
            except Exception as e:
                self.console.print(f"[red]Failed to delete configuration: {e}[/red]")
                return False
        else:
            self.console.print(f"[yellow]Configuration not found: {filename}[/yellow]")
            return False
    
    def validate_configuration_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a configuration file without loading it completely.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "metadata": {}
        }
        
        try:
            # Check if file exists
            path = Path(file_path)
            if not path.exists():
                result["errors"].append(f"File not found: {file_path}")
                return result
            
            # Check file format
            if path.suffix.lower() not in ['.yaml', '.yml', '.toml']:
                result["errors"].append(f"Unsupported file format: {path.suffix}")
                return result
            
            # Try to parse the file
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    if path.suffix.lower() in ['.yaml', '.yml']:
                        config_dict = yaml.safe_load(f)
                    else:
                        config_dict = toml.load(f)
            except Exception as e:
                result["errors"].append(f"Failed to parse file: {e}")
                return result
            
            if not config_dict:
                result["errors"].append("Configuration file is empty")
                return result
            
            # Validate required fields
            required_fields = ["name", "source", "destination", "transfer", "options"]
            missing_fields = [field for field in required_fields if field not in config_dict]
            
            if missing_fields:
                result["errors"].extend([f"Missing required field: {field}" for field in missing_fields])
            
            # Try to create MigrationConfig to validate structure
            try:
                migration_config = self._dict_to_config(config_dict)
                result["valid"] = True
                result["metadata"] = {
                    "name": migration_config.name,
                    "description": migration_config.description,
                    "source_type": migration_config.source.type.value,
                    "destination_type": migration_config.destination.type.value,
                    "created_at": migration_config.created_at.isoformat() if migration_config.created_at else None
                }
            except PydanticValidationError as e:
                result["errors"].extend([f"Validation error: {error['msg']}" for error in e.errors()])
            except Exception as e:
                result["errors"].append(f"Configuration validation failed: {e}")
            
            # Add warnings for deprecated or unusual configurations
            if config_dict.get("options", {}).get("dry_run"):
                result["warnings"].append("Configuration has dry_run enabled")
            
            if not config_dict.get("options", {}).get("backup_before", True):
                result["warnings"].append("Backup before migration is disabled")
            
        except Exception as e:
            result["errors"].append(f"Unexpected error during validation: {e}")
        
        return result
    
    def show_configuration_summary(self, config: MigrationConfig) -> None:
        """
        Display a formatted summary of the configuration.
        
        Args:
            config: MigrationConfig to display
        """
        # Basic information table
        basic_table = Table(title="Migration Configuration", box=box.ROUNDED)
        basic_table.add_column("Setting", style="cyan", width=20)
        basic_table.add_column("Value", style="green")
        
        basic_table.add_row("Name", config.name)
        if config.description:
            basic_table.add_row("Description", config.description)
        basic_table.add_row("Created", config.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        
        self.console.print(basic_table)
        self.console.print()
        
        # Source and destination table
        systems_table = Table(title="Source & Destination", box=box.MINIMAL)
        systems_table.add_column("", style="cyan", width=15)
        systems_table.add_column("Source", style="blue")
        systems_table.add_column("Destination", style="green")
        
        systems_table.add_row("Type", config.source.type.value, config.destination.type.value)
        systems_table.add_row("Host", config.source.host, config.destination.host)
        systems_table.add_row("Auth Type", config.source.authentication.type.value, config.destination.authentication.type.value)
        
        if config.source.database:
            db_source = f"{config.source.database.type.value} ({config.source.database.database_name})"
        else:
            db_source = "None"
        
        if config.destination.database:
            db_dest = f"{config.destination.database.type.value} ({config.destination.database.database_name})"
        else:
            db_dest = "None"
        
        systems_table.add_row("Database", db_source, db_dest)
        
        self.console.print(systems_table)
        self.console.print()
        
        # Transfer and options
        details_table = Table(title="Transfer & Options", box=box.MINIMAL)
        details_table.add_column("Setting", style="cyan", width=20)
        details_table.add_column("Value", style="yellow")
        
        details_table.add_row("Transfer Method", config.transfer.method.value)
        details_table.add_row("Parallel Transfers", str(config.transfer.parallel_transfers))
        details_table.add_row("Compression", "Yes" if config.transfer.compression_enabled else "No")
        details_table.add_row("Verify Checksums", "Yes" if config.transfer.verify_checksums else "No")
        details_table.add_row("Maintenance Mode", "Yes" if config.options.maintenance_mode else "No")
        details_table.add_row("Backup Before", "Yes" if config.options.backup_before else "No")
        details_table.add_row("Rollback on Failure", "Yes" if config.options.rollback_on_failure else "No")
        
        self.console.print(details_table)
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string to be safe for use as a filename.
        
        Args:
            name: Original name
            
        Returns:
            Sanitized filename
        """
        # Replace spaces and special characters
        safe_name = name.lower()
        safe_name = safe_name.replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
        
        # Limit length
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        
        return safe_name or "migration_config"
    
    def _config_to_dict(self, config: MigrationConfig) -> Dict[str, Any]:
        """
        Convert MigrationConfig to dictionary for serialization.
        
        Args:
            config: MigrationConfig instance
            
        Returns:
            Dictionary representation
        """
        # Use mode='json' to ensure enums are serialized as strings
        return {
            "name": config.name,
            "description": config.description,
            "source": config.source.model_dump(mode='json'),
            "destination": config.destination.model_dump(mode='json'),
            "transfer": config.transfer.model_dump(mode='json'),
            "options": config.options.model_dump(mode='json'),
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
            "created_by": config.created_by,
            "tenant_id": config.tenant_id,
            "tags": config.tags,
            "metadata": config.metadata
        }
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> MigrationConfig:
        """
        Convert dictionary to MigrationConfig with validation.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            MigrationConfig instance
            
        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            return MigrationConfig(**config_dict)
        except PydanticValidationError as e:
            # Re-raise with more context
            error_details = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error['loc'])
                error_details.append(f"{field}: {error['msg']}")
            
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(error_details))
    
    def _get_config_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Get metadata for a configuration file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            Metadata dictionary
        """
        stat = file_path.stat()
        
        metadata = {
            "filename": file_path.name,
            "path": str(file_path),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "format": file_path.suffix.lower().lstrip('.'),
            "name": None,
            "description": None,
            "valid": False
        }
        
        # Try to extract basic info without full validation
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() in ['.yaml', '.yml']:
                    config_dict = yaml.safe_load(f)
                else:
                    config_dict = toml.load(f)
            
            if config_dict:
                metadata["name"] = config_dict.get("name")
                metadata["description"] = config_dict.get("description")
                metadata["valid"] = True
                
        except Exception:
            # If we can't parse the file, leave name/description as None
            pass
        
        return metadata


class ConfigurationValidator:
    """Advanced configuration validation with detailed error reporting."""
    
    def __init__(self):
        self.console = Console()
    
    def validate_configuration(self, config: MigrationConfig) -> Dict[str, Any]:
        """
        Perform comprehensive validation of a migration configuration.
        
        Args:
            config: MigrationConfig to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Basic validation
        self._validate_basic_info(config, result)
        
        # System compatibility validation
        self._validate_system_compatibility(config, result)
        
        # Transfer method validation
        self._validate_transfer_method(config, result)
        
        # Security validation
        self._validate_security_settings(config, result)
        
        # Performance validation
        self._validate_performance_settings(config, result)
        
        # Set overall validity
        result["valid"] = len(result["errors"]) == 0
        
        return result
    
    def _validate_basic_info(self, config: MigrationConfig, result: Dict[str, Any]) -> None:
        """Validate basic configuration information."""
        if not config.name or len(config.name.strip()) < 3:
            result["errors"].append("Migration name must be at least 3 characters long")
        
        if config.name and len(config.name) > 100:
            result["warnings"].append("Migration name is very long (>100 characters)")
        
        if not config.description:
            result["suggestions"].append("Consider adding a description for better documentation")
    
    def _validate_system_compatibility(self, config: MigrationConfig, result: Dict[str, Any]) -> None:
        """Validate source and destination system compatibility."""
        source_type = config.source.type
        dest_type = config.destination.type
        
        # Check for potentially problematic combinations
        if source_type == dest_type and config.source.host == config.destination.host:
            result["warnings"].append("Source and destination are the same system - ensure different paths/databases")
        
        # Database compatibility checks
        if config.source.database and config.destination.database:
            if config.source.database.type != config.destination.database.type:
                result["warnings"].append(
                    f"Database types differ: {config.source.database.type.value} -> {config.destination.database.type.value}. "
                    "Ensure compatibility and data conversion."
                )
        
        # Cloud-specific validations
        if dest_type.value.endswith('_s3') or dest_type.value.endswith('_storage') or dest_type.value.endswith('_blob'):
            if not config.destination.cloud_config:
                result["errors"].append(f"Cloud configuration required for {dest_type.value}")
    
    def _validate_transfer_method(self, config: MigrationConfig, result: Dict[str, Any]) -> None:
        """Validate transfer method configuration."""
        transfer = config.transfer
        
        # Check parallel transfers
        if transfer.parallel_transfers > 16:
            result["warnings"].append("Very high parallel transfer count may overwhelm the system")
        elif transfer.parallel_transfers < 2:
            result["suggestions"].append("Consider increasing parallel transfers for better performance")
        
        # Check compression settings
        if transfer.compression_enabled and transfer.method.value in ['aws_s3', 'google_cloud_storage']:
            result["suggestions"].append("Cloud storage often handles compression automatically")
        
        # Check method compatibility with system types
        source_type = config.source.type
        dest_type = config.destination.type
        method = transfer.method
        
        if method.value.startswith('aws_') and dest_type.value != 'aws_s3':
            result["warnings"].append("AWS transfer method selected but destination is not AWS S3")
        
        if method.value == 'kubernetes_volume' and dest_type.value != 'kubernetes_pod':
            result["errors"].append("Kubernetes volume transfer requires Kubernetes destination")
    
    def _validate_security_settings(self, config: MigrationConfig, result: Dict[str, Any]) -> None:
        """Validate security-related settings."""
        # Check authentication methods
        if config.source.authentication.type.value == 'password':
            result["suggestions"].append("Consider using SSH keys instead of passwords for better security")
        
        if config.destination.authentication.type.value == 'password':
            result["suggestions"].append("Consider using SSH keys for destination authentication")
        
        # Check backup settings
        if not config.options.backup_before:
            result["warnings"].append("Backup before migration is disabled - this increases risk")
        
        if not config.options.rollback_on_failure:
            result["warnings"].append("Automatic rollback is disabled - manual recovery may be needed")
    
    def _validate_performance_settings(self, config: MigrationConfig, result: Dict[str, Any]) -> None:
        """Validate performance-related settings."""
        # Check if Go acceleration is available for supported methods
        if (config.transfer.method.value in ['hybrid_sync', 'rsync'] and 
            not config.transfer.use_go_acceleration):
            result["suggestions"].append("Consider enabling Go acceleration for better performance")
        
        # Check verification settings
        if not config.transfer.verify_checksums:
            result["warnings"].append("Checksum verification is disabled - data integrity cannot be guaranteed")
        
        # Check maintenance mode for production systems
        if not config.options.maintenance_mode:
            result["suggestions"].append("Consider enabling maintenance mode for production systems")
    
    def display_validation_results(self, results: Dict[str, Any]) -> None:
        """
        Display validation results in a formatted way.
        
        Args:
            results: Validation results dictionary
        """
        if results["valid"]:
            self.console.print(Panel(
                "[green]✓ Configuration is valid[/green]",
                title="Validation Results",
                border_style="green"
            ))
        else:
            self.console.print(Panel(
                "[red]✗ Configuration has errors[/red]",
                title="Validation Results",
                border_style="red"
            ))
        
        # Display errors
        if results["errors"]:
            self.console.print("\n[bold red]Errors:[/bold red]")
            for error in results["errors"]:
                self.console.print(f"  • [red]{error}[/red]")
        
        # Display warnings
        if results["warnings"]:
            self.console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in results["warnings"]:
                self.console.print(f"  • [yellow]{warning}[/yellow]")
        
        # Display suggestions
        if results["suggestions"]:
            self.console.print("\n[bold blue]Suggestions:[/bold blue]")
            for suggestion in results["suggestions"]:
                self.console.print(f"  • [blue]{suggestion}[/blue]")
        
        self.console.print()