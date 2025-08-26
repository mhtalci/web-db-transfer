"""
Enhanced preset management system with hierarchical organization.

This module provides an improved preset management system that supports
hierarchical organization, dynamic filtering, and easy extensibility.
"""

from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from migration_assistant.cli.preset_registry import (
    PresetRegistry, PresetConfiguration, SourceCategory, 
    DestinationCategory, ApplicationStack
)
from migration_assistant.cli.preset_templates import PresetGenerator
from migration_assistant.models.config import MigrationConfig


class EnhancedPresetManager:
    """
    Enhanced preset manager with hierarchical organization and filtering.
    
    Features:
    - Hierarchical browsing (Source → Destination → Application)
    - Dynamic filtering and searching
    - Template-based preset generation
    - Easy extensibility
    """
    
    def __init__(self, preset_dir: Optional[str] = None):
        """
        Initialize the enhanced preset manager.
        
        Args:
            preset_dir: Optional directory for external preset files
        """
        self.console = Console()
        self.registry = PresetRegistry(preset_dir)
        self.generator = PresetGenerator()
        
        # Generate additional presets from templates
        self._populate_generated_presets()
    
    def _populate_generated_presets(self) -> None:
        """Populate registry with generated presets."""
        generated_presets = self.generator.generate_all_presets()
        for preset in generated_presets:
            self.registry.add_preset(preset)
    
    def show_hierarchical_menu(self) -> Optional[str]:
        """
        Display hierarchical preset selection menu.
        
        Returns:
            Selected preset key or None if cancelled
        """
        self.console.rule("[bold cyan]Migration Preset Selection")
        
        # Step 1: Select source category
        source_category = self._select_source_category()
        if not source_category:
            return None
        
        # Step 2: Select destination category
        destination_category = self._select_destination_category(source_category)
        if not destination_category:
            return None
        
        # Step 3: Select application stack
        application_stack = self._select_application_stack(source_category, destination_category)
        if not application_stack:
            return None
        
        # Step 4: Select specific preset
        return self._select_specific_preset(source_category, destination_category, application_stack)
    
    def _select_source_category(self) -> Optional[SourceCategory]:
        """Select source category with Rich formatting."""
        self.console.print("[bold]Step 1: Select Source System Category[/bold]")
        
        categories = [
            (SourceCategory.CONTROL_PANEL, "Control Panel Hosting", "cPanel, DirectAdmin, Plesk"),
            (SourceCategory.VPS_SERVER, "VPS/Dedicated Server", "Linux/Windows servers"),
            (SourceCategory.CLOUD_PLATFORM, "Cloud Platform", "AWS, GCP, Azure services"),
            (SourceCategory.CONTAINER, "Container Platform", "Docker, Podman containers"),
            (SourceCategory.STATIC_HOSTING, "Static Site Hosting", "GitHub Pages, Netlify"),
            (SourceCategory.CMS_PLATFORM, "CMS Platform", "WordPress, Drupal, Joomla"),
            (SourceCategory.FRAMEWORK, "Web Framework", "Django, Laravel, Next.js"),
            (SourceCategory.DATABASE, "Database Server", "MySQL, PostgreSQL, MongoDB"),
            (SourceCategory.FILE_SYSTEM, "File System", "Local files, network shares")
        ]
        
        table = Table(title="Source Categories", box=box.ROUNDED)
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Category", style="green", width=25)
        table.add_column("Examples", style="dim")
        
        for i, (category, name, examples) in enumerate(categories, 1):
            table.add_row(str(i), name, examples)
        
        self.console.print(table)
        
        from rich.prompt import Prompt
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select source category (1-{len(categories)}, 0 to cancel)[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice)
                
                if choice_idx == 0:
                    return None
                elif 1 <= choice_idx <= len(categories):
                    selected = categories[choice_idx - 1][0]
                    self.console.print(f"[green]Selected: {categories[choice_idx - 1][1]}[/green]")
                    return selected
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
    
    def _select_destination_category(self, source_category: SourceCategory) -> Optional[DestinationCategory]:
        """Select destination category based on source."""
        self.console.print(f"\n[bold]Step 2: Select Destination for {source_category.value.replace('_', ' ').title()}[/bold]")
        
        # Get available destinations for this source
        available_destinations = self._get_available_destinations(source_category)
        
        if not available_destinations:
            self.console.print("[yellow]No destinations available for this source category.[/yellow]")
            return None
        
        table = Table(title="Available Destinations", box=box.ROUNDED)
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Destination", style="green", width=25)
        table.add_column("Description", style="dim")
        
        dest_info = {
            DestinationCategory.VPS_SERVER: ("VPS/Dedicated Server", "Linux/Windows servers"),
            DestinationCategory.CLOUD_PLATFORM: ("Cloud Platform", "AWS, GCP, Azure"),
            DestinationCategory.CONTAINER_PLATFORM: ("Container Platform", "Kubernetes, Docker Swarm"),
            DestinationCategory.STATIC_HOSTING: ("Static Hosting", "S3, Netlify, Vercel"),
            DestinationCategory.MANAGED_HOSTING: ("Managed Hosting", "Vercel, Netlify, Heroku"),
            DestinationCategory.DATABASE_SERVICE: ("Database Service", "RDS, Cloud SQL"),
            DestinationCategory.CDN_SERVICE: ("CDN Service", "CloudFront, CloudFlare")
        }
        
        for i, dest_cat in enumerate(available_destinations, 1):
            name, desc = dest_info.get(dest_cat, (dest_cat.value, ""))
            table.add_row(str(i), name, desc)
        
        self.console.print(table)
        
        from rich.prompt import Prompt
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select destination (1-{len(available_destinations)}, 0 to go back)[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice)
                
                if choice_idx == 0:
                    return None
                elif 1 <= choice_idx <= len(available_destinations):
                    selected = available_destinations[choice_idx - 1]
                    dest_name = dest_info.get(selected, (selected.value, ""))[0]
                    self.console.print(f"[green]Selected: {dest_name}[/green]")
                    return selected
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
    
    def _select_application_stack(
        self, 
        source_category: SourceCategory, 
        destination_category: DestinationCategory
    ) -> Optional[ApplicationStack]:
        """Select application stack based on source and destination."""
        self.console.print(f"\n[bold]Step 3: Select Application/Stack Type[/bold]")
        
        # Get available applications for this combination
        available_apps = self._get_available_applications(source_category, destination_category)
        
        if not available_apps:
            self.console.print("[yellow]No applications available for this combination.[/yellow]")
            return None
        
        table = Table(title="Available Applications", box=box.ROUNDED)
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Application", style="green", width=20)
        table.add_column("Type", style="blue", width=15)
        table.add_column("Description", style="dim")
        
        app_info = {
            ApplicationStack.GENERIC_WEBSITE: ("Generic Website", "Web", "Any website or web app"),
            ApplicationStack.WORDPRESS: ("WordPress", "CMS", "WordPress CMS"),
            ApplicationStack.DRUPAL: ("Drupal", "CMS", "Drupal CMS"),
            ApplicationStack.DJANGO: ("Django", "Framework", "Python web framework"),
            ApplicationStack.LARAVEL: ("Laravel", "Framework", "PHP web framework"),
            ApplicationStack.NEXTJS: ("Next.js", "Framework", "React framework"),
            ApplicationStack.STATIC_SITE: ("Static Site", "Static", "HTML/CSS/JS only"),
            ApplicationStack.HUGO: ("Hugo", "Static", "Hugo static site generator"),
            ApplicationStack.GATSBY: ("Gatsby", "Static", "Gatsby static site generator")
        }
        
        for i, app_stack in enumerate(available_apps, 1):
            name, type_desc, desc = app_info.get(app_stack, (app_stack.value, "Unknown", ""))
            table.add_row(str(i), name, type_desc, desc)
        
        self.console.print(table)
        
        from rich.prompt import Prompt
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select application (1-{len(available_apps)}, 0 to go back)[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice)
                
                if choice_idx == 0:
                    return None
                elif 1 <= choice_idx <= len(available_apps):
                    selected = available_apps[choice_idx - 1]
                    app_name = app_info.get(selected, (selected.value, "", ""))[0]
                    self.console.print(f"[green]Selected: {app_name}[/green]")
                    return selected
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
    
    def _select_specific_preset(
        self,
        source_category: SourceCategory,
        destination_category: DestinationCategory,
        application_stack: ApplicationStack
    ) -> Optional[str]:
        """Select specific preset from filtered results."""
        self.console.print(f"\n[bold]Step 4: Select Migration Preset[/bold]")
        
        # Filter presets
        filtered_presets = self.registry.filter_presets(
            source_category=source_category,
            destination_category=destination_category,
            application_stack=application_stack
        )
        
        if not filtered_presets:
            self.console.print("[yellow]No presets available for this combination.[/yellow]")
            self.console.print("[dim]Consider creating a custom configuration.[/dim]")
            return None
        
        table = Table(title="Available Migration Presets", box=box.ROUNDED)
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Name", style="green", width=30)
        table.add_column("Complexity", style="blue", width=12)
        table.add_column("Est. Time", style="yellow", width=15)
        table.add_column("Description", style="dim")
        
        for i, preset in enumerate(filtered_presets, 1):
            table.add_row(
                str(i),
                preset.metadata.name,
                preset.metadata.complexity.title(),
                preset.metadata.estimated_time,
                preset.metadata.description
            )
        
        self.console.print(table)
        
        from rich.prompt import Prompt
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select preset (1-{len(filtered_presets)}, 0 to go back)[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice)
                
                if choice_idx == 0:
                    return None
                elif 1 <= choice_idx <= len(filtered_presets):
                    selected_preset = filtered_presets[choice_idx - 1]
                    self.console.print(f"[green]Selected: {selected_preset.metadata.name}[/green]")
                    
                    # Show preset details
                    self._show_preset_details(selected_preset)
                    
                    from rich.prompt import Confirm
                    if Confirm.ask("[cyan]Use this preset?[/cyan]", default=True, console=self.console):
                        return selected_preset.metadata.key
                    else:
                        continue
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
    
    def _show_preset_details(self, preset: PresetConfiguration) -> None:
        """Show detailed information about a preset."""
        details_table = Table(title=f"Preset Details: {preset.metadata.name}", box=box.MINIMAL)
        details_table.add_column("Property", style="cyan", width=20)
        details_table.add_column("Value", style="green")
        
        details_table.add_row("Complexity", preset.metadata.complexity.title())
        details_table.add_row("Estimated Time", preset.metadata.estimated_time)
        details_table.add_row("Version", preset.metadata.version)
        
        if preset.metadata.prerequisites:
            prereqs = ", ".join(preset.metadata.prerequisites)
            details_table.add_row("Prerequisites", prereqs)
        
        if preset.metadata.tags:
            tags = ", ".join(preset.metadata.tags)
            details_table.add_row("Tags", tags)
        
        self.console.print(details_table)
        self.console.print()
    
    def _get_available_destinations(self, source_category: SourceCategory) -> List[DestinationCategory]:
        """Get available destination categories for a source category."""
        structure = self.registry.get_hierarchical_structure()
        source_key = source_category.value
        
        if source_key in structure:
            return [DestinationCategory(dest) for dest in structure[source_key].keys()]
        
        return []
    
    def _get_available_applications(
        self, 
        source_category: SourceCategory, 
        destination_category: DestinationCategory
    ) -> List[ApplicationStack]:
        """Get available application stacks for source/destination combination."""
        structure = self.registry.get_hierarchical_structure()
        source_key = source_category.value
        dest_key = destination_category.value
        
        if source_key in structure and dest_key in structure[source_key]:
            return [ApplicationStack(app) for app in structure[source_key][dest_key].keys()]
        
        return []
    
    def show_preset_tree(self) -> None:
        """Display all presets in a tree structure."""
        self.console.rule("[bold cyan]Available Migration Presets")
        
        structure = self.registry.get_hierarchical_structure()
        tree = Tree("Migration Presets", style="bold blue")
        
        for source_cat, destinations in structure.items():
            source_node = tree.add(f"[bold green]{source_cat.replace('_', ' ').title()}[/bold green]")
            
            for dest_cat, applications in destinations.items():
                dest_node = source_node.add(f"[bold yellow]→ {dest_cat.replace('_', ' ').title()}[/bold yellow]")
                
                for app_stack, presets in applications.items():
                    app_node = dest_node.add(f"[bold magenta]→ {app_stack.replace('_', ' ').title()}[/bold magenta]")
                    
                    for preset in presets:
                        complexity_color = {
                            "simple": "green",
                            "medium": "yellow", 
                            "complex": "red"
                        }.get(preset.metadata.complexity, "white")
                        
                        app_node.add(
                            f"[{complexity_color}]{preset.metadata.name}[/{complexity_color}] "
                            f"[dim]({preset.metadata.complexity}, {preset.metadata.estimated_time})[/dim]"
                        )
        
        self.console.print(tree)
    
    def search_presets_interactive(self) -> Optional[str]:
        """Interactive preset search."""
        from rich.prompt import Prompt
        
        query = Prompt.ask("[cyan]Enter search query[/cyan]", console=self.console)
        if not query:
            return None
        
        results = self.registry.search_presets(query)
        
        if not results:
            self.console.print(f"[yellow]No presets found matching '{query}'[/yellow]")
            return None
        
        self.console.print(f"[green]Found {len(results)} preset(s) matching '{query}':[/green]")
        
        table = Table(title="Search Results", box=box.ROUNDED)
        table.add_column("Option", style="cyan", width=8)
        table.add_column("Name", style="green", width=30)
        table.add_column("Category", style="blue", width=20)
        table.add_column("Complexity", style="yellow", width=12)
        table.add_column("Description", style="dim")
        
        for i, preset in enumerate(results, 1):
            category = f"{preset.metadata.source_category.value} → {preset.metadata.destination_category.value}"
            table.add_row(
                str(i),
                preset.metadata.name,
                category.replace('_', ' ').title(),
                preset.metadata.complexity.title(),
                preset.metadata.description
            )
        
        self.console.print(table)
        
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select preset (1-{len(results)}, 0 to cancel)[/cyan]",
                    console=self.console
                )
                choice_idx = int(choice)
                
                if choice_idx == 0:
                    return None
                elif 1 <= choice_idx <= len(results):
                    selected_preset = results[choice_idx - 1]
                    self._show_preset_details(selected_preset)
                    
                    from rich.prompt import Confirm
                    if Confirm.ask("[cyan]Use this preset?[/cyan]", default=True, console=self.console):
                        return selected_preset.metadata.key
                    else:
                        continue
                else:
                    self.console.print("[red]Invalid selection.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
    
    def get_preset_configuration(self, preset_key: str) -> Optional[MigrationConfig]:
        """
        Get MigrationConfig from preset key.
        
        Args:
            preset_key: Preset identifier
            
        Returns:
            MigrationConfig instance or None if not found
        """
        preset = self.registry.get_preset(preset_key)
        if not preset:
            return None
        
        try:
            # Convert preset configuration to MigrationConfig
            config_data = preset.configuration.copy()
            config_data["name"] = preset.metadata.name
            config_data["description"] = preset.metadata.description
            
            return MigrationConfig(**config_data)
        except Exception as e:
            self.console.print(f"[red]Error creating configuration from preset: {e}[/red]")
            return None
    
    def list_presets_by_category(self, format: str = "table") -> None:
        """List presets organized by category."""
        if format == "table":
            self._list_presets_table()
        elif format == "tree":
            self.show_preset_tree()
        elif format == "json":
            self._list_presets_json()
        elif format == "yaml":
            self._list_presets_yaml()
    
    def _list_presets_table(self) -> None:
        """List presets in table format."""
        presets = self.registry.list_presets()
        
        table = Table(title="All Migration Presets", box=box.ROUNDED)
        table.add_column("Key", style="cyan", width=25)
        table.add_column("Name", style="green", width=30)
        table.add_column("Source → Destination", style="blue", width=25)
        table.add_column("App", style="magenta", width=15)
        table.add_column("Complexity", style="yellow", width=10)
        table.add_column("Time", style="dim", width=15)
        
        # Sort by source category, then destination, then application
        sorted_presets = sorted(
            presets,
            key=lambda p: (
                p.metadata.source_category.value,
                p.metadata.destination_category.value,
                p.metadata.application_stack.value
            )
        )
        
        for preset in sorted_presets:
            source_dest = f"{preset.metadata.source_category.value} → {preset.metadata.destination_category.value}"
            source_dest = source_dest.replace('_', ' ').title()
            
            table.add_row(
                preset.metadata.key,
                preset.metadata.name,
                source_dest,
                preset.metadata.application_stack.value.replace('_', ' ').title(),
                preset.metadata.complexity.title(),
                preset.metadata.estimated_time
            )
        
        self.console.print(table)
    
    def _list_presets_json(self) -> None:
        """List presets in JSON format."""
        import json
        
        presets_data = []
        for preset in self.registry.list_presets():
            presets_data.append({
                "key": preset.metadata.key,
                "name": preset.metadata.name,
                "description": preset.metadata.description,
                "source_category": preset.metadata.source_category.value,
                "destination_category": preset.metadata.destination_category.value,
                "application_stack": preset.metadata.application_stack.value,
                "complexity": preset.metadata.complexity,
                "estimated_time": preset.metadata.estimated_time,
                "tags": preset.metadata.tags
            })
        
        self.console.print(json.dumps(presets_data, indent=2))
    
    def _list_presets_yaml(self) -> None:
        """List presets in YAML format."""
        import yaml
        
        presets_data = []
        for preset in self.registry.list_presets():
            presets_data.append({
                "key": preset.metadata.key,
                "name": preset.metadata.name,
                "description": preset.metadata.description,
                "source_category": preset.metadata.source_category.value,
                "destination_category": preset.metadata.destination_category.value,
                "application_stack": preset.metadata.application_stack.value,
                "complexity": preset.metadata.complexity,
                "estimated_time": preset.metadata.estimated_time,
                "tags": preset.metadata.tags
            })
        
        self.console.print(yaml.dump(presets_data, default_flow_style=False, indent=2))
    
    def get_preset_count_by_category(self) -> Dict[str, int]:
        """Get count of presets by category."""
        counts = {
            "total": len(self.registry.presets),
            "by_source": {},
            "by_destination": {},
            "by_application": {},
            "by_complexity": {}
        }
        
        for preset in self.registry.list_presets():
            # Count by source category
            source = preset.metadata.source_category.value
            counts["by_source"][source] = counts["by_source"].get(source, 0) + 1
            
            # Count by destination category
            dest = preset.metadata.destination_category.value
            counts["by_destination"][dest] = counts["by_destination"].get(dest, 0) + 1
            
            # Count by application stack
            app = preset.metadata.application_stack.value
            counts["by_application"][app] = counts["by_application"].get(app, 0) + 1
            
            # Count by complexity
            complexity = preset.metadata.complexity
            counts["by_complexity"][complexity] = counts["by_complexity"].get(complexity, 0) + 1
        
        return counts