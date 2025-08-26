"""
Comprehensive logging and monitoring system for the Migration Assistant.

This module provides structured logging, audit logging, log rotation,
and monitoring capabilities for both CLI and API interfaces.
"""

import json
import logging
import logging.handlers
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

from rich.console import Console
from rich.logging import RichHandler


class LogLevel(str, Enum):
    """Log levels for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """Categories for structured logging."""
    SYSTEM = "system"
    MIGRATION = "migration"
    VALIDATION = "validation"
    TRANSFER = "transfer"
    DATABASE = "database"
    BACKUP = "backup"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AUDIT = "audit"
    API = "api"
    CLI = "cli"


@dataclass
class LogEntry:
    """Structured log entry with metadata."""
    timestamp: datetime = field(default_factory=datetime.now)
    level: LogLevel = LogLevel.INFO
    category: LogCategory = LogCategory.SYSTEM
    message: str = ""
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    operation: Optional[str] = None
    step: Optional[str] = None
    duration: Optional[float] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert log entry to JSON string."""
        return json.dumps(self.to_dict())


class StructuredFormatter(logging.Formatter):
    """Formatter for structured JSON logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Extract structured data from record
        log_entry = getattr(record, 'log_entry', None)
        
        if log_entry and isinstance(log_entry, LogEntry):
            return log_entry.to_json()
        
        # Fallback to creating log entry from record
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created),
            level=LogLevel(record.levelname),
            message=record.getMessage(),
            metadata={
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
            }
        )
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                          'pathname', 'filename', 'module', 'lineno', 
                          'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process',
                          'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                log_entry.metadata[key] = value
        
        return log_entry.to_json()


class AuditLogger:
    """Specialized logger for audit events."""
    
    def __init__(self, log_file: str):
        self.logger = logging.getLogger("migration_assistant.audit")
        self.logger.setLevel(logging.INFO)
        
        # Create audit log file handler with rotation
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log an audit event."""
        log_entry = LogEntry(
            level=LogLevel.INFO,
            category=LogCategory.AUDIT,
            message=f"Audit event: {event_type}",
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            metadata={
                'event_type': event_type,
                'details': details or {}
            }
        )
        
        self.logger.info(log_entry.message, extra={'log_entry': log_entry})


class PerformanceMonitor:
    """Monitor and log performance metrics."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._metrics: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def record_metric(self, metric_name: str, value: float, metadata: Optional[Dict[str, Any]] = None):
        """Record a performance metric."""
        with self._lock:
            if metric_name not in self._metrics:
                self._metrics[metric_name] = []
            self._metrics[metric_name].append(value)
        
        log_entry = LogEntry(
            level=LogLevel.INFO,
            category=LogCategory.PERFORMANCE,
            message=f"Performance metric: {metric_name} = {value}",
            metadata={
                'metric_name': metric_name,
                'metric_value': value,
                **(metadata or {})
            }
        )
        
        self.logger.info(log_entry.message, extra={'log_entry': log_entry})
    
    def get_metrics_summary(self, metric_name: str) -> Dict[str, float]:
        """Get summary statistics for a metric."""
        with self._lock:
            values = self._metrics.get(metric_name, [])
        
        if not values:
            return {}
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'total': sum(values)
        }
    
    def clear_metrics(self, metric_name: Optional[str] = None):
        """Clear metrics data."""
        with self._lock:
            if metric_name:
                self._metrics.pop(metric_name, None)
            else:
                self._metrics.clear()


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    audit_log_file: Optional[str] = None,
    rich_console: bool = True,
    structured_logging: bool = False,
    log_rotation: bool = True,
    max_log_size: int = 50 * 1024 * 1024,  # 50MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up comprehensive logging configuration for the Migration Assistant.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        audit_log_file: Optional audit log file path
        rich_console: Whether to use Rich console handler for CLI
        structured_logging: Whether to use structured JSON logging
        log_rotation: Whether to enable log rotation
        max_log_size: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    
    Returns:
        Configured logger instance
    """
    # Create main logger
    logger = logging.getLogger("migration_assistant")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    if rich_console and not structured_logging:
        console = Console()
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True
        )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        if structured_logging:
            console_handler.setFormatter(StructuredFormatter())
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        if log_rotation:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_log_size,
                backupCount=backup_count
            )
        else:
            file_handler = logging.FileHandler(log_file)
        
        if structured_logging:
            file_handler.setFormatter(StructuredFormatter())
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
    
    # Set up audit logging if specified
    if audit_log_file:
        audit_logger = AuditLogger(audit_log_file)
        # Store audit logger reference for later use
        logger._audit_logger = audit_logger
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(f"migration_assistant.{name}")


