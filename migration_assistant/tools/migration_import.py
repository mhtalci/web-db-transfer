"""
Migration import/export capabilities for existing tools.

This module provides functionality to import configurations and data
from existing migration tools and export Migration Assistant configurations
to other formats.
"""

import json
import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod

from migration_assistant.models.config import (
    MigrationConfig, SystemConfig, AuthConfig, PathConfig, DatabaseConfig,
    TransferConfig, MigrationOptions, SystemType, AuthType, DatabaseType, TransferMethod
)


@dataclass
class ImportResult:
    """Result of importing from external tool."""
    success: bool
    config: Optional[MigrationConfig] = None
    warnings: List[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


class ToolImporter(ABC):
    """Abstract base class for tool importers."""
    
    @abstractmethod
    def can_import(self, file_path: Path) -> bool:
        """Check if this importer can handle the given file."""
        pass
    
    @abstractmethod
    def import_config(self, file_path: Path) -> ImportResult:
        """Import configuration from the given file."""
        pass
    
    @abstractmethod
    def get_tool_name(self) -> str:
        """Get the name of the tool this importer handles."""
        pass


class WordPressMigratorImporter(ToolImporter):
    """Importer for WordPress migration tools."""
    
    def can_import(self, file_path: Path) -> bool:
        """Check if file is a WordPress migration config."""
        if file_path.suffix.lower() not in ['.json', '.xml']:
            return False
        
        try:
            if file_path.suffix.lower() == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                return 'wordpress' in str(data).lower() or 'wp' in data
            elif file_path.suffix.lower() == '.xml':
                tree = ET.parse(file_path)
                root = tree.getroot()
                return 'wordpress' in root.tag.lower() or any(
                    'wp' in elem.tag.lower() for elem in root.iter()
                )
        except Exception:
            return False
        
        return False
    
    def import_config(self, file_path: Path) -> ImportResult:
        """Import WordPress migration configuration."""
        try:
            if file_path.suffix.lower() == '.json':
                return self._import_json(file_path)
            elif file_path.suffix.lower() == '.xml':
                return self._import_xml(file_path)
            else:
                return ImportResult(
                    success=False,
                    errors=[f"Unsupported file format: {file_path.suffix}"]
                )
        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"Failed to import WordPress config: {str(e)}"]
            )
    
    def _import_json(self, file_path: Path) -> ImportResult:
        """Import from JSON format."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        warnings = []
        errors = []
        
        # Extract source configuration
        source_config = {}
        if 'source' in data:
            source_data = data['source']
            source_config = {
                'type': 'wordpress',
                'host': source_data.get('host', ''),
                'username': source_data.get('username', ''),
                'password': source_data.get('password', ''),
                'port': source_data.get('port', 22)
            }
            
            # Database configuration
            if 'database' in source_data:
                db_data = source_data['database']
                source_config['database'] = {
                    'type': 'mysql',
                    'host': db_data.get('host', source_config['host']),
                    'username': db_data.get('username', ''),
                    'password': db_data.get('password', ''),
                    'database': db_data.get('database', ''),
                    'port': db_data.get('port', 3306)
                }
        else:
            errors.append("No source configuration found")
        
        # Extract destination configuration
        dest_config = {}
        if 'destination' in data:
            dest_data = data['destination']
            dest_config = {
                'type': dest_data.get('type', 'aws-s3'),
                'host': dest_data.get('host') or 's3.amazonaws.com',  # Default host
                'region': dest_data.get('region', 'us-east-1'),
                'bucket': dest_data.get('bucket', 'wordpress-migration')
            }
            
            if 'database' in dest_data:
                db_data = dest_data['database']
                dest_config['database'] = {
                    'type': db_data.get('type', 'aurora-mysql'),
                    'host': db_data.get('host', ''),
                    'username': db_data.get('username', ''),
                    'password': db_data.get('password', ''),
                    'database': db_data.get('database', '')
                }
        else:
            warnings.append("No destination configuration found, using defaults")
            dest_config = {
                'type': 'aws-s3',
                'host': 's3.amazonaws.com',
                'region': 'us-east-1',
                'bucket': 'wordpress-migration'
            }
        
        # Create migration config
        try:
            # Create source system config
            source_auth = AuthConfig(
                type=AuthType.PASSWORD,
                username=source_config.get('username', 'user'),  # Default username
                password=source_config.get('password', 'password')  # Default password
            )
            
            source_paths = PathConfig(
                root_path=source_config.get('root_path', '/var/www/html'),
                web_root='/var/www/html',
                config_path='/var/www/html/wp-config.php'
            )
            
            source_db_config = None
            if 'database' in source_config:
                db_data = source_config['database']
                source_db_config = DatabaseConfig(
                    type=DatabaseType.MYSQL,
                    host=db_data.get('host', source_config['host']),
                    port=db_data.get('port', 3306),
                    database_name=db_data.get('database', ''),
                    username=db_data.get('username', ''),
                    password=db_data.get('password', '')
                )
            
            source_system = SystemConfig(
                type=SystemType.WORDPRESS,
                host=source_config['host'] or 'localhost',  # Ensure host is not empty
                port=source_config.get('port', 22),
                authentication=source_auth,
                paths=source_paths,
                database=source_db_config
            )
            
            # Create destination system config
            dest_auth = AuthConfig(
                type=AuthType.AWS_IAM,
                access_key_id=dest_config.get('access_key', 'AKIAIOSFODNN7EXAMPLE'),  # Example key
                secret_access_key=dest_config.get('secret_key', 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY')  # Example secret
            )
            
            dest_paths = PathConfig(
                root_path=f"s3://{dest_config.get('bucket', 'migration-bucket')}",
                web_root=f"s3://{dest_config.get('bucket', 'migration-bucket')}"
            )
            
            dest_db_config = None
            if 'database' in dest_config:
                db_data = dest_config['database']
                dest_db_config = DatabaseConfig(
                    type=DatabaseType.AWS_RDS,
                    host=db_data.get('host', ''),
                    database_name=db_data.get('database', ''),
                    username=db_data.get('username', ''),
                    password=db_data.get('password', '')
                )
            
            dest_system = SystemConfig(
                type=SystemType.AWS_S3,
                host=dest_config.get('host') or 's3.amazonaws.com',  # Ensure host is not empty
                authentication=dest_auth,
                paths=dest_paths,
                database=dest_db_config
            )
            
            # Create transfer config
            transfer_config = TransferConfig(
                method=TransferMethod.HYBRID_SYNC,
                parallel_transfers=data.get('parallel_transfers', 4),
                compression_enabled=data.get('compression', True),
                verify_checksums=True
            )
            
            # Create migration options
            migration_options = MigrationOptions(
                backup_before=data.get('backup_before', True),
                verify_after=data.get('verify_after', True),
                rollback_on_failure=data.get('rollback_on_failure', True),
                preserve_permissions=True,
                preserve_timestamps=True
            )
            
            config = MigrationConfig(
                name=data.get('name', 'Imported WordPress Migration'),
                description=data.get('description', 'Imported from WordPress migration tool'),
                source=source_system,
                destination=dest_system,
                transfer=transfer_config,
                options=migration_options
            )
            
            return ImportResult(
                success=True,
                config=config,
                warnings=warnings,
                errors=errors
            )
        except Exception as e:
            errors.append(f"Failed to create migration config: {str(e)}")
            return ImportResult(success=False, errors=errors)
    
    def _import_xml(self, file_path: Path) -> ImportResult:
        """Import from XML format (WordPress export)."""
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        warnings = []
        errors = []
        
        # Extract basic information
        site_url = ""
        site_title = ""
        
        for item in root.iter():
            if 'link' in item.tag.lower():
                site_url = item.text or ""
            elif 'title' in item.tag.lower():
                site_title = item.text or ""
        
        if not site_url:
            warnings.append("Could not extract site URL from WordPress export")
        
        warnings.append("XML export contains limited configuration data")
        warnings.append("Please manually configure database and server credentials")
        
        try:
            # Create minimal valid configuration
            source_auth = AuthConfig(
                type=AuthType.PASSWORD,
                username='user',  # Default username
                password='password'   # Default password
            )
            
            source_paths = PathConfig(
                root_path='/var/www/html',
                web_root='/var/www/html'
            )
            
            source_db_config = DatabaseConfig(
                type=DatabaseType.MYSQL,
                host='localhost',  # Default, to be updated by user
                port=3306,
                database_name='wordpress',  # Default
                username='wp_user',  # Default username
                password='wp_password'   # Default password
            )
            
            source_system = SystemConfig(
                type=SystemType.WORDPRESS,
                host=site_url.replace('http://', '').replace('https://', '').split('/')[0] if site_url else 'localhost',
                authentication=source_auth,
                paths=source_paths,
                database=source_db_config
            )
            
            # Create destination system config
            dest_auth = AuthConfig(
                type=AuthType.AWS_IAM,
                access_key_id='',  # To be filled by user
                secret_access_key=''  # To be filled by user
            )
            
            bucket_name = f"{site_title.lower().replace(' ', '-')}-migration" if site_title else 'wordpress-migration'
            dest_paths = PathConfig(
                root_path=f"s3://{bucket_name}",
                web_root=f"s3://{bucket_name}"
            )
            
            dest_system = SystemConfig(
                type=SystemType.AWS_S3,
                host='s3.amazonaws.com',
                authentication=dest_auth,
                paths=dest_paths
            )
            
            # Create transfer and options
            transfer_config = TransferConfig(method=TransferMethod.HYBRID_SYNC)
            migration_options = MigrationOptions(
                backup_before=True,
                verify_after=True,
                rollback_on_failure=True
            )
            
            config = MigrationConfig(
                name=f"WordPress Migration - {site_title}" if site_title else "WordPress Migration",
                description=f"Imported from WordPress export: {file_path.name}",
                source=source_system,
                destination=dest_system,
                transfer=transfer_config,
                options=migration_options
            )
            
            return ImportResult(
                success=True,
                config=config,
                warnings=warnings,
                errors=errors
            )
        except Exception as e:
            errors.append(f"Failed to create migration config: {str(e)}")
            return ImportResult(success=False, errors=errors)
    
    def get_tool_name(self) -> str:
        """Get tool name."""
        return "WordPress Migration Tools"


class DuplicatorImporter(ToolImporter):
    """Importer for Duplicator plugin configurations."""
    
    def can_import(self, file_path: Path) -> bool:
        """Check if file is a Duplicator configuration."""
        if file_path.suffix.lower() != '.json':
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return 'duplicator' in str(data).lower() or 'dup' in data
        except Exception:
            return False
    
    def import_config(self, file_path: Path) -> ImportResult:
        """Import Duplicator configuration."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            warnings = []
            errors = []
            
            # Extract Duplicator-specific data
            archive_info = data.get('archive', {})
            db_info = data.get('database', {})
            
            warnings.append("Duplicator passwords not imported for security reasons")
            warnings.append("Please manually configure server and database passwords")
            
            # Create source system config
            source_auth = AuthConfig(
                type=AuthType.PASSWORD,
                username='user',  # Default username
                password='password'   # Default password
            )
            
            source_paths = PathConfig(
                root_path='/var/www/html',
                web_root='/var/www/html'
            )
            
            source_db_config = DatabaseConfig(
                type=DatabaseType.MYSQL,
                host=db_info.get('host', 'localhost'),
                port=db_info.get('port', 3306),
                database_name=db_info.get('name', ''),
                username=db_info.get('user', ''),
                password=''  # Not stored for security
            )
            
            source_system = SystemConfig(
                type=SystemType.WORDPRESS,
                host=archive_info.get('url', '').replace('http://', '').replace('https://', '').split('/')[0] or 'localhost',
                authentication=source_auth,
                paths=source_paths,
                database=source_db_config
            )
            
            # Create destination system config
            dest_auth = AuthConfig(
                type=AuthType.AWS_IAM,
                access_key_id='',  # To be filled by user
                secret_access_key=''  # To be filled by user
            )
            
            bucket_name = f"{archive_info.get('name', 'duplicator')}-migration"
            dest_paths = PathConfig(
                root_path=f"s3://{bucket_name}",
                web_root=f"s3://{bucket_name}"
            )
            
            dest_system = SystemConfig(
                type=SystemType.AWS_S3,
                host='s3.amazonaws.com',
                authentication=dest_auth,
                paths=dest_paths
            )
            
            # Create transfer and options
            transfer_config = TransferConfig(method=TransferMethod.HYBRID_SYNC)
            migration_options = MigrationOptions(
                backup_before=True,
                verify_after=True,
                rollback_on_failure=True
            )
            
            config = MigrationConfig(
                name=f"Duplicator Migration - {archive_info.get('name', 'Unknown')}",
                description=f"Imported from Duplicator: {file_path.name}",
                source=source_system,
                destination=dest_system,
                transfer=transfer_config,
                options=migration_options
            )
            
            return ImportResult(
                success=True,
                config=config,
                warnings=warnings,
                errors=errors
            )
        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"Failed to import Duplicator config: {str(e)}"]
            )
    
    def get_tool_name(self) -> str:
        """Get tool name."""
        return "Duplicator Plugin"


