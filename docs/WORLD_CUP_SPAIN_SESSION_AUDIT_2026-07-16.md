# World Cup / Spain ChatGPT Session Audit and Real-World Decision Controls

**Audit date:** 2026-07-16  
**Repository posture:** research and paper trading only  
**Live-money authority:** prohibited  
**Session title:** `2026 FIFA World Cup Briefing`  
**ChatGPT conversation ID:** `6a4ec7ce-04dc-83e8-ac31-ac63ba3b4cc9`  
**Archive SHA-256:** `b0fbd7ff037720647c3836eca026b0eed00f1aaf1b4033b26c605ab659a7db00`

## Evidence boundary

The archive ledger verifies a 65-message session: 32 user turns and 33 assistant turns. The complete provider-native JSON body was not mounted into this audit workspace. This review therefore uses:

1. the exact archive manifest and hash;
2. the file-by-file session ledger;
3. five directly related screenshots recovered from the session;
4. current repository source and tests.

The screenshots are direct evidence of displayed product behavior. They are not proof that a wager was placed, that the quoted market remained available, or that any recommendation was profitable.

## Reconstructed high-signal behavior

The user asked for a parlay involving France, Norway, and Spain to win. A captured sportsbook-assistant surface displayed three 3-way moneyline legs:

- France at `-650`;
- Norway at `+430`;
- Spain at `-500`;
- extracted displayed parlay total: `+998`.

Other captured requests asked for Kylian Mbappe scoring, first-half-shot, goal, and assist statistics. Instead of answering the requested facts with a source, scope, and denominator, the product repeatedly returned available wager markets.

## Audit verdict

The session contains useful product observations, but its betting behavior is not safe or evidentially complete enough for real-world decision support.

### 1. Information requests were converted into wager offers

A question such as "How many first-half shots does the player average?" is an information request. Returning a `2+ first-half shots` market does not answer it. It also creates an incentive conflict: uncertainty in the answer becomes an opportunity to sell a wager.

**Control:** classify user intent first. `information` produces facts or an honest `DATA_UNAVAILABLE`; it never produces a bet recommendation.

### 2. "To win" was underspecified

For soccer, "to win" can mean a 90-minute 3-way moneyline, to qualify, draw-no-bet, or another settlement rule. Silent conversion to a 3-way moneyline changes the contract.

**Control:** require exact competition, event ID, market ID, market type, selection, start time, settlement rule, bookmaker, and observed price.

### 3. The parlay's apparent diversification hid concentrated risk

Two legs were heavy favorites; Norway at `+430` was the dominant failure risk. Adding heavy favorites does not make the longshot safe. It adds additional ways to lose and must be evaluated as a joint payoff, not described by leg count or team-name familiarity.

**Control:** parlays are disabled by default. Enabling them requires an actual bookmaker parlay quote, a dependency-aware joint probability, explicit correlation evidence, and a stricter paper-stake cap.

### 4. The visible prices do not reconcile to the extracted parlay total

Multiplying the visible decimal prices corresponding to `-650`, `+430`, and `-500` produces approximately `+633.85`, not `+998`. This does not prove the sportsbook was wrong: an odds boost, omitted leg, OCR error, dynamic repricing, or same-game pricing rule could explain the difference. It does prove the screenshot alone is not a complete execution receipt.

**Control:** compare quoted parlay price with visible leg prices. A difference is blocked unless a promotion or pricing-adjustment receipt identifies the rule.

### 5. Profit and total return were easy to conflate

At `+998`, a $10 stake has $99.80 profit and $109.80 total return. A production UI must label stake, profit, and total return separately.

**Control:** use deterministic payout arithmetic and expose all three values.

### 6. No model or market provenance was visible

The captured surface did not bind the offer to a dataset snapshot, model artifact, source commit, calibration evidence, quote timestamp, raw source receipt, or market freshness limit.

**Control:** every decision is sealed with those identities and a SHA-256 receipt.

### 7. The product lacked a first-class `NO_BET`

The session repeatedly substituted another market when the requested information was unavailable. That behavior optimizes engagement, not decision quality.

**Control:** `NO_BET` is a successful terminal outcome. Missing data, weak edge, stale price, ambiguous market, or insufficient evidence never forces a wager.

### 8. Session scale exceeded decision value

The archive ledger flags giant-context prompting, repeated context transplantation, multiple corrections, reported friction, and high output consumption. The final request asked for one code block after a long session. This is evidence of conversion loss: substantial analysis did not reliably become a compact, executable decision contract.

**Control:** one request produces one bounded receipt with explicit inputs, blockers, decision, calculations, evidence identity, and next proof.

## Implemented repository controls

The hardened decision boundary provides:

- intent separation: information, paper evaluation, and live request;
- exact market identity and complete multi-outcome bookmaker snapshots;
- no-vig normalization for market comparison;
- quote and model freshness limits;
- model artifact, dataset, commit, and evidence-maturity requirements;
- fail-closed `BLOCKED`, valid `NO_BET`, and paper-only `PAPER_CANDIDATE`;
- no synthetic odds and no forced minimum stake;
- fractional Kelly only after evidence and edge gates, conservatively capped;
- parlays off by default;
- explicit joint-probability and correlation evidence for parlays;
- visible-leg versus quoted-parlay price reconciliation;
- unambiguous stake, profit, and total-return arithmetic;
- deterministic, canonical SHA-256 decision receipts.

## Real-world operating sequence

```text
1. Classify user intent.
2. Resolve exact event and settlement market.
3. Capture all outcome prices from one bookmaker snapshot.
4. Persist raw source receipt, timestamp, book, market ID, and start time.
5. Load a provenance-bound model estimate.
6. Reject stale, mismatched, research-only, or post-start inputs.
7. Calculate no-vig market probability, EV, price threshold, and capped paper size.
8. Emit BLOCKED, NO_BET, or PAPER_CANDIDATE with a sealed receipt.
9. Record the paper decision before kickoff; never edit it retrospectively.
10. Settle from an authoritative result source and retain pushes/voids explicitly.
11. Capture an actual closing quote for CLV; do not substitute a model prediction.
12. Review calibration, Brier score, log loss, ROI uncertainty, drawdown, and failure classifications before any evidence promotion.
```

## Release gates

A candidate cannot move beyond research/paper status until all are present:

- immutable dataset and model hashes;
- source commit and reproducible command;
- independent temporal holdout;
- actual historical prices and settlement rules;
- multiplicity-aware selection protocol;
- calibration and uncertainty metrics;
- a predefined forward paper-trading period;
- no retrospective threshold changes;
- human review of conflicts and exclusions;
- explicit authorization change in canonical project status.

## Remaining limitations

- This audit does not contain the complete 65-message provider-native JSON body.
- The screenshot market totals have not been reconciled against a raw sportsbook betslip payload.
- No FIFA match outcome or historical sportsbook availability was used to grade the recommendation after the fact.
- The new decision gate does not validate the underlying NFL model; it prevents unsupported model output from silently becoming an actionable recommendation.
- Legacy production-named scripts remain historical/unsafe until each is routed through the gate or explicitly retired.

## Decision

The World Cup session should be retained as a product failure-and-learning case, not as strategy evidence. Its durable lesson is that the system must answer the user's actual question, expose risk and arithmetic, and make `NO_BET` easier than inventing confidence.
