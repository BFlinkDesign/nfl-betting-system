#!/usr/bin/env python3
"""
Sandbox Environment Setup
Installs requirements, configures system, and runs backtests.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_step(step_num, total, message):
    """Print formatted step message."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}[{step_num}/{total}]{Colors.END} {message}")

def print_success(message):
    """Print success message."""
    try:
        print(f"{Colors.GREEN}[OK] {message}{Colors.END}")
    except UnicodeEncodeError:
        print(f"[OK] {message}")

def print_error(message):
    """Print error message."""
    try:
        print(f"{Colors.RED}[FAIL] {message}{Colors.END}")
    except UnicodeEncodeError:
        print(f"[FAIL] {message}")

def print_warning(message):
    """Print warning message."""
    try:
        print(f"{Colors.YELLOW}[WARN] {message}{Colors.END}")
    except UnicodeEncodeError:
        print(f"[WARN] {message}")

def run_command(cmd, check=True, shell=False):
    """Run a shell command."""
    try:
        if isinstance(cmd, str):
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True, shell=shell)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except Exception as e:
        return False, "", str(e)

def check_python_version():
    """Check Python version."""
    print_step(1, 6, "Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
        return True
    else:
        print_error(f"Python 3.10+ required, found {version.major}.{version.minor}")
        return False

def install_requirements():
    """Install all requirements."""
    print_step(2, 6, "Installing requirements...")
    
    requirements_files = [
        "requirements.txt",
        "dashboard/requirements.txt"
    ]
    
    for req_file in requirements_files:
        if Path(req_file).exists():
            print(f"  Installing {req_file}...")
            success, stdout, stderr = run_command(f"pip install -r {req_file}")
            if success:
                print_success(f"Installed {req_file}")
            else:
                print_error(f"Failed to install {req_file}: {stderr}")
                return False
        else:
            print_warning(f"{req_file} not found, skipping")
    
    return True

def verify_dependencies():
    """Verify critical dependencies."""
    print_step(3, 6, "Verifying dependencies...")
    
    critical_deps = [
        ("streamlit", "streamlit"),
        ("psutil", "psutil"),
        ("nflreadpy", "nflreadpy"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("xgboost", "xgboost"),
        ("scikit-learn", "sklearn"),  # scikit-learn imports as sklearn
        ("plotly", "plotly")
    ]
    
    missing = []
    for dep_name, import_name in critical_deps:
        try:
            __import__(import_name)
            print_success(f"{dep_name} installed")
        except ImportError:
            print_error(f"{dep_name} missing")
            missing.append(dep_name)
    
    if missing:
        print_error(f"Missing dependencies: {', '.join(missing)}")
        return False
    
    return True

def configure_system():
    """Configure system (API keys, directories, etc.)."""
    print_step(4, 6, "Configuring system...")
    
    # Create necessary directories
    directories = [
        "data/raw",
        "data/processed",
        "data/schedules",
        "data/odds_cache",
        "logs",
        "models",
        "reports"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print_success(f"Directory ready: {dir_path}")
    
    # Check API keys
    api_keys_file = Path("config/api_keys.env")
    if not api_keys_file.exists():
        print_warning("API keys file not found")
        template = Path("config/api_keys.env.template")
        if template.exists():
            print("  Creating from template...")
            import shutil
            shutil.copy(template, api_keys_file)
            print_success("Created config/api_keys.env (please add your keys)")
        else:
            print_error("Template not found")
    else:
        print_success("API keys file exists")
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv(api_keys_file)
        print_success("Environment variables loaded")
    except ImportError:
        print_warning("python-dotenv not installed, skipping env load")
    
    return True

def run_tests():
    """Run system tests."""
    print_step(5, 6, "Running system tests...")
    
    test_file = Path("test_system_simple.py")
    if test_file.exists():
        success, stdout, stderr = run_command(f"python {test_file}")
        if success:
            print_success("System tests passed")
            print(stdout)
            return True
        else:
            print_error(f"Tests failed: {stderr}")
            return False
    else:
        print_warning("Test file not found")
        return True

def run_backtests():
    """Run backtests relentlessly."""
    print_step(6, 6, "Running backtests...")
    
    backtest_scripts = [
        "scripts/bulldog_backtest.py",
        "scripts/full_betting_pipeline.py",
        "tests/test_sandbox.py"
    ]
    
    available_scripts = [s for s in backtest_scripts if Path(s).exists()]
    
    if not available_scripts:
        print_error("No backtest scripts found")
        return False
    
    print(f"\n{Colors.BOLD}Found {len(available_scripts)} backtest script(s){Colors.END}")
    
    # Run each backtest script
    for script in available_scripts:
        print(f"\n{Colors.BOLD}Running: {script}{Colors.END}")
        print("=" * 60)
        
        # Change to project root for proper imports
        import os
        original_dir = os.getcwd()
        os.chdir(Path(__file__).parent)
        
        try:
            success, stdout, stderr = run_command(f"python {script}", check=False)
            
            if stdout:
                # Print last 500 chars to avoid spam
                output = stdout[-500:] if len(stdout) > 500 else stdout
                print(output)
            if stderr and not success:
                print_error(f"Errors: {stderr[-200:]}")
            
            if success:
                print_success(f"Completed: {script}")
            else:
                print_warning(f"Completed with warnings: {script}")
        finally:
            os.chdir(original_dir)
        
        time.sleep(2)  # Brief pause between tests
    
    return True

def run_continuous_backtests():
    """Run backtests continuously."""
    print(f"\n{Colors.BOLD}{Colors.YELLOW}Starting continuous backtest loop...{Colors.END}")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    backtest_scripts = [
        "scripts/bulldog_backtest.py",
        "scripts/full_betting_pipeline.py",
        "tests/test_sandbox.py"
    ]
    
    available_scripts = [s for s in backtest_scripts if Path(s).exists()]
    
    if not available_scripts:
        print_error("No backtest scripts found for continuous testing")
        return
    
    import os
    original_dir = os.getcwd()
    os.chdir(Path(__file__).parent)
    
    iteration = 1
    success_count = 0
    fail_count = 0
    
    try:
        while True:
            print(f"\n{Colors.BOLD}Backtest Iteration #{iteration}{Colors.END}")
            print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Success Rate: {success_count/(success_count+fail_count)*100:.1f}%" if (success_count+fail_count) > 0 else "Success Rate: N/A")
            
            # Run all backtest scripts
            for script in available_scripts:
                print(f"\n  Running: {script}")
                success, stdout, stderr = run_command(f"python {script}", check=False)
                
                if stdout:
                    # Print last 300 chars
                    output = stdout[-300:] if len(stdout) > 300 else stdout
                    print(f"  {output}")
                
                if success:
                    success_count += 1
                    print_success(f"  {script} completed")
                else:
                    fail_count += 1
                    print_warning(f"  {script} completed with warnings")
                    if stderr:
                        print(f"  Errors: {stderr[-150:]}")
            
            iteration += 1
            print(f"\n{Colors.BLUE}Waiting 30 seconds before next iteration...{Colors.END}")
            time.sleep(30)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Stopped by user{Colors.END}")
        print(f"\nFinal Stats:")
        print(f"  Total Iterations: {iteration-1}")
        print(f"  Total Successes: {success_count}")
        print(f"  Total Failures: {fail_count}")
        if (success_count + fail_count) > 0:
            print(f"  Overall Success Rate: {success_count/(success_count+fail_count)*100:.1f}%")
    except Exception as e:
        print_error(f"Error in backtest loop: {e}")
    finally:
        os.chdir(original_dir)

def main():
    """Main setup and backtest function."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}NFL Betting System - Sandbox Setup & Backtest{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    # Setup phase
    if not check_python_version():
        return 1
    
    if not install_requirements():
        return 1
    
    if not verify_dependencies():
        return 1
    
    if not configure_system():
        return 1
    
    if not run_tests():
        print_warning("Tests failed, but continuing...")
    
    # Backtest phase
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}Setup Complete - Starting Backtests{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}\n")
    
    # Run initial backtests
    run_backtests()
    
    # Run continuous backtests automatically
    print(f"\n{Colors.BOLD}Starting continuous backtests...{Colors.END}")
    print(f"Press Ctrl+C to stop\n")
    run_continuous_backtests()
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}Sandbox setup and backtesting complete!{Colors.END}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())

