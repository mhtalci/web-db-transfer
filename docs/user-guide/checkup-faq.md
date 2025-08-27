# Codebase Checkup FAQ

## Overview

This FAQ addresses common questions about the codebase checkup and cleanup system. Questions are organized by category for easy navigation.

## General Questions

### Q: What is the codebase checkup system?

**A:** The codebase checkup system is a comprehensive code analysis and cleanup tool that automatically identifies issues in Python codebases and can apply fixes. It combines multiple analysis tools (black, isort, flake8, mypy) with custom analyzers to provide detailed insights into code quality, structure, and maintainability.

### Q: How does it differ from running black, isort, and flake8 separately?

**A:** While you could run these tools individually, the checkup system provides:

- **Unified Configuration**: Single configuration file for all tools
- **Coordinated Analysis**: Tools work together with shared context
- **Custom Analysis**: Additional analyzers for duplicates, imports, structure
- **Safety Features**: Automatic backups, rollback capabilities, dry-run mode
- **Comprehensive Reporting**: Unified reports across all analysis types
- **Workflow Integration**: Built-in CI/CD and IDE integration support

### Q: Is it safe to use on production code?

**A:** Yes, with proper precautions:

- **Always use `--dry-run` first** to preview changes
- **Enable backups** with `--backup` or `create_backup = true`
- **Start with analysis-only** mode before applying fixes
- **Test thoroughly** after applying changes
- **Use version control** to track changes
- **Configure rollback** procedures for critical systems

### Q: What Python versions are supported?

**A:** The checkup system supports:

- **Python 3.8+** (recommended: 3.9+)
- **Analysis targets**: Can analyze code for Python 2.7+ (with limitations)
- **Tool compatibility**: Follows the compatibility matrix of underlying tools (black, mypy, etc.)

## Installation and Setup

### Q: Why am I getting "command not found" errors?

**A:** This usually indicates an ins
tallation issue:

```bash
# Check if migration-assistant is installed
pip list | grep migration-assistant

# If not installed, install it
pip install migration-assistant[checkup]

# If installed but not in PATH, check your Python environment
which python
which pip

# For virtual environments, ensure it's activated
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

### Q: How do I install the required tools (black, isort, etc.)?

**A:** The tools are automatically installed with the checkup dependencies:

```bash
# Install with all checkup dependencies
pip install migration-assistant[checkup]

# Or install tools manually
pip install black isort flake8 mypy pytest pytest-cov

# Verify installations
black --version
isort --version
flake8 --version
mypy --version
```

### Q: Can I use my existing tool configurations?

**A:** Yes! The checkup system respects existing configurations:

- **pyproject.toml**: Tool configurations are automatically detected
- **.flake8**: Flake8 configuration is used
- **mypy.ini**: MyPy configuration is respected
- **Custom configs**: Can be specified in checkup configuration

Example integration:
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py38']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.8"
strict = true

# Checkup will use these settings automatically
[tool.checkup]
enable_quality_analysis = true
auto_format = true
```

### Q: How do I configure checkup for my team?

**A:** Create a shared configuration file:

```toml
# team-checkup.toml
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = true
auto_format = true
create_backup = true

[checkup.quality]
max_complexity = 10
max_line_length = 88
enforce_docstrings = true
check_type_hints = true

[checkup.safety]
require_confirmation = false  # For CI/CD
max_file_moves = 5
```

Commit this file to your repository and use:
```bash
migration-assistant checkup analyze --config team-checkup.toml
```

## Usage and Configuration

### Q: What's the difference between `analyze` and `run`?

**A:** 

- **`analyze`**: Only performs analysis, no changes to code
  - Safe to run anytime
  - Generates reports
  - Identifies issues and suggests fixes
  - Good for CI/CD quality gates

- **`run`**: Performs analysis AND applies fixes
  - Modifies your code
  - Should be used with caution
  - Supports dry-run mode
  - Creates backups (if configured)

```bash
# Safe analysis only
migration-assistant checkup analyze

# Preview changes without applying
migration-assistant checkup run --dry-run

# Apply changes with backup
migration-assistant checkup run --backup
```

### Q: How do I exclude certain files or directories?

**A:** Use exclude patterns in configuration or command line:

