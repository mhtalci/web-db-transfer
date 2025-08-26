"""Tests for database migrators."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from migration_assistant.database.migrators import (
    MySQLMigrator,
    PostgreSQLMigrator,
    SQLiteMigrator,
    MongoMigrator,
    RedisMigrator
)
from migration_assistant.database.config import (
    MySQLConfig,
    PostgreSQLConfig,
    SQLiteConfig,
    MongoConfig,
    RedisConfig,
    DatabaseType
)
from migration_assistant.database.base import MigrationStatus, MigrationMethod


class TestMySQLMigrator:
    """Test MySQL migrator."""
    
    @pytest.fixture
    def source_config(self):
        return MySQLConfig(
            host="localhost",
            port=3306,
            username="test_user",
            password="test_pass",
            database="test_db"
        )
    
    @pytest.fixture
    def destination_config(self):
        return MySQLConfig(
            host="localhost",
            port=3307,
            username="test_user",
            password="test_pass",
            database="test_db_dest"
        )
    
    @pytest.fixture
    def migrator(self, source_config, destination_config):
        return MySQLMigrator(source_config, destination_config)
    
    @patch('migration_assistant.database.migrators.mysql_migrator.MySQLConnectionPool')
    @pytest.mark.asyncio
    async def test_connect_source_success(self, mock_pool, migrator):
        """Test successful source connection."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_conn = Mock()
        mock_pool_instance.get_connection.return_value = mock_conn
        
        result = await migrator.connect_source()
        
        assert result is True
        assert migrator._source_pool is not None
        mock_conn.ping.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('migration_assistant.database.migrators.mysql_migrator.MySQLConnectionPool')
    @pytest.mark.asyncio
    async def test_connect_source_failure(self, mock_pool, migrator):
        """Test failed source connection."""
        mock_pool.side_effect = Exception("Connection failed")
        
        result = await migrator.connect_source()
        
        assert result is False
        assert migrator._source_pool is None
    
    @pytest.mark.asyncio
    async def test_test_connectivity(self, migrator):
        """Test connectivity testing."""
        with patch.object(migrator, 'connect_source', return_value=True), \
             patch.object(migrator, 'connect_destination', return_value=False):
            
            result = await migrator.test_connectivity()
            
            assert result == {'source': True, 'destination': False}
    
    @pytest.mark.asyncio
    async def test_get_supported_methods(self, migrator):
        """Test getting supported migration methods."""
        methods = await migrator.get_supported_methods()
        
        assert MigrationMethod.DUMP_RESTORE in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.BULK_COPY in methods


class TestPostgreSQLMigrator:
    """Test PostgreSQL migrator."""
    
    @pytest.fixture
    def source_config(self):
        return PostgreSQLConfig(
            host="localhost",
            port=5432,
            username="test_user",
            password="test_pass",
            database="test_db"
        )
    
    @pytest.fixture
    def destination_config(self):
        return PostgreSQLConfig(
            host="localhost",
            port=5433,
            username="test_user",
            password="test_pass",
            database="test_db_dest"
        )
    
    @pytest.fixture
    def migrator(self, source_config, destination_config):
        return PostgreSQLMigrator(source_config, destination_config)
    
    def test_create_connection_string(self, migrator):
        """Test connection string creation."""
        conn_string = migrator._create_connection_string(migrator.source_config)
        
        assert "host=localhost" in conn_string
        assert "port=5432" in conn_string
        assert "dbname=test_db" in conn_string
        assert "user=test_user" in conn_string
        assert "password=test_pass" in conn_string
    
    @patch('migration_assistant.database.migrators.postgresql_migrator.ThreadedConnectionPool')
    @pytest.mark.asyncio
    async def test_connect_source_success(self, mock_pool, migrator):
        """Test successful source connection."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_conn = Mock()
        mock_conn.autocommit = True
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool_instance.getconn.return_value = mock_conn
        
        result = await migrator.connect_source()
        
        assert result is True
        assert migrator._source_pool is not None
        mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_get_supported_methods(self, migrator):
        """Test getting supported migration methods."""
        methods = await migrator.get_supported_methods()
        
        assert MigrationMethod.DUMP_RESTORE in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.STREAMING in methods
        assert MigrationMethod.BULK_COPY in methods


class TestSQLiteMigrator:
    """Test SQLite migrator."""
    
    @pytest.fixture
    def source_config(self):
        return SQLiteConfig(
            database_path="/tmp/test_source.db"
        )
    
    @pytest.fixture
    def destination_config(self):
        return SQLiteConfig(
            database_path="/tmp/test_dest.db"
        )
    
    @pytest.fixture
    def migrator(self, source_config, destination_config):
        return SQLiteMigrator(source_config, destination_config)
    
    @patch('migration_assistant.database.migrators.sqlite_migrator.sqlite3.connect')
    @patch('migration_assistant.database.migrators.sqlite_migrator.os.path.exists')
    @pytest.mark.asyncio
    async def test_connect_source_success(self, mock_exists, mock_connect, migrator):
        """Test successful source connection."""
        mock_exists.return_value = True
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        result = await migrator.connect_source()
        
        assert result is True
        assert migrator._source_connection is not None
        mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    @patch('migration_assistant.database.migrators.sqlite_migrator.os.path.exists')
    @pytest.mark.asyncio
    async def test_connect_source_file_not_exists(self, mock_exists, migrator):
        """Test source connection when file doesn't exist."""
        mock_exists.return_value = False
        
        result = await migrator.connect_source()
        
        assert result is False
        assert migrator._source_connection is None
    
    @pytest.mark.asyncio
    async def test_get_supported_methods(self, migrator):
        """Test getting supported migration methods."""
        methods = await migrator.get_supported_methods()
        
        assert MigrationMethod.DUMP_RESTORE in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.BULK_COPY in methods


