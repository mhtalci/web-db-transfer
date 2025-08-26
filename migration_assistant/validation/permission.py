"""
Permission validation module for checking file system and database access permissions.
"""

import asyncio
import logging
import os
import stat
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from migration_assistant.models.config import (
    SystemType, DatabaseType, MigrationConfig, SystemConfig, DatabaseConfig
)

logger = logging.getLogger(__name__)


class PermissionType(str, Enum):
    """Types of permissions to check"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EXECUTE = "file_execute"
    DIRECTORY_READ = "directory_read"
    DIRECTORY_WRITE = "directory_write"
    DIRECTORY_CREATE = "directory_create"
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    DATABASE_CREATE = "database_create"
    DATABASE_DROP = "database_drop"
    NETWORK_CONNECT = "network_connect"
    SYSTEM_COMMAND = "system_command"


class PermissionStatus(str, Enum):
    """Permission check status"""
    GRANTED = "granted"
    DENIED = "denied"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class PermissionCheck:
    """Result of a permission check"""
    name: str
    type: PermissionType
    status: PermissionStatus
    path: Optional[str] = None
    message: str = ""
    details: Optional[Dict[str, Any]] = None
    remediation: Optional[str] = None
    required: bool = True


class PermissionValidator:
    """
    Validates file system and database access permissions required
    for migration operations.
    """
    
    def __init__(self):
        self.temp_dir = None
    
    async def validate_permissions(self, config: MigrationConfig) -> List[PermissionCheck]:
        """
        Validate all permissions required for the migration configuration.
        
        Args:
            config: Migration configuration
            
        Returns:
            List of permission check results
        """
        checks = []
        
        # File system permissions for source
        source_fs_checks = await self._check_filesystem_permissions(
            config.source, "source"
        )
        checks.extend(source_fs_checks)
        
        # File system permissions for destination
        dest_fs_checks = await self._check_filesystem_permissions(
            config.destination, "destination"
        )
        checks.extend(dest_fs_checks)
        
        # Database permissions for source
        if config.source.database:
            source_db_checks = await self._check_database_permissions(
                config.source.database, "source"
            )
            checks.extend(source_db_checks)
        
        # Database permissions for destination
        if config.destination.database:
            dest_db_checks = await self._check_database_permissions(
                config.destination.database, "destination"
            )
            checks.extend(dest_db_checks)
        
        # Network permissions
        network_checks = await self._check_network_permissions(config)
        checks.extend(network_checks)
        
        # System command permissions
        system_checks = await self._check_system_permissions(config)
        checks.extend(system_checks)
        
        # Temporary directory permissions
        temp_checks = await self._check_temporary_permissions()
        checks.extend(temp_checks)
        
        return checks
    
    async def _check_filesystem_permissions(
        self, system: SystemConfig, system_type: str
    ) -> List[PermissionCheck]:
        """Check file system permissions for a system"""
        checks = []
        
        root_path = system.paths.root_path
        system_name = f"{system_type} ({system.type.value})"
        
        # Check if root path exists and is accessible
        if not os.path.exists(root_path):
            checks.append(PermissionCheck(
                name=f"Root Path Access - {system_name}",
                type=PermissionType.DIRECTORY_READ,
                status=PermissionStatus.DENIED,
                path=root_path,
                message=f"Root path does not exist: {root_path}",
                remediation="Create the directory or verify the path is correct"
            ))
            return checks
        
        # Check read permissions on root path
        read_check = await self._check_path_permission(
            root_path, PermissionType.DIRECTORY_READ, system_name
        )
        checks.append(read_check)
        
        # For source systems, we need read access
        if system_type == "source":
            # Check if we can list directory contents
            try:
                os.listdir(root_path)
                checks.append(PermissionCheck(
                    name=f"Directory Listing - {system_name}",
                    type=PermissionType.DIRECTORY_READ,
                    status=PermissionStatus.GRANTED,
                    path=root_path,
                    message="Can list directory contents"
                ))
            except PermissionError:
                checks.append(PermissionCheck(
                    name=f"Directory Listing - {system_name}",
                    type=PermissionType.DIRECTORY_READ,
                    status=PermissionStatus.DENIED,
                    path=root_path,
                    message="Cannot list directory contents",
                    remediation="Grant read permissions to the directory"
                ))
            
            # Check read access to important subdirectories
            important_paths = []
            if system.paths.web_root:
                important_paths.append(system.paths.web_root)
            if system.paths.config_path:
                important_paths.append(system.paths.config_path)
            
            for path in important_paths:
                if os.path.exists(path):
                    path_check = await self._check_path_permission(
                        path, PermissionType.DIRECTORY_READ, system_name
                    )
                    checks.append(path_check)
        
        # For destination systems, we need write access
        elif system_type == "destination":
            # Check write permissions
            write_check = await self._check_path_permission(
                root_path, PermissionType.DIRECTORY_WRITE, system_name
            )
            checks.append(write_check)
            
            # Test actual write access
            write_test = await self._test_write_access(root_path, system_name)
            checks.append(write_test)
            
            # Check if we can create subdirectories
            create_check = await self._test_directory_creation(root_path, system_name)
            checks.append(create_check)
        
        # Check backup directory permissions if specified
        if system.paths.backup_path:
            backup_checks = await self._check_backup_permissions(
                system.paths.backup_path, system_name
            )
            checks.extend(backup_checks)
        
        return checks
    
    async def _check_path_permission(
        self, path: str, permission_type: PermissionType, system_name: str
    ) -> PermissionCheck:
        """Check specific permission on a path"""
        
        try:
            path_stat = os.stat(path)
            path_mode = path_stat.st_mode
            
            # Check if we own the file/directory
            is_owner = path_stat.st_uid == os.getuid() if hasattr(os, 'getuid') else True
            
            # Determine required permission bits
            if permission_type == PermissionType.FILE_READ:
                required_bit = stat.S_IRUSR if is_owner else stat.S_IROTH
                action = "read"
            elif permission_type == PermissionType.FILE_WRITE:
                required_bit = stat.S_IWUSR if is_owner else stat.S_IWOTH
                action = "write"
            elif permission_type == PermissionType.FILE_EXECUTE:
                required_bit = stat.S_IXUSR if is_owner else stat.S_IXOTH
                action = "execute"
            elif permission_type == PermissionType.DIRECTORY_READ:
                required_bit = stat.S_IRUSR if is_owner else stat.S_IROTH
                action = "read"
            elif permission_type == PermissionType.DIRECTORY_WRITE:
                required_bit = stat.S_IWUSR if is_owner else stat.S_IWOTH
                action = "write"
            else:
                return PermissionCheck(
                    name=f"Permission Check - {system_name}",
                    type=permission_type,
                    status=PermissionStatus.UNKNOWN,
                    path=path,
                    message=f"Unknown permission type: {permission_type}"
                )
            
            # Check if permission is granted
            if path_mode & required_bit:
                return PermissionCheck(
                    name=f"Path {action.title()} - {system_name}",
                    type=permission_type,
                    status=PermissionStatus.GRANTED,
                    path=path,
                    message=f"Has {action} permission on {path}"
                )
            else:
                return PermissionCheck(
                    name=f"Path {action.title()} - {system_name}",
                    type=permission_type,
                    status=PermissionStatus.DENIED,
                    path=path,
                    message=f"No {action} permission on {path}",
                    remediation=f"Grant {action} permission: chmod +{action[0]} {path}"
                )
                
        except OSError as e:
            return PermissionCheck(
                name=f"Path Access - {system_name}",
                type=permission_type,
                status=PermissionStatus.DENIED,
                path=path,
                message=f"Cannot access path: {str(e)}",
                remediation="Check path exists and is accessible"
            )
    
    async def _test_write_access(self, directory: str, system_name: str) -> PermissionCheck:
        """Test actual write access by creating a temporary file"""
        
        try:
            # Create a temporary file in the directory
            test_file = os.path.join(directory, f".migration_test_{os.getpid()}")
            
            with open(test_file, 'w') as f:
                f.write("test")
            
            # Clean up
            os.remove(test_file)
            
            return PermissionCheck(
                name=f"Write Test - {system_name}",
                type=PermissionType.FILE_WRITE,
                status=PermissionStatus.GRANTED,
                path=directory,
                message="Successfully created and deleted test file"
            )
            
        except PermissionError:
            return PermissionCheck(
                name=f"Write Test - {system_name}",
                type=PermissionType.FILE_WRITE,
                status=PermissionStatus.DENIED,
                path=directory,
                message="Cannot create files in directory",
                remediation="Grant write permissions to the directory"
            )
        except OSError as e:
            return PermissionCheck(
                name=f"Write Test - {system_name}",
                type=PermissionType.FILE_WRITE,
                status=PermissionStatus.DENIED,
                path=directory,
                message=f"Write test failed: {str(e)}",
                remediation="Check directory permissions and disk space"
            )
    
    async def _test_directory_creation(self, parent_dir: str, system_name: str) -> PermissionCheck:
        """Test ability to create subdirectories"""
        
        try:
            # Create a temporary subdirectory
            test_dir = os.path.join(parent_dir, f".migration_test_dir_{os.getpid()}")
            
            os.makedirs(test_dir, exist_ok=True)
            
            # Clean up
            os.rmdir(test_dir)
            
            return PermissionCheck(
                name=f"Directory Creation - {system_name}",
                type=PermissionType.DIRECTORY_CREATE,
                status=PermissionStatus.GRANTED,
                path=parent_dir,
                message="Successfully created and removed test directory"
            )
            
        except PermissionError:
            return PermissionCheck(
                name=f"Directory Creation - {system_name}",
                type=PermissionType.DIRECTORY_CREATE,
                status=PermissionStatus.DENIED,
                path=parent_dir,
                message="Cannot create subdirectories",
                remediation="Grant write permissions to create subdirectories"
            )
        except OSError as e:
            return PermissionCheck(
                name=f"Directory Creation - {system_name}",
                type=PermissionType.DIRECTORY_CREATE,
                status=PermissionStatus.DENIED,
                path=parent_dir,
                message=f"Directory creation failed: {str(e)}",
                remediation="Check parent directory permissions"
            )
    
    async def _check_backup_permissions(self, backup_path: str, system_name: str) -> List[PermissionCheck]:
        """Check backup directory permissions"""
        checks = []
        
        # Check if backup directory exists
        if not os.path.exists(backup_path):
            # Try to create it
            try:
                os.makedirs(backup_path, exist_ok=True)
                checks.append(PermissionCheck(
                    name=f"Backup Directory Creation - {system_name}",
                    type=PermissionType.DIRECTORY_CREATE,
                    status=PermissionStatus.GRANTED,
                    path=backup_path,
                    message="Successfully created backup directory"
                ))
            except PermissionError:
                checks.append(PermissionCheck(
                    name=f"Backup Directory Creation - {system_name}",
                    type=PermissionType.DIRECTORY_CREATE,
                    status=PermissionStatus.DENIED,
                    path=backup_path,
                    message="Cannot create backup directory",
                    remediation="Create backup directory manually or grant permissions"
                ))
                return checks
        
        # Check write permissions on backup directory
        write_check = await self._test_write_access(backup_path, f"{system_name} Backup")
        checks.append(write_check)
        
        return checks
    
    async def _check_database_permissions(
        self, db_config: DatabaseConfig, system_type: str
    ) -> List[PermissionCheck]:
        """Check database permissions"""
        checks = []
        
        db_name = f"{system_type} ({db_config.type.value})"
        
        # For now, we'll do basic connectivity checks
        # More detailed permission checks would require actual database connections
        
        if system_type == "source":
            # Source needs read permissions
            checks.append(PermissionCheck(
                name=f"Database Read Access - {db_name}",
                type=PermissionType.DATABASE_READ,
                status=PermissionStatus.UNKNOWN,
                message="Database read permissions need to be verified during connectivity test",
                details={"host": db_config.host, "database": db_config.database_name},
                required=True
            ))
        
        elif system_type == "destination":
            # Destination needs write permissions
            checks.append(PermissionCheck(
                name=f"Database Write Access - {db_name}",
                type=PermissionType.DATABASE_WRITE,
                status=PermissionStatus.UNKNOWN,
                message="Database write permissions need to be verified during connectivity test",
                details={"host": db_config.host, "database": db_config.database_name},
                required=True
            ))
            
            # May need create/drop permissions for schema changes
            checks.append(PermissionCheck(
                name=f"Database Schema Permissions - {db_name}",
                type=PermissionType.DATABASE_CREATE,
                status=PermissionStatus.UNKNOWN,
                message="Database schema modification permissions recommended",
                details={"host": db_config.host, "database": db_config.database_name},
                required=False
            ))
        
        return checks
    
    async def _check_network_permissions(self, config: MigrationConfig) -> List[PermissionCheck]:
        """Check network connectivity permissions"""
        checks = []
        
        # Check if we can make outbound connections
        for system_name, system in [("source", config.source), ("destination", config.destination)]:
            
            # Basic network connectivity check
            checks.append(PermissionCheck(
                name=f"Network Connectivity - {system_name}",
                type=PermissionType.NETWORK_CONNECT,
                status=PermissionStatus.UNKNOWN,
                message=f"Network connectivity to {system.host} needs verification",
                details={"host": system.host, "port": system.port},
                required=True
            ))
            
            # Cloud service connectivity
            if system.cloud_config:
                checks.append(PermissionCheck(
                    name=f"Cloud Service Access - {system_name}",
                    type=PermissionType.NETWORK_CONNECT,
                    status=PermissionStatus.UNKNOWN,
                    message=f"Cloud service connectivity to {system.cloud_config.provider} needs verification",
                    details={"provider": system.cloud_config.provider},
                    required=True
                ))
        
        return checks
    
    async def _check_system_permissions(self, config: MigrationConfig) -> List[PermissionCheck]:
        """Check system command execution permissions"""
        checks = []
        
        # Check if we can execute system commands (needed for some transfer methods)
        transfer_method = config.transfer.method
        
        if transfer_method.value in ["rsync", "ssh_scp", "ssh_sftp"]:
            checks.append(PermissionCheck(
                name="System Command Execution",
                type=PermissionType.SYSTEM_COMMAND,
                status=PermissionStatus.UNKNOWN,
                message=f"System command execution needed for {transfer_method.value}",
                remediation="Ensure user can execute system commands",
                required=True
            ))
        
        # Check Docker permissions if needed
        if (config.source.type in ["docker_container", "kubernetes_pod"] or
            config.destination.type in ["docker_container", "kubernetes_pod"]):
            
            checks.append(PermissionCheck(
                name="Docker/Kubernetes Access",
                type=PermissionType.SYSTEM_COMMAND,
                status=PermissionStatus.UNKNOWN,
                message="Docker/Kubernetes access permissions need verification",
                remediation="Ensure user is in docker group or has kubectl access",
                required=True
            ))
        
        return checks
    
    async def _check_temporary_permissions(self) -> List[PermissionCheck]:
        """Check temporary directory permissions"""
        checks = []
        
        # Get system temporary directory
        temp_dir = tempfile.gettempdir()
        
        # Test write access to temp directory
        try:
            with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                tmp_file.write(b"test")
                tmp_file.flush()
            
            checks.append(PermissionCheck(
                name="Temporary Directory Access",
                type=PermissionType.DIRECTORY_WRITE,
                status=PermissionStatus.GRANTED,
                path=temp_dir,
                message="Can create temporary files"
            ))
            
        except PermissionError:
            checks.append(PermissionCheck(
                name="Temporary Directory Access",
                type=PermissionType.DIRECTORY_WRITE,
                status=PermissionStatus.DENIED,
                path=temp_dir,
                message="Cannot create temporary files",
                remediation="Grant write access to temporary directory or set TMPDIR environment variable"
            ))
        
        return checks
    
    def get_permission_summary(self, checks: List[PermissionCheck]) -> Dict[str, Any]:
        """Generate a summary of permission check results"""
        
        total_checks = len(checks)
        granted = len([c for c in checks if c.status == PermissionStatus.GRANTED])
        denied = len([c for c in checks if c.status == PermissionStatus.DENIED])
        partial = len([c for c in checks if c.status == PermissionStatus.PARTIAL])
        unknown = len([c for c in checks if c.status == PermissionStatus.UNKNOWN])
        
        required_denied = len([
            c for c in checks 
            if c.required and c.status == PermissionStatus.DENIED
        ])
        
        return {
            "total_checks": total_checks,
            "granted": granted,
            "denied": denied,
            "partial": partial,
            "unknown": unknown,
            "required_denied": required_denied,
            "can_proceed": required_denied == 0,
            "success_rate": (granted / total_checks * 100) if total_checks > 0 else 0
        }
    
    def generate_permission_fix_script(self, checks: List[PermissionCheck]) -> str:
        """Generate script to fix permission issues"""
        
        denied_checks = [c for c in checks if c.status == PermissionStatus.DENIED and c.remediation]
        
        if not denied_checks:
            return "# No permission issues found"
        
        script_lines = [
            "#!/bin/bash",
            "# Auto-generated permission fix script",
            "# Review and modify as needed before running",
            "set -e",
            "",
            "echo 'Fixing permission issues...'",
            ""
        ]
        
        for check in denied_checks:
            script_lines.append(f"# Fix: {check.name}")
            script_lines.append(f"# Issue: {check.message}")
            if check.remediation:
                script_lines.append(f"{check.remediation}")
            script_lines.append("")
        
        script_lines.append("echo 'Permission fixes complete!'")
        script_lines.append("echo 'Please verify the changes and re-run validation.'")
        
        return "\n".join(script_lines)