```toml
# In checkup.toml
[checkup]
exclude_patterns = [
    "venv/*",
    "__pycache__/*",
    "*.pyc",
    ".git/*",
    "migrations/*",
    "vendor/*",
    "third_party/*",
    "legacy_code/*"
]
```

Or via command line:
```bash
migration-assistant checkup analyze --exclude "venv/*" --exclude "*.pyc"
```

### Q: Can I run only specific analyzers?

**A:** Yes, you can enable/disable specific analyzers:

```bash
# Only quality analysis
migration-assistant checkup analyze --no-duplicates --no-imports --no-structure

# Only duplicate detection
migration-assistant checkup duplicates

# Only import analysis
migration-assistant checkup imports

# Custom combination
migration-assistant checkup analyze --no-duplicates --no-coverage
```

Or in configuration:
```toml
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = false
enable_import_analysis = true
enable_structure_analysis = false
enable_coverage_analysis = false
```

### Q: How do I adjust quality standards?

**A:** Configure quality thresholds in your checkup configuration:

```toml
[checkup.quality]
# Complexity settings
max_complexity = 10          # Cyclomatic complexity
max_nesting_depth = 4        # Maximum nesting levels
max_function_length = 50     # Lines per function
max_class_length = 200       # Lines per class

# Style settings
max_line_length = 88         # Line length (PEP 8: 79, Black: 88)
enforce_docstrings = true    # Require docstrings
check_type_hints = true      # Require type hints
enforce_naming_conventions = true  # PEP 8 naming

# Tool settings
use_flake8 = true
use_mypy = true
use_bandit = false           # Security scanner (can be noisy)
```

## Performance and Scalability

### Q: The analysis is very slow on my large codebase. How can I speed it up?

**A:** Several optimization strategies:

1. **Exclude unnecessary files**:
```toml
[checkup]
exclude_patterns = [
    "venv/*", "node_modules/*", "*.log", "build/*", "dist/*",
    "migrations/*", "vendor/*", "third_party/*"
]
max_file_size = 1048576  # 1MB limit
```

2. **Disable expensive analyzers**:
```toml
[checkup]
enable_duplicate_detection = false  # Most expensive
enable_structure_analysis = false   # Can be slow
```

3. **Optimize parallel processing**:
```toml
[checkup]
parallel_analysis = true
max_workers = 4  # Adjust based on your system
timeout = 300    # 5 minutes
```

4. **Progressive analysis**:
```bash
# Analyze specific directories
migration-assistant checkup analyze --path src/
migration-assistant checkup analyze --path tests/

# Analyze changed files only
git diff --name-only | grep '\.py$' | xargs migration-assistant checkup analyze --path
```

### Q: The system runs out of memory during duplicate detection. What can I do?

**A:** Memory optimization for duplicate detection:

```toml
[checkup.duplicates]
# More restrictive settings
similarity_threshold = 0.95  # Higher threshold = fewer comparisons
min_duplicate_lines = 10     # Larger minimum = fewer candidates
min_duplicate_tokens = 100   # More tokens required

# Exclude test files (often have similar patterns)
ignore_test_files = true
exclude_patterns = ["tests/*", "test_*.py"]
```

Or disable duplicate detection for initial cleanup:
```bash
migration-assistant checkup analyze --no-duplicates
```

### Q: How can I process multiple projects efficiently?

**A:** Use batch processing approaches:

```bash
# Simple batch script
for project in project1 project2 project3; do
    echo "Processing $project..."
    cd "$project"
    migration-assistant checkup analyze --quiet --report-json
    cd ..
done

# Parallel processing with GNU parallel
find . -name "*.py" -path "*/src/*" | parallel -j4 migration-assistant checkup analyze --path {}

# Python script for advanced batch processing
python scripts/batch_checkup.py --projects projects.txt --config team-checkup.toml
```

## Error Handling and Troubleshooting

### Q: I'm getting syntax errors during analysis. What should I do?

**A:** Syntax errors prevent analysis. Here's how to handle them:

1. **Identify syntax errors**:
```bash
# Check syntax manually
python -m py_compile problematic_file.py

# Run checkup with verbose output
migration-assistant checkup analyze --verbose
```

2. **Fix syntax errors first**:
```bash
# Use a Python linter to identify issues
flake8 --select=E9 .  # Only syntax errors

# Fix syntax errors before running checkup
```