class TestMongoMigrator:
    """Test MongoDB migrator."""
    
    @pytest.fixture
    def source_config(self):
        return MongoConfig(
            host="localhost",
            port=27017,
            username="test_user",
            password="test_pass",
            database="test_db"
        )
    
    @pytest.fixture
    def destination_config(self):
        return MongoConfig(
            host="localhost",
            port=27018,
            username="test_user",
            password="test_pass",
            database="test_db_dest"
        )
    
    @pytest.fixture
    def migrator(self, source_config, destination_config):
        return MongoMigrator(source_config, destination_config)
    
    def test_create_connection_string(self, migrator):
        """Test connection string creation."""
        conn_string = migrator._create_connection_string(migrator.source_config)
        
        assert "mongodb://test_user:test_pass@localhost:27017/test_db" in conn_string
    
    @patch('migration_assistant.database.migrators.mongo_migrator.MongoClient')
    @pytest.mark.asyncio
    async def test_connect_source_success(self, mock_client, migrator):
        """Test successful source connection."""
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.admin.command.return_value = {'ok': 1}
        
        result = await migrator.connect_source()
        
        assert result is True
        assert migrator._source_client is not None
        mock_client_instance.admin.command.assert_called_once_with('ping')
    
    @pytest.mark.asyncio
    async def test_get_supported_methods(self, migrator):
        """Test getting supported migration methods."""
        methods = await migrator.get_supported_methods()
        
        assert MigrationMethod.BULK_COPY in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.STREAMING in methods


class TestRedisMigrator:
    """Test Redis migrator."""
    
    @pytest.fixture
    def source_config(self):
        return RedisConfig(
            host="localhost",
            port=6379,
            db=0,
            username="test_user",
            password="test_pass"
        )
    
    @pytest.fixture
    def destination_config(self):
        return RedisConfig(
            host="localhost",
            port=6380,
            db=0,
            username="test_user",
            password="test_pass"
        )
    
    @pytest.fixture
    def migrator(self, source_config, destination_config):
        return RedisMigrator(source_config, destination_config)
    
    def test_create_client_options(self, migrator):
        """Test client options creation."""
        options = migrator._create_client_options(migrator.source_config)
        
        assert options['host'] == 'localhost'
        assert options['port'] == 6379
        assert options['db'] == 0
        assert options['username'] == 'test_user'
        assert options['password'] == 'test_pass'
    
    @patch('migration_assistant.database.migrators.redis_migrator.redis.Redis')
    @pytest.mark.asyncio
    async def test_connect_source_success(self, mock_redis, migrator):
        """Test successful source connection."""
        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        
        result = await migrator.connect_source()
        
        assert result is True
        assert migrator._source_client is not None
        mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_supported_methods(self, migrator):
        """Test getting supported migration methods."""
        methods = await migrator.get_supported_methods()
        
        assert MigrationMethod.BULK_COPY in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.STREAMING in methods


class TestMigrationIntegration:
    """Integration tests for migrators."""
    
    @pytest.mark.asyncio
    async def test_migration_workflow(self):
        """Test basic migration workflow."""
        source_config = SQLiteConfig(database_path="/tmp/test_source.db")
        dest_config = SQLiteConfig(database_path="/tmp/test_dest.db")
        
        migrator = SQLiteMigrator(source_config, dest_config)
        
        # Test connectivity
        with patch.object(migrator, 'connect_source', return_value=True), \
             patch.object(migrator, 'connect_destination', return_value=True):
            
            connectivity = await migrator.test_connectivity()
            assert connectivity['source'] is True
            assert connectivity['destination'] is True
        
        # Test compatibility validation
        with patch.object(migrator, 'get_schema_info', return_value={'database': 'test', 'tables': []}):
            issues = await migrator.validate_compatibility()
            # Should have some issues since we're mocking empty responses
            assert isinstance(issues, list)
        
        # Test size estimation
        with patch.object(migrator, 'get_schema_info', return_value={
            'tables': [{'rows': 100}],
            'views': [],
            'indexes': [],
            'triggers': []
        }), \
        patch('migration_assistant.database.migrators.sqlite_migrator.os.path.exists', return_value=True), \
        patch('migration_assistant.database.migrators.sqlite_migrator.os.path.getsize', return_value=1024):
            
            size_info = await migrator.estimate_migration_size()
            assert size_info['total_tables'] == 1
            assert size_info['total_rows'] == 100
            assert size_info['file_size_bytes'] == 1024


@pytest.mark.asyncio
async def test_migration_progress_generator():
    """Test migration progress generator."""
    source_config = RedisConfig(host="localhost", port=6379, db=0)
    dest_config = RedisConfig(host="localhost", port=6380, db=0)
    
    migrator = RedisMigrator(source_config, dest_config)
    
    # Mock Redis clients
    mock_source = Mock()
    mock_dest = Mock()
    migrator._source_client = mock_source
    migrator._destination_client = mock_dest
    
    # Mock Redis operations
    mock_source.keys.return_value = [b'key1', b'key2', b'key3']
    mock_source.type.return_value = b'string'
    mock_source.ttl.return_value = -1
    mock_source.get.return_value = b'value'
    
    mock_dest_pipe = Mock()
    mock_dest.pipeline.return_value = mock_dest_pipe
    mock_dest_pipe.execute.return_value = [True, True, True]
    
    # Test migration progress
    progress_updates = []
    async for progress in migrator.migrate_data(batch_size=2):
        progress_updates.append(progress)
    
    assert len(progress_updates) > 0
    assert progress_updates[0].current_operation == "Starting Redis data migration"
    assert progress_updates[-1].current_operation == "Redis data migration completed"