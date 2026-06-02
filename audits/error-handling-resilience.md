# Error-Handling & Resilience Audit — NFL Betting System

**Date:** 2026-05-31
**Scope:** `src/`, `scripts/`, `agents/`, `dashboard/` (154 Python files)
**Method:** Static review + scripted grep/AST-style scanning. No source code was modified.

---

## Executive Summary

The codebase contains a genuinely good resilience library at `src/utils/resilience.py`
(circuit breakers via `pybreaker`, exponential-backoff retry via `tenacity`, `FallbackChain`,
token-bucket `RateLimiter`, and a `ResilienceMetrics` collector). **The central problem is that
this library is barely used.** Only 2 modules actually consume it for live calls
(`src/api/espn_client.py` and `src/swarms/prediction_pipeline.py`); `master_pipeline.py` imports its
breakers and `system_connectivity_auditor.py`/`health_check.py` read `get_circuit_status()`. Every
other external-call site — the xAI/Grok agents, NOAA agents, The Odds API client,
`request_orchestrator.py`, the dashboard, and most scripts — **re-implements raw `requests` with
ad-hoc, inconsistent error handling.** Notably `src/api/request_orchestrator.py` hand-rolls its **own
separate `CircuitBreaker` class** (lines 526-580) rather than reusing `resilience.py`, and rate
limiting is implemented at least twice (`resilience.RateLimiter` token bucket vs the `OddsCache`/
`token_bucket.py` system used by the orchestrator).

There is **no centralized error handler and no custom exception hierarchy** (0 custom exception
classes found), so callers cannot distinguish validation vs auth vs rate-limit vs server errors —
nearly everything collapses to `return None` / `return {}` / `return []`, frequently discarding the
traceback.

### Summary Table — Most Serious Issues

| # | Issue | Count / Locations | Importance |
|---|-------|-------------------|:---------:|
| 1 | `resilience.py` exists but is unused at most call sites; raw `requests`/breakers reimplemented | Only `espn_client.py` + `prediction_pipeline.py` use it; `request_orchestrator.py` has its OWN breaker | 9/10 |
| 2 | No custom exception classes; no centralized handler; error categories not distinguished | **0** custom exception classes found | 8/10 |
| 3 | Bare `except:` (catches `KeyboardInterrupt`/`SystemExit`, hides everything) | **17 occurrences** | 8/10 |
| 4 | Silent swallow `except ...: pass` (loses error entirely) | **24 occurrences** | 7/10 |
| 5 | Broad `except` returning `{}`/`[]`/`None` losing traceback | widespread (see §5.4) | 7/10 |
| 6 | `requests.*` (module-level) calls without `timeout=` (hang risk) | **6 confirmed** | 7/10 |
| 7 | `smtplib.SMTP_SSL(...)` without `timeout` (blocking notification path) | 1 (`email_sender.py:64`) | 6/10 |
| 8 | `logger.error` used for caught exceptions instead of `logger.exception` (no stack trace) | **185** × `.error` vs **0** × `.exception` | 7/10 |
| 9 | 429 / rate-limit handling inconsistent (some recurse unbounded, some ignore) | multiple distinct patterns | 6/10 |
| 10 | Dead/unreachable `except` after bare `except:` | `agents/noaa_weather_agent.py:116` | 5/10 |

**Quantified scan results (verified by scripted scan of the current tree):**
- Module-level `requests.{get,post,...}` call sites: **9**; without `timeout=`: **6** — `src/utils/resilience.py:607` (a docstring/example, benign), `scripts/self_improving_bulldog.py:191`, `scripts/send_notifications.py:102`, `scripts/production_daily_pipeline.py:50,98,172`. (Note: most clients in `agents/api_integrations.py`, `src/api/*`, `agents/noaa_weather_agent.py` correctly use `self.session.get(..., timeout=10)` — those are not counted here but ARE timeout-protected.)
- Bare `except:`: **17**. Silent `except ...: pass`: **24** (a few are defensible optional-import/Streamlit-context cases). 
- `logger.error`/`logging.error`: **185**; `logger.exception`: **0** — not a single use of `logger.exception` in the whole scope.
- Custom exception classes (`class *Error/*Exception`): **0**.
- Files importing `tenacity`/`pybreaker`: **2** (`src/utils/resilience.py` and `src/api/espn_client.py`).
- `parlay_generator.py` has **504 lines** (earlier 533/343 references were to a different file/region and are withdrawn — its xAI POST sites should still be re-verified for `timeout`).

