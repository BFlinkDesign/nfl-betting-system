# Forward Paper-Trading Protocol

**Effective date:** 2026-07-16  
**Status:** Required release gate; not optional validation  
**Authority:** Paper tracking only; no live wager authority  
**Start date:** Not scheduled. The run starts only after Gates 0 through 5 in [`TASKS.md`](TASKS.md) pass.  
**Controlling status:** [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)

This protocol replaces the obsolete January 2025 four-week plan. Four weeks of selective NFL results cannot establish a durable edge, and a favorable paper result never directly authorizes live money.

## 1. Objective

Test one frozen NFL decision policy prospectively under real market and operational conditions without risking money.

The protocol must answer four separate questions:

1. **Integrity:** Did every decision use only information available before the event?
2. **Model quality:** Were the probabilities calibrated and at least as informative as the market baseline?
3. **Economic quality:** Did candidates retain positive value at actual available prices after uncertainty?
4. **Operational quality:** Did outages, ambiguity, stale data, duplicates, and settlement corrections fail safely?

A winning record alone is insufficient. A losing record may still reveal a sound mechanism, but it does not pass the economic release gate.

## 2. Non-negotiable principles

- No real money is placed.
- The policy is frozen before the first eligible event.
- Every eligible opportunity is logged, including `BLOCKED`, `DATA_UNAVAILABLE`, and `NO_BET`.
- Missing information never becomes a substitute wager.
- Ambiguous markets never receive silent interpretation.
- Actual offered sportsbook prices are required; synthetic or model-derived prices are prohibited.
- Every decision is sealed before event start.
- Every policy or code change creates a new version and a new qualification series.
- A pass advances only to human live review; it does not authorize deployment.

## 3. Preconditions

Paper tracking may begin only when all items are complete.

### 3.1 Frozen release identity

- [ ] repository commit SHA;
- [ ] model identifier and SHA-256;
- [ ] immutable dataset snapshot identifier and source hashes;
- [ ] feature manifest and leakage-audit result;
- [ ] strategy/policy version and serialized executable condition;
- [ ] market scope and settlement rules;
- [ ] price source and provider contract;
- [ ] calibration method and artifact;
- [ ] risk-policy version;
- [ ] exact reproduction command;
- [ ] green CI and independent review on the exact commit.

### 3.2 Historical qualification

- [ ] the honest post-leakage negative baseline is reproducible;
- [ ] deliberately introduced leakage and late data are rejected;
- [ ] model selection, calibration, threshold selection, and final holdout are temporally separated;
- [ ] the untouched final holdout passes pre-registered calibration and lower-bound economic criteria;
- [ ] all searched strategies and thresholds are included in multiplicity control;
- [ ] the candidate is classified `out_of_sample_validated`.

### 3.3 Operational readiness

- [ ] system clock and timezone behavior are verified;
- [ ] quote freshness and event-start boundaries are tested;
- [ ] duplicate and idempotent reruns are tested;
- [ ] partial-write and corrupted-ledger recovery are tested;
- [ ] postponed, void, push, and correction handling are tested;
- [ ] kill switch is tested;
- [ ] live-money configuration remains impossible from the paper command path.

## 4. Frozen protocol manifest

Before the first event, create and hash one protocol manifest containing:

```text
protocol_id
repository_commit
model_id
model_hash
dataset_snapshot_id
feature_manifest_hash
strategy_id
strategy_logic_hash
market_scope
sportsbook_scope
settlement_policy
prediction_cutoff_policy
quote_max_age_seconds
minimum_lower_bound_ev
minimum_probability_advantage
paper_unit_definition
single_candidate_cap
parlay_candidate_cap
daily_exposure_cap
maximum_paper_drawdown
minimum_observation_period
minimum_settled_candidates
statistical_method
stopping_rules
```

Recommended conservative defaults, unless a stricter value is pre-registered and justified:

```text
single candidate cap:       0.50% of hypothetical bankroll
parlay candidate cap:       0.25% of hypothetical bankroll
daily exposure cap:         1.00% of hypothetical bankroll
maximum paper drawdown:    10.00%
quote maximum age:          300 seconds
minimum observation period: one complete NFL regular season
minimum settled candidates: 100 PAPER_TRACK decisions
```

A justified power analysis may require more observations. A smaller minimum is not allowed merely because the season ended or the early results looked favorable.

## 5. Decision taxonomy

