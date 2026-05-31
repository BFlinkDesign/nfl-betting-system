#!/bin/bash
# SessionStart hook for Claude Code on the web.
# Installs runtime + dev dependencies so tests and linters work in remote sessions.
# Idempotent and non-interactive — safe to run repeatedly.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

echo "[session-start] Installing Python dependencies..."
# Best-effort pip upgrade; never fail the session if the base image manages pip.
python -m pip install --upgrade pip >/dev/null 2>&1 || true

# Runtime dependencies
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
fi

# Dev / CI tooling (formatters, linters, test + security tools)
if [ -f requirements-dev.txt ]; then
  pip install -r requirements-dev.txt
fi

# Make the project importable for scripts/tests without per-command PYTHONPATH.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PYTHONPATH=\"$PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"
fi

echo "[session-start] Environment ready."
