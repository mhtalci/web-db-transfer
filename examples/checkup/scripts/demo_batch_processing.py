#!/usr/bin/env python3
"""
Batch Processing Demonstration for Codebase Checkup

This script demonstrates how to process multiple projects or directories
in batch using the codebase checkup system.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig


@dataclass
class ProjectResult:
    """Results for a single project."""
    project_path: Path
    project_name: str
    success: bool
    files_analyzed: int
    issues_found: int
    quality_score: float
    duration_seconds: float
    error_message: Optional[str] = None
    report_paths: Optional[Dict[str, Path]] = None


@dataclass
class BatchResults:
    """Results for batch processing."""
    total_projects: int
    successful_projects: int
    failed_projects: int
    total_files: int
    total_issues: int
    average_quality_score: float
    total_duration_seconds: float
    project_results: List[ProjectResult]
    timestamp: datetime


class BatchProcessor:
    """Handles batch processing of multiple projects."""
    
    def __init__(self, base_config: CheckupConfig):
        self.base_config = base_config
        self.results: List[ProjectResult] = []
    
    async def process_projects(self, project_paths: List[Path]) -> BatchResults:
        """Process multiple projects in batch."""
        print(f"🚀 Starting batch processing of {len(project_paths)} projects")
        start_time = datetime.now()
        
        # Process projects concurrently (with limit)
        semaphore = asyncio.Semaphore(3)  # Limit concurrent processing
        tasks = [
            self._process_project_with_semaphore(semaphore, path)
            for path in project_paths
        ]
        
        self.results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(self.results):
            if isinstance(result, Exception):
                processed_results.append(ProjectResult(
                    project_path=project_paths[i],
                    project_name=project_paths[i].name,
                    success=False,
                    files_analyzed=0,
                    issues_found=0,
                    quality_score=0.0,
                    duration_seconds=0.0,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        self.results = processed_results
        
        # Calculate batch statistics
        end_time = datetime.now()
        successful = [r for r in self.results if r.success]
        
        return BatchResults(
            total_projects=len(project_paths),
            successful_projects=len(successful),
            failed_projects=len(project_paths) - len(successful),
            total_files=sum(r.files_analyzed for r in successful),
            total_issues=sum(r.issues_found for r in successful),
            average_quality_score=sum(r.quality_score for r in successful) / len(successful) if successful else 0.0,
            total_duration_seconds=(end_time - start_time).total_seconds(),
            project_results=self.results,
            timestamp=start_time
        )
    
    async def _process_project_with_semaphore(self, semaphore: asyncio.Semaphore, project_path: Path) -> ProjectResult:
        """Process a single project with semaphore for concurrency control."""
        async with semaphore:
            return await self._process_single_project(project_path)
    
    async def _process_single_project(self, project_path: Path) -> ProjectResult:
        """Process a single project."""
        project_name = project_path.name
        print(f"  📁 Processing {project_name}...")
        
        start_time = datetime.now()
        
        try:
            # Create project-specific configuration
            config = self._create_project_config(project_path)
            
            # Initialize orchestrator
            orchestrator = CodebaseOrchestrator(config, project_path)
            
            # Run analysis
            results = await orchestrator.run_analysis_only()
            
            # Generate reports if requested
            report_paths = None
            if config.generate_html_report or config.generate_json_report:
                report_results = await orchestrator.generate_reports(results)
                report_paths = {
                    'html': report_results.html_report_path,
                    'json': report_results.json_report_path,
                    'markdown': report_results.markdown_report_path
                }
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return ProjectResult(
                project_path=project_path,
                project_name=project_name,
                success=True,
                files_analyzed=results.files_analyzed,
                issues_found=results.total_issues,
                quality_score=results.metrics.quality_score if hasattr(results.metrics, 'quality_score') else 0.0,
                duration_seconds=duration,
                report_paths=report_paths
            )
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return ProjectResult(
                project_path=project_path,
                project_name=project_name,
                success=False,
                files_analyzed=0,
                issues_found=0,
                quality_score=0.0,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def _create_project_config(self, project_path: Path) -> CheckupConfig:
        """Create project-specific configuration."""
        # Check for project-specific config file
        project_config_file = project_path / "checkup.toml"
        if project_config_file.exists():
            try:
                return CheckupConfig.from_file(project_config_file)
            except Exception as e:
                print(f"    ⚠️  Failed to load project config: {e}, using default")
        
        # Use base configuration with project-specific adjustments
        config = CheckupConfig(
            # Copy base settings
            enable_quality_analysis=self.base_config.enable_quality_analysis,
            enable_duplicate_detection=self.base_config.enable_duplicate_detection,
            enable_import_analysis=self.base_config.enable_import_analysis,
            
            # Batch-specific settings
            generate_json_report=True,  # Always generate JSON for batch processing
            generate_html_report=False,  # Skip HTML for batch to save time
            output_directory=f"batch-reports/{project_path.name}",
            
            # Performance settings for batch
            parallel_analysis=True,
            max_workers=2,  # Reduced for batch processing
            timeout=120,  # 2 minutes per project
            
            # Safety settings
            create_backup=False,  # No backups in batch mode
            dry_run=True,  # Safe mode for batch
            require_confirmation=False
        )
        
        return config
    
    def save_batch_report(self, batch_results: BatchResults, output_file: Path):
        """Save batch results to JSON file."""
        # Convert to serializable format
        data = asdict(batch_results)
        
        # Convert Path objects to strings
        for project_result in data['project_results']:
            project_result['project_path'] = str(project_result['project_path'])
            if project_result['report_paths']:
                project_result['report_paths'] = {
                    k: str(v) if v else None 
                    for k, v in project_result['report_paths'].items()
                }
        
        # Convert timestamp
        data['timestamp'] = batch_results.timestamp.isoformat()
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"📄 Batch report saved to: {output_file}")


async def demo_batch_processing():
    """Demonstrate batch processing of multiple projects."""
    print("📦 Batch Processing Demonstration")
    print("=" * 50)
    
    # Create sample projects for demonstration
    sample_projects = await create_sample_projects()
    
    try:
        # Configure batch processing
        base_config = CheckupConfig(
            enable_quality_analysis=True,
            enable_import_analysis=True,
            enable_duplicate_detection=False,  # Skip for speed in demo
            generate_json_report=True,
            parallel_analysis=True,
            max_workers=2,
            timeout=60  # 1 minute per project
        )
        
        # Initialize batch processor
        processor = BatchProcessor(base_config)
        
        # Process projects
        batch_results = await processor.process_projects(sample_projects)
        
        # Display results
        print_batch_results(batch_results)
        
        # Save batch report
        report_file = Path("batch_processing_report.json")
        processor.save_batch_report(batch_results, report_file)
        
        return batch_results
        
    finally:
        # Clean up sample projects
        await cleanup_sample_projects(sample_projects)


async def demo_selective_batch_processing():
    """Demonstrate selective batch processing with filtering."""
    print("\n🎯 Selective Batch Processing Demonstration")
    print("=" * 50)
    
    # Create projects with different characteristics
    projects = await create_diverse_sample_projects()
    
    try:
        # Define different processing strategies
        strategies = {
            'quick_scan': CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=False,
                enable_duplicate_detection=False,
                timeout=30,
                generate_json_report=True
            ),
            'comprehensive': CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                enable_duplicate_detection=True,
                enable_coverage_analysis=True,
                timeout=180,
                generate_html_report=True,
                generate_json_report=True
            ),
            'security_focused': CheckupConfig(
                enable_quality_analysis=True,
                enable_import_analysis=True,
                use_bandit=True,
                timeout=90,
                generate_json_report=True
            )
        }
        
        # Process with different strategies
        for strategy_name, config in strategies.items():
            print(f"\n🔍 Processing with '{strategy_name}' strategy:")
            
            processor = BatchProcessor(config)
            results = await processor.process_projects(projects)
            
            print(f"  Projects processed: {results.successful_projects}/{results.total_projects}")
            print(f"  Average quality score: {results.average_quality_score:.1f}")
            print(f"  Total duration: {results.total_duration_seconds:.1f}s")
            
            # Save strategy-specific report
            report_file = Path(f"batch_{strategy_name}_report.json")
            processor.save_batch_report(results, report_file)
        
    finally:
        await cleanup_sample_projects(projects)


async def demo_project_comparison():
    """Demonstrate comparing projects using batch processing."""
    print("\n📊 Project Comparison Demonstration")
    print("=" * 50)
    
    # Create projects for comparison
    projects = await create_comparison_projects()
    
    try:
        config = CheckupConfig(
            enable_quality_analysis=True,
            enable_import_analysis=True,
            enable_duplicate_detection=True,
            generate_json_report=True,
            timeout=120
        )
        
        processor = BatchProcessor(config)
        results = await processor.process_projects(projects)
        
        # Create comparison report
        create_comparison_report(results)
        
    finally:
        await cleanup_sample_projects(projects)


def print_batch_results(batch_results: BatchResults):
    """Print formatted batch results."""
    print(f"\n📊 Batch Processing Results")
    print("=" * 50)
    print(f"Total projects: {batch_results.total_projects}")
    print(f"Successful: {batch_results.successful_projects}")
    print(f"Failed: {batch_results.failed_projects}")
    print(f"Total files analyzed: {batch_results.total_files}")
    print(f"Total issues found: {batch_results.total_issues}")
    print(f"Average quality score: {batch_results.average_quality_score:.1f}")
    print(f"Total duration: {batch_results.total_duration_seconds:.1f} seconds")
    
    print(f"\n📋 Project Details:")
    for result in batch_results.project_results:
        status = "✅" if result.success else "❌"
        print(f"{status} {result.project_name}")
        if result.success:
            print(f"    Files: {result.files_analyzed}, Issues: {result.issues_found}")
            print(f"    Quality: {result.quality_score:.1f}, Duration: {result.duration_seconds:.1f}s")
        else:
            print(f"    Error: {result.error_message}")


def create_comparison_report(batch_results: BatchResults):
    """Create a comparison report between projects."""
    successful_results = [r for r in batch_results.project_results if r.success]
    
    if not successful_results:
        print("No successful results to compare")
        return
    
    print(f"\n📈 Project Comparison Report")
    print("=" * 50)
    
    # Sort by quality score
    by_quality = sorted(successful_results, key=lambda x: x.quality_score, reverse=True)
    print(f"🏆 Best Quality Scores:")
    for i, result in enumerate(by_quality[:3], 1):
        print(f"  {i}. {result.project_name}: {result.quality_score:.1f}")
    
    # Sort by issues (fewer is better)
    by_issues = sorted(successful_results, key=lambda x: x.issues_found)
    print(f"\n🎯 Fewest Issues:")
    for i, result in enumerate(by_issues[:3], 1):
        print(f"  {i}. {result.project_name}: {result.issues_found} issues")
    
    # Sort by size
    by_size = sorted(successful_results, key=lambda x: x.files_analyzed, reverse=True)
    print(f"\n📁 Largest Projects:")
    for i, result in enumerate(by_size[:3], 1):
        print(f"  {i}. {result.project_name}: {result.files_analyzed} files")
    
    # Calculate statistics
    quality_scores = [r.quality_score for r in successful_results]
    issue_counts = [r.issues_found for r in successful_results]
    
    print(f"\n📊 Statistics:")
    print(f"Quality Score - Min: {min(quality_scores):.1f}, Max: {max(quality_scores):.1f}")
    print(f"Issues - Min: {min(issue_counts)}, Max: {max(issue_counts)}")


async def create_sample_projects() -> List[Path]:
    """Create sample projects for batch processing demo."""
    projects = []
    base_dir = Path("batch_demo_projects")
    base_dir.mkdir(exist_ok=True)
    
    # Project 1: Simple project
    project1 = base_dir / "simple_project"
    project1.mkdir(exist_ok=True)
    (project1 / "main.py").write_text('''
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
''')
    projects.append(project1)
    
    # Project 2: Project with issues
    project2 = base_dir / "problematic_project"
    project2.mkdir(exist_ok=True)
    (project2 / "issues.py").write_text('''
import os, sys, json  # Multiple imports on one line
import unused_module  # Unused import

def complex_function(a,b,c,d,e,f,g,h):  # Too many parameters
    if a>b:
        if c>d:
            if e>f:
                if g>h:
                    return a+b+c+d+e+f+g+h
                else:
                    return 0
            else:
                return 1
        else:
            return 2
    else:
        return 3

# Missing docstring
def undocumented_function():
    pass

# Long line that exceeds the recommended length and should be split into multiple lines for better readability
x = "This is a very long string that exceeds the recommended line length and should be split"
''')
    projects.append(project2)
    
    # Project 3: Well-structured project
    project3 = base_dir / "good_project"
    project3.mkdir(exist_ok=True)
    (project3 / "calculator.py").write_text('''
"""A simple calculator module."""

from typing import Union


def add(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """Add two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b


