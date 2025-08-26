#!/usr/bin/env python3
"""
Comprehensive test runner for the Migration Assistant.

This script runs all test suites including unit tests, integration tests,
performance benchmarks, and Go tests with coverage reporting.
"""

import os
import sys
import subprocess
import argparse
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Test configuration
TEST_CONFIG = {
    "unit_tests": {
        "command": ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        "coverage": True,
        "timeout": 300
    },
    "integration_tests": {
        "command": ["python", "-m", "pytest", "tests/", "-v", "-m", "integration"],
        "coverage": True,
        "timeout": 600,
        "requires_docker": True
    },
    "performance_tests": {
        "command": ["python", "-m", "pytest", "tests/", "-v", "-m", "benchmark", "--benchmark-only"],
        "coverage": False,
        "timeout": 900,
        "requires_docker": True
    },
    "go_tests": {
        "command": ["go", "test", "./...", "-v", "-race", "-coverprofile=coverage.out"],
        "coverage": True,
        "timeout": 300,
        "working_dir": "go-engine"
    },
    "go_benchmarks": {
        "command": ["go", "test", "./...", "-v", "-bench=.", "-benchmem"],
        "coverage": False,
        "timeout": 600,
        "working_dir": "go-engine"
    }
}

class TestRunner:
    """Comprehensive test runner."""
    
    def __init__(self, verbose: bool = False, coverage: bool = True):
        self.verbose = verbose
        self.coverage = coverage
        self.results = {}
        self.start_time = time.time()
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        if self.verbose or level in ["ERROR", "WARNING"]:
            print(f"[{timestamp}] {level}: {message}")
    
    def check_docker(self) -> bool:
        """Check if Docker is available and running."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def start_test_environment(self) -> bool:
        """Start Docker test environment."""
        self.log("Starting test environment...")
        
        try:
            # Start test services
            result = subprocess.run([
                "docker-compose", "-f", "docker-compose.test.yml",
                "up", "-d", "--build"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                self.log(f"Failed to start test environment: {result.stderr}", "ERROR")
                return False
            
            # Wait for services to be healthy
            self.log("Waiting for services to be ready...")
            time.sleep(30)
            
            # Check service health
            health_check = subprocess.run([
                "docker-compose", "-f", "docker-compose.test.yml",
                "ps", "--format", "json"
            ], capture_output=True, text=True)
            
            if health_check.returncode == 0:
                services = json.loads(health_check.stdout)
                unhealthy = [s for s in services if s.get("Health") == "unhealthy"]
                if unhealthy:
                    self.log(f"Unhealthy services: {[s['Name'] for s in unhealthy]}", "WARNING")
            
            return True
            
        except subprocess.TimeoutExpired:
            self.log("Timeout starting test environment", "ERROR")
            return False
        except Exception as e:
            self.log(f"Error starting test environment: {e}", "ERROR")
            return False
    
    def stop_test_environment(self):
        """Stop Docker test environment."""
        self.log("Stopping test environment...")
        
        try:
            subprocess.run([
                "docker-compose", "-f", "docker-compose.test.yml",
                "down", "-v"
            ], capture_output=True, text=True, timeout=60)
        except Exception as e:
            self.log(f"Error stopping test environment: {e}", "WARNING")
    
    def run_test_suite(self, suite_name: str, config: Dict) -> Tuple[bool, Dict]:
        """Run a specific test suite."""
        self.log(f"Running {suite_name}...")
        
        start_time = time.time()
        
        # Prepare command
        command = config["command"].copy()
        if self.coverage and config.get("coverage", False):
            if "pytest" in command[0]:
                command.extend(["--cov=migration_assistant", "--cov-report=xml", "--cov-report=html"])
        
        # Set working directory
        working_dir = config.get("working_dir", ".")
        
        try:
            # Run the test suite
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=config.get("timeout", 300)
            )
            
            duration = time.time() - start_time
            success = result.returncode == 0
            
            test_result = {
                "success": success,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
            if success:
                self.log(f"{suite_name} completed successfully in {duration:.2f}s")
            else:
                self.log(f"{suite_name} failed in {duration:.2f}s", "ERROR")
                if self.verbose:
                    self.log(f"STDOUT: {result.stdout}")
                    self.log(f"STDERR: {result.stderr}")
            
            return success, test_result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.log(f"{suite_name} timed out after {duration:.2f}s", "ERROR")
            return False, {
                "success": False,
                "duration": duration,
                "error": "timeout",
                "timeout": config.get("timeout", 300)
            }
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"{suite_name} failed with exception: {e}", "ERROR")
            return False, {
                "success": False,
                "duration": duration,
                "error": str(e)
            }
    
    def generate_coverage_report(self):
        """Generate combined coverage report."""
        if not self.coverage:
            return
        
        self.log("Generating coverage reports...")
        
        try:
            # Python coverage
            subprocess.run([
                "python", "-m", "coverage", "combine"
            ], capture_output=True)
            
            subprocess.run([
                "python", "-m", "coverage", "report", "--show-missing"
            ], capture_output=True)
            
            subprocess.run([
                "python", "-m", "coverage", "html", "-d", "htmlcov"
            ], capture_output=True)
            
            # Go coverage (if available)
            go_coverage_file = Path("go-engine/coverage.out")
            if go_coverage_file.exists():
                subprocess.run([
                    "go", "tool", "cover", "-html=coverage.out", "-o", "go-coverage.html"
                ], cwd="go-engine", capture_output=True)
            
            self.log("Coverage reports generated")
            
        except Exception as e:
            self.log(f"Error generating coverage reports: {e}", "WARNING")
    
    def run_all_tests(self, suites: Optional[List[str]] = None) -> bool:
        """Run all or specified test suites."""
        if suites is None:
            suites = list(TEST_CONFIG.keys())
        
        # Check Docker availability for tests that need it
        docker_available = self.check_docker()
        docker_required = any(
            TEST_CONFIG[suite].get("requires_docker", False) 
            for suite in suites
        )
        
        if docker_required and not docker_available:
            self.log("Docker is required but not available", "ERROR")
            return False
        
        # Start test environment if needed
        if docker_required:
            if not self.start_test_environment():
                return False
        
        try:
            all_success = True
            
            for suite_name in suites:
                if suite_name not in TEST_CONFIG:
                    self.log(f"Unknown test suite: {suite_name}", "WARNING")
                    continue
                
                config = TEST_CONFIG[suite_name]
                
                # Skip Docker-dependent tests if Docker not available
                if config.get("requires_docker", False) and not docker_available:
                    self.log(f"Skipping {suite_name} (Docker not available)", "WARNING")
                    continue
                
                success, result = self.run_test_suite(suite_name, config)
                self.results[suite_name] = result
                
                if not success:
                    all_success = False
            
            # Generate coverage reports
            if self.coverage:
                self.generate_coverage_report()
            
            return all_success
            
        finally:
            if docker_required:
                self.stop_test_environment()
    
    def print_summary(self):
        """Print test results summary."""
        total_time = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        
        total_suites = len(self.results)
        successful_suites = sum(1 for r in self.results.values() if r["success"])
        
        print(f"Total test suites: {total_suites}")
        print(f"Successful: {successful_suites}")
        print(f"Failed: {total_suites - successful_suites}")
        print(f"Total time: {total_time:.2f}s")
        print()
        
        for suite_name, result in self.results.items():
            status = "✓ PASS" if result["success"] else "✗ FAIL"
            duration = result.get("duration", 0)
            print(f"{status} {suite_name:<20} ({duration:.2f}s)")
            
            if not result["success"] and "error" in result:
                print(f"    Error: {result['error']}")
        
        print("\n" + "="*60)
        
        if self.coverage:
            print("Coverage reports generated:")
            print("  - Python: htmlcov/index.html")
            if Path("go-engine/go-coverage.html").exists():
                print("  - Go: go-engine/go-coverage.html")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run comprehensive tests")
    parser.add_argument(
        "--suites", 
        nargs="+", 
        choices=list(TEST_CONFIG.keys()),
        help="Test suites to run (default: all)"
    )
    parser.add_argument(
        "--no-coverage", 
        action="store_true",
        help="Disable coverage reporting"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="List available test suites"
    )
    
    args = parser.parse_args()
    
    if args.list_suites:
        print("Available test suites:")
        for suite_name, config in TEST_CONFIG.items():
            requires_docker = " (requires Docker)" if config.get("requires_docker") else ""
            print(f"  - {suite_name}{requires_docker}")
        return 0
    
    # Create test runner
    runner = TestRunner(
        verbose=args.verbose,
        coverage=not args.no_coverage
    )
    
    # Run tests
    success = runner.run_all_tests(args.suites)
    
    # Print summary
    runner.print_summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())