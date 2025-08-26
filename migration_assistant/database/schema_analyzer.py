"""Schema analysis module using SQLAlchemy for relational databases."""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, inspect, text
from sqlalchemy.engine import Engine, Inspector
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import ForeignKeyConstraint, PrimaryKeyConstraint, Index, UniqueConstraint
from sqlalchemy.types import TypeEngine

from .config import DatabaseConfigUnion, DatabaseType
from .base import MigrationMethod
from ..core.exceptions import UnsupportedDatabaseError


logger = logging.getLogger(__name__)


class SchemaAnalysisResult:
    """Result of schema analysis operation."""
    
    def __init__(self):
        self.success: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.tables: Dict[str, Dict[str, Any]] = {}
        self.views: Dict[str, Dict[str, Any]] = {}
        self.indexes: Dict[str, List[Dict[str, Any]]] = {}
        self.foreign_keys: Dict[str, List[Dict[str, Any]]] = {}
        self.constraints: Dict[str, List[Dict[str, Any]]] = {}
        self.sequences: List[str] = []
        self.functions: List[Dict[str, Any]] = []
        self.triggers: List[Dict[str, Any]] = []
        self.schema_info: Dict[str, Any] = {}
        self.analysis_time: Optional[datetime] = None
        
    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.success = False
        
    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)
        
    def get_table_count(self) -> int:
        """Get total number of tables."""
        return len(self.tables)
        
    def get_total_rows(self) -> int:
        """Get total number of rows across all tables."""
        return sum(table.get('row_count', 0) for table in self.tables.values())
        
    def get_total_size_bytes(self) -> int:
        """Get total size in bytes across all tables."""
        return sum(table.get('size_bytes', 0) for table in self.tables.values())


class SchemaCompatibilityResult:
    """Result of schema compatibility analysis."""
    
    def __init__(self):
        self.compatible: bool = True
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.recommendations: List[str] = []
        self.migration_complexity: str = "simple"  # simple, moderate, complex
        self.recommended_method: Optional[MigrationMethod] = None
        self.data_type_mappings: Dict[str, str] = {}
        self.unsupported_features: List[str] = []
        
    def add_issue(self, issue: str) -> None:
        """Add a compatibility issue."""
        self.issues.append(issue)
        self.compatible = False
        
    def add_warning(self, warning: str) -> None:
        """Add a compatibility warning."""
        self.warnings.append(warning)
        
    def add_recommendation(self, recommendation: str) -> None:
        """Add a migration recommendation."""
        self.recommendations.append(recommendation)