| State | Meaning | Paper action |
|---|---|---|
| `BLOCKED` | Required intent, market, source, model, time, or authority evidence is invalid or absent | Record blocker; no candidate |
| `DATA_UNAVAILABLE` | Requested factual information cannot be sourced | State missing source; no substitute wager |
| `NO_BET` | Evidence can be evaluated but the frozen policy does not pass | Record zero exposure |
| `PAPER_TRACK` | Complete frozen evidence passes the paper-only policy | Record hypothetical exposure and seal receipt |
| `EXPIRED` | Price or decision receipt is no longer valid | Do not reuse; refresh and create a new receipt |
| `SETTLED` | Authoritative result and settlement rule have been applied | Preserve immutable settlement record |
| `CORRECTED` | Authoritative result or market settlement changed later | Append correction; never rewrite the original receipt |

## 6. Required pre-event record

Every eligible opportunity must include:

### Identity and intent

- protocol ID;
- opportunity ID;
- request/intent class;
- competition, event, teams, and event ID;
- market key and human-readable market name;
- selection key;
- settlement rule;
- event-start timestamp with timezone.

### Market evidence

- sportsbook and source;
- raw market snapshot or content-addressed locator;
- offered American and decimal odds;
- quote-observed timestamp;
- quote age;
- market status;
- source SHA-256;
- complete outcomes required to calculate no-vig market probability;
- promotion, boost, or pricing-adjustment ID when applicable.

### Model evidence

- estimate ID;
- model ID and digest;
- evaluation ID;
- point probability;
- conservative probability lower bound;
- data-cutoff timestamp;
- estimate-generated timestamp;
- evidence maturity;
- model artifact SHA-256.

### Decision evidence

- market no-vig probability;
- point and lower-bound expected value;
- minimum acceptable price;
- policy thresholds;
- decision state;
- blockers and reasons;
- decision expiry;
- hypothetical stake fraction, if `PAPER_TRACK`;
- deterministic decision-receipt hash.

`Stake`, `profit`, and `total return` must be separate fields.

## 7. Information and ambiguity rules

The Spain/World Cup failure becomes a permanent regression standard.

- A factual question is answered with sourced facts or `DATA_UNAVAILABLE`.
- Missing Mbappé or team statistics cannot produce a different player prop.
- “Spain to win” is unresolved until the system identifies whether it means regulation moneyline, qualify/advance, draw-no-bet, tournament winner, or another exact market.
- A 3-way soccer moneyline must identify draw settlement explicitly.
- A parlay quote that differs from visible leg multiplication must contain a boost or pricing-adjustment receipt; otherwise it is blocked.
- A longshot leg driving most of the failure probability must be surfaced as concentration, not diversification.

## 8. Straight-candidate rules

A straight candidate may receive `PAPER_TRACK` only when:

1. the intent and exact market are resolved;
2. the market snapshot is fresh, complete, pre-event, and placeable at one named book;
3. the model estimate is qualified and created from pre-event data;
4. the lower probability bound exceeds the no-vig market probability by the frozen minimum;
5. lower-bound expected value exceeds the frozen minimum;
6. the offered price meets or exceeds the calculated minimum acceptable price;
7. all hashes and identifiers are present;
8. exposure limits remain within the frozen policy.

Otherwise the result is `BLOCKED` or `NO_BET`.

## 9. Parlay rules

Parlays are disabled unless every requirement below is satisfied:

- all legs are individually eligible at the same sportsbook;
- one exact same-book parlay offer exists for the exact leg set;
- one distinct, pre-registered, dependency-aware joint model covers the exact leg set;
- a point joint probability and conservative joint lower bound are recorded;
- the joint estimate has its own model/evaluation identifiers and artifact hash;
- the actual parlay quote is fresh and archived;
- any boost or same-game-parlay pricing adjustment is identified;
- lower-bound expected value is positive under the frozen policy;
- the parlay exposure cap is applied.

Multiplying marginal leg probabilities may be retained as a diagnostic only. It can never serve as the joint probability or authorize a candidate.

## 10. Closing-price and settlement capture

### 10.1 Closing price

For every `PAPER_TRACK` decision:

- capture the closing price for the same event, market, selection, book scope, and settlement definition;
- record close timestamp and source hash;
- calculate closing-line value from decision price versus actual closing price;
- do not label model expected value as CLV;
- preserve unavailable or incomparable closes explicitly rather than imputing them.

### 10.2 Settlement

- use an authoritative result source;
- record settlement timestamp, source, source hash, and rule applied;
- support win, loss, push, void, partial void, postponed, abandoned, and correction states;
- append corrections with reason and prior/new values;
- never rewrite the pre-event decision receipt.

## 11. Duration and stopping rules

The default qualification series continues until all are true:

1. one complete NFL regular season has elapsed;
2. at least 100 `PAPER_TRACK` candidates are authoritatively settled;
3. the pre-registered statistical-information requirement is met;
4. all operational and integrity reviews are complete.

