"""Feature engineering package.

Modules:
- pipeline: Feature orchestration
- elo: ELO rating features
- epa: Expected Points Added features
- form: Recent performance features
- rest_days: Rest and schedule features
- weather: Weather impact features
- injury: Injury impact features
- advanced: State-of-the-art features (opponent-adjusted, multi-window)
"""

try:
    from .pipeline import FeaturePipeline, create_features
    from .advanced import AdvancedFeatures, MarketFeatures
except ImportError:
    pass
