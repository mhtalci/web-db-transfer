"""
Unit tests for the error handling system.
"""

import asyncio
import logging
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from migration_assistant.core.error_handler import (
    ErrorHandler,
    RetryHandler,
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
    ErrorContext,
    RetryConfig,
    ErrorInfo,
    create_connectivity_retry_config,
    create_transfer_retry_config,
    create_database_retry_config,
)
from migration_assistant.core.exceptions import (
    ConfigurationError,
    ValidationError,
    ConnectionError,
    TransferError,
    DatabaseError,
    BackupError,
    AuthenticationError,
)


class TestErrorHandler:
    """Test cases for ErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.error_handler = ErrorHandler(logger=self.logger)
    
    def test_categorize_configuration_error(self):
        """Test categorization of configuration errors."""
        error = ConfigurationError("Invalid configuration")
        context = ErrorContext(operation="test_op", step="config")
        
        error_info = self.error_handler.categorize_error(error, context)
        
        assert error_info.category == ErrorCategory.CONFIGURATION
        assert error_info.severity == ErrorSeverity.HIGH
        assert error_info.is_recoverable is True
        assert RecoveryStrategy.MANUAL in error_info.recovery_strategies
        assert len(error_info.remediation_steps) > 0
    
    def test_categorize_connection_error(self):
        """Test categorization of connection errors."""
        error = ConnectionError("Connection failed")
        
        error_info = self.error_handler.categorize_error(error)
        
        assert error_info.category == ErrorCategory.CONNECTIVITY
        assert error_info.severity == ErrorSeverity.HIGH
        assert error_info.is_recoverable is True
        assert RecoveryStrategy.RETRY in error_info.recovery_strategies
    
    def test_categorize_database_error(self):
        """Test categorization of database errors."""
        error = DatabaseError("Database operation failed")
        
        error_info = self.error_handler.categorize_error(error)
        
        assert error_info.category == ErrorCategory.DATABASE
        assert error_info.severity == ErrorSeverity.CRITICAL
        assert error_info.is_recoverable is True
    
    def test_categorize_backup_error(self):
        """Test categorization of backup errors."""
        error = BackupError("Backup failed")
        
        error_info = self.error_handler.categorize_error(error)
        
        assert error_info.category == ErrorCategory.BACKUP
        assert error_info.severity == ErrorSeverity.CRITICAL
        assert error_info.is_recoverable is False
    
    def test_categorize_unknown_error(self):
        """Test categorization of unknown errors."""
        error = ValueError("Unknown error")
        
        error_info = self.error_handler.categorize_error(error)
        
        assert error_info.category == ErrorCategory.UNKNOWN
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert error_info.is_recoverable is True
    
    def test_categorize_standard_python_error(self):
        """Test categorization of standard Python errors."""
        error = FileNotFoundError("File not found")
        
        error_info = self.error_handler.categorize_error(error)
        
        assert error_info.category == ErrorCategory.CONFIGURATION
        assert error_info.severity == ErrorSeverity.MEDIUM
    
    @pytest.mark.asyncio
    async def test_handle_error_logging(self):
        """Test error handling with logging."""
        error = ValidationError("Validation failed")
        context = ErrorContext(
            operation="validate",
            step="pre_migration",
            session_id="test-session",
            tenant_id="test-tenant"
        )
        
        error_info = await self.error_handler.handle_error(error, context)
        
        assert error_info.error == error
        assert error_info.context == context
        
        # Verify logging was called
        self.logger.warning.assert_called_once()
        call_args = self.logger.warning.call_args
        assert "Medium severity error occurred" in call_args[0][0]
        
        # Check log data
        log_data = call_args[1]["extra"]
        assert log_data["error_type"] == "ValidationError"
        assert log_data["category"] == ErrorCategory.VALIDATION.value
        assert log_data["session_id"] == "test-session"
        assert log_data["tenant_id"] == "test-tenant"
    
    @pytest.mark.asyncio
    async def test_handle_critical_error_logging(self):
        """Test handling of critical errors with appropriate logging."""
        error = DatabaseError("Critical database failure")
        
        await self.error_handler.handle_error(error)
        
        # Verify critical logging was called
        self.logger.critical.assert_called_once()
        self.logger.debug.assert_called_once()  # Traceback logging
    
    def test_error_context_creation(self):
        """Test ErrorContext creation and defaults."""
        context = ErrorContext(operation="test")
        
        assert context.operation == "test"
        assert context.step is None
        assert context.session_id is None
        assert isinstance(context.timestamp, datetime)
        assert isinstance(context.additional_data, dict)
    
    def test_remediation_guides_exist(self):
        """Test that remediation guides exist for all error categories."""
        for category in ErrorCategory:
            remediation_steps = self.error_handler._remediation_guides.get(category)
            assert remediation_steps is not None
            assert len(remediation_steps) > 0
    
    def test_recovery_strategies_exist(self):
        """Test that recovery strategies exist for all error categories."""
        for category in ErrorCategory:
            strategies = self.error_handler._recovery_strategies.get(category)
            assert strategies is not None
            assert len(strategies) > 0


class TestRetryHandler:
    """Test cases for RetryHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = Mock(spec=ErrorHandler)
        self.retry_handler = RetryHandler(error_handler=self.error_handler)
    
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful function execution without retries."""
        mock_func = Mock(return_value="success")
        
        result = await self.retry_handler.retry_with_backoff(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        self.error_handler.handle_error.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_async_function_execution(self):
        """Test async function execution."""
        async def async_func(value):
            return f"async_{value}"
        
        result = await self.retry_handler.retry_with_backoff(async_func, "test")
        
        assert result == "async_test"
    
    @pytest.mark.asyncio
    async def test_retry_with_eventual_success(self):
        """Test retry logic with eventual success."""
        call_count = 0
        
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,  # Short delay for testing
            retryable_exceptions=[ConnectionError]
        )
        
        with patch('asyncio.sleep'):  # Mock sleep to speed up test
            result = await self.retry_handler.retry_with_backoff(
                failing_func,
                retry_config=config
            )
        
        assert result == "success"
        assert call_count == 3
        assert self.error_handler.handle_error.call_count == 2  # Called for first 2 failures
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test retry logic when all attempts are exhausted."""
        def always_failing_func():
            raise TransferError("Transfer always fails")
        
        config = RetryConfig(
            max_attempts=2,
            base_delay=0.01,
            retryable_exceptions=[TransferError]
        )
        
        with patch('asyncio.sleep'):
            with pytest.raises(TransferError):
                await self.retry_handler.retry_with_backoff(
                    always_failing_func,
                    retry_config=config
                )
        
        assert self.error_handler.handle_error.call_count == 2
    
    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        def func_with_non_retryable_error():
            raise AuthenticationError("Auth failed")
        
        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=[ConnectionError]  # Auth error not in list
        )
        
        with pytest.raises(AuthenticationError):
            await self.retry_handler.retry_with_backoff(
                func_with_non_retryable_error,
                retry_config=config
            )
        
        # Should only be called once since it's not retryable
        assert self.error_handler.handle_error.call_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        call_count = 0
        delays = []
        
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection failed")
        
        async def mock_sleep(delay):
            delays.append(delay)
        
        config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False,  # Disable jitter for predictable testing
            retryable_exceptions=[ConnectionError]
        )
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with pytest.raises(ConnectionError):
                await self.retry_handler.retry_with_backoff(
                    failing_func,
                    retry_config=config
                )
        
        # Should have 2 delays (for 2 retries)
        assert len(delays) == 2
        assert delays[0] == 1.0  # First retry: base_delay * 2^0
        assert delays[1] == 2.0  # Second retry: base_delay * 2^1
    
    @pytest.mark.asyncio
    async def test_max_delay_limit(self):
        """Test that delay doesn't exceed max_delay."""
        def failing_func():
            raise ConnectionError("Connection failed")
        
        delays = []
        
        async def mock_sleep(delay):
            delays.append(delay)
        
        config = RetryConfig(
            max_attempts=5,
            base_delay=10.0,
            max_delay=15.0,
            exponential_base=2.0,
            jitter=False,
            retryable_exceptions=[ConnectionError]
        )
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with pytest.raises(ConnectionError):
                await self.retry_handler.retry_with_backoff(
                    failing_func,
                    retry_config=config
                )
        
        # All delays should be capped at max_delay
        for delay in delays:
            assert delay <= config.max_delay
    
    @pytest.mark.asyncio
    async def test_jitter_application(self):
        """Test that jitter is applied to delays."""
        def failing_func():
            raise ConnectionError("Connection failed")
        
        delays = []
        
        async def mock_sleep(delay):
            delays.append(delay)
        
        config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            jitter=True,
            retryable_exceptions=[ConnectionError]
        )
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with pytest.raises(ConnectionError):
                await self.retry_handler.retry_with_backoff(
                    failing_func,
                    retry_config=config
                )
        
        # With jitter, delays should be between 50% and 100% of calculated delay
        expected_base_delay = 2.0
        assert len(delays) >= 1
        assert delays[0] >= expected_base_delay * 0.5
        assert delays[0] <= expected_base_delay
    
    @pytest.mark.asyncio
    async def test_retry_count_tracking(self):
        """Test that retry count is tracked on exceptions."""
        call_count = 0
        
        def failing_func():
            nonlocal call_count
            call_count += 1
            error = ConnectionError("Connection failed")
            return error
        
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=[ConnectionError]
        )
        
        # Mock the error handler to capture the exceptions
        handled_errors = []
        
        async def mock_handle_error(error, context, retry_config):
            handled_errors.append(error)
            return Mock()
        
        self.error_handler.handle_error.side_effect = mock_handle_error
        
        def always_failing():
            raise ConnectionError("Always fails")
        
        with patch('asyncio.sleep'):
            with pytest.raises(ConnectionError):
                await self.retry_handler.retry_with_backoff(
                    always_failing,
                    retry_config=config
                )
        
        # Check that retry counts were set on exceptions
        for i, error in enumerate(handled_errors):
            assert hasattr(error, '_retry_count')
            assert getattr(error, '_retry_count') == i + 1


