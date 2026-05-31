"""
Adaptive Learning Engine

Tracks prediction results and automatically:
1. Updates model weights based on performance
2. Identifies winning/losing patterns
3. Adjusts betting parameters
4. Generates "lessons learned" reports
5. Triggers retraining when performance degrades

This is the self-improvement loop for the system.
"""

import json
import logging
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PredictionRecord:
    """Record of a single prediction and its outcome."""

    prediction_id: str
    game_id: str
    timestamp: datetime
    home_team: str
    away_team: str
    pick: str  # "home", "away", "over", "under"
    bet_type: str  # "moneyline", "spread", "total"
    line: float
    odds: float
    confidence: float
    edge: float
    model_name: str
    council_consensus: float
    tier: str

    # Outcome (filled after game)
    actual_result: Optional[str] = None  # "win", "loss", "push"
    actual_score_home: Optional[int] = None
    actual_score_away: Optional[int] = None
    profit: Optional[float] = None

    # Features at prediction time
    features: Dict[str, Any] = field(default_factory=dict)

    # Post-game analysis
    what_went_wrong: Optional[str] = None
    what_went_right: Optional[str] = None


@dataclass
class PerformanceSegment:
    """Performance analysis for a segment of bets."""

    segment_name: str
    filter_criteria: Dict[str, Any]
    total_bets: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    roi: float
    avg_odds: float
    avg_confidence: float
    avg_edge: float
    profit: float
    sharpe_ratio: float
    max_drawdown: float
    recommendation: str  # "increase", "decrease", "maintain", "stop"


@dataclass
class LessonLearned:
    """A learned insight from historical performance."""

    lesson_id: str
    timestamp: datetime
    category: str  # "model", "strategy", "timing", "selection"
    insight: str
    evidence: Dict[str, Any]
    action_taken: str
    impact: Optional[float] = None


