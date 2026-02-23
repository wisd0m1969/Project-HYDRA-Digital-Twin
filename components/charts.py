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
    NEON_CYAN,
    NEON_GREEN,
    NEON_GOLD,
    NEON_AMBER,
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


def render_aegis_chart(
    membrane: DataSeq,
    biofouling: DataSeq,
    prediction_line: Optional[list[float]] = None,
) -> go.Figure:
    """Overlay chart: membrane integrity vs biofouling risk.

    If ``prediction_line`` is provided, draws a dashed projection line
    and a horizontal threshold at 80%.
    """
    fig = go.Figure()
    fig.add_trace(neon_trace(membrane, AEGIS_PRIMARY, "Membrane %"))
    fig.add_trace(neon_trace(biofouling, NEON_RED, "Biofouling %", fill=False))

    if prediction_line is not None:
        n = len(list(membrane))
        x_pred = list(range(n, n + len(prediction_line)))
        fig.add_trace(
            go.Scatter(
                x=x_pred,
                y=prediction_line,
                mode="lines",
                name="Projection",
                line=dict(color=NEON_AMBER, width=1.5, dash="dash"),
                hovertemplate="%{y:.1f}%<extra>Projection</extra>",
            )
        )
        # Threshold line at 80%
        total_x = n + len(prediction_line)
        fig.add_trace(
            go.Scatter(
                x=[0, total_x],
                y=[80, 80],
                mode="lines",
                name="Threshold",
                line=dict(color=NEON_RED, width=1, dash="dot"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

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


# ── WQI Gauge ─────────────────────────────────────────────────────────────


def render_wqi_gauge(score: float, grade: str, color: str) -> go.Figure:
    """Large Water Quality Index gauge with letter grade annotation."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": "WATER QUALITY INDEX", "font": {"size": 11, "color": "#505068"}},
            number={
                "font": {"size": 32, "color": color, "family": "JetBrains Mono, SF Mono, monospace"},
                "valueformat": ".0f",
                "suffix": f"  {grade}",
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickcolor": "#252540",
                    "tickfont": {"size": 9, "color": "#353550"},
                    "dtick": 20,
                },
                "bar": {"color": color, "thickness": 0.75},
                "bgcolor": "#111116",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": "rgba(255,7,58,0.10)"},
                    {"range": [30, 50], "color": "rgba(255,140,0,0.06)"},
                    {"range": [50, 70], "color": "rgba(255,215,0,0.06)"},
                    {"range": [70, 90], "color": "rgba(0,240,255,0.04)"},
                    {"range": [90, 100], "color": "rgba(57,255,20,0.06)"},
                ],
            },
        )
    )
    fig.update_layout(**gauge_layout(height=220))
    return fig


# ── Sparkline ──────────────────────────────────────────────────────────────


def render_sparkline(data: DataSeq, color: str, height: int = 60) -> go.Figure:
    """Minimal sparkline chart with no axes or labels."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=list(data),
            mode="lines",
            line=dict(color=color, width=1.5, shape="spline", smoothing=1.0),
            fill="tozeroy",
            fillcolor=_hex_to_rgba(color, 0.08),
            hovertemplate="%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#111116", bordercolor="#1a1a2e",
            font=dict(color="#c0c0c0", size=10),
        ),
    )
    return fig


# ── Anomaly Timeline ──────────────────────────────────────────────────────

_SEVERITY_COLORS = {1: NEON_GOLD, 2: NEON_AMBER, 3: NEON_RED}
_SEVERITY_SIZES = {1: 6, 2: 9, 3: 12}


def render_anomaly_timeline(
    events: Sequence[tuple],
    current_tick: int,
) -> go.Figure:
    """Scatter chart of anomaly events over time.

    Each event is ``(tick, type_str, severity_int)``.
    Severity 1=warn, 2=alert, 3=critical.
    """
    fig = go.Figure()

    if events:
        ticks = [e[0] for e in events]
        labels = [e[1] for e in events]
        sevs = [e[2] for e in events]
        colors = [_SEVERITY_COLORS.get(s, NEON_GOLD) for s in sevs]
        sizes = [_SEVERITY_SIZES.get(s, 6) for s in sevs]

        fig.add_trace(
            go.Scatter(
                x=ticks,
                y=sevs,
                mode="markers",
                marker=dict(color=colors, size=sizes, opacity=0.85),
                text=labels,
                hovertemplate="t=%{x}<br>%{text}<br>severity=%{y}<extra></extra>",
            )
        )

    fig.update_layout(
        **base_layout(
            height=140,
            yaxis=dict(
                showgrid=False, zeroline=False,
                tickvals=[1, 2, 3], ticktext=["Warn", "Alert", "Crit"],
                color="#353550", tickfont=dict(size=9),
                range=[0.5, 3.5],
            ),
            xaxis=dict(
                showgrid=False, zeroline=False,
                color="#353550", tickfont=dict(size=9),
                range=[max(0, current_tick - 200), current_tick + 5],
            ),
        )
    )
    return fig
