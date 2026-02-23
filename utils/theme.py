"""Vantablack / Neon cyber-aesthetic theme system.

Exports colour constants, injectable CSS, Plotly layout builders,
and HTML generators for metric cards.
"""

from __future__ import annotations

import plotly.graph_objects as go

# ── Colour Palette ─────────────────────────────────────────────────────────

VANTABLACK = "#0a0a0a"
SURFACE = "#111116"
SURFACE_BORDER = "#1a1a2e"

NEON_CYAN = "#00f0ff"
NEON_MAGENTA = "#ff00ff"
NEON_GREEN = "#39ff14"
NEON_GOLD = "#ffd700"
NEON_AMBER = "#ff8c00"
NEON_RED = "#ff073a"
TERMINAL_GREEN = "#00ff41"

HELIOS_PRIMARY = NEON_GOLD
HELIOS_SECONDARY = NEON_AMBER
AEGIS_PRIMARY = NEON_GREEN
AEGIS_SECONDARY = "#00ff88"
SENTINEL_PRIMARY = NEON_CYAN
SENTINEL_SECONDARY = NEON_MAGENTA

# ── Global CSS ─────────────────────────────────────────────────────────────

GLOBAL_CSS = """<style>
/* ── Vantablack foundation ──────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"] {
    background-color: #0a0a0a !important;
}
[data-testid="stSidebar"] {
    background-color: #0d0d12 !important;
    border-right: 1px solid #1a1a2e !important;
}
section[data-testid="stSidebar"] > div {
    background-color: #0d0d12 !important;
}

/* ── Hide default chrome ────────────────────────────── */
#MainMenu, footer, [data-testid="stToolbar"] {
    visibility: hidden;
}

/* ── Typography ─────────────────────────────────────── */
h1, h2, h3, h4, h5, h6, p, span, div, label {
    color: #c0c0c0 !important;
}

/* ── Metric card ────────────────────────────────────── */
.hydra-metric {
    background: linear-gradient(145deg, rgba(17,17,22,0.95), rgba(10,10,10,0.95));
    border: 1px solid #1a1a2e;
    border-radius: 12px;
    padding: 18px 10px 14px 10px;
    text-align: center;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.hydra-metric:hover {
    border-color: #2a2a4e;
    box-shadow: 0 0 24px rgba(0,0,0,0.4);
}
.hydra-metric .label {
    color: #505068 !important;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-bottom: 6px;
}
.hydra-metric .value {
    font-size: 30px;
    font-weight: 700;
    font-family: 'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace;
    line-height: 1.2;
}
.hydra-metric .unit {
    color: #404058 !important;
    font-size: 12px;
    font-weight: 400;
}
.sensor-offline {
    background: linear-gradient(145deg, rgba(255,7,58,0.04), rgba(10,10,10,0.95)) !important;
    border-color: rgba(255,7,58,0.25) !important;
}
.sensor-offline .value {
    color: #ff073a !important;
    font-size: 14px !important;
    letter-spacing: 3px;
    text-shadow: 0 0 14px rgba(255,7,58,0.5);
}

/* ── Section headers ────────────────────────────────── */
.section-header {
    color: #353550 !important;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 3px;
    padding-bottom: 8px;
    margin-top: 18px;
    border-bottom: 1px solid #141420;
}

/* ── GraphRAG terminal ──────────────────────────────── */
.graphrag-terminal {
    background: #08080c;
    border: 1px solid #1a1a2e;
    border-radius: 8px;
    padding: 14px;
    font-family: 'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace;
    font-size: 11px;
    line-height: 1.65;
    color: #00ff41 !important;
    max-height: 600px;
    overflow-y: auto;
    display: flex;
    flex-direction: column-reverse;
}
.graphrag-terminal .warn  { color: #ffd700 !important; }
.graphrag-terminal .error { color: #ff073a !important; }
.graphrag-terminal .ok    { color: #39ff14 !important; }

/* ── Plotly containers ──────────────────────────────── */
.stPlotlyChart {
    border-radius: 12px;
    overflow: hidden;
}

/* ── Map pulse animation ────────────────────────────── */
.hydra-map-pulse .stPlotlyChart {
    animation: hydra-pulse 2.4s ease-in-out infinite;
}
@keyframes hydra-pulse {
    0%, 100% { filter: drop-shadow(0 0 4px rgba(0,240,255,0.15)); }
    50%      { filter: drop-shadow(0 0 18px rgba(0,240,255,0.45)); }
}

/* ── Scrollbar ──────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #1a1a2e; border-radius: 2px; }
</style>"""


# ── Plotly Layout Builder ──────────────────────────────────────────────────


