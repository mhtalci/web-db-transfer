#!/usr/bin/env python3
"""
Comprehensive demonstration of the ValidationEngine for the Migration Assistant.

This example shows how to use the ValidationEngine to orchestrate all validation
checks, aggregate results, and provide Rich-formatted reporting with remediation
suggestions.
"""

import asyncio
import tempfile
from pathlib import Path

from rich.console import Console

from migration_assistant.models.config import (
    SystemType, DatabaseType, TransferMethod, MigrationConfig,
    SystemConfig, DatabaseConfig, TransferConfig, MigrationOptions,
    AuthConfig, PathConfig, CloudConfig, AuthType
)
from migration_assistant.validation.engine import (
    ValidationEngine, ValidationCategory, ValidationSeverity
)


async def demo_successful_validation():
    """Demonstrate validation with a configuration that should mostly pass."""
    console = Console()
    console.print("\n[bold blue]🎯 Demo 1: Successful Validation Scenario[/bold blue]")
    console.print("=" * 60)
    
    # Create a simple, likely-to-succeed configuration
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "source"
        dest_path = temp_path / "destination"
        source_path.mkdir()
        dest_path.mkdir()
        
        # Create test files
        (source_path / "index.html").write_text("<html><body>Static Site</body></html>")
        (source_path / "style.css").write_text("body { margin: 0; }")
        
        # Simple static site migration (fewer dependencies)
        auth_config = AuthConfig(
            type=AuthType.SSH_KEY,
            username="deploy",
            ssh_key_path="~/.ssh/id_rsa"
        )
        
        source_system = SystemConfig(
            type=SystemType.STATIC_SITE,
            host="source.example.com",
            authentication=auth_config,
            paths=PathConfig(
                root_path=str(source_path),
                web_root=str(source_path)
            )
        )
        
        destination_system = SystemConfig(
            type=SystemType.STATIC_SITE,
            host="dest.example.com",
            authentication=auth_config,
            paths=PathConfig(
                root_path=str(dest_path),
                web_root=str(dest_path)
            )
        )
        
        migration_config = MigrationConfig(
            name="Static Site Migration",
            description="Simple static site migration with minimal dependencies",
            source=source_system,
            destination=destination_system,
            transfer=TransferConfig(
                method=TransferMethod.RSYNC,
                parallel_transfers=2,
                compression_enabled=True
            ),
            options=MigrationOptions(
                backup_before=True,
                verify_after=True
            )
        )
        
        # Run validation
        engine = ValidationEngine(console=console)
        summary = await engine.validate_migration(migration_config)
        
        # Display additional insights
        console.print(f"\n[bold]📊 Validation Insights:[/bold]")
        console.print(f"• Configuration complexity: [green]Low[/green] (static site)")
        console.print(f"• Expected success rate: [green]High[/green] (minimal dependencies)")
        console.print(f"• Recommended for: [cyan]Beginners[/cyan]")
        
        return summary


