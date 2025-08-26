"""
Unit tests for the comprehensive logging and monitoring system.
"""

import json
import logging
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from migration_assistant.utils.logging import (
    LogLevel,
    LogCategory,
    LogEntry,
    StructuredFormatter,
    AuditLogger,
    PerformanceMonitor,
    MigrationLogger,
    LogManager,
    setup_logging,
    get_logger,
)


class TestLogEntry:
    """Test cases for LogEntry dataclass."""
    
    def test_log_entry_creation(self):
        """Test LogEntry creation with default values."""
        entry = LogEntry(message="Test message")
        
        assert entry.message == "Test message"
        assert entry.level == LogLevel.INFO
        assert entry.category == LogCategory.SYSTEM
        assert isinstance(entry.timestamp, datetime)
        assert entry.session_id is None
        assert isinstance(entry.metadata, dict)
    
    def test_log_entry_with_all_fields(self):
        """Test LogEntry creation with all fields."""
        timestamp = datetime.now()
        metadata = {"key": "value"}
        
        entry = LogEntry(
            timestamp=timestamp,
            level=LogLevel.ERROR,
            category=LogCategory.MIGRATION,
            message="Error message",
            session_id="test-session",
            tenant_id="test-tenant",
            user_id="test-user",
            operation="test-op",
            step="test-step",
            duration=1.5,
            error_code="E001",
            metadata=metadata
        )
        
        assert entry.timestamp == timestamp
        assert entry.level == LogLevel.ERROR
        assert entry.category == LogCategory.MIGRATION
        assert entry.message == "Error message"
        assert entry.session_id == "test-session"
        assert entry.tenant_id == "test-tenant"
        assert entry.user_id == "test-user"
        assert entry.operation == "test-op"
        assert entry.step == "test-step"
        assert entry.duration == 1.5
        assert entry.error_code == "E001"
        assert entry.metadata == metadata
    
    def test_log_entry_to_dict(self):
        """Test LogEntry conversion to dictionary."""
        entry = LogEntry(
            message="Test message",
            session_id="test-session",
            metadata={"key": "value"}
        )
        
        data = entry.to_dict()
        
        assert isinstance(data, dict)
        assert data["message"] == "Test message"
        assert data["session_id"] == "test-session"
        assert data["metadata"]["key"] == "value"
        assert isinstance(data["timestamp"], str)  # Should be ISO format
    
    def test_log_entry_to_json(self):
        """Test LogEntry conversion to JSON."""
        entry = LogEntry(message="Test message", session_id="test-session")
        
        json_str = entry.to_json()
        
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["message"] == "Test message"
        assert data["session_id"] == "test-session"