---

## 1. Error Handling Consistency

**Finding 1.1 — No centralized handler, no custom exception hierarchy (Importance 8/10).**
A scan for `class *Error` / `class *Exception` returned **zero** results across the entire scope.
Every module invents its own ad-hoc convention. The dominant pattern is "catch broadly, log a
string, return a sentinel":

- `agents/api_integrations.py:90,116,281,310,364,377,400` — every API method:
  `except Exception as e: logger.error(...); return {}` (or `return []`)
- `agents/xai_grok_agent.py:77-79` — `except Exception as e: logger.error(...); return {}`
- `src/api/noaa_client.py:347,372,409` — `except Exception as e: logger.error(...); return {}`

Because errors are not typed, a caller receiving `None`/`{}` cannot tell *why* it failed (timeout?
auth? rate limit? bad data?) and therefore cannot react intelligently (e.g., back off on 429,
abort on 401, retry on 503).

*Fix:* introduce a small exception module, e.g. `src/utils/errors.py`:
```python
class AppError(Exception): ...
class ApiError(AppError):
    def __init__(self, msg, *, status=None, retryable=False):
        super().__init__(msg); self.status = status; self.retryable = retryable
class AuthError(ApiError): ...        # 401/403
class RateLimitError(ApiError): ...   # 429, carry Retry-After
class NotFoundError(ApiError): ...    # 404
class ServerError(ApiError): ...      # 5xx, retryable=True
class ValidationError(AppError): ...  # bad/missing data
```
Map HTTP status to these in one helper and raise them from all clients, so callers (and the
circuit breakers, which already `exclude=[ValueError, KeyError]`) can branch correctly.

**Finding 1.2 — Parallel circuit-breaker and rate-limiter implementations (Importance 7/10).**
`src/utils/resilience.py` provides a `pybreaker`-based breaker + token-bucket `RateLimiter`, while
`src/api/request_orchestrator.py:526` defines a **second, independent** `CircuitBreaker` class and
relies on `src/utils/token_bucket.py`/`OddsCache` for rate limiting. Two breaker implementations
with separate state means circuit status is fragmented and `get_circuit_status()` only sees the
`pybreaker` ones. Consolidate onto `resilience.py`.

---

## 2. Error Categories (validation / auth / authz / not-found / server / rate-limit)

**Finding 2.1 — Only 429 is sometimes handled; 401/403/404/5xx are not categorized (Importance 7/10).**
`raise_for_status()` is called in most clients, which lumps 401/403/404/5xx into a single
`HTTPError`/`RequestException` that is then swallowed into `None`. Rate-limit (429) handling exists
but is inconsistent:

- `agents/api_integrations.py:184-197` — on 429, `time.sleep(60)` then **recurses** into
  `self._make_request(...)` with **no recursion depth bound** → risk of unbounded recursion / stack
  growth if the API stays rate-limited.
- `agents/api_integrations.py:60-66` (first `_make_request`) — reads `Retry-After`, sleeps,
  `continue`s inside a bounded `for attempt in range(max_retries)` loop. This is the better pattern.
- `src/api/request_orchestrator.py:~170` — checks `status_code == 429`, reads `Retry-After`, sleeps.
- `scripts/track_line_movement.py:88`, `scripts/generate_daily_picks.py:566` — inspect
  `status_code` ad hoc.

*Fix:* centralize status→exception mapping (Finding 1.1). For 429 prefer the **bounded-loop**
pattern, never unbounded recursion. Cap `Retry-After` to a sane max and bound total attempts:
```python
if resp.status_code == 429:
    wait = min(int(resp.headers.get("Retry-After", 60)), 120)
    raise RateLimitError("rate limited", status=429, retryable=True)  # let retry decorator handle
```

