"""Data validation module for post-migration data integrity checks."""

import logging
import hashlib
from typing import Dict, Any, List, Optional, Set, Tuple, AsyncGenerator
from datetime import datetime
from sqlalchemy import create_engine, text, MetaData, Table, inspect
from sqlalchemy.engine import Engine, Inspector
from sqlalchemy.exc import SQLAlchemyError
from dataclasses import dataclass
from enum import Enum

from .config import DatabaseConfigUnion, DatabaseType
from .schema_analyzer import SchemaAnalyzer, SchemaAnalysisResult
from ..core.exceptions import UnsupportedDatabaseError


logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Data validation levels."""
    BASIC = "basic"          # Row counts only
    STANDARD = "standard"    # Row counts + checksums
    COMPREHENSIVE = "comprehensive"  # Full data comparison


class ValidationStatus(str, Enum):
    """Validation status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    table_name: str
    check_type: str
    status: ValidationStatus
    source_value: Any = None
    destination_value: Any = None
    message: str = ""
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class TableValidationSummary:
    """Summary of validation results for a table."""
    table_name: str
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    validation_time_seconds: float = 0.0
    results: List[ValidationResult] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.passed_checks / self.total_checks) * 100
    
    @property
    def overall_status(self) -> ValidationStatus:
        """Get overall validation status for the table."""
        if self.failed_checks > 0:
            return ValidationStatus.FAILED
        elif self.warning_checks > 0:
            return ValidationStatus.WARNING
        elif self.passed_checks > 0:
            return ValidationStatus.PASSED
        else:
            return ValidationStatus.PENDING