class TestRetryConfigurations:
    """Test cases for retry configuration helpers."""
    
    def test_connectivity_retry_config(self):
        """Test connectivity retry configuration."""
        config = create_connectivity_retry_config()
        
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 30.0
        assert ConnectionError in config.retryable_exceptions
        assert TimeoutError in config.retryable_exceptions
    
    def test_transfer_retry_config(self):
        """Test transfer retry configuration."""
        config = create_transfer_retry_config()
        
        assert config.max_attempts == 3
        assert config.base_delay == 5.0
        assert config.max_delay == 60.0
        assert TransferError in config.retryable_exceptions
        assert ConnectionError in config.retryable_exceptions
    
    def test_database_retry_config(self):
        """Test database retry configuration."""
        config = create_database_retry_config()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 10.0
        assert DatabaseError in config.retryable_exceptions
        assert ConnectionError in config.retryable_exceptions


class TestErrorInfo:
    """Test cases for ErrorInfo dataclass."""
    
    def test_error_info_creation(self):
        """Test ErrorInfo creation with all fields."""
        error = ValidationError("Test error")
        context = ErrorContext(operation="test")
        
        error_info = ErrorInfo(
            error=error,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            recovery_strategies=[RecoveryStrategy.MANUAL],
            remediation_steps=["Step 1", "Step 2"],
            traceback_str="traceback here",
            retry_count=2,
            is_recoverable=True
        )
        
        assert error_info.error == error
        assert error_info.category == ErrorCategory.VALIDATION
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert error_info.context == context
        assert error_info.retry_count == 2
        assert error_info.is_recoverable is True
        assert len(error_info.recovery_strategies) == 1
        assert len(error_info.remediation_steps) == 2


if __name__ == "__main__":
    pytest.main([__file__])