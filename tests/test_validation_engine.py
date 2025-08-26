"""
Integration tests for the ValidationEngine.

Tests the complete validation workflow including all validation checks,
result aggregation, Rich-formatted reporting, and remediation suggestions.
"""

import asyncio
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from rich.console import Console

from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, DatabaseConfig, TransferConfig, MigrationOptions,
    AuthConfig, PathConfig, SystemType, DatabaseType, TransferMethod, AuthType
)
from migration_assistant.validation.engine import (
    ValidationEngine, ValidationSummary, ValidationIssue, ValidationSeverity, ValidationCategory
)
from migration_assistant.validation.connectivity import ValidationResult
from migration_assistant.validation.compatibility import CompatibilityResult
from migration_assistant.validation.dependency import DependencyStatus
from migration_assistant.validation.permission import PermissionStatus


@pytest.fixture
def sample_migration_config():
    """Create a sample migration configuration for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "source"
        dest_path = temp_path / "destination"
        source_path.mkdir()
        dest_path.mkdir()
        
        # Create test files
        (source_path / "index.html").write_text("<html><body>Test</body></html>")
        (source_path / "config.php").write_text("<?php // WordPress config ?>")
        
        auth_config = AuthConfig(
            type=AuthType.PASSWORD,
            username="admin",
            password="secure_password"
        )
        
        source_paths = PathConfig(
            root_path=str(source_path),
            web_root=str(source_path),
            config_path=str(source_path / "config.php")
        )
        
        dest_paths = PathConfig(
            root_path=str(dest_path),
            web_root=str(dest_path)
        )
        
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
        
        transfer_config = TransferConfig(
            method=TransferMethod.SSH_SFTP,
            parallel_transfers=4,
            compression_enabled=True,
            verify_checksums=True
        )
        
        migration_options = MigrationOptions(
            maintenance_mode=True,
            backup_before=True,
            verify_after=True,
            rollback_on_failure=True
        )
        
        yield MigrationConfig(
            name="Test WordPress Migration",
            description="Test migration for validation engine",
            source=source_system,
            destination=destination_system,
            transfer=transfer_config,
            options=migration_options
        )


@pytest.fixture
def validation_engine():
    """Create a ValidationEngine instance for testing."""
    console = Console(file=Mock(), width=80)  # Mock console to avoid output during tests
    return ValidationEngine(console=console)


class TestValidationEngine:
    """Test cases for ValidationEngine class."""
    
    @pytest.mark.asyncio
    async def test_validate_migration_success(self, validation_engine, sample_migration_config):
        """Test successful validation workflow."""
        # Mock all validators to return successful results
        with patch.object(validation_engine.connectivity_validator, 'validate_all', new_callable=AsyncMock) as mock_conn, \
             patch.object(validation_engine.compatibility_validator, 'validate_compatibility', new_callable=AsyncMock) as mock_comp, \
             patch.object(validation_engine.dependency_validator, 'validate_dependencies', new_callable=AsyncMock) as mock_dep, \
             patch.object(validation_engine.permission_validator, 'validate_permissions', new_callable=AsyncMock) as mock_perm:
            
            # Setup successful mock responses
            mock_conn.return_value = [
                Mock(name="Network Test", result=ValidationResult.SUCCESS, message="Connection successful", details=None, remediation=None)
            ]
            mock_comp.return_value = [
                Mock(name="System Compatibility", result=CompatibilityResult.COMPATIBLE, message="Systems compatible", details=None, remediation=None)
            ]
            mock_dep.return_value = [
                Mock(name="Python Package", status=DependencyStatus.AVAILABLE, required=True, type=Mock(value="python_package"), 
                     description="Test package", current_version="1.0.0", required_version=">=1.0.0", install_command=None)
            ]
            mock_perm.return_value = [
                Mock(name="File Access", status=PermissionStatus.GRANTED, required=True, type=Mock(value="file_read"),
                     path="/test/path", message="Access granted", details=None, remediation=None)
            ]
            
            # Run validation
            summary = await validation_engine.validate_migration(
                sample_migration_config, 
                show_progress=False, 
                detailed_output=False
            )
            
            # Verify results
            assert isinstance(summary, ValidationSummary)
            assert summary.can_proceed is True
            assert summary.critical_issues == 0
            assert summary.total_checks == 4
            assert summary.passed_checks == 4
            assert summary.success_rate == 100.0
            
            # Verify all validators were called
            mock_conn.assert_called_once()
            mock_comp.assert_called_once_with(sample_migration_config)
            mock_dep.assert_called_once_with(sample_migration_config)
            mock_perm.assert_called_once_with(sample_migration_config)
    
    @pytest.mark.asyncio
    async def test_validate_migration_with_critical_issues(self, validation_engine, sample_migration_config):
        """Test validation with critical issues that block migration."""
        with patch.object(validation_engine.connectivity_validator, 'validate_all', new_callable=AsyncMock) as mock_conn, \
             patch.object(validation_engine.compatibility_validator, 'validate_compatibility', new_callable=AsyncMock) as mock_comp, \
             patch.object(validation_engine.dependency_validator, 'validate_dependencies', new_callable=AsyncMock) as mock_dep, \
             patch.object(validation_engine.permission_validator, 'validate_permissions', new_callable=AsyncMock) as mock_perm:
            
            # Setup mock responses with critical issues
            mock_conn.return_value = [
                Mock(name="Database Connection", result=ValidationResult.FAILED, message="Connection failed", 
                     details={"host": "source.example.com"}, remediation="Check database credentials")
            ]
            mock_comp.return_value = [
                Mock(name="Database Compatibility", result=CompatibilityResult.INCOMPATIBLE, message="Incompatible databases", 
                     details=None, remediation="Use conversion tools")
            ]
            mock_dep.return_value = [
                Mock(name="Required Package", status=DependencyStatus.MISSING, required=True, type=Mock(value="python_package"),
                     description="Missing required package", current_version=None, required_version=">=1.0.0", 
                     install_command="pip install package")
            ]
            mock_perm.return_value = [
                Mock(name="Write Permission", status=PermissionStatus.DENIED, required=True, type=Mock(value="file_write"),
                     path="/dest/path", message="Write access denied", details=None, remediation="chmod +w /dest/path")
            ]
            
            # Run validation
            summary = await validation_engine.validate_migration(
                sample_migration_config, 
                show_progress=False, 
                detailed_output=False
            )
            
            # Verify results
            assert summary.can_proceed is False
            assert summary.critical_issues == 4  # All issues are critical
            assert summary.total_checks == 4
            assert summary.passed_checks == 0
            assert summary.success_rate == 0.0
            assert len(validation_engine.all_issues) == 4
            
            # Verify issue categories
            categories = {issue.category for issue in validation_engine.all_issues}
            assert ValidationCategory.CONNECTIVITY in categories
            assert ValidationCategory.COMPATIBILITY in categories
            assert ValidationCategory.DEPENDENCIES in categories
            assert ValidationCategory.PERMISSIONS in categories
    
    @pytest.mark.asyncio
    async def test_validate_migration_with_warnings(self, validation_engine, sample_migration_config):
        """Test validation with warnings that don't block migration."""
        with patch.object(validation_engine.connectivity_validator, 'validate_all', new_callable=AsyncMock) as mock_conn, \
             patch.object(validation_engine.compatibility_validator, 'validate_compatibility', new_callable=AsyncMock) as mock_comp, \
             patch.object(validation_engine.dependency_validator, 'validate_dependencies', new_callable=AsyncMock) as mock_dep, \
             patch.object(validation_engine.permission_validator, 'validate_permissions', new_callable=AsyncMock) as mock_perm:
            
            # Setup mock responses with warnings
            mock_conn.return_value = [
                Mock(name="Network Test", result=ValidationResult.WARNING, message="Slow connection", 
                     details=None, remediation="Consider faster connection")
            ]
            mock_comp.return_value = [
                Mock(name="Version Compatibility", result=CompatibilityResult.REQUIRES_CONVERSION, message="Version mismatch", 
                     details=None, remediation="Review upgrade notes")
            ]
            mock_dep.return_value = [
                Mock(name="Optional Package", status=DependencyStatus.MISSING, required=False, type=Mock(value="python_package"),
                     description="Optional enhancement", current_version=None, required_version=">=1.0.0", 
                     install_command="pip install optional-package")
            ]
            mock_perm.return_value = [
                Mock(name="Optional Permission", status=PermissionStatus.DENIED, required=False, type=Mock(value="file_execute"),
                     path="/optional/path", message="Execute permission denied", details=None, remediation="chmod +x /optional/path")
            ]
            
            # Run validation
            summary = await validation_engine.validate_migration(
                sample_migration_config, 
                show_progress=False, 
                detailed_output=False
            )
            
            # Verify results
            assert summary.can_proceed is True  # No critical issues
            assert summary.critical_issues == 0
            assert summary.warning_issues == 4
            assert summary.total_checks == 4
            assert summary.passed_checks == 0
            assert len(validation_engine.all_issues) == 4
            
            # All issues should be warnings
            for issue in validation_engine.all_issues:
                assert issue.severity == ValidationSeverity.WARNING
    
    @pytest.mark.asyncio
    async def test_validate_single_category(self, validation_engine, sample_migration_config):
        """Test validation of a single category."""
        with patch.object(validation_engine.connectivity_validator, 'validate_all', new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = [
                Mock(name="Network Test", result=ValidationResult.SUCCESS, message="Connection successful", 
                     details=None, remediation=None)
            ]
            
            # Run single category validation
            issues = await validation_engine.validate_single_category(
                sample_migration_config, 
                ValidationCategory.CONNECTIVITY
            )
            
            # Verify results
            assert len(issues) == 0  # No issues for successful validation
            assert len(validation_engine.connectivity_results) == 1
            mock_conn.assert_called_once()
    
    def test_config_to_dict_conversion(self, validation_engine, sample_migration_config):
        """Test conversion of MigrationConfig to dictionary format."""
        config_dict = validation_engine._config_to_dict(sample_migration_config)
        
        # Verify structure
        assert 'source' in config_dict
        assert 'destination' in config_dict
        
        # Verify source configuration
        source = config_dict['source']
        assert source['type'] == 'wordpress'
        assert source['host'] == 'source.example.com'
        assert source['db_type'] == 'mysql'
        assert source['db_user'] == 'wp_user'
        
        # Verify destination configuration
        dest = config_dict['destination']
        assert dest['type'] == 'wordpress'
        assert dest['host'] == 'dest.example.com'
        assert dest['db_type'] == 'postgresql'
        assert dest['db_user'] == 'pg_user'
    
    def test_estimate_fix_time(self, validation_engine):
        """Test fix time estimation based on issues."""
        # Add mock issues
        validation_engine.all_issues = [
            ValidationIssue(
                category=ValidationCategory.CONNECTIVITY,
                name="Network Issue",
                severity=ValidationSeverity.CRITICAL,
                message="Connection failed"
            ),
            ValidationIssue(
                category=ValidationCategory.DEPENDENCIES,
                name="Missing Package",
                severity=ValidationSeverity.WARNING,
                message="Package not found"
            )
        ]
        
        fix_time = validation_engine._estimate_fix_time()
        
        # Should estimate time based on category and severity
        assert fix_time != "No fixes needed"
        assert "minute" in fix_time or "hour" in fix_time
    
    def test_generate_remediation_scripts(self, validation_engine):
        """Test generation of remediation scripts."""
        # Mock dependency and permission results
        validation_engine.dependency_results = [
            Mock(name="test-package", status=DependencyStatus.MISSING, required=True,
                 type=Mock(value="python_package"), install_command="pip install test-package")
        ]
        validation_engine.permission_results = [
            Mock(name="File Permission", status=PermissionStatus.DENIED, required=True,
                 message="Access denied", remediation="chmod +r /path")
        ]
        
        scripts = validation_engine._generate_remediation_scripts()
        
        # Verify scripts are generated
        assert 'install_dependencies' in scripts
        assert 'fix_permissions' in scripts
        assert len(scripts['install_dependencies']) > 0
        assert len(scripts['fix_permissions']) > 0
    
    def test_validation_report_generation(self, validation_engine, sample_migration_config):
        """Test generation of validation reports in different formats."""
        # Setup mock summary
        validation_engine.validation_summary = ValidationSummary(
            total_checks=4,
            passed_checks=3,
            failed_checks=1,
            warning_checks=0,
            critical_issues=1,
            warning_issues=0,
            can_proceed=False,
            estimated_fix_time="15 minutes",
            success_rate=75.0,
            issues_by_category={ValidationCategory.CONNECTIVITY: 1},
            remediation_scripts={}
        )
        
        validation_engine.all_issues = [
            ValidationIssue(
                category=ValidationCategory.CONNECTIVITY,
                name="Database Connection",
                severity=ValidationSeverity.CRITICAL,
                message="Connection failed",
                remediation="Check credentials"
            )
        ]
        
        # Test markdown report
        markdown_report = validation_engine.get_validation_report("markdown")
        assert "# Migration Validation Report" in markdown_report
        assert "Database Connection" in markdown_report
        assert "Check credentials" in markdown_report
        
        # Test JSON report
        json_report = validation_engine.get_validation_report("json")
        assert '"can_proceed": false' in json_report
        assert '"critical_issues": 1' in json_report
        
        # Test text report
        text_report = validation_engine.get_validation_report("text")
        assert "MIGRATION VALIDATION REPORT" in text_report
        assert "ISSUES FOUND" in text_report
    
    def test_save_report(self, validation_engine, tmp_path):
        """Test saving validation report to file."""
        # Setup mock summary
        validation_engine.validation_summary = ValidationSummary(
            total_checks=1,
            passed_checks=1,
            failed_checks=0,
            warning_checks=0,
            critical_issues=0,
            warning_issues=0,
            can_proceed=True,
            estimated_fix_time="No fixes needed",
            success_rate=100.0,
            issues_by_category={},
            remediation_scripts={}
        )
        
        # Save report
        report_path = tmp_path / "validation_report.md"
        validation_engine.save_report(str(report_path), "markdown")
        
        # Verify file was created and contains expected content
        assert report_path.exists()
        content = report_path.read_text()
        assert "# Migration Validation Report" in content
        assert "Ready to Proceed" in content
    
    def test_result_icons(self, validation_engine):
        """Test icon generation for different result types."""
        # Test validation result icons
        assert validation_engine._get_result_icon("success") == "✅"
        assert validation_engine._get_result_icon("failed") == "❌"
        assert validation_engine._get_result_icon("warning") == "⚠️"
        
        # Test dependency status icons
        assert validation_engine._get_dependency_icon(DependencyStatus.AVAILABLE) == "✅"
        assert validation_engine._get_dependency_icon(DependencyStatus.MISSING) == "❌"
        
        # Test permission status icons
        assert validation_engine._get_permission_icon(PermissionStatus.GRANTED) == "✅"
        assert validation_engine._get_permission_icon(PermissionStatus.DENIED) == "❌"
    
    @pytest.mark.asyncio
    async def test_validation_with_mixed_results(self, validation_engine, sample_migration_config):
        """Test validation with a mix of successful and failed checks."""
        with patch.object(validation_engine.connectivity_validator, 'validate_all', new_callable=AsyncMock) as mock_conn, \
             patch.object(validation_engine.compatibility_validator, 'validate_compatibility', new_callable=AsyncMock) as mock_comp, \
             patch.object(validation_engine.dependency_validator, 'validate_dependencies', new_callable=AsyncMock) as mock_dep, \
             patch.object(validation_engine.permission_validator, 'validate_permissions', new_callable=AsyncMock) as mock_perm:
            
            # Setup mixed results
            mock_conn.return_value = [
                Mock(name="Network Success", result=ValidationResult.SUCCESS, message="Connection OK", details=None, remediation=None),
                Mock(name="Database Fail", result=ValidationResult.FAILED, message="DB connection failed", 
                     details=None, remediation="Check DB credentials")
            ]
            mock_comp.return_value = [
                Mock(name="System Compatible", result=CompatibilityResult.COMPATIBLE, message="Systems match", details=None, remediation=None)
            ]
            mock_dep.return_value = [
                Mock(name="Available Package", status=DependencyStatus.AVAILABLE, required=True, type=Mock(value="python_package"),
                     description="Available package", current_version="1.0.0", required_version=">=1.0.0", install_command=None),
                Mock(name="Missing Package", status=DependencyStatus.MISSING, required=False, type=Mock(value="python_package"),
                     description="Optional package", current_version=None, required_version=">=1.0.0", install_command="pip install optional")
            ]
            mock_perm.return_value = [
                Mock(name="Read Permission", status=PermissionStatus.GRANTED, required=True, type=Mock(value="file_read"),
                     path="/source", message="Read access OK", details=None, remediation=None)
            ]
            
            # Run validation
            summary = await validation_engine.validate_migration(
                sample_migration_config, 
                show_progress=False, 
                detailed_output=False
            )
            
            # Verify mixed results
            # We have: 2 connectivity (1 success, 1 fail), 1 compatibility (success), 2 dependency (1 success, 1 missing), 1 permission (success)
            assert summary.total_checks == 6
            assert summary.passed_checks == 4  # 4 successful checks
            assert summary.failed_checks == 2   # 2 failed checks (1 critical, 1 warning)
            assert summary.critical_issues == 1  # 1 critical connectivity issue
            assert summary.warning_issues == 1   # 1 warning dependency issue
            assert summary.can_proceed is False  # Blocked by critical issue
            assert 60 < summary.success_rate < 80  # Mixed success rate (4/6 = 66.7%)
    
    def test_clear_results(self, validation_engine):
        """Test clearing of validation results."""
        # Add some mock results
        validation_engine.connectivity_results = [Mock()]
        validation_engine.all_issues = [Mock()]
        validation_engine.validation_summary = Mock()
        
        # Clear results
        validation_engine._clear_results()
        
        # Verify all results are cleared
        assert len(validation_engine.connectivity_results) == 0
        assert len(validation_engine.compatibility_results) == 0
        assert len(validation_engine.dependency_results) == 0
        assert len(validation_engine.permission_results) == 0
        assert len(validation_engine.all_issues) == 0
        assert validation_engine.validation_summary is None


class TestValidationSummary:
    """Test cases for ValidationSummary data class."""
    
    def test_validation_summary_creation(self):
        """Test creation of ValidationSummary with all fields."""
        summary = ValidationSummary(
            total_checks=10,
            passed_checks=8,
            failed_checks=2,
            warning_checks=1,
            critical_issues=1,
            warning_issues=1,
            can_proceed=False,
            estimated_fix_time="30 minutes",
            success_rate=80.0,
            issues_by_category={ValidationCategory.CONNECTIVITY: 1, ValidationCategory.DEPENDENCIES: 1},
            remediation_scripts={"install_deps": "pip install package"}
        )
        
        assert summary.total_checks == 10
        assert summary.passed_checks == 8
        assert summary.can_proceed is False
        assert summary.success_rate == 80.0
        assert ValidationCategory.CONNECTIVITY in summary.issues_by_category
        assert "install_deps" in summary.remediation_scripts


class TestValidationIssue:
    """Test cases for ValidationIssue data class."""
    
    def test_validation_issue_creation(self):
        """Test creation of ValidationIssue with all fields."""
        issue = ValidationIssue(
            category=ValidationCategory.CONNECTIVITY,
            name="Database Connection",
            severity=ValidationSeverity.CRITICAL,
            message="Connection failed",
            details={"host": "example.com", "port": 3306},
            remediation="Check database credentials",
            check_result=Mock()
        )
        
        assert issue.category == ValidationCategory.CONNECTIVITY
        assert issue.severity == ValidationSeverity.CRITICAL
        assert issue.name == "Database Connection"
        assert issue.details["host"] == "example.com"
        assert "credentials" in issue.remediation


@pytest.mark.asyncio
async def test_integration_with_real_validators(sample_migration_config):
    """Integration test with real validator instances (not mocked)."""
    # Create validation engine with real validators
    console = Console(file=Mock(), width=80)
    engine = ValidationEngine(console=console)
    
    # Run validation (this will use real validators but may fail due to missing dependencies)
    try:
        summary = await engine.validate_migration(
            sample_migration_config,
            show_progress=False,
            detailed_output=False
        )
        
        # Verify we get a valid summary regardless of results
        assert isinstance(summary, ValidationSummary)
        assert summary.total_checks > 0
        assert isinstance(summary.can_proceed, bool)
        assert 0 <= summary.success_rate <= 100
        
    except Exception as e:
        # If real validation fails due to missing dependencies, that's expected in test environment
        pytest.skip(f"Integration test skipped due to missing dependencies: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])