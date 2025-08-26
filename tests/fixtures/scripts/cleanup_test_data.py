#!/usr/bin/env python3
"""
Test data cleanup script for the Migration Assistant.

This script cleans up test data, containers, and temporary files
created during testing.
"""

import os
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import List


class TestDataCleaner:
    """Clean up test data and resources."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[CLEANUP] {message}")
    
    def cleanup_test_files(self, data_dir: str = "/data"):
        """Clean up generated test files."""
        data_path = Path(data_dir)
        
        if not data_path.exists():
            self.log(f"Data directory {data_dir} does not exist, skipping file cleanup")
            return
        
        self.log(f"Cleaning up test files in {data_dir}")
        
        # Remove test file directories
        test_dirs = [
            "test-files",
            "performance-tests",
            "benchmark_results.json",
            "coverage_reports",
            "test_logs"
        ]
        
        for test_dir in test_dirs:
            dir_path = data_path / test_dir
            if dir_path.exists():
                self.log(f"Removing {dir_path}")
                if dir_path.is_file():
                    dir_path.unlink()
                else:
                    shutil.rmtree(dir_path)
        
        # Clean up any remaining test files
        for item in data_path.iterdir():
            if item.name.startswith("test_") or item.name.endswith("_test"):
                self.log(f"Removing {item}")
                if item.is_file():
                    item.unlink()
                else:
                    shutil.rmtree(item)
    
    def cleanup_docker_containers(self):
        """Clean up Docker test containers."""
        self.log("Cleaning up Docker test containers")
        
        try:
            # Stop and remove test containers
            result = subprocess.run([
                "docker-compose", "-f", "docker-compose.test.yml", "down", "-v", "--remove-orphans"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.log("Docker containers cleaned up successfully")
            else:
                self.log(f"Docker cleanup warning: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            self.log("Docker cleanup timed out")
        except FileNotFoundError:
            self.log("Docker Compose not found, skipping container cleanup")
        except Exception as e:
            self.log(f"Error cleaning up Docker containers: {e}")
    
    def cleanup_docker_volumes(self):
        """Clean up Docker test volumes."""
        self.log("Cleaning up Docker test volumes")
        
        try:
            # List and remove test volumes
            result = subprocess.run([
                "docker", "volume", "ls", "-q", "--filter", "name=migration_test"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout.strip():
                volumes = result.stdout.strip().split('\n')
                for volume in volumes:
                    if volume:
                        self.log(f"Removing volume: {volume}")
                        subprocess.run([
                            "docker", "volume", "rm", volume
                        ], capture_output=True, timeout=30)
        
        except Exception as e:
            self.log(f"Error cleaning up Docker volumes: {e}")
    
    def cleanup_docker_networks(self):
        """Clean up Docker test networks."""
        self.log("Cleaning up Docker test networks")
        
        try:
            # List and remove test networks
            result = subprocess.run([
                "docker", "network", "ls", "-q", "--filter", "name=migration_test"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout.strip():
                networks = result.stdout.strip().split('\n')
                for network in networks:
                    if network:
                        self.log(f"Removing network: {network}")
                        subprocess.run([
                            "docker", "network", "rm", network
                        ], capture_output=True, timeout=30)
        
        except Exception as e:
            self.log(f"Error cleaning up Docker networks: {e}")
    
    def cleanup_test_databases(self):
        """Clean up test database data."""
        self.log("Cleaning up test database data")
        
        # This would connect to test databases and clean up test data
        # For now, we rely on Docker container cleanup
        pass
    
    def cleanup_coverage_reports(self):
        """Clean up coverage reports and test artifacts."""
        self.log("Cleaning up coverage reports and test artifacts")
        
        artifacts = [
            "htmlcov",
            "coverage.xml",
            ".coverage",
            ".pytest_cache",
            "__pycache__",
            "*.pyc",
            ".mypy_cache",
            "go-engine/coverage.out",
            "go-engine/go-coverage.html",
            "benchmark_results.json",
            "test_results.xml"
        ]
        
        for artifact in artifacts:
            if "*" in artifact:
                # Handle glob patterns
                import glob
                for file_path in glob.glob(artifact, recursive=True):
                    path = Path(file_path)
                    if path.exists():
                        self.log(f"Removing {path}")
                        if path.is_file():
                            path.unlink()
                        else:
                            shutil.rmtree(path)
            else:
                path = Path(artifact)
                if path.exists():
                    self.log(f"Removing {path}")
                    if path.is_file():
                        path.unlink()
                    else:
                        shutil.rmtree(path)
    
    def cleanup_log_files(self):
        """Clean up log files."""
        self.log("Cleaning up log files")
        
        log_patterns = [
            "*.log",
            "logs/*.log",
            "tests/logs/*",
            "/tmp/migration_*.log",
            "/tmp/test_*.log"
        ]
        
        import glob
        for pattern in log_patterns:
            for log_file in glob.glob(pattern, recursive=True):
                log_path = Path(log_file)
                if log_path.exists() and log_path.is_file():
                    self.log(f"Removing log file: {log_path}")
                    log_path.unlink()
    
    def cleanup_temp_files(self):
        """Clean up temporary files."""
        self.log("Cleaning up temporary files")
        
        import tempfile
        temp_dir = Path(tempfile.gettempdir())
        
        # Clean up migration-related temp files
        temp_patterns = [
            "migration_*",
            "test_*",
            "pytest_*",
            "coverage_*"
        ]
        
        for pattern in temp_patterns:
            for temp_path in temp_dir.glob(pattern):
                if temp_path.exists():
                    self.log(f"Removing temp file/dir: {temp_path}")
                    try:
                        if temp_path.is_file():
                            temp_path.unlink()
                        else:
                            shutil.rmtree(temp_path)
                    except Exception as e:
                        self.log(f"Error removing {temp_path}: {e}")
    
    def cleanup_go_artifacts(self):
        """Clean up Go build artifacts."""
        self.log("Cleaning up Go build artifacts")
        
        go_artifacts = [
            "go-engine/bin/migration-engine",
            "go-engine/coverage.out",
            "go-engine/go-coverage.html"
        ]
        
        for artifact in go_artifacts:
            path = Path(artifact)
            if path.exists():
                self.log(f"Removing Go artifact: {path}")
                path.unlink()
    
    def cleanup_all(self, data_dir: str = "/data"):
        """Clean up all test data and resources."""
        self.log("Starting comprehensive cleanup")
        
        # Clean up in order of dependencies
        self.cleanup_docker_containers()
        self.cleanup_docker_volumes()
        self.cleanup_docker_networks()
        self.cleanup_test_files(data_dir)
        self.cleanup_test_databases()
        self.cleanup_coverage_reports()
        self.cleanup_log_files()
        self.cleanup_temp_files()
        self.cleanup_go_artifacts()
        
        self.log("Cleanup completed")
    
    def verify_cleanup(self, data_dir: str = "/data"):
        """Verify that cleanup was successful."""
        self.log("Verifying cleanup")
        
        issues = []
        
        # Check for remaining test files
        data_path = Path(data_dir)
        if data_path.exists():
            remaining_files = list(data_path.glob("test_*")) + list(data_path.glob("*_test"))
            if remaining_files:
                issues.append(f"Remaining test files: {[str(f) for f in remaining_files[:5]]}")
        
        # Check for running test containers
        try:
            result = subprocess.run([
                "docker", "ps", "-q", "--filter", "name=migration_test"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                issues.append("Test containers still running")
        except Exception:
            pass
        
        # Check for coverage files
        coverage_files = [
            Path("htmlcov"),
            Path("coverage.xml"),
            Path(".coverage")
        ]
        
        remaining_coverage = [f for f in coverage_files if f.exists()]
        if remaining_coverage:
            issues.append(f"Remaining coverage files: {[str(f) for f in remaining_coverage]}")
        
        if issues:
            self.log("Cleanup verification found issues:")
            for issue in issues:
                self.log(f"  - {issue}")
            return False
        else:
            self.log("Cleanup verification passed")
            return True


def main():
    """Main function to clean up test data."""
    parser = argparse.ArgumentParser(description="Clean up test data and resources")
    parser.add_argument("--data-dir", default="/data", help="Test data directory to clean")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--verify", action="store_true", help="Verify cleanup was successful")
    parser.add_argument("--docker-only", action="store_true", help="Only clean up Docker resources")
    parser.add_argument("--files-only", action="store_true", help="Only clean up test files")
    
    args = parser.parse_args()
    
    cleaner = TestDataCleaner(verbose=args.verbose)
    
    if args.docker_only:
        cleaner.cleanup_docker_containers()
        cleaner.cleanup_docker_volumes()
        cleaner.cleanup_docker_networks()
    elif args.files_only:
        cleaner.cleanup_test_files(args.data_dir)
        cleaner.cleanup_coverage_reports()
        cleaner.cleanup_log_files()
        cleaner.cleanup_temp_files()
    else:
        cleaner.cleanup_all(args.data_dir)
    
    if args.verify:
        success = cleaner.verify_cleanup(args.data_dir)
        exit(0 if success else 1)


if __name__ == "__main__":
    main()