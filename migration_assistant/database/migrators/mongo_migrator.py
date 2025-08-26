"""MongoDB database migrator implementation using pymongo."""

import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId

from ..base import DatabaseMigrator, MigrationResult, MigrationProgress, MigrationStatus, MigrationMethod
from ..config import MongoConfig, DatabaseConfigUnion


logger = logging.getLogger(__name__)


class MongoMigrator(DatabaseMigrator):
    """MongoDB database migrator using pymongo."""
    
    def __init__(self, source_config: DatabaseConfigUnion, destination_config: DatabaseConfigUnion):
        """Initialize MongoDB migrator.
        
        Args:
            source_config: Source MongoDB database configuration
            destination_config: Destination MongoDB database configuration
        """
        super().__init__(source_config, destination_config)
        self._source_client: Optional[MongoClient] = None
        self._destination_client: Optional[MongoClient] = None
        self._source_db = None
        self._destination_db = None
        
    def _create_connection_string(self, config: MongoConfig) -> str:
        """Create MongoDB connection string.
        
        Args:
            config: MongoDB configuration
            
        Returns:
            MongoDB connection string
        """
        # Build connection string
        if config.username and config.password:
            auth_part = f"{config.username}:{config.password}@"
        else:
            auth_part = ""
        
        # Handle replica set
        replica_set_part = f"?replicaSet={config.replica_set}" if config.replica_set else ""
        
        # Build full connection string
        conn_string = f"mongodb://{auth_part}{config.host}:{config.port}/{config.database}{replica_set_part}"
        
        return conn_string
    
    def _create_client_options(self, config: MongoConfig) -> Dict[str, Any]:
        """Create MongoDB client options.
        
        Args:
            config: MongoDB configuration
            
        Returns:
            Client options dictionary
        """
        options = {
            'serverSelectionTimeoutMS': config.connection_timeout * 1000,
            'connectTimeoutMS': config.connection_timeout * 1000,
            'socketTimeoutMS': config.connection_timeout * 1000,
            'authSource': config.auth_source,
            'readPreference': config.read_preference,
        }
        
        if config.replica_set:
            options['replicaSet'] = config.replica_set
        
        # Add extra parameters
        options.update(config.extra_params)
        
        return options
    
    async def connect_source(self) -> bool:
        """Connect to the source MongoDB database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            options = self._create_client_options(self.source_config)
            
            self._source_client = MongoClient(
                host=self.source_config.host,
                port=self.source_config.port,
                username=self.source_config.username,
                password=self.source_config.password,
                **options
            )
            
            # Test connection
            self._source_client.admin.command('ping')
            self._source_db = self._source_client[self.source_config.database]
            
            logger.info(f"Connected to source MongoDB database: {self.source_config.host}:{self.source_config.port}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to source MongoDB database: {e}")
            return False
        except PyMongoError as e:
            logger.error(f"MongoDB error connecting to source: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to source MongoDB: {e}")
            return False
    
    async def connect_destination(self) -> bool:
        """Connect to the destination MongoDB database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            options = self._create_client_options(self.destination_config)
            
            self._destination_client = MongoClient(
                host=self.destination_config.host,
                port=self.destination_config.port,
                username=self.destination_config.username,
                password=self.destination_config.password,
                **options
            )
            
            # Test connection
            self._destination_client.admin.command('ping')
            self._destination_db = self._destination_client[self.destination_config.database]
            
            logger.info(f"Connected to destination MongoDB database: {self.destination_config.host}:{self.destination_config.port}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to destination MongoDB database: {e}")
            return False
        except PyMongoError as e:
            logger.error(f"MongoDB error connecting to destination: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to destination MongoDB: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from both source and destination databases."""
        try:
            if self._source_client:
                self._source_client.close()
                self._source_client = None
                self._source_db = None
                
            if self._destination_client:
                self._destination_client.close()
                self._destination_client = None
                self._destination_db = None
                
            logger.info("Disconnected from MongoDB databases")
            
        except Exception as e:
            logger.error(f"Error during MongoDB disconnect: {e}")
    
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
        """Get schema information from a MongoDB database.
        
        Args:
            config: Database configuration
            
        Returns:
            Dictionary containing schema information
        """
        try:
            options = self._create_client_options(config)
            client = MongoClient(
                host=config.host,
                port=config.port,
                username=config.username,
                password=config.password,
                **options
            )
            
            db = client[config.database]
            
            schema_info = {
                'database': config.database,
                'collections': [],
                'indexes': [],
                'users': [],
                'stats': {}
            }
            
            # Get database stats
            try:
                stats = db.command('dbStats')
                schema_info['stats'] = {
                    'collections': stats.get('collections', 0),
                    'objects': stats.get('objects', 0),
                    'dataSize': stats.get('dataSize', 0),
                    'storageSize': stats.get('storageSize', 0),
                    'indexes': stats.get('indexes', 0),
                    'indexSize': stats.get('indexSize', 0)
                }
            except PyMongoError as e:
                logger.warning(f"Could not get database stats: {e}")
            
            # Get collections
            collection_names = db.list_collection_names()
            
            for collection_name in collection_names:
                collection = db[collection_name]
                
                try:
                    # Get collection stats
                    coll_stats = db.command('collStats', collection_name)
                    
                    # Get indexes
                    indexes = list(collection.list_indexes())
                    
                    # Sample a few documents to understand structure
                    sample_docs = list(collection.find().limit(5))
                    
                    schema_info['collections'].append({
                        'name': collection_name,
                        'count': coll_stats.get('count', 0),
                        'size': coll_stats.get('size', 0),
                        'storageSize': coll_stats.get('storageSize', 0),
                        'indexes': [
                            {
                                'name': idx.get('name'),
                                'key': idx.get('key'),
                                'unique': idx.get('unique', False)
                            } for idx in indexes
                        ],
                        'sampleDocuments': len(sample_docs),
                        'avgObjSize': coll_stats.get('avgObjSize', 0)
                    })
                    
                except PyMongoError as e:
                    logger.warning(f"Could not get stats for collection {collection_name}: {e}")
                    # Add basic info even if stats fail
                    schema_info['collections'].append({
                        'name': collection_name,
                        'count': collection.estimated_document_count(),
                        'size': 0,
                        'storageSize': 0,
                        'indexes': [],
                        'sampleDocuments': 0,
                        'avgObjSize': 0
                    })
            
            # Get database users (if admin access)
            try:
                users_info = db.command('usersInfo')
                if 'users' in users_info:
                    schema_info['users'] = [
                        {'user': user.get('user'), 'roles': user.get('roles', [])}
                        for user in users_info['users']
                    ]
            except PyMongoError:
                # User might not have permission to list users
                pass
            
            client.close()
            return schema_info
            
        except PyMongoError as e:
            logger.error(f"Failed to get MongoDB schema info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting MongoDB schema info: {e}")
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
            
            # Check for collection name conflicts
            source_collections = {coll['name'] for coll in source_info.get('collections', [])}
            dest_collections = {coll['name'] for coll in dest_info.get('collections', [])}
            
            conflicts = source_collections.intersection(dest_collections)
            if conflicts:
                issues.append(f"Collection name conflicts detected: {', '.join(conflicts)}")
            
            # Check MongoDB version compatibility
            try:
                source_version = self._source_client.server_info()['version']
                dest_version = self._destination_client.server_info()['version']
                
                source_major = int(source_version.split('.')[0])
                dest_major = int(dest_version.split('.')[0])
                
                if dest_major < source_major:
                    issues.append(f"Destination MongoDB version ({dest_version}) is older than source ({source_version})")
                
            except Exception as e:
                issues.append(f"Could not verify MongoDB version compatibility: {e}")
            
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
            collections = schema_info.get('collections', [])
            
            total_collections = len(collections)
            total_documents = stats.get('objects', 0)
            total_data_size = stats.get('dataSize', 0)
            total_indexes = sum(len(coll.get('indexes', [])) for coll in collections)
            
            return {
                'total_collections': total_collections,
                'total_documents': total_documents,
                'total_data_size_bytes': total_data_size,
                'total_data_size_mb': round(total_data_size / (1024 * 1024), 2),
                'total_storage_size_bytes': stats.get('storageSize', 0),
                'total_indexes': total_indexes,
                'index_size_bytes': stats.get('indexSize', 0),
                'estimated_duration_minutes': max(1, total_documents // 5000)  # Rough estimate
            }
            
        except Exception as e:
            logger.error(f"Error estimating migration size: {e}")
            return {
                'total_collections': 0,
                'total_documents': 0,
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
            if not self._source_db or not self._destination_db:
                result.status = MigrationStatus.FAILED
                result.errors.append("Database connections not established")
                return result
            
            # Get collections from source
            collection_names = self._source_db.list_collection_names()
            migrated_collections = 0
            
            for collection_name in collection_names:
                try:
                    source_collection = self._source_db[collection_name]
                    dest_collection = self._destination_db[collection_name]
                    
                    # Create collection (MongoDB creates collections automatically on first insert)
                    # But we can create indexes
                    indexes = list(source_collection.list_indexes())
                    
                    for index in indexes:
                        # Skip the default _id index
                        if index['name'] == '_id_':
                            continue
                        
                        try:
                            # Create index on destination
                            index_keys = index['key']
                            index_options = {k: v for k, v in index.items() 
                                           if k not in ['key', 'v', 'ns']}
                            
                            dest_collection.create_index(
                                list(index_keys.items()),
                                **index_options
                            )
                        except PyMongoError as e:
                            result.warnings.append(f"Failed to create index {index['name']} on {collection_name}: {e}")
                    
                    migrated_collections += 1
                    
                except PyMongoError as e:
                    result.errors.append(f"Failed to migrate collection {collection_name}: {e}")
                    logger.error(f"Failed to migrate collection {collection_name}: {e}")
            
            result.tables_migrated = migrated_collections  # Using tables_migrated for collections
            result.status = MigrationStatus.COMPLETED
            
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
            tables: List of collections to migrate (None for all collections)
            batch_size: Number of documents to process in each batch
            method: Migration method to use
            
        Yields:
            MigrationProgress objects with current progress
        """
        if not self._source_db or not self._destination_db:
            raise RuntimeError("Database connections not established")
        
        try:
            # Get collections to migrate
            if tables is None:
                collection_names = self._source_db.list_collection_names()
            else:
                collection_names = tables
            
            total_collections = len(collection_names)
            collections_completed = 0
            total_documents = 0
            
            progress = MigrationProgress(
                total_tables=total_collections,
                tables_completed=0,
                records_processed=0,
                current_operation="Starting data migration"
            )
            yield progress
            
            for collection_name in collection_names:
                progress.current_table = collection_name
                progress.current_operation = f"Migrating collection {collection_name}"
                yield progress
                
                try:
                    source_collection = self._source_db[collection_name]
                    dest_collection = self._destination_db[collection_name]
                    
                    # Get total document count for this collection
                    collection_doc_count = source_collection.estimated_document_count()
                    
                    if collection_doc_count == 0:
                        collections_completed += 1
                        progress.tables_completed = collections_completed
                        continue
                    
                    # Migrate documents in batches
                    collection_documents = 0
                    cursor = source_collection.find()
                    
                    batch = []
                    for document in cursor:
                        batch.append(document)
                        
                        if len(batch) >= batch_size:
                            # Insert batch into destination
                            try:
                                dest_collection.insert_many(batch, ordered=False)
                            except PyMongoError as e:
                                # Try inserting documents one by one if bulk insert fails
                                for doc in batch:
                                    try:
                                        dest_collection.insert_one(doc)
                                    except PyMongoError as doc_e:
                                        logger.warning(f"Failed to insert document in {collection_name}: {doc_e}")
                            
                            collection_documents += len(batch)
                            total_documents += len(batch)
                            batch = []
                            
                            progress.records_processed = total_documents
                            progress.current_operation = f"Migrating collection {collection_name} ({collection_documents}/{collection_doc_count} documents)"
                            yield progress
                            
                            # Small delay to prevent overwhelming the database
                            await asyncio.sleep(0.01)
                    
                    # Insert remaining documents
                    if batch:
                        try:
                            dest_collection.insert_many(batch, ordered=False)
                        except PyMongoError as e:
                            for doc in batch:
                                try:
                                    dest_collection.insert_one(doc)
                                except PyMongoError as doc_e:
                                    logger.warning(f"Failed to insert document in {collection_name}: {doc_e}")
                        
                        collection_documents += len(batch)
                        total_documents += len(batch)
                    
                    collections_completed += 1
                    progress.tables_completed = collections_completed
                    progress.records_processed = total_documents
                    progress.current_operation = f"Completed collection {collection_name} ({collection_documents} documents)"
                    yield progress
                    
                except PyMongoError as e:
                    logger.error(f"Error migrating collection {collection_name}: {e}")
                    progress.current_operation = f"Error migrating collection {collection_name}: {e}"
                    yield progress
                    continue
            
            progress.current_operation = "Data migration completed"
            yield progress
            
        except Exception as e:
            logger.error(f"Unexpected error during data migration: {e}")
            progress.current_operation = f"Migration failed: {e}"
            yield progress
            raise
    
    async def verify_migration(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Verify the migration by comparing source and destination data.
        
        Args:
            tables: List of collections to verify (None for all collections)
            
        Returns:
            Dictionary with verification results
        """
        if not self._source_db or not self._destination_db:
            return {'success': False, 'error': 'Database connections not established'}
        
        verification_results = {
            'success': True,
            'collections_verified': 0,
            'collections_matched': 0,
            'mismatches': [],
            'errors': []
        }
        
        try:
            # Get collections to verify
            if tables is None:
                collection_names = self._source_db.list_collection_names()
            else:
                collection_names = tables
            
            for collection_name in collection_names:
                try:
                    source_collection = self._source_db[collection_name]
                    dest_collection = self._destination_db[collection_name]
                    
                    # Compare document counts
                    source_count = source_collection.estimated_document_count()
                    dest_count = dest_collection.estimated_document_count()
                    
                    verification_results['collections_verified'] += 1
                    
                    if source_count == dest_count:
                        verification_results['collections_matched'] += 1
                    else:
                        verification_results['mismatches'].append({
                            'collection': collection_name,
                            'source_count': source_count,
                            'destination_count': dest_count
                        })
                        verification_results['success'] = False
                    
                    # Additional verification: compare a sample of documents
                    if source_count > 0 and dest_count > 0:
                        sample_size = min(10, source_count)
                        source_sample = list(source_collection.find().limit(sample_size))
                        
                        for doc in source_sample:
                            dest_doc = dest_collection.find_one({'_id': doc['_id']})
                            if not dest_doc:
                                verification_results['errors'].append(
                                    f"Document with _id {doc['_id']} not found in destination collection {collection_name}"
                                )
                                verification_results['success'] = False
                    
                except PyMongoError as e:
                    verification_results['errors'].append(f"Error verifying collection {collection_name}: {e}")
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