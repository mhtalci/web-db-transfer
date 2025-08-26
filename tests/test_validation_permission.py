"""
Unit tests for permission validation module.
"""

import pytest
import os
import stat
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from migration_assistant.models.config import (
    SystemType, DatabaseType, TransferMethod, MigrationConfig,
    SystemConfig, DatabaseConfig, TransferConfig, MigrationOptions,
    AuthConfig, PathConfig, AuthType
)
from migration_assistant.validation.permission import (
    PermissionValidator, PermissionCheck, PermissionStatus, PermissionType
)


@pytest.fixture
def permission_validator():
    """Create a PermissionValidator instance for testing."""
    return PermissionValidator()


@pytest.fixture
def sample_migration_config(tmp_path):
    """Create a sample migration configuration for testing."""
    auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
    
    source_path = PathConfig(root_path=str(tmp_path / "source"))
    dest_path = PathConfig(root_path=str(tmp_path / "dest"))
    
    # Create directories
    os.makedirs(source_path.root_path, exist_ok=True)
    os.makedirs(dest_path.root_path, exist_ok=True)
    
    source_db = DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="source.example.com",
        database_name="source_db"
    )
    
    source = SystemConfig(
        type=SystemType.WORDPRESS,
        host="source.example.com",
        authentication=auth_config,
        paths=source_path,
        database=source_db
    )
    
    destination = SystemConfig(
        type=SystemType.WORDPRESS,
        host="dest.example.com",
        authentication=auth_config,
        paths=dest_path,
        database=source_db
    )
    
    transfer = TransferConfig(method=TransferMethod.SSH_SFTP)
    options = MigrationOptions()
    
    return MigrationConfig(
        name="test_migration",
        source=source,
        destination=destination,
        transfer=transfer,
        options=options
    )


