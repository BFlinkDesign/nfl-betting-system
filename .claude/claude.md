# Claude Code Instructions — NFL Betting System

Read these files before making any change:

1. `AGENTS.md`
2. `docs/PROJECT_STATUS.md`
3. the affected source and tests

`AGENTS.md` is the cross-agent contract. This file adds Claude-specific enforcement.

## Current authority

The project is **research/paper-trading only**. Historical files that describe it as production-ready or profitable are not current authority. Never repeat those claims without reproducing the required commit-bound evidence bundle.

## Required behavior

- Treat `NO BET` and “insufficient evidence” as valid outcomes.
- Separate research discovery, independent validation, paper trading, and live authorization.
- Keep deterministic code authoritative for arithmetic, policy, persistence, and state.
- Use LLMs for hypothesis generation or explanation only; never for promotion authorization.
- Show exact commands, scopes, exit statuses, and changed files for verification claims.
- State when external services, private datasets, integrations, or full model backtests were not exercised.
- Do not silently repair corrupt registries or databases by replacing them with empty state.
- Do not merge or port a broad stale branch wholesale; isolate and revalidate each useful change.

## Minimum verification

```bash
python -m pytest -m "not integration and not slow"
black --check .
isort --check-only .
ruff check .
```

Add focused tests for the changed failure modes. CI success is code evidence only; it is not betting-performance evidence.
