"""Odds API client for real-time and historical betting lines.

Supports:
- The Odds API (theOddsAPI.com) - Most popular, good coverage
- OpticOdds (opticodds.com) - Real-time, sharp indicators

CRITICAL: Real odds data required for:
1. True CLV calculation (requires closing line)
2. Line movement analysis
3. Sharp money detection
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class OddsAPIClient:
    """
    Client for The Odds API (https://the-odds-api.com).

    Pricing (as of 2024):
    - Free: 500 requests/month
    - Starter ($79/month): 10,000 requests
    - Standard ($199/month): 50,000 requests
    - Pro ($499/month): 200,000 requests

    Features:
    - Pre-match odds from 40+ bookmakers
    - Live in-play odds
    - Historical odds (Pro plan)
    """

    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT = "americanfootball_nfl"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize client.

        Args:
            api_key: The Odds API key. If not provided, reads from
                     ODDS_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        if not self.api_key:
            logger.warning(
                "No ODDS_API_KEY found. Set environment variable or pass api_key. "
                "Get key at https://the-odds-api.com"
            )
        self.remaining_requests = None

    def get_live_odds(
        self,
        markets: List[str] = ["h2h", "spreads", "totals"],
        regions: List[str] = ["us"],
        bookmakers: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Get current odds for upcoming NFL games.

        Args:
            markets: Market types (h2h, spreads, totals)
            regions: Regions for bookmakers (us, us2, uk, eu, au)
            bookmakers: Specific bookmakers (optional)

        Returns:
            List of games with odds from multiple bookmakers
        """
        if not self.api_key:
            logger.error("API key required for live odds")
            return []

        params = {
            "apiKey": self.api_key,
            "regions": ",".join(regions),
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
        }

        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)

        try:
            response = requests.get(
                f"{self.BASE_URL}/sports/{self.SPORT}/odds",
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            # Track remaining requests
            self.remaining_requests = response.headers.get("x-requests-remaining")
            logger.info(f"Remaining API requests: {self.remaining_requests}")

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch live odds: {e}")
            return []

    def get_event_odds(
        self,
        event_id: str,
        markets: List[str] = ["h2h", "spreads", "totals"],
    ) -> Optional[Dict]:
        """
        Get odds for a specific event.

        Args:
            event_id: The Odds API event ID
            markets: Market types

        Returns:
            Event dict with odds
        """
        if not self.api_key:
            return None

        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/sports/{self.SPORT}/events/{event_id}/odds",
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch event odds: {e}")
            return None

    def get_historical_odds(
        self,
        date: datetime,
        markets: List[str] = ["h2h", "spreads"],
    ) -> List[Dict]:
        """
        Get historical odds for a specific date (Pro plan required).

        Args:
            date: Date to fetch odds for
            markets: Market types

        Returns:
            List of events with historical odds
        """
        if not self.api_key:
            return []

        date_str = date.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
            "date": date_str,
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/historical/sports/{self.SPORT}/odds",
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json().get("data", [])

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch historical odds: {e}")
            return []

    def extract_best_odds(self, event: Dict, market: str = "h2h") -> Dict:
        """
        Extract best available odds from event data.

        Args:
            event: Event dict from API
            market: Market type

        Returns:
            Dict with best odds for each outcome
        """
        best_odds = {
            "home_team": event.get("home_team"),
            "away_team": event.get("away_team"),
            "home_best_odds": 1.0,
            "home_best_book": None,
            "away_best_odds": 1.0,
            "away_best_book": None,
        }

        for bookmaker in event.get("bookmakers", []):
            for mkt in bookmaker.get("markets", []):
                if mkt.get("key") != market:
                    continue

                for outcome in mkt.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price", 1.0)

                    if name == event.get("home_team"):
                        if price > best_odds["home_best_odds"]:
                            best_odds["home_best_odds"] = price
                            best_odds["home_best_book"] = bookmaker.get("key")

                    elif name == event.get("away_team"):
                        if price > best_odds["away_best_odds"]:
                            best_odds["away_best_odds"] = price
                            best_odds["away_best_book"] = bookmaker.get("key")

        return best_odds

    def get_line_movement(
        self,
        event_id: str,
        hours: int = 24,
    ) -> List[Dict]:
        """
        Get line movement over time (requires storing historical fetches).

        Note: The Odds API doesn't provide native line movement.
        This method returns empty - implement by storing periodic fetches.

        Args:
            event_id: Event ID
            hours: Hours of history

        Returns:
            List of timestamped odds snapshots
        """
        logger.warning(
            "Line movement requires storing periodic odds fetches. "
            "Implement a scheduled job to store odds snapshots."
        )
        return []


class OpticOddsClient:
    """
    Client for OpticOdds API (https://opticodds.com).

    Features (Enterprise):
    - Sub-second real-time odds
    - Historical odds database
    - Sharp money indicators
    - Line movement analysis

    Contact for pricing: enterprise@opticodds.com
    """

    BASE_URL = "https://api.opticodds.com"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize client.

        Args:
            api_key: OpticOdds API key
        """
        self.api_key = api_key or os.environ.get("OPTIC_ODDS_API_KEY")
        if not self.api_key:
            logger.warning(
                "No OPTIC_ODDS_API_KEY found. OpticOdds requires enterprise access. "
                "Contact enterprise@opticodds.com"
            )

    def get_live_odds(self, league: str = "NFL") -> List[Dict]:
        """Get real-time odds (placeholder for enterprise integration)."""
        logger.warning("OpticOdds requires enterprise access")
        return []

    def get_sharp_indicators(self, event_id: str) -> Optional[Dict]:
        """Get sharp money indicators (placeholder for enterprise integration)."""
        logger.warning("Sharp indicators require OpticOdds enterprise access")
        return None


def calculate_clv(
    bet_odds: float,
    closing_odds: float,
) -> float:
    """
    Calculate Closing Line Value.

    CLV = (bet_odds / closing_odds) - 1

    Positive CLV = beat the closing line = real edge

    Args:
        bet_odds: Odds at time of bet (decimal)
        closing_odds: Final odds at game start (decimal)

    Returns:
        CLV as decimal (e.g., 0.02 = 2% CLV)
    """
    if closing_odds <= 0:
        return 0.0

    return (bet_odds / closing_odds) - 1


def calculate_no_vig_probability(
    home_odds: float,
    away_odds: float,
) -> tuple:
    """
    Calculate no-vig (fair) probabilities from decimal odds.

    Args:
        home_odds: Decimal odds for home team
        away_odds: Decimal odds for away team

    Returns:
        (home_fair_prob, away_fair_prob)
    """
    # Convert to implied probabilities
    home_implied = 1 / home_odds
    away_implied = 1 / away_odds

    # Total overround (vig)
    total = home_implied + away_implied

    # Remove vig proportionally
    home_fair = home_implied / total
    away_fair = away_implied / total

    return home_fair, away_fair


def detect_line_value(
    model_prob: float,
    market_odds: float,
    min_edge: float = 0.02,
) -> Dict[str, Any]:
    """
    Detect if model probability implies value vs market odds.

    Args:
        model_prob: Model's probability estimate
        market_odds: Current decimal odds from market
        min_edge: Minimum edge to consider valuable

    Returns:
        Dict with value analysis
    """
    # Market implied probability
    market_implied = 1 / market_odds

    # Edge = model_prob - market_implied
    edge = model_prob - market_implied

    # Expected value
    ev = (model_prob * market_odds) - 1

    return {
        "model_probability": model_prob,
        "market_implied": market_implied,
        "edge": edge,
        "edge_pct": edge * 100,
        "expected_value": ev,
        "ev_pct": ev * 100,
        "has_value": edge >= min_edge,
        "bet_recommendation": "BET" if edge >= min_edge else "NO BET",
    }
