# Codebase Checkup API Documentation

## Overview

The codebase checkup system provides a comprehensive Python API for programmatic access to code analysis and cleanup functionality. This API allows you to integrate checkup capabilities into your own tools, scripts, and applications.

## Installation

```bash
pip install migration-assistant[checkup]
```

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Classes](#core-classes)
3. [Configuration](#configuration)
4. [Data Models](#data-models)
5. [Analyzer Classes](#analyzer-classes)
6. [Cleaner Classes](#cleaner-classes)
7. [Report Generators](#report-generators)
8. [Utility Functions](#utility-functions)
9. [Error Handling](#error-handling)
10. [Advanced Usage](#advanced-usage)
11. [REST API](#rest-api)
12. [WebSocket API](#websocket-api)
13. [CLI Integration](#cli-integration)
14. [Examples](#examples)

## Quick Start

```python
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig

# Create configuration
config = CheckupConfig(
    enable_quality_analysis=True,
    enable_duplicate_detection=True,
    auto_format=False,
    create_backup=True
)

# Initialize orchestrator
orchestrator = CodebaseOrchestrator(config)

# Run analysis
results = await orchestrator.run_analysis_only()

# Generate reports
reports = await orchestrator.generate_reports(results)
```

## Core Classes

### CodebaseOrchestrator

The main orchestration class that coordinates all checkup operations.

```python
class CodebaseOrchestrator:
    def __init__(self, config: CheckupConfig, path: Optional[Path] = None)
    
    async def run_full_checkup(self) -> CheckupResults
    async def run_analysis_only(self) -> AnalysisResults
    async def run_cleanup_only(self, analysis_results: AnalysisResults) -> CleanupResults
    async def generate_reports(self, results: CheckupResults) -> ReportResults
    async def create_backup(self) -> BackupInfo
    async def rollback(self, backup_id: Optional[str] = None) -> RollbackResult
```

#### Methods

##### `__init__(config: CheckupConfig, path: Optional[Path] = None)`

Initialize the orchestrator with configuration and optional path.

**Parameters:**
- `config`: CheckupConfig instance with analysis and cleanup settings
- `path`: Optional path to analyze (defaults to current directory)

**Example:**
```python
from pathlib import Path
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig

config = CheckupConfig(enable_quality_analysis=True)
orchestrator = CodebaseOrchestrator(config, Path("/path/to/project"))
```

##### `async run_full_checkup() -> CheckupResults`

Run complete checkup including analysis, cleanup (if enabled), and reporting.

**Returns:** `CheckupResults` object containing all results

**Example:**
```python
results = await orchestrator.run_full_checkup()
print(f"Found {len(results.analysis.quality_issues)} quality issues")
print(f"Applied {len(results.cleanup.fixes_applied)} fixes")
```

##### `async run_analysis_only() -> AnalysisResults`

Run analysis without applying any changes.

**Returns:** `AnalysisResults` object containing analysis findings

**Example:**
```python
analysis = await orchestrator.run_analysis_only()
for issue in analysis.quality_issues:
    print(f"{issue.file}: {issue.message}")
```

##### `async run_cleanup_only(analysis_results: AnalysisResults) -> CleanupResults`

Apply cleanup operations based on analysis results.

**Parameters:**
- `analysis_results`: Results from previous analysis

**Returns:** `CleanupResults` object containing cleanup actions

**Example:**
```python
analysis = await orchestrator.run_analysis_only()
cleanup = await orchestrator.run_cleanup_only(analysis)
print(f"Formatted {len(cleanup.formatting_changes)} files")
```

##### `async generate_reports(results: CheckupResults) -> ReportResults`

Generate reports from checkup results.

**Parameters:**
- `results`: CheckupResults from full checkup

**Returns:** `ReportResults` object with report file paths

**Example:**
```python
results = await orchestrator.run_full_checkup()
reports = await orchestrator.generate_reports(results)
print(f"HTML report: {reports.html_report_path}")
```

### CheckupConfig

Configuration class for customizing checkup behavior.

```python
@dataclass
class CheckupConfig:
    # Analysis settings
    enable_quality_analysis: bool = True
    enable_duplicate_detection: bool = True
    enable_import_analysis: bool = True
    enable_structure_analysis: bool = True
    enable_coverage_analysis: bool = True
    enable_config_validation: bool = True
    enable_doc_validation: bool = True
    
    # Cleanup settings
    auto_format: bool = False
    auto_fix_imports: bool = False
    auto_organize_files: bool = False
    auto_fix_quality: bool = False
    
    # Reporting settings
    generate_html_report: bool = True
    generate_json_report: bool = True
    generate_markdown_report: bool = True
    output_directory: str = "reports"
    
    # Safety settings
    create_backup: bool = True
    dry_run: bool = False
    max_file_moves: int = 10
    require_confirmation: bool = False
    
    # Performance settings
    parallel_analysis: bool = True
    max_workers: int = 4
    timeout: int = 300
    
    # File filtering
    include_patterns: List[str] = field(default_factory=lambda: ["*.py"])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "venv/*", "__pycache__/*", "*.pyc", ".git/*"
    ])
    max_file_size: int = 1048576  # 1MB
```

#### Class Methods

##### `from_file(path: Path) -> CheckupConfig`

Load configuration from TOML file.

**Parameters:**
- `path`: Path to configuration file

**Returns:** CheckupConfig instance

**Example:**
```python
config = CheckupConfig.from_file(Path("checkup.toml"))
```

##### `from_dict(data: Dict[str, Any]) -> CheckupConfig`

Create configuration from dictionary.

**Parameters:**
- `data`: Configuration dictionary

**Returns:** CheckupConfig instance

**Example:**
```python
config_data = {
    "enable_quality_analysis": True,
    "auto_format": True,
    "create_backup": True
}
config = CheckupConfig.from_dict(config_data)
```

##### `to_dict() -> Dict[str, Any]`

Convert configuration to dictionary.

**Returns:** Configuration as dictionary

**Example:**
```python
config = CheckupConfig()
config_dict = config.to_dict()
```

##### `validate() -> List[str]`

Validate configuration and return list of errors.

**Returns:** List of validation error messages

**Example:**
```python
config = CheckupConfig(max_workers=-1)  # Invalid
errors = config.validate()
if errors:
    print("Configuration errors:", errors)
```

## Data Models

### AnalysisResults

Contains results from code analysis.

```python
@dataclass
class AnalysisResults:
    quality_issues: List[QualityIssue]
    duplicates: List[Duplicate]
    import_issues: List[ImportIssue]
    structure_issues: List[StructureIssue]
    coverage_gaps: List[CoverageGap]
    config_issues: List[ConfigIssue]
    doc_issues: List[DocIssue]
    metrics: CodebaseMetrics
    timestamp: datetime
    duration: timedelta
    success: bool
    errors: List[str]
```

#### Properties

##### `total_issues: int`
Total number of issues found across all categories.

##### `severity_counts: Dict[str, int]`
Count of issues by severity level.

##### `files_analyzed: int`
Number of files analyzed.

#### Methods

##### `get_issues_by_file(file_path: Path) -> List[Issue]`
Get all issues for a specific file.

##### `get_issues_by_severity(severity: str) -> List[Issue]`
Get all issues of a specific severity.

##### `to_dict() -> Dict[str, Any]`
Convert results to dictionary for serialization.

**Example:**
```python
analysis = await orchestrator.run_analysis_only()
print(f"Total issues: {analysis.total_issues}")
print(f"Files analyzed: {analysis.files_analyzed}")

# Get high-severity issues
critical_issues = analysis.get_issues_by_severity("critical")
for issue in critical_issues:
    print(f"Critical: {issue.file}: {issue.message}")
```

### CleanupResults

Contains results from cleanup operations.

```python
@dataclass
class CleanupResults:
    formatting_changes: List[FormattingChange]
    import_cleanups: List[ImportCleanup]
    file_moves: List[FileMove]
    removals: List[FileRemoval]
    fixes_applied: List[AutoFix]
    backup_info: Optional[BackupInfo]
    timestamp: datetime
    duration: timedelta
    success: bool
    errors: List[str]
```

#### Properties

##### `total_changes: int`
Total number of changes made.

##### `files_modified: int`
Number of files modified.

#### Methods

##### `get_changes_by_file(file_path: Path) -> List[Change]`
Get all changes for a specific file.

##### `to_dict() -> Dict[str, Any]`
Convert results to dictionary.

**Example:**
```python
cleanup = await orchestrator.run_cleanup_only(analysis)
print(f"Total changes: {cleanup.total_changes}")
print(f"Files modified: {cleanup.files_modified}")

if cleanup.backup_info:
    print(f"Backup created: {cleanup.backup_info.path}")
```

### CheckupResults

Combined results from full checkup.

```python
@dataclass
class CheckupResults:
    analysis: AnalysisResults
    cleanup: Optional[CleanupResults]
    before_metrics: CodebaseMetrics
    after_metrics: Optional[CodebaseMetrics]
    duration: timedelta
    success: bool
```

#### Properties

##### `improvement_metrics: Dict[str, float]`
Metrics showing improvement from cleanup.

#### Methods

##### `get_summary() -> CheckupSummary`
Get summary of checkup results.

**Example:**
```python
results = await orchestrator.run_full_checkup()
summary = results.get_summary()
print(f"Issues found: {summary.issues_found}")
print(f"Issues fixed: {summary.issues_fixed}")
print(f"Quality improvement: {summary.quality_improvement:.1%}")
```

## Issue Types

### QualityIssue

Represents a code quality issue.

```python
@dataclass
class QualityIssue:
    file: Path
    line: int
    column: int
    message: str
    rule: str
    severity: str  # "error", "warning", "info"
    category: str  # "syntax", "style", "complexity", "smell"
    suggestion: Optional[str] = None
    auto_fixable: bool = False
```

**Example:**
```python
for issue in analysis.quality_issues:
    if issue.auto_fixable:
        print(f"Auto-fixable: {issue.file}:{issue.line} - {issue.message}")
```

### Duplicate

Represents duplicate code.

```python
@dataclass
class Duplicate:
    files: List[Path]
    lines: List[Tuple[int, int]]  # (start, end) for each file
    similarity: float
    tokens: int
    suggestion: Optional[str] = None
    confidence: float = 0.0
```

**Example:**
```python
for duplicate in analysis.duplicates:
    if duplicate.confidence > 0.8:
        print(f"High-confidence duplicate ({duplicate.similarity:.1%}):")
        for file, (start, end) in zip(duplicate.files, duplicate.lines):
            print(f"  {file}:{start}-{end}")
```

### ImportIssue

Represents import-related issues.

```python
@dataclass
class ImportIssue:
    file: Path
    line: int
    import_name: str
    issue_type: str  # "unused", "circular", "missing", "orphaned"
    message: str
    suggestion: Optional[str] = None
    auto_fixable: bool = False
```

## Analyzer Classes

### CodeQualityAnalyzer

Analyzes code quality issues.

```python
class CodeQualityAnalyzer:
    def __init__(self, config: QualityConfig)
    
    async def analyze(self, files: List[Path]) -> List[QualityIssue]
    async def analyze_file(self, file: Path) -> List[QualityIssue]
    async def check_syntax(self, file: Path) -> List[QualityIssue]
    async def check_style(self, file: Path) -> List[QualityIssue]
    async def check_complexity(self, file: Path) -> List[QualityIssue]
```

**Example:**
```python
from migration_assistant.checkup.analyzers import CodeQualityAnalyzer

analyzer = CodeQualityAnalyzer(config.quality)
issues = await analyzer.analyze([Path("src/main.py")])
```

### DuplicateCodeDetector

Detects duplicate code blocks.

```python
class DuplicateCodeDetector:
    def __init__(self, config: DuplicateConfig)
    
    async def find_duplicates(self, files: List[Path]) -> List[Duplicate]
    async def find_exact_duplicates(self, files: List[Path]) -> List[Duplicate]
    async def find_similar_blocks(self, files: List[Path]) -> List[Duplicate]
    def suggest_refactoring(self, duplicates: List[Duplicate]) -> List[str]
```

**Example:**
```python
from migration_assistant.checkup.analyzers import DuplicateCodeDetector

detector = DuplicateCodeDetector(config.duplicates)
duplicates = await detector.find_duplicates(python_files)
suggestions = detector.suggest_refactoring(duplicates)
```

## Cleaner Classes

### CodeFormatter

Formats code using black and isort.

```python
class CodeFormatter:
    def __init__(self, config: FormattingConfig)
    
    async def format_files(self, files: List[Path]) -> List[FormattingChange]
    async def format_with_black(self, files: List[Path]) -> List[FormattingChange]
    async def organize_imports(self, files: List[Path]) -> List[FormattingChange]
    async def standardize_docstrings(self, files: List[Path]) -> List[FormattingChange]
```

**Example:**
```python
from migration_assistant.checkup.cleaners import CodeFormatter

formatter = CodeFormatter(config.formatting)
changes = await formatter.format_files([Path("src/main.py")])
```

### ImportCleaner

Cleans up import statements.

```python
class ImportCleaner:
    def __init__(self, config: ImportConfig)
    
    async def clean_imports(self, files: List[Path]) -> List[ImportCleanup]
    async def remove_unused_imports(self, files: List[Path]) -> List[ImportCleanup]
    async def optimize_import_order(self, files: List[Path]) -> List[ImportCleanup]
```

## Report Generators

### HTMLReportGenerator

Generates interactive HTML reports.

```python
class HTMLReportGenerator:
    def __init__(self, config: ReportConfig)
    
    async def generate_report(self, results: CheckupResults) -> Path
    async def generate_summary_report(self, results: AnalysisResults) -> Path
    async def generate_comparison_report(self, before: AnalysisResults, after: AnalysisResults) -> Path
```

**Example:**
```python
from migration_assistant.checkup.reporters import HTMLReportGenerator

generator = HTMLReportGenerator(config.reporting)
report_path = await generator.generate_report(results)
print(f"HTML report generated: {report_path}")
```

### JSONReportGenerator

Generates JSON reports for programmatic access.

```python
class JSONReportGenerator:
    def __init__(self, config: ReportConfig)
    
    async def generate_report(self, results: CheckupResults) -> Path
    def serialize_results(self, results: CheckupResults) -> Dict[str, Any]
```

**Example:**
```python
from migration_assistant.checkup.reporters import JSONReportGenerator
import json

generator = JSONReportGenerator(config.reporting)
report_path = await generator.generate_report(results)

# Load and process JSON report
with open(report_path) as f:
    report_data = json.load(f)
    
print(f"Quality score: {report_data['metrics']['quality_score']}")
```

## Utility Functions

### Configuration Helpers

```python
from migration_assistant.checkup.utils import (
    load_config_from_file,
    validate_config,
    merge_configs,
    get_default_config
)

# Load configuration
config = load_config_from_file("checkup.toml")

# Validate configuration
errors = validate_config(config)

# Merge configurations
merged = merge_configs(default_config, user_config)

# Get default configuration
default = get_default_config()
```

### File Utilities

```python
from migration_assistant.checkup.utils import (
    find_python_files,
    filter_files,
    get_file_metrics,
    create_backup
)

# Find Python files
python_files = find_python_files(Path("src"))

# Filter files by patterns
filtered = filter_files(python_files, include=["*.py"], exclude=["test_*.py"])

# Get file metrics
metrics = get_file_metrics(Path("main.py"))

# Create backup
backup_info = create_backup(Path("src"), Path("backups"))
```

## Error Handling

### Exception Hierarchy

```python
class CheckupError(Exception):
    """Base exception for checkup operations"""

class AnalysisError(CheckupError):
    """Errors during code analysis"""

class CleanupError(CheckupError):
    """Errors during cleanup operations"""

class ValidationError(CheckupError):
    """Errors during validation"""

class ReportGenerationError(CheckupError):
    """Errors during report generation"""

class ConfigurationError(CheckupError):
    """Configuration-related errors"""
```

### Error Handling Example

```python
from migration_assistant.checkup import CheckupError, AnalysisError

try:
    results = await orchestrator.run_full_checkup()
except AnalysisError as e:
    print(f"Analysis failed: {e}")
    # Handle analysis-specific error
except CheckupError as e:
    print(f"Checkup error: {e}")
    # Handle general checkup error
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle unexpected errors
```

## Advanced Usage

### Custom Analyzers

Create custom analyzers by extending the base analyzer class:

```python
from migration_assistant.checkup.analyzers.base import BaseAnalyzer

class CustomAnalyzer(BaseAnalyzer):
    async def analyze(self, files: List[Path]) -> List[Issue]:
        issues = []
        for file in files:
            # Custom analysis logic
            custom_issues = await self.analyze_file(file)
            issues.extend(custom_issues)
        return issues
    
    async def analyze_file(self, file: Path) -> List[Issue]:
        # Implement custom file analysis
        pass

# Use custom analyzer
analyzer = CustomAnalyzer(config)
orchestrator.add_analyzer(analyzer)
```

### Custom Cleaners

Create custom cleaners:

```python
from migration_assistant.checkup.cleaners.base import BaseCleaner

class CustomCleaner(BaseCleaner):
    async def clean(self, files: List[Path], issues: List[Issue]) -> List[Change]:
        changes = []
        for file in files:
            # Custom cleanup logic
            file_changes = await self.clean_file(file, issues)
            changes.extend(file_changes)
        return changes
    
    async def clean_file(self, file: Path, issues: List[Issue]) -> List[Change]:
        # Implement custom file cleanup
        pass

# Use custom cleaner
cleaner = CustomCleaner(config)
orchestrator.add_cleaner(cleaner)
```

### Batch Processing

Process multiple projects:

```python
async def process_projects(project_paths: List[Path]):
    results = []
    
    for project_path in project_paths:
        config = CheckupConfig.from_file(project_path / "checkup.toml")
        orchestrator = CodebaseOrchestrator(config, project_path)
        
        try:
            result = await orchestrator.run_full_checkup()
            results.append((project_path, result))
        except CheckupError as e:
            print(f"Failed to process {project_path}: {e}")
    
    return results

# Process multiple projects
projects = [Path("project1"), Path("project2"), Path("project3")]
results = await process_projects(projects)
```

### Integration with CI/CD

```python
import sys
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig

async def ci_checkup():
    config = CheckupConfig(
        enable_quality_analysis=True,
        generate_json_report=True,
        require_confirmation=False,
        create_backup=False
    )
    
    orchestrator = CodebaseOrchestrator(config)
    results = await orchestrator.run_analysis_only()
    
    # Fail CI if critical issues found
    critical_issues = results.get_issues_by_severity("critical")
    if critical_issues:
        print(f"Found {len(critical_issues)} critical issues")
        sys.exit(1)
    
    # Generate report for artifacts
    reports = await orchestrator.generate_reports(results)
    print(f"Report generated: {reports.json_report_path}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(ci_checkup())
```

## Performance Considerations

### Memory Usage

For large codebases, consider:

```python
config = CheckupConfig(
    max_workers=2,  # Reduce parallel processing
    max_file_size=524288,  # 512KB limit
    enable_duplicate_detection=False,  # Most memory-intensive
    exclude_patterns=[
        "venv/*",
        "node_modules/*",
        "*.log",
        "data/*"
    ]
)
```

### Incremental Analysis

Analyze only changed files:

```python
from migration_assistant.checkup.utils import get_changed_files

# Get files changed since last commit
changed_files = get_changed_files()

# Analyze only changed files
config = CheckupConfig()
orchestrator = CodebaseOrchestrator(config)
results = await orchestrator.analyze_files(changed_files)
```

## REST API

The checkup system provides a REST API for remote access and integration with web applications.

### Starting the API Server

```bash
# Start the API server
migration-assistant api start --port 8000

# Start with custom configuration
migration-assistant api start --port 8000 --config checkup.toml
```

### Authentication

```python
# API uses token-based authentication
headers = {
    'Authorization': 'Bearer your-api-token',
    'Content-Type': 'application/json'
}
```

### Endpoints

#### POST /api/v1/checkup/analyze

Analyze a codebase without making changes.

**Request:**
```json
{
  "path": "/path/to/project",
  "config": {
    "enable_quality_analysis": true,
    "enable_duplicate_detection": true,
    "generate_html_report": true
  },
  "include_patterns": ["*.py"],
  "exclude_patterns": ["venv/*", "__pycache__/*"]
}
```

**Response:**
```json
{
  "analysis_id": "analysis-123456",
  "status": "completed",
  "results": {
    "total_files": 45,
    "quality_issues": 12,
    "duplicates": 3,
    "import_issues": 5
  },
  "reports": {
    "html_report": "/reports/analysis-123456.html",
    "json_report": "/reports/analysis-123456.json"
  },
  "duration": 15.2,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### POST /api/v1/checkup/run

Run analysis and apply fixes.

**Request:**
```json
{
  "path": "/path/to/project",
  "config": {
    "auto_format": true,
    "auto_fix_imports": true,
    "create_backup": true
  },
  "dry_run": false
}
```

**Response:**
```json
{
  "checkup_id": "checkup-789012",
  "status": "completed",
  "analysis": {
    "issues_found": 25,
    "files_analyzed": 45
  },
  "cleanup": {
    "issues_fixed": 21,
    "files_modified": 12,
    "backup_id": "backup-20240115-103000"
  },
  "improvement_metrics": {
    "quality_improvement": 0.84,
    "issues_resolved": 0.84
  }
}
```

#### GET /api/v1/checkup/status/{checkup_id}

Get status of a running checkup.

**Response:**
```json
{
  "checkup_id": "checkup-789012",
  "status": "running",
  "progress": 0.65,
  "current_phase": "cleanup",
  "message": "Applying code formatting...",
  "estimated_remaining": 45
}
```

#### POST /api/v1/checkup/rollback

Rollback previous changes.

**Request:**
```json
{
  "backup_id": "backup-20240115-103000",
  "path": "/path/to/project"
}
```

#### GET /api/v1/checkup/reports/{report_id}

Download generated reports.

**Response:** Binary report file (HTML, JSON, or Markdown)

#### GET /api/v1/checkup/config/validate

Validate checkup configuration.

**Request:**
```json
{
  "config": {
    "enable_quality_analysis": true,
    "max_complexity": 10,
    "auto_format": true
  }
}
```

**Response:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Consider enabling duplicate detection for comprehensive analysis"
  ]
}
```

### Error Responses

```json
{
  "error": {
    "code": "ANALYSIS_FAILED",
    "message": "Analysis failed due to syntax errors",
    "details": {
      "file": "src/main.py",
      "line": 45,
      "error": "SyntaxError: invalid syntax"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## WebSocket API

Real-time updates during checkup operations.

### Connection

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/checkup');

// Authentication
ws.send(JSON.stringify({
  type: 'auth',
  token: 'your-api-token'
}));
```

### Starting a Checkup

```javascript
// Start checkup with real-time updates
ws.send(JSON.stringify({
  type: 'start_checkup',
  data: {
    path: '/path/to/project',
    config: {
      enable_quality_analysis: true,
      auto_format: true
    }
  }
}));
```

### Receiving Updates

```javascript
ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'progress':
      console.log(`Progress: ${message.data.progress}%`);
      console.log(`Phase: ${message.data.phase}`);
      console.log(`Message: ${message.data.message}`);
      break;
      
    case 'analysis_complete':
      console.log('Analysis completed:', message.data.results);
      break;
      
    case 'cleanup_complete':
      console.log('Cleanup completed:', message.data.changes);
      break;
      
    case 'error':
      console.error('Error:', message.data.error);
      break;
      
    case 'complete':
      console.log('Checkup completed:', message.data.summary);
      break;
  }
};
```

### Message Types

#### Progress Updates
```json
{
  "type": "progress",
  "data": {
    "checkup_id": "checkup-789012",
    "progress": 0.45,
    "phase": "analysis",
    "message": "Analyzing code quality...",
    "files_processed": 20,
    "total_files": 45,
    "current_file": "src/utils.py"
  }
}
```

#### Analysis Results
```json
{
  "type": "analysis_complete",
  "data": {
    "checkup_id": "checkup-789012",
    "results": {
      "quality_issues": 12,
      "duplicates": 3,
      "import_issues": 5
    },
    "duration": 8.5
  }
}
```

#### Cleanup Updates
```json
{
  "type": "cleanup_progress",
  "data": {
    "checkup_id": "checkup-789012",
    "operation": "formatting",
    "file": "src/main.py",
    "changes": 15
  }
}
```

## CLI Integration

### Programmatic CLI Usage

```python
import subprocess
import json
from pathlib import Path

def run_checkup_cli(project_path: Path, config_path: Path = None) -> dict:
    """Run checkup via CLI and return results."""
    cmd = [
        'migration-assistant', 'checkup', 'analyze',
        '--path', str(project_path),
        '--report-json',
        '--quiet'
    ]
    
    if config_path:
        cmd.extend(['--config', str(config_path)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Checkup failed: {result.stderr}")
    
    # Load JSON report
    report_path = project_path / 'reports' / 'checkup-latest.json'
    with open(report_path) as f:
        return json.load(f)

# Usage
results = run_checkup_cli(Path('/path/to/project'))
print(f"Found {len(results['quality_issues'])} quality issues")
```

### CLI Configuration

```python
def create_cli_config(output_path: Path, **options) -> Path:
    """Create CLI configuration file."""
    import toml
    
    config = {
        'checkup': {
            'enable_quality_analysis': options.get('quality', True),
            'enable_duplicate_detection': options.get('duplicates', True),
            'auto_format': options.get('format', False),
            'create_backup': options.get('backup', True)
        }
    }
    
    config_path = output_path / 'checkup-cli.toml'
    with open(config_path, 'w') as f:
        toml.dump(config, f)
    
    return config_path

# Usage
config_path = create_cli_config(
    Path('/tmp'),
    quality=True,
    duplicates=False,
    format=True
)
```

## Examples

### Complete Integration Example

```python
import asyncio
from pathlib import Path
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig

async def comprehensive_checkup_example():
    """Complete example of checkup integration."""
    
    # 1. Configure checkup
    config = CheckupConfig(
        enable_quality_analysis=True,
        enable_duplicate_detection=True,
        enable_import_analysis=True,
        auto_format=True,
        create_backup=True,
        generate_html_report=True
    )
    
    # 2. Initialize orchestrator
    project_path = Path('/path/to/project')
    orchestrator = CodebaseOrchestrator(config, project_path)
    
    try:
        # 3. Run analysis
        print("🔍 Running analysis...")
        analysis = await orchestrator.run_analysis_only()
        
        print(f"📊 Analysis Results:")
        print(f"  - Files analyzed: {analysis.files_analyzed}")
        print(f"  - Quality issues: {len(analysis.quality_issues)}")
        print(f"  - Duplicates: {len(analysis.duplicates)}")
        print(f"  - Import issues: {len(analysis.import_issues)}")
        
        # 4. Apply fixes if issues found
        if analysis.total_issues > 0:
            print("🛠️  Applying fixes...")
            cleanup = await orchestrator.run_cleanup_only(analysis)
            
            print(f"✅ Cleanup Results:")
            print(f"  - Files modified: {cleanup.files_modified}")
            print(f"  - Changes applied: {cleanup.total_changes}")
            
            if cleanup.backup_info:
                print(f"  - Backup created: {cleanup.backup_info.path}")
        
        # 5. Generate reports
        print("📋 Generating reports...")
        full_results = CheckupResults(
            analysis=analysis,
            cleanup=cleanup if analysis.total_issues > 0 else None,
            before_metrics=analysis.metrics,
            after_metrics=None,  # Would be calculated after cleanup
            duration=analysis.duration,
            success=True
        )
        
        reports = await orchestrator.generate_reports(full_results)
        print(f"📄 Reports generated:")
        if reports.html_report_path:
            print(f"  - HTML: {reports.html_report_path}")
        if reports.json_report_path:
            print(f"  - JSON: {reports.json_report_path}")
        
        return full_results
        
    except Exception as e:
        print(f"❌ Checkup failed: {e}")
        raise

# Run the example
if __name__ == "__main__":
    results = asyncio.run(comprehensive_checkup_example())
```

### Custom Analyzer Example

```python
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import Issue
from pathlib import Path
from typing import List
import ast

class CustomSecurityAnalyzer(BaseAnalyzer):
    """Custom analyzer for security issues."""
    
    def __init__(self, config):
        super().__init__(config)
        self.security_patterns = [
            'eval(',
            'exec(',
            'os.system(',
            'subprocess.call(',
            'input(',  # Python 2 input is dangerous
        ]
    
    async def analyze(self, files: List[Path]) -> List[Issue]:
        """Analyze files for security issues."""
        issues = []
        
        for file_path in files:
            if file_path.suffix != '.py':
                continue
                
            try:
                file_issues = await self.analyze_file(file_path)
                issues.extend(file_issues)
            except Exception as e:
                self.logger.warning(f"Failed to analyze {file_path}: {e}")
        
        return issues
    
    async def analyze_file(self, file_path: Path) -> List[Issue]:
        """Analyze a single file for security issues."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for dangerous patterns
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                for pattern in self.security_patterns:
                    if pattern in line:
                        issues.append(Issue(
                            file=file_path,
                            line=line_num,
                            column=line.find(pattern) + 1,
                            message=f"Potentially dangerous function: {pattern.rstrip('(')}",
                            rule="security-dangerous-function",
                            severity="warning",
                            category="security",
                            suggestion=f"Consider safer alternatives to {pattern.rstrip('(')}",
                            auto_fixable=False
                        ))
            
            # AST-based analysis for more complex patterns
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if (isinstance(node.func, ast.Name) and 
                            node.func.id in ['eval', 'exec']):
                            issues.append(Issue(
                                file=file_path,
                                line=node.lineno,
                                column=node.col_offset + 1,
                                message=f"Dangerous function call: {node.func.id}",
                                rule="security-eval-exec",
                                severity="error",
                                category="security",
                                suggestion="Use safer alternatives like ast.literal_eval",
                                auto_fixable=False
                            ))
            except SyntaxError:
                # Skip files with syntax errors
                pass
                
        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {e}")
        
        return issues

# Usage example
async def use_custom_analyzer():
    from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig
    
    config = CheckupConfig()
    orchestrator = CodebaseOrchestrator(config)
    
    # Add custom analyzer
    security_analyzer = CustomSecurityAnalyzer(config)
    orchestrator.add_analyzer(security_analyzer)
    
    # Run analysis
    results = await orchestrator.run_analysis_only()
    
    # Filter security issues
    security_issues = [
        issue for issue in results.quality_issues 
        if issue.category == "security"
    ]
    
    print(f"Found {len(security_issues)} security issues")
    for issue in security_issues:
        print(f"  {issue.file}:{issue.line} - {issue.message}")

# Run custom analyzer example
asyncio.run(use_custom_analyzer())
```

### Batch Processing Example

```python
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig

async def batch_process_projects(
    project_paths: List[Path],
    config: CheckupConfig
) -> Dict[Path, Any]:
    """Process multiple projects in batch."""
    
    results = {}
    
    # Process projects concurrently
    semaphore = asyncio.Semaphore(3)  # Limit concurrent processing
    
    async def process_project(project_path: Path):
        async with semaphore:
            try:
                print(f"🔍 Processing {project_path.name}...")
                
                orchestrator = CodebaseOrchestrator(config, project_path)
                result = await orchestrator.run_full_checkup()
                
                results[project_path] = {
                    'success': True,
                    'results': result,
                    'summary': {
                        'files_analyzed': result.analysis.files_analyzed,
                        'issues_found': result.analysis.total_issues,
                        'issues_fixed': (
                            result.cleanup.total_changes 
                            if result.cleanup else 0
                        ),
                        'quality_improvement': (
                            result.improvement_metrics.get('quality_improvement', 0)
                            if hasattr(result, 'improvement_metrics') else 0
                        )
                    }
                }
                
                print(f"✅ Completed {project_path.name}")
                
            except Exception as e:
                print(f"❌ Failed {project_path.name}: {e}")
                results[project_path] = {
                    'success': False,
                    'error': str(e)
                }
    
    # Run all projects
    tasks = [process_project(path) for path in project_paths]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    return results

async def generate_batch_report(results: Dict[Path, Any]):
    """Generate summary report for batch processing."""
    
    successful = [r for r in results.values() if r.get('success')]
    failed = [r for r in results.values() if not r.get('success')]
    
    print(f"\n📊 Batch Processing Summary:")
    print(f"  - Projects processed: {len(results)}")
    print(f"  - Successful: {len(successful)}")
    print(f"  - Failed: {len(failed)}")
    
    if successful:
        total_files = sum(r['summary']['files_analyzed'] for r in successful)
        total_issues = sum(r['summary']['issues_found'] for r in successful)
        total_fixed = sum(r['summary']['issues_fixed'] for r in successful)
        
        print(f"  - Total files analyzed: {total_files}")
        print(f"  - Total issues found: {total_issues}")
        print(f"  - Total issues fixed: {total_fixed}")
        print(f"  - Fix rate: {total_fixed/total_issues*100:.1f}%" if total_issues > 0 else "  - Fix rate: N/A")
    
    if failed:
        print(f"\n❌ Failed Projects:")
        for path, result in results.items():
            if not result.get('success'):
                print(f"  - {path.name}: {result.get('error', 'Unknown error')}")

# Usage
async def main():
    projects = [
        Path('/path/to/project1'),
        Path('/path/to/project2'),
        Path('/path/to/project3'),
    ]
    
    config = CheckupConfig(
        enable_quality_analysis=True,
        auto_format=True,
        create_backup=True,
        generate_json_report=True
    )
    
    results = await batch_process_projects(projects, config)
    await generate_batch_report(results)

if __name__ == "__main__":
    asyncio.run(main())
```

This comprehensive API documentation provides developers with all the tools and examples needed to integrate the codebase checkup system into their own applications and workflows.