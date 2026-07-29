# Canonical Execution Plan

**Effective date:** 2026-07-16  
**Current phase:** P0 safety and evidence hardening  
**Operational mode:** `RESEARCH_ONLY / PAPER_TRADING`  
**Live-money authorization:** `FALSE`  
**Controlling status:** [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)

This plan supersedes the former autonomous-agent and feature-expansion roadmap. The repository is not trying to generate more picks, agents, dashboards, or confident prose. It is trying to produce reproducible decisions—including `NO_BET`—that survive independent review against real data, exact market prices, and real operational conditions.

## 1. Mission

Build a single-operator NFL decision system that can answer one bounded question reliably:

> Given an exact pregame event, market, selection, sportsbook price, and time-bounded evidence set, should this candidate be rejected, held, or recorded for forward paper tracking?

The system is successful only when it:

1. preserves the user's actual intent;
2. refuses to substitute a different market or action when evidence is unavailable;
3. binds every calculation to exact source, model, price, and time evidence;
4. distinguishes information, analysis, paper tracking, and live authority;
5. records passes and `NO_BET` decisions as first-class outcomes;
6. remains reproducible after the original chat, model session, or operator is gone.

## 2. Artifact maturity rule

Creation is not correctness. No Claude output, ChatGPT answer, skill, prompt, agent, script, model, test, dashboard, or report receives authority merely because it exists or ran.

| State | Minimum evidence | What it does not prove |
|---|---|---|
| `created` | Artifact exists | Correctness or usefulness |
| `parsed` | Syntax/schema accepted | Intended behavior |
| `executed` | Command completed | Correct output |
| `behavior_tested` | Predefined cases passed | Domain validity |
| `value_validated` | Independent historical evidence supports the result | Prospective performance |
| `prospectively_validated` | Frozen forward protocol passed | Unlimited deployment |
| `authorized` | Explicit human approval for a bounded use | Permanent safety |

A lower state never implies a higher state. Same-model agreement is not independent corroboration. Self-authored tests prove only what they actually assert.

## 3. Product contract

### Information request

```text
User asks for a fact or statistic
→ return sourced information
→ or DATA_UNAVAILABLE with the missing source named
→ never substitute a wager
```

### Market-analysis request

```text
Resolve exact event + market + selection + settlement rule
→ capture one fresh named-book price and source hash
→ bind one qualified model estimate and lower uncertainty bound
→ evaluate deterministic policy
→ BLOCKED / NO_BET / PAPER_TRACK
```

### Live-money request

```text
Live authority is false
→ BLOCKED
```

No skill, model confidence, agent vote, operator click, or prior winning streak may bypass this contract.

## 4. Work that is explicitly stopped

Until Gates 0 through 6 pass, do not spend project capacity on:

- autonomous betting or auto-placement;
- cross-sport expansion;
- agent swarms, LLM councils, or model-voting systems;
- confidence-tier gamification;
- new dashboards beyond evidence and operational review needs;
- new data providers that do not close a named validation gap;
- parlay generation without exact same-book offers and validated joint estimates;
- UI polish that does not improve decision correctness or auditability;
- marketing, scaling, or profitability claims.

These items may be reconsidered only when a measured failure in the active real-world loop justifies them.

## 5. Ordered release gates

Gates are sequential. A later gate cannot compensate for an earlier failure.

### Gate 0 — Accept the hardening baseline

**Goal:** Establish one reviewed branch whose status, code, tests, and documentation agree.

- [ ] CI is green on the exact proposed merge head.
- [ ] Black and isort pass on the exact proposed merge head.
- [ ] The non-integration test matrix passes on Python 3.10, 3.11, and 3.12 across supported operating systems.
- [ ] Security scans complete and material findings are adjudicated.
- [ ] One independent code review is completed; a bot status that skipped review does not count.
- [ ] `README.md`, `docs/PROJECT_STATUS.md`, `TASKS.md`, and `PAPER_TRADING_PLAN.md` describe the same authority boundary.
- [ ] The branch is merged only after the above evidence is recorded.

**Acceptance:** One commit SHA is designated as the hardening baseline. No earlier green run is inherited by a later commit.

### Gate 1 — Eliminate unsafe legacy execution paths

**Goal:** Ensure no legacy script can silently produce actionable picks, dollar sizes, fabricated validation, or operational history outside the evidence contract.

Audit each path and either route it through the decision contract, disable it by default, or retire it:

- [ ] `scripts/generate_daily_picks.py`
- [ ] `scripts/generate_daily_picks_with_grok.py`
- [ ] `scripts/pregame_prediction_engine.py`
- [ ] `src/orchestrator/master_pipeline.py`
- [ ] `scripts/start_autonomous_system.py`
- [ ] `agents/aggressive_kelly.py`
- [ ] `src/agents/strategy_analyst_agent.py`
- [ ] `src/agents/risk_management_agent.py`
- [ ] `scripts/backfill_2025_season.py`
- [ ] any notification, dashboard, or API route that presents `BET`, stake dollars, or confidence tiers.

