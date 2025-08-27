# Codebase Checkup Best Practices

## Overview

This guide provides best practices for effectively using the codebase checkup and cleanup system. Following these practices will help you maintain high code quality while minimizing disruption to your development workflow.

## Getting Started Best Practices

### 1. Start with Analysis Only

**Always begin with analysis-only mode** to understand your codebase before making changes.

```bash
# First run - understand your codebase
migration-assistant checkup analyze --verbose --report-html

# Review the HTML report before proceeding
open reports/checkup-latest.html
```

**Why this matters:**
- Understand the scope of issues
- Identify potential problem areas
- Plan your improvement strategy
- Avoid unexpected changes

### 2. Use Dry Run Mode

**Preview changes before applying them** using dry-run mode.

```bash
# See what would be changed without making changes
migration-assistant checkup run --dry-run --auto-format --auto-fix-imports

# Review the planned changes
# Then apply if satisfied
migration-assistant checkup run --auto-format --auto-fix-imports --backup
```

**Benefits:**
- Prevents unexpected modifications
- Allows review of planned changes
- Builds confidence in the tool
- Helps understand impact

### 3. Always Create Backups

**Enable backups for any operation that modifies code.**

```toml
# In checkup.toml
[checkup.safety]
create_backup = true
backup_directory = ".checkup-backups"
max_backups = 10
compress_backups = true
```

```bash
# Command line backup
migration-assistant checkup run --backup --auto-format
```

**Backup strategy:**
- Keep multiple backup versions
- Compress backups to save space
- Document backup locations
- Test rollback procedures

## Configuration Best Practices

### 1. Team-Consistent Configuration

**Create and maintain a shared team configuration.**

```toml
# team-checkup.toml - commit to repository
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = true
enable_import_analysis = true
auto_format = true
create_backup = true

[checkup.quality]
max_complexity = 10
max_line_length = 88
enforce_docstrings = true
check_type_hints = true
use_flake8 = true
use_mypy = true

[checkup.duplicates]
similarity_threshold = 0.85
min_duplicate_lines = 5
suggest_refactoring = true

[checkup.imports]
remove_unused = true
organize_imports = true
use_isort = true
isort_profile = "black"

[checkup.reporting]
generate_html_report = true
generate_json_report = true
output_directory = "quality-reports"

[checkup.safety]
create_backup = true
require_confirmation = false  # For CI/CD
max_file_moves = 5
```

**Team configuration benefits:**
- Consistent code quality standards
- Reproducible results across environments
- Easier onboarding for new team members
- Simplified CI/CD integration

### 2. Environment-Specific Configurations

**Use different configurations for different environments.**

```bash
# Development - more lenient, interactive
migration-assistant checkup analyze --config dev-checkup.toml

# CI/CD - strict, automated
migration-assistant checkup analyze --config ci-checkup.toml

# Legacy - gradual improvement
migration-assistant checkup analyze --config legacy-checkup.toml
```

**Example configurations:**

**Development (dev-checkup.toml):**
```toml
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = false  # Can be slow during development
auto_format = true
verbose = true

[checkup.quality]
max_complexity = 12  # Slightly more lenient
enforce_docstrings = false  # Don't enforce during development
```

**CI/CD (ci-checkup.toml):**
```toml
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = false  # Too slow for CI
auto_format = false  # Don't modify code in CI
quiet = true

[checkup.quality]
max_complexity = 10  # Strict for CI
enforce_docstrings = true
```

### 3. Progressive Configuration

**Start with lenient settings and gradually tighten standards.**

```toml
# Phase 1: Basic cleanup
[checkup]
enable_quality_analysis = true
enable_duplicate_detection = false
auto_format = true

[checkup.quality]
max_complexity = 15  # Lenient initially
enforce_docstrings = false
check_type_hints = false

# Phase 2: After basic cleanup (update configuration)
[checkup.quality]
max_complexity = 12  # Tighten standards
enforce_docstrings = true  # Start requiring docs

# Phase 3: Mature codebase
[checkup.quality]
max_complexity = 8   # Strict standards
enforce_docstrings = true
check_type_hints = true
```

## Workflow Integration Best Practices

### 1. Pre-Commit Integration

