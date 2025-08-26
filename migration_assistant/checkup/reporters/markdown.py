"""
Markdown Report Generator

Generates Markdown reports for documentation integration.
"""

from typing import List, Dict, Any
from datetime import datetime

from migration_assistant.checkup.reporters.base import ReportGenerator
from migration_assistant.checkup.models import (
    CheckupResults, AnalysisResults, CleanupResults, Issue,
    IssueSeverity, IssueType
)


class MarkdownReportGenerator(ReportGenerator):
    """Generator for Markdown reports with documentation-friendly formatting."""
    
    @property
    def file_extension(self) -> str:
        """Return file extension."""
        return '.md'
    
    async def generate_summary_report(self, results: CheckupResults) -> str:
        """Generate Markdown summary report."""
        metadata = self.get_report_metadata(results)
        quality_score = self.utils.calculate_quality_score(results.analysis)
        
        sections = [
            self._create_header("Codebase Checkup Summary Report"),
            self._create_overview_section(results, quality_score),
            self._create_metrics_section(results.analysis.metrics),
            self._create_issues_summary_section(results.analysis),
        ]
        
        if results.cleanup:
            sections.append(self._create_cleanup_summary_section(results.cleanup))
        
        if results.after_metrics:
            sections.append(self._create_improvements_section(results))
        
        sections.append(self._create_metadata_section(metadata))
        
        return '\n\n'.join(sections)
    
    async def generate_detailed_report(self, results: CheckupResults) -> str:
        """Generate Markdown detailed report."""
        metadata = self.get_report_metadata(results)
        quality_score = self.utils.calculate_quality_score(results.analysis)
        
        sections = [
            self._create_header("Detailed Codebase Checkup Report"),
            self._create_overview_section(results, quality_score),
            self._create_detailed_analysis_section(results.analysis),
            self._create_issues_by_severity_section(results.analysis),
            self._create_issues_by_file_section(results.analysis),
            self._create_issues_by_type_section(results.analysis),
        ]
        
        if results.cleanup:
            sections.extend([
                self._create_detailed_cleanup_section(results.cleanup),
                self._create_cleanup_details_section(results.cleanup)
            ])
        
        if results.after_metrics:
            sections.append(self._create_before_after_section(results))
        
        sections.extend([
            self._create_recommendations_section(results.analysis),
            self._create_metadata_section(metadata)
        ])
        
        return '\n\n'.join(sections)
    
    async def generate_comparison_report(self, before: CheckupResults, after: CheckupResults) -> str:
        """Generate Markdown comparison report."""
        time_between = after.analysis.timestamp - before.analysis.timestamp
        
        sections = [
            self._create_header("Codebase Checkup Comparison Report"),
            self._create_comparison_overview_section(before, after, time_between),
            self._create_quality_score_comparison_section(before, after),
            self._create_metrics_comparison_section(before, after),
            self._create_issues_comparison_section(before, after),
            self._create_trend_analysis_section(before, after),
            self._create_detailed_changes_section(before, after),
            self._create_recommendations_from_comparison(before, after),
            self._create_comparison_metadata_section(before, after)
        ]
        
        return '\n\n'.join(sections)
    
    def _create_header(self, title: str) -> str:
        """Create report header."""
        return f"# {title}\n\n*Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}*"
    
    def _create_overview_section(self, results: CheckupResults, quality_score: float) -> str:
        """Create overview section."""
        status_emoji = "✅" if results.success else "❌"
        score_emoji = self._get_score_emoji(quality_score)
        
        content = f"""## 📊 Overview

{status_emoji} **Status**: {'Success' if results.success else 'Failed'}
{score_emoji} **Quality Score**: {quality_score}/100
🔍 **Total Issues**: {results.analysis.total_issues}
📁 **Files Analyzed**: {results.analysis.metrics.total_files}
⏱️ **Duration**: {self.format_duration(results.duration)}
{'🧹 **Cleanup Performed**: Yes' if results.cleanup else ''}"""
        
        return content
    
    def _create_metrics_section(self, metrics) -> str:
        """Create metrics section."""
        return f"""## 📈 Codebase Metrics

| Metric | Value |
|--------|-------|
| Total Files | {self.utils.format_number(metrics.total_files)} |
| Python Files | {self.utils.format_number(metrics.python_files)} |
| Test Files | {self.utils.format_number(metrics.test_files)} |
| Total Lines | {self.utils.format_number(metrics.total_lines)} |
| Test Coverage | {self.utils.format_percentage(metrics.test_coverage_percentage)} |
| Syntax Errors | {metrics.syntax_errors} |
| Style Violations | {metrics.style_violations} |
| Unused Imports | {metrics.unused_imports} |"""
    
    def _create_issues_summary_section(self, analysis: AnalysisResults) -> str:
        """Create issues summary section."""
        severity_counts = self.get_severity_counts(analysis)
        type_counts = self.get_issue_type_counts(analysis)
        
        content = ["## 🚨 Issues Summary"]
        
        if analysis.total_issues == 0:
            content.append("🎉 **No issues found!** Your codebase is in excellent shape.")
            return '\n\n'.join(content)
        
        # Severity breakdown
        content.append("### By Severity")
        content.append("| Severity | Count | Icon |")
        content.append("|----------|-------|------|")
        
        for severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.MEDIUM, IssueSeverity.LOW]:
            count = severity_counts.get(severity.value, 0)
            if count > 0:
                icon = self.utils.get_severity_icon(severity)
                content.append(f"| {severity.value.title()} | {count} | {icon} |")
        
        # Type breakdown
        content.append("\n### By Type")
        content.append("| Issue Type | Count |")
        content.append("|------------|-------|")
        
        for issue_type, count in type_counts.items():
            if count > 0:
                formatted_type = issue_type.replace('_', ' ').title()
                content.append(f"| {formatted_type} | {count} |")
        
        return '\n'.join(content)
    
    def _create_cleanup_summary_section(self, cleanup: CleanupResults) -> str:
        """Create cleanup summary section."""
        success_rate = (cleanup.successful_changes / cleanup.total_changes * 100) if cleanup.total_changes > 0 else 100
        
        return f"""## 🧹 Cleanup Summary

✨ **Total Changes**: {cleanup.total_changes}
✅ **Successful**: {cleanup.successful_changes} ({success_rate:.1f}%)
⏱️ **Duration**: {self.format_duration(cleanup.duration)}
💾 **Backup Created**: {'Yes' if cleanup.backup_created else 'No'}

### Changes Made

- 🎨 **Formatting**: {len(cleanup.formatting_changes)} files
- 📦 **Import Cleanup**: {len(cleanup.import_cleanups)} files
- 📁 **File Moves**: {len(cleanup.file_moves)} files
- 🔧 **Auto Fixes**: {len(cleanup.auto_fixes)} fixes"""
    
    def _create_improvements_section(self, results: CheckupResults) -> str:
        """Create improvements section."""
        improvements = results.improvement_metrics
        
        return f"""## 📈 Improvements

| Metric | Improvement |
|--------|-------------|
| Issues Fixed | {improvements.get('issues_fixed', 0)} |
| Imports Cleaned | {improvements.get('imports_cleaned', 0)} |
| Files Organized | {improvements.get('files_organized', 0)} |
| Coverage Change | {improvements.get('coverage_improvement', 0):+.1f}% |"""
    
    def _create_detailed_analysis_section(self, analysis: AnalysisResults) -> str:
        """Create detailed analysis section."""
        return f"""## 🔍 Detailed Analysis

**Analysis completed in {self.format_duration(analysis.duration)}**

The analysis examined {analysis.metrics.total_files} files and identified {analysis.total_issues} issues across various categories. The issues range from minor style violations to more significant structural problems that could impact maintainability.

### Analysis Scope

- **Python Files**: {analysis.metrics.python_files}
- **Test Files**: {analysis.metrics.test_files}
- **Documentation Files**: {analysis.metrics.documentation_files}
- **Configuration Files**: {analysis.metrics.config_files}"""
    
    def _create_issues_by_severity_section(self, analysis: AnalysisResults) -> str:
        """Create issues by severity section."""
        all_issues = self.get_all_issues(analysis)
        grouped = self.utils.group_issues_by_severity(all_issues)
        
        content = ["## 🚨 Issues by Severity"]
        
        for severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.MEDIUM, IssueSeverity.LOW]:
            if severity in grouped:
                issues = grouped[severity]
                icon = self.utils.get_severity_icon(severity)
                
                content.append(f"\n### {icon} {severity.value.title()} Severity ({len(issues)} issues)")
                
                for issue in issues[:10]:  # Show first 10 issues
                    file_path = self.utils.format_file_path(issue.file_path)
                    line_info = f":{issue.line_number}" if issue.line_number else ""
                    content.append(f"- **{file_path}{line_info}**: {issue.message}")
                    if issue.suggestion:
                        content.append(f"  - *Suggestion: {issue.suggestion}*")
                
                if len(issues) > 10:
                    content.append(f"  - *... and {len(issues) - 10} more issues*")
        
        return '\n'.join(content)
    
    def _create_issues_by_file_section(self, analysis: AnalysisResults) -> str:
        """Create issues by file section."""
        all_issues = self.get_all_issues(analysis)
        grouped = self.utils.group_issues_by_file(all_issues)
        
        content = ["## 📁 Issues by File"]
        
        # Sort files by number of issues (descending)
        sorted_files = sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True)
        
        for file_path, issues in sorted_files[:20]:  # Show top 20 files
            content.append(f"\n### `{file_path}` ({len(issues)} issues)")
            
            for issue in issues:
                severity_icon = self.utils.get_severity_icon(issue.severity)
                line_info = f" (Line {issue.line_number})" if issue.line_number else ""
                content.append(f"- {severity_icon} **{issue.severity.value.title()}**{line_info}: {issue.message}")
        
        if len(sorted_files) > 20:
            content.append(f"\n*... and {len(sorted_files) - 20} more files with issues*")
        
        return '\n'.join(content)
    
    def _create_issues_by_type_section(self, analysis: AnalysisResults) -> str:
        """Create issues by type section."""
        all_issues = self.get_all_issues(analysis)
        grouped = self.utils.group_issues_by_type(all_issues)
        
        content = ["## 🏷️ Issues by Type"]
        
        for issue_type, issues in grouped.items():
            type_name = issue_type.value.replace('_', ' ').title()
            content.append(f"\n### {type_name} ({len(issues)} issues)")
            
            # Group by file for this issue type
            files_with_type = {}
            for issue in issues:
                file_path = str(issue.file_path)
                if file_path not in files_with_type:
                    files_with_type[file_path] = 0
                files_with_type[file_path] += 1
            
            # Show top files for this issue type
            sorted_files = sorted(files_with_type.items(), key=lambda x: x[1], reverse=True)
            for file_path, count in sorted_files[:10]:
                content.append(f"- `{file_path}`: {count} issues")
            
            if len(sorted_files) > 10:
                content.append(f"- *... and {len(sorted_files) - 10} more files*")
        
        return '\n'.join(content)
    
    def _create_detailed_cleanup_section(self, cleanup: CleanupResults) -> str:
        """Create detailed cleanup section."""
        return f"""## 🧹 Detailed Cleanup Results

The cleanup process completed in {self.format_duration(cleanup.duration)} with {cleanup.successful_changes} out of {cleanup.total_changes} operations successful.

### Backup Information

{'✅' if cleanup.backup_created else '❌'} **Backup Created**: {'Yes' if cleanup.backup_created else 'No'}
{f'📁 **Backup Location**: `{cleanup.backup_path}`' if cleanup.backup_path else ''}

### Operation Summary

| Operation | Count | Success Rate |
|-----------|-------|--------------|
| Code Formatting | {len(cleanup.formatting_changes)} | 100% |
| Import Cleanup | {len(cleanup.import_cleanups)} | 100% |
| File Moves | {len(cleanup.file_moves)} | {self._calculate_success_rate(cleanup.file_moves)}% |
| File Removals | {len(cleanup.file_removals)} | {self._calculate_success_rate(cleanup.file_removals)}% |
| Auto Fixes | {len(cleanup.auto_fixes)} | {self._calculate_success_rate(cleanup.auto_fixes)}% |"""
    
    def _create_cleanup_details_section(self, cleanup: CleanupResults) -> str:
        """Create cleanup details section."""
        content = ["## 🔧 Cleanup Details"]
        
        if cleanup.formatting_changes:
            content.append("\n### 🎨 Formatting Changes")
            for change in cleanup.formatting_changes[:10]:
                content.append(f"- `{change.file_path}`: {change.change_type} ({change.lines_changed} lines)")
            if len(cleanup.formatting_changes) > 10:
                content.append(f"- *... and {len(cleanup.formatting_changes) - 10} more files*")
        
        if cleanup.import_cleanups:
            content.append("\n### 📦 Import Cleanups")
            for cleanup_item in cleanup.import_cleanups[:10]:
                removed_count = len(cleanup_item.removed_imports)
                reorganized = "reorganized" if cleanup_item.reorganized_imports else "not reorganized"
                content.append(f"- `{cleanup_item.file_path}`: {removed_count} imports removed, {reorganized}")
            if len(cleanup.import_cleanups) > 10:
                content.append(f"- *... and {len(cleanup.import_cleanups) - 10} more files*")
        
        if cleanup.file_moves:
            content.append("\n### 📁 File Moves")
            for move in cleanup.file_moves:
                status = "✅" if move.success else "❌"
                content.append(f"- {status} `{move.source_path}` → `{move.destination_path}`")
                if move.reason:
                    content.append(f"  - *Reason: {move.reason}*")
        
        if cleanup.auto_fixes:
            content.append("\n### 🔧 Auto Fixes")
            for fix in cleanup.auto_fixes[:10]:
                status = "✅" if fix.success else "❌"
                content.append(f"- {status} `{fix.file_path}`: {fix.fix_description}")
            if len(cleanup.auto_fixes) > 10:
                content.append(f"- *... and {len(cleanup.auto_fixes) - 10} more fixes*")
        
        return '\n'.join(content)
    
    def _create_before_after_section(self, results: CheckupResults) -> str:
        """Create before/after comparison section."""
        before = results.before_metrics
        after = results.after_metrics
        
        return f"""## 📊 Before vs After Comparison

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Style Violations | {before.style_violations} | {after.style_violations} | {self._format_change(before.style_violations, after.style_violations)} |
| Unused Imports | {before.unused_imports} | {after.unused_imports} | {self._format_change(before.unused_imports, after.unused_imports)} |
| Code Smells | {before.code_smells} | {after.code_smells} | {self._format_change(before.code_smells, after.code_smells)} |
| Test Coverage | {self.utils.format_percentage(before.test_coverage_percentage)} | {self.utils.format_percentage(after.test_coverage_percentage)} | {self._format_percentage_change(before.test_coverage_percentage, after.test_coverage_percentage)} |"""
    
    def _create_recommendations_section(self, analysis: AnalysisResults) -> str:
        """Create recommendations section."""
        recommendations = []
        
        if analysis.metrics.syntax_errors > 0:
            recommendations.append("🔴 **Critical**: Fix syntax errors immediately to ensure code functionality")
        
        if analysis.metrics.test_coverage_percentage < 80:
            recommendations.append(f"🟡 **Important**: Improve test coverage from {analysis.metrics.test_coverage_percentage:.1f}% to at least 80%")
        
        if analysis.metrics.unused_imports > 5:
            recommendations.append("🟡 **Cleanup**: Remove unused imports to reduce code clutter")
        
        if analysis.metrics.style_violations > 10:
            recommendations.append("🟡 **Style**: Address style violations to improve code consistency")
        
        if analysis.metrics.duplicate_blocks > 0:
            recommendations.append("🟡 **Refactor**: Consider refactoring duplicate code blocks")
        
        if not recommendations:
            recommendations.append("🎉 **Excellent**: Your codebase is in great shape! Keep up the good work.")
        
        content = ["## 💡 Recommendations"]
        content.extend(recommendations)
        
        return '\n'.join(content)
    
    def _create_metadata_section(self, metadata: Dict[str, Any]) -> str:
        """Create metadata section."""
        return f"""## 📋 Report Metadata

- **Generator**: {metadata['generator']}
- **Generated At**: {metadata['generated_at']}
- **Target Directory**: `{metadata['target_directory']}`
- **Checkup Timestamp**: {metadata['checkup_timestamp']}
- **Total Issues**: {metadata['total_issues']}
- **Cleanup Performed**: {'Yes' if metadata['cleanup_performed'] else 'No'}
- **Success**: {'Yes' if metadata['success'] else 'No'}

---

*This report was automatically generated by the Migration Assistant Codebase Checkup system.*"""
    
    def _get_score_emoji(self, score: float) -> str:
        """Get emoji for quality score."""
        if score >= 90:
            return "🟢"
        elif score >= 70:
            return "🟡"
        elif score >= 50:
            return "🟠"
        else:
            return "🔴"
    
    def _calculate_success_rate(self, items: List) -> int:
        """Calculate success rate for a list of items with success attribute."""
        if not items:
            return 100
        successful = sum(1 for item in items if getattr(item, 'success', True))
        return int(successful / len(items) * 100)
    
    def _format_change(self, before: int, after: int) -> str:
        """Format numeric change with appropriate emoji."""
        change = after - before
        if change == 0:
            return "→ 0"
        elif change < 0:
            return f"✅ {change}"
        else:
            return f"❌ +{change}"
    
    def _format_percentage_change(self, before: float, after: float) -> str:
        """Format percentage change with appropriate emoji."""
        change = after - before
        if abs(change) < 0.1:
            return "→ 0.0%"
        elif change > 0:
            return f"✅ +{change:.1f}%"
        else:
            return f"❌ {change:.1f}%"
    
    def _create_comparison_overview_section(self, before: CheckupResults, after: CheckupResults, time_between) -> str:
        """Create comparison overview section."""
        before_score = self.utils.calculate_quality_score(before.analysis)
        after_score = self.utils.calculate_quality_score(after.analysis)
        score_change = after_score - before_score
        
        score_emoji = "📈" if score_change > 0 else "📉" if score_change < 0 else "➡️"
        status_emoji = "✅" if score_change >= 0 else "⚠️"
        
        return f"""## 📊 Comparison Overview

{status_emoji} **Overall Trend**: {'Improving' if score_change > 0 else 'Declining' if score_change < 0 else 'Stable'}
⏱️ **Time Between Checkups**: {self.format_duration(time_between)}
{score_emoji} **Quality Score Change**: {score_change:+.1f} points
📋 **Issues Change**: {after.analysis.total_issues - before.analysis.total_issues:+d}
📁 **Files Analyzed**: {after.analysis.metrics.total_files}"""
    
    def _create_quality_score_comparison_section(self, before: CheckupResults, after: CheckupResults) -> str:
        """Create quality score comparison section."""
        before_score = self.utils.calculate_quality_score(before.analysis)
        after_score = self.utils.calculate_quality_score(after.analysis)
        score_change = after_score - before_score
        
        before_emoji = self._get_score_emoji(before_score)
        after_emoji = self._get_score_emoji(after_score)
        
        return f"""## 🎯 Quality Score Comparison

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Quality Score | {before_emoji} {before_score}/100 | {after_emoji} {after_score}/100 | {self._format_score_change(score_change)} |

### Score Breakdown

The quality score is calculated based on various factors including code style, complexity, test coverage, and structural issues. {'A positive change indicates improvement in overall code quality.' if score_change > 0 else 'A negative change suggests areas that need attention.' if score_change < 0 else 'The score remained stable between checkups.'}"""
    
    def _create_metrics_comparison_section(self, before: CheckupResults, after: CheckupResults) -> str:
        """Create metrics comparison section."""
        before_metrics = before.analysis.metrics
        after_metrics = after.analysis.metrics
        
        return f"""## 📈 Detailed Metrics Comparison

### Code Quality Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Syntax Errors | {before_metrics.syntax_errors} | {after_metrics.syntax_errors} | {self._format_change(before_metrics.syntax_errors, after_metrics.syntax_errors)} |
| Style Violations | {before_metrics.style_violations} | {after_metrics.style_violations} | {self._format_change(before_metrics.style_violations, after_metrics.style_violations)} |
| Code Smells | {before_metrics.code_smells} | {after_metrics.code_smells} | {self._format_change(before_metrics.code_smells, after_metrics.code_smells)} |
| Complexity Issues | {before_metrics.complexity_issues} | {after_metrics.complexity_issues} | {self._format_change(before_metrics.complexity_issues, after_metrics.complexity_issues)} |

### Import and Structure Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Unused Imports | {before_metrics.unused_imports} | {after_metrics.unused_imports} | {self._format_change(before_metrics.unused_imports, after_metrics.unused_imports)} |
| Circular Imports | {before_metrics.circular_imports} | {after_metrics.circular_imports} | {self._format_change(before_metrics.circular_imports, after_metrics.circular_imports)} |
| Orphaned Modules | {before_metrics.orphaned_modules} | {after_metrics.orphaned_modules} | {self._format_change(before_metrics.orphaned_modules, after_metrics.orphaned_modules)} |
| Misplaced Files | {before_metrics.misplaced_files} | {after_metrics.misplaced_files} | {self._format_change(before_metrics.misplaced_files, after_metrics.misplaced_files)} |

### Testing and Duplication Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Test Coverage | {self.utils.format_percentage(before_metrics.test_coverage_percentage)} | {self.utils.format_percentage(after_metrics.test_coverage_percentage)} | {self._format_percentage_change(before_metrics.test_coverage_percentage, after_metrics.test_coverage_percentage)} |
| Untested Functions | {before_metrics.untested_functions} | {after_metrics.untested_functions} | {self._format_change(before_metrics.untested_functions, after_metrics.untested_functions)} |
| Duplicate Blocks | {before_metrics.duplicate_blocks} | {after_metrics.duplicate_blocks} | {self._format_change(before_metrics.duplicate_blocks, after_metrics.duplicate_blocks)} |
| Duplicate Lines | {before_metrics.duplicate_lines} | {after_metrics.duplicate_lines} | {self._format_change(before_metrics.duplicate_lines, after_metrics.duplicate_lines)} |"""
    
    def _create_issues_comparison_section(self, before: CheckupResults, after: CheckupResults) -> str:
        """Create issues comparison section."""
        before_severity = self.get_severity_counts(before.analysis)
        after_severity = self.get_severity_counts(after.analysis)
        before_types = self.get_issue_type_counts(before.analysis)
        after_types = self.get_issue_type_counts(after.analysis)
        
        content = ["## 🚨 Issues Comparison"]
        
        # Severity comparison
        content.append("### Issues by Severity")
        content.append("| Severity | Before | After | Change |")
        content.append("|----------|--------|-------|--------|")
        
        for severity in ['critical', 'high', 'medium', 'low']:
            before_count = before_severity.get(severity, 0)
            after_count = after_severity.get(severity, 0)
            change = after_count - before_count
            severity_icon = self.utils.get_severity_icon(getattr(IssueSeverity, severity.upper()))
            content.append(f"| {severity_icon} {severity.title()} | {before_count} | {after_count} | {self._format_change(before_count, after_count)} |")
        
        # Type comparison
        content.append("\n### Issues by Type")
        content.append("| Issue Type | Before | After | Change |")
        content.append("|------------|--------|-------|--------|")
        
        all_types = set(before_types.keys()) | set(after_types.keys())
        for issue_type in sorted(all_types):
            before_count = before_types.get(issue_type, 0)
            after_count = after_types.get(issue_type, 0)
            if before_count > 0 or after_count > 0:
                formatted_type = issue_type.replace('_', ' ').title()
                content.append(f"| {formatted_type} | {before_count} | {after_count} | {self._format_change(before_count, after_count)} |")
        
        return '\n'.join(content)
    
    def _create_trend_analysis_section(self, before: CheckupResults, after: CheckupResults) -> str:
        """Create trend analysis section."""
        before_score = self.utils.calculate_quality_score(before.analysis)
        after_score = self.utils.calculate_quality_score(after.analysis)
        
        # Analyze trends
        improvements = []
        concerns = []
        
        if after.analysis.metrics.style_violations < before.analysis.metrics.style_violations:
            improvements.append(f"Style violations reduced by {before.analysis.metrics.style_violations - after.analysis.metrics.style_violations}")
        elif after.analysis.metrics.style_violations > before.analysis.metrics.style_violations:
            concerns.append(f"Style violations increased by {after.analysis.metrics.style_violations - before.analysis.metrics.style_violations}")
        
        if after.analysis.metrics.unused_imports < before.analysis.metrics.unused_imports:
            improvements.append(f"Unused imports cleaned up: {before.analysis.metrics.unused_imports - after.analysis.metrics.unused_imports}")
        elif after.analysis.metrics.unused_imports > before.analysis.metrics.unused_imports:
            concerns.append(f"New unused imports detected: {after.analysis.metrics.unused_imports - before.analysis.metrics.unused_imports}")
        
        if after.analysis.metrics.test_coverage_percentage > before.analysis.metrics.test_coverage_percentage:
            improvements.append(f"Test coverage improved by {after.analysis.metrics.test_coverage_percentage - before.analysis.metrics.test_coverage_percentage:.1f}%")
        elif after.analysis.metrics.test_coverage_percentage < before.analysis.metrics.test_coverage_percentage:
            concerns.append(f"Test coverage decreased by {before.analysis.metrics.test_coverage_percentage - after.analysis.metrics.test_coverage_percentage:.1f}%")
        
        if after.analysis.metrics.code_smells < before.analysis.metrics.code_smells:
            improvements.append(f"Code smells reduced by {before.analysis.metrics.code_smells - after.analysis.metrics.code_smells}")
        elif after.analysis.metrics.code_smells > before.analysis.metrics.code_smells:
            concerns.append(f"New code smells detected: {after.analysis.metrics.code_smells - before.analysis.metrics.code_smells}")
        
        content = [f"""## 📊 Trend Analysis

**Overall Trend**: {'📈 Improving' if after_score > before_score else '📉 Declining' if after_score < before_score else '➡️ Stable'}
**Quality Score Change**: {after_score - before_score:+.1f} points"""]
        
        if improvements:
            content.append("\n### ✅ Improvements")
            for improvement in improvements:
                content.append(f"- {improvement}")
        
        if concerns:
            content.append("\n### ⚠️ Areas of Concern")
            for concern in concerns:
                content.append(f"- {concern}")
        
        if not improvements and not concerns:
            content.append("\n### ➡️ Stable Metrics")
            content.append("- No significant changes detected between checkups")
        
        return '\n'.join(content)
    
    def _create_detailed_changes_section(self, before: CheckupResults, after: CheckupResults) -> str:
        """Create detailed changes section."""
        content = ["## 🔍 Detailed Changes"]
        
        # Calculate key changes
        total_change = after.analysis.total_issues - before.analysis.total_issues
        style_change = after.analysis.metrics.style_violations - before.analysis.metrics.style_violations
        import_change = after.analysis.metrics.unused_imports - before.analysis.metrics.unused_imports
        coverage_change = after.analysis.metrics.test_coverage_percentage - before.analysis.metrics.test_coverage_percentage
        
        content.append("### Summary of Changes")
        content.append(f"- **Total Issues**: {total_change:+d}")
        content.append(f"- **Style Violations**: {style_change:+d}")
        content.append(f"- **Unused Imports**: {import_change:+d}")
        content.append(f"- **Test Coverage**: {coverage_change:+.1f}%")
        
        # File-level changes (simplified)
        content.append("\n### Key Observations")
        
        if total_change < 0:
            content.append(f"- ✅ Overall improvement with {abs(total_change)} fewer issues")
        elif total_change > 0:
            content.append(f"- ⚠️ {total_change} new issues detected")
        else:
            content.append("- ➡️ No change in total issue count")
        
        if style_change < 0:
            content.append(f"- 🎨 Code formatting improved ({abs(style_change)} fewer style violations)")
        elif style_change > 0:
            content.append(f"- 🎨 Code formatting needs attention ({style_change} new style violations)")
        
        if import_change < 0:
            content.append(f"- 📦 Import cleanup successful ({abs(import_change)} unused imports removed)")
        elif import_change > 0:
            content.append(f"- 📦 New unused imports detected ({import_change})")
        
        if coverage_change > 0.1:
            content.append(f"- 🧪 Test coverage improved by {coverage_change:.1f}%")
        elif coverage_change < -0.1:
            content.append(f"- 🧪 Test coverage decreased by {abs(coverage_change):.1f}%")
        
        return '\n'.join(content)
    
    def _create_recommendations_from_comparison(self, before: CheckupResults, after: CheckupResults) -> str:
        """Create recommendations based on comparison."""
        recommendations = []
        
        # Analyze changes and provide recommendations
        if after.analysis.total_issues > before.analysis.total_issues:
            recommendations.append("🔴 **Priority**: Address the increase in total issues to prevent technical debt accumulation")
        
        if after.analysis.metrics.style_violations > before.analysis.metrics.style_violations:
            recommendations.append("🟡 **Style**: Run code formatters (black, isort) to address style violations")
        
        if after.analysis.metrics.unused_imports > before.analysis.metrics.unused_imports:
            recommendations.append("🟡 **Cleanup**: Remove unused imports to reduce code clutter")
        
        if after.analysis.metrics.test_coverage_percentage < before.analysis.metrics.test_coverage_percentage:
            recommendations.append("🟡 **Testing**: Focus on improving test coverage to maintain code quality")
        
        if after.analysis.metrics.code_smells > before.analysis.metrics.code_smells:
            recommendations.append("🟡 **Refactor**: Address new code smells to improve maintainability")
        
        # Positive reinforcement
        if after.analysis.total_issues < before.analysis.total_issues:
            recommendations.append("🎉 **Great Work**: Keep up the excellent progress in reducing issues")
        
        if after.analysis.metrics.test_coverage_percentage > before.analysis.metrics.test_coverage_percentage:
            recommendations.append("🎉 **Testing**: Excellent improvement in test coverage")
        
        if not recommendations:
            recommendations.append("✅ **Stable**: Codebase quality is stable. Consider focusing on new features or performance optimizations")
        
        content = ["## 💡 Recommendations Based on Comparison"]
        content.extend(recommendations)
        
        return '\n'.join(content)
    
    def _create_comparison_metadata_section(self, before: CheckupResults, after: CheckupResults) -> str:
        """Create comparison metadata section."""
        time_between = after.analysis.timestamp - before.analysis.timestamp
        
        return f"""## 📋 Comparison Metadata

- **Before Checkup**: {before.analysis.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- **After Checkup**: {after.analysis.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- **Time Between**: {self.format_duration(time_between)}
- **Target Directory**: `{self.config.target_directory}`
- **Before Issues**: {before.analysis.total_issues}
- **After Issues**: {after.analysis.total_issues}
- **Net Change**: {after.analysis.total_issues - before.analysis.total_issues:+d}

---

*This comparison report was automatically generated by the Migration Assistant Codebase Checkup system.*"""
    
    def _format_score_change(self, change: float) -> str:
        """Format quality score change with appropriate emoji."""
        if abs(change) < 0.1:
            return "→ 0.0"
        elif change > 0:
            return f"✅ +{change:.1f}"
        else:
            return f"❌ {change:.1f}"