"""
Codebase Checkup Orchestrator

Main orchestration engine that coordinates analysis, cleanup, and reporting.
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Type, Union
import logging
import logging.handlers
from contextlib import asynccontextmanager

from migration_assistant.checkup.models import (
    CheckupConfig, CheckupResults, AnalysisResults, CleanupResults,
    CodebaseMetrics, IssueType
)
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.cleaners.base import BaseCleaner
from migration_assistant.checkup.validators.base import BaseValidator
from migration_assistant.checkup.reporters.base import ReportGenerator


class CheckupError(Exception):
    """Base exception for checkup operations."""
    
    def __init__(self, message: str, component: Optional[str] = None, 
                 original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.component = component
        self.original_error = original_error
        self.context = context or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for structured logging."""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "component": self.component,
            "original_error": str(self.original_error) if self.original_error else None,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "traceback": traceback.format_exc() if self.original_error else None
        }


class AnalysisError(CheckupError):
    """Errors during code analysis."""
    pass


class CleanupError(CheckupError):
    """Errors during cleanup operations."""
    pass


class ReportGenerationError(CheckupError):
    """Errors during report generation."""
    pass


class ValidationError(CheckupError):
    """Errors during validation operations."""
    pass


class RetryableError(CheckupError):
    """Errors that can be retried."""
    pass


