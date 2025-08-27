"""
Backup Management System for Codebase Checkup and Cleanup

This module provides comprehensive backup management specifically designed
for the checkup system, including incremental backups, verification,
and recovery capabilities.
"""

import asyncio
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from migration_assistant.checkup.models import CheckupConfig, CleanupResults
from migration_assistant.core.exceptions import BackupError


class BackupInfo:
    """Information about a backup."""
    
    def __init__(
        self,
        backup_id: str,
        backup_type: str,
        source_path: Path,
        backup_path: Path,
        checksum: str,
        size: int,
        created_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.backup_id = backup_id
        self.backup_type = backup_type
        self.source_path = source_path
        self.backup_path = backup_path
        self.checksum = checksum
        self.size = size
        self.created_at = created_at or datetime.now()
        self.metadata = metadata or {}
        self.verified = False
        self.verification_date: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert backup info to dictionary."""
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type,
            "source_path": str(self.source_path),
            "backup_path": str(self.backup_path),
            "checksum": self.checksum,
            "size": self.size,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "verified": self.verified,
            "verification_date": self.verification_date.isoformat() if self.verification_date else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupInfo':
        """Create backup info from dictionary."""
        backup_info = cls(
            backup_id=data["backup_id"],
            backup_type=data["backup_type"],
            source_path=Path(data["source_path"]),
            backup_path=Path(data["backup_path"]),
            checksum=data["checksum"],
            size=data["size"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {})
        )
        backup_info.verified = data.get("verified", False)
        if data.get("verification_date"):
            backup_info.verification_date = datetime.fromisoformat(data["verification_date"])
        return backup_info


class IncrementalBackupStrategy:
    """Strategy for creating incremental backups."""
    
    def __init__(self, base_backup_dir: Path):
        self.base_backup_dir = base_backup_dir
        self._file_checksums: Dict[Path, str] = {}
        self._last_backup_time: Optional[datetime] = None
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except (OSError, IOError):
            return ""
    
    def get_changed_files(self, target_directory: Path) -> List[Path]:
        """Get list of files that have changed since last backup."""
        changed_files = []
        
        # Get all Python files in target directory
        for file_path in target_directory.rglob("*.py"):
            if file_path.is_file():
                current_checksum = self._calculate_file_checksum(file_path)
                previous_checksum = self._file_checksums.get(file_path, "")
                
                if current_checksum != previous_checksum:
                    changed_files.append(file_path)
                    self._file_checksums[file_path] = current_checksum
        
        return changed_files
    
    def update_checksums(self, files: List[Path]):
        """Update checksums for the given files."""
        for file_path in files:
            if file_path.is_file():
                self._file_checksums[file_path] = self._calculate_file_checksum(file_path)
    
    def save_state(self, state_file: Path):
        """Save the current state to a file."""
        state_data = {
            "file_checksums": {str(k): v for k, v in self._file_checksums.items()},
            "last_backup_time": self._last_backup_time.isoformat() if self._last_backup_time else None
        }
        
        with open(state_file, "w") as f:
            json.dump(state_data, f, indent=2)
    
    def load_state(self, state_file: Path):
        """Load state from a file."""
        if not state_file.exists():
            return
        
        try:
            with open(state_file, "r") as f:
                state_data = json.load(f)
            
            self._file_checksums = {
                Path(k): v for k, v in state_data.get("file_checksums", {}).items()
            }
            
            if state_data.get("last_backup_time"):
                self._last_backup_time = datetime.fromisoformat(state_data["last_backup_time"])
        except (json.JSONDecodeError, KeyError, ValueError):
            # If state file is corrupted, start fresh
            self._file_checksums = {}
            self._last_backup_time = None


class BackupManager:
    """
    Comprehensive backup manager for checkup operations.
    
    Provides automatic backup creation, incremental backup strategies,
    backup verification, and integrity checking.
    """
    
    def __init__(self, config: CheckupConfig):
        self.config = config
        self.backup_dir = config.backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize incremental backup strategy
        self.incremental_strategy = IncrementalBackupStrategy(self.backup_dir)
        self.state_file = self.backup_dir / "backup_state.json"
        self.incremental_strategy.load_state(self.state_file)
        
        # Backup registry
        self.registry_file = self.backup_dir / "backup_registry.json"
        self._backup_registry: Dict[str, BackupInfo] = {}
        self._load_registry()
    
    def _load_registry(self):
        """Load backup registry from file."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r") as f:
                    registry_data = json.load(f)
                
                self._backup_registry = {
                    backup_id: BackupInfo.from_dict(data)
                    for backup_id, data in registry_data.items()
                }
            except (json.JSONDecodeError, KeyError):
                self._backup_registry = {}
    
    def _save_registry(self):
        """Save backup registry to file."""
        registry_data = {
            backup_id: backup_info.to_dict()
            for backup_id, backup_info in self._backup_registry.items()
        }
        
        with open(self.registry_file, "w") as f:
            json.dump(registry_data, f, indent=2)
    
    def _generate_backup_id(self) -> str:
        """Generate a unique backup ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"checkup_backup_{timestamp}"
    
    def _calculate_directory_checksum(self, directory: Path) -> str:
        """Calculate checksum for entire directory structure."""
        sha256_hash = hashlib.sha256()
        
        # Sort files for consistent checksum
        files = sorted(directory.rglob("*"))
        
        for file_path in files:
            if file_path.is_file():
                # Include file path in checksum
                sha256_hash.update(str(file_path.relative_to(directory)).encode())
                
                # Include file content in checksum
                try:
                    with open(file_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            sha256_hash.update(chunk)
                except (OSError, IOError):
                    # If file can't be read, include error marker
                    sha256_hash.update(b"<UNREADABLE>")
        
        return sha256_hash.hexdigest()
    
    async def create_full_backup(
        self,
        source_path: Optional[Path] = None,
        backup_name: Optional[str] = None
    ) -> BackupInfo:
        """
        Create a full backup of the target directory.
        
        Args:
            source_path: Path to backup (defaults to config.target_directory)
            backup_name: Custom name for backup (optional)
            
        Returns:
            BackupInfo object with backup details
        """
        if self.config.dry_run:
            raise BackupError("Cannot create backup in dry run mode")
        
        source_path = source_path or self.config.target_directory
        backup_id = backup_name or self._generate_backup_id()
        
        # Validate prerequisites
        validation_issues = self._validate_backup_prerequisites(source_path)
        if validation_issues:
            raise BackupError(f"Backup validation failed: {'; '.join(validation_issues)}")
        
        try:
            # Create backup directory
            backup_path = self.backup_dir / f"{backup_id}.tar.gz"
            
            # Track files and issues
            files_added = 0
            files_skipped = 0
            permission_issues = []
            
            # Create tar archive
            with tarfile.open(backup_path, "w:gz") as tar:
                # Add files while respecting exclusion patterns
                for item in source_path.rglob("*"):
                    if self._should_exclude(item):
                        continue
                    
                    # Check file permissions
                    perms = self._check_file_permissions(item)
                    if not perms["readable"]:
                        permission_issues.append(str(item))
                        files_skipped += 1
                        continue
                    
                    try:
                        arcname = item.relative_to(source_path)
                        tar.add(item, arcname=arcname)
                        files_added += 1
                    except (OSError, IOError, PermissionError) as e:
                        permission_issues.append(f"{item}: {str(e)}")
                        files_skipped += 1
            
            # Calculate checksum and size
            checksum = self._calculate_file_checksum(backup_path)
            size = backup_path.stat().st_size
            
            # Create backup info
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type="full",
                source_path=source_path,
                backup_path=backup_path,
                checksum=checksum,
                size=size,
                metadata={
                    "compression": "gzip",
                    "source_files": files_added,
                    "files_skipped": files_skipped,
                    "backup_method": "tar_archive",
                    "permission_issues": permission_issues[:10],  # Limit to first 10
                    "total_permission_issues": len(permission_issues)
                }
            )
            
            # Register backup
            self._backup_registry[backup_id] = backup_info
            self._save_registry()
            
            return backup_info
            
        except Exception as e:
            # Clean up partial backup file
            backup_path = self.backup_dir / f"{backup_id}.tar.gz"
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except:
                    pass
            raise BackupError(f"Failed to create full backup: {str(e)}")
    
    async def create_incremental_backup(
        self,
        source_path: Optional[Path] = None,
        backup_name: Optional[str] = None
    ) -> Optional[BackupInfo]:
        """
        Create an incremental backup containing only changed files.
        
        Args:
            source_path: Path to backup (defaults to config.target_directory)
            backup_name: Custom name for backup (optional)
            
        Returns:
            BackupInfo object if changes were found, None if no changes
        """
        if self.config.dry_run:
            raise BackupError("Cannot create backup in dry run mode")
        
        source_path = source_path or self.config.target_directory
        
        # Get changed files
        changed_files = self.incremental_strategy.get_changed_files(source_path)
        
        if not changed_files:
            return None  # No changes to backup
        
        backup_id = backup_name or self._generate_backup_id()
        
        try:
            # Create backup directory for incremental files
            incremental_dir = self.backup_dir / f"{backup_id}_incremental"
            incremental_dir.mkdir(exist_ok=True)
            
            # Copy changed files to backup directory
            for file_path in changed_files:
                if self._should_exclude(file_path):
                    continue
                
                relative_path = file_path.relative_to(source_path)
                backup_file_path = incremental_dir / relative_path
                backup_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(file_path, backup_file_path)
            
            # Create tar archive of incremental backup
            backup_path = self.backup_dir / f"{backup_id}_incremental.tar.gz"
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(incremental_dir, arcname=".")
            
            # Clean up temporary directory
            shutil.rmtree(incremental_dir)
            
            # Calculate checksum and size
            checksum = self._calculate_file_checksum(backup_path)
            size = backup_path.stat().st_size
            
            # Create backup info
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type="incremental",
                source_path=source_path,
                backup_path=backup_path,
                checksum=checksum,
                size=size,
                metadata={
                    "compression": "gzip",
                    "changed_files": len(changed_files),
                    "backup_method": "incremental_tar",
                    "changed_file_list": [str(f) for f in changed_files]
                }
            )
            
            # Register backup
            self._backup_registry[backup_id] = backup_info
            self._save_registry()
            
            # Update incremental strategy state
            self.incremental_strategy.update_checksums(changed_files)
            self.incremental_strategy.save_state(self.state_file)
            
            return backup_info
            
        except Exception as e:
            raise BackupError(f"Failed to create incremental backup: {str(e)}")
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from backup."""
        path_str = str(path)
        
        # Check exclusion patterns
        for pattern in self.config.exclude_patterns:
            if pattern in path_str:
                return True
        
        # Check exclusion directories
        for exclude_dir in self.config.exclude_dirs:
            if exclude_dir in path.parts:
                return True
        
        return False
    
    def _check_file_permissions(self, file_path: Path) -> Dict[str, bool]:
        """Check file permissions and accessibility."""
        try:
            stat_info = file_path.stat()
            return {
                "readable": file_path.is_file() and os.access(file_path, os.R_OK),
                "writable": os.access(file_path, os.W_OK),
                "executable": os.access(file_path, os.X_OK),
                "size": stat_info.st_size,
                "exists": file_path.exists()
            }
        except (OSError, IOError, PermissionError):
            return {
                "readable": False,
                "writable": False,
                "executable": False,
                "size": 0,
                "exists": False
            }
    
    def _validate_backup_prerequisites(self, source_path: Path) -> List[str]:
        """Validate that backup can be created successfully."""
        issues = []
        
        # Check source directory exists and is readable
        if not source_path.exists():
            issues.append(f"Source directory does not exist: {source_path}")
            return issues
        
        if not source_path.is_dir():
            issues.append(f"Source path is not a directory: {source_path}")
            return issues
        
        if not os.access(source_path, os.R_OK):
            issues.append(f"Source directory is not readable: {source_path}")
        
        # Check backup directory can be created/written to
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(self.backup_dir, os.W_OK):
                issues.append(f"Backup directory is not writable: {self.backup_dir}")
        except (OSError, IOError, PermissionError) as e:
            issues.append(f"Cannot create backup directory: {e}")
        
        # Check available disk space (basic check)
        try:
            source_size = sum(f.stat().st_size for f in source_path.rglob("*") if f.is_file())
            backup_disk_usage = shutil.disk_usage(self.backup_dir)
            available_space = backup_disk_usage.free
            
            # Require at least 2x source size for safety (compression + temp files)
            required_space = source_size * 2
            if available_space < required_space:
                issues.append(
                    f"Insufficient disk space. Required: {required_space / (1024**2):.1f}MB, "
                    f"Available: {available_space / (1024**2):.1f}MB"
                )
        except (OSError, IOError):
            issues.append("Could not check available disk space")
        
        return issues
    
    async def verify_backup(self, backup_id: str, test_restoration: bool = False) -> bool:
        """
        Verify backup integrity by checking checksum and archive validity.
        
        Args:
            backup_id: ID of backup to verify
            test_restoration: If True, test actual restoration to temporary directory
            
        Returns:
            True if backup is valid, False otherwise
        """
        backup_info = self._backup_registry.get(backup_id)
        if not backup_info:
            return False
        
        try:
            # Check if backup file exists
            if not backup_info.backup_path.exists():
                return False
            
            # Check file permissions
            if not backup_info.backup_path.is_file():
                return False
            
            # Verify checksum
            current_checksum = self._calculate_file_checksum(backup_info.backup_path)
            if current_checksum != backup_info.checksum:
                return False
            
            # Verify archive can be opened and read
            with tarfile.open(backup_info.backup_path, "r:gz") as tar:
                # Try to list contents
                members = tar.getnames()
                if not members:
                    return False
                
                # Test restoration if requested
                if test_restoration:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)
                        tar.extractall(temp_path)
                        
                        # Verify extracted files exist and are readable
                        for member in members:
                            extracted_file = temp_path / member
                            if not extracted_file.exists():
                                return False
                            
                            # Test file readability
                            if extracted_file.is_file():
                                try:
                                    extracted_file.read_bytes()
                                except (OSError, IOError):
                                    return False
            
            # Mark as verified
            backup_info.verified = True
            backup_info.verification_date = datetime.now()
            backup_info.metadata["verification_method"] = "full" if test_restoration else "basic"
            self._save_registry()
            
            return True
            
        except Exception as e:
            # Log the verification error for debugging
            backup_info.metadata["last_verification_error"] = str(e)
            self._save_registry()
            return False
    
    async def verify_all_backups(self) -> Dict[str, bool]:
        """
        Verify all backups in the registry.
        
        Returns:
            Dictionary mapping backup IDs to verification results
        """
        verification_results = {}
        
        for backup_id in self._backup_registry.keys():
            verification_results[backup_id] = await self.verify_backup(backup_id)
        
        return verification_results
    
    def list_backups(
        self,
        backup_type: Optional[str] = None,
        verified_only: bool = False
    ) -> List[BackupInfo]:
        """
        List available backups.
        
        Args:
            backup_type: Filter by backup type ("full" or "incremental")
            verified_only: Only return verified backups
            
        Returns:
            List of BackupInfo objects
        """
        backups = list(self._backup_registry.values())
        
        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]
        
        if verified_only:
            backups = [b for b in backups if b.verified]
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        
        return backups
    
    def get_backup_info(self, backup_id: str) -> Optional[BackupInfo]:
        """Get backup information by ID."""
        return self._backup_registry.get(backup_id)
    
    async def delete_backup(self, backup_id: str) -> bool:
        """
        Delete a backup and remove it from registry.
        
        Args:
            backup_id: ID of backup to delete
            
        Returns:
            True if backup was deleted, False if not found
        """
        backup_info = self._backup_registry.get(backup_id)
        if not backup_info:
            return False
        
        try:
            # Delete backup file
            if backup_info.backup_path.exists():
                backup_info.backup_path.unlink()
            
            # Remove from registry
            del self._backup_registry[backup_id]
            self._save_registry()
            
            return True
            
        except Exception:
            return False
    
    async def cleanup_old_backups(
        self,
        max_age_days: int = 30,
        max_backups: int = 10
    ) -> List[str]:
        """
        Clean up old backups based on age and count limits.
        
        Args:
            max_age_days: Maximum age of backups to keep
            max_backups: Maximum number of backups to keep
            
        Returns:
            List of deleted backup IDs
        """
        deleted_backups = []
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # Get all backups sorted by creation date (oldest first)
        all_backups = sorted(
            self._backup_registry.values(),
            key=lambda b: b.created_at
        )
        
        # Delete backups older than cutoff date
        for backup_info in all_backups:
            if backup_info.created_at < cutoff_date:
                if await self.delete_backup(backup_info.backup_id):
                    deleted_backups.append(backup_info.backup_id)
        
        # Delete excess backups (keep only max_backups newest)
        remaining_backups = [
            b for b in all_backups 
            if b.backup_id not in deleted_backups
        ]
        
        if len(remaining_backups) > max_backups:
            excess_backups = remaining_backups[:-max_backups]
            for backup_info in excess_backups:
                if await self.delete_backup(backup_info.backup_id):
                    deleted_backups.append(backup_info.backup_id)
        
        return deleted_backups
    
    async def test_backup_restoration(self, backup_id: str, test_directory: Optional[Path] = None) -> Dict[str, Any]:
        """
        Test backup restoration to verify data integrity.
        
        Args:
            backup_id: ID of backup to test
            test_directory: Directory to restore to (uses temp dir if None)
            
        Returns:
            Dictionary with restoration test results
        """
        backup_info = self._backup_registry.get(backup_id)
        if not backup_info:
            return {"success": False, "error": "Backup not found"}
        
        if not backup_info.backup_path.exists():
            return {"success": False, "error": "Backup file not found"}
        
        try:
            # Use provided directory or create temporary one
            if test_directory:
                restore_path = test_directory
                cleanup_after = False
            else:
                temp_dir = tempfile.mkdtemp()
                restore_path = Path(temp_dir)
                cleanup_after = True
            
            try:
                # Extract backup
                with tarfile.open(backup_info.backup_path, "r:gz") as tar:
                    tar.extractall(restore_path)
                
                # Verify extracted files
                extracted_files = list(restore_path.rglob("*"))
                readable_files = 0
                total_size = 0
                
                for file_path in extracted_files:
                    if file_path.is_file():
                        try:
                            file_size = file_path.stat().st_size
                            total_size += file_size
                            
                            # Test file readability
                            with open(file_path, 'rb') as f:
                                f.read(1024)  # Read first 1KB to test
                            readable_files += 1
                            
                        except (OSError, IOError, PermissionError):
                            pass
                
                return {
                    "success": True,
                    "backup_id": backup_id,
                    "backup_type": backup_info.backup_type,
                    "extracted_files": len(extracted_files),
                    "readable_files": readable_files,
                    "total_size": total_size,
                    "restore_path": str(restore_path) if not cleanup_after else None,
                    "test_timestamp": datetime.now().isoformat()
                }
                
            finally:
                if cleanup_after:
                    shutil.rmtree(restore_path, ignore_errors=True)
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Restoration test failed: {str(e)}",
                "backup_id": backup_id
            }
    
    def get_backup_statistics(self) -> Dict[str, Any]:
        """Get statistics about backups."""
        backups = list(self._backup_registry.values())
        
        if not backups:
            return {
                "total_backups": 0,
                "total_size": 0,
                "verified_backups": 0,
                "full_backups": 0,
                "incremental_backups": 0,
                "oldest_backup": None,
                "newest_backup": None
            }
        
        total_size = sum(b.size for b in backups)
        verified_count = sum(1 for b in backups if b.verified)
        full_count = sum(1 for b in backups if b.backup_type == "full")
        incremental_count = sum(1 for b in backups if b.backup_type == "incremental")
        
        oldest_backup = min(backups, key=lambda b: b.created_at)
        newest_backup = max(backups, key=lambda b: b.created_at)
        
        return {
            "total_backups": len(backups),
            "total_size": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "verified_backups": verified_count,
            "full_backups": full_count,
            "incremental_backups": incremental_count,
            "oldest_backup": oldest_backup.created_at.isoformat(),
            "newest_backup": newest_backup.created_at.isoformat(),
            "verification_rate": verified_count / len(backups) if backups else 0
        }
    
    async def create_pre_cleanup_backup(self, files_to_modify: List[Path]) -> Optional[BackupInfo]:
        """
        Create a targeted backup of files that will be modified during cleanup.
        
        Args:
            files_to_modify: List of files that will be modified
            
        Returns:
            BackupInfo object if backup was created, None if no files to backup
        """
        if not files_to_modify or self.config.dry_run:
            return None
        
        backup_id = f"pre_cleanup_{self._generate_backup_id()}"
        
        try:
            # Create backup directory for specific files
            backup_dir = self.backup_dir / f"{backup_id}_files"
            backup_dir.mkdir(exist_ok=True)
            
            # Copy files to backup directory
            backed_up_files = []
            for file_path in files_to_modify:
                if not file_path.exists() or self._should_exclude(file_path):
                    continue
                
                relative_path = file_path.relative_to(self.config.target_directory)
                backup_file_path = backup_dir / relative_path
                backup_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(file_path, backup_file_path)
                backed_up_files.append(file_path)
            
            if not backed_up_files:
                shutil.rmtree(backup_dir)
                return None
            
            # Create tar archive
            backup_path = self.backup_dir / f"{backup_id}.tar.gz"
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(backup_dir, arcname=".")
            
            # Clean up temporary directory
            shutil.rmtree(backup_dir)
            
            # Calculate checksum and size
            checksum = self._calculate_file_checksum(backup_path)
            size = backup_path.stat().st_size
            
            # Create backup info
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type="pre_cleanup",
                source_path=self.config.target_directory,
                backup_path=backup_path,
                checksum=checksum,
                size=size,
                metadata={
                    "compression": "gzip",
                    "backed_up_files": len(backed_up_files),
                    "backup_method": "targeted_files",
                    "file_list": [str(f) for f in backed_up_files]
                }
            )
            
            # Register backup
            self._backup_registry[backup_id] = backup_info
            self._save_registry()
            
            return backup_info
            
        except Exception as e:
            raise BackupError(f"Failed to create pre-cleanup backup: {str(e)}")