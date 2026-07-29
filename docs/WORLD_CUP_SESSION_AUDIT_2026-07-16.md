# World Cup ChatGPT Session Audit and NFL Product Disposition

**Audit date:** 2026-07-16  
**Source title:** `2026 FIFA World Cup Briefing`  
**Source file:** `ChatGPT-2026 FIFA World Cup Briefing.json`  
**Source SHA-256:** `b0fbd7ff037720647c3836eca026b0eed00f1aaf1b4033b26c605ab659a7db00`  
**Source record:** 65 messages, 32 user messages, 33 assistant messages, parse successful, no attachment placeholders  
**Project disposition:** selected controls adopted; all-sports platform proposal rejected; no live-money authority

## 1. Evidence and authority boundary

The source proves what the user asked, what the assistant claimed, and what appeared in the supplied sportsbook screenshots. It does not prove that:

- assistant-generated probabilities were calibrated;
- a displayed or suggested wager had positive expected value;
- a named sportsbook assistant used any particular model, classifier, retrieval system, or system prompt;
- a large simulation count improved decision quality;
- a Claude output, skill, prompt, or generated architecture was correct;
- an all-sports autonomous platform was justified by the observed workflow.

Every chat statement, Claude artifact, skill, and generated design is treated as a hypothesis or mechanism. Current code, immutable evidence, independent evaluation, and observed outcomes outrank it.

## 2. What the session mixed together

The conversation combined three distinct tasks that require separate evidence standards:

1. **Tournament briefing:** match status and narrative interpretation.
2. **Black-box product observation:** screenshots of an assistant retrieving markets and composing bet cards.
3. **System design:** a proposed autonomous multi-sport betting platform.

The interface observations are useful product evidence. They do not validate the betting logic. The final architecture also expanded far beyond what one soccer workflow demonstrated.

## 3. Mechanisms worth retaining

### 3.1 Verify the exact market

The observed interface could surface a named selection, book price, and potential return. This is useful only when the raw provider response is archived before the event, content-hashed, and tied to the rendered decision. A card or assistant sentence is not sufficient market evidence.

### 3.2 Resolve the objective before ranking

“Safest,” “highest probability,” “best value,” “highest payout,” and “turn a bankroll into a target” are different optimization problems. The system must record the objective, constraints, and stop conditions before it evaluates candidates. Ambiguity falls back to `NO_BET`.

### 3.3 Separate probability from price

The most likely outcome is not automatically the best wager. Probability describes an event estimate; price determines payout and break-even probability. Expected value requires both and must be evaluated at a conservative probability bound.

### 3.4 Make passing a first-class result

A system that always produces a ticket is structurally biased toward action. The default output remains `NO_BET` when evidence, price, freshness, correlation, or authority is insufficient.

## 4. Rejected reasoning

### 4.1 Unsupported exact probabilities

The session assigned exact championship or match probabilities without a versioned model, training/evaluation record, data cutoff, calibration evidence, or uncertainty interval. Narrative descriptions are not probability evidence.

**Disposition:** session-generated probability claims remain unverified.

### 4.2 Price-invariant advice

Advice that would choose the same side at materially different prices is mathematically unsound. Price alone can move a wager from negative to positive expected value.

**Disposition:** every candidate must include a minimum acceptable price derived from a conservative probability lower bound.

### 4.3 Break-even arithmetic treated as full analysis

Converting American odds to implied break-even probability is useful arithmetic, but it does not establish value. A valid decision also needs model probability, uncertainty, exact book/time/source, vig-aware market comparison, and reproducible provenance.

**Disposition:** retain the arithmetic primitive; reject conclusions that stop there.

### 4.4 Same-game parlay correlation blindness

Player goals, assists, shots, minutes, opponent tactics, and game state are dependent. Multiplying marginal probabilities does not produce a defensible joint probability. A sportsbook’s offered parlay price may also include correlation adjustments that cannot be reconstructed from single-leg prices.

**Disposition:** a paper-track parlay requires a distinct validated joint-probability estimate for the exact leg set and one exact same-book parlay offer. Marginal products are diagnostics only.

### 4.5 Simulation-count theater

More Monte Carlo draws reduce sampling noise inside the selected model. They do not repair leakage, stale inputs, misspecified distributions, unmodeled dependence, weak calibration, or selection bias.

**Disposition:** simulation count is not a release gate. Held-out calibration, uncertainty coverage, reproducibility, and forward decision performance are.

### 4.6 Ticket-factory selection bias

