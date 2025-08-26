"""
Migration scheduler for managing immediate and cron-based migrations.

This module provides the MigrationScheduler class for scheduling migrations,
managing migration queues, and handling concurrent migration execution.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
import croniter
import json

from migration_assistant.models.config import MigrationConfig
from migration_assistant.models.session import MigrationSession, MigrationStatus, LogEntry, LogLevel
from migration_assistant.core.exceptions import MigrationAssistantError
from migration_assistant.orchestrator.orchestrator import MigrationOrchestrator

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Types of migration schedules."""
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    CRON = "cron"
    RECURRING = "recurring"


class ScheduleStatus(str, Enum):
    """Status of scheduled migrations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class ScheduledMigration:
    """Represents a scheduled migration."""
    id: str
    config: MigrationConfig
    schedule_type: ScheduleType
    scheduled_time: datetime
    status: ScheduleStatus = ScheduleStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    session_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Cron-specific fields
    cron_expression: Optional[str] = None
    next_run: Optional[datetime] = None
    
    # Recurring migration fields
    recurrence_interval: Optional[int] = None  # seconds
    recurrence_end: Optional[datetime] = None
    
    # Execution options
    options: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "config": self.config.model_dump(),
            "schedule_type": self.schedule_type.value,
            "scheduled_time": self.scheduled_time.isoformat(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "session_id": self.session_id,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "cron_expression": self.cron_expression,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "recurrence_interval": self.recurrence_interval,
            "recurrence_end": self.recurrence_end.isoformat() if self.recurrence_end else None,
            "options": self.options
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledMigration':
        """Create from dictionary."""
        try:
            config = MigrationConfig(**data["config"])
            
            scheduled_migration = cls(
                id=data["id"],
                config=config,
                schedule_type=ScheduleType(data["schedule_type"]),
                scheduled_time=datetime.fromisoformat(data["scheduled_time"]),
                status=ScheduleStatus(data["status"]),
                created_at=datetime.fromisoformat(data["created_at"]),
                session_id=data.get("session_id"),
                error_message=data.get("error_message"),
                retry_count=data.get("retry_count", 0),
                max_retries=data.get("max_retries", 3),
                cron_expression=data.get("cron_expression"),
                recurrence_interval=data.get("recurrence_interval"),
                options=data.get("options", {})
            )
            
            if data.get("started_at"):
                scheduled_migration.started_at = datetime.fromisoformat(data["started_at"])
            
            if data.get("completed_at"):
                scheduled_migration.completed_at = datetime.fromisoformat(data["completed_at"])
            
            if data.get("next_run"):
                scheduled_migration.next_run = datetime.fromisoformat(data["next_run"])
            
            if data.get("recurrence_end"):
                scheduled_migration.recurrence_end = datetime.fromisoformat(data["recurrence_end"])
            
            return scheduled_migration
        except Exception as e:
            logger.error(f"Failed to create ScheduledMigration from dict: {e}")
            raise


class MigrationQueue:
    """Queue for managing concurrent migrations."""
    
    def __init__(self, max_concurrent: int = 3):
        """
        Initialize migration queue.
        
        Args:
            max_concurrent: Maximum number of concurrent migrations
        """
        self.max_concurrent = max_concurrent
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: Dict[str, asyncio.Task] = {}
        self._completed: List[str] = []
        self._failed: List[str] = []
    
    async def add_migration(self, scheduled_migration: ScheduledMigration):
        """Add a migration to the queue."""
        await self._queue.put(scheduled_migration)
    
    def is_running(self, migration_id: str) -> bool:
        """Check if a migration is currently running."""
        return migration_id in self._running
    
    def get_running_count(self) -> int:
        """Get number of currently running migrations."""
        return len(self._running)
    
    def get_queue_size(self) -> int:
        """Get number of migrations waiting in queue."""
        return self._queue.qsize()
    
    def get_status(self) -> Dict[str, Any]:
        """Get queue status."""
        return {
            "max_concurrent": self.max_concurrent,
            "running_count": self.get_running_count(),
            "queue_size": self.get_queue_size(),
            "running_migrations": list(self._running.keys()),
            "completed_count": len(self._completed),
            "failed_count": len(self._failed)
        }


class MigrationScheduler:
    """
    Scheduler for managing immediate and cron-based migrations.
    
    This class provides functionality to schedule migrations for immediate
    execution, delayed execution, or recurring execution based on cron
    expressions or intervals.
    """
    
    def __init__(
        self,
        orchestrator: MigrationOrchestrator,
        max_concurrent_migrations: int = 3,
        persistence_file: Optional[str] = None
    ):
        """
        Initialize the migration scheduler.
        
        Args:
            orchestrator: Migration orchestrator instance
            max_concurrent_migrations: Maximum concurrent migrations
            persistence_file: File to persist scheduled migrations
        """
        self.orchestrator = orchestrator
        self.max_concurrent_migrations = max_concurrent_migrations
        self.persistence_file = persistence_file
        
        # Scheduled migrations storage
        self._scheduled_migrations: Dict[str, ScheduledMigration] = {}
        
        # Migration queue
        self._migration_queue = MigrationQueue(max_concurrent_migrations)
        
        # Scheduler task
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks
        self._schedule_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Logs
        self._scheduler_logs: List[LogEntry] = []
        
        # Load persisted schedules
        if self.persistence_file:
            self._load_scheduled_migrations()
    
    def _log(self, level: LogLevel, message: str, migration_id: Optional[str] = None, **kwargs):
        """Add a log entry."""
        log_entry = LogEntry(
            level=level,
            message=message,
            component="MigrationScheduler",
            details={"migration_id": migration_id, **kwargs}
        )
        self._scheduler_logs.append(log_entry)
    
    def add_schedule_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add a schedule event callback."""
        self._schedule_callbacks.append(callback)
    
    def remove_schedule_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Remove a schedule event callback."""
        if callback in self._schedule_callbacks:
            self._schedule_callbacks.remove(callback)
    
    def _notify_schedule_event(self, migration_id: str, event_data: Dict[str, Any]):
        """Notify schedule event callbacks."""
        for callback in self._schedule_callbacks:
            try:
                callback(migration_id, event_data)
            except Exception as e:
                logger.warning(f"Schedule callback failed: {e}")
    
    async def start_scheduler(self):
        """Start the migration scheduler."""
        if self._running:
            self._log(LogLevel.WARNING, "Scheduler is already running")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._log(LogLevel.INFO, "Migration scheduler started")
    
    async def stop_scheduler(self):
        """Stop the migration scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        self._log(LogLevel.INFO, "Migration scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Check for due migrations
                await self._check_due_migrations()
                
                # Process migration queue
                await self._process_migration_queue()
                
                # Clean up completed tasks
                await self._cleanup_completed_tasks()
                
                # Wait before next iteration
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log(LogLevel.ERROR, f"Scheduler loop error: {str(e)}")
                await asyncio.sleep(30)  # Wait longer on error
    
    async def _check_due_migrations(self):
        """Check for migrations that are due to run."""
        current_time = datetime.now(UTC)
        
        for migration_id, scheduled_migration in list(self._scheduled_migrations.items()):
            if (scheduled_migration.status == ScheduleStatus.PENDING and
                scheduled_migration.scheduled_time <= current_time):
                
                # Add to queue for execution
                await self._migration_queue.add_migration(scheduled_migration)
                scheduled_migration.status = ScheduleStatus.RUNNING
                
                self._log(LogLevel.INFO, f"Migration queued for execution", migration_id)
                
                # Update next run time for recurring migrations
                if scheduled_migration.schedule_type in [ScheduleType.CRON, ScheduleType.RECURRING]:
                    self._schedule_next_run(scheduled_migration)
    
    def _schedule_next_run(self, scheduled_migration: ScheduledMigration):
        """Schedule the next run for recurring migrations."""
        if scheduled_migration.schedule_type == ScheduleType.CRON and scheduled_migration.cron_expression:
            # Calculate next run using cron expression
            cron = croniter.croniter(scheduled_migration.cron_expression, datetime.now(UTC))
            next_run = cron.get_next(datetime)
            
            # Check if we should continue recurring
            if (scheduled_migration.recurrence_end is None or 
                next_run <= scheduled_migration.recurrence_end):
                
                # Create new scheduled migration for next run
                next_migration = ScheduledMigration(
                    id=str(uuid.uuid4()),
                    config=scheduled_migration.config,
                    schedule_type=ScheduleType.CRON,
                    scheduled_time=next_run,
                    cron_expression=scheduled_migration.cron_expression,
                    recurrence_end=scheduled_migration.recurrence_end,
                    max_retries=scheduled_migration.max_retries,
                    options=scheduled_migration.options.copy()
                )
                
                self._scheduled_migrations[next_migration.id] = next_migration
                self._log(LogLevel.INFO, f"Scheduled next cron run", next_migration.id, next_run=next_run.isoformat())
        
        elif (scheduled_migration.schedule_type == ScheduleType.RECURRING and 
              scheduled_migration.recurrence_interval):
            
            # Calculate next run using interval
            next_run = datetime.now(UTC) + timedelta(seconds=scheduled_migration.recurrence_interval)
            
            # Check if we should continue recurring
            if (scheduled_migration.recurrence_end is None or 
                next_run <= scheduled_migration.recurrence_end):
                
                # Create new scheduled migration for next run
                next_migration = ScheduledMigration(
                    id=str(uuid.uuid4()),
                    config=scheduled_migration.config,
                    schedule_type=ScheduleType.RECURRING,
                    scheduled_time=next_run,
                    recurrence_interval=scheduled_migration.recurrence_interval,
                    recurrence_end=scheduled_migration.recurrence_end,
                    max_retries=scheduled_migration.max_retries,
                    options=scheduled_migration.options.copy()
                )
                
                self._scheduled_migrations[next_migration.id] = next_migration
                self._log(LogLevel.INFO, f"Scheduled next recurring run", next_migration.id, next_run=next_run.isoformat())
    
    async def _process_migration_queue(self):
        """Process migrations from the queue."""
        while (self._migration_queue.get_running_count() < self.max_concurrent_migrations and
               not self._migration_queue._queue.empty()):
            
            try:
                scheduled_migration = await asyncio.wait_for(
                    self._migration_queue._queue.get(),
                    timeout=1.0
                )
                
                # Start migration execution
                task = asyncio.create_task(
                    self._execute_scheduled_migration(scheduled_migration)
                )
                
                self._migration_queue._running[scheduled_migration.id] = task
                
            except asyncio.TimeoutError:
                break
            except Exception as e:
                self._log(LogLevel.ERROR, f"Error processing migration queue: {str(e)}")
    
    async def _cleanup_completed_tasks(self):
        """Clean up completed migration tasks."""
        completed_tasks = []
        
        for migration_id, task in self._migration_queue._running.items():
            if task.done():
                completed_tasks.append(migration_id)
                
                try:
                    await task  # Get any exceptions
                    self._migration_queue._completed.append(migration_id)
                except Exception as e:
                    self._migration_queue._failed.append(migration_id)
                    self._log(LogLevel.ERROR, f"Migration task failed", migration_id, error=str(e))
        
        # Remove completed tasks
        for migration_id in completed_tasks:
            del self._migration_queue._running[migration_id]
    
    async def _execute_scheduled_migration(self, scheduled_migration: ScheduledMigration):
        """Execute a scheduled migration."""
        migration_id = scheduled_migration.id
        
        try:
            self._log(LogLevel.INFO, f"Starting scheduled migration execution", migration_id)
            
            scheduled_migration.started_at = datetime.now(UTC)
            scheduled_migration.status = ScheduleStatus.RUNNING
            
            # Notify callbacks
            self._notify_schedule_event(migration_id, {
                "event": "migration_started",
                "migration_id": migration_id,
                "config_name": scheduled_migration.config.name
            })
            
            # Create migration session
            session = await self.orchestrator.create_migration_session(
                scheduled_migration.config,
                session_id=str(uuid.uuid4())
            )
            
            scheduled_migration.session_id = session.id
            
            # Execute migration
            await self.orchestrator.execute_migration(
                session.id,
                show_progress=scheduled_migration.options.get("show_progress", False),
                auto_rollback=scheduled_migration.options.get("auto_rollback", True)
            )
            
            # Mark as completed
            scheduled_migration.completed_at = datetime.now(UTC)
            scheduled_migration.status = ScheduleStatus.COMPLETED
            
            self._log(LogLevel.INFO, f"Scheduled migration completed successfully", migration_id)
            
            # Notify callbacks
            self._notify_schedule_event(migration_id, {
                "event": "migration_completed",
                "migration_id": migration_id,
                "session_id": session.id,
                "duration": (scheduled_migration.completed_at - scheduled_migration.started_at).total_seconds()
            })
            
        except Exception as e:
            # Handle migration failure
            scheduled_migration.completed_at = datetime.now(UTC)
            scheduled_migration.status = ScheduleStatus.FAILED
            scheduled_migration.error_message = str(e)
            
            self._log(LogLevel.ERROR, f"Scheduled migration failed", migration_id, error=str(e))
            
            # Notify callbacks
            self._notify_schedule_event(migration_id, {
                "event": "migration_failed",
                "migration_id": migration_id,
                "error": str(e),
                "retry_count": scheduled_migration.retry_count
            })
            
            # Handle retries
            if scheduled_migration.retry_count < scheduled_migration.max_retries:
                await self._schedule_retry(scheduled_migration)
            
            raise e
        
        finally:
            # Persist changes
            if self.persistence_file:
                self._save_scheduled_migrations()
    
    async def _schedule_retry(self, scheduled_migration: ScheduledMigration):
        """Schedule a retry for a failed migration."""
        scheduled_migration.retry_count += 1
        
        # Calculate retry delay (exponential backoff)
        delay_minutes = 2 ** scheduled_migration.retry_count  # 2, 4, 8 minutes
        retry_time = datetime.now(UTC) + timedelta(minutes=delay_minutes)
        
        # Create retry migration
        retry_migration = ScheduledMigration(
            id=str(uuid.uuid4()),
            config=scheduled_migration.config,
            schedule_type=ScheduleType.DELAYED,
            scheduled_time=retry_time,
            retry_count=scheduled_migration.retry_count,
            max_retries=scheduled_migration.max_retries,
            options=scheduled_migration.options.copy()
        )
        
        self._scheduled_migrations[retry_migration.id] = retry_migration
        
        self._log(LogLevel.INFO, f"Scheduled migration retry", retry_migration.id, 
                 retry_count=scheduled_migration.retry_count, retry_time=retry_time.isoformat())
    
    def schedule_immediate_migration(
        self,
        config: MigrationConfig,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a migration for immediate execution.
        
        Args:
            config: Migration configuration
            options: Execution options
            
        Returns:
            Scheduled migration ID
        """
        migration_id = str(uuid.uuid4())
        options = options or {}
        
        scheduled_migration = ScheduledMigration(
            id=migration_id,
            config=config,
            schedule_type=ScheduleType.IMMEDIATE,
            scheduled_time=datetime.now(UTC),
            options=options
        )
        
        self._scheduled_migrations[migration_id] = scheduled_migration
        
        self._log(LogLevel.INFO, f"Scheduled immediate migration", migration_id, config_name=config.name)
        
        # Persist changes
        if self.persistence_file:
            self._save_scheduled_migrations()
        
        return migration_id
    
    def schedule_delayed_migration(
        self,
        config: MigrationConfig,
        scheduled_time: datetime,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a migration for delayed execution.
        
        Args:
            config: Migration configuration
            scheduled_time: When to execute the migration
            options: Execution options
            
        Returns:
            Scheduled migration ID
        """
        migration_id = str(uuid.uuid4())
        options = options or {}
        
        scheduled_migration = ScheduledMigration(
            id=migration_id,
            config=config,
            schedule_type=ScheduleType.DELAYED,
            scheduled_time=scheduled_time,
            options=options
        )
        
        self._scheduled_migrations[migration_id] = scheduled_migration
        
        self._log(LogLevel.INFO, f"Scheduled delayed migration", migration_id, 
                 config_name=config.name, scheduled_time=scheduled_time.isoformat())
        
        # Persist changes
        if self.persistence_file:
            self._save_scheduled_migrations()
        
        return migration_id
    
    def schedule_cron_migration(
        self,
        config: MigrationConfig,
        cron_expression: str,
        end_time: Optional[datetime] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a migration using cron expression.
        
        Args:
            config: Migration configuration
            cron_expression: Cron expression for scheduling
            end_time: When to stop recurring (optional)
            options: Execution options
            
        Returns:
            Scheduled migration ID
            
        Raises:
            ValueError: If cron expression is invalid
        """
        migration_id = str(uuid.uuid4())
        options = options or {}
        
        # Validate cron expression
        try:
            cron = croniter.croniter(cron_expression)
            next_run = cron.get_next(datetime)
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {cron_expression}") from e
        
        scheduled_migration = ScheduledMigration(
            id=migration_id,
            config=config,
            schedule_type=ScheduleType.CRON,
            scheduled_time=next_run,
            cron_expression=cron_expression,
            recurrence_end=end_time,
            options=options
        )
        
        self._scheduled_migrations[migration_id] = scheduled_migration
        
        self._log(LogLevel.INFO, f"Scheduled cron migration", migration_id,
                 config_name=config.name, cron_expression=cron_expression, next_run=next_run.isoformat())
        
        # Persist changes
        if self.persistence_file:
            self._save_scheduled_migrations()
        
        return migration_id
    
    def schedule_recurring_migration(
        self,
        config: MigrationConfig,
        interval_seconds: int,
        end_time: Optional[datetime] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Schedule a recurring migration with fixed interval.
        
        Args:
            config: Migration configuration
            interval_seconds: Interval between executions in seconds
            end_time: When to stop recurring (optional)
            options: Execution options
            
        Returns:
            Scheduled migration ID
        """
        migration_id = str(uuid.uuid4())
        options = options or {}
        
        next_run = datetime.now(UTC) + timedelta(seconds=interval_seconds)
        
        scheduled_migration = ScheduledMigration(
            id=migration_id,
            config=config,
            schedule_type=ScheduleType.RECURRING,
            scheduled_time=next_run,
            recurrence_interval=interval_seconds,
            recurrence_end=end_time,
            options=options
        )
        
        self._scheduled_migrations[migration_id] = scheduled_migration
        
        self._log(LogLevel.INFO, f"Scheduled recurring migration", migration_id,
                 config_name=config.name, interval_seconds=interval_seconds, next_run=next_run.isoformat())
        
        # Persist changes
        if self.persistence_file:
            self._save_scheduled_migrations()
        
        return migration_id
    
    def cancel_scheduled_migration(self, migration_id: str) -> bool:
        """
        Cancel a scheduled migration.
        
        Args:
            migration_id: Scheduled migration ID
            
        Returns:
            True if cancellation was successful
        """
        scheduled_migration = self._scheduled_migrations.get(migration_id)
        if not scheduled_migration:
            return False
        
        if scheduled_migration.status in [ScheduleStatus.COMPLETED, ScheduleStatus.CANCELLED]:
            return False
        
        # Cancel running migration if applicable
        if scheduled_migration.status == ScheduleStatus.RUNNING and scheduled_migration.session_id:
            asyncio.create_task(self.orchestrator.cancel_migration(scheduled_migration.session_id))
        
        scheduled_migration.status = ScheduleStatus.CANCELLED
        scheduled_migration.completed_at = datetime.now(UTC)
        
        self._log(LogLevel.INFO, f"Cancelled scheduled migration", migration_id)
        
        # Persist changes
        if self.persistence_file:
            self._save_scheduled_migrations()
        
        return True
    
    def get_scheduled_migration(self, migration_id: str) -> Optional[ScheduledMigration]:
        """Get scheduled migration by ID."""
        return self._scheduled_migrations.get(migration_id)
    
    def list_scheduled_migrations(
        self,
        status: Optional[ScheduleStatus] = None,
        schedule_type: Optional[ScheduleType] = None
    ) -> List[ScheduledMigration]:
        """
        List scheduled migrations with optional filtering.
        
        Args:
            status: Filter by status (optional)
            schedule_type: Filter by schedule type (optional)
            
        Returns:
            List of scheduled migrations
        """
        migrations = list(self._scheduled_migrations.values())
        
        if status:
            migrations = [m for m in migrations if m.status == status]
        
        if schedule_type:
            migrations = [m for m in migrations if m.schedule_type == schedule_type]
        
        # Sort by scheduled time
        migrations.sort(key=lambda m: m.scheduled_time)
        
        return migrations
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status information."""
        return {
            "running": self._running,
            "max_concurrent_migrations": self.max_concurrent_migrations,
            "queue_status": self._migration_queue.get_status(),
            "scheduled_migrations": {
                "total": len(self._scheduled_migrations),
                "pending": len([m for m in self._scheduled_migrations.values() if m.status == ScheduleStatus.PENDING]),
                "running": len([m for m in self._scheduled_migrations.values() if m.status == ScheduleStatus.RUNNING]),
                "completed": len([m for m in self._scheduled_migrations.values() if m.status == ScheduleStatus.COMPLETED]),
                "failed": len([m for m in self._scheduled_migrations.values() if m.status == ScheduleStatus.FAILED]),
                "cancelled": len([m for m in self._scheduled_migrations.values() if m.status == ScheduleStatus.CANCELLED])
            }
        }
    
    def _save_scheduled_migrations(self):
        """Save scheduled migrations to persistence file."""
        if not self.persistence_file:
            return
        
        try:
            data = {
                migration_id: migration.to_dict()
                for migration_id, migration in self._scheduled_migrations.items()
            }
            
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to save scheduled migrations: {str(e)}")
    
    def _load_scheduled_migrations(self):
        """Load scheduled migrations from persistence file."""
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return
        
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
            
            loaded_count = 0
            for migration_id, migration_data in data.items():
                try:
                    migration = ScheduledMigration.from_dict(migration_data)
                    self._scheduled_migrations[migration_id] = migration
                    loaded_count += 1
                except Exception as e:
                    self._log(LogLevel.ERROR, f"Failed to load scheduled migration {migration_id}: {str(e)}")
                    logger.error(f"Failed to load scheduled migration {migration_id}: {str(e)}")
            
            self._log(LogLevel.INFO, f"Loaded {loaded_count} scheduled migrations")
            logger.info(f"Loaded {loaded_count} scheduled migrations from {self.persistence_file}")
            
        except Exception as e:
            self._log(LogLevel.ERROR, f"Failed to load scheduled migrations: {str(e)}")
            logger.error(f"Failed to load scheduled migrations: {str(e)}")
    
    async def cleanup_old_migrations(self, max_age_days: int = 30) -> int:
        """
        Clean up old completed/failed migrations.
        
        Args:
            max_age_days: Maximum age in days for keeping migrations
            
        Returns:
            Number of migrations cleaned up
        """
        cutoff_time = datetime.now(UTC) - timedelta(days=max_age_days)
        cleaned_count = 0
        
        for migration_id in list(self._scheduled_migrations.keys()):
            migration = self._scheduled_migrations[migration_id]
            
            if (migration.status in [ScheduleStatus.COMPLETED, ScheduleStatus.FAILED, ScheduleStatus.CANCELLED] and
                migration.completed_at and migration.completed_at < cutoff_time):
                
                del self._scheduled_migrations[migration_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            self._log(LogLevel.INFO, f"Cleaned up {cleaned_count} old migrations")
            
            # Persist changes
            if self.persistence_file:
                self._save_scheduled_migrations()
        
        return cleaned_count
    
    def get_logs(self, migration_id: Optional[str] = None) -> List[LogEntry]:
        """Get scheduler logs."""
        if migration_id:
            return [
                log for log in self._scheduler_logs
                if log.details.get("migration_id") == migration_id
            ]
        return self._scheduler_logs.copy()
    
    def clear_logs(self):
        """Clear scheduler logs."""
        self._scheduler_logs.clear()