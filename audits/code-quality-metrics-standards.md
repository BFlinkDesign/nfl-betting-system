# Code Quality & Complexity Metrics Audit — nfl-betting-system

**Date:** 2026-05-31
**Scope:** `src/`, `scripts/`, `agents/`, `dashboard/` — Python only. Excludes `*.md`, `tests/`, `*.ipynb`, `__pycache__`.
**Method:** File line counts via `wc -l`. Cyclomatic complexity via **`radon cc`** (v6.0.1, the authoritative tool) cross-checked against a custom read-only Python `ast` script that also measured per-function LOC (`end_lineno - lineno + 1`), per-class length/method counts, and an internal import graph (coupling + cycle detection). No source files were modified. Where radon and the AST script disagreed, **radon's CC is reported** (the AST script over-counted nesting depth on nested dict/generator literals; radon's structural counting is more accurate). Function LOC values are exact from the AST.

## Summary

This is a **large, sprawling codebase**: **137 in-scope Python files, 44,886 lines, ~1,034 functions, ~162 classes**. radon analyzed 1,176 callable blocks (it skips module-level script bodies, which are substantial here) and reports an **average complexity of A (3.82)** — but that average is heavily diluted by hundreds of trivial helpers. **The tail is the problem:** a handful of god-functions and god-modules concentrate the risk.

Headline metrics:
- **59 of 137 files exceed 300 lines; 35 exceed 500.** The largest, `dashboard/app.py`, is **2,492 lines** of mostly top-level Streamlit script in only ~8 functions.
- **185 functions exceed 50 LOC** and **67 functions have cyclomatic complexity > 10** (the recommended ceiling).
- radon grades **1 function F (CC 48)**, **1 function E (CC 33)**, and **7 more D (CC 21-29)** — these ~9 blocks are the priority refactor targets.
- **38 functions nest control flow ≥ 5 deep.**
- Architecture-level health is **better than the function-level**: **no class exceeds 500 lines**, and the internal import graph has **zero circular imports** with a sane dependency direction.

The dominant problem is **god-functions and god-modules**, concentrated in `dashboard/admin_panel.py`, the `scripts/` pick-generation and research tools, `src/data_pipeline.py`, `src/orchestrator/master_pipeline.py`, `src/api/request_orchestrator.py`, and the Streamlit `dashboard/` pages.

### Top-10 longest files (in-scope)

| Rank | File | Lines | Classes | Functions |
|------|------|------:|--------:|----------:|
| 1 | `dashboard/app.py` | 2,492 | 0 | 8 |
| 2 | `dashboard/pages/3_🧪_The_Lab.py` | 1,069 | 0 | 6 |
| 3 | `src/visualization/prediction_visualizer.py` | 987 | 2 | 9 |
| 4 | `dashboard/backtesting_lab.py` | 884 | 1 | 23 |
| 5 | `dashboard/app_complete.py` | 836 | 0 | 9 |
| 6 | `src/agents/llm_council.py` | 798 | 12 | 23 |
| 7 | `src/orchestrator/master_pipeline.py` | 781 | 4 | 19 |
| 8 | `src/utils/odds_cache.py` | 755 | 2 | 23 |
| 9 | `scripts/generate_daily_picks.py` | 745 | 1 | 10 |
| 10 | `src/learning/adaptive_engine.py` | 726 | 4 | 13 |

### Most-complex functions (radon CC; LOC from AST)

| Rank | radon grade (CC) | Function | File:line | LOC |
|------|------------------|----------|-----------|----:|
| 1 | **F (48)** | `advanced_settings_panel` | `dashboard/admin_panel.py:26` | 664 |
| 2 | **E (33)** | `BetResearchTool.analyze_game` | `scripts/bet_research_tool.py:84` | 202 |
| 3 | **D (29)** | `DailyPicksGenerator.generate_pick` | `scripts/generate_daily_picks.py:414` | 142 |
| 4 | **D (28)** | `RequestOrchestrator._fetch_from_api` | `src/api/request_orchestrator.py:200` | 148 |
| 5 | D (27) | `AggressiveKellyCalculator.calculate_bet_size` | `agents/aggressive_kelly.py:36` | 146 |
| 6 | D (27) | `render_strategy_card` | `dashboard/strategy_manager.py:20` | 204 |
| 7 | D (23) | `MasterPipeline.fetch_todays_games` | `src/orchestrator/master_pipeline.py:245` | 41 |
| 8 | D (22) | `show_performance_page` | `dashboard/app_complete.py:503` | 89 |
| 9 | D (21) | `show_api_key_settings` | `dashboard/api_key_manager.py:251` | 199 |

(radon found exactly 9 blocks graded D or worse; everything else is grade C or better. `scripts/backtest.py:150 main` is 270 LOC but only grade C/20.)

### Top longest functions by LOC (length, regardless of CC)

