# SOLID Principles Review — NFL Betting System

**Scope:** `src/` (agents, api, audit, backtesting, betting, config, features, health, learning, notifications, orchestrator, self_healing, strategy_registry.py, swarms, utils, visualization), `scripts/`, `agents/`, `dashboard/`.
**Date:** 2026-05-31
**Method:** Static, read-only inspection. No source was modified. Every `file:line` below was read directly and verified against file contents. Anything that could not be confirmed is explicitly marked **Unable to verify**.

> Scope facts established during the review:
> - `src/strategy_registry.py` is a single 675-line module (not a package), and its `StrategyRegistry` is a clean, well-factored class — the quality bar for the rest of the codebase.
> - `src/orchestrator/` contains only `master_pipeline.py`; there is no `main_orchestrator.py`.
> - `src/swarms/swarm_base.py` (159 lines) defines `SwarmBase` (a plain class, not an `ABC`) with a consensus contract. `ConsensusSwarm`, `ValidationSwarm`, and `StrategyGenerationSwarm` **do** subclass it; `PredictionPipeline` does not.
> - `agents/api_integrations.py` is already split into one class per provider (`TheOddsAPI`, `ESPNAPI`, `NFLVerseAPI`, `NOAAWeatherAPI`, `RedditAPI`) — good separation; not flagged.
> - Across the whole scope there are no `isinstance`-based type dispatches that act as polymorphism substitutes (the `isinstance` calls present are all defensive type-guards), and the only `NotImplementedError` raises are the stub handlers in `src/api/request_orchestrator.py`.

---

## Summary Table

| Principle | Findings | Importance (max) | Worst offenders |
|-----------|---------:|:----------------:|-----------------|
| **S** — Single Responsibility | 3 | 8/10 | `dashboard/app.py` (data load + AI HTTP + secrets + presentation), `src/orchestrator/master_pipeline.py` (`MasterPipeline`) |
| **O** — Open/Closed | 2 | 7/10 | `src/api/request_orchestrator.py:227-345` (two-level endpoint `if/elif`), `dashboard/app.py:607` (`provider` chain) |
| **L** — Liskov Substitution | 1 | 4/10 | `src/swarms/swarm_base.py` (`SwarmBase`/`PredictionPipeline` split — weak-form smell only) |
| **I** — Interface Segregation | 1 | 3/10 | `src/agents/base_agent.py:58` (`BaseAgent` — minor over-provisioning) |
| **D** — Dependency Inversion | 3 | 9/10 | `src/orchestrator/master_pipeline.py:151-221` (concrete deps via lazy properties), `dashboard/app.py:607` (inline LLM client), `src/notifications/*` consumers |

**Verified non-issue:** I initially suspected `ConsensusSwarm` skipped its base initializer. It does **not** — `ConsensusSwarm.__init__` (`consensus_swarm.py:22`) correctly calls `super().__init__(... consensus_rule=ConsensusRule.WEIGHTED)` at line 35, exactly like `ValidationSwarm` (`:26`) and `StrategyGenerationSwarm` (`:22`). All three SwarmBase subclasses honor the base contract; `StrategyGenerationSwarm` and `ValidationSwarm` actually call the inherited `make_decision` (`:83` / `:68`). No Liskov violation there.

---

## S — Single Responsibility

### S1. `dashboard/app.py` mixes data loading, AI HTTP, secrets, domain math, and presentation — **8/10**
**Location:** `dashboard/app.py` (2492 lines).
**Problem:** A single Streamlit module spans every layer:
- **Secrets:** `get_secret()` (97) reads `st.secrets`/`os.environ`; four module-level API keys captured at import (106–109).
- **Data loading:** `load_games()` (230) reads JSON files from hardcoded paths (`data/schedules/current_week_games.json`, 234).
- **External AI HTTP:** `get_ai_analysis()` (594) constructs `OpenAI(base_url="https://api.x.ai/v1", ...)` (609) and a second OpenAI client (621) inline and calls the chat API.
- **Domain math:** nested `american_to_decimal` (1126) and `calculate_parlay_odds` (1132).
- **Presentation:** the bulk of the file (tabs, CSS, `render_*` blocks).

