"""Integration tests for schema analysis and data validation."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey

from migration_assistant.database.factory import DatabaseMigrationFactory
from migration_assistant.database.schema_analyzer import SchemaAnalyzer, SchemaAnalysisResult
from migration_assistant.database.data_validator import DataValidator, ValidationLevel
from migration_assistant.database.config import MySQLConfig, PostgreSQLConfig, DatabaseType
from migration_assistant.database.base import MigrationMethod


class TestSchemaDataIntegration:
    """Integration tests for schema analysis and data validation."""
    
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
    
    @pytest.mark.asyncio
    async def test_complete_migration_analysis_workflow(self, mysql_config, postgres_config):
        """Test complete workflow from schema analysis to migration recommendation."""
        # Mock schema analyzer
        mock_analyzer = Mock(spec=SchemaAnalyzer)
        
        # Create mock source schema analysis
        source_schema = SchemaAnalysisResult()
        source_schema.success = True
        source_schema.tables = {
            'users': {
                'name': 'users',
                'columns': [
                    {'name': 'id', 'type': 'INTEGER', 'nullable': False},
                    {'name': 'email', 'type': 'VARCHAR(255)', 'nullable': False},
                    {'name': 'name', 'type': 'VARCHAR(100)', 'nullable': True}
                ],
                'primary_key': {'name': 'pk_users', 'columns': ['id']},
                'row_count': 1000,
                'size_bytes': 65536
            },
            'posts': {
                'name': 'posts',
                'columns': [
                    {'name': 'id', 'type': 'INTEGER', 'nullable': False},
                    {'name': 'user_id', 'type': 'INTEGER', 'nullable': False},
                    {'name': 'title', 'type': 'VARCHAR(200)', 'nullable': False},
                    {'name': 'content', 'type': 'TEXT', 'nullable': True}
                ],
                'primary_key': {'name': 'pk_posts', 'columns': ['id']},
                'row_count': 5000,
                'size_bytes': 262144
            }
        }
        source_schema.foreign_keys = {
            'posts': [
                {
                    'name': 'fk_posts_user_id',
                    'constrained_columns': ['user_id'],
                    'referred_table': 'users',
                    'referred_columns': ['id']
                }
            ]
        }
        source_schema.views = {}
        source_schema.functions = []
        source_schema.sequences = []
        
        # Mock compatibility analysis
        from migration_assistant.database.schema_analyzer import SchemaCompatibilityResult
        compatibility = SchemaCompatibilityResult()
        compatibility.compatible = True
        compatibility.migration_complexity = "moderate"
        compatibility.recommended_method = MigrationMethod.DIRECT_TRANSFER
        compatibility.warnings = ["Cross-SQL database migration may require data type conversions"]
        compatibility.recommendations = ["Use direct transfer for moderate complexity migration"]
        
        mock_analyzer.analyze_schema.return_value = source_schema
        mock_analyzer.analyze_compatibility.return_value = compatibility
        mock_analyzer.get_migration_method_recommendations.return_value = [
            MigrationMethod.DIRECT_TRANSFER,
            MigrationMethod.DUMP_RESTORE,
            MigrationMethod.BULK_COPY
        ]
        
        # Test the complete workflow
        with patch.object(DatabaseMigrationFactory, '_schema_analyzer', mock_analyzer):
            result = await DatabaseMigrationFactory.analyze_and_recommend_method(
                mysql_config, postgres_config, analyze_schema=True
            )
            
            # Verify analysis results
            assert result['recommended_method'] == 'direct_transfer'
            assert 'direct_transfer' in result['alternative_methods']
            assert 'dump_restore' in result['alternative_methods']
            assert 'bulk_copy' in result['alternative_methods']
            
            # Verify schema analysis
            schema_analysis = result['schema_analysis']
            assert schema_analysis['source_tables'] == 2
            assert schema_analysis['source_rows'] == 6000
            assert schema_analysis['source_size_mb'] == 0.31  # (65536 + 262144) / (1024*1024)
            assert schema_analysis['has_views'] is False
            assert schema_analysis['has_functions'] is False
            assert schema_analysis['has_sequences'] is False
            
            # Verify compatibility analysis
            compatibility_analysis = result['compatibility_analysis']
            assert compatibility_analysis['compatible'] is True
            assert compatibility_analysis['complexity'] == 'moderate'
            assert len(compatibility_analysis['warnings']) > 0
            assert len(compatibility_analysis['recommendations']) > 0
            
            # Verify requirements
            assert len(result['requirements']) > 0
            assert any('connections' in req.lower() for req in result['requirements'])
    
    @pytest.mark.asyncio
    async def test_migration_method_selection_logic(self, mysql_config, postgres_config):
        """Test migration method selection based on database types and schema complexity."""
        # Test same-type migration
        methods = DatabaseMigrationFactory.get_supported_methods_for_migration(mysql_config, mysql_config)
        assert MigrationMethod.DUMP_RESTORE in methods
        assert MigrationMethod.DIRECT_TRANSFER in methods
        
        # Test cross-SQL migration
        methods = DatabaseMigrationFactory.get_supported_methods_for_migration(mysql_config, postgres_config)
        assert MigrationMethod.DIRECT_TRANSFER in methods
        assert MigrationMethod.DUMP_RESTORE in methods
    
    @pytest.mark.asyncio
    async def test_migration_time_estimation(self, mysql_config, postgres_config):
        """Test migration time estimation based on data characteristics."""
        # Test with known data size
        estimate = DatabaseMigrationFactory.estimate_migration_time(
            mysql_config, postgres_config, MigrationMethod.DIRECT_TRANSFER,
            data_size_mb=1024, row_count=100000
        )
        
        assert estimate['estimated_hours'] > 0
        assert estimate['min_hours'] < estimate['estimated_hours']
        assert estimate['max_hours'] > estimate['estimated_hours']
        assert len(estimate['factors']) > 0
        assert len(estimate['assumptions']) > 0
        
        # Verify cross-database penalty
        same_type_estimate = DatabaseMigrationFactory.estimate_migration_time(
            mysql_config, mysql_config, MigrationMethod.DIRECT_TRANSFER,
            data_size_mb=1024, row_count=100000
        )
        
        assert estimate['estimated_hours'] > same_type_estimate['estimated_hours']
    
    @pytest.mark.asyncio
    async def test_data_validation_after_migration(self, mysql_config):
        """Test data validation workflow after migration."""
        validator = DataValidator()
        
        # Mock successful validation
        with patch.object(validator, '_create_engine') as mock_create_engine, \
             patch('migration_assistant.database.data_validator.inspect') as mock_inspect, \
             patch.object(validator, '_validate_table') as mock_validate_table:
            
            mock_source_engine = Mock()
            mock_dest_engine = Mock()
            mock_create_engine.side_effect = [mock_source_engine, mock_dest_engine]
            
            mock_inspector = Mock()
            mock_inspector.get_table_names.return_value = ['users', 'posts']
            mock_inspect.return_value = mock_inspector
            
            # Mock successful table validation
            from migration_assistant.database.data_validator import TableValidationSummary, ValidationResult, ValidationStatus
            
            def create_successful_summary(table_name):
                summary = TableValidationSummary(
                    table_name=table_name,
                    total_checks=3,
                    passed_checks=3,
                    failed_checks=0,
                    warning_checks=0
                )
                summary.results = [
                    ValidationResult(table_name, 'row_count', ValidationStatus.PASSED, 1000, 1000, "Row counts match"),
                    ValidationResult(table_name, 'checksum', ValidationStatus.PASSED, 'abc123', 'abc123', "Checksums match"),
                    ValidationResult(table_name, 'constraints', ValidationStatus.PASSED, message="Constraints match")
                ]
                return summary
            
            mock_validate_table.side_effect = [
                create_successful_summary('users'),
                create_successful_summary('posts')
            ]
            
            # Run validation
            report = await validator.validate_migration(
                mysql_config, mysql_config, 
                tables=['users', 'posts'],
                validation_level=ValidationLevel.STANDARD
            )
            
            # Verify results
            assert report.overall_status == ValidationStatus.PASSED
            assert report.total_tables == 2
            assert report.passed_tables == 2
            assert report.failed_tables == 0
            assert report.overall_success_rate == 100.0
            
            # Verify individual table results
            assert 'users' in report.table_summaries
            assert 'posts' in report.table_summaries
            assert report.table_summaries['users'].overall_status == ValidationStatus.PASSED
            assert report.table_summaries['posts'].overall_status == ValidationStatus.PASSED
    
    @pytest.mark.asyncio
    async def test_schema_compatibility_with_issues(self, mysql_config, postgres_config):
        """Test schema compatibility analysis with various issues."""
        analyzer = SchemaAnalyzer()
        
        # Create source schema with potential issues
        source_schema = SchemaAnalysisResult()
        source_schema.success = True
        source_schema.tables = {
            'users': {
                'columns': [
                    {'name': 'id', 'type': 'INTEGER'},
                    {'name': 'data', 'type': 'JSON'},  # PostgreSQL-specific type
                    {'name': 'status', 'type': 'ENUM("active","inactive")'}  # MySQL-specific type
                ]
            }
        }
        source_schema.views = {'user_stats': {}}  # Has views
        source_schema.functions = [{'name': 'calculate_stats', 'type': 'function'}]  # Has functions
        source_schema.sequences = ['user_id_seq']  # PostgreSQL sequences
        
        # Create destination schema with conflicts
        dest_schema = SchemaAnalysisResult()
        dest_schema.success = True
        dest_schema.tables = {
            'users': {  # Same table name - conflict
                'columns': [
                    {'name': 'id', 'type': 'INTEGER'},
                    {'name': 'name', 'type': 'VARCHAR(100)'}
                ]
            }
        }
        
        with patch.object(analyzer, 'analyze_schema') as mock_analyze:
            mock_analyze.side_effect = [source_schema, dest_schema]
            
            result = await analyzer.analyze_compatibility(
                mysql_config, postgres_config, source_schema, dest_schema
            )
            
            # Should detect issues
            assert result.compatible is False
            assert len(result.issues) > 0
            assert any("Table name conflicts" in issue for issue in result.issues)
            assert len(result.warnings) > 0
            assert result.migration_complexity in ["moderate", "complex"]
            assert len(result.unsupported_features) > 0
    
    @pytest.mark.asyncio
    async def test_method_requirements_generation(self, mysql_config, postgres_config):
        """Test generation of method-specific requirements."""
        # Test dump_restore requirements
        requirements = DatabaseMigrationFactory._get_method_requirements(
            "dump_restore", mysql_config, postgres_config
        )
        
        assert any("disk space" in req.lower() for req in requirements)
        assert any("dump" in req.lower() for req in requirements)
        assert any("mysql" in req.lower() for req in requirements)
        
        # Test direct_transfer requirements
        requirements = DatabaseMigrationFactory._get_method_requirements(
            "direct_transfer", mysql_config, postgres_config
        )
        
        assert any("simultaneous connections" in req.lower() for req in requirements)
        assert any("compatible data types" in req.lower() for req in requirements)
        
        # Test cloud_native requirements
        requirements = DatabaseMigrationFactory._get_method_requirements(
            "cloud_native", mysql_config, postgres_config
        )
        
        assert any("cloud provider" in req.lower() for req in requirements)
        assert any("iam permissions" in req.lower() for req in requirements)
    
    @pytest.mark.asyncio
    async def test_comprehensive_validation_workflow(self, mysql_config):
        """Test comprehensive data validation with sample data checking."""
        validator = DataValidator()
        
        with patch.object(validator, '_create_engine') as mock_create_engine, \
             patch('migration_assistant.database.data_validator.inspect') as mock_inspect, \
             patch.object(validator, '_validate_row_count') as mock_row_count, \
             patch.object(validator, '_validate_table_checksum') as mock_checksum, \
             patch.object(validator, '_validate_sample_data') as mock_sample, \
             patch.object(validator, '_validate_constraints') as mock_constraints:
            
            mock_source_engine = Mock()
            mock_dest_engine = Mock()
            mock_create_engine.side_effect = [mock_source_engine, mock_dest_engine]
            
            mock_inspector = Mock()
            mock_inspector.get_table_names.return_value = ['users']
            mock_inspect.return_value = mock_inspector
            
            # Mock validation results
            from migration_assistant.database.data_validator import ValidationResult, ValidationStatus
            
            mock_row_count.return_value = ValidationResult(
                'users', 'row_count', ValidationStatus.PASSED, 1000, 1000, "Row counts match"
            )
            mock_checksum.return_value = ValidationResult(
                'users', 'checksum', ValidationStatus.PASSED, 'abc123', 'abc123', "Checksums match"
            )
            mock_sample.return_value = [
                ValidationResult('users', 'sample_data', ValidationStatus.PASSED, message="Sample data matches"),
                ValidationResult('users', 'sample_data_row', ValidationStatus.FAILED, 
                               {'id': 1, 'name': 'Alice'}, {'id': 1, 'name': 'Bob'}, "Row 1 data mismatch")
            ]
            mock_constraints.return_value = [
                ValidationResult('users', 'primary_key', ValidationStatus.PASSED, message="Primary key matches")
            ]
            
            # Run comprehensive validation
            report = await validator.validate_migration(
                mysql_config, mysql_config,
                tables=['users'],
                validation_level=ValidationLevel.COMPREHENSIVE,
                sample_size=100
            )
            
            # Verify comprehensive validation was performed
            assert report.validation_level == ValidationLevel.COMPREHENSIVE
            assert 'users' in report.table_summaries
            
            summary = report.table_summaries['users']
            assert summary.total_checks == 5  # row_count + checksum + 2 sample + constraints
            assert summary.passed_checks == 3
            assert summary.failed_checks == 1
            assert summary.overall_status == ValidationStatus.FAILED  # Due to sample data mismatch
    
    @pytest.mark.asyncio
    async def test_data_integrity_validation(self, mysql_config):
        """Test data integrity validation within a single database."""
        validator = DataValidator()
        
        with patch.object(validator, '_create_engine') as mock_create_engine, \
             patch('migration_assistant.database.data_validator.inspect') as mock_inspect, \
             patch.object(validator, '_check_foreign_key_integrity') as mock_fk_check, \
             patch.object(validator, '_check_primary_key_integrity') as mock_pk_check:
            
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            mock_inspector = Mock()
            mock_inspector.get_table_names.return_value = ['users', 'posts']
            mock_inspect.return_value = mock_inspector
            
            # Mock integrity checks with issues
            mock_fk_check.side_effect = [
                [],  # users - no FK issues
                ['Table posts: 5 orphaned records found in foreign key user_id -> users.id']  # posts - FK issues
            ]
            mock_pk_check.side_effect = [
                [],  # users - no PK issues
                []   # posts - no PK issues
            ]
            
            result = await validator.validate_data_integrity(mysql_config, ['users', 'posts'])
            
            # Verify integrity validation results
            assert result['success'] is False  # Due to FK issues
            assert result['tables_validated'] == 2
            assert len(result['integrity_issues']) == 1
            assert 'orphaned records' in result['integrity_issues'][0]
            assert 'posts' in result['integrity_issues'][0]
    
    def test_migration_method_compatibility_matrix(self):
        """Test migration method compatibility across different database types."""
        # Define test configurations
        mysql_config = MySQLConfig(host="localhost", username="test", password="test", database="test")
        postgres_config = PostgreSQLConfig(host="localhost", username="test", password="test", database="test")
        
        # Test compatibility matrix
        test_cases = [
            (mysql_config, mysql_config, True),      # Same type - should be supported
            (mysql_config, postgres_config, True),   # SQL to SQL - should be supported
            (postgres_config, mysql_config, True),   # SQL to SQL - should be supported
            (postgres_config, postgres_config, True) # Same type - should be supported
        ]
        
        for source_config, dest_config, expected_supported in test_cases:
            is_supported = DatabaseMigrationFactory.is_migration_supported(
                source_config.type, dest_config.type
            )
            assert is_supported == expected_supported, \
                f"Migration from {source_config.type} to {dest_config.type} support mismatch"
            
            if is_supported:
                methods = DatabaseMigrationFactory.get_supported_methods_for_migration(
                    source_config, dest_config
                )
                assert len(methods) > 0, \
                    f"No methods available for {source_config.type} to {dest_config.type}"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_analysis_workflow(self, mysql_config, postgres_config):
        """Test error handling throughout the analysis workflow."""
        # Test schema analysis failure
        with patch.object(DatabaseMigrationFactory, '_schema_analyzer') as mock_analyzer:
            mock_analyzer.analyze_schema.side_effect = Exception("Database connection failed")
            
            result = await DatabaseMigrationFactory.analyze_and_recommend_method(
                mysql_config, postgres_config, analyze_schema=True
            )
            
            # Should fall back to basic recommendation
            assert result['recommended_method'] is not None
            assert len(result['warnings']) > 0
            assert any("Schema analysis failed" in warning for warning in result['warnings'])
        
        # Test data validation failure
        validator = DataValidator()
        
        with patch.object(validator, '_create_engine', side_effect=Exception("Connection failed")):
            report = await validator.validate_migration(mysql_config, postgres_config)
            
            assert report.overall_status == ValidationStatus.FAILED
            assert len(report.errors) > 0
            assert any("Migration validation failed" in error for error in report.errors)