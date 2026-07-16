"""Fail-closed compatibility orchestrator for the historical master pipeline.

The former orchestrator mixed unversioned model output, LLM council confidence,
single-book prices, and direct bankroll sizing. It is retained only as a paper
receipt runner. It never fetches games, synthesizes probabilities, sizes stakes,
or authorizes live wagering.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.evaluate_paper_decisions import evaluate_payload
from src.betting.decision_contracts import PAPER_AUTHORITY

logger = logging.getLogger(__name__)

_DISABLED_REASON = (
    "historical master pipeline disabled: use provenance-bound paper decision "
    "contracts; model or council confidence cannot authorize a wager"
)


@dataclass
class PipelineConfig:
    """Configuration for the safe compatibility runner."""

    use_live_odds: bool = False
    use_nflverse: bool = False
    use_weather: bool = False
    use_llm_council: bool = False
    use_research_agent: bool = False
    min_edge_threshold: float = 0.03
    min_confidence_threshold: float = 0.55
    generate_visuals: bool = False
    save_picks_to_db: bool = False
    output_dir: str = "reports"
    bankroll: float = 10000.0
    max_bet_pct: float = 0.0
    evidence_input: Optional[str] = None
    max_age_seconds: int = 300
    min_expected_value_lower_bound: float = 0.0
    live_money_authorized: bool = False

    def __post_init__(self) -> None:
        if self.live_money_authorized:
            raise ValueError(
                "live_money_authorized cannot be enabled in the research branch"
            )
        if isinstance(self.bankroll, bool) or not isinstance(
            self.bankroll, (int, float)
        ):
            raise ValueError("bankroll must be numeric")
        if not math.isfinite(float(self.bankroll)) or float(self.bankroll) <= 0:
            raise ValueError("bankroll must be finite and greater than zero")
        if self.max_bet_pct != 0.0:
            raise ValueError("max_bet_pct must remain zero in the research branch")
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")


@dataclass
class GameData:
    """Legacy game container retained for import compatibility."""

    game_id: str
    home_team: str
    away_team: str
    game_time: datetime
    venue: str = ""
    ml_home: Optional[float] = None
    ml_away: Optional[float] = None
    spread: Optional[float] = None
    total: Optional[float] = None
    home_stats: Dict[str, Any] = field(default_factory=dict)
    away_stats: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, float] = field(default_factory=dict)
    weather: Dict[str, Any] = field(default_factory=dict)
    intelligence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PickResult:
    """Non-actionable compatibility result."""

    game_id: str
    game: str
    pick: str = "pass"
    bet_type: str = "none"
    team: str = ""
    odds: float = 0.0
    line: Optional[float] = None
    model_prob: float = 0.0
    council_confidence: float = 0.0
    council_consensus: float = 0.0
    edge: float = 0.0
    tier: str = "NO_BET"
    kelly_fraction: float = 0.0
    recommended_bet: float = 0.0
    recommended_bet_pct: float = 0.0
    reasoning: List[str] = field(default_factory=lambda: [_DISABLED_REASON])
    research_summary: str = ""
    dissenting_views: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MasterPipeline:
    """Paper-receipt runner; all historical automated-pick behavior is disabled."""

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self.config = config or PipelineConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.last_receipt_path: Optional[Path] = None

    async def fetch_todays_games(self) -> List[GameData]:
        """Return no games because this compatibility path cannot form evidence."""

        logger.warning(_DISABLED_REASON)
        return []

    async def enrich_with_research(self, game: GameData) -> GameData:
        """Do not let model-generated research become betting authority."""

        return game

    async def get_model_prediction(self, game: GameData) -> Dict[str, Any]:
        """Return an explicit unavailable state instead of a 50/50 placeholder."""

        return {
            "prob": None,
            "confidence": 0.0,
            "model_used": False,
            "evidence_status": "unverified",
            "status": "NO_BET",
        }

    async def get_council_decision(self, game: GameData) -> Dict[str, Any]:
        """LLM council output is not accepted as wagering evidence."""

        return {
            "pick": "pass",
            "confidence": 0.0,
            "consensus": 0.0,
            "status": "NO_BET",
        }

    def calculate_bet_size(
        self, prob: float, odds: float, confidence: float
    ) -> Dict[str, float]:
        """Return a zero stake; this branch has no live sizing authority."""

        return {
            "kelly_full": 0.0,
            "kelly_fraction": 0.0,
            "bet_pct": 0.0,
            "bet_amount": 0.0,
        }

    async def analyze_game(self, game: GameData) -> Optional[PickResult]:
        """Do not turn a game object into a wager without canonical evidence."""

        logger.warning("%s: %s @ %s", _DISABLED_REASON, game.away_team, game.home_team)
        return None

    def _blocked_receipt(self) -> Dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "NO_BET",
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
            "reason": _DISABLED_REASON,
        }

    async def run_daily_pipeline(self) -> List[PickResult]:
        """Evaluate an explicit evidence file or emit an auditable NO_BET receipt."""

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if not self.config.evidence_input:
            result: Dict[str, Any] = self._blocked_receipt()
            output = self.output_dir / f"pipeline_blocked_{timestamp}.json"
        else:
            input_path = Path(self.config.evidence_input)
            try:
                payload = json.loads(input_path.read_text(encoding="utf-8"))
                result = evaluate_payload(
                    payload,
                    max_age_seconds=self.config.max_age_seconds,
                    min_expected_value_lower_bound=(
                        self.config.min_expected_value_lower_bound
                    ),
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                result = {
                    **self._blocked_receipt(),
                    "reason": f"invalid_evidence_input:{exc}",
                }
            output = self.output_dir / f"paper_decision_receipts_{timestamp}.json"

        output.write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        self.last_receipt_path = output
        logger.info("Decision receipt written to %s", output)
        return []

    async def cleanup(self) -> None:
        """No external resources are opened by the safe runner."""


async def main() -> int:
    """Run the paper-only compatibility entry point."""

    config = PipelineConfig(
        output_dir=os.getenv("OUTPUT_DIR", "reports"),
        evidence_input=os.getenv("PAPER_EVIDENCE_INPUT"),
    )
    pipeline = MasterPipeline(config)
    await pipeline.run_daily_pipeline()
    if pipeline.last_receipt_path:
        print(f"Receipt: {pipeline.last_receipt_path}")
    return 0 if config.evidence_input else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
