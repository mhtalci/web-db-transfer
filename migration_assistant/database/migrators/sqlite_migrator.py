"""SQLite database migrator implementation using built-in sqlite3."""

import asyncio
import logging
import sqlite3
import shutil
import os
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
from pathlib import Path

from ..base import DatabaseMigrator, MigrationResult, MigrationProgress, MigrationStatus, MigrationMethod
from ..config import SQLiteConfig, DatabaseConfigUnion


logger = logging.getLogger(__name__)


class SQLiteMigrator(DatabaseMigrator):
    """SQLite database migrator using built-in sqlite3."""
    
    def __init__(self, source_config: DatabaseConfigUnion, destination_config: DatabaseConfigUnion):
        """Initialize SQLite migrator.
        
        Args:
            source_config: Source SQLite database configuration
            destination_config: Destination SQLite database configuration
        """
        super().__init__(source_config, destination_config)
        self._source_connection: Optional[sqlite3.Connection] = None
        self._destination_connection: Optional[sqlite3.Connection] = None
        
    def _create_connection(self, config: SQLiteConfig) -> sqlite3.Connection:
        """Create SQLite connection.
        
        Args:
            config: SQLite configuration
            
        Returns:
            SQLite connection
        """
        # Ensure the directory exists
        db_path = Path(config.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(
            config.database_path,
            timeout=config.timeout,
            check_same_thread=config.check_same_thread
        )
        
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Set row factory for dictionary-like access
        conn.row_factory = sqlite3.Row
        
        return conn
    
    async def connect_source(self) -> bool:
        """Connect to the source SQLite database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Check if source database file exists
            if not os.path.exists(self.source_config.database_path):
                logger.error(f"Source SQLite database file does not exist: {self.source_config.database_path}")
                return False
            
            self._source_connection = self._create_connection(self.source_config)
            
            # Test connection
            cursor = self._source_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            logger.info(f"Connected to source SQLite database: {self.source_config.database_path}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to source SQLite database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to source SQLite: {e}")
            return False
    
    async def connect_destination(self) -> bool:
        """Connect to the destination SQLite database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._destination_connection = self._create_connection(self.destination_config)
            
            # Test connection
            cursor = self._destination_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            logger.info(f"Connected to destination SQLite database: {self.destination_config.database_path}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to destination SQLite database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to destination SQLite: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from both source and destination databases."""
        try:
            if self._source_connection:
                self._source_connection.close()
                self._source_connection = None
                
            if self._destination_connection:
                self._destination_connection.close()
                self._destination_connection = None
                
            logger.info("Disconnected from SQLite databases")
            
        except Exception as e:
            logger.error(f"Error during SQLite disconnect: {e}")
    
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
        """Get schema information from a SQLite database.
        
        Args:
            config: Database configuration
            
        Returns:
            Dictionary containing schema information
        """
        try:
            conn = self._create_connection(config)
            cursor = conn.cursor()
            
            schema_info = {
                'database': config.database_path,
                'tables': [],
                'views': [],
                'indexes': [],
                'triggers': []
            }
            
            # Get tables
            cursor.execute("""
                SELECT name, sql 
                FROM sqlite_master 
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables_info = cursor.fetchall()
            
            for table_info in tables_info:
                table_name = table_info['name']
                table_sql = table_info['sql']
                
                # Get column information
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                row_count = cursor.fetchone()[0]
                
                # Get table size (approximate)
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                db_size = cursor.fetchone()[0]
                
                schema_info['tables'].append({
                    'name': table_name,
                    'sql': table_sql,
                    'columns': [dict(col) for col in columns],
                    'rows': row_count,
                    'estimated_size_bytes': db_size // len(tables_info) if tables_info else 0
                })
            
            # Get views
            cursor.execute("""
                SELECT name, sql 
                FROM sqlite_master 
                WHERE type = 'view'
                ORDER BY name
            """)
            views = cursor.fetchall()
            schema_info['views'] = [{'name': view['name'], 'sql': view['sql']} for view in views]
            
            # Get indexes
            cursor.execute("""
                SELECT name, sql, tbl_name
                FROM sqlite_master 
                WHERE type = 'index' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            indexes = cursor.fetchall()
            schema_info['indexes'] = [dict(idx) for idx in indexes]
            
            # Get triggers
            cursor.execute("""
                SELECT name, sql, tbl_name
                FROM sqlite_master 
                WHERE type = 'trigger'
                ORDER BY name
            """)
            triggers = cursor.fetchall()
            schema_info['triggers'] = [dict(trigger) for trigger in triggers]
            
            cursor.close()
            conn.close()
            
            return schema_info
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get SQLite schema info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting SQLite schema info: {e}")
            return {}
    
    async def validate_compatibility(self) -> List[str]:
        """Validate compatibility between source and destination databases.
        
        Returns:
            List of compatibility issues (empty if compatible)
        """
        issues = []
        
        try:
            source_info = await self.get_schema_info(self.source_config)
            
            if not source_info:
                issues.append("Cannot retrieve source database schema information")
                return issues
            
            # Check if source database file exists
            if not os.path.exists(self.source_config.database_path):
                issues.append(f"Source database file does not exist: {self.source_config.database_path}")
            
            # Check if destination directory is writable
            dest_path = Path(self.destination_config.database_path)
            dest_dir = dest_path.parent
            
            if not dest_dir.exists():
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    issues.append(f"Cannot create destination directory: {e}")
            
            if not os.access(dest_dir, os.W_OK):
                issues.append(f"Destination directory is not writable: {dest_dir}")
            
            # Check if destination file already exists
            if os.path.exists(self.destination_config.database_path):
                issues.append(f"Destination database file already exists: {self.destination_config.database_path}")
            
            # Check available disk space
            try:
                source_size = os.path.getsize(self.source_config.database_path)
                dest_stat = shutil.disk_usage(dest_dir)
                available_space = dest_stat.free
                
                if source_size > available_space:
                    issues.append(f"Insufficient disk space. Need {source_size} bytes, have {available_space} bytes")
            except Exception as e:
                issues.append(f"Cannot check disk space: {e}")
            
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
            
            # Get actual file size
            file_size = 0
            if os.path.exists(self.source_config.database_path):
                file_size = os.path.getsize(self.source_config.database_path)
            
            return {
                'total_tables': total_tables,
                'total_rows': total_rows,
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'views': len(schema_info.get('views', [])),
                'indexes': len(schema_info.get('indexes', [])),
                'triggers': len(schema_info.get('triggers', [])),
                'estimated_duration_minutes': max(1, file_size // (1024 * 1024 * 10))  # ~10MB per minute
            }
            
        except Exception as e:
            logger.error(f"Error estimating migration size: {e}")
            return {
                'total_tables': 0,
                'total_rows': 0,
                'file_size_bytes': 0,
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
            if not self._source_connection or not self._destination_connection:
                result.status = MigrationStatus.FAILED
                result.errors.append("Database connections not established")
                return result
            
            source_cursor = self._source_connection.cursor()
            dest_cursor = self._destination_connection.cursor()
            
            # Get all schema objects (tables, views, indexes, triggers)
            source_cursor.execute("""
                SELECT type, name, sql 
                FROM sqlite_master 
                WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
                ORDER BY 
                    CASE type 
                        WHEN 'table' THEN 1 
                        WHEN 'view' THEN 2 
                        WHEN 'index' THEN 3 
                        WHEN 'trigger' THEN 4 
                        ELSE 5 
                    END, name
            """)
            schema_objects = source_cursor.fetchall()
            
            migrated_objects = 0
            
            for obj in schema_objects:
                obj_type, obj_name, obj_sql = obj
                
                try:
                    # Execute CREATE statement on destination
                    dest_cursor.execute(obj_sql)
                    migrated_objects += 1
                    
                    if obj_type == 'table':
                        result.tables_migrated += 1
                    
                except sqlite3.Error as e:
                    result.errors.append(f"Failed to migrate {obj_type} {obj_name}: {e}")
                    logger.error(f"Failed to migrate {obj_type} {obj_name}: {e}")
            
            self._destination_connection.commit()
            result.status = MigrationStatus.COMPLETED
            result.metadata['migrated_objects'] = migrated_objects
            
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
        if not self._source_connection or not self._destination_connection:
            raise RuntimeError("Database connections not established")
        
        # For SQLite, we can use a more efficient approach for full database migration
        if method == MigrationMethod.DUMP_RESTORE and tables is None:
            async for progress in self._migrate_full_database():
                yield progress
            return
        
        source_cursor = self._source_connection.cursor()
        dest_cursor = self._destination_connection.cursor()
        
        try:
            # Get tables to migrate
            if tables is None:
                source_cursor.execute("""
                    SELECT name 
                    FROM sqlite_master 
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
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
                    source_cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                    table_row_count = source_cursor.fetchone()[0]
                    
                    if table_row_count == 0:
                        tables_completed += 1
                        progress.tables_completed = tables_completed
                        continue
                    
                    # Get column names
                    source_cursor.execute(f"PRAGMA table_info({table_name})")
                    columns_info = source_cursor.fetchall()
                    columns = [col['name'] for col in columns_info]
                    column_list = ', '.join(f'`{col}`' for col in columns)
                    placeholders = ', '.join(['?'] * len(columns))
                    
                    # Migrate data in batches
                    offset = 0
                    table_records = 0
                    
                    while offset < table_row_count:
                        # Fetch batch from source
                        source_cursor.execute(
                            f"SELECT {column_list} FROM `{table_name}` LIMIT ? OFFSET ?",
                            (batch_size, offset)
                        )
                        rows = source_cursor.fetchall()
                        
                        if not rows:
                            break
                        
                        # Convert Row objects to tuples
                        row_data = [tuple(row) for row in rows]
                        
                        # Insert batch into destination
                        insert_query = f"INSERT INTO `{table_name}` ({column_list}) VALUES ({placeholders})"
                        dest_cursor.executemany(insert_query, row_data)
                        self._destination_connection.commit()
                        
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
                    
                except sqlite3.Error as e:
                    logger.error(f"Error migrating table {table_name}: {e}")
                    progress.current_operation = f"Error migrating table {table_name}: {e}"
                    yield progress
                    continue
            
            progress.current_operation = "Data migration completed"
            yield progress
            
        finally:
            source_cursor.close()
            dest_cursor.close()
    
    async def _migrate_full_database(self) -> AsyncGenerator[MigrationProgress, None]:
        """Migrate entire SQLite database using file copy (most efficient method).
        
        Yields:
            MigrationProgress objects with current progress
        """
        progress = MigrationProgress(
            total_tables=1,
            tables_completed=0,
            records_processed=0,
            current_operation="Starting full database migration"
        )
        yield progress
        
        try:
            # Close connections to allow file copy
            if self._source_connection:
                self._source_connection.close()
                self._source_connection = None
            
            if self._destination_connection:
                self._destination_connection.close()
                self._destination_connection = None
            
            progress.current_operation = "Copying database file"
            yield progress
            
            # Copy the entire database file
            shutil.copy2(self.source_config.database_path, self.destination_config.database_path)
            
            progress.tables_completed = 1
            progress.current_operation = "Database file copied successfully"
            yield progress
            
            # Reconnect to verify
            await self.connect_source()
            await self.connect_destination()
            
            progress.current_operation = "Full database migration completed"
            yield progress
            
        except Exception as e:
            progress.current_operation = f"Error during full database migration: {e}"
            yield progress
            raise
    
    async def verify_migration(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Verify the migration by comparing source and destination data.
        
        Args:
            tables: List of tables to verify (None for all tables)
            
        Returns:
            Dictionary with verification results
        """
        if not self._source_connection or not self._destination_connection:
            return {'success': False, 'error': 'Database connections not established'}
        
        verification_results = {
            'success': True,
            'tables_verified': 0,
            'tables_matched': 0,
            'mismatches': [],
            'errors': []
        }
        
        source_cursor = self._source_connection.cursor()
        dest_cursor = self._destination_connection.cursor()
        
        try:
            # Get tables to verify
            if tables is None:
                source_cursor.execute("""
                    SELECT name 
                    FROM sqlite_master 
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """)
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
                    
                except sqlite3.Error as e:
                    verification_results['errors'].append(f"Error verifying table {table_name}: {e}")
                    verification_results['success'] = False
            
            # Additional verification: compare database file sizes if full migration was used
            try:
                source_size = os.path.getsize(self.source_config.database_path)
                dest_size = os.path.getsize(self.destination_config.database_path)
                
                verification_results['source_file_size'] = source_size
                verification_results['destination_file_size'] = dest_size
                verification_results['file_sizes_match'] = source_size == dest_size
                
            except Exception as e:
                verification_results['errors'].append(f"Error comparing file sizes: {e}")
            
        except Exception as e:
            verification_results['success'] = False
            verification_results['errors'].append(f"Verification failed: {str(e)}")
        
        finally:
            source_cursor.close()
            dest_cursor.close()
        
        return verification_results
    
    async def get_supported_methods(self) -> List[MigrationMethod]:
        """Get list of migration methods supported by this migrator.
        
        Returns:
            List of supported migration methods
        """
        return [
            MigrationMethod.DUMP_RESTORE,  # File copy for full database
            MigrationMethod.DIRECT_TRANSFER,  # Table-by-table migration
            MigrationMethod.BULK_COPY
        ]