3. **Exclude problematic files temporarily**:
```toml
[checkup]
exclude_patterns = [
    "broken_file.py",
    "legacy/*"  # Exclude entire legacy directory
]
```

### Q: The tool reports false positives. How can I handle them?

**A:** Several strategies for false positives:

1. **Adjust thresholds**:
```toml
[checkup.duplicates]
similarity_threshold = 0.95  # More strict
min_duplicate_lines = 10     # Larger blocks only

[checkup.quality]
max_complexity = 15  # More lenient for legacy code
```

2. **Use ignore comments**:
```python
# For specific lines
import unused_module  # noqa: F401
complex_function()    # noqa: C901

# For entire files
# flake8: noqa
```

3. **Configure tool-specific ignores**:
```toml
# In pyproject.toml
[tool.flake8]
ignore = ["E203", "W503"]  # Ignore specific rules
per-file-ignores = [
    "tests/*:F401,F811",   # Allow unused imports in tests
    "migrations/*:E501"    # Allow long lines in migrations
]
```

### Q: How do I rollback changes if something goes wrong?

**A:** The checkup system provides several rollback options:

1. **Automatic backups**:
```bash
# Enable backups (default)
migration-assistant checkup run --backup

# List available backups
migration-assistant checkup list-backups

# Rollback to specific backup
migration-assistant checkup rollback backup-20240115-103000
```

2. **Git-based rollback**:
```bash
# If using version control
git status  # See what changed
git diff    # Review changes
git checkout -- .  # Rollback all changes
git reset --hard HEAD  # Complete reset
```

3. **Manual rollback**:
```bash
# Copy from backup directory
cp -r .checkup-backups/backup-20240115-103000/* .
```

### Q: The HTML reports aren't generating. What's wrong?

**A:** Common HTML report issues:

1. **Check dependencies**:
```bash
# Ensure all dependencies are installed
pip install migration-assistant[checkup]

# Check for missing optional dependencies
pip install jinja2 matplotlib plotly  # For enhanced reports
```

2. **Check permissions**:
```bash
# Ensure write permissions for report directory
ls -la reports/
chmod +w reports/
```

3. **Check disk space**:
```bash
df -h  # Check available disk space
```

4. **Use alternative formats**:
```bash
# Generate JSON instead
migration-assistant checkup analyze --report-json --no-html

# Generate Markdown
migration-assistant checkup analyze --report-markdown
```

## Integration and Workflow

### Q: How do I integrate checkup with my CI/CD pipeline?

**A:** Example CI/CD configurations:

**GitHub Actions**:
```yaml
name: Code Quality
on: [push, pull_request]

jobs:
  checkup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install migration-assistant[checkup]
      - name: Run checkup
        run: |
          migration-assistant checkup analyze --report-json --quiet
          python scripts/check_quality_gate.py
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: checkup-reports
          path: reports/
```

**GitLab CI**:
```yaml
checkup:
  stage: test
  image: python:3.9
  script:
    - pip install migration-assistant[checkup]
    - migration-assistant checkup analyze --report-json --quiet
    - python scripts/check_quality_gate.py
  artifacts:
    reports:
      junit: reports/checkup-junit.xml
    paths:
      - reports/
```

### Q: Can I use checkup with pre-commit hooks?

**A:** Yes! Here's how to set it up:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: codebase-checkup
        name: Codebase Checkup
        entry: migration-assistant checkup analyze --quiet --no-report
        language: system
        pass_filenames: false
        stages: [commit]
      - id: checkup-format
        name: Auto-format Code
        entry: migration-assistant checkup run --auto-format --no-backup
        language: system
        pass_filenames: false
        stages: [commit]
```

Install and use:
```bash
pip install pre-commit
pre-commit install
git commit -m "Test commit"  # Will run checkup automatically
```

### Q: How do I integrate with VS Code?

**A:** Create VS Code tasks and settings:

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Checkup Analysis",
      "type": "shell",
      "command": "migration-assistant",
      "args": ["checkup", "analyze", "--verbose"],
      "group": "build",
      "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "shared"
      }
    },
    {
      "label": "Checkup Format",
      "type": "shell",
      "command": "migration-assistant",
      "args": ["checkup", "run", "--auto-format", "--dry-run"],
      "group": "build"
    }
  ]
}
```