| LOC | radon CC | Function | File:line |
|----:|---------:|----------|-----------|
| 664 | 48 (F) | `advanced_settings_panel` | `dashboard/admin_panel.py:26` |
| 270 | 20 (C) | `main` | `scripts/backtest.py:150` |
| 260 | 7 (B) | `create_matchup_card` | `src/visualization/prediction_visualizer.py:106` |
| 221 | ~15 (C) | `_create_html_body` | `src/notifications/email_sender.py:89` |
| 212 | ~13 (C) | `train_evolved_model` | `scripts/evolve_model_to_75pct.py:281` |
| 204 | 27 (D) | `render_strategy_card` | `dashboard/strategy_manager.py:20` |
| 202 | 33 (E) | `analyze_game` | `scripts/bet_research_tool.py:84` |
| 199 | 21 (D) | `show_api_key_settings` | `dashboard/api_key_manager.py:251` |

### Largest classes (none exceed the 500-line ceiling)

| Class | File:line | Lines | Methods |
|-------|-----------|------:|--------:|
| `PredictionVisualizer` | `src/visualization/prediction_visualizer.py:74` | 358* | 8 |
| `OddsCache` | `src/utils/odds_cache.py:48` | 331* | 21 |
| `DailyPicksGenerator` | `scripts/generate_daily_picks.py:34` | ~330* | 9 |
| `BacktestingLab` | `dashboard/backtesting_lab.py:216` | ~330* | 22 |
| `MasterPipeline` | `src/orchestrator/master_pipeline.py:125` | ~310* | 18 |
| `AdaptiveEngine` | `src/learning/adaptive_engine.py:94` | ~300* | 12 |
| `NFLDataPipeline` | `src/data_pipeline.py:28` | ~290* | 11 |
| `StrategyRegistry` | `src/strategy_registry.py:197` | ~290* | 18 |

\* Class extents reported by the AST script include trailing module content in a few cases; treat as approximate. The key finding holds: **no class breaches the 500-line guideline**, so the size problem is at the function and module level, not the class level.

### Coupling (internal import graph; static imports only)

- **Highest efferent coupling (fan-out):** `src/swarms/prediction_pipeline.py` (10 internal imports), `src/backtesting/prediction_generator.py` (10), `src/features/pipeline.py` (10), `scripts/start_autonomous_system.py` (9), `src/agents/__init__.py` (8), `src/orchestrator/master_pipeline.py` (7). Expected for orchestrators/pipelines, but these are the modules most likely to break on refactors.
- **Highest afferent coupling (fan-in — the stable core):** `src/agents/base_agent.py` (imported by 14), `agents/api_integrations.py` (9), `src/backtesting/engine.py` (6), `src/betting/kelly.py` (5), `src/swarms/model_loader.py` (5), `src/utils/odds_cache.py` (5), `src/models/xgboost_model.py` (5). These warrant the strictest test coverage; changes ripple widely.
- **Circular imports:** none detected.

---

## Prioritized recommendations (worst offenders first)

### 1. `advanced_settings_panel` — the single worst function (664 LOC, radon F/49). Importance: 9/10
**File:** `dashboard/admin_panel.py:26`

This one Streamlit function is 664 lines with cyclomatic complexity 48 (radon F), nested 7 deep — it is the entire admin panel rendered procedurally in a single call, mixing form widgets, validation, persistence, and conditional sections. It is the largest and most complex block in the codebase and is effectively impossible to test or review.

**Recommendation:** Decompose into one helper per settings section (`_render_api_keys()`, `_render_model_params()`, `_render_bankroll()`, `_render_data_sources()`, …), each rendering its own widgets and returning a small dict; `advanced_settings_panel` becomes a ~30-line dispatcher driven by a section list. Separate the pure validation/persistence logic from the `st.*` calls so it can be unit-tested. Target: no helper > 60 LOC or CC > 10.

### 2. `scripts/bet_research_tool.analyze_game` and `generate_daily_picks.generate_pick`. Importance: 8/10
**Files:** `scripts/bet_research_tool.py:84 analyze_game` (202 LOC, E/33, nest 7); `scripts/generate_daily_picks.py:414 generate_pick` (142 LOC, D/29) and the sibling `:167 predict_game` (154 LOC, C/20).

These are long top-to-bottom procedures mixing fetch → model-predict → score → filter → format, with deep nesting and large if/elif chains over markets and bet types. They also overlap heavily with the weekly equivalents (DRY/cohesion problem).

**Recommendation:** Extract a shared pick-generation core (`scripts/_picks_core.py` or `src/picks/`) with discrete stages — `fetch_odds()`, `build_model_probs()`, `score_edges()`, `tier_and_filter()`, `format_output()` — each < 50 LOC / CC < 10. Have the daily and weekly generators differ only in their date window. Pull the edge→tier mapping (`if edge>0.10 'A' elif ...`) into a one-line `_tier(edge)` helper.

### 3. `src/api/request_orchestrator._fetch_from_api`. Importance: 8/10
**File:** `src/api/request_orchestrator.py:200` (148 LOC, radon D/28, nesting ~9)