async def demo_complex_migration_validation():
    """Demonstrate validation with a complex migration that may have issues."""
    console = Console()
    console.print("\n[bold yellow]🎯 Demo 2: Complex Migration Scenario[/bold yellow]")
    console.print("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "wordpress"
        dest_path = temp_path / "destination"
        source_path.mkdir()
        dest_path.mkdir()
        
        # Create WordPress-like structure
        (source_path / "wp-config.php").write_text("<?php // WordPress config ?>")
        (source_path / "index.php").write_text("<?php // WordPress index ?>")
        wp_content = source_path / "wp-content"
        wp_content.mkdir()
        (wp_content / "themes").mkdir()
        (wp_content / "plugins").mkdir()
        
        # Complex WordPress to cloud migration
        source_auth = AuthConfig(
            type=AuthType.PASSWORD,
            username="wp_admin",
            password="complex_password_123"
        )
        
        dest_auth = AuthConfig(
            type=AuthType.API_KEY,
            api_key="aws_access_key_id",
            api_secret="aws_secret_access_key"
        )
        
        source_db = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="mysql.shared-hosting.com",
            port=3306,
            database_name="wp_database",
            username="wp_user",
            password="wp_db_password"
        )
        
        # Cloud destination with different database
        dest_db = DatabaseConfig(
            type=DatabaseType.AWS_RDS,
            host="rds.us-east-1.amazonaws.com",
            port=5432,  # PostgreSQL port
            database_name="wordpress_prod",
            username="postgres",
            password="secure_rds_password"
        )
        
        cloud_config = CloudConfig(
            provider="aws",
            region="us-east-1",
            bucket_name="wordpress-migration-bucket",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )
        
        source_system = SystemConfig(
            type=SystemType.WORDPRESS,
            host="shared-hosting.example.com",
            authentication=source_auth,
            paths=PathConfig(
                root_path=str(source_path),
                web_root=str(source_path),
                config_path=str(source_path / "wp-config.php"),
                backup_path=str(temp_path / "backups")
            ),
            database=source_db
        )
        
        destination_system = SystemConfig(
            type=SystemType.DOCKER_CONTAINER,
            host="aws-ec2-instance.amazonaws.com",
            authentication=dest_auth,
            paths=PathConfig(
                root_path=str(dest_path),
                web_root=str(dest_path / "public"),
                config_path=str(dest_path / "config")
            ),
            database=dest_db,
            cloud_config=cloud_config
        )
        
        migration_config = MigrationConfig(
            name="WordPress to AWS Docker Migration",
            description="Complex migration from shared hosting to AWS with database conversion",
            source=source_system,
            destination=destination_system,
            transfer=TransferConfig(
                method=TransferMethod.HYBRID_SYNC,  # Uses Go acceleration
                parallel_transfers=8,
                compression_enabled=True,
                verify_checksums=True,
                use_go_acceleration=True
            ),
            options=MigrationOptions(
                maintenance_mode=True,
                backup_before=True,
                backup_destination=True,
                verify_after=True,
                rollback_on_failure=True,
                preserve_permissions=True,
                preserve_timestamps=True
            )
        )
        
        # Run validation
        engine = ValidationEngine(console=console)
        summary = await engine.validate_migration(migration_config)
        
        # Display complexity analysis
        console.print(f"\n[bold]🔍 Complexity Analysis:[/bold]")
        console.print(f"• Configuration complexity: [red]High[/red] (WordPress + Cloud + DB conversion)")
        console.print(f"• Database conversion: [yellow]MySQL → PostgreSQL[/yellow]")
        console.print(f"• Platform change: [yellow]Shared hosting → Docker/AWS[/yellow]")
        console.print(f"• Expected challenges: [red]Multiple[/red] (dependencies, permissions, compatibility)")
        
        return summary


async def demo_validation_categories():
    """Demonstrate validation of individual categories."""
    console = Console()
    console.print("\n[bold cyan]🎯 Demo 3: Category-Specific Validation[/bold cyan]")
    console.print("=" * 60)
    
    # Create a test configuration
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "source"
        dest_path = temp_path / "destination"
        source_path.mkdir()
        dest_path.mkdir()
        
        auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
        
        migration_config = MigrationConfig(
            name="Category Test Migration",
            description="Testing individual validation categories",
            source=SystemConfig(
                type=SystemType.DJANGO,
                host="source.example.com",
                authentication=auth_config,
                paths=PathConfig(root_path=str(source_path)),
                database=DatabaseConfig(
                    type=DatabaseType.POSTGRESQL,
                    host="db.example.com",
                    database_name="django_db",
                    username="django_user",
                    password="django_pass"
                )
            ),
            destination=SystemConfig(
                type=SystemType.KUBERNETES_POD,
                host="k8s.example.com",
                authentication=auth_config,
                paths=PathConfig(root_path=str(dest_path)),
                database=DatabaseConfig(
                    type=DatabaseType.POSTGRESQL,
                    host="k8s-db.example.com",
                    database_name="django_prod",
                    username="prod_user",
                    password="prod_pass"
                )
            ),
            transfer=TransferConfig(method=TransferMethod.KUBERNETES_VOLUME),
            options=MigrationOptions()
        )
        
        engine = ValidationEngine(console=console)
        
        # Test each category individually
        categories = [
            (ValidationCategory.CONNECTIVITY, "🌐 Network & Service Connectivity"),
            (ValidationCategory.COMPATIBILITY, "🔄 System & Database Compatibility"),
            (ValidationCategory.DEPENDENCIES, "📦 Required Packages & Tools"),
            (ValidationCategory.PERMISSIONS, "🔐 File & Database Permissions")
        ]
        
        for category, description in categories:
            console.print(f"\n[bold]{description}[/bold]")
            console.print("-" * 50)
            
            try:
                issues = await engine.validate_single_category(migration_config, category)
                
                if not issues:
                    console.print("[green]✅ No issues found in this category[/green]")
                else:
                    for issue in issues[:3]:  # Show first 3 issues
                        severity_color = "red" if issue.severity == ValidationSeverity.CRITICAL else "yellow"
                        console.print(f"[{severity_color}]• {issue.name}: {issue.message}[/{severity_color}]")
                        if issue.remediation:
                            console.print(f"  💡 [dim]{issue.remediation}[/dim]")
                    
                    if len(issues) > 3:
                        console.print(f"  [dim]... and {len(issues) - 3} more issues[/dim]")
                        
            except Exception as e:
                console.print(f"[red]❌ Validation failed: {str(e)}[/red]")


