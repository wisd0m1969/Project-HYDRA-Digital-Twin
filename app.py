"""
Project HYDRA — Telemetry Dashboard
════════════════════════════════════

Pure UI Renderer.  This module contains ZERO business logic.

Data flow is strictly unidirectional:

    State  →  Render  →  Update  →  State
    (engine)  (components)  (session_state)  (engine)

All chart construction lives in ``components/``.
All state-transition logic lives in ``engine/``.
All styling lives in ``utils/theme``.
"""

import streamlit as st
from collections import deque
from datetime import timedelta

from engine import HydraSimulator, GraphRAGEngine
from components.charts import (
    render_helios_chart,
    render_aegis_chart,
    render_sensor_chart,
    render_gauge,
)
from components.map_view import render_deployment_map
from components.terminal import render_graphrag_log
from utils.theme import (
    GLOBAL_CSS,
    metric_card,
    NEON_GREEN,
    NEON_RED,
    HELIOS_PRIMARY,
    HELIOS_SECONDARY,
    AEGIS_PRIMARY,
    AEGIS_SECONDARY,
    SENTINEL_PRIMARY,
    SENTINEL_SECONDARY,
)

# ═══════════════════════════════════════════════════════════════════════════
#  Page Configuration (runs once)
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="HYDRA Telemetry",
    page_icon="🔱",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
#  Session State Initialisation (runs once)
# ═══════════════════════════════════════════════════════════════════════════

HISTORY_LEN = 60
_KEYS = ["irradiance", "desal", "membrane", "biofouling", "ph", "turbidity", "heavy_metal"]

if "sim" not in st.session_state:
    st.session_state.sim = HydraSimulator(seed=42)
    st.session_state.rag = GraphRAGEngine(seed=99)
    st.session_state.hist = {k: deque(maxlen=HISTORY_LEN) for k in _KEYS}
    st.session_state.log = deque(maxlen=200)

