"""Tests for security module."""

import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet

from migration_assistant.security.credential_manager import CredentialManager, Credential
from migration_assistant.security.data_sanitizer import DataSanitizer, SensitivityLevel
from migration_assistant.security.encryption import EncryptionManager
from migration_assistant.security.scanner import SecurityScanner, VulnerabilitySeverity
from migration_assistant.core.exceptions import SecurityError


class TestCredentialManager:
    """Test credential management functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.credential_manager = CredentialManager("test_service")
    
    def test_store_and_retrieve_credential(self):
        """Test storing and retrieving credentials."""
        service = "test_db"
        username = "testuser"
        password = "testpass"
        metadata = {"host": "localhost", "port": 5432}
        
        # Store credential
        result = self.credential_manager.store_credential(
            service, username, password, metadata
        )
        assert result is True
        
        # Retrieve credential
        credential = self.credential_manager.get_credential(service, username)
        assert credential is not None
        assert credential.username == username
        assert credential.password == password
        assert credential.service == service
        assert credential.metadata == metadata
    
    def test_credential_not_found(self):
        """Test retrieving non-existent credential."""
        credential = self.credential_manager.get_credential("nonexistent", "user")
        assert credential is None
    
    def test_delete_credential(self):
        """Test deleting credentials."""
        service = "test_service"
        username = "testuser"
        password = "testpass"
        
        # Store and then delete
        self.credential_manager.store_credential(service, username, password)
        result = self.credential_manager.delete_credential(service, username)
        assert result is True
        
        # Verify deletion
        credential = self.credential_manager.get_credential(service, username)
        assert credential is None
    
    def test_encrypted_data_storage(self):
        """Test encrypted data storage and retrieval."""
        service = "encrypted_test"
        data = {"api_key": "secret123", "config": {"timeout": 30}}
        password = "encryption_password"
        
        # Store encrypted data
        result = self.credential_manager.store_encrypted_data(service, data, password)
        assert result is True
        
        # Retrieve encrypted data
        retrieved_data = self.credential_manager.get_encrypted_data(service, password)
        assert retrieved_data == data
    
    def test_encrypted_data_wrong_password(self):
        """Test encrypted data retrieval with wrong password."""
        service = "encrypted_test"
        data = {"secret": "value"}
        password = "correct_password"
        wrong_password = "wrong_password"
        
        self.credential_manager.store_encrypted_data(service, data, password)
        retrieved_data = self.credential_manager.get_encrypted_data(service, wrong_password)
        assert retrieved_data is None
    
    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_keyring_availability(self, mock_get, mock_set):
        """Test keyring availability check."""
        mock_set.return_value = None
        mock_get.return_value = "test_password"
        
        result = self.credential_manager.test_keyring_availability()
        assert result is True
    
    def test_get_keyring_info(self):
        """Test getting keyring information."""
        info = self.credential_manager.get_keyring_info()
        assert isinstance(info, dict)
        assert "backend_name" in info


class TestDataSanitizer:
    """Test data sanitization functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.sanitizer = DataSanitizer()
    
    def test_email_sanitization(self):
        """Test email address sanitization."""
        text = "Contact us at support@example.com for help"
        sanitized = self.sanitizer.sanitize_text(text)
        assert "[EMAIL_REDACTED]" in sanitized
        assert "support@example.com" not in sanitized
    
    def test_phone_sanitization(self):
        """Test phone number sanitization."""
        text = "Call us at (555) 123-4567 or 555.123.4567"
        sanitized = self.sanitizer.sanitize_text(text)
        assert "[PHONE_REDACTED]" in sanitized
        assert "555" not in sanitized
    
    def test_credit_card_sanitization(self):
        """Test credit card number sanitization."""
        text = "Card number: 4532 1234 5678 9012"
        sanitized = self.sanitizer.sanitize_text(text)
        assert "[CREDIT_CARD_REDACTED]" in sanitized
        assert "4532" not in sanitized
    
    def test_ip_address_sanitization(self):
        """Test IP address sanitization."""
        text = "Server IP: 192.168.1.100"
        sanitized = self.sanitizer.sanitize_text(text)
        assert "[IP_REDACTED]" in sanitized
        assert "192.168.1.100" not in sanitized
    
    def test_database_connection_sanitization(self):
        """Test database connection string sanitization."""
        text = "mysql://user:password@localhost:3306/db"
        sanitized = self.sanitizer.sanitize_text(text)
        assert "[USER_REDACTED]" in sanitized
        assert "[PASSWORD_REDACTED]" in sanitized
        assert "[HOST_REDACTED]" in sanitized
        assert "user:password" not in sanitized
    
    def test_api_key_sanitization(self):
        """Test API key sanitization."""
        text = 'api_key="sk-1234567890abcdef1234567890abcdef"'
        sanitized = self.sanitizer.sanitize_text(text)
        assert "[API_KEY_REDACTED]" in sanitized
        assert "sk-1234567890abcdef1234567890abcdef" not in sanitized
    
    def test_sensitivity_levels(self):
        """Test different sensitivity levels."""
        text = "Email: test@example.com, IP: 192.168.1.1, SSN: 123-45-6789"
        
        # Low sensitivity - only IP addresses
        low_sanitized = self.sanitizer.sanitize_text(text, SensitivityLevel.LOW)
        assert "[IP_REDACTED]" in low_sanitized
        assert "test@example.com" in low_sanitized  # Email not sanitized at low level
        
        # Critical sensitivity - everything
        critical_sanitized = self.sanitizer.sanitize_text(text, SensitivityLevel.CRITICAL)
        assert "[EMAIL_REDACTED]" in critical_sanitized
        assert "[IP_REDACTED]" in critical_sanitized
        assert "[SSN_REDACTED]" in critical_sanitized
    
    def test_dict_sanitization(self):
        """Test dictionary sanitization."""
        data = {
            "user_email": "test@example.com",
            "server_ip": "192.168.1.1",
            "nested": {
                "api_key": "secret123456789012345678901234567890"
            }
        }
        
        sanitized = self.sanitizer.sanitize_dict(data)
        assert "[EMAIL_REDACTED]" in str(sanitized)
        assert "[IP_REDACTED]" in str(sanitized)
        assert "[API_KEY_REDACTED]" in str(sanitized)
    
    def test_list_sanitization(self):
        """Test list sanitization."""
        data = [
            "test@example.com",
            "192.168.1.1",
            {"password": "secret123"}
        ]
        
        sanitized = self.sanitizer.sanitize_list(data)
        assert "[EMAIL_REDACTED]" in str(sanitized)
        assert "[IP_REDACTED]" in str(sanitized)
        assert "[PASSWORD_REDACTED]" in str(sanitized)
    
    def test_custom_rule(self):
        """Test adding custom sanitization rules."""
        self.sanitizer.add_rule(
            pattern=r'custom-\d{6}',
            replacement='[CUSTOM_REDACTED]',
            sensitivity=SensitivityLevel.MEDIUM,
            description='Custom pattern'
        )
        
        text = "Code: custom-123456"
        sanitized = self.sanitizer.sanitize_text(text)
        assert "[CUSTOM_REDACTED]" in sanitized
        assert "custom-123456" not in sanitized
    
    def test_sanitization_report(self):
        """Test sanitization reporting."""
        text = "Email: test@example.com, Phone: (555) 123-4567"
        report = self.sanitizer.get_sanitization_report(text)
        
        assert report["original_length"] > 0
        assert report["sanitized_length"] > 0
        assert len(report["rules_applied"]) > 0
        assert report["reduction_ratio"] >= 0