class MigrationLogger:
    """Enhanced logger for migration operations with structured logging support."""
    
    def __init__(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        log_file: Optional[str] = None,
        structured: bool = False
    ):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.structured = structured
        self.logger = get_logger(f"session.{session_id}")
        self.performance_monitor = PerformanceMonitor(self.logger)
        
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            
            if structured:
                file_handler.setFormatter(StructuredFormatter())
            else:
                formatter = logging.Formatter(
                    fmt=f"%(asctime)s - {session_id} - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
                file_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
    
    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.MIGRATION,
        operation: Optional[str] = None,
        step: Optional[str] = None,
        duration: Optional[float] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LogEntry:
        """Create a structured log entry."""
        return LogEntry(
            level=level,
            category=category,
            message=message,
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            operation=operation,
            step=step,
            duration=duration,
            error_code=error_code,
            metadata=metadata or {}
        )
    
    def debug(
        self,
        message: str,
        category: LogCategory = LogCategory.MIGRATION,
        operation: Optional[str] = None,
        step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log debug message."""
        if self.structured:
            log_entry = self._create_log_entry(
                LogLevel.DEBUG, message, category, operation, step, metadata=metadata
            )
            self.logger.debug(message, extra={'log_entry': log_entry})
        else:
            self.logger.debug(message, extra=metadata or {})
    
    def info(
        self,
        message: str,
        category: LogCategory = LogCategory.MIGRATION,
        operation: Optional[str] = None,
        step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log info message."""
        if self.structured:
            log_entry = self._create_log_entry(
                LogLevel.INFO, message, category, operation, step, metadata=metadata
            )
            self.logger.info(message, extra={'log_entry': log_entry})
        else:
            self.logger.info(message, extra=metadata or {})
    
    def warning(
        self,
        message: str,
        category: LogCategory = LogCategory.MIGRATION,
        operation: Optional[str] = None,
        step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log warning message."""
        if self.structured:
            log_entry = self._create_log_entry(
                LogLevel.WARNING, message, category, operation, step, metadata=metadata
            )
            self.logger.warning(message, extra={'log_entry': log_entry})
        else:
            self.logger.warning(message, extra=metadata or {})
    
    def error(
        self,
        message: str,
        category: LogCategory = LogCategory.MIGRATION,
        operation: Optional[str] = None,
        step: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log error message."""
        if self.structured:
            log_entry = self._create_log_entry(
                LogLevel.ERROR, message, category, operation, step, 
                error_code=error_code, metadata=metadata
            )
            self.logger.error(message, extra={'log_entry': log_entry})
        else:
            self.logger.error(message, extra=metadata or {})
    
    def critical(
        self,
        message: str,
        category: LogCategory = LogCategory.MIGRATION,
        operation: Optional[str] = None,
        step: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log critical message."""
        if self.structured:
            log_entry = self._create_log_entry(
                LogLevel.CRITICAL, message, category, operation, step,
                error_code=error_code, metadata=metadata
            )
            self.logger.critical(message, extra={'log_entry': log_entry})
        else:
            self.logger.critical(message, extra=metadata or {})
    
    def step_start(self, step_name: str, operation: Optional[str] = None):
        """Log step start."""
        self.info(
            f"Starting step: {step_name}",
            category=LogCategory.MIGRATION,
            operation=operation,
            step=step_name,
            metadata={'step_status': 'started'}
        )
    
    def step_complete(self, step_name: str, duration: float, operation: Optional[str] = None):
        """Log step completion."""
        self.info(
            f"Completed step: {step_name} (took {duration:.2f}s)",
            category=LogCategory.MIGRATION,
            operation=operation,
            step=step_name,
            metadata={'step_status': 'completed', 'duration': duration}
        )
        
        # Record performance metric
        self.performance_monitor.record_metric(
            f"step_duration_{step_name}",
            duration,
            {'step_name': step_name, 'operation': operation}
        )
    
    def step_failed(self, step_name: str, error: str, operation: Optional[str] = None, error_code: Optional[str] = None):
        """Log step failure."""
        self.error(
            f"Failed step: {step_name} - {error}",
            category=LogCategory.MIGRATION,
            operation=operation,
            step=step_name,
            error_code=error_code,
            metadata={'step_status': 'failed', 'error_details': error}
        )
    
    def log_transfer_progress(
        self,
        transferred_bytes: int,
        total_bytes: int,
        transfer_rate: float,
        operation: str = "file_transfer"
    ):
        """Log file transfer progress."""
        progress_percent = (transferred_bytes / total_bytes) * 100 if total_bytes > 0 else 0
        
        self.info(
            f"Transfer progress: {progress_percent:.1f}% ({transferred_bytes}/{total_bytes} bytes) at {transfer_rate:.2f} MB/s",
            category=LogCategory.TRANSFER,
            operation=operation,
            metadata={
                'transferred_bytes': transferred_bytes,
                'total_bytes': total_bytes,
                'progress_percent': progress_percent,
                'transfer_rate_mbps': transfer_rate
            }
        )
        
        # Record performance metrics
        self.performance_monitor.record_metric("transfer_rate_mbps", transfer_rate)
        self.performance_monitor.record_metric("transfer_progress_percent", progress_percent)
    
    def log_database_operation(
        self,
        operation: str,
        table_name: Optional[str] = None,
        rows_processed: Optional[int] = None,
        duration: Optional[float] = None
    ):
        """Log database operation."""
        message = f"Database operation: {operation}"
        if table_name:
            message += f" on table {table_name}"
        if rows_processed:
            message += f" ({rows_processed} rows)"
        if duration:
            message += f" in {duration:.2f}s"
        
        self.info(
            message,
            category=LogCategory.DATABASE,
            operation=operation,
            metadata={
                'table_name': table_name,
                'rows_processed': rows_processed,
                'operation_type': operation,
                'duration': duration
            }
        )
        
        if duration:
            self.performance_monitor.record_metric(f"db_operation_duration_{operation}", duration)
        if rows_processed:
            self.performance_monitor.record_metric(f"db_rows_processed_{operation}", rows_processed)
    
    def log_validation_result(
        self,
        validation_type: str,
        passed: bool,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log validation result."""
        status = "PASSED" if passed else "FAILED"
        message = f"Validation {validation_type}: {status}"
        
        level = LogLevel.INFO if passed else LogLevel.WARNING
        
        if self.structured:
            log_entry = self._create_log_entry(
                level,
                message,
                LogCategory.VALIDATION,
                operation="validation",
                metadata={
                    'validation_type': validation_type,
                    'validation_passed': passed,
                    'validation_details': details or {}
                }
            )
            getattr(self.logger, level.lower())(message, extra={'log_entry': log_entry})
        else:
            getattr(self.logger, level.lower())(message, extra=details or {})
    
    def log_security_event(
        self,
        event_type: str,
        severity: str = "medium",
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security-related event."""
        message = f"Security event: {event_type} (severity: {severity})"
        
        level = LogLevel.WARNING if severity in ["medium", "high"] else LogLevel.INFO
        
        self._log_with_level(
            level,
            message,
            LogCategory.SECURITY,
            operation="security_monitoring",
            metadata={
                'event_type': event_type,
                'severity': severity,
                'security_details': details or {}
            }
        )
    
    def _log_with_level(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory,
        operation: Optional[str] = None,
        step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Helper method to log with specific level."""
        if self.structured:
            log_entry = self._create_log_entry(
                level, message, category, operation, step, metadata=metadata
            )
            getattr(self.logger, level.lower())(message, extra={'log_entry': log_entry})
        else:
            getattr(self.logger, level.lower())(message, extra=metadata or {})
    
    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics summary."""
        summary = {}
        for metric_name in self.performance_monitor._metrics:
            summary[metric_name] = self.performance_monitor.get_metrics_summary(metric_name)
        return summary


class LogManager:
    """Centralized log management for the Migration Assistant."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.loggers: Dict[str, MigrationLogger] = {}
        self.audit_logger: Optional[AuditLogger] = None
        
        # Set up main logger
        self.main_logger = setup_logging(
            level=self.config.get('level', 'INFO'),
            log_file=self.config.get('log_file'),
            audit_log_file=self.config.get('audit_log_file'),
            rich_console=self.config.get('rich_console', True),
            structured_logging=self.config.get('structured_logging', False),
            log_rotation=self.config.get('log_rotation', True)
        )
        
        # Set up audit logger if configured
        if self.config.get('audit_log_file'):
            self.audit_logger = AuditLogger(self.config['audit_log_file'])
    
    def get_session_logger(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> MigrationLogger:
        """Get or create a session-specific logger."""
        logger_key = f"{session_id}_{tenant_id}_{user_id}"
        
        if logger_key not in self.loggers:
            session_log_file = None
            if self.config.get('session_logs_dir'):
                session_logs_dir = Path(self.config['session_logs_dir'])
                session_logs_dir.mkdir(parents=True, exist_ok=True)
                session_log_file = str(session_logs_dir / f"{session_id}.log")
            
            self.loggers[logger_key] = MigrationLogger(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                log_file=session_log_file,
                structured=self.config.get('structured_logging', False)
            )
        
        return self.loggers[logger_key]
    
    def log_audit_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log an audit event."""
        if self.audit_logger:
            self.audit_logger.log_event(event_type, user_id, session_id, tenant_id, details)
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Clean up session logs
        if self.config.get('session_logs_dir'):
            session_logs_dir = Path(self.config['session_logs_dir'])
            if session_logs_dir.exists():
                for log_file in session_logs_dir.glob("*.log*"):
                    if log_file.stat().st_mtime < cutoff_date.timestamp():
                        try:
                            log_file.unlink()
                            self.main_logger.info(f"Cleaned up old log file: {log_file}")
                        except OSError as e:
                            self.main_logger.warning(f"Failed to clean up log file {log_file}: {e}")
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get logging statistics."""
        stats = {
            'active_sessions': len(self.loggers),
            'audit_logging_enabled': self.audit_logger is not None,
            'structured_logging': self.config.get('structured_logging', False),
            'log_rotation_enabled': self.config.get('log_rotation', True)
        }
        
        # Add log file sizes if available
        if self.config.get('log_file'):
            log_file = Path(self.config['log_file'])
            if log_file.exists():
                stats['main_log_size_mb'] = log_file.stat().st_size / (1024 * 1024)
        
        if self.config.get('audit_log_file'):
            audit_log_file = Path(self.config['audit_log_file'])
            if audit_log_file.exists():
                stats['audit_log_size_mb'] = audit_log_file.stat().st_size / (1024 * 1024)
        
        return stats