```json
// .vscode/settings.json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

## Advanced Usage

### Q: Can I create custom analyzers?

**A:** Yes! Here's a simple example:

```python
from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import Issue
from pathlib import Path
from typing import List

class CustomAnalyzer(BaseAnalyzer):
    async def analyze(self, files: List[Path]) -> List[Issue]:
        issues = []
        for file_path in files:
            # Your custom analysis logic
            if self.has_custom_issue(file_path):
                issues.append(Issue(
                    file=file_path,
                    line=1,
                    column=1,
                    message="Custom issue found",
                    rule="custom-rule",
                    severity="warning",
                    category="custom"
                ))
        return issues
    
    def has_custom_issue(self, file_path: Path) -> bool:
        # Implement your custom logic
        return False

# Use the custom analyzer
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig

config = CheckupConfig()
orchestrator = CodebaseOrchestrator(config)
orchestrator.add_analyzer(CustomAnalyzer(config))
```

### Q: How do I create custom reports?

**A:** Extend the base report generator:

```python
from migration_assistant.checkup.reporters.base import ReportGenerator
from migration_assistant.checkup.models import CheckupResults

class CustomReportGenerator(ReportGenerator):
    async def generate_report(self, results: CheckupResults) -> Path:
        # Your custom report generation logic
        report_content = self.create_custom_format(results)
        
        report_path = self.output_dir / "custom-report.txt"
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        return report_path
    
    def create_custom_format(self, results: CheckupResults) -> str:
        # Format results as needed
        return f"Custom Report\nIssues: {results.analysis.total_issues}"

# Use the custom reporter
orchestrator.add_reporter(CustomReportGenerator(config.reporting))
```

### Q: Can I run checkup programmatically in my application?

**A:** Absolutely! Here's a complete example:

```python
import asyncio
from pathlib import Path
from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig

async def integrate_checkup():
    # Configure checkup
    config = CheckupConfig(
        enable_quality_analysis=True,
        auto_format=False,  # Don't modify code automatically
        generate_json_report=True
    )
    
    # Run checkup
    orchestrator = CodebaseOrchestrator(config, Path('.'))
    results = await orchestrator.run_analysis_only()
    
    # Process results in your application
    if results.total_issues > 10:
        print("Too many issues found!")
        return False
    
    # Generate reports
    reports = await orchestrator.generate_reports(results)
    
    # Use results in your application logic
    return True

# Use in your application
success = asyncio.run(integrate_checkup())
```

## Best Practices

### Q: What's the recommended workflow for using checkup?

**A:** Follow this progressive approach:

1. **Initial Assessment**:
```bash
# Start with analysis only
migration-assistant checkup analyze --verbose
```

2. **Gradual Improvement**:
```bash
# Fix formatting first (safest)
migration-assistant checkup run --auto-format --backup --dry-run
migration-assistant checkup run --auto-format --backup

# Then fix imports
migration-assistant checkup run --auto-fix-imports --backup

# Finally, address structural issues manually
```

3. **Establish Standards**:
```bash
# Create team configuration
migration-assistant checkup init-config --strict > team-checkup.toml
```

4. **Integrate into Workflow**:
```bash
# Add to CI/CD
# Set up pre-commit hooks
# Configure IDE integration
```

### Q: How often should I run checkup?

**A:** Recommended frequency:

- **Development**: Before each commit (via pre-commit hooks)
- **CI/CD**: On every push/PR
- **Comprehensive**: Weekly full analysis
- **Legacy projects**: Monthly deep analysis
- **Before releases**: Always run full checkup

### Q: What should I do about legacy code with many issues?

**A:** Use a phased approach:

1. **Use legacy configuration**:
```bash
migration-assistant checkup analyze --config examples/checkup/legacy-checkup.toml
```

2. **Focus on critical issues first**:
```bash
# Only security and syntax issues
migration-assistant checkup analyze --focus critical
```

3. **Gradual improvement**:
```bash
# Fix one module at a time
migration-assistant checkup analyze --path src/core/
migration-assistant checkup run --path src/core/ --auto-format
```

4. **Set realistic goals**:
```toml
# Relaxed standards for legacy code
[checkup.quality]
max_complexity = 20  # Higher than normal
enforce_docstrings = false
check_type_hints = false
```

This FAQ covers the most common questions and scenarios you'll encounter when using the codebase checkup system. For additional help, consult the full documentation or seek community support.