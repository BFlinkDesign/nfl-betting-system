# Intel Alignment and Hardening Report

**Date:** 2026-07-16  
**Repository:** `BFlinkDesign/nfl-betting-system`  
**Status:** Source-aligned implementation report; model profitability remains unverified.

## Mission

Recover accessible Claude Code, Claude-authored repository material, Codex/ChatGPT archives, project blueprints, commits, pull requests, and directly related archived artifacts; separate proven facts from claims; align the project to its real operator outcome; and harden the highest-risk mechanisms.

Two independent analysis tracks were used:

- **Track A — Corpus and provenance:** identify the project, source lineage, session links, commits, PRs, blueprints, archived reports, and missing evidence.
- **Track B — Adversarial alignment and hardening:** test the product contract against code behavior, statistics, persistence, documentation, and deployment claims.

The tracks were reconciled only where evidence agreed.

## Coverage and limitations

### Retrieved and analyzed

- Current GitHub repository source, documentation, commit history, PR metadata, workflow evidence, and active branches.
- Claude-authored/Claude-documented repository artifacts.
- Claude Code session provenance embedded in merged PRs.
- Google Drive project-origin blueprints and gap-audit artifacts for SharpEdge AI / SoloBet AI.
- Indexed ChatGPT/Codex archive manifests, ledgers, and directly retrievable transcript fragments.
- Existing repository audits, including the data-leakage report.

### Not directly retrievable

- Full private Claude chat bodies behind external Claude session URLs.
- A complete private Codex session export tied exactly to this repository.
- Local-only files on machines referenced by archive indexes but not synced into an accessible connector.
- A complete immutable historical data/model/result bundle for the favorites-only performance claim.

No content was inferred to fill those gaps.

## Confirmed project identity and intended outcome

The canonical repository is `BFlinkDesign/nfl-betting-system`, not the provisional generic AI-workbench identity present in an earlier archive report.

Project-origin Drive artifacts describe:

- an Iowa-focused/single-operator NFL betting system;
- a micro-bankroll operating model;
- a small number of high-confidence decisions;
- mobile-friendly review and bankroll controls;
- extensive automation ambitions.

The durable outcome is therefore:

> Produce a small number of auditable, calibrated, risk-bounded paper decisions—or NO BET—from data and market evidence available at decision time.

The system must learn through verified causal and operational mechanisms, not through raw wins, in-sample ROI, agent consensus, or narrative confidence.

## Claude Code lineage

One exact Claude Code session identifier is preserved in merged PRs:

`session_01CFTZ9jnWHD4vZnKqpDdx4q`

Its merged work includes:

- PR #3: reproducible development/CI setup, pinned actions and tools, least-privilege workflow permissions, and 27 scoped non-integration tests.
- PR #4: network timeouts and safer exception handling.
- PR #6: dependency/tooling automation and CI drift fixes.

These are legitimate engineering improvements. The test counts are evidence for those tested code paths only.

The repository also contains Claude implementation summaries claiming 30/30 checks and production readiness. The surviving simple test harness counted import checks while API/config/dependency warnings were not all represented in its exit status. Those conclusions are not accepted as full-system proof.

## Codex / ChatGPT archive findings

The indexed ChatGPT file ledger and integrity manifest contained no exact indexed matches for the project terms `NFL`, `betting`, `Edge Finder`, or `Bulldog`. This is a negative retrieval result, not proof that no relevant conversation ever existed.

Retrievable archive material contributed durable engineering doctrine:

- prove one loop before generalizing;
- keep deterministic state and policy authoritative;
- place AI at interpretive edges;
- persist task and evidence state outside chat;
- verify the environment rather than trusting confidence;
- use multi-agent work only across separable boundaries;
- treat artifacts as intermediate mechanisms, not user outcomes;
- require held-out verification, baselines, failure classes, and kill/continue criteria.

A Codex transcript fragment referenced an NFL project worktree, but its surrounding task context was adjacent tooling/workflow work rather than verified betting-model evidence. It was not promoted into project canon.

## Origin-artifact findings

SharpEdge/SoloBet blueprints correctly emphasized calibration, actual market monitoring, risk controls, and single-operator automation. They also contained unsupported certainty and scale claims:

- “Only bet when we know we’ll win.”
- “Production-ready” before operational evidence.
- precise ROI/accuracy improvements without supplied provenance;
- model/calibrator selection and ROI evaluation on the same validation sample;
- premature GNN, multi-agent, AWS, Kubernetes, and 10,000-user architecture.

These are proposal artifacts. They establish intent, not achieved performance.

## Critical contradictions

### P0 — README used metrics the repository itself invalidated

The README advertised 67.22% win rate and 428.04% ROI. `DATA_LEAKAGE_FIX_REPORT.md` explicitly identifies those figures as pre-fix results driven by betting-line leakage and unrealistic odds. The post-fix run was 49.57% win rate, -23.62% ROI, and NO-GO.

### P0 — Discovery converted correlations into registry strategies

The former Bulldog implementation:

- reused discovery data for evaluation;
- used uncorrected p-values across many tests;
- assumed universal -110 economics;
- treated outright win rates as priced moneyline bets;
- treated dataset mean/median totals as betting totals;
- promoted or replaced registry records using higher in-sample estimated ROI;
- stored prose names instead of executable conditions.

