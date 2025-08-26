"""
HTML Report Generator

Generates interactive HTML reports with charts, graphs, and drill-down capabilities.
"""

from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

from migration_assistant.checkup.reporters.base import (
    ReportGenerator, ReportTemplate, ReportSection
)
from migration_assistant.checkup.models import (
    CheckupResults, AnalysisResults, Issue, IssueSeverity, IssueType
)


class HTMLReportGenerator(ReportGenerator):
    """Generator for interactive HTML reports."""
    
    @property
    def file_extension(self) -> str:
        """Return file extension."""
        return '.html'
    
    def _get_default_template(self) -> ReportTemplate:
        """Get HTML-specific template."""
        return ReportTemplate(
            header_template=self._get_html_header(),
            section_template=self._get_section_template(),
            footer_template=self._get_html_footer(),
            css_styles=self._get_css_styles(),
            javascript=self._get_javascript()
        )
    
    async def generate_summary_report(self, results: CheckupResults) -> str:
        """Generate HTML summary report."""
        sections = self.create_report_sections(results)
        metadata = self.get_report_metadata(results)
        
        # Create summary-specific sections
        summary_sections = [
            self._create_overview_section(results),
            self._create_metrics_dashboard(results),
            self._create_issues_summary(results.analysis)
        ]
        
        if results.cleanup:
            summary_sections.append(self._create_cleanup_summary(results.cleanup))
        
        html_content = self._build_html_document(
            title="Codebase Checkup Summary",
            sections=summary_sections,
            metadata=metadata,
            include_charts=True
        )
        
        return html_content
    
    async def generate_detailed_report(self, results: CheckupResults) -> str:
        """Generate HTML detailed report."""
        sections = self.create_report_sections(results)
        metadata = self.get_report_metadata(results)
        
        # Create detailed sections
        detailed_sections = [
            self._create_overview_section(results),
            self._create_issues_summary(results.analysis),
            self._create_detailed_analysis(results.analysis),
            self._create_issues_by_file(results.analysis),
            self._create_issues_by_type(results.analysis)
        ]
        
        if results.cleanup:
            detailed_sections.extend([
                self._create_detailed_cleanup(results.cleanup),
                self._create_before_after_comparison(results)
            ])
        
        html_content = self._build_html_document(
            title="Detailed Codebase Checkup Report",
            sections=detailed_sections,
            metadata=metadata,
            include_charts=True,
            include_drill_down=True
        )
        
        return html_content
    
    async def generate_comparison_report(self, before: CheckupResults, after: CheckupResults) -> str:
        """Generate HTML comparison report."""
        metadata = {
            "generator": self.name,
            "generated_at": datetime.now().isoformat(),
            "before_timestamp": before.analysis.timestamp.isoformat(),
            "after_timestamp": after.analysis.timestamp.isoformat(),
            "target_directory": str(self.config.target_directory)
        }
        
        # Create comparison sections
        comparison_sections = [
            self._create_comparison_overview(before, after),
            self._create_metrics_comparison(before, after),
            self._create_issues_comparison(before, after),
            self._create_quality_trend_analysis(before, after),
            self._create_improvement_summary(before, after)
        ]
        
        html_content = self._build_html_document(
            title="Codebase Checkup Comparison Report",
            sections=comparison_sections,
            metadata=metadata,
            include_charts=True,
            include_drill_down=True
        )
        
        return html_content
    
    def _build_html_document(
        self, 
        title: str, 
        sections: List[ReportSection],
        metadata: Dict[str, Any],
        include_charts: bool = False,
        include_drill_down: bool = False
    ) -> str:
        """Build complete HTML document."""
        html_parts = []
        
        # HTML header
        html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{self.template.css_styles}</style>
    {self._get_chart_libraries() if include_charts else ''}
</head>
<body>
    <div class="container">
        <header class="report-header">
            <h1>{title}</h1>
            <div class="metadata">
                <span class="timestamp">Generated: {metadata.get('generated_at', 'Unknown')}</span>
                <span class="target">Target: {metadata.get('target_directory', 'Unknown')}</span>
            </div>
        </header>
        <main class="report-content">""")
        
        # Sections
        for section in sections:
            html_parts.append(self._render_section(section, include_drill_down))
        
        # HTML footer
        html_parts.append(f"""
        </main>
        <footer class="report-footer">
            <p>Generated by {metadata.get('generator', 'Unknown')} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </footer>
    </div>
    <script>{self.template.javascript}</script>
    {self._get_interactive_scripts() if include_drill_down else ''}
