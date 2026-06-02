# Code Duplication Audit — NFL Betting System

**Repository:** `/home/user/nfl-betting-system`
**Date:** 2026-05-31
**Scope:** `src/`, `scripts/`, `agents/`, `dashboard/` (excluding `*.md`, `tests/`, `*.ipynb`)
**Scoped size:** ~44,886 LOC across ~120 Python modules

## Summary

Duplication is pervasive and falls into three buckets:

1. **Parallel API clients** — ESPN is implemented in **4 separate classes** plus several
   inline `requests.get` call sites; NOAA/weather.gov is implemented in **3 separate
   classes**. Only the `src/api/*` versions have resilience (retries / circuit breaker);
   the agent and script copies silently swallow errors. Behavior has already diverged.
2. **Betting-math helpers** — `american_to_decimal` is redefined in **9 places** and
   `decimal_to_american` in several; the Kelly formula `(p*b-(1-p))/b` is hand-written in
   multiple files. Notably there is **no shared odds/Kelly utility module** — the canonical
   `src/betting/kelly.py` exposes only a `KellyCriterion` class, not reusable functions.
3. **Boilerplate & data constants** — the `sys.path` bootstrap appears **53 times** (and a
   purpose-built helper `src/utils/path_setup.py` exists but is imported by **zero** files);
   `logging.basicConfig` appears **37 times**; stadium-coordinate and team-name dicts are
   copy-pasted across 4–6 files each.

Most fixes are low-risk and mechanical, but the divergence risk is real and already
materialized (e.g. duplicate ESPN clients with/without circuit breakers; `kelly.py` caps at
10% while `agents/aggressive_kelly.py` caps at 75%/10% via different logic).

### Findings sorted by importance

| # | Finding | Type | Key locations | Est. dup | Effort | Imp. |
|---|---------|------|---------------|----------|--------|------|
| 1 | ESPN client implemented 4x (+ inline call sites) | Exact + Near | `src/api/espn_client.py:31` `ESPNClient`; `agents/api_integrations.py:318` `ESPNAPI`; `scripts/fetch_latest_nfl_data.py:26` `ESPNDataFetcher`; `src/api/live_game_tracker.py`; inline: `src/health/health_check.py:171`, `scripts/audit_data_sources.py:181`, `scripts/production_daily_pipeline.py:40`, `src/config/settings.py:106` | ~60–90% across the 3 small clients | M | 9/10 |
| 2 | `american_to_decimal` / `decimal_to_american` / Kelly formula redefined 9x | Exact + Near | `american_to_decimal`: `scripts/parlay_generator.py:39`, `dashboard/parlay_builder.py:281`, `dashboard/pages/1_🧩_Parlay_Builder.py:281`, `scripts/backtest.py:73`, `scripts/train_favorites_specialist.py:33`, `scripts/bulldog_backtest.py:205`, `scripts/pregame_prediction_engine.py:173`, `dashboard/app.py:1126` | ~95% per helper | S–M | 9/10 |
| 3 | NOAA/weather client implemented 3x | Near | `src/api/noaa_client.py:16` `NOAAClient`; `agents/noaa_weather_agent.py:17` `NOAAWeatherAgent`; `agents/api_integrations.py:23` `NOAAWeatherAPI` | ~70% | S–M | 8/10 |
| 4 | `sys.path` bootstrap duplicated 53x; helper exists but unused | Structural | 53 sites (see Finding 4); helper `src/utils/path_setup.py:33` imported by **0** files | identical intent | S | 7/10 |
| 5 | Stadium-coordinate dict copy-pasted | Data | `agents/noaa_weather_agent.py:31` `STADIUMS`; `scripts/generate_daily_picks.py:106` (inline tuples); `scripts/generate_daily_picks_with_grok.py` (inline) | ~100% of overlapping entries | S | 7/10 |
| 6 | ESPN base-URL literal hardcoded 8x | Data | `src/api/espn_client.py:44`, `agents/api_integrations.py:327`, `scripts/fetch_latest_nfl_data.py:29`, `src/config/settings.py:106`, `src/health/health_check.py:171`, `scripts/audit_data_sources.py:181/187`, `scripts/production_daily_pipeline.py:40` | 100% literal (one uses `http://`) | S | 6/10 |
| 7 | `logging.basicConfig(...)` duplicated 37x | Structural | 37 sites across scripts/agents/dashboard (see Finding 7) | identical 1-liner mostly | S | 6/10 |
| 8 | NFL team-name / abbrev maps reimplemented 6x | Data | `scripts/full_betting_pipeline.py:106`, `scripts/generate_daily_picks.py:213`, `scripts/parlay_generator.py:351`, `scripts/pregame_prediction_engine.py:599`, `src/agents/research_agent.py:53`, `src/visualization/prediction_visualizer.py:60` | ~70–100% value overlap | M | 6/10 |
| 9 | ESPN `get_teams` response-parse block copied | Exact | `src/api/espn_client.py` `get_teams`; `agents/api_integrations.py` (ESPNAPI); `scripts/fetch_latest_nfl_data.py:151-167` | ~100% | S | 5/10 |
| 10 | `sqlite3.connect` DB-access boilerplate | Structural | `src/agents/worker_agents.py`, `src/health/health_check.py`, `src/learning/adaptive_engine.py`, `src/utils/odds_cache.py`, `scripts/backup_database.py`, `scripts/manage_cache.py`, `dashboard/auth_system.py`, `dashboard/app_auth.py` | partial | M | 4/10 |

