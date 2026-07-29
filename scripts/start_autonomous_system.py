"""Disabled entry point for the historical autonomous betting system.

The repository is research/paper-trading only. Starting agents, swarms,
notifications, remediation loops, and continuous backtests under an
"autonomous betting" entry point would exceed the current authority envelope.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.betting.decision_contracts import PAPER_AUTHORITY

_DISABLED_REASON = (
    "autonomous betting runtime is disabled until model, market, settlement, "
    "paper-trading, and explicit human authorization gates pass"
)


class AutonomousExecutionBlockedError(RuntimeError):
    """Raised when the historical autonomous runtime is started."""


class AutonomousSystem:
    """Compatibility object that cannot start operational agents."""

    def __init__(self) -> None:
        self.status = "BLOCKED"

    def receipt(self) -> Dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "NO_BET",
            "runtime": "autonomous_system",
            "reason": _DISABLED_REASON,
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
            "agents_started": 0,
        }

    async def start(self) -> None:
        raise AutonomousExecutionBlockedError(_DISABLED_REASON)

    async def stop(self) -> None:
        self.status = "STOPPED"


async def main() -> int:
    system = AutonomousSystem()
    output = Path(
        os.getenv("AUTONOMOUS_BLOCK_RECEIPT", "reports/autonomous_blocked.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = system.receipt()
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