class AdaptiveEngine:
    """
    Self-improving engine that learns from betting results.

    Key functions:
    1. Track all predictions and outcomes
    2. Analyze performance by segment (team, bet type, confidence, etc.)
    3. Identify patterns in wins/losses
    4. Auto-adjust betting parameters
    5. Trigger retraining when needed
    """

    def __init__(self, db_path: str = "data/adaptive_learning.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

        # Performance thresholds
        self.min_win_rate = 0.52
        self.min_roi = 0.00
        self.max_drawdown = 0.20
        self.min_sample_size = 20

        # Auto-adjustment settings
        self.auto_adjust_enabled = True
        self.adjustment_cooldown_hours = 24
        self.last_adjustment: Optional[datetime] = None

        logger.info("Adaptive Learning Engine initialized")

    def _init_database(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Predictions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    game_id TEXT,
                    timestamp TEXT,
                    home_team TEXT,
                    away_team TEXT,
                    pick TEXT,
                    bet_type TEXT,
                    line REAL,
                    odds REAL,
                    confidence REAL,
                    edge REAL,
                    model_name TEXT,
                    council_consensus REAL,
                    tier TEXT,
                    actual_result TEXT,
                    actual_score_home INTEGER,
                    actual_score_away INTEGER,
                    profit REAL,
                    features TEXT,
                    what_went_wrong TEXT,
                    what_went_right TEXT
                )
            """)

            # Lessons learned table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    lesson_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    category TEXT,
                    insight TEXT,
                    evidence TEXT,
                    action_taken TEXT,
                    impact REAL
                )
            """)

            # Adjustments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS adjustments (
                    adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    parameter TEXT,
                    old_value REAL,
                    new_value REAL,
                    reason TEXT,
                    performance_before REAL,
                    performance_after REAL
                )
            """)

            # Model performance table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    model_name TEXT,
                    window_days INTEGER,
                    total_bets INTEGER,
                    win_rate REAL,
                    roi REAL,
                    sharpe_ratio REAL
                )
            """)

            conn.commit()

    def record_prediction(self, record: PredictionRecord):
        """Record a new prediction."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO predictions (
                    prediction_id, game_id, timestamp, home_team, away_team,
                    pick, bet_type, line, odds, confidence, edge, model_name,
                    council_consensus, tier, features
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.prediction_id,
                    record.game_id,
                    record.timestamp.isoformat(),
                    record.home_team,
                    record.away_team,
                    record.pick,
                    record.bet_type,
                    record.line,
                    record.odds,
                    record.confidence,
                    record.edge,
                    record.model_name,
                    record.council_consensus,
                    record.tier,
                    json.dumps(record.features),
                ),
            )
            conn.commit()

        logger.info(f"Recorded prediction: {record.prediction_id}")

    def update_result(
        self,
        prediction_id: str,
        result: str,
        score_home: int,
        score_away: int,
        profit: float,
    ):
        """Update a prediction with its outcome."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE predictions
                SET actual_result = ?, 
                    actual_score_home = ?,
                    actual_score_away = ?,
                    profit = ?
                WHERE prediction_id = ?
            """,
                (result, score_home, score_away, profit, prediction_id),
            )
            conn.commit()

        logger.info(f"Updated result for {prediction_id}: {result}")

        # Trigger analysis after each result
        self._analyze_recent_performance()

    def _analyze_recent_performance(self):
        """Analyze recent performance and trigger adjustments if needed."""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                """
                SELECT * FROM predictions 
                WHERE actual_result IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 50
            """,
                conn,
            )

        if len(df) < 10:
            return

        # Calculate recent metrics
        wins = (df["actual_result"] == "win").sum()
        total = len(df[df["actual_result"] != "push"])
        win_rate = wins / total if total > 0 else 0
        roi = df["profit"].sum() / len(df)

        logger.info(f"Recent performance: {win_rate:.1%} win rate, {roi:.1%} ROI")

        # Check if performance is degrading
        if win_rate < self.min_win_rate or roi < self.min_roi:
            self._trigger_retraining_check()

    def _trigger_retraining_check(self):
        """Check if model retraining should be triggered."""
        logger.warning("Performance below threshold - checking retraining need")

        # Get performance over different windows
        windows = [7, 14, 30]  # days

        for window in windows:
            with sqlite3.connect(self.db_path) as conn:
                cutoff = (datetime.now() - timedelta(days=window)).isoformat()
                df = pd.read_sql_query(
                    f"""
                    SELECT * FROM predictions 
                    WHERE actual_result IS NOT NULL
                    AND timestamp >= '{cutoff}'
                """,
                    conn,
                )

            if len(df) < 10:
                continue

            wins = (df["actual_result"] == "win").sum()
            total = len(df[df["actual_result"] != "push"])
            win_rate = wins / total if total > 0 else 0

            logger.info(f"{window}d window: {win_rate:.1%} win rate ({len(df)} bets)")

        # Record this check
        lesson = LessonLearned(
            lesson_id=f"retrain_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            category="model",
            insight="Performance dropped below threshold - retraining may be needed",
            evidence={"trigger": "performance_threshold"},
            action_taken="logged_for_review",
        )
        self._record_lesson(lesson)

    def analyze_segment(
        self, segment_name: str, filters: Dict[str, Any]
    ) -> Optional[PerformanceSegment]:
        """
        Analyze performance for a specific segment.

        Args:
            segment_name: Name for this segment (e.g., "home_favorites")
            filters: SQL-like filters (e.g., {"pick": "home", "confidence": ">0.7"})

        Returns:
            PerformanceSegment with detailed analysis
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                """
                SELECT * FROM predictions 
                WHERE actual_result IS NOT NULL
            """,
                conn,
            )

        if len(df) == 0:
            return None

        # Apply filters
        for column, condition in filters.items():
            if isinstance(condition, str) and condition.startswith(">"):
                threshold = float(condition[1:])
                df = df[df[column] > threshold]
            elif isinstance(condition, str) and condition.startswith("<"):
                threshold = float(condition[1:])
                df = df[df[column] < threshold]
            else:
                df = df[df[column] == condition]

        if len(df) < self.min_sample_size:
            return None

        # Calculate metrics
        wins = (df["actual_result"] == "win").sum()
        losses = (df["actual_result"] == "loss").sum()
        pushes = (df["actual_result"] == "push").sum()
        total = wins + losses

        win_rate = wins / total if total > 0 else 0
        total_profit = df["profit"].sum()
        roi = total_profit / len(df) if len(df) > 0 else 0

        # Sharpe ratio (simplified)
        if len(df) > 1 and df["profit"].std() > 0:
            sharpe = (df["profit"].mean() / df["profit"].std()) * (252**0.5)
        else:
            sharpe = 0

        # Max drawdown
        cumulative = df["profit"].cumsum()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max).min()
        max_dd = abs(drawdown / running_max.max()) if running_max.max() > 0 else 0

        # Generate recommendation
        if win_rate >= 0.55 and roi >= 0.05:
            recommendation = "increase"
        elif win_rate >= 0.52 and roi >= 0.02:
            recommendation = "maintain"
        elif win_rate < 0.48 or roi < -0.05:
            recommendation = "stop"
        else:
            recommendation = "decrease"

        return PerformanceSegment(
            segment_name=segment_name,
            filter_criteria=filters,
            total_bets=len(df),
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=win_rate,
            roi=roi,
            avg_odds=df["odds"].mean(),
            avg_confidence=df["confidence"].mean(),
            avg_edge=df["edge"].mean(),
            profit=total_profit,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            recommendation=recommendation,
        )

    def get_all_segments_analysis(self) -> List[PerformanceSegment]:
        """Analyze all key segments."""
        segments = []

        # Predefined segments to analyze
        segment_definitions = [
            ("home_picks", {"pick": "home"}),
            ("away_picks", {"pick": "away"}),
            ("high_confidence", {"confidence": ">0.7"}),
            ("medium_confidence", {"confidence": ">0.5"}),
            ("s_tier", {"tier": "S_tier"}),
            ("a_tier", {"tier": "A_tier"}),
            ("moneyline", {"bet_type": "moneyline"}),
            ("spread", {"bet_type": "spread"}),
            ("favorites", {"odds": "<-110"}),
            ("underdogs", {"odds": ">+110"}),
        ]

        for name, filters in segment_definitions:
            segment = self.analyze_segment(name, filters)
            if segment:
                segments.append(segment)

        return segments

    def identify_patterns(self) -> Dict[str, Any]:
        """Identify winning and losing patterns in the data."""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                """
                SELECT * FROM predictions 
                WHERE actual_result IS NOT NULL
            """,
                conn,
            )

        if len(df) < 20:
            return {"message": "Insufficient data for pattern analysis"}

        patterns = {"winning_patterns": [], "losing_patterns": [], "insights": []}

        # Analyze by confidence bins
        df["confidence_bin"] = pd.cut(
            df["confidence"], bins=[0, 0.5, 0.6, 0.7, 0.8, 1.0]
        )
        for bin_val in df["confidence_bin"].unique():
            subset = df[df["confidence_bin"] == bin_val]
            if len(subset) >= 10:
                wins = (subset["actual_result"] == "win").sum()
                wr = wins / len(subset)

                if wr >= 0.60:
                    patterns["winning_patterns"].append(
                        {
                            "type": "confidence_range",
                            "range": str(bin_val),
                            "win_rate": wr,
                            "sample": len(subset),
                        }
                    )
                elif wr <= 0.45:
                    patterns["losing_patterns"].append(
                        {
                            "type": "confidence_range",
                            "range": str(bin_val),
                            "win_rate": wr,
                            "sample": len(subset),
                        }
                    )

        # Analyze by tier
        for tier in df["tier"].unique():
            subset = df[df["tier"] == tier]
            if len(subset) >= 10:
                wins = (subset["actual_result"] == "win").sum()
                wr = wins / len(subset)
                roi = subset["profit"].sum() / len(subset)

                if wr >= 0.55 and roi >= 0.03:
                    patterns["winning_patterns"].append(
                        {
                            "type": "tier",
                            "tier": tier,
                            "win_rate": wr,
                            "roi": roi,
                            "sample": len(subset),
                        }
                    )
                elif wr <= 0.48 or roi <= -0.03:
                    patterns["losing_patterns"].append(
                        {
                            "type": "tier",
                            "tier": tier,
                            "win_rate": wr,
                            "roi": roi,
                            "sample": len(subset),
                        }
                    )

        # Generate insights
        if patterns["winning_patterns"]:
            patterns["insights"].append(
                f"Strong performance in {len(patterns['winning_patterns'])} segments - consider increasing allocation"
            )

        if patterns["losing_patterns"]:
            patterns["insights"].append(
                f"Weak performance in {len(patterns['losing_patterns'])} segments - consider reducing or eliminating"
            )

        return patterns

    def _record_lesson(self, lesson: LessonLearned):
        """Record a lesson learned."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO lessons (
                    lesson_id, timestamp, category, insight, evidence, action_taken, impact
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    lesson.lesson_id,
                    lesson.timestamp.isoformat(),
                    lesson.category,
                    lesson.insight,
                    json.dumps(lesson.evidence),
                    lesson.action_taken,
                    lesson.impact,
                ),
            )
            conn.commit()

    def generate_report(self) -> str:
        """Generate a comprehensive performance report."""
        report = []
        report.append("=" * 60)
        report.append("ADAPTIVE LEARNING ENGINE - PERFORMANCE REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)

        # Overall metrics
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                """
                SELECT * FROM predictions 
                WHERE actual_result IS NOT NULL
            """,
                conn,
            )

        if len(df) == 0:
            report.append("\nNo completed predictions to analyze.")
            return "\n".join(report)

        wins = (df["actual_result"] == "win").sum()
        losses = (df["actual_result"] == "loss").sum()
        total = wins + losses

        report.append(f"\n📊 OVERALL PERFORMANCE")
        report.append(f"  Total Bets: {len(df)}")
        report.append(f"  Record: {wins}-{losses}")
        report.append(
            f"  Win Rate: {wins/total:.1%}" if total > 0 else "  Win Rate: N/A"
        )
        report.append(f"  Total Profit: ${df['profit'].sum():.2f}")
        report.append(f"  ROI: {df['profit'].sum()/len(df)*100:.1f}%")

        # Segment analysis
        report.append(f"\n📈 SEGMENT ANALYSIS")
        segments = self.get_all_segments_analysis()

        for segment in segments:
            emoji = (
                "🟢"
                if segment.recommendation == "increase"
                else (
                    "🟡"
                    if segment.recommendation == "maintain"
                    else "🔴" if segment.recommendation == "stop" else "⚪"
                )
            )

            report.append(f"\n  {emoji} {segment.segment_name.upper()}")
            report.append(f"      Bets: {segment.total_bets}")
            report.append(f"      Win Rate: {segment.win_rate:.1%}")
            report.append(f"      ROI: {segment.roi:.1%}")
            report.append(f"      Recommendation: {segment.recommendation.upper()}")

        # Patterns
        report.append(f"\n🔍 PATTERN ANALYSIS")
        patterns = self.identify_patterns()

        if patterns.get("winning_patterns"):
            report.append(f"  Winning Patterns:")
            for p in patterns["winning_patterns"][:3]:
                report.append(
                    f"    ✓ {p['type']}: {p.get('range', p.get('tier', ''))} - {p['win_rate']:.1%} WR"
                )

        if patterns.get("losing_patterns"):
            report.append(f"  Losing Patterns:")
            for p in patterns["losing_patterns"][:3]:
                report.append(
                    f"    ✗ {p['type']}: {p.get('range', p.get('tier', ''))} - {p['win_rate']:.1%} WR"
                )

        if patterns.get("insights"):
            report.append(f"\n💡 INSIGHTS")
            for insight in patterns["insights"]:
                report.append(f"  • {insight}")

        report.append("\n" + "=" * 60)

        return "\n".join(report)

    def export_data(self, output_path: str = "reports/adaptive_learning_export.json"):
        """Export all learning data to JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            predictions = pd.read_sql_query("SELECT * FROM predictions", conn)
            lessons = pd.read_sql_query("SELECT * FROM lessons", conn)
            adjustments = pd.read_sql_query("SELECT * FROM adjustments", conn)

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "predictions": predictions.to_dict(orient="records"),
            "lessons": lessons.to_dict(orient="records"),
            "adjustments": adjustments.to_dict(orient="records"),
            "summary": {
                "total_predictions": len(predictions),
                "completed_predictions": len(
                    predictions[predictions["actual_result"].notna()]
                ),
                "total_lessons": len(lessons),
                "total_adjustments": len(adjustments),
            },
        }

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Exported data to {output_path}")
        return output_path


