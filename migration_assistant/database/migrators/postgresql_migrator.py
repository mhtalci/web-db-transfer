"""PostgreSQL database migrator implementation using psycopg2."""

import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import psycopg2
from psycopg2 import Error as PostgreSQLError
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from ..base import DatabaseMigrator, MigrationResult, MigrationProgress, MigrationStatus, MigrationMethod
from ..config import PostgreSQLConfig, DatabaseConfigUnion


logger = logging.getLogger(__name__)


class PostgreSQLMigrator(DatabaseMigrator):
    """PostgreSQL database migrator using psycopg2."""
    
    def __init__(self, source_config: DatabaseConfigUnion, destination_config: DatabaseConfigUnion):
        """Initialize PostgreSQL migrator.
        
        Args:
            source_config: Source PostgreSQL database configuration
            destination_config: Destination PostgreSQL database configuration
        """
        super().__init__(source_config, destination_config)
        self._source_pool: Optional[ThreadedConnectionPool] = None
        self._destination_pool: Optional[ThreadedConnectionPool] = None
        
    def _create_connection_string(self, config: PostgreSQLConfig) -> str:
        """Create connection string for PostgreSQL.
        
        Args:
            config: PostgreSQL configuration
            
        Returns:
            Connection string
        """
        conn_params = []
        
        if config.host:
            conn_params.append(f"host={config.host}")
        if config.port:
            conn_params.append(f"port={config.port}")
        if config.database:
            conn_params.append(f"dbname={config.database}")
        if config.username:
            conn_params.append(f"user={config.username}")
        if config.password:
            conn_params.append(f"password={config.password}")
        if config.sslmode:
            conn_params.append(f"sslmode={config.sslmode}")
        if config.connection_timeout:
            conn_params.append(f"connect_timeout={config.connection_timeout}")
        
        # Add extra parameters
        for key, value in config.extra_params.items():
            conn_params.append(f"{key}={value}")
        
        return " ".join(conn_params)
    
    async def connect_source(self) -> bool:
        """Connect to the source PostgreSQL database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            conn_string = self._create_connection_string(self.source_config)
            self._source_pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=conn_string
            )
            
            # Test connection
            conn = self._source_pool.getconn()
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            self._source_pool.putconn(conn)
            
            logger.info(f"Connected to source PostgreSQL database: {self.source_config.host}:{self.source_config.port}")
            return True
            
        except PostgreSQLError as e:
            logger.error(f"Failed to connect to source PostgreSQL database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to source PostgreSQL: {e}")
            return False
    
    async def connect_destination(self) -> bool:
        """Connect to the destination PostgreSQL database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            conn_string = self._create_connection_string(self.destination_config)
            self._destination_pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=conn_string
            )
            
            # Test connection
            conn = self._destination_pool.getconn()
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            self._destination_pool.putconn(conn)
            
            logger.info(f"Connected to destination PostgreSQL database: {self.destination_config.host}:{self.destination_config.port}")
            return True
            
        except PostgreSQLError as e:
            logger.error(f"Failed to connect to destination PostgreSQL database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to destination PostgreSQL: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from both source and destination databases."""
        try:
            if self._source_pool:
                self._source_pool.closeall()
                self._source_pool = None
                
            if self._destination_pool:
                self._destination_pool.closeall()
                self._destination_pool = None
                
            logger.info("Disconnected from PostgreSQL databases")
            
        except Exception as e:
            logger.error(f"Error during PostgreSQL disconnect: {e}")
    
    async def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to both source and destination databases.
        
        Returns:
            Dictionary with 'source' and 'destination' connectivity status
        """
        source_ok = await self.connect_source()
        dest_ok = await self.connect_destination()
        
        return {
            'source': source_ok,
            'destination': dest_ok
        }
    
    async def get_schema_info(self, config: DatabaseConfigUnion) -> Dict[str, Any]:
        """Get schema information from a PostgreSQL database.
        
        Args:
            config: Database configuration
            
        Returns:
            Dictionary containing schema information
        """
        try:
            conn_string = self._create_connection_string(config)
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            schema_info = {
                'database': config.database,
                'tables': [],
                'views': [],
                'sequences': [],
                'functions': [],
                'indexes': []
            }
            
            # Get tables
            cursor.execute("""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            tables_info = cursor.fetchall()
            
            for table_info in tables_info:
                table_name = table_info['table_name']
                table_type = table_info['table_type']
                
                if table_type == 'BASE TABLE':
                    # Get column information
                    cursor.execute("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s
                        ORDER BY ordinal_position
                    """, (table_name,))
                    columns = cursor.fetchall()
                    
                    # Get row count
                    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    row_count = cursor.fetchone()[0]
                    
                    # Get table size
                    cursor.execute("SELECT pg_total_relation_size(%s)", (table_name,))
                    table_size = cursor.fetchone()[0] or 0
                    
                    schema_info['tables'].append({
                        'name': table_name,
                        'columns': [dict(col) for col in columns],
                        'rows': row_count,
                        'size_bytes': table_size
                    })
                    
                elif table_type == 'VIEW':
                    schema_info['views'].append(table_name)
            
            # Get sequences
            cursor.execute("""
                SELECT sequence_name 
                FROM information_schema.sequences 
                WHERE sequence_schema = 'public'
            """)
            sequences = cursor.fetchall()
            schema_info['sequences'] = [seq['sequence_name'] for seq in sequences]
            
            # Get functions
            cursor.execute("""
                SELECT routine_name, routine_type
                FROM information_schema.routines
                WHERE routine_schema = 'public'
            """)
            functions = cursor.fetchall()
            schema_info['functions'] = [
                {'name': func['routine_name'], 'type': func['routine_type']} 
                for func in functions
            ]
            
            # Get indexes
            cursor.execute("""
                SELECT indexname, tablename
                FROM pg_indexes
                WHERE schemaname = 'public'
            """)
            indexes = cursor.fetchall()
            schema_info['indexes'] = [dict(idx) for idx in indexes]
            
            cursor.close()
            conn.close()
            
            return schema_info
            
        except PostgreSQLError as e:
            logger.error(f"Failed to get PostgreSQL schema info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting PostgreSQL schema info: {e}")
            return {}
    
    async def validate_compatibility(self) -> List[str]:
        """Validate compatibility between source and destination databases.
        
        Returns:
            List of compatibility issues (empty if compatible)
        """
        issues = []
        
        try:
            source_info = await self.get_schema_info(self.source_config)
            dest_info = await self.get_schema_info(self.destination_config)
            
            if not source_info:
                issues.append("Cannot retrieve source database schema information")
                return issues
            
            if not dest_info:
                issues.append("Cannot retrieve destination database schema information")
                return issues
            
            # Check if destination database exists and is accessible
            if not dest_info.get('database'):
                issues.append("Destination database is not accessible")
            
            # Check for table name conflicts
            source_tables = {table['name'] for table in source_info.get('tables', [])}
            dest_tables = {table['name'] for table in dest_info.get('tables', [])}
            
            conflicts = source_tables.intersection(dest_tables)
            if conflicts:
                issues.append(f"Table name conflicts detected: {', '.join(conflicts)}")
            
            # Check PostgreSQL version compatibility
            try:
                source_conn = psycopg2.connect(self._create_connection_string(self.source_config))
                dest_conn = psycopg2.connect(self._create_connection_string(self.destination_config))
                
                source_cursor = source_conn.cursor()
                dest_cursor = dest_conn.cursor()
                
                source_cursor.execute("SELECT version()")
                source_version = source_cursor.fetchone()[0]
                
                dest_cursor.execute("SELECT version()")
                dest_version = dest_cursor.fetchone()[0]
                
                # Extract major version numbers
                source_major = int(source_version.split()[1].split('.')[0])
                dest_major = int(dest_version.split()[1].split('.')[0])
                
                if dest_major < source_major:
                    issues.append(f"Destination PostgreSQL version ({dest_major}) is older than source ({source_major})")
                
                source_conn.close()
                dest_conn.close()
                
            except Exception as e:
                issues.append(f"Could not verify PostgreSQL version compatibility: {e}")
            
        except Exception as e:
            issues.append(f"Error during compatibility validation: {str(e)}")
        
        return issues
    
    async def estimate_migration_size(self) -> Dict[str, Any]:
        """Estimate the size and complexity of the migration.
        
        Returns:
            Dictionary with size estimates
        """
        try:
            schema_info = await self.get_schema_info(self.source_config)
            
            total_tables = len(schema_info.get('tables', []))
            total_rows = sum(table.get('rows', 0) for table in schema_info.get('tables', []))
            total_data_size = sum(table.get('size_bytes', 0) for table in schema_info.get('tables', []))
            
            return {
                'total_tables': total_tables,
                'total_rows': total_rows,
                'total_data_size_bytes': total_data_size,
                'total_data_size_mb': round(total_data_size / (1024 * 1024), 2),
                'views': len(schema_info.get('views', [])),
                'sequences': len(schema_info.get('sequences', [])),
                'functions': len(schema_info.get('functions', [])),
                'indexes': len(schema_info.get('indexes', [])),
                'estimated_duration_minutes': max(1, total_rows // 8000)  # Rough estimate
            }
            
        except Exception as e:
            logger.error(f"Error estimating migration size: {e}")
            return {
                'total_tables': 0,
                'total_rows': 0,
                'total_data_size_bytes': 0,
                'error': str(e)
            }
    
    async def migrate_schema(self) -> MigrationResult:
        """Migrate database schema from source to destination.
        
        Returns:
            Migration result with status and details
        """
        start_time = datetime.utcnow()
        result = MigrationResult(
            status=MigrationStatus.RUNNING,
            start_time=start_time
        )
        
        try:
            if not self._source_pool or not self._destination_pool:
                result.status = MigrationStatus.FAILED
                result.errors.append("Database connections not established")
                return result
            
            source_conn = self._source_pool.getconn()
            dest_conn = self._destination_pool.getconn()
            
            try:
                source_cursor = source_conn.cursor()
                dest_cursor = dest_conn.cursor()
                
                # Get all tables
                source_cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in source_cursor.fetchall()]
                
                migrated_tables = 0
                
                for table_name in tables:
                    try:
                        # Get table definition using pg_dump-like approach
                        source_cursor.execute("""
                            SELECT column_name, data_type, character_maximum_length, 
                                   is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = %s
                            ORDER BY ordinal_position
                        """, (table_name,))
                        columns = source_cursor.fetchall()
                        
                        # Build CREATE TABLE statement
                        column_defs = []
                        for col in columns:
                            col_name, data_type, max_length, nullable, default = col
                            
                            col_def = f'"{col_name}" {data_type}'
                            if max_length and data_type in ('character varying', 'character'):
                                col_def += f'({max_length})'
                            
                            if nullable == 'NO':
                                col_def += ' NOT NULL'
                            
                            if default:
                                col_def += f' DEFAULT {default}'
                            
                            column_defs.append(col_def)
                        
                        create_statement = f'CREATE TABLE "{table_name}" (\n  ' + ',\n  '.join(column_defs) + '\n)'
                        
                        # Execute CREATE TABLE on destination
                        dest_cursor.execute(create_statement)
                        dest_conn.commit()
                        migrated_tables += 1
                        
                    except PostgreSQLError as e:
                        result.errors.append(f"Failed to migrate table {table_name}: {e}")
                        logger.error(f"Failed to migrate table {table_name}: {e}")
                        dest_conn.rollback()
                
                result.tables_migrated = migrated_tables
                result.status = MigrationStatus.COMPLETED
                
            finally:
                self._source_pool.putconn(source_conn)
                self._destination_pool.putconn(dest_conn)
                
        except Exception as e:
            result.status = MigrationStatus.FAILED
            result.errors.append(f"Schema migration failed: {str(e)}")
            logger.error(f"Schema migration failed: {e}")
        
        result.end_time = datetime.utcnow()
        return result
    
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
        if not self._source_pool or not self._destination_pool:
            raise RuntimeError("Database connections not established")
        
        source_conn = self._source_pool.getconn()
        dest_conn = self._destination_pool.getconn()
        
        try:
            source_cursor = source_conn.cursor()
            dest_cursor = dest_conn.cursor()
            
            # Get tables to migrate
            if tables is None:
                source_cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in source_cursor.fetchall()]
            
            total_tables = len(tables)
            tables_completed = 0
            total_records = 0
            
            progress = MigrationProgress(
                total_tables=total_tables,
                tables_completed=0,
                records_processed=0,
                current_operation="Starting data migration"
            )
            yield progress
            
            for table_name in tables:
                progress.current_table = table_name
                progress.current_operation = f"Migrating table {table_name}"
                yield progress
                
                try:
                    # Get total row count for this table
                    source_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    table_row_count = source_cursor.fetchone()[0]
                    
                    if table_row_count == 0:
                        tables_completed += 1
                        progress.tables_completed = tables_completed
                        continue
                    
                    # Get column names
                    source_cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s
                        ORDER BY ordinal_position
                    """, (table_name,))
                    columns = [row[0] for row in source_cursor.fetchall()]
                    column_list = ', '.join(f'"{col}"' for col in columns)
                    placeholders = ', '.join(['%s'] * len(columns))
                    
                    # Migrate data in batches
                    offset = 0
                    table_records = 0
                    
                    while offset < table_row_count:
                        # Fetch batch from source
                        source_cursor.execute(
                            f'SELECT {column_list} FROM "{table_name}" LIMIT %s OFFSET %s',
                            (batch_size, offset)
                        )
                        rows = source_cursor.fetchall()
                        
                        if not rows:
                            break
                        
                        # Insert batch into destination
                        insert_query = f'INSERT INTO "{table_name}" ({column_list}) VALUES ({placeholders})'
                        dest_cursor.executemany(insert_query, rows)
                        dest_conn.commit()
                        
                        table_records += len(rows)
                        total_records += len(rows)
                        offset += batch_size
                        
                        progress.records_processed = total_records
                        progress.current_operation = f"Migrating table {table_name} ({table_records}/{table_row_count} records)"
                        yield progress
                        
                        # Small delay to prevent overwhelming the database
                        await asyncio.sleep(0.01)
                    
                    tables_completed += 1
                    progress.tables_completed = tables_completed
                    progress.current_operation = f"Completed table {table_name} ({table_records} records)"
                    yield progress
                    
                except PostgreSQLError as e:
                    logger.error(f"Error migrating table {table_name}: {e}")
                    progress.current_operation = f"Error migrating table {table_name}: {e}"
                    dest_conn.rollback()
                    yield progress
                    continue
            
            progress.current_operation = "Data migration completed"
            yield progress
            
        finally:
            self._source_pool.putconn(source_conn)
            self._destination_pool.putconn(dest_conn)
    
    async def verify_migration(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Verify the migration by comparing source and destination data.
        
        Args:
            tables: List of tables to verify (None for all tables)
            
        Returns:
            Dictionary with verification results
        """
        if not self._source_pool or not self._destination_pool:
            return {'success': False, 'error': 'Database connections not established'}
        
        verification_results = {
            'success': True,
            'tables_verified': 0,
            'tables_matched': 0,
            'mismatches': [],
            'errors': []
        }
        
        source_conn = self._source_pool.getconn()
        dest_conn = self._destination_pool.getconn()
        
        try:
            source_cursor = source_conn.cursor()
            dest_cursor = dest_conn.cursor()
            
            # Get tables to verify
            if tables is None:
                source_cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in source_cursor.fetchall()]
            
            for table_name in tables:
                try:
                    # Compare row counts
                    source_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    source_count = source_cursor.fetchone()[0]
                    
                    dest_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    dest_count = dest_cursor.fetchone()[0]
                    
                    verification_results['tables_verified'] += 1
                    
                    if source_count == dest_count:
                        verification_results['tables_matched'] += 1
                    else:
                        verification_results['mismatches'].append({
                            'table': table_name,
                            'source_count': source_count,
                            'destination_count': dest_count
                        })
                        verification_results['success'] = False
                    
                except PostgreSQLError as e:
                    verification_results['errors'].append(f"Error verifying table {table_name}: {e}")
                    verification_results['success'] = False
            
        except Exception as e:
            verification_results['success'] = False
            verification_results['errors'].append(f"Verification failed: {str(e)}")
        
        finally:
            self._source_pool.putconn(source_conn)
            self._destination_pool.putconn(dest_conn)
        
        return verification_results
    
    async def get_supported_methods(self) -> List[MigrationMethod]:
        """Get list of migration methods supported by this migrator.
        
        Returns:
            List of supported migration methods
        """
        return [
            MigrationMethod.DUMP_RESTORE,
            MigrationMethod.DIRECT_TRANSFER,
            MigrationMethod.STREAMING,
            MigrationMethod.BULK_COPY
        ]