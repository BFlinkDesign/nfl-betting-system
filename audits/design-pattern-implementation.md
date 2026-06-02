# Design-Pattern Implementation Review — NFL Betting System

**Date:** 2026-05-31
**Scope:** `src/` (all listed subpackages), `scripts/`, `agents/`, `dashboard/`
**Constraint:** Read-only review. No source code was modified.

> Every file referenced below (with `path:line`) was read in full or in the cited
> region during this review. Two small claims that could not be confirmed are
> marked **Unable to verify**. No code was invented; snippets are either quoted
> from the source or clearly labeled as suggested replacements.

---

## Architecture Overview

This is a large, organically-grown system (~137 in-scope Python files) that
collects NFL odds/stats from several third-party APIs, caches them, engineers
features, runs ML + LLM agents/swarms, scores betting strategies, sizes bets with
Kelly, and persists/visualizes results.

The codebase is, on balance, **more pattern-aware than typical** — it contains
several correctly-built GoF patterns. The dominant problem is not absence of
patterns but **duplication and non-convergence**: the same concern (orchestration,
circuit breaking, bet sizing, persistence, config) is implemented two or three
times in parallel modules that don't share state or a common interface.

Patterns that are genuinely present and well-built:
- **Caching Proxy / multi-layer cache** — `OddsCache` (`src/utils/odds_cache.py:48`):
  memory → file → SQLite with dynamic TTL by kickoff proximity (`_get_dynamic_ttl`,
  line 451) and a token-bucket rate limiter. The strongest component in the repo.
- **Circuit Breaker (resilience)** — implemented **twice**: a hand-rolled
  `CircuitBreaker` (`src/api/request_orchestrator.py:53`) and a `pybreaker`-based
  set with a custom listener (`src/utils/resilience.py:68`, breakers at lines
  125/136/147/158, registry at 166).
- **Facade** — `RequestOrchestrator` (`src/api/request_orchestrator.py:110`)
  composes cache + circuit breaker + token bucket + priority queue + per-API
  clients behind `enqueue`. Also a clean **Command/priority-queue** (`PriorityRequest`
  with `__lt__`, line 45) and request **deduplication** (line 181).
- **Adapter** — `ESPNClient`/`NOAAClient` take an injected cache and present a
  uniform surface (`src/api/espn_client.py:48`, `src/api/noaa_client.py:26`).
- **Factory Method** — `get_llm_client(config)` (`src/agents/llm_council.py:262`)
  is a textbook factory over a provider→class dict; `BaseLLMClient` ABC (line 99)
  is a correct Strategy/Template hierarchy for the five LLM providers.
- **Template Method / ABCs** — `FeatureBuilder` (`src/features/base.py:18`),
  `BaseAgent` (`src/agents/base_agent.py:58`), `BaseLLMClient` — all use
  `@abstractmethod` correctly.
- **Builder / Pipeline** — `FeaturePipeline` (`src/features/pipeline.py:42`) with
  chainable `add_builder` returning `self` (line 55) and ordered `build_features`.
- **Observer / pub-sub** — `MessageBus` (`src/agents/message_bus.py:17`) with
  `subscribe`/`broadcast`/`send` and an `AgentRegistry` (`base_agent.py:248`).
- **Singleton** — done idiomatically via module globals + `@lru_cache`
  (`settings`/`get_settings` in `src/config/settings.py:435-444`, `get_council` in
  `llm_council.py:717`) AND via `__new__` (`src/config/secrets.py:80`,
  `src/swarms/model_loader.py:21`).
- **Strategy + Registry** — `src/strategy_registry.py` (see Finding 1 — good
  *catalog*, but not the executable Strategy pattern the task expected).

Recurring weaknesses (the through-line of this report):
- Two orchestrators (`MasterPipeline` in `src/orchestrator/master_pipeline.py:125`
  and `RequestOrchestrator` in `src/api/request_orchestrator.py:110`).
