#!/usr/bin/env python3
"""
Comprehensive codebase structure and syntax test.
Tests the entire codebase without requiring external dependencies.
"""

import ast
import sys
import os
from pathlib import Path
import importlib.util


class CodebaseAnalyzer:
    """Analyze the codebase structure and quality."""
    
    def __init__(self):
        self.results = {
            'files_analyzed': 0,
            'syntax_errors': [],
            'import_errors': [],
            'class_count': 0,
            'function_count': 0,
            'line_count': 0,
            'docstring_coverage': 0,
            'complexity_issues': []
        }
    
    def analyze_file(self, file_path):
        """Analyze a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the AST
            tree = ast.parse(content, filename=str(file_path))
            
            # Count elements
            classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            self.results['class_count'] += len(classes)
            self.results['function_count'] += len(functions)
            self.results['line_count'] += len(content.splitlines())
            
            # Check docstring coverage
            documented_classes = sum(1 for cls in classes if ast.get_docstring(cls))
            documented_functions = sum(1 for func in functions if ast.get_docstring(func))
            
            total_items = len(classes) + len(functions)
            if total_items > 0:
                documented_items = documented_classes + documented_functions
                coverage = (documented_items / total_items) * 100
                self.results['docstring_coverage'] += coverage
            
            # Check for complexity issues
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Count nested levels
                    max_depth = self._calculate_nesting_depth(node)
                    if max_depth > 4:  # Arbitrary threshold
                        self.results['complexity_issues'].append(
                            f"{file_path}:{node.lineno} - Function '{node.name}' has high nesting depth ({max_depth})"
                        )
            
            return True
            
        except SyntaxError as e:
            self.results['syntax_errors'].append(f"{file_path}:{e.lineno} - {e.msg}")
            return False
        except Exception as e:
            self.results['syntax_errors'].append(f"{file_path} - {str(e)}")
            return False
    
    def _calculate_nesting_depth(self, node, depth=0):
        """Calculate maximum nesting depth of a function."""
        max_depth = depth
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_depth = self._calculate_nesting_depth(child, depth + 1)
                max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def analyze_codebase(self):
        """Analyze the entire codebase."""
        print("🔍 Analyzing Codebase Structure...")
        
        # Find all Python files
        python_files = []
        
        # Core migration assistant files
        migration_assistant_dir = Path("migration_assistant")
        if migration_assistant_dir.exists():
            python_files.extend(migration_assistant_dir.rglob("*.py"))
        
        # Test files
        tests_dir = Path("tests")
        if tests_dir.exists():
            python_files.extend(tests_dir.rglob("*.py"))
        
        # Example files
        examples_dir = Path("examples")
        if examples_dir.exists():
            python_files.extend(examples_dir.rglob("*.py"))
        
        # Root level Python files
        for file_path in Path(".").glob("*.py"):
            python_files.append(file_path)
        
        print(f"Found {len(python_files)} Python files to analyze")
        
        # Analyze each file
        successful_files = 0
        for file_path in python_files:
            if self.analyze_file(file_path):
                successful_files += 1
            self.results['files_analyzed'] += 1
        
        # Calculate averages
        if self.results['files_analyzed'] > 0:
            self.results['docstring_coverage'] /= self.results['files_analyzed']
        
        print(f"✅ Successfully analyzed {successful_files}/{len(python_files)} files")
        
        return successful_files == len(python_files)


def test_file_structure():
    """Test that all expected files exist."""
    print("\n📁 Testing File Structure...")
    
    expected_files = [
        # Core platform files
        "migration_assistant/platforms/__init__.py",
        "migration_assistant/platforms/base.py",
        "migration_assistant/platforms/cms.py",
        "migration_assistant/platforms/factory.py",
        
        # Advanced feature files
        "migration_assistant/core/cms_exceptions.py",
        "migration_assistant/utils/cms_utils.py",
        "migration_assistant/validators/cms_validator.py",
        "migration_assistant/orchestrators/cms_migration_orchestrator.py",
        "migration_assistant/monitoring/cms_metrics.py",
        "migration_assistant/api/cms_endpoints.py",
        
        # Documentation files
        "docs/cms-platforms.md",
        "docs/api-reference.md",
        "docs/user-guide/advanced-cms-migration.md",
        "docs/QUICK_START.md",
        
        # Test files
        "tests/test_cms_platforms.py",
        "tests/test_full_codebase.py",
        "tests/test_performance_benchmarks.py",
        "tests/test_api_integration.py",
        
        # Example files
        "examples/cms_platform_demo.py",
        
        # Root files
        "README.md",
        "CHANGELOG.md",
        "verify_cms_support.py"
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in expected_files:
        if Path(file_path).exists():
            existing_files.append(file_path)
            print(f"  ✅ {file_path}")
        else:
            missing_files.append(file_path)
            print(f"  ❌ {file_path} - Missing")
    
    print(f"\nFile Structure Summary:")
    print(f"  Existing: {len(existing_files)}")
    print(f"  Missing: {len(missing_files)}")
    
    return len(missing_files) == 0


def test_class_definitions():
    """Test that all expected classes are defined."""
    print("\n🏗️  Testing Class Definitions...")
    
    expected_classes = {
        "migration_assistant/platforms/cms.py": [
            "CMSAdapter", "WordPressAdapter", "DrupalAdapter", "JoomlaAdapter",
            "MagentoAdapter", "ShopwareAdapter", "PrestaShopAdapter", "OpenCartAdapter",
            "GhostAdapter", "CraftCMSAdapter", "Typo3Adapter", "Concrete5Adapter", "UmbracoAdapter"
        ],
        "migration_assistant/core/cms_exceptions.py": [
            "CMSError", "CMSDetectionError", "CMSVersionError", "CMSConfigurationError",
            "CMSDatabaseError", "CMSMigrationError", "CMSCompatibilityError"
        ],
        "migration_assistant/utils/cms_utils.py": [
            "CMSVersionParser", "CMSConfigParser", "CMSFileAnalyzer", 
            "CMSSecurityAnalyzer", "CMSMigrationPlanner"
        ],
        "migration_assistant/validators/cms_validator.py": [
            "CMSHealthChecker", "CMSCompatibilityChecker"
        ],
        "migration_assistant/orchestrators/cms_migration_orchestrator.py": [
            "CMSMigrationOrchestrator"
        ],
        "migration_assistant/monitoring/cms_metrics.py": [
            "CMSPerformanceMonitor", "CMSMetricsCollector"
        ]
    }
    
    all_classes_found = True
    
    for file_path, expected_class_list in expected_classes.items():
        if not Path(file_path).exists():
            print(f"  ❌ {file_path} - File missing")
            all_classes_found = False
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            found_classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            
            print(f"\n  📄 {file_path}:")
            for expected_class in expected_class_list:
                if expected_class in found_classes:
                    print(f"    ✅ {expected_class}")
                else:
                    print(f"    ❌ {expected_class} - Missing")
                    all_classes_found = False
                    
        except Exception as e:
            print(f"  ❌ {file_path} - Error parsing: {e}")
            all_classes_found = False
    
    return all_classes_found


def test_function_definitions():
    """Test that key functions are defined."""
    print("\n⚙️  Testing Key Function Definitions...")
    
    key_functions = {
        "migration_assistant/platforms/factory.py": [
            "get_available_platforms", "create_adapter", "detect_platform",
            "validate_platform_compatibility", "get_migration_complexity"
        ]
    }
    
    all_functions_found = True
    
    for file_path, expected_function_list in key_functions.items():
        if not Path(file_path).exists():
            print(f"  ❌ {file_path} - File missing")
            all_functions_found = False
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            found_functions = []
            
            # Get functions from classes and module level
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    found_functions.append(node.name)
                elif isinstance(node, ast.AsyncFunctionDef):  # Include async functions
                    found_functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            found_functions.append(item.name)
            
            print(f"\n  📄 {file_path}:")
            for expected_function in expected_function_list:
                if expected_function in found_functions:
                    print(f"    ✅ {expected_function}")
                else:
                    print(f"    ❌ {expected_function} - Missing")
                    all_functions_found = False
                    
        except Exception as e:
            print(f"  ❌ {file_path} - Error parsing: {e}")
            all_functions_found = False
    
    return all_functions_found


def test_documentation_completeness():
    """Test documentation completeness."""
    print("\n📚 Testing Documentation Completeness...")
    
    doc_files = [
        "README.md",
        "CHANGELOG.md", 
        "docs/cms-platforms.md",
        "docs/api-reference.md",
        "docs/user-guide/advanced-cms-migration.md",
        "docs/QUICK_START.md"
    ]
    
    all_docs_complete = True
    
    for doc_file in doc_files:
        if not Path(doc_file).exists():
            print(f"  ❌ {doc_file} - Missing")
            all_docs_complete = False
            continue
        
        try:
            content = Path(doc_file).read_text(encoding='utf-8')
            
            # Check minimum content length
            if len(content) < 1000:  # At least 1KB of content
                print(f"  ⚠️  {doc_file} - Too short ({len(content)} chars)")
                all_docs_complete = False
            else:
                print(f"  ✅ {doc_file} - Complete ({len(content)} chars)")
                
        except Exception as e:
            print(f"  ❌ {doc_file} - Error reading: {e}")
            all_docs_complete = False
    
    return all_docs_complete


def main():
    """Run comprehensive codebase tests."""
    print("🚀 CMS Migration Assistant - Codebase Structure Test")
    print("=" * 70)
    
    # Initialize analyzer
    analyzer = CodebaseAnalyzer()
    
    # Run tests
    tests = [
        ("File Structure", test_file_structure),
        ("Class Definitions", test_class_definitions),
        ("Function Definitions", test_function_definitions),
        ("Documentation Completeness", test_documentation_completeness),
    ]
    
    results = []
    all_passed = True
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            if not success:
                all_passed = False
        except Exception as e:
            print(f"  ❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
            all_passed = False
    
    # Run codebase analysis
    print("\n🔍 Running Codebase Analysis...")
    analysis_success = analyzer.analyze_codebase()
    results.append(("Codebase Analysis", analysis_success))
    if not analysis_success:
        all_passed = False
    
    # Print detailed analysis results
    print(f"\n📊 Codebase Analysis Results:")
    print(f"  Files Analyzed: {analyzer.results['files_analyzed']}")
    print(f"  Classes Found: {analyzer.results['class_count']}")
    print(f"  Functions Found: {analyzer.results['function_count']}")
    print(f"  Total Lines: {analyzer.results['line_count']:,}")
    print(f"  Docstring Coverage: {analyzer.results['docstring_coverage']:.1f}%")
    
    if analyzer.results['syntax_errors']:
        print(f"\n❌ Syntax Errors ({len(analyzer.results['syntax_errors'])}):")
        for error in analyzer.results['syntax_errors'][:5]:  # Show first 5
            print(f"  {error}")
        if len(analyzer.results['syntax_errors']) > 5:
            print(f"  ... and {len(analyzer.results['syntax_errors']) - 5} more")
    
    if analyzer.results['complexity_issues']:
        print(f"\n⚠️  Complexity Issues ({len(analyzer.results['complexity_issues'])}):")
        for issue in analyzer.results['complexity_issues'][:3]:  # Show first 3
            print(f"  {issue}")
        if len(analyzer.results['complexity_issues']) > 3:
            print(f"  ... and {len(analyzer.results['complexity_issues']) - 3} more")
    
    # Print final summary
    print("\n" + "=" * 70)
    print("📊 CODEBASE TEST SUMMARY")
    print("=" * 70)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    if all_passed:
        print(f"\n🎉 ALL CODEBASE TESTS PASSED!")
        print("   The codebase structure is complete and well-formed!")
        print(f"\n📈 Codebase Statistics:")
        print(f"   • {analyzer.results['files_analyzed']} Python files")
        print(f"   • {analyzer.results['class_count']} classes")
        print(f"   • {analyzer.results['function_count']} functions")
        print(f"   • {analyzer.results['line_count']:,} lines of code")
        print(f"   • {analyzer.results['docstring_coverage']:.1f}% documented")
        print(f"   • {len(analyzer.results['syntax_errors'])} syntax errors")
        print(f"   • {len(analyzer.results['complexity_issues'])} complexity issues")
    else:
        print(f"\n⚠️  SOME CODEBASE TESTS FAILED")
        print("   Please review the failed tests above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())