class TestEncryptionManager:
    """Test encryption functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.encryption_manager = EncryptionManager()
    
    def test_key_generation(self):
        """Test encryption key generation."""
        key = self.encryption_manager.generate_key()
        assert isinstance(key, bytes)
        assert len(key) > 0
        
        # Verify it's a valid Fernet key
        fernet = Fernet(key)
        assert fernet is not None
    
    def test_password_key_derivation(self):
        """Test key derivation from password."""
        password = "test_password"
        salt = b"test_salt_16byte"
        
        key1 = self.encryption_manager.derive_key_from_password(password, salt)
        key2 = self.encryption_manager.derive_key_from_password(password, salt)
        
        # Same password and salt should produce same key
        assert key1 == key2
        
        # Different salt should produce different key
        key3 = self.encryption_manager.derive_key_from_password(password, b"different_salt16")
        assert key1 != key3
    
    def test_symmetric_encryption(self):
        """Test symmetric encryption and decryption."""
        key = self.encryption_manager.generate_key()
        data = "This is secret data"
        
        # Encrypt
        encrypted = self.encryption_manager.encrypt_data(data, key)
        assert isinstance(encrypted, bytes)
        assert encrypted != data.encode()
        
        # Decrypt
        decrypted = self.encryption_manager.decrypt_data(encrypted, key)
        assert decrypted == data
    
    def test_dict_encryption(self):
        """Test dictionary encryption and decryption."""
        key = self.encryption_manager.generate_key()
        data = {"username": "test", "password": "secret", "port": 5432}
        
        encrypted = self.encryption_manager.encrypt_data(data, key)
        decrypted = self.encryption_manager.decrypt_data(encrypted, key, return_type='json')
        
        assert decrypted == data
    
    def test_rsa_keypair_generation(self):
        """Test RSA key pair generation."""
        private_pem, public_pem = self.encryption_manager.generate_rsa_keypair()
        
        assert isinstance(private_pem, bytes)
        assert isinstance(public_pem, bytes)
        assert b"BEGIN PRIVATE KEY" in private_pem
        assert b"BEGIN PUBLIC KEY" in public_pem
    
    def test_rsa_encryption(self):
        """Test RSA encryption and decryption."""
        private_pem, public_pem = self.encryption_manager.generate_rsa_keypair()
        
        # Load keys
        self.encryption_manager.load_private_key(private_pem)
        self.encryption_manager.load_public_key(public_pem)
        
        # Test encryption/decryption
        data = "Secret message"
        encrypted = self.encryption_manager.encrypt_with_public_key(data)
        decrypted = self.encryption_manager.decrypt_with_private_key(encrypted)
        
        assert decrypted.decode() == data
    
    def test_file_encryption(self):
        """Test file encryption and decryption."""
        key = self.encryption_manager.generate_key()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("This is test file content")
            test_file = f.name
        
        encrypted_file = test_file + ".enc"
        decrypted_file = test_file + ".dec"
        
        try:
            # Encrypt file
            self.encryption_manager.encrypt_file(test_file, encrypted_file, key)
            assert os.path.exists(encrypted_file)
            
            # Decrypt file
            self.encryption_manager.decrypt_file(encrypted_file, decrypted_file, key)
            assert os.path.exists(decrypted_file)
            
            # Verify content
            with open(decrypted_file, 'r') as f:
                content = f.read()
            assert content == "This is test file content"
            
        finally:
            # Cleanup
            for file_path in [test_file, encrypted_file, decrypted_file]:
                if os.path.exists(file_path):
                    os.unlink(file_path)
    
    def test_secure_token(self):
        """Test secure token creation and verification."""
        key = self.encryption_manager.generate_key()
        data = {"user_id": "123", "permissions": ["read", "write"]}
        
        # Create token
        token = self.encryption_manager.create_secure_token(data, key, expiry_seconds=3600)
        assert isinstance(token, str)
        
        # Verify token
        verified_data = self.encryption_manager.verify_secure_token(token, key)
        assert verified_data == data
    
    def test_expired_token(self):
        """Test expired token handling."""
        key = self.encryption_manager.generate_key()
        data = {"test": "data"}
        
        # Create token with very short expiry
        token = self.encryption_manager.create_secure_token(data, key, expiry_seconds=-1)
        
        # Should return None for expired token
        verified_data = self.encryption_manager.verify_secure_token(token, key)
        assert verified_data is None
    
    def test_secure_hash(self):
        """Test secure hash generation."""
        data = "test data"
        salt = b"test_salt"
        
        hash1 = self.encryption_manager.generate_secure_hash(data, salt)
        hash2 = self.encryption_manager.generate_secure_hash(data, salt)
        
        # Same data and salt should produce same hash
        assert hash1 == hash2
        
        # Different data should produce different hash
        hash3 = self.encryption_manager.generate_secure_hash("different data", salt)
        assert hash1 != hash3
    
    def test_constant_time_compare(self):
        """Test constant time comparison."""
        value1 = "secret123"
        value2 = "secret123"
        value3 = "different"
        
        assert self.encryption_manager.constant_time_compare(value1, value2) is True
        assert self.encryption_manager.constant_time_compare(value1, value3) is False


class TestSecurityScanner:
    """Test security scanning functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.scanner = SecurityScanner()
    
    def test_python_dependency_scan(self):
        """Test Python dependency scanning."""
        result = self.scanner.scan_python_dependencies()
        
        assert result.scan_type == "python_dependencies"
        assert result.success is True
        assert result.total_packages > 0
        assert isinstance(result.vulnerabilities, list)
    
    def test_go_binary_scan_nonexistent(self):
        """Test Go binary scan with non-existent file."""
        result = self.scanner.scan_go_binary("/nonexistent/binary")
        
        assert result.scan_type == "go_binary"
        assert result.success is False
        assert "not found" in result.error_message.lower()
    
    def test_system_dependency_scan(self):
        """Test system dependency scanning."""
        result = self.scanner.scan_system_dependencies()
        
        assert result.scan_type == "system_dependencies"
        assert result.success is True
        assert isinstance(result.vulnerabilities, list)
    
    def test_file_hash_calculation(self):
        """Test file hash calculation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            test_file = f.name
        
        try:
            hash_value = self.scanner._calculate_file_hash(test_file)
            assert isinstance(hash_value, str)
            assert len(hash_value) == 64  # SHA-256 hex length
        finally:
            os.unlink(test_file)
    
    def test_security_report_generation(self):
        """Test security report generation."""
        # Create mock scan results
        scan_results = [
            self.scanner.scan_python_dependencies(),
            self.scanner.scan_system_dependencies()
        ]
        
        report = self.scanner.generate_security_report(scan_results)
        
        assert "scan_timestamp" in report
        assert "total_vulnerabilities" in report
        assert "risk_score" in report
        assert "severity_breakdown" in report
        assert "scan_summary" in report
        assert "vulnerabilities" in report
        assert "recommendations" in report
    
    @patch('subprocess.run')
    def test_tool_availability_check(self, mock_run):
        """Test system tool availability checking."""
        # Mock successful tool check
        mock_run.return_value = MagicMock(returncode=0)
        assert self.scanner._check_tool_available("ssh") is True
        
        # Mock failed tool check
        mock_run.return_value = MagicMock(returncode=1)
        assert self.scanner._check_tool_available("nonexistent_tool") is False
    
    def test_vulnerability_severity_handling(self):
        """Test vulnerability severity handling."""
        from migration_assistant.security.scanner import Vulnerability
        
        vuln = Vulnerability(
            id="TEST-001",
            package="test_package",
            version="1.0.0",
            severity=VulnerabilitySeverity.HIGH,
            description="Test vulnerability"
        )
        
        assert vuln.severity == VulnerabilitySeverity.HIGH
        assert vuln.severity.value == "high"


@pytest.fixture
def temp_keyring_backend():
    """Fixture to use a temporary keyring backend for testing."""
    import keyring
    from keyring.backends import file
    
    # Save original backend
    original_backend = keyring.get_keyring()
    
    # Set up temporary file backend
    temp_backend = file.PlaintextKeyring()
    keyring.set_keyring(temp_backend)
    
    yield temp_backend
    
    # Restore original backend
    keyring.set_keyring(original_backend)


class TestIntegration:
    """Integration tests for security components."""
    
    def test_credential_manager_with_encryption(self, temp_keyring_backend):
        """Test credential manager with encryption integration."""
        credential_manager = CredentialManager("integration_test")
        encryption_manager = EncryptionManager()
        
        # Store encrypted credential
        service = "test_service"
        username = "testuser"
        password = "testpass"
        
        # Encrypt password before storing
        key = encryption_manager.generate_key()
        encrypted_password = encryption_manager.encrypt_data(password, key)
        
        # Store the key securely (in practice, this would be done differently)
        credential_manager.store_credential(
            f"{service}_key", 
            username, 
            key.decode('utf-8')
        )
        
        # Store encrypted password
        credential_manager.store_credential(
            service, 
            username, 
            encrypted_password.decode('latin-1')
        )
        
        # Retrieve and decrypt
        stored_key = credential_manager.get_credential(f"{service}_key", username)
        stored_encrypted = credential_manager.get_credential(service, username)
        
        assert stored_key is not None
        assert stored_encrypted is not None
        
        # Decrypt password
        decrypted_password = encryption_manager.decrypt_data(
            stored_encrypted.password.encode('latin-1'),
            stored_key.password.encode('utf-8')
        )
        
        assert decrypted_password == password
    
    def test_sanitizer_with_encryption(self):
        """Test data sanitizer with encryption integration."""
        sanitizer = DataSanitizer()
        encryption_manager = EncryptionManager()
        
        # Sensitive data
        data = {
            "email": "user@example.com",
            "password": "secret123",
            "api_key": "sk-1234567890abcdef1234567890abcdef"
        }
        
        # Sanitize data
        sanitized_data = sanitizer.sanitize_dict(data)
        
        # Encrypt sanitized data
        key = encryption_manager.generate_key()
        encrypted_data = encryption_manager.encrypt_data(sanitized_data, key)
        
        # Decrypt and verify
        decrypted_data = encryption_manager.decrypt_data(encrypted_data, key, return_type='json')
        
        # Verify sensitive data was sanitized
        assert "[EMAIL_REDACTED]" in str(decrypted_data)
        assert "[PASSWORD_REDACTED]" in str(decrypted_data)
        assert "[API_KEY_REDACTED]" in str(decrypted_data)
        assert "user@example.com" not in str(decrypted_data)
        assert "secret123" not in str(decrypted_data)