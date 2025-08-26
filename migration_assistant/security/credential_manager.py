"""Secure credential storage and management using keyring."""

import keyring
import json
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from ..core.exceptions import SecurityError

logger = logging.getLogger(__name__)

@dataclass
class Credential:
    """Represents a stored credential."""
    username: str
    password: str
    service: str
    metadata: Optional[Dict[str, Any]] = None

class CredentialManager:
    """Manages secure credential storage using system keyring."""
    
    def __init__(self, service_prefix: str = "migration_assistant"):
        """Initialize credential manager.
        
        Args:
            service_prefix: Prefix for service names in keyring
        """
        self.service_prefix = service_prefix
        self._encryption_key = None
        
    def _get_service_name(self, service: str) -> str:
        """Get full service name with prefix."""
        return f"{self.service_prefix}.{service}"
    
    def _get_encryption_key(self, password: str, salt: bytes = None) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt = b'migration_assistant_salt'  # In production, use random salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def store_credential(self, service: str, username: str, password: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store a credential securely in the system keyring.
        
        Args:
            service: Service identifier (e.g., 'source_db', 'destination_ftp')
            username: Username for the service
            password: Password for the service
            metadata: Optional metadata to store with credential
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            service_name = self._get_service_name(service)
            
            # Store the main password
            keyring.set_password(service_name, username, password)
            
            # Store metadata if provided
            if metadata:
                metadata_service = f"{service_name}.metadata"
                metadata_json = json.dumps(metadata)
                keyring.set_password(metadata_service, username, metadata_json)
            
            logger.info(f"Credential stored for service: {service}, user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credential for {service}: {e}")
            raise SecurityError(f"Failed to store credential: {e}")
    
    def get_credential(self, service: str, username: str) -> Optional[Credential]:
        """Retrieve a credential from the system keyring.
        
        Args:
            service: Service identifier
            username: Username for the service
            
        Returns:
            Credential object if found, None otherwise
        """
        try:
            service_name = self._get_service_name(service)
            
            # Get the main password
            password = keyring.get_password(service_name, username)
            if password is None:
                return None
            
            # Get metadata if available
            metadata = None
            try:
                metadata_service = f"{service_name}.metadata"
                metadata_json = keyring.get_password(metadata_service, username)
                if metadata_json:
                    metadata = json.loads(metadata_json)
            except Exception as e:
                logger.warning(f"Failed to retrieve metadata for {service}: {e}")
            
            return Credential(
                username=username,
                password=password,
                service=service,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to retrieve credential for {service}: {e}")
            return None
    
    def delete_credential(self, service: str, username: str) -> bool:
        """Delete a credential from the system keyring.
        
        Args:
            service: Service identifier
            username: Username for the service
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            service_name = self._get_service_name(service)
            
            # Delete the main password
            keyring.delete_password(service_name, username)
            
            # Delete metadata if exists
            try:
                metadata_service = f"{service_name}.metadata"
                keyring.delete_password(metadata_service, username)
            except keyring.errors.PasswordDeleteError:
                # Metadata doesn't exist, which is fine
                pass
            
            logger.info(f"Credential deleted for service: {service}, user: {username}")
            return True
            
        except keyring.errors.PasswordDeleteError:
            logger.warning(f"Credential not found for {service}, user: {username}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete credential for {service}: {e}")
            raise SecurityError(f"Failed to delete credential: {e}")
    
    def list_services(self) -> List[str]:
        """List all services with stored credentials.
        
        Note: This is a best-effort implementation as keyring doesn't
        provide a standard way to list all stored credentials.
        
        Returns:
            List of service names
        """
        # This is a limitation of the keyring library - it doesn't provide
        # a standard way to enumerate stored credentials across all backends
        logger.warning("Service enumeration not supported by keyring backend")
        return []
    
    def store_encrypted_data(self, service: str, data: Dict[str, Any], 
                           encryption_password: str) -> bool:
        """Store encrypted data using Fernet encryption.
        
        Args:
            service: Service identifier
            data: Data to encrypt and store
            encryption_password: Password for encryption
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            # Generate encryption key
            key = self._get_encryption_key(encryption_password)
            fernet = Fernet(key)
            
            # Encrypt the data
            data_json = json.dumps(data)
            encrypted_data = fernet.encrypt(data_json.encode())
            encrypted_b64 = base64.b64encode(encrypted_data).decode()
            
            # Store in keyring
            service_name = self._get_service_name(f"{service}.encrypted")
            keyring.set_password(service_name, "encrypted_data", encrypted_b64)
            
            logger.info(f"Encrypted data stored for service: {service}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store encrypted data for {service}: {e}")
            raise SecurityError(f"Failed to store encrypted data: {e}")
    
    def get_encrypted_data(self, service: str, encryption_password: str) -> Optional[Dict[str, Any]]:
        """Retrieve and decrypt stored data.
        
        Args:
            service: Service identifier
            encryption_password: Password for decryption
            
        Returns:
            Decrypted data if successful, None otherwise
        """
        try:
            # Get encrypted data from keyring
            service_name = self._get_service_name(f"{service}.encrypted")
            encrypted_b64 = keyring.get_password(service_name, "encrypted_data")
            
            if encrypted_b64 is None:
                return None
            
            # Decrypt the data
            key = self._get_encryption_key(encryption_password)
            fernet = Fernet(key)
            
            encrypted_data = base64.b64decode(encrypted_b64.encode())
            decrypted_data = fernet.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode())
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to retrieve encrypted data for {service}: {e}")
            return None
    
    def test_keyring_availability(self) -> bool:
        """Test if keyring is available and functional.
        
        Returns:
            True if keyring is working, False otherwise
        """
        try:
            test_service = f"{self.service_prefix}.test"
            test_user = "test_user"
            test_password = "test_password"
            
            # Try to store and retrieve a test credential
            keyring.set_password(test_service, test_user, test_password)
            retrieved = keyring.get_password(test_service, test_user)
            
            # Clean up
            keyring.delete_password(test_service, test_user)
            
            return retrieved == test_password
            
        except Exception as e:
            logger.error(f"Keyring availability test failed: {e}")
            return False
    
    def get_keyring_info(self) -> Dict[str, Any]:
        """Get information about the current keyring backend.
        
        Returns:
            Dictionary with keyring information
        """
        try:
            current_keyring = keyring.get_keyring()
            return {
                "backend_name": getattr(current_keyring, 'name', str(type(current_keyring).__name__)),
                "backend_class": str(type(current_keyring).__name__),
                "priority": getattr(current_keyring, 'priority', 'unknown'),
                "available": self.test_keyring_availability()
            }
        except Exception as e:
            logger.error(f"Failed to get keyring info: {e}")
            return {"error": str(e)}