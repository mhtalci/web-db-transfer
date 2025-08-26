"""
Recovery validator for ensuring backup integrity and recovery readiness.

This module provides validation capabilities to ensure backups are
valid and can be successfully restored when needed.
"""

import asyncio
import hashlib
import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from migration_assistant.backup.strategies import (
    BackupStrategy,
    CloudBackupStrategy,
    ConfigBackupStrategy,
    DatabaseBackupStrategy,
    FileBackupStrategy,
)
from migration_assistant.core.exceptions import BackupError
from migration_assistant.models.config import DatabaseConfig, SystemConfig
from migration_assistant.models.session import BackupInfo, LogEntry, LogLevel


class ValidationResult:
    """Result of backup validation."""
    
    def __init__(self):
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.details: Dict[str, Any] = {}
        self.validation_time = datetime.utcnow()
    
    def add_error(self, message: str):
        """Add an error to the validation result."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add a warning to the validation result."""
        self.warnings.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details,
            "validation_time": self.validation_time.isoformat(),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }


class RecoveryValidator:
    """Validates backup integrity and recovery readiness."""
    
    def __init__(self):
        self._validation_logs: List[LogEntry] = []
    
    def _log(self, level: LogLevel, message: str, backup_id: Optional[str] = None, **kwargs):
        """Add a log entry."""
        log_entry = LogEntry(
            level=level,
            message=message,
            component="RecoveryValidator",
            details={"backup_id": backup_id, **kwargs}
        )
        self._validation_logs.append(log_entry)
    
    async def validate_backup(self, backup_info: BackupInfo) -> ValidationResult:
        """Validate a single backup for integrity and recoverability."""
        result = ValidationResult()
        
        try:
            self._log(LogLevel.INFO, "Starting backup validation", backup_info.id)
            
            # Basic file existence and accessibility checks
            await self._validate_file_existence(backup_info, result)
            
            if not result.is_valid:
                return result
            
            # Checksum validation
            await self._validate_checksum(backup_info, result)
            
            # Content validation based on backup type
            await self._validate_content(backup_info, result)
            
            # Metadata validation
            await self._validate_metadata(backup_info, result)
            
            # Recovery readiness check
            await self._validate_recovery_readiness(backup_info, result)
            
            if result.is_valid:
                self._log(LogLevel.INFO, "Backup validation successful", backup_info.id)
            else:
                self._log(LogLevel.ERROR, f"Backup validation failed with {len(result.errors)} errors", backup_info.id)
            
            return result
            
        except Exception as e:
            result.add_error(f"Validation exception: {str(e)}")
            self._log(LogLevel.ERROR, f"Backup validation exception: {str(e)}", backup_info.id)
            return result
    
    async def _validate_file_existence(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate that backup file exists and is accessible."""
        if not backup_info.location:
            result.add_error("Backup location is not specified")
            return
        
        if not os.path.exists(backup_info.location):
            result.add_error(f"Backup file does not exist: {backup_info.location}")
            return
        
        if not os.path.isfile(backup_info.location):
            result.add_error(f"Backup location is not a file: {backup_info.location}")
            return
        
        # Check file permissions
        if not os.access(backup_info.location, os.R_OK):
            result.add_error(f"Backup file is not readable: {backup_info.location}")
            return
        
        # Check file size
        actual_size = os.path.getsize(backup_info.location)
        if backup_info.size and actual_size != backup_info.size:
            result.add_warning(f"File size mismatch: expected {backup_info.size}, actual {actual_size}")
        
        result.details["file_size"] = actual_size
        result.details["file_accessible"] = True
    
    async def _validate_checksum(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate backup file checksum."""
        if not backup_info.checksum:
            result.add_warning("No checksum available for validation")
            return
        
        try:
            # Calculate current checksum
            sha256_hash = hashlib.sha256()
            with open(backup_info.location, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            current_checksum = sha256_hash.hexdigest()
            
            if current_checksum != backup_info.checksum:
                result.add_error(f"Checksum mismatch: expected {backup_info.checksum}, actual {current_checksum}")
            else:
                result.details["checksum_valid"] = True
                
        except Exception as e:
            result.add_error(f"Failed to calculate checksum: {str(e)}")
    
    async def _validate_content(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate backup content based on backup type."""
        backup_type = backup_info.metadata.get("backup_type", "unknown")
        
        if backup_type == "file_archive":
            await self._validate_archive_content(backup_info, result)
        elif backup_type == "database_dump":
            await self._validate_database_content(backup_info, result)
        elif backup_type == "configuration":
            await self._validate_config_content(backup_info, result)
        elif backup_type == "cloud_resources":
            await self._validate_cloud_content(backup_info, result)
        else:
            result.add_warning(f"Unknown backup type for content validation: {backup_type}")
    
    async def _validate_archive_content(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate tar archive content."""
        import tarfile
        
        try:
            with tarfile.open(backup_info.location, "r") as tar:
                # Get archive members
                members = tar.getnames()
                result.details["archive_members"] = len(members)
                
                if not members:
                    result.add_error("Archive is empty")
                    return
                
                # Validate a few random members
                sample_members = members[:min(5, len(members))]
                for member_name in sample_members:
                    try:
                        member = tar.getmember(member_name)
                        if member.isfile():
                            # Try to extract a small portion to verify integrity
                            f = tar.extractfile(member)
                            if f:
                                f.read(1024)  # Read first 1KB
                                f.close()
                    except Exception as e:
                        result.add_error(f"Failed to validate archive member {member_name}: {str(e)}")
                
                result.details["archive_validation"] = "passed"
                
        except Exception as e:
            result.add_error(f"Failed to validate archive content: {str(e)}")
    
    async def _validate_database_content(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate database dump content."""
        try:
            db_type = backup_info.metadata.get("database_type", "").lower()
            
            with open(backup_info.location, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(10000)  # Read first 10KB
                
                if not content.strip():
                    result.add_error("Database dump file is empty")
                    return
                
                # Check for SQL keywords based on database type
                if db_type in ["mysql", "mariadb"]:
                    expected_keywords = ["CREATE", "INSERT", "DROP", "USE"]
                elif db_type == "postgresql":
                    expected_keywords = ["CREATE", "INSERT", "DROP", "\\connect"]
                elif db_type == "sqlite":
                    expected_keywords = ["CREATE", "INSERT", "PRAGMA"]
                else:
                    expected_keywords = ["CREATE", "INSERT"]
                
                found_keywords = []
                content_upper = content.upper()
                for keyword in expected_keywords:
                    if keyword in content_upper:
                        found_keywords.append(keyword)
                
                if not found_keywords:
                    result.add_warning("No expected SQL keywords found in dump file")
                else:
                    result.details["sql_keywords_found"] = found_keywords
                
                # Check for potential corruption indicators
                if "ERROR" in content_upper or "FAILED" in content_upper:
                    result.add_warning("Potential error indicators found in dump file")
                
                result.details["database_validation"] = "passed"
                
        except Exception as e:
            result.add_error(f"Failed to validate database content: {str(e)}")
    
    async def _validate_config_content(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate configuration backup content."""
        try:
            with open(backup_info.location, "r") as f:
                config_data = json.load(f)
            
            # Check required fields
            required_fields = ["backup_id", "timestamp", "system_config"]
            missing_fields = [field for field in required_fields if field not in config_data]
            
            if missing_fields:
                result.add_error(f"Missing required fields in config backup: {missing_fields}")
            
            # Validate JSON structure
            if "config_files" in config_data and isinstance(config_data["config_files"], dict):
                result.details["config_files_count"] = len(config_data["config_files"])
            
            result.details["config_validation"] = "passed"
            
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON in configuration backup: {str(e)}")
        except Exception as e:
            result.add_error(f"Failed to validate configuration content: {str(e)}")
    
    async def _validate_cloud_content(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate cloud backup content."""
        try:
            with open(backup_info.location, "r") as f:
                cloud_data = json.load(f)
            
            # Check required fields
            required_fields = ["backup_id", "timestamp", "cloud_provider"]
            missing_fields = [field for field in required_fields if field not in cloud_data]
            
            if missing_fields:
                result.add_error(f"Missing required fields in cloud backup: {missing_fields}")
            
            result.details["cloud_validation"] = "passed"
            
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON in cloud backup: {str(e)}")
        except Exception as e:
            result.add_error(f"Failed to validate cloud content: {str(e)}")
    
    async def _validate_metadata(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate backup metadata."""
        # Check backup age
        if backup_info.expires_at and datetime.utcnow() > backup_info.expires_at:
            result.add_warning("Backup has expired")
        
        # Check if backup was previously verified
        if not backup_info.verified:
            result.add_warning("Backup has not been previously verified")
        elif backup_info.verification_date:
            days_since_verification = (datetime.utcnow() - backup_info.verification_date).days
            if days_since_verification > 30:
                result.add_warning(f"Backup verification is {days_since_verification} days old")
        
        # Validate metadata completeness
        if not backup_info.metadata:
            result.add_warning("Backup metadata is empty")
        else:
            result.details["metadata_keys"] = list(backup_info.metadata.keys())
    
    async def _validate_recovery_readiness(self, backup_info: BackupInfo, result: ValidationResult):
        """Validate that backup is ready for recovery operations."""
        backup_type = backup_info.metadata.get("backup_type", "unknown")
        
        # Check if required tools are available for restoration
        if backup_type == "database_dump":
            db_type = backup_info.metadata.get("database_type", "").lower()
            await self._check_database_tools(db_type, result)
        elif backup_type == "file_archive":
            await self._check_archive_tools(result)
        
        # Check available disk space for restoration
        await self._check_disk_space(backup_info, result)
    
    async def _check_database_tools(self, db_type: str, result: ValidationResult):
        """Check if database restoration tools are available."""
        import shutil
        
        tool_map = {
            "mysql": "mysql",
            "mariadb": "mysql",
            "postgresql": "psql",
            "sqlite": "sqlite3",
            "mongodb": "mongorestore"
        }
        
        required_tool = tool_map.get(db_type)
        if required_tool:
            if not shutil.which(required_tool):
                result.add_warning(f"Database restoration tool '{required_tool}' not found in PATH")
            else:
                result.details[f"{required_tool}_available"] = True
    
    async def _check_archive_tools(self, result: ValidationResult):
        """Check if archive extraction tools are available."""
        # Python's tarfile module is built-in, so this is mostly informational
        result.details["archive_tools_available"] = True
    
    async def _check_disk_space(self, backup_info: BackupInfo, result: ValidationResult):
        """Check available disk space for restoration."""
        try:
            import shutil
            
            # Get disk usage for the backup location
            backup_dir = os.path.dirname(backup_info.location)
            total, used, free = shutil.disk_usage(backup_dir)
            
            # Estimate space needed for restoration (backup size * 2 for safety)
            estimated_space_needed = (backup_info.size or 0) * 2
            
            if free < estimated_space_needed:
                result.add_warning(
                    f"Insufficient disk space for restoration: "
                    f"need {estimated_space_needed / (1024**3):.2f}GB, "
                    f"available {free / (1024**3):.2f}GB"
                )
            
            result.details["disk_space"] = {
                "total_gb": total / (1024**3),
                "used_gb": used / (1024**3),
                "free_gb": free / (1024**3),
                "estimated_need_gb": estimated_space_needed / (1024**3)
            }
            
        except Exception as e:
            result.add_warning(f"Could not check disk space: {str(e)}")
    
    async def validate_multiple_backups(self, backups: List[BackupInfo]) -> Dict[str, ValidationResult]:
        """Validate multiple backups concurrently."""
        validation_tasks = [
            self.validate_backup(backup) for backup in backups
        ]
        
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        validation_results = {}
        for backup, result in zip(backups, results):
            if isinstance(result, Exception):
                error_result = ValidationResult()
                error_result.add_error(f"Validation exception: {str(result)}")
                validation_results[backup.id] = error_result
            else:
                validation_results[backup.id] = result
        
        return validation_results
    
    async def test_restore_capability(
        self,
        backup_info: BackupInfo,
        test_location: Optional[str] = None
    ) -> ValidationResult:
        """Test actual restore capability by performing a test restoration."""
        result = ValidationResult()
        
        try:
            self._log(LogLevel.INFO, "Starting restore capability test", backup_info.id)
            
            # Create temporary directory for test restoration
            if not test_location:
                test_location = tempfile.mkdtemp(prefix="backup_restore_test_")
            
            # Create appropriate strategy for test restoration
            backup_type = backup_info.metadata.get("backup_type", "unknown")
            
            if backup_type == "file_archive":
                strategy = FileBackupStrategy(SystemConfig(type=backup_info.source_system, host=""))
                success = await strategy.restore_backup(backup_info, test_location)
            elif backup_type == "configuration":
                strategy = ConfigBackupStrategy(SystemConfig(type=backup_info.source_system, host=""))
                success = await strategy.restore_backup(backup_info, test_location)
            else:
                result.add_warning(f"Test restoration not implemented for backup type: {backup_type}")
                return result
            
            if success:
                result.details["test_restore_successful"] = True
                self._log(LogLevel.INFO, "Test restoration successful", backup_info.id)
            else:
                result.add_error("Test restoration failed")
                self._log(LogLevel.ERROR, "Test restoration failed", backup_info.id)
            
            # Cleanup test location
            if test_location.startswith(tempfile.gettempdir()):
                import shutil
                shutil.rmtree(test_location, ignore_errors=True)
            
            return result
            
        except Exception as e:
            result.add_error(f"Test restoration exception: {str(e)}")
            self._log(LogLevel.ERROR, f"Test restoration exception: {str(e)}", backup_info.id)
            return result
    
    async def generate_validation_report(
        self,
        validation_results: Dict[str, ValidationResult]
    ) -> Dict[str, Any]:
        """Generate a comprehensive validation report."""
        report = {
            "validation_summary": {
                "total_backups": len(validation_results),
                "valid_backups": sum(1 for r in validation_results.values() if r.is_valid),
                "invalid_backups": sum(1 for r in validation_results.values() if not r.is_valid),
                "total_errors": sum(len(r.errors) for r in validation_results.values()),
                "total_warnings": sum(len(r.warnings) for r in validation_results.values())
            },
            "backup_results": {
                backup_id: result.to_dict() 
                for backup_id, result in validation_results.items()
            },
            "recommendations": [],
            "report_generated": datetime.utcnow().isoformat()
        }
        
        # Generate recommendations based on validation results
        invalid_count = report["validation_summary"]["invalid_backups"]
        if invalid_count > 0:
            report["recommendations"].append(
                f"Immediate attention required: {invalid_count} backup(s) failed validation"
            )
        
        warning_count = report["validation_summary"]["total_warnings"]
        if warning_count > 0:
            report["recommendations"].append(
                f"Review {warning_count} warning(s) to improve backup reliability"
            )
        
        # Check for common issues
        checksum_errors = sum(
            1 for r in validation_results.values() 
            if any("checksum" in error.lower() for error in r.errors)
        )
        if checksum_errors > 0:
            report["recommendations"].append(
                f"Checksum validation failed for {checksum_errors} backup(s) - possible corruption"
            )
        
        return report
    
    def get_logs(self, backup_id: Optional[str] = None) -> List[LogEntry]:
        """Get validation logs."""
        if backup_id:
            return [
                log for log in self._validation_logs 
                if log.details.get("backup_id") == backup_id
            ]
        return self._validation_logs.copy()
    
    def clear_logs(self):
        """Clear validation logs."""
        self._validation_logs.clear()