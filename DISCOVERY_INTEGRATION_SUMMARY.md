# Legacy Discovery Integration Summary — Superseded

> **Superseded on 2026-07-16.** The former document described in-sample associations as production-ready betting edges and instructed operators to accept them into the Strategy Registry. That workflow is no longer authorized.

## Current behavior

`scripts/bulldog_edge_discovery.py` is a research-only hypothesis screener.

It now:

- records all evaluable hypotheses;
- applies Benjamini-Hochberg false-discovery-rate correction;
- reports Wilson lower confidence bounds;
- labels dataset-average scoring tests as scoring associations, not sportsbook totals bets;
- omits ROI when actual market prices are absent;
- performs zero Strategy Registry writes;
- preserves `edges_found` for future independently validated evidence only;
- writes research output to `reports/bulldog_hypotheses_all.csv` and `reports/bulldog_research_candidates.csv`.

## Why the prior workflow was unsafe

The prior implementation:

- discovered and evaluated hypotheses on the same samples;
- used uncorrected p-values across many tests;
- assumed a universal 52.4% break-even probability and -110 pricing;
- treated outright wins as if they were uniformly priced bets;
- treated totals above or below a dataset mean/median as sportsbook over/under results;
- could archive an existing strategy and add an “upgrade” using only higher in-sample estimated ROI;
- persisted prose labels rather than executable strategy conditions.

Those mechanisms cannot prove a market edge.

## Promotion path

A research candidate may enter the Strategy Registry only through a separate validation process that supplies:

1. an executable, versioned condition;
2. a discovery window and untouched temporal holdout;
3. actual market, line, price, timestamp, and push rules;
4. multiplicity-adjusted statistics and uncertainty intervals;
5. calibration and complete bet-ledger evidence;
6. a commit/data/config/model provenance reference;
7. an explicit evidence status.

See `docs/PROJECT_STATUS.md`, `AGENTS.md`, and `src/discovery_validation.py`.