async def demo_report_generation():
    """Demonstrate different report formats."""
    console = Console()
    console.print("\n[bold magenta]🎯 Demo 4: Report Generation[/bold magenta]")
    console.print("=" * 60)
    
    # Create a simple configuration for report demo
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "source"
        dest_path = temp_path / "destination"
        source_path.mkdir()
        dest_path.mkdir()
        
        migration_config = MigrationConfig(
            name="Report Demo Migration",
            description="Demonstrating report generation capabilities",
            source=SystemConfig(
                type=SystemType.STATIC_SITE,
                host="source.example.com",
                authentication=AuthConfig(type=AuthType.SSH_KEY, username="user", ssh_key_path="~/.ssh/id_rsa"),
                paths=PathConfig(root_path=str(source_path))
            ),
            destination=SystemConfig(
                type=SystemType.AWS_S3,
                host="s3.amazonaws.com",
                authentication=AuthConfig(type=AuthType.API_KEY, api_key="key", api_secret="secret"),
                paths=PathConfig(root_path=str(dest_path)),
                cloud_config=CloudConfig(
                    provider="aws",
                    region="us-east-1",
                    bucket_name="static-site-bucket"
                )
            ),
            transfer=TransferConfig(method=TransferMethod.AWS_S3),
            options=MigrationOptions()
        )
        
        engine = ValidationEngine(console=console)
        summary = await engine.validate_migration(migration_config, detailed_output=False)
        
        # Generate and save different report formats
        report_dir = temp_path / "reports"
        report_dir.mkdir()
        
        # Markdown report
        markdown_path = report_dir / "validation_report.md"
        engine.save_report(str(markdown_path), "markdown")
        console.print(f"📄 Markdown report saved: [cyan]{markdown_path}[/cyan]")
        
        # JSON report
        json_path = report_dir / "validation_report.json"
        engine.save_report(str(json_path), "json")
        console.print(f"📊 JSON report saved: [cyan]{json_path}[/cyan]")
        
        # Text report
        text_path = report_dir / "validation_report.txt"
        engine.save_report(str(text_path), "text")
        console.print(f"📝 Text report saved: [cyan]{text_path}[/cyan]")
        
        # Display sample of markdown report
        console.print(f"\n[bold]📖 Sample Markdown Report:[/bold]")
        console.print("-" * 40)
        
        markdown_content = markdown_path.read_text()
        # Show first 10 lines
        lines = markdown_content.split('\n')[:10]
        for line in lines:
            console.print(f"[dim]{line}[/dim]")
        
        if len(markdown_content.split('\n')) > 10:
            console.print("[dim]...[/dim]")
        
        # Show remediation scripts if available
        if summary.remediation_scripts:
            console.print(f"\n[bold]🔧 Available Remediation Scripts:[/bold]")
            for script_name in summary.remediation_scripts.keys():
                script_path = report_dir / f"{script_name}.sh"
                with open(script_path, 'w') as f:
                    f.write(summary.remediation_scripts[script_name])
                console.print(f"• {script_name.replace('_', ' ').title()}: [cyan]{script_path}[/cyan]")


