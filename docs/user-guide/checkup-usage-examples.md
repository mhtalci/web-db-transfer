# Codebase Checkup Usage Examples

## Overview

This guide provides practical examples of using the codebase checkup and cleanup system in various scenarios. Each example includes the command, expected output, and explanation of results.

## Basic Usage Examples

### Example 1: First-Time Analysis

**Scenario**: You want to analyze a new Python project for the first time.

```bash
# Navigate to your project directory
cd /path/to/your/project

# Run basic analysis
migration-assistant checkup analyze

# Expected output:
# ✓ Analyzing code quality...
# ✓ Checking imports...
# ✓ Generating reports...
# 
# Analysis Summary:
# - Files analyzed: 45
# - Quality issues: 12
# - Import issues: 3
# - Suggestions: 8
# 
# Reports generated in: ./reports/
```

**What this does**:
- Analyzes all Python files in the current directory
- Checks for code quality issues (PEP 8, complexity, etc.)
- Identifies import problems
- Generates HTML and Markdown reports

### Example 2: Analysis with Custom Configuration

**Scenario**: You want to use specific quality standards for your team.

```bash
# Create team configuration
cat > team-checkup.toml << EOF
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = true

[checkup.quality]
max_complexity = 8
max_line_length = 88
enforce_docstrings = true
check_type_hints = true

[checkup.duplicates]
similarity_threshold = 0.9
min_duplicate_lines = 5
EOF

# Run analysis with custom config
migration-assistant checkup analyze --config team-checkup.toml --verbose

# Expected output:
# ✓ Loading configuration from team-checkup.toml
# ✓ Analyzing code quality (strict mode)...
#   - Checking complexity (max: 8)
#   - Enforcing docstrings
#   - Validating type hints
# ✓ Detecting duplicate code (threshold: 90%)...
# ✓ Generating detailed reports...
# 
# Analysis Results:
# - Complexity violations: 5
# - Missing docstrings: 15
# - Missing type hints: 8
# - Duplicate blocks: 2
```

### Example 3: Dry Run Before Cleanup

**Scenario**: You want to see what changes would be made before applying them.

```bash
# Run dry run to preview changes
migration-assistant checkup run --dry-run --auto-format

# Expected output:
# 🔍 DRY RUN MODE - No changes will be made
# 
# ✓ Analysis complete
# ✓ Planning cleanup operations...
# 
# Planned Changes:
# 📝 Code Formatting:
#   - src/main.py: 15 lines would be reformatted
#   - src/utils.py: 8 lines would be reformatted
#   - tests/test_main.py: 3 lines would be reformatted
# 
# 📦 Import Cleanup:
#   - src/main.py: Remove 2 unused imports
#   - src/helpers.py: Reorganize 5 import statements
# 
# 🗂️  File Organization:
#   - No file moves recommended
# 
# Total files affected: 4
# Run without --dry-run to apply changes
```

## Advanced Usage Examples

### Example 4: Full Cleanup with Backup

**Scenario**: You want to apply all fixes with safety measures.

```bash
# Run full cleanup with backup
migration-assistant checkup run --auto-fix --backup --verbose

# Expected output:
# 🔄 Creating backup...
# ✓ Backup created: .checkup-backups/backup-20240115-103000/
# 
# 🔍 Running analysis...
# ✓ Found 25 issues across 12 files
# 
# 🛠️  Applying fixes...
# ✓ Formatted 8 files with black
# ✓ Organized imports in 6 files with isort
# ✓ Removed 4 unused imports
# ✓ Fixed 3 minor quality issues
# 
# 📊 Results:
# - Issues fixed: 21/25 (84%)
# - Files modified: 10
# - Backup available for rollback
# 
# ✓ All changes applied successfully!
# 
# To rollback: migration-assistant checkup rollback backup-20240115-103000
```

### Example 5: Analyzing Specific Components

**Scenario**: You want to analyze only certain parts of your codebase.

