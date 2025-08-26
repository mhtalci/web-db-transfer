"""
Backup manager for creating and managing backups.

This module provides the main BackupManager class that orchestrates
backup operations using different strategies and storage management.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from migration_assistant.backup.storage import BackupStorage, RetentionPolicy
import os
from migration_assistant.backup.strategies import (
    BackupStrategy,
    CloudBackupStrategy,
    ConfigBackupStrategy,
    DatabaseBackupStrategy,
    FileBackupStrategy,
)
from migration_assistant.core.exceptions import BackupError
from migration_assistant.models.config import DatabaseConfig, MigrationConfig, SystemConfig
from migration_assistant.models.session import BackupInfo, BackupType, LogEntry, LogLevel


class BackupManager:
    """Main backup manager class for creating and managing backups."""
    
    def __init__(
        self,
        storage: BackupStorage,
        retention_policy: Optional[RetentionPolicy] = None
    ):
        self.storage = storage
        self.retention_policy = retention_policy or RetentionPolicy()
        self._active_backups: Dict[str, BackupInfo] = {}
        self._backup_logs: List[LogEntry] = []
    
    def _log(self, level: LogLevel, message: str, backup_id: Optional[str] = None, **kwargs):
        """Add a log entry."""
        log_entry = LogEntry(
            level=level,
            message=message,
            component="BackupManager",
            details={"backup_id": backup_id, **kwargs}
        )
        self._backup_logs.append(log_entry)
    
    def _create_backup_strategy(
        self,
        system_config: SystemConfig,
        backup_type: str,
        db_config: Optional[DatabaseConfig] = None
    ) -> BackupStrategy:
        """Create appropriate backup strategy based on type."""
        if backup_type == "files":
            return FileBackupStrategy(system_config)
        elif backup_type == "database":
            if not db_config:
                raise BackupError("Database configuration required for database backup")
            return DatabaseBackupStrategy(system_config, db_config)
        elif backup_type == "config":
            return ConfigBackupStrategy(system_config)
        elif backup_type == "cloud":
            return CloudBackupStrategy(system_config)
        else:
            raise BackupError(f"Unsupported backup type: {backup_type}")
    
    async def create_backup(
        self,
        system_config: SystemConfig,
        backup_type: str,
        options: Optional[Dict[str, Any]] = None,
        db_config: Optional[DatabaseConfig] = None
    ) -> BackupInfo:
        """Create a backup of the specified type."""
        backup_id = str(uuid.uuid4())
        options = options or {}
        
        try:
            self._log(LogLevel.INFO, f"Starting {backup_type} backup", backup_id)
            
            # Create backup strategy
            strategy = self._create_backup_strategy(system_config, backup_type, db_config)
            
            # Get storage location
            storage_path = self.storage.get_backup_path(backup_type, system_config.type)
            
            # Create backup
            backup_info = await strategy.create_backup(backup_id, storage_path, options)
            
            # Store backup in storage system
            final_location = await self.storage.store_backup(backup_info, backup_info.location)
            backup_info.location = final_location
            
            # Track active backup
            self._active_backups[backup_id] = backup_info
            
            self._log(LogLevel.INFO, f"Backup created successfully", backup_id, 
                     location=backup_info.location, size=backup_info.size)
            
            return backup_info
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Backup creation failed: {str(e)}", backup_id)
            raise BackupError(f"Failed to create {backup_type} backup: {str(e)}")
    
    async def create_full_system_backup(
        self,
        migration_config: MigrationConfig,
        backup_options: Optional[Dict[str, Any]] = None
    ) -> List[BackupInfo]:
        """Create a complete system backup including files, database, and config."""
        backup_options = backup_options or {}
        backups = []
        
        try:
            self._log(LogLevel.INFO, "Starting full system backup")
            
            # Create file backup if source paths specified
            if backup_options.get("backup_files", True):
                file_options = {
                    "source_paths": backup_options.get("file_paths", []),
                    "compression": backup_options.get("compression", "gzip"),
                    "exclude_patterns": backup_options.get("exclude_patterns", [])
                }
                
                if file_options["source_paths"]:
                    file_backup = await self.create_backup(
                        migration_config.source,
                        "files",
                        file_options
                    )
                    backups.append(file_backup)
            
            # Create database backup if database config exists
            if (backup_options.get("backup_database", True) and 
                migration_config.source.database):
                
                db_options = {
                    "no_data": backup_options.get("schema_only", False),
                    "add_drop_table": backup_options.get("add_drop_table", True)
                }
                
                db_backup = await self.create_backup(
                    migration_config.source,
                    "database",
                    db_options,
                    migration_config.source.database
                )
                backups.append(db_backup)
            
            # Create configuration backup
            if backup_options.get("backup_config", True):
                config_options = {
                    "config_files": backup_options.get("config_files", []),
                    "config_data": {
                        "migration_config": migration_config.dict(),
                        "backup_timestamp": datetime.utcnow().isoformat()
                    }
                }
                
                config_backup = await self.create_backup(
                    migration_config.source,
                    "config",
                    config_options
                )
                backups.append(config_backup)
            
            # Create cloud backup if cloud config exists
            if (backup_options.get("backup_cloud", False) and 
                migration_config.source.cloud_config):
                
                cloud_options = {
                    "resources": backup_options.get("cloud_resources", {}),
                    "configurations": backup_options.get("cloud_configurations", {}),
                    "metadata": {"backup_scope": "full_system"}
                }
                
                cloud_backup = await self.create_backup(
                    migration_config.source,
                    "cloud",
                    cloud_options
                )
                backups.append(cloud_backup)
            
            self._log(LogLevel.INFO, f"Full system backup completed with {len(backups)} backups")
            
            return backups
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Full system backup failed: {str(e)}")
            raise BackupError(f"Failed to create full system backup: {str(e)}")
    
    async def verify_backup(self, backup_info: BackupInfo) -> bool:
        """Verify backup integrity."""
        try:
            self._log(LogLevel.INFO, "Verifying backup", backup_info.id)
            
            # Determine backup type from metadata
            backup_type = backup_info.metadata.get("backup_type", "unknown")
            
            # Create appropriate strategy for verification
            if backup_type == "file_archive":
                strategy = FileBackupStrategy(SystemConfig(type=backup_info.source_system, host=""))
            elif backup_type == "database_dump":
                db_type = backup_info.metadata.get("database_type", "mysql")
                db_config = DatabaseConfig(type=db_type, name="", host="", username="", password="")
                strategy = DatabaseBackupStrategy(
                    SystemConfig(type=backup_info.source_system, host=""),
                    db_config
                )
            elif backup_type == "configuration":
                strategy = ConfigBackupStrategy(SystemConfig(type=backup_info.source_system, host=""))
            elif backup_type == "cloud_resources":
                strategy = CloudBackupStrategy(SystemConfig(type=backup_info.source_system, host=""))
            else:
                self._log(LogLevel.WARNING, f"Unknown backup type for verification: {backup_type}", backup_info.id)
                return False
            
            # Verify backup
            is_valid = await strategy.verify_backup(backup_info)
            
            if is_valid:
                backup_info.verified = True
                backup_info.verification_date = datetime.utcnow()
                self._log(LogLevel.INFO, "Backup verification successful", backup_info.id)
            else:
                self._log(LogLevel.ERROR, "Backup verification failed", backup_info.id)
            
            return is_valid
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Backup verification error: {str(e)}", backup_info.id)
            return False
    
    async def verify_all_backups(self, backups: List[BackupInfo]) -> Dict[str, bool]:
        """Verify multiple backups concurrently."""
        verification_tasks = [
            self.verify_backup(backup) for backup in backups
        ]
        
        results = await asyncio.gather(*verification_tasks, return_exceptions=True)
        
        verification_results = {}
        for backup, result in zip(backups, results):
            if isinstance(result, Exception):
                verification_results[backup.id] = False
                self._log(LogLevel.ERROR, f"Backup verification exception: {str(result)}", backup.id)
            else:
                verification_results[backup.id] = result
        
        return verification_results
    
    async def list_backups(
        self,
        system_type: Optional[str] = None,
        backup_type: Optional[str] = None
    ) -> List[str]:
        """List available backups."""
        try:
            return await self.storage.list_backups(backup_type, system_type)
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to list backups: {str(e)}")
            raise BackupError(f"Failed to list backups: {str(e)}")
    
    async def get_backup_info(self, backup_id: str) -> Optional[BackupInfo]:
        """Get backup information by ID."""
        return self._active_backups.get(backup_id)
    
    async def delete_backup(self, backup_info: BackupInfo) -> bool:
        """Delete a backup."""
        try:
            self._log(LogLevel.INFO, "Deleting backup", backup_info.id)
            
            success = await self.storage.delete_backup(backup_info)
            
            if success:
                # Remove from active backups
                if backup_info.id in self._active_backups:
                    del self._active_backups[backup_info.id]
                
                self._log(LogLevel.INFO, "Backup deleted successfully", backup_info.id)
            else:
                self._log(LogLevel.WARNING, "Backup file not found for deletion", backup_info.id)
            
            return success
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to delete backup: {str(e)}", backup_info.id)
            raise BackupError(f"Failed to delete backup: {str(e)}")
    
    async def cleanup_expired_backups(self, all_backups: List[BackupInfo]) -> List[str]:
        """Clean up expired backups based on retention policy."""
        try:
            self._log(LogLevel.INFO, f"Starting cleanup of {len(all_backups)} backups")
            
            deleted_backups = await self.storage.cleanup_expired_backups(all_backups)
            
            # Remove deleted backups from active tracking
            for backup_location in deleted_backups:
                for backup_id, backup_info in list(self._active_backups.items()):
                    if backup_info.location == backup_location:
                        del self._active_backups[backup_id]
                        break
            
            self._log(LogLevel.INFO, f"Cleanup completed, deleted {len(deleted_backups)} backups")
            
            return deleted_backups
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Backup cleanup failed: {str(e)}")
            raise BackupError(f"Failed to cleanup expired backups: {str(e)}")
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get backup storage statistics."""
        try:
            return await self.storage.get_storage_stats()
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to get storage stats: {str(e)}")
            raise BackupError(f"Failed to get storage stats: {str(e)}")
    
    async def verify_storage_integrity(self) -> Dict[str, Any]:
        """Verify backup storage integrity."""
        try:
            self._log(LogLevel.INFO, "Starting storage integrity verification")
            
            integrity_report = await self.storage.verify_storage_integrity()
            
            if integrity_report["storage_healthy"]:
                self._log(LogLevel.INFO, "Storage integrity verification passed")
            else:
                self._log(LogLevel.WARNING, "Storage integrity issues detected",
                         corrupted=len(integrity_report["corrupted_files"]),
                         missing=len(integrity_report["missing_files"]),
                         permission_issues=len(integrity_report["permission_issues"]))
            
            return integrity_report
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Storage integrity verification failed: {str(e)}")
            raise BackupError(f"Failed to verify storage integrity: {str(e)}")
    
    async def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """Clean up temporary backup files."""
        try:
            deleted_count = await self.storage.cleanup_temp_files(max_age_hours)
            self._log(LogLevel.INFO, f"Cleaned up {deleted_count} temporary files")
            return deleted_count
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to cleanup temp files: {str(e)}")
            raise BackupError(f"Failed to cleanup temp files: {str(e)}")
    
    def get_logs(self, backup_id: Optional[str] = None) -> List[LogEntry]:
        """Get backup operation logs."""
        if backup_id:
            return [
                log for log in self._backup_logs 
                if log.details.get("backup_id") == backup_id
            ]
        return self._backup_logs.copy()
    
    def clear_logs(self):
        """Clear backup operation logs."""
        self._backup_logs.clear()
    
    async def estimate_backup_size(
        self,
        system_config: SystemConfig,
        backup_type: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Estimate backup size and duration."""
        options = options or {}
        
        try:
            estimate = {
                "estimated_size": 0,
                "estimated_duration": 0,
                "compression_ratio": 0.7,  # Assume 30% compression
                "details": {}
            }
            
            if backup_type == "files":
                source_paths = options.get("source_paths", [])
                total_size = 0
                file_count = 0
                
                for path in source_paths:
                    if os.path.exists(path):
                        if os.path.isfile(path):
                            total_size += os.path.getsize(path)
                            file_count += 1
                        elif os.path.isdir(path):
                            for root, dirs, files in os.walk(path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    try:
                                        total_size += os.path.getsize(file_path)
                                        file_count += 1
                                    except (OSError, IOError):
                                        continue
                
                # Apply compression ratio
                if options.get("compression", "gzip") == "gzip":
                    estimated_size = int(total_size * estimate["compression_ratio"])
                else:
                    estimated_size = total_size
                
                # Estimate duration (rough calculation: 50MB/s processing speed)
                estimated_duration = max(1, total_size / (50 * 1024 * 1024))
                
                estimate.update({
                    "estimated_size": estimated_size,
                    "estimated_duration": estimated_duration,
                    "details": {
                        "file_count": file_count,
                        "raw_size": total_size,
                        "compression_used": options.get("compression", "gzip") == "gzip"
                    }
                })
            
            elif backup_type == "database":
                # Database size estimation would require connection to database
                # This is a simplified estimation
                estimate.update({
                    "estimated_size": 100 * 1024 * 1024,  # 100MB default
                    "estimated_duration": 30,  # 30 seconds default
                    "details": {
                        "note": "Database size estimation requires connection to database"
                    }
                })
            
            elif backup_type == "config":
                # Configuration backups are typically small
                estimate.update({
                    "estimated_size": 1024 * 1024,  # 1MB
                    "estimated_duration": 5,  # 5 seconds
                    "details": {
                        "config_files": len(options.get("config_files", []))
                    }
                })
            
            return estimate
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to estimate backup size: {str(e)}")
            raise BackupError(f"Failed to estimate backup size: {str(e)}")