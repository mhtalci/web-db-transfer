"""
Backup strategies for different types of data and systems.

This module defines various backup strategies for files, databases,
configurations, and cloud resources.
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from migration_assistant.core.exceptions import BackupError
from migration_assistant.models.session import BackupInfo, BackupType
from migration_assistant.models.config import SystemConfig, DatabaseConfig


class BackupStrategy(ABC):
    """Abstract base class for backup strategies."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.temp_dir = None
    
    @abstractmethod
    async def create_backup(
        self,
        backup_id: str,
        destination: str,
        options: Optional[Dict[str, Any]] = None
    ) -> BackupInfo:
        """Create a backup and return backup information."""
        pass
    
    @abstractmethod
    async def verify_backup(self, backup_info: BackupInfo) -> bool:
        """Verify backup integrity."""
        pass
    
    @abstractmethod
    async def restore_backup(
        self,
        backup_info: BackupInfo,
        restore_location: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Restore from backup."""
        pass
    
    def _create_temp_dir(self) -> str:
        """Create a temporary directory for backup operations."""
        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp(prefix="migration_backup_")
        return self.temp_dir
    
    def _cleanup_temp_dir(self):
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        return os.path.getsize(file_path)


class FileBackupStrategy(BackupStrategy):
    """Strategy for backing up files and directories."""
    
    async def create_backup(
        self,
        backup_id: str,
        destination: str,
        options: Optional[Dict[str, Any]] = None
    ) -> BackupInfo:
        """Create a file backup using tar compression."""
        options = options or {}
        source_paths = options.get("source_paths", [])
        compression = options.get("compression", "gzip")
        exclude_patterns = options.get("exclude_patterns", [])
        
        if not source_paths:
            raise BackupError("No source paths specified for file backup")
        
        try:
            # Create backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"files_backup_{backup_id}_{timestamp}.tar.gz"
            backup_path = os.path.join(destination, backup_filename)
            
            # Ensure destination directory exists
            os.makedirs(destination, exist_ok=True)
            
            # Create tar archive
            compression_mode = "w:gz" if compression == "gzip" else "w"
            with tarfile.open(backup_path, compression_mode) as tar:
                for source_path in source_paths:
                    if os.path.exists(source_path):
                        # Add exclusion filter
                        def exclude_filter(tarinfo):
                            for pattern in exclude_patterns:
                                if pattern in tarinfo.name:
                                    return None
                            return tarinfo
                        
                        tar.add(
                            source_path,
                            arcname=os.path.basename(source_path),
                            filter=exclude_filter if exclude_patterns else None
                        )
            
            # Calculate checksum and size
            checksum = self._calculate_checksum(backup_path)
            size = self._get_file_size(backup_path)
            
            # Create backup info
            backup_info = BackupInfo(
                id=backup_id,
                type=BackupType.FULL,
                source_system=self.config.type,
                location=backup_path,
                size=size,
                checksum=checksum,
                compression_used=compression == "gzip",
                metadata={
                    "source_paths": source_paths,
                    "compression": compression,
                    "exclude_patterns": exclude_patterns,
                    "backup_type": "file_archive"
                }
            )
            
            return backup_info
            
        except Exception as e:
            raise BackupError(f"Failed to create file backup: {str(e)}")
    
    async def verify_backup(self, backup_info: BackupInfo) -> bool:
        """Verify file backup integrity."""
        try:
            if not os.path.exists(backup_info.location):
                return False
            
            # Verify checksum
            current_checksum = self._calculate_checksum(backup_info.location)
            if current_checksum != backup_info.checksum:
                return False
            
            # Verify tar archive can be opened
            with tarfile.open(backup_info.location, "r") as tar:
                # Try to list contents
                tar.getnames()
            
            return True
            
        except Exception:
            return False
    
    async def restore_backup(
        self,
        backup_info: BackupInfo,
        restore_location: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Restore files from backup."""
        try:
            if not await self.verify_backup(backup_info):
                raise BackupError("Backup verification failed before restore")
            
            # Ensure restore location exists
            os.makedirs(restore_location, exist_ok=True)
            
            # Extract tar archive
            with tarfile.open(backup_info.location, "r") as tar:
                tar.extractall(path=restore_location)
            
            return True
            
        except Exception as e:
            raise BackupError(f"Failed to restore file backup: {str(e)}")


class DatabaseBackupStrategy(BackupStrategy):
    """Strategy for backing up databases."""
    
    def __init__(self, config: SystemConfig, db_config: DatabaseConfig):
        super().__init__(config)
        self.db_config = db_config
    
    async def create_backup(
        self,
        backup_id: str,
        destination: str,
        options: Optional[Dict[str, Any]] = None
    ) -> BackupInfo:
        """Create a database backup using appropriate dump tools."""
        options = options or {}
        
        try:
            # Create backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"db_backup_{backup_id}_{timestamp}.sql"
            backup_path = os.path.join(destination, backup_filename)
            
            # Ensure destination directory exists
            os.makedirs(destination, exist_ok=True)
            
            # Create database dump based on database type
            if self.db_config.type.lower() in ["mysql", "mariadb"]:
                await self._create_mysql_backup(backup_path, options)
            elif self.db_config.type.lower() == "postgresql":
                await self._create_postgresql_backup(backup_path, options)
            elif self.db_config.type.lower() == "sqlite":
                await self._create_sqlite_backup(backup_path, options)
            elif self.db_config.type.lower() == "mongodb":
                backup_filename = f"db_backup_{backup_id}_{timestamp}.archive"
                backup_path = os.path.join(destination, backup_filename)
                await self._create_mongodb_backup(backup_path, options)
            else:
                raise BackupError(f"Unsupported database type: {self.db_config.type}")
            
            # Calculate checksum and size
            checksum = self._calculate_checksum(backup_path)
            size = self._get_file_size(backup_path)
            
            # Create backup info
            backup_info = BackupInfo(
                id=backup_id,
                type=BackupType.FULL,
                source_system=self.config.type,
                location=backup_path,
                size=size,
                checksum=checksum,
                metadata={
                    "database_type": self.db_config.type,
                    "database_name": self.db_config.name,
                    "backup_type": "database_dump"
                }
            )
            
            return backup_info
            
        except Exception as e:
            raise BackupError(f"Failed to create database backup: {str(e)}")
    
    async def _create_mysql_backup(self, backup_path: str, options: Dict[str, Any]):
        """Create MySQL backup using mysqldump."""
        cmd = [
            "mysqldump",
            f"--host={self.db_config.host}",
            f"--port={self.db_config.port or 3306}",
            f"--user={self.db_config.username}",
            f"--password={self.db_config.password}",
            "--single-transaction",
            "--routines",
            "--triggers",
            self.db_config.name
        ]
        
        # Add additional options
        if options.get("no_data", False):
            cmd.append("--no-data")
        if options.get("add_drop_table", True):
            cmd.append("--add-drop-table")
        
        with open(backup_path, "w") as f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=f,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"mysqldump failed: {stderr.decode()}")
    
    async def _create_postgresql_backup(self, backup_path: str, options: Dict[str, Any]):
        """Create PostgreSQL backup using pg_dump."""
        env = os.environ.copy()
        env["PGPASSWORD"] = self.db_config.password
        
        cmd = [
            "pg_dump",
            f"--host={self.db_config.host}",
            f"--port={self.db_config.port or 5432}",
            f"--username={self.db_config.username}",
            "--verbose",
            "--clean",
            "--if-exists",
            self.db_config.name
        ]
        
        # Add additional options
        if options.get("no_data", False):
            cmd.append("--schema-only")
        if options.get("format"):
            cmd.extend(["--format", options["format"]])
        
        with open(backup_path, "w") as f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=f,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"pg_dump failed: {stderr.decode()}")
    
    async def _create_sqlite_backup(self, backup_path: str, options: Dict[str, Any]):
        """Create SQLite backup using .dump command."""
        cmd = [
            "sqlite3",
            self.db_config.name,
            ".dump"
        ]
        
        with open(backup_path, "w") as f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=f,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"sqlite3 dump failed: {stderr.decode()}")
    
    async def _create_mongodb_backup(self, backup_path: str, options: Dict[str, Any]):
        """Create MongoDB backup using mongodump."""
        cmd = [
            "mongodump",
            "--host", f"{self.db_config.host}:{self.db_config.port or 27017}",
            "--db", self.db_config.name,
            "--archive", backup_path
        ]
        
        if self.db_config.username:
            cmd.extend(["--username", self.db_config.username])
        if self.db_config.password:
            cmd.extend(["--password", self.db_config.password])
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise BackupError(f"mongodump failed: {stderr.decode()}")
    
    async def verify_backup(self, backup_info: BackupInfo) -> bool:
        """Verify database backup integrity."""
        try:
            if not os.path.exists(backup_info.location):
                return False
            
            # Verify checksum
            current_checksum = self._calculate_checksum(backup_info.location)
            if current_checksum != backup_info.checksum:
                return False
            
            # Basic file validation - check if file is not empty and readable
            if os.path.getsize(backup_info.location) == 0:
                return False
            
            # For SQL dumps, check if file contains SQL statements
            db_type = backup_info.metadata.get("database_type", "").lower()
            if db_type in ["mysql", "postgresql", "sqlite"]:
                with open(backup_info.location, "r") as f:
                    content = f.read(1000)  # Read first 1000 chars
                    if not any(keyword in content.upper() for keyword in ["CREATE", "INSERT", "DROP"]):
                        return False
            
            return True
            
        except Exception:
            return False
    
    async def restore_backup(
        self,
        backup_info: BackupInfo,
        restore_location: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Restore database from backup."""
        try:
            if not await self.verify_backup(backup_info):
                raise BackupError("Backup verification failed before restore")
            
            db_type = backup_info.metadata.get("database_type", "").lower()
            
            if db_type in ["mysql", "mariadb"]:
                await self._restore_mysql_backup(backup_info, options)
            elif db_type == "postgresql":
                await self._restore_postgresql_backup(backup_info, options)
            elif db_type == "sqlite":
                await self._restore_sqlite_backup(backup_info, restore_location, options)
            elif db_type == "mongodb":
                await self._restore_mongodb_backup(backup_info, options)
            else:
                raise BackupError(f"Unsupported database type for restore: {db_type}")
            
            return True
            
        except Exception as e:
            raise BackupError(f"Failed to restore database backup: {str(e)}")
    
    async def _restore_mysql_backup(self, backup_info: BackupInfo, options: Optional[Dict[str, Any]]):
        """Restore MySQL backup using mysql client."""
        cmd = [
            "mysql",
            f"--host={self.db_config.host}",
            f"--port={self.db_config.port or 3306}",
            f"--user={self.db_config.username}",
            f"--password={self.db_config.password}",
            self.db_config.name
        ]
        
        with open(backup_info.location, "r") as f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=f,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"mysql restore failed: {stderr.decode()}")
    
    async def _restore_postgresql_backup(self, backup_info: BackupInfo, options: Optional[Dict[str, Any]]):
        """Restore PostgreSQL backup using psql."""
        env = os.environ.copy()
        env["PGPASSWORD"] = self.db_config.password
        
        cmd = [
            "psql",
            f"--host={self.db_config.host}",
            f"--port={self.db_config.port or 5432}",
            f"--username={self.db_config.username}",
            "--dbname", self.db_config.name
        ]
        
        with open(backup_info.location, "r") as f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=f,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"psql restore failed: {stderr.decode()}")
    
    async def _restore_sqlite_backup(self, backup_info: BackupInfo, restore_location: str, options: Optional[Dict[str, Any]]):
        """Restore SQLite backup."""
        # For SQLite, we restore to a new database file
        db_path = os.path.join(restore_location, f"restored_{os.path.basename(self.db_config.name)}")
        
        cmd = [
            "sqlite3",
            db_path
        ]
        
        with open(backup_info.location, "r") as f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=f,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"sqlite3 restore failed: {stderr.decode()}")
    
    async def _restore_mongodb_backup(self, backup_info: BackupInfo, options: Optional[Dict[str, Any]]):
        """Restore MongoDB backup using mongorestore."""
        cmd = [
            "mongorestore",
            "--host", f"{self.db_config.host}:{self.db_config.port or 27017}",
            "--archive", backup_info.location
        ]
        
        if self.db_config.username:
            cmd.extend(["--username", self.db_config.username])
        if self.db_config.password:
            cmd.extend(["--password", self.db_config.password])
        
        # Add drop option to replace existing data
        if options and options.get("drop_existing", False):
            cmd.append("--drop")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise BackupError(f"mongorestore failed: {stderr.decode()}")


class ConfigBackupStrategy(BackupStrategy):
    """Strategy for backing up configuration files and settings."""
    
    async def create_backup(
        self,
        backup_id: str,
        destination: str,
        options: Optional[Dict[str, Any]] = None
    ) -> BackupInfo:
        """Create a configuration backup."""
        options = options or {}
        config_files = options.get("config_files", [])
        config_data = options.get("config_data", {})
        
        try:
            # Create backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_backup_{backup_id}_{timestamp}.json"
            backup_path = os.path.join(destination, backup_filename)
            
            # Ensure destination directory exists
            os.makedirs(destination, exist_ok=True)
            
            # Collect configuration data
            backup_data = {
                "backup_id": backup_id,
                "timestamp": timestamp,
                "system_config": self.config.dict(),
                "config_data": config_data,
                "config_files": {}
            }
            
            # Read configuration files
            for config_file in config_files:
                if os.path.exists(config_file):
                    try:
                        with open(config_file, "r") as f:
                            backup_data["config_files"][config_file] = f.read()
                    except Exception as e:
                        backup_data["config_files"][config_file] = f"Error reading file: {str(e)}"
            
            # Write backup data to JSON file
            with open(backup_path, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Calculate checksum and size
            checksum = self._calculate_checksum(backup_path)
            size = self._get_file_size(backup_path)
            
            # Create backup info
            backup_info = BackupInfo(
                id=backup_id,
                type=BackupType.FULL,
                source_system=self.config.type,
                location=backup_path,
                size=size,
                checksum=checksum,
                metadata={
                    "config_files": config_files,
                    "backup_type": "configuration"
                }
            )
            
            return backup_info
            
        except Exception as e:
            raise BackupError(f"Failed to create configuration backup: {str(e)}")
    
    async def verify_backup(self, backup_info: BackupInfo) -> bool:
        """Verify configuration backup integrity."""
        try:
            if not os.path.exists(backup_info.location):
                return False
            
            # Verify checksum
            current_checksum = self._calculate_checksum(backup_info.location)
            if current_checksum != backup_info.checksum:
                return False
            
            # Verify JSON structure
            with open(backup_info.location, "r") as f:
                data = json.load(f)
                required_keys = ["backup_id", "timestamp", "system_config"]
                if not all(key in data for key in required_keys):
                    return False
            
            return True
            
        except Exception:
            return False
    
    async def restore_backup(
        self,
        backup_info: BackupInfo,
        restore_location: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Restore configuration from backup."""
        try:
            if not await self.verify_backup(backup_info):
                raise BackupError("Backup verification failed before restore")
            
            # Load backup data
            with open(backup_info.location, "r") as f:
                backup_data = json.load(f)
            
            # Restore configuration files
            config_files = backup_data.get("config_files", {})
            for file_path, content in config_files.items():
                if not content.startswith("Error reading file:"):
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    # Write file content
                    with open(file_path, "w") as f:
                        f.write(content)
            
            return True
            
        except Exception as e:
            raise BackupError(f"Failed to restore configuration backup: {str(e)}")


class CloudBackupStrategy(BackupStrategy):
    """Strategy for backing up cloud resources and configurations."""
    
    async def create_backup(
        self,
        backup_id: str,
        destination: str,
        options: Optional[Dict[str, Any]] = None
    ) -> BackupInfo:
        """Create a cloud resource backup."""
        options = options or {}
        
        try:
            # Create backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"cloud_backup_{backup_id}_{timestamp}.json"
            backup_path = os.path.join(destination, backup_filename)
            
            # Ensure destination directory exists
            os.makedirs(destination, exist_ok=True)
            
            # Collect cloud resource information
            backup_data = {
                "backup_id": backup_id,
                "timestamp": timestamp,
                "cloud_provider": self.config.cloud_config.provider if self.config.cloud_config else "unknown",
                "resources": options.get("resources", {}),
                "configurations": options.get("configurations", {}),
                "metadata": options.get("metadata", {})
            }
            
            # Write backup data to JSON file
            with open(backup_path, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Calculate checksum and size
            checksum = self._calculate_checksum(backup_path)
            size = self._get_file_size(backup_path)
            
            # Create backup info
            backup_info = BackupInfo(
                id=backup_id,
                type=BackupType.SNAPSHOT,
                source_system=self.config.type,
                location=backup_path,
                size=size,
                checksum=checksum,
                metadata={
                    "cloud_provider": backup_data["cloud_provider"],
                    "backup_type": "cloud_resources"
                }
            )
            
            return backup_info
            
        except Exception as e:
            raise BackupError(f"Failed to create cloud backup: {str(e)}")
    
    async def verify_backup(self, backup_info: BackupInfo) -> bool:
        """Verify cloud backup integrity."""
        try:
            if not os.path.exists(backup_info.location):
                return False
            
            # Verify checksum
            current_checksum = self._calculate_checksum(backup_info.location)
            if current_checksum != backup_info.checksum:
                return False
            
            # Verify JSON structure
            with open(backup_info.location, "r") as f:
                data = json.load(f)
                required_keys = ["backup_id", "timestamp", "cloud_provider"]
                if not all(key in data for key in required_keys):
                    return False
            
            return True
            
        except Exception:
            return False
    
    async def restore_backup(
        self,
        backup_info: BackupInfo,
        restore_location: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Restore cloud resources from backup."""
        try:
            if not await self.verify_backup(backup_info):
                raise BackupError("Backup verification failed before restore")
            
            # Load backup data
            with open(backup_info.location, "r") as f:
                backup_data = json.load(f)
            
            # Note: Actual cloud resource restoration would require
            # cloud provider-specific implementations using their APIs
            # This is a placeholder for the restoration logic
            
            return True
            
        except Exception as e:
            raise BackupError(f"Failed to restore cloud backup: {str(e)}")