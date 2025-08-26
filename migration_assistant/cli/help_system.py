"""
Help system and examples for the Migration Assistant CLI.

This module provides comprehensive help, examples, and troubleshooting guides
for users of the Migration Assistant CLI.
"""

from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.columns import Columns
from rich.markdown import Markdown
from rich import box


class HelpSystem:
    """Comprehensive help system for the CLI."""
    
    def __init__(self):
        self.console = Console()
    
    def show_quick_start_guide(self):
        """Show quick start guide for new users."""
        guide_text = """
# Quick Start Guide

## 1. List Available Presets
```bash
migration-assistant presets
```

## 2. Start Interactive Migration
```bash
migration-assistant migrate --preset wordpress-mysql
```

## 3. Validate Configuration
```bash
migration-assistant validate --config my-migration.yaml
```

## 4. Check Migration Status
```bash
migration-assistant status --session-id <session-id>
```

## 5. Start API Server
```bash
migration-assistant serve --port 8000
```
        """
        
        panel = Panel(
            Markdown(guide_text),
            title="🚀 Quick Start Guide",
            border_style="green",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def show_command_examples(self, command: Optional[str] = None):
        """Show detailed examples for commands."""
        if command == "migrate":
            self._show_migrate_examples()
        elif command == "validate":
            self._show_validate_examples()
        elif command == "status":
            self._show_status_examples()
        elif command == "rollback":
            self._show_rollback_examples()
        else:
            self._show_all_examples()
    
    def _show_migrate_examples(self):
        """Show migration command examples."""
        examples = [
            {
                "title": "Interactive Migration with Preset",
                "command": "migration-assistant migrate --preset wordpress-mysql",
                "description": "Start an interactive migration using the WordPress/MySQL preset"
            },
            {
                "title": "Migration from Configuration File",
                "command": "migration-assistant migrate --config my-config.yaml",
                "description": "Run migration using a saved configuration file"
            },
            {
                "title": "Dry Run Migration",
                "command": "migration-assistant migrate --config my-config.yaml --dry-run",
                "description": "Test migration without making actual changes"
            },
            {
                "title": "Non-Interactive Migration",
                "command": "migration-assistant migrate --config my-config.yaml --non-interactive",
                "description": "Run migration in batch mode without user prompts"
            },
            {
                "title": "Verbose Migration",
                "command": "migration-assistant --verbose migrate --config my-config.yaml",
                "description": "Run migration with detailed logging output"
            }
        ]
        
        self._display_examples("Migration Examples", examples)
    
    def _show_validate_examples(self):
        """Show validation command examples."""
        examples = [
            {
                "title": "Validate Configuration File",
                "command": "migration-assistant validate --config my-config.yaml",
                "description": "Validate a configuration file and show results in table format"
            },
            {
                "title": "JSON Output Format",
                "command": "migration-assistant validate --config my-config.yaml --format json",
                "description": "Get validation results in JSON format for scripting"
            },
            {
                "title": "YAML Output Format",
                "command": "migration-assistant validate --config my-config.yaml --format yaml",
                "description": "Get validation results in YAML format"
            },
            {
                "title": "Verbose Validation",
                "command": "migration-assistant --verbose validate --config my-config.yaml",
                "description": "Show detailed validation information and configuration summary"
            }
        ]
        
        self._display_examples("Validation Examples", examples)
    
    def _show_status_examples(self):
        """Show status command examples."""
        examples = [
            {
                "title": "Check All Migrations",
                "command": "migration-assistant status",
                "description": "Show status of all migration sessions"
            },
            {
                "title": "Check Specific Migration",
                "command": "migration-assistant status --session-id abc123",
                "description": "Show status of a specific migration session"
            },
            {
                "title": "JSON Status Output",
                "command": "migration-assistant status --format json",
                "description": "Get status information in JSON format"
            },
            {
                "title": "Watch Migration Progress",
                "command": "migration-assistant status --session-id abc123 --watch",
                "description": "Continuously monitor migration progress (future feature)"
            }
        ]
        
        self._display_examples("Status Examples", examples)
    
    def _show_rollback_examples(self):
        """Show rollback command examples."""
        examples = [
            {
                "title": "Interactive Rollback",
                "command": "migration-assistant rollback --session-id abc123",
                "description": "Rollback a migration with user confirmation"
            },
            {
                "title": "Force Rollback",
                "command": "migration-assistant rollback --session-id abc123 --force",
                "description": "Rollback without confirmation prompt"
            },
            {
                "title": "Verbose Rollback",
                "command": "migration-assistant --verbose rollback --session-id abc123",
                "description": "Rollback with detailed logging information"
            }
        ]
        
        self._display_examples("Rollback Examples", examples)
    
    def _show_all_examples(self):
        """Show examples for all commands."""
        self.console.print("[bold blue]📚 Command Examples[/bold blue]\n")
        
        commands = ["migrate", "validate", "status", "rollback"]
        for command in commands:
            self.show_command_examples(command)
            self.console.print()
    
    def _display_examples(self, title: str, examples: List[Dict[str, str]]):
        """Display a list of examples in a formatted table."""
        table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("Example", style="cyan", width=40)
        table.add_column("Command", style="green", width=50)
        table.add_column("Description", style="dim", width=40)
        
        for example in examples:
            table.add_row(
                example["title"],
                f"[code]{example['command']}[/code]",
                example["description"]
            )
        
        self.console.print(table)
    
    def show_troubleshooting_guide(self):
        """Show comprehensive troubleshooting guide."""
        troubleshooting_text = """
# Troubleshooting Guide

## Common Issues

### Configuration Errors
- **Invalid YAML/JSON format**: Check file syntax with a validator
- **Missing required fields**: Use `validate` command to identify missing fields
- **Unsupported file format**: Use `.yaml`, `.yml`, or `.toml` extensions

### Connection Issues
- **Database connection failed**: Verify credentials and network connectivity
- **SSH connection timeout**: Check firewall settings and SSH key permissions
- **Cloud authentication failed**: Verify API keys and permissions

### Migration Failures
- **Insufficient disk space**: Check available space on source and destination
- **Permission denied**: Verify file and database permissions
- **Network timeout**: Check network stability and bandwidth

## Getting Help

### Verbose Output
Add `--verbose` flag to any command for detailed information:
```bash
migration-assistant --verbose migrate --config my-config.yaml
```

### Validation
Always validate your configuration before migration:
```bash
migration-assistant validate --config my-config.yaml
```

### Log Files
Check log files in `~/.migration-assistant/logs/` for detailed error information.

### Support
- GitHub Issues: https://github.com/migration-assistant/issues
- Documentation: https://migration-assistant.readthedocs.io
- Email: support@migration-assistant.com
        """
        
        panel = Panel(
            Markdown(troubleshooting_text),
            title="🔧 Troubleshooting Guide",
            border_style="yellow",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def show_configuration_templates(self):
        """Show configuration file templates for different scenarios."""
        templates = {
            "WordPress to AWS S3": {
                "description": "Migrate WordPress site to AWS S3 with RDS",
                "config": """
name: "WordPress to AWS Migration"
source:
  type: wordpress
  host: "old-site.com"
  database:
    type: mysql
    host: "db.old-site.com"
    username: "wp_user"
    password: "secure_password"
    database: "wordpress_db"
destination:
  type: aws-s3
  host: "s3.amazonaws.com"
  bucket: "my-new-site"
  database:
    type: aurora-mysql
    host: "aurora.us-east-1.rds.amazonaws.com"
transfer:
  files: s3_sync
  database: dump_restore
options:
  maintenance_mode: true
  backup_before: true
  verify_after: true
                """
            },
            "Django to Google Cloud": {
                "description": "Migrate Django application to Google Cloud Platform",
                "config": """
name: "Django to GCP Migration"
source:
  type: django
  host: "192.168.1.100"
  database:
    type: postgresql
    host: "localhost"
    username: "django_user"
    password: "secure_password"
    database: "django_db"
destination:
  type: gcp-storage
  host: "storage.googleapis.com"
  bucket: "my-django-app"
  database:
    type: cloud-sql-postgres
    instance: "my-instance"
transfer:
  files: gcs_sync
  database: pg_dump_restore
options:
  maintenance_mode: true
  backup_before: true
                """
            },
            "Static Site to Netlify": {
                "description": "Migrate static website to Netlify",
                "config": """
name: "Static Site to Netlify"
source:
  type: static
  host: "old-hosting.com"
  path: "/var/www/html"
destination:
  type: netlify
  site_id: "my-netlify-site"
transfer:
  files: netlify_deploy
options:
  backup_before: true
  verify_after: true
                """
            }
        }
        
        self.console.print("[bold blue]📄 Configuration Templates[/bold blue]\n")
        
        for template_name, template_data in templates.items():
            panel = Panel(
                f"[dim]{template_data['description']}[/dim]\n\n[code]{template_data['config'].strip()}[/code]",
                title=f"📋 {template_name}",
                border_style="blue",
                padding=(1, 2)
            )
            self.console.print(panel)
            self.console.print()
    
    def show_preset_details(self):
        """Show detailed information about available presets."""
        preset_info = {
            "wordpress-mysql": {
                "name": "WordPress with MySQL",
                "description": "Standard WordPress installation with MySQL database",
                "source_types": ["wordpress", "cms"],
                "destination_types": ["aws-s3", "gcp-storage", "azure-blob", "static"],
                "features": ["Database migration", "File transfer", "Plugin preservation", "Theme migration"]
            },
            "django-postgres": {
                "name": "Django with PostgreSQL", 
                "description": "Django web application with PostgreSQL database",
                "source_types": ["django", "python-web"],
                "destination_types": ["aws-ec2", "gcp-compute", "azure-vm", "heroku"],
                "features": ["Database migration", "Static files", "Environment variables", "Dependencies"]
            },
            "static-site": {
                "name": "Static Website",
                "description": "Static HTML/CSS/JS website",
                "source_types": ["static", "html"],
                "destination_types": ["aws-s3", "netlify", "vercel", "github-pages"],
                "features": ["File transfer", "CDN setup", "Domain configuration"]
            },
            "laravel-mysql": {
                "name": "Laravel with MySQL",
                "description": "Laravel PHP application with MySQL database",
                "source_types": ["laravel", "php-web"],
                "destination_types": ["aws-ec2", "digitalocean", "linode"],
                "features": ["Database migration", "Composer dependencies", "Environment config", "Storage links"]
            }
        }
        
        self.console.print("[bold blue]🎯 Available Presets[/bold blue]\n")
        
        for preset_key, preset_data in preset_info.items():
            # Create a tree structure for each preset
            tree = Tree(f"[bold cyan]{preset_data['name']}[/bold cyan] ([dim]{preset_key}[/dim])")
            tree.add(f"[green]Description:[/green] {preset_data['description']}")
            
            # Source types
            source_branch = tree.add("[yellow]Source Types:[/yellow]")
            for source_type in preset_data['source_types']:
                source_branch.add(f"• {source_type}")
            
            # Destination types
            dest_branch = tree.add("[blue]Destination Types:[/blue]")
            for dest_type in preset_data['destination_types']:
                dest_branch.add(f"• {dest_type}")
            
            # Features
            features_branch = tree.add("[magenta]Features:[/magenta]")
            for feature in preset_data['features']:
                features_branch.add(f"• {feature}")
            
            self.console.print(tree)
            self.console.print()
    
    def show_interactive_help_menu(self):
        """Show an interactive help menu."""
        from rich.prompt import Prompt
        
        while True:
            self.console.print("\n[bold blue]📖 Migration Assistant Help System[/bold blue]\n")
            
            options = [
                "1. Quick Start Guide",
                "2. Command Examples", 
                "3. Configuration Templates",
                "4. Available Presets",
                "5. Troubleshooting Guide",
                "6. Exit Help"
            ]
            
            for option in options:
                self.console.print(f"  {option}")
            
            choice = Prompt.ask(
                "\n[cyan]Select an option[/cyan]",
                choices=["1", "2", "3", "4", "5", "6"],
                default="1"
            )
            
            self.console.print()
            
            if choice == "1":
                self.show_quick_start_guide()
            elif choice == "2":
                self._show_command_examples_menu()
            elif choice == "3":
                self.show_configuration_templates()
            elif choice == "4":
                self.show_preset_details()
            elif choice == "5":
                self.show_troubleshooting_guide()
            elif choice == "6":
                self.console.print("[green]👋 Happy migrating![/green]")
                break
            
            input("\nPress Enter to continue...")
    
    def _show_command_examples_menu(self):
        """Show command examples submenu."""
        from rich.prompt import Prompt
        
        self.console.print("[bold blue]📚 Command Examples[/bold blue]\n")
        
        options = [
            "1. Migration Examples",
            "2. Validation Examples",
            "3. Status Examples", 
            "4. Rollback Examples",
            "5. All Examples",
            "6. Back to Main Menu"
        ]
        
        for option in options:
            self.console.print(f"  {option}")
        
        choice = Prompt.ask(
            "\n[cyan]Select command examples[/cyan]",
            choices=["1", "2", "3", "4", "5", "6"],
            default="5"
        )
        
        self.console.print()
        
        if choice == "1":
            self._show_migrate_examples()
        elif choice == "2":
            self._show_validate_examples()
        elif choice == "3":
            self._show_status_examples()
        elif choice == "4":
            self._show_rollback_examples()
        elif choice == "5":
            self._show_all_examples()
        # choice == "6" returns to main menu