Generating thousands of combinations and selecting the most attractive output creates a multiple-testing problem. Without a bounded or pre-registered candidate set and untouched evaluation data, false edges are expected.

**Disposition:** candidate growth is bounded before scoring; unbounded combinatorial search is rejected.

### 4.7 Staged rollover presented as safer

Rolling the full bankroll through sequential wagers does not automatically improve the probability of reaching a target. If every stage must win, total success probability compounds. Updated information, withdrawal rules, and stop conditions can change the mechanics, but they must be defined and tested.

**Disposition:** no staged-rollover safety claim without an explicit policy and independent evaluation.

### 4.8 Scope expansion to every sport

The source did not demonstrate portable data contracts, calibration, settlement rules, or model validity across sports and markets.

**Disposition:** this repository remains NFL-specific until one NFL paper-trading loop closes with complete evidence.

### 4.9 Outcome correctness as the promise

A sound decision can lose and an unsound decision can win. Learning directly from realized wins and losses without preserving the pre-event mechanism creates post-hoc reinforcement.

**Disposition:** outcome and mechanism are separate records. The product promises an auditable decision process, not guaranteed wins.

## 5. Repository hardening resulting from the audit

### 5.1 Immutable decision contracts

`src/betting/decision_contracts.py` requires:

- exact event, market, selection, sportsbook, price, and timestamps;
- archived source and SHA-256 hash;
- versioned model and evaluation identifiers;
- point probability and a conservative lower bound;
- pre-event data cutoff;
- qualified evidence maturity;
- price freshness and event-start checks;
- lower-bound expected value;
- a minimum acceptable price threshold;
- an auditable receipt with action, evidence, authority, blockers, checkpoint, and fallback.

The only positive output is `PAPER_TRACK`. Live authority remains false.

### 5.2 Paper-decision CLI

`scripts/evaluate_paper_decisions.py` converts evidence into deterministic receipts. Missing or malformed evidence becomes an explicit `NO_BET` record instead of a synthetic default or hidden failure.

### 5.3 Parlay redesign

`scripts/parlay_generator.py` no longer:

- synthesizes missing prices from model probability;
- treats multiplied marginal probabilities as joint probability;
- combines prices from different books into an impossible ticket;
- sizes bankroll risk;
- promotes a confidence label as evidence.

It requires one exact same-book offer and one distinct validated joint estimate for the exact leg set. Combination growth is bounded before selection.

### 5.4 Kelly authority boundary

`src/betting/kelly.py` removes favorite multipliers, hot-streak bonuses, ten-percent sizing, and historical “proven strength” assumptions. Analytical fractions use a qualified probability lower bound and cap at two percent. Dollar sizing raises in paper mode and requires explicit live mode, `live_validated` evidence, and one-time authorization.

## 6. Real-world operating contract

Every operator-facing candidate must state:

1. **Objective** — the metric being optimized.
2. **Exact action** — event, market, selection, sportsbook, and minimum price.
3. **Evidence** — immutable market and model/evaluation artifacts.
4. **Uncertainty** — point estimate plus conservative lower bound.
5. **Authority** — research, paper tracking, or explicitly approved live execution.
6. **Blockers** — missing data, stale price, ambiguous market, invalid dependence model, or insufficient lower-bound EV.
7. **Checkpoint** — expiry time or next required evidence.
8. **Fallback** — `NO_BET`.

## 7. Acceptance criteria for forward paper use

Paper tracking is permitted only when:

- provider responses are archived before event start and hashed;
- event, market, selection, line, price, book, and time are exact;
- model estimates are tied to a commit and immutable evaluation artifact;
- lower probability bounds demonstrate coverage on independent temporal data;
- prices are within the configured freshness window;
- parlays have exact book offers and independently evaluated joint estimates;
- candidate sets are bounded or pre-registered before scoring;
- every decision is retained and settled, including passes and no-bets;
- no threshold is changed retrospectively during the paper window.

## 8. Remaining blockers

This audit does not establish an NFL edge. Remaining blockers include:

- one reproducible, leakage-audited model artifact;
- no-vig market normalization and exact price history;
- calibration and uncertainty coverage by season and market;
- independent joint-probability evaluation for parlays;
- complete forward paper settlement and pass logging;
- legal, provider, and operational review before any live-money status change;
- explicit operator authorization in the canonical project-status file.

Until those gates pass, the correct real-world behavior is **decision support, paper tracking, or NO BET—not autonomous wagering**.
