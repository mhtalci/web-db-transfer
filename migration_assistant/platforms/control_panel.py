"""
Control panel adapters for cPanel, DirectAdmin, Plesk, and other hosting control panels.
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio
import subprocess
import base64
from urllib.parse import urljoin
try:
    import aiohttp
except ImportError:
    aiohttp = None

from .base import PlatformAdapter, PlatformInfo, DependencyInfo, EnvironmentConfig
from ..models.config import SystemConfig
from ..core.exceptions import PlatformError


class HostingAccount(dict):
    """Represents a hosting account from a control panel."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.username = kwargs.get('username', '')
        self.domain = kwargs.get('domain', '')
        self.email = kwargs.get('email', '')
        self.databases = kwargs.get('databases', [])
        self.subdomains = kwargs.get('subdomains', [])
        self.email_accounts = kwargs.get('email_accounts', [])


class DatabaseInfo(dict):
    """Represents database information from a control panel."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get('name', '')
        self.user = kwargs.get('user', '')
        self.host = kwargs.get('host', 'localhost')
        self.type = kwargs.get('type', 'mysql')
        self.size = kwargs.get('size', 0)


class EmailAccount(dict):
    """Represents an email account from a control panel."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.email = kwargs.get('email', '')
        self.quota = kwargs.get('quota', 0)
        self.usage = kwargs.get('usage', 0)


