"""
Comprehensive error handling system for the Migration Assistant.

This module provides centralized error handling with categorized error types,
retry logic with exponential backoff, and error recovery strategies.
"""

import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field

from .exceptions import (
    MigrationAssistantError,
    ConfigurationError,
    ValidationError,
    ConnectionError,
    TransferError,
    DatabaseError,
    BackupError,
    RollbackError,
    AuthenticationError,
    PermissionError,
    CompatibilityError,
    ResourceError,
)


class ErrorCategory(str, Enum):
    """Categories of errors for better handling and reporting."""
    CONFIGURATION = "configuration"
    CONNECTIVITY = "connectivity"
    COMPATIBILITY = "compatibility"
    TRANSFER = "transfer"
    DATABASE = "database"
    BACKUP = "backup"
    ROLLBACK = "rollback"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    RESOURCE = "resource"
    VALIDATION = "validation"
    PLATFORM = "platform"
    UNKNOWN = "unknown"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryStrategy(str, Enum):
    """Available recovery strategies for different error types."""
    RETRY = "retry"
    ROLLBACK = "rollback"
    SKIP = "skip"
    MANUAL = "manual"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for an error occurrence."""
    timestamp: datetime = field(default_factory=datetime.now)
    operation: Optional[str] = None
    step: Optional[str] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: List[Type[Exception]] = field(default_factory=list)


@dataclass
class ErrorInfo:
    """Comprehensive error information."""
    error: Exception
    category: ErrorCategory
    severity: ErrorSeverity
    context: ErrorContext
    recovery_strategies: List[RecoveryStrategy]
    remediation_steps: List[str]
    traceback_str: str
    retry_count: int = 0
    is_recoverable: bool = True


class ErrorHandler:
    """
    Comprehensive error handler with categorization, retry logic, and recovery strategies.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._error_mappings = self._build_error_mappings()
        self._recovery_strategies = self._build_recovery_strategies()
        self._remediation_guides = self._build_remediation_guides()
        
    def _build_error_mappings(self) -> Dict[Type[Exception], Dict[str, Any]]:
        """Build mapping of exception types to error categories and severities."""
        return {
            ConfigurationError: {
                "category": ErrorCategory.CONFIGURATION,
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
            },
            ValidationError: {
                "category": ErrorCategory.VALIDATION,
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
            },
            ConnectionError: {
                "category": ErrorCategory.CONNECTIVITY,
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
            },
            TransferError: {
                "category": ErrorCategory.TRANSFER,
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
            },
            DatabaseError: {
                "category": ErrorCategory.DATABASE,
                "severity": ErrorSeverity.CRITICAL,
                "recoverable": True,
            },
            BackupError: {
                "category": ErrorCategory.BACKUP,
                "severity": ErrorSeverity.CRITICAL,
                "recoverable": False,
            },
            RollbackError: {
                "category": ErrorCategory.ROLLBACK,
                "severity": ErrorSeverity.CRITICAL,
                "recoverable": False,
            },
            AuthenticationError: {
                "category": ErrorCategory.AUTHENTICATION,
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
            },
            PermissionError: {
                "category": ErrorCategory.PERMISSION,
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
            },
            CompatibilityError: {
                "category": ErrorCategory.COMPATIBILITY,
                "severity": ErrorSeverity.HIGH,
                "recoverable": False,
            },
            ResourceError: {
                "category": ErrorCategory.RESOURCE,
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
            },
            # Standard Python exceptions
            FileNotFoundError: {
                "category": ErrorCategory.CONFIGURATION,
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
            },
            PermissionError: {
                "category": ErrorCategory.PERMISSION,
                "severity": ErrorSeverity.HIGH,
                "recoverable": True,
            },
            TimeoutError: {
                "category": ErrorCategory.CONNECTIVITY,
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
            },
            OSError: {
                "category": ErrorCategory.RESOURCE,
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
            },
        }
    
    def _build_recovery_strategies(self) -> Dict[ErrorCategory, List[RecoveryStrategy]]:
        """Build recovery strategies for each error category."""
        return {
            ErrorCategory.CONFIGURATION: [RecoveryStrategy.MANUAL, RecoveryStrategy.ABORT],
            ErrorCategory.CONNECTIVITY: [RecoveryStrategy.RETRY, RecoveryStrategy.MANUAL],
            ErrorCategory.COMPATIBILITY: [RecoveryStrategy.MANUAL, RecoveryStrategy.ABORT],
            ErrorCategory.TRANSFER: [RecoveryStrategy.RETRY, RecoveryStrategy.ROLLBACK],
            ErrorCategory.DATABASE: [RecoveryStrategy.RETRY, RecoveryStrategy.ROLLBACK],
            ErrorCategory.BACKUP: [RecoveryStrategy.MANUAL, RecoveryStrategy.ABORT],
            ErrorCategory.ROLLBACK: [RecoveryStrategy.MANUAL, RecoveryStrategy.ABORT],
            ErrorCategory.AUTHENTICATION: [RecoveryStrategy.MANUAL, RecoveryStrategy.RETRY],
            ErrorCategory.PERMISSION: [RecoveryStrategy.MANUAL, RecoveryStrategy.ABORT],
            ErrorCategory.RESOURCE: [RecoveryStrategy.RETRY, RecoveryStrategy.MANUAL],
            ErrorCategory.VALIDATION: [RecoveryStrategy.MANUAL, RecoveryStrategy.ABORT],
            ErrorCategory.PLATFORM: [RecoveryStrategy.MANUAL, RecoveryStrategy.SKIP],
            ErrorCategory.UNKNOWN: [RecoveryStrategy.MANUAL, RecoveryStrategy.ABORT],
        }
    
    def _build_remediation_guides(self) -> Dict[ErrorCategory, List[str]]:
        """Build remediation guides for each error category."""
        return {
            ErrorCategory.CONFIGURATION: [
                "Check configuration file syntax and required fields",
                "Verify file paths and permissions",
                "Ensure all required configuration values are provided",
                "Validate configuration against schema",
            ],
            ErrorCategory.CONNECTIVITY: [
                "Check network connectivity to target systems",
                "Verify firewall rules and port accessibility",
                "Confirm authentication credentials are correct",
                "Test DNS resolution for hostnames",
                "Check if services are running on target systems",
            ],
            ErrorCategory.COMPATIBILITY: [
                "Review source and destination system compatibility",
                "Check supported database versions and features",
                "Verify platform-specific requirements",
                "Consider alternative migration methods",
            ],
            ErrorCategory.TRANSFER: [
                "Check available disk space on source and destination",
                "Verify network stability and bandwidth",
                "Ensure proper file permissions",
                "Consider resuming from last successful checkpoint",
            ],
            ErrorCategory.DATABASE: [
                "Verify database connectivity and credentials",
                "Check database server status and resources",
                "Ensure sufficient privileges for migration operations",
                "Validate database schema compatibility",
                "Check for locked tables or active transactions",
            ],
            ErrorCategory.BACKUP: [
                "Ensure sufficient storage space for backups",
                "Verify backup destination accessibility",
                "Check backup tool availability and permissions",
                "Consider alternative backup methods",
            ],
            ErrorCategory.ROLLBACK: [
                "Verify backup integrity before rollback",
                "Ensure rollback destination is accessible",
                "Check for conflicting processes or locks",
                "Consider manual recovery procedures",
            ],
            ErrorCategory.AUTHENTICATION: [
                "Verify username and password are correct",
                "Check if account is locked or expired",
                "Ensure proper authentication method is used",
                "Verify API keys or tokens are valid",
                "Check multi-factor authentication requirements",
            ],
            ErrorCategory.PERMISSION: [
                "Verify user has required permissions",
                "Check file and directory access rights",
                "Ensure database user has necessary privileges",
                "Review sudo or administrative access requirements",
            ],
            ErrorCategory.RESOURCE: [
                "Check available disk space",
                "Monitor memory usage and availability",
                "Verify network bandwidth and stability",
                "Check system load and CPU usage",
                "Consider resource optimization or scaling",
            ],
            ErrorCategory.VALIDATION: [
                "Review validation criteria and requirements",
                "Check data integrity and consistency",
                "Verify system state and configuration",
                "Consider adjusting validation parameters",
            ],
            ErrorCategory.PLATFORM: [
                "Check platform-specific requirements",
                "Verify supported versions and features",
                "Review platform documentation",
                "Consider alternative approaches or tools",
            ],
            ErrorCategory.UNKNOWN: [
                "Review error logs for additional context",
                "Check system resources and status",
                "Verify configuration and connectivity",
                "Contact support with detailed error information",
            ],
        }
    
    def categorize_error(self, error: Exception, context: Optional[ErrorContext] = None) -> ErrorInfo:
        """
        Categorize an error and create comprehensive error information.
        
        Args:
            error: The exception that occurred
            context: Optional context information
            
        Returns:
            ErrorInfo object with categorized error details
        """
        error_type = type(error)
        mapping = self._error_mappings.get(error_type)
        
        if not mapping:
            # Try to find mapping for parent classes
            for exc_type, exc_mapping in self._error_mappings.items():
                if isinstance(error, exc_type):
                    mapping = exc_mapping
                    break
        
        if not mapping:
            mapping = {
                "category": ErrorCategory.UNKNOWN,
                "severity": ErrorSeverity.MEDIUM,
                "recoverable": True,
            }
        
        category = mapping["category"]
        severity = mapping["severity"]
        is_recoverable = mapping["recoverable"]
        
        recovery_strategies = self._recovery_strategies.get(category, [RecoveryStrategy.MANUAL])
        remediation_steps = self._remediation_guides.get(category, [])
        
        return ErrorInfo(
            error=error,
            category=category,
            severity=severity,
            context=context or ErrorContext(),
            recovery_strategies=recovery_strategies,
            remediation_steps=remediation_steps,
            traceback_str=traceback.format_exc(),
            is_recoverable=is_recoverable,
        )
    
    async def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        retry_config: Optional[RetryConfig] = None,
    ) -> ErrorInfo:
        """
        Handle an error with comprehensive logging and categorization.
        
        Args:
            error: The exception that occurred
            context: Optional context information
            retry_config: Optional retry configuration
            
        Returns:
            ErrorInfo object with error details
        """
        error_info = self.categorize_error(error, context)
        
        # Log the error
        self._log_error(error_info)
        
        # Update retry count if this is a retry
        if retry_config and hasattr(error, '_retry_count'):
            error_info.retry_count = getattr(error, '_retry_count', 0)
        
        return error_info
    
    def _log_error(self, error_info: ErrorInfo) -> None:
        """Log error information with appropriate level."""
        log_data = {
            "error_type": type(error_info.error).__name__,
            "error_message": str(error_info.error),
            "category": error_info.category.value,
            "severity": error_info.severity.value,
            "operation": error_info.context.operation,
            "step": error_info.context.step,
            "session_id": error_info.context.session_id,
            "tenant_id": error_info.context.tenant_id,
            "retry_count": error_info.retry_count,
            "is_recoverable": error_info.is_recoverable,
            "timestamp": error_info.context.timestamp.isoformat(),
        }
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            self.logger.critical("Critical error occurred", extra=log_data)
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error("High severity error occurred", extra=log_data)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning("Medium severity error occurred", extra=log_data)
        else:
            self.logger.info("Low severity error occurred", extra=log_data)
        
        # Log traceback for debugging
        if error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.debug("Error traceback", extra={"traceback": error_info.traceback_str})


