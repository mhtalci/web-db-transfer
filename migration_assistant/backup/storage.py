"""
Backup storage management with retention policies.

This module handles backup storage locations, retention policies,
and cleanup operations for the backup system.
"""

import asyncio
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from migration_assistant.core.exceptions import BackupError
from migration_assistant.models.session import BackupInfo, BackupType


class RetentionPolicy:
    """Defines backup retention policies."""
    
    def __init__(
        self,
        max_backups: Optional[int] = None,
        max_age_days: Optional[int] = None,
        max_size_gb: Optional[float] = None,
        keep_daily: Optional[int] = None,
        keep_weekly: Optional[int] = None,
        keep_monthly: Optional[int] = None
    ):
        self.max_backups = max_backups
        self.max_age_days = max_age_days
        self.max_size_gb = max_size_gb
        self.keep_daily = keep_daily
        self.keep_weekly = keep_weekly
        self.keep_monthly = keep_monthly
    
    def should_retain(self, backup_info: BackupInfo, all_backups: List[BackupInfo]) -> bool:
        """Determine if a backup should be retained based on policy."""
        now = datetime.utcnow()
        backup_age = now - backup_info.created_at
        
        # Check age-based retention
        if self.max_age_days and backup_age.days > self.max_age_days:
            return False
        
        # Check count-based retention
        if self.max_backups:
            # Sort backups by creation date (newest first)
            sorted_backups = sorted(all_backups, key=lambda b: b.created_at, reverse=True)
            if backup_info in sorted_backups[self.max_backups:]:
                return False
        
        # Check size-based retention (simplified - would need more complex logic)
        if self.max_size_gb:
            total_size = sum(b.size or 0 for b in all_backups) / (1024**3)  # Convert to GB
            if total_size > self.max_size_gb:
                # Keep newer backups, remove older ones
                sorted_backups = sorted(all_backups, key=lambda b: b.created_at, reverse=True)
                cumulative_size = 0
                for backup in sorted_backups:
                    cumulative_size += (backup.size or 0) / (1024**3)
                    if cumulative_size > self.max_size_gb and backup == backup_info:
                        return False
        
        # Check granular retention (daily/weekly/monthly)
        if self.keep_daily or self.keep_weekly or self.keep_monthly:
            return self._check_granular_retention(backup_info, all_backups)
        
        return True
    
    def _check_granular_retention(self, backup_info: BackupInfo, all_backups: List[BackupInfo]) -> bool:
        """Check granular retention policies (daily/weekly/monthly)."""
        now = datetime.utcnow()
        backup_date = backup_info.created_at
        
        # Group backups by time periods
        daily_backups = []
        weekly_backups = []
        monthly_backups = []
        
        for backup in all_backups:
            age_days = (now - backup.created_at).days
            
            if age_days <= 30:  # Last 30 days
                daily_backups.append(backup)
            elif age_days <= 90:  # Last 3 months (weekly)
                weekly_backups.append(backup)
            else:  # Older than 3 months (monthly)
                monthly_backups.append(backup)
        
        # Check daily retention
        if self.keep_daily and backup_info in daily_backups:
            daily_backups.sort(key=lambda b: b.created_at, reverse=True)
            if backup_info in daily_backups[:self.keep_daily]:
                return True
        
        # Check weekly retention
        if self.keep_weekly and backup_info in weekly_backups:
            # Group by week and keep one per week
            weekly_groups = {}
            for backup in weekly_backups:
                week_key = backup.created_at.strftime("%Y-W%U")
                if week_key not in weekly_groups:
                    weekly_groups[week_key] = []
                weekly_groups[week_key].append(backup)
            
            # Keep the newest backup from each week
            weekly_keepers = []
            for week_backups in weekly_groups.values():
                week_backups.sort(key=lambda b: b.created_at, reverse=True)
                weekly_keepers.append(week_backups[0])
            
            weekly_keepers.sort(key=lambda b: b.created_at, reverse=True)
            if backup_info in weekly_keepers[:self.keep_weekly]:
                return True
        
        # Check monthly retention
        if self.keep_monthly and backup_info in monthly_backups:
            # Group by month and keep one per month
            monthly_groups = {}
            for backup in monthly_backups:
                month_key = backup.created_at.strftime("%Y-%m")
                if month_key not in monthly_groups:
                    monthly_groups[month_key] = []
                monthly_groups[month_key].append(backup)
            
            # Keep the newest backup from each month
            monthly_keepers = []
            for month_backups in monthly_groups.values():
                month_backups.sort(key=lambda b: b.created_at, reverse=True)
                monthly_keepers.append(month_backups[0])
            
            monthly_keepers.sort(key=lambda b: b.created_at, reverse=True)
            if backup_info in monthly_keepers[:self.keep_monthly]:
                return True
        
        return False


