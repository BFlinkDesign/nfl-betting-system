"""Consensus Swarm - Daily picks through agent consensus."""

import logging
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.swarms.model_loader import ModelLoader
from src.swarms.prediction_pipeline import PredictionPipeline
from src.swarms.swarm_base import ConsensusRule, SwarmBase

logger = logging.getLogger(__name__)


class ConsensusSwarm(SwarmBase):
    """
    Consensus Swarm (Daily Picks)

    Size: 7-12 agents (odd number, mixed providers)
    Decision rule: Majority vote with confidence scaling
    """

    def __init__(
        self,
        agents: List[BaseAgent],
        model_assignments: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize consensus swarm.

        Args:
            agents: List of BaseAgent instances
            model_assignments: Dict mapping agent_id to model_name (optional)
                              If None, will auto-assign from available models
        """
        super().__init__(
            swarm_id="consensus_swarm_001",
            swarm_name="Consensus Swarm",
            agents=agents,
            consensus_rule=ConsensusRule.WEIGHTED,
        )

        # Initialize prediction pipelines for each agent
        self.prediction_pipelines: Dict[str, PredictionPipeline] = {}
        self._initialize_pipelines(model_assignments)

        logger.info(
            f"Consensus Swarm initialized with {len(self.prediction_pipelines)} models"
        )

    def _initialize_pipelines(self, model_assignments: Optional[Dict[str, str]]):
        """Initialize prediction pipelines for agents."""
        model_loader = ModelLoader()

        if model_assignments is None:
            # Auto-assign models
            model_assignments = model_loader.get_default_models()

        available_models = model_loader.list_available_models()
        if not available_models:
            logger.warning("No trained models found! Predictions will fail.")
            return

        # Assign models to agents
        for agent in self.agents:
            # Try to get assigned model for this agent
            model_name = model_assignments.get(agent.agent_id)

            # Fallback: cycle through available models
            if model_name is None or model_name not in available_models:
                agent_index = self.agents.index(agent)
                model_name = available_models[agent_index % len(available_models)]

            try:
                pipeline = PredictionPipeline(model_name)
                self.prediction_pipelines[agent.agent_id] = pipeline
                logger.info(f"Agent {agent.agent_id} assigned model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize pipeline for {agent.agent_id}: {e}")

    async def generate_daily_picks(self, games: List[Dict]) -> List[Dict]:
        """
        Generate daily picks through swarm consensus.

        Args:
            games: List of games to analyze

        Returns:
            List of picks with confidence tiers
        """
        picks = []

        for game in games:
            # Phase 1: Individual analysis (each agent evaluates game)
            individual_picks = await self._individual_analysis(game)

            # Phase 2: Deliberation (share picks, debate disagreements)
            deliberated = await self._deliberation_phase(individual_picks)

            # Phase 3: Voting (weighted by recent_performance × confidence)
            vote_result = await self._voting_phase(deliberated)

            # Phase 4: Quality check (Risk Management Agent review)
            if vote_result.get("consensus_pct", 0) >= 0.60:
                pick = {
                    "game": game,
                    "pick": vote_result.get("pick"),
                    "confidence": vote_result.get("confidence", 0),
                    "consensus_pct": vote_result.get("consensus_pct", 0),
                    "tier": self._assign_tier(vote_result),
                }
                picks.append(pick)

        return picks

    async def _individual_analysis(self, game: Dict) -> List[Dict]:
        """
        Each agent analyzes the game using their assigned model.

        Args:
            game: Dict with game info (home_team, away_team, gameday, etc.)

        Returns:
            List of picks from each agent with confidence scores
        """
        picks = []

        for agent in self.agents:
            # Get agent's prediction pipeline
            pipeline = self.prediction_pipelines.get(agent.agent_id)

            if pipeline is None:
                logger.warning(f"No pipeline for agent {agent.agent_id}, using default")
                pick = {
                    "agent": agent.agent_id,
                    "pick": "home",
                    "confidence": 0.5,
                    "pred_prob": 0.5,
                    "model_name": "default",
                }
            else:
                try:
                    # Generate real prediction
                    prediction = pipeline.predict(game)
                    pick = {
                        "agent": agent.agent_id,
                        "pick": prediction["pick"],
                        "confidence": prediction["confidence"],
                        "pred_prob": prediction["pred_prob"],
                        "model_name": prediction["model_name"],
                    }
                except Exception as e:
                    logger.error(f"Prediction failed for agent {agent.agent_id}: {e}")
                    # Fallback to conservative prediction
                    pick = {
                        "agent": agent.agent_id,
                        "pick": "home",
                        "confidence": 0.5,
                        "pred_prob": 0.5,
                        "model_name": "error_fallback",
                        "error": str(e),
                    }

            picks.append(pick)

        return picks

    async def _deliberation_phase(self, picks: List[Dict]) -> List[Dict]:
        """
        Agents deliberate: when an agent's pick disagrees with the majority
        AND has low confidence, adjust confidence toward the consensus view.
        """
        if len(picks) < 3:
            return picks

        vote_counts: Dict[str, int] = {}
        for p in picks:
            v = p.get("pick", "home")
            vote_counts[v] = vote_counts.get(v, 0) + 1

        majority_pick = max(vote_counts, key=vote_counts.get)
        majority_pct = vote_counts[majority_pick] / len(picks)

        refined = []
        for p in picks:
            p = dict(p)
            if p.get("pick") != majority_pick and p.get("confidence", 0) < 0.55:
                if majority_pct >= 0.70:
                    p["confidence"] = p.get("confidence", 0.5) * 0.7
                    p["deliberation_note"] = "low-conf minority, confidence dampened"
            elif p.get("pick") == majority_pick and majority_pct >= 0.80:
                p["confidence"] = min(p.get("confidence", 0.5) * 1.1, 1.0)
                p["deliberation_note"] = "high-consensus majority, confidence boosted"
            refined.append(p)

        return refined

    async def _voting_phase(self, picks: List[Dict]) -> Dict[str, Any]:
        """Weighted voting."""
        # Count votes by pick
        vote_counts = {}
        total_confidence = {}

        for pick in picks:
            pick_value = pick.get("pick")
            confidence = pick.get("confidence", 0)

            if pick_value not in vote_counts:
                vote_counts[pick_value] = 0
                total_confidence[pick_value] = 0

            vote_counts[pick_value] += 1
            total_confidence[pick_value] += confidence

        # Find winner
        winner = max(vote_counts.items(), key=lambda x: x[1])
        consensus_pct = winner[1] / len(picks)
        avg_confidence = total_confidence[winner[0]] / winner[1]

        return {
            "pick": winner[0],
            "confidence": avg_confidence,
            "consensus_pct": consensus_pct,
            "votes": vote_counts,
        }

    def _assign_tier(self, vote_result: Dict[str, Any]) -> str:
        """Assign confidence tier."""
        consensus = vote_result.get("consensus_pct", 0)
        confidence = vote_result.get("confidence", 0)

        if consensus >= 0.90 and confidence > 0.10:
            return "S_tier"  # ≥90% consensus, 5% bankroll, >10% ROI
        elif consensus >= 0.75:
            return "A_tier"  # 75-89% consensus, 3% bankroll, 5-10% ROI
        elif consensus >= 0.60:
            return "B_tier"  # 60-74% consensus, 1.5% bankroll, 3-5% ROI
        else:
            return "no_bet"  # <60% consensus, skip
