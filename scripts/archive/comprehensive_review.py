#!/usr/bin/env python3
"""
Comprehensive Codebase Review and Stress Test
Tests all components, finds issues, and validates integrations.
"""

import sys
import importlib
import traceback
from pathlib import Path
from typing import List, Dict, Tuple
import ast
import re

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class CodebaseReviewer:
    """Comprehensive codebase reviewer."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
        self.duplicates = []
        self.unused_files = []
        
    def review_imports(self) -> List[str]:
        """Check for import errors and circular dependencies."""
        print("\n" + "="*60)
        print("IMPORT REVIEW")
        print("="*60)
        
        modules_to_test = [
            # Core
            "src.utils.odds_cache",
            "src.utils.token_bucket",
            "src.api.espn_client",
            "src.api.noaa_client",
            "src.api.request_orchestrator",
            
            # Agents
            "src.agents.base_agent",
            "src.agents.message_bus",
            "src.agents.orchestrator_agent",
            "src.agents.strategy_analyst_agent",
            "src.agents.market_intelligence_agent",
            "src.agents.data_engineering_agent",
            "src.agents.risk_management_agent",
            "src.agents.performance_analyst_agent",
            "src.agents.worker_agents",
            
            # Swarms
            "src.swarms.swarm_base",
            "src.swarms.strategy_generation_swarm",
            "src.swarms.validation_swarm",
            "src.swarms.consensus_swarm",
            
            # Self-healing
            "src.self_healing.monitoring",
            "src.self_healing.anomaly_detection",
            "src.self_healing.auto_remediation",
            
            # Other
            "src.audit.system_connectivity_auditor",
            "src.backtesting.ai_orchestrator",
            "src.data.stadium_locations",
        ]
        
        failed_imports = []
        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
                print(f"PASS: {module_name}")
                self.successes.append(f"Import: {module_name}")
            except Exception as e:
                print(f"FAIL: {module_name}: {e}")
                failed_imports.append((module_name, str(e)))
                self.issues.append(f"Import error: {module_name} - {e}")
        
        return failed_imports
    
    def check_circular_dependencies(self) -> List[str]:
        """Check for circular import patterns."""
        print("\n" + "="*60)
        print("CIRCULAR DEPENDENCY CHECK")
        print("="*60)
        
        circular_issues = []
        
        # Check known problematic patterns
        problematic_pairs = [
            ("src.agents.base_agent", "src.agents.message_bus"),
            ("src.agents.message_bus", "src.agents.base_agent"),
        ]
        
        for mod1, mod2 in problematic_pairs:
            try:
                # Try importing both
                importlib.import_module(mod1)
                importlib.import_module(mod2)
                print(f"PASS: {mod1} <-> {mod2} (no circular dependency)")
            except Exception as e:
                if "circular" in str(e).lower() or "cannot import" in str(e).lower():
                    print(f"FAIL: Potential circular dependency: {mod1} <-> {mod2}")
                    circular_issues.append(f"{mod1} <-> {mod2}")
                    self.issues.append(f"Circular dependency: {mod1} <-> {mod2}")
        
        return circular_issues
    
    def test_api_clients(self) -> Dict[str, bool]:
        """Test API clients."""
        print("\n" + "="*60)
        print("API CLIENT TESTS")
        print("="*60)
        
        results = {}
        
        # Test ESPN
        try:
            from src.api.espn_client import ESPNClient
            client = ESPNClient()
            data = client.get_scoreboard()
            if data and 'events' in data:
                print(f"PASS: ESPN API - Found {len(data['events'])} games")
                results['espn'] = True
                self.successes.append("ESPN API working")
            else:
                print("WARN: ESPN API returned empty data")
                results['espn'] = False
                self.warnings.append("ESPN API returned empty data")
        except Exception as e:
            print(f"FAIL: ESPN API: {e}")
            results['espn'] = False
            self.issues.append(f"ESPN API error: {e}")
        
        # Test NOAA
        try:
            from src.api.noaa_client import NOAAClient
            client = NOAAClient()
            data = client.get_forecast_for_location(39.0489, -94.4839)
            if data:
                print(f"PASS: NOAA API - Forecast retrieved")
                results['noaa'] = True
                self.successes.append("NOAA API working")
            else:
                print("WARN: NOAA API returned empty data")
                results['noaa'] = False
                self.warnings.append("NOAA API returned empty data")
        except Exception as e:
            print(f"FAIL: NOAA API: {e}")
            results['noaa'] = False
            self.issues.append(f"NOAA API error: {e}")
        
        return results
    
    def test_agent_system(self) -> Dict[str, bool]:
        """Test agent system."""
        print("\n" + "="*60)
        print("AGENT SYSTEM TESTS")
        print("="*60)
        
        results = {}
        
        try:
            from src.agents.base_agent import BaseAgent, AgentCapability, agent_registry
            from src.agents.message_bus import message_bus
            
            # Test registry
            agents = agent_registry.get_all()
            print(f"PASS: Agent registry - {len(agents)} agents registered")
            results['registry'] = True
            self.successes.append("Agent registry working")
            
            # Test message bus
            if message_bus:
                print("PASS: Message bus initialized")
                results['message_bus'] = True
                self.successes.append("Message bus working")
            else:
                print("FAIL: Message bus not initialized")
                results['message_bus'] = False
                self.issues.append("Message bus not initialized")
                
        except Exception as e:
            print(f"FAIL: Agent system: {e}")
            results['agent_system'] = False
            self.issues.append(f"Agent system error: {e}")
        
        return results
    
    def find_duplicate_code(self) -> List[Tuple[str, str]]:
        """Find duplicate code patterns."""
        print("\n" + "="*60)
        print("DUPLICATE CODE CHECK")
        print("="*60)
        
        duplicates = []
        
        # Check for duplicate function definitions
        python_files = list(project_root.rglob("*.py"))
        function_signatures = {}
        
        for file_path in python_files:
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            sig = f"{node.name}({len(node.args.args)} args)"
                            if sig in function_signatures:
                                duplicates.append((str(file_path), function_signatures[sig]))
                            else:
                                function_signatures[sig] = str(file_path)
            except:
                pass
        
        if duplicates:
            print(f"WARN: Found {len(duplicates)} potential duplicate functions")
            for dup in duplicates[:10]:  # Show first 10
                print(f"  {dup[0]} <-> {dup[1]}")
        else:
            print("PASS: No obvious duplicate functions found")
        
        return duplicates
    
    def check_unused_files(self) -> List[str]:
        """Check for unused files."""
        print("\n" + "="*60)
        print("UNUSED FILES CHECK")
        print("="*60)
        
        unused = []
        
        # Check for test files that might be duplicates
        test_files = list(project_root.glob("test*.py"))
        if len(test_files) > 1:
            print(f"INFO: Found {len(test_files)} test files")
            for tf in test_files:
                if tf.name not in ["test_system_simple.py"]:
                    unused.append(str(tf))
        
        # Check for duplicate markdown files
        md_files = list(project_root.glob("*.md"))
        similar_md = []
        for md1 in md_files:
            for md2 in md_files:
                if md1 != md2 and md1.stem.lower() == md2.stem.lower():
                    similar_md.append((str(md1), str(md2)))
        
        if similar_md:
            print(f"WARN: Found {len(similar_md)} similar markdown files")
            for pair in similar_md[:5]:
                print(f"  {pair[0]} <-> {pair[1]}")
        
        return unused
    
    def stress_test_components(self) -> Dict[str, bool]:
        """Stress test major components."""
        print("\n" + "="*60)
        print("STRESS TESTS")
        print("="*60)
        
        results = {}
        
        # Test cache
        try:
            from src.utils.odds_cache import OddsCache
            cache = OddsCache()
            
            # Test multiple operations
            for i in range(10):
                cache.get(f"test_key_{i}")
            print("PASS: Cache stress test - 10 operations")
            results['cache'] = True
            self.successes.append("Cache stress test passed")
        except Exception as e:
            print(f"FAIL: Cache stress test: {e}")
            results['cache'] = False
            self.issues.append(f"Cache stress test error: {e}")
        
        # Test token bucket
        try:
            from src.utils.token_bucket import MultiAPITokenBucket
            bucket = MultiAPITokenBucket()
            bucket.register_default('test_api')
            
            # Test multiple consumes
            for i in range(100):
                bucket.consume('test_api', 1)
            print("PASS: Token bucket stress test - 100 operations")
            results['token_bucket'] = True
            self.successes.append("Token bucket stress test passed")
        except Exception as e:
            print(f"FAIL: Token bucket stress test: {e}")
            results['token_bucket'] = False
            self.issues.append(f"Token bucket stress test error: {e}")
        
        return results
    
    def generate_report(self) -> str:
        """Generate comprehensive report."""
        report = []
        report.append("\n" + "="*60)
        report.append("COMPREHENSIVE CODEBASE REVIEW REPORT")
        report.append("="*60)
        report.append("")
        
        report.append(f"SUCCESSES: {len(self.successes)}")
        report.append(f"WARNINGS: {len(self.warnings)}")
        report.append(f"ISSUES: {len(self.issues)}")
        report.append("")
        
        if self.issues:
            report.append("ISSUES FOUND:")
            for issue in self.issues[:20]:  # Top 20
                report.append(f"  - {issue}")
        
        if self.warnings:
            report.append("\nWARNINGS:")
            for warning in self.warnings[:10]:  # Top 10
                report.append(f"  - {warning}")
        
        return "\n".join(report)

def main():
    """Run comprehensive review."""
    reviewer = CodebaseReviewer()
    
    print("Starting comprehensive codebase review...")
    
    # Run all checks
    reviewer.review_imports()
    reviewer.check_circular_dependencies()
    reviewer.test_api_clients()
    reviewer.test_agent_system()
    reviewer.find_duplicate_code()
    reviewer.check_unused_files()
    reviewer.stress_test_components()
    
    # Generate report
    report = reviewer.generate_report()
    print(report)
    
    # Save report
    with open("CODEBASE_REVIEW_REPORT.md", "w") as f:
        f.write(report)
        f.write("\n\n## Full Details\n\n")
        f.write(f"Issues: {len(reviewer.issues)}\n")
        f.write(f"Warnings: {len(reviewer.warnings)}\n")
        f.write(f"Successes: {len(reviewer.successes)}\n")
    
    print("\nReport saved to CODEBASE_REVIEW_REPORT.md")
    
    return 0 if len(reviewer.issues) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

