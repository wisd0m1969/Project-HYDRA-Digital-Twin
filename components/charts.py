"""Stateless chart renderers — Gauges & Line Charts.

Each function accepts raw data sequences and returns a fully-configured
``plotly.graph_objects.Figure``.  No Streamlit calls, no session state
access — pure data → visual transformation.
"""

from __future__ import annotations

from collections import deque
from typing import Optional, Sequence, Union

import plotly.graph_objects as go

from utils.theme import (
    AEGIS_PRIMARY,
    HELIOS_PRIMARY,
    HELIOS_SECONDARY,
    NEON_RED,
    base_layout,
    gauge_layout,
    neon_trace,
    _hex_to_rgba,
)

DataSeq = Union[deque, Sequence[float]]


# ── Neon Gauge Renderer ────────────────────────────────────────────────────


def render_gauge(
    value: float,
    range_min: float,
    range_max: float,
    color: str,
    label: str = "",
    steps: Optional[list[dict]] = None,
    threshold: Optional[float] = None,
) -> go.Figure:
    """Return a neon-styled Plotly gauge indicator.

    Stateless:  (value, config) → go.Figure.
    """
    gauge_cfg: dict = {
        "axis": {
            "range": [range_min, range_max],
            "tickcolor": "#252540",
            "tickfont": {"size": 9, "color": "#353550"},
            "dtick": (range_max - range_min) / 5,
        },
        "bar": {"color": color, "thickness": 0.75},
        "bgcolor": "#111116",
        "borderwidth": 0,
        "bordercolor": "#111116",
    }
    if steps:
        gauge_cfg["steps"] = steps
    if threshold is not None:
        gauge_cfg["threshold"] = {
            "line": {"color": NEON_RED, "width": 2},
            "thickness": 0.82,
            "value": threshold,
        }

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": label, "font": {"size": 11, "color": "#505068"}},
            number={
                "font": {"size": 26, "color": color, "family": "JetBrains Mono, SF Mono, monospace"},
                "valueformat": ".1f" if range_max > 20 else ".2f",
            },
            gauge=gauge_cfg,
        )
    )
    fig.update_layout(**gauge_layout())
    return fig


def render_helios_chart(irradiance: DataSeq, desal: DataSeq) -> go.Figure:
    """Dual-axis chart: irradiance (left) + desalination rate (right)."""
    fig = go.Figure()
    fig.add_trace(neon_trace(irradiance, HELIOS_PRIMARY, "Irradiance W/m²"))
    fig.add_trace(neon_trace(desal, HELIOS_SECONDARY, "Desal L/hr", fill=False))
    fig.data[1].yaxis = "y2"
    fig.update_layout(
        **base_layout(
            yaxis2=dict(
                overlaying="y",
                side="right",
                showgrid=False,
                zeroline=False,
                color="#353550",
                tickfont=dict(size=9),
            ),
        )
    )
    return fig


def render_aegis_chart(membrane: DataSeq, biofouling: DataSeq) -> go.Figure:
    """Overlay chart: membrane integrity vs biofouling risk."""
    fig = go.Figure()
    fig.add_trace(neon_trace(membrane, AEGIS_PRIMARY, "Membrane %"))
    fig.add_trace(neon_trace(biofouling, NEON_RED, "Biofouling %", fill=False))
    fig.update_layout(**base_layout())
    return fig


def render_sensor_chart(
    data: DataSeq,
    color: str,
    name: str,
) -> go.Figure:
    """Single-metric sparkline for any SENTINEL sensor channel."""
    fig = go.Figure()
    fig.add_trace(neon_trace(data, color, name))
    fig.update_layout(**base_layout(height=180))
    return fig