class MigrateDBImporter(ToolImporter):
    """Importer for WP Migrate DB configurations."""
    
    def can_import(self, file_path: Path) -> bool:
        """Check if file is a WP Migrate DB configuration."""
        if file_path.suffix.lower() != '.json':
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return 'migrate' in str(data).lower() and 'db' in str(data).lower()
        except Exception:
            return False
    
    def import_config(self, file_path: Path) -> ImportResult:
        """Import WP Migrate DB configuration."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            warnings = []
            errors = []
            
            # Extract migration profile data
            profile = data.get('profile', {})
            
            warnings.append("WP Migrate DB passwords not imported for security reasons")
            
            # Create source system config
            source_auth = AuthConfig(
                type=AuthType.PASSWORD,
                username=profile.get('source_user', ''),
                password=''  # Not stored
            )
            
            source_paths = PathConfig(
                root_path='/var/www/html',
                web_root='/var/www/html'
            )
            
            source_db_config = DatabaseConfig(
                type=DatabaseType.MYSQL,
                host=profile.get('source_db_host', 'localhost'),
                port=profile.get('source_db_port', 3306),
                database_name=profile.get('source_db_name', ''),
                username=profile.get('source_db_user', ''),
                password=''  # Not stored
            )
            
            source_system = SystemConfig(
                type=SystemType.WORDPRESS,
                host=profile.get('source_url', '').replace('http://', '').replace('https://', '').split('/')[0] or 'localhost',
                authentication=source_auth,
                paths=source_paths,
                database=source_db_config
            )
            
            # Create destination system config
            dest_auth = AuthConfig(
                type=AuthType.PASSWORD,
                username=profile.get('dest_user', ''),
                password=''  # Not stored
            )
            
            dest_paths = PathConfig(
                root_path='/var/www/html',
                web_root='/var/www/html'
            )
            
            dest_db_config = DatabaseConfig(
                type=DatabaseType.MYSQL,
                host=profile.get('dest_db_host', 'localhost'),
                port=profile.get('dest_db_port', 3306),
                database_name=profile.get('dest_db_name', ''),
                username=profile.get('dest_db_user', ''),
                password=''  # Not stored
            )
            
            dest_system = SystemConfig(
                type=SystemType.WORDPRESS,
                host=profile.get('dest_url', '').replace('http://', '').replace('https://', '').split('/')[0] or 'localhost',
                authentication=dest_auth,
                paths=dest_paths,
                database=dest_db_config
            )
            
            # Create transfer and options
            transfer_config = TransferConfig(method=TransferMethod.HYBRID_SYNC)
            migration_options = MigrationOptions(
                backup_before=True,
                verify_after=True,
                rollback_on_failure=True
            )
            
            config = MigrationConfig(
                name=f"WP Migrate DB - {profile.get('name', 'Unknown')}",
                description=f"Imported from WP Migrate DB: {file_path.name}",
                source=source_system,
                destination=dest_system,
                transfer=transfer_config,
                options=migration_options
            )
            
            return ImportResult(
                success=True,
                config=config,
                warnings=warnings,
                errors=errors
            )
        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"Failed to import WP Migrate DB config: {str(e)}"]
            )
    
    def get_tool_name(self) -> str:
        """Get tool name."""
        return "WP Migrate DB"


class GenericConfigImporter(ToolImporter):
    """Generic importer for common configuration formats."""
    
    def can_import(self, file_path: Path) -> bool:
        """Check if file is a generic configuration file."""
        return file_path.suffix.lower() in ['.json', '.yaml', '.yml', '.toml', '.ini']
    
    def import_config(self, file_path: Path) -> ImportResult:
        """Import generic configuration."""
        try:
            data = self._load_config_file(file_path)
            
            warnings = []
            errors = []
            
            # Try to extract common configuration patterns
            source_config = self._extract_source_config(data, warnings, errors)
            dest_config = self._extract_dest_config(data, warnings, errors)
            
            if not source_config:
                errors.append("Could not extract source configuration")
            if not dest_config:
                warnings.append("Could not extract destination configuration, using defaults")
                dest_config = {
                    'type': 'aws-s3',
                    'region': 'us-east-1',
                    'bucket': 'generic-migration'
                }
            
            # Create proper system configs
            if source_config:
                source_auth = AuthConfig(
                    type=AuthType.PASSWORD,
                    username=source_config.get('username', ''),
                    password=source_config.get('password', '')
                )
                
                source_paths = PathConfig(
                    root_path=source_config.get('root_path', '/var/www/html'),
                    web_root=source_config.get('web_root', '/var/www/html')
                )
                
                source_db_config = None
                if source_config.get('database'):
                    db_data = source_config['database']
                    source_db_config = DatabaseConfig(
                        type=DatabaseType.MYSQL,  # Default to MySQL
                        host=db_data.get('host', 'localhost'),
                        port=db_data.get('port', 3306),
                        database_name=db_data.get('database', ''),
                        username=db_data.get('username', ''),
                        password=db_data.get('password', '')
                    )
                
                source_system = SystemConfig(
                    type=SystemType.STATIC_SITE,  # Default to static site for generic
                    host=source_config.get('host', 'localhost'),
                    port=source_config.get('port', 22),
                    authentication=source_auth,
                    paths=source_paths,
                    database=source_db_config
                )
            else:
                errors.append("Could not create source configuration")
                return ImportResult(success=False, errors=errors)
            
            if dest_config:
                dest_auth = AuthConfig(
                    type=AuthType.AWS_IAM,
                    access_key_id=dest_config.get('access_key', ''),
                    secret_access_key=dest_config.get('secret_key', '')
                )
                
                dest_paths = PathConfig(
                    root_path=f"s3://{dest_config.get('bucket', 'generic-migration')}",
                    web_root=f"s3://{dest_config.get('bucket', 'generic-migration')}"
                )
                
                dest_system = SystemConfig(
                    type=SystemType.AWS_S3,
                    host=dest_config.get('host', 's3.amazonaws.com'),
                    authentication=dest_auth,
                    paths=dest_paths
                )
            else:
                # Create default destination
                dest_auth = AuthConfig(
                    type=AuthType.AWS_IAM,
                    access_key_id='',
                    secret_access_key=''
                )
                
                dest_paths = PathConfig(
                    root_path='s3://generic-migration',
                    web_root='s3://generic-migration'
                )
                
                dest_system = SystemConfig(
                    type=SystemType.AWS_S3,
                    host='s3.amazonaws.com',
                    authentication=dest_auth,
                    paths=dest_paths
                )
            
            # Create transfer and options
            transfer_data = data.get('transfer', {})
            transfer_config = TransferConfig(
                method=TransferMethod.HYBRID_SYNC,
                parallel_transfers=transfer_data.get('parallel_transfers', 4),
                compression_enabled=transfer_data.get('compression', True)
            )
            
            options_data = data.get('options', data.get('safety', {}))
            migration_options = MigrationOptions(
                backup_before=options_data.get('backup_before', True),
                verify_after=options_data.get('verify_after', True),
                rollback_on_failure=options_data.get('rollback_on_failure', True)
            )
            
            config = MigrationConfig(
                name=data.get('name', f"Generic Migration - {file_path.stem}"),
                description=data.get('description', f"Imported from {file_path.name}"),
                source=source_system,
                destination=dest_system,
                transfer=transfer_config,
                options=migration_options
            )
            
            return ImportResult(
                success=True,
                config=config,
                warnings=warnings,
                errors=errors
            )
        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"Failed to import generic config: {str(e)}"]
            )
    
    def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration file based on format."""
        if file_path.suffix.lower() == '.json':
            with open(file_path, 'r') as f:
                return json.load(f)
        elif file_path.suffix.lower() in ['.yaml', '.yml']:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f)
        elif file_path.suffix.lower() == '.toml':
            import toml
            with open(file_path, 'r') as f:
                return toml.load(f)
        elif file_path.suffix.lower() == '.ini':
            import configparser
            config = configparser.ConfigParser()
            config.read(file_path)
            return {section: dict(config[section]) for section in config.sections()}
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    def _extract_source_config(self, data: Dict[str, Any], warnings: List[str], errors: List[str]) -> Optional[Dict[str, Any]]:
        """Extract source configuration from generic data."""
        source_keys = ['source', 'src', 'from', 'origin']
        source_data = None
        
        for key in source_keys:
            if key in data:
                source_data = data[key]
                break
        
        if not source_data:
            # Try to infer from top-level keys
            if 'host' in data and 'username' in data:
                source_data = data
            else:
                return None
        
        return {
            'type': source_data.get('type', 'static_site'),
            'host': source_data.get('host', ''),
            'username': source_data.get('username', source_data.get('user', '')),
            'password': source_data.get('password', ''),
            'port': source_data.get('port', 22),
            'root_path': source_data.get('root_path', '/var/www/html'),
            'web_root': source_data.get('web_root', '/var/www/html'),
            'database': source_data.get('database', source_data.get('db', {}))
        }
    
    def _extract_dest_config(self, data: Dict[str, Any], warnings: List[str], errors: List[str]) -> Optional[Dict[str, Any]]:
        """Extract destination configuration from generic data."""
        dest_keys = ['destination', 'dest', 'to', 'target']
        dest_data = None
        
        for key in dest_keys:
            if key in data:
                dest_data = data[key]
                break
        
        if not dest_data:
            return None
        
        return {
            'type': dest_data.get('type', 'aws_s3'),
            'host': dest_data.get('host', 's3.amazonaws.com'),
            'region': dest_data.get('region', 'us-east-1'),
            'bucket': dest_data.get('bucket', 'generic-migration'),
            'access_key': dest_data.get('access_key', dest_data.get('access_key_id', '')),
            'secret_key': dest_data.get('secret_key', dest_data.get('secret_access_key', '')),
            'database': dest_data.get('database', dest_data.get('db', {}))
        }
    
    def get_tool_name(self) -> str:
        """Get tool name."""
        return "Generic Configuration"