> **Verification:** Findings 1–7 and 9 were confirmed by reading source bodies and/or exact
> `grep -n` line hits. Findings 8 and 10 had their *defining lines* confirmed but the full
> dict/connection bodies were not byte-diffed; the proving step is stated inline.

---

## Detailed findings

### 1. ESPN API client implemented four times — importance 9/10

**Type:** Exact + near duplicate (parallel clients).

**Implementations (all wrap the same ESPN endpoints):**
- `src/api/espn_client.py:31` — `class ESPNClient` — the canonical, resilient one (~320 LOC):
  circuit breaker (`espn_breaker`), exponential backoff (`MAX_RETRIES`,
  `RETRY_BACKOFF_BASE`), rate limiting, fallback cache. `BASE_URL` at l.44.
- `agents/api_integrations.py:318` — `class ESPNAPI` — simplified copy. `get_scoreboard`
  (l.332), `get_teams` (l.368), `get_game_summary` (l.381) replicate the same calls with
  plain try/except. **No resilience.** `BASE_URL` at l.327 (note: `http://`, not `https://`).
- `scripts/fetch_latest_nfl_data.py:26` — `class ESPNDataFetcher` — third copy:
  `get_current_week_games` (l.37), `_parse_game` (l.76), `get_team_info` (l.141).
  Identical session setup (`User-Agent: NFLBettingSystem/1.0`) to `ESPNClient`. `BASE_URL` l.29.
- `src/api/live_game_tracker.py` — yet another ESPN URL/usage path.

Plus inline `requests.get` to the ESPN scoreboard in `src/health/health_check.py:171`,
`scripts/audit_data_sources.py:181`, `scripts/production_daily_pipeline.py:40`.

**Duplication estimate:** The three method-bearing implementations share ~60–90% of their
request + response-parse logic; `get_scoreboard`/`get_teams` are functionally identical.

**Risk (already realized):** Only `ESPNClient` retries / trips a breaker. The agent + script
copies fail silently; one even uses insecure `http://`.

**Extraction:** Make `src/api/espn_client.ESPNClient` the single source of truth. Delete
`ESPNAPI` and `ESPNDataFetcher` and re-point callers:
```python
from src.api.espn_client import ESPNClient
espn = ESPNClient()
data = espn.get_scoreboard()         # replaces ESPNAPI().get_scoreboard() / ESPNDataFetcher
```
**Effort:** M (4 implementations + ~7 inline sites; verify the two script CLIs still run).

---

### 2. American-odds + Kelly helpers redefined ~9 times — importance 9/10

**Type:** Exact + near duplicate (math helpers) with **no canonical home**.

