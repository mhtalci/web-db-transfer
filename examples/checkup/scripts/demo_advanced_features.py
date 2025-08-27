#!/usr/bin/env python3
"""
Advanced Features Demonstration for Codebase Checkup

This script demonstrates advanced features like custom analyzers,
configuration management, and integration with external tools.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from migration_assistant.checkup import (
    CodebaseOrchestrator, 
    CheckupConfig,
    BaseAnalyzer,
    AnalysisResult,
    Issue
)


class CustomSecurityAnalyzer(BaseAnalyzer):
    """Custom analyzer for security-specific checks."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "custom_security"
        self.description = "Custom security analyzer"
    
    async def analyze(self, files: List[Path]) -> AnalysisResult:
        """Analyze files for security issues."""
        issues = []
        
        for file_path in files:
            if file_path.suffix != '.py':
                continue
                
            try:
                content = file_path.read_text()
                file_issues = self._analyze_file_security(file_path, content)
                issues.extend(file_issues)
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
        
        return AnalysisResult(
            analyzer_name=self.name,
            files_analyzed=len([f for f in files if f.suffix == '.py']),
            issues=issues,
            metrics={'security_score': self._calculate_security_score(issues)}
        )
    
    def _analyze_file_security(self, file_path: Path, content: str) -> List[Issue]:
        """Analyze a single file for security issues."""
        issues = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for hardcoded secrets
            if any(keyword in line.lower() for keyword in ['password', 'secret', 'key', 'token']):
                if '=' in line and any(quote in line for quote in ['"', "'"]):
                    issues.append(Issue(
                        file=file_path,
                        line=line_num,
                        column=1,
                        message="Potential hardcoded secret detected",
                        severity="high",
                        rule="hardcoded-secret",
                        category="security"
                    ))
            
            # Check for dangerous functions
            dangerous_functions = ['eval', 'exec', 'compile', '__import__']
            for func in dangerous_functions:
                if f'{func}(' in line:
                    issues.append(Issue(
                        file=file_path,
                        line=line_num,
                        column=line.find(func) + 1,
                        message=f"Dangerous function '{func}' usage detected",
                        severity="critical",
                        rule="dangerous-function",
                        category="security"
                    ))
            
            # Check for SQL injection patterns
            sql_patterns = ['%s', '.format(', 'f"', "f'"]
            if 'SELECT' in line.upper() or 'INSERT' in line.upper() or 'UPDATE' in line.upper():
                if any(pattern in line for pattern in sql_patterns):
                    issues.append(Issue(
                        file=file_path,
                        line=line_num,
                        column=1,
                        message="Potential SQL injection vulnerability",
                        severity="high",
                        rule="sql-injection",
                        category="security"
                    ))
        
        return issues
    
    def _calculate_security_score(self, issues: List[Issue]) -> float:
        """Calculate security score based on issues."""
        if not issues:
            return 100.0
        
        critical_count = sum(1 for issue in issues if issue.severity == 'critical')
        high_count = sum(1 for issue in issues if issue.severity == 'high')
        medium_count = sum(1 for issue in issues if issue.severity == 'medium')
        
        # Weighted scoring
        penalty = (critical_count * 20) + (high_count * 10) + (medium_count * 5)
        return max(0.0, 100.0 - penalty)