</body>
</html>""")
        
        return '\n'.join(html_parts)
    
    def _render_section(self, section: ReportSection, include_drill_down: bool = False) -> str:
        """Render a report section as HTML."""
        section_id = section.title.lower().replace(' ', '-')
        
        html = f"""
        <section class="report-section" id="{section_id}">
            <h2 class="section-title">{section.title}</h2>
            <div class="section-content">
                {self._format_content_as_html(section.content)}
            </div>"""
        
        # Add subsections
        if section.subsections:
            html += '<div class="subsections">'
            for subsection in section.subsections:
                html += self._render_subsection(subsection, include_drill_down)
            html += '</div>'
        
        html += '</section>'
        return html
    
    def _render_subsection(self, subsection: ReportSection, include_drill_down: bool = False) -> str:
        """Render a subsection as HTML."""
        subsection_id = subsection.title.lower().replace(' ', '-')
        
        html = f"""
        <div class="subsection" id="{subsection_id}">
            <h3 class="subsection-title">{subsection.title}</h3>
            <div class="subsection-content">
                {self._format_content_as_html(subsection.content)}
            </div>
        </div>"""
        
        return html
    
    def _format_content_as_html(self, content: str) -> str:
        """Format content as HTML."""
        # Simple text to HTML conversion
        lines = content.split('\n')
        html_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Convert to paragraph
            html_lines.append(f'<p>{line}</p>')
        
        return '\n'.join(html_lines)
    
    def _create_overview_section(self, results: CheckupResults) -> ReportSection:
        """Create overview section with key metrics."""
        quality_score = self.utils.calculate_quality_score(results.analysis)
        
        content = f"""
        <div class="overview-grid">
            <div class="metric-card quality-score">
                <h3>Quality Score</h3>
                <div class="score">{quality_score}/100</div>
                <div class="score-bar">
                    <div class="score-fill" style="width: {quality_score}%"></div>
                </div>
            </div>
            <div class="metric-card total-issues">
                <h3>Total Issues</h3>
                <div class="count">{results.analysis.total_issues}</div>
            </div>
            <div class="metric-card files-analyzed">
                <h3>Files Analyzed</h3>
                <div class="count">{results.analysis.metrics.total_files}</div>
            </div>
            <div class="metric-card duration">
                <h3>Analysis Duration</h3>
                <div class="time">{self.format_duration(results.duration)}</div>
            </div>
        </div>
        """
        
        return ReportSection(
            title="Overview",
            content=content,
            metadata={"quality_score": quality_score}
        )
    
    def _create_metrics_dashboard(self, results: CheckupResults) -> ReportSection:
        """Create metrics dashboard with charts."""
        severity_counts = self.get_severity_counts(results.analysis)
        type_counts = self.get_issue_type_counts(results.analysis)
        
        content = f"""
        <div class="dashboard-grid">
            <div class="chart-container">
                <h4>Issues by Severity</h4>
                <canvas id="severity-chart" width="300" height="200"></canvas>
            </div>
            <div class="chart-container">
                <h4>Issues by Type</h4>
                <canvas id="type-chart" width="300" height="200"></canvas>
            </div>
            <div class="stats-table">
                <h4>Codebase Statistics</h4>
                <table>
                    <tr><td>Python Files</td><td>{results.analysis.metrics.python_files}</td></tr>
                    <tr><td>Test Files</td><td>{results.analysis.metrics.test_files}</td></tr>
                    <tr><td>Total Lines</td><td>{self.utils.format_number(results.analysis.metrics.total_lines)}</td></tr>
                    <tr><td>Test Coverage</td><td>{self.utils.format_percentage(results.analysis.metrics.test_coverage_percentage)}</td></tr>
                </table>
            </div>
        </div>
        
        <script>
            // Chart data
            window.severityData = {severity_counts};
            window.typeData = {type_counts};
        </script>
        """
        
        return ReportSection(
            title="Metrics Dashboard",
            content=content,
            metadata={"severity_counts": severity_counts, "type_counts": type_counts}
        )
    
    def _create_issues_summary(self, analysis: AnalysisResults) -> ReportSection:
        """Create issues summary section."""
        all_issues = self.get_all_issues(analysis)
        grouped_by_severity = self.utils.group_issues_by_severity(all_issues)
        
        content = '<div class="issues-summary">'
        
        for severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.MEDIUM, IssueSeverity.LOW]:
            if severity in grouped_by_severity:
                issues = grouped_by_severity[severity]
                color = self.utils.get_severity_color(severity)
                icon = self.utils.get_severity_icon(severity)
                
                content += f"""
                <div class="severity-group" data-severity="{severity.value}">
                    <h4 style="color: {color}">
                        {icon} {severity.value.title()} Severity ({len(issues)} issues)
                    </h4>
                    <div class="issue-list">
                """
                
                for issue in issues[:5]:  # Show first 5 issues
                    content += f"""
                    <div class="issue-item">
                        <span class="file-path">{self.utils.format_file_path(issue.file_path)}</span>
                        <span class="issue-message">{self.utils.truncate_text(issue.message, 80)}</span>
                    </div>
                    """
                
                if len(issues) > 5:
                    content += f'<div class="more-issues">... and {len(issues) - 5} more</div>'
                
                content += '</div></div>'
        
        content += '</div>'
        
        return ReportSection(
            title="Issues Summary",
            content=content,
            metadata={"total_issues": len(all_issues)}
        )
    
    def _create_cleanup_summary(self, cleanup) -> ReportSection:
        """Create cleanup summary section."""
        content = f"""
        <div class="cleanup-summary">
            <div class="cleanup-stats">
                <div class="stat">
                    <h4>Total Changes</h4>
                    <span class="number">{cleanup.total_changes}</span>
                </div>
                <div class="stat">
                    <h4>Successful</h4>
                    <span class="number success">{cleanup.successful_changes}</span>
                </div>
                <div class="stat">
                    <h4>Duration</h4>
                    <span class="time">{self.format_duration(cleanup.duration)}</span>
                </div>
            </div>
            
            <div class="cleanup-details">
                <h4>Changes Made</h4>
                <ul>
        """
        
        if cleanup.formatting_changes:
            content += f'<li>Formatting: {len(cleanup.formatting_changes)} files</li>'
        if cleanup.import_cleanups:
            content += f'<li>Import cleanup: {len(cleanup.import_cleanups)} files</li>'
        if cleanup.file_moves:
            content += f'<li>File moves: {len(cleanup.file_moves)} files</li>'
        if cleanup.auto_fixes:
            content += f'<li>Auto fixes: {len(cleanup.auto_fixes)} fixes</li>'
        
        content += """
                </ul>
            </div>
        </div>
        """
        
        return ReportSection(
            title="Cleanup Summary",
            content=content,
            metadata={"total_changes": cleanup.total_changes}
        )
    
    def _create_detailed_analysis(self, analysis: AnalysisResults) -> ReportSection:
        """Create detailed analysis section."""
        # This will contain detailed breakdowns
        content = f"""
        <div class="detailed-analysis">
            <p>Detailed analysis of {analysis.total_issues} issues found across {analysis.metrics.total_files} files.</p>
        </div>
        """
        
        return ReportSection(
            title="Detailed Analysis",
            content=content
        )
    
    def _create_issues_by_file(self, analysis: AnalysisResults) -> ReportSection:
        """Create issues grouped by file section."""
        all_issues = self.get_all_issues(analysis)
        grouped_by_file = self.utils.group_issues_by_file(all_issues)
        
        content = '<div class="issues-by-file">'
        
        for file_path, issues in sorted(grouped_by_file.items()):
            content += f"""
            <div class="file-group" data-file="{file_path}">
                <h4 class="file-header">
                    <span class="file-name">{file_path}</span>
                    <span class="issue-count">({len(issues)} issues)</span>
                </h4>
                <div class="file-issues">
            """
            
            for issue in issues:
                severity_color = self.utils.get_severity_color(issue.severity)
                content += f"""
                <div class="issue-detail" data-severity="{issue.severity.value}">
                    <div class="issue-header">
                        <span class="line-number">Line {issue.line_number or 'N/A'}</span>
                        <span class="severity" style="color: {severity_color}">{issue.severity.value}</span>
                        <span class="issue-type">{issue.issue_type.value}</span>
                    </div>
                    <div class="issue-message">{issue.message}</div>
                    {f'<div class="issue-suggestion">{issue.suggestion}</div>' if issue.suggestion else ''}
                </div>
                """
            
            content += '</div></div>'
        
        content += '</div>'
        
        return ReportSection(
            title="Issues by File",
            content=content,
            metadata={"files_with_issues": len(grouped_by_file)}
        )
    
    def _create_issues_by_type(self, analysis: AnalysisResults) -> ReportSection:
        """Create issues grouped by type section."""
        all_issues = self.get_all_issues(analysis)
        grouped_by_type = self.utils.group_issues_by_type(all_issues)
        
        content = '<div class="issues-by-type">'
        
        for issue_type, issues in grouped_by_type.items():
            content += f"""
            <div class="type-group" data-type="{issue_type.value}">
                <h4 class="type-header">{issue_type.value.replace('_', ' ').title()} ({len(issues)} issues)</h4>
                <div class="type-issues">
            """
            
            for issue in issues[:10]:  # Show first 10 issues
                content += f"""
                <div class="issue-summary">
                    <span class="file-path">{self.utils.format_file_path(issue.file_path)}</span>
                    <span class="line-number">:{issue.line_number or 'N/A'}</span>
                    <span class="message">{self.utils.truncate_text(issue.message, 60)}</span>
                </div>
                """
            
            if len(issues) > 10:
                content += f'<div class="more-issues">... and {len(issues) - 10} more</div>'
            
            content += '</div></div>'
        
        content += '</div>'
        
        return ReportSection(
            title="Issues by Type",
            content=content,
            metadata={"issue_types": len(grouped_by_type)}
        )
    
    def _create_detailed_cleanup(self, cleanup) -> ReportSection:
        """Create detailed cleanup section."""
        content = f"""
        <div class="detailed-cleanup">
            <p>Detailed breakdown of {cleanup.total_changes} cleanup operations.</p>
        </div>
        """
        
        return ReportSection(
            title="Detailed Cleanup",
            content=content
        )
    
    def _create_before_after_comparison(self, results: CheckupResults) -> ReportSection:
        """Create before/after comparison section."""
        if not results.after_metrics:
            return ReportSection(
                title="Before/After Comparison",
                content="<p>No after metrics available for comparison.</p>"
            )
        
        improvements = results.improvement_metrics
        
        content = f"""
        <div class="before-after-comparison">
            <div class="comparison-grid">
                <div class="metric-comparison">
                    <h4>Issues Fixed</h4>
                    <span class="improvement">{improvements.get('issues_fixed', 0)}</span>
                </div>
                <div class="metric-comparison">
                    <h4>Imports Cleaned</h4>
                    <span class="improvement">{improvements.get('imports_cleaned', 0)}</span>
                </div>
                <div class="metric-comparison">
                    <h4>Files Organized</h4>
                    <span class="improvement">{improvements.get('files_organized', 0)}</span>
                </div>
            </div>
        </div>
        """
        
        return ReportSection(
            title="Before/After Comparison",
            content=content,
            metadata=improvements
        )
    
    def _create_comparison_overview(self, before: CheckupResults, after: CheckupResults) -> ReportSection:
        """Create comparison overview section."""
        before_score = self.utils.calculate_quality_score(before.analysis)
        after_score = self.utils.calculate_quality_score(after.analysis)
        score_change = after_score - before_score
        
        time_between = after.analysis.timestamp - before.analysis.timestamp
        
        content = f"""
        <div class="comparison-overview">
            <div class="comparison-header">
                <h3>Quality Score Comparison</h3>
                <div class="score-comparison">
                    <div class="score-before">
                        <span class="label">Before</span>
                        <span class="score">{before_score}/100</span>
                    </div>
                    <div class="score-arrow">
                        {'📈' if score_change > 0 else '📉' if score_change < 0 else '➡️'}
                    </div>
                    <div class="score-after">
                        <span class="label">After</span>
                        <span class="score">{after_score}/100</span>
                    </div>
                    <div class="score-change">
                        <span class="change {'positive' if score_change > 0 else 'negative' if score_change < 0 else 'neutral'}">
                            {'+' if score_change > 0 else ''}{score_change:.1f}
                        </span>
                    </div>
                </div>
            </div>
            
            <div class="comparison-stats">
                <div class="stat">
                    <h4>Time Between Checkups</h4>
                    <span class="value">{self.format_duration(time_between)}</span>
                </div>
                <div class="stat">
                    <h4>Issues Change</h4>
                    <span class="value {'positive' if after.analysis.total_issues < before.analysis.total_issues else 'negative' if after.analysis.total_issues > before.analysis.total_issues else 'neutral'}">
                        {after.analysis.total_issues - before.analysis.total_issues:+d}
                    </span>
                </div>
                <div class="stat">
                    <h4>Files Analyzed</h4>
                    <span class="value">{after.analysis.metrics.total_files}</span>
                </div>
            </div>
        </div>
        """
        
        return ReportSection(
            title="Comparison Overview",
            content=content,
            metadata={
                "before_score": before_score,
                "after_score": after_score,
                "score_change": score_change,
                "time_between": str(time_between)
            }
        )
    
    def _create_metrics_comparison(self, before: CheckupResults, after: CheckupResults) -> ReportSection:
        """Create metrics comparison section."""
        before_metrics = before.analysis.metrics
        after_metrics = after.analysis.metrics
        
        content = f"""
        <div class="metrics-comparison">
            <div class="comparison-table">
                <table>
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Before</th>
                            <th>After</th>
                            <th>Change</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Style Violations</td>
                            <td>{before_metrics.style_violations}</td>
                            <td>{after_metrics.style_violations}</td>
                            <td class="{'positive' if after_metrics.style_violations < before_metrics.style_violations else 'negative' if after_metrics.style_violations > before_metrics.style_violations else 'neutral'}">
                                {after_metrics.style_violations - before_metrics.style_violations:+d}
                            </td>
                        </tr>
                        <tr>
                            <td>Unused Imports</td>
                            <td>{before_metrics.unused_imports}</td>
                            <td>{after_metrics.unused_imports}</td>
                            <td class="{'positive' if after_metrics.unused_imports < before_metrics.unused_imports else 'negative' if after_metrics.unused_imports > before_metrics.unused_imports else 'neutral'}">
                                {after_metrics.unused_imports - before_metrics.unused_imports:+d}
                            </td>
                        </tr>
                        <tr>
                            <td>Code Smells</td>
                            <td>{before_metrics.code_smells}</td>
                            <td>{after_metrics.code_smells}</td>
                            <td class="{'positive' if after_metrics.code_smells < before_metrics.code_smells else 'negative' if after_metrics.code_smells > before_metrics.code_smells else 'neutral'}">
                                {after_metrics.code_smells - before_metrics.code_smells:+d}
                            </td>
                        </tr>
                        <tr>
                            <td>Test Coverage</td>
                            <td>{self.utils.format_percentage(before_metrics.test_coverage_percentage)}</td>
                            <td>{self.utils.format_percentage(after_metrics.test_coverage_percentage)}</td>
                            <td class="{'positive' if after_metrics.test_coverage_percentage > before_metrics.test_coverage_percentage else 'negative' if after_metrics.test_coverage_percentage < before_metrics.test_coverage_percentage else 'neutral'}">
                                {after_metrics.test_coverage_percentage - before_metrics.test_coverage_percentage:+.1f}%
                            </td>
                        </tr>
                        <tr>
                            <td>Duplicate Blocks</td>
                            <td>{before_metrics.duplicate_blocks}</td>
                            <td>{after_metrics.duplicate_blocks}</td>
                            <td class="{'positive' if after_metrics.duplicate_blocks < before_metrics.duplicate_blocks else 'negative' if after_metrics.duplicate_blocks > before_metrics.duplicate_blocks else 'neutral'}">
                                {after_metrics.duplicate_blocks - before_metrics.duplicate_blocks:+d}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="metrics-charts">
                <canvas id="metrics-comparison-chart" width="400" height="300"></canvas>
            </div>
        </div>
        
        <script>
            window.metricsComparisonData = {{
                before: {{
                    style_violations: {before_metrics.style_violations},
                    unused_imports: {before_metrics.unused_imports},
                    code_smells: {before_metrics.code_smells},
                    test_coverage: {before_metrics.test_coverage_percentage}
                }},
                after: {{
                    style_violations: {after_metrics.style_violations},
                    unused_imports: {after_metrics.unused_imports},
                    code_smells: {after_metrics.code_smells},
                    test_coverage: {after_metrics.test_coverage_percentage}
                }}
            }};
        </script>
        """
        
        return ReportSection(
            title="Metrics Comparison",
            content=content,
            metadata={
                "before_metrics": before_metrics,
                "after_metrics": after_metrics
            }
        )
    
    def _create_issues_comparison(self, before: CheckupResults, after: CheckupResults) -> ReportSection:
        """Create issues comparison section."""
        before_severity = self.get_severity_counts(before.analysis)
        after_severity = self.get_severity_counts(after.analysis)
        
        content = f"""
        <div class="issues-comparison">
            <div class="severity-comparison">
                <h4>Issues by Severity</h4>
                <div class="severity-bars">
        """
        
        for severity in ['critical', 'high', 'medium', 'low']:
            before_count = before_severity.get(severity, 0)
            after_count = after_severity.get(severity, 0)
            change = after_count - before_count
            
            content += f"""
                    <div class="severity-bar">
                        <span class="severity-label">{severity.title()}</span>
                        <div class="bar-container">
                            <div class="bar before" style="width: {min(before_count * 10, 100)}px">{before_count}</div>
                            <div class="bar after" style="width: {min(after_count * 10, 100)}px">{after_count}</div>
                        </div>
                        <span class="change {'positive' if change < 0 else 'negative' if change > 0 else 'neutral'}">
                            {change:+d}
                        </span>
                    </div>
            """
        
        content += """
                </div>
            </div>
            
            <div class="issues-trend">
                <canvas id="issues-trend-chart" width="400" height="200"></canvas>
            </div>
        </div>
        """
        
        return ReportSection(
            title="Issues Comparison",
            content=content,
            metadata={
                "before_severity": before_severity,
                "after_severity": after_severity
            }
        )
    
    def _create_quality_trend_analysis(self, before: CheckupResults, after: CheckupResults) -> ReportSection:
        """Create quality trend analysis section."""
        before_score = self.utils.calculate_quality_score(before.analysis)
        after_score = self.utils.calculate_quality_score(after.analysis)
        
        # Calculate trend indicators
        trend_indicators = []
        
        if after.analysis.metrics.style_violations < before.analysis.metrics.style_violations:
            trend_indicators.append("✅ Style violations decreased")
        elif after.analysis.metrics.style_violations > before.analysis.metrics.style_violations:
            trend_indicators.append("❌ Style violations increased")
        
        if after.analysis.metrics.unused_imports < before.analysis.metrics.unused_imports:
            trend_indicators.append("✅ Unused imports cleaned up")
        elif after.analysis.metrics.unused_imports > before.analysis.metrics.unused_imports:
            trend_indicators.append("❌ More unused imports detected")
        
        if after.analysis.metrics.test_coverage_percentage > before.analysis.metrics.test_coverage_percentage:
            trend_indicators.append("✅ Test coverage improved")
        elif after.analysis.metrics.test_coverage_percentage < before.analysis.metrics.test_coverage_percentage:
            trend_indicators.append("❌ Test coverage decreased")
        
        if after.analysis.metrics.code_smells < before.analysis.metrics.code_smells:
            trend_indicators.append("✅ Code smells reduced")
        elif after.analysis.metrics.code_smells > before.analysis.metrics.code_smells:
            trend_indicators.append("❌ More code smells detected")
        
        content = f"""
        <div class="quality-trend">
            <div class="trend-summary">
                <h4>Quality Trend Analysis</h4>
                <div class="trend-score">
                    <span class="score-label">Overall Trend:</span>
                    <span class="trend-direction {'positive' if after_score > before_score else 'negative' if after_score < before_score else 'neutral'}">
                        {'Improving' if after_score > before_score else 'Declining' if after_score < before_score else 'Stable'}
                    </span>
                </div>
            </div>
            
            <div class="trend-indicators">
                <h4>Key Changes</h4>
                <ul>
        """
        
        for indicator in trend_indicators:
            content += f"<li>{indicator}</li>"
        
        if not trend_indicators:
            content += "<li>No significant changes detected</li>"
        
        content += """
                </ul>
            </div>
            
            <div class="trend-chart">
                <canvas id="quality-trend-chart" width="400" height="200"></canvas>
            </div>
        </div>
        """
        
        return ReportSection(
            title="Quality Trend Analysis",
            content=content,
            metadata={
                "before_score": before_score,
                "after_score": after_score,
                "trend_indicators": trend_indicators
            }
        )
    
    def _create_improvement_summary(self, before: CheckupResults, after: CheckupResults) -> ReportSection:
        """Create improvement summary section."""
        improvements = {
            "issues_fixed": before.analysis.total_issues - after.analysis.total_issues,
            "style_improvements": before.analysis.metrics.style_violations - after.analysis.metrics.style_violations,
            "import_cleanups": before.analysis.metrics.unused_imports - after.analysis.metrics.unused_imports,
            "coverage_change": after.analysis.metrics.test_coverage_percentage - before.analysis.metrics.test_coverage_percentage,
            "code_smell_reduction": before.analysis.metrics.code_smells - after.analysis.metrics.code_smells
        }
        
        content = f"""
        <div class="improvement-summary">
            <div class="improvements-grid">
                <div class="improvement-card {'positive' if improvements['issues_fixed'] > 0 else 'negative' if improvements['issues_fixed'] < 0 else 'neutral'}">
                    <h4>Issues Fixed</h4>
                    <span class="number">{improvements['issues_fixed']:+d}</span>
                </div>
                <div class="improvement-card {'positive' if improvements['style_improvements'] > 0 else 'negative' if improvements['style_improvements'] < 0 else 'neutral'}">
                    <h4>Style Improvements</h4>
                    <span class="number">{improvements['style_improvements']:+d}</span>
                </div>
                <div class="improvement-card {'positive' if improvements['import_cleanups'] > 0 else 'negative' if improvements['import_cleanups'] < 0 else 'neutral'}">
                    <h4>Import Cleanups</h4>
                    <span class="number">{improvements['import_cleanups']:+d}</span>
                </div>
                <div class="improvement-card {'positive' if improvements['coverage_change'] > 0 else 'negative' if improvements['coverage_change'] < 0 else 'neutral'}">
                    <h4>Coverage Change</h4>
                    <span class="number">{improvements['coverage_change']:+.1f}%</span>
                </div>
            </div>
            
            <div class="improvement-details">
                <h4>Summary</h4>
                <p>
        """
        
        if improvements['issues_fixed'] > 0:
            content += f"Fixed {improvements['issues_fixed']} issues overall. "
        elif improvements['issues_fixed'] < 0:
            content += f"Detected {abs(improvements['issues_fixed'])} new issues. "
        else:
            content += "No change in total issue count. "
        
        if improvements['style_improvements'] > 0:
            content += f"Improved {improvements['style_improvements']} style violations. "
        
        if improvements['import_cleanups'] > 0:
            content += f"Cleaned up {improvements['import_cleanups']} unused imports. "
        
        if improvements['coverage_change'] > 0:
            content += f"Increased test coverage by {improvements['coverage_change']:.1f}%. "
        
        content += """
                </p>
            </div>
        </div>
        """
        
        return ReportSection(
            title="Improvement Summary",
            content=content,
            metadata=improvements
        )
    
    def _get_html_header(self) -> str:
        """Get HTML header template."""
        return """
        <header class="report-header">
            <h1>{title}</h1>
            <div class="metadata">
                <span class="timestamp">{timestamp}</span>
                <span class="target">{target}</span>
            </div>
        </header>
        """
    
    def _get_section_template(self) -> str:
        """Get section template."""
        return """
        <section class="report-section">
            <h2>{title}</h2>
            <div class="section-content">{content}</div>
        </section>
        """
    
    def _get_html_footer(self) -> str:
        """Get HTML footer template."""
        return """
        <footer class="report-footer">
            <p>Generated by {generator} on {timestamp}</p>
        </footer>
        """
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for HTML reports."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        
        .report-header {
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        
        .report-header h1 {
            color: #007bff;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .metadata {
            color: #666;
            font-size: 0.9em;
        }
        
        .metadata span {
            margin-right: 20px;
        }
        
        .report-section {
            margin-bottom: 40px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #007bff;
        }
        
        .section-title {
            color: #007bff;
            font-size: 1.8em;
            margin-bottom: 15px;
        }
        
        .subsection {
            margin: 20px 0;
            padding: 15px;
            background: white;
            border-radius: 6px;
            border-left: 3px solid #28a745;
        }
        
        .subsection-title {
            color: #28a745;
            font-size: 1.3em;
            margin-bottom: 10px;
        }
        
        .overview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .metric-card h3 {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .metric-card .score {
            font-size: 2.5em;
            font-weight: bold;
            color: #007bff;
        }
        
        .metric-card .count {
            font-size: 2em;
            font-weight: bold;
            color: #28a745;
        }
        
        .metric-card .time {
            font-size: 1.5em;
            color: #ffc107;
        }
        
        .score-bar {
            width: 100%;
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            margin-top: 10px;
            overflow: hidden;
        }
        
        .score-fill {
            height: 100%;
            background: linear-gradient(90deg, #dc3545 0%, #ffc107 50%, #28a745 100%);
            transition: width 0.3s ease;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }
        
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        
        .stats-table table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .stats-table td {
            padding: 8px;
            border-bottom: 1px solid #dee2e6;
        }
        
        .stats-table td:first-child {
            font-weight: bold;
            color: #666;
        }
        
        .issues-summary {
            margin: 20px 0;
        }
        
        .severity-group {
            margin: 20px 0;
            padding: 15px;
            background: white;
            border-radius: 6px;
        }
        
        .issue-list {
            margin-top: 10px;
        }
        
        .issue-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        
        .file-path {
            font-family: monospace;
            color: #007bff;
            font-weight: bold;
        }
        
        .issue-message {
            color: #666;
            flex: 1;
            margin-left: 15px;
        }
        
        .cleanup-summary {
            background: white;
            padding: 20px;
            border-radius: 8px;
        }
        
        .cleanup-stats {
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat h4 {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        
        .stat .number {
            font-size: 1.8em;
            font-weight: bold;
            color: #007bff;
        }
        
        .stat .number.success {
            color: #28a745;
        }
        
        .file-group {
            margin: 20px 0;
            background: white;
            border-radius: 6px;
            overflow: hidden;
        }
        
        .file-header {
            background: #007bff;
            color: white;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .file-issues {
            padding: 15px;
        }
        
        .issue-detail {
            margin: 10px 0;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 3px solid #dee2e6;
        }
        
        .issue-header {
            display: flex;
            gap: 15px;
            margin-bottom: 5px;
            font-size: 0.9em;
        }
        
        .line-number {
            font-family: monospace;
            background: #e9ecef;
            padding: 2px 6px;
            border-radius: 3px;
        }
        
        .severity {
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .issue-type {
            color: #666;
            font-style: italic;
        }
        
        .issue-message {
            font-weight: bold;
            margin: 5px 0;
        }
        
        .issue-suggestion {
            color: #28a745;
            font-style: italic;
            font-size: 0.9em;
        }
        
        .type-group {
            margin: 20px 0;
            background: white;
            border-radius: 6px;
            padding: 15px;
        }
        
        .type-header {
            color: #007bff;
            border-bottom: 1px solid #dee2e6;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        
        .issue-summary {
            display: flex;
            gap: 10px;
            padding: 5px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 0.9em;
        }
        
        .more-issues {
            color: #666;
            font-style: italic;
            text-align: center;
            padding: 10px;
        }
        
        .comparison-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
        }
        
        .metric-comparison {
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 6px;
        }
        
        .improvement {
            font-size: 1.5em;
            font-weight: bold;
            color: #28a745;
        }
        
        .report-footer {
            text-align: center;
            padding: 20px;
            border-top: 1px solid #dee2e6;
            color: #666;
            font-size: 0.9em;
        }
        
        @media (max-width: 768px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
            
            .overview-grid {
                grid-template-columns: 1fr 1fr;
            }
            
            .comparison-grid {
                grid-template-columns: 1fr;
            }
        }
        """
    
    def _get_javascript(self) -> str:
        """Get JavaScript for interactive features."""
        return """
        // Initialize charts when page loads
        document.addEventListener('DOMContentLoaded', function() {
            if (typeof Chart !== 'undefined') {
                initializeCharts();
            }
            initializeInteractivity();
        });
        
        function initializeInteractivity() {
            // Add click handlers for collapsible sections
            document.querySelectorAll('.file-header').forEach(header => {
                header.style.cursor = 'pointer';
                header.addEventListener('click', function() {
                    const issues = this.nextElementSibling;
                    if (issues.style.display === 'none') {
                        issues.style.display = 'block';
                        this.classList.remove('collapsed');
                    } else {
                        issues.style.display = 'none';
                        this.classList.add('collapsed');
                    }
                });
            });
            
            // Add severity filtering
            const severityFilters = document.querySelectorAll('[data-severity]');
            if (severityFilters.length > 0) {
                addSeverityFiltering();
            }
        }
        
        function addSeverityFiltering() {
            // Create filter controls
            const filterContainer = document.createElement('div');
            filterContainer.className = 'filter-controls';
            filterContainer.innerHTML = `
                <h4>Filter by Severity:</h4>
                <label><input type="checkbox" value="critical" checked> Critical</label>
                <label><input type="checkbox" value="high" checked> High</label>
                <label><input type="checkbox" value="medium" checked> Medium</label>
                <label><input type="checkbox" value="low" checked> Low</label>
            `;
            
            const firstSection = document.querySelector('.report-section');
            if (firstSection) {
                firstSection.insertBefore(filterContainer, firstSection.firstChild);
            }
            
            // Add filter functionality
            filterContainer.addEventListener('change', function(e) {
                if (e.target.type === 'checkbox') {
                    const severity = e.target.value;
                    const elements = document.querySelectorAll(`[data-severity="${severity}"]`);
                    elements.forEach(el => {
                        el.style.display = e.target.checked ? 'block' : 'none';
                    });
                }
            });
        }
        """
    
    def _get_chart_libraries(self) -> str:
        """Get chart library includes."""
        return """
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        """
    
    def _get_interactive_scripts(self) -> str:
        """Get interactive scripts for drill-down functionality."""
        return """
        <script>
        function initializeCharts() {
            // Severity chart
            const severityCtx = document.getElementById('severity-chart');
            if (severityCtx && window.severityData) {
                new Chart(severityCtx, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(window.severityData),
                        datasets: [{
                            data: Object.values(window.severityData),
                            backgroundColor: ['#dc3545', '#fd7e14', '#ffc107', '#28a745']
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
            }
            
            // Type chart
            const typeCtx = document.getElementById('type-chart');
            if (typeCtx && window.typeData) {
                new Chart(typeCtx, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(window.typeData).map(key => 
                            key.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase())
                        ),
                        datasets: [{
                            data: Object.values(window.typeData),
                            backgroundColor: '#007bff'
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                display: false
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });
            }
        }
        </script>
        """