def base_layout(height: int = 220, **overrides: object) -> dict:
    """Return a fully-transparent, grid-free Plotly layout."""
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            color="#505068",
            size=10,
            family="JetBrains Mono, SF Mono, monospace",
        ),
        margin=dict(l=42, r=14, t=8, b=28),
        height=height,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=True,
            color="#353550",
            tickfont=dict(size=9),
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=True,
            color="#353550",
            tickfont=dict(size=9),
        ),
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#111116",
            bordercolor="#1a1a2e",
            font=dict(color="#c0c0c0", size=11),
        ),
    )
    layout.update(overrides)
    return layout


# ── Trace Builder ──────────────────────────────────────────────────────────


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert ``#RGB`` or ``#RRGGBB`` hex to an ``rgba(...)`` string."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def neon_trace(
    y_data: object,
    color: str,
    name: str = "",
    fill: bool = True,
) -> go.Scatter:
    """Create a neon-glow Scatter trace with optional area fill."""
    return go.Scatter(
        y=list(y_data),
        mode="lines",
        name=name,
        line=dict(color=color, width=2.2, shape="spline", smoothing=1.0),
        fill="tozeroy" if fill else "none",
        fillcolor=_hex_to_rgba(color, 0.07) if fill else None,
        hovertemplate=f"%{{y:.2f}}<extra>{name}</extra>",
    )


# ── Metric Card HTML ──────────────────────────────────────────────────────


def gauge_layout(height: int = 190) -> dict:
    """Return a Plotly layout for neon gauge indicators."""
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            color="#505068",
            size=10,
            family="JetBrains Mono, SF Mono, monospace",
        ),
        margin=dict(l=28, r=28, t=48, b=16),
        height=height,
    )


def metric_card(
    label: str,
    value: str,
    unit: str,
    color: str,
    offline: bool = False,
) -> str:
    """Return an HTML metric card with neon glow."""
    if offline:
        return (
            '<div class="hydra-metric sensor-offline">'
            f'<div class="label">{label}</div>'
            '<div class="value">SENSOR OFFLINE</div>'
            "</div>"
        )

    glow = _hex_to_rgba(color, 0.4)
    border_hint = _hex_to_rgba(color, 0.12)

    return (
        f'<div class="hydra-metric" style="border-color:{border_hint};">'
        f'<div class="label">{label}</div>'
        f'<div class="value" style="color:{color};text-shadow:0 0 20px {glow};">'
        f'{value} <span class="unit">{unit}</span>'
        "</div></div>"
    )


def countdown_card(ticks_remaining: object, color: str) -> str:
    """Maintenance countdown card.

    ``ticks_remaining``: int (ticks until threshold), 0 (now!), or None (nominal).
    """
    glow = _hex_to_rgba(color, 0.4)
    border_hint = _hex_to_rgba(color, 0.12)

    if ticks_remaining is None:
        return (
            f'<div class="hydra-metric" style="border-color:{border_hint};">'
            '<div class="label">MAINTENANCE</div>'
            f'<div class="value" style="color:{color};text-shadow:0 0 20px {glow};'
            f'font-size:18px;">NOMINAL</div></div>'
        )
    if ticks_remaining == 0:
        red_glow = _hex_to_rgba("#ff073a", 0.5)
        return (
            '<div class="hydra-metric sensor-offline">'
            '<div class="label">MAINTENANCE</div>'
            f'<div class="value" style="color:#ff073a;text-shadow:0 0 20px {red_glow};'
            'font-size:14px;letter-spacing:2px;">MAINTENANCE NOW</div></div>'
        )
    return (
        f'<div class="hydra-metric" style="border-color:{border_hint};">'
        '<div class="label">MAINTENANCE</div>'
        f'<div class="value" style="color:{color};text-shadow:0 0 20px {glow};'
        f'font-size:16px;">~{ticks_remaining} ticks</div></div>'
    )


def summary_card(stats: dict) -> str:
    """Multi-row session summary card."""
    rows = []
    for label, value in stats.items():
        rows.append(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:3px 0;border-bottom:1px solid #141420;">'
            f'<span style="color:#505068;font-size:10px;letter-spacing:1px;'
            f'text-transform:uppercase;">{label}</span>'
            f'<span style="color:#c0c0c0;font-size:11px;'
            f'font-family:JetBrains Mono,SF Mono,monospace;">{value}</span>'
            f'</div>'
        )
    return (
        '<div class="hydra-metric" style="text-align:left;padding:14px 16px;">'
        '<div class="label" style="margin-bottom:10px;">Session Summary</div>'
        + "".join(rows)
        + '</div>'
    )
