"""Dynamic Edge Detection - Hidden Insights from 2023-2025

Implements AI detection mechanisms for non-obvious patterns:
1. RB receiving volume explosions (CMC-type archetypes)
2. Game-script & red-zone regression detection
3. Rest × usage interactions
4. Second-tier player undervaluation
5. Defensive scheme shift detection

Key methods:
- Rolling window features (3-5 games vs baseline)
- Interaction terms
- Regime/change-point detection
- Anomaly & line movement detection

These turn "hidden" historical patterns into systematic, adaptive edges.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class UsageSpike:
    """Detected usage spike for a player."""
    player: str
    team: str
    position: str
    metric: str  # target_share, snap_pct, red_zone_looks
    recent_value: float  # Last 3-5 games
    baseline_value: float  # Season or career
    spike_pct: float  # How much above baseline
    trigger_reason: str  # e.g., "WR1 injured"
    confidence: str
    prop_implication: str


@dataclass
class RegimeShift:
    """Detected regime change (correlation breaking down)."""
    correlation_type: str  # e.g., "RB1 TD + Game Total"
    previous_rate: float  # Historical hit rate
    recent_rate: float  # Last 4-6 weeks
    change_magnitude: float
    likely_cause: str
    recommendation: str


@dataclass
class HiddenEdge:
    """A detected hidden edge opportunity."""
    edge_type: str
    player: str
    team: str
    prop_type: str
    direction: str  # over/under
    edge_magnitude: float
    detection_method: str
    supporting_data: Dict
    confidence: str
    expiration_risk: str  # How likely this fades


class DynamicEdgeDetector:
    """
    Detects hidden patterns that public bettors miss.

    Key insights from 2023-2025:
    - RB receiving spikes when WRs injured
    - Anytime TD correlations regress mid-season
    - Rest edges boost skill player props
    - Second-tier players systematically underpriced
    - Defensive scheme shifts create predictable patterns
    """

    # Thresholds for spike detection
    SPIKE_THRESHOLDS = {
        'target_share': 0.20,  # 20% above baseline = spike
        'snap_pct': 0.10,
        'red_zone_looks': 0.30,
        'air_yards_share': 0.25,
    }

    # Second-tier player value indicators
    SECOND_TIER_VALUE_SIGNALS = {
        'slot_wr_vs_weak_nickel': 0.08,  # +8% edge
        'change_of_pace_rb_positive_script': 0.06,
        'te_vs_lb_coverage': 0.07,
        'backup_rb_with_starter_limited': 0.10,
    }

    def __init__(self):
        self.detected_spikes: List[UsageSpike] = []
        self.detected_shifts: List[RegimeShift] = []
        self.hidden_edges: List[HiddenEdge] = []

    def detect_usage_spike(
        self,
        player: str,
        team: str,
        position: str,
        recent_games: List[Dict],  # Last 3-5 games
        season_baseline: Dict,
        injury_context: Optional[Dict] = None,
    ) -> Optional[UsageSpike]:
        """
        Detect if a player has a usage spike worth exploiting.

        CMC example: Target share jumped to 25-29% when Aiyuk/Kittle out.
        """
        if len(recent_games) < 3:
            return None

        # Calculate recent averages
        recent_target_share = np.mean([g.get('target_share', 0) for g in recent_games])
        recent_snap_pct = np.mean([g.get('snap_pct', 0) for g in recent_games])
        recent_rz_looks = np.mean([g.get('red_zone_looks', 0) for g in recent_games])

        # Compare to baseline
        baseline_target = season_baseline.get('target_share', 0.15)
        baseline_snap = season_baseline.get('snap_pct', 0.70)
        baseline_rz = season_baseline.get('red_zone_looks', 2.0)

        # Check for spikes
        spikes_detected = []

        if baseline_target > 0:
            target_spike = (recent_target_share - baseline_target) / baseline_target
            if target_spike > self.SPIKE_THRESHOLDS['target_share']:
                spikes_detected.append(('target_share', recent_target_share, baseline_target, target_spike))

        if baseline_snap > 0:
            snap_spike = (recent_snap_pct - baseline_snap) / baseline_snap
            if snap_spike > self.SPIKE_THRESHOLDS['snap_pct']:
                spikes_detected.append(('snap_pct', recent_snap_pct, baseline_snap, snap_spike))

        if baseline_rz > 0:
            rz_spike = (recent_rz_looks - baseline_rz) / baseline_rz
            if rz_spike > self.SPIKE_THRESHOLDS['red_zone_looks']:
                spikes_detected.append(('red_zone_looks', recent_rz_looks, baseline_rz, rz_spike))

        if not spikes_detected:
            return None

        # Get the biggest spike
        best_spike = max(spikes_detected, key=lambda x: x[3])
        metric, recent_val, baseline_val, spike_pct = best_spike

        # Determine trigger reason
        trigger_reason = "Usage increase detected"
        if injury_context:
            injured_players = injury_context.get('injured_teammates', [])
            if injured_players:
                trigger_reason = f"Teammates out: {', '.join(injured_players)}"

        # Confidence based on spike magnitude and consistency
        if spike_pct > 0.30 and len([g for g in recent_games if g.get(metric, 0) > baseline_val]) >= 4:
            confidence = 'high'
        elif spike_pct > 0.20:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Prop implication
        if position == 'RB' and metric == 'target_share':
            prop_implication = "RB receiving props (receptions, rec yards) likely underpriced"
        elif metric == 'red_zone_looks':
            prop_implication = "Anytime TD and rushing TD props have value"
        else:
            prop_implication = f"{metric.replace('_', ' ').title()} suggests overs"

        spike = UsageSpike(
            player=player,
            team=team,
            position=position,
            metric=metric,
            recent_value=recent_val,
            baseline_value=baseline_val,
            spike_pct=spike_pct,
            trigger_reason=trigger_reason,
            confidence=confidence,
            prop_implication=prop_implication,
        )

        self.detected_spikes.append(spike)
        return spike

    def detect_regime_shift(
        self,
        correlation_type: str,
        historical_results: List[bool],  # Full history
        recent_results: List[bool],  # Last 4-6 weeks
        context: Optional[str] = None,
    ) -> Optional[RegimeShift]:
        """
        Detect if a previously strong correlation is breaking down.

        Example: CMC + Henry ATTD stack worked early 2023, regressed by late 2024.
        """
        if len(historical_results) < 15 or len(recent_results) < 4:
            return None

        historical_rate = sum(historical_results) / len(historical_results)
        recent_rate = sum(recent_results) / len(recent_results)

        change = recent_rate - historical_rate

        # Significant negative shift = regression
        if change < -0.10:  # 10%+ drop
            likely_cause = context or "Defensive adjustments or usage changes"

            if change < -0.20:
                recommendation = "🚫 AVOID: This correlation has broken down"
            else:
                recommendation = "⚠️ CAUTION: Regression detected, reduce exposure"

            shift = RegimeShift(
                correlation_type=correlation_type,
                previous_rate=historical_rate,
                recent_rate=recent_rate,
                change_magnitude=change,
                likely_cause=likely_cause,
                recommendation=recommendation,
            )

            self.detected_shifts.append(shift)
            return shift

        return None

    def detect_rest_usage_edge(
        self,
        player: str,
        team: str,
        position: str,
        rest_days: int,
        opponent_rest_days: int,
        player_usage_rate: float,  # Snap % or target share
    ) -> Optional[HiddenEdge]:
        """
        Detect rest × usage interaction edge.

        Insight: Rested teams see disproportionate overperformance on
        skill-player props, especially RBs and slot WRs.
        """
        rest_advantage = rest_days - opponent_rest_days

        # Need rest advantage AND high usage
        if rest_advantage < 2:
            return None

        if player_usage_rate < 0.60:  # Not a featured player
            return None

        # Calculate edge magnitude
        base_edge = 0.03  # 3% base for rest advantage
        usage_multiplier = 1 + (player_usage_rate - 0.60) * 0.5  # Higher usage = bigger edge
        rest_multiplier = 1 + (rest_advantage - 2) * 0.15  # More rest = bigger edge

        edge_magnitude = base_edge * usage_multiplier * rest_multiplier

        if edge_magnitude < 0.03:
            return None

        edge = HiddenEdge(
            edge_type='rest_usage_interaction',
            player=player,
            team=team,
            prop_type='yards',  # Applies to rushing/receiving yards
            direction='over',
            edge_magnitude=edge_magnitude,
            detection_method='Rest × Usage Interaction Model',
            supporting_data={
                'rest_days': rest_days,
                'opponent_rest': opponent_rest_days,
                'rest_advantage': rest_advantage,
                'usage_rate': player_usage_rate,
            },
            confidence='medium' if edge_magnitude > 0.05 else 'low',
            expiration_risk='low',  # Rest edges are structural
        )

        self.hidden_edges.append(edge)
        return edge

    def detect_second_tier_value(
        self,
        player: str,
        team: str,
        role: str,  # 'slot_wr', 'te', 'rb2', etc.
        opponent_weakness: str,  # 'nickel', 'lb_coverage', etc.
        projected_script: str,  # 'positive', 'negative', 'neutral'
        current_line_vs_projection: float,  # How much line is off
    ) -> Optional[HiddenEdge]:
        """
        Detect undervaluation in second-tier players.

        Insight: Market shading on stars creates value in less-hyped roles.
        Slot WRs vs weak nickel, backup RBs in positive scripts, etc.
        """
        # Check for known value patterns
        value_key = None

        if role == 'slot_wr' and opponent_weakness == 'nickel':
            value_key = 'slot_wr_vs_weak_nickel'
        elif role == 'rb2' and projected_script == 'positive':
            value_key = 'change_of_pace_rb_positive_script'
        elif role == 'te' and opponent_weakness == 'lb_coverage':
            value_key = 'te_vs_lb_coverage'
        elif role == 'rb2' and 'starter_limited' in opponent_weakness:
            value_key = 'backup_rb_with_starter_limited'

        if not value_key:
            return None

        base_edge = self.SECOND_TIER_VALUE_SIGNALS.get(value_key, 0)

        # Add line discrepancy edge
        total_edge = base_edge + max(0, current_line_vs_projection * 0.5)

        if total_edge < 0.04:
            return None

        edge = HiddenEdge(
            edge_type='second_tier_undervaluation',
            player=player,
            team=team,
            prop_type='receiving_yards' if 'wr' in role or role == 'te' else 'rushing_yards',
            direction='over',
            edge_magnitude=total_edge,
            detection_method='Second-Tier Value Detection',
            supporting_data={
                'role': role,
                'opponent_weakness': opponent_weakness,
                'script': projected_script,
                'value_pattern': value_key,
            },
            confidence='medium',
            expiration_risk='medium',  # Can fade as market adjusts
        )

        self.hidden_edges.append(edge)
        return edge

    def detect_defensive_scheme_edge(
        self,
        player: str,
        team: str,
        position: str,
        opponent: str,
        opponent_scheme: str,  # 'zone_heavy', 'man_heavy', 'blitz_heavy'
        player_metrics: Dict,  # YPC vs stacked box, YAC, etc.
    ) -> Optional[HiddenEdge]:
        """
        Detect edges from defensive scheme mismatches.

        Insight: Zone-heavy defenses create predictable patterns.
        RBs vs stacked boxes, slot WRs vs man coverage have
        efficiency metrics visible before lines adjust.
        """
        edge_magnitude = 0.0
        detection_details = []

        if position == 'RB':
            # RBs struggle vs stacked boxes
            ypc_vs_8plus = player_metrics.get('ypc_vs_8plus_defenders', 3.5)
            if opponent_scheme == 'blitz_heavy' and ypc_vs_8plus < 3.0:
                edge_magnitude = -0.06  # Negative edge, fade
                detection_details.append(f"Low YPC ({ypc_vs_8plus}) vs stacked boxes")
            elif opponent_scheme == 'zone_heavy' and ypc_vs_8plus > 4.5:
                edge_magnitude = 0.05
                detection_details.append(f"Strong YPC ({ypc_vs_8plus}) exploits zone")

        elif position in ['WR', 'SLOT']:
            yac_per_target = player_metrics.get('yac_per_target', 4.0)
            if opponent_scheme == 'zone_heavy' and yac_per_target > 5.0:
                edge_magnitude = 0.06
                detection_details.append(f"High YAC ({yac_per_target}) vs zone")
            elif opponent_scheme == 'man_heavy' and player_metrics.get('separation_rate', 0.5) > 0.6:
                edge_magnitude = 0.05
                detection_details.append("Elite separation vs man coverage")

        if abs(edge_magnitude) < 0.04:
            return None

        direction = 'over' if edge_magnitude > 0 else 'under'

        edge = HiddenEdge(
            edge_type='defensive_scheme_mismatch',
            player=player,
            team=team,
            prop_type='yards',
            direction=direction,
            edge_magnitude=abs(edge_magnitude),
            detection_method='Defensive Scheme Analysis',
            supporting_data={
                'opponent': opponent,
                'scheme': opponent_scheme,
                'metrics': player_metrics,
                'details': detection_details,
            },
            confidence='medium',
            expiration_risk='low',  # Scheme-based, relatively stable
        )

        self.hidden_edges.append(edge)
        return edge

    def get_all_edges(self) -> List[HiddenEdge]:
        """Get all detected hidden edges, sorted by magnitude."""
        return sorted(self.hidden_edges, key=lambda e: e.edge_magnitude, reverse=True)

    def print_detection_report(self):
        """Print comprehensive detection report."""
        print("\n" + "=" * 70)
        print("🔍 HIDDEN EDGE DETECTION REPORT")
        print("=" * 70)

        # Usage spikes
        if self.detected_spikes:
            print("\n📈 USAGE SPIKES DETECTED")
            print("-" * 50)
            for spike in self.detected_spikes:
                print(f"""