```bash
# Analyze only source code (exclude tests)
migration-assistant checkup analyze --path src/ --report-html

# Analyze only test files
migration-assistant checkup analyze --path tests/ --config test-checkup.toml

# Analyze specific file types
migration-assistant checkup analyze --include "*.py" --exclude "test_*.py"

# Expected output for src/ analysis:
# ✓ Analyzing src/ directory...
# ✓ Found 23 Python files
# ✓ Excluding test files
# 
# Quality Analysis:
# - Syntax errors: 0
# - Style violations: 8
# - Complexity issues: 3
# - Code smells: 2
# 
# Import Analysis:
# - Unused imports: 5
# - Circular imports: 0
# - Missing imports: 1
# 
# HTML report: reports/checkup-src-20240115-103000.html
```

### Example 6: Duplicate Code Detection

**Scenario**: You suspect there's duplicate code in your project.

```bash
# Focus on duplicate detection
migration-assistant checkup duplicates --similarity 0.8 --min-lines 5

# Expected output:
# 🔍 Scanning for duplicate code...
# ✓ Analyzed 45 files
# 
# Duplicate Code Found:
# 
# 📋 Duplicate Block 1 (Similarity: 95%)
#   Files:
#   - src/user_manager.py:45-60 (16 lines)
#   - src/admin_manager.py:78-93 (16 lines)
#   
#   Suggestion: Extract common functionality into a base class
#   Confidence: High (0.92)
# 
# 📋 Duplicate Block 2 (Similarity: 87%)
#   Files:
#   - src/validators.py:120-135 (15 lines)
#   - src/helpers.py:200-215 (15 lines)
#   
#   Suggestion: Create shared validation utility function
#   Confidence: Medium (0.75)
# 
# 💡 Refactoring Suggestions:
# 1. Create BaseManager class for user/admin management
# 2. Extract validation logic into utils.validation module
# 3. Consider using composition over inheritance
```

### Example 7: Test Coverage Analysis

**Scenario**: You want to understand your test coverage and identify gaps.

```bash
# Analyze test coverage
migration-assistant checkup coverage --min-coverage 80

# Expected output:
# 🧪 Analyzing test coverage...
# ✓ Running pytest with coverage
# ✓ Parsing coverage report
# 
# Coverage Summary:
# - Overall coverage: 76% (below target: 80%)
# - Lines covered: 1,234 / 1,623
# - Functions covered: 89% (156/175)
# - Branches covered: 68% (234/345)
# 
# Coverage Gaps:
# 
# 📁 src/database/
#   - connection.py: 45% coverage (missing: error handling)
#   - migrations.py: 0% coverage (no tests found)
# 
# 📁 src/api/
#   - auth.py: 65% coverage (missing: edge cases)
#   - validators.py: 82% coverage (good)
# 
# 💡 Test Suggestions:
# 1. Add tests for database connection error scenarios
# 2. Create comprehensive migration tests
# 3. Test authentication edge cases (invalid tokens, expired sessions)
# 4. Add integration tests for API endpoints
# 
# Recommended next steps:
# - Focus on database module (lowest coverage)
# - Add error handling tests
# - Create integration test suite
```

### Example 8: Import Analysis and Cleanup

**Scenario**: Your project has grown and imports are messy.

```bash
# Analyze and clean up imports
migration-assistant checkup imports --organize --remove-unused

# Expected output:
# 📦 Analyzing imports...
# ✓ Scanning 45 Python files
# ✓ Building dependency graph
# 
# Import Issues Found:
# 
# 🚫 Unused Imports (12 total):
#   - src/main.py: os, sys, json (3 unused)
#   - src/utils.py: datetime, re (2 unused)
#   - tests/test_api.py: mock, pytest (2 unused)
# 
# 🔄 Circular Dependencies (1 found):
#   - src/models.py → src/services.py → src/models.py
#   Suggestion: Extract shared interfaces
# 
# 🗂️  Import Organization Issues:
#   - 15 files have unorganized imports
#   - 8 files mix standard library and third-party imports
# 
# 🛠️  Applying fixes...
# ✓ Removed 12 unused imports
# ✓ Organized imports in 15 files
# ✓ Grouped imports by type (stdlib, third-party, local)
# 
# ⚠️  Manual Review Needed:
# - Circular dependency in models.py and services.py
# - Consider extracting shared types to separate module
```

## Workflow Examples

### Example 9: Pre-Commit Workflow

**Scenario**: You want to run checkup before every commit.

