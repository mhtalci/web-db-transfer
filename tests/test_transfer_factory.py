"""
Unit tests for transfer method factory.

Tests the TransferMethodFactory class and method registration.
"""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock

from migration_assistant.transfer.factory import (
    TransferMethodFactory,
    register_transfer_method
)
from migration_assistant.transfer.base import TransferMethod, TransferResult, TransferStatus


class MockTransferMethod(TransferMethod):
    """Mock transfer method for testing."""
    
    SUPPORTED_SCHEMES = ['mock://']
    REQUIRED_CONFIG = ['host']
    OPTIONAL_CONFIG = ['port', 'timeout']
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validate_config_called = False
        self.test_connection_called = False
        self.cleanup_called = False
    
    async def validate_config(self) -> bool:
        self.validate_config_called = True
        return True
    
    async def test_connection(self) -> bool:
        self.test_connection_called = True
        return True
    
    async def transfer_file(self, source, destination, **kwargs) -> TransferResult:
        return TransferResult(
            success=True,
            status=TransferStatus.COMPLETED,
            progress=self._progress,
            transferred_files=[str(source)],
            failed_files=[]
        )
    
    async def transfer_directory(self, source, destination, recursive=True, **kwargs) -> TransferResult:
        return TransferResult(
            success=True,
            status=TransferStatus.COMPLETED,
            progress=self._progress,
            transferred_files=[str(source)],
            failed_files=[]
        )
    
    async def cleanup(self) -> None:
        self.cleanup_called = True


class InvalidTransferMethod:
    """Invalid transfer method that doesn't inherit from TransferMethod."""
    pass


