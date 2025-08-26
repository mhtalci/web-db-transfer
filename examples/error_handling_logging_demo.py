#!/usr/bin/env python3
"""
Demonstration of the comprehensive error handling and logging system.

This example shows how to use the error handling and logging components
together in a migration scenario.
"""

import asyncio
import tempfile
from pathlib import Path

from migration_assistant.core.error_handler import (
    ErrorHandler,
    RetryHandler,
    ErrorContext,
    RetryConfig,
    create_connectivity_retry_config,
)
from migration_assistant.core.exceptions import (
    ConnectionError,
    TransferError,
    ValidationError,
)
from migration_assistant.utils.logging import (
    LogManager,
    LogCategory,
    MigrationLogger,
)


class MockMigrationService:
    """Mock migration service to demonstrate error handling and logging."""
    
    def __init__(self, logger: MigrationLogger):
        self.logger = logger
        self.error_handler = ErrorHandler()
        self.retry_handler = RetryHandler(self.error_handler)
        self.attempt_count = 0
    
    async def connect_to_source(self) -> bool:
        """Simulate connecting to source system with potential failures."""
        self.attempt_count += 1
        
        self.logger.info(
            f"Attempting to connect to source system (attempt {self.attempt_count})",
            category=LogCategory.SYSTEM,
            operation="connect_source"
        )
        
        # Simulate failure on first two attempts
        if self.attempt_count <= 2:
            error = ConnectionError(f"Connection failed on attempt {self.attempt_count}")
            context = ErrorContext(
                operation="connect_source",
                step="initial_connection",
                session_id=self.logger.session_id
            )
            await self.error_handler.handle_error(error, context)
            raise error
        
        self.logger.info(
            "Successfully connected to source system",
            category=LogCategory.SYSTEM,
            operation="connect_source"
        )
        return True
    
    async def transfer_files(self, file_count: int = 100) -> bool:
        """Simulate file transfer with progress logging."""
        self.logger.step_start("file_transfer", "migration")
        
        try:
            for i in range(file_count):
                # Simulate transfer progress
                transferred = i + 1
                progress_percent = (transferred / file_count) * 100
                transfer_rate = 10.5  # MB/s
                
                if i % 20 == 0:  # Log progress every 20 files
                    self.logger.log_transfer_progress(
                        transferred_bytes=transferred * 1024 * 1024,  # 1MB per file
                        total_bytes=file_count * 1024 * 1024,
                        transfer_rate=transfer_rate,
                        operation="file_transfer"
                    )
                
                # Simulate occasional transfer error
                if i == 50:
                    raise TransferError("Network timeout during file transfer")
                
                await asyncio.sleep(0.01)  # Simulate transfer time
            
            self.logger.step_complete("file_transfer", 2.5, "migration")
            return True
            
        except Exception as e:
            self.logger.step_failed("file_transfer", str(e), "migration", "T001")
            raise
    
    async def validate_migration(self) -> bool:
        """Simulate migration validation."""
        self.logger.info(
            "Starting migration validation",
            category=LogCategory.VALIDATION,
            operation="validation"
        )
        
        # Simulate various validation checks
        validations = [
            ("connectivity", True, {"host": "source.example.com"}),
            ("file_integrity", True, {"files_checked": 100, "checksum_matches": 100}),
            ("database_schema", False, {"missing_tables": ["temp_table"]}),
            ("permissions", True, {"read_access": True, "write_access": True}),
        ]
        
        all_passed = True
        for validation_type, passed, details in validations:
            self.logger.log_validation_result(validation_type, passed, details)
            if not passed:
                all_passed = False
        
        if not all_passed:
            raise ValidationError("Migration validation failed")
        
        return True
    
    async def simulate_database_operations(self):
        """Simulate database operations with logging."""
        operations = [
            ("CREATE_TABLE", "users", None, 0.5),
            ("INSERT", "users", 1000, 2.3),
            ("CREATE_INDEX", "users", None, 1.2),
            ("UPDATE", "users", 500, 1.8),
        ]
        
        for operation, table, rows, duration in operations:
            self.logger.log_database_operation(
                operation=operation,
                table_name=table,
                rows_processed=rows,
                duration=duration
            )
            await asyncio.sleep(0.1)  # Simulate operation time
    
    async def log_security_events(self):
        """Simulate security event logging."""
        events = [
            ("authentication_success", "low", {"user": "admin", "method": "api_key"}),
            ("permission_check", "medium", {"resource": "database", "granted": True}),
            ("data_access", "medium", {"table": "users", "operation": "read"}),
        ]
        
        for event_type, severity, details in events:
            self.logger.log_security_event(event_type, severity, details)


