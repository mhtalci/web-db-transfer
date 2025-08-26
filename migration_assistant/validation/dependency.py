"""
Dependency validation module for verifying required Python packages and system tools.
"""

import asyncio
import importlib
import logging
import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from migration_assistant.models.config import (
    SystemType, DatabaseType, TransferMethod, MigrationConfig,
    SystemConfig, DatabaseConfig, TransferConfig
)

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
    """Types of dependencies"""
    PYTHON_PACKAGE = "python_package"
    SYSTEM_TOOL = "system_tool"
    SYSTEM_LIBRARY = "system_library"
    CLOUD_CLI = "cloud_cli"
    DATABASE_CLIENT = "database_client"


class DependencyStatus(str, Enum):
    """Dependency check status"""
    AVAILABLE = "available"
    MISSING = "missing"
    WRONG_VERSION = "wrong_version"
    OPTIONAL = "optional"


@dataclass
class DependencyCheck:
    """Result of a dependency check"""
    name: str
    type: DependencyType
    status: DependencyStatus
    required: bool
    current_version: Optional[str] = None
    required_version: Optional[str] = None
    install_command: Optional[str] = None
    description: Optional[str] = None
    alternatives: List[str] = None


class DependencyValidator:
    """
    Validates that all required Python packages and system tools
    are available for the migration configuration.
    """
    
    def __init__(self):
        self._init_dependency_mappings()
    
    def _init_dependency_mappings(self):
        """Initialize dependency mappings for different components"""
        
        # Python package dependencies by database type
        self.database_python_deps = {
            DatabaseType.MYSQL: [
                ("mysql-connector-python", "mysql.connector", ">=8.0.0", True),
                ("PyMySQL", "pymysql", ">=1.0.0", False),  # Alternative
            ],
            DatabaseType.POSTGRESQL: [
                ("psycopg2-binary", "psycopg2", ">=2.8.0", True),
                ("psycopg2", "psycopg2", ">=2.8.0", False),  # Alternative
            ],
            DatabaseType.MONGODB: [
                ("pymongo", "pymongo", ">=4.0.0", True),
            ],
            DatabaseType.REDIS: [
                ("redis", "redis", ">=4.0.0", True),
            ],
            DatabaseType.CASSANDRA: [
                ("cassandra-driver", "cassandra", ">=3.25.0", True),
            ],
            DatabaseType.ORACLE: [
                ("cx_Oracle", "cx_Oracle", ">=8.0.0", True),
            ],
            DatabaseType.SQLSERVER: [
                ("pyodbc", "pyodbc", ">=4.0.0", True),
            ],
        }
        
        # Python package dependencies by transfer method
        self.transfer_python_deps = {
            TransferMethod.SSH_SCP: [
                ("paramiko", "paramiko", ">=2.7.0", True),
            ],
            TransferMethod.SSH_SFTP: [
                ("paramiko", "paramiko", ">=2.7.0", True),
            ],
            TransferMethod.FTP: [],  # Built-in ftplib
            TransferMethod.FTPS: [],  # Built-in ftplib
            TransferMethod.AWS_S3: [
                ("boto3", "boto3", ">=1.20.0", True),
                ("botocore", "botocore", ">=1.23.0", True),
            ],
            TransferMethod.GOOGLE_CLOUD_STORAGE: [
                ("google-cloud-storage", "google.cloud.storage", ">=2.0.0", True),
            ],
            TransferMethod.AZURE_BLOB: [
                ("azure-storage-blob", "azure.storage.blob", ">=12.0.0", True),
            ],
            TransferMethod.DOCKER_VOLUME: [
                ("docker", "docker", ">=5.0.0", True),
            ],
            TransferMethod.KUBERNETES_VOLUME: [
                ("kubernetes", "kubernetes", ">=18.0.0", True),
            ],
        }
        
        # System tool dependencies by transfer method
        self.transfer_system_deps = {
            TransferMethod.RSYNC: [
                ("rsync", "rsync", None, True),
            ],
            TransferMethod.SSH_SCP: [
                ("ssh", "ssh", None, False),  # Optional, paramiko can handle
            ],
            TransferMethod.SSH_SFTP: [
                ("ssh", "ssh", None, False),  # Optional, paramiko can handle
            ],
        }
        
        # Cloud CLI dependencies
        self.cloud_cli_deps = {
            "aws": [
                ("aws", "aws-cli", ">=2.0.0", False),
            ],
            "gcp": [
                ("gcloud", "google-cloud-sdk", None, False),
                ("gsutil", "google-cloud-sdk", None, False),
            ],
            "azure": [
                ("az", "azure-cli", ">=2.0.0", False),
            ],
        }
        
        # Database client dependencies
        self.database_client_deps = {
            DatabaseType.MYSQL: [
                ("mysql", "mysql-client", None, False),
                ("mysqldump", "mysql-client", None, False),
            ],
            DatabaseType.POSTGRESQL: [
                ("psql", "postgresql-client", None, False),
                ("pg_dump", "postgresql-client", None, False),
            ],
            DatabaseType.MONGODB: [
                ("mongodump", "mongodb-tools", None, False),
                ("mongorestore", "mongodb-tools", None, False),
            ],
            DatabaseType.REDIS: [
                ("redis-cli", "redis-tools", None, False),
            ],
        }
        
        # System type specific dependencies
        self.system_type_deps = {
            SystemType.WORDPRESS: [
                ("wp", "wp-cli", None, False, DependencyType.SYSTEM_TOOL),
            ],
            SystemType.DJANGO: [
                ("django", "Django", ">=3.0.0", False, DependencyType.PYTHON_PACKAGE),
            ],
            SystemType.DOCKER_CONTAINER: [
                ("docker", "docker", None, True, DependencyType.SYSTEM_TOOL),
            ],
            SystemType.KUBERNETES_POD: [
                ("kubectl", "kubectl", None, True, DependencyType.SYSTEM_TOOL),
            ],
        }
    
    async def validate_dependencies(self, config: MigrationConfig) -> List[DependencyCheck]:
        """
        Validate all dependencies required for the migration configuration.
        
        Args:
            config: Migration configuration
            
        Returns:
            List of dependency check results
        """
        checks = []
        
        # Core Python dependencies (always required)
        core_checks = await self._check_core_dependencies()
        checks.extend(core_checks)
        
        # Database dependencies
        db_checks = await self._check_database_dependencies(config)
        checks.extend(db_checks)
        
        # Transfer method dependencies
        transfer_checks = await self._check_transfer_dependencies(config.transfer)
        checks.extend(transfer_checks)
        
        # System type dependencies
        system_checks = await self._check_system_dependencies(config.source, config.destination)
        checks.extend(system_checks)
        
        # Cloud dependencies
        cloud_checks = await self._check_cloud_dependencies(config.source, config.destination)
        checks.extend(cloud_checks)
        
        # Performance layer dependencies (Go binary)
        if config.transfer.use_go_acceleration:
            go_checks = await self._check_go_dependencies()
            checks.extend(go_checks)
        
        return checks
    
    async def _check_core_dependencies(self) -> List[DependencyCheck]:
        """Check core Python dependencies always required"""
        core_deps = [
            ("click", "click", ">=8.0.0", True),
            ("rich", "rich", ">=12.0.0", True),
            ("pydantic", "pydantic", ">=2.0.0", True),
            ("fastapi", "fastapi", ">=0.100.0", True),
            ("uvicorn", "uvicorn", ">=0.20.0", True),
            ("aiofiles", "aiofiles", ">=22.0.0", True),
            ("httpx", "httpx", ">=0.24.0", True),
            ("python-multipart", "multipart", ">=0.0.6", True),
            ("pyyaml", "yaml", ">=6.0", True),
            ("toml", "tomllib", None, False),  # Built-in Python 3.11+
        ]
        
        checks = []
        for pkg_name, import_name, min_version, required in core_deps:
            check = await self._check_python_package(
                pkg_name, import_name, min_version, required,
                "Core dependency for migration assistant"
            )
            checks.append(check)
        
        return checks
    
    async def _check_database_dependencies(self, config: MigrationConfig) -> List[DependencyCheck]:
        """Check database-specific dependencies"""
        checks = []
        
        # Collect all database types used
        db_types = set()
        if config.source.database:
            db_types.add(config.source.database.type)
        if config.destination.database:
            db_types.add(config.destination.database.type)
        
        # Check Python packages for each database type
        for db_type in db_types:
            if db_type in self.database_python_deps:
                for pkg_name, import_name, min_version, required in self.database_python_deps[db_type]:
                    check = await self._check_python_package(
                        pkg_name, import_name, min_version, required,
                        f"Required for {db_type.value} database connectivity"
                    )
                    checks.append(check)
            
            # Check database client tools
            if db_type in self.database_client_deps:
                for tool_name, package_name, min_version, required in self.database_client_deps[db_type]:
                    check = await self._check_system_tool(
                        tool_name, package_name, min_version, required,
                        f"Database client tool for {db_type.value}"
                    )
                    checks.append(check)
        
        return checks
    
    async def _check_transfer_dependencies(self, transfer_config: TransferConfig) -> List[DependencyCheck]:
        """Check transfer method dependencies"""
        checks = []
        
        method = transfer_config.method
        
        # Check Python packages
        if method in self.transfer_python_deps:
            for pkg_name, import_name, min_version, required in self.transfer_python_deps[method]:
                check = await self._check_python_package(
                    pkg_name, import_name, min_version, required,
                    f"Required for {method.value} file transfer"
                )
                checks.append(check)
        
        # Check system tools
        if method in self.transfer_system_deps:
            for tool_name, package_name, min_version, required in self.transfer_system_deps[method]:
                check = await self._check_system_tool(
                    tool_name, package_name, min_version, required,
                    f"System tool for {method.value} transfer"
                )
                checks.append(check)
        
        return checks
    
    async def _check_system_dependencies(
        self, source: SystemConfig, dest: SystemConfig
    ) -> List[DependencyCheck]:
        """Check system type specific dependencies"""
        checks = []
        
        # Check dependencies for both source and destination systems
        for system in [source, dest]:
            if system.type in self.system_type_deps:
                for dep_info in self.system_type_deps[system.type]:
                    if len(dep_info) == 5:
                        tool_name, package_name, min_version, required, dep_type = dep_info
                    else:
                        tool_name, package_name, min_version, required = dep_info
                        dep_type = DependencyType.SYSTEM_TOOL
                    
                    if dep_type == DependencyType.PYTHON_PACKAGE:
                        check = await self._check_python_package(
                            package_name, tool_name, min_version, required,
                            f"Required for {system.type.value} system"
                        )
                    else:
                        check = await self._check_system_tool(
                            tool_name, package_name, min_version, required,
                            f"Required for {system.type.value} system"
                        )
                    checks.append(check)
        
        return checks
    
    async def _check_cloud_dependencies(
        self, source: SystemConfig, dest: SystemConfig
    ) -> List[DependencyCheck]:
        """Check cloud provider dependencies"""
        checks = []
        
        # Collect cloud providers
        providers = set()
        for system in [source, dest]:
            if system.cloud_config:
                providers.add(system.cloud_config.provider.lower())
        
        # Check CLI tools for each provider
        for provider in providers:
            if provider in self.cloud_cli_deps:
                for tool_name, package_name, min_version, required in self.cloud_cli_deps[provider]:
                    check = await self._check_system_tool(
                        tool_name, package_name, min_version, required,
                        f"CLI tool for {provider.upper()} cloud operations"
                    )
                    checks.append(check)
        
        return checks
    
    async def _check_go_dependencies(self) -> List[DependencyCheck]:
        """Check Go binary dependencies for performance acceleration"""
        checks = []
        
        # Check if Go is installed (for building if needed)
        go_check = await self._check_system_tool(
            "go", "golang", ">=1.19", False,
            "Go compiler for building performance acceleration binary"
        )
        checks.append(go_check)
        
        # Check if migration-engine binary exists
        binary_paths = [
            "./bin/migration-engine",
            "./migration-engine",
            "migration-engine"
        ]
        
        binary_found = False
        for path in binary_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                binary_found = True
                break
        
        if binary_found:
            checks.append(DependencyCheck(
                name="migration-engine",
                type=DependencyType.SYSTEM_TOOL,
                status=DependencyStatus.AVAILABLE,
                required=False,
                description="Go binary for high-performance operations",
                install_command="Build from source or download pre-built binary"
            ))
        else:
            checks.append(DependencyCheck(
                name="migration-engine",
                type=DependencyType.SYSTEM_TOOL,
                status=DependencyStatus.MISSING,
                required=False,
                description="Go binary for high-performance operations",
                install_command="Build with 'make build-go' or download pre-built binary"
            ))
        
        return checks
    
    async def _check_python_package(
        self, package_name: str, import_name: str, min_version: Optional[str],
        required: bool, description: str
    ) -> DependencyCheck:
        """Check if a Python package is available and meets version requirements"""
        
        try:
            # Try to import the package
            module = importlib.import_module(import_name)
            
            # Get version if available
            current_version = None
            for attr in ['__version__', 'version', 'VERSION']:
                if hasattr(module, attr):
                    current_version = getattr(module, attr)
                    if callable(current_version):
                        current_version = current_version()
                    break
            
            # Check version requirement
            if min_version and current_version:
                # Remove ">=" prefix if present for comparison
                min_ver_clean = min_version.replace(">=", "").strip()
                if self._compare_versions(current_version, min_ver_clean) < 0:
                    return DependencyCheck(
                        name=package_name,
                        type=DependencyType.PYTHON_PACKAGE,
                        status=DependencyStatus.WRONG_VERSION,
                        required=required,
                        current_version=current_version,
                        required_version=min_version,
                        install_command=f"pip install '{package_name}{min_version}'",
                        description=description
                    )
            
            return DependencyCheck(
                name=package_name,
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.AVAILABLE,
                required=required,
                current_version=current_version,
                required_version=min_version,
                description=description
            )
            
        except ImportError:
            return DependencyCheck(
                name=package_name,
                type=DependencyType.PYTHON_PACKAGE,
                status=DependencyStatus.MISSING,
                required=required,
                required_version=min_version,
                install_command=f"pip install {package_name}",
                description=description
            )
    
    async def _check_system_tool(
        self, tool_name: str, package_name: str, min_version: Optional[str],
        required: bool, description: str
    ) -> DependencyCheck:
        """Check if a system tool is available"""
        
        # Check if tool is in PATH
        tool_path = shutil.which(tool_name)
        
        if not tool_path:
            return DependencyCheck(
                name=tool_name,
                type=DependencyType.SYSTEM_TOOL,
                status=DependencyStatus.MISSING,
                required=required,
                required_version=min_version,
                install_command=self._get_install_command(package_name),
                description=description
            )
        
        # Try to get version
        current_version = await self._get_tool_version(tool_name)
        
        # Check version requirement
        if min_version and current_version:
            # Remove ">=" prefix if present for comparison
            min_ver_clean = min_version.replace(">=", "").strip()
            if self._compare_versions(current_version, min_ver_clean) < 0:
                return DependencyCheck(
                    name=tool_name,
                    type=DependencyType.SYSTEM_TOOL,
                    status=DependencyStatus.WRONG_VERSION,
                    required=required,
                    current_version=current_version,
                    required_version=min_version,
                    install_command=self._get_install_command(package_name),
                    description=description
                )
        
        return DependencyCheck(
            name=tool_name,
            type=DependencyType.SYSTEM_TOOL,
            status=DependencyStatus.AVAILABLE,
            required=required,
            current_version=current_version,
            required_version=min_version,
            description=description
        )
    
    async def _get_tool_version(self, tool_name: str) -> Optional[str]:
        """Get version of a system tool"""
        version_commands = [
            [tool_name, "--version"],
            [tool_name, "-version"],
            [tool_name, "version"],
            [tool_name, "-V"],
        ]
        
        for cmd in version_commands:
            try:
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    output = stdout.decode().strip()
                    # Extract version number (simple regex would be better)
                    import re
                    version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', output)
                    if version_match:
                        return version_match.group(1)
                    
            except Exception:
                continue
        
        return None
    
    def _get_install_command(self, package_name: str) -> str:
        """Get installation command for a package based on the operating system"""
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            return f"brew install {package_name}"
        elif system == "linux":
            # Try to detect Linux distribution
            if os.path.exists("/etc/debian_version"):
                return f"sudo apt-get install {package_name}"
            elif os.path.exists("/etc/redhat-release"):
                return f"sudo yum install {package_name}"
            elif os.path.exists("/etc/arch-release"):
                return f"sudo pacman -S {package_name}"
            else:
                return f"Install {package_name} using your system package manager"
        elif system == "windows":
            return f"Install {package_name} using chocolatey: choco install {package_name}"
        else:
            return f"Install {package_name} using your system package manager"
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        Returns: -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        try:
            # Simple version comparison (could use packaging.version for better handling)
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 < v2:
                    return -1
                elif v1 > v2:
                    return 1
            
            return 0
            
        except ValueError:
            # If version parsing fails, assume they're equal
            return 0
    
    def get_missing_dependencies(self, checks: List[DependencyCheck]) -> List[DependencyCheck]:
        """Get list of missing required dependencies"""
        return [
            check for check in checks
            if check.required and check.status in [DependencyStatus.MISSING, DependencyStatus.WRONG_VERSION]
        ]
    
    def get_optional_dependencies(self, checks: List[DependencyCheck]) -> List[DependencyCheck]:
        """Get list of missing optional dependencies"""
        return [
            check for check in checks
            if not check.required and check.status in [DependencyStatus.MISSING, DependencyStatus.WRONG_VERSION]
        ]
    
    def generate_install_script(self, checks: List[DependencyCheck]) -> str:
        """Generate installation script for missing dependencies"""
        missing_deps = self.get_missing_dependencies(checks)
        
        if not missing_deps:
            return "# All required dependencies are satisfied"
        
        script_lines = [
            "#!/bin/bash",
            "# Auto-generated dependency installation script",
            "set -e",
            "",
            "echo 'Installing missing dependencies...'",
            ""
        ]
        
        # Group by type
        python_packages = [dep for dep in missing_deps if dep.type == DependencyType.PYTHON_PACKAGE]
        system_tools = [dep for dep in missing_deps if dep.type == DependencyType.SYSTEM_TOOL]
        
        # Python packages
        if python_packages:
            script_lines.append("# Python packages")
            pip_packages = []
            for dep in python_packages:
                if dep.required_version:
                    pip_packages.append(f"{dep.name}{dep.required_version}")
                else:
                    pip_packages.append(dep.name)
            
            script_lines.append(f"pip install {' '.join(pip_packages)}")
            script_lines.append("")
        
        # System tools
        if system_tools:
            script_lines.append("# System tools")
            for dep in system_tools:
                if dep.install_command:
                    script_lines.append(dep.install_command)
            script_lines.append("")
        
        script_lines.append("echo 'Dependency installation complete!'")
        
        return "\n".join(script_lines)