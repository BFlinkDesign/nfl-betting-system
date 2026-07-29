from datetime import datetime, timedelta, timezone

from scripts.evaluate_paper_decisions import evaluate_payload

NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


def valid_candidate():
    return {
        "label": "Example moneyline",
        "market_snapshot": {
            "snapshot_id": "snap-1",
            "event_id": "event-1",
            "market_key": "h2h",
            "selection_key": "home",
            "sportsbook": "ExampleBook",
            "source": "stored-api-response",
            "american_odds": 150,
            "observed_at": (NOW - timedelta(seconds=20)).isoformat(),
            "event_start_at": (NOW + timedelta(hours=1)).isoformat(),
            "source_hash": "a" * 64,
        },
        "model_estimate": {
            "estimate_id": "est-1",
            "model_id": "model@sha",
            "evaluation_id": "wf-2026",
            "point_probability": 0.50,
            "lower_probability_bound": 0.45,
            "evidence_status": "out_of_sample_validated",
            "generated_at": (NOW - timedelta(minutes=2)).isoformat(),
            "data_cutoff_at": (NOW - timedelta(hours=2)).isoformat(),
            "artifact_hash": "b" * 64,
        },
    }


def test_payload_preserves_good_and_invalid_candidates():
    result = evaluate_payload(
        {"candidates": [valid_candidate(), {"label": "broken"}]}, now=NOW
    )

    assert result["summary"]["candidate_count"] == 2
    assert result["summary"]["status_counts"]["PAPER_TRACK"] == 1
    assert result["summary"]["status_counts"]["NO_BET"] == 1
    assert result["summary"]["live_wagers_authorized"] is False
    assert result["receipts"][1]["fallback"] == "NO_BET"
