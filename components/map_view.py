"""Geospatial renderer — Doi Inthanon deployment marker with pulse rings.

Returns a Plotly Scattermapbox figure on the ``carto-darkmatter``
tile layer.  No API key required.  Stateless — always returns the
same figure for the same deployment coordinates.

The pulsing effect is achieved with:
  - Concentric translucent ring markers (static glow halo)
  - CSS ``@keyframes hydra-pulse`` on the container (animated glow)
"""

from __future__ import annotations

import plotly.graph_objects as go

from typing import Sequence

from utils.theme import NEON_CYAN, NEON_GREEN, NEON_GOLD, NEON_RED

# ── Deployment coordinates ─────────────────────────────────────────────────

DOI_INTHANON_LAT = 18.5883
DOI_INTHANON_LON = 98.4861

# Concentric pulse rings: (size, opacity)
_PULSE_RINGS = [
    (40, 0.08),
    (28, 0.14),
    (20, 0.22),
]


def render_deployment_map(
    lat: float = DOI_INTHANON_LAT,
    lon: float = DOI_INTHANON_LON,
    label: str = "HYDRA Alpha Station",
    altitude: int = 2565,
) -> go.Figure:
    """Return a dark-themed Mapbox figure with a pulsing HYDRA marker."""

    # Outer-to-inner glow rings (rendered first = behind)
    traces = []
    for size, opacity in _PULSE_RINGS:
        traces.append(
            go.Scattermapbox(
                lat=[lat],
                lon=[lon],
                mode="markers",
                marker=dict(size=size, color=NEON_CYAN, opacity=opacity),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Core marker with label
    traces.append(
        go.Scattermapbox(
            lat=[lat],
            lon=[lon],
            mode="markers+text",
            marker=dict(size=13, color=NEON_CYAN, opacity=0.95),
            text=[label],
            textfont=dict(color=NEON_CYAN, size=11),
            textposition="top center",
            hovertemplate=(
                f"<b>{label}</b><br>"
                f"Lat: {lat:.4f}°N<br>"
                f"Lon: {lon:.4f}°E<br>"
                f"Alt: {altitude:,} m<extra></extra>"
            ),
            showlegend=False,
        )
    )

    fig = go.Figure(data=traces)
    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=lat, lon=lon),
            zoom=10,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=360,
    )
    return fig


# ── WQI score → marker color ──────────────────────────────────────────────

_WQI_COLORS = [
    (90, NEON_GREEN),   # A
    (70, NEON_CYAN),    # B
    (50, NEON_GOLD),    # C
    (30, "#ff8c00"),    # D
    (0,  NEON_RED),     # F
]


def _wqi_to_color(score: float) -> str:
    for threshold, color in _WQI_COLORS:
        if score >= threshold:
            return color
    return NEON_RED


def render_global_map(
    stations: Sequence[dict],
    active_name: str = "",
) -> go.Figure:
    """Render all stations on a single world map with WQI-colored markers.

    ``stations``: list of dicts with keys: name, lat, lon, wqi_score.
    ``active_name``: name of the currently selected station (highlighted).
    """
    lats = [s["lat"] for s in stations]
    lons = [s["lon"] for s in stations]
    names = [s["name"] for s in stations]
    scores = [s.get("wqi_score", 50) for s in stations]
    colors = [_wqi_to_color(sc) for sc in scores]
    sizes = [18 if s["name"] == active_name else 12 for s in stations]
    opacities = [1.0 if s["name"] == active_name else 0.7 for s in stations]

    hover = [
        f"<b>{n}</b><br>WQI: {sc:.0f}<br>{la:.4f}°, {lo:.4f}°<extra></extra>"
        for n, sc, la, lo in zip(names, scores, lats, lons)
    ]

    traces = [
        go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode="markers+text",
            marker=dict(
                size=sizes,
                color=colors,
                opacity=opacities,
            ),
            text=names,
            textfont=dict(color="#c0c0c0", size=9),
            textposition="top center",
            hovertemplate=hover,
            showlegend=False,
        )
    ]

    # Compute center
    c_lat = sum(lats) / len(lats) if lats else 0
    c_lon = sum(lons) / len(lons) if lons else 0

    fig = go.Figure(data=traces)
    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=c_lat, lon=c_lon),
            zoom=2 if len(stations) > 1 else 10,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=300,
    )
    return fig