- Two circuit breakers with no shared state (Finding 2).
- Three+ Kelly bet-sizing implementations (Finding 3).
- Persistence scattered across raw `sqlite3` in 4+ modules with no Repository
  abstraction (Finding 4) — though a schema-aware `QueryBuilder`
  (`src/agents/query_builder.py:15`) exists and is the right seed for one.
- A well-built `settings` singleton that is widely bypassed by hardcoded values
  (Finding 5).
- Two `__new__`-based singletons that are the riskier idiom vs the module-global
  ones used elsewhere (Finding 7).

---

## Prioritized Findings

### 1. `StrategyRegistry` is a metadata catalog, not an executable Strategy registry — Importance 8/10

**File:** `src/strategy_registry.py` — `Strategy` (line 84), `StrategyRegistry` (line 197)

The task specifically asks whether `strategy_registry.py` implements the
Strategy/Registry patterns well. Precise answer: it is an **excellent Registry of
strategy *records*** but **not** the GoF Strategy pattern.

What it does well:
- `Strategy` is a `@dataclass` describing a *discovered* betting pattern
  (`win_rate`, `roi`, `edge`, lifecycle `status` via `StrategyStatus` enum at line
  66) with fuzzy-duplicate detection (`similarity_score` using `SequenceMatcher`,
  line 133), versioning (`create_strategy_version`, line 582), and JSON
  persistence. This is effectively a **Repository over a JSON store** and it is
  thorough and correct.

What is missing: there is no polymorphic `evaluate(game) -> signal`. A `Strategy`
record cannot *make a bet*; the `conditions: Dict` field (line 111) is free-form
and uninterpreted. So accepting/rejecting a strategy in the registry has **no
automatic effect** on what the pipeline bets — actual bet logic lives separately
in `KellyCriterion`, `MasterPipeline.analyze_game`, and the LLM council. The
registry is descriptive, not prescriptive.

Confirmed by usage: callers (`dashboard/app.py:2119/2257/2295`,
`scripts/bulldog_edge_discovery.py:40`) only ever do CRUD/stat reads
(`get_stats`, `add_strategy`); none dispatch executable strategies from it.

**Recommendation:** If strategies should drive bets, add a real Strategy
interface and bind accepted records to executables through the registry:

```python
class BetStrategy(Protocol):
    def evaluate(self, game: GameContext) -> BetSignal | None: ...

_EXECUTORS: dict[str, BetStrategy] = {}
def register_executor(strategy_id: str, impl: BetStrategy): _EXECUTORS[strategy_id] = impl

def active_strategies(reg: StrategyRegistry) -> list[BetStrategy]:
    return [_EXECUTORS[s.strategy_id]
            for s in reg.get_accepted_strategies() if s.strategy_id in _EXECUTORS]
```

The pipeline then runs only `active_strategies(...)`, closing the loop between the
registry's accept/reject decisions and live betting. If the registry is
*intentionally* descriptive-only, rename it `strategy_catalog.py` to remove the
false expectation that it is the Strategy pattern.

---

### 2. Two independent circuit breakers with no shared state — Importance 8/10

**Files:** `src/api/request_orchestrator.py:53` (`CircuitBreaker`),
`src/utils/resilience.py:68-171` (pybreaker breakers + registry),
`src/health/health_check.py:188`

The resilience concern is implemented twice:
- `RequestOrchestrator` carries its **own** hand-written `CircuitBreaker` class
  (line 53), keyed per-API in `self.circuit_breakers` (lines 150-163), wired into
  `_fetch_from_api`/`_process_request` (lines 211-213, 358-359, 386-387). This is
  a correct, thread-safe breaker.
- `src/utils/resilience.py` *separately* defines four `pybreaker.CircuitBreaker`
  instances (`espn_breaker`, `odds_breaker`, `weather_breaker`, `llm_breaker`) with
  a listener (line 68), decorators (`resilient_call` line 283, `with_resilience`
  line 592), and a registry `CIRCUIT_BREAKERS` (line 166). `ESPNClient` uses
  `espn_breaker` directly (`espn_client.py:87,102`).