```bash
# Set up pre-commit hook
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: local
    hooks:
      - id: codebase-checkup
        name: Codebase Checkup
        entry: migration-assistant checkup analyze --quiet --no-report
        language: system
        pass_filenames: false
        stages: [commit]
EOF

# Install pre-commit
pip install pre-commit
pre-commit install

# Test the hook
git add .
git commit -m "Test commit"

# Expected output:
# Codebase Checkup...........................................................PASSED
# [main abc1234] Test commit
```

### Example 10: CI/CD Integration

**Scenario**: You want to run checkup in your CI pipeline.

```bash
# GitHub Actions workflow (.github/workflows/checkup.yml)
cat > .github/workflows/checkup.yml << EOF
name: Code Quality Check
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
        run: |
          pip install migration-assistant[checkup]
      - name: Run checkup
        run: |
          migration-assistant checkup analyze --report-json --quiet
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: checkup-reports
          path: reports/
      - name: Check quality gate
        run: |
          python -c "
          import json
          with open('reports/checkup-latest.json') as f:
              data = json.load(f)
          critical_issues = len([i for i in data.get('quality_issues', []) if i.get('severity') == 'critical'])
          if critical_issues > 0:
              print(f'❌ Found {critical_issues} critical issues')
              exit(1)
          print('✅ Quality gate passed')
          "
EOF

# Expected CI output:
# ✓ Set up Python
# ✓ Install dependencies
# ✓ Run checkup
#   Analysis complete: 0 critical issues found
# ✓ Upload reports
# ✓ Check quality gate
#   ✅ Quality gate passed
```

### Example 11: Team Code Review Workflow

**Scenario**: You want to generate reports for code review.

```bash
# Generate comprehensive review report
migration-assistant checkup analyze \
  --report-html \
  --report-markdown \
  --include-suggestions \
  --include-examples

# Create comparison report (after fixes)
migration-assistant checkup run --auto-format --backup
migration-assistant checkup analyze --report-html --output-dir after-cleanup/

# Generate comparison
migration-assistant checkup compare \
  --before reports/checkup-before.json \
  --after after-cleanup/checkup-after.json \
  --output comparison-report.html

# Expected comparison output:
# 📊 Code Quality Comparison Report
# 
# Overall Improvement: +15.2%
# 
# Quality Metrics:
# - Code style violations: 45 → 12 (-73%)
# - Complexity issues: 8 → 5 (-37%)
# - Import problems: 15 → 3 (-80%)
# - Test coverage: 76% → 76% (no change)
# 
# Files Improved: 23/45 (51%)
# 
# Top Improvements:
# 1. src/main.py: 12 issues → 2 issues (-83%)
# 2. src/utils.py: 8 issues → 1 issue (-87%)
# 3. src/api/handlers.py: 15 issues → 4 issues (-73%)
# 
# Remaining Issues:
# - 3 high-complexity functions need refactoring
# - 2 modules missing comprehensive tests
# - 1 circular import requires architectural change
```

## Specialized Examples

### Example 12: Legacy Code Analysis

**Scenario**: You're working with a large legacy codebase.

```bash
# Use legacy-friendly configuration
migration-assistant checkup analyze --config examples/checkup/legacy-checkup.toml --verbose

# Expected output:
# 🔍 Legacy Codebase Analysis Mode
# ✓ Using relaxed quality standards
# ✓ Excluding generated/vendor code
# ✓ Focusing on critical issues only
# 
# Legacy Analysis Results:
# - Files analyzed: 234 (excluded 89 legacy/vendor files)
# - Critical issues: 12 (security, syntax errors)
# - High-priority issues: 45 (complexity, maintainability)
# - Low-priority issues: 156 (style, minor improvements)
# 
# 🎯 Recommended Focus Areas:
# 1. Fix 3 security vulnerabilities in auth module
# 2. Reduce complexity in payment processing (8 functions)
# 3. Add tests for core business logic (23% coverage)
# 4. Modernize database connection handling
# 
# 📋 Improvement Roadmap:
# Phase 1: Security fixes (1-2 weeks)
# Phase 2: Critical complexity reduction (2-3 weeks)
# Phase 3: Test coverage improvement (4-6 weeks)
# Phase 4: Code modernization (ongoing)
```

### Example 13: Performance-Focused Analysis

**Scenario**: You want to identify performance bottlenecks in your code.