class TestTransferMethodFactory:
    """Test TransferMethodFactory class."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear registry before each test
        TransferMethodFactory._transfer_methods.clear()
    
    def test_register_method(self):
        """Test method registration."""
        TransferMethodFactory.register_method('mock', MockTransferMethod)
        
        assert 'mock' in TransferMethodFactory._transfer_methods
        assert TransferMethodFactory._transfer_methods['mock'] == MockTransferMethod
    
    def test_register_method_case_insensitive(self):
        """Test method registration is case insensitive."""
        TransferMethodFactory.register_method('MOCK', MockTransferMethod)
        
        assert 'mock' in TransferMethodFactory._transfer_methods
        assert 'MOCK' not in TransferMethodFactory._transfer_methods
    
    def test_get_available_methods(self):
        """Test getting available methods."""
        TransferMethodFactory.register_method('mock1', MockTransferMethod)
        TransferMethodFactory.register_method('mock2', MockTransferMethod)
        
        methods = TransferMethodFactory.get_available_methods()
        
        assert 'mock1' in methods
        assert 'mock2' in methods
        assert len(methods) == 2
    
    def test_get_available_methods_empty(self):
        """Test getting available methods when none registered."""
        methods = TransferMethodFactory.get_available_methods()
        assert methods == []
    
    def test_create_transfer_method_success(self):
        """Test successful transfer method creation."""
        TransferMethodFactory.register_method('mock', MockTransferMethod)
        config = {'host': 'example.com', 'port': 22}
        
        method = TransferMethodFactory.create_transfer_method('mock', config)
        
        assert isinstance(method, MockTransferMethod)
        assert method.config == config
    
    def test_create_transfer_method_case_insensitive(self):
        """Test transfer method creation is case insensitive."""
        TransferMethodFactory.register_method('mock', MockTransferMethod)
        config = {'host': 'example.com'}
        
        method = TransferMethodFactory.create_transfer_method('MOCK', config)
        
        assert isinstance(method, MockTransferMethod)
        assert method.config == config
    
    def test_create_transfer_method_unsupported(self):
        """Test creating unsupported transfer method."""
        with pytest.raises(ValueError) as exc_info:
            TransferMethodFactory.create_transfer_method('unsupported', {})
        
        assert "Unsupported transfer method: unsupported" in str(exc_info.value)
        assert "Available methods:" in str(exc_info.value)
    
    def test_create_transfer_method_invalid_config(self):
        """Test creating transfer method with invalid config."""
        # Mock a transfer method that raises exception on initialization
        class FailingTransferMethod(TransferMethod):
            def __init__(self, config):
                raise ValueError("Invalid config")
            
            async def validate_config(self): pass
            async def test_connection(self): pass
            async def transfer_file(self, source, destination, **kwargs): pass
            async def transfer_directory(self, source, destination, recursive=True, **kwargs): pass
            async def cleanup(self): pass
        
        TransferMethodFactory.register_method('failing', FailingTransferMethod)
        
        with pytest.raises(TypeError) as exc_info:
            TransferMethodFactory.create_transfer_method('failing', {})
        
        assert "Failed to create transfer method failing" in str(exc_info.value)
    
    def test_create_from_url_ssh(self):
        """Test creating transfer method from SSH URL."""
        TransferMethodFactory.register_method('ssh', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('ssh://user@example.com/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'ssh://user@example.com/path'
    
    def test_create_from_url_sftp(self):
        """Test creating transfer method from SFTP URL."""
        TransferMethodFactory.register_method('ssh', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('sftp://user@example.com/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'sftp://user@example.com/path'
    
    def test_create_from_url_scp(self):
        """Test creating transfer method from SCP URL."""
        TransferMethodFactory.register_method('ssh', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('scp://user@example.com/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'scp://user@example.com/path'
    
    def test_create_from_url_ftp(self):
        """Test creating transfer method from FTP URL."""
        TransferMethodFactory.register_method('ftp', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('ftp://user@example.com/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'ftp://user@example.com/path'
    
    def test_create_from_url_ftps(self):
        """Test creating transfer method from FTPS URL."""
        TransferMethodFactory.register_method('ftp', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('ftps://user@example.com/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'ftps://user@example.com/path'
    
    def test_create_from_url_s3(self):
        """Test creating transfer method from S3 URL."""
        TransferMethodFactory.register_method('s3', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('s3://bucket/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 's3://bucket/path'
    
    def test_create_from_url_gcs(self):
        """Test creating transfer method from GCS URL."""
        TransferMethodFactory.register_method('gcs', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('gs://bucket/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'gs://bucket/path'
    
    def test_create_from_url_azure(self):
        """Test creating transfer method from Azure URL."""
        TransferMethodFactory.register_method('azure', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('azure://container/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'azure://container/path'
    
    def test_create_from_url_azure_blob(self):
        """Test creating transfer method from Azure Blob URL."""
        TransferMethodFactory.register_method('azure', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('https://account.blob.core.windows.net/container/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'https://account.blob.core.windows.net/container/path'
    
    def test_create_from_url_docker(self):
        """Test creating transfer method from Docker URL."""
        TransferMethodFactory.register_method('docker', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('docker://container/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'docker://container/path'
    
    def test_create_from_url_kubernetes(self):
        """Test creating transfer method from Kubernetes URL."""
        TransferMethodFactory.register_method('kubernetes', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('k8s://namespace/pod/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'k8s://namespace/pod/path'
    
    def test_create_from_url_kubernetes_full(self):
        """Test creating transfer method from full Kubernetes URL."""
        TransferMethodFactory.register_method('kubernetes', MockTransferMethod)
        
        method = TransferMethodFactory.create_from_url('kubernetes://namespace/pod/path')
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'kubernetes://namespace/pod/path'
    
    def test_create_from_url_unsupported_scheme(self):
        """Test creating transfer method from unsupported URL scheme."""
        with pytest.raises(ValueError) as exc_info:
            TransferMethodFactory.create_from_url('unsupported://example.com/path')
        
        assert "Unsupported URL scheme" in str(exc_info.value)
    
    def test_create_from_url_with_additional_config(self):
        """Test creating transfer method from URL with additional config."""
        TransferMethodFactory.register_method('ssh', MockTransferMethod)
        additional_config = {'timeout': 30, 'retries': 3}
        
        method = TransferMethodFactory.create_from_url(
            'ssh://user@example.com/path', 
            additional_config
        )
        
        assert isinstance(method, MockTransferMethod)
        assert method.config['url'] == 'ssh://user@example.com/path'
        assert method.config['timeout'] == 30
        assert method.config['retries'] == 3
    
    def test_get_method_info_success(self):
        """Test getting method information."""
        TransferMethodFactory.register_method('mock', MockTransferMethod)
        
        info = TransferMethodFactory.get_method_info('mock')
        
        assert info['name'] == 'mock'
        assert info['class'] == 'MockTransferMethod'
        assert 'module' in info
        assert 'description' in info
        assert info['supported_schemes'] == ['mock://']
        assert info['required_config'] == ['host']
        assert info['optional_config'] == ['port', 'timeout']
    
    def test_get_method_info_unsupported(self):
        """Test getting information for unsupported method."""
        with pytest.raises(ValueError) as exc_info:
            TransferMethodFactory.get_method_info('unsupported')
        
        assert "Unsupported transfer method: unsupported" in str(exc_info.value)
    
    def test_get_method_info_missing_attributes(self):
        """Test getting method information when attributes are missing."""
        class MinimalTransferMethod(TransferMethod):
            async def validate_config(self): pass
            async def test_connection(self): pass
            async def transfer_file(self, source, destination, **kwargs): pass
            async def transfer_directory(self, source, destination, recursive=True, **kwargs): pass
            async def cleanup(self): pass
        
        TransferMethodFactory.register_method('minimal', MinimalTransferMethod)
        
        info = TransferMethodFactory.get_method_info('minimal')
        
        assert info['name'] == 'minimal'
        assert info['class'] == 'MinimalTransferMethod'
        assert info['supported_schemes'] == []
        assert info['required_config'] == []
        assert info['optional_config'] == []


class TestRegisterTransferMethodDecorator:
    """Test register_transfer_method decorator."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear registry before each test
        TransferMethodFactory._transfer_methods.clear()
    
    def test_decorator_registration(self):
        """Test decorator registers method correctly."""
        @register_transfer_method('decorated')
        class DecoratedTransferMethod(MockTransferMethod):
            pass
        
        assert 'decorated' in TransferMethodFactory._transfer_methods
        assert TransferMethodFactory._transfer_methods['decorated'] == DecoratedTransferMethod
    
    def test_decorator_returns_class(self):
        """Test decorator returns the original class."""
        @register_transfer_method('decorated')
        class DecoratedTransferMethod(MockTransferMethod):
            pass
        
        # Should be able to instantiate the class normally
        instance = DecoratedTransferMethod({'host': 'example.com'})
        assert isinstance(instance, DecoratedTransferMethod)
    
    def test_decorator_multiple_methods(self):
        """Test decorator with multiple methods."""
        @register_transfer_method('method1')
        class Method1(MockTransferMethod):
            pass
        
        @register_transfer_method('method2')
        class Method2(MockTransferMethod):
            pass
        
        assert 'method1' in TransferMethodFactory._transfer_methods
        assert 'method2' in TransferMethodFactory._transfer_methods
        assert TransferMethodFactory._transfer_methods['method1'] == Method1
        assert TransferMethodFactory._transfer_methods['method2'] == Method2