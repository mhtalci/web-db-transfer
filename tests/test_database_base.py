"""Tests for database base classes and models."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from migration_assistant.database.base import (
    MigrationStatus,
    MigrationMethod,
    MigrationResult,
    MigrationProgress,
    DatabaseMigrator
)
from migration_assistant.database.config import MySQLConfig, PostgreSQLConfig, DatabaseType


class TestMigrationResult:
    """Test cases for MigrationResult model."""
    
    def test_migration_result_creation(self):
        """Test creating a migration result."""
        start_time = datetime.utcnow()
        result = MigrationResult(
            status=MigrationStatus.COMPLETED,
            start_time=start_time,
            records_migrated=1000,
            tables_migrated=5
        )
        
        assert result.status == MigrationStatus.COMPLETED
        assert result.start_time == start_time
        assert result.records_migrated == 1000
        assert result.tables_migrated == 5
        assert result.errors == []
        assert result.warnings == []
    
    def test_migration_result_duration(self):
        """Test migration duration calculation."""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=30)
        
        result = MigrationResult(
            status=MigrationStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time
        )
        
        assert result.duration_seconds == 30.0
    
    def test_migration_result_duration_no_end_time(self):
        """Test migration duration when end time is not set."""
        result = MigrationResult(
            status=MigrationStatus.RUNNING,
            start_time=datetime.utcnow()
        )
        
        assert result.duration_seconds is None
    
    def test_migration_result_is_successful(self):
        """Test successful migration detection."""
        # Successful migration
        result = MigrationResult(
            status=MigrationStatus.COMPLETED,
            start_time=datetime.utcnow()
        )
        assert result.is_successful is True
        
        # Failed migration
        result = MigrationResult(
            status=MigrationStatus.FAILED,
            start_time=datetime.utcnow(),
            errors=["Connection failed"]
        )
        assert result.is_successful is False
        
        # Completed but with errors
        result = MigrationResult(
            status=MigrationStatus.COMPLETED,
            start_time=datetime.utcnow(),
            errors=["Minor issue"]
        )
        assert result.is_successful is False


class TestMigrationProgress:
    """Test cases for MigrationProgress model."""
    
    def test_migration_progress_creation(self):
        """Test creating migration progress."""
        progress = MigrationProgress(
            current_table="users",
            tables_completed=2,
            total_tables=5,
            records_processed=500,
            estimated_total_records=2000,
            current_operation="Copying data"
        )
        
        assert progress.current_table == "users"
        assert progress.tables_completed == 2
        assert progress.total_tables == 5
        assert progress.records_processed == 500
        assert progress.estimated_total_records == 2000
        assert progress.current_operation == "Copying data"
    
    def test_table_progress_percentage(self):
        """Test table progress percentage calculation."""
        progress = MigrationProgress(
            tables_completed=3,
            total_tables=10
        )
        
        assert progress.table_progress_percentage == 30.0
    
    def test_table_progress_percentage_zero_total(self):
        """Test table progress percentage with zero total tables."""
        progress = MigrationProgress(
            tables_completed=0,
            total_tables=0
        )
        
        assert progress.table_progress_percentage == 0.0
    
    def test_record_progress_percentage(self):
        """Test record progress percentage calculation."""
        progress = MigrationProgress(
            records_processed=750,
            estimated_total_records=1000
        )
        
        assert progress.record_progress_percentage == 75.0
    
    def test_record_progress_percentage_no_estimate(self):
        """Test record progress percentage without total estimate."""
        progress = MigrationProgress(
            records_processed=500,
            estimated_total_records=None
        )
        
        assert progress.record_progress_percentage is None


class MockDatabaseMigrator(DatabaseMigrator):
    """Mock implementation of DatabaseMigrator for testing."""
    
    def __init__(self, source_config, destination_config):
        super().__init__(source_config, destination_config)
        self.source_connected = False
        self.destination_connected = False
    
    async def connect_source(self) -> bool:
        self.source_connected = True
        return True
    
    async def connect_destination(self) -> bool:
        self.destination_connected = True
        return True
    
    async def disconnect(self) -> None:
        self.source_connected = False
        self.destination_connected = False
    
    async def test_connectivity(self) -> dict:
        return {
            "source": self.source_connected,
            "destination": self.destination_connected
        }
    
    async def get_schema_info(self, config) -> dict:
        return {
            "tables": ["users", "orders", "products"],
            "views": ["user_orders"],
            "indexes": 5
        }
    
    async def validate_compatibility(self) -> list:
        return []  # No compatibility issues
    
    async def estimate_migration_size(self) -> dict:
        return {
            "tables": 3,
            "estimated_records": 10000,
            "estimated_size_mb": 50
        }
    
    async def migrate_schema(self) -> MigrationResult:
        return MigrationResult(
            status=MigrationStatus.COMPLETED,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow()
        )
    
    async def migrate_data(self, tables=None, batch_size=1000, method=MigrationMethod.DUMP_RESTORE):
        # Simulate progress updates
        total_tables = 3
        for i in range(total_tables):
            yield MigrationProgress(
                current_table=f"table_{i}",
                tables_completed=i,
                total_tables=total_tables,
                records_processed=i * 1000,
                current_operation=f"Migrating table_{i}"
            )
    
    async def verify_migration(self, tables=None) -> dict:
        return {
            "success": True,
            "verified_tables": 3,
            "record_count_match": True
        }
    
    async def get_supported_methods(self) -> list:
        return [MigrationMethod.DUMP_RESTORE, MigrationMethod.DIRECT_TRANSFER]


class TestDatabaseMigrator:
    """Test cases for DatabaseMigrator abstract base class."""
    
    @pytest.fixture
    def source_config(self):
        """Create a source database configuration."""
        return MySQLConfig(
            host="source.example.com",
            username="source_user",
            password="source_pass",
            database="source_db"
        )
    
    @pytest.fixture
    def destination_config(self):
        """Create a destination database configuration."""
        return PostgreSQLConfig(
            host="dest.example.com",
            username="dest_user",
            password="dest_pass",
            database="dest_db"
        )
    
    @pytest.fixture
    def migrator(self, source_config, destination_config):
        """Create a mock database migrator."""
        return MockDatabaseMigrator(source_config, destination_config)
    
    def test_migrator_initialization(self, migrator, source_config, destination_config):
        """Test migrator initialization."""
        assert migrator.source_config == source_config
        assert migrator.destination_config == destination_config
        assert migrator._source_connection is None
        assert migrator._destination_connection is None
    
    @pytest.mark.asyncio
    async def test_connectivity_methods(self, migrator):
        """Test connectivity methods."""
        # Initially not connected
        connectivity = await migrator.test_connectivity()
        assert connectivity["source"] is False
        assert connectivity["destination"] is False
        
        # Connect to source
        result = await migrator.connect_source()
        assert result is True
        assert migrator.source_connected is True
        
        # Connect to destination
        result = await migrator.connect_destination()
        assert result is True
        assert migrator.destination_connected is True
        
        # Test connectivity after connection
        connectivity = await migrator.test_connectivity()
        assert connectivity["source"] is True
        assert connectivity["destination"] is True
        
        # Disconnect
        await migrator.disconnect()
        assert migrator.source_connected is False
        assert migrator.destination_connected is False
    
    @pytest.mark.asyncio
    async def test_schema_info(self, migrator, source_config):
        """Test getting schema information."""
        schema_info = await migrator.get_schema_info(source_config)
        
        assert "tables" in schema_info
        assert "views" in schema_info
        assert "indexes" in schema_info
        assert len(schema_info["tables"]) == 3
    
    @pytest.mark.asyncio
    async def test_compatibility_validation(self, migrator):
        """Test compatibility validation."""
        issues = await migrator.validate_compatibility()
        assert isinstance(issues, list)
        assert len(issues) == 0  # Mock returns no issues
    
    @pytest.mark.asyncio
    async def test_migration_size_estimation(self, migrator):
        """Test migration size estimation."""
        size_info = await migrator.estimate_migration_size()
        
        assert "tables" in size_info
        assert "estimated_records" in size_info
        assert "estimated_size_mb" in size_info
        assert size_info["tables"] == 3
    
    @pytest.mark.asyncio
    async def test_schema_migration(self, migrator):
        """Test schema migration."""
        result = await migrator.migrate_schema()
        
        assert isinstance(result, MigrationResult)
        assert result.status == MigrationStatus.COMPLETED
        assert result.start_time is not None
        assert result.end_time is not None
    
    @pytest.mark.asyncio
    async def test_data_migration_progress(self, migrator):
        """Test data migration with progress updates."""
        progress_updates = []
        
        async for progress in migrator.migrate_data():
            progress_updates.append(progress)
        
        assert len(progress_updates) == 3  # Mock returns 3 updates
        assert all(isinstance(p, MigrationProgress) for p in progress_updates)
        
        # Check progress sequence
        for i, progress in enumerate(progress_updates):
            assert progress.current_table == f"table_{i}"
            assert progress.tables_completed == i
            assert progress.total_tables == 3
    
    @pytest.mark.asyncio
    async def test_migration_verification(self, migrator):
        """Test migration verification."""
        verification = await migrator.verify_migration()
        
        assert verification["success"] is True
        assert verification["verified_tables"] == 3
        assert verification["record_count_match"] is True
    
    @pytest.mark.asyncio
    async def test_supported_methods(self, migrator):
        """Test getting supported migration methods."""
        methods = await migrator.get_supported_methods()
        
        assert isinstance(methods, list)
        assert MigrationMethod.DUMP_RESTORE in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
    
    @pytest.mark.asyncio
    async def test_full_migration_success(self, migrator):
        """Test successful full migration."""
        result = await migrator.full_migration(verify=True)
        
        assert isinstance(result, MigrationResult)
        assert result.status == MigrationStatus.COMPLETED
        assert result.is_successful is True
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.duration_seconds is not None
        assert result.tables_migrated == 2  # Last progress update value
    
    def test_migrator_string_representation(self, migrator):
        """Test string representation of migrator."""
        str_repr = str(migrator)
        assert "MockDatabaseMigrator" in str_repr
        assert "mysql -> postgresql" in str_repr
        
        repr_str = repr(migrator)
        assert "MockDatabaseMigrator" in repr_str
        assert "source.example.com" in repr_str
        assert "dest.example.com" in repr_str