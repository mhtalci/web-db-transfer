#!/usr/bin/env python3
"""
Basic Usage Demonstration for Codebase Checkup API

This script demonstrates the basic usage of the codebase checkup system
through its Python API.
"""

import asyncio
import sys
from pathlib import Path
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig


async def demo_basic_analysis():
    """Demonstrate basic code analysis."""
    print("🔍 Basic Code Analysis Demo")
    print("=" * 50)
    
    # Create basic configuration
    config = CheckupConfig(
        enable_quality_analysis=True,
        enable_import_analysis=True,
        enable_duplicate_detection=False,  # Disable for speed
        create_backup=False,  # No changes in this demo
        generate_html_report=True,
        output_directory="demo-reports"
    )
    
    # Initialize orchestrator
    orchestrator = CodebaseOrchestrator(config, Path("."))
    
    try:
        # Run analysis
        print("Running analysis...")
        results = await orchestrator.run_analysis_only()
        
        # Display results
        print(f"\n📊 Analysis Results:")
        print(f"Files analyzed: {results.files_analyzed}")
        print(f"Total issues: {results.total_issues}")
        print(f"Duration: {results.duration.total_seconds():.1f} seconds")
        
        # Show issues by category
        print(f"\n📋 Issues by Category:")
        print(f"Quality issues: {len(results.quality_issues)}")
        print(f"Import issues: {len(results.import_issues)}")
        print(f"Structure issues: {len(results.structure_issues)}")
        
        # Show severity breakdown
        severity_counts = results.severity_counts
        print(f"\n⚠️  Issues by Severity:")
        for severity, count in severity_counts.items():
            print(f"{severity.capitalize()}: {count}")
        
        # Show some example issues
        if results.quality_issues:
            print(f"\n🔍 Sample Quality Issues:")
            for issue in results.quality_issues[:3]:  # Show first 3
                print(f"  {issue.file}:{issue.line} - {issue.message}")
            if len(results.quality_issues) > 3:
                print(f"  ... and {len(results.quality_issues) - 3} more")
        
        # Generate reports
        print(f"\n📄 Generating reports...")
        report_results = await orchestrator.generate_reports(results)
        
        if report_results.html_report_path:
            print(f"HTML report: {report_results.html_report_path}")
        if report_results.json_report_path:
            print(f"JSON report: {report_results.json_report_path}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        return None


async def demo_with_cleanup():
    """Demonstrate analysis with cleanup."""
    print("\n🧹 Analysis with Cleanup Demo")
    print("=" * 50)
    
    # Create configuration with cleanup enabled
    config = CheckupConfig(
        enable_quality_analysis=True,
        enable_import_analysis=True,
        auto_format=True,
        auto_fix_imports=True,
        create_backup=True,
        dry_run=True,  # Safe mode for demo
        output_directory="demo-reports"
    )
    
    orchestrator = CodebaseOrchestrator(config, Path("."))
    
    try:
        # Run full checkup
        print("Running full checkup with cleanup...")
        results = await orchestrator.run_full_checkup()
        
        print(f"\n📊 Checkup Results:")
        print(f"Analysis duration: {results.analysis.duration.total_seconds():.1f}s")
        print(f"Issues found: {results.analysis.total_issues}")
        
        if results.cleanup:
            print(f"Cleanup duration: {results.cleanup.duration.total_seconds():.1f}s")
            print(f"Changes made: {results.cleanup.total_changes}")
            print(f"Files modified: {results.cleanup.files_modified}")
            
            # Show types of changes
            if results.cleanup.formatting_changes:
                print(f"Formatting changes: {len(results.cleanup.formatting_changes)}")
            if results.cleanup.import_cleanups:
                print(f"Import cleanups: {len(results.cleanup.import_cleanups)}")
        
        # Show improvement metrics
        if results.improvement_metrics:
            print(f"\n📈 Improvements:")
            for metric, improvement in results.improvement_metrics.items():
                print(f"{metric}: {improvement:+.1%}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during checkup: {e}")
        return None


async def demo_custom_configuration():
    """Demonstrate custom configuration options."""
    print("\n⚙️  Custom Configuration Demo")
    print("=" * 50)
    
    # Create custom configuration
    config = CheckupConfig(
        # Analysis settings
        enable_quality_analysis=True,
        enable_duplicate_detection=True,
        enable_import_analysis=True,
        
        # Custom quality settings
        max_complexity=8,  # Stricter than default
        max_line_length=100,  # Different from black default
        
        # Custom file filtering
        include_patterns=["*.py"],
        exclude_patterns=[
            "venv/*",
            "tests/*",  # Skip tests for this demo
            "__pycache__/*"
        ],
        
        # Performance settings
        parallel_analysis=True,
        max_workers=2,
        timeout=60,  # 1 minute timeout
        
        # Reporting
        generate_html_report=True,
        generate_json_report=True,
        output_directory="custom-reports"
    )
    
    print("Custom configuration:")
    print(f"  Max complexity: {config.max_complexity}")
    print(f"  Max line length: {config.max_line_length}")
    print(f"  Parallel workers: {config.max_workers}")
    print(f"  Exclude patterns: {config.exclude_patterns}")
    
    orchestrator = CodebaseOrchestrator(config, Path("."))
    
    try:
        results = await orchestrator.run_analysis_only()
        
        print(f"\n📊 Custom Analysis Results:")
        print(f"Files analyzed: {results.files_analyzed}")
        print(f"Issues found: {results.total_issues}")
        
        # Show complexity issues specifically
        complexity_issues = [
            issue for issue in results.quality_issues 
            if "complexity" in issue.message.lower()
        ]
        if complexity_issues:
            print(f"\n🔄 Complexity Issues (max {config.max_complexity}):")
            for issue in complexity_issues[:3]:
                print(f"  {issue.file}:{issue.line} - {issue.message}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error with custom configuration: {e}")
        return None


async def demo_file_specific_analysis():
    """Demonstrate analyzing specific files."""
    print("\n📁 File-Specific Analysis Demo")
    print("=" * 50)
    
    # Find some Python files to analyze
    python_files = list(Path(".").glob("**/*.py"))[:5]  # First 5 files
    
    if not python_files:
        print("No Python files found for analysis")
        return
    
    print(f"Analyzing {len(python_files)} specific files:")
    for file in python_files:
        print(f"  {file}")
    
    config = CheckupConfig(
        enable_quality_analysis=True,
        enable_import_analysis=True,
        generate_json_report=True,
        output_directory="file-specific-reports"
    )
    
    orchestrator = CodebaseOrchestrator(config, Path("."))
    
    try:
        # Analyze specific files
        results = await orchestrator.analyze_files(python_files)
        
        print(f"\n📊 File-Specific Results:")
        print(f"Files analyzed: {len(python_files)}")
        print(f"Issues found: {results.total_issues}")
        
        # Show issues per file
        print(f"\n📋 Issues per File:")
        for file in python_files:
            file_issues = results.get_issues_by_file(file)
            print(f"  {file}: {len(file_issues)} issues")
            
            # Show first issue for each file
            if file_issues:
                first_issue = file_issues[0]
                print(f"    └─ {first_issue.message}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in file-specific analysis: {e}")
        return None


def print_summary(results_list):
    """Print summary of all demo results."""
    print("\n" + "=" * 60)
    print("📋 DEMO SUMMARY")
    print("=" * 60)
    
    total_files = 0
    total_issues = 0
    
    for i, results in enumerate(results_list, 1):
        if results:
            total_files += results.files_analyzed
            total_issues += results.total_issues
            print(f"Demo {i}: {results.files_analyzed} files, {results.total_issues} issues")
        else:
            print(f"Demo {i}: Failed")
    
    print(f"\nOverall: {total_files} files analyzed, {total_issues} total issues")
    print("\n✅ Demo completed! Check the generated reports in:")
    print("  - demo-reports/")
    print("  - custom-reports/")
    print("  - file-specific-reports/")


async def main():
    """Run all demonstrations."""
    print("🚀 Codebase Checkup API Demonstration")
    print("=" * 60)
    print("This demo shows various ways to use the checkup system.")
    print()
    
    results = []
    
    # Run demonstrations
    result1 = await demo_basic_analysis()
    results.append(result1)
    
    result2 = await demo_with_cleanup()
    results.append(result2)
    
    result3 = await demo_custom_configuration()
    results.append(result3)
    
    result4 = await demo_file_specific_analysis()
    results.append(result4)
    
    # Print summary
    print_summary(results)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        sys.exit(1)