**Set up pre-commit hooks for automatic quality checks.**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: checkup-analysis
        name: Code Quality Analysis
        entry: migration-assistant checkup analyze --quiet --no-report
        language: system
        pass_filenames: false
        stages: [commit]
        
      - id: checkup-format
        name: Auto-format Code
        entry: migration-assistant checkup run --auto-format --no-backup --quiet
        language: system
        pass_filenames: false
        stages: [commit]
        files: \.py$
```

**Pre-commit best practices:**
- Keep hooks fast (< 10 seconds)
- Use `--quiet` to reduce noise
- Only run on relevant files
- Provide clear error messages

### 2. CI/CD Integration

**Integrate checkup into your continuous integration pipeline.**

```yaml
# .github/workflows/quality.yml
name: Code Quality
on: [push, pull_request]

jobs:
  quality-check:
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
          
      - name: Run quality analysis
        run: |
          migration-assistant checkup analyze --config ci-checkup.toml --report-json
          
      - name: Quality gate check
        run: |
          python scripts/quality_gate.py --report reports/checkup-latest.json
          
      - name: Upload quality reports
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: quality-reports
          path: reports/
          
      - name: Comment PR with results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('reports/checkup-latest.json'));
            const comment = `## Code Quality Report
            - **Files analyzed:** ${report.summary.files_analyzed}
            - **Issues found:** ${report.summary.total_issues}
            - **Quality score:** ${report.metrics.quality_score}/100
            
            ${report.summary.total_issues > 0 ? '⚠️ Issues found that need attention' : '✅ No issues found'}`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

**CI/CD best practices:**
- Fail fast on critical issues
- Generate artifacts for review
- Provide clear feedback
- Don't modify code in CI
- Cache dependencies for speed

### 3. IDE Integration

**Configure your IDE for seamless checkup integration.**

**VS Code (.vscode/tasks.json):**
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Quick Quality Check",
      "type": "shell",
      "command": "migration-assistant",
      "args": ["checkup", "analyze", "--path", "${file}", "--quiet"],
      "group": "build",
      "presentation": {
        "echo": false,
        "reveal": "silent",
        "focus": false,
        "panel": "shared",
        "showReuseMessage": false
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
      "label": "Format Current File",
      "type": "shell",
      "command": "migration-assistant",
      "args": ["checkup", "run", "--path", "${file}", "--auto-format", "--no-backup"],
      "group": "build"
    }
  ]
}
```

**VS Code (.vscode/settings.json):**
```json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "files.associations": {
    "checkup*.toml": "toml"
  }
}
```

## Code Quality Best Practices

### 1. Gradual Quality Improvement

**Improve code quality incrementally rather than all at once.**

```bash
# Phase 1: Fix formatting and imports (safest)
migration-assistant checkup run --auto-format --auto-fix-imports --backup

# Phase 2: Address complexity issues (manual review)
migration-assistant checkup analyze --focus complexity

# Phase 3: Add missing documentation
migration-assistant checkup analyze --focus documentation

# Phase 4: Improve test coverage
migration-assistant checkup coverage --suggest-tests
```

**Incremental improvement strategy:**
1. **Formatting first** - safest, most visible improvement
2. **Import cleanup** - removes unused code, improves organization
3. **Complexity reduction** - requires manual refactoring
4. **Documentation** - adds value without changing logic
5. **Test coverage** - improves reliability

### 2. Focus on High-Impact Issues

**Prioritize issues that provide the most value.**

```bash
# Focus on critical issues first
migration-assistant checkup analyze --severity critical

# Address security issues
migration-assistant checkup analyze --focus security

# Fix performance-related complexity
migration-assistant checkup analyze --focus performance
```

**Issue prioritization:**
1. **Security vulnerabilities** - highest priority
2. **Syntax errors** - prevent code from running
3. **High complexity** - maintenance burden
4. **Duplicate code** - maintenance and bug risk
5. **Style violations** - consistency and readability

### 3. Maintain Quality Standards

**Establish and maintain consistent quality standards.**

```toml
# Establish clear quality gates
[checkup.quality]
max_complexity = 10          # Reasonable complexity limit
max_line_length = 88         # Black standard
enforce_docstrings = true    # Documentation requirement
check_type_hints = true      # Type safety

