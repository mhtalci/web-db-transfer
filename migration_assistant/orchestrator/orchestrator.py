"""
Main migration orchestrator for coordinating the entire migration process.

This module provides the MigrationOrchestrator class that coordinates
validation, backup, transfer, database migration, and monitoring with
proper error handling and rollback capabilities.
"""

import asyncio
import logging
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from migration_assistant.models.config import MigrationConfig
from migration_assistant.models.session import (
    MigrationSession, MigrationStep, MigrationStatus, StepStatus,
    LogLevel, ErrorInfo, ErrorSeverity, ProgressInfo, BackupInfo,
    ValidationResult as SessionValidationResult
)
from migration_assistant.core.exceptions import (
    MigrationAssistantError, ValidationError, TransferError,
    DatabaseError, BackupError, RollbackError
)
from migration_assistant.validation.engine import ValidationEngine, ValidationSummary
from migration_assistant.backup.manager import BackupManager
from migration_assistant.transfer.factory import TransferMethodFactory
from migration_assistant.database.factory import DatabaseMigrationFactory
from migration_assistant.backup.rollback import RollbackManager

logger = logging.getLogger(__name__)


class OrchestrationPhase(str, Enum):
    """Migration orchestration phases."""
    INITIALIZATION = "initialization"
    VALIDATION = "validation"
    BACKUP = "backup"
    MAINTENANCE_MODE = "maintenance_mode"
    TRANSFER = "transfer"
    DATABASE_MIGRATION = "database_migration"
    POST_VALIDATION = "post_validation"
    CLEANUP = "cleanup"
    ROLLBACK = "rollback"