`def american_to_decimal(...)` is defined independently in:
`scripts/parlay_generator.py:39`, `dashboard/parlay_builder.py:281`,
`dashboard/pages/1_🧩_Parlay_Builder.py:281` (parlay_builder + the page are themselves near-
duplicate files), `scripts/backtest.py:73`, `scripts/train_favorites_specialist.py:33`,
`scripts/bulldog_backtest.py:205`, `scripts/pregame_prediction_engine.py:173`,
`dashboard/app.py:1126`. `decimal_to_american` is paired in `parlay_generator.py:47`,
`parlay_builder.py:288`, `pages/1_…:288`.

The Kelly formula `b = odds-1; (prob*b-(1-prob))/b` is hand-written in
`src/betting/kelly.py:79` (inside `KellyCriterion.calculate_bet_size`) and re-derived in
`agents/aggressive_kelly.py` (`optimal_kelly = edge/0.25`, l.58) and in
`scripts/generate_daily_picks.py:503` and `scripts/pregame_prediction_engine.py:527`.

**Important nuance:** `src/betting/kelly.py` contains **only the `KellyCriterion` class**
(confirmed: top-level defs are `class KellyCriterion` at l.19 and method `calculate_bet_size`
at l.46) — there is **no shared `american_to_decimal`/`kelly_fraction` function module**, so
every caller rolls its own. Divergence already exists: `kelly.py` caps at 10%/2%;
`aggressive_kelly.py` clips Kelly fraction to 0.75 then caps dollars at 10%.

**Extraction:** Create `src/betting/odds.py` with pure functions and reuse them everywhere:
```python
# src/betting/odds.py
def american_to_decimal(a: float) -> float:
    return 1 + (a/100 if a > 0 else 100/abs(a))
def decimal_to_american(d: float) -> float:
    return (d-1)*100 if d >= 2 else -100/(d-1)
def american_to_implied(a: float) -> float:
    return 100/(a+100) if a > 0 else abs(a)/(abs(a)+100)
def kelly_fraction(p: float, dec_odds: float, frac: float = 0.25) -> float:
    b = dec_odds - 1
    return max(0.0, (p*b-(1-p))/b) * frac
```
Then `from src.betting.odds import american_to_decimal, kelly_fraction` in all 9+ sites;
`KellyCriterion`/`AggressiveKellyCalculator` call `kelly_fraction()` instead of inlining.
**Effort:** S–M.

---

### 3. NOAA / weather.gov client implemented three times — importance 8/10

**Type:** Near duplicate (parallel clients).

- `src/api/noaa_client.py:16` — `class NOAAClient` (`BASE_URL="https://api.weather.gov"` l.23).
  Two-step points→forecast in `get_forecast_for_location` (l.35), plus hourly/current/game-day.
- `agents/noaa_weather_agent.py:17` — `class NOAAWeatherAgent` (`NOAA_API` l.28). Same two-step
  points→forecast in `get_forecast` (l.58) + `_find_closest_period`, `_fallback_forecast`.
- `agents/api_integrations.py:23` — `class NOAAWeatherAPI` (`BASE_URL` l.32).
  `get_forecast_for_stadium` (l.41) — the same points→forecast sequence a third time.

**Duplication estimate:** The points→forecast HTTP sequence (`/points/{lat},{lon}` →
`properties.forecast` → GET that URL → `properties.periods[0]`) is verbatim three times;
~70% of `get_forecast*` overlaps.

**Extraction:** Keep `NOAAClient`; delete `NOAAWeatherAgent`'s and `NOAAWeatherAPI`'s HTTP
methods, re-pointing to `NOAAClient`. The genuinely-unique betting logic in
`noaa_weather_agent.py` (`calculate_weather_edge`, l.144) should stay but consume `NOAAClient`.
**Effort:** S–M.

---

### 4. `sys.path` bootstrap duplicated 53x — and the fix already exists unused — importance 7/10

**Type:** Structural boilerplate.

`sys.path.insert/append(... project root ...)` appears at **53 sites**, in three slightly
different dialects:
- `sys.path.insert(0, str(Path(__file__).parent.parent))` (most scripts, e.g.
  `scripts/parlay_generator.py:22`, `scripts/bulldog_backtest.py:12`, +~20 more)