class RetryHandler:
    """
    Handles retry logic with exponential backoff and jitter.
    """
    
    def __init__(self, error_handler: Optional[ErrorHandler] = None):
        self.error_handler = error_handler or ErrorHandler()
        self.logger = logging.getLogger(__name__)
    
    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        retry_config: Optional[RetryConfig] = None,
        context: Optional[ErrorContext] = None,
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic and exponential backoff.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            retry_config: Retry configuration
            context: Error context information
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
            
        Raises:
            The last exception if all retries are exhausted
        """
        config = retry_config or RetryConfig()
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                # Add retry count to exception for tracking
                setattr(e, '_retry_count', attempt + 1)
                
                # Handle the error
                error_info = await self.error_handler.handle_error(e, context, config)
                
                # Check if this exception type is retryable
                if config.retryable_exceptions and not any(
                    isinstance(e, exc_type) for exc_type in config.retryable_exceptions
                ):
                    self.logger.info(f"Exception {type(e).__name__} is not retryable")
                    raise e
                
                # Don't retry on the last attempt
                if attempt == config.max_attempts - 1:
                    break
                
                # Calculate delay with exponential backoff
                delay = min(
                    config.base_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )
                
                # Add jitter to prevent thundering herd
                if config.jitter:
                    import random
                    delay *= (0.5 + random.random() * 0.5)
                
                self.logger.info(
                    f"Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{config.max_attempts})"
                )
                
                await asyncio.sleep(delay)
        
        # All retries exhausted, raise the last exception
        if last_exception:
            raise last_exception


# Convenience functions for common retry configurations
def create_connectivity_retry_config() -> RetryConfig:
    """Create retry configuration for connectivity errors."""
    return RetryConfig(
        max_attempts=5,
        base_delay=2.0,
        max_delay=30.0,
        retryable_exceptions=[ConnectionError, TimeoutError, OSError]
    )


def create_transfer_retry_config() -> RetryConfig:
    """Create retry configuration for transfer errors."""
    return RetryConfig(
        max_attempts=3,
        base_delay=5.0,
        max_delay=60.0,
        retryable_exceptions=[TransferError, ConnectionError, OSError]
    )


def create_database_retry_config() -> RetryConfig:
    """Create retry configuration for database errors."""
    return RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        retryable_exceptions=[DatabaseError, ConnectionError]
    )