class TestStructuredFormatter:
    """Test cases for StructuredFormatter."""
    
    def test_format_with_log_entry(self):
        """Test formatting with LogEntry in record."""
        formatter = StructuredFormatter()
        
        log_entry = LogEntry(message="Test message", session_id="test-session")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None
        )
        record.log_entry = log_entry
        
        formatted = formatter.format(record)
        
        assert isinstance(formatted, str)
        data = json.loads(formatted)
        assert data["message"] == "Test message"
        assert data["session_id"] == "test-session"
    
    def test_format_without_log_entry(self):
        """Test formatting without LogEntry in record."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        formatted = formatter.format(record)
        
        assert isinstance(formatted, str)
        data = json.loads(formatted)
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["metadata"]["module"] == "test_module"
        assert data["metadata"]["function"] == "test_function"
        assert data["metadata"]["line"] == 42


class TestAuditLogger:
    """Test cases for AuditLogger."""
    
    def test_audit_logger_creation(self):
        """Test AuditLogger creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "audit.log"
            
            audit_logger = AuditLogger(str(log_file))
            
            assert audit_logger.logger.name == "migration_assistant.audit"
            assert log_file.parent.exists()
    
    def test_log_audit_event(self):
        """Test logging audit events."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "audit.log"
            
            audit_logger = AuditLogger(str(log_file))
            
            audit_logger.log_event(
                "user_login",
                user_id="test-user",
                session_id="test-session",
                tenant_id="test-tenant",
                details={"ip_address": "192.168.1.1"}
            )
            
            # Check that log file was created and contains data
            assert log_file.exists()
            content = log_file.read_text()
            assert "user_login" in content
            assert "test-user" in content


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.monitor = PerformanceMonitor(self.logger)
    
    def test_record_metric(self):
        """Test recording performance metrics."""
        self.monitor.record_metric("test_metric", 1.5)
        
        assert "test_metric" in self.monitor._metrics
        assert self.monitor._metrics["test_metric"] == [1.5]
        self.logger.info.assert_called_once()
    
    def test_record_multiple_metrics(self):
        """Test recording multiple values for same metric."""
        self.monitor.record_metric("test_metric", 1.0)
        self.monitor.record_metric("test_metric", 2.0)
        self.monitor.record_metric("test_metric", 3.0)
        
        assert len(self.monitor._metrics["test_metric"]) == 3
        assert self.monitor._metrics["test_metric"] == [1.0, 2.0, 3.0]
    
    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        self.monitor.record_metric("test_metric", 1.0)
        self.monitor.record_metric("test_metric", 2.0)
        self.monitor.record_metric("test_metric", 3.0)
        
        summary = self.monitor.get_metrics_summary("test_metric")
        
        assert summary["count"] == 3
        assert summary["min"] == 1.0
        assert summary["max"] == 3.0
        assert summary["avg"] == 2.0
        assert summary["total"] == 6.0
    
    def test_get_metrics_summary_empty(self):
        """Test getting summary for non-existent metric."""
        summary = self.monitor.get_metrics_summary("nonexistent")
        
        assert summary == {}
    
    def test_clear_metrics(self):
        """Test clearing metrics."""
        self.monitor.record_metric("metric1", 1.0)
        self.monitor.record_metric("metric2", 2.0)
        
        # Clear specific metric
        self.monitor.clear_metrics("metric1")
        assert "metric1" not in self.monitor._metrics
        assert "metric2" in self.monitor._metrics
        
        # Clear all metrics
        self.monitor.clear_metrics()
        assert len(self.monitor._metrics) == 0


class TestMigrationLogger:
    """Test cases for MigrationLogger."""
    
    def test_migration_logger_creation(self):
        """Test MigrationLogger creation."""
        logger = MigrationLogger("test-session")
        
        assert logger.session_id == "test-session"
        assert logger.tenant_id is None
        assert logger.user_id is None
        assert not logger.structured
        assert isinstance(logger.performance_monitor, PerformanceMonitor)
    
    def test_migration_logger_with_all_params(self):
        """Test MigrationLogger creation with all parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "session.log"
            
            logger = MigrationLogger(
                session_id="test-session",
                tenant_id="test-tenant",
                user_id="test-user",
                log_file=str(log_file),
                structured=True
            )
            
            assert logger.session_id == "test-session"
            assert logger.tenant_id == "test-tenant"
            assert logger.user_id == "test-user"
            assert logger.structured is True
    
    def test_structured_logging(self):
        """Test structured logging functionality."""
        with patch('migration_assistant.utils.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = MigrationLogger("test-session", structured=True)
            
            logger.info("Test message", category=LogCategory.VALIDATION)
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Test message" in call_args[0]
            assert 'log_entry' in call_args[1]['extra']
    
    def test_step_logging(self):
        """Test step-related logging methods."""
        with patch('migration_assistant.utils.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = MigrationLogger("test-session")
            
            # Test step start
            logger.step_start("test_step", "test_operation")
            mock_logger.info.assert_called()
            
            # Test step complete
            logger.step_complete("test_step", 1.5, "test_operation")
            assert mock_logger.info.call_count >= 2
            
            # Test step failed
            logger.step_failed("test_step", "Test error", "test_operation", "E001")
            mock_logger.error.assert_called()
    
    def test_transfer_progress_logging(self):
        """Test transfer progress logging."""
        with patch('migration_assistant.utils.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = MigrationLogger("test-session")
            
            logger.log_transfer_progress(
                transferred_bytes=500,
                total_bytes=1000,
                transfer_rate=10.5
            )
            
            # Should be called multiple times (transfer progress + performance metrics)
            assert mock_logger.info.call_count >= 1
            
            # Check that one of the calls contains the progress percentage
            found_progress = False
            for call in mock_logger.info.call_args_list:
                if "50.0%" in call[0][0]:
                    found_progress = True
                    break
            assert found_progress
    
    def test_database_operation_logging(self):
        """Test database operation logging."""
        with patch('migration_assistant.utils.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = MigrationLogger("test-session")
            
            logger.log_database_operation(
                operation="INSERT",
                table_name="users",
                rows_processed=100,
                duration=2.5
            )
            
            # Should be called multiple times (main log + performance metrics)
            assert mock_logger.info.call_count >= 1
            
            # Check that one of the calls contains the database operation details
            found_operation = False
            for call in mock_logger.info.call_args_list:
                message = call[0][0]
                if "INSERT" in message and "users" in message and "100 rows" in message:
                    found_operation = True
                    break
            assert found_operation
    
    def test_validation_result_logging(self):
        """Test validation result logging."""
        with patch('migration_assistant.utils.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = MigrationLogger("test-session")
            
            # Test passed validation
            logger.log_validation_result("connectivity", True, {"host": "example.com"})
            mock_logger.info.assert_called()
            
            # Test failed validation
            logger.log_validation_result("connectivity", False, {"error": "timeout"})
            mock_logger.warning.assert_called()
    
    def test_security_event_logging(self):
        """Test security event logging."""
        with patch('migration_assistant.utils.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = MigrationLogger("test-session")
            
            logger.log_security_event(
                "failed_login",
                severity="high",
                details={"ip": "192.168.1.1", "attempts": 3}
            )
            
            mock_logger.warning.assert_called()
    
    def test_performance_summary(self):
        """Test getting performance summary."""
        logger = MigrationLogger("test-session")
        
        # Record some metrics through step completion
        with patch('migration_assistant.utils.logging.get_logger'):
            logger.step_complete("test_step", 1.5)
            
            summary = logger.get_performance_summary()
            
            assert isinstance(summary, dict)
            # Should have recorded step duration metric
            assert any("step_duration" in key for key in summary.keys())


class TestLogManager:
    """Test cases for LogManager."""
    
    def test_log_manager_creation(self):
        """Test LogManager creation."""
        manager = LogManager()
        
        assert isinstance(manager.config, dict)
        assert isinstance(manager.loggers, dict)
        assert manager.audit_logger is None
    
    def test_log_manager_with_config(self):
        """Test LogManager creation with configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                'level': 'DEBUG',
                'log_file': str(Path(temp_dir) / 'main.log'),
                'audit_log_file': str(Path(temp_dir) / 'audit.log'),
                'structured_logging': True,
                'session_logs_dir': str(Path(temp_dir) / 'sessions')
            }
            
            manager = LogManager(config)
            
            assert manager.config == config
            assert manager.audit_logger is not None
    
    def test_get_session_logger(self):
        """Test getting session-specific loggers."""
        manager = LogManager()
        
        logger1 = manager.get_session_logger("session1", "tenant1", "user1")
        logger2 = manager.get_session_logger("session1", "tenant1", "user1")  # Same logger
        logger3 = manager.get_session_logger("session2", "tenant1", "user1")  # Different logger
        
        assert logger1 is logger2  # Should return same instance
        assert logger1 is not logger3  # Should return different instance
        assert len(manager.loggers) == 2
    
    def test_log_audit_event(self):
        """Test logging audit events through manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {'audit_log_file': str(Path(temp_dir) / 'audit.log')}
            manager = LogManager(config)
            
            manager.log_audit_event(
                "test_event",
                user_id="test-user",
                session_id="test-session",
                details={"key": "value"}
            )
            
            # Verify audit log file was created
            audit_file = Path(temp_dir) / 'audit.log'
            assert audit_file.exists()
    
    def test_cleanup_old_logs(self):
        """Test cleaning up old log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_logs_dir = Path(temp_dir) / 'sessions'
            session_logs_dir.mkdir()
            
            # Create old log file
            old_log = session_logs_dir / 'old_session.log'
            old_log.write_text("old log content")
            
            # Set modification time to 40 days ago
            import os
            old_time = time.time() - (40 * 24 * 60 * 60)
            os.utime(old_log, (old_time, old_time))
            
            # Create recent log file
            recent_log = session_logs_dir / 'recent_session.log'
            recent_log.write_text("recent log content")
            
            config = {'session_logs_dir': str(session_logs_dir)}
            manager = LogManager(config)
            
            manager.cleanup_old_logs(days_to_keep=30)
            
            # Old log should be deleted, recent log should remain
            assert not old_log.exists()
            assert recent_log.exists()
    
    def test_get_log_statistics(self):
        """Test getting logging statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                'log_file': str(Path(temp_dir) / 'main.log'),
                'audit_log_file': str(Path(temp_dir) / 'audit.log'),
                'structured_logging': True
            }
            
            # Create log files with some content
            Path(config['log_file']).write_text("main log content")
            Path(config['audit_log_file']).write_text("audit log content")
            
            manager = LogManager(config)
            
            # Create some session loggers
            manager.get_session_logger("session1")
            manager.get_session_logger("session2")
            
            stats = manager.get_log_statistics()
            
            assert stats['active_sessions'] == 2
            assert stats['audit_logging_enabled'] is True
            assert stats['structured_logging'] is True
            assert 'main_log_size_mb' in stats
            assert 'audit_log_size_mb' in stats


class TestSetupLogging:
    """Test cases for setup_logging function."""
    
    def test_basic_setup(self):
        """Test basic logging setup."""
        logger = setup_logging(level="DEBUG")
        
        assert logger.name == "migration_assistant"
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) > 0
    
    def test_setup_with_file_logging(self):
        """Test logging setup with file handler."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            
            logger = setup_logging(
                level="INFO",
                log_file=str(log_file),
                rich_console=False
            )
            
            assert len(logger.handlers) == 2  # Console + File
            assert log_file.parent.exists()
    
    def test_setup_with_structured_logging(self):
        """Test logging setup with structured logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "structured.log"
            
            logger = setup_logging(
                log_file=str(log_file),
                structured_logging=True,
                rich_console=False
            )
            
            # Test that structured formatter is used
            file_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler = handler
                    break
            
            assert file_handler is not None
            assert isinstance(file_handler.formatter, StructuredFormatter)
    
    def test_setup_with_log_rotation(self):
        """Test logging setup with log rotation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "rotating.log"
            
            logger = setup_logging(
                log_file=str(log_file),
                log_rotation=True,
                max_log_size=1024,  # 1KB for testing
                backup_count=3
            )
            
            # Find the rotating file handler
            rotating_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    rotating_handler = handler
                    break
            
            assert rotating_handler is not None
            assert rotating_handler.maxBytes == 1024
            assert rotating_handler.backupCount == 3


if __name__ == "__main__":
    pytest.main([__file__])