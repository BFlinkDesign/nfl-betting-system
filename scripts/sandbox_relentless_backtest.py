#!/usr/bin/env python3
"""
Relentless Backtest Runner
Runs backtests continuously to stress test the system.
"""

import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def run_backtest(script_path):
    """Run a backtest script."""
    print(f"\n{'='*70}")
    print(f"Running: {script_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per backtest
        )
        
        if result.stdout:
            # Print last 500 chars to avoid spam
            output = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            print(output)
        
        if result.returncode == 0:
            print(f"\n[SUCCESS] {script_path} completed")
            return True
        else:
            print(f"\n[WARNING] {script_path} completed with exit code {result.returncode}")
            if result.stderr:
                print(f"Errors: {result.stderr[-200:]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"\n[ERROR] {script_path} timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"\n[ERROR] {script_path} failed: {e}")
        return False

def main():
    """Run backtests relentlessly."""
    print("\n" + "="*70)
    print("RELENTLESS BACKTEST RUNNER")
    print("="*70)
    print("\nThis will run backtests continuously.")
    print("Press Ctrl+C to stop.\n")
    
    # Find all backtest scripts
    backtest_scripts = [
        "scripts/backtest.py",
        "scripts/bulldog_backtest.py",
        "tests/test_sandbox.py"
    ]
    
    available_scripts = [s for s in backtest_scripts if Path(s).exists()]
    
    if not available_scripts:
        print("[ERROR] No backtest scripts found!")
        return 1
    
    print(f"Found {len(available_scripts)} backtest script(s):")
    for script in available_scripts:
        print(f"  - {script}")
    
    print("\nStarting relentless backtesting...\n")
    
    iteration = 1
    success_count = 0
    fail_count = 0
    
    try:
        while True:
            print(f"\n{'#'*70}")
            print(f"BACKTEST ITERATION #{iteration}")
            print(f"{'#'*70}")
            
            for script in available_scripts:
                success = run_backtest(script)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                
                time.sleep(5)  # Brief pause between scripts
            
            iteration += 1
            
            print(f"\n[STATS] Iteration {iteration-1} complete")
            print(f"  Successes: {success_count}")
            print(f"  Failures: {fail_count}")
            print(f"  Success Rate: {success_count/(success_count+fail_count)*100:.1f}%" if (success_count+fail_count) > 0 else "  Success Rate: N/A")
            
            print(f"\nWaiting 30 seconds before next iteration...")
            time.sleep(30)
            
    except KeyboardInterrupt:
        print(f"\n\n[STOPPED] Backtest loop interrupted by user")
        print(f"\nFinal Stats:")
        print(f"  Total Iterations: {iteration-1}")
        print(f"  Total Successes: {success_count}")
        print(f"  Total Failures: {fail_count}")
        if (success_count + fail_count) > 0:
            print(f"  Overall Success Rate: {success_count/(success_count+fail_count)*100:.1f}%")
        return 0

if __name__ == "__main__":
    sys.exit(main())

