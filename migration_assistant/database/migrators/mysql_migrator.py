"""MySQL database migrator implementation using mysql-connector-python."""

import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector.pooling import MySQLConnectionPool

from ..base import DatabaseMigrator, MigrationResult, MigrationProgress, MigrationStatus, MigrationMethod
from ..config import MySQLConfig, DatabaseConfigUnion


logger = logging.getLogger(__name__)


class MySQLMigrator(DatabaseMigrator):
    """MySQL database migrator using mysql-connector-python."""
    
    def __init__(self, source_config: DatabaseConfigUnion, destination_config: DatabaseConfigUnion):
        """Initialize MySQL migrator.
        
        Args:
            source_config: Source MySQL database configuration
            destination_config: Destination MySQL database configuration
        """
        super().__init__(source_config, destination_config)
        self._source_pool: Optional[MySQLConnectionPool] = None
        self._destination_pool: Optional[MySQLConnectionPool] = None
        
    def _create_connection_config(self, config: MySQLConfig) -> Dict[str, Any]:
        """Create connection configuration dictionary.
        
        Args:
            config: MySQL configuration
            
        Returns:
            Connection configuration dictionary
        """
        conn_config = {
            'host': config.host,
            'port': config.port,
            'user': config.username,
            'password': config.password,
            'database': config.database,
            'charset': config.charset,
            'autocommit': config.autocommit,
            'connection_timeout': config.connection_timeout,
            'use_unicode': True,
            'sql_mode': 'TRADITIONAL',
        }
        
        if config.ssl_enabled:
            conn_config['ssl_disabled'] = False
        
        # Add extra parameters
        conn_config.update(config.extra_params)
        
        return conn_config
    
    async def connect_source(self) -> bool:
        """Connect to the source MySQL database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            config = self._create_connection_config(self.source_config)
            self._source_pool = MySQLConnectionPool(
                pool_name="source_pool",
                pool_size=5,
                pool_reset_session=True,
                **config
            )
            
            # Test connection
            conn = self._source_pool.get_connection()
            conn.ping(reconnect=True)
            conn.close()
            
            logger.info(f"Connected to source MySQL database: {self.source_config.host}:{self.source_config.port}")
            return True
            
        except MySQLError as e:
            logger.error(f"Failed to connect to source MySQL database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to source MySQL: {e}")
            return False
    
    async def connect_destination(self) -> bool:
        """Connect to the destination MySQL database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            config = self._create_connection_config(self.destination_config)
            self._destination_pool = MySQLConnectionPool(
                pool_name="destination_pool",
                pool_size=5,
                pool_reset_session=True,
                **config
            )
            
            # Test connection
            conn = self._destination_pool.get_connection()
            conn.ping(reconnect=True)
            conn.close()
            
            logger.info(f"Connected to destination MySQL database: {self.destination_config.host}:{self.destination_config.port}")
            return True
            
        except MySQLError as e:
            logger.error(f"Failed to connect to destination MySQL database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to destination MySQL: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from both source and destination databases."""
        try:
            if self._source_pool:
                # Close all connections in the pool
                for _ in range(self._source_pool.pool_size):
                    try:
                        conn = self._source_pool.get_connection()
                        conn.close()
                    except:
                        pass
                self._source_pool = None
                
            if self._destination_pool:
                # Close all connections in the pool
                for _ in range(self._destination_pool.pool_size):
                    try:
                        conn = self._destination_pool.get_connection()
                        conn.close()
                    except:
                        pass
                self._destination_pool = None
                
            logger.info("Disconnected from MySQL databases")
            
        except Exception as e:
            logger.error(f"Error during MySQL disconnect: {e}")
    
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
        """Get schema information from a MySQL database.
        
        Args:
            config: Database configuration
            
        Returns:
            Dictionary containing schema information
        """
        try:
            conn_config = self._create_connection_config(config)
            conn = mysql.connector.connect(**conn_config)
            cursor = conn.cursor(dictionary=True)
            
            schema_info = {
                'database': config.database,
                'tables': [],
                'views': [],
                'procedures': [],
                'functions': [],
                'triggers': []
            }
            
            # Get tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = list(table.values())[0]
                
                # Get table structure
                cursor.execute(f"DESCRIBE `{table_name}`")
                columns = cursor.fetchall()
                
                # Get table info
                cursor.execute(f"SHOW TABLE STATUS LIKE '{table_name}'")
                table_info = cursor.fetchone()
                
                schema_info['tables'].append({
                    'name': table_name,
                    'columns': columns,
                    'engine': table_info.get('Engine'),
                    'rows': table_info.get('Rows', 0),
                    'data_length': table_info.get('Data_length', 0),
                    'collation': table_info.get('Collation')
                })
            
            # Get views
            cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
            views = cursor.fetchall()
            schema_info['views'] = [list(view.values())[0] for view in views]
            
            # Get procedures
            cursor.execute("SHOW PROCEDURE STATUS WHERE Db = %s", (config.database,))
            procedures = cursor.fetchall()
            schema_info['procedures'] = [proc['Name'] for proc in procedures]
            
            # Get functions
            cursor.execute("SHOW FUNCTION STATUS WHERE Db = %s", (config.database,))
            functions = cursor.fetchall()
            schema_info['functions'] = [func['Name'] for func in functions]
            
            cursor.close()
            conn.close()
            
            return schema_info
            
        except MySQLError as e:
            logger.error(f"Failed to get MySQL schema info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting MySQL schema info: {e}")
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
            
            # Check for charset/collation compatibility
            source_charset = getattr(self.source_config, 'charset', 'utf8mb4')
            dest_charset = getattr(self.destination_config, 'charset', 'utf8mb4')
            
            if source_charset != dest_charset:
                issues.append(f"Charset mismatch: source={source_charset}, destination={dest_charset}")
            
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
            total_data_size = sum(table.get('data_length', 0) for table in schema_info.get('tables', []))
            
            return {
                'total_tables': total_tables,
                'total_rows': total_rows,
                'total_data_size_bytes': total_data_size,
                'total_data_size_mb': round(total_data_size / (1024 * 1024), 2),
                'views': len(schema_info.get('views', [])),
                'procedures': len(schema_info.get('procedures', [])),
                'functions': len(schema_info.get('functions', [])),
                'estimated_duration_minutes': max(1, total_rows // 10000)  # Rough estimate
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
            
            source_conn = self._source_pool.get_connection()
            dest_conn = self._destination_pool.get_connection()
            
            try:
                source_cursor = source_conn.cursor()
                dest_cursor = dest_conn.cursor()
                
                # Get all tables
                source_cursor.execute("SHOW TABLES")
                tables = [row[0] for row in source_cursor.fetchall()]
                
                migrated_tables = 0
                
                for table_name in tables:
                    try:
                        # Get CREATE TABLE statement
                        source_cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                        create_statement = source_cursor.fetchone()[1]
                        
                        # Execute CREATE TABLE on destination
                        dest_cursor.execute(create_statement)
                        migrated_tables += 1
                        
                    except MySQLError as e:
                        result.errors.append(f"Failed to migrate table {table_name}: {e}")
                        logger.error(f"Failed to migrate table {table_name}: {e}")
                
                dest_conn.commit()
                result.tables_migrated = migrated_tables
                result.status = MigrationStatus.COMPLETED
                
            finally:
                source_conn.close()
                dest_conn.close()
                
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
        
        source_conn = self._source_pool.get_connection()
        dest_conn = self._destination_pool.get_connection()
        
        try:
            source_cursor = source_conn.cursor()
            dest_cursor = dest_conn.cursor()
            
            # Get tables to migrate
            if tables is None:
                source_cursor.execute("SHOW TABLES")
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
                    source_cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                    table_row_count = source_cursor.fetchone()[0]
                    
                    if table_row_count == 0:
                        tables_completed += 1
                        progress.tables_completed = tables_completed
                        continue
                    
                    # Get column names
                    source_cursor.execute(f"DESCRIBE `{table_name}`")
                    columns = [row[0] for row in source_cursor.fetchall()]
                    column_list = ', '.join(f'`{col}`' for col in columns)
                    placeholders = ', '.join(['%s'] * len(columns))
                    
                    # Migrate data in batches
                    offset = 0
                    table_records = 0
                    
                    while offset < table_row_count:
                        # Fetch batch from source
                        source_cursor.execute(
                            f"SELECT {column_list} FROM `{table_name}` LIMIT %s OFFSET %s",
                            (batch_size, offset)
                        )
                        rows = source_cursor.fetchall()
                        
                        if not rows:
                            break
                        
                        # Insert batch into destination
                        insert_query = f"INSERT INTO `{table_name}` ({column_list}) VALUES ({placeholders})"
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
                    
                except MySQLError as e:
                    logger.error(f"Error migrating table {table_name}: {e}")
                    progress.current_operation = f"Error migrating table {table_name}: {e}"
                    yield progress
                    continue
            
            progress.current_operation = "Data migration completed"
            yield progress
            
        finally:
            source_conn.close()
            dest_conn.close()
    
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
        
        source_conn = self._source_pool.get_connection()
        dest_conn = self._destination_pool.get_connection()
        
        try:
            source_cursor = source_conn.cursor()
            dest_cursor = dest_conn.cursor()
            
            # Get tables to verify
            if tables is None:
                source_cursor.execute("SHOW TABLES")
                tables = [row[0] for row in source_cursor.fetchall()]
            
            for table_name in tables:
                try:
                    # Compare row counts
                    source_cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                    source_count = source_cursor.fetchone()[0]
                    
                    dest_cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
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
                    
                except MySQLError as e:
                    verification_results['errors'].append(f"Error verifying table {table_name}: {e}")
                    verification_results['success'] = False
            
        except Exception as e:
            verification_results['success'] = False
            verification_results['errors'].append(f"Verification failed: {str(e)}")
        
        finally:
            source_conn.close()
            dest_conn.close()
        
        return verification_results
    
    async def get_supported_methods(self) -> List[MigrationMethod]:
        """Get list of migration methods supported by this migrator.
        
        Returns:
            List of supported migration methods
        """
        return [
            MigrationMethod.DUMP_RESTORE,
            MigrationMethod.DIRECT_TRANSFER,
            MigrationMethod.BULK_COPY
        ]