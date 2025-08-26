"""Data sanitization and privacy protection utilities."""

import re
import hashlib
import logging
from typing import Dict, Any, List, Optional, Union, Pattern
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SensitivityLevel(Enum):
    """Data sensitivity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SanitizationRule:
    """Defines a data sanitization rule."""
    pattern: Union[str, Pattern]
    replacement: str
    sensitivity: SensitivityLevel
    description: str
    enabled: bool = True

class DataSanitizer:
    """Handles data sanitization and privacy protection."""
    
    def __init__(self):
        """Initialize data sanitizer with default rules."""
        self.rules: List[SanitizationRule] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default sanitization rules."""
        # Email addresses
        self.add_rule(
            pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            replacement='[EMAIL_REDACTED]',
            sensitivity=SensitivityLevel.MEDIUM,
            description='Email addresses'
        )
        
        # Phone numbers (various formats)
        self.add_rule(
            pattern=r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})',
            replacement='[PHONE_REDACTED]',
            sensitivity=SensitivityLevel.MEDIUM,
            description='Phone numbers'
        )
        
        # Credit card numbers
        self.add_rule(
            pattern=r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            replacement='[CREDIT_CARD_REDACTED]',
            sensitivity=SensitivityLevel.CRITICAL,
            description='Credit card numbers'
        )
        
        # Social Security Numbers
        self.add_rule(
            pattern=r'\b\d{3}-?\d{2}-?\d{4}\b',
            replacement='[SSN_REDACTED]',
            sensitivity=SensitivityLevel.CRITICAL,
            description='Social Security Numbers'
        )
        
        # IP addresses
        self.add_rule(
            pattern=r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            replacement='[IP_REDACTED]',
            sensitivity=SensitivityLevel.LOW,
            description='IP addresses'
        )
        
        # Database connection strings
        self.add_rule(
            pattern=r'(mysql|postgresql|mongodb|redis)://[^:\s]+:[^@\s]+@[^\s]+',
            replacement=r'\1://[USER_REDACTED]:[PASSWORD_REDACTED]@[HOST_REDACTED]',
            sensitivity=SensitivityLevel.HIGH,
            description='Database connection strings'
        )
        
        # API keys (common patterns)
        self.add_rule(
            pattern=r'(api[_-]?key|token|secret)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?',
            replacement=r'\1=[API_KEY_REDACTED]',
            sensitivity=SensitivityLevel.HIGH,
            description='API keys and tokens'
        )
        
        # AWS access keys
        self.add_rule(
            pattern=r'AKIA[0-9A-Z]{16}',
            replacement='[AWS_ACCESS_KEY_REDACTED]',
            sensitivity=SensitivityLevel.HIGH,
            description='AWS access keys'
        )
        
        # Passwords in various formats
        self.add_rule(
            pattern=r'(password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']{6,})["\']?',
            replacement=r'\1=[PASSWORD_REDACTED]',
            sensitivity=SensitivityLevel.HIGH,
            description='Password fields'
        )
    
    def add_rule(self, pattern: Union[str, Pattern], replacement: str, 
                 sensitivity: SensitivityLevel, description: str, enabled: bool = True):
        """Add a sanitization rule.
        
        Args:
            pattern: Regex pattern to match
            replacement: Replacement string
            sensitivity: Sensitivity level
            description: Rule description
            enabled: Whether rule is enabled
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern, re.IGNORECASE)
        
        rule = SanitizationRule(
            pattern=pattern,
            replacement=replacement,
            sensitivity=sensitivity,
            description=description,
            enabled=enabled
        )
        self.rules.append(rule)
        logger.debug(f"Added sanitization rule: {description}")
    
    def sanitize_text(self, text: str, min_sensitivity: SensitivityLevel = SensitivityLevel.LOW) -> str:
        """Sanitize text content based on rules.
        
        Args:
            text: Text to sanitize
            min_sensitivity: Minimum sensitivity level to apply
            
        Returns:
            Sanitized text
        """
        if not text:
            return text
        
        sanitized = text
        applied_rules = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
                
            # Check if rule meets minimum sensitivity requirement
            sensitivity_order = [SensitivityLevel.LOW, SensitivityLevel.MEDIUM, 
                               SensitivityLevel.HIGH, SensitivityLevel.CRITICAL]
            if sensitivity_order.index(rule.sensitivity) < sensitivity_order.index(min_sensitivity):
                continue
            
            # Apply the rule
            matches = rule.pattern.findall(sanitized)
            if matches:
                sanitized = rule.pattern.sub(rule.replacement, sanitized)
                applied_rules.append(rule.description)
        
        if applied_rules:
            logger.info(f"Applied sanitization rules: {', '.join(applied_rules)}")
        
        return sanitized
    
    def sanitize_dict(self, data: Dict[str, Any], 
                     min_sensitivity: SensitivityLevel = SensitivityLevel.LOW) -> Dict[str, Any]:
        """Sanitize dictionary data recursively.
        
        Args:
            data: Dictionary to sanitize
            min_sensitivity: Minimum sensitivity level to apply
            
        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        
        for key, value in data.items():
            # Sanitize the key
            sanitized_key = self.sanitize_text(str(key), min_sensitivity)
            
            # Sanitize the value based on its type
            if isinstance(value, str):
                sanitized_value = self.sanitize_text(value, min_sensitivity)
            elif isinstance(value, dict):
                sanitized_value = self.sanitize_dict(value, min_sensitivity)
            elif isinstance(value, list):
                sanitized_value = self.sanitize_list(value, min_sensitivity)
            else:
                # For other types, convert to string and sanitize
                sanitized_value = self.sanitize_text(str(value), min_sensitivity)
            
            sanitized[sanitized_key] = sanitized_value
        
        return sanitized
    
    def sanitize_list(self, data: List[Any], 
                     min_sensitivity: SensitivityLevel = SensitivityLevel.LOW) -> List[Any]:
        """Sanitize list data recursively.
        
        Args:
            data: List to sanitize
            min_sensitivity: Minimum sensitivity level to apply
            
        Returns:
            Sanitized list
        """
        if not isinstance(data, list):
            return data
        
        sanitized = []
        
        for item in data:
            if isinstance(item, str):
                sanitized_item = self.sanitize_text(item, min_sensitivity)
            elif isinstance(item, dict):
                sanitized_item = self.sanitize_dict(item, min_sensitivity)
            elif isinstance(item, list):
                sanitized_item = self.sanitize_list(item, min_sensitivity)
            else:
                sanitized_item = self.sanitize_text(str(item), min_sensitivity)
            
            sanitized.append(sanitized_item)
        
        return sanitized
    
    def hash_sensitive_data(self, data: str, salt: str = None) -> str:
        """Create a hash of sensitive data for logging/debugging.
        
        Args:
            data: Data to hash
            salt: Optional salt for hashing
            
        Returns:
            Hashed data as hex string
        """
        if salt is None:
            salt = "migration_assistant_salt"
        
        combined = f"{salt}{data}".encode('utf-8')
        return hashlib.sha256(combined).hexdigest()[:16]  # First 16 chars
    
    def create_data_map(self, original_data: str, sanitized_data: str) -> Dict[str, str]:
        """Create a mapping of original to sanitized data for debugging.
        
        Args:
            original_data: Original data
            sanitized_data: Sanitized data
            
        Returns:
            Dictionary mapping hashed original to sanitized values
        """
        data_map = {}
        
        # Find all sanitized placeholders
        placeholders = re.findall(r'\[([A-Z_]+_REDACTED)\]', sanitized_data)
        
        for placeholder in set(placeholders):
            # Create a hash of the original data for this placeholder
            hash_key = self.hash_sensitive_data(f"{placeholder}_{original_data}")
            data_map[hash_key] = f"[{placeholder}]"
        
        return data_map
    
    def get_sanitization_report(self, text: str, 
                              min_sensitivity: SensitivityLevel = SensitivityLevel.LOW) -> Dict[str, Any]:
        """Generate a report of sanitization actions.
        
        Args:
            text: Text to analyze
            min_sensitivity: Minimum sensitivity level
            
        Returns:
            Sanitization report
        """
        if not text:
            return {"original_length": 0, "sanitized_length": 0, "rules_applied": []}
        
        original_length = len(text)
        sanitized = self.sanitize_text(text, min_sensitivity)
        sanitized_length = len(sanitized)
        
        rules_applied = []
        for rule in self.rules:
            if not rule.enabled:
                continue
                
            matches = rule.pattern.findall(text)
            if matches:
                rules_applied.append({
                    "rule": rule.description,
                    "sensitivity": rule.sensitivity.value,
                    "matches_found": len(matches)
                })
        
        return {
            "original_length": original_length,
            "sanitized_length": sanitized_length,
            "rules_applied": rules_applied,
            "reduction_ratio": (original_length - sanitized_length) / original_length if original_length > 0 else 0
        }
    
    def disable_rule(self, description: str):
        """Disable a sanitization rule by description.
        
        Args:
            description: Rule description to disable
        """
        for rule in self.rules:
            if rule.description == description:
                rule.enabled = False
                logger.info(f"Disabled sanitization rule: {description}")
                return
        
        logger.warning(f"Rule not found: {description}")
    
    def enable_rule(self, description: str):
        """Enable a sanitization rule by description.
        
        Args:
            description: Rule description to enable
        """
        for rule in self.rules:
            if rule.description == description:
                rule.enabled = True
                logger.info(f"Enabled sanitization rule: {description}")
                return
        
        logger.warning(f"Rule not found: {description}")
    
    def list_rules(self) -> List[Dict[str, Any]]:
        """List all sanitization rules.
        
        Returns:
            List of rule information
        """
        return [
            {
                "description": rule.description,
                "sensitivity": rule.sensitivity.value,
                "enabled": rule.enabled,
                "pattern": rule.pattern.pattern if hasattr(rule.pattern, 'pattern') else str(rule.pattern)
            }
            for rule in self.rules
        ]