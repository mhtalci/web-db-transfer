#!/usr/bin/env python3
"""
Comprehensive test runner for the CMS Migration Assistant.
Runs all tests and generates detailed reports.
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path
from datetime import datetime
import platform


class TestRunner:
    """Comprehensive test runner with reporting."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.results = {
            'start_time': self.start_time.isoformat(),
            'test_suites': {},
            'summary': {},
            'system_info': self._get_system_info()
        }
    
    def _get_system_info(self):
        """Get system information for test context."""
        return {
            'python_version': sys.version,
            'platform': sys.platform,
            'architecture': platform.architecture(),
            'processor': platform.processor() or 'Unknown',
            'system': platform.system()
        }
    
    def run_test_suite(self, name, test_file, markers=None):
        """Run a specific test suite."""
        print(f"\n{'='*60}")
        print(f"🧪 Running {name}")
        print(f"{'='*60}")
        
        # Build pytest command
        cmd = ['python', '-m', 'pytest', test_file, '-v', '--tb=short']
        
        if markers:
            cmd.extend(['-m', markers])
        
        # Add coverage if available
        try:
            import coverage
            cmd.extend(['--cov=migration_assistant', '--cov-report=term-missing'])
        except ImportError:
            pass
        
        # Run tests
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per suite
            )
            
            duration = time.time() - start_time
            
            # Parse results
            output_lines = result.stdout.split('\n')
            
            # Extract test results
            passed = 0
            failed = 0
            errors = 0
            skipped = 0
            
            for line in output_lines:
                if ' passed' in line and ' failed' in line:
                    # Parse summary line like "5 passed, 2 failed in 1.23s"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'passed':
                            passed = int(parts[i-1])
                        elif part == 'failed':
                            failed = int(parts[i-1])
                        elif part == 'error':
                            errors = int(parts[i-1])
                        elif part == 'skipped':
                            skipped = int(parts[i-1])
                elif line.strip().endswith(' passed'):
                    # Simple case: "5 passed"
                    passed = int(line.strip().split()[0])
            
            success = result.returncode == 0
            
            self.results['test_suites'][name] = {
                'success': success,
                'duration': duration,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'skipped': skipped,
                'output': result.stdout,
                'error_output': result.stderr
            }
            
            # Print summary
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"\n{status} - {name}")
            print(f"Duration: {duration:.2f}s")
            print(f"Tests: {passed} passed, {failed} failed, {errors} errors, {skipped} skipped")
            
            if not success and result.stderr:
                print(f"Errors:\n{result.stderr}")
            
            return success
            
        except subprocess.TimeoutExpired:
            print(f"❌ TIMEOUT - {name} (exceeded 5 minutes)")
            self.results['test_suites'][name] = {
                'success': False,
                'duration': 300,
                'error': 'Test suite timed out'
            }
            return False
        
        except Exception as e:
            print(f"❌ ERROR - {name}: {e}")
            self.results['test_suites'][name] = {
                'success': False,
                'duration': time.time() - start_time,
                'error': str(e)
            }
            return False
    
    def run_all_tests(self):
        """Run all test suites."""
        print("🚀 Starting Comprehensive CMS Migration Assistant Test Suite")
        print(f"Start Time: {self.start_time}")
        print(f"Python Version: {sys.version}")
        print(f"Platform: {sys.platform}")
        
        # Define test suites
        test_suites = [
            ("Core Implementation Verification", "verify_cms_support.py", None),
            ("Unit Tests - CMS Platforms", "tests/test_cms_platforms.py", None),
            ("Full Codebase Tests", "tests/test_full_codebase.py", None),
            ("Performance Benchmarks", "tests/test_performance_benchmarks.py", None),
            ("API Integration Tests", "tests/test_api_integration.py", None),
        ]
        
        # Run each test suite
        all_passed = True
        for name, test_file, markers in test_suites:
            if Path(test_file).exists():
                success = self.run_test_suite(name, test_file, markers)
                if not success:
                    all_passed = False
            else:
                print(f"⚠️  Skipping {name} - {test_file} not found")
                self.results['test_suites'][name] = {
                    'success': False,
                    'skipped': True,
                    'reason': 'Test file not found'
                }
        
        # Generate final report
        self._generate_final_report(all_passed)
        
        return all_passed
    
    def _generate_final_report(self, all_passed):
        """Generate comprehensive final report."""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        self.results['end_time'] = end_time.isoformat()
        self.results['total_duration'] = total_duration
        
        # Calculate summary statistics
        total_passed = sum(suite.get('passed', 0) for suite in self.results['test_suites'].values())
        total_failed = sum(suite.get('failed', 0) for suite in self.results['test_suites'].values())
        total_errors = sum(suite.get('errors', 0) for suite in self.results['test_suites'].values())
        total_skipped = sum(suite.get('skipped', 0) for suite in self.results['test_suites'].values())
        
        suites_passed = sum(1 for suite in self.results['test_suites'].values() if suite.get('success', False))
        suites_total = len(self.results['test_suites'])
        
        self.results['summary'] = {
            'all_passed': all_passed,
            'total_duration': total_duration,
            'suites_passed': suites_passed,
            'suites_total': suites_total,
            'tests_passed': total_passed,
            'tests_failed': total_failed,
            'tests_errors': total_errors,
            'tests_skipped': total_skipped,
            'tests_total': total_passed + total_failed + total_errors + total_skipped
        }
        
        # Print final report
        print(f"\n{'='*80}")
        print("📊 COMPREHENSIVE TEST REPORT")
        print(f"{'='*80}")
        
        print(f"\n⏱️  Execution Summary:")
        print(f"   Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Total Duration: {total_duration:.2f} seconds ({total_duration/60:.1f} minutes)")
        
        print(f"\n🧪 Test Suite Results:")
        print(f"   Suites Passed: {suites_passed}/{suites_total}")
        for name, result in self.results['test_suites'].items():
            status = "✅" if result.get('success', False) else "❌"
            duration = result.get('duration', 0)
            print(f"   {status} {name:<35} ({duration:.2f}s)")
        
        print(f"\n📈 Test Statistics:")
        print(f"   Total Tests: {self.results['summary']['tests_total']}")
        print(f"   Passed: {total_passed}")
        print(f"   Failed: {total_failed}")
        print(f"   Errors: {total_errors}")
        print(f"   Skipped: {total_skipped}")
        
        if self.results['summary']['tests_total'] > 0:
            success_rate = (total_passed / self.results['summary']['tests_total']) * 100
            print(f"   Success Rate: {success_rate:.1f}%")
        
        print(f"\n💻 System Information:")
        sys_info = self.results['system_info']
        print(f"   Python: {sys_info['python_version'].split()[0]}")
        print(f"   Platform: {sys_info['platform']}")
        print(f"   System: {sys_info['system']}")
        print(f"   Architecture: {sys_info['architecture'][0]}")
        print(f"   Processor: {sys_info['processor']}")
        
        # Overall result
        if all_passed:
            print(f"\n🎉 ALL TESTS PASSED!")
            print("   The CMS Migration Assistant is ready for production!")
        else:
            print(f"\n⚠️  SOME TESTS FAILED")
            print("   Please review the failed tests above.")
        
        # Save detailed report
        self._save_report()
    
    def _save_report(self):
        """Save detailed test report to file."""
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            print(f"\n📄 Detailed report saved to: {report_file}")
            
        except Exception as e:
            print(f"⚠️  Could not save report: {e}")
    
    def run_quick_tests(self):
        """Run only quick tests for development."""
        print("🏃‍♂️ Running Quick Test Suite")
        
        quick_suites = [
            ("Core Verification", "verify_cms_support.py", None),
            ("Unit Tests", "tests/test_cms_platforms.py", "not slow"),
        ]
        
        all_passed = True
        for name, test_file, markers in quick_suites:
            if Path(test_file).exists():
                success = self.run_test_suite(name, test_file, markers)
                if not success:
                    all_passed = False
        
        return all_passed
    
    def run_performance_tests(self):
        """Run only performance tests."""
        print("⚡ Running Performance Test Suite")
        
        return self.run_test_suite(
            "Performance Benchmarks", 
            "tests/test_performance_benchmarks.py", 
            None
        )


def main():
    """Main test runner function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CMS Migration Assistant Test Runner")
    parser.add_argument(
        "--mode", 
        choices=["full", "quick", "performance"], 
        default="full",
        help="Test mode to run"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Set environment variables for testing
    os.environ['TESTING'] = '1'
    os.environ['PYTHONPATH'] = str(Path.cwd())
    
    runner = TestRunner()
    
    try:
        if args.mode == "full":
            success = runner.run_all_tests()
        elif args.mode == "quick":
            success = runner.run_quick_tests()
        elif args.mode == "performance":
            success = runner.run_performance_tests()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()