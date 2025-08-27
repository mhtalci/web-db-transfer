"""
Rollback and Recovery Manager for Codebase Checkup and Cleanup

This module provides comprehensive rollback and recovery capabilities
for failed operations, including automatic rollback for failed operations
and manual rollback commands for user-initiated recovery.
"""

import asyncio
import json
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from migration_assistant.checkup.backup_manager import BackupInfo, BackupManager
from migration_assistant.checkup.models import CheckupConfig, CleanupResults
from migration_assistant.core.exceptions import BackupError


class RollbackOperation:
    """Information about a rollback operation."""
    
    def __init__(
        self,
        operation_id: str,
        operation_type: str,
        backup_id: str,
        affected_files: List[Path],
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.backup_id = backup_id
        self.affected_files = affected_files
        self.timestamp = timestamp or datetime.now()
        self.metadata = metadata or {}
        self.rollback_completed = False
        self.rollback_timestamp: Optional[datetime] = None
        self.rollback_errors: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rollback operation to dictionary."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "backup_id": self.backup_id,
            "affected_files": [str(f) for f in self.affected_files],
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "rollback_completed": self.rollback_completed,
            "rollback_timestamp": self.rollback_timestamp.isoformat() if self.rollback_timestamp else None,
            "rollback_errors": self.rollback_errors
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RollbackOperation':
        """Create rollback operation from dictionary."""
        operation = cls(
            operation_id=data["operation_id"],
            operation_type=data["operation_type"],
            backup_id=data["backup_id"],
            affected_files=[Path(f) for f in data["affected_files"]],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )
        operation.rollback_completed = data.get("rollback_completed", False)
        if data.get("rollback_timestamp"):
            operation.rollback_timestamp = datetime.fromisoformat(data["rollback_timestamp"])
        operation.rollback_errors = data.get("rollback_errors", [])
        return operation


class RecoveryValidator:
    """Validates recovery operations and ensures data integrity."""
    
    def __init__(self, config: CheckupConfig):
        self.config = config
    
    async def validate_recovery_preconditions(
        self,
        backup_info: BackupInfo,
        target_files: List[Path]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that recovery can be performed safely.
        
        Args:
            backup_info: Backup to recover from
            target_files: Files that will be affected by recovery
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check if backup exists and is valid
        if not backup_info.backup_path.exists():
            errors.append(f"Backup file not found: {backup_info.backup_path}")
        
        # Verify backup integrity
        if not await self._verify_backup_integrity(backup_info):
            errors.append("Backup integrity verification failed")
        
        # Check if target files can be overwritten
        for file_path in target_files:
            if file_path.exists() and not self._can_overwrite_file(file_path):
                errors.append(f"Cannot overwrite file: {file_path}")
        
        # Check available disk space
        if not await self._check_disk_space(backup_info):
            errors.append("Insufficient disk space for recovery")
        
        return len(errors) == 0, errors
    
    async def _verify_backup_integrity(self, backup_info: BackupInfo) -> bool:
        """Verify backup file integrity."""
        try:
            # Check file size
            actual_size = backup_info.backup_path.stat().st_size
            if backup_info.size and actual_size != backup_info.size:
                return False
            
            # Verify archive can be opened
            with tarfile.open(backup_info.backup_path, "r:gz") as tar:
                tar.getnames()
            
            return True
        except Exception:
            return False
    
    def _can_overwrite_file(self, file_path: Path) -> bool:
        """Check if a file can be safely overwritten."""
        try:
            # Check if file is writable
            return file_path.is_file() and file_path.stat().st_mode & 0o200
        except (OSError, IOError):
            return False
    
    async def _check_disk_space(self, backup_info: BackupInfo) -> bool:
        """Check if there's enough disk space for recovery."""
        try:
            # Get available space in target directory
            target_dir = self.config.target_directory
            total, used, free = shutil.disk_usage(target_dir)
            
            # Estimate space needed (backup size * 2 for safety)
            estimated_space_needed = (backup_info.size or 0) * 2
            
            return free >= estimated_space_needed
        except Exception:
            return False
    
    async def validate_post_recovery(
        self,
        recovered_files: List[Path],
        expected_checksums: Optional[Dict[Path, str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate that recovery was successful.
        
        Args:
            recovered_files: Files that were recovered
            expected_checksums: Expected checksums for validation
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check that all expected files exist
        for file_path in recovered_files:
            if not file_path.exists():
                errors.append(f"Recovered file not found: {file_path}")
            elif not file_path.is_file():
                errors.append(f"Recovered path is not a file: {file_path}")
        
        # Validate checksums if provided
        if expected_checksums:
            for file_path, expected_checksum in expected_checksums.items():
                if file_path in recovered_files:
                    actual_checksum = await self._calculate_file_checksum(file_path)
                    if actual_checksum != expected_checksum:
                        errors.append(f"Checksum mismatch for {file_path}")
        
        return len(errors) == 0, errors
    
    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        import hashlib
        
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except (OSError, IOError):
            return ""


class RollbackManager:
    """
    Comprehensive rollback and recovery manager for checkup operations.
    
    Provides automatic rollback for failed operations, manual rollback
    commands for user-initiated recovery, and recovery validation.
    """
    
    def __init__(self, config: CheckupConfig, backup_manager: BackupManager):
        self.config = config
        self.backup_manager = backup_manager
        self.validator = RecoveryValidator(config)
        
        # Rollback tracking
        self.rollback_dir = config.backup_dir / "rollback_operations"
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        self.operations_file = self.rollback_dir / "operations.json"
        
        self._rollback_operations: Dict[str, RollbackOperation] = {}
        self._load_operations()
    
    def _load_operations(self):
        """Load rollback operations from file."""
        if self.operations_file.exists():
            try:
                with open(self.operations_file, "r") as f:
                    operations_data = json.load(f)
                
                self._rollback_operations = {
                    op_id: RollbackOperation.from_dict(data)
                    for op_id, data in operations_data.items()
                }
            except (json.JSONDecodeError, KeyError):
                self._rollback_operations = {}
    
    def _save_operations(self):
        """Save rollback operations to file."""
        operations_data = {
            op_id: operation.to_dict()
            for op_id, operation in self._rollback_operations.items()
        }
        
        with open(self.operations_file, "w") as f:
            json.dump(operations_data, f, indent=2)
    
    def _generate_operation_id(self) -> str:
        """Generate a unique operation ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"rollback_op_{timestamp}"
    
    async def register_operation(
        self,
        operation_type: str,
        backup_id: str,
        affected_files: List[Path],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register an operation that can be rolled back.
        
        Args:
            operation_type: Type of operation (e.g., "cleanup", "formatting")
            backup_id: ID of backup created before operation
            affected_files: Files that will be affected by the operation
            metadata: Additional metadata about the operation
            
        Returns:
            Operation ID for tracking
        """
        operation_id = self._generate_operation_id()
        
        operation = RollbackOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            backup_id=backup_id,
            affected_files=affected_files,
            metadata=metadata or {}
        )
        
        self._rollback_operations[operation_id] = operation
        self._save_operations()
        
        return operation_id
    
    async def automatic_rollback(
        self,
        operation_id: str,
        error_context: Optional[str] = None
    ) -> bool:
        """
        Perform automatic rollback for a failed operation.
        
        Args:
            operation_id: ID of operation to roll back
            error_context: Context about the error that triggered rollback
            
        Returns:
            True if rollback was successful, False otherwise
        """
        operation = self._rollback_operations.get(operation_id)
        if not operation:
            return False
        
        try:
            # Get backup information
            backup_info = self.backup_manager.get_backup_info(operation.backup_id)
            if not backup_info:
                operation.rollback_errors.append(f"Backup not found: {operation.backup_id}")
                self._save_operations()
                return False
            
            # Validate recovery preconditions
            is_valid, errors = await self.validator.validate_recovery_preconditions(
                backup_info, operation.affected_files
            )
            
            if not is_valid:
                operation.rollback_errors.extend(errors)
                self._save_operations()
                return False
            
            # Perform rollback
            success = await self._perform_rollback(operation, backup_info, error_context)
            
            # Update operation status
            operation.rollback_completed = success
            operation.rollback_timestamp = datetime.now()
            
            if not success:
                operation.rollback_errors.append("Rollback operation failed")
            
            self._save_operations()
            return success
            
        except Exception as e:
            operation.rollback_errors.append(f"Rollback exception: {str(e)}")
            self._save_operations()
            return False
    
    async def manual_rollback(
        self,
        operation_id: Optional[str] = None,
        backup_id: Optional[str] = None,
        target_files: Optional[List[Path]] = None
    ) -> bool:
        """
        Perform manual rollback initiated by user.
        
        Args:
            operation_id: ID of operation to roll back (if available)
            backup_id: ID of backup to restore from
            target_files: Specific files to restore (optional)
            
        Returns:
            True if rollback was successful, False otherwise
        """
        try:
            # Determine what to roll back
            if operation_id:
                operation = self._rollback_operations.get(operation_id)
                if not operation:
                    return False
                
                backup_info = self.backup_manager.get_backup_info(operation.backup_id)
                affected_files = operation.affected_files
                
            elif backup_id:
                backup_info = self.backup_manager.get_backup_info(backup_id)
                affected_files = target_files or []
                
                # Create a temporary operation for tracking
                operation = RollbackOperation(
                    operation_id=self._generate_operation_id(),
                    operation_type="manual_rollback",
                    backup_id=backup_id,
                    affected_files=affected_files,
                    metadata={"manual": True}
                )
                self._rollback_operations[operation.operation_id] = operation
                
            else:
                return False
            
            if not backup_info:
                return False
            
            # Validate recovery preconditions
            is_valid, errors = await self.validator.validate_recovery_preconditions(
                backup_info, affected_files
            )
            
            if not is_valid:
                operation.rollback_errors.extend(errors)
                self._save_operations()
                return False
            
            # Perform rollback
            success = await self._perform_rollback(operation, backup_info, "Manual rollback")
            
            # Update operation status
            operation.rollback_completed = success
            operation.rollback_timestamp = datetime.now()
            
            if not success:
                operation.rollback_errors.append("Manual rollback failed")
            
            self._save_operations()
            return success
            
        except Exception as e:
            if 'operation' in locals():
                operation.rollback_errors.append(f"Manual rollback exception: {str(e)}")
                self._save_operations()
            return False
    
    async def _perform_rollback(
        self,
        operation: RollbackOperation,
        backup_info: BackupInfo,
        context: Optional[str] = None
    ) -> bool:
        """
        Perform the actual rollback operation.
        
        Args:
            operation: Rollback operation to perform
            backup_info: Backup to restore from
            context: Context about why rollback is being performed
            
        Returns:
            True if rollback was successful, False otherwise
        """
        try:
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Extract backup
                with tarfile.open(backup_info.backup_path, "r:gz") as tar:
                    tar.extractall(path=temp_path)
                
                # Restore files
                restored_files = []
                
                if backup_info.backup_type == "pre_cleanup":
                    # For pre-cleanup backups, restore specific files
                    await self._restore_specific_files(
                        temp_path, operation.affected_files, restored_files
                    )
                elif backup_info.backup_type in ["full", "incremental"]:
                    # For full/incremental backups, restore entire directory structure
                    await self._restore_directory_structure(
                        temp_path, self.config.target_directory, restored_files
                    )
                else:
                    operation.rollback_errors.append(f"Unsupported backup type: {backup_info.backup_type}")
                    return False
                
                # Validate post-recovery
                is_valid, errors = await self.validator.validate_post_recovery(restored_files)
                
                if not is_valid:
                    operation.rollback_errors.extend(errors)
                    return False
                
                # Update operation metadata
                operation.metadata.update({
                    "restored_files": len(restored_files),
                    "context": context,
                    "backup_type": backup_info.backup_type
                })
                
                return True
                
        except Exception as e:
            operation.rollback_errors.append(f"Rollback execution failed: {str(e)}")
            return False
    
    async def _restore_specific_files(
        self,
        backup_path: Path,
        target_files: List[Path],
        restored_files: List[Path]
    ):
        """Restore specific files from backup."""
        for target_file in target_files:
            # Find corresponding file in backup
            relative_path = target_file.relative_to(self.config.target_directory)
            backup_file = backup_path / relative_path
            
            if backup_file.exists():
                # Ensure target directory exists
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file from backup to target location
                shutil.copy2(backup_file, target_file)
                restored_files.append(target_file)
    
    async def _restore_directory_structure(
        self,
        backup_path: Path,
        target_path: Path,
        restored_files: List[Path]
    ):
        """Restore entire directory structure from backup."""
        for item in backup_path.rglob("*"):
            if item.is_file():
                relative_path = item.relative_to(backup_path)
                target_file = target_path / relative_path
                
                # Ensure target directory exists
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file from backup to target location
                shutil.copy2(item, target_file)
                restored_files.append(target_file)
    
    def list_rollback_operations(
        self,
        operation_type: Optional[str] = None,
        completed_only: bool = False
    ) -> List[RollbackOperation]:
        """
        List rollback operations.
        
        Args:
            operation_type: Filter by operation type
            completed_only: Only return completed rollbacks
            
        Returns:
            List of rollback operations
        """
        operations = list(self._rollback_operations.values())
        
        if operation_type:
            operations = [op for op in operations if op.operation_type == operation_type]
        
        if completed_only:
            operations = [op for op in operations if op.rollback_completed]
        
        # Sort by timestamp (newest first)
        operations.sort(key=lambda op: op.timestamp, reverse=True)
        
        return operations
    
    def get_rollback_operation(self, operation_id: str) -> Optional[RollbackOperation]:
        """Get rollback operation by ID."""
        return self._rollback_operations.get(operation_id)
    
    async def cleanup_old_operations(self, max_age_days: int = 30) -> List[str]:
        """
        Clean up old rollback operations.
        
        Args:
            max_age_days: Maximum age of operations to keep
            
        Returns:
            List of deleted operation IDs
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        deleted_operations = []
        
        for op_id, operation in list(self._rollback_operations.items()):
            if operation.timestamp < cutoff_date:
                del self._rollback_operations[op_id]
                deleted_operations.append(op_id)
        
        if deleted_operations:
            self._save_operations()
        
        return deleted_operations
    
    def get_rollback_statistics(self) -> Dict[str, Any]:
        """Get statistics about rollback operations."""
        operations = list(self._rollback_operations.values())
        
        if not operations:
            return {
                "total_operations": 0,
                "completed_rollbacks": 0,
                "failed_rollbacks": 0,
                "success_rate": 0.0,
                "operation_types": {},
                "recent_operations": 0
            }
        
        completed_count = sum(1 for op in operations if op.rollback_completed)
        failed_count = len(operations) - completed_count
        
        # Count by operation type
        operation_types = {}
        for operation in operations:
            op_type = operation.operation_type
            if op_type not in operation_types:
                operation_types[op_type] = {"total": 0, "completed": 0}
            operation_types[op_type]["total"] += 1
            if operation.rollback_completed:
                operation_types[op_type]["completed"] += 1
        
        # Count recent operations (last 7 days)
        from datetime import timedelta
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_count = sum(1 for op in operations if op.timestamp >= recent_cutoff)
        
        return {
            "total_operations": len(operations),
            "completed_rollbacks": completed_count,
            "failed_rollbacks": failed_count,
            "success_rate": completed_count / len(operations) if operations else 0.0,
            "operation_types": operation_types,
            "recent_operations": recent_count
        }
    
    async def verify_rollback_capability(self, operation_id: str) -> Tuple[bool, List[str]]:
        """
        Verify that a rollback operation can be performed.
        
        Args:
            operation_id: ID of operation to verify
            
        Returns:
            Tuple of (can_rollback, error_messages)
        """
        operation = self._rollback_operations.get(operation_id)
        if not operation:
            return False, ["Operation not found"]
        
        if operation.rollback_completed:
            return False, ["Operation has already been rolled back"]
        
        # Get backup information
        backup_info = self.backup_manager.get_backup_info(operation.backup_id)
        if not backup_info:
            return False, [f"Backup not found: {operation.backup_id}"]
        
        # Validate recovery preconditions
        return await self.validator.validate_recovery_preconditions(
            backup_info, operation.affected_files
        )
    
    async def create_recovery_plan(
        self,
        operation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a detailed recovery plan for a rollback operation.
        
        Args:
            operation_id: ID of operation to create plan for
            
        Returns:
            Recovery plan dictionary or None if operation not found
        """
        operation = self._rollback_operations.get(operation_id)
        if not operation:
            return None
        
        backup_info = self.backup_manager.get_backup_info(operation.backup_id)
        if not backup_info:
            return None
        
        # Validate rollback capability
        can_rollback, errors = await self.verify_rollback_capability(operation_id)
        
        plan = {
            "operation_id": operation_id,
            "operation_type": operation.operation_type,
            "backup_id": operation.backup_id,
            "backup_type": backup_info.backup_type,
            "backup_size": backup_info.size,
            "backup_created": backup_info.created_at.isoformat(),
            "affected_files": len(operation.affected_files),
            "can_rollback": can_rollback,
            "validation_errors": errors,
            "estimated_duration": self._estimate_rollback_duration(backup_info),
            "disk_space_required": backup_info.size * 2,  # Estimate
            "steps": [
                "Validate backup integrity",
                "Check disk space availability",
                "Create temporary extraction directory",
                "Extract backup files",
                "Restore affected files",
                "Validate restored files",
                "Update operation status"
            ]
        }
        
        return plan
    
    def _estimate_rollback_duration(self, backup_info: BackupInfo) -> int:
        """Estimate rollback duration in seconds based on backup size."""
        # Rough estimate: 10MB/second processing speed
        size_mb = (backup_info.size or 0) / (1024 * 1024)
        return max(5, int(size_mb / 10))  # Minimum 5 seconds