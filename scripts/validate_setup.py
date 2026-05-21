#!/usr/bin/env python3
"""
Setup Validation Script
=======================

Validates that the NFL Betting System is properly set up.

Usage:
    python validate_setup.py

This script checks:
1. Python version (3.10-3.12)
2. Dependencies installed
3. Data directories exist
4. Optional: Data downloaded
5. Optional: Tests pass

Author: NFL Betting System
Date: 2025-01-27
"""

import subprocess
import sys
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_check(passed: bool, message: str):
    """Print a check result."""
    if passed:
        print(f"{Colors.GREEN}✓{Colors.END} {message}")
    else:
        print(f"{Colors.RED}✗{Colors.END} {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.END} {message}")


def check_python_version() -> bool:
    """Check if Python version is supported."""
    version = sys.version_info
    major, minor = version.major, version.minor
    
    supported = (major == 3 and 10 <= minor <= 12)
    
    if supported:
        print_check(True, f"Python {major}.{minor} (supported)")
    else:
        print_check(False, f"Python {major}.{minor} (unsupported)")
        print_warning("Recommended: Python 3.10, 3.11, or 3.12")
        print_warning("Python 3.13+ may have compatibility issues")
    
    return supported


def check_import(module_name: str, display_name: str = None) -> bool:
    """Check if a Python module can be imported."""
    if display_name is None:
        display_name = module_name
    
    try:
        __import__(module_name)
        print_check(True, f"{display_name} installed")
        return True
    except ImportError:
        print_check(False, f"{display_name} NOT installed")
        return False


def check_dependencies() -> bool:
    """Check if all required dependencies are installed."""
    print_header("Checking Dependencies")
    
    deps = [
        ('nflreadpy', 'nflreadpy'),
        ('polars', 'polars'),
        ('pandas', 'pandas'),
        ('pyarrow', 'pyarrow'),
        ('numpy', 'numpy'),
        ('xgboost', 'xgboost'),
        ('sklearn', 'scikit-learn'),
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        ('requests', 'requests'),
        ('pytest', 'pytest'),
    ]
    
    results = []
    for module, display in deps:
        results.append(check_import(module, display))
    
    all_installed = all(results)
    
    if not all_installed:
        print(f"\n{Colors.YELLOW}To install missing dependencies:{Colors.END}")
        print("  pip install -r requirements.txt")
    
    return all_installed


def check_directories() -> bool:
    """Check if required directories exist."""
    print_header("Checking Project Structure")
    
    dirs = [
        'src',
        'scripts',
        'tests',
        'data',
        'data/raw',
    ]
    
    results = []
    for dir_path in dirs:
        path = Path(dir_path)
        exists = path.exists() and path.is_dir()
        print_check(exists, f"Directory: {dir_path}/")
        results.append(exists)
    
    return all(results)


def check_files() -> bool:
    """Check if required files exist."""
    print_header("Checking Core Files")
    
    files = [
        'requirements.txt',
        'pytest.ini',
        'README.md',
        'src/data_pipeline.py',
        'scripts/download_data.py',
        'tests/test_data_pipeline.py',
    ]
    
    results = []
    for file_path in files:
        path = Path(file_path)
        exists = path.exists() and path.is_file()
        print_check(exists, f"File: {file_path}")
        results.append(exists)
    
    return all(results)


def check_data_downloaded() -> bool:
    """Check if data has been downloaded."""
    print_header("Checking Downloaded Data (Optional)")
    
    data_files = [
        'data/raw/schedules_2016_2024.parquet',
        'data/raw/pbp_2016_2024.parquet',
        'data/raw/weekly_offense_2016_2024.parquet',
        'data/raw/teams.parquet',
        'data/raw/metadata.json',
    ]
    
    results = []
    for file_path in data_files:
        path = Path(file_path)
        exists = path.exists() and path.is_file()
        
        if exists:
            # Show file size
            size_mb = path.stat().st_size / (1024 * 1024)
            print_check(True, f"{file_path} ({size_mb:.1f} MB)")
        else:
            print_check(False, f"{file_path} (not found)")
        
        results.append(exists)
    
    if not all(results):
        print(f"\n{Colors.YELLOW}To download data:{Colors.END}")
        print("  python scripts/download_data.py")
    
    return all(results)


def run_tests() -> bool:
    """Run the test suite."""
    print_header("Running Tests (Optional)")
    
    try:
        print("Running pytest...")
        result = subprocess.run(
            ['python', '-m', 'pytest', 'tests/', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print_check(True, "All tests passed")
            
            # Count tests
            output = result.stdout
            if 'passed' in output:
                import re
                match = re.search(r'(\d+) passed', output)
                if match:
                    count = match.group(1)
                    print(f"  {count} tests passed")
            
            return True
        else:
            print_check(False, "Some tests failed")
            print("\nTest output:")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return False
            
    except subprocess.TimeoutExpired:
        print_check(False, "Tests timed out (>60s)")
        return False
    except FileNotFoundError:
        print_check(False, "pytest not found")
        print_warning("Install with: pip install pytest")
        return False
    except Exception as e:
        print_check(False, f"Error running tests: {e}")
        return False


def print_summary(results: dict):
    """Print a summary of validation results."""
    print_header("Validation Summary")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for check, result in results.items():
        print_check(result, check)
    
    print(f"\n{Colors.BOLD}Score: {passed}/{total} checks passed{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Setup is complete! Ready to build.{Colors.END}\n")
        print("Next steps:")
        print("  1. Download data: python scripts/download_data.py")
        print("  2. Explore data: python -c 'import pandas as pd; df = pd.read_parquet(\"data/raw/schedules_2016_2024.parquet\"); print(df.head())'")
        print("  3. Start Day 3-4: Feature engineering")
    elif passed >= total * 0.7:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Setup is mostly complete, but needs attention.{Colors.END}\n")
        print("Review failed checks above and install missing components.")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Setup is incomplete.{Colors.END}\n")
        print("Follow the setup guide:")
        print("  1. Create virtual environment: py -3.12 -m venv .venv")
        print("  2. Activate: .venv\\Scripts\\activate")
        print("  3. Install dependencies: pip install -r requirements.txt")
        print("  4. Run this script again: python validate_setup.py")


def main():
    """Main entry point."""
    print(f"\n{Colors.BOLD}NFL Betting System - Setup Validation{Colors.END}")
    print(f"{'='*70}\n")
    
    results = {}
    
    # Critical checks
    results['Python version (3.10-3.12)'] = check_python_version()
    results['Dependencies installed'] = check_dependencies()
    results['Directories exist'] = check_directories()
    results['Core files exist'] = check_files()
    
    # Optional checks
    data_downloaded = check_data_downloaded()
    results['Data downloaded (optional)'] = data_downloaded
    
    # Only run tests if basic setup is complete
    if all([results['Python version (3.10-3.12)'], 
            results['Dependencies installed'],
            results['Core files exist']]):
        tests_passed = run_tests()
        results['Tests passing (optional)'] = tests_passed
    else:
        print_header("Skipping Tests (Optional)")
        print_warning("Fix critical issues above before running tests")
        results['Tests passing (optional)'] = False
    
    # Print summary
    print_summary(results)
    
    # Exit code
    critical_checks = [
        results['Python version (3.10-3.12)'],
        results['Dependencies installed'],
        results['Directories exist'],
        results['Core files exist'],
    ]
    
    if all(critical_checks):
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure


if __name__ == "__main__":
    main()