class MigrationImportManager:
    """Manager for importing configurations from various migration tools."""
    
    def __init__(self):
        self.importers = [
            WordPressMigratorImporter(),
            DuplicatorImporter(),
            MigrateDBImporter(),
            GenericConfigImporter()  # Keep as last resort
        ]
    
    def import_from_file(self, file_path: Union[str, Path]) -> ImportResult:
        """Import migration configuration from file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return ImportResult(
                success=False,
                errors=[f"File not found: {file_path}"]
            )
        
        # Try each importer
        for importer in self.importers:
            if importer.can_import(file_path):
                result = importer.import_config(file_path)
                if result.success:
                    result.warnings.insert(0, f"Imported using {importer.get_tool_name()} importer")
                return result
        
        return ImportResult(
            success=False,
            errors=[f"No suitable importer found for file: {file_path}"]
        )
    
    def export_to_file(self, config: MigrationConfig, file_path: Union[str, Path], format: str = 'yaml') -> bool:
        """Export migration configuration to file."""
        file_path = Path(file_path)
        
        try:
            # Convert config to dictionary
            config_dict = config.dict()
            
            # Export based on format
            if format.lower() == 'json':
                with open(file_path, 'w') as f:
                    json.dump(config_dict, f, indent=2, default=str)
            elif format.lower() in ['yaml', 'yml']:
                with open(file_path, 'w') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            elif format.lower() == 'toml':
                import toml
                with open(file_path, 'w') as f:
                    toml.dump(config_dict, f)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            return True
        except Exception as e:
            print(f"Failed to export configuration: {e}")
            return False
    
    def list_supported_tools(self) -> List[str]:
        """List supported migration tools."""
        return [importer.get_tool_name() for importer in self.importers]
    
    def detect_tool_type(self, file_path: Union[str, Path]) -> Optional[str]:
        """Detect which tool created the configuration file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return None
        
        for importer in self.importers:
            if importer.can_import(file_path):
                return importer.get_tool_name()
        
        return None


# CLI integration functions
def import_migration_config(file_path: str) -> ImportResult:
    """Import migration configuration from external tool."""
    manager = MigrationImportManager()
    return manager.import_from_file(file_path)


def export_migration_config(config: MigrationConfig, file_path: str, format: str = 'yaml') -> bool:
    """Export migration configuration to file."""
    manager = MigrationImportManager()
    return manager.export_to_file(config, file_path, format)


def list_supported_import_tools() -> List[str]:
    """List supported migration tools for import."""
    manager = MigrationImportManager()
    return manager.list_supported_tools()


if __name__ == "__main__":
    # Example usage
    manager = MigrationImportManager()
    
    print("Supported migration tools:")
    for tool in manager.list_supported_tools():
        print(f"  - {tool}")
    
    # Example import
    # result = manager.import_from_file("example-config.json")
    # if result.success:
    #     print(f"Successfully imported: {result.config.name}")
    #     for warning in result.warnings:
    #         print(f"Warning: {warning}")
    # else:
    #     print("Import failed:")
    #     for error in result.errors:
    #         print(f"Error: {error}")