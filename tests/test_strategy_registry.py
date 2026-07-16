import json

import pytest

import src.strategy_registry as strategy_registry_module
from src.strategy_registry import (
    EvidenceStatus,
    RegistryCorruptionError,
    RegistryPersistenceError,
    Strategy,
    StrategyRegistry,
    StrategyStatus,
)


def make_strategy(strategy_id="home_favorites_v1", **overrides):
    values = {
        "strategy_id": strategy_id,
        "name": "Home Favorites",
        "description": "Research candidate",
        "pattern": "elo_diff > 100",
        "win_rate": 55.0,
        "roi": 2.0,
        "sample_size": 100,
        "edge": 3.0,
        "conditions": {"elo_diff": "> 100"},
    }
    values.update(overrides)
    return Strategy(**values)


def test_registry_creates_versioned_atomic_file(tmp_path):
    path = tmp_path / "registry.json"
    registry = StrategyRegistry(path)
    success, _ = registry.add_strategy(make_strategy())
    assert success

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["_meta"]["format_version"] == 1
    assert payload["_meta"]["strategy_count"] == 1
    assert payload["strategies"]["home_favorites_v1"]["name"] == "Home Favorites"
    assert not list(tmp_path.glob("*.tmp"))

    reloaded = StrategyRegistry(path)
    assert reloaded.strategies["home_favorites_v1"].sample_size == 100


def test_corrupt_registry_fails_closed_without_replacement(tmp_path):
    path = tmp_path / "registry.json"
    original = "{not-valid-json"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(RegistryCorruptionError):
        StrategyRegistry(path)

    assert path.read_text(encoding="utf-8") == original


def test_failed_persistence_does_not_mutate_memory(tmp_path, monkeypatch):
    registry = StrategyRegistry(tmp_path / "registry.json")

    def fail(_strategies):
        raise RegistryPersistenceError("disk unavailable")

    monkeypatch.setattr(registry, "_persist", fail)
    success, message = registry.add_strategy(make_strategy())
    assert not success
    assert "disk unavailable" in message
    assert registry.strategies == {}


def test_external_change_is_detected_instead_of_overwritten(tmp_path):
    path = tmp_path / "registry.json"
    first = StrategyRegistry(path)
    second = StrategyRegistry(path)

    assert first.add_strategy(make_strategy())[0]
    success, message = second.add_strategy(make_strategy("away_dogs_v1"))
    assert not success
    assert "changed after it was loaded" in message

    second.reload()
    assert second.add_strategy(
        make_strategy("away_dogs_v1", name="Away Dogs", pattern="away underdogs")
    )[0]


def test_invalid_update_is_rejected_and_original_is_preserved(tmp_path):
    registry = StrategyRegistry(tmp_path / "registry.json")
    assert registry.add_strategy(make_strategy())[0]

    success, _ = registry.update_strategy("home_favorites_v1", win_rate=101.0)
    assert not success
    assert registry.strategies["home_favorites_v1"].win_rate == 55.0

    success, message = registry.update_strategy("home_favorites_v1", version=99)
    assert not success
    assert "Unsupported update fields" in message


def test_version_creation_is_single_transaction(tmp_path, monkeypatch):
    registry = StrategyRegistry(tmp_path / "registry.json")
    assert registry.add_strategy(make_strategy(status=StrategyStatus.ACCEPTED.value))[0]
    original_snapshot = registry.strategies["home_favorites_v1"].to_dict()

    def fail(_strategies):
        raise RegistryPersistenceError("simulated failure")

    monkeypatch.setattr(registry, "_persist", fail)
    success, _ = registry.create_strategy_version(
        "home_favorites_v1", {"win_rate": 56.0, "sample_size": 150}
    )
    assert not success
    assert registry.strategies["home_favorites_v1"].to_dict() == original_snapshot
    assert "home_favorites_v2" not in registry.strategies


def test_deployable_filter_requires_evidence_maturity(tmp_path):
    registry = StrategyRegistry(tmp_path / "registry.json")
    assert registry.add_strategy(
        make_strategy(
            "research_v1",
            name="Research",
            status=StrategyStatus.ACCEPTED.value,
            evidence_status=EvidenceStatus.RESEARCH_ONLY.value,
        )
    )[0]
    assert registry.add_strategy(
        make_strategy(
            "paper_v1",
            name="Paper",
            pattern="paper condition",
            status=StrategyStatus.ACCEPTED.value,
            evidence_status=EvidenceStatus.PAPER_TRADING.value,
        )
    )[0]

    assert [s.strategy_id for s in registry.get_deployable_strategies()] == ["paper_v1"]


def test_active_writer_lock_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    registry = StrategyRegistry(path)
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.write_text("active", encoding="utf-8")
    monkeypatch.setattr(strategy_registry_module, "LOCK_WAIT_SECONDS", 0.0)

    success, message = registry.add_strategy(make_strategy())
    assert not success
    assert "locked by another writer" in message
    assert registry.strategies == {}
