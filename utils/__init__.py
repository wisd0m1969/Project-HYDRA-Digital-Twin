"""Shared utilities — CSS injection and Plotly layout templates."""

from .theme import (
    GLOBAL_CSS,
    alert_banner,
    base_layout,
    comparison_table,
    countdown_card,
    metric_card,
    neon_trace,
    summary_card,
    who_badge,
)

__all__ = [
    "GLOBAL_CSS",
    "base_layout",
    "neon_trace",
    "metric_card",
    "countdown_card",
    "summary_card",
    "who_badge",
    "alert_banner",
    "comparison_table",
]