- `sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`
  (`scripts/line_shopping.py:15`, `scripts/generate_daily_picks.py:20`,
  `scripts/self_improving_system.py:16`, …)
- `.../parent.parent / "src"` variants (`scripts/analyze_features.py:15`,
  `scripts/download_data.py:39`, `scripts/tune_hyperparameters.py:18`, …)

**Key finding:** `src/utils/path_setup.py` was written specifically to "eliminate the need for
duplicate sys.path.insert/append calls across scripts" (its docstring, l.5; helper at l.33),
but a search for `path_setup` imports across `scripts/`, `dashboard/`, `agents/`, `src/`
returns **zero** consumers. The DRY solution exists and is simply not adopted.

**Extraction:** Best: rely on packaging (the repo has `setup.py`+`pyproject.toml`) and run via
`python -m scripts.xxx` / console entry points, deleting the hack. Interim: replace all 53
sites with `from src.utils.path_setup import setup_paths; setup_paths()` (verify the helper's
exact API first).
**Effort:** S per site (mechanical), but high count.

---

### 5. Stadium-coordinate dict copy-pasted — importance 7/10

**Type:** Data duplication.

Stadium lat/lon data is embedded in 3 files (confirmed by presence of the same coordinates,
e.g. Arrowhead `39.0489,-94.4839`, Lambeau `44.5013,-88.0622`):
- `agents/noaa_weather_agent.py:31` — `STADIUMS` (richer: includes `team` + `roof` keys)
- `scripts/generate_daily_picks.py:106` — inline `{full_name: (lat, lon)}` tuples
- `scripts/generate_daily_picks_with_grok.py` — inline coordinates

(Note: `src/api/noaa_client.py` does **not** define a stadium dict — it takes lat/lon as
arguments — so the canonical store should live in config and be passed in.)

**Extraction:** One canonical `src/config/stadiums.py`:
```python
STADIUMS = {"KC": {"name": "Arrowhead Stadium", "lat": 39.0489, "lon": -94.4839}, ...}
STADIUM_COORDS = {k: (v["lat"], v["lon"]) for k, v in STADIUMS.items()}
```
**Effort:** S. **Proving step:** diff the coordinate sets to confirm value identity (markers
confirmed; full dicts not byte-compared).

---

### 6. ESPN base-URL literal hardcoded 8x — importance 6/10

**Type:** Data duplication (magic string).

`https://site.api.espn.com/apis/site/v2/sports/football/nfl` (one variant `http://`) appears
at: `src/api/espn_client.py:44`, `agents/api_integrations.py:327` (`http://`),
`scripts/fetch_latest_nfl_data.py:29`, `src/config/settings.py:106`,
`src/health/health_check.py:171`, `scripts/audit_data_sources.py:181` & `:187`,
`scripts/production_daily_pipeline.py:40`.

**Extraction:** Expose `ESPNClient.BASE_URL` (or one constant in `src/config/settings.py`) and
import it; largely subsumed once Finding 1 is done. **Effort:** S.

---

### 7. `logging.basicConfig(...)` duplicated 37x — importance 6/10

**Type:** Structural boilerplate.

37 call sites. Most are the identical `logging.basicConfig(level=logging.INFO)` (e.g.
`scripts/backtest.py:24`, `scripts/audit_data_sources.py:16`, `dashboard/app.py:80`,
`agents/api_integrations.py:15`); several use multi-line forms with the same
`"%(asctime)s - %(name)s - %(levelname)s - %(message)s"` format (e.g.
`scripts/train_model.py:27`, `scripts/full_betting_pipeline.py:35`,
`scripts/production_daily_pipeline.py:29`); a couple use `format="%(message)s"`
(`scripts/bet_research_tool.py:27`, `scripts/self_improving_bulldog.py:39`).

**Extraction:** `src/utils/logging_setup.py` with `def configure_logging(level=logging.INFO,
fmt=DEFAULT_FMT): ...`; each entry point calls `configure_logging()`.
**Effort:** S.

---

### 8. NFL team-name / abbreviation maps reimplemented 6x — importance 6/10

**Type:** Data duplication.

