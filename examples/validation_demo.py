#!/usr/bin/env python3
"""
Demonstration of the validation system for the Migration Assistant.

This example shows how to use the CompatibilityValidator, DependencyValidator,
and PermissionValidator to validate a migration configuration.
"""

import asyncio
import tempfile
from pathlib import Path

from migration_assistant.models.config import (
    SystemType, DatabaseType, TransferMethod, MigrationConfig,
    SystemConfig, DatabaseConfig, TransferConfig, MigrationOptions,
    AuthConfig, PathConfig, AuthType
)
from migration_assistant.validation import (
    CompatibilityValidator, DependencyValidator, PermissionValidator,
    CompatibilityResult, DependencyStatus, PermissionStatus
)


async def main():
    """Demonstrate validation system usage."""
    print("🔍 Migration Assistant Validation Demo")
    print("=" * 50)
    
    # Create a sample migration configuration
    print("\n📋 Creating sample migration configuration...")
    
    # Create temporary directories for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "source"
        dest_path = temp_path / "destination"
        source_path.mkdir()
        dest_path.mkdir()
        
        # Create some test files
        (source_path / "index.html").write_text("<html><body>Test</body></html>")
        (source_path / "config.php").write_text("<?php // WordPress config ?>")
        
        # Configure authentication
        auth_config = AuthConfig(
            type=AuthType.PASSWORD,
            username="admin",
            password="secure_password"
        )
        
        # Configure paths
        source_paths = PathConfig(
            root_path=str(source_path),
            web_root=str(source_path),
            config_path=str(source_path / "config.php")
        )
        
        dest_paths = PathConfig(
            root_path=str(dest_path),
            web_root=str(dest_path)
        )
        
        # Configure databases
        source_db = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="source.example.com",
            port=3306,
            database_name="wordpress_db",
            username="wp_user",
            password="wp_password"
        )
        
        dest_db = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            host="dest.example.com",
            port=5432,
            database_name="wordpress_pg",
            username="pg_user",
            password="pg_password"
        )
        
        # Configure systems
        source_system = SystemConfig(
            type=SystemType.WORDPRESS,
            host="source.example.com",
            authentication=auth_config,
            paths=source_paths,
            database=source_db
        )
        
        destination_system = SystemConfig(
            type=SystemType.WORDPRESS,
            host="dest.example.com",
            authentication=auth_config,
            paths=dest_paths,
            database=dest_db
        )
        
        # Configure transfer
        transfer_config = TransferConfig(
            method=TransferMethod.SSH_SFTP,
            parallel_transfers=4,
            compression_enabled=True,
            verify_checksums=True
        )
        
        # Configure options
        migration_options = MigrationOptions(
            maintenance_mode=True,
            backup_before=True,
            verify_after=True,
            rollback_on_failure=True
        )
        
        # Create migration configuration
        migration_config = MigrationConfig(
            name="WordPress MySQL to PostgreSQL Migration",
            description="Migrate WordPress from MySQL to PostgreSQL with validation",
            source=source_system,
            destination=destination_system,
            transfer=transfer_config,
            options=migration_options
        )
        
        print(f"✅ Configuration created: {migration_config.name}")
        print(f"   Source: {migration_config.source.type.value} ({migration_config.source.database.type.value})")
        print(f"   Destination: {migration_config.destination.type.value} ({migration_config.destination.database.type.value})")
        print(f"   Transfer: {migration_config.transfer.method.value}")
        
        # Initialize validators
        print("\n🔧 Initializing validators...")
        compatibility_validator = CompatibilityValidator()
        dependency_validator = DependencyValidator()
        permission_validator = PermissionValidator()
        
        # Run compatibility validation
        print("\n🔄 Running compatibility validation...")
        compatibility_checks = await compatibility_validator.validate_compatibility(migration_config)
        
        print(f"   Performed {len(compatibility_checks)} compatibility checks:")
        for check in compatibility_checks:
            status_icon = {
                CompatibilityResult.COMPATIBLE: "✅",
                CompatibilityResult.INCOMPATIBLE: "❌",
                CompatibilityResult.WARNING: "⚠️",
                CompatibilityResult.REQUIRES_CONVERSION: "🔄"
            }.get(check.result, "❓")
            
            print(f"   {status_icon} {check.name}: {check.message}")
            if check.remediation:
                print(f"      💡 Remediation: {check.remediation}")
        
        # Run dependency validation
        print("\n📦 Running dependency validation...")
        dependency_checks = await dependency_validator.validate_dependencies(migration_config)
        
        # Group by status
        available_deps = [c for c in dependency_checks if c.status == DependencyStatus.AVAILABLE]
        missing_deps = [c for c in dependency_checks if c.status == DependencyStatus.MISSING]
        wrong_version_deps = [c for c in dependency_checks if c.status == DependencyStatus.WRONG_VERSION]
        
        print(f"   Checked {len(dependency_checks)} dependencies:")
        print(f"   ✅ Available: {len(available_deps)}")
        print(f"   ❌ Missing: {len(missing_deps)}")
        print(f"   ⚠️  Wrong version: {len(wrong_version_deps)}")
        
        if missing_deps:
            print("\n   Missing dependencies:")
            for dep in missing_deps[:5]:  # Show first 5
                print(f"   - {dep.name} ({dep.type.value})")
                if dep.install_command:
                    print(f"     Install: {dep.install_command}")
        
        # Generate install script for missing dependencies
        if missing_deps:
            print("\n📜 Generating dependency install script...")
            install_script = dependency_validator.generate_install_script(dependency_checks)
            script_path = temp_path / "install_dependencies.sh"
            script_path.write_text(install_script)
            print(f"   Script saved to: {script_path}")
        
        # Run permission validation
        print("\n🔐 Running permission validation...")
        permission_checks = await permission_validator.validate_permissions(migration_config)
        
        # Get summary
        permission_summary = permission_validator.get_permission_summary(permission_checks)
        
        print(f"   Checked {permission_summary['total_checks']} permissions:")
        print(f"   ✅ Granted: {permission_summary['granted']}")
        print(f"   ❌ Denied: {permission_summary['denied']}")
        print(f"   ❓ Unknown: {permission_summary['unknown']}")
        print(f"   Success rate: {permission_summary['success_rate']:.1f}%")
        print(f"   Can proceed: {'✅ Yes' if permission_summary['can_proceed'] else '❌ No'}")
        
        # Show some permission details
        denied_perms = [c for c in permission_checks if c.status == PermissionStatus.DENIED]
        if denied_perms:
            print("\n   Permission issues:")
            for perm in denied_perms[:3]:  # Show first 3
                print(f"   ❌ {perm.name}: {perm.message}")
                if perm.remediation:
                    print(f"      💡 Fix: {perm.remediation}")
        
        # Generate permission fix script
        if denied_perms:
            print("\n🔧 Generating permission fix script...")
            fix_script = permission_validator.generate_permission_fix_script(permission_checks)
            fix_script_path = temp_path / "fix_permissions.sh"
            fix_script_path.write_text(fix_script)
            print(f"   Script saved to: {fix_script_path}")
        
        # Overall validation summary
        print("\n📊 Overall Validation Summary")
        print("-" * 30)
        
        # Check if migration can proceed
        compatibility_issues = len([c for c in compatibility_checks if c.result == CompatibilityResult.INCOMPATIBLE])
        required_deps_missing = len(dependency_validator.get_missing_dependencies(dependency_checks))
        permission_issues = permission_summary['required_denied']
        
        total_blockers = compatibility_issues + required_deps_missing + permission_issues
        
        if total_blockers == 0:
            print("✅ Migration can proceed!")
            print("   All critical validations passed.")
        else:
            print("❌ Migration cannot proceed yet.")
            print(f"   Found {total_blockers} blocking issues:")
            if compatibility_issues > 0:
                print(f"   - {compatibility_issues} compatibility issues")
            if required_deps_missing > 0:
                print(f"   - {required_deps_missing} missing required dependencies")
            if permission_issues > 0:
                print(f"   - {permission_issues} permission issues")
        
        # Show warnings
        warnings = []
        warnings.extend([c for c in compatibility_checks if c.result == CompatibilityResult.WARNING])
        warnings.extend([c for c in compatibility_checks if c.result == CompatibilityResult.REQUIRES_CONVERSION])
        
        if warnings:
            print(f"\n⚠️  {len(warnings)} warnings to review:")
            for warning in warnings[:3]:  # Show first 3
                print(f"   - {warning.name}: {warning.message}")
        
        # Recommendations
        print("\n💡 Recommendations:")
        
        # Get recommended transfer methods
        recommended_methods = compatibility_validator.get_recommended_transfer_methods(
            migration_config.source.type,
            migration_config.destination.type
        )
        
        if migration_config.transfer.method not in recommended_methods:
            print(f"   - Consider using a recommended transfer method: {', '.join(m.value for m in recommended_methods[:3])}")
        
        # Check for conversion requirements
        conversion_reqs = compatibility_validator.get_conversion_requirements(
            migration_config.source,
            migration_config.destination
        )
        
        if conversion_reqs['database_conversion']:
            print("   - Database conversion will be required (MySQL → PostgreSQL)")
            print(f"   - Estimated complexity: {conversion_reqs['complexity']}")
            print(f"   - Estimated time: {conversion_reqs.get('estimated_time', 'unknown')}")
        
        print("\n🎉 Validation demo completed!")


if __name__ == "__main__":
    asyncio.run(main())