# ═══════════════════════════════════════════════════════════════════════════
#  Static Header (renders once — outside all fragments)
# ═══════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div style="text-align:center; padding:8px 0 24px 0;">
        <div style="font-size:11px; letter-spacing:6px; color:#353550;
                    text-transform:uppercase;">
            Deterministic Digital Twin · Mission-Critical Telemetry
        </div>
        <div style="font-size:44px; font-weight:800;
                    background:linear-gradient(90deg,#00f0ff,#ff00ff);
                    -webkit-background-clip:text;
                    -webkit-text-fill-color:transparent;
                    letter-spacing:5px; margin:-2px 0;">
            PROJECT HYDRA
        </div>
        <div style="font-size:11px; letter-spacing:4px; color:#252540;
                    margin-top:2px;">
            DOI INTHANON DEPLOYMENT · 18.5883°N  98.4861°E
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════
#  Sidebar — GraphRAG Autonomous Reasoning Log
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center; padding:16px 0 12px 0;">
            <div style="font-size:22px; font-weight:700; color:#00ff41;
                        text-shadow:0 0 18px rgba(0,255,65,0.3);
                        letter-spacing:2px;">
                🧠 GraphRAG
            </div>
            <div style="font-size:9px; color:#353550; letter-spacing:2.5px;
                        text-transform:uppercase; margin-top:4px;">
                Autonomous Reasoning Engine
            </div>
            <div style="font-size:9px; color:#252540; margin-top:2px;
                        letter-spacing:1.5px;">
                14,000 Neo4j Nodes · Real-Time Traversal
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    @st.fragment(run_every=timedelta(seconds=1))
    def _sidebar_log() -> None:
        st.markdown(
            render_graphrag_log(st.session_state.log),
            unsafe_allow_html=True,
        )

    _sidebar_log()

# ═══════════════════════════════════════════════════════════════════════════
#  Main Telemetry Fragment (non-blocking, 1 Hz)
#
#  Unidirectional flow per tick:
#    1. engine.simulator.step()       → new HydraState
#    2. engine.graphrag.analyze()     → new log lines
#    3. session_state mutation        → append to history deques
#    4. components.* render calls     → display
# ═══════════════════════════════════════════════════════════════════════════


@st.fragment(run_every=timedelta(seconds=1))
def _telemetry() -> None:
    # ── 1. State transition (engine) ───────────────────────
    state = st.session_state.sim.step()

    # ── 2. Reasoning (engine) ──────────────────────────────
    for entry in st.session_state.rag.analyze(state):
        st.session_state.log.append(entry)

    # ── 3. History update (session state) ──────────────────
    h = st.session_state.hist
    h["irradiance"].append(state.helios.solar_irradiance_wm2)
    h["desal"].append(state.helios.desalination_rate_lhr)
    h["membrane"].append(state.aegis.membrane_integrity_pct)
    h["biofouling"].append(state.aegis.biofouling_risk_pct)
    h["ph"].append(state.sentinel.ph_level)
    h["turbidity"].append(state.sentinel.turbidity_ntu)
    h["heavy_metal"].append(state.sentinel.heavy_metal_ppm)

    # ── 4. Render: Metric Cards (utils.theme) ─────────────
    s = state.sentinel
    c = st.columns(6)

    with c[0]:
        st.markdown(
            metric_card("Solar Irradiance", f"{state.helios.solar_irradiance_wm2:.0f}", "W/m²", HELIOS_PRIMARY),
            unsafe_allow_html=True,
        )
    with c[1]:
        st.markdown(
            metric_card("Desalination", f"{state.helios.desalination_rate_lhr:.2f}", "L/hr", HELIOS_SECONDARY),
            unsafe_allow_html=True,
        )
    with c[2]:
        st.markdown(
            metric_card("Membrane", f"{state.aegis.membrane_integrity_pct:.1f}", "%", AEGIS_PRIMARY),
            unsafe_allow_html=True,
        )
    with c[3]:
        qq_tag = "QQ:ON" if state.aegis.quorum_quenching_active else "QQ:OFF"
        bio_color = NEON_RED if state.aegis.biofouling_risk_pct > 25 else AEGIS_SECONDARY
        st.markdown(
            metric_card("Biofouling", f"{state.aegis.biofouling_risk_pct:.1f}", f"% · {qq_tag}", bio_color),
            unsafe_allow_html=True,
        )
    with c[4]:
        st.markdown(
            metric_card(
                "pH Level",
                f"{s.ph_level:.2f}" if s.ph_level is not None else "",
                "" if s.ph_level is not None else "",
                SENTINEL_PRIMARY,
                offline=s.ph_level is None,
            ),
            unsafe_allow_html=True,
        )
    with c[5]:
        st.markdown(
            metric_card(
                "Turbidity",
                f"{s.turbidity_ntu:.2f}" if s.turbidity_ntu is not None else "",
                "NTU" if s.turbidity_ntu is not None else "",
                SENTINEL_SECONDARY,
                offline=s.turbidity_ntu is None,
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── 4. Render: Subsystem Gauges (components.charts) ───
    gc1, gc2, gc3 = st.columns(3)

    with gc1:
        st.plotly_chart(
            render_gauge(
                value=state.helios.solar_irradiance_wm2,
                range_min=0,
                range_max=1400,
                color=HELIOS_PRIMARY,
                label="IRRADIANCE W/m²",
                steps=[
                    {"range": [0, 200], "color": "rgba(255,7,58,0.10)"},
                    {"range": [200, 900], "color": "rgba(255,215,0,0.04)"},
                    {"range": [900, 1400], "color": "rgba(57,255,20,0.06)"},
                ],
                threshold=200,
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with gc2:
        st.plotly_chart(
            render_gauge(
                value=state.aegis.membrane_integrity_pct,
                range_min=0,
                range_max=100,
                color=AEGIS_PRIMARY,
                label="MEMBRANE %",
                steps=[
                    {"range": [0, 60], "color": "rgba(255,7,58,0.10)"},
                    {"range": [60, 80], "color": "rgba(255,215,0,0.06)"},
                    {"range": [80, 100], "color": "rgba(57,255,20,0.06)"},
                ],
                threshold=80,
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with gc3:
        ph_val = s.ph_level if s.ph_level is not None else 7.0
        st.plotly_chart(
            render_gauge(
                value=ph_val,
                range_min=0,
                range_max=14,
                color=SENTINEL_PRIMARY,
                label="pH LEVEL",
                steps=[
                    {"range": [0, 6.5], "color": "rgba(255,7,58,0.10)"},
                    {"range": [6.5, 8.5], "color": "rgba(0,240,255,0.04)"},
                    {"range": [8.5, 14], "color": "rgba(255,7,58,0.10)"},
                ],
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # ── 5. Render: HELIOS + AEGIS (components.charts) ─────
    col_h, col_a = st.columns(2)

    with col_h:
        st.markdown(
            '<div class="section-header">☀ HELIOS — Solar Core</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            render_helios_chart(h["irradiance"], h["desal"]),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with col_a:
        st.markdown(
            '<div class="section-header">🛡 AEGIS — Biological Defense</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            render_aegis_chart(h["membrane"], h["biofouling"]),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # ── 4. Render: SENTINEL (components.charts) ───────────
    st.markdown(
        '<div class="section-header">📡 SENTINEL — IoT Sensor Array</div>',
        unsafe_allow_html=True,
    )
    col_p, col_t, col_m = st.columns(3)

    with col_p:
        st.plotly_chart(
            render_sensor_chart(h["ph"], SENTINEL_PRIMARY, "pH"),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    with col_t:
        st.plotly_chart(
            render_sensor_chart(h["turbidity"], SENTINEL_SECONDARY, "Turbidity NTU"),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    with col_m:
        st.plotly_chart(
            render_sensor_chart(h["heavy_metal"], NEON_GREEN, "Heavy Metal PPM"),
            use_container_width=True,
            config={"displayModeBar": False},
        )


_telemetry()

# ═══════════════════════════════════════════════════════════════════════════
#  Static Deployment Map (renders once — zero fragment overhead)
# ═══════════════════════════════════════════════════════════════════════════

st.markdown(
    '<div class="section-header">🗺 Deployment — Doi Inthanon, Thailand</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="hydra-map-pulse">', unsafe_allow_html=True)
st.plotly_chart(
    render_deployment_map(),
    use_container_width=True,
    config={"displayModeBar": False},
)
st.markdown("</div>", unsafe_allow_html=True)
