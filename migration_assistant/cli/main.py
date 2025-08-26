"""
Main CLI entry point for the Migration Assistant.

This module provides the primary command-line interface using Click
with Rich formatting for enhanced user experience.
"""

import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from migration_assistant import __version__

console = Console()


def print_banner():
    """Print the enhanced application banner."""
    from rich.columns import Columns
    from rich.align import Align
    
    # Main title
    title_text = Text()
    title_text.append("🚀 Web & Database Migration Assistant", style="bold blue")
    title_text.append(f"\n   Version {__version__}", style="dim cyan")
    title_text.append("\n   A comprehensive tool for migrating web applications and databases", style="italic green")
    
    # Feature highlights
    features_text = Text()
    features_text.append("✨ Features:\n", style="bold yellow")
    features_text.append("• Interactive CLI with Rich formatting\n", style="dim")
    features_text.append("• REST API with async support\n", style="dim")
    features_text.append("• Multiple database types supported\n", style="dim")
    features_text.append("• Cloud platform integrations\n", style="dim")
    features_text.append("• Backup & rollback capabilities\n", style="dim")
    features_text.append("• Comprehensive validation engine", style="dim")
    
    # Quick actions
    actions_text = Text()
    actions_text.append("🎯 Quick Actions:\n", style="bold magenta")
    actions_text.append("migration-assistant help --interactive\n", style="code")
    actions_text.append("migration-assistant presets\n", style="code")
    actions_text.append("migration-assistant migrate\n", style="code")
    actions_text.append("migration-assistant serve", style="code")
    
    # Create columns layout
    columns = Columns([
        Panel(title_text, title="Welcome", border_style="blue", padding=(1, 2)),
        Panel(features_text, title="Features", border_style="green", padding=(1, 2)),
        Panel(actions_text, title="Get Started", border_style="magenta", padding=(1, 2))
    ], equal=True, expand=True)
    
    console.print(columns)


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def main(ctx: click.Context, version: bool, verbose: bool):
    """
    Web & Database Migration Assistant
    
    A comprehensive Python-based tool for migrating web applications and databases
    between different systems, platforms, and environments.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    if version:
        console.print(f"Migration Assistant version {__version__}")
        sys.exit(0)
    
    # If no subcommand is provided, show help
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("\n[yellow]Use --help to see available commands[/yellow]")
        console.print("\n[dim]Quick start:[/dim]")
        console.print("  [cyan]migration-assistant migrate[/cyan]  - Start interactive migration wizard")
        console.print("  [cyan]migration-assistant validate[/cyan] - Validate migration configuration")
        console.print("  [cyan]migration-assistant status[/cyan]   - Check migration status")


@main.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--preset', '-p', help='Use a migration preset')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without making changes')
@click.option('--interactive/--non-interactive', default=True, help='Interactive or batch mode')
@click.pass_context
def migrate(ctx: click.Context, config: Optional[str], preset: Optional[str], 
           dry_run: bool, interactive: bool):
    """Start a migration process."""
    console.print("[green]Starting migration process...[/green]")
    
    if ctx.obj.get('verbose', False):
        console.print(f"[dim]Config file: {config or 'None'}[/dim]")
        console.print(f"[dim]Preset: {preset or 'None'}[/dim]")
        console.print(f"[dim]Dry run: {dry_run}[/dim]")
        console.print(f"[dim]Interactive: {interactive}[/dim]")
    
    try:
        if interactive and not config:
            # Use interactive configuration collector
            from migration_assistant.cli.config_collector import ConfigurationCollector
            from migration_assistant.cli.config_persistence import ConfigurationPersistence
            from rich.prompt import Confirm
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
            
            # Show progress for configuration collection
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                task = progress.add_task("Initializing configuration collector...", total=None)
                collector = ConfigurationCollector()
                progress.update(task, description="Collecting migration configuration...")
                migration_config = collector.collect_configuration(preset)
                progress.update(task, description="Configuration collection complete!", completed=True)
            
            # Show success with enhanced formatting
            from rich.panel import Panel
            success_text = Text()
            success_text.append("✅ Configuration collected successfully!\n", style="bold green")
            success_text.append(f"Migration Name: {migration_config.name}\n", style="cyan")
            success_text.append(f"Source: {migration_config.source.type.value if hasattr(migration_config.source, 'type') else 'Unknown'}\n", style="dim")
            success_text.append(f"Destination: {migration_config.destination.type.value if hasattr(migration_config.destination, 'type') else 'Unknown'}", style="dim")
            
            panel = Panel(success_text, title="Configuration Ready", border_style="green", padding=(1, 2))
            console.print(panel)
            
            # Ask if user wants to save the configuration
            if Confirm.ask("[cyan]💾 Save this configuration for future use?[/cyan]", default=True):
                persistence = ConfigurationPersistence()
                try:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Saving configuration...", total=None)
                        saved_path = persistence.save_configuration(migration_config)
                        progress.update(task, description="Configuration saved!", completed=True)
                    
                    console.print(f"[green]✅ Configuration saved successfully![/green]")
                    console.print(f"[dim]📁 Saved to: {saved_path}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]⚠️  Warning: Could not save configuration: {e}[/yellow]")
            
            # Show next steps
            next_steps_text = Text()
            next_steps_text.append("🎯 Next Steps:\n", style="bold blue")
            next_steps_text.append("1. Validate your configuration: ", style="dim")
            next_steps_text.append("migration-assistant validate --config <saved-file>\n", style="code")
            next_steps_text.append("2. Start the migration: ", style="dim")
            next_steps_text.append("migration-assistant migrate --config <saved-file>\n", style="code")
            next_steps_text.append("3. Monitor progress: ", style="dim")
            next_steps_text.append("migration-assistant status", style="code")
            
            panel = Panel(next_steps_text, title="What's Next?", border_style="blue", padding=(1, 2))
            console.print(panel)
            
            # TODO: Proceed with migration execution in future tasks
            console.print("\n[yellow]🚧 Migration execution will be implemented in upcoming tasks[/yellow]")
        
        elif config:
            # Load from config file
            from migration_assistant.cli.config_persistence import ConfigurationPersistence, ConfigurationValidator
            
            persistence = ConfigurationPersistence()
            validator = ConfigurationValidator()
            
            try:
                migration_config = persistence.load_configuration(config)
                console.print(f"[green]✓ Configuration loaded: {migration_config.name}[/green]")
                
                # Validate the loaded configuration
                validation_results = validator.validate_configuration(migration_config)
                validator.display_validation_results(validation_results)
                
                if not validation_results["valid"]:
                    from rich.prompt import Confirm
                    if not Confirm.ask("[yellow]Configuration has errors. Continue anyway?[/yellow]", default=False):
                        console.print("[yellow]Migration cancelled due to configuration errors[/yellow]")
                        sys.exit(1)
                
                # Show configuration summary
                if ctx.obj.get('verbose', False):
                    persistence.show_configuration_summary(migration_config)
                
                # TODO: Proceed with migration execution in future tasks
                console.print("[yellow]Migration execution will be implemented in upcoming tasks[/yellow]")
                
            except Exception as e:
                console.print(f"[red]Error loading configuration: {e}[/red]")
                sys.exit(1)
        
        else:
            console.print("[yellow]Non-interactive mode without config file not yet supported[/yellow]")
            console.print("[dim]Use --interactive or provide --config file[/dim]")
            
    except click.Abort:
        console.print("[yellow]Migration cancelled by user[/yellow]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("[yellow]Migration cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error during configuration: {e}[/red]")
        if ctx.obj.get('verbose', False):
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@main.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'yaml']), 
              default='table', help='Output format')
@click.pass_context
def validate(ctx: click.Context, config: Optional[str], format: str):
    """Validate migration configuration."""
    if not config:
        console.print("[red]Error: Configuration file path is required[/red]")
        console.print("[dim]Use: migration-assistant validate --config path/to/config.yaml[/dim]")
        sys.exit(1)
    
    console.print("[green]Validating migration configuration...[/green]")
    
    if ctx.obj.get('verbose', False):
        console.print(f"[dim]Config file: {config}[/dim]")
        console.print(f"[dim]Output format: {format}[/dim]")
    
    try:
        from migration_assistant.cli.config_persistence import ConfigurationPersistence, ConfigurationValidator
        import json
        
        persistence = ConfigurationPersistence()
        validator = ConfigurationValidator()
        
        # First validate the file format and structure
        file_validation = persistence.validate_configuration_file(config)
        
        if format == 'json':
            console.print(json.dumps(file_validation, indent=2, default=str))
            return
        elif format == 'yaml':
            import yaml
            console.print(yaml.dump(file_validation, default_flow_style=False))
            return
        
        # Table format (default)
        if file_validation["valid"]:
            # Load and perform comprehensive validation
            migration_config = persistence.load_configuration(config)
            validation_results = validator.validate_configuration(migration_config)
            validator.display_validation_results(validation_results)
            
            if ctx.obj.get('verbose', False):
                console.print("\n[bold]Configuration Summary:[/bold]")
                persistence.show_configuration_summary(migration_config)
            
            # Exit with error code if validation failed
            if not validation_results.get("valid", True):
                sys.exit(1)
        else:
            console.print("[red]Configuration file validation failed:[/red]")
            for error in file_validation["errors"]:
                console.print(f"  • [red]{error}[/red]")
            
            if file_validation["warnings"]:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in file_validation["warnings"]:
                    console.print(f"  • [yellow]{warning}[/yellow]")
            
            # Exit with error code for file validation failure
            sys.exit(1)
    
    except Exception as e:
        console.print(f"[red]Error during validation: {e}[/red]")
        if ctx.obj.get('verbose', False):
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@main.command()
@click.option('--session-id', '-s', help='Migration session ID')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'yaml']), 
              default='table', help='Output format')
@click.option('--watch', '-w', is_flag=True, help='Watch for status changes')
@click.pass_context
def status(ctx: click.Context, session_id: Optional[str], format: str, watch: bool):
    """Check migration status."""
    console.print("[green]Checking migration status...[/green]")
    
    if ctx.obj.get('verbose', False):
        console.print(f"[dim]Session ID: {session_id or 'All sessions'}[/dim]")
        console.print(f"[dim]Output format: {format}[/dim]")
        console.print(f"[dim]Watch mode: {watch}[/dim]")
    
    # TODO: Implement status checking logic in future tasks
    console.print("[yellow]Status functionality will be implemented in upcoming tasks[/yellow]")


@main.command()
@click.option('--session-id', '-s', required=True, help='Migration session ID to rollback')
@click.option('--force', is_flag=True, help='Force rollback without confirmation')
@click.pass_context
def rollback(ctx: click.Context, session_id: str, force: bool):
    """Rollback a migration."""
    console.print(f"[yellow]Rolling back migration session: {session_id}[/yellow]")
    
    if not force:
        if not click.confirm("Are you sure you want to rollback this migration?"):
            console.print("[red]Rollback cancelled[/red]")
            return
    
    if ctx.obj.get('verbose', False):
        console.print(f"[dim]Session ID: {session_id}[/dim]")
        console.print(f"[dim]Force: {force}[/dim]")
    
    # TODO: Implement rollback logic in future tasks
    console.print("[yellow]Rollback functionality will be implemented in upcoming tasks[/yellow]")


@main.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'yaml']), 
              default='table', help='Output format')
def configs(format: str):
    """List saved migration configurations."""
    try:
        from migration_assistant.cli.config_persistence import ConfigurationPersistence
        
        persistence = ConfigurationPersistence()
        saved_configs = persistence.list_configurations()
        
        if not saved_configs:
            console.print("[yellow]No saved configurations found[/yellow]")
            return
        
        if format == 'table':
            from rich.table import Table
            from rich import box
            from rich.panel import Panel
            
            # Enhanced table with better styling
            table = Table(
                title="💾 Saved Migration Configurations", 
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
                title_style="bold blue"
            )
            table.add_column("Filename", style="cyan", width=25, no_wrap=True)
            table.add_column("Name", style="green", width=30)
            table.add_column("Modified", style="blue", width=20)
            table.add_column("Size", style="yellow", width=10, justify="right")
            table.add_column("Status", style="magenta", width=8, justify="center")
            table.add_column("Actions", style="dim", width=30)
            
            for config_info in saved_configs:
                size_kb = f"{config_info['size'] / 1024:.1f} KB"
                valid_status = "✅" if config_info['valid'] else "❌"
                modified_str = config_info['modified'].strftime("%Y-%m-%d %H:%M")
                
                # Generate action hints
                filename = config_info['filename']
                actions = f"validate --config {filename}"
                
                table.add_row(
                    f"[bold]{config_info['filename']}[/bold]",
                    config_info['name'] or "[dim]Unknown[/dim]",
                    modified_str,
                    size_kb,
                    valid_status,
                    f"[code]{actions}[/code]"
                )
            
            console.print(table)
            
            # Add usage examples
            if saved_configs:
                examples_text = Text()
                examples_text.append("💡 Usage Examples:\n", style="bold blue")
                examples_text.append("• Validate config: ", style="dim")
                examples_text.append(f"migration-assistant validate --config {saved_configs[0]['filename']}\n", style="code")
                examples_text.append("• Run migration: ", style="dim")
                examples_text.append(f"migration-assistant migrate --config {saved_configs[0]['filename']}\n", style="code")
                examples_text.append("• Export as JSON: ", style="dim")
                examples_text.append("migration-assistant configs --format json", style="code")
                
                panel = Panel(examples_text, title="How to Use Saved Configurations", border_style="blue", padding=(1, 2))
                console.print("\n")
                console.print(panel)
            
        elif format == 'json':
            import json
            console.print(json.dumps(saved_configs, indent=2, default=str))
            
        elif format == 'yaml':
            import yaml
            console.print(yaml.dump(saved_configs, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error listing configurations: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'yaml']), 
              default='table', help='Output format')
def presets(format: str):
    """List available migration presets."""
    try:
        from migration_assistant.cli.preset_manager import PresetManager
        
        preset_manager = PresetManager()
        available_presets = preset_manager.get_available_presets()
        
        if format == 'table':
            from rich.table import Table
            from rich import box
            from rich.panel import Panel
            
            # Enhanced table with more styling
            table = Table(
                title="🎯 Available Migration Presets", 
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
                title_style="bold blue"
            )
            table.add_column("Preset Key", style="cyan", width=25, no_wrap=True)
            table.add_column("Name", style="green", width=30)
            table.add_column("Description", style="dim", width=50)
            table.add_column("Usage", style="yellow", width=20)
            
            for preset_key, name, description in available_presets:
                usage_hint = f"--preset {preset_key}"
                table.add_row(
                    f"[bold]{preset_key}[/bold]", 
                    name, 
                    description,
                    f"[code]{usage_hint}[/code]"
                )
            
            console.print(table)
            
            # Add usage examples
            examples_text = Text()
            examples_text.append("💡 Usage Examples:\n", style="bold blue")
            examples_text.append("• Interactive migration: ", style="dim")
            examples_text.append("migration-assistant migrate --preset wordpress-mysql\n", style="code")
            examples_text.append("• Get preset details: ", style="dim")
            examples_text.append("migration-assistant help --topic presets\n", style="code")
            examples_text.append("• List all presets: ", style="dim")
            examples_text.append("migration-assistant presets --format json", style="code")
            
            panel = Panel(examples_text, title="How to Use Presets", border_style="blue", padding=(1, 2))
            console.print("\n")
            console.print(panel)
            
        elif format == 'json':
            import json
            preset_data = [
                {"key": key, "name": name, "description": desc}
                for key, name, desc in available_presets
            ]
            console.print(json.dumps(preset_data, indent=2))
            
        elif format == 'yaml':
            import yaml
            preset_data = [
                {"key": key, "name": name, "description": desc}
                for key, name, desc in available_presets
            ]
            console.print(yaml.dump(preset_data, default_flow_style=False))
            
    except Exception as e:
        console.print(f"[red]Error listing presets: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option('--port', '-p', default=8000, help='API server port')
@click.option('--host', '-h', default='127.0.0.1', help='API server host')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
def serve(port: int, host: str, reload: bool):
    """Start the API server."""
    console.print(f"[green]Starting API server on {host}:{port}[/green]")
    
    try:
        import uvicorn
        from migration_assistant.api.main import app
        
        uvicorn.run(
            "migration_assistant.api.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except ImportError:
        console.print("[red]Error: uvicorn is required to run the API server[/red]")
        console.print("[yellow]Install with: pip install uvicorn[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option('--topic', '-t', type=click.Choice(['quick-start', 'examples', 'templates', 'presets', 'troubleshooting']), 
              help='Show specific help topic')
@click.option('--command', '-c', type=click.Choice(['migrate', 'validate', 'status', 'rollback']), 
              help='Show examples for specific command')
@click.option('--interactive', '-i', is_flag=True, help='Start interactive help menu')
def help(topic: Optional[str], command: Optional[str], interactive: bool):
    """Show comprehensive help, examples, and troubleshooting guides."""
    from migration_assistant.cli.help_system import HelpSystem
    
    help_system = HelpSystem()
    
    if interactive:
        help_system.show_interactive_help_menu()
        return
    
    if topic == 'quick-start':
        help_system.show_quick_start_guide()
    elif topic == 'examples':
        if command:
            help_system.show_command_examples(command)
        else:
            help_system.show_command_examples()
    elif topic == 'templates':
        help_system.show_configuration_templates()
    elif topic == 'presets':
        help_system.show_preset_details()
    elif topic == 'troubleshooting':
        help_system.show_troubleshooting_guide()
    elif command:
        help_system.show_command_examples(command)
    else:
        # Show default help overview
        console.print("[bold blue]🎯 Migration Assistant Help[/bold blue]\n")
        console.print("Use one of these options to get specific help:\n")
        
        help_options = [
            ("--topic quick-start", "Quick start guide for new users"),
            ("--topic examples", "Command examples and usage patterns"),
            ("--topic templates", "Configuration file templates"),
            ("--topic presets", "Available migration presets"),
            ("--topic troubleshooting", "Troubleshooting common issues"),
            ("--command <cmd>", "Examples for specific command (migrate, validate, status, rollback)"),
            ("--interactive", "Interactive help menu")
        ]
        
        from rich.table import Table
        from rich import box
        
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("Option", style="cyan", width=25)
        table.add_column("Description", style="dim", width=50)
        
        for option, description in help_options:
            table.add_row(f"migration-assistant help {option}", description)
        
        console.print(table)
        console.print("\n[dim]Example: migration-assistant help --topic quick-start[/dim]")


if __name__ == '__main__':
    main()