Any change to a data path, an AI endpoint, or an odds formula forces edits to the UI module, and none of it is unit-testable without files and live network.

**Remediation:** Extract collaborators; keep the module presentation-only.
```python
# dashboard/services.py
class GameRepository:        # file/JSON access only
    def load_games(self) -> list[dict]: ...
class AIAnalyst:             # one client-construction site
    def __init__(self, client): self._client = client
    def analyze(self, game) -> str: ...
class OddsMath:              # pure functions
    @staticmethod
    def american_to_decimal(o): ...
```
The render code then receives already-loaded data and an injected `AIAnalyst`.

### S2. `MasterPipeline` coordinates *and* owns I/O, modelling, sizing, persistence, and visualization — **8/10**
**Location:** `src/orchestrator/master_pipeline.py`, `class MasterPipeline` (125).
**Problem:** Beyond orchestration it directly performs many distinct jobs:
- Loads the model from disk by trying hardcoded paths (`_load_model`, 223–243).
- Fetches and normalizes odds/ESPN games (`fetch_todays_games`, 245).
- Computes Kelly bet sizing inline (`calculate_bet_size`, 453–486).
- Serializes picks to JSON, generates visualizations, and writes adaptive-learning records (`run_daily_pipeline`, 577–725).

Bet-sizing math, model-loading, and output rendering are separate responsibilities that should live in their own collaborators; `MasterPipeline` should sequence them.

**Remediation:** Move `calculate_bet_size` into `src/betting/kelly.py`, `_load_model` behind a `ModelProvider`, and the JSON/visual/record steps into a `PickReporter`. The pipeline keeps only the step sequence in `run_daily_pipeline`.

### S3. `ConsensusSwarm` mixes pipeline construction with consensus orchestration (and is half-stubbed) — **5/10**
**Location:** `src/swarms/consensus_swarm.py`, `class ConsensusSwarm` (14).
**Problem:** The class both builds per-model `PredictionPipeline` objects (`_initialize_pipelines`, 68) and runs the multi-phase consensus (`generate_daily_picks`/`_individual_analysis`/`_voting_phase`/`_assign_tier`). Combined with the duplicate `__init__` and the dead second `except` clause (74/76), the responsibilities are tangled and partly non-functional (several methods are `...` stubs returning `[]`).
**Remediation:** Inject the `dict[str, PredictionPipeline]` (built by a small factory) and keep `ConsensusSwarm` focused on voting/consensus.

---

## O — Open/Closed

### O1. `RequestOrchestrator` routes by a two-level `if/elif` chain on endpoint substrings + per-API endpoint names — **7/10**
**Location:** `src/api/request_orchestrator.py`, `_make_api_call` (226–347). Outer dispatch keys off `request.endpoint`/`request.api_name`: `if "odds" in request.endpoint.lower() or request.api_name == "odds_api"` (227), `elif "espn" ...` (256), `elif "noaa" ...` (293), `else: raise NotImplementedError` (345). Each branch then has its own inner `if/elif` over endpoint names (e.g. ESPN: `scoreboard`/`game_summary`/`teams`/`team_schedule`/`standings`/`news` at 266–284) plus an inline lazy `import` and concrete client construction.
**Problem:** Adding a data source means editing the outer chain *and* writing a new branch; adding an endpoint to an existing source means editing that source's inner chain. The router is closed to extension on two axes, and each branch hardwires its concrete client (see D1's sibling pattern). Unhandled cases degrade to `raise NotImplementedError` (247, 286, 337, 345).
**Remediation:** Register one handler object per API, each exposing its own endpoint map:
```python
self._apis = {"odds_api": OddsApiHandler(), "espn_api": EspnHandler(), "noaa_api": NoaaHandler()}
api = self._resolve(request)            # name/substring -> handler
return await api.handle(request)        # handler owns its endpoint dispatch
```
New sources/endpoints are added by registering or extending a handler, not by editing the router.

