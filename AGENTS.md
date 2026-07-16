# Agent Operating Contract

These instructions apply to Codex, Claude Code, Cursor, Devin, ChatGPT-connected coding tools, and human contributors. Read `docs/PROJECT_STATUS.md` before changing code.

## Project truth

- This is an NFL analytics and betting-research repository.
- Current mode is research/paper trading only.
- Live-money authorization is false.
- Profitability is not verified.
- Historical “production ready,” win-rate, ROI, CLV, test-count, or autonomous-learning claims are noncanonical unless reproduced in a commit-bound evidence bundle.

## Outcome contract

Users judge the product by whether it produces a correct, auditable decision. The system must improve through verified mechanisms. A valid output may be `NO BET`.

Every recommendation must trace:

```text
source data -> as-of features -> model/version -> calibrated probability
-> market/price/time -> decision policy -> risk size -> result -> attribution
```

## Source authority

When sources conflict:

1. Current code plus tests at the evaluated commit.
2. Immutable result artifacts containing data/config/model provenance.
3. `docs/PROJECT_STATUS.md` and current architecture contracts.
4. Merged PR evidence and workflow logs.
5. Historical reports, generated summaries, chat exports, and blueprints.

Do not copy a historical claim into current documentation without revalidation.

## Forbidden shortcuts

- No in-sample result may be labeled a betting edge.
- No discovery set may also serve as final evaluation.
- No model/calibrator/threshold may be selected on the final holdout.
- No random split may replace a temporal split for a time-dependent claim.
- No betting-line, closing-line, outcome, or future-derived leakage.
- No fixed -110 or 1.91 assumption when actual market prices are required.
- No universal break-even threshold across different markets and prices.
- No p-value screening across many hypotheses without multiplicity correction.
- No auto-promotion from AI output, p-value, win rate, ROI, or operator review state.
- No silent exception that resets, overwrites, or fabricates state.
- No “all tests passed” claim unless the exact command, scope, and exit status are recorded.
- No “production ready” or “profitable” claim without the canonical release gates.
- No live-money feature or notification phrased as verified advice while status is research-only.

## Strategy lifecycle

Evidence state:

```text
unverified -> research_only -> out_of_sample_validated
-> paper_trading -> live_validated
```

Review state (`pending`, `accepted`, `rejected`, `archived`) is separate. Use `get_deployable_strategies()` for evidence-qualified records; never treat all accepted records as deployable.

## Discovery rules

- `scripts/bulldog_edge_discovery.py` is a research screener.
- It must not write to the Strategy Registry.
- It must retain all evaluable hypotheses for multiple-testing correction.
- Scoring-above-dataset-average is not a sportsbook over; outright win rate is not moneyline ROI.
- Promotion requires executable conditions, actual market lines/prices, independent temporal holdout, uncertainty, and a complete evidence reference.

## Persistence rules

- Durable state changes must validate before commit.
- Writes must be atomic and fail closed.
- Corrupt state must not be replaced with an empty default.
- Concurrent writers must be serialized or rejected.
- Multi-step updates must commit transactionally or leave no mutation.
- Timestamps must be timezone-aware.

## Definition of done

For each change:

1. Identify the exact user-visible outcome and failure modes.
2. Add or update tests before claiming completion.
3. Run the smallest affected test set and the authoritative non-integration suite.
4. Run pinned formatting, lint, and security checks in CI.
5. Record what was not exercised—especially live APIs, private data, integration tests, and model reproduction.
6. Update canonical docs when behavior or evidence status changes.
7. Provide a rollback or fail-closed path for stateful changes.

Passing unit tests prove the tested code paths, not model profitability or operational readiness.
