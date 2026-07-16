# Real-World Paper Decision Runbook

This runbook exercises the fail-closed decision boundary. It does not authorize or automate live wagering.

## Minimum input contract

A single-market JSON input must contain:

- `intent`: `information`, `paper_bet_evaluation`, or `live_bet_request`;
- `evaluated_at`: timezone-aware ISO-8601 timestamp;
- one exact market snapshot with all outcomes, bookmaker, observed timestamp, event start, market status, and raw source-receipt ID;
- one estimate with matching event/market/selection, probability, generated timestamp, model identity/version, model artifact SHA-256, dataset ID, source commit, and evidence maturity;
- an optional explicit policy override.

## Safe execution

```powershell
$env:PYTHONPATH = "."
python scripts/evaluate_market_decision.py input.json --output reports/decision.json
$LASTEXITCODE
```

Exit meanings:

- `0`: `NO_BET` or `PAPER_CANDIDATE`;
- `2`: `BLOCKED` because an evidence, market, freshness, or authority gate failed;
- `64`: malformed or incomplete input.

## Example single-market input

```json
{
  "receipt_type": "single_market_decision",
  "intent": "paper_bet_evaluation",
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
      {"selection": "KC", "american_odds": -110}
    ]
  },
  "estimate": {
    "event_id": "2026-W01-BUF-KC",
    "market_id": "2026-W01-BUF-KC:moneyline",
    "selection": "BUF",
    "win_probability": 0.58,
    "generated_at": "2026-09-10T21:55:00Z",
    "model_id": "nfl-calibrated-v1",
    "model_version": "1.0.0",
    "model_artifact_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "dataset_id": "nfl-snapshot-2026-09-10",
    "source_commit": "abcdef1234567890",
    "evidence_status": "out_of_sample_validated"
  }
}
```

The example is a deterministic interface fixture, not a real market or model claim.

## Blocking scenarios that must be tested operationally

- missing or synthetic price;
- one-sided market snapshot that cannot be de-vigged;
- stale quote or stale model output;
- event already started;
- suspended or closed market;
- event, market, or selection mismatch;
- research-only model evidence;
- information request presented as a bet request;
- live-money request while authorization is false;
- parlay without a dependency-aware joint model;
- parlay total that differs from visible legs without an adjustment receipt;
- all-push, void, postponed, or corrected-result settlement.

## Evidence retention

Persist the input JSON, output receipt, raw quote source receipt, model manifest, settlement record, closing quote, and hashes as one immutable decision bundle. Never overwrite the pre-event receipt after the outcome is known.
