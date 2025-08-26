"""
JSON Report Generator

Generates JSON reports for programmatic access.
"""

import json
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from migration_assistant.checkup.reporters.base import ReportGenerator
from migration_assistant.checkup.models import (
    CheckupResults, AnalysisResults, CleanupResults, Issue,
    CodebaseMetrics, IssueSeverity, IssueType
)


class JSONReportGenerator(ReportGenerator):
    """Generator for JSON reports with comprehensive data export."""
    
    @property
    def file_extension(self) -> str:
        """Return file extension."""
        return '.json'
    
    async def generate_summary_report(self, results: CheckupResults) -> str:
        """Generate JSON summary report."""
        summary_data = {
            "report_type": "summary",
            "metadata": self.get_report_metadata(results),
            "overview": self._create_overview_data(results),
            "metrics": self._serialize_metrics(results.analysis.metrics),
            "issue_counts": self._create_issue_counts(results.analysis),
            "severity_breakdown": self.get_severity_counts(results.analysis),
            "type_breakdown": self.get_issue_type_counts(results.analysis),
            "quality_score": self.utils.calculate_quality_score(results.analysis),
            "cleanup_summary": self._create_cleanup_summary_data(results.cleanup) if results.cleanup else None,
            "improvements": results.improvement_metrics if results.after_metrics else None
        }
        
        return json.dumps(summary_data, indent=2, default=self._json_serializer)
    
    async def generate_detailed_report(self, results: CheckupResults) -> str:
        """Generate JSON detailed report."""
        detailed_data = {
            "report_type": "detailed",
            "metadata": self.get_report_metadata(results),
            "overview": self._create_overview_data(results),
            "analysis": {
                "metrics": self._serialize_metrics(results.analysis.metrics),
                "duration": str(results.analysis.duration),
                "timestamp": results.analysis.timestamp.isoformat(),
                "total_issues": results.analysis.total_issues
            },
            "issues": {
                "by_severity": self._group_issues_by_severity_json(results.analysis),
                "by_type": self._group_issues_by_type_json(results.analysis),
                "by_file": self._group_issues_by_file_json(results.analysis),
                "all_issues": self._serialize_all_issues(results.analysis)
            },
            "cleanup": self._serialize_cleanup_results(results.cleanup) if results.cleanup else None,
            "before_after": self._create_before_after_data(results) if results.after_metrics else None
        }
        
        return json.dumps(detailed_data, indent=2, default=self._json_serializer)
    
    async def generate_comparison_report(self, before: CheckupResults, after: CheckupResults) -> str:
        """Generate JSON comparison report."""
        time_between = after.analysis.timestamp - before.analysis.timestamp
        
        comparison_data = {
            "report_type": "comparison",
            "metadata": {
                "before": self.get_report_metadata(before),
                "after": self.get_report_metadata(after),
                "comparison_generated_at": datetime.now().isoformat(),
                "time_between_checkups": str(time_between)
            },
            "quality_scores": {
                "before": self.utils.calculate_quality_score(before.analysis),
                "after": self.utils.calculate_quality_score(after.analysis),
                "change": self.utils.calculate_quality_score(after.analysis) - self.utils.calculate_quality_score(before.analysis)
            },
            "metrics_comparison": self._create_metrics_comparison_data(before, after),
            "issues_comparison": self._create_issues_comparison_data(before, after),
            "improvements": self._calculate_improvements(before, after),
            "trend_analysis": self._create_trend_analysis(before, after),
            "detailed_changes": {
                "new_issues": self._find_new_issues(before, after),
                "resolved_issues": self._find_resolved_issues(before, after),
                "persistent_issues": self._find_persistent_issues(before, after)
            }
        }
        
        return json.dumps(comparison_data, indent=2, default=self._json_serializer)
    
    def _create_overview_data(self, results: CheckupResults) -> Dict[str, Any]:
        """Create overview data for JSON export."""
        return {
            "success": results.success,
            "duration": str(results.duration),
            "total_issues": results.analysis.total_issues,
            "files_analyzed": results.analysis.metrics.total_files,
            "quality_score": self.utils.calculate_quality_score(results.analysis),
            "cleanup_performed": results.cleanup is not None,
            "backup_created": results.cleanup.backup_created if results.cleanup else False
        }
    
    def _serialize_metrics(self, metrics: CodebaseMetrics) -> Dict[str, Any]:
        """Serialize codebase metrics to JSON-compatible format."""
        return {
            "files": {
                "total": metrics.total_files,
                "python": metrics.python_files,
                "test": metrics.test_files,
                "documentation": metrics.documentation_files,
                "config": metrics.config_files
            },
            "lines": {
                "total": metrics.total_lines
            },
            "quality": {
                "syntax_errors": metrics.syntax_errors,
                "style_violations": metrics.style_violations,
                "code_smells": metrics.code_smells,
                "complexity_issues": metrics.complexity_issues
            },
            "imports": {
                "unused": metrics.unused_imports,
                "circular": metrics.circular_imports,
                "orphaned_modules": metrics.orphaned_modules
            },
            "testing": {
                "coverage_percentage": metrics.test_coverage_percentage,
                "untested_functions": metrics.untested_functions
            },
            "duplicates": {
                "blocks": metrics.duplicate_blocks,
                "lines": metrics.duplicate_lines
            },
            "structure": {
                "misplaced_files": metrics.misplaced_files,
                "empty_directories": metrics.empty_directories
            },
            "timestamp": metrics.timestamp.isoformat()
        }
    
    def _create_issue_counts(self, analysis: AnalysisResults) -> Dict[str, int]:
        """Create issue counts summary."""
        return {
            "total": analysis.total_issues,
            "quality_issues": len(analysis.quality_issues),
            "duplicates": len(analysis.duplicates),
            "import_issues": len(analysis.import_issues),
            "structure_issues": len(analysis.structure_issues),
            "coverage_gaps": len(analysis.coverage_gaps),
            "config_issues": len(analysis.config_issues),
            "doc_issues": len(analysis.doc_issues)
        }
    
    def _create_cleanup_summary_data(self, cleanup: CleanupResults) -> Dict[str, Any]:
        """Create cleanup summary data."""
        return {
            "total_changes": cleanup.total_changes,
            "successful_changes": cleanup.successful_changes,
            "duration": str(cleanup.duration),
            "backup_created": cleanup.backup_created,
            "backup_path": str(cleanup.backup_path) if cleanup.backup_path else None,
            "changes": {
                "formatting": len(cleanup.formatting_changes),
                "imports": len(cleanup.import_cleanups),
                "file_moves": len(cleanup.file_moves),
                "file_removals": len(cleanup.file_removals),
                "auto_fixes": len(cleanup.auto_fixes)
            }
        }
    
    def _group_issues_by_severity_json(self, analysis: AnalysisResults) -> Dict[str, List[Dict[str, Any]]]:
        """Group issues by severity for JSON export."""
        all_issues = self.get_all_issues(analysis)
        grouped = self.utils.group_issues_by_severity(all_issues)
        
        result = {}
        for severity, issues in grouped.items():
            result[severity.value] = [self._serialize_issue(issue) for issue in issues]
        
        return result
    
    def _group_issues_by_type_json(self, analysis: AnalysisResults) -> Dict[str, List[Dict[str, Any]]]:
        """Group issues by type for JSON export."""
        all_issues = self.get_all_issues(analysis)
        grouped = self.utils.group_issues_by_type(all_issues)
        
        result = {}
        for issue_type, issues in grouped.items():
            result[issue_type.value] = [self._serialize_issue(issue) for issue in issues]
        
        return result
    
    def _group_issues_by_file_json(self, analysis: AnalysisResults) -> Dict[str, List[Dict[str, Any]]]:
        """Group issues by file for JSON export."""
        all_issues = self.get_all_issues(analysis)
        grouped = self.utils.group_issues_by_file(all_issues)
        
        result = {}
        for file_path, issues in grouped.items():
            result[file_path] = [self._serialize_issue(issue) for issue in issues]
        
        return result
    
    def _serialize_all_issues(self, analysis: AnalysisResults) -> List[Dict[str, Any]]:
        """Serialize all issues to JSON format."""
        all_issues = self.get_all_issues(analysis)
        return [self._serialize_issue(issue) for issue in all_issues]
    
    def _serialize_issue(self, issue: Issue) -> Dict[str, Any]:
        """Serialize a single issue to JSON format."""
        base_data = {
            "file_path": str(issue.file_path),
            "line_number": issue.line_number,
            "severity": issue.severity.value,
            "issue_type": issue.issue_type.value,
            "message": issue.message,
            "description": issue.description,
            "suggestion": issue.suggestion,
            "confidence": issue.confidence
        }
        
        # Add type-specific fields
        if hasattr(issue, 'rule_name') and issue.rule_name:
            base_data["rule_name"] = issue.rule_name
        if hasattr(issue, 'tool_name') and issue.tool_name:
            base_data["tool_name"] = issue.tool_name
        if hasattr(issue, 'import_name') and issue.import_name:
            base_data["import_name"] = issue.import_name
        if hasattr(issue, 'is_circular') and issue.is_circular:
            base_data["is_circular"] = issue.is_circular
        if hasattr(issue, 'dependency_chain') and issue.dependency_chain:
            base_data["dependency_chain"] = issue.dependency_chain
        if hasattr(issue, 'similarity_score'):
            base_data["similarity_score"] = issue.similarity_score
        if hasattr(issue, 'duplicate_files') and issue.duplicate_files:
            base_data["duplicate_files"] = [str(f) for f in issue.duplicate_files]
        if hasattr(issue, 'suggested_location') and issue.suggested_location:
            base_data["suggested_location"] = str(issue.suggested_location)
        if hasattr(issue, 'coverage_percentage'):
            base_data["coverage_percentage"] = issue.coverage_percentage
        if hasattr(issue, 'function_name') and issue.function_name:
            base_data["function_name"] = issue.function_name
        if hasattr(issue, 'class_name') and issue.class_name:
            base_data["class_name"] = issue.class_name
        
        return base_data
    
    def _serialize_cleanup_results(self, cleanup: CleanupResults) -> Dict[str, Any]:
        """Serialize cleanup results to JSON format."""
        return {
            "summary": self._create_cleanup_summary_data(cleanup),
            "details": {
                "formatting_changes": [
                    {
                        "file_path": str(change.file_path),
                        "change_type": change.change_type,
                        "lines_changed": change.lines_changed,
                        "description": change.description
                    }
                    for change in cleanup.formatting_changes
                ],
                "import_cleanups": [
                    {
                        "file_path": str(cleanup_item.file_path),
                        "removed_imports": cleanup_item.removed_imports,
                        "reorganized_imports": cleanup_item.reorganized_imports,
                        "circular_imports_resolved": cleanup_item.circular_imports_resolved
                    }
                    for cleanup_item in cleanup.import_cleanups
                ],
                "file_moves": [
                    {
                        "source_path": str(move.source_path),
                        "destination_path": str(move.destination_path),
                        "reason": move.reason,
                        "success": move.success
                    }
                    for move in cleanup.file_moves
                ],
                "file_removals": [
                    {
                        "file_path": str(removal.file_path),
                        "reason": removal.reason,
                        "backup_path": str(removal.backup_path) if removal.backup_path else None,
                        "success": removal.success
                    }
                    for removal in cleanup.file_removals
                ],
                "auto_fixes": [
                    {
                        "file_path": str(fix.file_path),
                        "issue_type": fix.issue_type.value,
                        "fix_description": fix.fix_description,
                        "success": fix.success
                    }
                    for fix in cleanup.auto_fixes
                ]
            }
        }
    
    def _create_before_after_data(self, results: CheckupResults) -> Dict[str, Any]:
        """Create before/after comparison data."""
        if not results.after_metrics:
            return None
        
        return {
            "before": self._serialize_metrics(results.before_metrics),
            "after": self._serialize_metrics(results.after_metrics),
            "improvements": results.improvement_metrics,
            "changes": {
                "issues_fixed": (
                    results.before_metrics.syntax_errors + results.before_metrics.style_violations -
                    results.after_metrics.syntax_errors - results.after_metrics.style_violations
                ),
                "imports_cleaned": results.before_metrics.unused_imports - results.after_metrics.unused_imports,
                "coverage_change": results.after_metrics.test_coverage_percentage - results.before_metrics.test_coverage_percentage
            }
        }
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for complex objects."""
        if isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (IssueSeverity, IssueType)):
            return obj.value
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    def _create_metrics_comparison_data(self, before: CheckupResults, after: CheckupResults) -> Dict[str, Any]:
        """Create metrics comparison data."""
        before_metrics = before.analysis.metrics
        after_metrics = after.analysis.metrics
        
        return {
            "before": self._serialize_metrics(before_metrics),
            "after": self._serialize_metrics(after_metrics),
            "changes": {
                "files": {
                    "total": after_metrics.total_files - before_metrics.total_files,
                    "python": after_metrics.python_files - before_metrics.python_files,
                    "test": after_metrics.test_files - before_metrics.test_files
                },
                "quality": {
                    "syntax_errors": after_metrics.syntax_errors - before_metrics.syntax_errors,
                    "style_violations": after_metrics.style_violations - before_metrics.style_violations,
                    "code_smells": after_metrics.code_smells - before_metrics.code_smells,
                    "complexity_issues": after_metrics.complexity_issues - before_metrics.complexity_issues
                },
                "imports": {
                    "unused": after_metrics.unused_imports - before_metrics.unused_imports,
                    "circular": after_metrics.circular_imports - before_metrics.circular_imports,
                    "orphaned_modules": after_metrics.orphaned_modules - before_metrics.orphaned_modules
                },
                "testing": {
                    "coverage_percentage": after_metrics.test_coverage_percentage - before_metrics.test_coverage_percentage,
                    "untested_functions": after_metrics.untested_functions - before_metrics.untested_functions
                },
                "duplicates": {
                    "blocks": after_metrics.duplicate_blocks - before_metrics.duplicate_blocks,
                    "lines": after_metrics.duplicate_lines - before_metrics.duplicate_lines
                },
                "structure": {
                    "misplaced_files": after_metrics.misplaced_files - before_metrics.misplaced_files,
                    "empty_directories": after_metrics.empty_directories - before_metrics.empty_directories
                }
            }
        }
    
    def _create_issues_comparison_data(self, before: CheckupResults, after: CheckupResults) -> Dict[str, Any]:
        """Create issues comparison data."""
        before_severity = self.get_severity_counts(before.analysis)
        after_severity = self.get_severity_counts(after.analysis)
        before_types = self.get_issue_type_counts(before.analysis)
        after_types = self.get_issue_type_counts(after.analysis)
        
        severity_changes = {}
        for severity in before_severity.keys():
            severity_changes[severity] = after_severity.get(severity, 0) - before_severity[severity]
        
        type_changes = {}
        all_types = set(before_types.keys()) | set(after_types.keys())
        for issue_type in all_types:
            type_changes[issue_type] = after_types.get(issue_type, 0) - before_types.get(issue_type, 0)
        
        return {
            "total_issues": {
                "before": before.analysis.total_issues,
                "after": after.analysis.total_issues,
                "change": after.analysis.total_issues - before.analysis.total_issues
            },
            "by_severity": {
                "before": before_severity,
                "after": after_severity,
                "changes": severity_changes
            },
            "by_type": {
                "before": before_types,
                "after": after_types,
                "changes": type_changes
            }
        }
    
    def _calculate_improvements(self, before: CheckupResults, after: CheckupResults) -> Dict[str, Any]:
        """Calculate improvement metrics."""
        return {
            "issues_fixed": before.analysis.total_issues - after.analysis.total_issues,
            "style_improvements": before.analysis.metrics.style_violations - after.analysis.metrics.style_violations,
            "import_cleanups": before.analysis.metrics.unused_imports - after.analysis.metrics.unused_imports,
            "coverage_improvement": after.analysis.metrics.test_coverage_percentage - before.analysis.metrics.test_coverage_percentage,
            "code_smell_reduction": before.analysis.metrics.code_smells - after.analysis.metrics.code_smells,
            "complexity_reduction": before.analysis.metrics.complexity_issues - after.analysis.metrics.complexity_issues,
            "duplicate_reduction": before.analysis.metrics.duplicate_blocks - after.analysis.metrics.duplicate_blocks,
            "structure_improvements": before.analysis.metrics.misplaced_files - after.analysis.metrics.misplaced_files
        }
    
    def _create_trend_analysis(self, before: CheckupResults, after: CheckupResults) -> Dict[str, Any]:
        """Create trend analysis data."""
        before_score = self.utils.calculate_quality_score(before.analysis)
        after_score = self.utils.calculate_quality_score(after.analysis)
        score_change = after_score - before_score
        
        trend_direction = "improving" if score_change > 0 else "declining" if score_change < 0 else "stable"
        
        # Analyze specific trends
        trends = []
        
        if after.analysis.metrics.style_violations < before.analysis.metrics.style_violations:
            trends.append({"category": "style", "direction": "improving", "description": "Style violations decreased"})
        elif after.analysis.metrics.style_violations > before.analysis.metrics.style_violations:
            trends.append({"category": "style", "direction": "declining", "description": "Style violations increased"})
        
        if after.analysis.metrics.unused_imports < before.analysis.metrics.unused_imports:
            trends.append({"category": "imports", "direction": "improving", "description": "Unused imports cleaned up"})
        elif after.analysis.metrics.unused_imports > before.analysis.metrics.unused_imports:
            trends.append({"category": "imports", "direction": "declining", "description": "More unused imports detected"})
        
        if after.analysis.metrics.test_coverage_percentage > before.analysis.metrics.test_coverage_percentage:
            trends.append({"category": "testing", "direction": "improving", "description": "Test coverage improved"})
        elif after.analysis.metrics.test_coverage_percentage < before.analysis.metrics.test_coverage_percentage:
            trends.append({"category": "testing", "direction": "declining", "description": "Test coverage decreased"})
        
        if after.analysis.metrics.code_smells < before.analysis.metrics.code_smells:
            trends.append({"category": "quality", "direction": "improving", "description": "Code smells reduced"})
        elif after.analysis.metrics.code_smells > before.analysis.metrics.code_smells:
            trends.append({"category": "quality", "direction": "declining", "description": "More code smells detected"})
        
        return {
            "overall_direction": trend_direction,
            "quality_score_change": score_change,
            "specific_trends": trends,
            "improvement_areas": [trend for trend in trends if trend["direction"] == "improving"],
            "concern_areas": [trend for trend in trends if trend["direction"] == "declining"]
        }
    
    def _find_new_issues(self, before: CheckupResults, after: CheckupResults) -> List[Dict[str, Any]]:
        """Find issues that are new in the after report."""
        # This is a simplified implementation - in practice, you'd want to match issues more precisely
        before_issues = self.get_all_issues(before.analysis)
        after_issues = self.get_all_issues(after.analysis)
        
        # Create a simple signature for each issue
        before_signatures = set()
        for issue in before_issues:
            signature = f"{issue.file_path}:{issue.line_number}:{issue.issue_type.value}:{issue.message}"
            before_signatures.add(signature)
        
        new_issues = []
        for issue in after_issues:
            signature = f"{issue.file_path}:{issue.line_number}:{issue.issue_type.value}:{issue.message}"
            if signature not in before_signatures:
                new_issues.append(self._serialize_issue(issue))
        
        return new_issues[:20]  # Limit to first 20 new issues
    
    def _find_resolved_issues(self, before: CheckupResults, after: CheckupResults) -> List[Dict[str, Any]]:
        """Find issues that were resolved between reports."""
        before_issues = self.get_all_issues(before.analysis)
        after_issues = self.get_all_issues(after.analysis)
        
        # Create signatures for after issues
        after_signatures = set()
        for issue in after_issues:
            signature = f"{issue.file_path}:{issue.line_number}:{issue.issue_type.value}:{issue.message}"
            after_signatures.add(signature)
        
        resolved_issues = []
        for issue in before_issues:
            signature = f"{issue.file_path}:{issue.line_number}:{issue.issue_type.value}:{issue.message}"
            if signature not in after_signatures:
                resolved_issues.append(self._serialize_issue(issue))
        
        return resolved_issues[:20]  # Limit to first 20 resolved issues
    
    def _find_persistent_issues(self, before: CheckupResults, after: CheckupResults) -> List[Dict[str, Any]]:
        """Find issues that persist between reports."""
        before_issues = self.get_all_issues(before.analysis)
        after_issues = self.get_all_issues(after.analysis)
        
        # Create signatures for both sets
        before_signatures = {}
        for issue in before_issues:
            signature = f"{issue.file_path}:{issue.line_number}:{issue.issue_type.value}:{issue.message}"
            before_signatures[signature] = issue
        
        after_signatures = set()
        for issue in after_issues:
            signature = f"{issue.file_path}:{issue.line_number}:{issue.issue_type.value}:{issue.message}"
            after_signatures.add(signature)
        
        persistent_issues = []
        for signature, issue in before_signatures.items():
            if signature in after_signatures:
                persistent_issues.append(self._serialize_issue(issue))
        
        return persistent_issues[:20]  # Limit to first 20 persistent issues