"""Tests for schema analyzer module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey
from sqlalchemy.engine import Inspector

from migration_assistant.database.schema_analyzer import (
    SchemaAnalyzer, SchemaAnalysisResult, SchemaCompatibilityResult
)
from migration_assistant.database.config import (
    MySQLConfig, PostgreSQLConfig, SQLiteConfig, DatabaseType
)
from migration_assistant.database.base import MigrationMethod
from migration_assistant.core.exceptions import UnsupportedDatabaseError


class TestSchemaAnalyzer:
    """Test cases for SchemaAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a schema analyzer instance."""
        return SchemaAnalyzer()
    
    @pytest.fixture
    def mysql_config(self):
        """Create a MySQL configuration."""
        return MySQLConfig(
            host="localhost",
            port=3306,
            username="test",
            password="test",
            database="test_db"
        )
    
    @pytest.fixture
    def postgres_config(self):
        """Create a PostgreSQL configuration."""
        return PostgreSQLConfig(
            host="localhost",
            port=5432,
            username="test",
            password="test",
            database="test_db"
        )
    
    @pytest.fixture
    def sqlite_config(self):
        """Create a SQLite configuration."""
        return SQLiteConfig(
            database_path="/tmp/test.db"
        )
    
    def test_init(self, analyzer):
        """Test analyzer initialization."""
        assert analyzer is not None
        assert DatabaseType.MYSQL in analyzer._supported_types
        assert DatabaseType.POSTGRESQL in analyzer._supported_types
        assert DatabaseType.SQLITE in analyzer._supported_types
    
    def test_create_engine_mysql(self, analyzer, mysql_config):
        """Test engine creation for MySQL."""
        with patch('migration_assistant.database.schema_analyzer.create_engine') as mock_create:
            mock_engine = Mock()
            mock_create.return_value = mock_engine
            
            engine = analyzer._create_engine(mysql_config)
            
            mock_create.assert_called_once()
            args, kwargs = mock_create.call_args
            assert "mysql+mysqlconnector://" in args[0]
            assert "test:test@localhost:3306/test_db" in args[0]
    
    def test_create_engine_postgresql(self, analyzer, postgres_config):
        """Test engine creation for PostgreSQL."""
        with patch('migration_assistant.database.schema_analyzer.create_engine') as mock_create:
            mock_engine = Mock()
            mock_create.return_value = mock_engine
            
            engine = analyzer._create_engine(postgres_config)
            
            mock_create.assert_called_once()
            args, kwargs = mock_create.call_args
            assert "postgresql+psycopg2://" in args[0]
            assert "test:test@localhost:5432/test_db" in args[0]
    
    def test_create_engine_sqlite(self, analyzer, sqlite_config):
        """Test engine creation for SQLite."""
        with patch('migration_assistant.database.schema_analyzer.create_engine') as mock_create:
            mock_engine = Mock()
            mock_create.return_value = mock_engine
            
            engine = analyzer._create_engine(sqlite_config)
            
            mock_create.assert_called_once()
            args, kwargs = mock_create.call_args
            assert "sqlite:////tmp/test.db" in args[0]
    
    def test_create_engine_unsupported(self, analyzer):
        """Test engine creation with unsupported database type."""
        from migration_assistant.database.config import MongoConfig
        
        mongo_config = MongoConfig(
            host="localhost",
            port=27017,
            username="test",
            password="test",
            database="test_db"
        )
        
        with pytest.raises(UnsupportedDatabaseError):
            analyzer._create_engine(mongo_config)
    
    @pytest.mark.asyncio
    async def test_analyze_schema_success(self, analyzer, mysql_config):
        """Test successful schema analysis."""
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_metadata = Mock()
        
        # Mock inspector methods
        mock_inspector.get_table_names.return_value = ['users', 'posts']
        mock_inspector.get_view_names.return_value = ['user_view']
        mock_inspector.get_columns.return_value = [
            {'name': 'id', 'type': Integer(), 'nullable': False, 'default': None},
            {'name': 'name', 'type': String(50), 'nullable': True, 'default': None}
        ]
        mock_inspector.get_pk_constraint.return_value = {
            'name': 'pk_users',
            'constrained_columns': ['id']
        }
        mock_inspector.get_indexes.return_value = []
        mock_inspector.get_foreign_keys.return_value = []
        mock_inspector.get_unique_constraints.return_value = []
        
        # Mock connection for data stats
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.scalar.return_value = 100  # row count
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        with patch.object(analyzer, '_create_engine', return_value=mock_engine), \
             patch('migration_assistant.database.schema_analyzer.inspect', return_value=mock_inspector), \
             patch('migration_assistant.database.schema_analyzer.MetaData', return_value=mock_metadata), \
             patch.object(analyzer, '_get_schema_info', return_value={'version': '8.0'}), \
             patch.object(analyzer, '_analyze_table') as mock_analyze_table, \
             patch.object(analyzer, '_analyze_view') as mock_analyze_view, \
             patch.object(analyzer, '_get_functions_and_procedures', return_value=[]):
            
            mock_analyze_table.return_value = {
                'name': 'users',
                'columns': [{'name': 'id', 'type': 'INTEGER'}],
                'row_count': 100,
                'size_bytes': 1024
            }
            mock_analyze_view.return_value = {
                'name': 'user_view',
                'columns': [{'name': 'id', 'type': 'INTEGER'}]
            }
            
            result = await analyzer.analyze_schema(mysql_config)
            
            assert result.success is True
            assert len(result.errors) == 0
            assert 'users' in result.tables
            assert 'posts' in result.tables
            assert 'user_view' in result.views
    
    @pytest.mark.asyncio
    async def test_analyze_schema_failure(self, analyzer, mysql_config):
        """Test schema analysis with failure."""
        with patch.object(analyzer, '_create_engine', side_effect=Exception("Connection failed")):
            result = await analyzer.analyze_schema(mysql_config)
            
            assert result.success is False
            assert len(result.errors) > 0
            assert "Schema analysis failed" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_analyze_compatibility_same_type(self, analyzer, mysql_config):
        """Test compatibility analysis for same database types."""
        source_schema = SchemaAnalysisResult()
        source_schema.tables = {
            'users': {'columns': [{'name': 'id', 'type': 'INTEGER'}]}
        }
        
        dest_schema = SchemaAnalysisResult()
        dest_schema.tables = {}
        
        result = await analyzer.analyze_compatibility(
            mysql_config, mysql_config, source_schema, dest_schema
        )
        
        assert result.compatible is True
        assert result.migration_complexity == "simple"
        assert any("Same database type" in rec for rec in result.recommendations)
    
    @pytest.mark.asyncio
    async def test_analyze_compatibility_different_types(self, analyzer, mysql_config, postgres_config):
        """Test compatibility analysis for different database types."""
        source_schema = SchemaAnalysisResult()
        source_schema.tables = {
            'users': {'columns': [{'name': 'id', 'type': 'INTEGER'}]}
        }
        
        dest_schema = SchemaAnalysisResult()
        dest_schema.tables = {}
        
        result = await analyzer.analyze_compatibility(
            mysql_config, postgres_config, source_schema, dest_schema
        )
        
        assert result.migration_complexity in ["simple", "moderate", "complex"]
        assert any("Cross-SQL database migration" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_analyze_compatibility_table_conflicts(self, analyzer, mysql_config):
        """Test compatibility analysis with table name conflicts."""
        source_schema = SchemaAnalysisResult()
        source_schema.tables = {'users': {}, 'posts': {}}
        
        dest_schema = SchemaAnalysisResult()
        dest_schema.tables = {'users': {}, 'comments': {}}
        
        result = await analyzer.analyze_compatibility(
            mysql_config, mysql_config, source_schema, dest_schema
        )
        
        assert result.compatible is False
        assert any("Table name conflicts" in issue for issue in result.issues)
        assert "users" in str(result.issues)
    
    def test_get_migration_method_recommendations_same_type(self, analyzer, mysql_config):
        """Test migration method recommendations for same database type."""
        methods = analyzer.get_migration_method_recommendations(mysql_config, mysql_config)
        
        assert MigrationMethod.DUMP_RESTORE in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.STREAMING in methods
    
    def test_get_migration_method_recommendations_sql_to_sql(self, analyzer, mysql_config, postgres_config):
        """Test migration method recommendations for SQL to SQL migration."""
        methods = analyzer.get_migration_method_recommendations(mysql_config, postgres_config)
        
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.DUMP_RESTORE in methods
        assert MigrationMethod.BULK_COPY in methods
    
    @pytest.mark.asyncio
    async def test_get_schema_info_mysql(self, analyzer, mysql_config):
        """Test getting schema info for MySQL."""
        mock_inspector = Mock()
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.scalar.return_value = "8.0.25"
        mock_conn.execute.return_value = mock_result
        mock_inspector.bind.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_inspector.bind.connect.return_value.__exit__ = Mock(return_value=None)
        
        info = await analyzer._get_schema_info(mock_inspector, mysql_config)
        
        assert info['database_type'] == 'mysql'
        assert info['database_name'] == 'test_db'
        assert info['host'] == 'localhost'
        assert info['port'] == 3306
        assert info['version'] == "8.0.25"
    
    @pytest.mark.asyncio
    async def test_analyze_table_with_data_stats(self, analyzer, mysql_config):
        """Test table analysis with data statistics."""
        mock_inspector = Mock()
        mock_engine = Mock()
        mock_metadata = Mock()
        
        # Mock column information
        mock_inspector.get_columns.return_value = [
            {
                'name': 'id',
                'type': Integer(),
                'nullable': False,
                'default': None,
                'autoincrement': True
            },
            {
                'name': 'name',
                'type': String(50),
                'nullable': True,
                'default': None,
                'autoincrement': False
            }
        ]
        
        # Mock primary key
        mock_inspector.get_pk_constraint.return_value = {
            'name': 'pk_users',
            'constrained_columns': ['id']
        }
        
        # Mock connection for data stats
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.scalar.return_value = 100  # row count
        mock_result.fetchone.return_value = ('InnoDB', 'utf8mb4_general_ci', 2048)  # MySQL specific
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        table_info = await analyzer._analyze_table(
            mock_inspector, mock_engine, mock_metadata, 'users', True, mysql_config
        )
        
        assert table_info['name'] == 'users'
        assert len(table_info['columns']) == 2
        assert table_info['columns'][0]['name'] == 'id'
        assert table_info['columns'][0]['type'] == 'INTEGER'
        assert table_info['columns'][0]['nullable'] is False
        assert table_info['primary_key']['columns'] == ['id']
        assert table_info['row_count'] == 100
        assert table_info['engine'] == 'InnoDB'
        assert table_info['collation'] == 'utf8mb4_general_ci'
        assert table_info['size_bytes'] == 2048
    
    @pytest.mark.asyncio
    async def test_analyze_view(self, analyzer, mysql_config):
        """Test view analysis."""
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {'name': 'id', 'type': Integer(), 'nullable': False},
            {'name': 'name', 'type': String(50), 'nullable': True}
        ]
        
        view_info = await analyzer._analyze_view(mock_inspector, 'user_view', mysql_config)
        
        assert view_info['name'] == 'user_view'
        assert len(view_info['columns']) == 2
        assert view_info['columns'][0]['name'] == 'id'
        assert view_info['columns'][1]['name'] == 'name'
    
    def test_get_table_indexes(self, analyzer):
        """Test getting table indexes."""
        mock_inspector = Mock()
        mock_inspector.get_indexes.return_value = [
            {
                'name': 'idx_name',
                'column_names': ['name'],
                'unique': False,
                'type': 'btree'
            },
            {
                'name': 'idx_email',
                'column_names': ['email'],
                'unique': True,
                'type': 'btree'
            }
        ]
        
        indexes = analyzer._get_table_indexes(mock_inspector, 'users')
        
        assert len(indexes) == 2
        assert indexes[0]['name'] == 'idx_name'
        assert indexes[0]['columns'] == ['name']
        assert indexes[0]['unique'] is False
        assert indexes[1]['name'] == 'idx_email'
        assert indexes[1]['unique'] is True
    
    def test_get_table_foreign_keys(self, analyzer):
        """Test getting table foreign keys."""
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = [
            {
                'name': 'fk_user_id',
                'constrained_columns': ['user_id'],
                'referred_table': 'users',
                'referred_columns': ['id'],
                'referred_schema': None,
                'options': {'ondelete': 'CASCADE', 'onupdate': 'RESTRICT'}
            }
        ]
        
        foreign_keys = analyzer._get_table_foreign_keys(mock_inspector, 'posts')
        
        assert len(foreign_keys) == 1
        assert foreign_keys[0]['name'] == 'fk_user_id'
        assert foreign_keys[0]['constrained_columns'] == ['user_id']
        assert foreign_keys[0]['referred_table'] == 'users'
        assert foreign_keys[0]['referred_columns'] == ['id']
        assert foreign_keys[0]['on_delete'] == 'CASCADE'
        assert foreign_keys[0]['on_update'] == 'RESTRICT'
    
    def test_get_table_constraints(self, analyzer):
        """Test getting table constraints."""
        mock_inspector = Mock()
        mock_inspector.get_unique_constraints.return_value = [
            {
                'name': 'uq_email',
                'column_names': ['email']
            }
        ]
        
        # Mock check constraints (not all databases support this)
        mock_inspector.get_check_constraints = Mock(return_value=[
            {
                'name': 'chk_age',
                'sqltext': 'age >= 0'
            }
        ])
        
        constraints = analyzer._get_table_constraints(mock_inspector, 'users')
        
        assert len(constraints) == 2
        assert constraints[0]['type'] == 'unique'
        assert constraints[0]['name'] == 'uq_email'
        assert constraints[0]['columns'] == ['email']
        assert constraints[1]['type'] == 'check'
        assert constraints[1]['name'] == 'chk_age'
        assert constraints[1]['condition'] == 'age >= 0'
    
    @pytest.mark.asyncio
    async def test_get_functions_and_procedures_mysql(self, analyzer, mysql_config):
        """Test getting functions and procedures for MySQL."""
        mock_inspector = Mock()
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([
            ('get_user_count', 'FUNCTION', 'test_db'),
            ('update_user_stats', 'PROCEDURE', 'test_db')
        ]))
        mock_conn.execute.return_value = mock_result
        mock_inspector.bind.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_inspector.bind.connect.return_value.__exit__ = Mock(return_value=None)
        
        functions = await analyzer._get_functions_and_procedures(mock_inspector, mysql_config)
        
        assert len(functions) == 2
        assert functions[0]['name'] == 'get_user_count'
        assert functions[0]['type'] == 'function'
        assert functions[1]['name'] == 'update_user_stats'
        assert functions[1]['type'] == 'procedure'
    
    @pytest.mark.asyncio
    async def test_get_functions_and_procedures_postgresql(self, analyzer, postgres_config):
        """Test getting functions and procedures for PostgreSQL."""
        mock_inspector = Mock()
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([
            ('get_user_count', 'f', 'public'),  # function
            ('update_stats', 'p', 'public')     # procedure
        ]))
        mock_conn.execute.return_value = mock_result
        mock_inspector.bind.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_inspector.bind.connect.return_value.__exit__ = Mock(return_value=None)
        
        functions = await analyzer._get_functions_and_procedures(mock_inspector, postgres_config)
        
        assert len(functions) == 2
        assert functions[0]['name'] == 'get_user_count'
        assert functions[0]['type'] == 'function'
        assert functions[1]['name'] == 'update_stats'
        assert functions[1]['type'] == 'procedure'


class TestSchemaAnalysisResult:
    """Test cases for SchemaAnalysisResult."""
    
    def test_init(self):
        """Test result initialization."""
        result = SchemaAnalysisResult()
        
        assert result.success is True
        assert result.errors == []
        assert result.warnings == []
        assert result.tables == {}
        assert result.views == {}
        assert result.indexes == {}
        assert result.foreign_keys == {}
        assert result.constraints == {}
        assert result.sequences == []
        assert result.functions == []
        assert result.triggers == []
        assert result.schema_info == {}
        assert result.analysis_time is None
    
    def test_add_error(self):
        """Test adding errors."""
        result = SchemaAnalysisResult()
        result.add_error("Test error")
        
        assert result.success is False
        assert "Test error" in result.errors
    
    def test_add_warning(self):
        """Test adding warnings."""
        result = SchemaAnalysisResult()
        result.add_warning("Test warning")
        
        assert result.success is True  # Warnings don't affect success
        assert "Test warning" in result.warnings
    
    def test_get_table_count(self):
        """Test getting table count."""
        result = SchemaAnalysisResult()
        result.tables = {'users': {}, 'posts': {}, 'comments': {}}
        
        assert result.get_table_count() == 3
    
    def test_get_total_rows(self):
        """Test getting total rows."""
        result = SchemaAnalysisResult()
        result.tables = {
            'users': {'row_count': 100},
            'posts': {'row_count': 250},
            'comments': {'row_count': 500}
        }
        
        assert result.get_total_rows() == 850
    
    def test_get_total_size_bytes(self):
        """Test getting total size in bytes."""
        result = SchemaAnalysisResult()
        result.tables = {
            'users': {'size_bytes': 1024},
            'posts': {'size_bytes': 2048},
            'comments': {'size_bytes': 4096}
        }
        
        assert result.get_total_size_bytes() == 7168


class TestSchemaCompatibilityResult:
    """Test cases for SchemaCompatibilityResult."""
    
    def test_init(self):
        """Test result initialization."""
        result = SchemaCompatibilityResult()
        
        assert result.compatible is True
        assert result.issues == []
        assert result.warnings == []
        assert result.recommendations == []
        assert result.migration_complexity == "simple"
        assert result.recommended_method is None
        assert result.data_type_mappings == {}
        assert result.unsupported_features == []
    
    def test_add_issue(self):
        """Test adding issues."""
        result = SchemaCompatibilityResult()
        result.add_issue("Test issue")
        
        assert result.compatible is False
        assert "Test issue" in result.issues
    
    def test_add_warning(self):
        """Test adding warnings."""
        result = SchemaCompatibilityResult()
        result.add_warning("Test warning")
        
        assert result.compatible is True  # Warnings don't affect compatibility
        assert "Test warning" in result.warnings
    
    def test_add_recommendation(self):
        """Test adding recommendations."""
        result = SchemaCompatibilityResult()
        result.add_recommendation("Test recommendation")
        
        assert "Test recommendation" in result.recommendations