[checkup.coverage]
min_coverage = 80.0          # Minimum test coverage
min_function_coverage = 75.0 # Function-level coverage

[checkup.duplicates]
similarity_threshold = 0.85  # Catch significant duplicates
min_duplicate_lines = 5      # Meaningful duplicate size
```

**Quality maintenance:**
- Regular quality reviews
- Trend monitoring
- Team training on standards
- Automated enforcement

## Performance Best Practices

### 1. Optimize for Large Codebases

**Configure checkup for optimal performance on large projects.**

```toml
# Performance-optimized configuration
[checkup]
parallel_analysis = true
max_workers = 4              # Adjust based on system
timeout = 600                # 10 minutes for large codebases
max_file_size = 1048576      # 1MB file size limit

# Exclude unnecessary files
exclude_patterns = [
    "venv/*", "node_modules/*", "*.log", "build/*", "dist/*",
    "migrations/*", "vendor/*", "third_party/*", "generated/*"
]

# Disable expensive analyzers for regular runs
enable_duplicate_detection = false  # Run separately when needed
enable_structure_analysis = false   # Run periodically
```

**Performance strategies:**
- Use exclusion patterns liberally
- Disable expensive analyzers for frequent runs
- Process in smaller chunks
- Use parallel processing
- Monitor resource usage

### 2. Incremental Analysis

**Analyze only changed files for faster feedback.**

```bash
# Git-based incremental analysis
git diff --name-only HEAD~1 | grep '\.py$' | \
  xargs migration-assistant checkup analyze --path

# Modified files only
find . -name "*.py" -mtime -1 | \
  xargs migration-assistant checkup analyze --path

# Specific directories
migration-assistant checkup analyze --path src/core/
migration-assistant checkup analyze --path src/api/
```

**Incremental analysis benefits:**
- Faster feedback cycles
- Focused attention on changes
- Reduced resource usage
- Better integration with development workflow

### 3. Caching and Optimization

**Use caching strategies to improve performance.**

```bash
# Cache analysis results
export CHECKUP_CACHE_DIR=".checkup-cache"
migration-assistant checkup analyze --use-cache

# Skip unchanged files
migration-assistant checkup analyze --incremental

# Parallel processing
migration-assistant checkup analyze --parallel --max-workers 4
```

## Team Collaboration Best Practices

### 1. Establish Team Standards

**Create and document team coding standards.**

```markdown
# Team Coding Standards

## Code Quality Requirements
- Maximum complexity: 10
- Line length: 88 characters
- All public functions must have docstrings
- Type hints required for new code

## Tool Configuration
- Use Black for formatting
- Use isort with Black profile
- Use flake8 for linting
- Use mypy for type checking

## Workflow
- Run checkup before committing
- Address all critical issues
- Review quality reports in PRs
- Update standards quarterly
```

### 2. Code Review Integration

**Integrate checkup results into code review process.**

```bash
# Generate review-friendly reports
migration-assistant checkup analyze --report-markdown --include-suggestions

# Compare before/after for PRs
migration-assistant checkup compare \
  --before baseline-report.json \
  --after current-report.json \
  --output pr-quality-report.html
```

**Code review checklist:**
- [ ] Checkup analysis passed
- [ ] No new critical issues introduced
- [ ] Quality metrics maintained or improved
- [ ] Documentation updated if needed
- [ ] Tests added for new functionality

### 3. Knowledge Sharing

**Share checkup knowledge across the team.**

```bash
# Generate team training materials
migration-assistant checkup analyze --report-html --include-examples

# Create improvement roadmap
migration-assistant checkup analyze --focus roadmap --output team-roadmap.md
```

**Knowledge sharing activities:**
- Regular quality review meetings
- Checkup tool training sessions
- Best practices documentation
- Quality metrics dashboards

## Maintenance Best Practices

### 1. Regular Quality Reviews

**Schedule regular quality assessment sessions.**

```bash
# Weekly quality check
migration-assistant checkup analyze --report-html --include-trends

# Monthly comprehensive analysis
migration-assistant checkup analyze --comprehensive --report-all