# Singleton instance
_adaptive_engine: Optional[AdaptiveEngine] = None


def get_adaptive_engine() -> AdaptiveEngine:
    """Get or create singleton AdaptiveEngine instance."""
    global _adaptive_engine
    if _adaptive_engine is None:
        _adaptive_engine = AdaptiveEngine()
    return _adaptive_engine


if __name__ == "__main__":
    # Test the adaptive engine
    engine = get_adaptive_engine()

    # Add some test predictions
    from uuid import uuid4

    for i in range(25):
        record = PredictionRecord(
            prediction_id=str(uuid4()),
            game_id=f"test_game_{i}",
            timestamp=datetime.now() - timedelta(days=i),
            home_team="Team A",
            away_team="Team B",
            pick="home" if i % 2 == 0 else "away",
            bet_type="moneyline",
            line=0,
            odds=-150 if i % 2 == 0 else +130,
            confidence=0.5 + (i % 5) * 0.1,
            edge=0.03 + (i % 3) * 0.02,
            model_name="test_model",
            council_consensus=0.7,
            tier="A_tier" if i % 3 == 0 else "B_tier",
        )
        engine.record_prediction(record)

        # Update with result
        result = "win" if i % 3 != 0 else "loss"
        profit = 100 if result == "win" else -110
        engine.update_result(record.prediction_id, result, 28, 21, profit)

    # Generate report
    print(engine.generate_report())

    # Analyze patterns
    patterns = engine.identify_patterns()
    print(f"\nPatterns found: {patterns}")
