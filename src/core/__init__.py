"""Core module - Validation, feedback, and autonomous system.

Research-grounded, self-validating components:
- ValidationFramework: Proper metrics (Brier, log loss, ECE, CLV)
- FeedbackLoop: Self-improving system that learns from results
"""

from .validation_framework import (
    ValidationFramework,
    ValidationResult,
    PredictionRecord,
    THRESHOLDS,
    create_validation_framework,
)
from .feedback_loop import (
    FeedbackLoop,
    PerformanceWindow,
    FeatureSignal,
    ImprovementSignal,
    create_feedback_loop,
)

__all__ = [
    'ValidationFramework',
    'ValidationResult',
    'PredictionRecord',
    'THRESHOLDS',
    'create_validation_framework',
    'FeedbackLoop',
    'PerformanceWindow',
    'FeatureSignal',
    'ImprovementSignal',
    'create_feedback_loop',
]