def multiply(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """Multiply two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Product of a and b
    """
    return a * b
''')
    projects.append(project3)
    
    return projects


async def create_diverse_sample_projects() -> List[Path]:
    """Create diverse sample projects for selective processing demo."""
    projects = []
    base_dir = Path("diverse_demo_projects")
    base_dir.mkdir(exist_ok=True)
    
    # Small project
    small = base_dir / "small_project"
    small.mkdir(exist_ok=True)
    (small / "app.py").write_text('print("Small app")')
    projects.append(small)
    
    # Large project (simulated)
    large = base_dir / "large_project"
    large.mkdir(exist_ok=True)
    for i in range(5):
        (large / f"module_{i}.py").write_text(f'''
def function_{i}():
    """Function {i}."""
    return {i}

class Class{i}:
    """Class {i}."""
    
    def method_{i}(self):
        """Method {i}."""
        return function_{i}()
''')
    projects.append(large)
    
    # Legacy project
    legacy = base_dir / "legacy_project"
    legacy.mkdir(exist_ok=True)
    (legacy / "old_code.py").write_text('''
# Legacy code with many issues
def oldFunction(param1,param2,param3,param4,param5,param6):
    global globalVar
    if param1==param2:
        if param3==param4:
            if param5==param6:
                return globalVar+param1+param2+param3+param4+param5+param6
            else:
                return globalVar
        else:
            return param1
    else:
        return 0

globalVar="some global variable"
''')
    projects.append(legacy)
    
    return projects


async def create_comparison_projects() -> List[Path]:
    """Create projects specifically for comparison demo."""
    projects = []
    base_dir = Path("comparison_demo_projects")
    base_dir.mkdir(exist_ok=True)
    
    # High-quality project
    high_quality = base_dir / "high_quality"
    high_quality.mkdir(exist_ok=True)
    (high_quality / "quality_code.py").write_text('''
"""High-quality code example."""

from typing import List, Optional


class DataProcessor:
    """Processes data with high quality standards."""
    
    def __init__(self, data: List[str]) -> None:
        """Initialize processor with data.
        
        Args:
            data: List of strings to process
        """
        self.data = data
    
    def process(self) -> Optional[List[str]]:
        """Process the data.
        
        Returns:
            Processed data or None if empty
        """
        if not self.data:
            return None
        
        return [item.strip().lower() for item in self.data if item.strip()]
    
    def get_stats(self) -> dict:
        """Get processing statistics.
        
        Returns:
            Dictionary with statistics
        """
        processed = self.process()
        if not processed:
            return {"count": 0, "average_length": 0}
        
        return {
            "count": len(processed),
            "average_length": sum(len(item) for item in processed) / len(processed)
        }
''')
    projects.append(high_quality)
    
    # Medium-quality project
    medium_quality = base_dir / "medium_quality"
    medium_quality.mkdir(exist_ok=True)
    (medium_quality / "medium_code.py").write_text('''
# Medium quality code
import json

def process_data(data):
    if data:
        result = []
        for item in data:
            if item:
                result.append(item.strip())
        return result
    return None

def get_stats(data):
    processed = process_data(data)
    if processed:
        return {"count": len(processed)}
    return {"count": 0}
''')
    projects.append(medium_quality)
    
    # Low-quality project
    low_quality = base_dir / "low_quality"
    low_quality.mkdir(exist_ok=True)
    (low_quality / "poor_code.py").write_text('''
import os,sys,json,re,time
import unused

def badFunction(a,b,c,d,e,f,g):
    global x
    if a==b:
        if c==d:
            if e==f:
                return x+a+b+c+d+e+f+g
            else:
                return x
        else:
            return a
    else:
        return 0

x="global variable"

def anotherBadFunction():
    pass

# Very long line that definitely exceeds any reasonable line length limit and should be broken up into multiple lines
y = "This is an extremely long string that goes on and on and definitely exceeds the line length limit"
''')
    projects.append(low_quality)
    
    return projects


async def cleanup_sample_projects(projects: List[Path]):
    """Clean up sample projects."""
    import shutil
    
    for project in projects:
        if project.exists():
            # Remove the parent directory (batch_demo_projects, etc.)
            parent = project.parent
            if parent.exists() and parent.name.endswith("_projects"):
                shutil.rmtree(parent)
                break


async def main():
    """Run batch processing demonstrations."""
    print("🚀 Batch Processing Demonstration")
    print("=" * 60)
    
    try:
        # Run demonstrations
        await demo_batch_processing()
        await demo_selective_batch_processing()
        await demo_project_comparison()
        
        print(f"\n✅ Batch processing demo completed!")
        print("\nKey features demonstrated:")
        print("  - Concurrent processing of multiple projects")
        print("  - Project-specific configuration handling")
        print("  - Batch result aggregation and reporting")
        print("  - Different processing strategies")
        print("  - Project comparison and ranking")
        print("  - Error handling and recovery")
        
        print(f"\nGenerated reports:")
        print("  - batch_processing_report.json")
        print("  - batch_quick_scan_report.json")
        print("  - batch_comprehensive_report.json")
        print("  - batch_security_focused_report.json")
        
    except Exception as e:
        print(f"❌ Batch processing demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted by user")
        sys.exit(1)