Six independent team dicts with different names/shapes but overlapping content:
- `scripts/full_betting_pipeline.py:106` — `team_name_map`
- `scripts/generate_daily_picks.py:213` — `TEAM_NAME_TO_ABBR`
- `scripts/parlay_generator.py:351` — `team_mapping`
- `scripts/pregame_prediction_engine.py:599` — `full_names`
- `src/agents/research_agent.py:53` — `TEAM_NAMES`
- `src/visualization/prediction_visualizer.py:60` — `self.nfl_teams`

**Duplication estimate:** ~70–100% value overlap (abbr↔full-name mappings of the same 32
teams), differing only by direction (name→abbr vs abbr→name) and dict name.

**Extraction:** `src/config/teams.py` with canonical `NFL_TEAMS` (abbr→full name) and derived
`NAME_TO_ABBR = {v: k for k, v in NFL_TEAMS.items()}`. **Effort:** M (6 call sites + verify
direction at each). **Proving step:** byte-diff the dict bodies to confirm value identity
(defining lines confirmed; full bodies not compared).

---

### 9. ESPN `get_teams` response-parse block copied — importance 5/10

**Type:** Exact duplicate (sub-case of Finding 1, called out for the verbatim parse logic).

The nested `data["sports"] → leagues → teams → t["team"]` walk is duplicated in
`src/api/espn_client.py` (`get_teams`), `agents/api_integrations.py` (`ESPNAPI.get_teams`),
and `scripts/fetch_latest_nfl_data.py:151-167` (`get_team_info`). ~100% identical traversal.
Resolved by Finding 1. **Effort:** S.

---

### 10. `sqlite3.connect` DB-access boilerplate — importance 4/10

**Type:** Structural duplication.

`sqlite3.connect(...)` + cursor + commit/close recurs in 8 files: `src/agents/worker_agents.py`,
`src/health/health_check.py`, `src/learning/adaptive_engine.py`, `src/utils/odds_cache.py`,
`scripts/backup_database.py`, `scripts/manage_cache.py`, `dashboard/auth_system.py`,
`dashboard/app_auth.py`.

**Extraction:** `src/utils/db.py` with `@contextmanager def get_conn(path)` and a
`run_query(sql, params)` helper to centralize connection handling + DB path.
**Effort:** M. **Proving step:** read each connect block to confirm the pattern (and DB-path
literal) is shared vs. legitimately distinct schemas.

---

## Recommended remediation order

1. **Findings 2 + 5 + 6 + 8 (constants/helpers → `src/betting/odds.py`, `src/config/`)** —
   cheapest, highest divergence risk, behavior-preserving. Do first.
2. **Findings 1 + 3 + 9 (collapse parallel API clients onto the resilient `src/api/*`
   versions)** — biggest correctness win (duplicate clients lack retries / breakers; one uses
   `http://`).
3. **Findings 4 + 7 + 10 (boilerplate)** — adopt the already-written `src/utils/path_setup.py`,
   add `logging_setup.py` and `db.py`; pairs well with relying on proper packaging.

## How to reproduce

```bash
cd /home/user/nfl-betting-system
grep -rn "site.api.espn.com" src scripts agents dashboard                     # Findings 1,6
grep -rn "def american_to_decimal\|def decimal_to_american" src scripts agents dashboard  # Finding 2
grep -rnE "class (ESPN|NOAA)" src scripts agents                              # Findings 1,3
grep -rn "sys.path.insert\|sys.path.append" src scripts agents dashboard | wc -l   # Finding 4 (=53)
grep -rln "path_setup" scripts dashboard src agents | grep -v path_setup.py   # Finding 4 (=0 users)
grep -rcn "39.0489" src/api/noaa_client.py agents/noaa_weather_agent.py scripts/generate_daily_picks*.py  # Finding 5
grep -rn "logging.basicConfig" src scripts agents dashboard | wc -l           # Finding 7 (=37)
grep -rn "TEAM_NAME\|team_name_map\|team_mapping\|nfl_teams =\|full_names =" src scripts dashboard  # Finding 8
grep -rln "sqlite3.connect" src scripts agents dashboard                      # Finding 10
# Automated cross-check (recommended): jscpd --min-tokens 50 --pattern "**/*.py" src scripts agents dashboard
```