🚀 {spike.player} ({spike.team}) - {spike.position}
   Metric: {spike.metric.replace('_', ' ').title()}
   Recent: {spike.recent_value:.1%} vs Baseline: {spike.baseline_value:.1%}
   Spike: +{spike.spike_pct:.0%}
   Trigger: {spike.trigger_reason}
   >>> {spike.prop_implication}
   Confidence: {spike.confidence.upper()}
""")

        # Regime shifts
        if self.detected_shifts:
            print("\n⚠️ REGIME SHIFTS (Correlations Breaking Down)")
            print("-" * 50)
            for shift in self.detected_shifts:
                print(f"""
📉 {shift.correlation_type}
   Historical: {shift.previous_rate:.0%} → Recent: {shift.recent_rate:.0%}
   Change: {shift.change_magnitude:+.0%}
   Cause: {shift.likely_cause}
   >>> {shift.recommendation}
""")

        # Hidden edges
        if self.hidden_edges:
            print("\n💎 HIDDEN EDGES DETECTED")
            print("-" * 50)
            for edge in self.get_all_edges()[:10]:
                print(f"""
✨ {edge.player} ({edge.team})
   Type: {edge.edge_type.replace('_', ' ').title()}
   Prop: {edge.prop_type} {edge.direction.upper()}
   Edge: {edge.edge_magnitude:.1%}
   Method: {edge.detection_method}
   Confidence: {edge.confidence.upper()}
   Fade Risk: {edge.expiration_risk}