Required removals:

- [ ] no placeholder or fixed probabilities may reach a decision path;
- [ ] no LLM confidence may substitute for a model probability;
- [ ] no generated prose may upgrade a betting tier;
- [ ] no mock backtest may mark a strategy validated;
- [ ] no synthetic sample game may enter operational history;
- [ ] no zero-Kelly result may become a forced minimum wager;
- [ ] no model-derived expected value may be labeled closing-line value;
- [ ] no executable default may imply live authority.

**Acceptance:** Regression tests demonstrate that every audited legacy path returns a research-only result, `NO_BET`, or an explicit blocking error without producing actionable stake output.

### Gate 2 — Intent and market-contract integrity

**Goal:** Preserve the user's actual request and the sportsbook's exact settlement contract.

- [ ] Implement explicit intent classes: `information`, `market_analysis`, `paper_tracking`, `live_request`.
- [ ] Require competition, event, market, selection, and settlement semantics.
- [ ] Treat ambiguous phrases such as “Spain to win” as unresolved until the market is explicit: regulation moneyline, qualify/advance, draw-no-bet, futures, or another defined market.
- [ ] Return `DATA_UNAVAILABLE` for missing requested statistics; do not substitute another prop or wager.
- [ ] Require sportsbook, offered price, quote timestamp, event-start timestamp, source, and source SHA-256.
- [ ] Reject stale, suspended, post-start, or incomplete market snapshots.
- [ ] Separate stake, profit, and total return in every output.
- [ ] Reconcile parlay price against the exact quoted ticket and record any boost or pricing-adjustment identifier.

Required World Cup/Spain regression cases:

- [ ] unavailable Mbappé statistic never becomes an alternate wager;
- [ ] “Spain to win” cannot silently become a 3-way regulation moneyline;
- [ ] the visible `-650 / +430 / -500` legs do not reconcile to `+998` without an adjustment receipt;
- [ ] a concentrated longshot leg is identified rather than described as diversification;
- [ ] `NO_BET` is rendered as a successful terminal outcome.

**Acceptance:** Every decision receipt identifies the resolved intent and exact market contract, or names the precise blocker.

### Gate 3 — Immutable data, model, and result bundle

**Goal:** Make every performance claim independently reproducible.

Create one content-addressed result bundle containing:

- [ ] repository commit SHA;
- [ ] immutable dataset snapshot identifier and file hashes;
- [ ] source coverage, as-of timestamps, and prediction cutoff policy;
- [ ] full feature manifest and leakage audit;
- [ ] train, calibration, validation, and untouched final-holdout windows;
- [ ] model class, hyperparameters, seeds, environment, and model digest;
- [ ] exact market source, book, line, price, timestamp, and settlement rules;
- [ ] frozen decision and risk policy;
- [ ] complete opportunity ledger, including blocked, pass, and `NO_BET` outcomes;
- [ ] calibration, uncertainty, drawdown, sensitivity, and subgroup results;
- [ ] exact reproduction command;
- [ ] CI and test evidence for the evaluated commit.

- [ ] Add a schema validator for the bundle.
- [ ] Add a deterministic verifier that recomputes hashes and metrics.
- [ ] Fail closed on any missing, mutable, late, or inconsistent field.

**Acceptance:** A clean environment can reproduce the result and artifact hashes using one documented command. A markdown summary alone cannot pass.

### Gate 4 — Reproduce the honest historical baseline

**Goal:** Establish that the evaluation machinery can reproduce a known negative result before trusting a positive one.

- [ ] Reproduce the post-leakage baseline from immutable data and actual prices.
- [ ] Confirm no future-derived feature or closing information enters pregame features.
- [ ] Confirm pushes, voids, price formats, and settlement rules are correct.
- [ ] Compare calculated metrics with `DATA_LEAKAGE_FIX_REPORT.md` and explain every material difference.
- [ ] Run negative controls and label-shuffle tests.
- [ ] Verify that intentionally corrupted timestamps, prices, and feature cutoffs are rejected.

**Acceptance:** The system reproduces the honest negative baseline within predefined tolerances and catches deliberately introduced leakage. Failure means the validator is not ready to certify a positive result.

### Gate 5 — Produce one qualified model candidate

**Goal:** Select one bounded strategy without data dredging or retrospective rule changes.

- [ ] Pre-register the target market, population, model family, features, thresholds, and evaluation windows.
- [ ] Separate model selection, calibration, threshold selection, and final holdout.
- [ ] Use actual market prices and a no-vig market baseline.
- [ ] Report Brier score, log loss, calibration curve, calibration slope/intercept, and uncertainty.
- [ ] Report ROI and drawdown with block-bootstrap or another justified dependence-aware interval.
- [ ] Correct for multiple strategy and threshold searches.
- [ ] Serialize the executable strategy condition and risk policy.
- [ ] Record `proves`, `does_not_prove`, and `next_proof` in the result bundle.

**Acceptance:** The untouched final holdout meets the pre-registered model, calibration, market, and lower-bound economic criteria. Otherwise the candidate remains `research_only`.

