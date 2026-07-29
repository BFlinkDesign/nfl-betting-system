---
name: testing-nfl-betting
description: Test the NFL betting system end-to-end. Use when verifying bug fixes, feature changes, or running the test suite.
---

# Testing the NFL Betting System

## Quick Reference

| Command | Purpose |
|---|---|
| `pytest tests/ -v` | Run full test suite (98 tests) |
| `ruff check src/ scripts/ tests/` | Lint check |
| `black --check src/ scripts/ tests/` | Format check |
| `mypy src/ --ignore-missing-imports --no-strict-optional` | Type check (may have pre-existing errors) |

## Environment Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Dashboard dependencies (pyotp, python-jose, passlib, bcrypt) are NOT in requirements.txt — install separately if testing dashboard/auth code: `pip install pyotp python-jose passlib bcrypt`
3. Always run from the repo root — `dashboard/app.py` and scripts use `sys.path` manipulation relative to repo root
4. `$HOME/.local/bin` must be on PATH for pytest, ruff, black, streamlit

## Testing Patterns

### sklearn Compatibility (calibration.py)
- sklearn >= 1.6 provides `FrozenEstimator` in `sklearn.frozen`
- sklearn >= 1.8 removed `cv="prefit"` from `CalibratedClassifierCV`
- The code uses try/except to handle both paths — test by verifying `type(calibrator.calibrated_model.estimator).__name__` is `FrozenEstimator` on modern sklearn

### Import Path Testing (pipeline.py, self_improving_system.py)
- Feature pipeline has dual import paths: relative (`.module`) and absolute (`src.features.module`)
- When running from repo root, the `except ImportError` fallback path is used
- Test imports from `src.features.pipeline` to exercise the fallback path
- `scripts/self_improving_system.py` should import `NFLDataPipeline` directly — if it imports an argparse-based `main()`, importing the module will trigger `SystemExit`

### Method Name Verification (auto_remediation.py)
- `OddsCache` has `clear_memory()` (not `clear_memory_cache()`)
- The remediation handler catches all exceptions silently, so a wrong method name won't raise — verify by checking `hasattr(OddsCache, 'clear_memory')` AND `not hasattr(OddsCache, 'clear_memory_cache')`

### JWT Secret Persistence (app_auth.py)
- `_get_stable_secret_key()` persists to `data/.jwt_secret` with 0o600 permissions
- Cannot import `dashboard.app_auth` directly without streamlit + pyotp + python-jose installed
- Test the function logic by replicating it or installing dashboard deps first
- Verify: two calls return same key, file has 0o600 permissions, `.gitignore` includes `data/.jwt_secret`

### Validation Swarm Edge Cases (validation_swarm.py)
- `_cross_validation` must return `roi_mean` and `win_rate_mean` even with < 2 valid results
- Test with 0 valid results (all have 'error' key) and 1 valid result
- The method is async — can test logic inline without instantiating the full swarm

## Pre-commit Hooks
- Black, ruff, isort, detect-secrets, mypy are configured
- mypy may have pre-existing errors in files you didn't touch — `SKIP=mypy git commit` is acceptable if your changes don't introduce new mypy errors
- `pyproject.toml` has `per-file-ignores` for pre-existing lint issues in `dashboard/`, `scripts/`, and `pipeline.py`

## CI Notes
- Windows tests may timeout with KeyboardInterrupt — this is a pre-existing issue
- Code Quality check may fail on Black formatting in files not touched by your PR
- All Ubuntu + macOS test matrix jobs should pass

## Devin Secrets Needed
- No secrets required for running tests
- Optional: `ODDS_API_KEY`, `XAI_API_KEY` for live odds/AI features (not needed for test suite)
- Optional: `NFL_ADMIN_EMAIL`, `NFL_ADMIN_USERNAME`, `NFL_ADMIN_PASSWORD` for dashboard auth testing