async def demonstrate_error_handling_and_logging():
    """Demonstrate the error handling and logging system."""
    print("🚀 Starting Error Handling and Logging Demonstration")
    print("=" * 60)
    
    # Set up temporary directory for logs
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Configure logging
        log_config = {
            'level': 'INFO',
            'log_file': str(temp_path / 'migration.log'),
            'audit_log_file': str(temp_path / 'audit.log'),
            'session_logs_dir': str(temp_path / 'sessions'),
            'structured_logging': True,
            'rich_console': True,
        }
        
        # Create log manager
        log_manager = LogManager(log_config)
        
        # Get session logger
        session_logger = log_manager.get_session_logger(
            session_id="demo-session-001",
            tenant_id="demo-tenant",
            user_id="demo-user"
        )
        
        # Create mock migration service
        migration_service = MockMigrationService(session_logger)
        
        print("📝 Logging configuration:")
        print(f"  - Main log: {log_config['log_file']}")
        print(f"  - Audit log: {log_config['audit_log_file']}")
        print(f"  - Session logs: {log_config['session_logs_dir']}")
        print(f"  - Structured logging: {log_config['structured_logging']}")
        print()
        
        # Log audit events
        print("🔐 Logging audit events...")
        log_manager.log_audit_event(
            "migration_started",
            user_id="demo-user",
            session_id="demo-session-001",
            tenant_id="demo-tenant",
            details={"source": "legacy_system", "destination": "cloud_platform"}
        )
        
        # Demonstrate retry logic with connection
        print("🔄 Demonstrating retry logic with connection failures...")
        try:
            retry_config = create_connectivity_retry_config()
            await migration_service.retry_handler.retry_with_backoff(
                migration_service.connect_to_source,
                retry_config=retry_config,
                context=ErrorContext(
                    operation="connect_source",
                    session_id="demo-session-001"
                )
            )
            print("✅ Connection successful after retries")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
        
        print()
        
        # Demonstrate file transfer with error handling
        print("📁 Demonstrating file transfer with error handling...")
        try:
            transfer_retry_config = RetryConfig(
                max_attempts=2,
                base_delay=0.1,
                retryable_exceptions=[TransferError]
            )
            
            await migration_service.retry_handler.retry_with_backoff(
                migration_service.transfer_files,
                50,  # Transfer 50 files
                retry_config=transfer_retry_config,
                context=ErrorContext(
                    operation="file_transfer",
                    session_id="demo-session-001"
                )
            )
            print("✅ File transfer completed")
        except TransferError as e:
            print(f"❌ File transfer failed: {e}")
        
        print()
        
        # Demonstrate validation with mixed results
        print("✅ Demonstrating validation with mixed results...")
        try:
            await migration_service.validate_migration()
            print("✅ All validations passed")
        except ValidationError as e:
            print(f"⚠️  Some validations failed: {e}")
        
        print()
        
        # Demonstrate database operations logging
        print("🗄️  Demonstrating database operations logging...")
        await migration_service.simulate_database_operations()
        print("✅ Database operations completed")
        
        print()
        
        # Demonstrate security event logging
        print("🔒 Demonstrating security event logging...")
        await migration_service.log_security_events()
        print("✅ Security events logged")
        
        print()
        
        # Show performance summary
        print("📊 Performance Summary:")
        performance_summary = session_logger.get_performance_summary()
        for metric_name, stats in performance_summary.items():
            print(f"  - {metric_name}:")
            for stat_name, value in stats.items():
                print(f"    {stat_name}: {value:.2f}")
        
        print()
        
        # Show log statistics
        print("📈 Log Statistics:")
        log_stats = log_manager.get_log_statistics()
        for key, value in log_stats.items():
            print(f"  - {key}: {value}")
        
        print()
        
        # Show log file contents
        print("📄 Log File Contents:")
        print("-" * 40)
        
        if Path(log_config['log_file']).exists():
            print("Main Log (last 5 lines):")
            with open(log_config['log_file'], 'r') as f:
                lines = f.readlines()
                for line in lines[-5:]:
                    print(f"  {line.strip()}")
        
        print()
        
        if Path(log_config['audit_log_file']).exists():
            print("Audit Log:")
            with open(log_config['audit_log_file'], 'r') as f:
                content = f.read()
                print(f"  {content.strip()}")
        
        print()
        print("🎉 Demonstration completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demonstrate_error_handling_and_logging())