class BackupStorage:
    """Manages backup storage locations and operations."""
    
    def __init__(
        self,
        base_path: str,
        retention_policy: Optional[RetentionPolicy] = None
    ):
        self.base_path = Path(base_path)
        self.retention_policy = retention_policy or RetentionPolicy(
            max_backups=10,
            max_age_days=30
        )
        self._ensure_base_path()
    
    def _ensure_base_path(self):
        """Ensure the base backup path exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_backup_path(self, backup_type: str, system_id: str) -> str:
        """Get the storage path for a specific backup type and system."""
        backup_dir = self.base_path / backup_type / system_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        return str(backup_dir)
    
    def get_temp_path(self) -> str:
        """Get a temporary storage path for backup operations."""
        temp_dir = self.base_path / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return str(temp_dir)
    
    async def store_backup(self, backup_info: BackupInfo, source_path: str) -> str:
        """Store a backup file in the appropriate location."""
        try:
            # Determine storage location based on backup metadata
            backup_type = backup_info.metadata.get("backup_type", "unknown")
            system_type = backup_info.source_system
            
            storage_path = self.get_backup_path(backup_type, system_type)
            filename = os.path.basename(backup_info.location)
            destination_path = os.path.join(storage_path, filename)
            
            # Copy backup file to storage location
            if source_path != destination_path:
                shutil.copy2(source_path, destination_path)
                
                # Update backup info with new location
                backup_info.location = destination_path
            
            return destination_path
            
        except Exception as e:
            raise BackupError(f"Failed to store backup: {str(e)}")
    
    async def retrieve_backup(self, backup_info: BackupInfo) -> str:
        """Retrieve a backup file path."""
        if not os.path.exists(backup_info.location):
            raise BackupError(f"Backup file not found: {backup_info.location}")
        
        return backup_info.location
    
    async def delete_backup(self, backup_info: BackupInfo) -> bool:
        """Delete a backup file."""
        try:
            if os.path.exists(backup_info.location):
                os.remove(backup_info.location)
                return True
            return False
            
        except Exception as e:
            raise BackupError(f"Failed to delete backup: {str(e)}")
    
    async def list_backups(
        self,
        backup_type: Optional[str] = None,
        system_id: Optional[str] = None
    ) -> List[str]:
        """List backup files in storage."""
        try:
            backup_files = []
            
            if backup_type and system_id:
                # List backups for specific type and system
                backup_dir = self.base_path / backup_type / system_id
                if backup_dir.exists():
                    backup_files.extend([
                        str(f) for f in backup_dir.iterdir() 
                        if f.is_file()
                    ])
            elif backup_type:
                # List all backups for specific type
                type_dir = self.base_path / backup_type
                if type_dir.exists():
                    for system_dir in type_dir.iterdir():
                        if system_dir.is_dir():
                            backup_files.extend([
                                str(f) for f in system_dir.iterdir() 
                                if f.is_file()
                            ])
            else:
                # List all backups
                for type_dir in self.base_path.iterdir():
                    if type_dir.is_dir() and type_dir.name != "temp":
                        for system_dir in type_dir.iterdir():
                            if system_dir.is_dir():
                                backup_files.extend([
                                    str(f) for f in system_dir.iterdir() 
                                    if f.is_file()
                                ])
            
            return backup_files
            
        except Exception as e:
            raise BackupError(f"Failed to list backups: {str(e)}")
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            stats = {
                "total_backups": 0,
                "total_size": 0,
                "backup_types": {},
                "oldest_backup": None,
                "newest_backup": None
            }
            
            oldest_time = None
            newest_time = None
            
            for type_dir in self.base_path.iterdir():
                if type_dir.is_dir() and type_dir.name != "temp":
                    type_stats = {
                        "count": 0,
                        "size": 0,
                        "systems": {}
                    }
                    
                    for system_dir in type_dir.iterdir():
                        if system_dir.is_dir():
                            system_count = 0
                            system_size = 0
                            
                            for backup_file in system_dir.iterdir():
                                if backup_file.is_file():
                                    file_stat = backup_file.stat()
                                    file_size = file_stat.st_size
                                    file_time = datetime.fromtimestamp(file_stat.st_mtime)
                                    
                                    system_count += 1
                                    system_size += file_size
                                    stats["total_backups"] += 1
                                    stats["total_size"] += file_size
                                    
                                    # Track oldest and newest
                                    if oldest_time is None or file_time < oldest_time:
                                        oldest_time = file_time
                                        stats["oldest_backup"] = str(backup_file)
                                    
                                    if newest_time is None or file_time > newest_time:
                                        newest_time = file_time
                                        stats["newest_backup"] = str(backup_file)
                            
                            if system_count > 0:
                                type_stats["systems"][system_dir.name] = {
                                    "count": system_count,
                                    "size": system_size
                                }
                    
                    type_stats["count"] = sum(s["count"] for s in type_stats["systems"].values())
                    type_stats["size"] = sum(s["size"] for s in type_stats["systems"].values())
                    
                    if type_stats["count"] > 0:
                        stats["backup_types"][type_dir.name] = type_stats
            
            return stats
            
        except Exception as e:
            raise BackupError(f"Failed to get storage stats: {str(e)}")
    
    async def cleanup_expired_backups(self, all_backups: List[BackupInfo]) -> List[str]:
        """Clean up expired backups based on retention policy."""
        try:
            deleted_backups = []
            
            for backup_info in all_backups:
                if not self.retention_policy.should_retain(backup_info, all_backups):
                    if await self.delete_backup(backup_info):
                        deleted_backups.append(backup_info.location)
            
            return deleted_backups
            
        except Exception as e:
            raise BackupError(f"Failed to cleanup expired backups: {str(e)}")
    
    async def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """Clean up temporary files older than specified hours."""
        try:
            temp_dir = self.base_path / "temp"
            if not temp_dir.exists():
                return 0
            
            deleted_count = 0
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    file_time = datetime.fromtimestamp(temp_file.stat().st_mtime)
                    if file_time < cutoff_time:
                        temp_file.unlink()
                        deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            raise BackupError(f"Failed to cleanup temp files: {str(e)}")
    
    async def verify_storage_integrity(self) -> Dict[str, Any]:
        """Verify storage integrity and report issues."""
        try:
            integrity_report = {
                "total_files_checked": 0,
                "corrupted_files": [],
                "missing_files": [],
                "permission_issues": [],
                "storage_healthy": True
            }
            
            backup_files = await self.list_backups()
            
            for backup_file in backup_files:
                integrity_report["total_files_checked"] += 1
                
                # Check if file exists and is readable
                if not os.path.exists(backup_file):
                    integrity_report["missing_files"].append(backup_file)
                    integrity_report["storage_healthy"] = False
                    continue
                
                try:
                    # Check if file is readable
                    with open(backup_file, "rb") as f:
                        f.read(1)  # Try to read first byte
                except PermissionError:
                    integrity_report["permission_issues"].append(backup_file)
                    integrity_report["storage_healthy"] = False
                except Exception:
                    integrity_report["corrupted_files"].append(backup_file)
                    integrity_report["storage_healthy"] = False
            
            return integrity_report
            
        except Exception as e:
            raise BackupError(f"Failed to verify storage integrity: {str(e)}")