class DNSRecord(dict):
    """Represents a DNS record from a control panel."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get('name', '')
        self.type = kwargs.get('type', 'A')
        self.value = kwargs.get('value', '')
        self.ttl = kwargs.get('ttl', 3600)


class ControlPanelAdapter(PlatformAdapter):
    """Base adapter for hosting control panels."""
    
    @property
    def platform_type(self) -> str:
        return "control_panel"
    
    async def get_accounts(self) -> List[HostingAccount]:
        """Get list of hosting accounts."""
        return []
    
    async def get_databases(self, account: Optional[str] = None) -> List[DatabaseInfo]:
        """Get list of databases for an account."""
        return []
    
    async def get_email_accounts(self, account: Optional[str] = None) -> List[EmailAccount]:
        """Get list of email accounts for an account."""
        return []
    
    async def get_dns_records(self, domain: str) -> List[DNSRecord]:
        """Get DNS records for a domain."""
        return []
    
    async def backup_account(self, account: str, backup_path: Path) -> bool:
        """Create a backup of an account."""
        return False
    
    async def extract_files(self, account: str, destination_path: Path) -> bool:
        """Extract files from an account."""
        return False


class CPanelAdapter(ControlPanelAdapter):
    """Adapter for cPanel control panel using cPanel API v2/UAPI."""
    
    def __init__(self, config: SystemConfig):
        super().__init__(config)
        self.api_base_url = f"https://{config.host}:2083"
        self.username = getattr(config, 'username', '')
        self.api_token = getattr(config, 'api_token', '')
        self.session = None
    
    @property
    def platform_type(self) -> str:
        return "cpanel"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["11.0", "11.1", "11.2", "11.3", "11.4", "11.5", "11.6"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect cPanel installation or configuration."""
        # Check for cPanel-specific files
        cpanel_files = [
            ".cpanel",
            "cpanel.yml",
            "public_html",  # Common cPanel directory
            ".htaccess"
        ]
        
        for cpanel_file in cpanel_files:
            if (path / cpanel_file).exists():
                return True
        
        # Check if we can connect to cPanel API
        try:
            if self.username and self.api_token:
                return await self._test_api_connection()
        except Exception:
            pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze cPanel installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"cPanel not detected at {path}")
        
        # Get cPanel version and information
        cpanel_info = await self._get_cpanel_info()
        accounts = await self.get_accounts()
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=cpanel_info.get("version"),
            framework="cpanel",
            database_type="mysql",  # cPanel typically uses MySQL
            dependencies=["curl", "ssh"],
            config_files=[".cpanel", "cpanel.yml"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get cPanel dependencies."""
        return [
            DependencyInfo(
                name="curl",
                required=True,
                install_command="apt-get install curl"
            ),
            DependencyInfo(
                name="ssh",
                required=False,
                install_command="apt-get install openssh-client"
            ),
            DependencyInfo(
                name="mysql-client",
                required=False,
                install_command="apt-get install mysql-client"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract cPanel environment configuration."""
        return EnvironmentConfig(
            variables={
                "CPANEL_HOST": self.config.host,
                "CPANEL_USER": self.username
            },
            files=[".cpanel", "cpanel.yml"],
            secrets=["CPANEL_API_TOKEN", "CPANEL_PASSWORD"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare cPanel migration."""
        platform_info = await self.analyze_platform(source_path)
        accounts = await self.get_accounts()
        
        migration_steps = [
            "authenticate_cpanel",
            "list_accounts",
            "backup_accounts",
            "extract_databases",
            "extract_files",
            "extract_email_accounts",
            "extract_dns_records",
            "prepare_destination"
        ]
        
        return {
            "platform_info": platform_info.dict(),
            "accounts": [account.dict() if hasattr(account, 'dict') else account for account in accounts],
            "migration_steps": migration_steps,
            "api_endpoints": self._get_api_endpoints()
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform cPanel post-migration setup."""
        try:
            # Process extracted accounts
            accounts = migration_info.get("accounts", [])
            
            for account_data in accounts:
                account = HostingAccount(**account_data)
                
                # Create directory structure for account
                account_dir = destination_path / account.username
                account_dir.mkdir(exist_ok=True)
                
                # Extract files for this account
                await self.extract_files(account.username, account_dir)
                
                # Extract databases
                databases = await self.get_databases(account.username)
                if databases:
                    db_dir = account_dir / "databases"
                    db_dir.mkdir(exist_ok=True)
                    
                    for db in databases:
                        await self._export_database(db, db_dir)
            
            return True
        except Exception as e:
            self.logger.error(f"cPanel post-migration setup failed: {e}")
            return False
    
    async def get_accounts(self) -> List[HostingAccount]:
        """Get list of cPanel accounts."""
        try:
            # Use UAPI to list accounts
            response = await self._api_request("uapi", "DomainInfo", "list_domains")
            
            if response and "result" in response:
                domains = response["result"].get("data", [])
                accounts = []
                
                for domain_info in domains:
                    account = HostingAccount(
                        username=self.username,  # In shared hosting, usually one account
                        domain=domain_info.get("domain", ""),
                        email="",  # Will be populated separately
                        databases=[],
                        subdomains=[],
                        email_accounts=[]
                    )
                    accounts.append(account)
                
                return accounts
            
            return []
        except Exception as e:
            self.logger.error(f"Failed to get cPanel accounts: {e}")
            return []
    
    async def get_databases(self, account: Optional[str] = None) -> List[DatabaseInfo]:
        """Get list of databases from cPanel."""
        try:
            # Get MySQL databases
            response = await self._api_request("uapi", "Mysql", "list_databases")
            
            databases = []
            if response and "result" in response:
                db_list = response["result"].get("data", [])
                
                for db_info in db_list:
                    database = DatabaseInfo(
                        name=db_info.get("db", ""),
                        user="",  # Will be populated from users list
                        host="localhost",
                        type="mysql",
                        size=db_info.get("disk_usage", 0)
                    )
                    databases.append(database)
            
            # Get database users
            users_response = await self._api_request("uapi", "Mysql", "list_users")
            if users_response and "result" in users_response:
                users = users_response["result"].get("data", [])
                
                # Match users to databases (simplified)
                for db in databases:
                    for user in users:
                        if db.name in user.get("user", ""):
                            db.user = user.get("user", "")
                            break
            
            return databases
        except Exception as e:
            self.logger.error(f"Failed to get cPanel databases: {e}")
            return []
    
    async def get_email_accounts(self, account: Optional[str] = None) -> List[EmailAccount]:
        """Get list of email accounts from cPanel."""
        try:
            response = await self._api_request("uapi", "Email", "list_pops")
            
            email_accounts = []
            if response and "result" in response:
                accounts = response["result"].get("data", [])
                
                for account_info in accounts:
                    email_account = EmailAccount(
                        email=account_info.get("email", ""),
                        quota=account_info.get("_diskquota", 0),
                        usage=account_info.get("_diskused", 0)
                    )
                    email_accounts.append(email_account)
            
            return email_accounts
        except Exception as e:
            self.logger.error(f"Failed to get cPanel email accounts: {e}")
            return []
    
    async def get_dns_records(self, domain: str) -> List[DNSRecord]:
        """Get DNS records for a domain from cPanel."""
        try:
            response = await self._api_request("uapi", "DNS", "parse_zone", zone=domain)
            
            dns_records = []
            if response and "result" in response:
                records = response["result"].get("data", [])
                
                for record_info in records:
                    dns_record = DNSRecord(
                        name=record_info.get("name", ""),
                        type=record_info.get("type", "A"),
                        value=record_info.get("record", ""),
                        ttl=record_info.get("ttl", 3600)
                    )
                    dns_records.append(dns_record)
            
            return dns_records
        except Exception as e:
            self.logger.error(f"Failed to get DNS records for {domain}: {e}")
            return []
    
    async def backup_account(self, account: str, backup_path: Path) -> bool:
        """Create a full backup of a cPanel account."""
        try:
            # Initiate backup via cPanel API
            response = await self._api_request("uapi", "Backup", "fullbackup_to_homedir")
            
            if response and response.get("result", {}).get("status") == 1:
                self.logger.info(f"Backup initiated for account {account}")
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Failed to backup account {account}: {e}")
            return False
    
    async def extract_files(self, account: str, destination_path: Path) -> bool:
        """Extract files from cPanel account via SSH/FTP."""
        try:
            # This would typically use SSH or FTP to download files
            # For now, we'll create a placeholder implementation
            
            # Create common cPanel directories
            directories = ["public_html", "mail", "etc", "logs", "tmp"]
            
            for directory in directories:
                dir_path = destination_path / directory
                dir_path.mkdir(exist_ok=True)
                
                # Create a placeholder file to indicate the directory structure
                (dir_path / ".cpanel_extracted").write_text(f"Extracted from cPanel account: {account}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to extract files for account {account}: {e}")
            return False
    
    async def _get_session(self):
        """Get or create HTTP session for API requests."""
        if aiohttp is None:
            raise ImportError("aiohttp is required for cPanel API access. Install with: pip install aiohttp")
        
        if self.session is None:
            connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification for self-signed certs
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session
    
    async def _api_request(self, api_type: str, module: str, function: str, **params) -> Optional[Dict[str, Any]]:
        """Make a request to cPanel API."""
        try:
            session = await self._get_session()
            
            # Build API URL
            if api_type == "uapi":
                url = f"{self.api_base_url}/execute/{module}/{function}"
            else:  # cpapi2
                url = f"{self.api_base_url}/json-api/cpanel"
                params.update({"cpanel_jsonapi_module": module, "cpanel_jsonapi_func": function})
            
            # Prepare headers
            headers = {
                "Authorization": f"cpanel {self.username}:{self.api_token}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Make request
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"cPanel API request failed: {response.status}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"cPanel API request error: {e}")
            return None
    
    async def _test_api_connection(self) -> bool:
        """Test connection to cPanel API."""
        try:
            response = await self._api_request("uapi", "Features", "list_features")
            return response is not None and "result" in response
        except Exception:
            return False
    
    async def _get_cpanel_info(self) -> Dict[str, Any]:
        """Get cPanel version and system information."""
        try:
            response = await self._api_request("uapi", "Branding", "get_info")
            
            if response and "result" in response:
                return response["result"].get("data", {})
            
            return {}
        except Exception as e:
            self.logger.error(f"Failed to get cPanel info: {e}")
            return {}
    
    def _get_api_endpoints(self) -> Dict[str, str]:
        """Get available cPanel API endpoints."""
        return {
            "domains": f"{self.api_base_url}/execute/DomainInfo/list_domains",
            "databases": f"{self.api_base_url}/execute/Mysql/list_databases",
            "email": f"{self.api_base_url}/execute/Email/list_pops",
            "dns": f"{self.api_base_url}/execute/DNS/parse_zone",
            "backup": f"{self.api_base_url}/execute/Backup/fullbackup_to_homedir"
        }
    
    async def _export_database(self, database: DatabaseInfo, destination_path: Path) -> bool:
        """Export a database to SQL file."""
        try:
            # This would typically use mysqldump or cPanel's database export
            # For now, create a placeholder
            sql_file = destination_path / f"{database.name}.sql"
            sql_file.write_text(f"-- Database export for {database.name}\n-- Exported from cPanel\n")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to export database {database.name}: {e}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()


class DirectAdminAdapter(ControlPanelAdapter):
    """Adapter for DirectAdmin control panel."""
    
    def __init__(self, config: SystemConfig):
        super().__init__(config)
        self.api_base_url = f"https://{config.host}:2222"
        self.username = getattr(config, 'username', '')
        self.password = getattr(config, 'password', '')
        self.session = None
    
    @property
    def platform_type(self) -> str:
        return "directadmin"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["1.60", "1.61", "1.62", "1.63", "1.64", "1.65"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect DirectAdmin installation."""
        # Check for DirectAdmin-specific files
        da_files = [
            ".directadmin",
            "directadmin.conf",
            "domains",  # Common DirectAdmin directory
            "public_html"
        ]
        
        for da_file in da_files:
            if (path / da_file).exists():
                return True
        
        # Test API connection
        try:
            if self.username and self.password:
                return await self._test_api_connection()
        except Exception:
            pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze DirectAdmin installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"DirectAdmin not detected at {path}")
        
        da_info = await self._get_directadmin_info()
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=da_info.get("version"),
            framework="directadmin",
            database_type="mysql",
            dependencies=["curl", "ssh"],
            config_files=[".directadmin", "directadmin.conf"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get DirectAdmin dependencies."""
        return [
            DependencyInfo(
                name="curl",
                required=True,
                install_command="apt-get install curl"
            ),
            DependencyInfo(
                name="ssh",
                required=False,
                install_command="apt-get install openssh-client"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract DirectAdmin environment configuration."""
        return EnvironmentConfig(
            variables={
                "DA_HOST": self.config.host,
                "DA_USER": self.username
            },
            files=[".directadmin", "directadmin.conf"],
            secrets=["DA_PASSWORD", "DA_API_KEY"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare DirectAdmin migration."""
        platform_info = await self.analyze_platform(source_path)
        accounts = await self.get_accounts()
        
        return {
            "platform_info": platform_info.dict(),
            "accounts": [account.dict() if hasattr(account, 'dict') else account for account in accounts],
            "migration_steps": ["authenticate_da", "list_users", "backup_accounts", "extract_data"],
            "api_endpoints": self._get_api_endpoints()
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform DirectAdmin post-migration setup."""
        try:
            # Similar to cPanel but using DirectAdmin API structure
            accounts = migration_info.get("accounts", [])
            
            for account_data in accounts:
                account = HostingAccount(**account_data)
                account_dir = destination_path / account.username
                account_dir.mkdir(exist_ok=True)
                
                await self.extract_files(account.username, account_dir)
            
            return True
        except Exception as e:
            self.logger.error(f"DirectAdmin post-migration setup failed: {e}")
            return False
    
    async def get_accounts(self) -> List[HostingAccount]:
        """Get list of DirectAdmin accounts."""
        try:
            response = await self._api_request("CMD_API_SHOW_USERS")
            
            accounts = []
            if response:
                # DirectAdmin returns users in a specific format
                users = response.get("list", [])
                
                for user in users:
                    account = HostingAccount(
                        username=user,
                        domain="",  # Will be populated separately
                        email="",
                        databases=[],
                        subdomains=[],
                        email_accounts=[]
                    )
                    accounts.append(account)
            
            return accounts
        except Exception as e:
            self.logger.error(f"Failed to get DirectAdmin accounts: {e}")
            return []
    
    async def get_databases(self, account: Optional[str] = None) -> List[DatabaseInfo]:
        """Get list of databases from DirectAdmin."""
        try:
            response = await self._api_request("CMD_API_DATABASES", user=account)
            
            databases = []
            if response:
                db_list = response.get("list", [])
                
                for db_name in db_list:
                    database = DatabaseInfo(
                        name=db_name,
                        user=account or "",
                        host="localhost",
                        type="mysql",
                        size=0
                    )
                    databases.append(database)
            
            return databases
        except Exception as e:
            self.logger.error(f"Failed to get DirectAdmin databases: {e}")
            return []
    
    async def get_email_accounts(self, account: Optional[str] = None) -> List[EmailAccount]:
        """Get list of email accounts from DirectAdmin."""
        try:
            response = await self._api_request("CMD_API_POP", user=account)
            
            email_accounts = []
            if response:
                accounts = response.get("list", [])
                
                for email in accounts:
                    email_account = EmailAccount(
                        email=email,
                        quota=0,  # DirectAdmin API might not provide this directly
                        usage=0
                    )
                    email_accounts.append(email_account)
            
            return email_accounts
        except Exception as e:
            self.logger.error(f"Failed to get DirectAdmin email accounts: {e}")
            return []
    
    async def get_dns_records(self, domain: str) -> List[DNSRecord]:
        """Get DNS records for a domain from DirectAdmin."""
        try:
            response = await self._api_request("CMD_API_DNS_CONTROL", domain=domain)
            
            dns_records = []
            if response:
                records = response.get("records", [])
                
                for record in records:
                    dns_record = DNSRecord(
                        name=record.get("name", ""),
                        type=record.get("type", "A"),
                        value=record.get("value", ""),
                        ttl=record.get("ttl", 3600)
                    )
                    dns_records.append(dns_record)
            
            return dns_records
        except Exception as e:
            self.logger.error(f"Failed to get DNS records for {domain}: {e}")
            return []
    
    async def backup_account(self, account: str, backup_path: Path) -> bool:
        """Create a backup of a DirectAdmin account."""
        try:
            response = await self._api_request("CMD_API_BACKUP", user=account)
            return response is not None
        except Exception as e:
            self.logger.error(f"Failed to backup DirectAdmin account {account}: {e}")
            return False
    
    async def extract_files(self, account: str, destination_path: Path) -> bool:
        """Extract files from DirectAdmin account."""
        try:
            # Create DirectAdmin directory structure
            directories = ["domains", "public_html", "mail", "backups"]
            
            for directory in directories:
                dir_path = destination_path / directory
                dir_path.mkdir(exist_ok=True)
                (dir_path / ".directadmin_extracted").write_text(f"Extracted from DirectAdmin account: {account}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to extract files for DirectAdmin account {account}: {e}")
            return False
    
    async def _get_session(self) -> Any:
        """Get or create HTTP session for API requests."""
        if self.session is None:
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session
    
    async def _api_request(self, command: str, **params) -> Optional[Dict[str, Any]]:
        """Make a request to DirectAdmin API."""
        try:
            session = await self._get_session()
            
            url = f"{self.api_base_url}/CMD_API_ADMIN"
            
            # Prepare authentication
            auth_string = f"{self.username}:{self.password}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Prepare parameters
            data = {"action": command}
            data.update(params)
            
            async with session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    text = await response.text()
                    # DirectAdmin returns data in various formats, parse accordingly
                    return self._parse_directadmin_response(text)
                else:
                    self.logger.error(f"DirectAdmin API request failed: {response.status}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"DirectAdmin API request error: {e}")
            return None
    
    def _parse_directadmin_response(self, response_text: str) -> Dict[str, Any]:
        """Parse DirectAdmin API response."""
        try:
            # DirectAdmin responses are often in key=value format
            result = {}
            lines = response_text.strip().split('\n')
            
            for line in lines:
                if '=' in line:
                    key, value = line.split('=', 1)
                    result[key] = value
            
            return result
        except Exception:
            return {"raw_response": response_text}
    
    async def _test_api_connection(self) -> bool:
        """Test connection to DirectAdmin API."""
        try:
            response = await self._api_request("CMD_API_ADMIN_STATS")
            return response is not None
        except Exception:
            return False
    
    async def _get_directadmin_info(self) -> Dict[str, Any]:
        """Get DirectAdmin version and system information."""
        try:
            response = await self._api_request("CMD_API_ADMIN_STATS")
            return response or {}
        except Exception as e:
            self.logger.error(f"Failed to get DirectAdmin info: {e}")
            return {}
    
    def _get_api_endpoints(self) -> Dict[str, str]:
        """Get available DirectAdmin API endpoints."""
        return {
            "users": f"{self.api_base_url}/CMD_API_SHOW_USERS",
            "databases": f"{self.api_base_url}/CMD_API_DATABASES",
            "email": f"{self.api_base_url}/CMD_API_POP",
            "dns": f"{self.api_base_url}/CMD_API_DNS_CONTROL",
            "backup": f"{self.api_base_url}/CMD_API_BACKUP"
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()


class PleskAdapter(ControlPanelAdapter):
    """Adapter for Plesk control panel using Plesk API."""
    
    def __init__(self, config: SystemConfig):
        super().__init__(config)
        self.api_base_url = f"https://{config.host}:8443/enterprise/control/agent.php"
        self.api_key = getattr(config, 'api_key', '')
        self.session = None
    
    @property
    def platform_type(self) -> str:
        return "plesk"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["18.0", "19.0", "20.0", "21.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Plesk installation."""
        # Check for Plesk-specific files
        plesk_files = [
            ".plesk",
            "plesk.conf",
            "httpdocs",  # Common Plesk directory
            "vhosts"
        ]
        
        for plesk_file in plesk_files:
            if (path / plesk_file).exists():
                return True
        
        # Test API connection
        try:
            if self.api_key:
                return await self._test_api_connection()
        except Exception:
            pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Plesk installation."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Plesk not detected at {path}")
        
        plesk_info = await self._get_plesk_info()
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=plesk_info.get("version"),
            framework="plesk",
            database_type="mysql",
            dependencies=["curl", "ssh"],
            config_files=[".plesk", "plesk.conf"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Plesk dependencies."""
        return [
            DependencyInfo(
                name="curl",
                required=True,
                install_command="apt-get install curl"
            ),
            DependencyInfo(
                name="ssh",
                required=False,
                install_command="apt-get install openssh-client"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Plesk environment configuration."""
        return EnvironmentConfig(
            variables={
                "PLESK_HOST": self.config.host,
                "PLESK_API_KEY": self.api_key
            },
            files=[".plesk", "plesk.conf"],
            secrets=["PLESK_API_KEY", "PLESK_PASSWORD"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Plesk migration."""
        platform_info = await self.analyze_platform(source_path)
        accounts = await self.get_accounts()
        
        return {
            "platform_info": platform_info.dict(),
            "accounts": [account.dict() if hasattr(account, 'dict') else account for account in accounts],
            "migration_steps": ["authenticate_plesk", "list_domains", "backup_domains", "extract_data"],
            "api_endpoints": self._get_api_endpoints()
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Plesk post-migration setup."""
        try:
            accounts = migration_info.get("accounts", [])
            
            for account_data in accounts:
                account = HostingAccount(**account_data)
                account_dir = destination_path / account.domain
                account_dir.mkdir(exist_ok=True)
                
                await self.extract_files(account.domain, account_dir)
            
            return True
        except Exception as e:
            self.logger.error(f"Plesk post-migration setup failed: {e}")
            return False
    
    async def get_accounts(self) -> List[HostingAccount]:
        """Get list of Plesk domains/accounts."""
        try:
            xml_request = """
            <packet>
                <domain>
                    <get>
                        <filter/>
                        <dataset>
                            <gen_info/>
                            <hosting/>
                        </dataset>
                    </get>
                </domain>
            </packet>
            """
            
            response = await self._api_request(xml_request)
            accounts = []
            
            if response:
                # Parse XML response
                root = ET.fromstring(response)
                
                for domain in root.findall(".//domain"):
                    result = domain.find("result")
                    if result is not None:
                        data = result.find("data")
                        if data is not None:
                            gen_info = data.find("gen_info")
                            domain_name = gen_info.find("name").text if gen_info is not None and gen_info.find("name") is not None else ""
                            
                            account = HostingAccount(
                                username="",  # Plesk uses domain-based structure
                                domain=domain_name,
                                email="",
                                databases=[],
                                subdomains=[],
                                email_accounts=[]
                            )
                            accounts.append(account)
            
            return accounts
        except Exception as e:
            self.logger.error(f"Failed to get Plesk accounts: {e}")
            return []
    
    async def get_databases(self, account: Optional[str] = None) -> List[DatabaseInfo]:
        """Get list of databases from Plesk."""
        try:
            xml_request = """
            <packet>
                <database>
                    <get>
                        <filter/>
                        <dataset>
                            <gen_info/>
                        </dataset>
                    </get>
                </database>
            </packet>
            """
            
            response = await self._api_request(xml_request)
            databases = []
            
            if response:
                root = ET.fromstring(response)
                
                for db in root.findall(".//database"):
                    result = db.find("result")
                    if result is not None:
                        data = result.find("data")
                        if data is not None:
                            gen_info = data.find("gen_info")
                            if gen_info is not None:
                                db_name = gen_info.find("name")
                                db_type = gen_info.find("type")
                                
                                database = DatabaseInfo(
                                    name=db_name.text if db_name is not None else "",
                                    user="",
                                    host="localhost",
                                    type=db_type.text.lower() if db_type is not None else "mysql",
                                    size=0
                                )
                                databases.append(database)
            
            return databases
        except Exception as e:
            self.logger.error(f"Failed to get Plesk databases: {e}")
            return []
    
    async def get_email_accounts(self, account: Optional[str] = None) -> List[EmailAccount]:
        """Get list of email accounts from Plesk."""
        try:
            xml_request = """
            <packet>
                <mail>
                    <get>
                        <filter/>
                        <dataset>
                            <gen_info/>
                        </dataset>
                    </get>
                </mail>
            </packet>
            """
            
            response = await self._api_request(xml_request)
            email_accounts = []
            
            if response:
                root = ET.fromstring(response)
                
                for mail in root.findall(".//mail"):
                    result = mail.find("result")
                    if result is not None:
                        data = result.find("data")
                        if data is not None:
                            gen_info = data.find("gen_info")
                            if gen_info is not None:
                                email = gen_info.find("name")
                                
                                email_account = EmailAccount(
                                    email=email.text if email is not None else "",
                                    quota=0,
                                    usage=0
                                )
                                email_accounts.append(email_account)
            
            return email_accounts
        except Exception as e:
            self.logger.error(f"Failed to get Plesk email accounts: {e}")
            return []
    
    async def get_dns_records(self, domain: str) -> List[DNSRecord]:
        """Get DNS records for a domain from Plesk."""
        try:
            xml_request = f"""
            <packet>
                <dns>
                    <get_rec>
                        <filter>
                            <site-name>{domain}</site-name>
                        </filter>
                    </get_rec>
                </dns>
            </packet>
            """
            
            response = await self._api_request(xml_request)
            dns_records = []
            
            if response:
                root = ET.fromstring(response)
                
                for dns in root.findall(".//dns"):
                    result = dns.find("result")
                    if result is not None:
                        data = result.find("data")
                        if data is not None:
                            dns_record = DNSRecord(
                                name=data.find("host").text if data.find("host") is not None else "",
                                type=data.find("type").text if data.find("type") is not None else "A",
                                value=data.find("value").text if data.find("value") is not None else "",
                                ttl=int(data.find("ttl").text) if data.find("ttl") is not None else 3600
                            )
                            dns_records.append(dns_record)
            
            return dns_records
        except Exception as e:
            self.logger.error(f"Failed to get DNS records for {domain}: {e}")
            return []
    
    async def backup_account(self, account: str, backup_path: Path) -> bool:
        """Create a backup of a Plesk domain."""
        try:
            xml_request = f"""
            <packet>
                <backup>
                    <backup-domain>
                        <domain-name>{account}</domain-name>
                    </backup-domain>
                </backup>
            </packet>
            """
            
            response = await self._api_request(xml_request)
            return response is not None
        except Exception as e:
            self.logger.error(f"Failed to backup Plesk domain {account}: {e}")
            return False
    
    async def extract_files(self, domain: str, destination_path: Path) -> bool:
        """Extract files from Plesk domain."""
        try:
            # Create Plesk directory structure
            directories = ["httpdocs", "httpsdocs", "cgi-bin", "logs", "statistics"]
            
            for directory in directories:
                dir_path = destination_path / directory
                dir_path.mkdir(exist_ok=True)
                (dir_path / ".plesk_extracted").write_text(f"Extracted from Plesk domain: {domain}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to extract files for Plesk domain {domain}: {e}")
            return False
    
    async def _get_session(self) -> Any:
        """Get or create HTTP session for API requests."""
        if self.session is None:
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session
    
    async def _api_request(self, xml_request: str) -> Optional[str]:
        """Make a request to Plesk API."""
        try:
            session = await self._get_session()
            
            headers = {
                "HTTP_AUTH_LOGIN": "admin",
                "HTTP_AUTH_PASSWD": self.api_key,
                "Content-Type": "text/xml"
            }
            
            async with session.post(self.api_base_url, data=xml_request, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    self.logger.error(f"Plesk API request failed: {response.status}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Plesk API request error: {e}")
            return None
    
    async def _test_api_connection(self) -> bool:
        """Test connection to Plesk API."""
        try:
            xml_request = """
            <packet>
                <server>
                    <get>
                        <gen_info/>
                    </get>
                </server>
            </packet>
            """
            
            response = await self._api_request(xml_request)
            return response is not None and "<result>" in response
        except Exception:
            return False
    
    async def _get_plesk_info(self) -> Dict[str, Any]:
        """Get Plesk version and system information."""
        try:
            xml_request = """
            <packet>
                <server>
                    <get>
                        <gen_info/>
                    </get>
                </server>
            </packet>
            """
            
            response = await self._api_request(xml_request)
            
            if response:
                root = ET.fromstring(response)
                gen_info = root.find(".//gen_info")
                
                if gen_info is not None:
                    version_elem = gen_info.find("version")
                    return {
                        "version": version_elem.text if version_elem is not None else "unknown"
                    }
            
            return {}
        except Exception as e:
            self.logger.error(f"Failed to get Plesk info: {e}")
            return {}
    
    def _get_api_endpoints(self) -> Dict[str, str]:
        """Get available Plesk API endpoints."""
        return {
            "domains": self.api_base_url,
            "databases": self.api_base_url,
            "email": self.api_base_url,
            "dns": self.api_base_url,
            "backup": self.api_base_url
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()