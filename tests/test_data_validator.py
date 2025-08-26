"""Tests for data validator module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from migration_assistant.database.data_validator import (
    DataValidator, DataValidationReport, TableValidationSummary, ValidationResult,
    ValidationLevel, ValidationStatus
)
from migration_assistant.database.config import MySQLConfig, PostgreSQLConfig, DatabaseType


class TestDataValidator:
    """Test cases for DataValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create a data validator instance."""
        return DataValidator()
    
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
    
    def test_init(self, validator):
        """Test validator initialization."""
        assert validator is not None
        assert validator.schema_analyzer is not None
        assert DatabaseType.MYSQL in validator._supported_types
        assert DatabaseType.POSTGRESQL in validator._supported_types
        assert DatabaseType.SQLITE in validator._supported_types
    
    @pytest.mark.asyncio
    async def test_validate_migration_success(self, validator, mysql_config):
        """Test successful migration validation."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['users', 'posts']
        
        with patch.object(validator, '_create_engine') as mock_create_engine, \
             patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector), \
             patch.object(validator, '_validate_table') as mock_validate_table:
            
            mock_create_engine.side_effect = [mock_source_engine, mock_dest_engine]
            
            # Mock successful table validation
            mock_table_summary = TableValidationSummary(
                table_name='users',
                total_checks=3,
                passed_checks=3,
                failed_checks=0,
                warning_checks=0
            )
            mock_table_summary.results = [
                ValidationResult('users', 'row_count', ValidationStatus.PASSED, 100, 100, "Row counts match"),
                ValidationResult('users', 'checksum', ValidationStatus.PASSED, 'abc123', 'abc123', "Checksums match"),
                ValidationResult('users', 'constraints', ValidationStatus.PASSED, message="Constraints match")
            ]
            mock_validate_table.return_value = mock_table_summary
            
            report = await validator.validate_migration(
                mysql_config, mysql_config, ['users'], ValidationLevel.STANDARD
            )
            
            assert report.overall_status == ValidationStatus.PASSED
            assert report.total_tables == 1
            assert report.passed_tables == 1
            assert report.failed_tables == 0
            assert 'users' in report.table_summaries
    
    @pytest.mark.asyncio
    async def test_validate_migration_with_failures(self, validator, mysql_config):
        """Test migration validation with failures."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['users']
        
        with patch.object(validator, '_create_engine') as mock_create_engine, \
             patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector), \
             patch.object(validator, '_validate_table') as mock_validate_table:
            
            mock_create_engine.side_effect = [mock_source_engine, mock_dest_engine]
            
            # Mock failed table validation
            mock_table_summary = TableValidationSummary(
                table_name='users',
                total_checks=2,
                passed_checks=1,
                failed_checks=1,
                warning_checks=0
            )
            mock_table_summary.results = [
                ValidationResult('users', 'row_count', ValidationStatus.PASSED, 100, 100, "Row counts match"),
                ValidationResult('users', 'checksum', ValidationStatus.FAILED, 'abc123', 'def456', "Checksums don't match")
            ]
            mock_validate_table.return_value = mock_table_summary
            
            report = await validator.validate_migration(
                mysql_config, mysql_config, ['users'], ValidationLevel.STANDARD
            )
            
            assert report.overall_status == ValidationStatus.FAILED
            assert report.total_tables == 1
            assert report.passed_tables == 0
            assert report.failed_tables == 1
    
    @pytest.mark.asyncio
    async def test_validate_migration_with_errors(self, validator, mysql_config):
        """Test migration validation with errors."""
        with patch.object(validator, '_create_engine', side_effect=Exception("Connection failed")):
            report = await validator.validate_migration(
                mysql_config, mysql_config, ['users'], ValidationLevel.BASIC
            )
            
            assert report.overall_status == ValidationStatus.FAILED
            assert len(report.errors) > 0
            assert "Migration validation failed" in report.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_table_basic(self, validator):
        """Test basic table validation."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        
        with patch.object(validator, '_validate_row_count') as mock_row_count, \
             patch.object(validator, '_validate_constraints') as mock_constraints:
            
            mock_row_count.return_value = ValidationResult(
                'users', 'row_count', ValidationStatus.PASSED, 100, 100, "Row counts match"
            )
            mock_constraints.return_value = []
            
            summary = await validator._validate_table(
                mock_source_engine, mock_dest_engine, 'users', ValidationLevel.BASIC, None
            )
            
            assert summary.table_name == 'users'
            assert summary.total_checks == 1
            assert summary.passed_checks == 1
            assert summary.failed_checks == 0
            assert summary.overall_status == ValidationStatus.PASSED
    
    @pytest.mark.asyncio
    async def test_validate_table_standard(self, validator):
        """Test standard table validation."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        
        with patch.object(validator, '_validate_row_count') as mock_row_count, \
             patch.object(validator, '_validate_table_checksum') as mock_checksum, \
             patch.object(validator, '_validate_constraints') as mock_constraints:
            
            mock_row_count.return_value = ValidationResult(
                'users', 'row_count', ValidationStatus.PASSED, 100, 100, "Row counts match"
            )
            mock_checksum.return_value = ValidationResult(
                'users', 'checksum', ValidationStatus.PASSED, 'abc123', 'abc123', "Checksums match"
            )
            mock_constraints.return_value = []
            
            summary = await validator._validate_table(
                mock_source_engine, mock_dest_engine, 'users', ValidationLevel.STANDARD, None
            )
            
            assert summary.table_name == 'users'
            assert summary.total_checks == 2
            assert summary.passed_checks == 2
            assert summary.failed_checks == 0
    
    @pytest.mark.asyncio
    async def test_validate_table_comprehensive(self, validator):
        """Test comprehensive table validation."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        
        with patch.object(validator, '_validate_row_count') as mock_row_count, \
             patch.object(validator, '_validate_table_checksum') as mock_checksum, \
             patch.object(validator, '_validate_sample_data') as mock_sample, \
             patch.object(validator, '_validate_constraints') as mock_constraints:
            
            mock_row_count.return_value = ValidationResult(
                'users', 'row_count', ValidationStatus.PASSED, 100, 100, "Row counts match"
            )
            mock_checksum.return_value = ValidationResult(
                'users', 'checksum', ValidationStatus.PASSED, 'abc123', 'abc123', "Checksums match"
            )
            mock_sample.return_value = [
                ValidationResult('users', 'sample_data', ValidationStatus.PASSED, message="Sample data matches")
            ]
            mock_constraints.return_value = []
            
            summary = await validator._validate_table(
                mock_source_engine, mock_dest_engine, 'users', ValidationLevel.COMPREHENSIVE, 100
            )
            
            assert summary.table_name == 'users'
            assert summary.total_checks == 3
            assert summary.passed_checks == 3
            assert summary.failed_checks == 0
    
    @pytest.mark.asyncio
    async def test_validate_row_count_match(self, validator):
        """Test row count validation with matching counts."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        
        # Mock source connection
        mock_source_conn = Mock()
        mock_source_result = Mock()
        mock_source_result.scalar.return_value = 100
        mock_source_conn.execute.return_value = mock_source_result
        mock_source_engine.connect.return_value.__enter__ = Mock(return_value=mock_source_conn)
        mock_source_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        # Mock destination connection
        mock_dest_conn = Mock()
        mock_dest_result = Mock()
        mock_dest_result.scalar.return_value = 100
        mock_dest_conn.execute.return_value = mock_dest_result
        mock_dest_engine.connect.return_value.__enter__ = Mock(return_value=mock_dest_conn)
        mock_dest_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        result = await validator._validate_row_count(mock_source_engine, mock_dest_engine, 'users')
        
        assert result.table_name == 'users'
        assert result.check_type == 'row_count'
        assert result.status == ValidationStatus.PASSED
        assert result.source_value == 100
        assert result.destination_value == 100
        assert "Row counts match" in result.message
    
    @pytest.mark.asyncio
    async def test_validate_row_count_mismatch(self, validator):
        """Test row count validation with mismatched counts."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        
        # Mock source connection
        mock_source_conn = Mock()
        mock_source_result = Mock()
        mock_source_result.scalar.return_value = 100
        mock_source_conn.execute.return_value = mock_source_result
        mock_source_engine.connect.return_value.__enter__ = Mock(return_value=mock_source_conn)
        mock_source_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        # Mock destination connection
        mock_dest_conn = Mock()
        mock_dest_result = Mock()
        mock_dest_result.scalar.return_value = 95
        mock_dest_conn.execute.return_value = mock_dest_result
        mock_dest_engine.connect.return_value.__enter__ = Mock(return_value=mock_dest_conn)
        mock_dest_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        result = await validator._validate_row_count(mock_source_engine, mock_dest_engine, 'users')
        
        assert result.table_name == 'users'
        assert result.check_type == 'row_count'
        assert result.status == ValidationStatus.FAILED
        assert result.source_value == 100
        assert result.destination_value == 95
        assert "Row count mismatch" in result.message
    
    @pytest.mark.asyncio
    async def test_validate_row_count_error(self, validator):
        """Test row count validation with error."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        
        # Mock source connection to raise exception
        mock_source_engine.connect.side_effect = Exception("Connection failed")
        
        result = await validator._validate_row_count(mock_source_engine, mock_dest_engine, 'users')
        
        assert result.table_name == 'users'
        assert result.check_type == 'row_count'
        assert result.status == ValidationStatus.FAILED
        assert "Row count validation failed" in result.message
    
    @pytest.mark.asyncio
    async def test_validate_table_checksum_match(self, validator):
        """Test table checksum validation with matching checksums."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {'name': 'id', 'type': 'INTEGER'},
            {'name': 'name', 'type': 'VARCHAR'}
        ]
        
        with patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector), \
             patch.object(validator, '_calculate_table_checksum') as mock_checksum:
            
            mock_checksum.return_value = 'abc123def456'
            
            result = await validator._validate_table_checksum(mock_source_engine, mock_dest_engine, 'users')
            
            assert result.table_name == 'users'
            assert result.check_type == 'checksum'
            assert result.status == ValidationStatus.PASSED
            assert result.source_value == 'abc123def456'
            assert result.destination_value == 'abc123def456'
            assert "checksums match" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_validate_table_checksum_mismatch(self, validator):
        """Test table checksum validation with mismatched checksums."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {'name': 'id', 'type': 'INTEGER'},
            {'name': 'name', 'type': 'VARCHAR'}
        ]
        
        with patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector), \
             patch.object(validator, '_calculate_table_checksum') as mock_checksum:
            
            mock_checksum.side_effect = ['abc123def456', 'xyz789ghi012']
            
            result = await validator._validate_table_checksum(mock_source_engine, mock_dest_engine, 'users')
            
            assert result.table_name == 'users'
            assert result.check_type == 'checksum'
            assert result.status == ValidationStatus.FAILED
            assert result.source_value == 'abc123def456'
            assert result.destination_value == 'xyz789ghi012'
            assert "do not match" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_calculate_table_checksum(self, validator):
        """Test table checksum calculation."""
        mock_engine = Mock()
        mock_conn = Mock()
        mock_result = Mock()
        
        # Mock query result with sample data
        mock_result.__iter__ = Mock(return_value=iter([
            (1, 'Alice', 'alice@example.com'),
            (2, 'Bob', 'bob@example.com'),
            (3, 'Charlie', None)
        ]))
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        checksum = await validator._calculate_table_checksum(
            mock_engine, 'users', '"id", "name", "email"'
        )
        
        assert isinstance(checksum, str)
        assert len(checksum) == 32  # MD5 hash length
    
    @pytest.mark.asyncio
    async def test_validate_sample_data_match(self, validator):
        """Test sample data validation with matching data."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        mock_inspector = Mock()
        
        mock_inspector.get_columns.return_value = [
            {'name': 'id', 'type': 'INTEGER'},
            {'name': 'name', 'type': 'VARCHAR'}
        ]
        mock_inspector.get_pk_constraint.return_value = {
            'constrained_columns': ['id']
        }
        
        # Mock identical data from both databases
        sample_data = [(1, 'Alice'), (2, 'Bob'), (3, 'Charlie')]
        
        mock_source_conn = Mock()
        mock_source_conn.execute.return_value.fetchall.return_value = sample_data
        mock_source_engine.connect.return_value.__enter__ = Mock(return_value=mock_source_conn)
        mock_source_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        mock_dest_conn = Mock()
        mock_dest_conn.execute.return_value.fetchall.return_value = sample_data
        mock_dest_engine.connect.return_value.__enter__ = Mock(return_value=mock_dest_conn)
        mock_dest_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        with patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector):
            results = await validator._validate_sample_data(
                mock_source_engine, mock_dest_engine, 'users', 10
            )
            
            assert len(results) == 1
            assert results[0].table_name == 'users'
            assert results[0].check_type == 'sample_data'
            assert results[0].status == ValidationStatus.PASSED
            assert "sample rows match" in results[0].message.lower()
    
    @pytest.mark.asyncio
    async def test_validate_sample_data_mismatch(self, validator):
        """Test sample data validation with mismatched data."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        mock_inspector = Mock()
        
        mock_inspector.get_columns.return_value = [
            {'name': 'id', 'type': 'INTEGER'},
            {'name': 'name', 'type': 'VARCHAR'}
        ]
        mock_inspector.get_pk_constraint.return_value = {
            'constrained_columns': ['id']
        }
        
        # Mock different data from both databases
        source_data = [(1, 'Alice'), (2, 'Bob'), (3, 'Charlie')]
        dest_data = [(1, 'Alice'), (2, 'Robert'), (3, 'Charlie')]  # Bob -> Robert
        
        mock_source_conn = Mock()
        mock_source_conn.execute.return_value.fetchall.return_value = source_data
        mock_source_engine.connect.return_value.__enter__ = Mock(return_value=mock_source_conn)
        mock_source_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        mock_dest_conn = Mock()
        mock_dest_conn.execute.return_value.fetchall.return_value = dest_data
        mock_dest_engine.connect.return_value.__enter__ = Mock(return_value=mock_dest_conn)
        mock_dest_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        with patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector):
            results = await validator._validate_sample_data(
                mock_source_engine, mock_dest_engine, 'users', 10
            )
            
            # Should have at least one result for the mismatch
            assert len(results) >= 1
            failed_results = [r for r in results if r.status == ValidationStatus.FAILED]
            assert len(failed_results) > 0
            assert any("mismatch" in r.message.lower() for r in failed_results)
    
    @pytest.mark.asyncio
    async def test_validate_constraints_match(self, validator):
        """Test constraint validation with matching constraints."""
        mock_source_engine = Mock()
        mock_dest_engine = Mock()
        mock_source_inspector = Mock()
        mock_dest_inspector = Mock()
        
        # Mock primary key constraints
        pk_constraint = {'constrained_columns': ['id']}
        mock_source_inspector.get_pk_constraint.return_value = pk_constraint
        mock_dest_inspector.get_pk_constraint.return_value = pk_constraint
        
        # Mock foreign key constraints
        fk_constraints = [{'name': 'fk_user_id', 'constrained_columns': ['user_id']}]
        mock_source_inspector.get_foreign_keys.return_value = fk_constraints
        mock_dest_inspector.get_foreign_keys.return_value = fk_constraints
        
        # Mock unique constraints
        unique_constraints = [{'name': 'uq_email', 'column_names': ['email']}]
        mock_source_inspector.get_unique_constraints.return_value = unique_constraints
        mock_dest_inspector.get_unique_constraints.return_value = unique_constraints
        
        with patch('migration_assistant.database.data_validator.inspect') as mock_inspect:
            mock_inspect.side_effect = [mock_source_inspector, mock_dest_inspector]
            
            results = await validator._validate_constraints(mock_source_engine, mock_dest_engine, 'users')
            
            assert len(results) == 3  # PK, FK, Unique
            assert all(r.status == ValidationStatus.PASSED for r in results)
            assert any(r.check_type == 'primary_key' for r in results)
            assert any(r.check_type == 'foreign_keys' for r in results)
            assert any(r.check_type == 'unique_constraints' for r in results)
    
    @pytest.mark.asyncio
    async def test_validate_data_integrity_success(self, validator, mysql_config):
        """Test data integrity validation with no issues."""
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['users', 'posts']
        
        with patch.object(validator, '_create_engine', return_value=mock_engine), \
             patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector), \
             patch.object(validator, '_check_foreign_key_integrity', return_value=[]), \
             patch.object(validator, '_check_primary_key_integrity', return_value=[]):
            
            result = await validator.validate_data_integrity(mysql_config, ['users', 'posts'])
            
            assert result['success'] is True
            assert result['tables_validated'] == 2
            assert len(result['integrity_issues']) == 0
    
    @pytest.mark.asyncio
    async def test_validate_data_integrity_with_issues(self, validator, mysql_config):
        """Test data integrity validation with issues found."""
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['users']
        
        with patch.object(validator, '_create_engine', return_value=mock_engine), \
             patch('migration_assistant.database.data_validator.inspect', return_value=mock_inspector), \
             patch.object(validator, '_check_foreign_key_integrity', return_value=['FK issue']), \
             patch.object(validator, '_check_primary_key_integrity', return_value=['PK issue']):
            
            result = await validator.validate_data_integrity(mysql_config, ['users'])
            
            assert result['success'] is False
            assert result['tables_validated'] == 1
            assert len(result['integrity_issues']) == 2
            assert 'FK issue' in result['integrity_issues']
            assert 'PK issue' in result['integrity_issues']
    
    @pytest.mark.asyncio
    async def test_check_foreign_key_integrity_no_orphans(self, validator):
        """Test foreign key integrity check with no orphaned records."""
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = [
            {
                'constrained_columns': ['user_id'],
                'referred_table': 'users',
                'referred_columns': ['id']
            }
        ]
        
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.scalar.return_value = 0  # No orphaned records
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        issues = await validator._check_foreign_key_integrity(mock_engine, mock_inspector, 'posts')
        
        assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_check_foreign_key_integrity_with_orphans(self, validator):
        """Test foreign key integrity check with orphaned records."""
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = [
            {
                'constrained_columns': ['user_id'],
                'referred_table': 'users',
                'referred_columns': ['id']
            }
        ]
        
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.scalar.return_value = 5  # 5 orphaned records
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        issues = await validator._check_foreign_key_integrity(mock_engine, mock_inspector, 'posts')
        
        assert len(issues) == 1
        assert "5 orphaned records" in issues[0]
        assert "posts" in issues[0]
    
    @pytest.mark.asyncio
    async def test_check_primary_key_integrity_no_duplicates(self, validator):
        """Test primary key integrity check with no duplicates."""
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_pk_constraint.return_value = {
            'constrained_columns': ['id']
        }
        
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = []  # No duplicates
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        issues = await validator._check_primary_key_integrity(mock_engine, mock_inspector, 'users')
        
        assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_check_primary_key_integrity_with_duplicates(self, validator):
        """Test primary key integrity check with duplicates."""
        mock_engine = Mock()
        mock_inspector = Mock()
        mock_inspector.get_pk_constraint.return_value = {
            'constrained_columns': ['id']
        }
        
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [(1, 2), (2, 3)]  # 2 duplicate groups
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=None)
        
        issues = await validator._check_primary_key_integrity(mock_engine, mock_inspector, 'users')
        
        assert len(issues) == 1
        assert "2 duplicate primary key values" in issues[0]
        assert "users" in issues[0]


class TestValidationResult:
    """Test cases for ValidationResult."""
    
    def test_init(self):
        """Test validation result initialization."""
        result = ValidationResult(
            table_name='users',
            check_type='row_count',
            status=ValidationStatus.PASSED,
            source_value=100,
            destination_value=100,
            message='Row counts match'
        )
        
        assert result.table_name == 'users'
        assert result.check_type == 'row_count'
        assert result.status == ValidationStatus.PASSED
        assert result.source_value == 100
        assert result.destination_value == 100
        assert result.message == 'Row counts match'
        assert result.details == {}


class TestTableValidationSummary:
    """Test cases for TableValidationSummary."""
    
    def test_init(self):
        """Test table validation summary initialization."""
        summary = TableValidationSummary(table_name='users')
        
        assert summary.table_name == 'users'
        assert summary.total_checks == 0
        assert summary.passed_checks == 0
        assert summary.failed_checks == 0
        assert summary.warning_checks == 0
        assert summary.validation_time_seconds == 0.0
        assert summary.results == []
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        summary = TableValidationSummary(
            table_name='users',
            total_checks=10,
            passed_checks=8,
            failed_checks=2
        )
        
        assert summary.success_rate == 80.0
    
    def test_success_rate_no_checks(self):
        """Test success rate with no checks."""
        summary = TableValidationSummary(table_name='users')
        
        assert summary.success_rate == 0.0
    
    def test_overall_status_passed(self):
        """Test overall status when all checks passed."""
        summary = TableValidationSummary(
            table_name='users',
            total_checks=5,
            passed_checks=5,
            failed_checks=0,
            warning_checks=0
        )
        
        assert summary.overall_status == ValidationStatus.PASSED
    
    def test_overall_status_failed(self):
        """Test overall status when some checks failed."""
        summary = TableValidationSummary(
            table_name='users',
            total_checks=5,
            passed_checks=3,
            failed_checks=2,
            warning_checks=0
        )
        
        assert summary.overall_status == ValidationStatus.FAILED
    
    def test_overall_status_warning(self):
        """Test overall status when some checks have warnings."""
        summary = TableValidationSummary(
            table_name='users',
            total_checks=5,
            passed_checks=3,
            failed_checks=0,
            warning_checks=2
        )
        
        assert summary.overall_status == ValidationStatus.WARNING
    
    def test_overall_status_pending(self):
        """Test overall status when no checks completed."""
        summary = TableValidationSummary(table_name='users')
        
        assert summary.overall_status == ValidationStatus.PENDING


class TestDataValidationReport:
    """Test cases for DataValidationReport."""
    
    def test_init(self):
        """Test data validation report initialization."""
        report = DataValidationReport()
        
        assert isinstance(report.validation_time, datetime)
        assert report.validation_level == ValidationLevel.STANDARD
        assert report.source_config is None
        assert report.destination_config is None
        assert report.table_summaries == {}
        assert report.overall_status == ValidationStatus.PENDING
        assert report.total_validation_time_seconds == 0.0
        assert report.errors == []
        assert report.warnings == []
    
    def test_add_table_summary(self):
        """Test adding table summary."""
        report = DataValidationReport()
        summary = TableValidationSummary(table_name='users')
        
        report.add_table_summary(summary)
        
        assert 'users' in report.table_summaries
        assert report.table_summaries['users'] == summary
    
    def test_add_error(self):
        """Test adding error."""
        report = DataValidationReport()
        report.add_error("Test error")
        
        assert "Test error" in report.errors
    
    def test_add_warning(self):
        """Test adding warning."""
        report = DataValidationReport()
        report.add_warning("Test warning")
        
        assert "Test warning" in report.warnings
    
    def test_finalize_passed(self):
        """Test finalizing report with all passed tables."""
        report = DataValidationReport()
        
        summary1 = TableValidationSummary(
            table_name='users',
            total_checks=3,
            passed_checks=3
        )
        summary2 = TableValidationSummary(
            table_name='posts',
            total_checks=2,
            passed_checks=2
        )
        
        report.add_table_summary(summary1)
        report.add_table_summary(summary2)
        report.finalize()
        
        assert report.overall_status == ValidationStatus.PASSED
    
    def test_finalize_failed(self):
        """Test finalizing report with failed tables."""
        report = DataValidationReport()
        
        summary1 = TableValidationSummary(
            table_name='users',
            total_checks=3,
            passed_checks=2,
            failed_checks=1
        )
        summary2 = TableValidationSummary(
            table_name='posts',
            total_checks=2,
            passed_checks=2
        )
        
        report.add_table_summary(summary1)
        report.add_table_summary(summary2)
        report.finalize()
        
        assert report.overall_status == ValidationStatus.FAILED
    
    def test_finalize_warning(self):
        """Test finalizing report with warning tables."""
        report = DataValidationReport()
        
        summary1 = TableValidationSummary(
            table_name='users',
            total_checks=3,
            passed_checks=2,
            warning_checks=1
        )
        summary2 = TableValidationSummary(
            table_name='posts',
            total_checks=2,
            passed_checks=2
        )
        
        report.add_table_summary(summary1)
        report.add_table_summary(summary2)
        report.finalize()
        
        assert report.overall_status == ValidationStatus.WARNING
    
    def test_finalize_no_tables(self):
        """Test finalizing report with no tables."""
        report = DataValidationReport()
        report.finalize()
        
        assert report.overall_status == ValidationStatus.FAILED
    
    def test_property_calculations(self):
        """Test property calculations."""
        report = DataValidationReport()
        
        summary1 = TableValidationSummary(
            table_name='users',
            total_checks=5,
            passed_checks=4,
            failed_checks=1
        )
        summary2 = TableValidationSummary(
            table_name='posts',
            total_checks=3,
            passed_checks=2,
            warning_checks=1
        )
        summary3 = TableValidationSummary(
            table_name='comments',
            total_checks=2,
            passed_checks=2
        )
        
        report.add_table_summary(summary1)
        report.add_table_summary(summary2)
        report.add_table_summary(summary3)
        
        assert report.total_tables == 3
        assert report.passed_tables == 1  # Only comments fully passed
        assert report.failed_tables == 1  # users has failures
        assert report.warning_tables == 1  # posts has warnings
        assert report.overall_success_rate == 80.0  # 8 passed out of 10 total