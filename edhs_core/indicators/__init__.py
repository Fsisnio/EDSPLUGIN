"""
Indicator engine package.

This package contains the pluggable indicator framework used to
compute health and demographic indicators from DHS/EDHS survey data.

The design goals are:
- Automatic DHS-style weighting (v005 / 1_000_000)
- Explicit population filtering
- Confidence interval calculation
- Rich metadata logging
- Dynamic registration of indicators as modules
"""

# Import built-in indicators so they register themselves via the decorator.
from . import (  # noqa: F401
    builtins_modern_contraception,
    builtins_stunting,
    builtins_tfr,
    builtins_women_autonomy,
)
from .base import BaseIndicator
from .models import ConfidenceInterval, IndicatorMetadata, IndicatorResult
from .registry import (
    get_indicator_class,
    get_indicator_registry,
    list_indicators,
)

__all__ = [
    "BaseIndicator",
    "ConfidenceInterval",
    "IndicatorMetadata",
    "IndicatorResult",
    "get_indicator_class",
    "get_indicator_registry",
    "list_indicators",
]