class SchemaAnalyzer:
    """Schema analyzer using SQLAlchemy for relational databases."""
    
    def __init__(self):
        """Initialize the schema analyzer."""
        self._supported_types = {
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL, 
            DatabaseType.SQLITE,
            DatabaseType.AWS_RDS_MYSQL,
            DatabaseType.AWS_RDS_POSTGRESQL,
            DatabaseType.GOOGLE_CLOUD_SQL,
            DatabaseType.AZURE_SQL
        }
        
    def _create_engine(self, config: DatabaseConfigUnion) -> Engine:
        """Create SQLAlchemy engine from database configuration.
        
        Args:
            config: Database configuration
            
        Returns:
            SQLAlchemy Engine instance
            
        Raises:
            UnsupportedDatabaseError: If database type is not supported
        """
        if config.type not in self._supported_types:
            raise UnsupportedDatabaseError(f"Schema analysis not supported for {config.type}")
        
        # Build connection string based on database type
        if config.type in (DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL):
            connection_string = f"mysql+mysqlconnector://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}"
        elif config.type in (DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL):
            connection_string = f"postgresql+psycopg2://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}"
        elif config.type == DatabaseType.SQLITE:
            connection_string = f"sqlite:///{config.database_path}"
        else:
            # For cloud databases, use appropriate connection strings
            connection_string = f"{config.type.value}://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}"
        
        # Add SSL and other connection parameters
        connect_args = {}
        if hasattr(config, 'ssl_enabled') and config.ssl_enabled:
            connect_args['ssl_disabled'] = False
            
        if hasattr(config, 'extra_params') and config.extra_params:
            connect_args.update(config.extra_params)
            
        return create_engine(
            connection_string,
            connect_args=connect_args,
            pool_timeout=config.connection_timeout,
            echo=False  # Set to True for debugging
        )
    
    async def analyze_schema(self, config: DatabaseConfigUnion, 
                           include_data_stats: bool = True,
                           tables: Optional[List[str]] = None) -> SchemaAnalysisResult:
        """Analyze database schema comprehensively.
        
        Args:
            config: Database configuration
            include_data_stats: Whether to include row counts and size statistics
            tables: Specific tables to analyze (None for all tables)
            
        Returns:
            Schema analysis result
        """
        result = SchemaAnalysisResult()
        result.analysis_time = datetime.utcnow()
        
        try:
            engine = self._create_engine(config)
            inspector = inspect(engine)
            metadata = MetaData()
            
            # Get basic schema information
            result.schema_info = await self._get_schema_info(inspector, config)
            
            # Get table names to analyze
            if tables is None:
                tables = inspector.get_table_names()
                if hasattr(inspector, 'get_schema_names'):
                    # For databases that support schemas
                    schema_name = getattr(config, 'schema', None)
                    if schema_name:
                        tables = inspector.get_table_names(schema=schema_name)
            
            # Analyze each table
            for table_name in tables:
                try:
                    table_info = await self._analyze_table(
                        inspector, engine, metadata, table_name, 
                        include_data_stats, config
                    )
                    result.tables[table_name] = table_info
                    
                    # Get table-specific constraints and indexes
                    result.indexes[table_name] = self._get_table_indexes(inspector, table_name)
                    result.foreign_keys[table_name] = self._get_table_foreign_keys(inspector, table_name)
                    result.constraints[table_name] = self._get_table_constraints(inspector, table_name)
                    
                except Exception as e:
                    result.add_error(f"Failed to analyze table {table_name}: {str(e)}")
                    logger.error(f"Error analyzing table {table_name}: {e}")
            
            # Analyze views
            try:
                view_names = inspector.get_view_names()
                for view_name in view_names:
                    view_info = await self._analyze_view(inspector, view_name, config)
                    result.views[view_name] = view_info
            except Exception as e:
                result.add_warning(f"Could not analyze views: {str(e)}")
            
            # Get sequences (for PostgreSQL and Oracle)
            try:
                if hasattr(inspector, 'get_sequence_names'):
                    result.sequences = inspector.get_sequence_names()
            except Exception as e:
                result.add_warning(f"Could not get sequences: {str(e)}")
            
            # Get functions and procedures (database-specific)
            try:
                result.functions = await self._get_functions_and_procedures(inspector, config)
            except Exception as e:
                result.add_warning(f"Could not get functions/procedures: {str(e)}")
                
        except Exception as e:
            result.add_error(f"Schema analysis failed: {str(e)}")
            logger.error(f"Schema analysis failed: {e}")
        
        return result
    
    async def _get_schema_info(self, inspector: Inspector, config: DatabaseConfigUnion) -> Dict[str, Any]:
        """Get general schema information.
        
        Args:
            inspector: SQLAlchemy Inspector
            config: Database configuration
            
        Returns:
            Schema information dictionary
        """
        info = {
            'database_type': config.type.value,
            'database_name': config.database,
            'host': config.host,
            'port': config.port
        }
        
        try:
            # Get database version if available
            with inspector.bind.connect() as conn:
                if config.type in (DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL):
                    result = conn.execute(text("SELECT VERSION()"))
                    info['version'] = result.scalar()
                elif config.type in (DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL):
                    result = conn.execute(text("SELECT version()"))
                    info['version'] = result.scalar()
                elif config.type == DatabaseType.SQLITE:
                    result = conn.execute(text("SELECT sqlite_version()"))
                    info['version'] = result.scalar()
        except Exception as e:
            logger.warning(f"Could not get database version: {e}")
        
        try:
            # Get schema names if supported
            if hasattr(inspector, 'get_schema_names'):
                info['schemas'] = inspector.get_schema_names()
        except Exception as e:
            logger.warning(f"Could not get schema names: {e}")
            
        return info
    
    async def _analyze_table(self, inspector: Inspector, engine: Engine, 
                           metadata: MetaData, table_name: str,
                           include_data_stats: bool, config: DatabaseConfigUnion) -> Dict[str, Any]:
        """Analyze a specific table.
        
        Args:
            inspector: SQLAlchemy Inspector
            engine: SQLAlchemy Engine
            metadata: MetaData object
            table_name: Name of table to analyze
            include_data_stats: Whether to include data statistics
            config: Database configuration
            
        Returns:
            Table analysis information
        """
        table_info = {
            'name': table_name,
            'columns': [],
            'primary_key': None,
            'row_count': 0,
            'size_bytes': 0,
            'engine': None,  # For MySQL
            'collation': None
        }
        
        # Get column information
        columns = inspector.get_columns(table_name)
        for column in columns:
            column_info = {
                'name': column['name'],
                'type': str(column['type']),
                'nullable': column.get('nullable', True),
                'default': column.get('default'),
                'autoincrement': column.get('autoincrement', False),
                'comment': column.get('comment')
            }
            
            # Add type-specific information
            if hasattr(column['type'], 'length') and column['type'].length:
                column_info['length'] = column['type'].length
            if hasattr(column['type'], 'precision') and column['type'].precision:
                column_info['precision'] = column['type'].precision
            if hasattr(column['type'], 'scale') and column['type'].scale:
                column_info['scale'] = column['type'].scale
                
            table_info['columns'].append(column_info)
        
        # Get primary key information
        try:
            pk_constraint = inspector.get_pk_constraint(table_name)
            if pk_constraint and pk_constraint.get('constrained_columns'):
                table_info['primary_key'] = {
                    'name': pk_constraint.get('name'),
                    'columns': pk_constraint['constrained_columns']
                }
        except Exception as e:
            logger.warning(f"Could not get primary key for {table_name}: {e}")
        
        # Get data statistics if requested
        if include_data_stats:
            try:
                with engine.connect() as conn:
                    # Get row count
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    table_info['row_count'] = result.scalar()
                    
                    # Get table size (database-specific)
                    if config.type in (DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL):
                        result = conn.execute(text("""
                            SELECT 
                                ENGINE,
                                TABLE_COLLATION,
                                DATA_LENGTH + INDEX_LENGTH as size_bytes
                            FROM information_schema.TABLES 
                            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name
                        """), {'table_name': table_name})
                        row = result.fetchone()
                        if row:
                            table_info['engine'] = row[0]
                            table_info['collation'] = row[1]
                            table_info['size_bytes'] = row[2] or 0
                            
                    elif config.type in (DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL):
                        result = conn.execute(text("""
                            SELECT pg_total_relation_size(:table_name)
                        """), {'table_name': table_name})
                        table_info['size_bytes'] = result.scalar() or 0
                        
            except Exception as e:
                logger.warning(f"Could not get data statistics for {table_name}: {e}")
        
        return table_info
    
    async def _analyze_view(self, inspector: Inspector, view_name: str, 
                          config: DatabaseConfigUnion) -> Dict[str, Any]:
        """Analyze a database view.
        
        Args:
            inspector: SQLAlchemy Inspector
            view_name: Name of view to analyze
            config: Database configuration
            
        Returns:
            View analysis information
        """
        view_info = {
            'name': view_name,
            'columns': [],
            'definition': None
        }
        
        try:
            # Get view columns
            columns = inspector.get_columns(view_name)
            for column in columns:
                column_info = {
                    'name': column['name'],
                    'type': str(column['type']),
                    'nullable': column.get('nullable', True)
                }
                view_info['columns'].append(column_info)
        except Exception as e:
            logger.warning(f"Could not get columns for view {view_name}: {e}")
        
        try:
            # Get view definition (database-specific)
            if hasattr(inspector, 'get_view_definition'):
                view_info['definition'] = inspector.get_view_definition(view_name)
        except Exception as e:
            logger.warning(f"Could not get definition for view {view_name}: {e}")
            
        return view_info
    
    def _get_table_indexes(self, inspector: Inspector, table_name: str) -> List[Dict[str, Any]]:
        """Get indexes for a table.
        
        Args:
            inspector: SQLAlchemy Inspector
            table_name: Name of table
            
        Returns:
            List of index information
        """
        try:
            indexes = inspector.get_indexes(table_name)
            return [
                {
                    'name': idx.get('name'),
                    'columns': idx.get('column_names', []),
                    'unique': idx.get('unique', False),
                    'type': idx.get('type')
                }
                for idx in indexes
            ]
        except Exception as e:
            logger.warning(f"Could not get indexes for {table_name}: {e}")
            return []
    
    def _get_table_foreign_keys(self, inspector: Inspector, table_name: str) -> List[Dict[str, Any]]:
        """Get foreign keys for a table.
        
        Args:
            inspector: SQLAlchemy Inspector
            table_name: Name of table
            
        Returns:
            List of foreign key information
        """
        try:
            foreign_keys = inspector.get_foreign_keys(table_name)
            return [
                {
                    'name': fk.get('name'),
                    'constrained_columns': fk.get('constrained_columns', []),
                    'referred_table': fk.get('referred_table'),
                    'referred_columns': fk.get('referred_columns', []),
                    'referred_schema': fk.get('referred_schema'),
                    'on_delete': fk.get('options', {}).get('ondelete'),
                    'on_update': fk.get('options', {}).get('onupdate')
                }
                for fk in foreign_keys
            ]
        except Exception as e:
            logger.warning(f"Could not get foreign keys for {table_name}: {e}")
            return []
    
    def _get_table_constraints(self, inspector: Inspector, table_name: str) -> List[Dict[str, Any]]:
        """Get constraints for a table.
        
        Args:
            inspector: SQLAlchemy Inspector
            table_name: Name of table
            
        Returns:
            List of constraint information
        """
        constraints = []
        
        try:
            # Get unique constraints
            unique_constraints = inspector.get_unique_constraints(table_name)
            for constraint in unique_constraints:
                constraints.append({
                    'type': 'unique',
                    'name': constraint.get('name'),
                    'columns': constraint.get('column_names', [])
                })
        except Exception as e:
            logger.warning(f"Could not get unique constraints for {table_name}: {e}")
        
        try:
            # Get check constraints
            if hasattr(inspector, 'get_check_constraints'):
                check_constraints = inspector.get_check_constraints(table_name)
                for constraint in check_constraints:
                    constraints.append({
                        'type': 'check',
                        'name': constraint.get('name'),
                        'condition': constraint.get('sqltext')
                    })
        except Exception as e:
            logger.warning(f"Could not get check constraints for {table_name}: {e}")
            
        return constraints
    
    async def _get_functions_and_procedures(self, inspector: Inspector, 
                                          config: DatabaseConfigUnion) -> List[Dict[str, Any]]:
        """Get functions and procedures (database-specific).
        
        Args:
            inspector: SQLAlchemy Inspector
            config: Database configuration
            
        Returns:
            List of function/procedure information
        """
        functions = []
        
        try:
            with inspector.bind.connect() as conn:
                if config.type in (DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL):
                    # Get stored procedures and functions
                    result = conn.execute(text("""
                        SELECT ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_SCHEMA
                        FROM information_schema.ROUTINES
                        WHERE ROUTINE_SCHEMA = DATABASE()
                    """))
                    for row in result:
                        functions.append({
                            'name': row[0],
                            'type': row[1].lower(),
                            'schema': row[2]
                        })
                        
                elif config.type in (DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL):
                    # Get functions
                    result = conn.execute(text("""
                        SELECT proname, prokind, pronamespace::regnamespace::text
                        FROM pg_proc
                        WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    """))
                    for row in result:
                        func_type = 'function'
                        if row[1] == 'p':  # procedure
                            func_type = 'procedure'
                        elif row[1] == 'a':  # aggregate
                            func_type = 'aggregate'
                            
                        functions.append({
                            'name': row[0],
                            'type': func_type,
                            'schema': row[2]
                        })
        except Exception as e:
            logger.warning(f"Could not get functions/procedures: {e}")
            
        return functions
    
    async def analyze_compatibility(self, source_config: DatabaseConfigUnion,
                                  destination_config: DatabaseConfigUnion,
                                  source_schema: Optional[SchemaAnalysisResult] = None,
                                  destination_schema: Optional[SchemaAnalysisResult] = None) -> SchemaCompatibilityResult:
        """Analyze compatibility between source and destination schemas.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            source_schema: Pre-analyzed source schema (optional)
            destination_schema: Pre-analyzed destination schema (optional)
            
        Returns:
            Schema compatibility analysis result
        """
        result = SchemaCompatibilityResult()
        
        try:
            # Analyze schemas if not provided
            if source_schema is None:
                source_schema = await self.analyze_schema(source_config)
            if destination_schema is None:
                destination_schema = await self.analyze_schema(destination_config, include_data_stats=False)
            
            # Check if source analysis was successful
            if not source_schema.success:
                result.add_issue("Could not analyze source schema")
                return result
            
            # Basic compatibility checks
            await self._check_database_type_compatibility(source_config, destination_config, result)
            await self._check_table_name_conflicts(source_schema, destination_schema, result)
            await self._check_data_type_compatibility(source_schema, destination_schema, result)
            await self._check_constraint_compatibility(source_schema, destination_schema, result)
            await self._check_feature_compatibility(source_schema, destination_schema, source_config, destination_config, result)
            
            # Determine migration complexity and recommended method
            self._determine_migration_complexity(source_schema, destination_schema, result)
            self._recommend_migration_method(source_config, destination_config, result)
            
        except Exception as e:
            result.add_issue(f"Compatibility analysis failed: {str(e)}")
            logger.error(f"Compatibility analysis failed: {e}")
        
        return result
    
    async def _check_database_type_compatibility(self, source_config: DatabaseConfigUnion,
                                               destination_config: DatabaseConfigUnion,
                                               result: SchemaCompatibilityResult) -> None:
        """Check basic database type compatibility."""
        source_type = source_config.type
        dest_type = destination_config.type
        
        # Same type migrations are generally compatible
        if source_type == dest_type:
            result.add_recommendation("Same database type migration - should be straightforward")
            return
        
        # SQL to SQL migrations
        sql_types = {DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE,
                    DatabaseType.AWS_RDS_MYSQL, DatabaseType.AWS_RDS_POSTGRESQL}
        
        if source_type in sql_types and dest_type in sql_types:
            result.add_warning("Cross-SQL database migration may require data type conversions")
            result.migration_complexity = "moderate"
        else:
            result.add_issue(f"Migration from {source_type} to {dest_type} requires significant schema transformation")
            result.migration_complexity = "complex"
    
    async def _check_table_name_conflicts(self, source_schema: SchemaAnalysisResult,
                                        destination_schema: SchemaAnalysisResult,
                                        result: SchemaCompatibilityResult) -> None:
        """Check for table name conflicts."""
        source_tables = set(source_schema.tables.keys())
        dest_tables = set(destination_schema.tables.keys())
        
        conflicts = source_tables.intersection(dest_tables)
        if conflicts:
            result.add_issue(f"Table name conflicts detected: {', '.join(sorted(conflicts))}")
            result.add_recommendation("Consider using table prefixes or renaming conflicting tables")
    
    async def _check_data_type_compatibility(self, source_schema: SchemaAnalysisResult,
                                           destination_schema: SchemaAnalysisResult,
                                           result: SchemaCompatibilityResult) -> None:
        """Check data type compatibility between schemas."""
        # This is a simplified check - in practice, you'd want more sophisticated type mapping
        incompatible_types = []
        
        for table_name, table_info in source_schema.tables.items():
            for column in table_info.get('columns', []):
                column_type = column.get('type', '').upper()
                
                # Check for database-specific types that might not be compatible
                if 'ENUM' in column_type:
                    result.add_warning(f"ENUM type in {table_name}.{column['name']} may need conversion")
                elif 'JSON' in column_type:
                    result.add_warning(f"JSON type in {table_name}.{column['name']} may not be supported in destination")
                elif 'GEOMETRY' in column_type or 'GEOGRAPHY' in column_type:
                    result.add_warning(f"Spatial type in {table_name}.{column['name']} may need special handling")
    
    async def _check_constraint_compatibility(self, source_schema: SchemaAnalysisResult,
                                            destination_schema: SchemaAnalysisResult,
                                            result: SchemaCompatibilityResult) -> None:
        """Check constraint compatibility."""
        for table_name, constraints in source_schema.constraints.items():
            for constraint in constraints:
                if constraint.get('type') == 'check':
                    result.add_warning(f"Check constraint in {table_name} may need manual verification")
    
    async def _check_feature_compatibility(self, source_schema: SchemaAnalysisResult,
                                         destination_schema: SchemaAnalysisResult,
                                         source_config: DatabaseConfigUnion,
                                         destination_config: DatabaseConfigUnion,
                                         result: SchemaCompatibilityResult) -> None:
        """Check database-specific feature compatibility."""
        # Check for sequences (PostgreSQL specific)
        if source_schema.sequences and destination_config.type not in (DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL):
            result.add_warning("Source database uses sequences which may not be supported in destination")
            result.unsupported_features.append("sequences")
        
        # Check for functions/procedures
        if source_schema.functions:
            result.add_warning("Source database contains functions/procedures that will need manual migration")
            result.unsupported_features.append("functions/procedures")
        
        # Check for views
        if source_schema.views:
            result.add_recommendation("Views will need to be recreated after data migration")
    
    def _determine_migration_complexity(self, source_schema: SchemaAnalysisResult,
                                      destination_schema: SchemaAnalysisResult,
                                      result: SchemaCompatibilityResult) -> None:
        """Determine overall migration complexity."""
        complexity_score = 0
        
        # Base complexity on number of tables
        table_count = source_schema.get_table_count()
        if table_count > 100:
            complexity_score += 3
        elif table_count > 20:
            complexity_score += 2
        elif table_count > 5:
            complexity_score += 1
        
        # Add complexity for foreign keys
        fk_count = sum(len(fks) for fks in source_schema.foreign_keys.values())
        if fk_count > 20:
            complexity_score += 2
        elif fk_count > 5:
            complexity_score += 1
        
        # Add complexity for views and functions
        if source_schema.views:
            complexity_score += 1
        if source_schema.functions:
            complexity_score += 2
        
        # Add complexity for issues found
        complexity_score += len(result.issues)
        
        if complexity_score >= 6:
            result.migration_complexity = "complex"
        elif complexity_score >= 3:
            result.migration_complexity = "moderate"
        else:
            result.migration_complexity = "simple"
    
    def _recommend_migration_method(self, source_config: DatabaseConfigUnion,
                                  destination_config: DatabaseConfigUnion,
                                  result: SchemaCompatibilityResult) -> None:
        """Recommend the best migration method."""
        source_type = source_config.type
        dest_type = destination_config.type
        
        # Same type migrations
        if source_type == dest_type:
            result.recommended_method = MigrationMethod.DUMP_RESTORE
            result.add_recommendation("Use dump and restore for same-type migration")
        
        # SQL to SQL migrations
        elif source_type in {DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE} and \
             dest_type in {DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE}:
            if result.migration_complexity == "simple":
                result.recommended_method = MigrationMethod.DIRECT_TRANSFER
                result.add_recommendation("Use direct transfer for simple cross-SQL migration")
            else:
                result.recommended_method = MigrationMethod.DUMP_RESTORE
                result.add_recommendation("Use dump and restore with schema transformation")
        
        # Cloud migrations
        elif "aws" in source_type.value.lower() or "aws" in dest_type.value.lower() or \
             "google" in source_type.value.lower() or "google" in dest_type.value.lower() or \
             "azure" in source_type.value.lower() or "azure" in dest_type.value.lower():
            result.recommended_method = MigrationMethod.CLOUD_NATIVE
            result.add_recommendation("Use cloud-native migration tools when available")
        
        else:
            result.recommended_method = MigrationMethod.DUMP_RESTORE
            result.add_recommendation("Use dump and restore as fallback method")
    
    def get_migration_method_recommendations(self, source_config: DatabaseConfigUnion,
                                           destination_config: DatabaseConfigUnion,
                                           schema_analysis: Optional[SchemaAnalysisResult] = None) -> List[MigrationMethod]:
        """Get recommended migration methods in order of preference.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            schema_analysis: Optional schema analysis result
            
        Returns:
            List of recommended migration methods in order of preference
        """
        methods = []
        
        source_type = source_config.type
        dest_type = destination_config.type
        
        # Same type migrations
        if source_type == dest_type:
            methods.extend([
                MigrationMethod.DUMP_RESTORE,
                MigrationMethod.DIRECT_TRANSFER,
                MigrationMethod.STREAMING
            ])
        
        # SQL to SQL migrations
        elif source_type in {DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE} and \
             dest_type in {DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE}:
            methods.extend([
                MigrationMethod.DIRECT_TRANSFER,
                MigrationMethod.DUMP_RESTORE,
                MigrationMethod.BULK_COPY
            ])
        
        # Cloud migrations
        elif any("aws" in t.value.lower() or "google" in t.value.lower() or "azure" in t.value.lower() 
                for t in [source_type, dest_type]):
            methods.extend([
                MigrationMethod.CLOUD_NATIVE,
                MigrationMethod.DUMP_RESTORE,
                MigrationMethod.DIRECT_TRANSFER
            ])
        
        else:
            methods.extend([
                MigrationMethod.DUMP_RESTORE,
                MigrationMethod.BULK_COPY
            ])
        
        return methods