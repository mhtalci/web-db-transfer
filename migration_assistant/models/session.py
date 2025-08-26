"""
Session models for the Migration Assistant.

This module defines Pydantic models for migration sessions,
steps, logging, and related runtime data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from migration_assistant.models.config import MigrationConfig


class MigrationStatus(str, Enum):
    """Migration session status."""
    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class StepStatus(str, Enum):
    """Migration step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class LogLevel(str, Enum):
    """Log entry levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BackupType(str, Enum):
    """Backup types."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class ReportType(str, Enum):
    """Report types."""
    VALIDATION = "validation"
    PROGRESS = "progress"
    SUMMARY = "summary"
    ERROR = "error"
    PERFORMANCE = "performance"


class LogEntry(BaseModel):
    """Log entry for migration operations."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: LogLevel
    message: str
    component: Optional[str] = None
    step_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    exception: Optional[str] = None
    stack_trace: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorInfo(BaseModel):
    """Error information for failed operations."""
    code: str
    message: str
    severity: ErrorSeverity
    component: Optional[str] = None
    step_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)
    remediation_steps: List[str] = Field(default_factory=list)
    documentation_links: List[str] = Field(default_factory=list)
    retry_possible: bool = False
    rollback_required: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProgressInfo(BaseModel):
    """Progress information for operations."""
    current: int = 0
    total: int = 0
    percentage: float = 0.0
    rate: Optional[float] = None  # items/second or bytes/second
    eta: Optional[int] = None  # seconds remaining
    unit: str = "items"
    details: Dict[str, Any] = Field(default_factory=dict)

    def update_progress(self, current: int, total: Optional[int] = None):
        """Update progress and calculate percentage."""
        self.current = current
        if total is not None:
            self.total = total
        
        if self.total > 0:
            self.percentage = (self.current / self.total) * 100
        else:
            self.percentage = 0.0


class MigrationStep(BaseModel):
    """Individual migration step."""
    id: str
    name: str
    description: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    progress: ProgressInfo = Field(default_factory=ProgressInfo)
    logs: List[LogEntry] = Field(default_factory=list)
    error: Optional[ErrorInfo] = None
    dependencies: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def start(self):
        """Mark step as started."""
        self.status = StepStatus.RUNNING
        self.start_time = datetime.utcnow()

    def complete(self):
        """Mark step as completed."""
        self.status = StepStatus.COMPLETED
        self.end_time = datetime.utcnow()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()

    def fail(self, error: ErrorInfo):
        """Mark step as failed with error information."""
        self.status = StepStatus.FAILED
        self.end_time = datetime.utcnow()
        self.error = error
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()

    def add_log(self, level: LogLevel, message: str, **kwargs):
        """Add a log entry to the step."""
        log_entry = LogEntry(
            level=level,
            message=message,
            step_id=self.id,
            **kwargs
        )
        self.logs.append(log_entry)


class BackupInfo(BaseModel):
    """Backup information."""
    id: str
    type: BackupType
    source_system: str
    location: str
    size: Optional[int] = None  # bytes
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    checksum: Optional[str] = None
    compression_used: bool = False
    encryption_used: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    verified: bool = False
    verification_date: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ReportInfo(BaseModel):
    """Report information."""
    id: str
    type: ReportType
    title: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    format: str = "json"  # json, html, pdf, etc.
    location: Optional[str] = None
    size: Optional[int] = None  # bytes
    summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ValidationResult(BaseModel):
    """Validation result information."""
    passed: bool
    checks_performed: int
    checks_passed: int
    checks_failed: int
    warnings: int
    errors: List[ErrorInfo] = Field(default_factory=list)
    warnings_list: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    estimated_duration: Optional[int] = None  # seconds
    estimated_size: Optional[int] = None  # bytes
    details: Dict[str, Any] = Field(default_factory=dict)


class MigrationSession(BaseModel):
    """Complete migration session."""
    id: str
    config: MigrationConfig
    status: MigrationStatus = MigrationStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    steps: List[MigrationStep] = Field(default_factory=list)
    current_step: Optional[str] = None
    progress: ProgressInfo = Field(default_factory=ProgressInfo)
    logs: List[LogEntry] = Field(default_factory=list)
    backups: List[BackupInfo] = Field(default_factory=list)
    reports: List[ReportInfo] = Field(default_factory=list)
    validation_result: Optional[ValidationResult] = None
    error: Optional[ErrorInfo] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def start(self):
        """Start the migration session."""
        self.status = MigrationStatus.RUNNING
        self.start_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def complete(self):
        """Complete the migration session."""
        self.status = MigrationStatus.COMPLETED
        self.end_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()

    def fail(self, error: ErrorInfo):
        """Fail the migration session."""
        self.status = MigrationStatus.FAILED
        self.end_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.error = error
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()

    def cancel(self):
        """Cancel the migration session."""
        self.status = MigrationStatus.CANCELLED
        self.end_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()

    def rollback(self):
        """Mark session as rolled back."""
        self.status = MigrationStatus.ROLLED_BACK
        self.updated_at = datetime.utcnow()

    def add_step(self, step: MigrationStep):
        """Add a migration step."""
        self.steps.append(step)
        self.updated_at = datetime.utcnow()

    def get_step(self, step_id: str) -> Optional[MigrationStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def add_log(self, level: LogLevel, message: str, **kwargs):
        """Add a log entry to the session."""
        log_entry = LogEntry(
            level=level,
            message=message,
            **kwargs
        )
        self.logs.append(log_entry)
        self.updated_at = datetime.utcnow()

    def add_backup(self, backup: BackupInfo):
        """Add backup information."""
        self.backups.append(backup)
        self.updated_at = datetime.utcnow()

    def add_report(self, report: ReportInfo):
        """Add report information."""
        self.reports.append(report)
        self.updated_at = datetime.utcnow()

    def update_progress(self, current: int, total: Optional[int] = None):
        """Update overall session progress."""
        self.progress.update_progress(current, total)
        self.updated_at = datetime.utcnow()

    def get_overall_progress(self) -> float:
        """Calculate overall progress based on completed steps."""
        if not self.steps:
            return 0.0
        
        completed_steps = sum(1 for step in self.steps if step.status == StepStatus.COMPLETED)
        return (completed_steps / len(self.steps)) * 100