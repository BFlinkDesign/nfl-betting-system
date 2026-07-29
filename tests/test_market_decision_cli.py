import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/evaluate_market_decision.py")
HASH = "a" * 64


def valid_payload(intent="paper_bet_evaluation"):
    return {
        "receipt_type": "single_market_decision",
        "intent": intent,
        "evaluated_at": "2026-09-10T22:00:00Z",
        "market": {
            "event_id": "2026-W01-BUF-KC",
            "competition": "NFL 2026",
            "market_id": "2026-W01-BUF-KC:moneyline",
            "market_type": "moneyline_2way",
            "bookmaker": "example-book",
            "observed_at": "2026-09-10T21:59:30Z",
            "starts_at": "2026-09-11T00:20:00Z",
            "status": "open",
            "source_receipt_id": "raw-quote-receipt-001",
            "outcomes": [
                {"selection": "BUF", "american_odds": -110},
                {"selection": "KC", "american_odds": -110},
            ],
        },
        "estimate": {
            "event_id": "2026-W01-BUF-KC",
            "market_id": "2026-W01-BUF-KC:moneyline",
            "selection": "BUF",
            "win_probability": 0.58,
            "generated_at": "2026-09-10T21:55:00Z",
            "model_id": "nfl-calibrated-v1",
            "model_version": "1.0.0",
            "model_artifact_sha256": HASH,
            "dataset_id": "nfl-snapshot-2026-09-10",
            "source_commit": "abcdef1234567890",
            "evidence_status": "out_of_sample_validated",
        },
    }


def run_cli(tmp_path, payload):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(input_path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_emits_sealed_paper_candidate(tmp_path):
    result = run_cli(tmp_path, valid_payload())
    assert result.returncode == 0
    receipt = json.loads(result.stdout)
    assert receipt["decision"] == "PAPER_CANDIDATE"
    assert len(receipt["receipt_sha256"]) == 64


def test_cli_uses_nonzero_exit_for_blocked_live_request(tmp_path):
    result = run_cli(tmp_path, valid_payload(intent="live_bet_request"))
    assert result.returncode == 2
    receipt = json.loads(result.stdout)
    assert receipt["decision"] == "BLOCKED"
    assert "live_money_not_authorized" in receipt["blockers"]


def test_cli_uses_input_error_exit_for_malformed_contract(tmp_path):
    result = run_cli(tmp_path, {"intent": "paper_bet_evaluation"})
    assert result.returncode == 64
    receipt = json.loads(result.stdout)
    assert receipt["decision"] == "BLOCKED"
    assert "input_error" in receipt
