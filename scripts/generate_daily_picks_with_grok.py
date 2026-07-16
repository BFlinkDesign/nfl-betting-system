"""Disabled compatibility adapter for Grok-enhanced daily picks.

LLM prose, keyword agreement, and sentiment are not calibrated probabilities and
cannot upgrade a betting tier. This module performs no Grok network calls and
cannot create an actionable pick.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from scripts.generate_daily_picks import DailyPicksGenerator

from src.betting.decision_contracts import PAPER_AUTHORITY

logger = logging.getLogger(__name__)

_DISABLED_REASON = (
    "Grok enhancement is advisory-only and disabled for wagering decisions; "
    "LLM agreement cannot promote evidence maturity"
)


class GrokEnhancedPicksGenerator(DailyPicksGenerator):
    """Compatibility shell that preserves zero-action behavior."""

    def __init__(self, *args: Any, use_grok: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if use_grok:
            logger.warning(_DISABLED_REASON)
        self.use_grok = False
        self.grok = None

    def get_grok_analysis(
        self,
        game: Dict[str, Any],
        prediction: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "grok_available": False,
            "status": "ADVISORY_DISABLED",
            "reason": _DISABLED_REASON,
            "authority": PAPER_AUTHORITY,
        }

    def enhance_pick_with_grok(
        self, pick: Dict[str, Any], grok_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = dict(pick)
        result["grok_enhanced"] = False
        result["grok_status"] = "ADVISORY_DISABLED"
        result["live_wagers_authorized"] = False
        return result

    def generate_daily_picks_with_grok(
        self, min_edge: float = 0.05
    ) -> List[Dict[str, Any]]:
        logger.warning(_DISABLED_REASON)
        return []


def main() -> int:
    print(_DISABLED_REASON)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
