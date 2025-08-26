"""
Rollback and recovery manager for automatic rollback procedures.

This module provides comprehensive rollback capabilities to restore
systems to their previous state when migrations fail.
"""

import asyncio
import os
import shutil
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from migration_assistant.backup.strategies import (
    BackupStrategy,
    CloudBackupStrategy,
    ConfigBackupStrategy,
    DatabaseBackupStrategy,
    FileBackupStrategy,
)
from migration_assistant.backup.validator import RecoveryValidator, ValidationResult
from migration_assistant.core.exceptions import BackupError, RollbackError
from migration_assistant.models.config import DatabaseConfig, MigrationConfig, SystemConfig
from migration_assistant.models.session import BackupInfo, LogEntry, LogLevel, MigrationSession


class RollbackStatus(str, Enum):
    """Rollback operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class RollbackStep:
    """Individual rollback step."""
    
    def __init__(self, step_id: str, description: str, backup_info: BackupInfo):
        self.step_id = step_id
        self.description = description
        self.backup_info = backup_info
        self.status = RollbackStatus.PENDING
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.error: Optional[str] = None
        self.details: Dict[str, Any] = {}
    
    def start(self):
        """Mark step as started."""
        self.status = RollbackStatus.IN_PROGRESS
        self.start_time = datetime.utcnow()
    
    def complete(self):
        """Mark step as completed."""
        self.status = RollbackStatus.COMPLETED
        self.end_time = datetime.utcnow()
    
    def fail(self, error: str):
        """Mark step as failed."""
        self.status = RollbackStatus.FAILED
        self.end_time = datetime.utcnow()
        self.error = error


class RollbackPlan:
    """Rollback execution plan."""
    
    def __init__(self, migration_session: MigrationSession):
        self.migration_session = migration_session
        self.steps: List[RollbackStep] = []
        self.created_at = datetime.utcnow()
        self.status = RollbackStatus.PENDING
        self.estimated_duration: Optional[int] = None
    
    def add_step(self, step: RollbackStep):
        """Add a rollback step."""
        self.steps.append(step)
    
    def get_step(self, step_id: str) -> Optional[RollbackStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def get_progress(self) -> Dict[str, Any]:
        """Get rollback progress."""
        total_steps = len(self.steps)
        completed_steps = sum(1 for step in self.steps if step.status == RollbackStatus.COMPLETED)
        failed_steps = sum(1 for step in self.steps if step.status == RollbackStatus.FAILED)
        
        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "progress_percentage": (completed_steps / total_steps * 100) if total_steps > 0 else 0,
            "current_step": next(
                (step.description for step in self.steps if step.status == RollbackStatus.IN_PROGRESS),
                None
            )
        }


class RollbackManager:
    """Main rollback manager for automatic rollback procedures."""
    
    def __init__(self, recovery_validator: Optional[RecoveryValidator] = None):
        self.recovery_validator = recovery_validator or RecoveryValidator()
        self._rollback_logs: List[LogEntry] = []
        self._active_rollbacks: Dict[str, RollbackPlan] = {}
    
    def _log(self, level: LogLevel, message: str, session_id: Optional[str] = None, **kwargs):
        """Add a log entry."""
        log_entry = LogEntry(
            level=level,
            message=message,
            component="RollbackManager",
            details={"session_id": session_id, **kwargs}
        )
        self._rollback_logs.append(log_entry)
    
    async def create_rollback_plan(self, migration_session: MigrationSession) -> RollbackPlan:
        """Create a rollback plan based on available backups."""
        try:
            self._log(LogLevel.INFO, "Creating rollback plan", migration_session.id)
            
            plan = RollbackPlan(migration_session)
            
            # Sort backups by creation time (restore in reverse order)
            sorted_backups = sorted(
                migration_session.backups,
                key=lambda b: b.created_at,
                reverse=True
            )
            
            # Create rollback steps for each backup
            step_counter = 1
            for backup_info in sorted_backups:
                backup_type = backup_info.metadata.get("backup_type", "unknown")
                
                step_id = f"rollback_step_{step_counter}"
                description = f"Restore {backup_type} backup ({backup_info.id[:8]})"
                
                step = RollbackStep(step_id, description, backup_info)
                plan.add_step(step)
                step_counter += 1
            
            # Estimate rollback duration
            plan.estimated_duration = self._estimate_rollback_duration(sorted_backups)
            
            self._active_rollbacks[migration_session.id] = plan
            
            self._log(LogLevel.INFO, f"Rollback plan created with {len(plan.steps)} steps", migration_session.id)
            
            return plan
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to create rollback plan: {str(e)}", migration_session.id)
            raise RollbackError(f"Failed to create rollback plan: {str(e)}")
    
    def _estimate_rollback_duration(self, backups: List[BackupInfo]) -> int:
        """Estimate rollback duration in seconds."""
        total_size = sum(backup.size or 0 for backup in backups)
        
        # Rough estimation: 50MB/s processing speed
        base_duration = max(30, total_size / (50 * 1024 * 1024))
        
        # Add overhead for each backup
        overhead = len(backups) * 10  # 10 seconds per backup
        
        return int(base_duration + overhead)
    
    async def validate_rollback_readiness(
        self,
        migration_session: MigrationSession
    ) -> Dict[str, ValidationResult]:
        """Validate that rollback can be performed successfully."""
        try:
            self._log(LogLevel.INFO, "Validating rollback readiness", migration_session.id)
            
            if not migration_session.backups:
                raise RollbackError("No backups available for rollback")
            
            # Validate all backups
            validation_results = await self.recovery_validator.validate_multiple_backups(
                migration_session.backups
            )
            
            # Check if any critical backups failed validation
            critical_failures = [
                backup_id for backup_id, result in validation_results.items()
                if not result.is_valid
            ]
            
            if critical_failures:
                self._log(
                    LogLevel.WARNING,
                    f"Backup validation failures detected: {critical_failures}",
                    migration_session.id
                )
            
            return validation_results
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Rollback readiness validation failed: {str(e)}", migration_session.id)
            raise RollbackError(f"Failed to validate rollback readiness: {str(e)}")
    
    async def execute_rollback(
        self,
        migration_session: MigrationSession,
        rollback_options: Optional[Dict[str, Any]] = None
    ) -> RollbackPlan:
        """Execute automatic rollback procedure."""
        rollback_options = rollback_options or {}
        
        try:
            self._log(LogLevel.INFO, "Starting rollback execution", migration_session.id)
            
            # Get or create rollback plan
            plan = self._active_rollbacks.get(migration_session.id)
            if not plan:
                plan = await self.create_rollback_plan(migration_session)
            
            plan.status = RollbackStatus.IN_PROGRESS
            
            # Validate rollback readiness unless skipped
            if not rollback_options.get("skip_validation", False):
                validation_results = await self.validate_rollback_readiness(migration_session)
                
                # Check for critical validation failures
                critical_failures = [
                    backup_id for backup_id, result in validation_results.items()
                    if not result.is_valid and not rollback_options.get("force_rollback", False)
                ]
                
                if critical_failures:
                    plan.status = RollbackStatus.FAILED
                    raise RollbackError(
                        f"Cannot proceed with rollback due to backup validation failures: {critical_failures}"
                    )
            
            # Execute rollback steps
            successful_steps = 0
            failed_steps = 0
            
            for step in plan.steps:
                try:
                    step.start()
                    self._log(LogLevel.INFO, f"Executing rollback step: {step.description}", migration_session.id)
                    
                    # Execute the rollback step
                    await self._execute_rollback_step(step, rollback_options)
                    
                    step.complete()
                    successful_steps += 1
                    
                    self._log(LogLevel.INFO, f"Rollback step completed: {step.description}", migration_session.id)
                    
                except Exception as e:
                    step.fail(str(e))
                    failed_steps += 1
                    
                    self._log(LogLevel.ERROR, f"Rollback step failed: {step.description} - {str(e)}", migration_session.id)
                    
                    # Decide whether to continue or stop
                    if not rollback_options.get("continue_on_failure", False):
                        break
            
            # Determine final status
            if failed_steps == 0:
                plan.status = RollbackStatus.COMPLETED
                self._log(LogLevel.INFO, "Rollback completed successfully", migration_session.id)
            elif successful_steps > 0:
                plan.status = RollbackStatus.PARTIAL
                self._log(LogLevel.WARNING, f"Rollback partially completed: {successful_steps} successful, {failed_steps} failed", migration_session.id)
            else:
                plan.status = RollbackStatus.FAILED
                self._log(LogLevel.ERROR, "Rollback failed completely", migration_session.id)
            
            return plan
            
        except Exception as e:
            if migration_session.id in self._active_rollbacks:
                self._active_rollbacks[migration_session.id].status = RollbackStatus.FAILED
            
            self._log(LogLevel.ERROR, f"Rollback execution failed: {str(e)}", migration_session.id)
            raise RollbackError(f"Failed to execute rollback: {str(e)}")
    
    async def _execute_rollback_step(
        self,
        step: RollbackStep,
        rollback_options: Dict[str, Any]
    ):
        """Execute a single rollback step."""
        backup_info = step.backup_info
        backup_type = backup_info.metadata.get("backup_type", "unknown")
        
        # Create appropriate strategy for restoration
        if backup_type == "file_archive":
            await self._rollback_files(step, rollback_options)
        elif backup_type == "database_dump":
            await self._rollback_database(step, rollback_options)
        elif backup_type == "configuration":
            await self._rollback_configuration(step, rollback_options)
        elif backup_type == "cloud_resources":
            await self._rollback_cloud_resources(step, rollback_options)
        else:
            raise RollbackError(f"Unsupported backup type for rollback: {backup_type}")
    
    async def _rollback_files(self, step: RollbackStep, options: Dict[str, Any]):
        """Rollback file system changes."""
        backup_info = step.backup_info
        
        # Determine restore location
        restore_location = options.get("file_restore_location", "/tmp/rollback_files")
        
        # Create file backup strategy
        system_config = SystemConfig(type=backup_info.source_system, host="")
        strategy = FileBackupStrategy(system_config)
        
        # Restore files
        success = await strategy.restore_backup(backup_info, restore_location, options)
        
        if not success:
            raise RollbackError("File rollback failed")
        
        step.details["restore_location"] = restore_location
    
    async def _rollback_database(self, step: RollbackStep, options: Dict[str, Any]):
        """Rollback database changes."""
        backup_info = step.backup_info
        
        # Get database configuration from options or backup metadata
        db_config_dict = options.get("database_config")
        if not db_config_dict:
            raise RollbackError("Database configuration required for database rollback")
        
        db_config = DatabaseConfig(**db_config_dict)
        
        # Create database backup strategy
        system_config = SystemConfig(type=backup_info.source_system, host="")
        strategy = DatabaseBackupStrategy(system_config, db_config)
        
        # Restore database
        success = await strategy.restore_backup(backup_info, "", options)
        
        if not success:
            raise RollbackError("Database rollback failed")
        
        step.details["database_restored"] = True
    
    async def _rollback_configuration(self, step: RollbackStep, options: Dict[str, Any]):
        """Rollback configuration changes."""
        backup_info = step.backup_info
        
        # Determine restore location
        restore_location = options.get("config_restore_location", "/tmp/rollback_config")
        
        # Create configuration backup strategy
        system_config = SystemConfig(type=backup_info.source_system, host="")
        strategy = ConfigBackupStrategy(system_config)
        
        # Restore configuration
        success = await strategy.restore_backup(backup_info, restore_location, options)
        
        if not success:
            raise RollbackError("Configuration rollback failed")
        
        step.details["config_restored"] = True
    
    async def _rollback_cloud_resources(self, step: RollbackStep, options: Dict[str, Any]):
        """Rollback cloud resource changes."""
        backup_info = step.backup_info
        
        # Create cloud backup strategy
        system_config = SystemConfig(type=backup_info.source_system, host="")
        strategy = CloudBackupStrategy(system_config)
        
        # Note: Cloud resource rollback would require cloud provider-specific implementations
        # This is a placeholder for the actual implementation
        
        step.details["cloud_rollback_attempted"] = True
        
        # For now, just log that cloud rollback was attempted
        self._log(LogLevel.WARNING, "Cloud resource rollback is not fully implemented", 
                 details={"backup_id": backup_info.id})
    
    async def get_rollback_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get rollback status for a migration session."""
        plan = self._active_rollbacks.get(session_id)
        if not plan:
            return None
        
        progress = plan.get_progress()
        
        return {
            "session_id": session_id,
            "status": plan.status.value,
            "created_at": plan.created_at.isoformat(),
            "estimated_duration": plan.estimated_duration,
            "progress": progress,
            "steps": [
                {
                    "step_id": step.step_id,
                    "description": step.description,
                    "status": step.status.value,
                    "start_time": step.start_time.isoformat() if step.start_time else None,
                    "end_time": step.end_time.isoformat() if step.end_time else None,
                    "error": step.error,
                    "details": step.details
                }
                for step in plan.steps
            ]
        }
    
    async def cancel_rollback(self, session_id: str) -> bool:
        """Cancel an ongoing rollback operation."""
        try:
            plan = self._active_rollbacks.get(session_id)
            if not plan:
                return False
            
            if plan.status != RollbackStatus.IN_PROGRESS:
                return False
            
            # Mark current step as failed and stop
            for step in plan.steps:
                if step.status == RollbackStatus.IN_PROGRESS:
                    step.fail("Rollback cancelled by user")
                    break
            
            plan.status = RollbackStatus.FAILED
            
            self._log(LogLevel.INFO, "Rollback cancelled", session_id)
            
            return True
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to cancel rollback: {str(e)}", session_id)
            return False
    
    async def cleanup_rollback_artifacts(self, session_id: str) -> bool:
        """Clean up temporary files and artifacts from rollback operations."""
        try:
            plan = self._active_rollbacks.get(session_id)
            if not plan:
                return False
            
            # Clean up temporary restore locations
            for step in plan.steps:
                restore_location = step.details.get("restore_location")
                if restore_location and restore_location.startswith("/tmp/rollback_"):
                    if os.path.exists(restore_location):
                        shutil.rmtree(restore_location, ignore_errors=True)
            
            # Remove from active rollbacks
            del self._active_rollbacks[session_id]
            
            self._log(LogLevel.INFO, "Rollback artifacts cleaned up", session_id)
            
            return True
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to cleanup rollback artifacts: {str(e)}", session_id)
            return False
    
    async def generate_rollback_guidance(
        self,
        migration_session: MigrationSession,
        validation_results: Optional[Dict[str, ValidationResult]] = None
    ) -> Dict[str, Any]:
        """Generate manual recovery guidance for complex scenarios."""
        try:
            guidance = {
                "session_id": migration_session.id,
                "automatic_rollback_possible": True,
                "manual_steps_required": [],
                "prerequisites": [],
                "warnings": [],
                "estimated_complexity": "low",
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Check if automatic rollback is possible
            if not migration_session.backups:
                guidance["automatic_rollback_possible"] = False
                guidance["manual_steps_required"].append(
                    "No backups available - manual system restoration required"
                )
                guidance["estimated_complexity"] = "high"
            
            # Analyze validation results if provided
            if validation_results:
                failed_validations = [
                    backup_id for backup_id, result in validation_results.items()
                    if not result.is_valid
                ]
                
                if failed_validations:
                    guidance["warnings"].append(
                        f"Backup validation failed for: {failed_validations}"
                    )
                    guidance["estimated_complexity"] = "medium"
            
            # Generate specific guidance based on backup types
            backup_types = set()
            for backup in migration_session.backups:
                backup_type = backup.metadata.get("backup_type", "unknown")
                backup_types.add(backup_type)
            
            if "database_dump" in backup_types:
                guidance["prerequisites"].append(
                    "Ensure database server is running and accessible"
                )
                guidance["manual_steps_required"].append(
                    "Verify database credentials and permissions"
                )
            
            if "file_archive" in backup_types:
                guidance["prerequisites"].append(
                    "Ensure sufficient disk space for file restoration"
                )
                guidance["manual_steps_required"].append(
                    "Stop application services before file restoration"
                )
            
            if "cloud_resources" in backup_types:
                guidance["manual_steps_required"].append(
                    "Cloud resource rollback requires manual intervention using cloud provider tools"
                )
                guidance["estimated_complexity"] = "high"
            
            # Add general recommendations
            guidance["manual_steps_required"].extend([
                "Create a snapshot of current system state before rollback",
                "Notify users about potential service interruption",
                "Test restored system functionality after rollback",
                "Update monitoring and alerting systems"
            ])
            
            return guidance
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to generate rollback guidance: {str(e)}", migration_session.id)
            raise RollbackError(f"Failed to generate rollback guidance: {str(e)}")
    
    def get_logs(self, session_id: Optional[str] = None) -> List[LogEntry]:
        """Get rollback operation logs."""
        if session_id:
            return [
                log for log in self._rollback_logs 
                if log.details.get("session_id") == session_id
            ]
        return self._rollback_logs.copy()
    
    def clear_logs(self):
        """Clear rollback operation logs."""
        self._rollback_logs.clear()
    
    async def get_rollback_statistics(self) -> Dict[str, Any]:
        """Get rollback operation statistics."""
        try:
            stats = {
                "total_rollbacks": len(self._active_rollbacks),
                "rollback_status_counts": {},
                "average_steps_per_rollback": 0,
                "success_rate": 0.0,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            if not self._active_rollbacks:
                return stats
            
            # Count rollbacks by status
            status_counts = {}
            total_steps = 0
            successful_rollbacks = 0
            
            for plan in self._active_rollbacks.values():
                status = plan.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                total_steps += len(plan.steps)
                
                if plan.status == RollbackStatus.COMPLETED:
                    successful_rollbacks += 1
            
            stats["rollback_status_counts"] = status_counts
            stats["average_steps_per_rollback"] = total_steps / len(self._active_rollbacks)
            stats["success_rate"] = (successful_rollbacks / len(self._active_rollbacks)) * 100
            
            return stats
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to get rollback statistics: {str(e)}")
            raise RollbackError(f"Failed to get rollback statistics: {str(e)}")