If the strategy is too selective to reach sufficient information, the result is `INCONCLUSIVE`; low volume does not justify relaxing thresholds after the fact.

Immediate stop conditions:

- any live-money action;
- discovered leakage or late feature;
- missing or altered pre-event receipts;
- silent price, market, or model substitution;
- post-start decision generation;
- policy change without a new protocol version;
- maximum paper drawdown exceeded;
- material provider or settlement mismatch;
- repeated operational failure that invalidates the ledger.

A stopped run is preserved and classified. It is not edited into a pass.

## 12. Metrics

### 12.1 Integrity metrics

- eligible opportunities versus logged opportunities;
- percentage with complete pre-event receipts;
- percentage with verified source/model hashes;
- late-data and post-start violation count;
- ambiguous-market count;
- stale-quote count;
- silent-fallback count;
- duplicate-decision count;
- settlement-reconciliation rate.

### 12.2 Model metrics

- Brier score;
- log loss;
- calibration curve;
- expected calibration error;
- calibration slope and intercept;
- sharpness/discrimination;
- performance versus the no-vig market baseline;
- subgroup and season/week stability;
- uncertainty coverage.

### 12.3 Market and economic metrics

- actual price versus minimum acceptable price;
- point and lower-bound expected value;
- mean and median CLV;
- CLV uncertainty interval;
- flat-stake ROI;
- policy-sized paper ROI;
- dependence-aware ROI confidence interval;
- maximum drawdown;
- longest losing sequence;
- profit concentration by market, team, price band, and time period;
- sensitivity to quote age and reasonable slippage.

### 12.4 Operational metrics

- provider availability;
- decision latency;
- percentage of decisions completed before cutoff;
- recovery time after failure;
- idempotent rerun success;
- kill-switch effectiveness;
- notification success without receipt loss.

## 13. Weekly review

A weekly review may observe and classify; it may not change the active policy.

Record:

- protocol and commit IDs;
- opportunities, blockers, no-bets, and paper candidates;
- integrity violations;
- data/provider incidents;
- calibration drift indicators;
- price and CLV summaries;
- settlements and corrections;
- drawdown and exposure;
- unresolved uncertainty;
- whether an immediate stop condition exists.

Any proposed policy change is queued for the next protocol version.

## 14. Final decision gates

### 14.1 Integrity gate — all required

- zero live actions;
- zero unresolved leakage or late-data violations;
- zero silent market/model substitutions;
- 100% of eligible opportunities accounted for;
- 100% of `PAPER_TRACK` decisions have sealed pre-event receipts;
- 100% of settled decisions have authoritative settlement evidence;
- exact reproduction succeeds from the frozen bundle.

### 14.2 Model gate — all required

- calibration and scoring metrics meet the pre-registered tolerances;
- the model is not materially worse than the no-vig market baseline;
- uncertainty behavior is acceptable across the relevant probability range;
- no unsupported subgroup or threshold carries the result;
- no material drift invalidates the frozen model.

### 14.3 Economic gate — all required

- dependence-aware lower confidence bound for ROI is above the pre-registered threshold;
- CLV is positive under the pre-registered method and uncertainty requirement;
- maximum drawdown remains within the frozen limit;
- results remain acceptable under reasonable price slippage and exclusion sensitivity;
- profit is not dependent on one unreproducible outlier, promotion, team, or short period.

### 14.4 Operational gate — all required

- no unresolved critical outage or data-integrity defect;
- safe failure behavior is demonstrated;
- duplicate, restart, correction, and kill-switch tests pass;
- monitoring and recovery evidence is complete.

## 15. Final classifications

| Classification | Meaning | Next action |
|---|---|---|
| `FAIL` | One or more integrity, model, economic, or operational gates failed | Return to the failed gate; no live review |
| `INCONCLUSIVE` | Protocol was valid but evidence quantity or uncertainty is insufficient | Continue unchanged, start a new frozen version, or stop |
| `PASS_TO_LIVE_REVIEW` | Every predefined gate passed | Independent human review only |

`PASS_TO_LIVE_REVIEW` is not `AUTHORIZED_LIMITED_LIVE`.

## 16. Live-review boundary

A separate reviewed package is required before any live experiment:

- complete immutable historical and paper bundles;
- independent technical and statistical review;
- provider-terms and jurisdiction review;
- explicit loss, exposure, and stop limits;
- separate live credentials and configuration;
- tested kill switch and rollback;
- narrow scope and expiry;
- explicit operator authorization in a reviewed commit and runbook.

Without that package, the canonical result remains:

```text
RESEARCH_ONLY
PAPER_TRADING
LIVE_MONEY_AUTHORIZED = FALSE
DEFAULT_DECISION = NO_BET
```