```bash
# Run performance-focused analysis
migration-assistant checkup analyze \
  --focus performance \
  --include-complexity \
  --include-duplicates

# Expected output:
# ⚡ Performance Analysis Mode
# 
# 🐌 Performance Issues Found:
# 
# High Complexity Functions:
# - src/data_processor.py:process_large_dataset() (complexity: 15)
#   Impact: High - called frequently in main loop
#   Suggestion: Break into smaller functions, use generators
# 
# - src/api/search.py:complex_search() (complexity: 12)
#   Impact: Medium - user-facing API endpoint
#   Suggestion: Extract query building logic
# 
# Duplicate Code (Performance Impact):
# - Database connection logic duplicated 8 times
#   Impact: High - creates unnecessary connections
#   Suggestion: Implement connection pooling
# 
# - Data validation repeated in 5 modules
#   Impact: Medium - redundant processing
#   Suggestion: Create shared validation service
# 
# 💡 Performance Recommendations:
# 1. Implement database connection pooling
# 2. Add caching for expensive operations
# 3. Use generators for large data processing
# 4. Consider async/await for I/O operations
# 5. Profile actual runtime performance
```

### Example 14: Security-Focused Analysis

**Scenario**: You want to identify potential security issues.

```bash
# Run security-focused analysis
migration-assistant checkup analyze \
  --enable-security \
  --include-bandit \
  --focus security

# Expected output:
# 🔒 Security Analysis Mode
# 
# 🚨 Security Issues Found:
# 
# High Severity:
# - src/auth.py:45: Hardcoded password in source code
#   Risk: Critical - credentials exposure
#   Fix: Use environment variables or secure vault
# 
# - src/api/upload.py:123: Unsafe file handling
#   Risk: High - potential path traversal
#   Fix: Validate and sanitize file paths
# 
# Medium Severity:
# - src/database.py:67: SQL query construction
#   Risk: Medium - potential SQL injection
#   Fix: Use parameterized queries
# 
# - src/utils.py:234: Insecure random number generation
#   Risk: Medium - predictable tokens
#   Fix: Use secrets module for cryptographic randomness
# 
# 🛡️  Security Recommendations:
# 1. Implement secure credential management
# 2. Add input validation and sanitization
# 3. Use parameterized database queries
# 4. Enable security headers in web responses
# 5. Regular security dependency updates
# 
# 📋 Security Checklist:
# ☐ Remove hardcoded credentials
# ☐ Implement file upload validation
# ☐ Review database query construction
# ☐ Audit third-party dependencies
# ☐ Set up automated security scanning
```

## Integration Examples

### Example 15: IDE Integration (VS Code)

**Scenario**: You want to run checkup from within VS Code.

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Codebase Checkup",
      "type": "shell",
      "command": "migration-assistant",
      "args": ["checkup", "analyze", "--verbose"],
      "group": "build",
      "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "shared"
      },
      "problemMatcher": {
        "pattern": {
          "regexp": "^(.*):(\\d+):(\\d+):\\s+(warning|error):\\s+(.*)$",
          "file": 1,
          "line": 2,
          "column": 3,
          "severity": 4,
          "message": 5
        }
      }
    },
    {
      "label": "Checkup with Cleanup",
      "type": "shell",
      "command": "migration-assistant",
      "args": ["checkup", "run", "--auto-format", "--dry-run"],
      "group": "build"
    }
  ]
}
```

### Example 16: Makefile Integration

**Scenario**: You want to include checkup in your project's Makefile.

```makefile
# Makefile
.PHONY: checkup checkup-fix checkup-report

checkup:
	@echo "Running codebase checkup..."
	migration-assistant checkup analyze --quiet

checkup-fix:
	@echo "Running checkup with fixes..."
	migration-assistant checkup run --auto-format --backup

checkup-report:
	@echo "Generating detailed checkup report..."
	migration-assistant checkup analyze --report-html --report-json
	@echo "Reports available in: reports/"

checkup-ci:
	@echo "Running CI checkup..."
	migration-assistant checkup analyze --report-json --quiet
	@python scripts/check_quality_gate.py

clean-checkup:
	@echo "Cleaning checkup artifacts..."
	rm -rf reports/ .checkup-backups/
```

These examples demonstrate the flexibility and power of the codebase checkup system across various development scenarios and workflows.