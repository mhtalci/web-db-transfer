"""
Interactive CLI configuration collector for the Migration Assistant.

This module provides an interactive CLI interface using Click and prompt_toolkit
for collecting migration parameters with Rich-formatted output and validation.
"""

from typing import Dict, Any, Optional, List, Tuple
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.validation import Validator, ValidationError
from pydantic import ValidationError as PydanticValidationError

from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, AuthConfig, PathConfig, DatabaseConfig,
    CloudConfig, ControlPanelConfig, TransferConfig, MigrationOptions,
    SystemType, AuthType, DatabaseType, TransferMethod, ControlPanelType
)
from migration_assistant.cli.preset_manager import PresetManager


class ConfigurationCollector:
    """Interactive CLI configuration collector with Rich formatting."""
    
    def __init__(self):
        self.console = Console()
        self.config_data: Dict[str, Any] = {}
        self.preset_manager = PresetManager()
    
    def collect_configuration(self, preset_key: Optional[str] = None) -> MigrationConfig:
        """
        Main method to collect complete migration configuration interactively.
        
        Args:
            preset_key: Optional preset to use as starting point
        
        Returns:
            MigrationConfig: Complete validated migration configuration
        """
        self._show_welcome()
        
        # Check if user wants to use a preset
        if not preset_key and self._offer_preset_selection():
            preset_key = self._select_preset()
        
        # If using a preset, load and customize it
        if preset_key:
            return self._customize_preset_configuration(preset_key)
        
        # Otherwise, collect configuration from scratch
        return self._collect_full_configuration()
    
    def _collect_full_configuration(self) -> MigrationConfig:
        """Collect complete configuration from scratch."""
        # Collect basic migration info
        self._collect_basic_info()
        
        # Collect source system configuration
        self.console.rule("[bold blue]Source System Configuration")
        source_config = self._collect_system_config("source")
        
        # Collect destination system configuration
        self.console.rule("[bold green]Destination System Configuration")
        destination_config = self._collect_system_config("destination")
        
        # Collect transfer configuration
        self.console.rule("[bold yellow]Transfer Configuration")
        transfer_config = self._collect_transfer_config()
        
        # Collect migration options
        self.console.rule("[bold magenta]Migration Options")
        options_config = self._collect_migration_options()
        
        # Create and validate final configuration
        try:
            migration_config = MigrationConfig(
                name=self.config_data["name"],
                description=self.config_data.get("description"),
                source=source_config,
                destination=destination_config,
                transfer=transfer_config,
                options=options_config
            )
            
            self._show_configuration_summary(migration_config)
            return migration_config
            
        except PydanticValidationError as e:
            self.console.print(f"[red]Configuration validation failed: {e}[/red]")
            raise
    
    def _show_welcome(self) -> None:
        """Display welcome message and instructions."""
        welcome_text = Text()
        welcome_text.append("Welcome to the Migration Assistant Configuration Wizard!\n\n", style="bold blue")
        welcome_text.append("This wizard will guide you through configuring your migration.\n", style="dim")
        welcome_text.append("You can press Ctrl+C at any time to cancel.\n", style="dim")
        
        panel = Panel(
            welcome_text,
            title="Migration Configuration Wizard",
            border_style="blue",
            box=box.ROUNDED
        )
        self.console.print(panel)
        self.console.print()
    
    def _collect_basic_info(self) -> None:
        """Collect basic migration information."""
        self.console.print("[bold]Basic Migration Information[/bold]")
        
        # Migration name (required)
        name = Prompt.ask(
            "[cyan]Migration name[/cyan]",
            console=self.console
        )
        self.config_data["name"] = name
        
        # Optional description
        description = Prompt.ask(
            "[cyan]Description (optional)[/cyan]",
            default="",
            console=self.console
        )
        if description:
            self.config_data["description"] = description
        
        self.console.print()
    
    def _collect_system_config(self, system_role: str) -> SystemConfig:
        """
        Collect system configuration for source or destination.
        
        Args:
            system_role: Either "source" or "destination"
            
        Returns:
            SystemConfig: Validated system configuration
        """
        self.console.print(f"[bold]Configuring {system_role} system[/bold]")
        
        # System type selection
        system_type = self._select_system_type(system_role)
        
        # Host configuration
        host = self._collect_host_info(system_role)
        
        # Authentication configuration
        auth_config = self._collect_auth_config(system_role, system_type)
        
        # Path configuration
        path_config = self._collect_path_config(system_role, system_type)
        
        # Database configuration (if needed)
        database_config = None
        if self._needs_database_config(system_type):
            database_config = self._collect_database_config(system_role)
        
        # Cloud configuration (if needed)
        cloud_config = None
        if self._needs_cloud_config(system_type):
            cloud_config = self._collect_cloud_config(system_role)
        
        # Control panel configuration (if needed)
        control_panel_config = None
        if self._needs_control_panel_config(system_type):
            control_panel_config = self._collect_control_panel_config(system_role)
        
        return SystemConfig(
            type=system_type,
            host=host["host"],
            port=host.get("port"),
            authentication=auth_config,
            paths=path_config,
            database=database_config,
            cloud_config=cloud_config,
            control_panel=control_panel_config
        )
    
    def _select_system_type(self, system_role: str) -> SystemType:
        """
        Display system type selection with Rich formatting.
        
        Args:
            system_role: Either "source" or "destination"
            
        Returns:
            SystemType: Selected system type
        """
        # Group system types by category for better display
        system_categories = {
            "Web Applications": [
                ("wordpress", "WordPress CMS"),
                ("drupal", "Drupal CMS"),
                ("joomla", "Joomla CMS"),
                ("django", "Django Framework"),
                ("flask", "Flask Framework"),
                ("fastapi", "FastAPI Framework"),
                ("laravel", "Laravel Framework"),
                ("rails", "Ruby on Rails"),
                ("spring_boot", "Spring Boot"),
                ("nextjs", "Next.js Framework"),
                ("static_site", "Static Website")
            ],
            "Cloud Storage": [
                ("aws_s3", "Amazon S3"),
                ("google_cloud_storage", "Google Cloud Storage"),
                ("azure_blob", "Azure Blob Storage")
            ],
            "Containers": [
                ("docker_container", "Docker Container"),
                ("kubernetes_pod", "Kubernetes Pod")
            ],
            "Control Panels": [
                ("cpanel", "cPanel Hosting"),
                ("directadmin", "DirectAdmin"),
                ("plesk", "Plesk Panel")
            ]
        }
        
        # Create selection table
        table = Table(title=f"Select {system_role.title()} System Type", box=box.ROUNDED)
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Category", style="magenta", width=15)
        table.add_column("System Type", style="green")
        table.add_column("Description", style="dim")
        
        options = []
        option_num = 1
        
        for category, systems in system_categories.items():
            for system_key, system_desc in systems:
                table.add_row(
                    str(option_num),
                    category,
                    system_key.replace("_", " ").title(),
                    system_desc
                )
                options.append(system_key)
                option_num += 1
        
        self.console.print(table)
        self.console.print()
        
        # Get user selection
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select {system_role} system type (1-{len(options)})[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(options):
                    selected_type = SystemType(options[choice_idx])
                    self.console.print(f"[green]Selected: {selected_type.value}[/green]")
                    self.console.print()
                    return selected_type
                else:
                    self.console.print("[red]Invalid selection. Please try again.[/red]")
            except (ValueError, KeyError):
                self.console.print("[red]Invalid selection. Please enter a number.[/red]")
    
    def _collect_host_info(self, system_role: str) -> Dict[str, Any]:
        """Collect host and port information."""
        self.console.print(f"[bold]Host Configuration for {system_role}[/bold]")
        
        # Host validation
        class HostValidator(Validator):
            def validate(self, document):
                text = document.text.strip()
                if not text:
                    raise ValidationError(message="Host cannot be empty")
                # Basic validation - could be enhanced
                if len(text) < 3:
                    raise ValidationError(message="Host seems too short")
        
        host = prompt(
            f"Enter {system_role} host (e.g., example.com, 192.168.1.10): ",
            validator=HostValidator()
        ).strip()
        
        # Optional port
        port_input = Prompt.ask(
            "[cyan]Port (optional, press Enter for default)[/cyan]",
            default="",
            console=self.console
        )
        
        result = {"host": host}
        if port_input:
            try:
                port = int(port_input)
                if 1 <= port <= 65535:
                    result["port"] = port
                else:
                    self.console.print("[yellow]Invalid port range, using default[/yellow]")
            except ValueError:
                self.console.print("[yellow]Invalid port format, using default[/yellow]")
        
        self.console.print()
        return result
    
    def _collect_auth_config(self, system_role: str, system_type: SystemType) -> AuthConfig:
        """Collect authentication configuration."""
        self.console.print(f"[bold]Authentication for {system_role}[/bold]")
        
        # Show available auth types
        auth_options = [
            ("password", "Username/Password"),
            ("ssh_key", "SSH Key"),
            ("api_key", "API Key"),
            ("oauth2", "OAuth2"),
            ("jwt", "JWT Token")
        ]
        
        if system_type in [SystemType.AWS_S3, SystemType.GOOGLE_CLOUD_STORAGE, SystemType.AZURE_BLOB]:
            auth_options.extend([
                ("aws_iam", "AWS IAM"),
                ("google_service_account", "Google Service Account"),
                ("azure_ad", "Azure AD")
            ])
        
        # Display auth options
        table = Table(title="Authentication Methods", box=box.MINIMAL)
        table.add_column("Option", style="cyan")
        table.add_column("Method", style="green")
        
        for i, (auth_key, auth_desc) in enumerate(auth_options, 1):
            table.add_row(str(i), auth_desc)
        
        self.console.print(table)
        
        # Get selection
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select authentication method (1-{len(auth_options)})[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(auth_options):
                    auth_type = AuthType(auth_options[choice_idx][0])
                    break
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except (ValueError, KeyError):
                self.console.print("[red]Invalid selection. Please enter a number.[/red]")
        
        # Collect auth details based on type
        auth_data = {"type": auth_type}
        
        if auth_type == AuthType.PASSWORD:
            auth_data["username"] = Prompt.ask("[cyan]Username[/cyan]", console=self.console)
            auth_data["password"] = Prompt.ask("[cyan]Password[/cyan]", password=True, console=self.console)
        
        elif auth_type == AuthType.SSH_KEY:
            auth_data["username"] = Prompt.ask("[cyan]Username[/cyan]", console=self.console)
            auth_data["ssh_key_path"] = Prompt.ask("[cyan]SSH key path[/cyan]", console=self.console)
            passphrase = Prompt.ask("[cyan]SSH key passphrase (optional)[/cyan]", password=True, default="", console=self.console)
            if passphrase:
                auth_data["ssh_key_passphrase"] = passphrase
        
        elif auth_type == AuthType.API_KEY:
            auth_data["api_key"] = Prompt.ask("[cyan]API Key[/cyan]", password=True, console=self.console)
            api_secret = Prompt.ask("[cyan]API Secret (optional)[/cyan]", password=True, default="", console=self.console)
            if api_secret:
                auth_data["api_secret"] = api_secret
        
        elif auth_type == AuthType.JWT:
            auth_data["token"] = Prompt.ask("[cyan]JWT Token[/cyan]", password=True, console=self.console)
        
        # Add more auth type handlers as needed
        
        self.console.print()
        return AuthConfig(**auth_data)
    
    def _collect_path_config(self, system_role: str, system_type: SystemType) -> PathConfig:
        """Collect path configuration."""
        self.console.print(f"[bold]Path Configuration for {system_role}[/bold]")
        
        root_path = Prompt.ask(
            "[cyan]Root path[/cyan]",
            default="/var/www/html" if system_type in [SystemType.WORDPRESS, SystemType.DRUPAL] else "/",
            console=self.console
        )
        
        path_data = {"root_path": root_path}
        
        # Optional paths
        web_root = Prompt.ask("[cyan]Web root (optional)[/cyan]", default="", console=self.console)
        if web_root:
            path_data["web_root"] = web_root
        
        self.console.print()
        return PathConfig(**path_data)
    
    def _collect_database_config(self, system_role: str) -> DatabaseConfig:
        """Collect database configuration."""
        self.console.print(f"[bold]Database Configuration for {system_role}[/bold]")
        
        # Database type selection
        db_types = [
            ("mysql", "MySQL/MariaDB"),
            ("postgresql", "PostgreSQL"),
            ("sqlite", "SQLite"),
            ("mongodb", "MongoDB"),
            ("redis", "Redis")
        ]
        
        table = Table(title="Database Types", box=box.MINIMAL)
        table.add_column("Option", style="cyan")
        table.add_column("Database", style="green")
        
        for i, (db_key, db_desc) in enumerate(db_types, 1):
            table.add_row(str(i), db_desc)
        
        self.console.print(table)
        
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select database type (1-{len(db_types)})[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(db_types):
                    db_type = DatabaseType(db_types[choice_idx][0])
                    break
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except (ValueError, KeyError):
                self.console.print("[red]Invalid selection. Please enter a number.[/red]")
        
        # Collect database details
        db_data = {"type": db_type}
        
        if db_type != DatabaseType.SQLITE:
            db_data["host"] = Prompt.ask("[cyan]Database host[/cyan]", default="localhost", console=self.console)
            
            # Port with default based on database type
            default_ports = {
                DatabaseType.MYSQL: 3306,
                DatabaseType.POSTGRESQL: 5432,
                DatabaseType.MONGODB: 27017,
                DatabaseType.REDIS: 6379
            }
            default_port = default_ports.get(db_type, 3306)
            
            port_input = Prompt.ask(
                f"[cyan]Database port[/cyan]",
                default=str(default_port),
                console=self.console
            )
            try:
                db_data["port"] = int(port_input)
            except ValueError:
                db_data["port"] = default_port
            
            db_data["database_name"] = Prompt.ask("[cyan]Database name[/cyan]", console=self.console)
            db_data["username"] = Prompt.ask("[cyan]Database username[/cyan]", console=self.console)
            db_data["password"] = Prompt.ask("[cyan]Database password[/cyan]", password=True, console=self.console)
        
        self.console.print()
        return DatabaseConfig(**db_data)
    
    def _collect_cloud_config(self, system_role: str) -> CloudConfig:
        """Collect cloud configuration."""
        self.console.print(f"[bold]Cloud Configuration for {system_role}[/bold]")
        
        provider = Prompt.ask("[cyan]Cloud provider (aws/gcp/azure)[/cyan]", console=self.console)
        region = Prompt.ask("[cyan]Region[/cyan]", console=self.console)
        
        cloud_data = {
            "provider": provider,
            "region": region
        }
        
        if provider.lower() == "aws":
            cloud_data["access_key_id"] = Prompt.ask("[cyan]AWS Access Key ID[/cyan]", console=self.console)
            cloud_data["secret_access_key"] = Prompt.ask("[cyan]AWS Secret Access Key[/cyan]", password=True, console=self.console)
            bucket = Prompt.ask("[cyan]S3 Bucket name (optional)[/cyan]", default="", console=self.console)
            if bucket:
                cloud_data["bucket_name"] = bucket
        
        self.console.print()
        return CloudConfig(**cloud_data)
    
    def _collect_control_panel_config(self, system_role: str) -> ControlPanelConfig:
        """Collect control panel configuration."""
        self.console.print(f"[bold]Control Panel Configuration for {system_role}[/bold]")
        
        # Control panel type selection
        cp_types = [
            ("cpanel", "cPanel"),
            ("directadmin", "DirectAdmin"),
            ("plesk", "Plesk")
        ]
        
        table = Table(title="Control Panel Types", box=box.MINIMAL)
        table.add_column("Option", style="cyan")
        table.add_column("Panel", style="green")
        
        for i, (cp_key, cp_desc) in enumerate(cp_types, 1):
            table.add_row(str(i), cp_desc)
        
        self.console.print(table)
        
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select control panel type (1-{len(cp_types)})[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(cp_types):
                    cp_type = ControlPanelType(cp_types[choice_idx][0])
                    break
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except (ValueError, KeyError):
                self.console.print("[red]Invalid selection. Please enter a number.[/red]")
        
        host = Prompt.ask("[cyan]Control panel host[/cyan]", console=self.console)
        username = Prompt.ask("[cyan]Username[/cyan]", console=self.console)
        
        cp_data = {
            "type": cp_type,
            "host": host,
            "username": username
        }
        
        # Authentication method
        if Confirm.ask("[cyan]Use API token instead of password?[/cyan]", console=self.console):
            cp_data["api_token"] = Prompt.ask("[cyan]API Token[/cyan]", password=True, console=self.console)
        else:
            cp_data["password"] = Prompt.ask("[cyan]Password[/cyan]", password=True, console=self.console)
        
        self.console.print()
        return ControlPanelConfig(**cp_data)
    
    def _collect_transfer_config(self) -> TransferConfig:
        """Collect transfer configuration."""
        self.console.print("[bold]Transfer Method Configuration[/bold]")
        
        # Transfer method selection
        transfer_methods = [
            ("ssh_scp", "SSH/SCP"),
            ("ssh_sftp", "SSH/SFTP"),
            ("rsync", "Rsync"),
            ("ftp", "FTP"),
            ("ftps", "FTPS"),
            ("aws_s3", "AWS S3 Sync"),
            ("google_cloud_storage", "Google Cloud Storage"),
            ("azure_blob", "Azure Blob Storage"),
            ("hybrid_sync", "Hybrid Sync (Go-accelerated)")
        ]
        
        table = Table(title="Transfer Methods", box=box.MINIMAL)
        table.add_column("Option", style="cyan")
        table.add_column("Method", style="green")
        
        for i, (method_key, method_desc) in enumerate(transfer_methods, 1):
            table.add_row(str(i), method_desc)
        
        self.console.print(table)
        
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select transfer method (1-{len(transfer_methods)})[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(transfer_methods):
                    transfer_method = TransferMethod(transfer_methods[choice_idx][0])
                    break
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except (ValueError, KeyError):
                self.console.print("[red]Invalid selection. Please enter a number.[/red]")
        
        # Transfer options
        transfer_data = {"method": transfer_method}
        
        # Performance options
        if Confirm.ask("[cyan]Configure advanced transfer options?[/cyan]", default=False, console=self.console):
            parallel = Prompt.ask("[cyan]Parallel transfers[/cyan]", default="4", console=self.console)
            try:
                transfer_data["parallel_transfers"] = max(1, min(16, int(parallel)))
            except ValueError:
                transfer_data["parallel_transfers"] = 4
            
            if Confirm.ask("[cyan]Enable compression?[/cyan]", default=False, console=self.console):
                transfer_data["compression_enabled"] = True
            
            if Confirm.ask("[cyan]Verify checksums?[/cyan]", default=True, console=self.console):
                transfer_data["verify_checksums"] = True
        
        self.console.print()
        return TransferConfig(**transfer_data)
    
    def _collect_migration_options(self) -> MigrationOptions:
        """Collect migration options."""
        self.console.print("[bold]Migration Options[/bold]")
        
        options_data = {}
        
        # Safety options
        options_data["maintenance_mode"] = Confirm.ask(
            "[cyan]Enable maintenance mode during migration?[/cyan]",
            default=False,
            console=self.console
        )
        
        options_data["backup_before"] = Confirm.ask(
            "[cyan]Create backup before migration?[/cyan]",
            default=True,
            console=self.console
        )
        
        options_data["verify_after"] = Confirm.ask(
            "[cyan]Verify migration after completion?[/cyan]",
            default=True,
            console=self.console
        )
        
        options_data["rollback_on_failure"] = Confirm.ask(
            "[cyan]Automatically rollback on failure?[/cyan]",
            default=True,
            console=self.console
        )
        
        # Advanced options
        if Confirm.ask("[cyan]Configure advanced options?[/cyan]", default=False, console=self.console):
            options_data["preserve_permissions"] = Confirm.ask(
                "[cyan]Preserve file permissions?[/cyan]",
                default=True,
                console=self.console
            )
            
            options_data["preserve_timestamps"] = Confirm.ask(
                "[cyan]Preserve file timestamps?[/cyan]",
                default=True,
                console=self.console
            )
            
            options_data["dry_run"] = Confirm.ask(
                "[cyan]Perform dry run (no actual changes)?[/cyan]",
                default=False,
                console=self.console
            )
        
        self.console.print()
        return MigrationOptions(**options_data)
    
    def _show_configuration_summary(self, config: MigrationConfig) -> None:
        """Display configuration summary."""
        self.console.rule("[bold green]Configuration Summary")
        
        # Basic info
        table = Table(title="Migration Configuration", box=box.ROUNDED)
        table.add_column("Setting", style="cyan", width=20)
        table.add_column("Value", style="green")
        
        table.add_row("Name", config.name)
        if config.description:
            table.add_row("Description", config.description)
        
        table.add_row("Source Type", config.source.type.value)
        table.add_row("Source Host", config.source.host)
        table.add_row("Destination Type", config.destination.type.value)
        table.add_row("Destination Host", config.destination.host)
        table.add_row("Transfer Method", config.transfer.method.value)
        
        self.console.print(table)
        self.console.print()
        
        # Confirmation
        if not Confirm.ask("[bold green]Proceed with this configuration?[/bold green]", console=self.console):
            raise click.Abort("Configuration cancelled by user")
    
    # Helper methods
    def _needs_database_config(self, system_type: SystemType) -> bool:
        """Check if system type requires database configuration."""
        db_required_types = {
            SystemType.WORDPRESS, SystemType.DRUPAL, SystemType.JOOMLA,
            SystemType.DJANGO, SystemType.LARAVEL, SystemType.RAILS
        }
        return system_type in db_required_types
    
    def _needs_cloud_config(self, system_type: SystemType) -> bool:
        """Check if system type requires cloud configuration."""
        cloud_types = {
            SystemType.AWS_S3, SystemType.GOOGLE_CLOUD_STORAGE, SystemType.AZURE_BLOB
        }
        return system_type in cloud_types
    
    def _needs_control_panel_config(self, system_type: SystemType) -> bool:
        """Check if system type requires control panel configuration."""
        cp_types = {SystemType.CPANEL, SystemType.DIRECTADMIN, SystemType.PLESK}
        return system_type in cp_types
    
    def _offer_preset_selection(self) -> bool:
        """Ask user if they want to use a preset."""
        return Confirm.ask(
            "[cyan]Would you like to use a migration preset?[/cyan]",
            default=True,
            console=self.console
        )
    
    def _select_preset(self) -> Optional[str]:
        """Allow user to select from available presets."""
        self.console.rule("[bold cyan]Available Presets")
        
        presets = self.preset_manager.get_available_presets()
        if not presets:
            self.console.print("[yellow]No presets available[/yellow]")
            return None
        
        # Display presets in a table
        table = Table(title="Migration Presets", box=box.ROUNDED)
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Name", style="green", width=25)
        table.add_column("Description", style="dim")
        
        for i, (preset_key, name, description) in enumerate(presets, 1):
            table.add_row(str(i), name, description)
        
        self.console.print(table)
        self.console.print()
        
        # Get user selection
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select preset (1-{len(presets)}, or 0 for custom)[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice)
                
                if choice_idx == 0:
                    return None  # Custom configuration
                elif 1 <= choice_idx <= len(presets):
                    selected_preset = presets[choice_idx - 1][0]
                    self.console.print(f"[green]Selected preset: {presets[choice_idx - 1][1]}[/green]")
                    return selected_preset
                else:
                    self.console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]Invalid selection. Please enter a number.[/red]")
    
    def _customize_preset_configuration(self, preset_key: str) -> MigrationConfig:
        """Load preset and allow customization."""
        self.console.rule(f"[bold cyan]Customizing Preset: {preset_key}")
        
        # Load preset configuration
        preset_config = self.preset_manager.create_migration_config_from_preset(preset_key)
        if not preset_config:
            self.console.print(f"[red]Failed to load preset: {preset_key}[/red]")
            return self._collect_full_configuration()
        
        self.console.print(f"[green]Loaded preset configuration for: {preset_config.name}[/green]")
        self.console.print(f"[dim]{preset_config.description}[/dim]")
        self.console.print()
        
        # Show current configuration summary
        self._show_preset_summary(preset_config)
        
        # Ask what to customize
        customizations = self._select_customizations()
        
        if not customizations:
            # Use preset as-is
            self._show_configuration_summary(preset_config)
            return preset_config
        
        # Apply customizations
        return self._apply_customizations(preset_config, customizations)
    
    def _show_preset_summary(self, config: MigrationConfig) -> None:
        """Show a summary of the preset configuration."""
        table = Table(title="Preset Configuration Summary", box=box.MINIMAL)
        table.add_column("Setting", style="cyan", width=20)
        table.add_column("Value", style="green")
        
        table.add_row("Migration Name", config.name)
        table.add_row("Source Type", config.source.type.value)
        table.add_row("Source Host", config.source.host)
        table.add_row("Destination Type", config.destination.type.value)
        table.add_row("Destination Host", config.destination.host)
        table.add_row("Transfer Method", config.transfer.method.value)
        table.add_row("Backup Before", "Yes" if config.options.backup_before else "No")
        table.add_row("Maintenance Mode", "Yes" if config.options.maintenance_mode else "No")
        
        self.console.print(table)
        self.console.print()
    
    def _select_customizations(self) -> List[str]:
        """Allow user to select what aspects to customize."""
        if not Confirm.ask("[cyan]Do you want to customize this preset?[/cyan]", default=False, console=self.console):
            return []
        
        customization_options = [
            ("basic", "Basic information (name, description)"),
            ("source", "Source system configuration"),
            ("destination", "Destination system configuration"),
            ("transfer", "Transfer settings"),
            ("options", "Migration options")
        ]
        
        self.console.print("[bold]Select what to customize:[/bold]")
        
        selected = []
        for option_key, option_desc in customization_options:
            if Confirm.ask(f"[cyan]Customize {option_desc.lower()}?[/cyan]", default=False, console=self.console):
                selected.append(option_key)
        
        return selected
    
    def _apply_customizations(self, config: MigrationConfig, customizations: List[str]) -> MigrationConfig:
        """Apply selected customizations to the preset configuration."""
        # Store original values
        self.config_data["name"] = config.name
        self.config_data["description"] = config.description
        
        source_config = config.source
        destination_config = config.destination
        transfer_config = config.transfer
        options_config = config.options
        
        # Apply customizations
        if "basic" in customizations:
            self.console.rule("[bold]Basic Information")
            self._collect_basic_info()
        
        if "source" in customizations:
            self.console.rule("[bold blue]Source System Configuration")
            source_config = self._collect_system_config("source")
        
        if "destination" in customizations:
            self.console.rule("[bold green]Destination System Configuration")
            destination_config = self._collect_system_config("destination")
        
        if "transfer" in customizations:
            self.console.rule("[bold yellow]Transfer Configuration")
            transfer_config = self._collect_transfer_config()
        
        if "options" in customizations:
            self.console.rule("[bold magenta]Migration Options")
            options_config = self._collect_migration_options()
        
        # Create updated configuration
        try:
            updated_config = MigrationConfig(
                name=self.config_data.get("name", config.name),
                description=self.config_data.get("description", config.description),
                source=source_config,
                destination=destination_config,
                transfer=transfer_config,
                options=options_config
            )
            
            self._show_configuration_summary(updated_config)
            return updated_config
            
        except PydanticValidationError as e:
            self.console.print(f"[red]Configuration validation failed: {e}[/red]")
            raise