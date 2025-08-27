#!/usr/bin/env python3
"""
CI/CD Integration Demonstration for Codebase Checkup

This script demonstrates how to integrate codebase checkup into
CI/CD pipelines with proper error handling and reporting.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from migration_assistant.checkup import CodebaseOrchestrator, CheckupConfig


@dataclass
class CIResult:
    """CI/CD integration result."""
    success: bool
    quality_gate_passed: bool
    issues_found: int
    critical_issues: int
    quality_score: float
    coverage_percentage: float
    duration_seconds: float
    report_paths: Dict[str, Path]
    error_message: Optional[str] = None


class CIIntegration:
    """Handles CI/CD integration for codebase checkup."""
    
    def __init__(self):
        self.ci_env = self._detect_ci_environment()
        self.config = self._create_ci_config()
    
    def _detect_ci_environment(self) -> str:
        """Detect the CI/CD environment."""
        if os.getenv('GITHUB_ACTIONS'):
            return 'github_actions'
        elif os.getenv('GITLAB_CI'):
            return 'gitlab_ci'
        elif os.getenv('JENKINS_URL'):
            return 'jenkins'
        elif os.getenv('TRAVIS'):
            return 'travis'
        elif os.getenv('CIRCLECI'):
            return 'circleci'
        else:
            return 'unknown'
    
    def _create_ci_config(self) -> CheckupConfig:
        """Create CI-optimized configuration."""
        return CheckupConfig(
            # Analysis settings for CI
            enable_quality_analysis=True,
            enable_import_analysis=True,
            enable_duplicate_detection=False,  # Can be slow in CI
            enable_coverage_analysis=True,
            enable_config_validation=True,
            enable_doc_validation=False,  # Can be flaky
            
            # No cleanup in CI
            auto_format=False,
            auto_fix_imports=False,
            auto_organize_files=False,
            
            # CI-optimized performance
            parallel_analysis=True,
            max_workers=2,  # Conservative for CI resources
            timeout=300,  # 5 minutes
            
            # CI-appropriate output
            verbose=False,
            quiet=True,
            
            # Reporting for CI
            generate_html_report=False,  # Not needed in CI
            generate_json_report=True,   # For CI integration
            generate_xml_report=True,    # For CI tools
            output_directory="ci-reports",
            
            # Safety settings for CI
            create_backup=False,
            require_confirmation=False,
            dry_run=False,
            
            # File filtering
            exclude_patterns=[
                "venv/*", "__pycache__/*", "*.pyc", ".git/*",
                "build/*", "dist/*", "node_modules/*",
                ".tox/*", ".pytest_cache/*", "*.egg-info/*"
            ]
        )
    
    async def run_ci_checkup(self, project_path: Path = None) -> CIResult:
        """Run checkup optimized for CI/CD environment."""
        start_time = datetime.now()
        
        try:
            print(f"🔍 Running checkup in {self.ci_env} environment")
            
            # Initialize orchestrator
            orchestrator = CodebaseOrchestrator(self.config, project_path or Path("."))
            
            # Run analysis
            results = await orchestrator.run_analysis_only()
            
            # Generate reports
            report_results = await orchestrator.generate_reports(results)
            
            # Calculate metrics
            critical_issues = sum(
                1 for issue in results.quality_issues 
                if issue.severity == 'critical'
            )
            
            quality_score = getattr(results.metrics, 'quality_score', 0.0)
            coverage_percentage = getattr(results.metrics, 'coverage_percentage', 0.0)
            
            # Determine quality gate status
            quality_gate_passed = self._evaluate_quality_gate(
                critical_issues, quality_score, coverage_percentage
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return CIResult(
                success=True,
                quality_gate_passed=quality_gate_passed,
                issues_found=results.total_issues,
                critical_issues=critical_issues,
                quality_score=quality_score,
                coverage_percentage=coverage_percentage,
                duration_seconds=duration,
                report_paths={
                    'json': report_results.json_report_path,
                    'xml': report_results.xml_report_path
                }
            )
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return CIResult(
                success=False,
                quality_gate_passed=False,
                issues_found=0,
                critical_issues=0,
                quality_score=0.0,
                coverage_percentage=0.0,
                duration_seconds=duration,
                report_paths={},
                error_message=str(e)
            )
    
    def _evaluate_quality_gate(self, critical_issues: int, quality_score: float, coverage: float) -> bool:
        """Evaluate whether the quality gate passes."""
        # Quality gate rules
        if critical_issues > 0:
            return False
        
        if quality_score < 70.0:
            return False
        
        if coverage < 80.0:
            return False
        
        return True
    
    def create_ci_comment(self, result: CIResult) -> str:
        """Create comment for CI/CD system (PR/MR comments)."""
        if not result.success:
            return f"""## ❌ Codebase Checkup Failed

