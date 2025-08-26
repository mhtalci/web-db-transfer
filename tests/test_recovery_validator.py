"""
Unit tests for the recovery validator.

Tests backup validation and recovery readiness functionality.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from migration_assistant.backup.validator import RecoveryValidator, ValidationResult
from migration_assistant.models.session import BackupInfo, BackupType


class TestRecoveryValidator:
    """Test cases for RecoveryValidator."""
    
    @pytest.fixture
    def recovery_validator(self):
        """Create a recovery validator instance for testing."""
        return RecoveryValidator()
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def file_backup_info(self, temp_dir):
        """Create a file backup info for testing."""
        backup_file = os.path.join(temp_dir, "test_backup.tar.gz")
        with open(backup_file, "w") as f:
            f.write("backup content")
        
        return BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=len("backup content"),
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            metadata={"backup_type": "file_archive"}
        )
    
    @pytest.fixture
    def database_backup_info(self, temp_dir):
        """Create a database backup info for testing."""
        backup_file = os.path.join(temp_dir, "test_backup.sql")
        with open(backup_file, "w") as f:
            f.write("CREATE TABLE test (id INT);\nINSERT INTO test VALUES (1);")
        
        return BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=len("CREATE TABLE test (id INT);\nINSERT INTO test VALUES (1);"),
            checksum="test_checksum",
            metadata={"backup_type": "database_dump", "database_type": "mysql"}
        )
    
    @pytest.fixture
    def config_backup_info(self, temp_dir):
        """Create a config backup info for testing."""
        backup_file = os.path.join(temp_dir, "config_backup.json")
        config_data = {
            "backup_id": "test",
            "timestamp": "2023-01-01T00:00:00",
            "system_config": {"type": "wordpress"},
            "config_files": {"config.ini": "[section]\nkey=value"}
        }
        with open(backup_file, "w") as f:
            json.dump(config_data, f)
        
        return BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=len(json.dumps(config_data)),
            checksum="config_checksum",
            metadata={"backup_type": "configuration"}
        )
    
    @pytest.mark.asyncio
    async def test_validate_file_backup_success(self, recovery_validator, file_backup_info):
        """Test successful file backup validation."""
        result = await recovery_validator.validate_backup(file_backup_info)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.details["file_accessible"] is True
    
    @pytest.mark.asyncio
    async def test_validate_database_backup_success(self, recovery_validator, database_backup_info):
        """Test successful database backup validation."""
        result = await recovery_validator.validate_backup(database_backup_info)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert "sql_keywords_found" in result.details
        assert "CREATE" in result.details["sql_keywords_found"]
        assert "INSERT" in result.details["sql_keywords_found"]
    
    @pytest.mark.asyncio
    async def test_validate_config_backup_success(self, recovery_validator, config_backup_info):
        """Test successful config backup validation."""
        result = await recovery_validator.validate_backup(config_backup_info)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.details["config_files_count"] == 1
    
    @pytest.mark.asyncio
    async def test_validate_backup_file_not_found(self, recovery_validator):
        """Test validation of backup with missing file."""
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location="/nonexistent/file.tar.gz",
            metadata={"backup_type": "file_archive"}
        )
        
        result = await recovery_validator.validate_backup(backup_info)
        
        assert result.is_valid is False
        assert any("does not exist" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_backup_checksum_mismatch(self, recovery_validator, file_backup_info):
        """Test validation with checksum mismatch."""
        # Set incorrect checksum
        file_backup_info.checksum = "incorrect_checksum"
        
        result = await recovery_validator.validate_backup(file_backup_info)
        
        assert result.is_valid is False
        assert any("checksum mismatch" in error.lower() for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_backup_no_checksum(self, recovery_validator, file_backup_info):
        """Test validation with no checksum."""
        file_backup_info.checksum = None
        
        result = await recovery_validator.validate_backup(file_backup_info)
        
        assert len(result.warnings) > 0
        assert any("no checksum" in warning.lower() for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_archive_content(self, recovery_validator, temp_dir):
        """Test archive content validation."""
        import tarfile
        
        # Create a proper tar archive
        backup_file = os.path.join(temp_dir, "test_backup.tar.gz")
        with tarfile.open(backup_file, "w:gz") as tar:
            # Create a test file to add to archive
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")
            tar.add(test_file, arcname="test.txt")
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=os.path.getsize(backup_file),
            checksum="test_checksum",
            metadata={"backup_type": "file_archive"}
        )
        
        result = await recovery_validator.validate_backup(backup_info)
        
        assert "archive_members" in result.details
        assert result.details["archive_members"] > 0
    
    @pytest.mark.asyncio
    async def test_validate_empty_database_backup(self, recovery_validator, temp_dir):
        """Test validation of empty database backup."""
        backup_file = os.path.join(temp_dir, "empty_backup.sql")
        with open(backup_file, "w") as f:
            f.write("")  # Empty file
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=0,
            checksum="empty_checksum",
            metadata={"backup_type": "database_dump", "database_type": "mysql"}
        )
        
        result = await recovery_validator.validate_backup(backup_info)
        
        assert result.is_valid is False
        assert any("empty" in error.lower() for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_config_backup_invalid_json(self, recovery_validator, temp_dir):
        """Test validation of config backup with invalid JSON."""
        backup_file = os.path.join(temp_dir, "invalid_config.json")
        with open(backup_file, "w") as f:
            f.write("invalid json content")
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=len("invalid json content"),
            checksum="invalid_checksum",
            metadata={"backup_type": "configuration"}
        )
        
        result = await recovery_validator.validate_backup(backup_info)
        
        assert result.is_valid is False
        assert any("invalid json" in error.lower() for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_config_backup_missing_fields(self, recovery_validator, temp_dir):
        """Test validation of config backup with missing required fields."""
        backup_file = os.path.join(temp_dir, "incomplete_config.json")
        config_data = {"backup_id": "test"}  # Missing required fields
        with open(backup_file, "w") as f:
            json.dump(config_data, f)
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=len(json.dumps(config_data)),
            checksum="incomplete_checksum",
            metadata={"backup_type": "configuration"}
        )
        
        result = await recovery_validator.validate_backup(backup_info)
        
        assert result.is_valid is False
        assert any("missing required fields" in error.lower() for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_expired_backup(self, recovery_validator, file_backup_info):
        """Test validation of expired backup."""
        file_backup_info.expires_at = datetime.utcnow() - timedelta(days=1)
        
        result = await recovery_validator.validate_backup(file_backup_info)
        
        assert len(result.warnings) > 0
        assert any("expired" in warning.lower() for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_unverified_backup(self, recovery_validator, file_backup_info):
        """Test validation of unverified backup."""
        file_backup_info.verified = False
        
        result = await recovery_validator.validate_backup(file_backup_info)
        
        assert len(result.warnings) > 0
        assert any("not been previously verified" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_old_verification(self, recovery_validator, file_backup_info):
        """Test validation of backup with old verification."""
        file_backup_info.verified = True
        file_backup_info.verification_date = datetime.utcnow() - timedelta(days=35)
        
        result = await recovery_validator.validate_backup(file_backup_info)
        
        assert len(result.warnings) > 0
        assert any("days old" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_validate_multiple_backups(self, recovery_validator, file_backup_info, database_backup_info):
        """Test validation of multiple backups."""
        backups = [file_backup_info, database_backup_info]
        
        results = await recovery_validator.validate_multiple_backups(backups)
        
        assert len(results) == 2
        assert file_backup_info.id in results
        assert database_backup_info.id in results
    
    @pytest.mark.asyncio
    async def test_validate_multiple_backups_with_exception(self, recovery_validator, file_backup_info):
        """Test validation of multiple backups with exception."""
        # Create a backup that will cause an exception
        bad_backup = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=None,  # This will cause an exception
            metadata={"backup_type": "file_archive"}
        )
        
        backups = [file_backup_info, bad_backup]
        
        results = await recovery_validator.validate_multiple_backups(backups)
        
        assert len(results) == 2
        assert results[file_backup_info.id].is_valid is True
        assert results[bad_backup.id].is_valid is False
    
    @pytest.mark.asyncio
    async def test_check_database_tools(self, recovery_validator):
        """Test database tools availability check."""
        result = ValidationResult()
        
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/mysql"
            
            await recovery_validator._check_database_tools("mysql", result)
            
            assert result.details["mysql_available"] is True
            assert len(result.warnings) == 0
    
    @pytest.mark.asyncio
    async def test_check_database_tools_missing(self, recovery_validator):
        """Test database tools availability check with missing tool."""
        result = ValidationResult()
        
        with patch('shutil.which') as mock_which:
            mock_which.return_value = None
            
            await recovery_validator._check_database_tools("mysql", result)
            
            assert len(result.warnings) > 0
            assert any("not found" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_check_disk_space(self, recovery_validator, file_backup_info):
        """Test disk space check."""
        result = ValidationResult()
        
        with patch('shutil.disk_usage') as mock_disk_usage:
            # Mock sufficient disk space
            mock_disk_usage.return_value = (1000000000, 500000000, 500000000)  # 1GB total, 500MB free
            
            await recovery_validator._check_disk_space(file_backup_info, result)
            
            assert "disk_space" in result.details
            assert len(result.warnings) == 0
    
    @pytest.mark.asyncio
    async def test_check_disk_space_insufficient(self, recovery_validator, file_backup_info):
        """Test disk space check with insufficient space."""
        result = ValidationResult()
        file_backup_info.size = 1000000000  # 1GB backup
        
        with patch('shutil.disk_usage') as mock_disk_usage:
            # Mock insufficient disk space
            mock_disk_usage.return_value = (1000000000, 900000000, 100000000)  # 1GB total, 100MB free
            
            await recovery_validator._check_disk_space(file_backup_info, result)
            
            assert len(result.warnings) > 0
            assert any("insufficient disk space" in warning.lower() for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_test_restore_capability_file(self, recovery_validator, temp_dir):
        """Test restore capability testing for file backup."""
        import tarfile
        
        # Create a proper tar archive
        backup_file = os.path.join(temp_dir, "test_backup.tar.gz")
        with tarfile.open(backup_file, "w:gz") as tar:
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")
            tar.add(test_file, arcname="test.txt")
        
        backup_info = BackupInfo(
            id=str(uuid.uuid4()),
            type=BackupType.FULL,
            source_system="wordpress",
            location=backup_file,
            size=os.path.getsize(backup_file),
            checksum="test_checksum",
            metadata={"backup_type": "file_archive"}
        )
        
        result = await recovery_validator.test_restore_capability(backup_info)
        
        assert result.details["test_restore_successful"] is True
    
    @pytest.mark.asyncio
    async def test_test_restore_capability_unsupported(self, recovery_validator, database_backup_info):
        """Test restore capability testing for unsupported backup type."""
        result = await recovery_validator.test_restore_capability(database_backup_info)
        
        assert len(result.warnings) > 0
        assert any("not implemented" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_generate_validation_report(self, recovery_validator, file_backup_info, database_backup_info):
        """Test validation report generation."""
        # Create validation results
        validation_results = {
            file_backup_info.id: ValidationResult(),
            database_backup_info.id: ValidationResult()
        }
        
        # Make one backup invalid
        validation_results[database_backup_info.id].add_error("Test error")
        validation_results[database_backup_info.id].add_warning("Test warning")
        
        report = await recovery_validator.generate_validation_report(validation_results)
        
        assert "validation_summary" in report
        assert "backup_results" in report
        assert "recommendations" in report
        
        summary = report["validation_summary"]
        assert summary["total_backups"] == 2
        assert summary["valid_backups"] == 1
        assert summary["invalid_backups"] == 1
        assert summary["total_errors"] == 1
        assert summary["total_warnings"] == 1
        
        # Check recommendations
        assert len(report["recommendations"]) > 0
        assert any("immediate attention" in rec.lower() for rec in report["recommendations"])
    
    def test_logging(self, recovery_validator):
        """Test validation operation logging."""
        # Clear existing logs
        recovery_validator.clear_logs()
        
        # Perform an operation that generates logs
        recovery_validator._log("INFO", "Test log message", "test_backup_id")
        
        # Check logs
        logs = recovery_validator.get_logs()
        assert len(logs) == 1
        assert logs[0].message == "Test log message"
        assert logs[0].details["backup_id"] == "test_backup_id"
        
        # Test filtered logs
        filtered_logs = recovery_validator.get_logs("test_backup_id")
        assert len(filtered_logs) == 1
        
        # Clear logs
        recovery_validator.clear_logs()
        assert len(recovery_validator.get_logs()) == 0


class TestValidationResult:
    """Test cases for ValidationResult."""
    
    def test_validation_result_creation(self):
        """Test validation result creation."""
        result = ValidationResult()
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert isinstance(result.details, dict)
        assert result.validation_time is not None
    
    def test_add_error(self):
        """Test adding error to validation result."""
        result = ValidationResult()
        result.add_error("Test error")
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
    
    def test_add_warning(self):
        """Test adding warning to validation result."""
        result = ValidationResult()
        result.add_warning("Test warning")
        
        assert result.is_valid is True  # Warnings don't make result invalid
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
    
    def test_to_dict(self):
        """Test converting validation result to dictionary."""
        result = ValidationResult()
        result.add_error("Test error")
        result.add_warning("Test warning")
        result.details["test_key"] = "test_value"
        
        result_dict = result.to_dict()
        
        assert "is_valid" in result_dict
        assert "errors" in result_dict
        assert "warnings" in result_dict
        assert "details" in result_dict
        assert "validation_time" in result_dict
        assert "error_count" in result_dict
        assert "warning_count" in result_dict
        
        assert result_dict["is_valid"] is False
        assert result_dict["error_count"] == 1
        assert result_dict["warning_count"] == 1
        assert result_dict["details"]["test_key"] == "test_value"