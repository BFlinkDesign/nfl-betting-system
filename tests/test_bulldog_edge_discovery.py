import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "bulldog_edge_discovery.py"
spec = importlib.util.spec_from_file_location("bulldog_edge_discovery", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
BulldogEdgeDiscovery = module.BulldogEdgeDiscovery


def test_hypothesis_screen_is_research_only_and_registry_read_only(tmp_path):
    discovery = BulldogEdgeDiscovery(
        registry_path=tmp_path / "registry.json", report_dir=tmp_path / "reports"
    )
    discovery.data = pd.DataFrame(
        {
            "season": [2020] * 100,
            "home_score": [24] * 100,
            "away_score": [17] * 100,
            "home_win": [1] * 70 + [0] * 30,
            "total_points": [41] * 100,
        }
    )
    condition = pd.Series([True] * 100)
    result = discovery.test_hypothesis(
        "Synthetic Association", condition, discovery.data["home_win"]
    )
    assert result is not None
    candidates = discovery.finalize_results()

    assert len(candidates) == 1
    assert candidates[0]["evidence_status"] == "research_only"
    assert not candidates[0]["promotion_eligible"]
    assert discovery.edges_found == []
    assert discovery.registry.get_stats()["total"] == 0


def test_multiple_testing_correction_is_applied_before_candidate_classification(
    tmp_path,
):
    discovery = BulldogEdgeDiscovery(
        registry_path=tmp_path / "registry.json", report_dir=tmp_path / "reports"
    )
    discovery.data = pd.DataFrame(
        {
            "season": [2020] * 40,
            "home_score": [24] * 40,
            "away_score": [17] * 40,
            "home_win": [1] * 24 + [0] * 16,
            "total_points": [41] * 40,
        }
    )
    condition = pd.Series([True] * 40)
    for index in range(20):
        discovery.test_hypothesis(
            f"Hypothesis {index}", condition, discovery.data["home_win"]
        )

    discovery.finalize_results()
    assert all("adjusted_p_value" in result for result in discovery.hypotheses)
    assert all(
        result["adjusted_p_value"] >= result["raw_p_value"]
        for result in discovery.hypotheses
    )