**Error:** {result.error_message}

Please check the CI logs for more details."""
        
        status_emoji = "✅" if result.quality_gate_passed else "⚠️"
        gate_status = "PASSED" if result.quality_gate_passed else "FAILED"
        
        comment = f"""## {status_emoji} Codebase Checkup Results

**Quality Gate:** {gate_status}

### Summary
- **Issues Found:** {result.issues_found}
- **Critical Issues:** {result.critical_issues}
- **Quality Score:** {result.quality_score:.1f}/100
- **Coverage:** {result.coverage_percentage:.1f}%
- **Duration:** {result.duration_seconds:.1f}s

### Quality Gate Rules
- ✅ No critical issues: {'PASS' if result.critical_issues == 0 else 'FAIL'}
- ✅ Quality score ≥ 70: {'PASS' if result.quality_score >= 70 else 'FAIL'}
- ✅ Coverage ≥ 80%: {'PASS' if result.coverage_percentage >= 80 else 'FAIL'}
"""
        
        if not result.quality_gate_passed:
            comment += "\n⚠️ **Quality gate failed.** Please address the issues before merging."
        
        return comment
    
    def create_ci_summary(self, result: CIResult) -> Dict[str, Any]:
        """Create summary for CI/CD system consumption."""
        return {
            'success': result.success,
            'quality_gate_passed': result.quality_gate_passed,
            'issues_found': result.issues_found,
            'critical_issues': result.critical_issues,
            'quality_score': result.quality_score,
            'coverage_percentage': result.coverage_percentage,
            'duration_seconds': result.duration_seconds,
            'timestamp': datetime.now().isoformat(),
            'ci_environment': self.ci_env
        }
    
    def set_ci_outputs(self, result: CIResult):
        """Set CI/CD system outputs."""
        if self.ci_env == 'github_actions':
            self._set_github_outputs(result)
        elif self.ci_env == 'gitlab_ci':
            self._set_gitlab_outputs(result)
    
    def _set_github_outputs(self, result: CIResult):
        """Set GitHub Actions outputs."""
        github_output = os.getenv('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"quality-gate-passed={str(result.quality_gate_passed).lower()}\n")
                f.write(f"issues-found={result.issues_found}\n")
                f.write(f"critical-issues={result.critical_issues}\n")
                f.write(f"quality-score={result.quality_score:.1f}\n")
                f.write(f"coverage={result.coverage_percentage:.1f}\n")
    
    def _set_gitlab_outputs(self, result: CIResult):
        """Set GitLab CI outputs."""
        # GitLab uses environment variables
        print(f"QUALITY_GATE_PASSED={str(result.quality_gate_passed).lower()}")
        print(f"ISSUES_FOUND={result.issues_found}")
        print(f"CRITICAL_ISSUES={result.critical_issues}")
        print(f"QUALITY_SCORE={result.quality_score:.1f}")
        print(f"COVERAGE={result.coverage_percentage:.1f}")


async def demo_github_actions_integration():
    """Demonstrate GitHub Actions integration."""
    print("🐙 GitHub Actions Integration Demo")
    print("=" * 50)
    
    # Simulate GitHub Actions environment
    os.environ['GITHUB_ACTIONS'] = 'true'
    os.environ['GITHUB_REPOSITORY'] = 'example/repo'
    os.environ['GITHUB_REF'] = 'refs/heads/main'
    
    # Create sample project
    project_dir = Path("github_demo_project")
    project_dir.mkdir(exist_ok=True)
    
    # Create sample code with issues
    (project_dir / "app.py").write_text('''
import os, sys  # Multiple imports (style issue)
import unused_module  # Unused import

def problematic_function(a,b,c,d,e):  # Too many params, no spaces
    if a==b:  # No spaces around operator
        if c==d:  # Nested if (complexity)
            return a+b+c+d+e
        else:
            return 0
    else:
        return 1

# Missing docstring
def undocumented():
    pass
''')
    
    try:
        ci = CIIntegration()
        result = await ci.run_ci_checkup(project_dir)
        
        print(f"CI Environment: {ci.ci_env}")
        print(f"Success: {result.success}")
        print(f"Quality Gate: {'PASSED' if result.quality_gate_passed else 'FAILED'}")
        print(f"Issues: {result.issues_found}")
        print(f"Critical Issues: {result.critical_issues}")
        
        # Create GitHub Actions comment
        comment = ci.create_ci_comment(result)
        print(f"\n📝 GitHub Actions Comment:")
        print(comment)
        
        # Set GitHub Actions outputs
        ci.set_ci_outputs(result)
        
        # Save summary for GitHub Actions
        summary = ci.create_ci_summary(result)
        with open("github-summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📄 Summary saved to: github-summary.json")
        
        return result
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        # Clean up environment
        os.environ.pop('GITHUB_ACTIONS', None)
        os.environ.pop('GITHUB_REPOSITORY', None)
        os.environ.pop('GITHUB_REF', None)


async def demo_gitlab_ci_integration():
    """Demonstrate GitLab CI integration."""
    print("\n🦊 GitLab CI Integration Demo")
    print("=" * 50)
    
    # Simulate GitLab CI environment
    os.environ['GITLAB_CI'] = 'true'
    os.environ['CI_PROJECT_NAME'] = 'example-project'
    os.environ['CI_COMMIT_REF_NAME'] = 'main'
    
    # Create sample project with better quality
    project_dir = Path("gitlab_demo_project")
    project_dir.mkdir(exist_ok=True)
    
    (project_dir / "calculator.py").write_text('''
"""A simple calculator module."""

from typing import Union


def add(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """Add two numbers."""
    return a + b


def subtract(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """Subtract two numbers."""
    return a - b
''')
    
    try:
        ci = CIIntegration()
        result = await ci.run_ci_checkup(project_dir)
        
        print(f"CI Environment: {ci.ci_env}")
        print(f"Success: {result.success}")
        print(f"Quality Gate: {'PASSED' if result.quality_gate_passed else 'FAILED'}")
        print(f"Issues: {result.issues_found}")
        
        # Create GitLab CI comment
        comment = ci.create_ci_comment(result)
        print(f"\n📝 GitLab CI Comment:")
        print(comment)
        
        # Set GitLab CI outputs
        print(f"\n🔧 GitLab CI Environment Variables:")
        ci.set_ci_outputs(result)
        
        # Save summary for GitLab CI
        summary = ci.create_ci_summary(result)
        with open("gitlab-summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        return result
        
    finally:
        # Clean up
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        # Clean up environment
        os.environ.pop('GITLAB_CI', None)
        os.environ.pop('CI_PROJECT_NAME', None)
        os.environ.pop('CI_COMMIT_REF_NAME', None)


async def demo_quality_gate_scenarios():
    """Demonstrate different quality gate scenarios."""
    print("\n🚪 Quality Gate Scenarios Demo")
    print("=" * 50)
    
    scenarios = [
        {
            'name': 'High Quality (Should Pass)',
            'code': '''
"""High quality module."""

from typing import List


def process_items(items: List[str]) -> List[str]:
    """Process a list of items.
    
    Args:
        items: List of strings to process
        
    Returns:
        Processed list of strings
    """
    return [item.strip().lower() for item in items if item.strip()]


class DataProcessor:
    """Processes data efficiently."""
    
    def __init__(self, data: List[str]) -> None:
        """Initialize with data."""
        self.data = data
    
    def process(self) -> List[str]:
        """Process the data."""
        return process_items(self.data)
'''
        },
        {
            'name': 'Critical Issues (Should Fail)',
            'code': '''
import os
import sys

# Critical: eval usage
def dangerous_function(user_input):
    return eval(user_input)

# Critical: hardcoded password
PASSWORD = "secret123"

# Critical: SQL injection
def unsafe_query(name):
    query = "SELECT * FROM users WHERE name = '%s'" % name
    return query
'''
        },
        {
            'name': 'Many Minor Issues (Should Fail)',
            'code': '''
import os,sys,json,re  # Multiple imports
import unused_module

def bad_function(a,b,c,d,e,f,g,h,i,j):  # Too many parameters
    if a==b:
        if c==d:
            if e==f:
                if g==h:
                    if i==j:
                        return a+b+c+d+e+f+g+h+i+j
                    else:
                        return 0
                else:
                    return 1
            else:
                return 2
        else:
            return 3
    else:
        return 4

def undocumented_function():
    pass

# Very long line that exceeds any reasonable limit and should be broken into multiple lines for better readability and maintainability
x = "This is an extremely long string that goes on and on and definitely exceeds the line length limit"
'''
        }
    ]
    
    ci = CIIntegration()
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📋 Scenario {i}: {scenario['name']}")
        
        # Create test project
        project_dir = Path(f"scenario_{i}_project")
        project_dir.mkdir(exist_ok=True)
        (project_dir / "test_code.py").write_text(scenario['code'])
        
        try:
            result = await ci.run_ci_checkup(project_dir)
            results.append(result)
            
            print(f"  Quality Gate: {'✅ PASSED' if result.quality_gate_passed else '❌ FAILED'}")
            print(f"  Issues: {result.issues_found}")
            print(f"  Critical: {result.critical_issues}")
            print(f"  Quality Score: {result.quality_score:.1f}")
            
        finally:
            # Clean up
            import shutil
            if project_dir.exists():
                shutil.rmtree(project_dir)
    
    return results


def create_ci_script_examples():
    """Create example CI/CD scripts."""
    print("\n📜 Creating CI/CD Script Examples")
    print("=" * 50)
    
    # GitHub Actions workflow
    github_workflow = '''
name: Code Quality Check

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  quality-check:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install migration-assistant[checkup]
    
    - name: Run checkup
      id: checkup
      run: |
        python examples/checkup/scripts/demo_ci_integration.py
    
    - name: Comment PR
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          if (fs.existsSync('github-summary.json')) {
            const summary = JSON.parse(fs.readFileSync('github-summary.json', 'utf8'));
            const comment = `## 🔍 Code Quality Results
            
Quality Gate: ${summary.quality_gate_passed ? '✅ PASSED' : '❌ FAILED'}
Issues Found: ${summary.issues_found}
Critical Issues: ${summary.critical_issues}
Quality Score: ${summary.quality_score}/100`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
          }
    
    - name: Fail on quality gate
      if: steps.checkup.outputs.quality-gate-passed == 'false'
      run: exit 1
'''
    
    with open("example-github-workflow.yml", "w") as f:
        f.write(github_workflow)
    
    # GitLab CI configuration
    gitlab_ci = '''
stages:
  - quality

quality-check:
  stage: quality
  image: python:3.9
  
  before_script:
    - pip install migration-assistant[checkup]
  
  script:
    - python examples/checkup/scripts/demo_ci_integration.py
    - |
      if [ "$QUALITY_GATE_PASSED" = "false" ]; then
        echo "Quality gate failed"
        exit 1
      fi
  
  artifacts:
    reports:
      junit: ci-reports/*.xml
    paths:
      - ci-reports/
    expire_in: 1 week
  
  only:
    - merge_requests
    - main
'''
    
    with open("example-gitlab-ci.yml", "w") as f:
        f.write(gitlab_ci)
    
    print("Created example CI/CD configurations:")
    print("  - example-github-workflow.yml")
    print("  - example-gitlab-ci.yml")


async def main():
    """Run CI/CD integration demonstrations."""
    print("🚀 CI/CD Integration Demonstration")
    print("=" * 60)
    
    try:
        # Run demonstrations
        github_result = await demo_github_actions_integration()
        gitlab_result = await demo_gitlab_ci_integration()
        scenario_results = await demo_quality_gate_scenarios()
        
        # Create example scripts
        create_ci_script_examples()
        
        print(f"\n✅ CI/CD integration demo completed!")
        print("\nKey features demonstrated:")
        print("  - CI environment detection")
        print("  - Quality gate evaluation")
        print("  - CI-specific configuration")
        print("  - Report generation for CI tools")
        print("  - PR/MR comment generation")
        print("  - CI output variable setting")
        print("  - Error handling and exit codes")
        
        print(f"\nQuality gate results:")
        print(f"  GitHub demo: {'PASSED' if github_result.quality_gate_passed else 'FAILED'}")
        print(f"  GitLab demo: {'PASSED' if gitlab_result.quality_gate_passed else 'FAILED'}")
        
        passed_scenarios = sum(1 for r in scenario_results if r.quality_gate_passed)
        print(f"  Scenarios: {passed_scenarios}/{len(scenario_results)} passed")
        
    except Exception as e:
        print(f"❌ CI/CD integration demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted by user")
        sys.exit(1)