"""Database transfer factory for creating same-type database transfers."""

from typing import Type, Dict, Optional
from .base import DatabaseMigrator
from .config import DatabaseType, DatabaseConfigUnion
from ..core.exceptions import UnsupportedDatabaseError
from .migrators import (
    MySQLMigrator,
    PostgreSQLMigrator,
    SQLiteMigrator,
    MongoMigrator,
    RedisMigrator
)


class DatabaseTransferFactory:
    """Factory class for creating same-type database transfers."""
    
    # Registry of migrator classes for same-type transfers only
    _migrator_registry: Dict[DatabaseType, Type[DatabaseMigrator]] = {}
    
    @classmethod
    def _register_default_migrators(cls):
        """Register default migrators for supported database types."""
        if cls._migrator_registry:
            return  # Already registered
        
        # Same-type transfers only
        cls._migrator_registry[DatabaseType.MYSQL] = MySQLMigrator
        cls._migrator_registry[DatabaseType.AWS_RDS_MYSQL] = MySQLMigrator
        cls._migrator_registry[DatabaseType.POSTGRESQL] = PostgreSQLMigrator
        cls._migrator_registry[DatabaseType.AWS_RDS_POSTGRESQL] = PostgreSQLMigrator
        cls._migrator_registry[DatabaseType.SQLITE] = SQLiteMigrator
        cls._migrator_registry[DatabaseType.MONGODB] = MongoMigrator
        cls._migrator_registry[DatabaseType.REDIS] = RedisMigrator
    
    @classmethod
    def register_migrator(cls, 
                         database_type: DatabaseType, 
                         migrator_class: Type[DatabaseMigrator]) -> None:
        """Register a migrator class for a specific database type.
        
        Args:
            database_type: Database type to register migrator for
            migrator_class: Migrator class to register
        """
        cls._migrator_registry[database_type] = migrator_class
    
    @classmethod
    def create_migrator(cls, 
                       source_config: DatabaseConfigUnion, 
                       destination_config: DatabaseConfigUnion) -> DatabaseMigrator:
        """Create appropriate migrator for same-type database transfer.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            Database migrator instance
            
        Raises:
            UnsupportedDatabaseError: If database type is not supported or types don't match
        """
        # Ensure default migrators are registered
        cls._register_default_migrators()
        
        source_type = source_config.type
        destination_type = destination_config.type
        
        # Only allow same-type transfers or compatible types
        if not cls._is_compatible_type(source_type, destination_type):
            raise UnsupportedDatabaseError(
                f"Transfer between different database types not supported: {source_type} to {destination_type}. "
                f"Only same-type transfers are allowed (e.g., MySQL to MySQL)."
            )
        
        # Get the appropriate migrator for this database type
        migrator_class = None
        
        # Try source type first
        if source_type in cls._migrator_registry:
            migrator_class = cls._migrator_registry[source_type]
        # Try destination type if source not found
        elif destination_type in cls._migrator_registry:
            migrator_class = cls._migrator_registry[destination_type]
        
        if migrator_class is None:
            raise UnsupportedDatabaseError(
                f"No migrator available for database type: {source_type}"
            )
        
        return migrator_class(source_config, destination_config)
    
    @classmethod
    def get_supported_databases(cls) -> list:
        """Get list of supported database types.
        
        Returns:
            List of supported database type names
        """
        cls._register_default_migrators()
        return [db_type.value for db_type in cls._migrator_registry.keys()]
    
    @classmethod
    def is_transfer_supported(cls, 
                             source_type: DatabaseType, 
                             destination_type: DatabaseType) -> bool:
        """Check if transfer between two database types is supported.
        
        Args:
            source_type: Source database type
            destination_type: Destination database type
            
        Returns:
            True if transfer is supported, False otherwise
        """
        cls._register_default_migrators()
        
        # Only support same-type or compatible transfers
        if not cls._is_compatible_type(source_type, destination_type):
            return False
        
        # Check if we have a migrator for this type
        return (source_type in cls._migrator_registry or 
                destination_type in cls._migrator_registry)
    
    @classmethod
    def validate_transfer_compatibility(cls, 
                                      source_config: DatabaseConfigUnion, 
                                      destination_config: DatabaseConfigUnion) -> tuple[bool, list]:
        """Validate if transfer between two configurations is possible.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            Tuple of (is_compatible, list_of_issues)
        """
        issues = []
        
        # Check if transfer is supported
        if not cls.is_transfer_supported(source_config.type, destination_config.type):
            issues.append(
                f"Transfer from {source_config.type} to {destination_config.type} is not supported. "
                f"Only same-type transfers are allowed."
            )
        
        # Basic connectivity checks
        if source_config.host == destination_config.host and source_config.port == destination_config.port:
            if source_config.database == destination_config.database:
                issues.append("Source and destination cannot be the same database")
        
        is_compatible = len(issues) == 0
        return is_compatible, issues
    
    @classmethod
    def get_recommended_method(cls, 
                             source_config: DatabaseConfigUnion, 
                             destination_config: DatabaseConfigUnion) -> str:
        """Get recommended transfer method for given source and destination.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            Recommended transfer method name
        """
        source_type = source_config.type
        
        # Database-specific recommendations
        if source_type in {DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL}:
            return "dump_restore"  # mysqldump/mysql
        elif source_type in {DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL}:
            return "dump_restore"  # pg_dump/pg_restore
        elif source_type == DatabaseType.SQLITE:
            return "file_copy"     # Direct file copy
        elif source_type == DatabaseType.MONGODB:
            return "dump_restore"  # mongodump/mongorestore
        elif source_type == DatabaseType.REDIS:
            return "dump_restore"  # RDB backup/restore
        
        # Default fallback
        return "dump_restore"
    
    @classmethod
    def get_transfer_requirements(cls, 
                                source_config: DatabaseConfigUnion, 
                                destination_config: DatabaseConfigUnion) -> dict:
        """Get requirements and recommendations for database transfer.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            Dictionary containing transfer requirements and recommendations
        """
        result = {
            'recommended_method': None,
            'requirements': [],
            'warnings': [],
            'estimated_downtime': 'Variable'
        }
        
        try:
            # Basic compatibility check
            is_compatible, issues = cls.validate_transfer_compatibility(source_config, destination_config)
            
            if not is_compatible:
                result['warnings'].extend(issues)
                return result
            
            # Get recommended method
            result['recommended_method'] = cls.get_recommended_method(source_config, destination_config)
            
            # Add method-specific requirements
            if result['recommended_method']:
                requirements = cls._get_method_requirements(result['recommended_method'], source_config)
                result['requirements'] = requirements
            
        except Exception as e:
            result['warnings'].append(f"Transfer analysis failed: {str(e)}")
            result['recommended_method'] = "dump_restore"  # Safe fallback
        
        return result
    
    @classmethod
    def _get_method_requirements(cls, 
                               method: str,
                               source_config: DatabaseConfigUnion) -> list[str]:
        """Get requirements for a specific transfer method.
        
        Args:
            method: Transfer method name
            source_config: Source database configuration
            
        Returns:
            List of requirements for the method
        """
        requirements = []
        
        if method == "dump_restore":
            requirements.extend([
                "Sufficient disk space for database dumps",
                "Network connectivity between source and destination",
                "Database downtime during transfer"
            ])
            
        elif method == "file_copy":
            requirements.extend([
                "File system access to database files",
                "Database must be stopped during copy",
                "Sufficient disk space for file copy"
            ])
        
        # Add database-specific requirements
        if source_config.type in {DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL}:
            requirements.extend([
                "MySQL client tools (mysqldump, mysql)",
                "MySQL server access credentials"
            ])
        elif source_config.type in {DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL}:
            requirements.extend([
                "PostgreSQL client tools (pg_dump, pg_restore)",
                "PostgreSQL server access credentials"
            ])
        elif source_config.type == DatabaseType.SQLITE:
            requirements.extend([
                "File system access to SQLite database file",
                "SQLite3 command-line tools (optional)"
            ])
        elif source_config.type == DatabaseType.MONGODB:
            requirements.extend([
                "MongoDB tools (mongodump, mongorestore)",
                "MongoDB server access credentials"
            ])
        elif source_config.type == DatabaseType.REDIS:
            requirements.extend([
                "Redis tools (redis-cli) or RDB file access",
                "Redis server access credentials"
            ])
        
        return requirements
    
    @classmethod
    def estimate_transfer_time(cls,
                             data_size_mb: Optional[float] = None) -> dict:
        """Estimate transfer time based on data size.
        
        Args:
            data_size_mb: Total data size in MB (optional)
            
        Returns:
            Dictionary with time estimates
        """
        if not data_size_mb:
            return {
                'message': 'Unable to estimate without data size',
                'recommendation': 'Run a test transfer with a small dataset first'
            }
        
        # Simple estimation: ~100 MB/minute for dump/restore over network
        estimated_minutes = data_size_mb / 100
        
        return {
            'estimated_minutes': round(estimated_minutes, 1),
            'estimated_hours': round(estimated_minutes / 60, 2),
            'factors': [
                'Network speed affects transfer time',
                'Database size and complexity',
                'Server performance and load'
            ],
            'recommendation': 'Plan for maintenance window during transfer'
        }
    
    @staticmethod
    def _is_compatible_type(source_type: DatabaseType, dest_type: DatabaseType) -> bool:
        """Check if two database types are compatible for transfer.
        
        Args:
            source_type: Source database type
            dest_type: Destination database type
            
        Returns:
            True if types are compatible, False otherwise
        """
        # Exact match
        if source_type == dest_type:
            return True
        
        # MySQL variants are compatible with each other
        mysql_types = {DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL}
        if source_type in mysql_types and dest_type in mysql_types:
            return True
        
        # PostgreSQL variants are compatible with each other
        postgres_types = {DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL}
        if source_type in postgres_types and dest_type in postgres_types:
            return True
        
        return False


# Convenience function for creating migrators
def create_database_migrator(source_config: DatabaseConfigUnion, 
                           destination_config: DatabaseConfigUnion) -> DatabaseMigrator:
    """Convenience function to create a database transfer migrator.
    
    Args:
        source_config: Source database configuration
        destination_config: Destination database configuration
        
    Returns:
        Database migrator instance for same-type transfer
    """
    return DatabaseTransferFactory.create_migrator(source_config, destination_config)