class CodebaseOrchestrator:
    """Main orchestrator for codebase checkup and cleanup operations."""
    
    def __init__(self, config: CheckupConfig):
        """
        Initialize the orchestrator with configuration.
        
        Args:
            config: Checkup configuration
        """
        self.config = config
        self.logger = self._setup_structured_logging()
        
        # Component registries
        self._analyzers: List[BaseAnalyzer] = []
        self._cleaners: List[BaseCleaner] = []
        self._validators: List[BaseValidator] = []
        self._reporters: List[ReportGenerator] = []
        
        # State tracking
        self._analysis_results: Optional[AnalysisResults] = None
        self._cleanup_results: Optional[CleanupResults] = None
        self._before_metrics: Optional[CodebaseMetrics] = None
        self._after_metrics: Optional[CodebaseMetrics] = None
        
        # Enhanced error tracking
        self._errors: List[CheckupError] = []
        self._warnings: List[str] = []
        self._retryable_errors: List[Dict[str, Any]] = []
        self._performance_metrics: Dict[str, List[Dict[str, Any]]] = {}
        self._operation_stack: List[str] = []
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Retry configuration
        self._max_retries = getattr(config, 'max_retries', 3)
        self._retry_delay = getattr(config, 'retry_delay', 1.0)
        
        # Error recovery configuration
        self._enable_error_recovery = getattr(config, 'enable_error_recovery', True)
        self._enable_circuit_breaker = getattr(config, 'enable_circuit_breaker', True)
        self._graceful_degradation = getattr(config, 'graceful_degradation', True)
        
        # Initialize backup and rollback managers
        self.backup_manager = None
        self.rollback_manager = None
        self._last_backup_path = None
        self._initialize_backup_rollback_managers()
    
    def _get_affected_files_from_analysis(self, analysis_results: AnalysisResults) -> List[Path]:
        """Extract list of files that will be affected by cleanup operations."""
        affected_files = set()
        
        # Add files from quality issues
        for issue in analysis_results.quality_issues:
            if hasattr(issue, 'file_path') and issue.file_path:
                affected_files.add(Path(issue.file_path))
        
        # Add files from import issues
        for issue in analysis_results.import_issues:
            if hasattr(issue, 'file_path') and issue.file_path:
                affected_files.add(Path(issue.file_path))
        
        # Add files from duplicate issues
        for issue in analysis_results.duplicates:
            if hasattr(issue, 'file_paths') and issue.file_paths:
                for file_path in issue.file_paths:
                    affected_files.add(Path(file_path))
            elif hasattr(issue, 'file_path') and issue.file_path:
                affected_files.add(Path(issue.file_path))
        
        # Add files from structure issues
        for issue in analysis_results.structure_issues:
            if hasattr(issue, 'file_path') and issue.file_path:
                affected_files.add(Path(issue.file_path))
        
        return list(affected_files)
    
    def _initialize_backup_rollback_managers(self):
        """Initialize backup and rollback managers if backup is enabled."""
        if self.config.create_backup:
            try:
                from migration_assistant.checkup.backup_manager import BackupManager
                from migration_assistant.checkup.rollback_manager import RollbackManager
                
                self.backup_manager = BackupManager(self.config)
                self.rollback_manager = RollbackManager(self.config, self.backup_manager)
                
                self._log_structured("info", "Backup and rollback managers initialized")
            except ImportError as e:
                self._log_structured("warning", "Could not initialize backup/rollback managers", 
                                   error=str(e))
    
    def _setup_structured_logging(self) -> logging.Logger:
        """Set up comprehensive structured logging for the orchestrator."""
        logger = logging.getLogger(f"{__name__}.{id(self)}")
        
        # Prevent duplicate handlers
        if logger.handlers:
            return logger
        
        logger.setLevel(logging.DEBUG)
        
        # Import structured logging components with fallback
        try:
            from migration_assistant.utils.logging import StructuredFormatter, LogCategory
        except ImportError:
            # Fallback if rich or other dependencies are not available
            StructuredFormatter = None
            LogCategory = None
        
        # Create structured formatter with fallback
        if StructuredFormatter:
            structured_formatter = StructuredFormatter()
        else:
            # Fallback to standard formatter
            structured_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        # Standard formatter for console
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler with appropriate level
        console_handler = logging.StreamHandler()
        console_level = getattr(self.config, 'console_log_level', 'INFO')
        console_handler.setLevel(getattr(logging, console_level.upper()))
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler for detailed logs with structured format
        if hasattr(self.config, 'log_file') and self.config.log_file:
            log_path = Path(self.config.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                self.config.log_file,
                maxBytes=getattr(self.config, 'max_log_size', 50*1024*1024),  # 50MB default
                backupCount=getattr(self.config, 'log_backup_count', 10)
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(structured_formatter)
            logger.addHandler(file_handler)
        
        # Error-specific file handler for critical issues
        if hasattr(self.config, 'error_log_file') and self.config.error_log_file:
            error_log_path = Path(self.config.error_log_file)
            error_log_path.parent.mkdir(parents=True, exist_ok=True)
            
            error_handler = logging.handlers.RotatingFileHandler(
                self.config.error_log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(structured_formatter)
            logger.addHandler(error_handler)
        
        # Performance metrics handler
        if hasattr(self.config, 'performance_log_file') and self.config.performance_log_file:
            perf_log_path = Path(self.config.performance_log_file)
            perf_log_path.parent.mkdir(parents=True, exist_ok=True)
            
            perf_handler = logging.handlers.RotatingFileHandler(
                self.config.performance_log_file,
                maxBytes=20*1024*1024,  # 20MB
                backupCount=3
            )
            perf_handler.setLevel(logging.INFO)
            perf_handler.setFormatter(structured_formatter)
            
            # Add filter for performance-related logs
            perf_handler.addFilter(lambda record: 'performance' in record.getMessage().lower() or 
                                 'duration' in record.getMessage().lower() or
                                 'metrics' in record.getMessage().lower())
            logger.addHandler(perf_handler)
        
        return logger
    
    def _log_structured(self, level: str, message: str, **kwargs):
        """Log structured data with comprehensive context and metadata."""
        try:
            from migration_assistant.utils.logging import LogEntry, LogLevel, LogCategory
            
            # Determine log category based on context
            category = LogCategory.SYSTEM
            if 'component' in kwargs:
                component = kwargs['component']
                if 'analyzer' in component:
                    category = LogCategory.VALIDATION
                elif 'cleaner' in component or 'formatter' in component:
                    category = LogCategory.MIGRATION
                elif 'reporter' in component:
                    category = LogCategory.SYSTEM
            
            # Create structured log entry
            log_entry = LogEntry(
                level=LogLevel(level.upper()),
                category=category,
                message=message,
                session_id=getattr(self.config, 'session_id', None),
                tenant_id=getattr(self.config, 'tenant_id', None),
                operation=kwargs.get('operation'),
                step=kwargs.get('step'),
                duration=kwargs.get('duration'),
                error_code=kwargs.get('error_code'),
                metadata={
                    "orchestrator_id": id(self),
                    "config_hash": hash(str(self.config.__dict__)),
                    "total_errors": len(self._errors),
                    "total_warnings": len(self._warnings),
                    **{k: v for k, v in kwargs.items() if k not in ['operation', 'step', 'duration', 'error_code']}
                }
            )
            
            # Log with structured entry
            log_method = getattr(self.logger, level.lower())
            log_method(message, extra={'log_entry': log_entry})
            
        except ImportError:
            # Fallback to simple structured logging
            log_data = {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "orchestrator_id": id(self),
                "total_errors": len(self._errors),
                "total_warnings": len(self._warnings),
                **kwargs
            }
            
            log_message = f"{message} | {json.dumps(log_data, default=str)}"
            log_method = getattr(self.logger, level.lower())
            log_method(log_message)
        
        # Additional performance tracking for specific operations
        if 'duration' in kwargs and kwargs['duration']:
            self._track_performance_metric(
                kwargs.get('operation', 'unknown_operation'),
                kwargs['duration'],
                kwargs.get('component')
            )
    
    def _track_performance_metric(self, operation: str, duration: float, component: Optional[str] = None):
        """Track performance metrics for operations."""
        if not hasattr(self, '_performance_metrics'):
            self._performance_metrics = {}
        
        metric_key = f"{operation}_{component}" if component else operation
        
        if metric_key not in self._performance_metrics:
            self._performance_metrics[metric_key] = []
        
        self._performance_metrics[metric_key].append({
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })
        
        # Log performance summary periodically
        if len(self._performance_metrics[metric_key]) % 10 == 0:
            durations = [m['duration'] for m in self._performance_metrics[metric_key]]
            avg_duration = sum(durations) / len(durations)
            
            self._log_structured("info", f"Performance summary for {metric_key}",
                               operation="performance_tracking",
                               avg_duration=avg_duration,
                               total_operations=len(durations),
                               min_duration=min(durations),
                               max_duration=max(durations))
    
    @asynccontextmanager
    async def _error_context(self, operation: str, component: Optional[str] = None, 
                           critical: bool = False, allow_partial_failure: bool = True):
        """
        Comprehensive error context manager with advanced error handling capabilities.
        
        Args:
            operation: Name of the operation being performed
            component: Optional component name for better error tracking
            critical: Whether this operation is critical (affects overall success)
            allow_partial_failure: Whether to allow graceful degradation on failure
        """
        start_time = datetime.now()
        operation_id = f"{operation}_{int(start_time.timestamp())}"
        
        # Initialize operation tracking
        if not hasattr(self, '_operation_stack'):
            self._operation_stack = []
        self._operation_stack.append(operation_id)
        
        try:
            self._log_structured("info", f"Starting {operation}", 
                                component=component, operation=operation,
                                operation_id=operation_id, critical=critical,
                                stack_depth=len(self._operation_stack))
            
            # Pre-operation health check
            await self._pre_operation_check(operation, component)
            
            yield
            
            duration = datetime.now() - start_time
            self._log_structured("info", f"Successfully completed {operation}", 
                                component=component, operation=operation,
                                operation_id=operation_id,
                                duration=duration.total_seconds(),
                                success=True)
            
        except RetryableError as e:
            duration = datetime.now() - start_time
            self._log_structured("warning", f"Retryable error in {operation}", 
                                component=component, operation=operation,
                                operation_id=operation_id,
                                error=e.to_dict(),
                                duration=duration.total_seconds(),
                                retry_count=getattr(e, 'retry_count', 0))
            
            # Track retryable errors separately
            if not hasattr(self, '_retryable_errors'):
                self._retryable_errors = []
            self._retryable_errors.append({
                'error': e,
                'operation': operation,
                'component': component,
                'timestamp': start_time,
                'duration': duration.total_seconds()
            })
            raise
            
        except CheckupError as e:
            duration = datetime.now() - start_time
            e.context.update({
                'operation_id': operation_id,
                'operation_duration': duration.total_seconds(),
                'stack_depth': len(self._operation_stack),
                'critical_operation': critical
            })
            
            self._errors.append(e)
            self._log_structured("error", f"Checkup error in {operation}", 
                                component=component, operation=operation,
                                operation_id=operation_id,
                                error=e.to_dict(), 
                                duration=duration.total_seconds(),
                                critical=critical)
            
            # Handle critical vs non-critical errors
            if critical and not allow_partial_failure:
                self._log_structured("critical", f"Critical operation {operation} failed, aborting",
                                    component=component, operation=operation,
                                    operation_id=operation_id)
                raise
            elif not critical and allow_partial_failure:
                self._log_structured("warning", f"Non-critical operation {operation} failed, continuing with degraded functionality",
                                    component=component, operation=operation,
                                    operation_id=operation_id)
                # Don't re-raise for non-critical operations that allow partial failure
                return
            else:
                raise
            
        except Exception as e:
            duration = datetime.now() - start_time
            
            # Enhanced error context with system state
            error_context = {
                "operation": operation,
                "operation_id": operation_id,
                "duration": duration.total_seconds(),
                "stack_depth": len(self._operation_stack),
                "critical_operation": critical,
                "system_state": await self._capture_system_state(),
                "recent_operations": self._operation_stack[-5:] if len(self._operation_stack) > 1 else []
            }
            
            checkup_error = CheckupError(
                f"Unexpected error in {operation}: {str(e)}", 
                component=component, 
                original_error=e,
                context=error_context
            )
            
            self._errors.append(checkup_error)
            self._log_structured("error", f"Unexpected error in {operation}", 
                                component=component, operation=operation,
                                operation_id=operation_id,
                                error=checkup_error.to_dict(),
                                error_type=type(e).__name__,
                                critical=critical)
            
            # Attempt error recovery for non-critical operations
            if not critical and allow_partial_failure:
                recovery_attempted = await self._attempt_error_recovery(operation, e, component)
                if recovery_attempted:
                    self._log_structured("info", f"Error recovery attempted for {operation}",
                                        component=component, operation=operation,
                                        operation_id=operation_id)
                    return
            
            raise checkup_error
            
        finally:
            # Clean up operation tracking
            if self._operation_stack and self._operation_stack[-1] == operation_id:
                self._operation_stack.pop()
            
            # Post-operation cleanup
            await self._post_operation_cleanup(operation, component)
    
    async def _pre_operation_check(self, operation: str, component: Optional[str] = None):
        """Perform pre-operation health checks."""
        try:
            # Check system resources
            import psutil
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage(str(self.config.target_directory)).percent
            
            if memory_percent > 90:
                self._warnings.append(f"High memory usage ({memory_percent}%) before {operation}")
                self._log_structured("warning", f"High memory usage detected before {operation}",
                                    operation=operation, component=component,
                                    memory_percent=memory_percent)
            
            if disk_percent > 95:
                raise CheckupError(f"Insufficient disk space ({disk_percent}% used) for {operation}",
                                 component=component)
            
        except ImportError:
            # psutil not available, skip resource checks
            pass
        except Exception as e:
            self._log_structured("warning", f"Pre-operation check failed for {operation}",
                                operation=operation, component=component, error=str(e))
    
    async def _capture_system_state(self) -> Dict[str, Any]:
        """Capture current system state for error context."""
        state = {
            'timestamp': datetime.now().isoformat(),
            'active_operations': len(self._operation_stack),
            'total_errors': len(self._errors),
            'total_warnings': len(self._warnings)
        }
        
        try:
            import psutil
            state.update({
                'memory_percent': psutil.virtual_memory().percent,
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'disk_percent': psutil.disk_usage(str(self.config.target_directory)).percent
            })
        except ImportError:
            pass
        except Exception:
            pass
        
        return state
    
    async def _attempt_error_recovery(self, operation: str, error: Exception, 
                                    component: Optional[str] = None) -> bool:
        """
        Attempt to recover from errors in non-critical operations.
        
        Returns:
            True if recovery was attempted, False otherwise
        """
        recovery_strategies = {
            'file_operation': self._recover_file_operation,
            'analysis': self._recover_analysis_operation,
            'cleanup': self._recover_cleanup_operation,
            'validation': self._recover_validation_operation
        }
        
        # Determine recovery strategy based on operation type
        for op_type, recovery_func in recovery_strategies.items():
            if op_type in operation.lower():
                try:
                    await recovery_func(operation, error, component)
                    return True
                except Exception as recovery_error:
                    self._log_structured("warning", f"Error recovery failed for {operation}",
                                        operation=operation, component=component,
                                        recovery_error=str(recovery_error))
                    return False
        
        return False
    
    async def _recover_file_operation(self, operation: str, error: Exception, component: Optional[str] = None):
        """Recover from file operation errors."""
        if isinstance(error, (FileNotFoundError, PermissionError)):
            # Attempt to create missing directories or adjust permissions
            self._log_structured("info", f"Attempting file operation recovery for {operation}",
                                operation=operation, component=component)
            # Implementation would depend on specific file operation
    
    async def _recover_analysis_operation(self, operation: str, error: Exception, component: Optional[str] = None):
        """Recover from analysis operation errors."""
        # Skip problematic files and continue with remaining analysis
        self._log_structured("info", f"Attempting analysis recovery for {operation}",
                            operation=operation, component=component)
    
    async def _recover_cleanup_operation(self, operation: str, error: Exception, component: Optional[str] = None):
        """Recover from cleanup operation errors."""
        # Rollback partial changes if possible
        self._log_structured("info", f"Attempting cleanup recovery for {operation}",
                            operation=operation, component=component)
    
    async def _recover_validation_operation(self, operation: str, error: Exception, component: Optional[str] = None):
        """Recover from validation operation errors."""
        # Continue with reduced validation scope
        self._log_structured("info", f"Attempting validation recovery for {operation}",
                            operation=operation, component=component)
    
    async def _post_operation_cleanup(self, operation: str, component: Optional[str] = None):
        """Perform post-operation cleanup tasks."""
        try:
            # Clean up temporary resources
            if hasattr(self, '_temp_resources'):
                for resource in self._temp_resources:
                    try:
                        if hasattr(resource, 'cleanup'):
                            await resource.cleanup()
                    except Exception as e:
                        self._log_structured("warning", f"Failed to cleanup resource after {operation}",
                                            operation=operation, component=component, error=str(e))
        except Exception as e:
            self._log_structured("warning", f"Post-operation cleanup failed for {operation}",
                                operation=operation, component=component, error=str(e))
    
    async def _retry_operation(self, operation_func, operation_name: str, 
                              component: Optional[str] = None, max_retries: Optional[int] = None,
                              retry_config: Optional[Dict[str, Any]] = None):
        """
        Advanced retry mechanism with exponential backoff, jitter, and circuit breaker pattern.
        
        Args:
            operation_func: Async function to retry
            operation_name: Name of the operation for logging
            component: Component name for error tracking
            max_retries: Maximum number of retry attempts
            retry_config: Advanced retry configuration
        """
        from migration_assistant.core.error_handler import RetryHandler, RetryConfig, ErrorContext
        
        # Use advanced retry configuration if provided
        if retry_config:
            config = RetryConfig(
                max_attempts=retry_config.get('max_attempts', max_retries or self._max_retries),
                base_delay=retry_config.get('base_delay', self._retry_delay),
                max_delay=retry_config.get('max_delay', 60.0),
                exponential_base=retry_config.get('exponential_base', 2.0),
                jitter=retry_config.get('jitter', True),
                retryable_exceptions=retry_config.get('retryable_exceptions', [RetryableError])
            )
        else:
            config = RetryConfig(
                max_attempts=max_retries or self._max_retries,
                base_delay=self._retry_delay,
                retryable_exceptions=[RetryableError]
            )
        
        # Create error context
        context = ErrorContext(
            operation=operation_name,
            step=component,
            session_id=getattr(self.config, 'session_id', None),
            additional_data={
                'orchestrator_id': id(self),
                'component': component
            }
        )
        
        # Use the advanced retry handler
        retry_handler = RetryHandler()
        
        try:
            return await retry_handler.retry_with_backoff(
                operation_func,
                retry_config=config,
                context=context
            )
        except Exception as e:
            # Enhanced error logging for failed retries
            self._log_structured("error", f"All retry attempts exhausted for {operation_name}",
                                component=component, operation=operation_name,
                                max_attempts=config.max_attempts,
                                final_error=str(e),
                                error_type=type(e).__name__)
            raise
    
    async def _retry_with_circuit_breaker(self, operation_func, operation_name: str,
                                         component: Optional[str] = None,
                                         failure_threshold: int = 5,
                                         recovery_timeout: int = 60):
        """
        Retry operation with circuit breaker pattern to prevent cascading failures.
        
        Args:
            operation_func: Function to execute
            operation_name: Name for logging
            component: Component name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        circuit_key = f"{component}_{operation_name}" if component else operation_name
        
        if not hasattr(self, '_circuit_breakers'):
            self._circuit_breakers = {}
        
        if circuit_key not in self._circuit_breakers:
            self._circuit_breakers[circuit_key] = {
                'state': 'closed',  # closed, open, half-open
                'failure_count': 0,
                'last_failure_time': None,
                'success_count': 0
            }
        
        circuit = self._circuit_breakers[circuit_key]
        
        # Check circuit state
        if circuit['state'] == 'open':
            if circuit['last_failure_time']:
                time_since_failure = (datetime.now() - circuit['last_failure_time']).total_seconds()
                if time_since_failure < recovery_timeout:
                    raise CheckupError(
                        f"Circuit breaker open for {operation_name}. "
                        f"Retry in {recovery_timeout - time_since_failure:.1f} seconds",
                        component=component
                    )
                else:
                    # Transition to half-open
                    circuit['state'] = 'half-open'
                    self._log_structured("info", f"Circuit breaker transitioning to half-open for {operation_name}",
                                        component=component, operation=operation_name)
        
        try:
            result = await operation_func()
            
            # Success - reset or improve circuit state
            if circuit['state'] == 'half-open':
                circuit['success_count'] += 1
                if circuit['success_count'] >= 3:  # Require 3 successes to close
                    circuit['state'] = 'closed'
                    circuit['failure_count'] = 0
                    circuit['success_count'] = 0
                    self._log_structured("info", f"Circuit breaker closed for {operation_name}",
                                        component=component, operation=operation_name)
            elif circuit['state'] == 'closed':
                circuit['failure_count'] = max(0, circuit['failure_count'] - 1)  # Gradual recovery
            
            return result
            
        except Exception as e:
            # Failure - update circuit state
            circuit['failure_count'] += 1
            circuit['last_failure_time'] = datetime.now()
            circuit['success_count'] = 0
            
            if circuit['failure_count'] >= failure_threshold and circuit['state'] == 'closed':
                circuit['state'] = 'open'
                self._log_structured("warning", f"Circuit breaker opened for {operation_name}",
                                    component=component, operation=operation_name,
                                    failure_count=circuit['failure_count'],
                                    failure_threshold=failure_threshold)
            elif circuit['state'] == 'half-open':
                circuit['state'] = 'open'
                self._log_structured("warning", f"Circuit breaker re-opened for {operation_name}",
                                    component=component, operation=operation_name)
            
            raise
    
    def register_analyzer(self, analyzer_class: Type[BaseAnalyzer]) -> None:
        """
        Register an analyzer class.
        
        Args:
            analyzer_class: Analyzer class to register
        """
        analyzer = analyzer_class(self.config)
        self._analyzers.append(analyzer)
        self.logger.debug(f"Registered analyzer: {analyzer.name}")
    
    def register_cleaner(self, cleaner_class: Type[BaseCleaner]) -> None:
        """
        Register a cleaner class.
        
        Args:
            cleaner_class: Cleaner class to register
        """
        cleaner = cleaner_class(self.config)
        self._cleaners.append(cleaner)
        self.logger.debug(f"Registered cleaner: {cleaner.name}")
    
    def register_validator(self, validator_class: Type[BaseValidator]) -> None:
        """
        Register a validator class.
        
        Args:
            validator_class: Validator class to register
        """
        validator = validator_class(self.config)
        self._validators.append(validator)
        self.logger.debug(f"Registered validator: {validator.name}")
    
    def register_reporter(self, reporter_class: Type[ReportGenerator]) -> None:
        """
        Register a report generator class.
        
        Args:
            reporter_class: Reporter class to register
        """
        reporter = reporter_class(self.config)
        self._reporters.append(reporter)
        self.logger.debug(f"Registered reporter: {reporter.name}")
    
    async def run_full_checkup(self) -> CheckupResults:
        """
        Run complete checkup including analysis, cleanup, and reporting with comprehensive error handling.
        
        Returns:
            Complete checkup results
        """
        start_time = datetime.now()
        
        async with self._error_context("full_checkup"):
            try:
                self._log_structured("info", "Starting full codebase checkup", 
                                   target_directory=str(self.config.target_directory))
                
                # Validate configuration
                config_errors = self.config.validate()
                if config_errors:
                    raise CheckupError(
                        f"Configuration validation failed", 
                        component="configuration",
                        context={"errors": config_errors}
                    )
                
                # Capture before metrics with error handling
                try:
                    self._before_metrics = await self._retry_operation(
                        self._capture_metrics, "capture_before_metrics"
                    )
                except Exception as e:
                    self._log_structured("warning", "Failed to capture before metrics", error=str(e))
                    self._before_metrics = CodebaseMetrics()
                
                # Run analysis with comprehensive error handling
                self._analysis_results = await self.run_analysis_only()
                
                # Run cleanup if enabled and not in dry run mode
                cleanup_enabled = (
                    not self.config.dry_run and (
                        self.config.auto_format or 
                        self.config.auto_fix_imports or 
                        self.config.auto_organize_files
                    )
                )
                
                if cleanup_enabled:
                    try:
                        self._cleanup_results = await self.run_cleanup_only(self._analysis_results)
                        
                        # Capture after metrics
                        try:
                            self._after_metrics = await self._retry_operation(
                                self._capture_metrics, "capture_after_metrics"
                            )
                        except Exception as e:
                            self._log_structured("warning", "Failed to capture after metrics", error=str(e))
                            
                    except CleanupError as e:
                        self._log_structured("error", "Cleanup failed, continuing with analysis results only", 
                                           error=e.to_dict())
                        # Continue with analysis results only
                
                # Create final results
                duration = datetime.now() - start_time
                results = CheckupResults(
                    analysis=self._analysis_results,
                    cleanup=self._cleanup_results,
                    before_metrics=self._before_metrics,
                    after_metrics=self._after_metrics,
                    duration=duration,
                    success=len(self._errors) == 0
                )
                
                # Generate reports with error handling
                try:
                    report_files = await self.generate_reports(results)
                    self._log_structured("info", "Reports generated successfully", 
                                       report_count=len(report_files))
                except ReportGenerationError as e:
                    self._log_structured("warning", "Report generation failed", error=e.to_dict())
                    # Continue without reports
                
                # Log summary
                self._log_structured("info", "Checkup completed", 
                                   duration=duration.total_seconds(),
                                   total_issues=self._analysis_results.total_issues,
                                   total_changes=self._cleanup_results.total_changes if self._cleanup_results else 0,
                                   errors=len(self._errors),
                                   warnings=len(self._warnings))
                
                return results
                
            except CheckupError:
                # Re-raise CheckupErrors as they're already properly handled
                raise
                
            except Exception as e:
                # Handle any unexpected errors
                duration = datetime.now() - start_time
                
                error_result = CheckupResults(
                    analysis=self._analysis_results or AnalysisResults(),
                    cleanup=self._cleanup_results,
                    before_metrics=self._before_metrics or CodebaseMetrics(),
                    after_metrics=self._after_metrics,
                    duration=duration,
                    success=False,
                    error_message=str(e)
                )
                
                self._log_structured("critical", "Checkup failed with unexpected error", 
                                   duration=duration.total_seconds(),
                                   error=str(e),
                                   error_type=type(e).__name__)
                
                return error_result
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive error summary with categorization and statistics.
        
        Returns:
            Dictionary containing error summary and statistics
        """
        from migration_assistant.core.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
        
        error_handler = ErrorHandler()
        
        # Categorize all errors
        categorized_errors = {}
        severity_counts = {severity.value: 0 for severity in ErrorSeverity}
        category_counts = {category.value: 0 for category in ErrorCategory}
        
        for error in self._errors:
            error_info = error_handler.categorize_error(error)
            
            category = error_info.category.value
            severity = error_info.severity.value
            
            if category not in categorized_errors:
                categorized_errors[category] = []
            
            categorized_errors[category].append({
                'message': str(error),
                'severity': severity,
                'component': error.component,
                'timestamp': error.timestamp.isoformat(),
                'context': error.context,
                'recoverable': error_info.is_recoverable,
                'recovery_strategies': [s.value for s in error_info.recovery_strategies]
            })
            
            severity_counts[severity] += 1
            category_counts[category] += 1
        
        # Calculate error statistics
        total_errors = len(self._errors)
        total_retryable_errors = len(self._retryable_errors)
        
        # Performance impact analysis
        performance_impact = self._analyze_performance_impact()
        
        # Circuit breaker status
        circuit_breaker_status = {}
        for circuit_key, circuit_data in self._circuit_breakers.items():
            circuit_breaker_status[circuit_key] = {
                'state': circuit_data['state'],
                'failure_count': circuit_data['failure_count'],
                'last_failure': circuit_data['last_failure_time'].isoformat() if circuit_data['last_failure_time'] else None
            }
        
        return {
            'summary': {
                'total_errors': total_errors,
                'total_warnings': len(self._warnings),
                'total_retryable_errors': total_retryable_errors,
                'error_rate': total_errors / max(1, total_errors + total_retryable_errors),
                'has_critical_errors': severity_counts['critical'] > 0,
                'has_recoverable_errors': any(
                    any(e.get('recoverable', False) for e in errors)
                    for errors in categorized_errors.values()
                )
            },
            'categorized_errors': categorized_errors,
            'severity_distribution': severity_counts,
            'category_distribution': category_counts,
            'retryable_errors': self._retryable_errors,
            'warnings': self._warnings,
            'performance_impact': performance_impact,
            'circuit_breaker_status': circuit_breaker_status,
            'recommendations': self._generate_error_recommendations(categorized_errors, severity_counts)
        }
    
    def _analyze_performance_impact(self) -> Dict[str, Any]:
        """Analyze performance impact of errors and retries."""
        if not self._performance_metrics:
            return {'total_overhead': 0, 'affected_operations': 0}
        
        total_overhead = 0
        affected_operations = 0
        operation_impacts = {}
        
        for operation, metrics in self._performance_metrics.items():
            durations = [m['duration'] for m in metrics]
            if durations:
                avg_duration = sum(durations) / len(durations)
                max_duration = max(durations)
                
                # Estimate overhead from retries and errors
                overhead = max_duration - avg_duration
                if overhead > 0:
                    total_overhead += overhead
                    affected_operations += 1
                    operation_impacts[operation] = {
                        'average_duration': avg_duration,
                        'max_duration': max_duration,
                        'estimated_overhead': overhead,
                        'operation_count': len(durations)
                    }
        
        return {
            'total_overhead': total_overhead,
            'affected_operations': affected_operations,
            'operation_impacts': operation_impacts
        }
    
    def _generate_error_recommendations(self, categorized_errors: Dict[str, Any], 
                                      severity_counts: Dict[str, int]) -> List[str]:
        """Generate actionable recommendations based on error patterns."""
        recommendations = []
        
        # Critical error recommendations
        if severity_counts['critical'] > 0:
            recommendations.append(
                "CRITICAL: Address critical errors immediately. "
                "These may indicate system instability or data integrity issues."
            )
        
        # High error count recommendations
        if severity_counts['high'] > 5:
            recommendations.append(
                "HIGH PRIORITY: Multiple high-severity errors detected. "
                "Review system configuration and resource availability."
            )
        
        # Category-specific recommendations
        if 'connectivity' in categorized_errors:
            recommendations.append(
                "CONNECTIVITY: Check network connectivity, firewall rules, and service availability."
            )
        
        if 'configuration' in categorized_errors:
            recommendations.append(
                "CONFIGURATION: Review configuration files for syntax errors and missing values."
            )
        
        if 'resource' in categorized_errors:
            recommendations.append(
                "RESOURCES: Monitor system resources (memory, disk space, CPU) and consider scaling."
            )
        
        # Retry pattern recommendations
        if len(self._retryable_errors) > 10:
            recommendations.append(
                "RETRY PATTERN: High number of retryable errors suggests intermittent issues. "
                "Consider increasing retry delays or investigating root causes."
            )
        
        # Circuit breaker recommendations
        open_circuits = [k for k, v in self._circuit_breakers.items() if v['state'] == 'open']
        if open_circuits:
            recommendations.append(
                f"CIRCUIT BREAKERS: {len(open_circuits)} circuit breakers are open. "
                f"Affected operations: {', '.join(open_circuits)}"
            )
        
        return recommendations
    
    async def attempt_error_recovery(self) -> Dict[str, Any]:
        """
        Attempt to recover from recoverable errors.
        
        Returns:
            Recovery results and statistics
        """
        if not self._enable_error_recovery:
            return {'recovery_attempted': False, 'reason': 'Error recovery disabled'}
        
        from migration_assistant.core.error_handler import ErrorHandler
        
        error_handler = ErrorHandler()
        recovery_results = {
            'recovery_attempted': True,
            'total_errors': len(self._errors),
            'recoverable_errors': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'recovery_details': []
        }
        
        for error in self._errors:
            error_info = error_handler.categorize_error(error)
            
            if error_info.is_recoverable:
                recovery_results['recoverable_errors'] += 1
                
                try:
                    # Attempt recovery based on error category
                    recovery_success = await self._attempt_specific_recovery(error, error_info)
                    
                    if recovery_success:
                        recovery_results['successful_recoveries'] += 1
                        recovery_results['recovery_details'].append({
                            'error': str(error),
                            'category': error_info.category.value,
                            'recovery_status': 'success',
                            'recovery_strategy': error_info.recovery_strategies[0].value if error_info.recovery_strategies else 'unknown'
                        })
                    else:
                        recovery_results['failed_recoveries'] += 1
                        recovery_results['recovery_details'].append({
                            'error': str(error),
                            'category': error_info.category.value,
                            'recovery_status': 'failed',
                            'reason': 'Recovery strategy unsuccessful'
                        })
                        
                except Exception as recovery_error:
                    recovery_results['failed_recoveries'] += 1
                    recovery_results['recovery_details'].append({
                        'error': str(error),
                        'category': error_info.category.value,
                        'recovery_status': 'error',
                        'recovery_error': str(recovery_error)
                    })
        
        # Log recovery summary
        self._log_structured("info", "Error recovery completed",
                            operation="error_recovery",
                            total_errors=recovery_results['total_errors'],
                            recoverable_errors=recovery_results['recoverable_errors'],
                            successful_recoveries=recovery_results['successful_recoveries'],
                            failed_recoveries=recovery_results['failed_recoveries'])
        
        return recovery_results
    
    async def _attempt_specific_recovery(self, error: CheckupError, error_info) -> bool:
        """
        Attempt recovery for a specific error based on its category.
        
        Returns:
            True if recovery was successful, False otherwise
        """
        from migration_assistant.core.error_handler import ErrorCategory, RecoveryStrategy
        
        category = error_info.category
        strategies = error_info.recovery_strategies
        
        for strategy in strategies:
            try:
                if strategy == RecoveryStrategy.RETRY:
                    # Attempt to retry the failed operation
                    return await self._recovery_retry(error)
                elif strategy == RecoveryStrategy.SKIP:
                    # Mark error as skipped and continue
                    return await self._recovery_skip(error)
                elif strategy == RecoveryStrategy.ROLLBACK:
                    # Attempt to rollback changes
                    return await self._recovery_rollback(error)
                elif strategy == RecoveryStrategy.MANUAL:
                    # Log manual intervention required
                    return await self._recovery_manual(error)
                    
            except Exception as strategy_error:
                self._log_structured("warning", f"Recovery strategy {strategy.value} failed",
                                    error=str(error), strategy_error=str(strategy_error))
                continue
        
        return False
    
    async def _recovery_retry(self, error: CheckupError) -> bool:
        """Attempt to retry a failed operation."""
        # This would need to be implemented based on the specific operation
        # For now, just log the attempt
        self._log_structured("info", "Retry recovery attempted", error=str(error))
        return False
    
    async def _recovery_skip(self, error: CheckupError) -> bool:
        """Skip the failed operation and continue."""
        self._log_structured("info", "Skip recovery applied", error=str(error))
        return True
    
    async def _recovery_rollback(self, error: CheckupError) -> bool:
        """Attempt to rollback changes from failed operation."""
        self._log_structured("info", "Rollback recovery attempted", error=str(error))
        
        try:
            # Check if we have a rollback manager available
            if hasattr(self, 'rollback_manager') and self.rollback_manager:
                # Find the most recent operation that can be rolled back
                operations = self.rollback_manager.list_rollback_operations()
                
                for operation in operations:
                    if not operation.rollback_completed:
                        # Attempt automatic rollback
                        success = await self.rollback_manager.automatic_rollback(
                            operation.operation_id,
                            f"Orchestrator recovery: {str(error)}"
                        )
                        
                        if success:
                            self._log_structured("info", "Automatic rollback successful",
                                               operation_id=operation.operation_id)
                            return True
                        else:
                            self._log_structured("warning", "Automatic rollback failed",
                                               operation_id=operation.operation_id)
            
            # Fallback to legacy rollback method
            if hasattr(self, '_last_backup_path') and self._last_backup_path:
                await self._rollback_changes_comprehensive(self._last_backup_path)
                self._log_structured("info", "Legacy rollback completed")
                return True
                
        except Exception as rollback_error:
            self._log_structured("error", "Rollback recovery failed", 
                               rollback_error=str(rollback_error))
        
        return False
    
    async def _recovery_manual(self, error: CheckupError) -> bool:
        """Log that manual intervention is required."""
        self._log_structured("warning", "Manual intervention required for error recovery",
                            error=str(error))
        return False
    
    def reset_circuit_breakers(self, circuit_key: Optional[str] = None):
        """
        Reset circuit breakers to closed state.
        
        Args:
            circuit_key: Specific circuit to reset, or None to reset all
        """
        if circuit_key:
            if circuit_key in self._circuit_breakers:
                self._circuit_breakers[circuit_key] = {
                    'state': 'closed',
                    'failure_count': 0,
                    'last_failure_time': None,
                    'success_count': 0
                }
                self._log_structured("info", f"Circuit breaker reset", circuit_key=circuit_key)
        else:
            for key in self._circuit_breakers:
                self._circuit_breakers[key] = {
                    'state': 'closed',
                    'failure_count': 0,
                    'last_failure_time': None,
                    'success_count': 0
                }
            self._log_structured("info", "All circuit breakers reset")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        if not self._performance_metrics:
            return {'total_operations': 0, 'metrics': {}}
        
        metrics_summary = {}
        total_operations = 0
        
        for operation, metrics in self._performance_metrics.items():
            durations = [m['duration'] for m in metrics]
            total_operations += len(durations)
            
            if durations:
                metrics_summary[operation] = {
                    'count': len(durations),
                    'total_duration': sum(durations),
                    'average_duration': sum(durations) / len(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'median_duration': sorted(durations)[len(durations) // 2],
                    'p95_duration': sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 20 else max(durations)
                }
        
        return {
            'total_operations': total_operations,
            'metrics': metrics_summary,
            'collection_period': {
                'start': min(
                    min(m['timestamp'] for m in metrics) 
                    for metrics in self._performance_metrics.values()
                ) if self._performance_metrics else None,
                'end': max(
                    max(m['timestamp'] for m in metrics) 
                    for metrics in self._performance_metrics.values()
                ) if self._performance_metrics else None
            }
        }
    
    def clear_error_history(self):
        """Clear all error history and reset tracking."""
        self._errors.clear()
        self._warnings.clear()
        self._retryable_errors.clear()
        self._performance_metrics.clear()
        self._operation_stack.clear()
        
        self._log_structured("info", "Error history cleared", operation="maintenance")
    
    async def run_analysis_only(self) -> AnalysisResults:
        """
        Run analysis phase only with enhanced parallel processing and progress tracking.
        
        Returns:
            Analysis results
        """
        async with self._error_context("analysis_workflow"):
            self._log_structured("info", "Starting enhanced analysis workflow")
            
            # Get enabled components
            enabled_analyzers = [a for a in self._analyzers if self._should_run_analyzer(a)]
            enabled_validators = [v for v in self._validators if self._should_run_validator(v)]
            
            if not enabled_analyzers and not enabled_validators:
                self._log_structured("warning", "No analyzers or validators enabled")
                return AnalysisResults()
            
            # Use the new parallel analysis method
            return await self.run_parallel_analysis(enabled_analyzers, enabled_validators)
    
    async def run_cleanup_only(self, analysis_results: AnalysisResults) -> CleanupResults:
        """
        Run cleanup phase with comprehensive backup creation, rollback capabilities, and validation.
        
        This method implements the complete cleanup workflow orchestration including:
        - Safe cleanup pipeline with backup creation
        - Rollback capabilities for failed cleanup operations  
        - Cleanup validation and verification
        - Progress tracking and error handling
        
        Args:
            analysis_results: Results from analysis phase
            
        Returns:
            Cleanup results with detailed operation tracking
        """
        start_time = datetime.now()
        backup_path = None
        
        async with self._error_context("cleanup_workflow"):
            try:
                self._log_structured("info", "Starting comprehensive cleanup workflow", 
                                   total_issues=analysis_results.total_issues,
                                   dry_run=self.config.dry_run)
                
                # Initialize results with comprehensive tracking
                results = CleanupResults()
                results.cleanup_plan = await self._create_cleanup_plan(analysis_results)
                
                # Phase 1: Pre-cleanup validation and backup creation
                await self._pre_cleanup_phase(results, analysis_results)
                
                if self.config.create_backup and not self.config.dry_run:
                    backup_path = await self._create_comprehensive_backup()
                    results.backup_created = True
                    results.backup_path = backup_path
                    self._last_backup_path = backup_path
                    self._log_structured("info", "Comprehensive backup created", 
                                       backup_path=str(backup_path))
                    
                    # Register cleanup operation with rollback manager
                    if self.rollback_manager:
                        affected_files = self._get_affected_files_from_analysis(analysis_results)
                        backup_id = backup_path.name  # Use backup directory name as ID
                        
                        operation_id = await self.rollback_manager.register_operation(
                            operation_type="cleanup",
                            backup_id=backup_id,
                            affected_files=affected_files,
                            metadata={
                                "analysis_issues": analysis_results.total_issues,
                                "cleanup_plan": len(results.cleanup_plan),
                                "orchestrator_id": id(self)
                            }
                        )
                        
                        results.rollback_operation_id = operation_id
                        self._log_structured("info", "Cleanup operation registered for rollback",
                                           operation_id=operation_id)
                
                # Phase 2: Execute cleanup operations with progress tracking
                enabled_cleaners = [c for c in self._cleaners if self._should_run_cleaner(c)]
                
                if not enabled_cleaners:
                    self._log_structured("info", "No cleaners enabled, completing cleanup workflow")
                    results.timestamp = datetime.now()
                    results.duration = results.timestamp - start_time
                    return results
                
                cleanup_execution_results = await self._execute_cleanup_operations(
                    enabled_cleaners, analysis_results, results
                )
                
                # Phase 3: Post-cleanup validation and verification
                validation_results = await self._post_cleanup_validation(
                    results, analysis_results, cleanup_execution_results
                )
                
                # Phase 4: Handle rollback if necessary
                if not validation_results.validation_passed:
                    await self._handle_cleanup_rollback(
                        backup_path, validation_results, cleanup_execution_results
                    )
                
                # Phase 5: Finalize results
                results.timestamp = datetime.now()
                results.duration = results.timestamp - start_time
                results.validation_results = validation_results
                
                self._log_structured("info", "Cleanup workflow completed", 
                                   total_changes=results.total_changes,
                                   successful_changes=results.successful_changes,
                                   duration=results.duration.total_seconds(),
                                   validation_passed=validation_results.validation_passed)
                
                return results
                
            except Exception as e:
                # Critical failure handling with comprehensive rollback
                await self._handle_critical_cleanup_failure(backup_path, e, start_time)
                raise
    
    async def _create_cleanup_plan(self, analysis_results: AnalysisResults) -> Dict[str, Any]:
        """Create a comprehensive cleanup plan based on analysis results."""
        plan = {
            "formatting_operations": [],
            "import_operations": [],
            "file_operations": [],
            "validation_operations": [],
            "estimated_changes": 0,
            "risk_assessment": "low"
        }
        
        # Plan formatting operations
        if self.config.auto_format:
            plan["formatting_operations"].extend([
                {"type": "black_formatting", "files": len(analysis_results.quality_issues)},
                {"type": "isort_imports", "files": len(analysis_results.import_issues)},
                {"type": "docstring_standardization", "files": analysis_results.metrics.python_files}
            ])
            plan["estimated_changes"] += len(analysis_results.quality_issues) * 2
        
        # Plan import operations
        if self.config.auto_fix_imports:
            unused_imports = len([i for i in analysis_results.import_issues 
                                if i.issue_type == IssueType.UNUSED_IMPORT])
            plan["import_operations"].extend([
                {"type": "remove_unused_imports", "count": unused_imports},
                {"type": "resolve_circular_imports", "count": len([i for i in analysis_results.import_issues 
                                                                 if i.is_circular])}
            ])
            plan["estimated_changes"] += unused_imports
        
        # Plan file operations
        if self.config.auto_organize_files:
            misplaced_files = len([s for s in analysis_results.structure_issues 
                                 if s.suggested_location])
            plan["file_operations"].extend([
                {"type": "reorganize_files", "count": misplaced_files},
                {"type": "remove_empty_dirs", "count": analysis_results.metrics.empty_directories}
            ])
            plan["estimated_changes"] += misplaced_files
            
            # Assess risk based on file operations
            if misplaced_files > self.config.max_file_moves:
                plan["risk_assessment"] = "high"
            elif misplaced_files > self.config.max_file_moves / 2:
                plan["risk_assessment"] = "medium"
        
        return plan
    
    async def _pre_cleanup_phase(self, results: CleanupResults, analysis_results: AnalysisResults) -> None:
        """Execute pre-cleanup validation and preparation."""
        self._log_structured("info", "Starting pre-cleanup phase")
        
        # Validate that target directory is in a clean state
        if not self.config.dry_run:
            # Check for uncommitted changes if in a git repository
            git_dir = self.config.target_directory / ".git"
            if git_dir.exists():
                try:
                    import subprocess
                    result = subprocess.run(
                        ["git", "status", "--porcelain"], 
                        cwd=self.config.target_directory,
                        capture_output=True, text=True, timeout=10
                    )
                    if result.stdout.strip():
                        self._log_structured("warning", "Uncommitted changes detected in git repository")
                        results.pre_cleanup_warnings.append("Uncommitted git changes detected")
                except Exception:
                    pass  # Git not available or other issue
        
        # Validate file permissions
        critical_files = [
            self.config.target_directory / "pyproject.toml",
            self.config.target_directory / "setup.py",
            self.config.target_directory / "requirements.txt"
        ]
        
        for file_path in critical_files:
            if file_path.exists() and not file_path.is_file():
                raise CleanupError(f"Critical path is not a file: {file_path}")
        
        # Check available disk space for backup
        if self.config.create_backup:
            import shutil
            free_space = shutil.disk_usage(self.config.backup_dir.parent).free
            estimated_backup_size = sum(
                f.stat().st_size for f in self.config.target_directory.rglob("*") 
                if f.is_file()
            )
            
            if free_space < estimated_backup_size * 1.5:  # 50% buffer
                raise CleanupError("Insufficient disk space for backup creation")
    
    async def _execute_cleanup_operations(self, enabled_cleaners: List, analysis_results: AnalysisResults, 
                                        results: CleanupResults) -> Dict[str, Any]:
        """Execute cleanup operations with comprehensive progress tracking."""
        total_cleaners = len(enabled_cleaners)
        completed_cleaners = 0
        failed_cleaners = []
        successful_cleaners = []
        
        self._log_structured("info", "Executing cleanup operations", 
                           total_cleaners=total_cleaners)
        
        for cleaner in enabled_cleaners:
            cleaner_start_time = datetime.now()
            
            try:
                async with self._error_context(f"cleaner_{cleaner.name}", cleaner.name):
                    self._log_structured("info", "Starting cleaner execution", 
                                       cleaner=cleaner.name, 
                                       progress=f"{completed_cleaners + 1}/{total_cleaners}")
                    
                    # Pre-cleanup validation
                    if hasattr(cleaner, 'pre_clean'):
                        await cleaner.pre_clean(analysis_results)
                    
                    # Execute cleanup with timeout
                    cleanup_result = await asyncio.wait_for(
                        cleaner.clean(analysis_results), 
                        timeout=300  # 5 minute timeout per cleaner
                    )
                    
                    # Post-cleanup validation
                    if hasattr(cleaner, 'post_clean'):
                        await cleaner.post_clean(cleanup_result)
                    
                    # Merge results with detailed tracking
                    await self._merge_cleanup_results_comprehensive(results, cleanup_result, cleaner)
                    
                    cleaner_duration = datetime.now() - cleaner_start_time
                    
                    if getattr(cleanup_result, 'success', True):
                        successful_cleaners.append({
                            "name": cleaner.name,
                            "duration": cleaner_duration.total_seconds(),
                            "changes": getattr(cleanup_result, 'changes_made', 0)
                        })
                        self._log_structured("info", "Cleaner completed successfully", 
                                           cleaner=cleaner.name,
                                           duration=cleaner_duration.total_seconds())
                    else:
                        failed_cleaners.append({
                            "name": cleaner.name,
                            "error": getattr(cleanup_result, 'error_message', 'Unknown error'),
                            "duration": cleaner_duration.total_seconds()
                        })
                        
            except asyncio.TimeoutError:
                failed_cleaners.append({
                    "name": cleaner.name,
                    "error": "Timeout after 5 minutes",
                    "duration": 300
                })
                self._log_structured("error", "Cleaner timed out", cleaner=cleaner.name)
                
            except Exception as e:
                cleaner_duration = datetime.now() - cleaner_start_time
                failed_cleaners.append({
                    "name": cleaner.name,
                    "error": str(e),
                    "duration": cleaner_duration.total_seconds()
                })
                self._log_structured("error", "Cleaner failed with exception", 
                                   cleaner=cleaner.name, error=str(e))
            
            completed_cleaners += 1
            progress = (completed_cleaners / total_cleaners) * 100
            self._log_structured("debug", "Cleanup progress update", 
                               progress=f"{progress:.1f}%", 
                               completed=completed_cleaners, 
                               total=total_cleaners)
        
        return {
            "successful_cleaners": successful_cleaners,
            "failed_cleaners": failed_cleaners,
            "total_cleaners": total_cleaners,
            "success_rate": len(successful_cleaners) / total_cleaners if total_cleaners > 0 else 0
        }
    
    async def _post_cleanup_validation(self, results: CleanupResults, analysis_results: AnalysisResults,
                                     execution_results: Dict[str, Any]) -> 'ValidationResults':
        """Comprehensive post-cleanup validation and verification."""
        self._log_structured("info", "Starting post-cleanup validation")
        
        validation_results = ValidationResults()
        
        try:
            # Validate file system integrity
            validation_results.file_system_integrity = await self._validate_file_system_integrity(results)
            
            # Validate syntax of modified Python files
            validation_results.syntax_validation = await self._validate_python_syntax(results)
            
            # Validate import integrity
            validation_results.import_integrity = await self._validate_import_integrity(results)
            
            # Validate that critical files weren't accidentally modified
            validation_results.critical_files_intact = await self._validate_critical_files(results)
            
            # Validate cleanup effectiveness
            validation_results.cleanup_effectiveness = await self._validate_cleanup_effectiveness(
                results, analysis_results
            )
            
            # Overall validation result
            validation_results.validation_passed = all([
                validation_results.file_system_integrity,
                validation_results.syntax_validation,
                validation_results.import_integrity,
                validation_results.critical_files_intact,
                execution_results["success_rate"] >= 0.5  # At least 50% of cleaners succeeded
            ])
            
            # Risk assessment
            if execution_results["success_rate"] < 0.3:
                validation_results.risk_level = "high"
            elif execution_results["success_rate"] < 0.7:
                validation_results.risk_level = "medium"
            else:
                validation_results.risk_level = "low"
            
            self._log_structured("info", "Post-cleanup validation completed", 
                               validation_passed=validation_results.validation_passed,
                               risk_level=validation_results.risk_level)
            
        except Exception as e:
            validation_results.validation_passed = False
            validation_results.validation_error = str(e)
            self._log_structured("error", "Post-cleanup validation failed", error=str(e))
        
        return validation_results
    
    async def _handle_cleanup_rollback(self, backup_path: Optional[Path], 
                                     validation_results: 'ValidationResults',
                                     execution_results: Dict[str, Any]) -> None:
        """Handle rollback decision and execution based on validation results."""
        if not backup_path or self.config.dry_run:
            self._log_structured("warning", "Rollback requested but no backup available or in dry run mode")
            return
        
        # Determine if rollback is necessary
        should_rollback = False
        rollback_reason = []
        
        if not validation_results.validation_passed:
            should_rollback = True
            rollback_reason.append("Validation failed")
        
        if execution_results["success_rate"] < 0.3:
            should_rollback = True
            rollback_reason.append("Too many cleaner failures")
        
        if validation_results.risk_level == "high":
            should_rollback = True
            rollback_reason.append("High risk assessment")
        
        if should_rollback:
            self._log_structured("warning", "Initiating rollback", 
                               reasons=rollback_reason)
            
            try:
                await self._rollback_changes_comprehensive(backup_path)
                self._log_structured("info", "Rollback completed successfully")
                
            except Exception as rollback_error:
                self._log_structured("error", "Rollback failed", error=str(rollback_error))
                raise CleanupError(f"Cleanup failed and rollback also failed: {rollback_error}")
    
    async def _handle_critical_cleanup_failure(self, backup_path: Optional[Path], 
                                             error: Exception, start_time: datetime) -> None:
        """Handle critical cleanup failures with comprehensive error reporting."""
        duration = datetime.now() - start_time
        
        self._log_structured("critical", "Critical cleanup failure occurred", 
                           error=str(error), 
                           error_type=type(error).__name__,
                           duration=duration.total_seconds())
        
        # Attempt emergency rollback
        if backup_path and self.config.create_backup and not self.config.dry_run:
            try:
                await self._rollback_changes_comprehensive(backup_path)
                self._log_structured("info", "Emergency rollback completed")
            except Exception as rollback_error:
                self._log_structured("critical", "Emergency rollback failed", 
                                   rollback_error=str(rollback_error))
        
        # Create error report
        error_report = {
            "timestamp": datetime.now().isoformat(),
            "error": str(error),
            "error_type": type(error).__name__,
            "duration": duration.total_seconds(),
            "backup_path": str(backup_path) if backup_path else None,
            "config": {
                "dry_run": self.config.dry_run,
                "create_backup": self.config.create_backup,
                "auto_format": self.config.auto_format,
                "auto_fix_imports": self.config.auto_fix_imports,
                "auto_organize_files": self.config.auto_organize_files
            }
        }
        
        # Save error report
        error_report_path = self.config.target_directory / "cleanup_error_report.json"
        try:
            import json
            with open(error_report_path, 'w') as f:
                json.dump(error_report, f, indent=2)
            self._log_structured("info", "Error report saved", path=str(error_report_path))
        except Exception:
            pass  # Don't fail on error report saving
        
        raise CleanupError(f"Critical cleanup failure: {error}")
    
    async def generate_reports(self, results: CheckupResults) -> Dict[str, Path]:
        """
        Generate all configured reports.
        
        Args:
            results: Complete checkup results
            
        Returns:
            Dictionary mapping report type to file path
        """
        try:
            self.logger.info("Generating reports")
            
            report_files = {}
            
            for reporter in self._reporters:
                if self._should_run_reporter(reporter):
                    try:
                        # Generate summary report
                        summary_path = await reporter.generate_and_save_summary(results)
                        report_files[f"{reporter.name}_summary"] = summary_path
                        
                        # Generate detailed report
                        detailed_path = await reporter.generate_and_save_detailed(results)
                        report_files[f"{reporter.name}_detailed"] = detailed_path
                        
                        self.logger.info(f"Generated {reporter.name} reports")
                        
                    except Exception as e:
                        self.logger.error(f"Report generator {reporter.name} failed: {e}")
                        continue
            
            return report_files
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            raise ReportGenerationError(f"Report generation failed: {e}")
    
    async def _capture_metrics(self) -> CodebaseMetrics:
        """Capture current codebase metrics."""
        metrics = CodebaseMetrics()
        
        try:
            # Count files by type
            for file_path in self.config.target_directory.rglob("*"):
                if file_path.is_file():
                    metrics.total_files += 1
                    
                    if file_path.suffix == '.py':
                        metrics.python_files += 1
                        if 'test' in file_path.name.lower():
                            metrics.test_files += 1
                    elif file_path.suffix in ['.md', '.rst', '.txt']:
                        metrics.documentation_files += 1
                    elif file_path.name in ['pyproject.toml', 'setup.py', 'requirements.txt']:
                        metrics.config_files += 1
            
            # Count lines of code
            for py_file in self.config.target_directory.rglob("*.py"):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        metrics.total_lines += len(f.readlines())
                except Exception:
                    continue
            
        except Exception as e:
            self.logger.warning(f"Failed to capture some metrics: {e}")
        
        return metrics
    
    async def _run_analyzer(self, analyzer: BaseAnalyzer):
        """Run a single analyzer."""
        try:
            await analyzer.pre_analyze()
            issues = await analyzer.analyze()
            await analyzer.post_analyze(issues)
            return issues, analyzer.metrics
        except Exception as e:
            raise AnalysisError(f"Analyzer {analyzer.name} failed: {e}")
    
    async def _run_validator(self, validator: BaseValidator):
        """Run a single validator."""
        try:
            await validator.pre_validate()
            result = await validator.validate()
            await validator.post_validate(result)
            return result, validator.metrics
        except Exception as e:
            raise AnalysisError(f"Validator {validator.name} failed: {e}")
    
    async def _run_analyzer_with_progress(self, analyzer: BaseAnalyzer, completed: int, total: int):
        """Run a single analyzer with progress tracking and error handling."""
        async with self._error_context(f"analyzer_{analyzer.name}", analyzer.name):
            
            async def analyzer_operation():
                self._log_structured("debug", "Starting analyzer", 
                                   analyzer=analyzer.name, progress=f"{completed}/{total}")
                
                # Pre-analyze phase
                if hasattr(analyzer, 'pre_analyze'):
                    await analyzer.pre_analyze()
                
                # Main analysis phase
                issues = await analyzer.analyze()
                
                # Post-analyze phase
                if hasattr(analyzer, 'post_analyze'):
                    await analyzer.post_analyze(issues)
                
                self._log_structured("debug", "Analyzer completed successfully", 
                                   analyzer=analyzer.name, issues_found=len(issues))
                
                return issues, analyzer.metrics
            
            return await self._retry_operation(
                analyzer_operation, 
                f"analyzer_{analyzer.name}", 
                analyzer.name
            )
    
    async def _run_validator_with_progress(self, validator: BaseValidator, completed: int, total: int):
        """Run a single validator with progress tracking and error handling."""
        async with self._error_context(f"validator_{validator.name}", validator.name):
            
            async def validator_operation():
                self._log_structured("debug", "Starting validator", 
                                   validator=validator.name, progress=f"{completed}/{total}")
                
                # Pre-validate phase
                if hasattr(validator, 'pre_validate'):
                    await validator.pre_validate()
                
                # Main validation phase
                result = await validator.validate()
                
                # Post-validate phase
                if hasattr(validator, 'post_validate'):
                    await validator.post_validate(result)
                
                self._log_structured("debug", "Validator completed successfully", 
                                   validator=validator.name, issues_found=len(result.issues) if hasattr(result, 'issues') else 0)
                
                return result, validator.metrics
            
            return await self._retry_operation(
                validator_operation, 
                f"validator_{validator.name}", 
                validator.name
            )
    
    async def run_parallel_analysis(self, analyzers: List[BaseAnalyzer], validators: List[BaseValidator]) -> AnalysisResults:
        """
        Run analysis with parallel processing and comprehensive progress tracking.
        
        Args:
            analyzers: List of analyzers to run
            validators: List of validators to run
            
        Returns:
            Complete analysis results
        """
        start_time = datetime.now()
        
        async with self._error_context("parallel_analysis"):
            self._log_structured("info", "Starting parallel analysis workflow", 
                               analyzer_count=len(analyzers), 
                               validator_count=len(validators))
            
            # Initialize results
            results = AnalysisResults()
            total_components = len(analyzers) + len(validators)
            completed_components = 0
            
            # Create progress tracking callback
            def update_progress(component_name: str, progress_data: Dict[str, Any] = None):
                nonlocal completed_components
                completed_components += 1
                progress_percentage = (completed_components / total_components) * 100
                
                self._log_structured("info", f"Analysis progress update", 
                                   component=component_name,
                                   completed=completed_components,
                                   total=total_components,
                                   progress_percentage=round(progress_percentage, 1),
                                   **(progress_data or {}))
            
            # Phase 1: Run analyzers in parallel
            if analyzers:
                self._log_structured("info", "Phase 1: Running analyzers in parallel", 
                                   count=len(analyzers))
                
                # Create analyzer tasks with progress tracking
                analyzer_tasks = []
                for i, analyzer in enumerate(analyzers):
                    task = asyncio.create_task(
                        self._run_analyzer_with_progress(analyzer, i, len(analyzers)),
                        name=f"analyzer_{analyzer.name}"
                    )
                    analyzer_tasks.append((analyzer, task))
                
                # Wait for all analyzers to complete
                for analyzer, task in analyzer_tasks:
                    try:
                        issues, metrics = await task
                        self._merge_issues_into_results(results, issues, analyzer)
                        self._merge_metrics(results.metrics, metrics)
                        update_progress(analyzer.name, {"issues_found": len(issues)})
                        
                    except Exception as e:
                        self._log_structured("error", f"Analyzer {analyzer.name} failed", 
                                           error=str(e), error_type=type(e).__name__)
                        update_progress(analyzer.name, {"status": "failed", "error": str(e)})
                        continue
            
            # Phase 2: Run validators in parallel
            if validators:
                self._log_structured("info", "Phase 2: Running validators in parallel", 
                                   count=len(validators))
                
                # Create validator tasks with progress tracking
                validator_tasks = []
                for i, validator in enumerate(validators):
                    task = asyncio.create_task(
                        self._run_validator_with_progress(validator, i, len(validators)),
                        name=f"validator_{validator.name}"
                    )
                    validator_tasks.append((validator, task))
                
                # Wait for all validators to complete
                for validator, task in validator_tasks:
                    try:
                        validation_result, metrics = await task
                        # Extract issues from validation result
                        issues = validation_result.issues if hasattr(validation_result, 'issues') else []
                        self._merge_issues_into_results(results, issues, validator)
                        self._merge_metrics(results.metrics, metrics)
                        update_progress(validator.name, {"issues_found": len(issues)})
                        
                    except Exception as e:
                        self._log_structured("error", f"Validator {validator.name} failed", 
                                           error=str(e), error_type=type(e).__name__)
                        update_progress(validator.name, {"status": "failed", "error": str(e)})
                        continue
            
            # Finalize results
            results.timestamp = datetime.now()
            results.duration = results.timestamp - start_time
            
            self._log_structured("info", "Parallel analysis completed", 
                               total_issues=results.total_issues,
                               critical_issues=len(results.critical_issues),
                               duration=results.duration.total_seconds(),
                               success_rate=f"{((completed_components - len(self._errors)) / total_components * 100):.1f}%")
            
            return results
    
    def get_analysis_status(self) -> Dict[str, Any]:
        """
        Get current analysis status and progress information.
        
        Returns:
            Dictionary with current status information
        """
        return {
            "orchestrator_id": id(self),
            "config": {
                "target_directory": str(self.config.target_directory),
                "analysis_enabled": {
                    "quality": self.config.enable_quality_analysis,
                    "duplicates": self.config.enable_duplicate_detection,
                    "imports": self.config.enable_import_analysis,
                    "structure": self.config.enable_structure_analysis,
                },
                "validation_enabled": {
                    "coverage": self.config.check_test_coverage,
                    "config": self.config.validate_configs,
                    "docs": self.config.validate_docs,
                }
            },
            "components": {
                "analyzers": [{"name": a.name, "type": type(a).__name__} for a in self._analyzers],
                "validators": [{"name": v.name, "type": type(v).__name__} for v in self._validators],
                "cleaners": [{"name": c.name, "type": type(c).__name__} for c in self._cleaners],
                "reporters": [{"name": r.name, "type": type(r).__name__} for r in self._reporters],
            },
            "current_state": {
                "analysis_results": self._analysis_results is not None,
                "cleanup_results": self._cleanup_results is not None,
                "before_metrics": self._before_metrics is not None,
                "after_metrics": self._after_metrics is not None,
                "errors": len(self._errors),
                "warnings": len(self._warnings),
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def _run_validator_with_progress(self, validator: BaseValidator, completed: int, total: int):
        """Run a single validator with progress tracking and error handling."""
        async with self._error_context(f"validator_{validator.name}", validator.name):
            
            async def validator_operation():
                self._log_structured("debug", "Starting validator", 
                                   validator=validator.name, progress=f"{completed}/{total}")
                
                # Pre-validate phase
                if hasattr(validator, 'pre_validate'):
                    await validator.pre_validate()
                
                # Main validation phase
                result = await validator.validate()
                
                # Post-validate phase
                if hasattr(validator, 'post_validate'):
                    await validator.post_validate(result)
                
                self._log_structured("debug", "Validator completed successfully", 
                                   validator=validator.name, 
                                   success=getattr(result, 'success', True))
                
                return result, getattr(validator, 'metrics', CodebaseMetrics())
            
            try:
                return await self._retry_operation(
                    validator_operation, 
                    f"validator_{validator.name}", 
                    validator.name
                )
            except Exception as e:
                raise ValidationError(
                    f"Validator {validator.name} failed after retries", 
                    component=validator.name, 
                    original_error=e,
                    context={"progress": f"{completed}/{total}"}
                )
    
    def _should_run_analyzer(self, analyzer: BaseAnalyzer) -> bool:
        """Determine if an analyzer should run based on configuration."""
        analyzer_name = analyzer.name.lower()
        
        if 'quality' in analyzer_name:
            return self.config.enable_quality_analysis
        elif 'duplicate' in analyzer_name:
            return self.config.enable_duplicate_detection
        elif 'import' in analyzer_name:
            return self.config.enable_import_analysis
        elif 'structure' in analyzer_name:
            return self.config.enable_structure_analysis
        
        return True  # Run by default
    
    def _should_run_cleaner(self, cleaner: BaseCleaner) -> bool:
        """Determine if a cleaner should run based on configuration."""
        cleaner_name = cleaner.name.lower()
        
        if 'formatter' in cleaner_name:
            return self.config.auto_format
        elif 'import' in cleaner_name:
            return self.config.auto_fix_imports
        elif 'file' in cleaner_name or 'organizer' in cleaner_name:
            return self.config.auto_organize_files
        
        return False  # Don't run by default
    
    def _should_run_validator(self, validator: BaseValidator) -> bool:
        """Determine if a validator should run based on configuration."""
        validator_name = validator.name.lower()
        
        if 'coverage' in validator_name:
            return self.config.check_test_coverage
        elif 'config' in validator_name:
            return self.config.validate_configs
        elif 'doc' in validator_name:
            return self.config.validate_docs
        
        return True  # Run by default
    
    def _should_run_reporter(self, reporter: ReportGenerator) -> bool:
        """Determine if a reporter should run based on configuration."""
        reporter_name = reporter.name.lower()
        
        if 'html' in reporter_name:
            return self.config.generate_html_report
        elif 'json' in reporter_name:
            return self.config.generate_json_report
        elif 'markdown' in reporter_name:
            return self.config.generate_markdown_report
        
        return True  # Run by default
    
    def _merge_issues_into_results(self, results: AnalysisResults, issues: List, component) -> None:
        """Merge issues from a component into analysis results."""
        from migration_assistant.checkup.models import (
            QualityIssue, Duplicate, ImportIssue, StructureIssue,
            CoverageGap, ConfigIssue, DocIssue
        )
        
        for issue in issues:
            if isinstance(issue, QualityIssue):
                results.quality_issues.append(issue)
            elif isinstance(issue, Duplicate):
                results.duplicates.append(issue)
            elif isinstance(issue, ImportIssue):
                results.import_issues.append(issue)
            elif isinstance(issue, StructureIssue):
                results.structure_issues.append(issue)
            elif isinstance(issue, CoverageGap):
                results.coverage_gaps.append(issue)
            elif isinstance(issue, ConfigIssue):
                results.config_issues.append(issue)
            elif isinstance(issue, DocIssue):
                results.doc_issues.append(issue)
    
    def _merge_metrics(self, target_metrics: CodebaseMetrics, source_metrics: CodebaseMetrics) -> None:
        """Merge metrics from source into target."""
        # Add numeric metrics
        for attr in ['syntax_errors', 'style_violations', 'code_smells', 'complexity_issues',
                     'unused_imports', 'circular_imports', 'orphaned_modules', 'untested_functions',
                     'duplicate_blocks', 'duplicate_lines', 'misplaced_files', 'empty_directories']:
            if hasattr(source_metrics, attr):
                current_value = getattr(target_metrics, attr, 0)
                source_value = getattr(source_metrics, attr, 0)
                setattr(target_metrics, attr, current_value + source_value)
        
        # Update coverage percentage (take maximum)
        if source_metrics.test_coverage_percentage > target_metrics.test_coverage_percentage:
            target_metrics.test_coverage_percentage = source_metrics.test_coverage_percentage
    
    async def _create_backup(self) -> Path:
        """Create a backup of the target directory before cleanup."""
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"checkup_backup_{timestamp}"
        backup_path = self.config.backup_dir / backup_name
        
        # Ensure backup directory exists
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Creating backup: {self.config.target_directory} -> {backup_path}")
        
        # Create backup (excluding common ignore patterns)
        def ignore_patterns(dir_path, names):
            ignored = []
            for name in names:
                if any(pattern in name for pattern in self.config.exclude_patterns):
                    ignored.append(name)
                if name in self.config.exclude_dirs:
                    ignored.append(name)
            return ignored
        
        shutil.copytree(
            self.config.target_directory,
            backup_path,
            ignore=ignore_patterns,
            dirs_exist_ok=True
        )
        
        return backup_path
    
    async def _rollback_changes(self, backup_path: Path) -> None:
        """Rollback changes by restoring from backup."""
        import shutil
        
        if not backup_path.exists():
            raise CleanupError(f"Backup path does not exist: {backup_path}")
        
        self.logger.info(f"Rolling back changes from backup: {backup_path}")
        
        # Remove current directory contents (except excluded items)
        for item in self.config.target_directory.iterdir():
            if item.name not in self.config.exclude_dirs:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        
        # Restore from backup
        for item in backup_path.iterdir():
            dest = self.config.target_directory / item.name
            if item.is_file():
                shutil.copy2(item, dest)
            elif item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
        
        self.logger.info("Rollback completed successfully")
    
    async def _validate_cleanup_results(self, cleanup_results: CleanupResults, analysis_results: AnalysisResults) -> bool:
        """Validate that cleanup operations were successful and safe."""
        try:
            self.logger.info("Validating cleanup results")
            
            # Check if any critical files were accidentally removed
            critical_files = [
                self.config.target_directory / "pyproject.toml",
                self.config.target_directory / "setup.py",
                self.config.target_directory / "requirements.txt",
                self.config.target_directory / "README.md"
            ]
            
            for critical_file in critical_files:
                if critical_file.exists() and any(
                    removal.file_path == critical_file and removal.success 
                    for removal in cleanup_results.file_removals
                ):
                    self.logger.error(f"Critical file was removed: {critical_file}")
                    return False
            
            # Validate that moved files still exist at their new locations
            for file_move in cleanup_results.file_moves:
                if file_move.success and not file_move.destination_path.exists():
                    self.logger.error(f"Moved file does not exist at destination: {file_move.destination_path}")
                    return False
            
            # Check that Python files are still syntactically valid after formatting
            for formatting_change in cleanup_results.formatting_changes:
                if formatting_change.change_type in ["black", "isort"] and formatting_change.file_path.suffix == ".py":
                    try:
                        with open(formatting_change.file_path, 'r') as f:
                            compile(f.read(), str(formatting_change.file_path), 'exec')
                    except SyntaxError as e:
                        self.logger.error(f"Syntax error in formatted file {formatting_change.file_path}: {e}")
                        return False
            
            # Validate that import cleanups didn't break functionality
            for import_cleanup in cleanup_results.import_cleanups:
                if import_cleanup.removed_imports:
                    # Basic check - file should still be syntactically valid
                    try:
                        with open(import_cleanup.file_path, 'r') as f:
                            compile(f.read(), str(import_cleanup.file_path), 'exec')
                    except SyntaxError as e:
                        self.logger.error(f"Syntax error after import cleanup in {import_cleanup.file_path}: {e}")
                        return False
            
            # Check that the number of successful changes is reasonable
            if cleanup_results.successful_changes == 0 and analysis_results.total_issues > 0:
                self.logger.warning("No successful changes made despite having issues to fix")
                return False
            
            self.logger.info("Cleanup validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Cleanup validation failed: {e}")
            return False
    
    def _merge_cleanup_results(self, results: CleanupResults, cleanup_result, cleaner) -> None:
        """Merge cleanup results from a cleaner."""
        # This implementation depends on the specific structure returned by cleaners
        # For now, we'll implement a basic merge that handles common result types
        
        if hasattr(cleanup_result, 'formatting_changes'):
            results.formatting_changes.extend(cleanup_result.formatting_changes)
        
        if hasattr(cleanup_result, 'import_cleanups'):
            results.import_cleanups.extend(cleanup_result.import_cleanups)
        
        if hasattr(cleanup_result, 'file_moves'):
            results.file_moves.extend(cleanup_result.file_moves)
        
        if hasattr(cleanup_result, 'file_removals'):
            results.file_removals.extend(cleanup_result.file_removals)
        
        if hasattr(cleanup_result, 'auto_fixes'):
            results.auto_fixes.extend(cleanup_result.auto_fixes)
        
        # Log the merge for debugging
        self.logger.debug(f"Merged results from {cleaner.name}: {cleanup_result.success if hasattr(cleanup_result, 'success') else 'unknown'}")
    
    async def _merge_cleanup_results_comprehensive(self, results: CleanupResults, cleanup_result, cleaner) -> None:
        """Comprehensive merge of cleanup results with detailed tracking."""
        # Use the existing merge method
        self._merge_cleanup_results(results, cleanup_result, cleaner)
        
        # Add comprehensive tracking
        if not hasattr(results, 'cleaner_results'):
            results.cleaner_results = {}
        
        results.cleaner_results[cleaner.name] = {
            "success": getattr(cleanup_result, 'success', True),
            "changes_made": getattr(cleanup_result, 'changes_made', 0),
            "error_message": getattr(cleanup_result, 'error_message', None),
            "execution_time": getattr(cleanup_result, 'execution_time', 0),
            "files_processed": getattr(cleanup_result, 'files_processed', 0)
        }
    
    async def _create_comprehensive_backup(self) -> Path:
        """Create a comprehensive backup with metadata and verification."""
        import shutil
        import json
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"comprehensive_backup_{timestamp}"
        backup_path = self.config.backup_dir / backup_name
        
        # Ensure backup directory exists
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._log_structured("info", "Creating comprehensive backup", 
                           source=str(self.config.target_directory),
                           destination=str(backup_path))
        
        # Create backup with enhanced ignore patterns
        def comprehensive_ignore_patterns(dir_path, names):
            ignored = []
            for name in names:
                # Standard ignore patterns
                if any(pattern in name for pattern in self.config.exclude_patterns):
                    ignored.append(name)
                if name in self.config.exclude_dirs:
                    ignored.append(name)
                # Additional patterns for comprehensive backup
                if name.startswith('.') and name not in ['.gitignore', '.env.example']:
                    ignored.append(name)
                if name.endswith(('.log', '.tmp', '.cache')):
                    ignored.append(name)
            return ignored
        
        # Create the backup
        shutil.copytree(
            self.config.target_directory,
            backup_path,
            ignore=comprehensive_ignore_patterns,
            dirs_exist_ok=True
        )
        
        # Create backup metadata
        metadata = {
            "backup_timestamp": timestamp,
            "source_directory": str(self.config.target_directory),
            "backup_directory": str(backup_path),
            "config": {
                "auto_format": self.config.auto_format,
                "auto_fix_imports": self.config.auto_fix_imports,
                "auto_organize_files": self.config.auto_organize_files,
                "dry_run": self.config.dry_run
            },
            "file_count": len(list(backup_path.rglob("*"))),
            "total_size": sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file())
        }
        
        metadata_path = backup_path / "backup_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Verify backup integrity
        await self._verify_backup_integrity(backup_path, self.config.target_directory)
        
        return backup_path
    
    async def _verify_backup_integrity(self, backup_path: Path, source_path: Path) -> bool:
        """Verify backup integrity by comparing file counts and critical files."""
        try:
            # Compare file counts
            source_files = list(source_path.rglob("*.py"))
            backup_files = list(backup_path.rglob("*.py"))
            
            if len(backup_files) < len(source_files) * 0.9:  # Allow 10% variance
                raise CleanupError("Backup verification failed: significant file count mismatch")
            
            # Verify critical files exist in backup
            critical_files = ["pyproject.toml", "setup.py", "requirements.txt", "README.md"]
            for critical_file in critical_files:
                source_file = source_path / critical_file
                backup_file = backup_path / critical_file
                
                if source_file.exists() and not backup_file.exists():
                    raise CleanupError(f"Backup verification failed: missing critical file {critical_file}")
            
            return True
            
        except Exception as e:
            self._log_structured("error", "Backup verification failed", error=str(e))
            raise CleanupError(f"Backup verification failed: {e}")
    
    async def _rollback_changes_comprehensive(self, backup_path: Path) -> None:
        """Comprehensive rollback with verification and logging."""
        import shutil
        
        if not backup_path.exists():
            raise CleanupError(f"Backup path does not exist: {backup_path}")
        
        self._log_structured("info", "Starting comprehensive rollback", 
                           backup_path=str(backup_path))
        
        # Verify backup before rollback
        metadata_path = backup_path / "backup_metadata.json"
        if metadata_path.exists():
            try:
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                self._log_structured("info", "Backup metadata verified", 
                                   file_count=metadata.get("file_count", "unknown"))
            except Exception as e:
                self._log_structured("warning", "Could not read backup metadata", error=str(e))
        
        # Create temporary backup of current state before rollback
        temp_backup = self.config.backup_dir / f"pre_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copytree(self.config.target_directory, temp_backup, dirs_exist_ok=True)
            self._log_structured("info", "Created pre-rollback backup", path=str(temp_backup))
        except Exception as e:
            self._log_structured("warning", "Could not create pre-rollback backup", error=str(e))
        
        # Remove current directory contents (except excluded items)
        for item in self.config.target_directory.iterdir():
            if item.name not in self.config.exclude_dirs and item.name != "backup_metadata.json":
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    self._log_structured("warning", f"Could not remove {item}", error=str(e))
        
        # Restore from backup
        restored_files = 0
        for item in backup_path.iterdir():
            if item.name == "backup_metadata.json":
                continue
                
            dest = self.config.target_directory / item.name
            try:
                if item.is_file():
                    shutil.copy2(item, dest)
                    restored_files += 1
                elif item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                    restored_files += len(list(dest.rglob("*")))
            except Exception as e:
                self._log_structured("error", f"Failed to restore {item}", error=str(e))
                raise CleanupError(f"Rollback failed while restoring {item}: {e}")
        
        self._log_structured("info", "Comprehensive rollback completed", 
                           restored_files=restored_files)
    
    async def _validate_file_system_integrity(self, results: CleanupResults) -> bool:
        """Validate file system integrity after cleanup."""
        try:
            # Check that moved files exist at their destinations
            for file_move in results.file_moves:
                if file_move.success and not file_move.destination_path.exists():
                    self._log_structured("error", "Moved file missing at destination", 
                                       file=str(file_move.destination_path))
                    return False
            
            # Check that removed files are actually gone
            for file_removal in results.file_removals:
                if file_removal.success and file_removal.file_path.exists():
                    self._log_structured("error", "File still exists after removal", 
                                       file=str(file_removal.file_path))
                    return False
            
            return True
            
        except Exception as e:
            self._log_structured("error", "File system integrity validation failed", error=str(e))
            return False
    
    async def _validate_python_syntax(self, results: CleanupResults) -> bool:
        """Validate Python syntax of all modified files."""
        try:
            syntax_errors = []
            
            # Check formatted files
            for formatting_change in results.formatting_changes:
                if formatting_change.file_path.suffix == ".py":
                    try:
                        with open(formatting_change.file_path, 'r', encoding='utf-8') as f:
                            compile(f.read(), str(formatting_change.file_path), 'exec')
                    except SyntaxError as e:
                        syntax_errors.append(f"{formatting_change.file_path}: {e}")
            
            # Check files with import changes
            for import_cleanup in results.import_cleanups:
                try:
                    with open(import_cleanup.file_path, 'r', encoding='utf-8') as f:
                        compile(f.read(), str(import_cleanup.file_path), 'exec')
                except SyntaxError as e:
                    syntax_errors.append(f"{import_cleanup.file_path}: {e}")
            
            if syntax_errors:
                self._log_structured("error", "Syntax validation failed", 
                                   errors=syntax_errors[:5])  # Log first 5 errors
                return False
            
            return True
            
        except Exception as e:
            self._log_structured("error", "Python syntax validation failed", error=str(e))
            return False
    
    async def _validate_import_integrity(self, results: CleanupResults) -> bool:
        """Validate that import changes didn't break functionality."""
        try:
            # This is a basic validation - in a real implementation,
            # you might want to run a subset of tests or use static analysis
            
            for import_cleanup in results.import_cleanups:
                if import_cleanup.removed_imports:
                    # Check that the file can still be imported
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(
                            "test_module", import_cleanup.file_path
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                    except Exception as e:
                        self._log_structured("error", "Import integrity validation failed", 
                                           file=str(import_cleanup.file_path), error=str(e))
                        return False
            
            return True
            
        except Exception as e:
            self._log_structured("error", "Import integrity validation failed", error=str(e))
            return False
    
    async def _validate_critical_files(self, results: CleanupResults) -> bool:
        """Validate that critical files weren't accidentally modified or removed."""
        critical_files = [
            self.config.target_directory / "pyproject.toml",
            self.config.target_directory / "setup.py", 
            self.config.target_directory / "requirements.txt",
            self.config.target_directory / "README.md"
        ]
        
        for critical_file in critical_files:
            if critical_file.exists():
                # Check if it was accidentally removed
                for removal in results.file_removals:
                    if removal.file_path == critical_file and removal.success:
                        self._log_structured("error", "Critical file was removed", 
                                           file=str(critical_file))
                        return False
        
        return True
    
    async def _validate_cleanup_effectiveness(self, results: CleanupResults, 
                                           analysis_results: AnalysisResults) -> bool:
        """Validate that cleanup operations were effective."""
        # Check if any changes were made when issues were present
        if analysis_results.total_issues > 0 and results.total_changes == 0:
            self._log_structured("warning", "No changes made despite having issues to fix")
            return False
        
        # Check success rate of operations
        if results.successful_changes < results.total_changes * 0.8:  # 80% success rate
            self._log_structured("warning", "Low success rate for cleanup operations",
                               successful=results.successful_changes,
                               total=results.total_changes)
            return False
        
        return True


class ValidationResults:
    """Results from post-cleanup validation."""
    
    def __init__(self):
        self.validation_passed: bool = False
        self.file_system_integrity: bool = False
        self.syntax_validation: bool = False
        self.import_integrity: bool = False
        self.critical_files_intact: bool = False
        self.cleanup_effectiveness: bool = False
        self.risk_level: str = "unknown"
        self.validation_error: Optional[str] = None