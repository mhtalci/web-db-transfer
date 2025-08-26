"""
Unit tests for connectivity validation module.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from migration_assistant.validation.connectivity import (
    ConnectivityValidator, 
    ConnectivityCheck, 
    ValidationResult
)


class TestConnectivityValidator:
    """Test cases for ConnectivityValidator"""
    
    @pytest.fixture
    def validator(self):
        return ConnectivityValidator()
    
    @pytest.fixture
    def sample_config(self):
        return {
            'source': {
                'type': 'wordpress',
                'host': 'source.example.com',
                'port': 3306,
                'db_type': 'mysql',
                'db_user': 'root',
                'db_password': 'password',
                'db_name': 'wordpress'
            },
            'destination': {
                'type': 'aws-s3',
                'host': 's3.amazonaws.com',
                'db_type': 'aurora-mysql',
                'cloud_config': {
                    'provider': 'aws',
                    'region': 'us-east-1',
                    'access_key_id': 'AKIATEST',
                    'secret_access_key': 'test-secret'
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_validate_all_success(self, validator, sample_config):
        """Test successful validation of all systems"""
        with patch.object(validator, '_validate_system') as mock_validate:
            mock_validate.side_effect = [
                [ConnectivityCheck('test1', ValidationResult.SUCCESS, 'OK')],
                [ConnectivityCheck('test2', ValidationResult.SUCCESS, 'OK')]
            ]
            
            results = await validator.validate_all(sample_config)
            
            assert len(results) == 2
            assert all(check.result == ValidationResult.SUCCESS for check in results)
            assert mock_validate.call_count == 2
    
    @pytest.mark.asyncio
    async def test_network_connectivity_success(self, validator):
        """Test successful network connectivity check"""
        with patch('socket.gethostbyname') as mock_resolve, \
             patch('socket.socket') as mock_socket:
            
            mock_resolve.return_value = '192.168.1.1'
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock
            
            result = await validator._check_network_connectivity('example.com', 80, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected' in result.message
    
    @pytest.mark.asyncio
    async def test_network_connectivity_dns_failure(self, validator):
        """Test network connectivity with DNS resolution failure"""
        import socket
        
        with patch('socket.gethostbyname') as mock_resolve:
            mock_resolve.side_effect = socket.gaierror("Name resolution failed")
            
            result = await validator._check_network_connectivity('invalid.host', 80, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'Failed to resolve hostname' in result.message
            assert result.remediation is not None
    
    @pytest.mark.asyncio
    async def test_network_connectivity_port_failure(self, validator):
        """Test network connectivity with port connection failure"""
        with patch('socket.gethostbyname') as mock_resolve, \
             patch('socket.socket') as mock_socket:
            
            mock_resolve.return_value = '192.168.1.1'
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 1  # Connection failed
            mock_socket.return_value = mock_sock
            
            result = await validator._check_network_connectivity('example.com', 80, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'Cannot connect' in result.message
    
    @pytest.mark.asyncio
    async def test_mysql_connectivity_success(self, validator):
        """Test successful MySQL connectivity"""
        config = {
            'host': 'localhost',
            'port': 3306,
            'db_user': 'root',
            'db_password': 'password',
            'db_name': 'test'
        }
        
        with patch('migration_assistant.validation.connectivity.MYSQL_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.mysql') as mock_mysql:
            
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_connection.cursor.return_value = mock_cursor
            mock_mysql.connector.connect.return_value = mock_connection
            
            result = await validator._check_mysql_connectivity(config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected to MySQL' in result.message
            mock_cursor.execute.assert_called_once_with("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_mysql_connectivity_not_available(self, validator):
        """Test MySQL connectivity when library not available"""
        config = {'host': 'localhost'}
        
        with patch('migration_assistant.validation.connectivity.MYSQL_AVAILABLE', False):
            result = await validator._check_mysql_connectivity(config, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'mysql-connector-python not installed' in result.message
            assert 'pip install mysql-connector-python' in result.remediation
    
    @pytest.mark.asyncio
    async def test_mysql_connectivity_connection_error(self, validator):
        """Test MySQL connectivity with connection error"""
        config = {
            'host': 'localhost',
            'db_user': 'root',
            'db_password': 'wrong_password'
        }
        
        with patch('migration_assistant.validation.connectivity.MYSQL_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.mysql') as mock_mysql:
            
            # Create a proper exception class that inherits from Exception
            class MockMySQLError(Exception):
                pass
            
            mock_mysql.connector.Error = MockMySQLError
            mock_mysql.connector.connect.side_effect = MockMySQLError("Access denied")
            
            result = await validator._check_mysql_connectivity(config, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'MySQL connection failed' in result.message
            assert result.remediation is not None
    
    @pytest.mark.asyncio
    async def test_postgresql_connectivity_success(self, validator):
        """Test successful PostgreSQL connectivity"""
        config = {
            'host': 'localhost',
            'port': 5432,
            'db_user': 'postgres',
            'db_password': 'password',
            'db_name': 'test'
        }
        
        with patch('migration_assistant.validation.connectivity.POSTGRESQL_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.psycopg2') as mock_psycopg2:
            
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_connection.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_connection
            
            result = await validator._check_postgresql_connectivity(config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected to PostgreSQL' in result.message
    
    @pytest.mark.asyncio
    async def test_postgresql_connectivity_not_available(self, validator):
        """Test PostgreSQL connectivity when library not available"""
        config = {'host': 'localhost'}
        
        with patch('migration_assistant.validation.connectivity.POSTGRESQL_AVAILABLE', False):
            result = await validator._check_postgresql_connectivity(config, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'psycopg2 not installed' in result.message
    
    @pytest.mark.asyncio
    async def test_mongodb_connectivity_success(self, validator):
        """Test successful MongoDB connectivity"""
        config = {
            'host': 'localhost',
            'port': 27017,
            'db_user': 'admin',
            'db_password': 'password'
        }
        
        with patch('migration_assistant.validation.connectivity.MONGODB_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.pymongo') as mock_pymongo:
            
            mock_client = Mock()
            mock_pymongo.MongoClient.return_value = mock_client
            
            result = await validator._check_mongodb_connectivity(config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected to MongoDB' in result.message
            mock_client.admin.command.assert_called_once_with('ping')
    
    @pytest.mark.asyncio
    async def test_redis_connectivity_success(self, validator):
        """Test successful Redis connectivity"""
        config = {
            'host': 'localhost',
            'port': 6379,
            'db_password': 'password'
        }
        
        with patch('migration_assistant.validation.connectivity.REDIS_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.redis') as mock_redis:
            
            mock_client = Mock()
            mock_redis.Redis.return_value = mock_client
            
            result = await validator._check_redis_connectivity(config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected to Redis' in result.message
            mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sqlite_connectivity_success(self, validator):
        """Test successful SQLite connectivity"""
        config = {'db_path': '/tmp/test.db'}
        
        with patch('os.path.exists', return_value=True), \
             patch('sqlite3.connect') as mock_connect:
            
            mock_connection = Mock()
            mock_cursor = Mock()
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection
            
            result = await validator._check_sqlite_connectivity(config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected to SQLite' in result.message
    
    @pytest.mark.asyncio
    async def test_sqlite_connectivity_file_not_found(self, validator):
        """Test SQLite connectivity when file doesn't exist"""
        config = {'db_path': '/tmp/nonexistent.db'}
        
        with patch('os.path.exists', return_value=False):
            result = await validator._check_sqlite_connectivity(config, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'database file not found' in result.message
    
    @pytest.mark.asyncio
    async def test_ssh_connectivity_success(self, validator):
        """Test successful SSH connectivity"""
        config = {
            'host': 'example.com',
            'ssh_config': {
                'username': 'user',
                'password': 'password'
            }
        }
        
        with patch('migration_assistant.validation.connectivity.SSH_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.paramiko') as mock_paramiko:
            
            mock_client = Mock()
            mock_stdout = Mock()
            mock_stdout.read.return_value = b'test'
            mock_client.exec_command.return_value = (None, mock_stdout, None)
            mock_paramiko.SSHClient.return_value = mock_client
            
            result = await validator._check_ssh_connectivity(config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected via SSH' in result.message
    
    @pytest.mark.asyncio
    async def test_ssh_connectivity_auth_failure(self, validator):
        """Test SSH connectivity with authentication failure"""
        config = {
            'host': 'example.com',
            'ssh_config': {
                'username': 'user',
                'password': 'wrong_password'
            }
        }
        
        with patch('migration_assistant.validation.connectivity.SSH_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.paramiko') as mock_paramiko:
            
            # Create proper exception classes
            class MockAuthException(Exception):
                pass
            
            mock_paramiko.AuthenticationException = MockAuthException
            
            mock_client = Mock()
            mock_client.connect.side_effect = MockAuthException("Authentication failed")
            mock_paramiko.SSHClient.return_value = mock_client
            
            result = await validator._check_ssh_connectivity(config, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'SSH authentication failed' in result.message
    
    @pytest.mark.asyncio
    async def test_ftp_connectivity_success(self, validator):
        """Test successful FTP connectivity"""
        config = {
            'host': 'ftp.example.com',
            'ftp_config': {
                'username': 'user',
                'password': 'password'
            }
        }
        
        with patch('migration_assistant.validation.connectivity.FTP_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.ftplib') as mock_ftplib:
            
            mock_ftp = Mock()
            mock_ftplib.FTP.return_value = mock_ftp
            
            result = await validator._check_ftp_connectivity(config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully connected via FTP' in result.message
            mock_ftp.connect.assert_called_once()
            mock_ftp.login.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_aws_connectivity_success(self, validator):
        """Test successful AWS connectivity"""
        cloud_config = {
            'provider': 'aws',
            'access_key_id': 'AKIATEST',
            'secret_access_key': 'test-secret',
            'region': 'us-east-1'
        }
        
        with patch('migration_assistant.validation.connectivity.AWS_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.boto3') as mock_boto3:
            
            mock_session = Mock()
            mock_client = Mock()
            mock_session.client.return_value = mock_client
            mock_boto3.Session.return_value = mock_session
            
            result = await validator._check_aws_connectivity(cloud_config, 'test')
            
            assert result.result == ValidationResult.SUCCESS
            assert 'Successfully authenticated with AWS' in result.message
            mock_client.list_buckets.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_aws_connectivity_no_credentials(self, validator):
        """Test AWS connectivity with no credentials"""
        cloud_config = {'provider': 'aws'}
        
        with patch('migration_assistant.validation.connectivity.AWS_AVAILABLE', True), \
             patch('migration_assistant.validation.connectivity.boto3') as mock_boto3:
            
            from botocore.exceptions import NoCredentialsError
            mock_session = Mock()
            mock_client = Mock()
            mock_client.list_buckets.side_effect = NoCredentialsError()
            mock_session.client.return_value = mock_client
            mock_boto3.Session.return_value = mock_session
            
            result = await validator._check_aws_connectivity(cloud_config, 'test')
            
            assert result.result == ValidationResult.FAILED
            assert 'AWS credentials not found' in result.message
    
    @pytest.mark.asyncio
    async def test_database_connectivity_unsupported_type(self, validator):
        """Test database connectivity with unsupported database type"""
        config = {
            'db_type': 'unsupported_db',
            'host': 'localhost'
        }
        
        result = await validator._check_database_connectivity(config, 'test')
        
        assert result.result == ValidationResult.SKIPPED
        assert 'not supported for connectivity testing' in result.message
    
    def test_requires_ssh_detection(self, validator):
        """Test SSH requirement detection"""
        # Test with ssh_config
        config1 = {'ssh_config': {'username': 'user'}}
        assert validator._requires_ssh(config1) is True
        
        # Test with transfer method
        config2 = {'transfer_method': 'ssh'}
        assert validator._requires_ssh(config2) is True
        
        # Test without SSH requirements
        config3 = {'host': 'example.com'}
        assert validator._requires_ssh(config3) is False
    
    def test_requires_ftp_detection(self, validator):
        """Test FTP requirement detection"""
        # Test with ftp_config
        config1 = {'ftp_config': {'username': 'user'}}
        assert validator._requires_ftp(config1) is True
        
        # Test with transfer method
        config2 = {'transfer_method': 'ftp'}
        assert validator._requires_ftp(config2) is True
        
        # Test without FTP requirements
        config3 = {'host': 'example.com'}
        assert validator._requires_ftp(config3) is False
    
    def test_build_postgresql_connection_string(self, validator):
        """Test PostgreSQL connection string building"""
        config = {
            'host': 'localhost',
            'port': 5432,
            'db_name': 'testdb',
            'db_user': 'postgres',
            'db_password': 'password'
        }
        
        conn_str = validator._build_postgresql_connection_string(config)
        
        assert 'host=localhost' in conn_str
        assert 'port=5432' in conn_str
        assert 'dbname=testdb' in conn_str
        assert 'user=postgres' in conn_str
        assert 'password=password' in conn_str
    
    def test_build_mongodb_connection_string(self, validator):
        """Test MongoDB connection string building"""
        # Test with authentication
        config1 = {
            'host': 'localhost',
            'port': 27017,
            'db_user': 'admin',
            'db_password': 'password',
            'db_name': 'testdb'
        }
        
        conn_str1 = validator._build_mongodb_connection_string(config1)
        assert conn_str1 == 'mongodb://admin:password@localhost:27017/testdb'
        
        # Test without authentication
        config2 = {
            'host': 'localhost',
            'port': 27017
        }
        
        conn_str2 = validator._build_mongodb_connection_string(config2)
        assert conn_str2 == 'mongodb://localhost:27017'


if __name__ == '__main__':
    pytest.main([__file__])