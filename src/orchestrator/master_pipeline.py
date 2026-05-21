"""
Master Pipeline Orchestrator

The central coordinator that runs the entire NFL betting system:

1. Data Ingestion - Fetch latest odds, schedules, injuries
2. Feature Engineering - Build features from raw data
3. Research Agent - Gather intelligence (injuries, trends, sentiment)
4. LLM Council - Multi-model consensus on picks
5. Validation - Check picks against historical patterns
6. Visualization - Generate charts and pick cards
7. Adaptive Learning - Track results and improve

This is the ONE script to run for daily operations.
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Core imports
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the pipeline run."""

    # Data sources
    use_live_odds: bool = True
    use_nflverse: bool = True
    use_weather: bool = True

    # Analysis
    use_llm_council: bool = True
    use_research_agent: bool = True
    min_edge_threshold: float = 0.03  # 3% minimum edge
    min_confidence_threshold: float = 0.55

    # Output
    generate_visuals: bool = True
    save_picks_to_db: bool = True
    output_dir: str = "reports"

    # Bankroll
    bankroll: float = 10000.0
    max_bet_pct: float = 0.05  # 5% max per bet


@dataclass
class GameData:
    """Complete data for a single game."""

    game_id: str
    home_team: str
    away_team: str
    game_time: datetime
    venue: str

    # Odds
    ml_home: Optional[float] = None
    ml_away: Optional[float] = None
    spread: Optional[float] = None
    total: Optional[float] = None

    # Stats
    home_stats: Dict[str, Any] = None
    away_stats: Dict[str, Any] = None

    # Features (model inputs)
    features: Dict[str, float] = None

    # Weather
    weather: Dict[str, Any] = None

    # Research/Intelligence
    intelligence: Dict[str, Any] = None


@dataclass
class PickResult:
    """A generated pick with full context."""

    game_id: str
    game: str
    pick: str  # "home", "away", "over", "under"
    bet_type: str  # "moneyline", "spread", "total"
    team: str
    odds: float
    line: Optional[float]

    # Analysis
    model_prob: float
    council_confidence: float
    council_consensus: float
    edge: float
    tier: str

    # Bet sizing
    kelly_fraction: float
    recommended_bet: float
    recommended_bet_pct: float

    # Reasoning
    reasoning: List[str]
    research_summary: str
    dissenting_views: List[str]

    # Metadata
    timestamp: datetime = None


