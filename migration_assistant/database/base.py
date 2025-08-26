"""Base database migrator abstract class and related models."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

from .config import DatabaseConfig, DatabaseConfigUnion


class MigrationStatus(str, Enum):
    """Migration status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MigrationMethod(str, Enum):
    """Database migration methods."""
    DUMP_RESTORE = "dump_restore"
    DIRECT_TRANSFER = "direct_transfer"
    STREAMING = "streaming"
    CLOUD_NATIVE = "cloud_native"
    BULK_COPY = "bulk_copy"


class MigrationResult(BaseModel):
    """Result of a database migration operation."""
    status: MigrationStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    records_migrated: int = 0
    tables_migrated: int = 0
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate migration duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def is_successful(self) -> bool:
        """Check if migration was successful."""
        return self.status == MigrationStatus.COMPLETED and not self.errors


class MigrationProgress(BaseModel):
    """Progress information for ongoing migration."""
    current_table: Optional[str] = None
    tables_completed: int = 0
    total_tables: int = 0
    records_processed: int = 0
    estimated_total_records: Optional[int] = None
    current_operation: str = ""
    
    @property
    def table_progress_percentage(self) -> float:
        """Calculate table progress percentage."""
        if self.total_tables == 0:
            return 0.0
        return (self.tables_completed / self.total_tables) * 100
    
    @property
    def record_progress_percentage(self) -> Optional[float]:
        """Calculate record progress percentage if total is known."""
        if self.estimated_total_records and self.estimated_total_records > 0:
            return (self.records_processed / self.estimated_total_records) * 100
        return None


class DatabaseMigrator(ABC):
    """Abstract base class for database migrators."""
    
    def __init__(self, source_config: DatabaseConfigUnion, destination_config: DatabaseConfigUnion):
        """Initialize the migrator with source and destination configurations.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
        """
        self.source_config = source_config
        self.destination_config = destination_config
        self._source_connection = None
        self._destination_connection = None
    
    @abstractmethod
    async def connect_source(self) -> bool:
        """Connect to the source database.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def connect_destination(self) -> bool:
        """Connect to the destination database.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from both source and destination databases."""
        pass
    
    @abstractmethod
    async def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to both source and destination databases.
        
        Returns:
            Dictionary with 'source' and 'destination' connectivity status
        """
        pass
    
    @abstractmethod
    async def get_schema_info(self, config: DatabaseConfigUnion) -> Dict[str, Any]:
        """Get schema information from a database.
        
        Args:
            config: Database configuration
            
        Returns:
            Dictionary containing schema information
        """
        pass
    
    @abstractmethod
    async def validate_compatibility(self) -> List[str]:
        """Validate compatibility between source and destination databases.
        
        Returns:
            List of compatibility issues (empty if compatible)
        """
        pass
    
    @abstractmethod
    async def estimate_migration_size(self) -> Dict[str, Any]:
        """Estimate the size and complexity of the migration.
        
        Returns:
            Dictionary with size estimates (tables, records, data size, etc.)
        """
        pass
    
    @abstractmethod
    async def migrate_schema(self) -> MigrationResult:
        """Migrate database schema from source to destination.
        
        Returns:
            Migration result with status and details
        """
        pass
    
    @abstractmethod
    async def migrate_data(self, 
                          tables: Optional[List[str]] = None,
                          batch_size: int = 1000,
                          method: MigrationMethod = MigrationMethod.DUMP_RESTORE) -> AsyncGenerator[MigrationProgress, None]:
        """Migrate data from source to destination with progress updates.
        
        Args:
            tables: List of tables to migrate (None for all tables)
            batch_size: Number of records to process in each batch
            method: Migration method to use
            
        Yields:
            MigrationProgress objects with current progress
        """
        pass
    
    @abstractmethod
    async def verify_migration(self, 
                              tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Verify the migration by comparing source and destination data.
        
        Args:
            tables: List of tables to verify (None for all tables)
            
        Returns:
            Dictionary with verification results
        """
        pass
    
    @abstractmethod
    async def get_supported_methods(self) -> List[MigrationMethod]:
        """Get list of migration methods supported by this migrator.
        
        Returns:
            List of supported migration methods
        """
        pass
    
    async def full_migration(self, 
                           tables: Optional[List[str]] = None,
                           batch_size: int = 1000,
                           method: MigrationMethod = MigrationMethod.DUMP_RESTORE,
                           verify: bool = True) -> MigrationResult:
        """Perform a complete migration including schema and data.
        
        Args:
            tables: List of tables to migrate (None for all tables)
            batch_size: Number of records to process in each batch
            method: Migration method to use
            verify: Whether to verify migration after completion
            
        Returns:
            Complete migration result
        """
        start_time = datetime.utcnow()
        result = MigrationResult(
            status=MigrationStatus.RUNNING,
            start_time=start_time
        )
        
        try:
            # Connect to databases
            source_connected = await self.connect_source()
            dest_connected = await self.connect_destination()
            
            if not source_connected or not dest_connected:
                result.status = MigrationStatus.FAILED
                result.errors.append("Failed to connect to source or destination database")
                return result
            
            # Validate compatibility
            compatibility_issues = await self.validate_compatibility()
            if compatibility_issues:
                result.status = MigrationStatus.FAILED
                result.errors.extend(compatibility_issues)
                return result
            
            # Migrate schema
            schema_result = await self.migrate_schema()
            if not schema_result.is_successful:
                result.status = MigrationStatus.FAILED
                result.errors.extend(schema_result.errors)
                return result
            
            # Migrate data
            async for progress in self.migrate_data(tables, batch_size, method):
                result.records_migrated = progress.records_processed
                result.tables_migrated = progress.tables_completed
            
            # Verify migration if requested
            if verify:
                verification_result = await self.verify_migration(tables)
                if not verification_result.get('success', False):
                    result.warnings.append("Migration verification found discrepancies")
                    result.metadata['verification'] = verification_result
            
            result.status = MigrationStatus.COMPLETED
            result.end_time = datetime.utcnow()
            
        except Exception as e:
            result.status = MigrationStatus.FAILED
            result.errors.append(f"Migration failed with error: {str(e)}")
            result.end_time = datetime.utcnow()
        
        finally:
            await self.disconnect()
        
        return result
    
    def __str__(self) -> str:
        """String representation of the migrator."""
        return f"{self.__class__.__name__}({self.source_config.type.value} -> {self.destination_config.type.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the migrator."""
        return (f"{self.__class__.__name__}("
                f"source={self.source_config.type.value}://{self.source_config.host}, "
                f"destination={self.destination_config.type.value}://{self.destination_config.host})")