These two mechanisms cannot see each other's open/closed state. A failure learned
by the orchestrator's breaker is invisible to `espn_breaker` and vice-versa.
Critically, `check_api_health` only queries `resilience.get_circuit_status()`
(`health_check.py:188-195`), so the `RequestOrchestrator`'s breakers are **never
surfaced in health checks** — operational blind spot.

There is also a subtle redundancy *inside* one path: `ESPNClient._make_request`
both checks `espn_breaker.current_state` manually (line 87) *and* calls
`espn_breaker.call(...)` (line 102) while running its own retry loop, so retries +
breaker counting can interact in non-obvious ways.

**Recommendation:** Standardize on the `pybreaker` set (it has listeners, a
registry, and is already health-check-visible). Have `RequestOrchestrator`
delegate to it and delete its own `CircuitBreaker`:

```python
from src.utils.resilience import CIRCUIT_BREAKERS
breaker = CIRCUIT_BREAKERS.get(request.api_name) or CIRCUIT_BREAKERS["odds"]
return breaker.call(self._fetch_from_api, request)
```

This unifies state, makes health checks complete, and removes ~55 lines of
duplicate breaker code.

---

### 3. Bet sizing (Kelly) is implemented three times, inconsistently — Importance 8/10

**Files:** `src/betting/kelly.py:19` (`KellyCriterion`),
`src/orchestrator/master_pipeline.py:453` (`MasterPipeline.calculate_bet_size`),
plus profile constants in `src/config/settings.py:147-169`

There are at least three Kelly implementations:
- `KellyCriterion.calculate_bet_size` (`kelly.py:46`) — fractional Kelly with
  aggressive favorite multipliers (lines 84-114), `min_edge=0.02` default.
- `MasterPipeline.calculate_bet_size` (`master_pipeline.py:453`) — a **separate,
  duplicate** Kelly formula (`kelly = (b*p - q)/b`, line 469) with its own
  fractional logic (`0.25 + confidence*0.25`, line 472) and `max_bet_pct` from
  `PipelineConfig` (line 59). It does **not** use `KellyCriterion` at all.
- `BacktestEngine` (`src/backtesting/engine.py:31`) constructs `KellyCriterion`
  from a free-form `config` dict, so the backtest and the live `MasterPipeline`
  size bets with **different code paths and different defaults**.

This is the most consequential duplication: backtest results will not match live
sizing because the two go through different Kelly math, undermining the whole
point of backtesting. The `min_edge` value also disagrees across sources (0.02 in
`kelly.py`, 0.03 in `settings.betting.min_edge` and `PipelineConfig`).

**Recommendation:** Make `KellyCriterion` the single sizing component and have
`MasterPipeline` and `BacktestEngine` both depend on it, seeded from `settings`:

```python
# master_pipeline.py
from src.betting.kelly import KellyCriterion
self.kelly = KellyCriterion(kelly_fraction=settings.betting.kelly_fraction,
                            min_edge=settings.betting.min_edge,
                            max_bet_pct=self.config.max_bet_pct)
# then: bet = self.kelly.calculate_bet_size(our_prob, decimal_odds, bankroll)
```

Delete `MasterPipeline.calculate_bet_size`. Now backtest and live betting are
provably the same sizing logic.

---

### 4. No Repository abstraction — raw `sqlite3` scattered across 4+ modules — Importance 7/10

**Files:** `src/utils/odds_cache.py:138` (`_init_database`, plus inserts at 318/571),
`src/health/health_check.py:117`, `src/agents/worker_agents.py:89/107`,
`src/data_pipeline.py` (parquet-based cache), and the *good* seed
`src/agents/query_builder.py:15` (`QueryBuilder`)