### O2. AI-provider selection via `if provider == ...` in the dashboard — **5/10**
**Location:** `dashboard/app.py`, `get_ai_analysis` (594): `if provider == "grok" and XAI_API_KEY:` (607) / `if provider == "gpt" and OPENAI_API_KEY:` (619).
**Problem:** Adding a provider means editing this function and adding another inline client-construction block. Small today (two providers), but it is the seam that grows every time a model is added.
**Remediation:** A `PROVIDERS` registry mapping name → an `AIAnalyst` instance (see S1), selected by key, so providers are added by registration rather than by editing the function.

---

## L — Liskov Substitution

### L1. `SwarmBase`'s inherited `make_decision` returns hardcoded-stub votes, so subclasses inherit a non-functional contract — **4/10 (weak-form smell)**
**Location:** `src/swarms/swarm_base.py`, `_collect_votes` (99–123).
**Problem:** This is **not** a classic substitution break — all three subclasses (`ConsensusSwarm`, `ValidationSwarm`, `StrategyGenerationSwarm`) correctly call `super().__init__(...)` and so satisfy the base invariants. The weaker concern is behavioral: `SwarmBase._collect_votes` ignores the agents entirely and returns a fixed `{"vote": "approve", "confidence": 0.8, "reasoning": "Default reasoning"}` for every agent (116–121). `StrategyGenerationSwarm._selection_phase` (`strategy_generation_swarm.py:83`) and `ValidationSwarm` (`validation_swarm.py:68`) then call this inherited `make_decision` and act on a decision that was never actually derived from agent input. The inherited method therefore does not do what its name/docstring promise, so subclasses relying on it get behavior that violates the *spirit* of the contract even though the type signature is honored.
**Remediation:** Either make `_collect_votes` genuinely query agents (via the message bus the code comments already anticipate at 113), or mark `SwarmBase` abstract and force subclasses to supply a real vote-collection implementation, so no subclass silently inherits placeholder consensus.
**Notes on the rest of L:** there are no `isinstance` polymorphism substitutes and no subclasses overriding methods to raise `NotImplementedError` anywhere in scope (the only `NotImplementedError` raises are leaf stub-handlers in `src/api/request_orchestrator.py`). `BaseAgent.run` (`base_agent.py:197`) is a legitimate `@abstractmethod`. `PredictionPipeline` (`prediction_pipeline.py:27`) deliberately does **not** inherit `SwarmBase`, which is correct — it is not a consensus body.

---

## I — Interface Segregation

### I1. `BaseAgent` base is broadly well-segregated; only minor over-provisioning — **3/10**
**Location:** `src/agents/base_agent.py`, `class BaseAgent(ABC)` (58).
**Problem:** This base is actually a good ISP citizen: it forces exactly one abstract method (`run`, 197) and otherwise supplies optional helpers. The mild concern is that **every** agent inherits the tool registry (`register_tool`/`get_tool`, 105/118), the asyncio message queue (`send_message`/`receive_message`/`process_messages`, 122–157), and the memory store (`update_memory`/`get_memory`, 182–190) whether or not it uses them, widening the surface each subclass and its tests must reason about. This is a smell, not a forced-stub problem.
**Remediation (optional polish):** Split optional concerns into mixins/protocols (`Messaging`, `ToolUsing`, `Memoryful`); have `BaseAgent` provide only lifecycle + the abstract `run`, and let agents opt into the mixins they actually need.
**Unable to verify:** whether concrete agents leave these inherited features unused — not all agent subclasses were read in full, so the real severity could be lower or slightly higher.

---

## D — Dependency Inversion