# Quarterly standards review
migration-assistant checkup analyze --focus standards-review
```

**Review schedule:**
- **Daily**: Pre-commit checks
- **Weekly**: Team quality review
- **Monthly**: Comprehensive analysis
- **Quarterly**: Standards and tool updates

### 2. Tool and Configuration Updates

**Keep tools and configurations up to date.**

```bash
# Update checkup system
pip install --upgrade migration-assistant[checkup]

# Update analysis tools
pip install --upgrade black isort flake8 mypy pytest pytest-cov

# Validate configuration after updates
migration-assistant checkup validate-config --config team-checkup.toml
```

**Update checklist:**
- [ ] Update migration-assistant
- [ ] Update analysis tools
- [ ] Test configuration compatibility
- [ ] Update team documentation
- [ ] Communicate changes to team

### 3. Metrics and Monitoring

**Track quality metrics over time.**

```bash
# Generate trend reports
migration-assistant checkup analyze --include-trends --report-json

# Export metrics for monitoring
migration-assistant checkup metrics --export prometheus --output metrics.txt

# Quality dashboard data
migration-assistant checkup analyze --dashboard-data --output dashboard.json
```

**Key metrics to track:**
- Code quality score trends
- Issue resolution rates
- Test coverage changes
- Complexity trends
- Team adoption rates

## Troubleshooting Best Practices

### 1. Systematic Problem Solving

**Follow a systematic approach to resolve issues.**

```bash
# Step 1: Identify the problem
migration-assistant checkup analyze --verbose --debug

# Step 2: Isolate the issue
migration-assistant checkup analyze --path problematic_file.py

# Step 3: Test with minimal configuration
migration-assistant checkup analyze --config minimal-checkup.toml

# Step 4: Verify tool installations
black --version && isort --version && flake8 --version && mypy --version
```

### 2. Documentation and Logging

**Maintain good documentation and logging practices.**

```bash
# Enable debug logging
export CHECKUP_DEBUG=1
migration-assistant checkup analyze --verbose > checkup-debug.log 2>&1

# Document configuration decisions
cat > CHECKUP_CONFIG.md << EOF
# Checkup Configuration Documentation

## Quality Standards
- Complexity limit: 10 (team decision from 2024-01-15)
- Line length: 88 (Black standard)
- Docstring requirement: Public functions only

## Tool Versions
- Black: 23.1.0
- isort: 5.12.0
- flake8: 6.0.0
- mypy: 1.0.0

## Exclusions
- migrations/: Auto-generated code
- vendor/: Third-party code
- legacy/: Gradual improvement approach
EOF
```

### 3. Recovery Procedures

**Establish clear recovery procedures.**

```bash
# Create recovery script
cat > scripts/checkup-recovery.sh << 'EOF'
#!/bin/bash
set -e

echo "🔄 Checkup Recovery Procedure"

# Step 1: List available backups
echo "Available backups:"
migration-assistant checkup list-backups

# Step 2: Rollback to latest backup
read -p "Enter backup 
ID to rollback to: " backup_id
migration-assistant checkup rollback "$backup_id"

