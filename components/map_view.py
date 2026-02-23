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

from utils.theme import NEON_CYAN

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