### Gate 6 — Forward paper-trading protocol

**Goal:** Test the frozen system prospectively without real money.

Use [`PAPER_TRADING_PLAN.md`](PAPER_TRADING_PLAN.md) as the controlling protocol.

- [ ] Freeze commit, model, data contract, strategy logic, market scope, thresholds, and risk policy before the first eligible event.
- [ ] Start only after Gates 0 through 5 pass.
- [ ] Capture every eligible opportunity, including blocked and `NO_BET` decisions.
- [ ] Preserve pre-event decision receipts before kickoff.
- [ ] Capture actual closing prices from the same market and settlement source.
- [ ] Settle through authoritative results with correction handling.
- [ ] Do not change thresholds mid-series; any change creates a new version and restarts qualification.
- [ ] Continue until both the minimum time horizon and pre-registered statistical-information requirement are met.

**Acceptance:** The run earns `PASS_TO_LIVE_REVIEW`, `INCONCLUSIVE`, or `FAIL`. It never directly authorizes live betting.

### Gate 7 — Operational resilience

**Goal:** Demonstrate that real-world failures become explicit safe states rather than silent substitutes.

- [ ] Exercise provider outage and rate-limit failure.
- [ ] Exercise stale and conflicting price feeds.
- [ ] Exercise clock drift and event-start boundary handling.
- [ ] Exercise duplicate events and idempotent reruns.
- [ ] Exercise restart, partial-write, and corrupted-ledger recovery.
- [ ] Exercise postponed, void, push, and stat-correction settlement.
- [ ] Exercise notification failure without losing the canonical receipt.
- [ ] Exercise the kill switch and verify no positive decision can pass while armed.
- [ ] Measure data freshness, missingness, decision latency, blocked-rate, and recovery time.

**Acceptance:** Every injected failure produces a deterministic blocker, preserves evidence, and leaves the system recoverable without fabricating a decision.

### Gate 8 — Live-review package

**Goal:** Prepare evidence for a human decision, not automate that decision.

- [ ] Independent review of source data, code, result bundle, and paper ledger.
- [ ] Legal, provider-terms, jurisdiction, account, and operational review.
- [ ] Explicit loss limits, exposure limits, stop conditions, monitoring, and rollback plan.
- [ ] Separate live configuration and credentials from research mode.
- [ ] One-time, bounded authorization recorded in a reviewed commit and operational runbook.

**Acceptance:** The operator may choose `REJECT`, `REMAIN_PAPER_ONLY`, or authorize a narrowly bounded live experiment. The default remains `REMAIN_PAPER_ONLY`.

## 6. Immediate ordered work

Do these in order; do not parallelize tasks that alter the same authority or decision boundary.

1. [ ] Finish exact-head CI and independent review for the hardening PR.
2. [ ] Merge the hardening baseline or record the explicit blocker.
3. [ ] Add a legacy-entry-point inventory with route/disable/retire decisions.
4. [ ] Add World Cup/Spain intent and market-contract regression fixtures.
5. [ ] Disable mock validation, synthetic operational history, LLM tier upgrades, and live-named defaults.
6. [ ] Implement and validate the immutable result-bundle schema.
7. [ ] Reproduce the post-leakage negative baseline from one command.
8. [ ] Pre-register and evaluate one bounded model candidate on an untouched temporal holdout.
9. [ ] Implement the complete forward paper ledger, closing-price capture, and settlement workflow.
10. [ ] Conduct a failure-injection rehearsal before starting prospective paper tracking.

## 7. Decision states

| State | Meaning | Permitted action |
|---|---|---|
| `BLOCKED` | Required intent, market, data, model, price, time, or authority evidence is absent or invalid | Repair evidence; no recommendation |
| `DATA_UNAVAILABLE` | Requested fact cannot be supported by the available source | State the gap; do not substitute a wager |
| `NO_BET` | Evidence is complete enough to evaluate, but policy or lower-bound value does not pass | Record and stop |
| `PAPER_TRACK` | Frozen evidence and policy support prospective paper tracking only | Record immutable receipt; no live action |
| `INCONCLUSIVE` | Forward evidence is valid but insufficient to decide | Continue unchanged or stop; do not promote |
| `FAIL` | Integrity, model, economic, or operational criteria failed | Return to the failed gate |
| `PASS_TO_LIVE_REVIEW` | All predefined paper gates passed | Human review only; no automatic authorization |
| `AUTHORIZED_LIMITED_LIVE` | Explicit bounded operator authorization exists | Operate only within the recorded limits |

## 8. Definition of done

A task is complete only when the repository records:

- the exact requirement and acceptance condition;
- changed files and commit SHA;
- exact verification commands and outputs;
- independent evidence where the claim requires it;
- what the result proves and does not prove;
- rollback or recovery path;
- unresolved risks and next proof.

“Implemented,” “production-grade,” “agent-verified,” “skill-created,” “tests passed,” or “CI green” are never sufficient by themselves.
