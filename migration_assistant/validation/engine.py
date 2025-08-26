"""
Validation engine for orchestrating all pre-migration validation checks.

This module provides the ValidationEngine class that coordinates connectivity,
compatibility, dependency, and permission validation checks, aggregates results,
and provides Rich-formatted reporting with remediation suggestions.
"""

import asyncio
import logging
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich.tree import Tree
from rich.markdown import Markdown

from migration_assistant.models.config import MigrationConfig
from migration_assistant.validation.connectivity import ConnectivityValidator, ConnectivityCheck, ValidationResult
from migration_assistant.validation.compatibility import CompatibilityValidator, CompatibilityCheck, CompatibilityResult
from migration_assistant.validation.dependency import DependencyValidator, DependencyCheck, DependencyStatus
from migration_assistant.validation.permission import PermissionValidator, PermissionCheck, PermissionStatus

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues"""
    CRITICAL = "critical"  # Blocks migration
    WARNING = "warning"    # Should be reviewed
    INFO = "info"         # Informational only


class ValidationCategory(str, Enum):
    """Categories of validation checks"""
    CONNECTIVITY = "connectivity"
    COMPATIBILITY = "compatibility"
    DEPENDENCIES = "dependencies"
    PERMISSIONS = "permissions"


@dataclass
class ValidationIssue:
    """Represents a validation issue with severity and remediation"""
    category: ValidationCategory
    name: str
    severity: ValidationSeverity
    message: str
    details: Optional[Dict[str, Any]] = None
    remediation: Optional[str] = None
    check_result: Optional[Any] = None  # Original check result


@dataclass
class ValidationSummary:
    """Summary of all validation results"""
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_checks: int
    critical_issues: int
    warning_issues: int
    can_proceed: bool
    estimated_fix_time: str
    success_rate: float
    issues_by_category: Dict[ValidationCategory, int]
    remediation_scripts: Dict[str, str]


class ValidationEngine:
    """
    Orchestrates all pre-migration validation checks and provides
    comprehensive reporting with remediation suggestions.
    """
    
    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the validation engine.
        
        Args:
            console: Rich console for formatted output (optional)
        """
        self.console = console or Console()
        self.connectivity_validator = ConnectivityValidator()
        self.compatibility_validator = CompatibilityValidator()
        self.dependency_validator = DependencyValidator()
        self.permission_validator = PermissionValidator()
        
        # Validation results storage
        self.connectivity_results: List[ConnectivityCheck] = []
        self.compatibility_results: List[CompatibilityCheck] = []
        self.dependency_results: List[DependencyCheck] = []
        self.permission_results: List[PermissionCheck] = []
        
        # Aggregated results
        self.all_issues: List[ValidationIssue] = []
        self.validation_summary: Optional[ValidationSummary] = None
        
    async def validate_migration(
        self, 
        config: MigrationConfig,
        show_progress: bool = True,
        detailed_output: bool = True
    ) -> ValidationSummary:
        """
        Run complete validation suite for a migration configuration.
        
        Args:
            config: Migration configuration to validate
            show_progress: Whether to show progress indicators
            detailed_output: Whether to show detailed results
            
        Returns:
            ValidationSummary with aggregated results
        """
        logger.info(f"Starting validation for migration: {config.name}")
        
        if show_progress:
            self.console.print(Panel.fit(
                f"🔍 [bold blue]Validating Migration Configuration[/bold blue]\n"
                f"Migration: [bold]{config.name}[/bold]\n"
                f"Source: {config.source.type.value} → Destination: {config.destination.type.value}",
                title="Migration Validation",
                border_style="blue"
            ))
        
        # Clear previous results
        self._clear_results()
        
        # Run validation checks with progress tracking
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                
                # Connectivity validation
                task1 = progress.add_task("🌐 Connectivity checks...", total=1)
                self.connectivity_results = await self.connectivity_validator.validate_all(
                    self._config_to_dict(config)
                )
                progress.update(task1, completed=1)
                
                # Compatibility validation
                task2 = progress.add_task("🔄 Compatibility checks...", total=1)
                self.compatibility_results = await self.compatibility_validator.validate_compatibility(config)
                progress.update(task2, completed=1)
                
                # Dependency validation
                task3 = progress.add_task("📦 Dependency checks...", total=1)
                self.dependency_results = await self.dependency_validator.validate_dependencies(config)
                progress.update(task3, completed=1)
                
                # Permission validation
                task4 = progress.add_task("🔐 Permission checks...", total=1)
                self.permission_results = await self.permission_validator.validate_permissions(config)
                progress.update(task4, completed=1)
        else:
            # Run without progress indicators
            self.connectivity_results = await self.connectivity_validator.validate_all(
                self._config_to_dict(config)
            )
            self.compatibility_results = await self.compatibility_validator.validate_compatibility(config)
            self.dependency_results = await self.dependency_validator.validate_dependencies(config)
            self.permission_results = await self.permission_validator.validate_permissions(config)
        
        # Aggregate and analyze results
        self._aggregate_results()
        self.validation_summary = self._generate_summary()
        
        # Display results if requested
        if detailed_output:
            self.display_validation_results()
        
        logger.info(f"Validation completed. Can proceed: {self.validation_summary.can_proceed}")
        return self.validation_summary
    
    def _clear_results(self):
        """Clear all previous validation results"""
        self.connectivity_results.clear()
        self.compatibility_results.clear()
        self.dependency_results.clear()
        self.permission_results.clear()
        self.all_issues.clear()
        self.validation_summary = None
    
    def _config_to_dict(self, config: MigrationConfig) -> Dict[str, Any]:
        """Convert MigrationConfig to dictionary format for connectivity validator"""
        return {
            'source': {
                'type': config.source.type.value,
                'host': config.source.host,
                'port': config.source.port,
                'db_type': config.source.database.type.value if config.source.database else None,
                'db_user': config.source.database.username if config.source.database else None,
                'db_password': config.source.database.password if config.source.database else None,
                'db_name': config.source.database.database_name if config.source.database else None,
                'ssh_config': {
                    'username': config.source.authentication.username,
                    'password': config.source.authentication.password,
                    'key_file': config.source.authentication.ssh_key_path,
                    'port': 22  # Default SSH port
                } if config.source.authentication.type.value in ['ssh_key', 'password'] else {},
                'cloud_config': config.source.cloud_config.model_dump() if config.source.cloud_config else None
            },
            'destination': {
                'type': config.destination.type.value,
                'host': config.destination.host,
                'port': config.destination.port,
                'db_type': config.destination.database.type.value if config.destination.database else None,
                'db_user': config.destination.database.username if config.destination.database else None,
                'db_password': config.destination.database.password if config.destination.database else None,
                'db_name': config.destination.database.database_name if config.destination.database else None,
                'ssh_config': {
                    'username': config.destination.authentication.username,
                    'password': config.destination.authentication.password,
                    'key_file': config.destination.authentication.ssh_key_path,
                    'port': 22  # Default SSH port
                } if config.destination.authentication.type.value in ['ssh_key', 'password'] else {},
                'cloud_config': config.destination.cloud_config.model_dump() if config.destination.cloud_config else None
            }
        }
    
    def _aggregate_results(self):
        """Aggregate all validation results into issues list"""
        self.all_issues.clear()
        
        # Process connectivity results
        for check in self.connectivity_results:
            if check.result == ValidationResult.FAILED:
                severity = ValidationSeverity.CRITICAL
            elif check.result == ValidationResult.WARNING:
                severity = ValidationSeverity.WARNING
            else:
                continue  # Skip successful checks
            
            self.all_issues.append(ValidationIssue(
                category=ValidationCategory.CONNECTIVITY,
                name=check.name,
                severity=severity,
                message=check.message,
                details=check.details,
                remediation=check.remediation,
                check_result=check
            ))
        
        # Process compatibility results
        for check in self.compatibility_results:
            if check.result == CompatibilityResult.INCOMPATIBLE:
                severity = ValidationSeverity.CRITICAL
            elif check.result in [CompatibilityResult.WARNING, CompatibilityResult.REQUIRES_CONVERSION]:
                severity = ValidationSeverity.WARNING
            else:
                continue  # Skip compatible checks
            
            self.all_issues.append(ValidationIssue(
                category=ValidationCategory.COMPATIBILITY,
                name=check.name,
                severity=severity,
                message=check.message,
                details=check.details,
                remediation=check.remediation,
                check_result=check
            ))
        
        # Process dependency results
        for check in self.dependency_results:
            if check.status == DependencyStatus.MISSING and check.required:
                severity = ValidationSeverity.CRITICAL
            elif check.status in [DependencyStatus.MISSING, DependencyStatus.WRONG_VERSION]:
                severity = ValidationSeverity.WARNING if not check.required else ValidationSeverity.CRITICAL
            else:
                continue  # Skip available dependencies
            
            self.all_issues.append(ValidationIssue(
                category=ValidationCategory.DEPENDENCIES,
                name=check.name,
                severity=severity,
                message=f"{check.status.value}: {check.description or 'Dependency issue'}",
                details={
                    'type': check.type.value,
                    'required': check.required,
                    'current_version': check.current_version,
                    'required_version': check.required_version
                },
                remediation=check.install_command,
                check_result=check
            ))
        
        # Process permission results
        for check in self.permission_results:
            if check.status == PermissionStatus.DENIED and check.required:
                severity = ValidationSeverity.CRITICAL
            elif check.status == PermissionStatus.DENIED:
                severity = ValidationSeverity.WARNING
            elif check.status == PermissionStatus.PARTIAL:
                severity = ValidationSeverity.WARNING
            else:
                continue  # Skip granted permissions
            
            self.all_issues.append(ValidationIssue(
                category=ValidationCategory.PERMISSIONS,
                name=check.name,
                severity=severity,
                message=check.message,
                details={
                    'type': check.type.value,
                    'path': check.path,
                    'required': check.required
                },
                remediation=check.remediation,
                check_result=check
            ))
    
    def _generate_summary(self) -> ValidationSummary:
        """Generate comprehensive validation summary"""
        total_checks = (
            len(self.connectivity_results) +
            len(self.compatibility_results) +
            len(self.dependency_results) +
            len(self.permission_results)
        )
        
        # Count successful checks
        passed_checks = 0
        passed_checks += len([c for c in self.connectivity_results if c.result == ValidationResult.SUCCESS])
        passed_checks += len([c for c in self.compatibility_results if c.result == CompatibilityResult.COMPATIBLE])
        passed_checks += len([c for c in self.dependency_results if c.status == DependencyStatus.AVAILABLE])
        passed_checks += len([c for c in self.permission_results if c.status == PermissionStatus.GRANTED])
        
        # Count issues by severity
        critical_issues = len([i for i in self.all_issues if i.severity == ValidationSeverity.CRITICAL])
        warning_issues = len([i for i in self.all_issues if i.severity == ValidationSeverity.WARNING])
        
        # Count issues by category
        issues_by_category = {}
        for category in ValidationCategory:
            issues_by_category[category] = len([i for i in self.all_issues if i.category == category])
        
        # Calculate metrics
        failed_checks = len(self.all_issues)
        warning_checks = warning_issues
        success_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        can_proceed = critical_issues == 0
        
        # Estimate fix time based on issue complexity
        estimated_fix_time = self._estimate_fix_time()
        
        # Generate remediation scripts
        remediation_scripts = self._generate_remediation_scripts()
        
        return ValidationSummary(
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warning_checks=warning_checks,
            critical_issues=critical_issues,
            warning_issues=warning_issues,
            can_proceed=can_proceed,
            estimated_fix_time=estimated_fix_time,
            success_rate=success_rate,
            issues_by_category=issues_by_category,
            remediation_scripts=remediation_scripts
        )
    
    def _estimate_fix_time(self) -> str:
        """Estimate time required to fix all issues"""
        time_estimates = {
            ValidationCategory.CONNECTIVITY: 15,  # minutes per issue
            ValidationCategory.COMPATIBILITY: 60,  # minutes per issue
            ValidationCategory.DEPENDENCIES: 10,   # minutes per issue
            ValidationCategory.PERMISSIONS: 5      # minutes per issue
        }
        
        total_minutes = 0
        for issue in self.all_issues:
            if issue.severity == ValidationSeverity.CRITICAL:
                total_minutes += time_estimates.get(issue.category, 30)
            else:
                total_minutes += time_estimates.get(issue.category, 30) // 2
        
        if total_minutes == 0:
            return "No fixes needed"
        elif total_minutes < 60:
            return f"{total_minutes} minutes"
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if minutes == 0:
                return f"{hours} hour{'s' if hours > 1 else ''}"
            else:
                return f"{hours}h {minutes}m"
    
    def _generate_remediation_scripts(self) -> Dict[str, str]:
        """Generate remediation scripts for different issue types"""
        scripts = {}
        
        # Dependency installation script
        if self.dependency_results:
            scripts['install_dependencies'] = self.dependency_validator.generate_install_script(
                self.dependency_results
            )
        
        # Permission fix script
        if self.permission_results:
            scripts['fix_permissions'] = self.permission_validator.generate_permission_fix_script(
                self.permission_results
            )
        
        # Connectivity troubleshooting script
        connectivity_issues = [i for i in self.all_issues if i.category == ValidationCategory.CONNECTIVITY]
        if connectivity_issues:
            scripts['troubleshoot_connectivity'] = self._generate_connectivity_script(connectivity_issues)
        
        return scripts
    
    def _generate_connectivity_script(self, connectivity_issues: List[ValidationIssue]) -> str:
        """Generate connectivity troubleshooting script"""
        script_lines = [
            "#!/bin/bash",
            "# Connectivity troubleshooting script",
            "# Review and modify as needed",
            "set -e",
            "",
            "echo 'Troubleshooting connectivity issues...'",
            ""
        ]
        
        for issue in connectivity_issues:
            script_lines.append(f"# Issue: {issue.name}")
            script_lines.append(f"# {issue.message}")
            if issue.remediation:
                script_lines.append(f"# Remediation: {issue.remediation}")
            
            # Add specific troubleshooting commands based on issue type
            issue_name_str = str(issue.name).lower()
            if 'network' in issue_name_str:
                if issue.details and 'host' in issue.details:
                    host = issue.details['host']
                    script_lines.append(f"echo 'Testing connectivity to {host}...'")
                    script_lines.append(f"ping -c 3 {host} || echo 'Ping failed'")
                    if 'port' in issue.details:
                        port = issue.details['port']
                        script_lines.append(f"nc -zv {host} {port} || echo 'Port {port} not reachable'")
            
            script_lines.append("")
        
        script_lines.append("echo 'Connectivity troubleshooting complete!'")
        return "\n".join(script_lines)
    
    def display_validation_results(self):
        """Display comprehensive validation results using Rich formatting"""
        if not self.validation_summary:
            self.console.print("[red]No validation results to display[/red]")
            return
        
        # Main summary panel
        self._display_summary_panel()
        
        # Issues by category
        if self.all_issues:
            self._display_issues_by_category()
        
        # Detailed results
        self._display_detailed_results()
        
        # Remediation suggestions
        if self.all_issues:
            self._display_remediation_suggestions()
    
    def _display_summary_panel(self):
        """Display main validation summary panel"""
        summary = self.validation_summary
        
        # Status indicator
        if summary.can_proceed:
            status_text = "[bold green]✅ READY TO PROCEED[/bold green]"
            status_color = "green"
        else:
            status_text = "[bold red]❌ ISSUES FOUND[/bold red]"
            status_color = "red"
        
        # Create summary content
        summary_content = f"""
{status_text}

[bold]Validation Summary:[/bold]
• Total Checks: {summary.total_checks}
• Passed: [green]{summary.passed_checks}[/green]
• Failed: [red]{summary.failed_checks}[/red]
• Warnings: [yellow]{summary.warning_checks}[/yellow]

[bold]Issues Found:[/bold]
• Critical: [red]{summary.critical_issues}[/red]
• Warnings: [yellow]{summary.warning_issues}[/yellow]

[bold]Success Rate:[/bold] {summary.success_rate:.1f}%
[bold]Estimated Fix Time:[/bold] {summary.estimated_fix_time}
"""
        
        self.console.print(Panel(
            summary_content.strip(),
            title="🔍 Validation Results",
            border_style=status_color,
            padding=(1, 2)
        ))
    
    def _display_issues_by_category(self):
        """Display issues grouped by category"""
        self.console.print("\n[bold]📊 Issues by Category[/bold]")
        
        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Critical", style="red", justify="center")
        table.add_column("Warnings", style="yellow", justify="center")
        table.add_column("Total", style="white", justify="center")
        
        for category in ValidationCategory:
            category_issues = [i for i in self.all_issues if i.category == category]
            critical_count = len([i for i in category_issues if i.severity == ValidationSeverity.CRITICAL])
            warning_count = len([i for i in category_issues if i.severity == ValidationSeverity.WARNING])
            total_count = len(category_issues)
            
            if total_count > 0:  # Only show categories with issues
                table.add_row(
                    category.value.title(),
                    str(critical_count) if critical_count > 0 else "-",
                    str(warning_count) if warning_count > 0 else "-",
                    str(total_count)
                )
        
        self.console.print(table)
    
    def _display_detailed_results(self):
        """Display detailed validation results in a tree structure"""
        self.console.print("\n[bold]🔍 Detailed Results[/bold]")
        
        tree = Tree("Validation Results")
        
        # Connectivity results
        if self.connectivity_results:
            connectivity_tree = tree.add("🌐 Connectivity")
            for check in self.connectivity_results:
                icon = self._get_result_icon(check.result.value)
                connectivity_tree.add(f"{icon} {check.name}: {check.message}")
        
        # Compatibility results
        if self.compatibility_results:
            compatibility_tree = tree.add("🔄 Compatibility")
            for check in self.compatibility_results:
                icon = self._get_result_icon(check.result.value)
                compatibility_tree.add(f"{icon} {check.name}: {check.message}")
        
        # Dependency results
        if self.dependency_results:
            dependency_tree = tree.add("📦 Dependencies")
            for check in self.dependency_results:
                icon = self._get_dependency_icon(check.status)
                status_text = f"[{'red' if check.required and check.status != DependencyStatus.AVAILABLE else 'yellow'}]{check.status.value}[/]"
                dependency_tree.add(f"{icon} {check.name} ({check.type.value}): {status_text}")
        
        # Permission results
        if self.permission_results:
            permission_tree = tree.add("🔐 Permissions")
            for check in self.permission_results:
                icon = self._get_permission_icon(check.status)
                permission_tree.add(f"{icon} {check.name}: {check.message}")
        
        self.console.print(tree)
    
    def _display_remediation_suggestions(self):
        """Display remediation suggestions and available scripts"""
        self.console.print("\n[bold]💡 Remediation Suggestions[/bold]")
        
        # Group issues by severity
        critical_issues = [i for i in self.all_issues if i.severity == ValidationSeverity.CRITICAL]
        warning_issues = [i for i in self.all_issues if i.severity == ValidationSeverity.WARNING]
        
        if critical_issues:
            self.console.print("\n[bold red]🚨 Critical Issues (Must Fix)[/bold red]")
            for i, issue in enumerate(critical_issues[:5], 1):  # Show first 5
                self.console.print(f"{i}. [red]{issue.name}[/red]: {issue.message}")
                if issue.remediation:
                    self.console.print(f"   💡 [dim]{issue.remediation}[/dim]")
        
        if warning_issues:
            self.console.print("\n[bold yellow]⚠️  Warnings (Recommended to Fix)[/bold yellow]")
            for i, issue in enumerate(warning_issues[:3], 1):  # Show first 3
                self.console.print(f"{i}. [yellow]{issue.name}[/yellow]: {issue.message}")
                if issue.remediation:
                    self.console.print(f"   💡 [dim]{issue.remediation}[/dim]")
        
        # Available scripts
        if self.validation_summary.remediation_scripts:
            self.console.print("\n[bold]📜 Available Remediation Scripts[/bold]")
            for script_name, script_content in self.validation_summary.remediation_scripts.items():
                if script_content and script_content.strip() != "# No issues found":
                    self.console.print(f"• {script_name.replace('_', ' ').title()}")
    
    def _get_result_icon(self, result: str) -> str:
        """Get icon for validation result"""
        icons = {
            "success": "✅",
            "failed": "❌",
            "warning": "⚠️",
            "skipped": "⏭️",
            "compatible": "✅",
            "incompatible": "❌",
            "requires_conversion": "🔄"
        }
        return icons.get(result, "❓")
    
    def _get_dependency_icon(self, status: DependencyStatus) -> str:
        """Get icon for dependency status"""
        icons = {
            DependencyStatus.AVAILABLE: "✅",
            DependencyStatus.MISSING: "❌",
            DependencyStatus.WRONG_VERSION: "⚠️",
            DependencyStatus.OPTIONAL: "ℹ️"
        }
        return icons.get(status, "❓")
    
    def _get_permission_icon(self, status: PermissionStatus) -> str:
        """Get icon for permission status"""
        icons = {
            PermissionStatus.GRANTED: "✅",
            PermissionStatus.DENIED: "❌",
            PermissionStatus.PARTIAL: "⚠️",
            PermissionStatus.UNKNOWN: "❓"
        }
        return icons.get(status, "❓")
    
    def get_validation_report(self, format: str = "markdown") -> str:
        """
        Generate a validation report in the specified format.
        
        Args:
            format: Report format ('markdown', 'json', 'text')
            
        Returns:
            Formatted validation report
        """
        if not self.validation_summary:
            return "No validation results available"
        
        if format == "markdown":
            return self._generate_markdown_report()
        elif format == "json":
            return self._generate_json_report()
        else:
            return self._generate_text_report()
    
    def _generate_markdown_report(self) -> str:
        """Generate markdown validation report"""
        summary = self.validation_summary
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        report_lines = [
            "# Migration Validation Report",
            f"Generated: {timestamp}",
            "",
            "## Summary",
            f"- **Status**: {'✅ Ready to Proceed' if summary.can_proceed else '❌ Issues Found'}",
            f"- **Total Checks**: {summary.total_checks}",
            f"- **Success Rate**: {summary.success_rate:.1f}%",
            f"- **Critical Issues**: {summary.critical_issues}",
            f"- **Warnings**: {summary.warning_issues}",
            f"- **Estimated Fix Time**: {summary.estimated_fix_time}",
            ""
        ]
        
        if self.all_issues:
            report_lines.extend([
                "## Issues Found",
                ""
            ])
            
            # Group by category
            for category in ValidationCategory:
                category_issues = [i for i in self.all_issues if i.category == category]
                if category_issues:
                    report_lines.append(f"### {category.value.title()}")
                    for issue in category_issues:
                        severity_icon = "🚨" if issue.severity == ValidationSeverity.CRITICAL else "⚠️"
                        report_lines.append(f"- {severity_icon} **{issue.name}**: {issue.message}")
                        if issue.remediation:
                            report_lines.append(f"  - *Remediation*: {issue.remediation}")
                    report_lines.append("")
        
        return "\n".join(report_lines)
    
    def _generate_json_report(self) -> str:
        """Generate JSON validation report"""
        import json
        
        report_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "summary": {
                "can_proceed": self.validation_summary.can_proceed,
                "total_checks": self.validation_summary.total_checks,
                "passed_checks": self.validation_summary.passed_checks,
                "failed_checks": self.validation_summary.failed_checks,
                "critical_issues": self.validation_summary.critical_issues,
                "warning_issues": self.validation_summary.warning_issues,
                "success_rate": self.validation_summary.success_rate,
                "estimated_fix_time": self.validation_summary.estimated_fix_time
            },
            "issues": [
                {
                    "category": issue.category.value,
                    "name": issue.name,
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "remediation": issue.remediation,
                    "details": issue.details
                }
                for issue in self.all_issues
            ],
            "remediation_scripts": self.validation_summary.remediation_scripts
        }
        
        return json.dumps(report_data, indent=2)
    
    def _generate_text_report(self) -> str:
        """Generate plain text validation report"""
        summary = self.validation_summary
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        report_lines = [
            "MIGRATION VALIDATION REPORT",
            "=" * 50,
            f"Generated: {timestamp}",
            "",
            "SUMMARY",
            "-" * 20,
            f"Status: {'READY TO PROCEED' if summary.can_proceed else 'ISSUES FOUND'}",
            f"Total Checks: {summary.total_checks}",
            f"Success Rate: {summary.success_rate:.1f}%",
            f"Critical Issues: {summary.critical_issues}",
            f"Warnings: {summary.warning_issues}",
            f"Estimated Fix Time: {summary.estimated_fix_time}",
            ""
        ]
        
        if self.all_issues:
            report_lines.extend([
                "ISSUES FOUND",
                "-" * 20,
                ""
            ])
            
            for i, issue in enumerate(self.all_issues, 1):
                severity_text = "CRITICAL" if issue.severity == ValidationSeverity.CRITICAL else "WARNING"
                report_lines.extend([
                    f"{i}. [{severity_text}] {issue.name}",
                    f"   Category: {issue.category.value.title()}",
                    f"   Message: {issue.message}",
                ])
                if issue.remediation:
                    report_lines.append(f"   Remediation: {issue.remediation}")
                report_lines.append("")
        
        return "\n".join(report_lines)
    
    async def validate_single_category(
        self, 
        config: MigrationConfig, 
        category: ValidationCategory
    ) -> List[ValidationIssue]:
        """
        Run validation for a single category.
        
        Args:
            config: Migration configuration
            category: Category to validate
            
        Returns:
            List of validation issues for the category
        """
        if category == ValidationCategory.CONNECTIVITY:
            results = await self.connectivity_validator.validate_all(self._config_to_dict(config))
            self.connectivity_results = results
        elif category == ValidationCategory.COMPATIBILITY:
            results = await self.compatibility_validator.validate_compatibility(config)
            self.compatibility_results = results
        elif category == ValidationCategory.DEPENDENCIES:
            results = await self.dependency_validator.validate_dependencies(config)
            self.dependency_results = results
        elif category == ValidationCategory.PERMISSIONS:
            results = await self.permission_validator.validate_permissions(config)
            self.permission_results = results
        
        # Re-aggregate results to get issues for this category
        self._aggregate_results()
        return [issue for issue in self.all_issues if issue.category == category]
    
    def save_report(self, filepath: str, format: str = "markdown"):
        """
        Save validation report to file.
        
        Args:
            filepath: Path to save the report
            format: Report format ('markdown', 'json', 'text')
        """
        report_content = self.get_validation_report(format)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"Validation report saved to: {filepath}")