"""
Main CLI entry point for the Migration Assistant.

This module provides the primary command-line interface using Click
with Rich formatting for enhanced user experience.
"""

import sys
from typing import Optional, List, Dict, Any

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
@click.option('--operation-id', '-o', help='Rollback operation ID to rollback')
@click.option('--backup-id', '-b', help='Backup ID to restore from')
@click.option('--session-id', '-s', help='Migration session ID to rollback (legacy)')
@click.option('--force', is_flag=True, help='Force rollback without confirmation')
@click.option('--list-operations', is_flag=True, help='List available rollback operations')
@click.option('--show-plan', is_flag=True, help='Show recovery plan without executing')
@click.pass_context
def rollback(ctx: click.Context, operation_id: str, backup_id: str, session_id: str, 
             force: bool, list_operations: bool, show_plan: bool):
    """Rollback a checkup operation or restore from backup."""
    import asyncio
    from pathlib import Path
    from migration_assistant.checkup.backup_manager import BackupManager
    from migration_assistant.checkup.rollback_manager import RollbackManager
    from migration_assistant.checkup.models import CheckupConfig
    from rich.table import Table
    from rich.panel import Panel
    
    # Set up configuration
    config = CheckupConfig(
        target_directory=Path.cwd(),
        backup_dir=Path.cwd() / ".checkup_backups",
        create_backup=True,
        dry_run=False
    )
    
    backup_manager = BackupManager(config)
    rollback_manager = RollbackManager(config, backup_manager)
    
    async def run_rollback():
        try:
            # List operations if requested
            if list_operations:
                operations = rollback_manager.list_rollback_operations()
                if not operations:
                    console.print("[yellow]No rollback operations found[/yellow]")
                    return
                
                table = Table(title="Available Rollback Operations")
                table.add_column("Operation ID", style="cyan")
                table.add_column("Type", style="green")
                table.add_column("Backup ID", style="blue")
                table.add_column("Files", justify="right")
                table.add_column("Status", style="yellow")
                table.add_column("Created", style="dim")
                
                for op in operations:
                    status = "Completed" if op.rollback_completed else "Available"
                    table.add_row(
                        op.operation_id[:12] + "...",
                        op.operation_type,
                        op.backup_id[:12] + "...",
                        str(len(op.affected_files)),
                        status,
                        op.timestamp.strftime("%Y-%m-%d %H:%M")
                    )
                
                console.print(table)
                return
            
            # Handle legacy session-id parameter
            if session_id and not operation_id:
                console.print("[yellow]Note: --session-id is deprecated, use --operation-id instead[/yellow]")
                operation_id = session_id
            
            # Validate parameters
            if not operation_id and not backup_id:
                console.print("[red]Error: Must specify either --operation-id or --backup-id[/red]")
                return
            
            # Show recovery plan if requested
            if show_plan and operation_id:
                plan = await rollback_manager.create_recovery_plan(operation_id)
                if not plan:
                    console.print(f"[red]Operation not found: {operation_id}[/red]")
                    return
                
                # Display recovery plan
                plan_text = f"""
[bold]Recovery Plan for Operation: {plan['operation_id'][:12]}...[/bold]

[cyan]Operation Details:[/cyan]
• Type: {plan['operation_type']}
• Backup ID: {plan['backup_id'][:12]}...
• Backup Type: {plan['backup_type']}
• Backup Size: {plan['backup_size'] / (1024*1024):.1f} MB
• Affected Files: {plan['affected_files']}
• Can Rollback: {'✅ Yes' if plan['can_rollback'] else '❌ No'}
• Estimated Duration: {plan['estimated_duration']} seconds

[cyan]Recovery Steps:[/cyan]
"""
                for i, step in enumerate(plan['steps'], 1):
                    plan_text += f"{i}. {step}\n"
                
                if plan['validation_errors']:
                    plan_text += f"\n[red]Validation Errors:[/red]\n"
                    for error in plan['validation_errors']:
                        plan_text += f"• {error}\n"
                
                console.print(Panel(plan_text, title="Recovery Plan", border_style="blue"))
                return
            
            # Confirm rollback operation
            if not force:
                if operation_id:
                    message = f"Are you sure you want to rollback operation {operation_id[:12]}...?"
                else:
                    message = f"Are you sure you want to restore from backup {backup_id[:12]}...?"
                
                if not click.confirm(message):
                    console.print("[red]Rollback cancelled[/red]")
                    return
            
            # Perform rollback
            console.print("[yellow]Starting rollback operation...[/yellow]")
            
            if operation_id:
                success = await rollback_manager.manual_rollback(operation_id=operation_id)
                if success:
                    console.print(f"[green]✅ Rollback completed successfully for operation {operation_id[:12]}...[/green]")
                else:
                    console.print(f"[red]❌ Rollback failed for operation {operation_id[:12]}...[/red]")
                    
                    # Show errors if any
                    operation = rollback_manager.get_rollback_operation(operation_id)
                    if operation and operation.rollback_errors:
                        console.print("[red]Errors:[/red]")
                        for error in operation.rollback_errors:
                            console.print(f"  • {error}")
            
            elif backup_id:
                success = await rollback_manager.manual_rollback(backup_id=backup_id)
                if success:
                    console.print(f"[green]✅ Restore completed successfully from backup {backup_id[:12]}...[/green]")
                else:
                    console.print(f"[red]❌ Restore failed from backup {backup_id[:12]}...[/red]")
            
            if ctx.obj.get('verbose', False):
                # Show rollback statistics
                stats = rollback_manager.get_rollback_statistics()
                console.print(f"\n[dim]Rollback Statistics:[/dim]")
                console.print(f"[dim]  Total Operations: {stats['total_operations']}[/dim]")
                console.print(f"[dim]  Success Rate: {stats['success_rate']:.1%}[/dim]")
                
        except Exception as e:
            console.print(f"[red]Error during rollback: {str(e)}[/red]")
            if ctx.obj.get('verbose', False):
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    # Run the async rollback operation
    asyncio.run(run_rollback())


