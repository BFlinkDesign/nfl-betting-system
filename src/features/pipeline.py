"""Feature engineering pipeline.

Orchestrates all feature builders in correct order.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging
from typing import List, Optional

import pandas as pd

try:
    from .base import FeatureBuilder
    from .elo import EloFeatures
    from .encoding import CategoricalEncodingFeatures
    from .epa import EPAFeatures
    from .form import FormFeatures
    from .injury import InjuryFeatures
    from .line import LineFeatures
    from .market import MarketFeatures
    from .referee import RefereeFeatures
    from .rest_days import RestDaysFeatures
    from .strength_of_schedule import StrengthOfScheduleFeatures
    from .weather import WeatherFeatures
except ImportError:
    from src.features.base import FeatureBuilder
    from src.features.elo import EloFeatures
    from src.features.encoding import CategoricalEncodingFeatures
    from src.features.epa import EPAFeatures
    from src.features.form import FormFeatures
    from src.features.injury import InjuryFeatures
    from src.features.line import LineFeatures
    from src.features.market import MarketFeatures
    from src.features.referee import RefereeFeatures
    from src.features.rest_days import RestDaysFeatures
    from src.features.strength_of_schedule import StrengthOfScheduleFeatures
    from src.features.weather import WeatherFeatures

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """Orchestrates feature building with validation."""

    def __init__(self, pbp_data: Optional[pd.DataFrame] = None):
        """
        Initialize pipeline.

        Args:
            pbp_data: Play-by-play data for EPA features (optional)
        """
        self.builders: List[FeatureBuilder] = []
        self.pbp_data = pbp_data

    def add_builder(self, builder: FeatureBuilder):
        """Add a feature builder."""
        self.builders.append(builder)
        return self

    def build_features(self, df: pd.DataFrame, validate=True) -> pd.DataFrame:
        """
        Apply all builders sequentially.

        Args:
            df: Input dataframe (schedules)
            validate: Whether to validate features after building

        Returns:
            DataFrame with all features
        """
        logger.info(f"Building features with {len(self.builders)} builders")

        for builder in self.builders:
            builder_name = builder.__class__.__name__
            logger.info(f"Applying {builder_name}...")

            try:
                df = builder.build(df)
                features = builder.get_feature_names()
                logger.info(f"  ✓ Added {len(features)} features")

                # Validate no unexpected nulls
                null_counts = df[features].isnull().sum()
                if null_counts.any():
                    logger.warning(
                        f"  ⚠ Nulls in {builder_name}:\n{null_counts[null_counts > 0]}"
                    )
            except Exception as e:
                logger.error(f"  ✗ {builder_name} failed: {e}")
                raise

        if validate:
            self._validate_features(df)

        logger.info(f"✓ Feature building complete: {len(df.columns)} total columns")

        return df

    def _validate_features(self, df: pd.DataFrame):
        """Validate feature quality."""
        logger.info("Validating features...")

        # Get feature columns (exclude metadata)
        exclude = [
            "game_id",
            "gameday",
            "home_team",
            "away_team",
            "season",
            "week",
            "home_score",
            "away_score",
            "result",
            "total",
            "game_type",
            "weekday",
            "gametime",
            "location",
            "overtime",
        ]
        feature_cols = [col for col in df.columns if col not in exclude]

        # Check for high correlations
        numeric_cols = (
            df[feature_cols].select_dtypes(include=["float64", "int64"]).columns
        )
        if len(numeric_cols) > 1:
            corr = df[numeric_cols].corr().abs()

            high_corr = []
            for i in range(len(corr.columns)):
                for j in range(i + 1, len(corr.columns)):
                    if corr.iloc[i, j] > 0.85:
                        high_corr.append(
                            (corr.columns[i], corr.columns[j], corr.iloc[i, j])
                        )

            if high_corr:
                logger.warning("High correlations found (>0.85):")
                for feat1, feat2, val in high_corr[:10]:  # Show first 10
                    logger.warning(f"  {feat1} <-> {feat2}: {val:.3f}")
                logger.warning("Consider removing one from each pair")
            else:
                logger.info("✓ No high correlations (max <0.85)")

        # Check for remaining nulls
        null_counts = df[feature_cols].isnull().sum()
        if null_counts.any():
            null_cols = null_counts[null_counts > 0]
            logger.warning(f"Remaining nulls:\n{null_cols}")
            # Fill with 0 for numeric features
            for col in null_cols.index:
                if df[col].dtype in ["float64", "int64"]:
                    df[col] = df[col].fillna(0)
                    logger.info(f"  Filled {col} nulls with 0")

        logger.info(f"✓ Features validated: {len(feature_cols)} features")

    def get_all_feature_names(self) -> List[str]:
        """Get all feature names from all builders."""
        all_features = []
        for builder in self.builders:
            all_features.extend(builder.get_feature_names())
        return all_features


def create_features(
    seasons: List[int], output_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Create features for given seasons.

    Args:
        seasons: List of seasons to process
        output_path: Path to save features (optional)

    Returns:
        DataFrame with features
    """

    logger.info(f"Creating features for seasons {min(seasons)}-{max(seasons)}")

    # Load raw data
    data_dir = Path("data")
    schedules = pd.read_parquet(
        data_dir / "raw" / f"schedules_{min(seasons)}_{max(seasons)}.parquet"
    )

    try:
        pbp = pd.read_parquet(
            data_dir / "raw" / f"pbp_{min(seasons)}_{max(seasons)}.parquet"
        )
    except FileNotFoundError:
        logger.warning("Play-by-play not found, skipping EPA features")
        pbp = None

    # Initialize pipeline
    pipeline = FeaturePipeline(pbp_data=pbp)

    # Add builders in order
    pipeline.add_builder(LineFeatures())
    pipeline.add_builder(RestDaysFeatures())
    pipeline.add_builder(EloFeatures())
    pipeline.add_builder(WeatherFeatures())
    pipeline.add_builder(FormFeatures())
    pipeline.add_builder(CategoricalEncodingFeatures())
    pipeline.add_builder(RefereeFeatures(pbp_data=pbp))
    pipeline.add_builder(StrengthOfScheduleFeatures())
    pipeline.add_builder(MarketFeatures())

    if pbp is not None:
        pipeline.add_builder(EPAFeatures(pbp_data=pbp))

    # Try to load injury data
    try:
        import nflreadpy as nfl

        injury_data = nfl.import_injuries(list(range(min(seasons), max(seasons) + 1)))
        if injury_data is not None and len(injury_data) > 0:
            pipeline.add_builder(InjuryFeatures(injury_data=injury_data))
    except Exception as e:
        logger.warning(f"Could not load injury data: {e}")

    # Build features
    df_features = pipeline.build_features(schedules.copy())

    # Save if requested
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df_features.to_parquet(output_file, index=False)
        logger.info(f"✓ Features saved to {output_file}")

    return df_features


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=str, default="2016-2024")
    parser.add_argument(
        "--output", type=str, default="data/processed/features_2016_2024.parquet"
    )
    args = parser.parse_args()

    # Parse seasons
    if "-" in args.seasons:
        start, end = args.seasons.split("-")
        seasons = list(range(int(start), int(end) + 1))
    else:
        seasons = [int(s) for s in args.seasons.split(",")]

    # Create features
    df = create_features(seasons, output_path=args.output)

    logger.info("=" * 70)
    logger.info("FEATURE GENERATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Seasons:  {min(seasons)}-{max(seasons)}")
    logger.info(f"Games:    {len(df):,}")
    logger.info(f"Features: {len(df.columns)}")
    logger.info(f"Output:   {args.output}")
    logger.info("=" * 70)
