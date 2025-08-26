"""Encryption utilities for secure data handling."""

import os
import base64
import logging
from typing import Optional, Dict, Any, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import json
from ..core.exceptions import SecurityError

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Manages encryption and decryption operations."""
    
    def __init__(self):
        """Initialize encryption manager."""
        self._symmetric_key = None
        self._private_key = None
        self._public_key = None
    
    def generate_key(self) -> bytes:
        """Generate a new Fernet encryption key.
        
        Returns:
            Base64-encoded encryption key
        """
        return Fernet.generate_key()
    
    def derive_key_from_password(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key from password using PBKDF2.
        
        Args:
            password: Password to derive key from
            salt: Salt for key derivation (generated if None)
            
        Returns:
            Derived encryption key
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_data(self, data: Union[str, bytes, Dict[str, Any]], key: bytes) -> bytes:
        """Encrypt data using Fernet symmetric encryption.
        
        Args:
            data: Data to encrypt (string, bytes, or dict)
            key: Encryption key
            
        Returns:
            Encrypted data
        """
        try:
            # Convert data to bytes if necessary
            if isinstance(data, dict):
                data_bytes = json.dumps(data).encode('utf-8')
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(data_bytes)
            
            logger.debug(f"Encrypted {len(data_bytes)} bytes of data")
            return encrypted_data
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise SecurityError(f"Failed to encrypt data: {e}")
    
    def decrypt_data(self, encrypted_data: bytes, key: bytes, 
                    return_type: str = 'string') -> Union[str, bytes, Dict[str, Any]]:
        """Decrypt data using Fernet symmetric encryption.
        
        Args:
            encrypted_data: Encrypted data to decrypt
            key: Decryption key
            return_type: Type to return ('string', 'bytes', 'json')
            
        Returns:
            Decrypted data in specified format
        """
        try:
            fernet = Fernet(key)
            decrypted_bytes = fernet.decrypt(encrypted_data)
            
            if return_type == 'bytes':
                return decrypted_bytes
            elif return_type == 'json':
                return json.loads(decrypted_bytes.decode('utf-8'))
            else:  # string
                return decrypted_bytes.decode('utf-8')
                
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise SecurityError(f"Failed to decrypt data: {e}")
    
    def generate_rsa_keypair(self, key_size: int = 2048) -> tuple[bytes, bytes]:
        """Generate RSA public/private key pair.
        
        Args:
            key_size: RSA key size in bits
            
        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize keys to PEM format
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            logger.info(f"Generated RSA key pair with {key_size} bits")
            return private_pem, public_pem
            
        except Exception as e:
            logger.error(f"RSA key generation failed: {e}")
            raise SecurityError(f"Failed to generate RSA keys: {e}")
    
    def load_private_key(self, private_key_pem: bytes, password: Optional[bytes] = None):
        """Load RSA private key from PEM data.
        
        Args:
            private_key_pem: Private key in PEM format
            password: Optional password for encrypted key
        """
        try:
            self._private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=password,
                backend=default_backend()
            )
            self._public_key = self._private_key.public_key()
            logger.debug("Loaded RSA private key")
            
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise SecurityError(f"Failed to load private key: {e}")
    
    def load_public_key(self, public_key_pem: bytes):
        """Load RSA public key from PEM data.
        
        Args:
            public_key_pem: Public key in PEM format
        """
        try:
            self._public_key = serialization.load_pem_public_key(
                public_key_pem,
                backend=default_backend()
            )
            logger.debug("Loaded RSA public key")
            
        except Exception as e:
            logger.error(f"Failed to load public key: {e}")
            raise SecurityError(f"Failed to load public key: {e}")
    
    def encrypt_with_public_key(self, data: Union[str, bytes]) -> bytes:
        """Encrypt data using RSA public key.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data
        """
        if self._public_key is None:
            raise SecurityError("No public key loaded")
        
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            encrypted_data = self._public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            logger.debug(f"Encrypted {len(data)} bytes with RSA public key")
            return encrypted_data
            
        except Exception as e:
            logger.error(f"RSA encryption failed: {e}")
            raise SecurityError(f"Failed to encrypt with public key: {e}")
    
    def decrypt_with_private_key(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using RSA private key.
        
        Args:
            encrypted_data: Data to decrypt
            
        Returns:
            Decrypted data
        """
        if self._private_key is None:
            raise SecurityError("No private key loaded")
        
        try:
            decrypted_data = self._private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            logger.debug(f"Decrypted {len(decrypted_data)} bytes with RSA private key")
            return decrypted_data
            
        except Exception as e:
            logger.error(f"RSA decryption failed: {e}")
            raise SecurityError(f"Failed to decrypt with private key: {e}")
    
    def encrypt_file(self, file_path: str, output_path: str, key: bytes):
        """Encrypt a file using Fernet encryption.
        
        Args:
            file_path: Path to file to encrypt
            output_path: Path for encrypted output file
            key: Encryption key
        """
        try:
            with open(file_path, 'rb') as infile:
                data = infile.read()
            
            encrypted_data = self.encrypt_data(data, key)
            
            with open(output_path, 'wb') as outfile:
                outfile.write(encrypted_data)
            
            logger.info(f"Encrypted file: {file_path} -> {output_path}")
            
        except Exception as e:
            logger.error(f"File encryption failed: {e}")
            raise SecurityError(f"Failed to encrypt file: {e}")
    
    def decrypt_file(self, encrypted_file_path: str, output_path: str, key: bytes):
        """Decrypt a file using Fernet encryption.
        
        Args:
            encrypted_file_path: Path to encrypted file
            output_path: Path for decrypted output file
            key: Decryption key
        """
        try:
            with open(encrypted_file_path, 'rb') as infile:
                encrypted_data = infile.read()
            
            decrypted_data = self.decrypt_data(encrypted_data, key, return_type='bytes')
            
            with open(output_path, 'wb') as outfile:
                outfile.write(decrypted_data)
            
            logger.info(f"Decrypted file: {encrypted_file_path} -> {output_path}")
            
        except Exception as e:
            logger.error(f"File decryption failed: {e}")
            raise SecurityError(f"Failed to decrypt file: {e}")
    
    def create_secure_token(self, data: Dict[str, Any], key: bytes, 
                           expiry_seconds: Optional[int] = None) -> str:
        """Create a secure token containing encrypted data.
        
        Args:
            data: Data to include in token
            key: Encryption key
            expiry_seconds: Optional expiry time in seconds
            
        Returns:
            Base64-encoded secure token
        """
        try:
            import time
            
            token_data = {
                'data': data,
                'created_at': time.time()
            }
            
            if expiry_seconds:
                token_data['expires_at'] = time.time() + expiry_seconds
            
            encrypted_token = self.encrypt_data(token_data, key)
            return base64.b64encode(encrypted_token).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Token creation failed: {e}")
            raise SecurityError(f"Failed to create secure token: {e}")
    
    def verify_secure_token(self, token: str, key: bytes) -> Optional[Dict[str, Any]]:
        """Verify and extract data from a secure token.
        
        Args:
            token: Base64-encoded secure token
            key: Decryption key
            
        Returns:
            Token data if valid, None if invalid or expired
        """
        try:
            import time
            
            encrypted_token = base64.b64decode(token.encode('utf-8'))
            token_data = self.decrypt_data(encrypted_token, key, return_type='json')
            
            # Check expiry
            if 'expires_at' in token_data:
                if time.time() > token_data['expires_at']:
                    logger.warning("Token has expired")
                    return None
            
            return token_data.get('data')
            
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None
    
    def generate_secure_hash(self, data: Union[str, bytes], salt: Optional[bytes] = None) -> str:
        """Generate a secure hash of data using SHA-256.
        
        Args:
            data: Data to hash
            salt: Optional salt
            
        Returns:
            Hex-encoded hash
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            if salt:
                data = salt + data
            
            digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
            digest.update(data)
            hash_bytes = digest.finalize()
            
            return hash_bytes.hex()
            
        except Exception as e:
            logger.error(f"Hash generation failed: {e}")
            raise SecurityError(f"Failed to generate hash: {e}")
    
    def constant_time_compare(self, a: Union[str, bytes], b: Union[str, bytes]) -> bool:
        """Compare two values in constant time to prevent timing attacks.
        
        Args:
            a: First value
            b: Second value
            
        Returns:
            True if values are equal, False otherwise
        """
        if isinstance(a, str):
            a = a.encode('utf-8')
        if isinstance(b, str):
            b = b.encode('utf-8')
        
        if len(a) != len(b):
            return False
        
        result = 0
        for x, y in zip(a, b):
            result |= x ^ y
        
        return result == 0