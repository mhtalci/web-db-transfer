"""
Codebase Checkup Orchestrator

Main orchestration engine that coordinates analysis, cleanup, and reporting.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Type
import logging

from migration_assistant.checkup.models import (
    CheckupConfig, CheckupResults, AnalysisResults, CleanupResults,
    CodebaseMetrics
)
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.cleaners.base import BaseCleaner
from migration_assistant.checkup.validators.base import BaseValidator
from migration_assistant.checkup.reporters.base import ReportGenerator


class CheckupError(Exception):
    """Base exception for checkup operations."""
    pass


class AnalysisError(CheckupError):
    """Errors during code analysis."""
    pass


class CleanupError(CheckupError):
    """Errors during cleanup operations."""
    pass


class ReportGenerationError(CheckupError):
    """Errors during report generation."""
    pass


class CodebaseOrchestrator:
    """Main orchestrator for codebase checkup and cleanup operations."""
    
    def __init__(self, config: CheckupConfig):
        """
        Initialize the orchestrator with configuration.
        
        Args:
            config: Checkup configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Component registries
        self._analyzers: List[BaseAnalyzer] = []
        self._cleaners: List[BaseCleaner] = []
        self._validators: List[BaseValidator] = []
        self._reporters: List[ReportGenerator] = []
        
        # State tracking
        self._analysis_results: Optional[AnalysisResults] = None
        self._cleanup_results: Optional[CleanupResults] = None
        self._before_metrics: Optional[CodebaseMetrics] = None
        self._after_metrics: Optional[CodebaseMetrics] = None
    
    def register_analyzer(self, analyzer_class: Type[BaseAnalyzer]) -> None:
        """
        Register an analyzer class.
        
        Args:
            analyzer_class: Analyzer class to register
        """
        analyzer = analyzer_class(self.config)
        self._analyzers.append(analyzer)
        self.logger.debug(f"Registered analyzer: {analyzer.name}")
    
    def register_cleaner(self, cleaner_class: Type[BaseCleaner]) -> None:
        """
        Register a cleaner class.
        
        Args:
            cleaner_class: Cleaner class to register
        """
        cleaner = cleaner_class(self.config)
        self._cleaners.append(cleaner)
        self.logger.debug(f"Registered cleaner: {cleaner.name}")
    
    def register_validator(self, validator_class: Type[BaseValidator]) -> None:
        """
        Register a validator class.
        
        Args:
            validator_class: Validator class to register
        """
        validator = validator_class(self.config)
        self._validators.append(validator)
        self.logger.debug(f"Registered validator: {validator.name}")
    
    def register_reporter(self, reporter_class: Type[ReportGenerator]) -> None:
        """
        Register a report generator class.
        
        Args:
            reporter_class: Reporter class to register
        """
        reporter = reporter_class(self.config)
        self._reporters.append(reporter)
        self.logger.debug(f"Registered reporter: {reporter.name}")
    
    async def run_full_checkup(self) -> CheckupResults:
        """
        Run complete checkup including analysis, cleanup, and reporting.
        
        Returns:
            Complete checkup results
        """
        start_time = datetime.now()
        
        try:
            self.logger.info("Starting full codebase checkup")
            
            # Validate configuration
            config_errors = self.config.validate()
            if config_errors:
                raise CheckupError(f"Configuration errors: {', '.join(config_errors)}")
            
            # Capture before metrics
            self._before_metrics = await self._capture_metrics()
            
            # Run analysis
            self._analysis_results = await self.run_analysis_only()
            
            # Run cleanup if enabled and not in dry run mode
            if not self.config.dry_run and (
                self.config.auto_format or 
                self.config.auto_fix_imports or 
                self.config.auto_organize_files
            ):
                self._cleanup_results = await self.run_cleanup_only(self._analysis_results)
                
                # Capture after metrics
                self._after_metrics = await self._capture_metrics()
            
            # Create final results
            duration = datetime.now() - start_time
            results = CheckupResults(
                analysis=self._analysis_results,
                cleanup=self._cleanup_results,
                before_metrics=self._before_metrics,
                after_metrics=self._after_metrics,
                duration=duration,
                success=True
            )
            
            # Generate reports
            await self.generate_reports(results)
            
            self.logger.info(f"Checkup completed successfully in {duration}")
            return results
            
        except Exception as e:
            duration = datetime.now() - start_time
            self.logger.error(f"Checkup failed: {e}")
            
            return CheckupResults(
                analysis=self._analysis_results or AnalysisResults(),
                cleanup=self._cleanup_results,
                before_metrics=self._before_metrics or CodebaseMetrics(),
                after_metrics=self._after_metrics,
                duration=duration,
                success=False,
                error_message=str(e)
            )
    
    async def run_analysis_only(self) -> AnalysisResults:
        """
        Run analysis phase only.
        
        Returns:
            Analysis results
        """
        start_time = datetime.now()
        
        try:
            self.logger.info("Starting code analysis")
            
            # Initialize results
            results = AnalysisResults()
            
            # Run analyzers in parallel
            analyzer_tasks = []
            for analyzer in self._analyzers:
                if self._should_run_analyzer(analyzer):
                    analyzer_tasks.append(self._run_analyzer(analyzer))
            
            if analyzer_tasks:
                analyzer_results = await asyncio.gather(*analyzer_tasks, return_exceptions=True)
                
                # Process analyzer results
                for i, result in enumerate(analyzer_results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Analyzer {self._analyzers[i].name} failed: {result}")
                        continue
                    
                    # Merge issues into results
                    issues, metrics = result
                    self._merge_issues_into_results(results, issues, self._analyzers[i])
                    self._merge_metrics(results.metrics, metrics)
            
            # Run validators
            validator_tasks = []
            for validator in self._validators:
                if self._should_run_validator(validator):
                    validator_tasks.append(self._run_validator(validator))
            
            if validator_tasks:
                validator_results = await asyncio.gather(*validator_tasks, return_exceptions=True)
                
                # Process validator results
                for i, result in enumerate(validator_results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Validator {self._validators[i].name} failed: {result}")
                        continue
                    
                    # Merge validation issues into results
                    validation_result, metrics = result
                    self._merge_issues_into_results(results, validation_result.issues, self._validators[i])
                    self._merge_metrics(results.metrics, metrics)
            
            # Set final timestamps and duration
            results.timestamp = datetime.now()
            results.duration = results.timestamp - start_time
            
            self.logger.info(f"Analysis completed: {results.total_issues} issues found")
            return results
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            raise AnalysisError(f"Analysis failed: {e}")
    
    async def run_cleanup_only(self, analysis_results: AnalysisResults) -> CleanupResults:
        """
        Run cleanup phase only.
        
        Args:
            analysis_results: Results from analysis phase
            
        Returns:
            Cleanup results
        """
        start_time = datetime.now()
        
        try:
            self.logger.info("Starting cleanup operations")
            
            # Initialize results
            results = CleanupResults()
            
            # Run cleaners sequentially to avoid conflicts
            for cleaner in self._cleaners:
                if self._should_run_cleaner(cleaner):
                    try:
                        cleanup_result = await cleaner.clean(analysis_results)
                        self._merge_cleanup_results(results, cleanup_result, cleaner)
                        
                        if not cleanup_result.success:
                            self.logger.warning(f"Cleaner {cleaner.name} reported issues: {cleanup_result.message}")
                            
                    except Exception as e:
                        self.logger.error(f"Cleaner {cleaner.name} failed: {e}")
                        continue
            
            # Set final timestamps and duration
            results.timestamp = datetime.now()
            results.duration = results.timestamp - start_time
            
            self.logger.info(f"Cleanup completed: {results.total_changes} changes made")
            return results
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            raise CleanupError(f"Cleanup failed: {e}")
    
    async def generate_reports(self, results: CheckupResults) -> Dict[str, Path]:
        """
        Generate all configured reports.
        
        Args:
            results: Complete checkup results
            
        Returns:
            Dictionary mapping report type to file path
        """
        try:
            self.logger.info("Generating reports")
            
            report_files = {}
            
            for reporter in self._reporters:
                if self._should_run_reporter(reporter):
                    try:
                        # Generate summary report
                        summary_path = await reporter.generate_and_save_summary(results)
                        report_files[f"{reporter.name}_summary"] = summary_path
                        
                        # Generate detailed report
                        detailed_path = await reporter.generate_and_save_detailed(results)
                        report_files[f"{reporter.name}_detailed"] = detailed_path
                        
                        self.logger.info(f"Generated {reporter.name} reports")
                        
                    except Exception as e:
                        self.logger.error(f"Report generator {reporter.name} failed: {e}")
                        continue
            
            return report_files
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            raise ReportGenerationError(f"Report generation failed: {e}")
    
    async def _capture_metrics(self) -> CodebaseMetrics:
        """Capture current codebase metrics."""
        metrics = CodebaseMetrics()
        
        try:
            # Count files by type
            for file_path in self.config.target_directory.rglob("*"):
                if file_path.is_file():
                    metrics.total_files += 1
                    
                    if file_path.suffix == '.py':
                        metrics.python_files += 1
                        if 'test' in file_path.name.lower():
                            metrics.test_files += 1
                    elif file_path.suffix in ['.md', '.rst', '.txt']:
                        metrics.documentation_files += 1
                    elif file_path.name in ['pyproject.toml', 'setup.py', 'requirements.txt']:
                        metrics.config_files += 1
            
            # Count lines of code
            for py_file in self.config.target_directory.rglob("*.py"):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        metrics.total_lines += len(f.readlines())
                except Exception:
                    continue
            
        except Exception as e:
            self.logger.warning(f"Failed to capture some metrics: {e}")
        
        return metrics
    
    async def _run_analyzer(self, analyzer: BaseAnalyzer):
        """Run a single analyzer."""
        try:
            await analyzer.pre_analyze()
            issues = await analyzer.analyze()
            await analyzer.post_analyze(issues)
            return issues, analyzer.metrics
        except Exception as e:
            raise AnalysisError(f"Analyzer {analyzer.name} failed: {e}")
    
    async def _run_validator(self, validator: BaseValidator):
        """Run a single validator."""
        try:
            await validator.pre_validate()
            result = await validator.validate()
            await validator.post_validate(result)
            return result, validator.metrics
        except Exception as e:
            raise AnalysisError(f"Validator {validator.name} failed: {e}")
    
    def _should_run_analyzer(self, analyzer: BaseAnalyzer) -> bool:
        """Determine if an analyzer should run based on configuration."""
        analyzer_name = analyzer.name.lower()
        
        if 'quality' in analyzer_name:
            return self.config.enable_quality_analysis
        elif 'duplicate' in analyzer_name:
            return self.config.enable_duplicate_detection
        elif 'import' in analyzer_name:
            return self.config.enable_import_analysis
        elif 'structure' in analyzer_name:
            return self.config.enable_structure_analysis
        
        return True  # Run by default
    
    def _should_run_cleaner(self, cleaner: BaseCleaner) -> bool:
        """Determine if a cleaner should run based on configuration."""
        cleaner_name = cleaner.name.lower()
        
        if 'formatter' in cleaner_name:
            return self.config.auto_format
        elif 'import' in cleaner_name:
            return self.config.auto_fix_imports
        elif 'file' in cleaner_name or 'organizer' in cleaner_name:
            return self.config.auto_organize_files
        
        return False  # Don't run by default
    
    def _should_run_validator(self, validator: BaseValidator) -> bool:
        """Determine if a validator should run based on configuration."""
        validator_name = validator.name.lower()
        
        if 'coverage' in validator_name:
            return self.config.check_test_coverage
        elif 'config' in validator_name:
            return self.config.validate_configs
        elif 'doc' in validator_name:
            return self.config.validate_docs
        
        return True  # Run by default
    
    def _should_run_reporter(self, reporter: ReportGenerator) -> bool:
        """Determine if a reporter should run based on configuration."""
        reporter_name = reporter.name.lower()
        
        if 'html' in reporter_name:
            return self.config.generate_html_report
        elif 'json' in reporter_name:
            return self.config.generate_json_report
        elif 'markdown' in reporter_name:
            return self.config.generate_markdown_report
        
        return True  # Run by default
    
    def _merge_issues_into_results(self, results: AnalysisResults, issues: List, component) -> None:
        """Merge issues from a component into analysis results."""
        from migration_assistant.checkup.models import (
            QualityIssue, Duplicate, ImportIssue, StructureIssue,
            CoverageGap, ConfigIssue, DocIssue
        )
        
        for issue in issues:
            if isinstance(issue, QualityIssue):
                results.quality_issues.append(issue)
            elif isinstance(issue, Duplicate):
                results.duplicates.append(issue)
            elif isinstance(issue, ImportIssue):
                results.import_issues.append(issue)
            elif isinstance(issue, StructureIssue):
                results.structure_issues.append(issue)
            elif isinstance(issue, CoverageGap):
                results.coverage_gaps.append(issue)
            elif isinstance(issue, ConfigIssue):
                results.config_issues.append(issue)
            elif isinstance(issue, DocIssue):
                results.doc_issues.append(issue)
    
    def _merge_metrics(self, target_metrics: CodebaseMetrics, source_metrics: CodebaseMetrics) -> None:
        """Merge metrics from source into target."""
        # Add numeric metrics
        for attr in ['syntax_errors', 'style_violations', 'code_smells', 'complexity_issues',
                     'unused_imports', 'circular_imports', 'orphaned_modules', 'untested_functions',
                     'duplicate_blocks', 'duplicate_lines', 'misplaced_files', 'empty_directories']:
            if hasattr(source_metrics, attr):
                current_value = getattr(target_metrics, attr, 0)
                source_value = getattr(source_metrics, attr, 0)
                setattr(target_metrics, attr, current_value + source_value)
        
        # Update coverage percentage (take maximum)
        if source_metrics.test_coverage_percentage > target_metrics.test_coverage_percentage:
            target_metrics.test_coverage_percentage = source_metrics.test_coverage_percentage
    
    def _merge_cleanup_results(self, results: CleanupResults, cleanup_result, cleaner) -> None:
        """Merge cleanup results from a cleaner."""
        # This would be implemented based on the specific CleanupResult structure
        # For now, we'll just track that cleanup was attempted
        pass