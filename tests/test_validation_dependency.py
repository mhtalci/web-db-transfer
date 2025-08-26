"""
Unit tests for dependency validation module.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import importlib
import sys

from migration_assistant.models.config import (
    SystemType, DatabaseType, TransferMethod, MigrationConfig,
    SystemConfig, DatabaseConfig, TransferConfig, MigrationOptions,
    AuthConfig, PathConfig, AuthType
)
from migration_assistant.validation.dependency import (
    DependencyValidator, DependencyCheck, DependencyStatus, DependencyType
)


@pytest.fixture
def dependency_validator():
    """Create a DependencyValidator instance for testing."""
    return DependencyValidator()


@pytest.fixture
def sample_migration_config():
    """Create a sample migration configuration for testing."""
    auth_config = AuthConfig(type=AuthType.PASSWORD, username="test", password="test")
    path_config = PathConfig(root_path="/var/www")
    
    source_db = DatabaseConfig(
        type=DatabaseType.MYSQL,
        host="source.example.com",
        database_name="source_db"
    )
    
    source = SystemConfig(
        type=SystemType.WORDPRESS,
        host="source.example.com",
        authentication=auth_config,
        paths=path_config,
        database=source_db
    )
    
    destination = SystemConfig(
        type=SystemType.WORDPRESS,
        host="dest.example.com",
        authentication=auth_config,
        paths=path_config,
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


class TestDependencyValidator:
    """Test cases for DependencyValidator."""
    
    @pytest.mark.asyncio
    async def test_validate_dependencies_basic(self, dependency_validator, sample_migration_config):
        """Test basic dependency validation."""
        with patch.object(dependency_validator, '_check_core_dependencies', return_value=[]):
            with patch.object(dependency_validator, '_check_database_dependencies', return_value=[]):
                with patch.object(dependency_validator, '_check_transfer_dependencies', return_value=[]):
                    with patch.object(dependency_validator, '_check_system_dependencies', return_value=[]):
                        with patch.object(dependency_validator, '_check_cloud_dependencies', return_value=[]):
                            checks = await dependency_validator.validate_dependencies(sample_migration_config)
                            
                            # Should call all check methods
                            assert isinstance(checks, list)
    
    @pytest.mark.asyncio
    async def test_check_core_dependencies(self, dependency_validator):
        """Test checking core Python dependencies."""
        with patch.object(dependency_validator, '_check_python_package') as mock_check:
            mock_check.return_value = DependencyCheck(
                name="click",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.AVAILABLE,
                required=True
            )
            
            checks = await dependency_validator._check_core_dependencies()
            
            assert len(checks) > 0
            assert mock_check.call_count > 0
            
            # Verify core packages are checked
            call_args = [call[0] for call in mock_check.call_args_list]
            package_names = [args[0] for args in call_args]
            assert "click" in package_names
            assert "rich" in package_names
            assert "pydantic" in package_names
    
    @pytest.mark.asyncio
    async def test_check_database_dependencies_mysql(self, dependency_validator, sample_migration_config):
        """Test checking MySQL database dependencies."""
        sample_migration_config.source.database.type = DatabaseType.MYSQL
        sample_migration_config.destination.database.type = DatabaseType.MYSQL
        
        with patch.object(dependency_validator, '_check_python_package') as mock_check_pkg:
            with patch.object(dependency_validator, '_check_system_tool') as mock_check_tool:
                mock_check_pkg.return_value = DependencyCheck(
                    name="mysql-connector-python",
                    type=DependencyType.PYTHON_PACKAGE,
                    status=DependencyStatus.AVAILABLE,
                    required=True
                )
                mock_check_tool.return_value = DependencyCheck(
                    name="mysql",
                    type=DependencyType.SYSTEM_TOOL,
                    status=DependencyStatus.AVAILABLE,
                    required=False
                )
                
                checks = await dependency_validator._check_database_dependencies(sample_migration_config)
                
                assert len(checks) > 0
                # Should check for mysql-connector-python
                pkg_calls = [call[0][0] for call in mock_check_pkg.call_args_list]
                assert "mysql-connector-python" in pkg_calls
    
    @pytest.mark.asyncio
    async def test_check_database_dependencies_postgresql(self, dependency_validator, sample_migration_config):
        """Test checking PostgreSQL database dependencies."""
        sample_migration_config.source.database.type = DatabaseType.POSTGRESQL
        
        with patch.object(dependency_validator, '_check_python_package') as mock_check_pkg:
            with patch.object(dependency_validator, '_check_system_tool') as mock_check_tool:
                mock_check_pkg.return_value = DependencyCheck(
                    name="psycopg2-binary",
                    type=DependencyType.PYTHON_PACKAGE,
                    status=DependencyStatus.AVAILABLE,
                    required=True
                )
                mock_check_tool.return_value = DependencyCheck(
                    name="psql",
                    type=DependencyType.SYSTEM_TOOL,
                    status=DependencyStatus.AVAILABLE,
                    required=False
                )
                
                checks = await dependency_validator._check_database_dependencies(sample_migration_config)
                
                # Should check for psycopg2
                pkg_calls = [call[0][0] for call in mock_check_pkg.call_args_list]
                assert "psycopg2-binary" in pkg_calls
    
    @pytest.mark.asyncio
    async def test_check_transfer_dependencies_ssh(self, dependency_validator):
        """Test checking SSH transfer dependencies."""
        transfer_config = TransferConfig(method=TransferMethod.SSH_SFTP)
        
        with patch.object(dependency_validator, '_check_python_package') as mock_check_pkg:
            with patch.object(dependency_validator, '_check_system_tool') as mock_check_tool:
                mock_check_pkg.return_value = DependencyCheck(
                    name="paramiko",
                    type=DependencyType.PYTHON_PACKAGE,
                    status=DependencyStatus.AVAILABLE,
                    required=True
                )
                mock_check_tool.return_value = DependencyCheck(
                    name="ssh",
                    type=DependencyType.SYSTEM_TOOL,
                    status=DependencyStatus.AVAILABLE,
                    required=False
                )
                
                checks = await dependency_validator._check_transfer_dependencies(transfer_config)
                
                # Should check for paramiko
                pkg_calls = [call[0][0] for call in mock_check_pkg.call_args_list]
                assert "paramiko" in pkg_calls
    
    @pytest.mark.asyncio
    async def test_check_transfer_dependencies_aws_s3(self, dependency_validator):
        """Test checking AWS S3 transfer dependencies."""
        transfer_config = TransferConfig(method=TransferMethod.AWS_S3)
        
        with patch.object(dependency_validator, '_check_python_package') as mock_check_pkg:
            mock_check_pkg.return_value = DependencyCheck(
                name="boto3",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.AVAILABLE,
                required=True
            )
            
            checks = await dependency_validator._check_transfer_dependencies(transfer_config)
            
            # Should check for boto3 and botocore
            pkg_calls = [call[0][0] for call in mock_check_pkg.call_args_list]
            assert "boto3" in pkg_calls
            assert "botocore" in pkg_calls
    
    @pytest.mark.asyncio
    async def test_check_python_package_available(self, dependency_validator):
        """Test checking available Python package."""
        # Mock successful import
        mock_module = MagicMock()
        mock_module.__version__ = "1.0.0"
        
        with patch('importlib.import_module', return_value=mock_module):
            check = await dependency_validator._check_python_package(
                "test_package", "test_package", ">=0.9.0", True, "Test package"
            )
            
            assert check.status == DependencyStatus.AVAILABLE
            assert check.current_version == "1.0.0"
            assert check.required is True
    
    @pytest.mark.asyncio
    async def test_check_python_package_missing(self, dependency_validator):
        """Test checking missing Python package."""
        # Mock ImportError
        with patch('importlib.import_module', side_effect=ImportError("No module named 'test_package'")):
            check = await dependency_validator._check_python_package(
                "test_package", "test_package", None, True, "Test package"
            )
            
            assert check.status == DependencyStatus.MISSING
            assert check.install_command == "pip install test_package"
            assert check.required is True
    
    @pytest.mark.asyncio
    async def test_check_python_package_wrong_version(self, dependency_validator):
        """Test checking Python package with wrong version."""
        mock_module = MagicMock()
        mock_module.__version__ = "0.5.0"
        
        with patch('importlib.import_module', return_value=mock_module):
            check = await dependency_validator._check_python_package(
                "test_package", "test_package", ">=1.0.0", True, "Test package"
            )
            
            assert check.status == DependencyStatus.WRONG_VERSION
            assert check.current_version == "0.5.0"
            assert check.required_version == ">=1.0.0"
    
    @pytest.mark.asyncio
    async def test_check_system_tool_available(self, dependency_validator):
        """Test checking available system tool."""
        with patch('shutil.which', return_value='/usr/bin/test_tool'):
            with patch.object(dependency_validator, '_get_tool_version', return_value="1.0.0"):
                check = await dependency_validator._check_system_tool(
                    "test_tool", "test-package", None, True, "Test tool"
                )
                
                assert check.status == DependencyStatus.AVAILABLE
                assert check.current_version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_check_system_tool_missing(self, dependency_validator):
        """Test checking missing system tool."""
        with patch('shutil.which', return_value=None):
            check = await dependency_validator._check_system_tool(
                "test_tool", "test-package", None, True, "Test tool"
            )
            
            assert check.status == DependencyStatus.MISSING
            assert "install test-package" in check.install_command.lower()
    
    @pytest.mark.asyncio
    async def test_get_tool_version(self, dependency_validator):
        """Test getting tool version."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"test_tool version 1.2.3\n", b"")
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            version = await dependency_validator._get_tool_version("test_tool")
            
            assert version == "1.2.3"
    
    @pytest.mark.asyncio
    async def test_get_tool_version_not_found(self, dependency_validator):
        """Test getting version of tool that doesn't support version command."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"command not found")
        mock_process.returncode = 1
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            version = await dependency_validator._get_tool_version("test_tool")
            
            assert version is None
    
    def test_get_install_command_macos(self, dependency_validator):
        """Test getting install command for macOS."""
        with patch('platform.system', return_value='Darwin'):
            command = dependency_validator._get_install_command("test-package")
            assert command == "brew install test-package"
    
    def test_get_install_command_ubuntu(self, dependency_validator):
        """Test getting install command for Ubuntu/Debian."""
        with patch('platform.system', return_value='Linux'):
            with patch('os.path.exists') as mock_exists:
                mock_exists.side_effect = lambda path: path == "/etc/debian_version"
                command = dependency_validator._get_install_command("test-package")
                assert command == "sudo apt-get install test-package"
    
    def test_get_install_command_centos(self, dependency_validator):
        """Test getting install command for CentOS/RHEL."""
        with patch('platform.system', return_value='Linux'):
            with patch('os.path.exists') as mock_exists:
                mock_exists.side_effect = lambda path: path == "/etc/redhat-release"
                command = dependency_validator._get_install_command("test-package")
                assert command == "sudo yum install test-package"
    
    def test_compare_versions_equal(self, dependency_validator):
        """Test version comparison for equal versions."""
        result = dependency_validator._compare_versions("1.2.3", "1.2.3")
        assert result == 0
    
    def test_compare_versions_less_than(self, dependency_validator):
        """Test version comparison for less than."""
        result = dependency_validator._compare_versions("1.2.2", "1.2.3")
        assert result == -1
    
    def test_compare_versions_greater_than(self, dependency_validator):
        """Test version comparison for greater than."""
        result = dependency_validator._compare_versions("1.2.4", "1.2.3")
        assert result == 1
    
    def test_compare_versions_different_lengths(self, dependency_validator):
        """Test version comparison with different lengths."""
        result = dependency_validator._compare_versions("1.2", "1.2.0")
        assert result == 0
        
        result = dependency_validator._compare_versions("1.2.1", "1.2")
        assert result == 1
    
    def test_get_missing_dependencies(self, dependency_validator):
        """Test getting missing required dependencies."""
        checks = [
            DependencyCheck(
                name="available_pkg",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.AVAILABLE,
                required=True
            ),
            DependencyCheck(
                name="missing_pkg",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.MISSING,
                required=True
            ),
            DependencyCheck(
                name="optional_missing",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.MISSING,
                required=False
            ),
        ]
        
        missing = dependency_validator.get_missing_dependencies(checks)
        
        assert len(missing) == 1
        assert missing[0].name == "missing_pkg"
    
    def test_get_optional_dependencies(self, dependency_validator):
        """Test getting missing optional dependencies."""
        checks = [
            DependencyCheck(
                name="available_pkg",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.AVAILABLE,
                required=False
            ),
            DependencyCheck(
                name="missing_required",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.MISSING,
                required=True
            ),
            DependencyCheck(
                name="missing_optional",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.MISSING,
                required=False
            ),
        ]
        
        optional = dependency_validator.get_optional_dependencies(checks)
        
        assert len(optional) == 1
        assert optional[0].name == "missing_optional"
    
    def test_generate_install_script_no_missing(self, dependency_validator):
        """Test generating install script with no missing dependencies."""
        checks = [
            DependencyCheck(
                name="available_pkg",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.AVAILABLE,
                required=True
            )
        ]
        
        script = dependency_validator.generate_install_script(checks)
        
        assert "All required dependencies are satisfied" in script
    
    def test_generate_install_script_with_missing(self, dependency_validator):
        """Test generating install script with missing dependencies."""
        checks = [
            DependencyCheck(
                name="missing_pkg",
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.MISSING,
                required=True,
                required_version=">=1.0.0"
            ),
            DependencyCheck(
                name="missing_tool",
                type=DependencyType.SYSTEM_TOOL,
                status=DependencyStatus.MISSING,
                required=True,
                install_command="sudo apt-get install missing-tool"
            )
        ]
        
        script = dependency_validator.generate_install_script(checks)
        
        assert "pip install missing_pkg>=1.0.0" in script
        assert "sudo apt-get install missing-tool" in script
        assert "#!/bin/bash" in script


class TestDependencyCheck:
    """Test cases for DependencyCheck dataclass."""
    
    def test_dependency_check_creation(self):
        """Test creating a DependencyCheck instance."""
        check = DependencyCheck(
            name="test_package",
            type=DependencyType.PYTHON_PACKAGE,
            status=DependencyStatus.AVAILABLE,
            required=True
        )
        
        assert check.name == "test_package"
        assert check.type == DependencyType.PYTHON_PACKAGE
        assert check.status == DependencyStatus.AVAILABLE
        assert check.required is True
        assert check.current_version is None
        assert check.alternatives is None
    
    def test_dependency_check_with_version(self):
        """Test creating a DependencyCheck with version information."""
        check = DependencyCheck(
            name="test_package",
            type=DependencyType.PYTHON_PACKAGE,
            status=DependencyStatus.WRONG_VERSION,
            required=True,
            current_version="0.9.0",
            required_version=">=1.0.0",
            install_command="pip install test_package>=1.0.0"
        )
        
        assert check.current_version == "0.9.0"
        assert check.required_version == ">=1.0.0"
        assert check.install_command == "pip install test_package>=1.0.0"


class TestDependencyEnums:
    """Test cases for dependency-related enums."""
    
    def test_dependency_type_values(self):
        """Test DependencyType enum values."""
        assert DependencyType.PYTHON_PACKAGE.value == "python_package"
        assert DependencyType.SYSTEM_TOOL.value == "system_tool"
        assert DependencyType.CLOUD_CLI.value == "cloud_cli"
    
    def test_dependency_status_values(self):
        """Test DependencyStatus enum values."""
        assert DependencyStatus.AVAILABLE.value == "available"
        assert DependencyStatus.MISSING.value == "missing"
        assert DependencyStatus.WRONG_VERSION.value == "wrong_version"
        assert DependencyStatus.OPTIONAL.value == "optional"