Persistence is implemented ad hoc in multiple places, each opening its own
`sqlite3.connect`:
- `OddsCache` owns an `odds_snapshots` table (`odds_cache.py:144`) and writes line
  movement itself.
- `DatabaseAgent` (`worker_agents.py:42`) opens `data/odds_history.db` and
  delegates to `QueryBuilder` — which is the **one place doing it right**:
  schema-aware, validated, parameterized CRUD (`store_prediction` line 124,
  `store_bet` line 199, `get_line_movement` line 74).
- `health_check.py` opens databases directly for integrity checks.
- `src/data_pipeline.py` (`NFLDataPipeline`) is a separate parquet-file repository
  for nflverse data with its own caching (`cache_days`, line 61).

So `QueryBuilder` already proves a clean Repository is achievable, but `OddsCache`
and the rest bypass it and write the same `odds_snapshots` table through different
code. Two writers, one table, different column handling → drift risk.

**Recommendation:** Promote `QueryBuilder` (or a thin `OddsHistoryRepository`
wrapping it) to *the* persistence interface and route `OddsCache`'s
`_store_to_database` (`odds_cache.py:315`) and any other writers through it.
Centralizes schema, connection lifetime, and parameterization, and removes the
duplicate `odds_snapshots` write path.

---

### 5. `settings` config singleton is well-built but widely bypassed — Importance 7/10

**File:** `src/config/settings.py` (singleton via `@lru_cache get_settings`, line
435; instance `settings`, line 444), vs. `src/betting/kelly.py:22-28`,
`src/orchestrator/master_pipeline.py:472`, `src/backtesting/engine.py:32-35`

`settings` is genuinely good: layered sources (env → `.env` → Streamlit secrets →
`config.yaml` → defaults), nested pydantic groups (`BettingSettings.kelly_fraction`
line 151 with a validator at 171, `min_edge` line 161), a pydantic-free
`FallbackSettings` (line 448), `reload_settings` (line 500), and a single cached
instance. This is the right way to do a config singleton.

But adoption is near-zero in the betting core:
- `KellyCriterion.__init__` hardcodes `kelly_fraction=0.25`, `min_edge=0.02`, etc.
  (`kelly.py:22-28`) instead of reading `settings.betting.*` — and `min_edge` even
  contradicts `settings.betting.min_edge=0.03`.
- `MasterPipeline.calculate_bet_size` hardcodes the fractional-Kelly range
  (`master_pipeline.py:472`) and `PipelineConfig` re-declares thresholds
  (lines 49-50, 59) that already exist in `settings`.
- `MasterPipeline.fetch_todays_games` reads `os.getenv("ODDS_API_KEY")` directly
  (`master_pipeline.py:250`) instead of `settings.api.odds_api_key`.

**Recommendation:** Default these components from `settings`, keeping explicit
args only for test overrides:

```python
class KellyCriterion:
    def __init__(self, kelly_fraction=None, min_edge=None, ...):
        b = settings.betting
        self.kelly_fraction = b.kelly_fraction if kelly_fraction is None else kelly_fraction
        self.min_edge = b.min_edge if min_edge is None else min_edge
```

This makes the "single source of truth" actually authoritative (and pairs with
Finding 3).

---

### 6. No shared DTO/value object for predictions & bet signals — Importance 6/10

**Evidence:** the codebase uses dataclasses well *within* modules — `PickResult`
(`master_pipeline.py:92`), `GameData` (line 62), `PickAnalysis`/`CouncilDecision`
(`llm_council.py:69/82`), `CacheStats` (`odds_cache.py:26`), `SwarmDecision`
(`swarm_base.py:23`) — but they are **module-local and non-shared**.

Across layers, betting data degrades to loose params and dicts: `KellyCriterion`
takes bare floats plus `recent_performance: dict` (`kelly.py:46-51`);
`BacktestEngine` reads rows by string key (`row["pred_prob"]`, `row["odds"]`,
`engine.py:70-94`); `MasterPipeline` builds a dict for the council
(`master_pipeline.py:421-435`) and `QueryBuilder.store_prediction` validates a
free `dict` by string keys (`query_builder.py:139-147`). There is no single
`Prediction`/`BetSignal` type shared by producer and consumer, so column/key
names are an informal contract checked only at runtime.