async def demo_error_handling():
    """Demonstrate error handling and edge cases."""
    console = Console()
    console.print("\n[bold red]🎯 Demo 5: Error Handling & Edge Cases[/bold red]")
    console.print("=" * 60)
    
    engine = ValidationEngine(console=console)
    
    # Test with invalid configuration
    try:
        # Create an intentionally problematic configuration
        invalid_config = MigrationConfig(
            name="Invalid Configuration Test",
            description="Testing error handling with invalid settings",
            source=SystemConfig(
                type=SystemType.WORDPRESS,
                host="nonexistent.invalid.domain.com",
                authentication=AuthConfig(type=AuthType.PASSWORD, username="", password=""),
                paths=PathConfig(root_path="/nonexistent/path"),
                database=DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host="invalid.db.host.com",
                    database_name="",
                    username="",
                    password=""
                )
            ),
            destination=SystemConfig(
                type=SystemType.MONGODB,  # Incompatible with WordPress
                host="another.invalid.host.com",
                authentication=AuthConfig(type=AuthType.API_KEY, api_key="", api_secret=""),
                paths=PathConfig(root_path="/another/nonexistent/path"),
                database=DatabaseConfig(
                    type=DatabaseType.REDIS,  # Incompatible
                    host="redis.invalid.com",
                    database_name="0"
                )
            ),
            transfer=TransferConfig(method=TransferMethod.DOCKER_VOLUME),  # Incompatible
            options=MigrationOptions()
        )
        
        console.print("[yellow]⚠️  Testing with intentionally invalid configuration...[/yellow]")
        summary = await engine.validate_migration(invalid_config, detailed_output=False)
        
        console.print(f"\n[bold]🔍 Error Handling Results:[/bold]")
        console.print(f"• Validation completed without crashing: [green]✅[/green]")
        console.print(f"• Critical issues detected: [red]{summary.critical_issues}[/red]")
        console.print(f"• Can proceed: [red]{'No' if not summary.can_proceed else 'Yes'}[/red]")
        console.print(f"• Issues found across [yellow]{len(summary.issues_by_category)}[/yellow] categories")
        
        # Show top issues
        if engine.all_issues:
            console.print(f"\n[bold]🚨 Top Critical Issues:[/bold]")
            critical_issues = [i for i in engine.all_issues if i.severity == ValidationSeverity.CRITICAL]
            for i, issue in enumerate(critical_issues[:5], 1):
                console.print(f"{i}. [red]{issue.name}[/red]: {issue.message}")
        
    except Exception as e:
        console.print(f"[red]❌ Unexpected error during validation: {str(e)}[/red]")
        console.print("[yellow]This indicates a bug in the validation engine that should be fixed.[/yellow]")


async def main():
    """Run all validation engine demonstrations."""
    console = Console()
    
    console.print("""
[bold blue]🔍 Migration Assistant - ValidationEngine Comprehensive Demo[/bold blue]
[dim]This demo showcases the complete validation workflow including:[/dim]
[dim]• Connectivity, compatibility, dependency, and permission validation[/dim]
[dim]• Result aggregation and Rich-formatted reporting[/dim]
[dim]• Remediation suggestions and script generation[/dim]
[dim]• Multiple report formats and error handling[/dim]
""")
    
    try:
        # Run all demos
        await demo_successful_validation()
        await demo_complex_migration_validation()
        await demo_validation_categories()
        await demo_report_generation()
        await demo_error_handling()
        
        console.print(f"\n[bold green]🎉 All ValidationEngine demos completed successfully![/bold green]")
        console.print(f"[dim]The ValidationEngine provides comprehensive pre-migration validation[/dim]")
        console.print(f"[dim]with detailed reporting and actionable remediation suggestions.[/dim]")
        
    except KeyboardInterrupt:
        console.print(f"\n[yellow]⚠️  Demo interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Demo failed with error: {str(e)}[/red]")
        raise


if __name__ == "__main__":
    asyncio.run(main())