**Finding 2.2 — Validation errors swallowed identically to transport errors (Importance 6/10).**
`agents/api_integrations.py:208-210` catches `(ValueError, KeyError)` (JSON/shape problems) and
returns `None`, the same sentinel used for network failure. The circuit breakers in
`resilience.py` deliberately `exclude=[ValueError, KeyError]` so validation bugs don't trip the
breaker — but since most clients don't use those breakers, that protection is moot. Raise
`ValidationError` instead so it is never confused with a retryable transport failure.

---

## 3. Async / Callback Error Handling

**Finding 3.1 — Silent swallow in async LLM council (Importance 7/10).**
`src/agents/llm_council.py:315` and `:334`:
```python
async def _query_one(self, model, prompt):
    try:
        return await self._call_llm(model, prompt)
    except Exception:
        pass        # <-- error vanishes; no log, no metric
    return None
```
A failing model produces `None` with **no log line at all**, making council degradation invisible
in production. The companion `_query_council` uses
`await asyncio.gather(*tasks, return_exceptions=True)` (good — won't crash on one failure) but the
returned exception objects do not appear to be logged/inspected, so partial failures are silent.

*Fix:*
```python
    except Exception:
        logger.exception("LLM query failed for model=%s", model)
        return None
# and after gather:
for model, res in zip(models, results):
    if isinstance(res, Exception):
        logger.warning("council member %s failed: %r", model, res)
```

**Finding 3.2 — Async files reviewed (Importance — informational).**
Async appears in `src/orchestrator/master_pipeline.py`, `src/agents/message_bus.py`,
`base_agent.py`, `orchestrator_agent.py`, `src/swarms/swarm_base.py`. `master_pipeline.py`
does wrap external calls with `resilient_call`/`with_resilience` and a weather fallback
(`fallback=lambda: default_weather()`), which is the desired pattern. Whether every `gather`/task
result is inspected throughout the message bus is **Unable to verify** without deeper tracing of
each call graph.

---

## 4. Error Recovery (degradation, retry, circuit breakers, fallback)

**Finding 4.1 — Excellent resilience library is largely unused (Importance 9/10 — top issue).**
`src/utils/resilience.py` provides `resilient_call`, `with_resilience`, four pre-wired circuit
breakers (`espn_breaker`, `odds_breaker`, `weather_breaker`, `llm_breaker`), retry decorators
(`api_retry`, `critical_retry`, `quick_retry`), `FallbackChain`, and metrics. **External consumers
found: only**
- `src/api/espn_client.py:31` — `@with_resilience("espn", espn_breaker, espn_limiter, max_retries=3)` (correct usage)
- `src/swarms/prediction_pipeline.py:120` — `@with_resilience('espn', espn_breaker)`
- `src/orchestrator/master_pipeline.py` — imports breakers + uses fallback
- `src/audit/system_connectivity_auditor.py:217` — reads `get_circuit_status()`

Everything else hits the network raw with no breaker and no fallback:
`agents/api_integrations.py` (Odds/Weather/ESPN clients), `agents/xai_grok_agent.py`,
`agents/noaa_weather_agent.py`, `scripts/parlay_generator.py`, `scripts/generate_daily_picks*.py`,
`src/api/request_orchestrator.py`, `src/api/noaa_client.py`, dashboard modules, etc. A single slow
or flapping upstream (The Odds API, x.ai, NOAA) can therefore stall or repeatedly hammer the
service with no fast-fail.

*Fix:* wrap each client's lowest-level request method with `with_resilience(...)` using the
matching breaker + limiter, and supply a `fallback` (cached value / default) where a degraded answer
is acceptable. Example for the Grok agent:
```python
from src.utils.resilience import with_resilience, llm_breaker, llm_limiter

@with_resilience("grok", llm_breaker, llm_limiter, max_retries=2,
                 fallback=lambda: None)
def analyze_game(self, ...):
    resp = requests.post(..., timeout=30)
    resp.raise_for_status()
    return resp.json()
```

**Finding 4.2 — Ad-hoc retry loops don't back off on the right exceptions (Importance 5/10).**
`agents/api_integrations.py:43-81` retries on `RequestException` with `time.sleep(2**attempt)`
(reasonable) but the second client (`:176-211`) has **no retry at all** beyond the 429 recursion.
Inconsistent. Prefer the `tenacity`-based decorators already provided.

**Finding 4.3 — Good fallbacks do exist in places (Importance — positive note).**
`agents/noaa_weather_agent.py` falls back to `_get_default_weather()`, and `master_pipeline.py`
uses a weather fallback. `FallbackChain` in `resilience.py` is available but **no external file
uses it** — chained multi-source fallback (primary API → backup API → cache) is not realized
anywhere despite the system having multiple data sources.

---

## 5. Error Information (dev vs prod, stack traces, logging completeness)

**Finding 5.1 — `logger.error` used for caught exceptions instead of `logger.exception` (Importance 7/10).**
`logger.error` appears **185** times; `logger.exception` is used **0** times (literally never). The overwhelmingly common
idiom is `except Exception as e: logger.error(f"... {e}")`, which logs the message string but
**discards the traceback**, making production debugging of these failures very hard. Inside an
`except` block, use `logger.exception(...)` (or `logger.error(..., exc_info=True)`):
```python
except Exception:
    logger.exception("Error fetching complete game data")   # includes traceback
    return {}
```
Representative sites: `agents/api_integrations.py:417`, `agents/xai_grok_agent.py:40,43`,
`src/notifications/sms_sender.py`, `src/notifications/email_sender.py`,
`src/self_healing/auto_remediation.py`, `scripts/download_data.py`,
`scripts/production_daily_pipeline.py`.

**Finding 5.2 — Bare `except:` (16) hides KeyboardInterrupt/SystemExit and all errors (Importance 8/10).**
Confirmed locations:
`src/utils/odds_cache.py:484`, `scripts/train_favorites_specialist.py:220`,
`scripts/generate_daily_picks_with_grok.py:233`, `scripts/generate_daily_picks.py:599`,
`scripts/train_improved_model.py:177`, `agents/noaa_weather_agent.py:116`,
`dashboard/video_engine.py:51,208`, `dashboard/app.py:101,114,240,248,616,628`,
`dashboard/pages/3_🧪_The_Lab.py:353,365`.
Bare `except:` swallows `KeyboardInterrupt` and `SystemExit`, so Ctrl-C and clean shutdown can be
silently eaten — especially harmful in the long-running `dashboard/app.py` and training scripts.
*Fix:* replace every bare `except:` with `except Exception:` at minimum, and prefer a specific type.

**Finding 5.3 — `except ...: pass` silent swallow (24) (Importance 7/10).**
Confirmed locations include: `src/agents/llm_council.py:315,334` (async LLM failures — see §3.1),
`src/config/secrets.py:21,125` and `src/config/settings.py:367` (optional Streamlit/secrets context
— defensible), `src/backtesting/data_loader.py:205,218`, `src/api/espn_client.py:91`,
`scripts/generate_daily_picks.py:236`, `dashboard/backtesting_lab.py:746`, `dashboard/app.py:270`
(plus the bare-except set), and `dashboard/pages/2_🎬_Media_Studio.py:43,56,164,177,190,199`.
Note `espn_client.py:91` is a *defensible* guard around the `pybreaker` state check (it falls back
to the cache regardless), and the secrets/Streamlit ones are acceptable optional-context handling.
The genuinely harmful ones are the **LLM-council** swallows (§3.1) and the `data_loader`/Media-Studio
ones, which hide real operational failures with no log line. *Fix:* add at least
`logger.debug/exception(...)` to each non-optional handler.

**Finding 5.4 — Broad except returning empty container/None loses traceback (Importance 7/10).**
This is the single most pervasive anti-pattern. Confirmed representative sites (each is
`except Exception as e: logger.error(f"...{e}"); return {}` or `return []`):
`agents/api_integrations.py:90,116,281,310,364,377,400` (every API method returns `{}`/`[]`),
`agents/xai_grok_agent.py:77` (`return {}`), `src/api/noaa_client.py:347,372,409` (`return {}`),
`scripts/production_daily_pipeline.py:156,219` (`return []`). Returning `[]`/`{}` makes a
failure look like "no data," which downstream model/odds logic may treat as a legitimate empty
result — a silent-correctness hazard for a betting system (e.g. `generate_daily_picks` logs
"No games available" and returns `[]` whether the API was down or there genuinely were no games).
*Fix:* log with `logger.exception(...)` and propagate a typed error (or at minimum a distinct
sentinel) so callers can distinguish "empty" from "failed."

**Finding 5.5 — No dev/prod gating of error detail (Importance 4/10).**
There is no evidence of environment-aware error verbosity (e.g., full traceback in dev, sanitized
message in prod) in the Streamlit dashboard; raw `str(e)` is shown/logged uniformly. For a
single-user personal tool this is low risk, but if the dashboard is ever exposed, surfaced
exception strings could leak internal paths/keys. **Unable to verify** any centralized logging
config (no `logging.config`/`dictConfig` found in the priority files reviewed).

---

## Targeted External-Call-Site Findings

**`scripts/production_daily_pipeline.py:50, 98, 172` — `requests.get(url)` to ESPN with NO `timeout` (Importance 7/10).**
Three module-level ESPN fetches in the production daily pipeline have no `timeout`, so a stalled
ESPN endpoint blocks the entire daily run indefinitely. Each is wrapped in
`try/except Exception as e: logger.error(...); return []` — but the bare request can hang before any
exception fires. *Fix:* add `timeout=10` to all three, and prefer routing through `ESPNClient`
(which already has the circuit breaker) instead of raw `requests`.

**`scripts/send_notifications.py:102` — `requests.post(webhook_url, json=message)` (Discord) with NO `timeout` (Importance 6/10).**
A stalled Discord webhook blocks the notification step. It does check `status_code == 204` and logs
failures (good), but needs `timeout=10`.

**`scripts/self_improving_bulldog.py:191` — `requests.post(...)` to Grok with NO `timeout` (Importance 6/10).**
This is the autonomous self-improvement loop; a hang here stalls the whole loop. Add `timeout=30`.

**`agents/xai_grok_agent.py:73` and `agents/api_integrations.py` clients — already timeout-protected (positive note).**
`GrokAgent.chat()` correctly uses `self.session.post(url, json=payload, timeout=30)`, and the
`api_integrations.py` Odds/ESPN/NOAA/Reddit clients all use `self.session.get(..., timeout=10)`.
These are NOT timeout bugs; their weakness is the broad `except Exception: ... return {}/[]`
swallow and lack of circuit-breaker/retry, not missing timeouts.

**`scripts/generate_daily_picks.py:599` — bare `except:` swallowing weather-fetch errors (Importance 5/10).**
```python
try:
    weather = self.weather_api.get_forecast_for_point(lat, lon)
    ...
except:                       # bare -> also swallows KeyboardInterrupt
    logger.warning("    Weather data unavailable")
```
*Fix:* `except Exception:` and log the actual error at debug level.

**`agents/noaa_weather_agent.py:116` — bare `except:` + unreachable handler (Importance 5/10).**
```python
        except:
            return self._get_default_weather()
        except Exception as e:        # UNREACHABLE — bare except above caught everything
            logger.error(f"NOAA error: {e}")
            return None
```
The second handler is dead code. The fallback to default weather is fine, but the bare `except:`
should be `except Exception:` and the error should be logged before falling back.

**`src/notifications/email_sender.py:64` — `smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)` without `timeout` (Importance 6/10).**
```python
with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
```
No `timeout`, so a stalled Gmail SMTP endpoint blocks the notification path indefinitely. The whole
block is wrapped in `except Exception as e: logger.error(...)` (which also discards the traceback).
*Fix:* `smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10)` and use `logger.exception(...)`.
(For contrast, `src/notifications/desktop_notifier.py:64` already passes a `timeout`.)

**`agents/api_integrations.py:184-197` — unbounded 429 recursion (Importance 6/10).**
`return self._make_request(method, endpoint, params, timeout, **kwargs)` after a fixed
`time.sleep(60)` has no recursion cap. *Fix:* convert to a bounded loop and respect `Retry-After`.

**`src/api/request_orchestrator.py` — defines its OWN `CircuitBreaker` class, duplicating `resilience.py` (Importance 6/10).**
This module (lines 526-580) hand-rolls a thread-safe `CircuitBreaker` (closed/open/half_open,
`record_success`/`record_failure`/`can_proceed`) plus its own retry/backoff in `_process_request`
(`wait_time = 2 ** (3 - request.retries)`, line 392) and a priority queue. It is a **complete
parallel reimplementation** that shares nothing with `resilience.py`'s `pybreaker` breakers, so its
failures are invisible to `get_circuit_status()`/`ResilienceMetrics` and its breaker state is per
`RequestOrchestrator` instance. It also raises bare `Exception(...)` for "circuit open" / "rate
limit exceeded" (lines 686, 690) instead of typed errors. *Fix:* delete the local `CircuitBreaker`
and route through `resilience.py`'s breakers/`with_resilience`.

---

## Prioritized Recommendations

1. **(9/10) Adopt `resilience.py` everywhere external calls happen.** Wrap the lowest-level request
   method of each client (`api_integrations` Odds/Weather/ESPN, `xai_grok_agent`,
   `noaa_weather_agent`, `request_orchestrator`, `parlay_generator`, `generate_daily_picks*`) in
   `with_resilience(name, breaker, limiter, fallback=...)`. Delete the duplicate `RateLimiter` in
   `api_integrations.py`. This is the single highest-leverage change.

2. **(8/10) Introduce a typed exception hierarchy** (`src/utils/errors.py`) and one
   `status_to_exception()` helper; raise `AuthError/RateLimitError/NotFoundError/ServerError/
   ValidationError` from all clients instead of returning bare `None`/`{}`/`[]`.

3. **(8/10) Eliminate all 16 bare `except:`** → `except Exception:` (or specific), starting with the
   long-running `dashboard/app.py` (6) and training scripts where Ctrl-C is being swallowed.

4. **(7/10) Fix the 13 silent `except: pass`** — add `logger.exception(...)` (keep the two
   genuinely-optional Streamlit-context ones, but comment them clearly). Priority:
   `llm_council.py:315,334`, `espn_client.py:90`.

5. **(7/10) Add `timeout=` to the 5 real raw `requests` calls** (`production_daily_pipeline.py:50,98,172`;
   `send_notifications.py:102`; `self_improving_bulldog.py:191`) and to `email_sender.py:64` `SMTP_SSL`.

6. **(6/10) Replace `logger.error(f"...{e}")` with `logger.exception(...)`** inside `except` blocks
   (currently 78:3 ratio) so production logs carry tracebacks.

7. **(6/10) Make 429 handling uniform and bounded** — remove the unbounded recursion in
   `api_integrations.py:184-197`; cap `Retry-After`; route through retry decorators.

8. **(6/10) For the 9 broad-except-returns-empty sites,** log with `exc_info=True` and (for the
   betting-critical paths in `data_pipeline.py`, `espn_client.py`, `research_agent.py`) propagate a
   typed error so "failed" is never silently treated as "no data."

9. **(5/10) Use `FallbackChain`** for multi-source data (primary API → backup API → cache); it is
   implemented but unused.

10. **(4/10) Add a centralized logging config** with dev/prod verbosity gating and ensure no raw
    exception strings (which may contain paths/keys) reach the dashboard UI in prod.

---

### Notes on Verifiability
- Line numbers come from a scripted scan of the current tree; emoji-named dashboard pages
  (`2_🎬_Media_Studio.py`, `3_🧪_The_Lab.py`) are reported with their real names.
- `api_integrations.py:225` was an initial no-timeout flag but is a **false positive** — that call
  passes `timeout=timeout`.
- Whether every `asyncio.gather` result in `src/agents/message_bus.py` is inspected for exceptions
  is **Unable to verify** without full call-graph tracing.
- Existence of a centralized `logging.config`/`dictConfig` is **Unable to verify** from the priority
  files reviewed.
