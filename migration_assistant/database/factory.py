"""Database migration factory for creating database-specific migrators."""

from typing import Type, Dict, Tuple, List, Optional
from .base import DatabaseMigrator, MigrationMethod
from .config import DatabaseType, DatabaseConfigUnion
from .schema_analyzer import SchemaAnalyzer, SchemaAnalysisResult, SchemaCompatibilityResult
from ..core.exceptions import UnsupportedDatabaseError, IncompatibleDatabaseError
from .migrators import (
    MySQLMigrator,
    PostgreSQLMigrator,
    SQLiteMigrator,
    MongoMigrator,
    RedisMigrator
)


class DatabaseMigrationFactory:
    """Factory class for creating database-specific migrators."""
    
    # Registry of migrator classes
    _migrator_registry: Dict[Tuple[DatabaseType, DatabaseType], Type[DatabaseMigrator]] = {}
    
    # Schema analyzer for migration method selection
    _schema_analyzer: Optional[SchemaAnalyzer] = None
    
    @classmethod
    def _register_default_migrators(cls):
        """Register default migrators for supported database types."""
        if cls._migrator_registry:
            return  # Already registered
        
        # MySQL migrators
        cls.register_migrator(DatabaseType.MYSQL, DatabaseType.MYSQL, MySQLMigrator)
        cls.register_migrator(DatabaseType.AWS_RDS_MYSQL, DatabaseType.AWS_RDS_MYSQL, MySQLMigrator)
        cls.register_migrator(DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL, MySQLMigrator)
        cls.register_migrator(DatabaseType.AWS_RDS_MYSQL, DatabaseType.MYSQL, MySQLMigrator)
        
        # PostgreSQL migrators
        cls.register_migrator(DatabaseType.POSTGRESQL, DatabaseType.POSTGRESQL, PostgreSQLMigrator)
        cls.register_migrator(DatabaseType.AWS_RDS_POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL, PostgreSQLMigrator)
        cls.register_migrator(DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL, PostgreSQLMigrator)
        cls.register_migrator(DatabaseType.AWS_RDS_POSTGRESQL, DatabaseType.POSTGRESQL, PostgreSQLMigrator)
        
        # SQLite migrators
        cls.register_migrator(DatabaseType.SQLITE, DatabaseType.SQLITE, SQLiteMigrator)
        
        # MongoDB migrators
        cls.register_migrator(DatabaseType.MONGODB, DatabaseType.MONGODB, MongoMigrator)
        
        # Redis migrators
        cls.register_migrator(DatabaseType.REDIS, DatabaseType.REDIS, RedisMigrator)
    
    @classmethod
    def register_migrator(cls, 
                         source_type: DatabaseType, 
                         destination_type: DatabaseType, 
                         migrator_class: Type[DatabaseMigrator]) -> None:
        """Register a migrator class for specific source and destination database types.
        
        Args:
            source_type: Source database type
            destination_type: Destination database type
            migrator_class: Migrator class to register
        """
        key = (source_type, destination_type)
        cls._migrator_registry[key] = migrator_class
    
    @classmethod
    def create_migrator(cls, 
                       source_config: DatabaseConfigUnion, 
                       destination_config: DatabaseConfigUnion) -> DatabaseMigrator:
        """Create appropriate migrator based on source and destination database types.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            Database migrator instance
            
        Raises:
            UnsupportedDatabaseError: If database type is not supported
            IncompatibleDatabaseError: If source and destination are incompatible
        """
        # Ensure default migrators are registered
        cls._register_default_migrators()
        
        source_type = source_config.type
        destination_type = destination_config.type
        
        # Check if we have a specific migrator for this combination
        key = (source_type, destination_type)
        if key in cls._migrator_registry:
            migrator_class = cls._migrator_registry[key]
            return migrator_class(source_config, destination_config)
        
        # Check for same-type migrations (e.g., MySQL to MySQL)
        if source_type == destination_type:
            same_type_key = (source_type, source_type)
            if same_type_key in cls._migrator_registry:
                migrator_class = cls._migrator_registry[same_type_key]
                return migrator_class(source_config, destination_config)
        
        # Check for generic migrators that can handle multiple types
        for (src_type, dest_type), migrator_class in cls._migrator_registry.items():
            if cls._is_compatible_type(source_type, src_type) and \
               cls._is_compatible_type(destination_type, dest_type):
                return migrator_class(source_config, destination_config)
        
        # If no specific migrator found, raise error
        raise UnsupportedDatabaseError(
            f"No migrator available for {source_type} to {destination_type} migration"
        )
    
    @classmethod
    def get_supported_migrations(cls) -> Dict[str, list]:
        """Get list of supported migration combinations.
        
        Returns:
            Dictionary mapping source types to list of supported destination types
        """
        supported = {}
        for (source_type, dest_type) in cls._migrator_registry.keys():
            source_str = source_type.value
            dest_str = dest_type.value
            
            if source_str not in supported:
                supported[source_str] = []
            
            if dest_str not in supported[source_str]:
                supported[source_str].append(dest_str)
        
        return supported
    
    @classmethod
    def is_migration_supported(cls, 
                              source_type: DatabaseType, 
                              destination_type: DatabaseType) -> bool:
        """Check if migration between two database types is supported.
        
        Args:
            source_type: Source database type
            destination_type: Destination database type
            
        Returns:
            True if migration is supported, False otherwise
        """
        key = (source_type, destination_type)
        if key in cls._migrator_registry:
            return True
        
        # Check for same-type migrations
        if source_type == destination_type:
            same_type_key = (source_type, source_type)
            if same_type_key in cls._migrator_registry:
                return True
        
        # Check for generic migrators
        for (src_type, dest_type) in cls._migrator_registry.keys():
            if cls._is_compatible_type(source_type, src_type) and \
               cls._is_compatible_type(destination_type, dest_type):
                return True
        
        return False
    
    @classmethod
    def validate_migration_compatibility(cls, 
                                       source_config: DatabaseConfigUnion, 
                                       destination_config: DatabaseConfigUnion) -> Tuple[bool, list]:
        """Validate if migration between two configurations is possible.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            Tuple of (is_compatible, list_of_issues)
        """
        issues = []
        
        # Check if migration is supported
        if not cls.is_migration_supported(source_config.type, destination_config.type):
            issues.append(f"Migration from {source_config.type} to {destination_config.type} is not supported")
        
        # Check for specific compatibility issues
        source_type = source_config.type
        dest_type = destination_config.type
        
        # SQL to NoSQL migrations need special handling
        sql_types = {DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE}
        nosql_types = {DatabaseType.MONGODB, DatabaseType.REDIS}
        
        if source_type in sql_types and dest_type in nosql_types:
            issues.append("SQL to NoSQL migration requires schema transformation")
        
        if source_type in nosql_types and dest_type in sql_types:
            issues.append("NoSQL to SQL migration requires schema definition")
        
        # Cloud-specific validations
        cloud_types = {DatabaseType.AWS_RDS_MYSQL, DatabaseType.AWS_RDS_POSTGRESQL, 
                      DatabaseType.GOOGLE_CLOUD_SQL, DatabaseType.AZURE_SQL}
        
        if source_type in cloud_types or dest_type in cloud_types:
            # Add cloud-specific validation logic here
            pass
        
        # Version compatibility checks (would need to be implemented per database type)
        # This is a placeholder for future version compatibility checks
        
        is_compatible = len(issues) == 0
        return is_compatible, issues
    
    @classmethod
    def get_recommended_method(cls, 
                             source_config: DatabaseConfigUnion, 
                             destination_config: DatabaseConfigUnion) -> str:
        """Get recommended migration method for given source and destination.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            Recommended migration method name
        """
        source_type = source_config.type
        dest_type = destination_config.type
        
        # Same type migrations
        if source_type == dest_type:
            return "dump_restore"
        
        # SQL to SQL migrations
        sql_types = {DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.SQLITE}
        if source_type in sql_types and dest_type in sql_types:
            return "direct_transfer"
        
        # NoSQL migrations
        nosql_types = {DatabaseType.MONGODB, DatabaseType.REDIS}
        if source_type in nosql_types and dest_type in nosql_types:
            return "bulk_copy"
        
        # Cloud migrations
        cloud_types = {DatabaseType.AWS_RDS_MYSQL, DatabaseType.AWS_RDS_POSTGRESQL, 
                      DatabaseType.GOOGLE_CLOUD_SQL, DatabaseType.AZURE_SQL}
        if source_type in cloud_types or dest_type in cloud_types:
            return "cloud_native"
        
        # Default fallback
        return "dump_restore"
    
    @classmethod
    async def analyze_and_recommend_method(cls,
                                         source_config: DatabaseConfigUnion,
                                         destination_config: DatabaseConfigUnion,
                                         analyze_schema: bool = True) -> Dict[str, any]:
        """Analyze schemas and recommend optimal migration method.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            analyze_schema: Whether to perform detailed schema analysis
            
        Returns:
            Dictionary containing analysis results and recommendations
        """
        if cls._schema_analyzer is None:
            cls._schema_analyzer = SchemaAnalyzer()
        
        result = {
            'recommended_method': None,
            'alternative_methods': [],
            'compatibility_analysis': None,
            'schema_analysis': None,
            'warnings': [],
            'requirements': []
        }
        
        try:
            # Basic compatibility check
            is_compatible, issues = cls.validate_migration_compatibility(source_config, destination_config)
            
            if not is_compatible:
                result['warnings'].extend(issues)
            
            # Perform schema analysis if requested
            if analyze_schema:
                try:
                    # Analyze source schema
                    source_schema = await cls._schema_analyzer.analyze_schema(source_config)
                    result['schema_analysis'] = {
                        'source_tables': source_schema.get_table_count(),
                        'source_rows': source_schema.get_total_rows(),
                        'source_size_mb': round(source_schema.get_total_size_bytes() / (1024 * 1024), 2),
                        'has_views': len(source_schema.views) > 0,
                        'has_functions': len(source_schema.functions) > 0,
                        'has_sequences': len(source_schema.sequences) > 0
                    }
                    
                    # Analyze compatibility
                    compatibility = await cls._schema_analyzer.analyze_compatibility(
                        source_config, destination_config, source_schema
                    )
                    result['compatibility_analysis'] = {
                        'compatible': compatibility.compatible,
                        'complexity': compatibility.migration_complexity,
                        'issues': compatibility.issues,
                        'warnings': compatibility.warnings,
                        'recommendations': compatibility.recommendations,
                        'unsupported_features': compatibility.unsupported_features
                    }
                    
                    # Get method recommendations from schema analyzer
                    if compatibility.recommended_method:
                        result['recommended_method'] = compatibility.recommended_method.value
                    
                    # Get alternative methods
                    alternative_methods = cls._schema_analyzer.get_migration_method_recommendations(
                        source_config, destination_config, source_schema
                    )
                    result['alternative_methods'] = [method.value for method in alternative_methods]
                    
                except Exception as e:
                    result['warnings'].append(f"Schema analysis failed: {str(e)}")
                    # Fall back to basic method recommendation
                    result['recommended_method'] = cls.get_recommended_method(source_config, destination_config)
            else:
                # Use basic method recommendation
                result['recommended_method'] = cls.get_recommended_method(source_config, destination_config)
            
            # Add method-specific requirements
            if result['recommended_method']:
                requirements = cls._get_method_requirements(result['recommended_method'], source_config, destination_config)
                result['requirements'] = requirements
            
        except Exception as e:
            result['warnings'].append(f"Migration analysis failed: {str(e)}")
            result['recommended_method'] = "dump_restore"  # Safe fallback
        
        return result
    
    @classmethod
    def _get_method_requirements(cls, 
                               method: str,
                               source_config: DatabaseConfigUnion,
                               destination_config: DatabaseConfigUnion) -> List[str]:
        """Get requirements for a specific migration method.
        
        Args:
            method: Migration method name
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            List of requirements for the method
        """
        requirements = []
        
        if method == "dump_restore":
            requirements.extend([
                "Sufficient disk space for database dumps",
                "Database-specific dump/restore tools (mysqldump, pg_dump, etc.)",
                "Network connectivity between source and destination"
            ])
            
        elif method == "direct_transfer":
            requirements.extend([
                "Simultaneous connections to both databases",
                "Compatible data types between source and destination",
                "Sufficient memory for data buffering"
            ])
            
        elif method == "streaming":
            requirements.extend([
                "Stable network connection for continuous streaming",
                "Database replication or CDC capabilities",
                "Minimal downtime tolerance"
            ])
            
        elif method == "cloud_native":
            requirements.extend([
                "Cloud provider migration tools access",
                "Appropriate IAM permissions",
                "Network connectivity to cloud services"
            ])
            
        elif method == "bulk_copy":
            requirements.extend([
                "Bulk data loading capabilities",
                "Temporary storage for data files",
                "Database-specific bulk loading tools"
            ])
        
        # Add database-specific requirements
        if source_config.type in {DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL}:
            requirements.append("MySQL client tools and connectors")
        elif source_config.type in {DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL}:
            requirements.append("PostgreSQL client tools and connectors")
        elif source_config.type == DatabaseType.SQLITE:
            requirements.append("SQLite3 command-line tools")
        elif source_config.type == DatabaseType.MONGODB:
            requirements.append("MongoDB tools (mongodump, mongorestore)")
        elif source_config.type == DatabaseType.REDIS:
            requirements.append("Redis tools (redis-cli, RDB files)")
        
        return requirements
    
    @classmethod
    def get_supported_methods_for_migration(cls,
                                          source_config: DatabaseConfigUnion,
                                          destination_config: DatabaseConfigUnion) -> List[MigrationMethod]:
        """Get all supported migration methods for a specific migration path.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            
        Returns:
            List of supported migration methods
        """
        try:
            # Create a temporary migrator to get supported methods
            migrator = cls.create_migrator(source_config, destination_config)
            return migrator.get_supported_methods()
        except (UnsupportedDatabaseError, IncompatibleDatabaseError):
            # Return empty list if migration is not supported
            return []
    
    @classmethod
    def estimate_migration_time(cls,
                              source_config: DatabaseConfigUnion,
                              destination_config: DatabaseConfigUnion,
                              method: MigrationMethod,
                              data_size_mb: Optional[float] = None,
                              row_count: Optional[int] = None) -> Dict[str, any]:
        """Estimate migration time based on method and data characteristics.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            method: Migration method to use
            data_size_mb: Total data size in MB (optional)
            row_count: Total number of rows (optional)
            
        Returns:
            Dictionary with time estimates and factors
        """
        estimate = {
            'estimated_hours': 0.0,
            'min_hours': 0.0,
            'max_hours': 0.0,
            'factors': [],
            'assumptions': []
        }
        
        # Base estimates per method (hours per GB)
        method_rates = {
            MigrationMethod.DUMP_RESTORE: 0.5,      # 2 GB/hour
            MigrationMethod.DIRECT_TRANSFER: 1.0,   # 1 GB/hour
            MigrationMethod.STREAMING: 2.0,         # 0.5 GB/hour (more overhead)
            MigrationMethod.CLOUD_NATIVE: 0.3,      # 3.3 GB/hour (optimized)
            MigrationMethod.BULK_COPY: 0.2          # 5 GB/hour (fastest)
        }
        
        if data_size_mb:
            data_size_gb = data_size_mb / 1024
            base_rate = method_rates.get(method, 1.0)
            estimate['estimated_hours'] = data_size_gb * base_rate
            
            # Add variance
            estimate['min_hours'] = estimate['estimated_hours'] * 0.7
            estimate['max_hours'] = estimate['estimated_hours'] * 1.5
            
            estimate['assumptions'].append(f"Based on {data_size_mb:.1f} MB of data")
        
        # Add complexity factors
        if source_config.type != destination_config.type:
            estimate['estimated_hours'] *= 1.3
            estimate['factors'].append("Cross-database type migration (+30%)")
        
        if row_count and row_count > 1000000:
            estimate['estimated_hours'] *= 1.2
            estimate['factors'].append("Large row count (+20%)")
        
        # Network factors
        if source_config.host != destination_config.host:
            estimate['estimated_hours'] *= 1.1
            estimate['factors'].append("Network transfer (+10%)")
        
        # Add setup and validation time
        setup_time = 0.5  # 30 minutes setup
        validation_time = max(0.2, estimate['estimated_hours'] * 0.1)  # 10% of migration time
        
        estimate['estimated_hours'] += setup_time + validation_time
        estimate['min_hours'] += setup_time + validation_time * 0.5
        estimate['max_hours'] += setup_time + validation_time * 1.5
        
        estimate['factors'].extend([
            f"Setup time: {setup_time} hours",
            f"Validation time: {validation_time:.1f} hours"
        ])
        
        return estimate
    
    @staticmethod
    def _is_compatible_type(actual_type: DatabaseType, registered_type: DatabaseType) -> bool:
        """Check if an actual database type is compatible with a registered type.
        
        This allows for generic migrators that can handle multiple similar types.
        
        Args:
            actual_type: The actual database type
            registered_type: The registered migrator type
            
        Returns:
            True if types are compatible, False otherwise
        """
        # Exact match
        if actual_type == registered_type:
            return True
        
        # MySQL variants
        mysql_types = {DatabaseType.MYSQL, DatabaseType.AWS_RDS_MYSQL}
        if actual_type in mysql_types and registered_type in mysql_types:
            return True
        
        # PostgreSQL variants
        postgres_types = {DatabaseType.POSTGRESQL, DatabaseType.AWS_RDS_POSTGRESQL}
        if actual_type in postgres_types and registered_type in postgres_types:
            return True
        
        return False


# Convenience function for creating migrators
def create_database_migrator(source_config: DatabaseConfigUnion, 
                           destination_config: DatabaseConfigUnion) -> DatabaseMigrator:
    """Convenience function to create a database migrator.
    
    Args:
        source_config: Source database configuration
        destination_config: Destination database configuration
        
    Returns:
        Database migrator instance
    """
    return DatabaseMigrationFactory.create_migrator(source_config, destination_config)