class TestPermissionValidator:
    """Test cases for PermissionValidator."""
    
    @pytest.mark.asyncio
    async def test_validate_permissions_basic(self, permission_validator, sample_migration_config):
        """Test basic permission validation."""
        checks = await permission_validator.validate_permissions(sample_migration_config)
        
        assert isinstance(checks, list)
        assert len(checks) > 0
        
        # Should have filesystem checks for both source and destination
        fs_checks = [c for c in checks if "Path" in c.name or "Directory" in c.name or "Write Test" in c.name]
        assert len(fs_checks) > 0
    
    @pytest.mark.asyncio
    async def test_check_filesystem_permissions_source_readable(self, permission_validator, tmp_path):
        """Test filesystem permission check for readable source."""
        auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
        path_config = PathConfig(root_path=str(tmp_path))
        
        # Create a readable directory
        test_dir = tmp_path / "readable"
        test_dir.mkdir()
        
        path_config.root_path = str(test_dir)
        
        system = SystemConfig(
            type=SystemType.WORDPRESS,
            host="test.example.com",
            authentication=auth_config,
            paths=path_config
        )
        
        checks = await permission_validator._check_filesystem_permissions(system, "source")
        
        # Should have successful read checks
        read_checks = [c for c in checks if c.status == PermissionStatus.GRANTED]
        assert len(read_checks) > 0
    
    @pytest.mark.asyncio
    async def test_check_filesystem_permissions_nonexistent_path(self, permission_validator):
        """Test filesystem permission check for nonexistent path."""
        auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
        path_config = PathConfig(root_path="/nonexistent/path")
        
        system = SystemConfig(
            type=SystemType.WORDPRESS,
            host="test.example.com",
            authentication=auth_config,
            paths=path_config
        )
        
        checks = await permission_validator._check_filesystem_permissions(system, "source")
        
        # Should have a denied check for nonexistent path
        assert len(checks) == 1
        assert checks[0].status == PermissionStatus.DENIED
        assert "does not exist" in checks[0].message
    
    @pytest.mark.asyncio
    async def test_check_filesystem_permissions_destination_writable(self, permission_validator, tmp_path):
        """Test filesystem permission check for writable destination."""
        auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
        
        # Create a writable directory
        test_dir = tmp_path / "writable"
        test_dir.mkdir()
        
        path_config = PathConfig(root_path=str(test_dir))
        
        system = SystemConfig(
            type=SystemType.WORDPRESS,
            host="test.example.com",
            authentication=auth_config,
            paths=path_config
        )
        
        checks = await permission_validator._check_filesystem_permissions(system, "destination")
        
        # Should have successful write checks
        write_checks = [c for c in checks if "Write" in c.name and c.status == PermissionStatus.GRANTED]
        assert len(write_checks) > 0
    
    @pytest.mark.asyncio
    async def test_check_path_permission_read_granted(self, permission_validator, tmp_path):
        """Test path permission check for read access."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        check = await permission_validator._check_path_permission(
            str(test_file), PermissionType.FILE_READ, "test system"
        )
        
        assert check.status == PermissionStatus.GRANTED
        assert "read" in check.message.lower()
    
    @pytest.mark.asyncio
    async def test_check_path_permission_nonexistent(self, permission_validator):
        """Test path permission check for nonexistent file."""
        check = await permission_validator._check_path_permission(
            "/nonexistent/file.txt", PermissionType.FILE_READ, "test system"
        )
        
        assert check.status == PermissionStatus.DENIED
        assert "Cannot access path" in check.message
    
    @pytest.mark.asyncio
    async def test_test_write_access_success(self, permission_validator, tmp_path):
        """Test write access test with successful write."""
        check = await permission_validator._test_write_access(str(tmp_path), "test system")
        
        assert check.status == PermissionStatus.GRANTED
        assert "Successfully created and deleted test file" in check.message
    
    @pytest.mark.asyncio
    async def test_test_write_access_denied(self, permission_validator):
        """Test write access test with denied write."""
        # Use a read-only directory (if we can create one)
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            check = await permission_validator._test_write_access("/tmp", "test system")
            
            assert check.status == PermissionStatus.DENIED
            assert "Cannot create files" in check.message
    
    @pytest.mark.asyncio
    async def test_test_directory_creation_success(self, permission_validator, tmp_path):
        """Test directory creation test with success."""
        check = await permission_validator._test_directory_creation(str(tmp_path), "test system")
        
        assert check.status == PermissionStatus.GRANTED
        assert "Successfully created and removed test directory" in check.message
    
    @pytest.mark.asyncio
    async def test_test_directory_creation_denied(self, permission_validator):
        """Test directory creation test with denied access."""
        with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
            check = await permission_validator._test_directory_creation("/tmp", "test system")
            
            assert check.status == PermissionStatus.DENIED
            assert "Cannot create subdirectories" in check.message
    
    @pytest.mark.asyncio
    async def test_check_backup_permissions_create_directory(self, permission_validator, tmp_path):
        """Test backup permission check that creates directory."""
        backup_path = str(tmp_path / "backup")
        
        checks = await permission_validator._check_backup_permissions(backup_path, "test system")
        
        # Should create directory and test write access
        assert len(checks) >= 1
        create_checks = [c for c in checks if "Creation" in c.name]
        if create_checks:
            assert create_checks[0].status == PermissionStatus.GRANTED
    
    @pytest.mark.asyncio
    async def test_check_backup_permissions_existing_directory(self, permission_validator, tmp_path):
        """Test backup permission check with existing directory."""
        backup_dir = tmp_path / "existing_backup"
        backup_dir.mkdir()
        
        checks = await permission_validator._check_backup_permissions(str(backup_dir), "test system")
        
        # Should test write access
        write_checks = [c for c in checks if "Write Test" in c.name]
        assert len(write_checks) == 1
        assert write_checks[0].status == PermissionStatus.GRANTED
    
    @pytest.mark.asyncio
    async def test_check_database_permissions_source(self, permission_validator):
        """Test database permission check for source."""
        db_config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="test.example.com",
            database_name="test_db"
        )
        
        checks = await permission_validator._check_database_permissions(db_config, "source")
        
        # Should have read permission check
        read_checks = [c for c in checks if c.type == PermissionType.DATABASE_READ]
        assert len(read_checks) == 1
        assert read_checks[0].status == PermissionStatus.UNKNOWN  # Can't verify without connection
    
    @pytest.mark.asyncio
    async def test_check_database_permissions_destination(self, permission_validator):
        """Test database permission check for destination."""
        db_config = DatabaseConfig(
            type=DatabaseType.MYSQL,
            host="test.example.com",
            database_name="test_db"
        )
        
        checks = await permission_validator._check_database_permissions(db_config, "destination")
        
        # Should have write and create permission checks
        write_checks = [c for c in checks if c.type == PermissionType.DATABASE_WRITE]
        create_checks = [c for c in checks if c.type == PermissionType.DATABASE_CREATE]
        
        assert len(write_checks) == 1
        assert len(create_checks) == 1
        assert write_checks[0].required is True
        assert create_checks[0].required is False
    
    @pytest.mark.asyncio
    async def test_check_network_permissions(self, permission_validator, sample_migration_config):
        """Test network permission checks."""
        checks = await permission_validator._check_network_permissions(sample_migration_config)
        
        # Should have network connectivity checks for both systems
        network_checks = [c for c in checks if c.type == PermissionType.NETWORK_CONNECT]
        assert len(network_checks) >= 2  # At least source and destination
        
        # All should be unknown status (need actual connectivity test)
        for check in network_checks:
            assert check.status == PermissionStatus.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_check_system_permissions_rsync(self, permission_validator, sample_migration_config):
        """Test system permission checks for rsync."""
        sample_migration_config.transfer.method = TransferMethod.RSYNC
        
        checks = await permission_validator._check_system_permissions(sample_migration_config)
        
        # Should have system command execution check
        cmd_checks = [c for c in checks if c.type == PermissionType.SYSTEM_COMMAND]
        assert len(cmd_checks) >= 1
        
        rsync_checks = [c for c in cmd_checks if "rsync" in c.message.lower()]
        assert len(rsync_checks) == 1
    
    @pytest.mark.asyncio
    async def test_check_system_permissions_docker(self, permission_validator, sample_migration_config):
        """Test system permission checks for Docker."""
        sample_migration_config.source.type = SystemType.DOCKER_CONTAINER
        
        checks = await permission_validator._check_system_permissions(sample_migration_config)
        
        # Should have Docker access check
        docker_checks = [c for c in checks if "Docker" in c.name]
        assert len(docker_checks) == 1
        assert docker_checks[0].type == PermissionType.SYSTEM_COMMAND
    
    @pytest.mark.asyncio
    async def test_check_temporary_permissions_success(self, permission_validator):
        """Test temporary directory permission check with success."""
        checks = await permission_validator._check_temporary_permissions()
        
        # Should have one check for temp directory
        assert len(checks) == 1
        temp_check = checks[0]
        assert temp_check.name == "Temporary Directory Access"
        assert temp_check.type == PermissionType.DIRECTORY_WRITE
        # Should succeed in most environments
        assert temp_check.status in [PermissionStatus.GRANTED, PermissionStatus.DENIED]
    
    @pytest.mark.asyncio
    async def test_check_temporary_permissions_denied(self, permission_validator):
        """Test temporary directory permission check with denied access."""
        with patch('tempfile.NamedTemporaryFile', side_effect=PermissionError("Permission denied")):
            checks = await permission_validator._check_temporary_permissions()
            
            assert len(checks) == 1
            assert checks[0].status == PermissionStatus.DENIED
            assert "Cannot create temporary files" in checks[0].message
    
    def test_get_permission_summary_all_granted(self, permission_validator):
        """Test permission summary with all permissions granted."""
        checks = [
            PermissionCheck(
                name="Test 1",
                type=PermissionType.FILE_READ,
                status=PermissionStatus.GRANTED,
                required=True
            ),
            PermissionCheck(
                name="Test 2",
                type=PermissionType.FILE_WRITE,
                status=PermissionStatus.GRANTED,
                required=False
            )
        ]
        
        summary = permission_validator.get_permission_summary(checks)
        
        assert summary["total_checks"] == 2
        assert summary["granted"] == 2
        assert summary["denied"] == 0
        assert summary["required_denied"] == 0
        assert summary["can_proceed"] is True
        assert summary["success_rate"] == 100.0
    
    def test_get_permission_summary_some_denied(self, permission_validator):
        """Test permission summary with some permissions denied."""
        checks = [
            PermissionCheck(
                name="Test 1",
                type=PermissionType.FILE_READ,
                status=PermissionStatus.GRANTED,
                required=True
            ),
            PermissionCheck(
                name="Test 2",
                type=PermissionType.FILE_WRITE,
                status=PermissionStatus.DENIED,
                required=True
            ),
            PermissionCheck(
                name="Test 3",
                type=PermissionType.FILE_EXECUTE,
                status=PermissionStatus.DENIED,
                required=False
            )
        ]
        
        summary = permission_validator.get_permission_summary(checks)
        
        assert summary["total_checks"] == 3
        assert summary["granted"] == 1
        assert summary["denied"] == 2
        assert summary["required_denied"] == 1
        assert summary["can_proceed"] is False
        assert summary["success_rate"] == pytest.approx(33.33, rel=1e-2)
    
    def test_generate_permission_fix_script_no_issues(self, permission_validator):
        """Test generating permission fix script with no issues."""
        checks = [
            PermissionCheck(
                name="Test 1",
                type=PermissionType.FILE_READ,
                status=PermissionStatus.GRANTED,
                required=True
            )
        ]
        
        script = permission_validator.generate_permission_fix_script(checks)
        
        assert "No permission issues found" in script
    
    def test_generate_permission_fix_script_with_issues(self, permission_validator):
        """Test generating permission fix script with issues."""
        checks = [
            PermissionCheck(
                name="File Write Test",
                type=PermissionType.FILE_WRITE,
                status=PermissionStatus.DENIED,
                message="Cannot write to directory",
                remediation="chmod +w /path/to/directory",
                required=True
            ),
            PermissionCheck(
                name="Directory Creation",
                type=PermissionType.DIRECTORY_CREATE,
                status=PermissionStatus.DENIED,
                message="Cannot create subdirectories",
                remediation="sudo chown user:group /path/to/parent",
                required=True
            )
        ]
        
        script = permission_validator.generate_permission_fix_script(checks)
        
        assert "#!/bin/bash" in script
        assert "chmod +w /path/to/directory" in script
        assert "sudo chown user:group /path/to/parent" in script
        assert "Fix: File Write Test" in script
        assert "Fix: Directory Creation" in script


class TestPermissionCheck:
    """Test cases for PermissionCheck dataclass."""
    
    def test_permission_check_creation(self):
        """Test creating a PermissionCheck instance."""
        check = PermissionCheck(
            name="Test Permission",
            type=PermissionType.FILE_READ,
            status=PermissionStatus.GRANTED
        )
        
        assert check.name == "Test Permission"
        assert check.type == PermissionType.FILE_READ
        assert check.status == PermissionStatus.GRANTED
        assert check.path is None
        assert check.message == ""
        assert check.required is True
    
    def test_permission_check_with_details(self):
        """Test creating a PermissionCheck with all fields."""
        details = {"owner": "user", "permissions": "755"}
        
        check = PermissionCheck(
            name="File Access",
            type=PermissionType.FILE_WRITE,
            status=PermissionStatus.DENIED,
            path="/path/to/file",
            message="Write permission denied",
            details=details,
            remediation="chmod +w /path/to/file",
            required=False
        )
        
        assert check.path == "/path/to/file"
        assert check.message == "Write permission denied"
        assert check.details == details
        assert check.remediation == "chmod +w /path/to/file"
        assert check.required is False


class TestPermissionEnums:
    """Test cases for permission-related enums."""
    
    def test_permission_type_values(self):
        """Test PermissionType enum values."""
        assert PermissionType.FILE_READ.value == "file_read"
        assert PermissionType.FILE_WRITE.value == "file_write"
        assert PermissionType.DIRECTORY_READ.value == "directory_read"
        assert PermissionType.DATABASE_READ.value == "database_read"
        assert PermissionType.NETWORK_CONNECT.value == "network_connect"
    
    def test_permission_status_values(self):
        """Test PermissionStatus enum values."""
        assert PermissionStatus.GRANTED.value == "granted"
        assert PermissionStatus.DENIED.value == "denied"
        assert PermissionStatus.PARTIAL.value == "partial"
        assert PermissionStatus.UNKNOWN.value == "unknown"