""")

        if not (self.detected_spikes or self.detected_shifts or self.hidden_edges):
            print("\nNo hidden edges detected in current data.")

        print("=" * 70)


def create_rolling_features(
    player_games: pd.DataFrame,
    windows: List[int] = [3, 5, 10],
) -> pd.DataFrame:
    """
    Create rolling window features for dynamic detection.

    Compares recent performance to baseline to detect spikes.
    """
    df = player_games.copy()

    metrics = ['targets', 'receptions', 'receiving_yards', 'rushing_yards',
               'snap_pct', 'target_share', 'red_zone_looks']

    for metric in metrics:
        if metric not in df.columns:
            continue

        for window in windows:
            # Rolling average
            df[f'{metric}_roll_{window}'] = df[metric].rolling(window, min_periods=1).mean()

            # Season average for comparison
            df[f'{metric}_season_avg'] = df[metric].expanding().mean()

            # Spike detection: rolling vs season
            df[f'{metric}_spike_{window}'] = (
                (df[f'{metric}_roll_{window}'] - df[f'{metric}_season_avg'])
                / df[f'{metric}_season_avg'].replace(0, 1)
            )

    return df


def detect_weekly_edges(
    games_df: pd.DataFrame,
    player_data: Dict[str, pd.DataFrame],  # player -> game log
) -> List[HiddenEdge]:
    """
    Run full edge detection for a week's games.

    Returns list of hidden edges found.
    """
    detector = DynamicEdgeDetector()

    for _, game in games_df.iterrows():
        home_team = game['home_team']
        away_team = game['away_team']

        # Check rest edges
        home_rest = game.get('home_rest_days', 7)
        away_rest = game.get('away_rest_days', 7)

        # Would iterate through players on each team
        # and run detection methods...

    return detector.get_all_edges()
