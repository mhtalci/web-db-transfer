"""
Helper utilities for the Migration Assistant.

This module contains various utility functions used throughout
the application for common operations.
"""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


def generate_session_id() -> str:
    """Generate a unique session ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"migration_{timestamp}_{unique_id}"


def generate_step_id(step_name: str) -> str:
    """Generate a unique step ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    clean_name = step_name.lower().replace(" ", "_").replace("-", "_")
    return f"step_{clean_name}_{timestamp}"


def calculate_file_checksum(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
    """
    Calculate checksum for a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)
    
    Returns:
        Hexadecimal checksum string
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def format_bytes(bytes_count: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def safe_filename(filename: str) -> str:
    """Convert a string to a safe filename."""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename


def load_config_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load configuration from YAML or JSON file.
    
    Args:
        file_path: Path to configuration file
    
    Returns:
        Configuration dictionary
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        if file_path.suffix.lower() in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif file_path.suffix.lower() == '.json':
            return json.load(f)
        else:
            raise ValueError(f"Unsupported configuration file format: {file_path.suffix}")


def save_config_file(config: Dict[str, Any], file_path: Union[str, Path], format: str = "yaml") -> None:
    """
    Save configuration to YAML or JSON file.
    
    Args:
        config: Configuration dictionary
        file_path: Path to save configuration
        format: File format ('yaml' or 'json')
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        if format.lower() == 'yaml':
            yaml.dump(config, f, default_flow_style=False, indent=2)
        elif format.lower() == 'json':
            json.dump(config, f, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries.
    
    Args:
        dict1: Base dictionary
        dict2: Dictionary to merge (takes precedence)
    
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_url(url: str) -> bool:
    """Validate if a string is a valid URL."""
    import re
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None


def sanitize_dict(data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Sanitize dictionary by masking sensitive values.
    
    Args:
        data: Dictionary to sanitize
        sensitive_keys: List of keys to mask (default: common sensitive keys)
    
    Returns:
        Sanitized dictionary
    """
    if sensitive_keys is None:
        sensitive_keys = [
            'password', 'passwd', 'pwd', 'secret', 'key', 'token',
            'api_key', 'api_secret', 'access_key', 'private_key',
            'ssh_key', 'passphrase', 'credential', 'auth'
        ]
    
    def _sanitize_value(key: str, value: Any) -> Any:
        if isinstance(value, dict):
            return sanitize_dict(value, sensitive_keys)
        elif isinstance(value, list):
            return [_sanitize_value(f"{key}[{i}]", item) for i, item in enumerate(value)]
        elif any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            return "***MASKED***" if value else value
        else:
            return value
    
    return {key: _sanitize_value(key, value) for key, value in data.items()}


def get_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """
    Find an available port starting from the given port.
    
    Args:
        start_port: Starting port number
        max_attempts: Maximum number of ports to try
    
    Returns:
        Available port number
    """
    import socket
    
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")


def retry_on_exception(
    func,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying function calls on exceptions.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff_factor: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch
    
    Returns:
        Decorated function
    """
    import time
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        current_delay = delay
        
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if attempt == max_attempts - 1:
                    raise e
                
                time.sleep(current_delay)
                current_delay *= backoff_factor
        
        return None
    
    return wrapper