class MigrationOrchestrator:
    """
    Main orchestrator for coordinating the entire migration process.
    
    This class manages the step-by-step execution of migrations with proper
    error handling, progress tracking, and rollback capabilities.
    """
    
    def __init__(
        self,
        console: Optional[Console] = None,
        backup_manager: Optional[BackupManager] = None,
        rollback_manager: Optional[RollbackManager] = None
    ):
        """
        Initialize the migration orchestrator.
        
        Args:
            console: Rich console for formatted output (optional)
            backup_manager: Backup manager instance (optional)
            rollback_manager: Rollback manager instance (optional)
        """
        self.console = console or Console()
        self.backup_manager = backup_manager
        self.rollback_manager = rollback_manager
        
        # Validation engine
        self.validation_engine = ValidationEngine(console=self.console)
        
        # Active sessions
        self._active_sessions: Dict[str, MigrationSession] = {}
        
        # Progress callbacks
        self._progress_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Step definitions
        self._step_definitions = self._initialize_step_definitions()
    
    def _initialize_step_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Initialize migration step definitions."""
        return {
            "initialize": {
                "name": "Initialize Migration",
                "description": "Initialize migration session and validate configuration",
                "phase": OrchestrationPhase.INITIALIZATION,
                "required": True,
                "dependencies": []
            },
            "validate_pre_migration": {
                "name": "Pre-Migration Validation",
                "description": "Validate connectivity, compatibility, and dependencies",
                "phase": OrchestrationPhase.VALIDATION,
                "required": True,
                "dependencies": ["initialize"]
            },
            "create_backups": {
                "name": "Create Backups",
                "description": "Create backups of source and destination systems",
                "phase": OrchestrationPhase.BACKUP,
                "required": False,
                "dependencies": ["validate_pre_migration"]
            },
            "enable_maintenance_mode": {
                "name": "Enable Maintenance Mode",
                "description": "Activate maintenance mode on destination system",
                "phase": OrchestrationPhase.MAINTENANCE_MODE,
                "required": False,
                "dependencies": ["create_backups"]
            },
            "transfer_files": {
                "name": "Transfer Files",
                "description": "Transfer files from source to destination",
                "phase": OrchestrationPhase.TRANSFER,
                "required": False,
                "dependencies": ["enable_maintenance_mode"]
            },
            "migrate_database": {
                "name": "Migrate Database",
                "description": "Migrate database from source to destination",
                "phase": OrchestrationPhase.DATABASE_MIGRATION,
                "required": False,
                "dependencies": ["transfer_files"]
            },
            "validate_post_migration": {
                "name": "Post-Migration Validation",
                "description": "Validate migration results and data integrity",
                "phase": OrchestrationPhase.POST_VALIDATION,
                "required": True,
                "dependencies": ["migrate_database"]
            },
            "disable_maintenance_mode": {
                "name": "Disable Maintenance Mode",
                "description": "Deactivate maintenance mode on destination system",
                "phase": OrchestrationPhase.CLEANUP,
                "required": False,
                "dependencies": ["validate_post_migration"]
            },
            "cleanup": {
                "name": "Cleanup",
                "description": "Clean up temporary files and resources",
                "phase": OrchestrationPhase.CLEANUP,
                "required": True,
                "dependencies": ["disable_maintenance_mode"]
            }
        }
    
    def add_progress_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add a progress callback function."""
        self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Remove a progress callback function."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    def _notify_progress(self, session_id: str, progress_data: Dict[str, Any]):
        """Notify all progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(session_id, progress_data)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    async def create_migration_session(
        self,
        config: MigrationConfig,
        session_id: Optional[str] = None
    ) -> MigrationSession:
        """
        Create a new migration session.
        
        Args:
            config: Migration configuration
            session_id: Optional session ID (generates UUID if not provided)
            
        Returns:
            Created migration session
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Create migration session
        session = MigrationSession(
            id=session_id,
            config=config,
            status=MigrationStatus.PENDING
        )
        
        # Initialize steps based on configuration
        steps = self._create_migration_steps(config)
        for step in steps:
            session.add_step(step)
        
        # Store session
        self._active_sessions[session_id] = session
        
        session.add_log(LogLevel.INFO, f"Migration session created: {config.name}")
        
        return session
    
    def _create_migration_steps(self, config: MigrationConfig) -> List[MigrationStep]:
        """Create migration steps based on configuration."""
        steps = []
        
        for step_id, step_def in self._step_definitions.items():
            # Determine if step is needed based on configuration
            if self._is_step_needed(step_id, config):
                step = MigrationStep(
                    id=step_id,
                    name=step_def["name"],
                    description=step_def["description"],
                    dependencies=step_def["dependencies"],
                    metadata={
                        "phase": step_def["phase"].value,
                        "required": step_def["required"]
                    }
                )
                steps.append(step)
        
        return steps
    
    def _is_step_needed(self, step_id: str, config: MigrationConfig) -> bool:
        """Determine if a step is needed based on configuration."""
        # Always include required steps
        if self._step_definitions[step_id]["required"]:
            return True
        
        # Check specific step requirements
        if step_id == "create_backups":
            return config.options.backup_before or config.options.backup_destination
        
        elif step_id == "enable_maintenance_mode" or step_id == "disable_maintenance_mode":
            return config.options.maintenance_mode
        
        elif step_id == "transfer_files":
            # Include if source has files to transfer
            return bool(config.source.paths.root_path)
        
        elif step_id == "migrate_database":
            # Include if source has database configuration
            return config.source.database is not None
        
        return True
    
    async def execute_migration(
        self,
        session_id: str,
        show_progress: bool = True,
        auto_rollback: bool = True
    ) -> MigrationSession:
        """
        Execute a migration session.
        
        Args:
            session_id: Migration session ID
            show_progress: Whether to show progress indicators
            auto_rollback: Whether to automatically rollback on failure
            
        Returns:
            Updated migration session
            
        Raises:
            MigrationAssistantError: If migration fails
        """
        session = self._active_sessions.get(session_id)
        if not session:
            raise MigrationAssistantError(f"Migration session not found: {session_id}")
        
        try:
            session.start()
            session.add_log(LogLevel.INFO, "Starting migration execution")
            
            if show_progress:
                self.console.print(Panel.fit(
                    f"🚀 [bold blue]Starting Migration[/bold blue]\n"
                    f"Session: [bold]{session_id}[/bold]\n"
                    f"Migration: [bold]{session.config.name}[/bold]\n"
                    f"Source: {session.config.source.type.value} → "
                    f"Destination: {session.config.destination.type.value}",
                    title="Migration Execution",
                    border_style="blue"
                ))
            
            # Execute steps in order
            await self._execute_migration_steps(session, show_progress)
            
            # Mark session as completed
            session.complete()
            session.add_log(LogLevel.INFO, "Migration completed successfully")
            
            if show_progress:
                self.console.print(Panel.fit(
                    "✅ [bold green]Migration Completed Successfully[/bold green]",
                    title="Migration Result",
                    border_style="green"
                ))
            
            return session
            
        except Exception as e:
            session.add_log(LogLevel.ERROR, f"Migration failed: {str(e)}")
            
            # Create error info
            error_info = ErrorInfo(
                code="MIGRATION_FAILED",
                message=str(e),
                severity=ErrorSeverity.CRITICAL,
                component="MigrationOrchestrator",
                rollback_required=auto_rollback
            )
            
            session.fail(error_info)
            
            # Attempt rollback if enabled
            if auto_rollback:
                try:
                    await self._rollback_migration(session)
                except Exception as rollback_error:
                    session.add_log(LogLevel.ERROR, f"Rollback failed: {str(rollback_error)}")
            
            if show_progress:
                self.console.print(Panel.fit(
                    f"❌ [bold red]Migration Failed[/bold red]\n"
                    f"Error: {str(e)}",
                    title="Migration Result",
                    border_style="red"
                ))
            
            raise MigrationAssistantError(f"Migration failed: {str(e)}")
    
    async def _execute_migration_steps(
        self,
        session: MigrationSession,
        show_progress: bool = True
    ):
        """Execute migration steps in dependency order."""
        # Sort steps by dependencies
        sorted_steps = self._sort_steps_by_dependencies(session.steps)
        
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                
                main_task = progress.add_task(
                    "Migration Progress",
                    total=len(sorted_steps)
                )
                
                for i, step in enumerate(sorted_steps):
                    step_task = progress.add_task(
                        f"🔄 {step.name}",
                        total=1
                    )
                    
                    try:
                        await self._execute_step(session, step)
                        progress.update(step_task, completed=1)
                        progress.update(main_task, completed=i + 1)
                        
                    except Exception as e:
                        progress.update(step_task, completed=1)
                        raise e
        else:
            # Execute without progress indicators
            for step in sorted_steps:
                await self._execute_step(session, step)
    
    def _sort_steps_by_dependencies(self, steps: List[MigrationStep]) -> List[MigrationStep]:
        """Sort steps by their dependencies using topological sort."""
        # Create a mapping of step IDs to steps
        step_map = {step.id: step for step in steps}
        
        # Topological sort
        visited = set()
        temp_visited = set()
        sorted_steps = []
        
        def visit(step_id: str):
            if step_id in temp_visited:
                raise MigrationAssistantError(f"Circular dependency detected involving step: {step_id}")
            
            if step_id not in visited:
                temp_visited.add(step_id)
                
                step = step_map.get(step_id)
                if step:
                    for dep_id in step.dependencies:
                        if dep_id in step_map:
                            visit(dep_id)
                    
                    temp_visited.remove(step_id)
                    visited.add(step_id)
                    sorted_steps.append(step)
        
        for step in steps:
            if step.id not in visited:
                visit(step.id)
        
        return sorted_steps
    
    async def _execute_step(self, session: MigrationSession, step: MigrationStep):
        """Execute a single migration step."""
        step.start()
        session.current_step = step.id
        session.add_log(LogLevel.INFO, f"Starting step: {step.name}")
        
        # Notify progress callbacks
        self._notify_progress(session.id, {
            "step_id": step.id,
            "step_name": step.name,
            "status": "started",
            "progress": step.progress.dict()
        })
        
        try:
            # Execute step based on its ID
            if step.id == "initialize":
                await self._execute_initialize_step(session, step)
            elif step.id == "validate_pre_migration":
                await self._execute_validation_step(session, step)
            elif step.id == "create_backups":
                await self._execute_backup_step(session, step)
            elif step.id == "enable_maintenance_mode":
                await self._execute_maintenance_mode_step(session, step, enable=True)
            elif step.id == "transfer_files":
                await self._execute_transfer_step(session, step)
            elif step.id == "migrate_database":
                await self._execute_database_migration_step(session, step)
            elif step.id == "validate_post_migration":
                await self._execute_post_validation_step(session, step)
            elif step.id == "disable_maintenance_mode":
                await self._execute_maintenance_mode_step(session, step, enable=False)
            elif step.id == "cleanup":
                await self._execute_cleanup_step(session, step)
            else:
                raise MigrationAssistantError(f"Unknown step: {step.id}")
            
            step.complete()
            session.add_log(LogLevel.INFO, f"Completed step: {step.name}")
            
            # Notify progress callbacks
            self._notify_progress(session.id, {
                "step_id": step.id,
                "step_name": step.name,
                "status": "completed",
                "progress": step.progress.dict()
            })
            
        except Exception as e:
            error_info = ErrorInfo(
                code=f"STEP_FAILED_{step.id.upper()}",
                message=str(e),
                severity=ErrorSeverity.CRITICAL,
                component="MigrationOrchestrator",
                step_id=step.id
            )
            
            step.fail(error_info)
            session.add_log(LogLevel.ERROR, f"Step failed: {step.name} - {str(e)}")
            
            # Notify progress callbacks
            self._notify_progress(session.id, {
                "step_id": step.id,
                "step_name": step.name,
                "status": "failed",
                "error": str(e),
                "progress": step.progress.dict()
            })
            
            raise e
    
    async def _execute_initialize_step(self, session: MigrationSession, step: MigrationStep):
        """Execute initialization step."""
        step.add_log(LogLevel.INFO, "Initializing migration session")
        
        # Validate configuration
        config = session.config
        if not config.source.host:
            raise ValidationError("Source host is required")
        
        if not config.destination.host:
            raise ValidationError("Destination host is required")
        
        # Initialize components based on configuration
        if config.options.backup_before and not self.backup_manager:
            step.add_log(LogLevel.WARNING, "Backup requested but no backup manager configured")
        
        if config.options.rollback_on_failure and not self.rollback_manager:
            step.add_log(LogLevel.WARNING, "Rollback requested but no rollback manager configured")
        
        step.progress.update_progress(1, 1)
        step.add_log(LogLevel.INFO, "Initialization completed")
    
    async def _execute_validation_step(self, session: MigrationSession, step: MigrationStep):
        """Execute pre-migration validation step."""
        step.add_log(LogLevel.INFO, "Starting pre-migration validation")
        
        try:
            # Run validation engine
            validation_summary = await self.validation_engine.validate_migration(
                session.config,
                show_progress=False,
                detailed_output=False
            )
            
            # Store validation results in session
            session.validation_result = SessionValidationResult(
                passed=validation_summary.can_proceed,
                checks_performed=validation_summary.total_checks,
                checks_passed=validation_summary.passed_checks,
                checks_failed=validation_summary.failed_checks,
                warnings=validation_summary.warning_issues,
                estimated_duration=self._parse_time_estimate(validation_summary.estimated_fix_time),
                details=validation_summary.__dict__
            )
            
            if not validation_summary.can_proceed:
                raise ValidationError(
                    f"Pre-migration validation failed with {validation_summary.critical_issues} critical issues"
                )
            
            step.progress.update_progress(1, 1)
            step.add_log(LogLevel.INFO, f"Validation completed: {validation_summary.success_rate:.1f}% success rate")
            
        except Exception as e:
            step.add_log(LogLevel.ERROR, f"Validation failed: {str(e)}")
            raise ValidationError(f"Pre-migration validation failed: {str(e)}")
    
    def _parse_time_estimate(self, time_str: str) -> Optional[int]:
        """Parse time estimate string to seconds."""
        if not time_str or time_str == "No fixes needed":
            return None
        
        try:
            if "minute" in time_str:
                return int(time_str.split()[0]) * 60
            elif "hour" in time_str:
                if "h" in time_str and "m" in time_str:
                    # Format like "2h 30m"
                    parts = time_str.split()
                    hours = int(parts[0].replace("h", ""))
                    minutes = int(parts[1].replace("m", ""))
                    return hours * 3600 + minutes * 60
                else:
                    # Format like "2 hours"
                    return int(time_str.split()[0]) * 3600
        except (ValueError, IndexError):
            pass
        
        return None
    
    async def _execute_backup_step(self, session: MigrationSession, step: MigrationStep):
        """Execute backup creation step."""
        if not self.backup_manager:
            step.add_log(LogLevel.WARNING, "Backup manager not configured, skipping backup")
            step.progress.update_progress(1, 1)
            return
        
        step.add_log(LogLevel.INFO, "Creating backups")
        
        try:
            # Create full system backup
            backup_options = {
                "backup_files": bool(session.config.source.paths.root_path),
                "backup_database": session.config.source.database is not None,
                "backup_config": True,
                "compression": "gzip",
                "exclude_patterns": session.config.source.paths.exclude_patterns
            }
            
            backups = await self.backup_manager.create_full_system_backup(
                session.config,
                backup_options
            )
            
            # Add backups to session
            for backup in backups:
                session.add_backup(backup)
            
            step.progress.update_progress(1, 1)
            step.add_log(LogLevel.INFO, f"Created {len(backups)} backups")
            
        except Exception as e:
            step.add_log(LogLevel.ERROR, f"Backup creation failed: {str(e)}")
            raise BackupError(f"Failed to create backups: {str(e)}")
    
    async def _execute_maintenance_mode_step(
        self,
        session: MigrationSession,
        step: MigrationStep,
        enable: bool
    ):
        """Execute maintenance mode activation/deactivation step."""
        action = "Enabling" if enable else "Disabling"
        step.add_log(LogLevel.INFO, f"{action} maintenance mode")
        
        # This is a placeholder for actual maintenance mode implementation
        # In a real implementation, this would interact with the destination system
        # to enable/disable maintenance mode (e.g., create maintenance.html file,
        # update web server configuration, etc.)
        
        await asyncio.sleep(1)  # Simulate maintenance mode operation
        
        step.progress.update_progress(1, 1)
        step.add_log(LogLevel.INFO, f"Maintenance mode {'enabled' if enable else 'disabled'}")
    
    async def _execute_transfer_step(self, session: MigrationSession, step: MigrationStep):
        """Execute file transfer step."""
        step.add_log(LogLevel.INFO, "Starting file transfer")
        
        try:
            # Create transfer method
            transfer_method = TransferMethodFactory.create_transfer_method(
                session.config.transfer.method.value,
                self._build_transfer_config(session.config)
            )
            
            # Execute transfer
            source_path = session.config.source.paths.root_path
            dest_path = session.config.destination.paths.root_path
            
            # This is a simplified transfer - in reality, this would be more complex
            transfer_result = await transfer_method.transfer_files(
                source_path,
                dest_path,
                {
                    "verify_checksums": session.config.transfer.verify_checksums,
                    "compression": session.config.transfer.compression_enabled,
                    "parallel_transfers": session.config.transfer.parallel_transfers
                }
            )
            
            step.progress.update_progress(1, 1)
            step.add_log(LogLevel.INFO, f"File transfer completed: {transfer_result.get('files_transferred', 0)} files")
            
        except Exception as e:
            step.add_log(LogLevel.ERROR, f"File transfer failed: {str(e)}")
            raise TransferError(f"File transfer failed: {str(e)}")
    
    def _build_transfer_config(self, migration_config: MigrationConfig) -> Dict[str, Any]:
        """Build transfer configuration from migration config."""
        return {
            "source": {
                "host": migration_config.source.host,
                "port": migration_config.source.port,
                "auth": migration_config.source.authentication.dict(),
                "path": migration_config.source.paths.root_path
            },
            "destination": {
                "host": migration_config.destination.host,
                "port": migration_config.destination.port,
                "auth": migration_config.destination.authentication.dict(),
                "path": migration_config.destination.paths.root_path
            },
            "options": migration_config.transfer.dict()
        }
    
    async def _execute_database_migration_step(self, session: MigrationSession, step: MigrationStep):
        """Execute database migration step."""
        if not session.config.source.database:
            step.add_log(LogLevel.INFO, "No database configuration, skipping database migration")
            step.progress.update_progress(1, 1)
            return
        
        step.add_log(LogLevel.INFO, "Starting database migration")
        
        try:
            # Create database migrator
            migrator = DatabaseMigrationFactory.create_migrator(
                session.config.source.database,
                session.config.destination.database
            )
            
            # Execute migration
            migration_result = await migrator.migrate()
            
            step.progress.update_progress(1, 1)
            step.add_log(LogLevel.INFO, f"Database migration completed: {migration_result.get('status', 'success')}")
            
        except Exception as e:
            step.add_log(LogLevel.ERROR, f"Database migration failed: {str(e)}")
            raise DatabaseError(f"Database migration failed: {str(e)}")
    
    async def _execute_post_validation_step(self, session: MigrationSession, step: MigrationStep):
        """Execute post-migration validation step."""
        step.add_log(LogLevel.INFO, "Starting post-migration validation")
        
        # This is a placeholder for post-migration validation
        # In a real implementation, this would verify:
        # - File integrity (checksums)
        # - Database data integrity
        # - Application functionality
        # - Performance benchmarks
        
        await asyncio.sleep(2)  # Simulate validation time
        
        step.progress.update_progress(1, 1)
        step.add_log(LogLevel.INFO, "Post-migration validation completed")
    
    async def _execute_cleanup_step(self, session: MigrationSession, step: MigrationStep):
        """Execute cleanup step."""
        step.add_log(LogLevel.INFO, "Starting cleanup")
        
        # Clean up temporary files, close connections, etc.
        # This is a placeholder for actual cleanup logic
        
        await asyncio.sleep(1)  # Simulate cleanup time
        
        step.progress.update_progress(1, 1)
        step.add_log(LogLevel.INFO, "Cleanup completed")
    
    async def _rollback_migration(self, session: MigrationSession):
        """Rollback a failed migration."""
        if not self.rollback_manager:
            session.add_log(LogLevel.WARNING, "Rollback manager not configured, cannot rollback")
            return
        
        session.add_log(LogLevel.INFO, "Starting migration rollback")
        
        try:
            # Use rollback manager to restore from backups
            rollback_result = await self.rollback_manager.rollback_migration(
                session.backups,
                session.config
            )
            
            if rollback_result.get("success", False):
                session.rollback()
                session.add_log(LogLevel.INFO, "Migration rollback completed successfully")
            else:
                session.add_log(LogLevel.ERROR, f"Migration rollback failed: {rollback_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            session.add_log(LogLevel.ERROR, f"Migration rollback failed: {str(e)}")
            raise RollbackError(f"Migration rollback failed: {str(e)}")
    
    async def cancel_migration(self, session_id: str) -> bool:
        """
        Cancel a running migration.
        
        Args:
            session_id: Migration session ID
            
        Returns:
            True if cancellation was successful
        """
        session = self._active_sessions.get(session_id)
        if not session:
            return False
        
        if session.status not in [MigrationStatus.RUNNING, MigrationStatus.VALIDATING]:
            return False
        
        try:
            session.cancel()
            session.add_log(LogLevel.INFO, "Migration cancelled by user")
            
            # Attempt rollback if configured
            if session.config.options.rollback_on_failure and self.rollback_manager:
                await self._rollback_migration(session)
            
            return True
            
        except Exception as e:
            session.add_log(LogLevel.ERROR, f"Migration cancellation failed: {str(e)}")
            return False
    
    def get_migration_session(self, session_id: str) -> Optional[MigrationSession]:
        """Get migration session by ID."""
        return self._active_sessions.get(session_id)
    
    def list_active_sessions(self) -> List[str]:
        """List active migration session IDs."""
        return list(self._active_sessions.keys())
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get migration session status."""
        session = self._active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            "id": session.id,
            "status": session.status.value,
            "progress": session.get_overall_progress(),
            "current_step": session.current_step,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "duration": session.duration,
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "status": step.status.value,
                    "progress": step.progress.percentage
                }
                for step in session.steps
            ]
        }
    
    def display_session_status(self, session_id: str):
        """Display migration session status using Rich formatting."""
        session = self._active_sessions.get(session_id)
        if not session:
            self.console.print(f"[red]Session not found: {session_id}[/red]")
            return
        
        # Status panel
        status_color = {
            MigrationStatus.PENDING: "yellow",
            MigrationStatus.VALIDATING: "blue",
            MigrationStatus.RUNNING: "blue",
            MigrationStatus.COMPLETED: "green",
            MigrationStatus.FAILED: "red",
            MigrationStatus.CANCELLED: "orange",
            MigrationStatus.ROLLED_BACK: "magenta"
        }.get(session.status, "white")
        
        status_panel = Panel.fit(
            f"Status: [{status_color}]{session.status.value.upper()}[/{status_color}]\n"
            f"Progress: {session.get_overall_progress():.1f}%\n"
            f"Current Step: {session.current_step or 'None'}\n"
            f"Duration: {session.duration or 0:.1f}s",
            title=f"Migration Session: {session_id[:8]}...",
            border_style=status_color
        )
        
        self.console.print(status_panel)
        
        # Steps table
        table = Table(title="Migration Steps")
        table.add_column("Step", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Progress", style="white")
        table.add_column("Duration", style="white")
        
        for step in session.steps:
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
                StepStatus.CANCELLED: "🚫"
            }.get(step.status, "❓")
            
            table.add_row(
                step.name,
                f"{status_icon} {step.status.value}",
                f"{step.progress.percentage:.1f}%",
                f"{step.duration or 0:.1f}s"
            )
        
        self.console.print(table)