class MasterPipeline:
    """
    Master orchestrator for the NFL betting system.

    Coordinates all agents and produces final picks.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components (lazy loading)
        self._odds_api = None
        self._espn_api = None
        self._nflverse_api = None
        self._weather_api = None
        self._llm_council = None
        self._research_agent = None
        self._adaptive_engine = None
        self._visualizer = None
        self._model = None
        self._feature_pipeline = None

        logger.info("Master Pipeline initialized")

    @property
    def odds_api(self):
        """Lazy load odds API."""
        if self._odds_api is None:
            from agents.api_integrations import TheOddsAPI

            self._odds_api = TheOddsAPI()
        return self._odds_api

    @property
    def espn_api(self):
        """Lazy load ESPN API."""
        if self._espn_api is None:
            from agents.api_integrations import ESPNAPI

            self._espn_api = ESPNAPI()
        return self._espn_api

    @property
    def nflverse_api(self):
        """Lazy load nflverse API."""
        if self._nflverse_api is None:
            from agents.api_integrations import NFLVerseAPI

            self._nflverse_api = NFLVerseAPI()
        return self._nflverse_api

    @property
    def weather_api(self):
        """Lazy load weather API."""
        if self._weather_api is None:
            from agents.api_integrations import NOAAWeatherAPI

            self._weather_api = NOAAWeatherAPI()
        return self._weather_api

    @property
    def llm_council(self):
        """Lazy load LLM council."""
        if self._llm_council is None:
            from src.agents.llm_council import get_council

            self._llm_council = get_council()
        return self._llm_council

    @property
    def research_agent(self):
        """Lazy load research agent."""
        if self._research_agent is None:
            from src.agents.research_agent import get_research_agent

            self._research_agent = get_research_agent()
        return self._research_agent

    @property
    def adaptive_engine(self):
        """Lazy load adaptive engine."""
        if self._adaptive_engine is None:
            from src.learning.adaptive_engine import get_adaptive_engine

            self._adaptive_engine = get_adaptive_engine()
        return self._adaptive_engine

    @property
    def visualizer(self):
        """Lazy load visualizer."""
        if self._visualizer is None:
            from src.visualization.prediction_visualizer import get_visualizer

            self._visualizer = get_visualizer()
        return self._visualizer

    def _load_model(self):
        """Load the trained prediction model."""
        if self._model is not None:
            return self._model

        import joblib

        model_paths = [
            PROJECT_ROOT / "models" / "xgboost_favorites_only.pkl",
            PROJECT_ROOT / "models" / "xgboost_improved.pkl",
            PROJECT_ROOT / "models" / "xgboost_model.pkl",
        ]

        for path in model_paths:
            if path.exists():
                self._model = joblib.load(path)
                logger.info(f"Loaded model from {path}")
                return self._model

        logger.warning("No trained model found!")
        return None

    async def fetch_todays_games(self) -> List[GameData]:
        """Fetch today's games with odds from multiple sources."""
        games = []

        # Get odds from The Odds API (blocking I/O off the event loop)
        if self.config.use_live_odds and os.getenv("ODDS_API_KEY"):
            logger.info("Fetching live odds...")
            odds_data = await asyncio.to_thread(self.odds_api.get_nfl_odds)

            for game_odds in odds_data:
                game = GameData(
                    game_id=game_odds.get("id", ""),
                    home_team=game_odds.get("home_team", ""),
                    away_team=game_odds.get("away_team", ""),
                    game_time=datetime.fromisoformat(
                        game_odds.get("commence_time", "").replace("Z", "+00:00")
                    ),
                    venue="",
                )

                # Extract odds from bookmakers
                for bookmaker in game_odds.get("bookmakers", []):
                    if bookmaker.get("key") == "fanduel":  # Prefer FanDuel
                        for market in bookmaker.get("markets", []):
                            if market.get("key") == "h2h":
                                for outcome in market.get("outcomes", []):
                                    if outcome.get("name") == game.home_team:
                                        game.ml_home = outcome.get("price")
                                    else:
                                        game.ml_away = outcome.get("price")
                            elif market.get("key") == "spreads":
                                for outcome in market.get("outcomes", []):
                                    if outcome.get("name") == game.home_team:
                                        game.spread = outcome.get("point")
                            elif market.get("key") == "totals":
                                for outcome in market.get("outcomes", []):
                                    if outcome.get("name") == "Over":
                                        game.total = outcome.get("point")
                        break

                games.append(game)

            logger.info(f"Found {len(games)} games with odds")

        # Fallback to ESPN if no odds API
        if not games:
            logger.info("Fetching from ESPN...")
            scoreboard = await asyncio.to_thread(self.espn_api.get_scoreboard, 2024)

            for event in scoreboard.get("events", []):
                if event.get("status", {}).get("type", {}).get("state") == "pre":
                    competition = event.get("competitions", [{}])[0]
                    competitors = competition.get("competitors", [])

                    home = next(
                        (c for c in competitors if c.get("homeAway") == "home"), {}
                    )
                    away = next(
                        (c for c in competitors if c.get("homeAway") == "away"), {}
                    )

                    game = GameData(
                        game_id=event.get("id", ""),
                        home_team=home.get("team", {}).get("displayName", ""),
                        away_team=away.get("team", {}).get("displayName", ""),
                        game_time=datetime.fromisoformat(
                            event.get("date", "").replace("Z", "+00:00")
                        ),
                        venue=competition.get("venue", {}).get("fullName", ""),
                    )
                    games.append(game)

            logger.info(f"Found {len(games)} upcoming games from ESPN")

        return games

    async def enrich_with_research(self, game: GameData) -> GameData:
        """Add research intelligence to a game."""
        if not self.config.use_research_agent:
            return game

        if not os.getenv("PERPLEXITY_API_KEY"):
            logger.warning("PERPLEXITY_API_KEY not set - skipping research")
            return game

        try:
            logger.info(f"Researching {game.away_team} @ {game.home_team}...")
            intel = await self.research_agent.compile_game_intelligence(
                home_team=game.home_team,
                away_team=game.away_team,
                venue=game.venue,
                game_time=game.game_time.strftime("%A, %B %d, %Y %I:%M %p"),
                game_id=game.game_id,
            )
            game.intelligence = asdict(intel)
        except Exception as e:
            logger.error(f"Research failed for {game.game_id}: {e}")

        return game

    async def get_model_prediction(self, game: GameData) -> Dict[str, Any]:
        """Get prediction from the trained ML model."""
        model = await asyncio.to_thread(self._load_model)
        if model is None:
            return {"prob": 0.5, "confidence": 0.0, "model_used": False}

        # Build features for this game
        # This is simplified - in production, would use full FeaturePipeline
        try:
            from src.features.elo import EloFeatures
            from src.features.form import FormFeatures

            # Get team Elo ratings
            elo_features = EloFeatures()

            # Try to get features from saved file
            features_path = (
                PROJECT_ROOT / "data" / "features_2016_2024_improved.parquet"
            )
            if features_path.exists():
                df = await asyncio.to_thread(pd.read_parquet, features_path)

                # Get most recent data for these teams
                home_data = df[df["home_team"] == game.home_team].sort_values(
                    "gameday", ascending=False
                )
                away_data = df[df["away_team"] == game.away_team].sort_values(
                    "gameday", ascending=False
                )

                if not home_data.empty and not away_data.empty:
                    # Use most recent feature values
                    feature_cols = [
                        c
                        for c in df.columns
                        if c
                        not in [
                            "game_id",
                            "season",
                            "week",
                            "gameday",
                            "home_team",
                            "away_team",
                            "home_score",
                            "away_score",
                            "result",
                            "spread_line",
                            "total_line",
                        ]
                    ]

                    # Average recent features
                    X = pd.DataFrame([home_data[feature_cols].iloc[:3].mean()])

                    prob = model.predict_proba(X)[0][1]
                    return {
                        "prob": prob,
                        "confidence": abs(prob - 0.5) * 2,
                        "model_used": True,
                    }

        except Exception as e:
            logger.warning(f"Feature extraction failed: {e}")

        return {"prob": 0.5, "confidence": 0.0, "model_used": False}

    async def get_council_decision(self, game: GameData) -> Dict[str, Any]:
        """Get decision from the LLM Council."""
        if not self.config.use_llm_council:
            return {"pick": "pass", "confidence": 0.0, "consensus": 0.0}

        if not self.llm_council.members:
            logger.warning("No LLM council members configured")
            return {"pick": "pass", "confidence": 0.0, "consensus": 0.0}

        try:
            game_data = {
                "game_id": game.game_id,
                "home_team": game.home_team,
                "away_team": game.away_team,
                "game_time": game.game_time.isoformat(),
                "venue": game.venue,
                "ml_home": game.ml_home,
                "ml_away": game.ml_away,
                "spread": game.spread,
                "total": game.total,
                "home_stats": game.home_stats or {},
                "away_stats": game.away_stats or {},
                "weather": game.weather or {},
                "intelligence": game.intelligence or {},
            }

            decision = await self.llm_council.analyze_game(game_data)

            return {
                "pick": decision.pick,
                "confidence": decision.confidence,
                "consensus": decision.consensus_pct,
                "tier": decision.tier,
                "reasoning": decision.reasoning,
                "dissenting": decision.dissenting_views,
                "summary": decision.chairman_summary,
            }

        except Exception as e:
            logger.error(f"Council analysis failed: {e}")
            return {"pick": "pass", "confidence": 0.0, "consensus": 0.0}

    def calculate_bet_size(
        self, prob: float, odds: float, confidence: float
    ) -> Dict[str, float]:
        """Calculate optimal bet size using Kelly Criterion."""
        # Convert American odds to decimal
        if odds > 0:
            decimal_odds = odds / 100 + 1
        else:
            decimal_odds = 100 / abs(odds) + 1

        # Kelly formula: f = (bp - q) / b
        # where b = decimal odds - 1, p = probability, q = 1 - p
        b = decimal_odds - 1
        p = prob
        q = 1 - p

        kelly = (b * p - q) / b if b > 0 else 0

        # Apply fractional Kelly (25-50% based on confidence)
        kelly_fraction = 0.25 + (confidence * 0.25)  # 25-50%
        adjusted_kelly = kelly * kelly_fraction

        # Cap at max bet percentage
        bet_pct = min(adjusted_kelly, self.config.max_bet_pct)
        bet_pct = max(bet_pct, 0)  # No negative bets

        bet_amount = self.config.bankroll * bet_pct

        return {
            "kelly_full": kelly,
            "kelly_fraction": kelly_fraction,
            "bet_pct": bet_pct,
            "bet_amount": bet_amount,
        }

    async def analyze_game(self, game: GameData) -> Optional[PickResult]:
        """Full analysis of a single game."""
        logger.info(f"\n{'='*50}")
        logger.info(f"ANALYZING: {game.away_team} @ {game.home_team}")
        logger.info(f"{'='*50}")

        # Step 1: Research
        game = await self.enrich_with_research(game)

        # Step 2: Model prediction
        model_pred = await self.get_model_prediction(game)
        logger.info(
            f"Model prob: {model_pred['prob']:.1%}, Used: {model_pred['model_used']}"
        )

        # Step 3: Council decision
        council = await self.get_council_decision(game)
        logger.info(
            f"Council: {council['pick']}, Conf: {council.get('confidence', 0):.1%}"
        )

        # Step 4: Combine signals
        if (
            council["pick"] == "pass"
            or council.get("confidence", 0) < self.config.min_confidence_threshold
        ):
            logger.info("PASS - Confidence too low")
            return None

        # Determine final pick
        pick = council["pick"]
        pick_team = game.home_team if pick == "home" else game.away_team
        odds = game.ml_home if pick == "home" else game.ml_away

        if odds is None:
            logger.info("PASS - No odds available")
            return None

        # Calculate edge
        implied_prob = 100 / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)
        our_prob = (
            model_pred["prob"]
            if model_pred["model_used"]
            else council.get("confidence", 0.5)
        )
        edge = our_prob - implied_prob

        if edge < self.config.min_edge_threshold:
            logger.info(f"PASS - Edge too low ({edge:.1%})")
            return None

        # Step 5: Calculate bet size
        bet_info = self.calculate_bet_size(
            our_prob, odds, council.get("confidence", 0.5)
        )

        # Build result
        result = PickResult(
            game_id=game.game_id,
            game=f"{game.away_team} @ {game.home_team}",
            pick=pick,
            bet_type="moneyline",
            team=pick_team,
            odds=odds,
            line=None,
            model_prob=model_pred["prob"],
            council_confidence=council.get("confidence", 0),
            council_consensus=council.get("consensus", 0),
            edge=edge,
            tier=council.get("tier", "B_tier"),
            kelly_fraction=bet_info["kelly_fraction"],
            recommended_bet=bet_info["bet_amount"],
            recommended_bet_pct=bet_info["bet_pct"],
            reasoning=(
                council.get("reasoning", "").split("; ")
                if isinstance(council.get("reasoning"), str)
                else []
            ),
            research_summary=council.get("summary", ""),
            dissenting_views=council.get("dissenting", []),
            timestamp=datetime.now(),
        )

        logger.info(
            f"✓ PICK: {pick_team} ({odds:+.0f}) | Edge: {edge:.1%} | Bet: ${bet_info['bet_amount']:.0f}"
        )

        return result

    async def run_daily_pipeline(self) -> List[PickResult]:
        """
        Run the complete daily pipeline.

        Returns:
            List of recommended picks
        """
        logger.info("\n" + "=" * 60)
        logger.info("NFL BETTING SYSTEM - DAILY PIPELINE")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        # Step 1: Fetch games
        games = await self.fetch_todays_games()

        if not games:
            logger.info("No games found for today")
            return []

        logger.info(f"\nFound {len(games)} games to analyze")

        # Step 2: Analyze each game
        picks = []
        for game in games:
            try:
                pick = await self.analyze_game(game)
                if pick:
                    picks.append(pick)
            except Exception as e:
                logger.error(f"Error analyzing {game.home_team}: {e}")

        # Step 3: Sort by tier and confidence
        tier_order = {"S_tier": 0, "A_tier": 1, "B_tier": 2, "no_bet": 3}
        picks.sort(key=lambda x: (tier_order.get(x.tier, 3), -x.council_confidence))

        # Step 4: Generate outputs
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save picks to JSON
        picks_data = {
            "generated_at": datetime.now().isoformat(),
            "bankroll": self.config.bankroll,
            "picks_count": len(picks),
            "picks": [
                {
                    "game_id": p.game_id,
                    "game": p.game,
                    "pick": p.pick,
                    "team": p.team,
                    "bet_type": p.bet_type,
                    "odds": p.odds,
                    "model_prob": p.model_prob,
                    "council_confidence": p.council_confidence,
                    "council_consensus": p.council_consensus,
                    "edge": p.edge,
                    "tier": p.tier,
                    "kelly_fraction": p.kelly_fraction,
                    "recommended_bet": p.recommended_bet,
                    "recommended_bet_pct": p.recommended_bet_pct,
                    "reasoning": p.reasoning,
                    "research_summary": p.research_summary,
                }
                for p in picks
            ],
        }

        picks_path = self.output_dir / f"daily_picks_{timestamp}.json"
        with open(picks_path, "w") as f:
            json.dump(picks_data, f, indent=2, default=str)
        logger.info(f"\nSaved picks to {picks_path}")

        # Step 5: Generate visuals (if enabled)
        if self.config.generate_visuals and picks:
            logger.info("\nGenerating visualizations...")

            # Summary graphic
            picks_for_viz = [
                {
                    "game": p.game,
                    "pick": p.team,
                    "odds": int(p.odds),
                    "confidence": p.council_confidence,
                    "tier": p.tier,
                }
                for p in picks
            ]

            summary = self.visualizer.create_daily_picks_summary(
                picks_for_viz, datetime.now().strftime("%B %d, %Y")
            )
            logger.info(f"Saved summary to {summary.file_path}")

            # Individual pick cards for top picks
            for pick in picks[:3]:  # Top 3
                card = self.visualizer.create_matchup_card(
                    home_team=pick.game.split(" @ ")[1],
                    away_team=pick.game.split(" @ ")[0],
                    pick=pick.pick,
                    confidence=pick.council_confidence,
                    edge=pick.edge,
                    odds=pick.odds,
                    tier=pick.tier,
                    game_time=pick.timestamp.strftime("%a %b %d, %I:%M %p"),
                    reasoning=pick.reasoning,
                )
                logger.info(f"Saved card to {card.file_path}")

        # Step 6: Record for adaptive learning
        if self.config.save_picks_to_db:
            for pick in picks:
                from src.learning.adaptive_engine import PredictionRecord

                record = PredictionRecord(
                    prediction_id=f"{pick.game_id}_{timestamp}",
                    game_id=pick.game_id,
                    timestamp=pick.timestamp,
                    home_team=pick.game.split(" @ ")[1],
                    away_team=pick.game.split(" @ ")[0],
                    pick=pick.pick,
                    bet_type=pick.bet_type,
                    line=pick.line or 0,
                    odds=pick.odds,
                    confidence=pick.council_confidence,
                    edge=pick.edge,
                    model_name="ensemble",
                    council_consensus=pick.council_consensus,
                    tier=pick.tier,
                )
                self.adaptive_engine.record_prediction(record)

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("DAILY PIPELINE COMPLETE")
        logger.info(f"Games Analyzed: {len(games)}")
        logger.info(f"Picks Generated: {len(picks)}")

        if picks:
            total_bet = sum(p.recommended_bet for p in picks)
            logger.info(f"Total Action: ${total_bet:.2f}")

            logger.info("\nTOP PICKS:")
            for i, p in enumerate(picks[:5], 1):
                logger.info(
                    f"  {i}. {p.team} ({p.odds:+.0f}) - {p.tier} - ${p.recommended_bet:.0f}"
                )

        logger.info("=" * 60)

        return picks

    async def cleanup(self):
        """Cleanup resources."""
        if self._llm_council:
            await self._llm_council.close()
        if self._research_agent:
            await self._research_agent.close()


async def main():
    """Main entry point for the daily pipeline."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    config = PipelineConfig(
        bankroll=float(os.getenv("BANKROLL", "10000")),
        generate_visuals=True,
        save_picks_to_db=True,
    )

    # Run pipeline
    pipeline = MasterPipeline(config)

    try:
        picks = await pipeline.run_daily_pipeline()

        # Print picks to stdout for easy copy/paste
        print("\n" + "=" * 50)
        print("TODAY'S RECOMMENDED BETS")
        print("=" * 50)

        for pick in picks:
            print(f"\n{pick.tier.replace('_', ' ').upper()}: {pick.team}")
            print(f"  Game: {pick.game}")
            print(f"  Odds: {pick.odds:+.0f}")
            print(f"  Edge: {pick.edge:.1%}")
            print(f"  Confidence: {pick.council_confidence:.1%}")
            print(
                f"  Recommended: ${pick.recommended_bet:.0f} ({pick.recommended_bet_pct:.1%})"
            )
            if pick.reasoning:
                print(f"  Reason: {pick.reasoning[0]}")

        return picks

    finally:
        await pipeline.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