High fan-in API layer (`request_orchestrator` is imported by 3 modules and is the network chokepoint). The function interleaves URL building, retry/backoff, rate-limit handling, caching, and response parsing in one deeply nested body, so any one concern is hard to change safely.

**Recommendation:** Split into `_build_request()`, `_execute_with_retry()` (retry/backoff only), `_check_cache()` / `_store_cache()`, and `_parse_response()`. The retry loop should be the only place with nested try/except; everything else flattens to sequential calls. This is core infra — add unit tests around the retry and rate-limit branches once extracted.

### 4. `src/data_pipeline.py` feature generation & `master_pipeline` orchestration. Importance: 7/10
**Files:** `src/data_pipeline.py` (`NFLDataPipeline`, fan-in 6) — its feature-building methods are long and dominated by repeated `... if "<col>" in df else 0.0` guards; `src/orchestrator/master_pipeline.py:245 fetch_todays_games` (D/24, nested ESPN-JSON walking) and `:577 run_daily_pipeline` (149 LOC, CC 16).

**Recommendation:**
- `data_pipeline`: introduce a `_safe_mean(df, col)` / `_safe(df, col, default)` helper to collapse the repeated column-existence guards, and split feature construction into `_offense_features` / `_defense_features` / `_situational_features` builders. This is high fan-in, so reducing branch density here pays off broadly.
- `fetch_todays_games`: replace the chained `.get("sports",[{}])[0].get(...)` walking with a small `_safe_path(data, *keys)` helper and extract `_parse_event(event)`; the function then drops several nesting levels.
- `run_daily_pipeline`: extract one private method per stage so the public method reads as ~10 sequential calls.

### 5. Dashboard god-module & duplication. Importance: 7/10
**Files:** `dashboard/app.py` (2,492 lines, ~8 functions — most logic is top-level script across 8 tabs); near-duplicate shells `app_complete.py` (836), `app_auth.py` (507); duplicated features across `parlay_builder.py` + `pages/1_🧩_Parlay_Builder.py` (both 611 lines, including an identical `fetch_live_odds` at line 326, CC 17, nest 9) and `backtesting_lab.py` + `pages/3_🧪_The_Lab.py`.

**Recommendation:**
- Extract each `with tab_*:` block from `app.py` into `dashboard/tabs/<name>.py` exposing `render(ctx)`; `app.py` becomes a thin router (< 200 lines).
- Hoist the static `TEAM_LOGOS/TEAM_NAMES/TEAM_COLORS` dicts and the CSS string into `dashboard/theme.py` / `dashboard/teams.py` imported by all dashboards.
- Pick one canonical implementation of parlay builder / lab / app shell and delete the dead duplicates (verify the live entry point via `Makefile` and the `start_dashboard_*` scripts first).
- Centralize the repeated `american_to_decimal` / implied-probability math (present inline in `dashboard/app.py:1126`, `src/betting/kelly.py`, and the dashboard parlay files) into a single `src/betting/odds_math.py`.

### 6. High-CC render/CLI functions worth a targeted pass. Importance: 5/10
**Files:** `dashboard/strategy_manager.py:20 render_strategy_card` (D/27), `dashboard/api_key_manager.py:251 show_api_key_settings` (D/21), `dashboard/app_complete.py:503 show_performance_page` (D/22), `scripts/backtest.py:150 main` (270 LOC, C/20), `agents/aggressive_kelly.py:36 calculate_bet_size` (146 LOC, D/27).

**Recommendation:** Split each `render_*`/`show_*` into per-section helpers and separate pure data-prep from `st.*` calls (the data-prep functions then become unit-testable). For `scripts/backtest.py:main`, move the argument handling into `argparse` and the body into a sequence of stage calls. For `aggressive_kelly.calculate_bet_size`, the long if/elif multiplier ladder (favorite tiers + streak bonuses) should become a small data-driven table lookup rather than branches.

---

## Notes & limitations
- **CC values are radon's** (authoritative); function LOC and class/file structure counts are from a custom AST pass. radon's total-average run reported "A (3.82)" over 1,176 blocks — accurate but misleading in isolation, since it excludes module-level script bodies and is diluted by trivial helpers. The grade tail (1 F, 1 E, 7 D) is the actionable signal and is what this report ranks on.
- The AST script's **max-nesting** metric over-counted on nested dict/generator/comprehension literals (e.g. it reported nesting 10 for `fetch_todays_games`, which is really ~4 levels of control flow plus nested literals). Nesting figures are therefore used only as a rough secondary signal; the LOC and radon-CC figures are reliable.
- Coupling counts reflect **static internal imports only** (absolute `import`/`from` within the four scoped roots). Dynamic imports, `sys.path` manipulation (e.g. `dashboard/app.py:24-28`), function-local imports (e.g. `import requests` inside `fetch_todays_games`), and level>0 relative imports were not counted, so true fan-in/out may be marginally higher. Any runtime-only dependency is **"unable to verify"** statically.
- A couple of class extents reported by the AST pass appear inflated by trailing module content; they are marked approximate. The load-bearing conclusion (no class > 500 lines; no import cycles) is verified.
