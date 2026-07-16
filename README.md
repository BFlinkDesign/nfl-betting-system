# NFL Betting System

> **Canonical status: RESEARCH / PAPER-TRADING ONLY**  
> **Live-money betting is not authorized. Profitability is not verified.**  
> See [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for the controlling status and evidence standard.

Current execution controls:

- [`TASKS.md`](TASKS.md): ordered, evidence-gated repository plan.
- [`PAPER_TRADING_PLAN.md`](PAPER_TRADING_PLAN.md): frozen prospective paper-trading protocol.

This repository is a single-operator NFL analytics and betting-research system. It ingests historical and current data, engineers pregame features, trains and evaluates probability models, screens hypotheses, sizes paper positions, and presents results through scripts and a Streamlit dashboard.

The product outcome is not “produce a pick.” The product outcome is an **auditable decision**—including **NO BET**—whose data, market price, model version, calibration, uncertainty, and risk controls can be reproduced.

## Current evidence posture

| Claim | Current classification |
|---|---|
| 67.22% win rate / 428.04% ROI | **Invalid historical result.** The repository’s leakage audit identifies these figures as pre-fix results produced with betting-line leakage and unrealistic fixed odds. |
| 49.57% win rate / -23.62% ROI | **Reproduced historical NO-GO baseline** after removing leaked line features and using actual moneyline prices. |
| 69.23% win rate / 60.05% ROI on 52 bets | **Unverified summary claim.** It appears in historical documents, but no tracked, commit-bound result artifact currently proves independent out-of-sample reproduction. |
| “Production ready” | **Not an authorized current status.** Historical documents using this phrase are subordinate to `docs/PROJECT_STATUS.md`. |

Primary evidence: [`DATA_LEAKAGE_FIX_REPORT.md`](DATA_LEAKAGE_FIX_REPORT.md), [`docs/PROJECT_HISTORY.md`](docs/PROJECT_HISTORY.md), and [`docs/CONSOLIDATED_REPORTS.md`](docs/CONSOLIDATED_REPORTS.md).

## Non-negotiable promotion gates

A research association cannot become a deployable strategy unless all of the following are evidenced:

1. Source data and feature values are time-stamped and available as of the prediction cutoff.
2. Betting lines, outcomes, closing information, and future-derived aggregates are excluded from model features unless explicitly used only as market prices or labels.
3. Model selection, calibration, threshold selection, and final evaluation use separated temporal windows.
4. Multiple-hypothesis searches use a false-discovery-rate or stronger correction.
5. The strategy condition is serialized as executable, versioned logic rather than a prose label.
6. ROI is calculated from actual market-specific prices with wins, losses, pushes, and transaction constraints handled correctly.
7. Probability calibration, uncertainty intervals, sample sizes, drawdown, and sensitivity analyses are reported.
8. A separate paper-trading period passes the predefined policy without retrospective threshold changes.
9. The result artifact records the code commit, data snapshot, configuration, feature set, model digest, and evaluation window.
10. Live authorization is an explicit human decision; it is never inferred from a passing backtest.

## Hardened strategy lifecycle

```text
research_only
    -> out_of_sample_validated
    -> paper_trading
    -> live_validated
```

Operator review state (`pending`, `accepted`, `rejected`, `archived`) is separate from evidence maturity. An accepted strategy is not deployable unless its evidence status is `paper_trading` or `live_validated`.

## Discovery behavior

`scripts/bulldog_edge_discovery.py` is a **research-only screener**:

- it records every evaluable hypothesis;
- applies Benjamini-Hochberg false-discovery-rate correction;
- reports Wilson lower confidence bounds;
- does not estimate ROI without actual prices;
- does not treat dataset-average totals as sportsbook totals;
- does not write to the Strategy Registry;
- leaves `edges_found` empty until a separate validation system supplies qualifying evidence.

Outputs:

- `reports/bulldog_hypotheses_all.csv`
- `reports/bulldog_research_candidates.csv`

## Strategy Registry guarantees

`src/strategy_registry.py` provides:

- schema validation and explicit evidence status;
- atomic temp-file + `os.replace` persistence;
- writer lock and external-change detection;
- corruption fail-closed behavior;
- transactional add, update, delete, and version operations;
- backward-compatible loading of the original flat JSON format;
- a dedicated `get_deployable_strategies()` evidence gate.

The registry is an operator ledger. It is not a substitute for a reproducible evaluation artifact.

## Setup

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Python 3.10 or newer is required by the repository tooling configuration.

## Verification

Run the repository’s authoritative non-integration suite:

```bash
python -m pytest -m "not integration and not slow"
```

Run the focused hardening tests:

```bash
python -m pytest \
  tests/test_strategy_registry.py \
  tests/test_discovery_validation.py \
  tests/test_bulldog_edge_discovery.py
```

Run static checks using the pinned development toolchain:

```bash
black --check .
isort --check-only .
ruff check .
```

## Research workflow

```bash
# Requires the historical feature parquet referenced by the script.
python scripts/bulldog_edge_discovery.py

# Dashboard; review output as research/paper-trading material only.
python -m streamlit run dashboard/app.py
```

Do not run any script as a live-money execution system. No repository claim overrides the canonical status file.

## Architecture

```text
Data ingestion
  -> as-of validation and feature engineering
  -> temporal training / calibration / evaluation
  -> probability and uncertainty output
  -> actual market-price comparison
  -> risk policy
  -> paper-trading ledger
  -> post-result attribution and recalibration
```

The deterministic core owns data contracts, state, arithmetic, persistence, policy gates, and audit records. AI/LLM components may propose hypotheses or explain results, but they do not authorize strategy promotion, change risk limits, or certify profitability.

## Source hierarchy

When documents disagree, use this order:

1. Current code and tests at the evaluated commit.
2. Commit-bound result artifacts with data/config/model provenance.
3. Current canonical status and architecture documents.
4. Merged pull requests and issue evidence.
5. Historical summaries, generated reports, chat exports, and design blueprints.

Historical documents are evidence of what was proposed or claimed—not proof that the current system achieved it.

## Project controls

- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md): canonical operational status and release gates.
- [`TASKS.md`](TASKS.md): ordered execution gates and current work sequence.
- [`PAPER_TRADING_PLAN.md`](PAPER_TRADING_PLAN.md): prospective paper protocol and promotion criteria.
- [`AGENTS.md`](AGENTS.md): mandatory operating rules for Codex, Claude Code, and other coding agents.
- [`docs/WORLD_CUP_SESSION_AUDIT_2026-07-16.md`](docs/WORLD_CUP_SESSION_AUDIT_2026-07-16.md): Spain/World Cup intent, market, pricing, and evidence lessons.
- [`docs/INTEL_ALIGNMENT_AND_HARDENING_2026-07-16.md`](docs/INTEL_ALIGNMENT_AND_HARDENING_2026-07-16.md): source extraction, contradiction analysis, and remediation record.
- [`DATA_LEAKAGE_FIX_REPORT.md`](DATA_LEAKAGE_FIX_REPORT.md): historical leakage finding and honest baseline.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): technical architecture; performance statements remain subordinate to current evidence.

## Responsible-use boundary

Sports betting involves financial loss risk. Backtests are highly sensitive to leakage, selection bias, market-price assumptions, limits, timing, and regime change. This repository must remain in research/paper-trading mode until every promotion gate is independently reproduced and explicitly approved.