class CustomPerformanceAnalyzer(BaseAnalyzer):
    """Custom analyzer for performance-related issues."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.name = "custom_performance"
        self.description = "Custom performance analyzer"
    
    async def analyze(self, files: List[Path]) -> AnalysisResult:
        """Analyze files for performance issues."""
        issues = []
        
        for file_path in files:
            if file_path.suffix != '.py':
                continue
                
            try:
                content = file_path.read_text()
                file_issues = self._analyze_file_performance(file_path, content)
                issues.extend(file_issues)
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
        
        return AnalysisResult(
            analyzer_name=self.name,
            files_analyzed=len([f for f in files if f.suffix == '.py']),
            issues=issues,
            metrics={'performance_score': self._calculate_performance_score(issues)}
        )
    
    def _analyze_file_performance(self, file_path: Path, content: str) -> List[Issue]:
        """Analyze a single file for performance issues."""
        issues = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for inefficient loops
            if 'for' in line and 'in range(len(' in line:
                issues.append(Issue(
                    file=file_path,
                    line=line_num,
                    column=1,
                    message="Inefficient loop pattern, consider enumerate() or direct iteration",
                    severity="medium",
                    rule="inefficient-loop",
                    category="performance"
                ))
            
            # Check for string concatenation in loops
            if any(keyword in line for keyword in ['for ', 'while ']) and '+=' in line and 'str' in line:
                issues.append(Issue(
                    file=file_path,
                    line=line_num,
                    column=1,
                    message="String concatenation in loop, consider using join()",
                    severity="medium",
                    rule="string-concat-loop",
                    category="performance"
                ))
            
            # Check for global variable access in functions
            if line.strip().startswith('global '):
                issues.append(Issue(
                    file=file_path,
                    line=line_num,
                    column=1,
                    message="Global variable usage may impact performance",
                    severity="low",
                    rule="global-variable",
                    category="performance"
                ))
        
        return issues
    
    def _calculate_performance_score(self, issues: List[Issue]) -> float:
        """Calculate performance score based on issues."""
        if not issues:
            return 100.0
        
        high_count = sum(1 for issue in issues if issue.severity == 'high')
        medium_count = sum(1 for issue in issues if issue.severity == 'medium')
        low_count = sum(1 for issue in issues if issue.severity == 'low')
        
        penalty = (high_count * 15) + (medium_count * 8) + (low_count * 3)
        return max(0.0, 100.0 - penalty)


class ConfigurationManager:
    """Manages different checkup configurations."""
    
    def __init__(self):
        self.configurations = {}
        self._load_default_configurations()
    
    def _load_default_configurations(self):
        """Load default configurations."""
        self.configurations = {
            'minimal': CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=False,
                enable_duplicate_detection=False,
                generate_html_report=False,
                generate_json_report=True,
                timeout=60
            ),
            'standard': CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                enable_duplicate_detection=True,
                generate_html_report=True,
                generate_json_report=True,
                timeout=300
            ),
            'comprehensive': CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                enable_duplicate_detection=True,
                enable_structure_analysis=True,
                enable_coverage_analysis=True,
                enable_config_validation=True,
                enable_doc_validation=True,
                generate_html_report=True,
                generate_json_report=True,
                generate_markdown_report=True,
                timeout=600
            ),
            'security_focused': CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                use_bandit=True,
                generate_json_report=True,
                timeout=300
            ),
            'performance_focused': CheckupConfig(
                enable_quality_analysis=True,
                enable_duplicate_detection=True,
                generate_json_report=True,
                timeout=300
            )
        }
    
    def get_configuration(self, name: str) -> Optional[CheckupConfig]:
        """Get configuration by name."""
        return self.configurations.get(name)
    
    def list_configurations(self) -> List[str]:
        """List available configuration names."""
        return list(self.configurations.keys())
    
    def create_custom_configuration(self, name: str, base_config: str = 'standard', **overrides) -> CheckupConfig:
        """Create custom configuration based on existing one."""
        base = self.configurations.get(base_config)
        if not base:
            raise ValueError(f"Base configuration '{base_config}' not found")
        
        # Create new config with overrides
        config_dict = base.__dict__.copy()
        config_dict.update(overrides)
        
        custom_config = CheckupConfig(**config_dict)
        self.configurations[name] = custom_config
        
        return custom_config


async def demo_custom_analyzers():
    """Demonstrate custom analyzer implementation."""
    print("🔧 Custom Analyzers Demonstration")
    print("=" * 50)
    
    # Create test project with security and performance issues
    project_dir = Path("custom_analyzer_demo")
    project_dir.mkdir(exist_ok=True)
    
    # Create file with security issues
    (project_dir / "security_issues.py").write_text('''
# Security issues for demonstration
import os

# Hardcoded secret
API_KEY = "sk-1234567890abcdef"
PASSWORD = "admin123"

def authenticate(username, password):
    # Dangerous eval usage
    result = eval(f"check_user('{username}', '{password}')")
    return result

def get_user_data(user_id):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return execute_query(query)

def process_input(user_input):
    # Another dangerous function
    return exec(user_input)
''')
    
    # Create file with performance issues
    (project_dir / "performance_issues.py").write_text('''
# Performance issues for demonstration

def inefficient_loop(items):
    # Inefficient range(len()) pattern
    for i in range(len(items)):
        print(items[i])

def string_concatenation(words):
    result = ""
    # String concatenation in loop
    for word in words:
        result += word + " "
    return result

# Global variable usage
global_counter = 0

def increment_counter():
    global global_counter
    global_counter += 1
    return global_counter
''')
    
    try:
        # Create configuration with custom analyzers
        config = CheckupConfig(
            enable_quality_analysis=True,
            generate_json_report=True,
            output_directory="custom-analyzer-reports"
        )
        
        # Initialize orchestrator
        orchestrator = CodebaseOrchestrator(config, project_dir)
        
        # Add custom analyzers
        security_analyzer = CustomSecurityAnalyzer(config)
        performance_analyzer = CustomPerformanceAnalyzer(config)
        
        orchestrator.add_custom_analyzer(security_analyzer)
        orchestrator.add_custom_analyzer(performance_analyzer)
        
        # Run analysis
        print("Running analysis with custom analyzers...")
        results = await orchestrator.run_analysis_only()
        
        # Display results
        print(f"\n📊 Custom Analysis Results:")
        print(f"Files analyzed: {results.files_analyzed}")
        print(f"Total issues: {results.total_issues}")
        
        # Show custom analyzer results
        security_results = results.get_analyzer_results('custom_security')
        if security_results:
            print(f"\n🔒 Security Analysis:")
            print(f"  Security issues: {len(security_results.issues)}")
            print(f"  Security score: {security_results.metrics.get('security_score', 0):.1f}")
            
            for issue in security_results.issues[:3]:  # Show first 3
                print(f"    {issue.file.name}:{issue.line} - {issue.message}")
        
        performance_results = results.get_analyzer_results('custom_performance')
        if performance_results:
            print(f"\n⚡ Performance Analysis:")
            print(f"  Performance issues: {len(performance_results.issues)}")
            print(f"  Performance score: {performance_results.metrics.get('performance_score', 0):.1f}")
            
            for issue in performance_results.issues[:3]:  # Show first 3
                print(f"    {issue.file.name}:{issue.line} - {issue.message}")
        
        return results
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)


async def demo_configuration_management():
    """Demonstrate configuration management."""
    print("\n⚙️ Configuration Management Demonstration")
    print("=" * 50)
    
    config_manager = ConfigurationManager()
    
    # List available configurations
    print("Available configurations:")
    for config_name in config_manager.list_configurations():
        config = config_manager.get_configuration(config_name)
        print(f"  - {config_name}: timeout={config.timeout}s, "
              f"quality={config.enable_quality_analysis}, "
              f"imports={config.enable_import_analysis}")
    
    # Create custom configuration
    print(f"\n🔧 Creating custom configuration...")
    custom_config = config_manager.create_custom_configuration(
        'my_custom',
        base_config='standard',
        timeout=180,
        enable_coverage_analysis=True,
        generate_markdown_report=True,
        output_directory='my-custom-reports'
    )
    
    print(f"Custom configuration created:")
    print(f"  Timeout: {custom_config.timeout}s")
    print(f"  Coverage analysis: {custom_config.enable_coverage_analysis}")
    print(f"  Markdown reports: {custom_config.generate_markdown_report}")
    print(f"  Output directory: {custom_config.output_directory}")
    
    # Test different configurations
    test_project = await create_test_project()
    
    try:
        for config_name in ['minimal', 'standard', 'comprehensive']:
            print(f"\n🧪 Testing '{config_name}' configuration:")
            
            config = config_manager.get_configuration(config_name)
            orchestrator = CodebaseOrchestrator(config, test_project)
            
            start_time = datetime.now()
            results = await orchestrator.run_analysis_only()
            end_time = datetime.now()
            
            duration = (end_time - start_time).total_seconds()
            
            print(f"  Duration: {duration:.1f}s")
            print(f"  Issues found: {results.total_issues}")
            print(f"  Files analyzed: {results.files_analyzed}")
    
    finally:
        # Clean up
        import shutil
        if test_project.exists():
            shutil.rmtree(test_project)


async def demo_external_tool_integration():
    """Demonstrate integration with external tools."""
    print("\n🔗 External Tool Integration Demonstration")
    print("=" * 50)
    
    # Create test project
    project_dir = Path("external_tools_demo")
    project_dir.mkdir(exist_ok=True)
    
    # Create Python files for testing
    (project_dir / "main.py").write_text('''
"""Main module."""

import json
import sys
from typing import List, Dict, Any


def process_data(data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Process data and return statistics.
    
    Args:
        data: List of dictionaries to process
        
    Returns:
        Dictionary with statistics
    """
    if not data:
        return {"count": 0, "total": 0}
    
    count = len(data)
    total = sum(item.get("value", 0) for item in data)
    
    return {"count": count, "total": total}