**Recommendation:** Define one shared frozen dataclass for the producer→consumer
contract and use it at the Kelly, backtest, and persistence boundaries:

```python
@dataclass(frozen=True)
class Prediction:
    game_id: str
    prob_win: float
    odds: float            # decimal
    recent_win_rate_10: float | None = None
```

`PickResult` already proves the team is comfortable with rich dataclasses; the gap
is purely that the *inter-layer* contract isn't one.

---

### 7. Two `__new__`-based singletons are the riskier idiom vs the module-global ones used elsewhere — Importance 5/10

**Files:** `src/config/secrets.py:80` (`SecretsManager.__new__`),
`src/swarms/model_loader.py:21` (`ModelLoader.__new__`), vs. the cleaner
`get_settings`/`settings` (`settings.py:435/444`) and `get_council`
(`llm_council.py:717`)

The codebase mixes two singleton idioms. The module-global + accessor idiom
(`settings`, `_council_instance`/`get_council`, `message_bus` at
`message_bus.py:122`, `agent_registry` at `base_agent.py:282`) is clean and
Pythonic. The `__new__`-guarded idiom in `secrets.py` and `model_loader.py` uses
the `_instance` + `_initialized` flag pattern — which works but is the classic
footgun: `__init__` still re-runs on every `ClassName()` call, so any future
`__init__` body must guard on `self._initialized`. `secrets.py` also wraps this in
`@lru_cache` at line 180, layering two singleton mechanisms on the same object.

**Recommendation:** Standardize on the module-global + `@lru_cache` accessor idiom
the project already uses well for `settings`. Replace the `__new__` guards with:

```python
@lru_cache(maxsize=1)
def get_secrets() -> SecretsManager: return SecretsManager()
```

and a plain `__init__`. Removes the `_initialized` footgun and the
double-singleton in `secrets.py`.

---

### 8. Caching Proxy is not enforced — callers can and do bypass the cache — Importance 6/10

**Files:** `src/utils/odds_cache.py`, `agents/api_integrations.py:161-287`,
`src/api/request_orchestrator.py:221`

`OddsCache` is excellent, but it is a *collaborator* objects pass around rather
than a transparent Proxy in front of the client, so caching depends on each
caller remembering to use it — and they don't do it uniformly:
- Good path: `RequestOrchestrator._fetch_from_api` does cache-check then
  `self.cache.set` (`request_orchestrator.py:221, 366`).
- Leaky path: `agents/api_integrations.py` re-implements cache-aside inline
  (lines 222-287) with its own `force_refresh`, `should_fetch_fresh`, and
  `max_age_minutes` fallbacks (2hr/4hr). And `MasterPipeline.odds_api`
  (`master_pipeline.py:152`) constructs `TheOddsAPI()` directly, so its caching
  behaviour depends on that class's internals, not the orchestrator's.

**Recommendation:** Wrap the raw client in a caching proxy implementing the same
interface so it cannot be bypassed:

```python
class CachedOddsClient:
    def __init__(self, inner, cache: OddsCache):
        self._inner, self._cache = inner, cache
    def get_nfl_odds(self, **kw):
        hit = self._cache.get("nfl_odds")
        if hit is not None: return hit.get("data")
        data = self._inner.get_nfl_odds(**kw)
        self._cache.set({"data": data}, "nfl_odds")
        return data
```

Inject it wherever `TheOddsAPI()` is built today and delete the hand-rolled cache
logic in `api_integrations.py`.

---

### 9. `OddsCache` carries two competing rate-limit surfaces — Importance 4/10

**File:** `src/utils/odds_cache.py:98` (`api_usage` dict) vs. line 107
(`token_bucket`)

