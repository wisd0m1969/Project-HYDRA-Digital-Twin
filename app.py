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

from engine import (
    HydraSimulator,
    GraphRAGEngine,
    STATIONS,
    compute_wqi,
    compute_energy_efficiency,
    predict_maintenance,
    build_session_summary,
    build_csv,
)
from components.charts import (
    render_helios_chart,
    render_aegis_chart,
    render_sensor_chart,
    render_gauge,
    render_wqi_gauge,
    render_sparkline,
    render_anomaly_timeline,
)
from components.map_view import render_deployment_map
from components.terminal import render_graphrag_log
from utils.theme import (
    GLOBAL_CSS,
    metric_card,
    countdown_card,
    summary_card,
    NEON_GREEN,
    NEON_RED,
    NEON_CYAN,
    NEON_AMBER,
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
_KEYS = [
    "irradiance", "desal", "membrane", "biofouling",
    "ph", "turbidity", "heavy_metal",
    "wqi", "efficiency",
]


def _init_session(station_name: str = "Doi Inthanon") -> None:
    """Initialise or reset all session state for a given station."""
    cfg = STATIONS[station_name]
    st.session_state.station = station_name
    st.session_state.sim = HydraSimulator(config=cfg)
    st.session_state.rag = GraphRAGEngine(seed=cfg.seed + 57)
    st.session_state.hist = {k: deque(maxlen=HISTORY_LEN) for k in _KEYS}
    st.session_state.log = deque(maxlen=200)
    st.session_state.anomaly_events = deque(maxlen=500)
    st.session_state.anomaly_count = 0


if "sim" not in st.session_state:
    _init_session()

# ═══════════════════════════════════════════════════════════════════════════
#  Static Header (renders once — outside all fragments)
# ═══════════════════════════════════════════════════════════════════════════

# ── Station selector (outside fragment) ─────────────────────────
hdr_left, hdr_center, hdr_right = st.columns([1, 3, 1])
with hdr_right:
    station_names = list(STATIONS.keys())
    current_idx = station_names.index(st.session_state.station)
    selected = st.selectbox(
        "Station",
        station_names,
        index=current_idx,
        label_visibility="collapsed",
    )
    if selected != st.session_state.station:
        _init_session(selected)
        st.rerun()

cfg = STATIONS[st.session_state.station]

with hdr_center:
    st.markdown(
        f"""
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
                {cfg.name.upper()} DEPLOYMENT · {cfg.lat:.4f}°N  {cfg.lon:.4f}°E
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════════════
#  Sidebar — GraphRAG Reasoning Log + Export
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

    # ── Export & Summary (static, outside fragment) ──────────
    st.markdown(
        '<div style="height:16px"></div>',
        unsafe_allow_html=True,
    )

    stats = build_session_summary(
        st.session_state.hist,
        st.session_state.anomaly_count,
        st.session_state.sim._tick,
    )
    st.markdown(summary_card(stats), unsafe_allow_html=True)

    csv_data = build_csv(st.session_state.hist)
    st.download_button(
        label="📥 Export CSV",
        data=csv_data,
        file_name=f"hydra_{st.session_state.station.lower().replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

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

    # ── 2b. Anomaly detection ─────────────────────────────
    new_anomalies = GraphRAGEngine.detect_anomalies(state)
    for evt in new_anomalies:
        st.session_state.anomaly_events.append(evt)
    st.session_state.anomaly_count += len(new_anomalies)

    # ── 3. History update (session state) ──────────────────
    h = st.session_state.hist
    s = state.sentinel
    h["irradiance"].append(state.helios.solar_irradiance_wm2)
    h["desal"].append(state.helios.desalination_rate_lhr)
    h["membrane"].append(state.aegis.membrane_integrity_pct)
    h["biofouling"].append(state.aegis.biofouling_risk_pct)
    h["ph"].append(s.ph_level)
    h["turbidity"].append(s.turbidity_ntu)
    h["heavy_metal"].append(s.heavy_metal_ppm)

    # ── 3b. Analytics ──────────────────────────────────────
    wqi_score, wqi_grade, wqi_color = compute_wqi(
        s.ph_level, s.turbidity_ntu, s.heavy_metal_ppm,
    )
    h["wqi"].append(wqi_score)

    eff = compute_energy_efficiency(
        state.helios.desalination_rate_lhr,
        state.helios.solar_irradiance_wm2,
    )
    h["efficiency"].append(eff)

    maint_ticks, maint_slope, maint_intercept = predict_maintenance(h["membrane"])

    # ── 4. Render: WQI Gauge (full width) ──────────────────
    st.plotly_chart(
        render_wqi_gauge(wqi_score, wqi_grade, wqi_color),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    # ── 4. Render: Metric Cards (utils.theme) ─────────────
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

    # ── 4. Render: Energy Efficiency + Maintenance ─────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    eff_col, spark_col, maint_col = st.columns([1, 1, 1])

    with eff_col:
        if eff is not None:
            st.markdown(
                metric_card("Energy Efficiency", f"{eff:.2f}", "L/kWh", NEON_CYAN),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                metric_card("Energy Efficiency", "", "", NEON_CYAN, offline=True),
                unsafe_allow_html=True,
            )

    with spark_col:
        eff_data = [v for v in h["efficiency"] if v is not None]
        if eff_data:
            st.plotly_chart(
                render_sparkline(eff_data, NEON_CYAN, height=80),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    with maint_col:
        maint_color = NEON_GREEN if maint_ticks is None else (NEON_RED if maint_ticks == 0 else NEON_AMBER)
        st.markdown(
            countdown_card(maint_ticks, maint_color),
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
        # Build prediction line for AEGIS chart
        pred_line = None
        if maint_slope < 0 and len(h["membrane"]) >= 10:
            n = len(h["membrane"])
            pred_line = [
                maint_slope * (n + i) + maint_intercept
                for i in range(20)
            ]
        st.plotly_chart(
            render_aegis_chart(h["membrane"], h["biofouling"], prediction_line=pred_line),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # ── 6. Render: SENTINEL (components.charts) ───────────
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

    # ── 7. Render: Anomaly Timeline ───────────────────────
    st.markdown(
        '<div class="section-header">⚡ Anomaly Timeline</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        render_anomaly_timeline(
            list(st.session_state.anomaly_events),
            state.tick,
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )


_telemetry()

# ═══════════════════════════════════════════════════════════════════════════
#  Static Deployment Map (renders once — zero fragment overhead)
# ═══════════════════════════════════════════════════════════════════════════

st.markdown(
    f'<div class="section-header">🗺 Deployment — {cfg.name}, Thailand</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="hydra-map-pulse">', unsafe_allow_html=True)
st.plotly_chart(
    render_deployment_map(
        lat=cfg.lat,
        lon=cfg.lon,
        label=f"HYDRA {cfg.name}",
        altitude=cfg.altitude_m,
    ),
    use_container_width=True,
    config={"displayModeBar": False},
)
st.markdown("</div>", unsafe_allow_html=True)