def main() -> None:
    """Main function."""
    sample_data = [
        {"name": "item1", "value": 10},
        {"name": "item2", "value": 20},
        {"name": "item3", "value": 30}
    ]
    
    result = process_data(sample_data)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
''')
    
    # Create requirements.txt
    (project_dir / "requirements.txt").write_text('''
requests>=2.25.0
numpy>=1.20.0
pandas>=1.3.0
''')
    
    # Create pyproject.toml
    (project_dir / "pyproject.toml").write_text('''
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "external-tools-demo"
version = "0.1.0"
description = "Demo project for external tool integration"

[tool.black]
line-length = 88
target-version = ['py39']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
''')
    
    try:
        # Configuration with external tools
        config = CheckupConfig(
            enable_quality_analysis=True,
            enable_import_analysis=True,
            enable_config_validation=True,
            
            # External tool integration
            use_black=True,
            use_isort=True,
            use_mypy=True,
            use_flake8=True,
            use_bandit=True,
            
            # Reporting
            generate_html_report=True,
            generate_json_report=True,
            output_directory="external-tools-reports"
        )
        
        orchestrator = CodebaseOrchestrator(config, project_dir)
        
        print("Running analysis with external tools integration...")
        results = await orchestrator.run_analysis_only()
        
        print(f"\n📊 External Tools Integration Results:")
        print(f"Files analyzed: {results.files_analyzed}")
        print(f"Issues found: {results.total_issues}")
        
        # Show tool-specific results
        tool_results = results.get_tool_results()
        for tool_name, tool_result in tool_results.items():
            print(f"\n🔧 {tool_name.upper()} Results:")
            print(f"  Issues: {len(tool_result.issues)}")
            print(f"  Status: {tool_result.status}")
            
            if tool_result.issues:
                for issue in tool_result.issues[:2]:  # Show first 2
                    print(f"    {issue.file.name}:{issue.line} - {issue.message}")
        
        # Generate reports
        print(f"\n📄 Generating reports...")
        report_results = await orchestrator.generate_reports(results)
        
        if report_results.html_report_path:
            print(f"HTML report: {report_results.html_report_path}")
        if report_results.json_report_path:
            print(f"JSON report: {report_results.json_report_path}")
        
        return results
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)


async def demo_advanced_reporting():
    """Demonstrate advanced reporting features."""
    print("\n📊 Advanced Reporting Demonstration")
    print("=" * 50)
    
    # Create test project with various issues
    project_dir = Path("advanced_reporting_demo")
    project_dir.mkdir(exist_ok=True)
    
    # Create files with different types of issues
    files_content = {
        "quality_issues.py": '''