### D1. `MasterPipeline` hard-binds every concrete component (via lazy `@property` instantiation) and hardcoded paths — **9/10**
**Location:** `src/orchestrator/master_pipeline.py`, properties 151–221 and `_load_model` 223–243:
```
155  from agents.api_integrations import TheOddsAPI;    self._odds_api = TheOddsAPI()
164  from agents.api_integrations import ESPNAPI;       self._espn_api = ESPNAPI()
182  from agents.api_integrations import NOAAWeatherAPI;self._weather_api = NOAAWeatherAPI()
191  from src.agents.llm_council import get_council;    self._llm_council = get_council()
200  from src.agents.research_agent import get_research_agent; ...
209  from src.learning.adaptive_engine import get_adaptive_engine; ...
218  from src.visualization.prediction_visualizer import get_visualizer; ...
230  model_paths = [PROJECT_ROOT/"models"/"xgboost_favorites_only.pkl", ...]  # hardcoded
```
**Problem:** The highest-level orchestrator constructs each concrete low-level dependency itself (inside lazy properties that hide the dependency graph via in-method imports) and hardcodes model file paths. It cannot be unit-tested with fakes and cannot swap an implementation (different odds source, an in-memory learner, a stub council) without editing the class.
**Remediation:** Constructor-inject the collaborators against abstractions, resolved once in a composition root (e.g. `scripts/`):
```python
class MasterPipeline:
    def __init__(self, odds, espn, weather, council, research,
                 learner, visualizer, model_provider, config=None): ...
```
Keep lazy loading if desired, but lazily resolve *injected factories*, not hardcoded concretes.

### D2. Dashboard constructs LLM clients and reads paths/secrets directly — **6/10**
**Location:** `dashboard/app.py`: `get_ai_analysis` builds `OpenAI(...)` clients inline (609, 621); `load_games` hardcodes JSON paths (234, 243); `get_secret`/module keys at 97–109.
**Problem:** Presentation depends on concrete SDK clients, concrete file locations, and a concrete secrets mechanism, so it can never be exercised against fakes.
**Remediation:** Inject an `AIAnalyst` and a `GameRepository` (see S1); pass clients/paths/secrets in from a composition root rather than constructing them in the view.

### D3. Notification senders are constructed and configured by their callers, not abstracted — **5/10**
**Location:** `src/notifications/email_sender.py` (`EmailSender.__init__(smtp_user, smtp_password, recipient)`, 20), `src/notifications/sms_sender.py` (`SMSSender.__init__(...)`, 16), `src/notifications/desktop_notifier.py` (16).
**Problem:** These classes are reasonably clean (config is passed in, not read from env internally — a point in their favor), but there is **no common `Notifier` abstraction**: each exposes a differently named method (`send_bet_alert`, `send_quick_alert`, `send_toast`). High-level callers must therefore know each concrete type and method name, so they depend on concretions rather than an interface. (Note `EmailSender` binds to Gmail specifically via `self.smtp_server = "smtp.gmail.com"` at line 35, hardcoding the provider.)
**Remediation:** Define a `Notifier` protocol with a single `send(context) -> bool` and have all three implement it; callers then depend on `list[Notifier]`. Make the SMTP host a constructor parameter rather than a hardcoded Gmail value.
**Unable to verify:** the exact call sites that wire these senders (the consuming scripts under `scripts/` were not all read), so the precise blast radius of D3 is approximate.

---

## Recommended order of attack
1. **D1 + S2** — introduce a composition root and inject `MasterPipeline`'s collaborators; move Kelly sizing into `src/betting/kelly.py` and model loading behind a provider. Highest leverage: unlocks testing of the central orchestrator.
2. **S1 + D2** — split `dashboard/app.py` into `GameRepository` / `AIAnalyst` / `OddsMath` services plus a presentation-only view.
3. **O1 + O2** — replace the endpoint and `provider` `if/elif` chains with per-API/per-provider handler registries (the existing `StrategyRegistry` is the template).
4. **D3** — introduce a common `Notifier` protocol and parameterize the SMTP host.
5. **L1** — give `SwarmBase._collect_votes` a real implementation (or make it abstract) so subclasses stop inheriting placeholder consensus.
6. **I1** — optional mixin/protocol split of `BaseAgent`.