### P0 — Registry persistence could destroy or misreport state

The prior registry loader swallowed parsing failures and replaced state with an empty dictionary. Writes swallowed errors, and callers could report success after persistence failure. Version upgrades archived and added records through separate writes.

### P1 — Test/readiness reports overstated proof

Historical reports used passing import checks and scoped unit suites to justify 24/7 or production-ready claims. Code correctness evidence and model-validity evidence were conflated.

### P1 — Documentation authority was inverted

Numerous generated status files declared production readiness while the stronger leakage report declared NO-GO. No canonical status hierarchy prevented stale claims from dominating the product story.

### P1 — Favorites-only claim is under-evidenced

The 69.23% win rate / 60.05% ROI claim is based on a reported 52 bets and lacks a tracked result bundle sufficient for independent reproduction. Even if numerically accurate, the evidence is too weak for deployment.

### P2 — Architecture exceeded the proven loop

The corpus repeatedly proposed agents, neural architectures, cloud services, and autonomous pipelines before proving a single calibrated, price-aware, temporally held-out decision loop.

## Implemented hardening

### Canonical truth and agent alignment

- Replaced the README’s leaked headline metrics with an evidence classification.
- Added `docs/PROJECT_STATUS.md` as controlling operational authority.
- Added `AGENTS.md` for Codex/Claude/other agents.
- Replaced `.claude/claude.md` with project-truth enforcement.
- Reclassified historical project/report summaries.
- Superseded the unsafe discovery integration instructions.

### Strategy Registry

- Strict schema and numeric/status validation.
- Explicit evidence maturity independent of operator review state.
- Atomic temp-file write, flush, fsync, and replace.
- Cross-platform writer lock plus stale-lock recovery.
- File fingerprint conflict detection.
- Corruption fail-closed behavior.
- Transactional add/update/delete/version operations.
- Backward-compatible migration from the flat JSON schema.
- `get_deployable_strategies()` returns only accepted records with paper/live evidence.

### Statistical discovery

- Bulldog converted to research-only screening.
- Every evaluable hypothesis retained.
- Benjamini-Hochberg false-discovery-rate correction.
- Wilson lower confidence bounds.
- No ROI without actual prices.
- Scoring associations clearly separated from market totals.
- Registry opened read-only; writes fixed at zero.
- `edges_found` reserved for independently validated evidence.
- Explicit promotion blockers recorded.

### Validation primitives

Added pure functions for:

- American-to-decimal odds conversion;
- push-aware flat-stake ROI;
- Benjamini-Hochberg correction;
- Wilson lower bounds;
- fail-closed promotion policy evaluation.

### Tests

Focused tests cover:

- atomic/versioned registry persistence;
- corruption preservation;
- persistence rollback;
- concurrent/external-write rejection;
- active-writer lock rejection;
- invalid update rollback;
- transactional strategy versioning;
- deployable evidence filtering;
- actual-price conversion and push handling;
- multiple-testing adjustment;
- uncertainty behavior;
- promotion-gate failure and success paths;
- Bulldog research-only and zero-registry-write behavior.

## Unmerged branch determination

PR #2 contains some useful fixes and a green latest workflow run, but it is a large, stale branch with broad file churn and deletions relative to current master. It must not be merged wholesale. Any remaining useful change should be isolated, ported to a fresh branch, and revalidated against current master.

## Aligned architecture

```text
1. Ingest source data with timestamps and quality state
2. Build only as-of features
3. Freeze discovery, calibration, and final temporal windows
4. Train and calibrate probabilities
5. Compare with actual market-specific prices
6. Apply multiplicity, uncertainty, and sensitivity gates
7. Emit BET / NO BET with full provenance
8. Apply bounded paper risk
9. Record complete ledger and closing information
10. Attribute result vs mechanism and recalibrate
```

AI may propose hypotheses and explanations. It may not own arithmetic, persistence, policy, evidence status, or promotion authorization.

## Remaining blockers

1. Reproduce the favorites-only model from immutable data and a documented command.
2. Build a canonical result-bundle schema and content-addressed artifact writer.
3. Add true walk-forward model selection, calibration, and untouched final holdout orchestration.
4. Reconstruct actual market lines/prices and push rules for every evaluated bet.
5. Replace prediction-derived “CLV” with actual closing-price comparison.
6. Add calibration curves/Brier/log loss by season, market, and confidence bucket.
7. Add bootstrap or block-bootstrap uncertainty for ROI/drawdown.
8. Add a forward paper-trading ledger and predefined promotion policy.
9. Audit all other “self-improving,” parlay, notification, and production-named scripts against the canonical status.
10. Resolve or close stale PR #2 after selective-port review.

## Confidence

- **Project identity and source lineage:** High.
- **Code-level registry/discovery findings:** High; directly inspected and regression-tested.
- **Historical metric invalidity:** High; stated by the repository’s own leakage report.
- **Favorites-only profitability:** Low confidence; insufficient reproducible evidence.
- **Completeness of private Claude/Codex chat extraction:** Medium-low; connector-visible artifacts were exhausted, but private external session bodies were not directly available.

## Decision

The project is materially safer and more honest after these changes, but it remains **NO-GO for live money**. The next successful outcome is not another architecture layer or agent. It is one independently reproducible, calibrated, price-aware, temporally held-out paper-trading loop with a complete evidence bundle.
