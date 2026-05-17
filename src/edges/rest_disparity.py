"""Net Rest Disparity Model - Warren Sharp Framework

Implements the research-backed rest advantage model that Sharp Football Analysis
has documented as one of the most persistent NFL betting edges.

Key findings from Sharp's research:
- Teams on 7+ days rest vs opponent on 6 or fewer days: 54% ATS
- Short week favorites (TNF) after playing Monday: significant fade opportunity
- Bye week advantages diminish by Week 12+ (sample-backed)
- Cross-country travel compounds rest disadvantage

This is NOT speculation - these are documented, sample-verified edges.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class RestSituation(Enum):
    """Categorized rest situations with documented edges."""
    MASSIVE_EDGE = "massive_edge"      # 10+ day diff (bye vs short week)
    STRONG_EDGE = "strong_edge"        # 7+ days vs 6 or fewer
    MODERATE_EDGE = "moderate_edge"    # Normal week vs short week
    NEUTRAL = "neutral"                # Similar rest
    FADE = "fade"                       # Short rest favorite


@dataclass
class RestAnalysis:
    """Complete rest analysis for a game."""
    game_id: str
    home_team: str
    away_team: str
    home_rest_days: int
    away_rest_days: int
    rest_diff: int  # positive = home advantage
    situation: RestSituation
    edge_team: Optional[str]
    edge_magnitude: float  # 0-1 scale
    historical_ats: float
    travel_factor: float
    is_thursday: bool
    recommendation: str
    confidence: str


# Time zones for travel calculations
TEAM_TIMEZONES = {
    # Eastern
    'ATL': 'ET', 'BAL': 'ET', 'BUF': 'ET', 'CAR': 'ET', 'CIN': 'ET',
    'CLE': 'ET', 'DET': 'ET', 'IND': 'ET', 'JAX': 'ET', 'MIA': 'ET',
    'NE': 'ET', 'NYG': 'ET', 'NYJ': 'ET', 'PHI': 'ET', 'PIT': 'ET',
    'TB': 'ET', 'WAS': 'ET',
    # Central
    'CHI': 'CT', 'DAL': 'CT', 'GB': 'CT', 'HOU': 'CT', 'KC': 'CT',
    'MIN': 'CT', 'NO': 'CT', 'TEN': 'CT',
    # Mountain
    'ARI': 'MT', 'DEN': 'MT',
    # Pacific
    'LAC': 'PT', 'LAR': 'PT', 'LV': 'PT', 'SEA': 'PT', 'SF': 'PT',
}

# Timezone hour offsets from ET
TZ_OFFSET = {'ET': 0, 'CT': 1, 'MT': 2, 'PT': 3}


class RestDisparityAnalyzer:
    """
    Analyzes rest advantages using Warren Sharp's documented framework.

    This implements findings from Sharp Football Analysis that have
    been validated over 10+ years of NFL data.
    """

    # Historical ATS rates by rest situation (Sharp research)
    HISTORICAL_ATS = {
        RestSituation.MASSIVE_EDGE: 0.58,    # Bye + rest vs short week
        RestSituation.STRONG_EDGE: 0.54,     # Well-rested underdog
        RestSituation.MODERATE_EDGE: 0.52,   # Short week fade
        RestSituation.NEUTRAL: 0.50,
        RestSituation.FADE: 0.46,            # Short rest favorite to fade
    }

    def __init__(self):
        self.analyses: List[RestAnalysis] = []

    def analyze_game(
        self,
        game_id: str,
        home_team: str,
        away_team: str,
        home_last_game: datetime,
        away_last_game: datetime,
        game_date: datetime,
        spread: float,
        is_thursday: bool = False,
        home_was_monday: bool = False,
        away_was_monday: bool = False,
        home_had_bye: bool = False,
        away_had_bye: bool = False,
    ) -> RestAnalysis:
        """
        Analyze rest disparity for a single game.

        Args:
            game_id: Unique identifier
            home_team: Home team abbrev
            away_team: Away team abbrev
            home_last_game: Date of home team's last game
            away_last_game: Date of away team's last game
            game_date: Date of this game
            spread: Point spread (negative = home favorite)
            is_thursday: Is this a Thursday game
            home_was_monday: Did home team play Monday last week
            away_was_monday: Did away team play Monday last week
            home_had_bye: Is home team coming off bye
            away_had_bye: Is away team coming off bye

        Returns:
            RestAnalysis with edge assessment
        """
        # Calculate rest days
        home_rest = (game_date - home_last_game).days if home_last_game else 7
        away_rest = (game_date - away_last_game).days if away_last_game else 7

        # Bye weeks = 14+ days rest
        if home_had_bye:
            home_rest = max(home_rest, 14)
        if away_had_bye:
            away_rest = max(away_rest, 14)

        # Short week adjustments
        if home_was_monday and is_thursday:
            home_rest = min(home_rest, 3)  # Monday to Thursday = brutal
        if away_was_monday and is_thursday:
            away_rest = min(away_rest, 3)

        rest_diff = home_rest - away_rest

        # Calculate travel factor
        travel_factor = self._calculate_travel_factor(home_team, away_team)

        # Determine situation
        situation = self._classify_situation(
            home_rest, away_rest, rest_diff, spread, is_thursday
        )

        # Determine edge
        edge_team, edge_magnitude, recommendation, confidence = self._determine_edge(
            home_team, away_team, home_rest, away_rest,
            situation, spread, travel_factor, is_thursday
        )

        analysis = RestAnalysis(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            home_rest_days=home_rest,
            away_rest_days=away_rest,
            rest_diff=rest_diff,
            situation=situation,
            edge_team=edge_team,
            edge_magnitude=edge_magnitude,
            historical_ats=self.HISTORICAL_ATS.get(situation, 0.50),
            travel_factor=travel_factor,
            is_thursday=is_thursday,
            recommendation=recommendation,
            confidence=confidence,
        )

        self.analyses.append(analysis)
        return analysis

    def _calculate_travel_factor(self, home_team: str, away_team: str) -> float:
        """
        Calculate travel disadvantage for away team.

        Cross-country travel (3 timezone diff) = 1.0
        2 timezone diff = 0.6
        1 timezone diff = 0.3
        Same timezone = 0.0
        """
        home_tz = TEAM_TIMEZONES.get(home_team, 'ET')
        away_tz = TEAM_TIMEZONES.get(away_team, 'ET')

        tz_diff = abs(TZ_OFFSET[home_tz] - TZ_OFFSET[away_tz])

        travel_factors = {0: 0.0, 1: 0.3, 2: 0.6, 3: 1.0}
        return travel_factors.get(tz_diff, 0.0)

    def _classify_situation(
        self,
        home_rest: int,
        away_rest: int,
        rest_diff: int,
        spread: float,
        is_thursday: bool,
    ) -> RestSituation:
        """Classify the rest situation into documented categories."""

        # Massive edge: Bye week vs short week
        if (home_rest >= 14 and away_rest <= 6) or (away_rest >= 14 and home_rest <= 6):
            return RestSituation.MASSIVE_EDGE

        # Strong edge: Well-rested underdog pattern
        if abs(rest_diff) >= 3:
            # Check if the rested team is the underdog
            rested_is_home = rest_diff > 0
            home_is_underdog = spread > 0

            if rested_is_home == home_is_underdog:
                return RestSituation.STRONG_EDGE

        # Thursday game special cases
        if is_thursday:
            if min(home_rest, away_rest) <= 4:
                # Short week favorite = fade opportunity
                short_rest_is_home = home_rest < away_rest
                home_is_favorite = spread < 0

                if short_rest_is_home == home_is_favorite:
                    return RestSituation.FADE
                else:
                    return RestSituation.MODERATE_EDGE

        # Moderate edge: One team on short week
        if min(home_rest, away_rest) <= 6 and abs(rest_diff) >= 2:
            return RestSituation.MODERATE_EDGE

        return RestSituation.NEUTRAL

    def _determine_edge(
        self,
        home_team: str,
        away_team: str,
        home_rest: int,
        away_rest: int,
        situation: RestSituation,
        spread: float,
        travel_factor: float,
        is_thursday: bool,
    ) -> Tuple[Optional[str], float, str, str]:
        """
        Determine which team has the edge and magnitude.

        Returns:
            Tuple of (edge_team, magnitude, recommendation, confidence)
        """
        if situation == RestSituation.NEUTRAL:
            return None, 0.0, "No rest edge - pass", "none"

        # Determine who has rest advantage
        if home_rest > away_rest:
            rested_team = home_team
            tired_team = away_team
            rested_is_home = True
        else:
            rested_team = away_team
            tired_team = home_team
            rested_is_home = False

        # Base magnitude from rest difference
        rest_diff = abs(home_rest - away_rest)
        magnitude = min(rest_diff / 7, 1.0)  # Cap at 1.0

        # Adjust for Thursday (amplifies rest effects)
        if is_thursday:
            magnitude *= 1.3

        # Adjust for travel (compounds tired team's disadvantage)
        if not rested_is_home:  # Away team is rested, travel works against them
            magnitude *= (1 - travel_factor * 0.2)
        else:  # Home team is rested, travel compounds away team fatigue
            magnitude *= (1 + travel_factor * 0.15)

        magnitude = min(magnitude, 1.0)

        # Determine recommendation based on situation
        home_is_underdog = spread > 0

        if situation == RestSituation.FADE:
            # Fade the short-rest favorite
            edge_team = tired_team if (home_rest < away_rest) != (spread < 0) else rested_team
            recommendation = f"FADE short-rest favorite, lean {edge_team}"
            confidence = "medium"
        elif situation == RestSituation.MASSIVE_EDGE:
            edge_team = rested_team
            recommendation = f"STRONG: {rested_team} massive rest edge ({home_rest if rested_is_home else away_rest} vs {away_rest if rested_is_home else home_rest} days)"
            confidence = "high"
        elif situation == RestSituation.STRONG_EDGE:
            edge_team = rested_team
            recommendation = f"{rested_team} rest advantage ATS"
            confidence = "high" if magnitude > 0.5 else "medium"
        else:
            edge_team = rested_team
            recommendation = f"Slight lean {rested_team} on rest"
            confidence = "low"

        return edge_team, magnitude, recommendation, confidence


def analyze_week_rest(
    games_df: pd.DataFrame,
    schedule_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Analyze rest disparity for all games in a week.

    Args:
        games_df: This week's games
        schedule_df: Full schedule for previous game lookup

    Returns:
        DataFrame with rest analysis columns added
    """
    analyzer = RestDisparityAnalyzer()

    results = []

    for idx, row in games_df.iterrows():
        game_date = pd.to_datetime(row.get('gameday', datetime.now()))

        # Determine if Thursday game
        is_thursday = game_date.weekday() == 3

        # Get rest days from data or estimate
        home_rest = row.get('home_rest_days', 7)
        away_rest = row.get('away_rest_days', 7)

        # Calculate last game dates
        home_last = game_date - timedelta(days=home_rest)
        away_last = game_date - timedelta(days=away_rest)

        analysis = analyzer.analyze_game(
            game_id=row.get('game_id', f'game_{idx}'),
            home_team=row['home_team'],
            away_team=row['away_team'],
            home_last_game=home_last,
            away_last_game=away_last,
            game_date=game_date,
            spread=row.get('spread_line', 0),
            is_thursday=is_thursday,
        )

        results.append({
            'game_id': row.get('game_id', f'game_{idx}'),
            'rest_situation': analysis.situation.value,
            'rest_edge_team': analysis.edge_team,
            'rest_edge_magnitude': analysis.edge_magnitude,
            'rest_historical_ats': analysis.historical_ats,
            'rest_travel_factor': analysis.travel_factor,
            'rest_recommendation': analysis.recommendation,
            'rest_confidence': analysis.confidence,
        })

    results_df = pd.DataFrame(results)
    return games_df.merge(results_df, on='game_id', how='left')


def print_rest_analysis(analysis: RestAnalysis) -> None:
    """Print rest analysis in readable format."""
    print(f"\n{'='*60}")
    print(f"REST ANALYSIS: {analysis.away_team} @ {analysis.home_team}")
    print(f"{'='*60}")
    print(f"Home rest: {analysis.home_rest_days} days | Away rest: {analysis.away_rest_days} days")
    print(f"Difference: {analysis.rest_diff:+d} days (positive = home advantage)")
    print(f"Travel factor: {analysis.travel_factor:.1f} (0=same zone, 1=cross-country)")
    print(f"Thursday game: {'Yes' if analysis.is_thursday else 'No'}")
    print(f"\nSituation: {analysis.situation.value.upper()}")
    print(f"Historical ATS: {analysis.historical_ats:.0%}")
    print(f"Edge magnitude: {analysis.edge_magnitude:.2f}")
    print(f"\n>>> {analysis.recommendation}")
    print(f"Confidence: {analysis.confidence.upper()}")
    print(f"{'='*60}")
