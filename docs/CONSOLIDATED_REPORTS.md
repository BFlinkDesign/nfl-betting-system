# Consolidated Reports — Authority and Evidence Index

**Canonical status:** Research / paper-trading only. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

Historical reports in this repository frequently use terms such as “complete,” “production ready,” “validated,” or “all tests passing.” Those phrases are scoped claims from prior sessions and are not current operational authority.

## Authority classes

### Tier A — Current controlling evidence

- `docs/PROJECT_STATUS.md` — operational status and release gates.
- `AGENTS.md` — cross-agent engineering and evidence contract.
- Current source and tests at the evaluated commit.
- Commit-bound CI/workflow results.
- Future immutable model-result bundles that meet the canonical artifact contract.

### Tier B — High-value historical evidence

- `DATA_LEAKAGE_FIX_REPORT.md` — proves the original headline metrics were invalid and records the post-fix NO-GO baseline.
- Merged GitHub pull requests and commit history — prove specific code changes and scoped validation.
- `CLAUDE_IMPLEMENTATION_SUMMARY.md` and `CHANGELOG_CLAUDE_SESSION.md` — useful change provenance, but their readiness/test-total conclusions require independent verification.

### Tier C — Unverified summaries and proposals

- Former “production ready” status reports.
- Favorites-only 69.23% / 60.05% summary without a tracked result bundle.
- AI-generated system blueprints, gap audits, architecture proposals, and ROI projections.
- Discovery reports based on in-sample associations or assumed odds.

Tier C material may generate hypotheses. It cannot authorize deployment.

## Known performance claims

| Claim | Classification | Required action |
|---|---|---|
| 67.22% win rate / 428.04% ROI | Invalid due to betting-line leakage and unrealistic odds | Never use as current performance |
| 49.57% win rate / -23.62% ROI | Historical honest baseline; NO-GO | Use as regression reference only |
| 69.23% win rate / 60.05% ROI on 52 bets | Unverified summary | Reproduce from immutable data and untouched holdout |
| 30/30 or “all tests” | Historical scoped claim | Record exact executable test inventory and CI result |

## Required report format going forward

Every model or strategy report must state:

- evidence status;
- code commit;
- data snapshot and coverage;
- prediction cutoff and leakage controls;
- split windows;
- actual market-price source;
- complete ledger and push handling;
- calibration and uncertainty;
- predefined thresholds;
- reproduction command;
- tests and CI scope;
- limitations and unexercised integrations.

A report missing these fields is automatically `unverified`.
