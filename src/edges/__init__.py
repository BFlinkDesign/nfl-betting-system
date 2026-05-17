"""Edge detection module for market inefficiencies."""

from .market_edges import (
    MarketEdgeDetector,
    DetectedEdge,
    EdgeType,
    detect_edges_for_week,
)
from .rest_disparity import (
    RestDisparityAnalyzer,
    RestAnalysis,
    RestSituation,
    analyze_week_rest,
)

__all__ = [
    'MarketEdgeDetector',
    'DetectedEdge',
    'EdgeType',
    'detect_edges_for_week',
    'RestDisparityAnalyzer',
    'RestAnalysis',
    'RestSituation',
    'analyze_week_rest',
]