# Step 3: Verify rollback
echo "✅ Rollback completed. Verifying..."
python -m py_compile src/*.py

# Step 4: Run basic analysis
migration-assistant checkup analyze --quiet

echo "🎉 Recovery completed successfully!"
EOF

chmod +x scripts/checkup-recovery.sh
```

## Security Best Practices

### 1. Secure Configuration Management

**Handle sensitive configuration securely.**

```bash
# Use environment variables for sensitive settings
export CHECKUP_API_TOKEN="your-secure-token"
export CHECKUP_BACKUP_ENCRYPTION_KEY="your-encryption-key"

# Secure configuration file permissions
chmod 600 checkup.toml
chown $USER:$USER checkup.toml
```

```toml
# Use environment variable references
[checkup.api]
token = "${CHECKUP_API_TOKEN}"

[checkup.backup]
encryption_key = "${CHECKUP_BACKUP_ENCRYPTION_KEY}"
```

### 2. Code Security Analysis

**Enable security-focused analysis.**

```toml
[checkup.security]
enable_security_analysis = true
use_bandit = true
check_dependencies = true
scan_secrets = true

[checkup.quality]
use_bandit = true  # Security linting
check_imports = true  # Detect suspicious imports
```

```bash
# Security-focused analysis
migration-assistant checkup analyze --focus security --report-security

# Dependency security check
migration-assistant checkup analyze --check-dependencies --report-vulnerabilities
```

### 3. Audit and Compliance

**Maintain audit trails and compliance.**

```bash
# Generate compliance reports
migration-assistant checkup analyze --compliance-report --standard pci-dss

# Audit trail logging
export CHECKUP_AUDIT_LOG="/var/log/checkup-audit.log"
migration-assistant checkup analyze --audit-mode

# Compliance dashboard
migration-assistant checkup compliance --dashboard --output compliance-dashboard.html
```

## Legacy Code Best Practices

### 1. Gradual Modernization

**Approach legacy code improvement systematically.**

```bash
# Phase 1: Assessment
migration-assistant checkup analyze --config legacy-checkup.toml --report-assessment

# Phase 2: Critical fixes only
migration-assistant checkup run --focus critical --backup --dry-run

# Phase 3: Module-by-module improvement
for module in core api utils; do
    migration-assistant checkup run --path src/$module/ --auto-format --backup
done

# Phase 4: Comprehensive modernization
migration-assistant checkup run --comprehensive --backup
```

### 2. Risk Management

**Minimize risk when working with legacy code.**

```toml
# Ultra-conservative legacy configuration
[checkup.safety]
create_backup = true
backup_directory = ".legacy-backups"
max_backups = 20
require_confirmation = true
max_file_moves = 0        # No file moves initially
max_changes_per_file = 10 # Limit changes per file

[checkup.quality]
max_complexity = 25       # Very lenient initially
enforce_docstrings = false
check_type_hints = false
```

### 3. Documentation and Planning

**Document legacy improvement plans.**

```markdown
# Legacy Code Improvement Plan

## Current State Assessment
- Total files: 234
- Critical issues: 45
- High complexity functions: 23
- Test coverage: 23%

## Improvement Phases

### Phase 1: Safety and Stability (Weeks 1-2)
- Fix syntax errors
- Address security vulnerabilities
- Create comprehensive backups
- Establish baseline metrics

### Phase 2: Basic Cleanup (Weeks 3-4)
- Apply code formatting
- Clean up imports
- Remove dead code
- Basic documentation

### Phase 3: Structural Improvements (Weeks 5-8)
- Reduce complexity in core modules
- Improve error handling
- Add basic tests
- Refactor duplicated code

### Phase 4: Modernization (Weeks 9-12)
- Add type hints
- Improve documentation
- Increase test coverage
- Apply modern patterns
```

## Conclusion

Following these best practices will help you:

- **Maintain high code quality** consistently across your team
- **Minimize disruption** to your development workflow
- **Improve code gradually** without overwhelming changes
- **Integrate seamlessly** with existing tools and processes
- **Scale effectively** as your codebase grows
- **Collaborate efficiently** with team members
- **Handle legacy code** safely and systematically

Remember that code quality improvement is a journey, not a destination. Start small, be consistent, and gradually raise your standards as your team becomes more comfortable with the tools and processes.

## Quick Reference

### Essential Commands
```bash
# First-time analysis
migration-assistant checkup analyze --verbose --report-html

# Safe cleanup with backup
migration-assistant checkup run --auto-format --backup --dry-run

# Team configuration
migration-assistant checkup analyze --config team-checkup.toml

# CI/CD integration
migration-assistant checkup analyze --report-json --quiet

# Legacy code approach
migration-assistant checkup analyze --config legacy-checkup.toml
```

### Key Configuration Sections
```toml
[checkup]                    # Global settings
[checkup.quality]           # Code quality standards
[checkup.duplicates]        # Duplicate detection
[checkup.imports]           # Import analysis
[checkup.coverage]          # Test coverage
[checkup.formatting]        # Code formatting
[checkup.reporting]         # Report generation
[checkup.safety]            # Safety and backup
```

### Important Files
- `checkup.toml` - Main configuration
- `team-checkup.toml` - Team standards
- `ci-checkup.toml` - CI/CD configuration
- `legacy-checkup.toml` - Legacy code settings
- `.pre-commit-config.yaml` - Pre-commit hooks
- `reports/` - Generated reports
- `.checkup-backups/` - Backup directory

By following these best practices, you'll establish a robust, maintainable approach to code quality that serves your team well over time.