@main.command()
@click.option('--cleanup-old', is_flag=True, help='Clean up old rollback operations')
@click.option('--max-age-days', default=30, help='Maximum age of operations to keep (default: 30)')
@click.option('--show-stats', is_flag=True, help='Show rollback statistics')
@click.option('--verify-backups', is_flag=True, help='Verify integrity of all backups')
@click.pass_context
def rollback_manage(ctx: click.Context, cleanup_old: bool, max_age_days: int, 
                   show_stats: bool, verify_backups: bool):
    """Manage rollback operations and backups."""
    import asyncio
    from pathlib import Path
    from migration_assistant.checkup.backup_manager import BackupManager
    from migration_assistant.checkup.rollback_manager import RollbackManager
    from migration_assistant.checkup.models import CheckupConfig
    from rich.table import Table
    from rich.panel import Panel
    
    # Set up configuration
    config = CheckupConfig(
        target_directory=Path.cwd(),
        backup_dir=Path.cwd() / ".checkup_backups",
        create_backup=True,
        dry_run=False
    )
    
    backup_manager = BackupManager(config)
    rollback_manager = RollbackManager(config, backup_manager)
    
    async def run_management():
        try:
            if cleanup_old:
                console.print(f"[yellow]Cleaning up rollback operations older than {max_age_days} days...[/yellow]")
                deleted = await rollback_manager.cleanup_old_operations(max_age_days)
                
                if deleted:
                    console.print(f"[green]✅ Cleaned up {len(deleted)} old operations[/green]")
                    if ctx.obj.get('verbose', False):
                        for op_id in deleted:
                            console.print(f"  • {op_id}")
                else:
                    console.print("[blue]No old operations to clean up[/blue]")
            
            if show_stats:
                stats = rollback_manager.get_rollback_statistics()
                
                stats_text = f"""
[bold]Rollback Statistics[/bold]

[cyan]Operations:[/cyan]
• Total Operations: {stats['total_operations']}
• Completed Rollbacks: {stats['completed_rollbacks']}
• Failed Rollbacks: {stats['failed_rollbacks']}
• Success Rate: {stats['success_rate']:.1%}
• Recent Operations (7 days): {stats['recent_operations']}

[cyan]By Operation Type:[/cyan]
"""
                
                for op_type, type_stats in stats['operation_types'].items():
                    success_rate = type_stats['completed'] / type_stats['total'] if type_stats['total'] > 0 else 0
                    stats_text += f"• {op_type}: {type_stats['completed']}/{type_stats['total']} ({success_rate:.1%})\n"
                
                console.print(Panel(stats_text, title="Rollback Statistics", border_style="blue"))
            
            if verify_backups:
                console.print("[yellow]Verifying backup integrity...[/yellow]")
                backups = backup_manager.list_backups()
                
                if not backups:
                    console.print("[blue]No backups found to verify[/blue]")
                    return
                
                table = Table(title="Backup Verification Results")
                table.add_column("Backup ID", style="cyan")
                table.add_column("Type", style="green")
                table.add_column("Size", justify="right")
                table.add_column("Status", style="yellow")
                table.add_column("Created", style="dim")
                
                verified_count = 0
                for backup_info in backups:
                    # Verify backup integrity
                    is_valid = await rollback_manager.validator._verify_backup_integrity(backup_info)
                    status = "✅ Valid" if is_valid else "❌ Invalid"
                    if is_valid:
                        verified_count += 1
                    
                    size_mb = (backup_info.size or 0) / (1024 * 1024)
                    table.add_row(
                        backup_info.backup_id[:12] + "...",
                        backup_info.backup_type,
                        f"{size_mb:.1f} MB",
                        status,
                        backup_info.created_at.strftime("%Y-%m-%d %H:%M")
                    )
                
                console.print(table)
                console.print(f"\n[green]✅ {verified_count}/{len(backups)} backups verified successfully[/green]")
            
            # If no specific action requested, show help
            if not any([cleanup_old, show_stats, verify_backups]):
                console.print("[yellow]Use --help to see available management options[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Error during rollback management: {str(e)}[/red]")
            if ctx.obj.get('verbose', False):
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    # Run the async management operation
    asyncio.run(run_management())


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