class DataValidationReport:
    """Comprehensive data validation report."""
    
    def __init__(self):
        self.validation_time: datetime = datetime.utcnow()
        self.validation_level: ValidationLevel = ValidationLevel.STANDARD
        self.source_config: Optional[DatabaseConfigUnion] = None
        self.destination_config: Optional[DatabaseConfigUnion] = None
        self.table_summaries: Dict[str, TableValidationSummary] = {}
        self.overall_status: ValidationStatus = ValidationStatus.PENDING
        self.total_validation_time_seconds: float = 0.0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def add_table_summary(self, summary: TableValidationSummary) -> None:
        """Add a table validation summary to the report."""
        self.table_summaries[summary.table_name] = summary
        
    def add_error(self, error: str) -> None:
        """Add an error to the report."""
        self.errors.append(error)
        
    def add_warning(self, warning: str) -> None:
        """Add a warning to the report."""
        self.warnings.append(warning)
        
    def finalize(self) -> None:
        """Finalize the report by calculating overall status."""
        if not self.table_summaries:
            self.overall_status = ValidationStatus.FAILED
            return
            
        failed_tables = sum(1 for s in self.table_summaries.values() 
                           if s.overall_status == ValidationStatus.FAILED)
        warning_tables = sum(1 for s in self.table_summaries.values() 
                            if s.overall_status == ValidationStatus.WARNING)
        
        if failed_tables > 0:
            self.overall_status = ValidationStatus.FAILED
        elif warning_tables > 0:
            self.overall_status = ValidationStatus.WARNING
        else:
            self.overall_status = ValidationStatus.PASSED
    
    @property
    def total_tables(self) -> int:
        """Get total number of tables validated."""
        return len(self.table_summaries)
    
    @property
    def passed_tables(self) -> int:
        """Get number of tables that passed validation."""
        return sum(1 for s in self.table_summaries.values() 
                  if s.overall_status == ValidationStatus.PASSED)
    
    @property
    def failed_tables(self) -> int:
        """Get number of tables that failed validation."""
        return sum(1 for s in self.table_summaries.values() 
                  if s.overall_status == ValidationStatus.FAILED)
    
    @property
    def warning_tables(self) -> int:
        """Get number of tables with warnings."""
        return sum(1 for s in self.table_summaries.values() 
                  if s.overall_status == ValidationStatus.WARNING)
    
    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate across all tables."""
        if not self.table_summaries:
            return 0.0
        
        total_checks = sum(s.total_checks for s in self.table_summaries.values())
        passed_checks = sum(s.passed_checks for s in self.table_summaries.values())
        
        if total_checks == 0:
            return 0.0
        return (passed_checks / total_checks) * 100


class DataValidator:
    """Data validator for post-migration data integrity checks."""
    
    def __init__(self):
        """Initialize the data validator."""
        self.schema_analyzer = SchemaAnalyzer()
        self._supported_types = {
            DatabaseType.MYSQL,
            DatabaseType.POSTGRESQL, 
            DatabaseType.SQLITE,
            DatabaseType.AWS_RDS_MYSQL,
            DatabaseType.AWS_RDS_POSTGRESQL,
            DatabaseType.GOOGLE_CLOUD_SQL,
            DatabaseType.AZURE_SQL
        }
    
    def _create_engine(self, config: DatabaseConfigUnion) -> Engine:
        """Create SQLAlchemy engine from database configuration.
        
        Args:
            config: Database configuration
            
        Returns:
            SQLAlchemy Engine instance
            
        Raises:
            UnsupportedDatabaseError: If database type is not supported
        """
        return self.schema_analyzer._create_engine(config)
    
    async def validate_migration(self, 
                               source_config: DatabaseConfigUnion,
                               destination_config: DatabaseConfigUnion,
                               tables: Optional[List[str]] = None,
                               validation_level: ValidationLevel = ValidationLevel.STANDARD,
                               sample_size: Optional[int] = None) -> DataValidationReport:
        """Validate data integrity after migration.
        
        Args:
            source_config: Source database configuration
            destination_config: Destination database configuration
            tables: Specific tables to validate (None for all tables)
            validation_level: Level of validation to perform
            sample_size: Number of rows to sample for comprehensive validation
            
        Returns:
            Data validation report
        """
        report = DataValidationReport()
        report.validation_level = validation_level
        report.source_config = source_config
        report.destination_config = destination_config
        
        start_time = datetime.utcnow()
        
        try:
            # Create database connections
            source_engine = self._create_engine(source_config)
            dest_engine = self._create_engine(destination_config)
            
            # Get table list if not specified
            if tables is None:
                source_inspector = inspect(source_engine)
                tables = source_inspector.get_table_names()
            
            # Validate each table
            for table_name in tables:
                try:
                    table_summary = await self._validate_table(
                        source_engine, dest_engine, table_name, 
                        validation_level, sample_size
                    )
                    report.add_table_summary(table_summary)
                    
                except Exception as e:
                    error_msg = f"Failed to validate table {table_name}: {str(e)}"
                    report.add_error(error_msg)
                    logger.error(error_msg)
                    
                    # Create a failed summary for this table
                    failed_summary = TableValidationSummary(
                        table_name=table_name,
                        total_checks=1,
                        failed_checks=1
                    )
                    failed_summary.results.append(ValidationResult(
                        table_name=table_name,
                        check_type="validation_error",
                        status=ValidationStatus.FAILED,
                        message=error_msg
                    ))
                    report.add_table_summary(failed_summary)
            
        except Exception as e:
            error_msg = f"Migration validation failed: {str(e)}"
            report.add_error(error_msg)
            logger.error(error_msg)
        
        # Finalize report
        end_time = datetime.utcnow()
        report.total_validation_time_seconds = (end_time - start_time).total_seconds()
        report.finalize()
        
        return report
    
    async def _validate_table(self, 
                             source_engine: Engine,
                             dest_engine: Engine,
                             table_name: str,
                             validation_level: ValidationLevel,
                             sample_size: Optional[int]) -> TableValidationSummary:
        """Validate a specific table.
        
        Args:
            source_engine: Source database engine
            dest_engine: Destination database engine
            table_name: Name of table to validate
            validation_level: Level of validation to perform
            sample_size: Number of rows to sample for comprehensive validation
            
        Returns:
            Table validation summary
        """
        summary = TableValidationSummary(table_name=table_name)
        start_time = datetime.utcnow()
        
        try:
            # Basic validation: row count comparison
            row_count_result = await self._validate_row_count(
                source_engine, dest_engine, table_name
            )
            summary.results.append(row_count_result)
            summary.total_checks += 1
            
            if row_count_result.status == ValidationStatus.PASSED:
                summary.passed_checks += 1
            elif row_count_result.status == ValidationStatus.FAILED:
                summary.failed_checks += 1
            else:
                summary.warning_checks += 1
            
            # Standard validation: add checksum validation
            if validation_level in (ValidationLevel.STANDARD, ValidationLevel.COMPREHENSIVE):
                checksum_result = await self._validate_table_checksum(
                    source_engine, dest_engine, table_name
                )
                summary.results.append(checksum_result)
                summary.total_checks += 1
                
                if checksum_result.status == ValidationStatus.PASSED:
                    summary.passed_checks += 1
                elif checksum_result.status == ValidationStatus.FAILED:
                    summary.failed_checks += 1
                else:
                    summary.warning_checks += 1
            
            # Comprehensive validation: sample data comparison
            if validation_level == ValidationLevel.COMPREHENSIVE:
                sample_results = await self._validate_sample_data(
                    source_engine, dest_engine, table_name, sample_size
                )
                summary.results.extend(sample_results)
                
                for result in sample_results:
                    summary.total_checks += 1
                    if result.status == ValidationStatus.PASSED:
                        summary.passed_checks += 1
                    elif result.status == ValidationStatus.FAILED:
                        summary.failed_checks += 1
                    else:
                        summary.warning_checks += 1
            
            # Additional validations
            constraint_results = await self._validate_constraints(
                source_engine, dest_engine, table_name
            )
            summary.results.extend(constraint_results)
            
            for result in constraint_results:
                summary.total_checks += 1
                if result.status == ValidationStatus.PASSED:
                    summary.passed_checks += 1
                elif result.status == ValidationStatus.FAILED:
                    summary.failed_checks += 1
                else:
                    summary.warning_checks += 1
            
        except Exception as e:
            error_result = ValidationResult(
                table_name=table_name,
                check_type="table_validation_error",
                status=ValidationStatus.FAILED,
                message=f"Table validation failed: {str(e)}"
            )
            summary.results.append(error_result)
            summary.total_checks += 1
            summary.failed_checks += 1
        
        end_time = datetime.utcnow()
        summary.validation_time_seconds = (end_time - start_time).total_seconds()
        
        return summary
    
    async def _validate_row_count(self, 
                                source_engine: Engine,
                                dest_engine: Engine,
                                table_name: str) -> ValidationResult:
        """Validate row count between source and destination tables.
        
        Args:
            source_engine: Source database engine
            dest_engine: Destination database engine
            table_name: Name of table to validate
            
        Returns:
            Validation result for row count check
        """
        try:
            with source_engine.connect() as source_conn:
                source_result = source_conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                source_count = source_result.scalar()
            
            with dest_engine.connect() as dest_conn:
                dest_result = dest_conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                dest_count = dest_result.scalar()
            
            if source_count == dest_count:
                return ValidationResult(
                    table_name=table_name,
                    check_type="row_count",
                    status=ValidationStatus.PASSED,
                    source_value=source_count,
                    destination_value=dest_count,
                    message=f"Row counts match: {source_count} rows"
                )
            else:
                return ValidationResult(
                    table_name=table_name,
                    check_type="row_count",
                    status=ValidationStatus.FAILED,
                    source_value=source_count,
                    destination_value=dest_count,
                    message=f"Row count mismatch: source={source_count}, destination={dest_count}"
                )
                
        except Exception as e:
            return ValidationResult(
                table_name=table_name,
                check_type="row_count",
                status=ValidationStatus.FAILED,
                message=f"Row count validation failed: {str(e)}"
            )
    
    async def _validate_table_checksum(self, 
                                     source_engine: Engine,
                                     dest_engine: Engine,
                                     table_name: str) -> ValidationResult:
        """Validate table data using checksums.
        
        Args:
            source_engine: Source database engine
            dest_engine: Destination database engine
            table_name: Name of table to validate
            
        Returns:
            Validation result for checksum check
        """
        try:
            # Get table structure first
            source_inspector = inspect(source_engine)
            columns = source_inspector.get_columns(table_name)
            column_names = [col['name'] for col in columns]
            
            if not column_names:
                return ValidationResult(
                    table_name=table_name,
                    check_type="checksum",
                    status=ValidationStatus.WARNING,
                    message="No columns found for checksum validation"
                )
            
            # Create column list for query
            column_list = ', '.join(f'"{col}"' for col in column_names)
            
            # Get checksums from both databases
            source_checksum = await self._calculate_table_checksum(
                source_engine, table_name, column_list
            )
            dest_checksum = await self._calculate_table_checksum(
                dest_engine, table_name, column_list
            )
            
            if source_checksum == dest_checksum:
                return ValidationResult(
                    table_name=table_name,
                    check_type="checksum",
                    status=ValidationStatus.PASSED,
                    source_value=source_checksum,
                    destination_value=dest_checksum,
                    message="Table checksums match"
                )
            else:
                return ValidationResult(
                    table_name=table_name,
                    check_type="checksum",
                    status=ValidationStatus.FAILED,
                    source_value=source_checksum,
                    destination_value=dest_checksum,
                    message="Table checksums do not match"
                )
                
        except Exception as e:
            return ValidationResult(
                table_name=table_name,
                check_type="checksum",
                status=ValidationStatus.FAILED,
                message=f"Checksum validation failed: {str(e)}"
            )
    
    async def _calculate_table_checksum(self, 
                                      engine: Engine,
                                      table_name: str,
                                      column_list: str) -> str:
        """Calculate checksum for a table.
        
        Args:
            engine: Database engine
            table_name: Name of table
            column_list: Comma-separated list of columns
            
        Returns:
            Hexadecimal checksum string
        """
        with engine.connect() as conn:
            # Order by all columns to ensure consistent ordering
            query = f'SELECT {column_list} FROM "{table_name}" ORDER BY {column_list}'
            result = conn.execute(text(query))
            
            # Calculate checksum of all data
            hasher = hashlib.md5()
            for row in result:
                # Convert row to string and hash it
                row_str = '|'.join(str(value) if value is not None else 'NULL' for value in row)
                hasher.update(row_str.encode('utf-8'))
            
            return hasher.hexdigest()
    
    async def _validate_sample_data(self, 
                                  source_engine: Engine,
                                  dest_engine: Engine,
                                  table_name: str,
                                  sample_size: Optional[int]) -> List[ValidationResult]:
        """Validate sample data between source and destination.
        
        Args:
            source_engine: Source database engine
            dest_engine: Destination database engine
            table_name: Name of table to validate
            sample_size: Number of rows to sample
            
        Returns:
            List of validation results for sample data
        """
        results = []
        
        try:
            # Get table structure
            source_inspector = inspect(source_engine)
            columns = source_inspector.get_columns(table_name)
            column_names = [col['name'] for col in columns]
            
            if not column_names:
                results.append(ValidationResult(
                    table_name=table_name,
                    check_type="sample_data",
                    status=ValidationStatus.WARNING,
                    message="No columns found for sample data validation"
                ))
                return results
            
            # Get primary key for sampling
            pk_constraint = source_inspector.get_pk_constraint(table_name)
            pk_columns = pk_constraint.get('constrained_columns', []) if pk_constraint else []
            
            if not pk_columns:
                # Use first column as fallback
                pk_columns = [column_names[0]]
            
            # Determine sample size
            if sample_size is None:
                with source_engine.connect() as conn:
                    count_result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    total_rows = count_result.scalar()
                    sample_size = min(1000, max(10, total_rows // 100))  # 1% sample, min 10, max 1000
            
            # Get sample data from source
            pk_column = pk_columns[0]  # Use first PK column for sampling
            column_list = ', '.join(f'"{col}"' for col in column_names)
            
            with source_engine.connect() as source_conn:
                sample_query = f'''
                    SELECT {column_list} 
                    FROM "{table_name}" 
                    ORDER BY "{pk_column}" 
                    LIMIT {sample_size}
                '''
                source_data = source_conn.execute(text(sample_query)).fetchall()
            
            # Get corresponding data from destination
            with dest_engine.connect() as dest_conn:
                dest_data = dest_conn.execute(text(sample_query)).fetchall()
            
            # Compare sample data
            if len(source_data) != len(dest_data):
                results.append(ValidationResult(
                    table_name=table_name,
                    check_type="sample_data_count",
                    status=ValidationStatus.FAILED,
                    source_value=len(source_data),
                    destination_value=len(dest_data),
                    message=f"Sample data count mismatch: source={len(source_data)}, destination={len(dest_data)}"
                ))
            else:
                # Compare row by row
                mismatches = 0
                for i, (source_row, dest_row) in enumerate(zip(source_data, dest_data)):
                    if source_row != dest_row:
                        mismatches += 1
                        if mismatches <= 5:  # Report first 5 mismatches
                            results.append(ValidationResult(
                                table_name=table_name,
                                check_type="sample_data_row",
                                status=ValidationStatus.FAILED,
                                source_value=dict(zip(column_names, source_row)),
                                destination_value=dict(zip(column_names, dest_row)),
                                message=f"Row {i+1} data mismatch",
                                details={'row_index': i}
                            ))
                
                if mismatches == 0:
                    results.append(ValidationResult(
                        table_name=table_name,
                        check_type="sample_data",
                        status=ValidationStatus.PASSED,
                        message=f"All {len(source_data)} sample rows match"
                    ))
                elif mismatches > 5:
                    results.append(ValidationResult(
                        table_name=table_name,
                        check_type="sample_data_summary",
                        status=ValidationStatus.FAILED,
                        message=f"Total {mismatches} row mismatches found in sample of {len(source_data)} rows"
                    ))
                    
        except Exception as e:
            results.append(ValidationResult(
                table_name=table_name,
                check_type="sample_data",
                status=ValidationStatus.FAILED,
                message=f"Sample data validation failed: {str(e)}"
            ))
        
        return results
    
    async def _validate_constraints(self, 
                                  source_engine: Engine,
                                  dest_engine: Engine,
                                  table_name: str) -> List[ValidationResult]:
        """Validate constraints between source and destination.
        
        Args:
            source_engine: Source database engine
            dest_engine: Destination database engine
            table_name: Name of table to validate
            
        Returns:
            List of validation results for constraints
        """
        results = []
        
        try:
            source_inspector = inspect(source_engine)
            dest_inspector = inspect(dest_engine)
            
            # Validate primary key
            source_pk = source_inspector.get_pk_constraint(table_name)
            dest_pk = dest_inspector.get_pk_constraint(table_name)
            
            source_pk_cols = set(source_pk.get('constrained_columns', [])) if source_pk else set()
            dest_pk_cols = set(dest_pk.get('constrained_columns', [])) if dest_pk else set()
            
            if source_pk_cols == dest_pk_cols:
                results.append(ValidationResult(
                    table_name=table_name,
                    check_type="primary_key",
                    status=ValidationStatus.PASSED,
                    message="Primary key constraints match"
                ))
            else:
                results.append(ValidationResult(
                    table_name=table_name,
                    check_type="primary_key",
                    status=ValidationStatus.FAILED,
                    source_value=list(source_pk_cols),
                    destination_value=list(dest_pk_cols),
                    message="Primary key constraints do not match"
                ))
            
            # Validate foreign keys
            source_fks = source_inspector.get_foreign_keys(table_name)
            dest_fks = dest_inspector.get_foreign_keys(table_name)
            
            if len(source_fks) == len(dest_fks):
                results.append(ValidationResult(
                    table_name=table_name,
                    check_type="foreign_keys",
                    status=ValidationStatus.PASSED,
                    message=f"Foreign key count matches: {len(source_fks)} constraints"
                ))
            else:
                results.append(ValidationResult(
                    table_name=table_name,
                    check_type="foreign_keys",
                    status=ValidationStatus.WARNING,
                    source_value=len(source_fks),
                    destination_value=len(dest_fks),
                    message=f"Foreign key count mismatch: source={len(source_fks)}, destination={len(dest_fks)}"
                ))
            
            # Validate unique constraints
            try:
                source_unique = source_inspector.get_unique_constraints(table_name)
                dest_unique = dest_inspector.get_unique_constraints(table_name)
                
                if len(source_unique) == len(dest_unique):
                    results.append(ValidationResult(
                        table_name=table_name,
                        check_type="unique_constraints",
                        status=ValidationStatus.PASSED,
                        message=f"Unique constraint count matches: {len(source_unique)} constraints"
                    ))
                else:
                    results.append(ValidationResult(
                        table_name=table_name,
                        check_type="unique_constraints",
                        status=ValidationStatus.WARNING,
                        source_value=len(source_unique),
                        destination_value=len(dest_unique),
                        message=f"Unique constraint count mismatch: source={len(source_unique)}, destination={len(dest_unique)}"
                    ))
            except Exception as e:
                results.append(ValidationResult(
                    table_name=table_name,
                    check_type="unique_constraints",
                    status=ValidationStatus.WARNING,
                    message=f"Could not validate unique constraints: {str(e)}"
                ))
                
        except Exception as e:
            results.append(ValidationResult(
                table_name=table_name,
                check_type="constraints",
                status=ValidationStatus.FAILED,
                message=f"Constraint validation failed: {str(e)}"
            ))
        
        return results
    
    async def validate_data_integrity(self, 
                                    config: DatabaseConfigUnion,
                                    tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Validate data integrity within a single database.
        
        Args:
            config: Database configuration
            tables: Specific tables to validate (None for all tables)
            
        Returns:
            Data integrity validation results
        """
        results = {
            'success': True,
            'tables_validated': 0,
            'integrity_issues': [],
            'warnings': []
        }
        
        try:
            engine = self._create_engine(config)
            inspector = inspect(engine)
            
            if tables is None:
                tables = inspector.get_table_names()
            
            for table_name in tables:
                try:
                    # Check for orphaned foreign key references
                    fk_issues = await self._check_foreign_key_integrity(engine, inspector, table_name)
                    if fk_issues:
                        results['integrity_issues'].extend(fk_issues)
                        results['success'] = False
                    
                    # Check for duplicate primary keys
                    pk_issues = await self._check_primary_key_integrity(engine, inspector, table_name)
                    if pk_issues:
                        results['integrity_issues'].extend(pk_issues)
                        results['success'] = False
                    
                    results['tables_validated'] += 1
                    
                except Exception as e:
                    error_msg = f"Integrity check failed for table {table_name}: {str(e)}"
                    results['warnings'].append(error_msg)
                    logger.warning(error_msg)
                    
        except Exception as e:
            results['success'] = False
            results['integrity_issues'].append(f"Data integrity validation failed: {str(e)}")
            logger.error(f"Data integrity validation failed: {e}")
        
        return results
    
    async def _check_foreign_key_integrity(self, 
                                         engine: Engine,
                                         inspector: Inspector,
                                         table_name: str) -> List[str]:
        """Check foreign key integrity for a table.
        
        Args:
            engine: Database engine
            inspector: SQLAlchemy Inspector
            table_name: Name of table to check
            
        Returns:
            List of integrity issues found
        """
        issues = []
        
        try:
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            for fk in foreign_keys:
                constrained_columns = fk.get('constrained_columns', [])
                referred_table = fk.get('referred_table')
                referred_columns = fk.get('referred_columns', [])
                
                if not constrained_columns or not referred_table or not referred_columns:
                    continue
                
                # Check for orphaned records
                with engine.connect() as conn:
                    fk_col = constrained_columns[0]  # Simplified for single-column FKs
                    ref_col = referred_columns[0]
                    
                    orphan_query = f'''
                        SELECT COUNT(*) 
                        FROM "{table_name}" t1
                        LEFT JOIN "{referred_table}" t2 ON t1."{fk_col}" = t2."{ref_col}"
                        WHERE t1."{fk_col}" IS NOT NULL AND t2."{ref_col}" IS NULL
                    '''
                    
                    result = conn.execute(text(orphan_query))
                    orphan_count = result.scalar()
                    
                    if orphan_count > 0:
                        issues.append(
                            f"Table {table_name}: {orphan_count} orphaned records found "
                            f"in foreign key {fk_col} -> {referred_table}.{ref_col}"
                        )
                        
        except Exception as e:
            logger.warning(f"Could not check foreign key integrity for {table_name}: {e}")
        
        return issues
    
    async def _check_primary_key_integrity(self, 
                                         engine: Engine,
                                         inspector: Inspector,
                                         table_name: str) -> List[str]:
        """Check primary key integrity for a table.
        
        Args:
            engine: Database engine
            inspector: SQLAlchemy Inspector
            table_name: Name of table to check
            
        Returns:
            List of integrity issues found
        """
        issues = []
        
        try:
            pk_constraint = inspector.get_pk_constraint(table_name)
            
            if not pk_constraint or not pk_constraint.get('constrained_columns'):
                return issues  # No primary key to check
            
            pk_columns = pk_constraint['constrained_columns']
            
            # Check for duplicate primary keys
            with engine.connect() as conn:
                pk_column_list = ', '.join(f'"{col}"' for col in pk_columns)
                
                duplicate_query = f'''
                    SELECT {pk_column_list}, COUNT(*) as cnt
                    FROM "{table_name}"
                    GROUP BY {pk_column_list}
                    HAVING COUNT(*) > 1
                '''
                
                result = conn.execute(text(duplicate_query))
                duplicates = result.fetchall()
                
                if duplicates:
                    issues.append(
                        f"Table {table_name}: {len(duplicates)} duplicate primary key values found"
                    )
                    
        except Exception as e:
            logger.warning(f"Could not check primary key integrity for {table_name}: {e}")
        
        return issues