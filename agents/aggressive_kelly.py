"""Disabled compatibility adapter for the historical aggressive Kelly module.

This repository is research/paper-trading only. The former implementation
multiplied stake sizes based on model confidence, situational claims, weather
confidence, and recent win streaks. Those multipliers are not supported by a
reproducible, live-validated evidence bundle and can amplify estimation error.

The public class name is retained so historical imports fail closed instead of
silently reviving the old behavior.
"""

from __future__ import annotations

from typing import Any, Dict

PAPER_AUTHORITY = "paper_only_no_live_wager_authority"
_DISABLED_REASON = (
    "legacy aggressive Kelly sizing is disabled; use provenance-bound "
    "paper decision receipts and the conservative Kelly analysis boundary"
)


class AggressiveKellyCalculator:
    """Compatibility shell that always returns a zero-stake blocked result."""

    def __init__(self, bankroll: float, max_bet_pct: float = 0.10) -> None:
        if isinstance(bankroll, bool) or not isinstance(bankroll, (int, float)):
            raise ValueError("bankroll must be numeric")
        if float(bankroll) <= 0:
            raise ValueError("bankroll must be greater than zero")
        if isinstance(max_bet_pct, bool) or not isinstance(
            max_bet_pct, (int, float)
        ):
            raise ValueError("max_bet_pct must be numeric")
        if float(max_bet_pct) <= 0:
            raise ValueError("max_bet_pct must be greater than zero")

        self.bankroll = float(bankroll)
        self.requested_max_bet_pct = float(max_bet_pct)
        self.max_bet_pct = 0.0
        self.recent_bets: list[dict[str, Any]] = []

    def calculate_bet_size(
        self,
        edge: float,
        confidence: float,
        situational_edge: float = 0.0,
        weather_confidence: str = "MEDIUM",
        recent_performance: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Return an explicit blocked receipt; never return an actionable stake."""

        return {
            "bet_size": 0.0,
            "bet_pct": 0.0,
            "kelly_fraction": 0.0,
            "multiplier": 0.0,
            "tier": "NO BET",
            "emoji": "",
            "optimal_kelly": 0.0,
            "reasoning": _DISABLED_REASON,
            "blocked": True,
            "blockers": [
                "aggressive_sizing_not_supported_by_reproducible_evidence",
                "live_wager_authority_absent",
            ],
            "authority": PAPER_AUTHORITY,
            "inputs_observed": {
                "edge": edge,
                "confidence": confidence,
                "situational_edge": situational_edge,
                "weather_confidence": weather_confidence,
                "recent_performance_supplied": recent_performance is not None,
            },
        }

    def get_tier_stats(self) -> list[dict[str, Any]]:
        """Return no performance summary because this path cannot size wagers."""

        return []


def main() -> int:
    """Print the fail-closed status for direct historical invocations."""

    result = AggressiveKellyCalculator(bankroll=1.0).calculate_bet_size(
        edge=0.0,
        confidence=0.0,
    )
    print(result["reasoning"])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
