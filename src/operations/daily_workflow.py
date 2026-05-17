"""Daily operations workflow for professional betting.

Implements the professional bettor daily routine:
1. Morning: Check overnight lines, run model, identify value
2. Continuous: Monitor line movements, execute bets
3. Post-Game: Record closing lines, calculate CLV, update model

Sources:
- GamblingSite Professional Bettor Daily Habits
- Billy Walters morning routine (starts before sunrise)
- Haralabos Voulgaris process
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValueBet:
    """Identified value betting opportunity."""
    game_id: str
    home_team: str
    away_team: str
    market: str
    selection: str
    model_prob: float
    best_odds: float
    best_book: str
    implied_prob: float
    edge: float
    recommended_stake_pct: float
    confidence: str  # high, medium, low
    notes: str = ""


@dataclass
class DailyPlan:
    """Daily betting plan output."""
    date: datetime
    games_analyzed: int
    value_bets: List[ValueBet]
    total_recommended_exposure: float
    alerts: List[str]
    generated_at: datetime


class DailyWorkflow:
    """
    Professional daily betting workflow.

    Automates the morning routine and continuous monitoring.
    """

    def __init__(
        self,
        model=None,
        odds_client=None,
        position_tracker=None,
        line_shopper=None,
        min_edge: float = 0.02,
        min_probability: float = 0.52
    ):
        """
        Initialize workflow.

        Args:
            model: Trained prediction model
            odds_client: Odds API client
            position_tracker: Position tracking system
            line_shopper: Line shopping system
            min_edge: Minimum edge to consider (2% default)
            min_probability: Minimum probability to bet
        """
        self.model = model
        self.odds_client = odds_client
        self.position_tracker = position_tracker
        self.line_shopper = line_shopper
        self.min_edge = min_edge
        self.min_probability = min_probability

    def run_morning_routine(
        self,
        games_df: pd.DataFrame,
        odds_data: Optional[Dict] = None
    ) -> DailyPlan:
        """
        Execute morning routine.

        Per Billy Walters: "mornings begin before sunrise when overnight
        lines from sportsbooks can still be grabbed"

        Args:
            games_df: Today's games with features
            odds_data: Current odds from API (if available)

        Returns:
            DailyPlan with recommended bets
        """
        logger.info("=" * 70)
        logger.info(f"MORNING ROUTINE - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        logger.info("=" * 70)

        alerts = []
        value_bets = []

        # Step 1: Run model on today's games
        logger.info("\n1. Running model predictions...")

        if self.model is None:
            alerts.append("WARNING: No model loaded - using placeholder predictions")
            games_df['pred_prob'] = 0.5
        else:
            try:
                games_df['pred_prob'] = self.model.predict_proba(games_df)
            except Exception as e:
                alerts.append(f"ERROR: Model prediction failed - {e}")
                games_df['pred_prob'] = 0.5

        # Step 2: Compare model to market
        logger.info("\n2. Comparing model probabilities to market odds...")

        for idx, row in games_df.iterrows():
            game_id = row.get('game_id', f"game_{idx}")
            home_team = row.get('home_team', 'Home')
            away_team = row.get('away_team', 'Away')
            model_prob = row['pred_prob']

            # Get market odds (from API or default)
            if odds_data and game_id in odds_data:
                market_odds = odds_data[game_id]
            else:
                # Default to -110 / -110 if no odds
                market_odds = {'home': 1.91, 'away': 1.91}
                alerts.append(f"No live odds for {game_id} - using default")

            # Check home team value
            home_implied = 1 / market_odds.get('home', 1.91)
            home_edge = model_prob - home_implied

            if home_edge >= self.min_edge and model_prob >= self.min_probability:
                stake_pct = self._calculate_kelly_stake(model_prob, market_odds['home'])
                confidence = self._assess_confidence(home_edge, model_prob)

                value_bets.append(ValueBet(
                    game_id=game_id,
                    home_team=home_team,
                    away_team=away_team,
                    market='moneyline',
                    selection=home_team,
                    model_prob=model_prob,
                    best_odds=market_odds['home'],
                    best_book='TBD',
                    implied_prob=home_implied,
                    edge=home_edge,
                    recommended_stake_pct=stake_pct,
                    confidence=confidence
                ))

            # Check away team value
            away_prob = 1 - model_prob
            away_implied = 1 / market_odds.get('away', 1.91)
            away_edge = away_prob - away_implied

            if away_edge >= self.min_edge and away_prob >= self.min_probability:
                stake_pct = self._calculate_kelly_stake(away_prob, market_odds['away'])
                confidence = self._assess_confidence(away_edge, away_prob)

                value_bets.append(ValueBet(
                    game_id=game_id,
                    home_team=home_team,
                    away_team=away_team,
                    market='moneyline',
                    selection=away_team,
                    model_prob=away_prob,
                    best_odds=market_odds['away'],
                    best_book='TBD',
                    implied_prob=away_implied,
                    edge=away_edge,
                    recommended_stake_pct=stake_pct,
                    confidence=confidence
                ))

        # Step 3: Create daily plan
        total_exposure = sum(vb.recommended_stake_pct for vb in value_bets)

        plan = DailyPlan(
            date=datetime.now(),
            games_analyzed=len(games_df),
            value_bets=value_bets,
            total_recommended_exposure=total_exposure,
            alerts=alerts,
            generated_at=datetime.now()
        )

        # Print summary
        self._print_morning_summary(plan)

        return plan

    def _calculate_kelly_stake(self, prob: float, odds: float, fraction: float = 0.25) -> float:
        """Calculate fractional Kelly stake percentage."""
        # Kelly formula: f* = (bp - q) / b
        # where b = odds - 1, p = prob, q = 1 - p
        b = odds - 1
        p = prob
        q = 1 - p

        if b <= 0:
            return 0

        full_kelly = (b * p - q) / b
        fractional_kelly = full_kelly * fraction

        # Cap at 3% per bet (professional standard)
        return min(max(fractional_kelly, 0), 0.03)

    def _assess_confidence(self, edge: float, prob: float) -> str:
        """Assess confidence level of bet."""
        if edge >= 0.05 and prob >= 0.60:
            return 'high'
        elif edge >= 0.03 and prob >= 0.55:
            return 'medium'
        else:
            return 'low'

    def _print_morning_summary(self, plan: DailyPlan) -> None:
        """Print formatted morning summary."""
        print("\n" + "=" * 70)
        print("MORNING ANALYSIS COMPLETE")
        print("=" * 70)

        print(f"\nGames Analyzed: {plan.games_analyzed}")
        print(f"Value Bets Found: {len(plan.value_bets)}")
        print(f"Total Recommended Exposure: {plan.total_recommended_exposure:.1%}")

        if plan.alerts:
            print(f"\n⚠ ALERTS ({len(plan.alerts)}):")
            for alert in plan.alerts:
                print(f"  - {alert}")

        if plan.value_bets:
            print("\n" + "-" * 70)
            print("VALUE BETS:")
            print("-" * 70)

            # Sort by edge
            sorted_bets = sorted(plan.value_bets, key=lambda x: x.edge, reverse=True)

            for vb in sorted_bets:
                conf_indicator = {'high': '★★★', 'medium': '★★', 'low': '★'}[vb.confidence]
                print(f"\n  {conf_indicator} {vb.selection} ({vb.market})")
                print(f"     Game: {vb.away_team} @ {vb.home_team}")
                print(f"     Model: {vb.model_prob:.1%} | Market: {vb.implied_prob:.1%} | Edge: {vb.edge:.1%}")
                print(f"     Best Odds: {vb.best_odds:.3f} ({vb.best_book})")
                print(f"     Recommended: {vb.recommended_stake_pct:.2%} of bankroll")

        else:
            print("\n  No value bets identified today.")

        print("\n" + "=" * 70)
        print("ACTION ITEMS:")
        print("=" * 70)

        if plan.value_bets:
            print("  1. Shop lines at all books before placing bets")
            print("  2. Verify injury/news hasn't changed since analysis")
            print("  3. Execute bets closest to game time for best CLV")
            print("  4. Record all bet details for CLV tracking")
        else:
            print("  1. Continue monitoring for line movements")
            print("  2. Re-run analysis if significant news breaks")

        print("=" * 70)

    def run_post_game_routine(
        self,
        completed_games: List[str],
        closing_odds: Dict[str, Dict[str, float]],
        results: Dict[str, int]
    ) -> Dict:
        """
        Execute post-game routine.

        Record closing lines, calculate CLV, update performance.

        Args:
            completed_games: List of completed game IDs
            closing_odds: Closing odds for each game
            results: Game results (1 = home win, 0 = away win)

        Returns:
            Performance summary
        """
        logger.info("\n" + "=" * 70)
        logger.info("POST-GAME ROUTINE")
        logger.info("=" * 70)

        summary = {
            'games_processed': 0,
            'bets_settled': 0,
            'clv_calculated': 0,
            'avg_clv': 0,
            'daily_pnl': 0
        }

        if self.position_tracker is None:
            logger.warning("No position tracker - cannot update bets")
            return summary

        # Get pending bets for these games
        pending = self.position_tracker.get_pending_bets()

        for bet in pending:
            if bet.game_id in completed_games:
                game_result = results.get(bet.game_id)
                game_closing = closing_odds.get(bet.game_id, {})

                if game_result is not None:
                    # Determine bet result
                    if bet.selection == 'home':
                        bet_result = 'win' if game_result == 1 else 'loss'
                        closing = game_closing.get('home')
                    else:
                        bet_result = 'win' if game_result == 0 else 'loss'
                        closing = game_closing.get('away')

                    # Update bet
                    self.position_tracker.update_bet_result(
                        bet_id=bet.bet_id,
                        result=bet_result,
                        closing_odds=closing
                    )

                    summary['bets_settled'] += 1
                    if closing:
                        summary['clv_calculated'] += 1

        # Calculate daily metrics
        metrics = self.position_tracker.calculate_performance_metrics()
        summary['avg_clv'] = metrics.get('avg_clv', 0)
        summary['daily_pnl'] = self.position_tracker._get_daily_pnl()
        summary['games_processed'] = len(completed_games)

        # Print summary
        print(f"\nGames processed: {summary['games_processed']}")
        print(f"Bets settled: {summary['bets_settled']}")
        print(f"CLV calculated: {summary['clv_calculated']}")
        print(f"Average CLV: {summary['avg_clv']:.2%}" if summary['avg_clv'] else "Average CLV: N/A")
        print(f"Daily P&L: ${summary['daily_pnl']:+,.2f}")

        return summary


def create_sample_workflow():
    """Create workflow with sample configuration."""
    from src.operations.position_tracker import PositionTracker, ExposureLimits
    from src.operations.line_shopper import LineShopper

    limits = ExposureLimits(
        max_per_game_pct=0.02,
        max_per_day_pct=0.10,
        max_single_bet_pct=0.01,  # Start conservative
        daily_loss_limit_pct=0.05
    )

    tracker = PositionTracker(
        db_path="data/positions.db",
        initial_bankroll=10000.0,
        limits=limits
    )

    shopper = LineShopper()

    workflow = DailyWorkflow(
        model=None,  # Load your trained model
        odds_client=None,  # Set up odds API
        position_tracker=tracker,
        line_shopper=shopper,
        min_edge=0.02,
        min_probability=0.52
    )

    return workflow
