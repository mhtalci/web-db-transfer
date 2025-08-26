"""Redis database migrator implementation using redis-py."""

import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
import json
import pickle

from ..base import DatabaseMigrator, MigrationResult, MigrationProgress, MigrationStatus, MigrationMethod
from ..config import RedisConfig, DatabaseConfigUnion


logger = logging.getLogger(__name__)


class RedisMigrator(DatabaseMigrator):
    """Redis database migrator using redis-py."""
    
    def __init__(self, source_config: DatabaseConfigUnion, destination_config: DatabaseConfigUnion):
        """Initialize Redis migrator.
        
        Args:
            source_config: Source Redis database configuration
            destination_config: Destination Redis database configuration
        """
        super().__init__(source_config, destination_config)
        self._source_client: Optional[redis.Redis] = None
        self._destination_client: Optional[redis.Redis] = None
        
    def _create_client_options(self, config: RedisConfig) -> Dict[str, Any]:
        """Create Redis client options.
        
        Args:
            config: Redis configuration
            
        Returns:
            Client options dictionary
        """
        options = {
            'host': config.host,
            'port': config.port,
            'db': config.db,
            'decode_responses': config.decode_responses,
            'socket_timeout': config.connection_timeout,
            'socket_connect_timeout': config.connection_timeout,
            'health_check_interval': 30,
        }
        
        if config.username:
            options['username'] = config.username
        if config.password:
            options['password'] = config.password
        
        # Connection pool settings
        options['max_connections'] = config.max_connections
        
        # Add extra parameters
        options.update(config.extra_params)
        
        return options
    
    async def connect_source(self) -> bool:
        """Connect to the source Redis database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            options = self._create_client_options(self.source_config)
            self._source_client = redis.Redis(**options)
            
            # Test connection
            self._source_client.ping()
            
            logger.info(f"Connected to source Redis database: {self.source_config.host}:{self.source_config.port}/{self.source_config.db}")
            return True
            
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to source Redis database: {e}")
            return False
        except RedisError as e:
            logger.error(f"Redis error connecting to source: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to source Redis: {e}")
            return False
    
    async def connect_destination(self) -> bool:
        """Connect to the destination Redis database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            options = self._create_client_options(self.destination_config)
            self._destination_client = redis.Redis(**options)
            
            # Test connection
            self._destination_client.ping()
            
            logger.info(f"Connected to destination Redis database: {self.destination_config.host}:{self.destination_config.port}/{self.destination_config.db}")
            return True
            
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to destination Redis database: {e}")
            return False
        except RedisError as e:
            logger.error(f"Redis error connecting to destination: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to destination Redis: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from both source and destination databases."""
        try:
            if self._source_client:
                self._source_client.close()
                self._source_client = None
                
            if self._destination_client:
                self._destination_client.close()
                self._destination_client = None
                
            logger.info("Disconnected from Redis databases")
            
        except Exception as e:
            logger.error(f"Error during Redis disconnect: {e}")
    
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
        """Get schema information from a Redis database.
        
        Args:
            config: Database configuration
            
        Returns:
            Dictionary containing schema information
        """
        try:
            options = self._create_client_options(config)
            client = redis.Redis(**options)
            
            schema_info = {
                'database': config.db,
                'host': config.host,
                'port': config.port,
                'keys': [],
                'key_types': {},
                'memory_usage': {},
                'stats': {}
            }
            
            # Get Redis info
            info = client.info()
            schema_info['stats'] = {
                'redis_version': info.get('redis_version'),
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'uptime_in_seconds': info.get('uptime_in_seconds', 0)
            }
            
            # Get database-specific info
            db_info = info.get(f'db{config.db}', {})
            if db_info:
                schema_info['stats']['keys'] = db_info.get('keys', 0)
                schema_info['stats']['expires'] = db_info.get('expires', 0)
                schema_info['stats']['avg_ttl'] = db_info.get('avg_ttl', 0)
            
            # Get all keys (be careful with large databases)
            keys = client.keys('*')
            schema_info['keys'] = [key.decode() if isinstance(key, bytes) else key for key in keys[:1000]]  # Limit to first 1000 keys
            
            if len(keys) > 1000:
                schema_info['total_keys'] = len(keys)
                schema_info['keys_truncated'] = True
            else:
                schema_info['total_keys'] = len(keys)
                schema_info['keys_truncated'] = False
            
            # Analyze key types and memory usage for a sample
            sample_keys = keys[:100]  # Sample first 100 keys
            key_types = {}
            memory_usage = {}
            
            for key in sample_keys:
                try:
                    key_str = key.decode() if isinstance(key, bytes) else key
                    key_type = client.type(key).decode() if isinstance(client.type(key), bytes) else client.type(key)
                    key_types[key_str] = key_type
                    
                    # Get memory usage if available (Redis 4.0+)
                    try:
                        memory = client.memory_usage(key)
                        if memory:
                            memory_usage[key_str] = memory
                    except (RedisError, AttributeError):
                        # memory_usage command not available
                        pass
                        
                except RedisError as e:
                    logger.warning(f"Error analyzing key {key}: {e}")
            
            schema_info['key_types'] = key_types
            schema_info['memory_usage'] = memory_usage
            
            # Get key type distribution
            type_distribution = {}
            for key_type in key_types.values():
                type_distribution[key_type] = type_distribution.get(key_type, 0) + 1
            schema_info['type_distribution'] = type_distribution
            
            client.close()
            return schema_info
            
        except RedisError as e:
            logger.error(f"Failed to get Redis schema info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting Redis schema info: {e}")
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
            
            # Check Redis version compatibility
            source_version = source_info.get('stats', {}).get('redis_version', '0.0.0')
            dest_version = dest_info.get('stats', {}).get('redis_version', '0.0.0')
            
            try:
                source_major = int(source_version.split('.')[0])
                dest_major = int(dest_version.split('.')[0])
                
                if dest_major < source_major:
                    issues.append(f"Destination Redis version ({dest_version}) is older than source ({source_version})")
            except (ValueError, IndexError):
                issues.append("Could not parse Redis version information")
            
            # Check if destination database has existing keys
            dest_keys = dest_info.get('stats', {}).get('keys', 0)
            if dest_keys > 0:
                issues.append(f"Destination database is not empty (contains {dest_keys} keys)")
            
            # Check memory availability
            source_memory = source_info.get('stats', {}).get('used_memory', 0)
            dest_memory = dest_info.get('stats', {}).get('used_memory', 0)
            
            # This is a rough check - in practice, you'd want to check available memory
            if source_memory > 0:
                issues.append(f"Source database uses {source_memory} bytes of memory. Ensure destination has sufficient memory.")
            
            # Check for specific Redis features that might not be compatible
            source_keys_count = source_info.get('total_keys', 0)
            if source_keys_count > 1000000:
                issues.append(f"Large number of keys ({source_keys_count}) may require special handling")
            
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
            
            stats = schema_info.get('stats', {})
            total_keys = schema_info.get('total_keys', 0)
            used_memory = stats.get('used_memory', 0)
            
            # Estimate based on key types
            type_distribution = schema_info.get('type_distribution', {})
            
            return {
                'total_keys': total_keys,
                'used_memory_bytes': used_memory,
                'used_memory_mb': round(used_memory / (1024 * 1024), 2),
                'type_distribution': type_distribution,
                'redis_version': stats.get('redis_version'),
                'estimated_duration_minutes': max(1, total_keys // 1000)  # Rough estimate: 1000 keys per minute
            }
            
        except Exception as e:
            logger.error(f"Error estimating migration size: {e}")
            return {
                'total_keys': 0,
                'used_memory_bytes': 0,
                'error': str(e)
            }
    
    async def migrate_schema(self) -> MigrationResult:
        """Migrate database schema from source to destination.
        
        Note: Redis doesn't have a traditional schema, so this method
        focuses on migrating configuration and database structure.
        
        Returns:
            Migration result with status and details
        """
        start_time = datetime.utcnow()
        result = MigrationResult(
            status=MigrationStatus.RUNNING,
            start_time=start_time
        )
        
        try:
            if not self._source_client or not self._destination_client:
                result.status = MigrationStatus.FAILED
                result.errors.append("Database connections not established")
                return result
            
            # Redis doesn't have a traditional schema, but we can copy some configuration
            # and ensure the destination database is ready
            
            # Check if destination is empty
            dest_keys = self._destination_client.dbsize()
            if dest_keys > 0:
                result.warnings.append(f"Destination database is not empty (contains {dest_keys} keys)")
            
            # Get source database info
            source_info = self._source_client.info()
            
            result.status = MigrationStatus.COMPLETED
            result.metadata = {
                'source_redis_version': source_info.get('redis_version'),
                'source_keys': source_info.get(f'db{self.source_config.db}', {}).get('keys', 0),
                'destination_prepared': True
            }
            
        except Exception as e:
            result.status = MigrationStatus.FAILED
            result.errors.append(f"Schema migration failed: {str(e)}")
            logger.error(f"Schema migration failed: {e}")
        
        result.end_time = datetime.utcnow()
        return result
    
    async def migrate_data(self, 
                          tables: Optional[List[str]] = None,
                          batch_size: int = 1000,
                          method: MigrationMethod = MigrationMethod.BULK_COPY) -> AsyncGenerator[MigrationProgress, None]:
        """Migrate data from source to destination with progress updates.
        
        Args:
            tables: List of key patterns to migrate (None for all keys)
            batch_size: Number of keys to process in each batch
            method: Migration method to use
            
        Yields:
            MigrationProgress objects with current progress
        """
        if not self._source_client or not self._destination_client:
            raise RuntimeError("Database connections not established")
        
        try:
            # Get keys to migrate
            if tables is None:
                # Get all keys
                all_keys = self._source_client.keys('*')
            else:
                # Get keys matching patterns
                all_keys = []
                for pattern in tables:
                    keys = self._source_client.keys(pattern)
                    all_keys.extend(keys)
            
            total_keys = len(all_keys)
            keys_processed = 0
            
            progress = MigrationProgress(
                total_tables=1,  # Redis doesn't have tables, using 1 for the database
                tables_completed=0,
                records_processed=0,
                estimated_total_records=total_keys,
                current_operation="Starting Redis data migration"
            )
            yield progress
            
            # Process keys in batches
            for i in range(0, total_keys, batch_size):
                batch_keys = all_keys[i:i + batch_size]
                
                progress.current_operation = f"Migrating keys batch {i//batch_size + 1}"
                yield progress
                
                # Use pipeline for better performance
                source_pipe = self._source_client.pipeline()
                dest_pipe = self._destination_client.pipeline()
                
                # Get all key data in the batch
                key_data = {}
                for key in batch_keys:
                    try:
                        key_str = key.decode() if isinstance(key, bytes) else key
                        key_type = self._source_client.type(key)
                        key_type_str = key_type.decode() if isinstance(key_type, bytes) else key_type
                        
                        # Get TTL
                        ttl = self._source_client.ttl(key)
                        
                        # Get value based on type
                        if key_type_str == 'string':
                            value = self._source_client.get(key)
                        elif key_type_str == 'list':
                            value = self._source_client.lrange(key, 0, -1)
                        elif key_type_str == 'set':
                            value = self._source_client.smembers(key)
                        elif key_type_str == 'zset':
                            value = self._source_client.zrange(key, 0, -1, withscores=True)
                        elif key_type_str == 'hash':
                            value = self._source_client.hgetall(key)
                        else:
                            logger.warning(f"Unsupported key type {key_type_str} for key {key_str}")
                            continue
                        
                        key_data[key_str] = {
                            'type': key_type_str,
                            'value': value,
                            'ttl': ttl if ttl > 0 else None
                        }
                        
                    except RedisError as e:
                        logger.error(f"Error reading key {key}: {e}")
                        continue
                
                # Write data to destination
                for key_str, data in key_data.items():
                    try:
                        key_type = data['type']
                        value = data['value']
                        ttl = data['ttl']
                        
                        # Set value based on type
                        if key_type == 'string':
                            dest_pipe.set(key_str, value)
                        elif key_type == 'list':
                            if value:
                                dest_pipe.delete(key_str)  # Clear existing
                                dest_pipe.lpush(key_str, *reversed(value))
                        elif key_type == 'set':
                            if value:
                                dest_pipe.delete(key_str)  # Clear existing
                                dest_pipe.sadd(key_str, *value)
                        elif key_type == 'zset':
                            if value:
                                dest_pipe.delete(key_str)  # Clear existing
                                # Convert to format expected by zadd
                                zadd_dict = {member: score for member, score in value}
                                dest_pipe.zadd(key_str, zadd_dict)
                        elif key_type == 'hash':
                            if value:
                                dest_pipe.delete(key_str)  # Clear existing
                                dest_pipe.hset(key_str, mapping=value)
                        
                        # Set TTL if exists
                        if ttl:
                            dest_pipe.expire(key_str, ttl)
                            
                    except Exception as e:
                        logger.error(f"Error preparing key {key_str} for destination: {e}")
                        continue
                
                # Execute the pipeline
                try:
                    dest_pipe.execute()
                except RedisError as e:
                    logger.error(f"Error executing destination pipeline: {e}")
                
                keys_processed += len(batch_keys)
                progress.records_processed = keys_processed
                progress.current_operation = f"Migrated {keys_processed}/{total_keys} keys"
                yield progress
                
                # Small delay to prevent overwhelming the databases
                await asyncio.sleep(0.01)
            
            progress.tables_completed = 1
            progress.current_operation = "Redis data migration completed"
            yield progress
            
        except Exception as e:
            logger.error(f"Unexpected error during Redis data migration: {e}")
            progress.current_operation = f"Migration failed: {e}"
            yield progress
            raise
    
    async def verify_migration(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Verify the migration by comparing source and destination data.
        
        Args:
            tables: List of key patterns to verify (None for all keys)
            
        Returns:
            Dictionary with verification results
        """
        if not self._source_client or not self._destination_client:
            return {'success': False, 'error': 'Database connections not established'}
        
        verification_results = {
            'success': True,
            'keys_verified': 0,
            'keys_matched': 0,
            'mismatches': [],
            'errors': []
        }
        
        try:
            # Get keys to verify
            if tables is None:
                source_keys = self._source_client.keys('*')
            else:
                source_keys = []
                for pattern in tables:
                    keys = self._source_client.keys(pattern)
                    source_keys.extend(keys)
            
            # Compare key counts
            source_count = len(source_keys)
            dest_count = self._destination_client.dbsize()
            
            verification_results['source_key_count'] = source_count
            verification_results['destination_key_count'] = dest_count
            
            if source_count != dest_count:
                verification_results['mismatches'].append({
                    'type': 'key_count',
                    'source_count': source_count,
                    'destination_count': dest_count
                })
                verification_results['success'] = False
            
            # Sample verification of individual keys
            sample_size = min(100, len(source_keys))
            sample_keys = source_keys[:sample_size]
            
            for key in sample_keys:
                try:
                    key_str = key.decode() if isinstance(key, bytes) else key
                    
                    # Check if key exists in destination
                    if not self._destination_client.exists(key):
                        verification_results['mismatches'].append({
                            'type': 'missing_key',
                            'key': key_str
                        })
                        verification_results['success'] = False
                        continue
                    
                    # Compare key types
                    source_type = self._source_client.type(key)
                    dest_type = self._destination_client.type(key)
                    
                    if source_type != dest_type:
                        verification_results['mismatches'].append({
                            'type': 'type_mismatch',
                            'key': key_str,
                            'source_type': source_type.decode() if isinstance(source_type, bytes) else source_type,
                            'destination_type': dest_type.decode() if isinstance(dest_type, bytes) else dest_type
                        })
                        verification_results['success'] = False
                        continue
                    
                    # Compare TTL
                    source_ttl = self._source_client.ttl(key)
                    dest_ttl = self._destination_client.ttl(key)
                    
                    # Allow some tolerance for TTL differences (within 5 seconds)
                    if abs(source_ttl - dest_ttl) > 5:
                        verification_results['mismatches'].append({
                            'type': 'ttl_mismatch',
                            'key': key_str,
                            'source_ttl': source_ttl,
                            'destination_ttl': dest_ttl
                        })
                    
                    verification_results['keys_verified'] += 1
                    verification_results['keys_matched'] += 1
                    
                except RedisError as e:
                    verification_results['errors'].append(f"Error verifying key {key}: {e}")
                    verification_results['success'] = False
            
        except Exception as e:
            verification_results['success'] = False
            verification_results['errors'].append(f"Verification failed: {str(e)}")
        
        return verification_results
    
    async def get_supported_methods(self) -> List[MigrationMethod]:
        """Get list of migration methods supported by this migrator.
        
        Returns:
            List of supported migration methods
        """
        return [
            MigrationMethod.BULK_COPY,
            MigrationMethod.DIRECT_TRANSFER,
            MigrationMethod.STREAMING
        ]