`OddsCache` keeps a legacy `self.api_usage` dict (line 98) *and* a
`MultiAPITokenBucket` (line 107). `record_api_call` (line 616) and
`should_fetch_fresh` (line 659) update/read both, with the bucket primary and the
dict a hand-synced shadow (`if self.token_bucket: ... else: <legacy>`). This is
duplicate state that can drift. The class also mixes three responsibilities
(caching, the historical-odds DB, and rate limiting).

**Recommendation:** Make the token bucket the single source of truth, derive any
"remaining/monthly" figures from it on demand, and delete `self.api_usage`.
Optionally extract the line-movement DB (`get_line_movement`, line 501) into the
Repository from Finding 4.

---

### 10. `MasterPipeline` mostly avoids the god-object trap — keep it that way — Importance 3/10 (largely positive)

**File:** `src/orchestrator/master_pipeline.py:125`

Worth noting as a *good* pattern: `MasterPipeline` uses lazy-loading `@property`
accessors for every collaborator (`odds_api`, `espn_api`, `llm_council`,
`research_agent`, `adaptive_engine`, `visualizer`, lines 151-221) plus a
fallback-chain in `fetch_todays_games` (odds → ESPN, lines 250-317). This is a
reasonable Facade and keeps construction cheap. The only blemishes are the
duplicate Kelly (Finding 3), direct `os.getenv` (Finding 5), and that
collaborators are not injectable for testing (the properties hardcode the concrete
class). A minimal improvement: let `__init__` accept optional pre-built
collaborators and fall back to lazy construction, enabling test doubles without
monkeypatching imports.

---

## Missing / Under-used Patterns Worth Adding

- **Chain of Responsibility for bet acceptance (Importance 5/10):** Bet gating is
  spread across `KellyCriterion` thresholds (`kelly.py:66-74`), `PipelineConfig`
  thresholds (`master_pipeline.py:49-50`), the LLM council's `_assign_tier`
  (`llm_council.py:686`), and `settings.betting.*`. An ordered chain
  (min-probability → min-edge → tier → bankroll cap → exposure limit) would make
  risk rules explicit, ordered, and individually testable instead of scattered.

- **Unify the two orchestrators (Importance 5/10):** `MasterPipeline` (pipeline
  stages) and `RequestOrchestrator` (API queueing/resilience) are complementary,
  but `MasterPipeline` builds `TheOddsAPI()` directly rather than routing through
  `RequestOrchestrator`, so its API calls miss the priority queue, dedup, and
  breaker. Having `MasterPipeline` fetch via `RequestOrchestrator` would give the
  whole pipeline one resilient data path.

- **Observer at the pipeline layer (Importance 4/10):** A real `MessageBus`
  already exists (`message_bus.py:17`) and is used by agents. Pipeline side
  effects (notifications, audit, visualization) are still driven by direct calls
  in `MasterPipeline.run_daily_pipeline` (lines 648-705). Emitting pipeline
  lifecycle events (`pick_generated`, `pipeline_complete`) onto the existing bus
  and letting sinks subscribe would decouple them — reusing the bus you have
  rather than inventing a second eventing system.

---

## Items Unable to Verify

- Whether the top-level `agents/` package classes (`agents/api_integrations.py`,
  `agents/aggressive_kelly.py`, etc.) conform to the `src/agents/base_agent.py`
  `BaseAgent` contract — they appear to be a separate, looser agent family
  (`MasterPipeline` imports `TheOddsAPI`/`ESPNAPI` from `agents.api_integrations`,
  not from `src/agents`), but their full class definitions were not read.
- The task referenced `src/utils/odds_cache.py` as the Proxy example (confirmed,
  correct) and a `features/data_pipeline.py` — no such file exists; the actual
  modules are `src/data_pipeline.py` (parquet/nflverse repository) and
  `src/features/pipeline.py` (the `FeaturePipeline` builder).
