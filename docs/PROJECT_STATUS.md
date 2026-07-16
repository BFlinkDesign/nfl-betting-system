# Canonical Project Status

**Effective date:** 2026-07-16  
**Authority:** This file controls when any repository document, dashboard, script, or archived chat conflicts with it.  
**Operational mode:** `RESEARCH_ONLY / PAPER_TRADING`  
**Live-money authorization:** `FALSE`  
**Profitability verified:** `FALSE`

## Executive determination

The repository contains substantial engineering work, but its current evidence does not justify a production-profitability claim or live-money operation.

The strongest reproducible historical audit found that the original headline metrics—67.22% win rate and 428.04% ROI—were generated with betting-line leakage and unrealistic odds. After those defects were removed, the reported baseline became 49.57% win rate, -23.62% ROI, and a NO-GO decision.

Later summaries report 69.23% win rate and 60.05% ROI on 52 bets for a favorites-only refinement. The repository does not currently contain a tracked, commit-bound result bundle proving that claim through an independent temporal holdout with complete data, configuration, model, price, and execution provenance. The claim is therefore historical and unverified, not a release gate.

## Authorized outcomes

The system may:

- ingest and validate data;
- train and calibrate research models;
- run reproducible historical evaluation;
- screen research hypotheses;
- generate paper-trading candidates and notifications clearly labeled as such;
- record operator review decisions;
- analyze results and failure mechanisms.

The system may not:

- represent any historical metric as verified current performance without a commit-bound artifact;
- auto-promote a discovered association into a deployable strategy;
- calculate betting ROI from assumed universal prices;
- authorize live betting from a model score, p-value, chat conclusion, skill, generated prompt, or operator “accept” click;
- place or instruct real-money bets as though profitability were established.

## Evidence maturity

| State | Meaning | Permitted use |
|---|---|---|
| `unverified` | No sufficient evidence bundle | Documentation or backlog only |
| `research_only` | In-sample or exploratory association | Research report only |
| `out_of_sample_validated` | Passed predefined independent temporal evaluation using actual market prices | Paper-trading candidate |
| `paper_trading` | Passed a forward paper-trading policy without retrospective rule changes | Eligible for explicit live-review decision |
| `live_validated` | Explicitly authorized and monitored with real execution evidence | Limited operation under active risk controls |

Operator review state is independent. `accepted` does not imply deployable.

## Minimum result artifact

Every performance claim used for a decision must include:

- repository commit SHA;
- immutable or content-addressed data snapshot identifier;
- data coverage and prediction cutoff rules;
- full feature manifest and leakage audit result;
- train, calibration, validation, and final holdout date ranges;
- model class, hyperparameters, random seeds, and model digest;
- market, sportsbook/source, line, price, timestamp, and push rules;
- predefined decision thresholds and risk policy;
- complete bet ledger, including passes and no-bets, not only selected wagers;
- calibration metrics, uncertainty intervals, drawdown, and sensitivity analysis;
- command or workflow required to reproduce the result;
- test and CI evidence for the evaluated commit.

A markdown statement, chat response, skill, or generated architecture without this bundle is a claim, not verification.

## Current P0 controls

1. The Strategy Registry fails closed on corruption, persists atomically, detects competing writers, validates records, and separates review status from evidence maturity.
2. Bulldog discovery is research-only, applies multiple-testing correction, reports uncertainty, omits fabricated ROI, and performs zero registry writes.
3. README and agent instructions reject historical “production ready” language as current authority.
4. Historical Claude/Chat/Codex artifacts, skills, and generated prompts are provenance or hypotheses—not execution proof.
5. Market decisions require exact hashed snapshots, fresh prices, versioned estimates, pre-event cutoffs, probability lower bounds, and deterministic receipts.
6. Parlay paper candidates require one exact same-book offer and a distinct validated joint-probability estimate; marginal multiplication cannot authorize a candidate.
7. Kelly favorite multipliers, hot-streak bonuses, and ten-percent sizing are removed. Dollar sizing is blocked in paper mode.
8. Legacy live-named pick pipelines are not authorized execution paths. Any attempt to use the former aggressive Kelly path fails closed until those scripts adopt the new decision contract and the canonical status changes.

## Release gates

A change may be called code-complete only when the affected tests and static checks pass. A model may be called validated only when the result artifact above is reproduced. The project may be called live-ready only after:

1. all model-validation gates pass;
2. a forward paper-trading period passes predefined criteria;
3. data/provider/legal/operational assumptions are rechecked;
4. failure recovery, monitoring, and kill switches are exercised;
5. the operator explicitly changes this canonical status in a reviewed commit.

Until then, **NO BET is the default safe output**.
