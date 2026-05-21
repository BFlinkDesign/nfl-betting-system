#!/usr/bin/env python3
"""
Simple system test script (Windows-compatible).
Tests all major components for import and basic functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_import(module_name, description):
    """Test if a module can be imported."""
    try:
        __import__(module_name)
        print(f"PASS: {description}")
        return True
    except Exception as e:
        print(f"FAIL: {description}: {e}")
        return False

def test_api_call(client_class, method_name, *args, **kwargs):
    """Test an API call."""
    try:
        client = client_class()
        result = getattr(client, method_name)(*args, **kwargs)
        print(f"PASS: {client_class.__name__}.{method_name}()")
        return True, result
    except Exception as e:
        print(f"FAIL: {client_class.__name__}.{method_name}(): {e}")
        return False, None

def main():
    """Run all tests."""
    print("=" * 60)
    print("SYSTEM TEST SUITE")
    print("=" * 60)
    print()
    
    results = []
    
    # Core API Clients
    print("API Clients:")
    results.append(test_import("src.api.espn_client", "ESPN Client"))
    results.append(test_import("src.api.noaa_client", "NOAA Client"))
    results.append(test_import("src.api.request_orchestrator", "Request Orchestrator"))
    print()
    
    # Data
    print("Data:")
    results.append(test_import("src.data.stadium_locations", "Stadium Locations"))
    print()
    
    # Utils
    print("Utilities:")
    results.append(test_import("src.utils.odds_cache", "Odds Cache"))
    results.append(test_import("src.utils.token_bucket", "Token Bucket"))
    print()
    
    # Infrastructure
    print("Infrastructure:")
    results.append(test_import("src.audit.system_connectivity_auditor", "Connectivity Auditor"))
    print()
    
    # API Tests
    print("API Tests:")
    try:
        from src.api.espn_client import ESPNClient
        success, data = test_api_call(ESPNClient, "get_scoreboard")
        if success and data:
            events = data.get('events', [])
            print(f"   Found {len(events)} games")
    except Exception as e:
        print(f"   ESPN API test failed: {e}")
    
    try:
        from src.api.noaa_client import NOAAClient
        success, data = test_api_call(NOAAClient, "get_forecast_for_location", 39.0489, -94.4839)
        if success and data:
            periods = data.get('properties', {}).get('periods', [])
            print(f"   Found {len(periods)} forecast periods")
    except Exception as e:
        print(f"   NOAA API test failed: {e}")
    print()
    
    # Configuration Check
    print("Configuration:")
    import os
    from pathlib import Path
    api_keys_file = Path("config/api_keys.env")
    if api_keys_file.exists():
        print(f"PASS: API keys file exists: {api_keys_file}")
    else:
        print(f"WARN: API keys file missing: {api_keys_file}")
    
    has_odds_key = bool(os.getenv('ODDS_API_KEY'))
    if has_odds_key:
        print("PASS: ODDS_API_KEY is set")
    else:
        print("WARN: ODDS_API_KEY not set (optional - ESPN/NOAA work without it)")
    print()
    
    # Dependencies Check
    print("Dependencies:")
    try:
        import psutil
        print("PASS: psutil installed")
    except ImportError:
        print("FAIL: psutil not installed - run: pip install psutil")
    
    try:
        import nflreadpy
        print("PASS: nflreadpy installed")
    except ImportError:
        print("WARN: nflreadpy not installed (optional - for data pipeline)")
    print()
    
    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} core tests passed")
    
    if passed == total:
        print("SUCCESS: All core tests passed!")
        print()
        print("System is ready to run!")
        print("Note: Some optional dependencies may be missing.")
        return 0
    else:
        print("WARNING: Some tests failed - check output above")
        return 1

if __name__ == "__main__":
    sys.exit(main())

