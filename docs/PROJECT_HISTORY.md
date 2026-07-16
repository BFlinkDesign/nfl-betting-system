# Project History — Evidence-Aware Timeline

**Canonical current status:** Research / paper-trading only. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

This file records what happened; it does not independently certify current performance.

## Phase 1 — Foundation

Implemented data ingestion, feature engineering, model training, backtesting, dashboards, notifications, and automation scaffolding.

## Phase 2 — Leakage discovery and honest baseline

The project identified that betting lines and derived line features had entered model features. Historical headline results of 67.22% win rate and 428.04% ROI were therefore circular and invalid for an independent prediction claim.

After removing line leakage and using actual moneyline prices, the reported baseline was:

- 49.57% win rate;
- -23.62% ROI;
- -25.15% maximum drawdown;
- NO-GO.

Evidence: `DATA_LEAKAGE_FIX_REPORT.md`.

## Phase 3 — Favorites-only refinement claim

Historical summaries state that a favorites-only XGBoost model produced 69.23% win rate and 60.05% ROI across 52 bets in 2023-2024.

**Evidence classification:** unverified historical summary. The tracked repository does not currently provide a commit-bound result bundle containing the complete ledger, immutable data snapshot, model digest, configuration, temporal selection/calibration/holdout boundaries, and reproduction command. The result may be investigated, but it is not current production evidence.

## Phase 4 — Automation and agent-generated expansion

The repository accumulated dashboards, automated scripts, LLM-assisted hypothesis generation, resilience utilities, CI hardening, and many completion/status reports. Several reports overstated system readiness or test coverage relative to the surviving executable evidence.

## Phase 5 — Claude Code hardening

A single identifiable Claude Code session produced merged PRs that:

- repaired and pinned the web-session/CI environment;
- pinned GitHub Actions and reduced workflow permissions;
- fixed network timeout and bare-exception hazards;
- added dependency and tooling automation.

These are valid engineering improvements. Their passing unit-test scopes do not validate betting performance.

## Phase 6 — Evidence and state hardening (2026-07-16)

- Reclassified the project as research/paper-trading only.
- Added cross-agent operating rules.
- Made Strategy Registry persistence atomic, validated, conflict-aware, and transactional.
- Separated review status from evidence maturity.
- Converted Bulldog discovery into a read-only research screener.
- Added false-discovery-rate correction, uncertainty bounds, and explicit promotion blockers.
- Removed fabricated ROI and automatic strategy promotion.
- Added focused regression tests.

## Current next milestone

Create a reproducible walk-forward result bundle using actual market prices, untouched temporal holdout data, calibrated probabilities, and a complete paper-trading ledger. Until that exists and passes predefined gates, the project remains NO-GO for live money.