# Quality issues
def bad_function(a,b,c,d,e,f,g,h,i,j):  # Too many parameters
    if a==b:  # No spaces
        if c==d:  # Nested conditions
            if e==f:
                return a+b+c+d+e+f+g+h+i+j
            else:
                return 0
        else:
            return 1
    else:
        return 2
''',
        "import_issues.py": '''
import os
import sys
import json
import unused_module  # Unused import
from typing import List, Dict, Any, Optional, Union, Tuple  # Too many imports

def function_with_imports():
    return os.path.join("test", "path")
''',
        "duplicate_code.py": '''
def process_user_data(user_data):
    if not user_data:
        return None
    
    result = {}
    for key, value in user_data.items():
        if value is not None:
            result[key] = str(value).strip()
    
    return result

def process_admin_data(admin_data):
    if not admin_data:
        return None
    
    result = {}
    for key, value in admin_data.items():
        if value is not None:
            result[key] = str(value).strip()
    
    return result
'''
    }
    
    for filename, content in files_content.items():
        (project_dir / filename).write_text(content)
    
    try:
        # Configuration for comprehensive analysis
        config = CheckupConfig(
            enable_quality_analysis=True,
            enable_import_analysis=True,
            enable_duplicate_detection=True,
            enable_structure_analysis=True,
            
            # Advanced reporting
            generate_html_report=True,
            generate_json_report=True,
            generate_markdown_report=True,
            
            # Report customization
            include_metrics=True,
            include_suggestions=True,
            include_examples=True,
            include_source_code=True,
            
            output_directory="advanced-reports"
        )
        
        orchestrator = CodebaseOrchestrator(config, project_dir)
        
        print("Running comprehensive analysis...")
        results = await orchestrator.run_analysis_only()
        
        # Generate advanced reports
        print("Generating advanced reports...")
        report_results = await orchestrator.generate_reports(results)
        
        print(f"\n📊 Advanced Reporting Results:")
        print(f"Files analyzed: {results.files_analyzed}")
        print(f"Total issues: {results.total_issues}")
        
        # Show metrics
        if hasattr(results, 'metrics'):
            print(f"\n📈 Metrics:")
            for metric_name, metric_value in results.metrics.items():
                print(f"  {metric_name}: {metric_value}")
        
        # Show issue categories
        issue_categories = {}
        for issue in results.all_issues:
            category = issue.category
            if category not in issue_categories:
                issue_categories[category] = 0
            issue_categories[category] += 1
        
        print(f"\n📋 Issues by Category:")
        for category, count in issue_categories.items():
            print(f"  {category}: {count}")
        
        # Show generated reports
        print(f"\n📄 Generated Reports:")
        if report_results.html_report_path:
            print(f"  HTML: {report_results.html_report_path}")
        if report_results.json_report_path:
            print(f"  JSON: {report_results.json_report_path}")
        if report_results.markdown_report_path:
            print(f"  Markdown: {report_results.markdown_report_path}")
        
        # Create custom report summary
        create_custom_report_summary(results, project_dir / "custom_summary.md")
        
        return results
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)


def create_custom_report_summary(results, output_path: Path):
    """Create a custom report summary."""
    summary = f"""# Custom Checkup Summary

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview
- **Files Analyzed:** {results.files_analyzed}
- **Total Issues:** {results.total_issues}
- **Analysis Duration:** {results.duration.total_seconds():.1f} seconds

## Issue Breakdown
"""
    
    # Group issues by severity
    severity_counts = {}
    for issue in results.all_issues:
        severity = issue.severity
        if severity not in severity_counts:
            severity_counts[severity] = 0
        severity_counts[severity] += 1
    
    for severity, count in sorted(severity_counts.items()):
        summary += f"- **{severity.capitalize()}:** {count}\n"
    
    summary += "\n## Top Issues\n\n"
    
    # Show top issues
    for i, issue in enumerate(results.all_issues[:5], 1):
        summary += f"{i}. **{issue.file.name}:{issue.line}** - {issue.message} ({issue.severity})\n"
    
    if len(results.all_issues) > 5:
        summary += f"\n... and {len(results.all_issues) - 5} more issues\n"
    
    summary += "\n## Recommendations\n\n"
    summary += "1. Address critical and high severity issues first\n"
    summary += "2. Focus on files with the most issues\n"
    summary += "3. Consider refactoring complex functions\n"
    summary += "4. Improve code documentation\n"
    
    output_path.write_text(summary)
    print(f"Custom summary saved to: {output_path}")


async def create_test_project() -> Path:
    """Create a test project for demonstrations."""
    project_dir = Path("test_project")
    project_dir.mkdir(exist_ok=True)
    
    (project_dir / "app.py").write_text('''
"""Test application."""

def greet(name: str) -> str:
    """Greet a person by name."""
    return f"Hello, {name}!"

def main():
    """Main function."""
    print(greet("World"))

if __name__ == "__main__":
    main()
''')
    
    return project_dir


async def main():
    """Run advanced features demonstrations."""
    print("🚀 Advanced Features Demonstration")
    print("=" * 60)
    
    try:
        # Run demonstrations
        await demo_custom_analyzers()
        await demo_configuration_management()
        await demo_external_tool_integration()
        await demo_advanced_reporting()
        
        print(f"\n✅ Advanced features demo completed!")
        print("\nKey features demonstrated:")
        print("  - Custom analyzer implementation")
        print("  - Configuration management system")
        print("  - External tool integration")
        print("  - Advanced reporting capabilities")
        print("  - Custom report generation")
        print("  - Flexible analysis workflows")
        
    except Exception as e:
        print(f"❌ Advanced features demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted by user")
        sys.exit(1)