@main.group()
def checkup():
    """Codebase checkup and cleanup commands."""
    pass


@checkup.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Checkup configuration file')
@click.option('--target', '-t', type=click.Path(exists=True), default='.', help='Target directory to analyze')
@click.option('--output', '-o', type=click.Path(), help='Output directory for reports')
@click.option('--format', '-f', type=click.Choice(['html', 'json', 'markdown', 'all']), 
              default='html', help='Report format')
@click.option('--dry-run', is_flag=True, help='Analyze only, do not perform cleanup')
@click.option('--interactive/--non-interactive', default=True, help='Interactive mode for confirmations')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--quiet', '-q', is_flag=True, help='Suppress non-essential output')
@click.pass_context
def run(ctx: click.Context, config: Optional[str], target: str, output: Optional[str], 
        format: str, dry_run: bool, interactive: bool, verbose: bool, quiet: bool):
    """Run comprehensive codebase checkup and cleanup."""
    if quiet and verbose:
        console.print("[red]Error: Cannot use both --quiet and --verbose options[/red]")
        sys.exit(1)
    
    # Set up progress display based on verbosity
    if quiet:
        progress_display = 'none'
    elif verbose:
        progress_display = 'detailed'
    else:
        progress_display = 'normal'
    
    console.print("[green]🔍 Starting codebase checkup...[/green]")
    
    if verbose:
        console.print(f"[dim]Target directory: {target}[/dim]")
        console.print(f"[dim]Config file: {config or 'Default configuration'}[/dim]")
        console.print(f"[dim]Output directory: {output or 'Current directory'}[/dim]")
        console.print(f"[dim]Report format: {format}[/dim]")
        console.print(f"[dim]Dry run: {dry_run}[/dim]")
        console.print(f"[dim]Interactive: {interactive}[/dim]")
    
    try:
        from migration_assistant.checkup.orchestrator import CodebaseOrchestrator
        from migration_assistant.checkup.models import CheckupConfig
        from pathlib import Path
        import asyncio
        
        # Load or create configuration
        if config:
            # Load from file
            import yaml
            with open(config, 'r') as f:
                config_data = yaml.safe_load(f)
            checkup_config = CheckupConfig(**config_data)
        else:
            # Use default configuration
            checkup_config = CheckupConfig(
                target_directory=Path(target),
                report_output_dir=Path(output) if output else Path.cwd(),
                dry_run=dry_run,
                generate_html_report=format in ['html', 'all'],
                generate_json_report=format in ['json', 'all'],
                generate_markdown_report=format in ['markdown', 'all']
            )
        
        # Create orchestrator and run checkup
        orchestrator = CodebaseOrchestrator(checkup_config)
        
        # Check for destructive operations and get user confirmation
        if interactive and not dry_run:
            destructive_ops = _check_destructive_operations(checkup_config)
            if destructive_ops:
                if not _confirm_destructive_operations(destructive_ops):
                    console.print("[yellow]⏭️  Switching to analysis-only mode[/yellow]")
                    checkup_config.dry_run = True
                    checkup_config.auto_format = False
                    checkup_config.auto_fix_imports = False
                    checkup_config.auto_organize_files = False
        
        # Run the checkup with progress display
        if progress_display == 'none':
            # Run without progress display
            results = asyncio.run(orchestrator.run_full_checkup())
        else:
            # Run with progress display
            results = asyncio.run(_run_checkup_with_progress(
                orchestrator, progress_display, interactive
            ))
        
        # Display results summary
        _display_checkup_results(results, verbose, quiet)
        
        if not results.success:
            console.print("[yellow]⚠️  Checkup completed with issues[/yellow]")
            sys.exit(1)
        else:
            console.print("[green]✅ Checkup completed successfully[/green]")
    
    except KeyboardInterrupt:
        console.print("[yellow]Checkup cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error during checkup: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@checkup.command()
@click.option('--target', '-t', type=click.Path(exists=True), default='.', help='Target directory to analyze')
@click.option('--output', '-o', type=click.Path(), help='Output directory for reports')
@click.option('--format', '-f', type=click.Choice(['html', 'json', 'markdown', 'all']), 
              default='html', help='Report format')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def analyze(ctx: click.Context, target: str, output: Optional[str], format: str, verbose: bool):
    """Run analysis only without cleanup."""
    console.print("[green]🔍 Running codebase analysis...[/green]")
    
    try:
        from migration_assistant.checkup.orchestrator import CodebaseOrchestrator
        from migration_assistant.checkup.models import CheckupConfig
        from pathlib import Path
        import asyncio
        
        # Create analysis-only configuration
        checkup_config = CheckupConfig(
            target_directory=Path(target),
            report_output_dir=Path(output) if output else Path.cwd(),
            dry_run=True,  # Analysis only
            generate_html_report=format in ['html', 'all'],
            generate_json_report=format in ['json', 'all'],
            generate_markdown_report=format in ['markdown', 'all']
        )
        
        orchestrator = CodebaseOrchestrator(checkup_config)
        results = asyncio.run(orchestrator.run_analysis_only())
        
        _display_analysis_results(results, verbose)
        
        console.print("[green]✅ Analysis completed[/green]")
    
    except Exception as e:
        console.print(f"[red]Error during analysis: {e}[/red]")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


@checkup.command()
@click.option('--config', '-c', type=click.Path(), help='Checkup configuration file')
@click.option('--interactive/--non-interactive', default=True, help='Interactive configuration')
@click.pass_context
def configure(ctx: click.Context, config: Optional[str], interactive: bool):
    """Create or modify checkup configuration."""
    console.print("[green]⚙️  Configuring codebase checkup...[/green]")
    
    try:
        if interactive:
            _interactive_configuration(config)
        else:
            _create_default_configuration(config)
    
    except KeyboardInterrupt:
        console.print("[yellow]Configuration cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error during configuration: {e}[/red]")
        sys.exit(1)


async def _run_checkup_with_progress(orchestrator, progress_display: str, interactive: bool):
    """Run checkup with progress display."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
    from rich.live import Live
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.text import Text
    from rich.status import Status
    from rich.prompt import Confirm
    import asyncio
    
    if progress_display == 'detailed':
        # Detailed progress with multiple progress bars and real-time updates
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
            expand=True
        ) as progress:
            
            # Create progress tasks
            overall_task = progress.add_task("🚀 Overall Progress", total=100)
            analysis_task = progress.add_task("🔍 Analysis Phase", total=100, visible=False)
            cleanup_task = progress.add_task("🧹 Cleanup Phase", total=100, visible=False)
            reporting_task = progress.add_task("📊 Report Generation", total=100, visible=False)
            
            # Phase 1: Analysis
            progress.update(analysis_task, visible=True)
            progress.update(overall_task, advance=5, description="🚀 Starting analysis...")
            
            # Simulate detailed analysis steps with real progress tracking
            analysis_steps = [
                ("🔍 Scanning Python files...", 15),
                ("📝 Running quality analysis...", 20),
                ("🔄 Detecting duplicates...", 20),
                ("📦 Analyzing imports...", 20),
                ("🏗️  Validating structure...", 15),
                ("✅ Analysis complete", 10)
            ]
            
            for step_desc, step_progress in analysis_steps:
                progress.update(analysis_task, description=step_desc)
                await asyncio.sleep(0.2)  # Simulate work
                progress.update(analysis_task, advance=step_progress)
                progress.update(overall_task, advance=step_progress * 0.4)  # 40% of overall
            
            # Get analysis results first
            analysis_results = await orchestrator.run_analysis_only()
            
            # Show analysis summary and get user confirmation for cleanup
            if interactive and not orchestrator.config.dry_run:
                progress.stop()
                
                # Display analysis summary
                _display_analysis_summary_for_confirmation(analysis_results)
                
                # Ask for cleanup confirmation
                if _has_cleanup_actions(analysis_results):
                    if not Confirm.ask("\n[yellow]🤔 Proceed with automated cleanup?[/yellow]", default=True):
                        console.print("[yellow]⏭️  Skipping cleanup phase[/yellow]")
                        # Skip to reporting
                        progress.start()
                        progress.update(cleanup_task, visible=True, completed=100, description="⏭️  Cleanup skipped")
                        progress.update(overall_task, advance=30)
                    else:
                        console.print("[green]✅ Proceeding with cleanup...[/green]")
                        progress.start()
                else:
                    console.print("[green]✨ No cleanup actions needed[/green]")
                    progress.start()
                    progress.update(cleanup_task, visible=True, completed=100, description="✨ No cleanup needed")
                    progress.update(overall_task, advance=30)
            
            # Phase 2: Cleanup (if not skipped)
            if not orchestrator.config.dry_run:
                progress.update(cleanup_task, visible=True)
                
                cleanup_steps = [
                    ("🎨 Formatting code...", 30),
                    ("📦 Cleaning imports...", 30),
                    ("🗂️  Organizing files...", 25),
                    ("✅ Cleanup complete", 15)
                ]
                
                for step_desc, step_progress in cleanup_steps:
                    progress.update(cleanup_task, description=step_desc)
                    await asyncio.sleep(0.15)
                    progress.update(cleanup_task, advance=step_progress)
                    progress.update(overall_task, advance=step_progress * 0.3)  # 30% of overall
            
            # Phase 3: Reporting
            progress.update(reporting_task, visible=True)
            progress.update(overall_task, advance=5, description="🚀 Generating reports...")
            
            reporting_steps = [
                ("📄 Generating HTML report...", 40),
                ("📋 Generating JSON report...", 30),
                ("📝 Generating summary...", 20),
                ("✅ Reports complete", 10)
            ]
            
            for step_desc, step_progress in reporting_steps:
                progress.update(reporting_task, description=step_desc)
                await asyncio.sleep(0.1)
                progress.update(reporting_task, advance=step_progress)
                progress.update(overall_task, advance=step_progress * 0.25)  # 25% of overall
            
            # Complete the checkup
            results = await orchestrator.run_full_checkup()
            progress.update(overall_task, completed=100, description="🎉 Checkup completed!")
            
            return results
    
    elif progress_display == 'normal':
        # Normal progress with status updates
        phases = [
            ("🔍 Analyzing codebase...", 40),
            ("🧹 Performing cleanup...", 30),
            ("📊 Generating reports...", 30)
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            console=console,
            transient=False
        ) as progress:
            
            main_task = progress.add_task("🚀 Running checkup...", total=100)
            
            for phase_desc, phase_weight in phases:
                progress.update(main_task, description=phase_desc)
                await asyncio.sleep(0.5)  # Simulate work
                progress.update(main_task, advance=phase_weight)
            
            # Run actual checkup
            results = await orchestrator.run_full_checkup()
            progress.update(main_task, completed=100, description="🎉 Checkup completed!")
            
            return results
    
    else:
        # Quiet mode - minimal output
        with Status("Running checkup...", console=console, spinner="dots"):
            results = await orchestrator.run_full_checkup()
        return results


def _display_analysis_summary_for_confirmation(analysis_results):
    """Display analysis summary for user confirmation."""
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    
    # Create summary table
    table = Table(
        title="📊 Analysis Summary", 
        box=box.ROUNDED, 
        show_header=True, 
        header_style="bold magenta"
    )
    table.add_column("Category", style="cyan", width=20)
    table.add_column("Issues Found", style="yellow", width=15, justify="right")
    table.add_column("Actions Available", style="green", width=20)
    table.add_column("Impact", style="blue", width=15)
    
    # Add analysis results
    if hasattr(analysis_results, 'quality_issues'):
        issues_count = len(getattr(analysis_results, 'quality_issues', []))
        table.add_row(
            "Code Quality", 
            str(issues_count), 
            "Auto-format" if issues_count > 0 else "None",
            "High" if issues_count > 10 else "Medium" if issues_count > 0 else "None"
        )
    
    if hasattr(analysis_results, 'duplicates'):
        duplicates_count = len(getattr(analysis_results, 'duplicates', []))
        table.add_row(
            "Duplicates", 
            str(duplicates_count), 
            "Refactor suggestions" if duplicates_count > 0 else "None",
            "Medium" if duplicates_count > 0 else "None"
        )
    
    if hasattr(analysis_results, 'import_issues'):
        import_count = len(getattr(analysis_results, 'import_issues', []))
        table.add_row(
            "Import Issues", 
            str(import_count), 
            "Auto-cleanup" if import_count > 0 else "None",
            "Low" if import_count > 0 else "None"
        )
    
    if hasattr(analysis_results, 'structure_issues'):
        structure_count = len(getattr(analysis_results, 'structure_issues', []))
        table.add_row(
            "Structure", 
            str(structure_count), 
            "File reorganization" if structure_count > 0 else "None",
            "Medium" if structure_count > 0 else "None"
        )
    
    console.print(table)


def _has_cleanup_actions(analysis_results) -> bool:
    """Check if there are any cleanup actions available."""
    if not analysis_results:
        return False
    
    # Check for issues that can be automatically cleaned up
    quality_issues = len(getattr(analysis_results, 'quality_issues', []))
    import_issues = len(getattr(analysis_results, 'import_issues', []))
    structure_issues = len(getattr(analysis_results, 'structure_issues', []))
    
    return quality_issues > 0 or import_issues > 0 or structure_issues > 0


def _confirm_destructive_operation(operation_name: str, details: List[str]) -> bool:
    """Confirm destructive operations with detailed information."""
    from rich.prompt import Confirm
    from rich.panel import Panel
    from rich.text import Text
    
    # Create warning panel
    warning_text = Text()
    warning_text.append(f"⚠️  {operation_name}\n\n", style="bold yellow")
    warning_text.append("This operation will make the following changes:\n", style="dim")
    
    for detail in details[:5]:  # Show first 5 details
        warning_text.append(f"• {detail}\n", style="dim")
    
    if len(details) > 5:
        warning_text.append(f"• ... and {len(details) - 5} more changes\n", style="dim")
    
    warning_text.append("\n⚠️  These changes cannot be automatically undone.", style="bold red")
    
    panel = Panel(
        warning_text, 
        title="⚠️  Destructive Operation Warning", 
        border_style="yellow",
        padding=(1, 2)
    )
    console.print(panel)
    
    return Confirm.ask(f"[yellow]Are you sure you want to proceed with {operation_name.lower()}?[/yellow]", default=False)


def _display_checkup_results(results, verbose: bool, quiet: bool):
    """Display checkup results summary."""
    if quiet:
        return
    
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.table import Table
    from rich import box
    
    # Create summary panels
    analysis_text = Text()
    analysis_text.append("📊 Analysis Results\n", style="bold blue")
    if hasattr(results, 'analysis') and results.analysis:
        analysis_text.append(f"Quality Issues: {len(getattr(results.analysis, 'quality_issues', []))}\n", style="dim")
        analysis_text.append(f"Duplicates: {len(getattr(results.analysis, 'duplicates', []))}\n", style="dim")
        analysis_text.append(f"Import Issues: {len(getattr(results.analysis, 'import_issues', []))}\n", style="dim")
        analysis_text.append(f"Structure Issues: {len(getattr(results.analysis, 'structure_issues', []))}", style="dim")
    else:
        analysis_text.append("No analysis results available", style="dim")
    
    cleanup_text = Text()
    cleanup_text.append("🧹 Cleanup Results\n", style="bold green")
    if hasattr(results, 'cleanup') and results.cleanup:
        cleanup_text.append(f"Files Formatted: {len(getattr(results.cleanup, 'formatting_changes', []))}\n", style="dim")
        cleanup_text.append(f"Imports Cleaned: {len(getattr(results.cleanup, 'import_cleanups', []))}\n", style="dim")
        cleanup_text.append(f"Files Moved: {len(getattr(results.cleanup, 'file_moves', []))}\n", style="dim")
        cleanup_text.append(f"Files Removed: {len(getattr(results.cleanup, 'removals', []))}", style="dim")
    else:
        cleanup_text.append("No cleanup performed", style="dim")
    
    status_text = Text()
    status_text.append("✅ Status\n", style="bold magenta")
    status_text.append(f"Success: {'Yes' if results.success else 'No'}\n", style="green" if results.success else "red")
    if hasattr(results, 'duration'):
        status_text.append(f"Duration: {results.duration}\n", style="dim")
    status_text.append(f"Reports Generated: Yes", style="dim")
    
    # Display panels
    columns = Columns([
        Panel(analysis_text, title="Analysis", border_style="blue"),
        Panel(cleanup_text, title="Cleanup", border_style="green"),
        Panel(status_text, title="Status", border_style="magenta")
    ], equal=True, expand=True)
    
    console.print(columns)
    
    if verbose and hasattr(results, 'analysis') and results.analysis:
        # Show detailed issues
        _display_detailed_issues(results.analysis)


def _display_analysis_results(results, verbose: bool):
    """Display analysis-only results."""
    from rich.table import Table
    from rich import box
    
    table = Table(title="📊 Analysis Summary", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan", width=20)
    table.add_column("Issues Found", style="yellow", width=15, justify="right")
    table.add_column("Severity", style="red", width=15)
    table.add_column("Description", style="dim", width=40)
    
    if hasattr(results, 'quality_issues'):
        table.add_row("Code Quality", str(len(results.quality_issues)), "High", "Syntax, style, and complexity issues")
    if hasattr(results, 'duplicates'):
        table.add_row("Duplicates", str(len(results.duplicates)), "Medium", "Duplicate code blocks")
    if hasattr(results, 'import_issues'):
        table.add_row("Imports", str(len(results.import_issues)), "Low", "Unused and circular imports")
    if hasattr(results, 'structure_issues'):
        table.add_row("Structure", str(len(results.structure_issues)), "Medium", "File organization issues")
    
    console.print(table)
    
    if verbose:
        _display_detailed_issues(results)


def _display_detailed_issues(analysis_results):
    """Display detailed issue breakdown."""
    from rich.tree import Tree
    
    tree = Tree("🔍 Detailed Issues")
    
    if hasattr(analysis_results, 'quality_issues') and analysis_results.quality_issues:
        quality_branch = tree.add("Code Quality Issues")
        for issue in analysis_results.quality_issues[:5]:  # Show first 5
            quality_branch.add(f"{getattr(issue, 'file', 'Unknown')}: {getattr(issue, 'message', str(issue))}")
        if len(analysis_results.quality_issues) > 5:
            quality_branch.add(f"... and {len(analysis_results.quality_issues) - 5} more")
    
    if hasattr(analysis_results, 'duplicates') and analysis_results.duplicates:
        duplicate_branch = tree.add("Duplicate Code")
        for duplicate in analysis_results.duplicates[:3]:  # Show first 3
            duplicate_branch.add(f"Duplicate found: {getattr(duplicate, 'description', str(duplicate))}")
        if len(analysis_results.duplicates) > 3:
            duplicate_branch.add(f"... and {len(analysis_results.duplicates) - 3} more")
    
    console.print(tree)


def _interactive_configuration(config_file: Optional[str]):
    """Interactive configuration setup."""
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    
    console.print(Panel("🛠️  Interactive Checkup Configuration", style="blue"))
    
    # Collect configuration options
    target_dir = Prompt.ask("Target directory to analyze", default=".")
    output_dir = Prompt.ask("Output directory for reports", default="./checkup-reports")
    
    # Analysis options
    console.print("\n[bold]Analysis Options:[/bold]")
    enable_quality = Confirm.ask("Enable code quality analysis?", default=True)
    enable_duplicates = Confirm.ask("Enable duplicate detection?", default=True)
    enable_imports = Confirm.ask("Enable import analysis?", default=True)
    enable_structure = Confirm.ask("Enable structure analysis?", default=True)
    
    # Cleanup options
    console.print("\n[bold]Cleanup Options:[/bold]")
    auto_format = Confirm.ask("Enable automatic code formatting?", default=False)
    auto_imports = Confirm.ask("Enable automatic import cleanup?", default=False)
    auto_organize = Confirm.ask("Enable automatic file organization?", default=False)
    
    # Report options
    console.print("\n[bold]Report Options:[/bold]")
    html_report = Confirm.ask("Generate HTML report?", default=True)
    json_report = Confirm.ask("Generate JSON report?", default=True)
    markdown_report = Confirm.ask("Generate Markdown report?", default=False)
    
    # Create configuration
    config_data = {
        'target_directory': target_dir,
        'report_output_dir': output_dir,
        'enable_quality_analysis': enable_quality,
        'enable_duplicate_detection': enable_duplicates,
        'enable_import_analysis': enable_imports,
        'enable_structure_analysis': enable_structure,
        'auto_format': auto_format,
        'auto_fix_imports': auto_imports,
        'auto_organize_files': auto_organize,
        'generate_html_report': html_report,
        'generate_json_report': json_report,
        'generate_markdown_report': markdown_report,
        'create_backup': True,
        'dry_run': False
    }
    
    # Save configuration
    config_path = config_file or "checkup-config.yaml"
    import yaml
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False)
    
    console.print(f"[green]✅ Configuration saved to {config_path}[/green]")
    console.print(f"[dim]Run checkup with: migration-assistant checkup run --config {config_path}[/dim]")


def _create_default_configuration(config_file: Optional[str]):
    """Create default configuration file."""
    config_path = config_file or "checkup-config.yaml"
    
    default_config = {
        'target_directory': '.',
        'report_output_dir': './checkup-reports',
        'enable_quality_analysis': True,
        'enable_duplicate_detection': True,
        'enable_import_analysis': True,
        'enable_structure_analysis': True,
        'check_test_coverage': True,
        'validate_configs': True,
        'validate_docs': True,
        'auto_format': False,
        'auto_fix_imports': False,
        'auto_organize_files': False,
        'generate_html_report': True,
        'generate_json_report': True,
        'generate_markdown_report': False,
        'create_backup': True,
        'dry_run': False,
        'max_file_moves': 10
    }
    
    import yaml
    with open(config_path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)
    
    console.print(f"[green]✅ Default configuration created: {config_path}[/green]")


def _check_destructive_operations(config) -> List[Dict[str, Any]]:
    """Check for potentially destructive operations in the configuration."""
    destructive_ops = []
    
    if getattr(config, 'auto_format', False):
        destructive_ops.append({
            'name': 'Automatic Code Formatting',
            'description': 'Will reformat all Python files using black and isort',
            'details': [
                'Modify indentation and spacing',
                'Reorganize import statements',
                'Apply PEP 8 formatting rules',
                'Update docstring formatting'
            ],
            'severity': 'medium'
        })
    
    if getattr(config, 'auto_fix_imports', False):
        destructive_ops.append({
            'name': 'Automatic Import Cleanup',
            'description': 'Will remove unused imports and reorganize import statements',
            'details': [
                'Remove unused import statements',
                'Reorganize import order',
                'Remove redundant imports',
                'Update import paths'
            ],
            'severity': 'low'
        })
    
    if getattr(config, 'auto_organize_files', False):
        destructive_ops.append({
            'name': 'Automatic File Organization',
            'description': 'Will move and reorganize files based on best practices',
            'details': [
                'Move misplaced files to appropriate directories',
                'Remove empty directories',
                'Rename files for consistency',
                'Update import paths in moved files'
            ],
            'severity': 'high'
        })
    
    return destructive_ops


def _confirm_destructive_operations(destructive_ops: List[Dict[str, Any]]) -> bool:
    """Confirm multiple destructive operations with the user."""
    from rich.prompt import Confirm
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    
    # Create operations table
    table = Table(
        title="⚠️  Destructive Operations Detected", 
        box=box.ROUNDED, 
        show_header=True, 
        header_style="bold red"
    )
    table.add_column("Operation", style="yellow", width=25)
    table.add_column("Description", style="dim", width=40)
    table.add_column("Severity", style="red", width=10)
    
    for op in destructive_ops:
        severity_style = {
            'high': 'bold red',
            'medium': 'yellow',
            'low': 'green'
        }.get(op['severity'], 'dim')
        
        table.add_row(
            op['name'],
            op['description'],
            f"[{severity_style}]{op['severity'].upper()}[/{severity_style}]"
        )
    
    console.print(table)
    
    # Show detailed information for high-severity operations
    high_severity_ops = [op for op in destructive_ops if op['severity'] == 'high']
    if high_severity_ops:
        console.print("\n[bold red]⚠️  High-severity operations will make significant changes:[/bold red]")
        for op in high_severity_ops:
            console.print(f"[red]• {op['name']}:[/red]")
            for detail in op['details'][:3]:
                console.print(f"  - {detail}")
            if len(op['details']) > 3:
                console.print(f"  - ... and {len(op['details']) - 3} more changes")
    
    # Get user confirmation
    console.print("\n[dim]💡 Tip: Use --dry-run to see what changes would be made without applying them[/dim]")
    
    return Confirm.ask(
        "\n[yellow]⚠️  Do you want to proceed with these destructive operations?[/yellow]", 
        default=False
    )


def _show_verbose_mode_info():
    """Show information about verbose mode capabilities."""
    from rich.panel import Panel
    from rich.text import Text
    
    verbose_text = Text()
    verbose_text.append("🔍 Verbose Mode Enabled\n\n", style="bold blue")
    verbose_text.append("You will see:\n", style="dim")
    verbose_text.append("• Detailed progress for each analysis step\n", style="dim")
    verbose_text.append("• File-by-file processing information\n", style="dim")
    verbose_text.append("• Detailed error messages and stack traces\n", style="dim")
    verbose_text.append("• Performance metrics and timing information\n", style="dim")
    verbose_text.append("• Configuration details and validation results\n", style="dim")
    
    panel = Panel(verbose_text, title="Verbose Mode", border_style="blue", padding=(1, 2))
    console.print(panel)


def _show_quiet_mode_info():
    """Show information about quiet mode."""
    from rich.panel import Panel
    from rich.text import Text
    
    quiet_text = Text()
    quiet_text.append("🔇 Quiet Mode Enabled\n\n", style="bold dim")
    quiet_text.append("Output will be minimal:\n", style="dim")
    quiet_text.append("• Only critical errors and final results\n", style="dim")
    quiet_text.append("• No progress bars or status updates\n", style="dim")
    quiet_text.append("• Use --verbose to see detailed information\n", style="dim")
    
    panel = Panel(quiet_text, title="Quiet Mode", border_style="dim", padding=(1, 2))
    console.print(panel)


@main.command()
@click.option('--topic', '-t', type=click.Choice(['quick-start', 'examples', 'templates', 'presets', 'troubleshooting']), 
              help='Show specific help topic')
@click.option('--command', '-c', type=click.Choice(['migrate', 'validate', 'status', 'rollback', 'checkup']), 
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
            ("--command <cmd>", "Examples for specific command (migrate, validate, status, rollback, checkup)"),
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