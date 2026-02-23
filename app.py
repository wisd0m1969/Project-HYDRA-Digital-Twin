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
    build_custom_station,
    climate_from_latitude,
    compute_wqi,
    check_who_compliance,
    compare_stations,
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
from components.map_view import render_deployment_map, render_global_map
from components.terminal import render_graphrag_log
from utils.theme import (
    GLOBAL_CSS,
    metric_card,
    countdown_card,
    summary_card,
    who_badge,
    alert_banner,
    comparison_table,
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


def _all_stations() -> dict:
    """Merge preset stations with user-created custom stations."""
    custom = st.session_state.get("custom_stations", {})
    return {**STATIONS, **custom}


def _init_session(station_name: str = "Doi Inthanon") -> None:
    """Initialise or reset all session state for a given station."""
    cfg = _all_stations()[station_name]
    st.session_state.station = station_name
    st.session_state.sim = HydraSimulator(config=cfg)
    st.session_state.rag = GraphRAGEngine(seed=cfg.seed + 57)
    st.session_state.hist = {k: deque(maxlen=HISTORY_LEN) for k in _KEYS}
    st.session_state.log = deque(maxlen=200)
    st.session_state.anomaly_events = deque(maxlen=500)
    st.session_state.anomaly_count = 0


if "custom_stations" not in st.session_state:
    st.session_state.custom_stations = {}
if "sim" not in st.session_state:
    _init_session()

# ═══════════════════════════════════════════════════════════════════════════
#  Static Header (renders once — outside all fragments)
# ═══════════════════════════════════════════════════════════════════════════

# ── Station selector + Custom station form (outside fragment) ───
hdr_left, hdr_center, hdr_right = st.columns([1, 3, 1])

with hdr_left:
    with st.expander("+ Add Station", expanded=False):
        custom_name = st.text_input(
            "Name (optional)", value="", key="custom_name_input",
        )
        custom_lat = st.number_input(
            "Latitude", value=0.0, min_value=-90.0, max_value=90.0,
            step=0.01, format="%.4f", key="custom_lat_input",
        )
        custom_lon = st.number_input(
            "Longitude", value=0.0, min_value=-180.0, max_value=180.0,
            step=0.01, format="%.4f", key="custom_lon_input",
        )
        if st.button("Deploy Station", use_container_width=True):
            new_cfg = build_custom_station(
                lat=custom_lat, lon=custom_lon, name=custom_name,
            )
            st.session_state.custom_stations[new_cfg.name] = new_cfg
            _init_session(new_cfg.name)
            st.rerun()

with hdr_right:
    all_st = _all_stations()
    station_names = list(all_st.keys())
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

cfg = _all_stations()[st.session_state.station]
climate = climate_from_latitude(cfg.lat)

with hdr_center:
    lat_dir = "N" if cfg.lat >= 0 else "S"
    lon_dir = "E" if cfg.lon >= 0 else "W"
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
                {cfg.name.upper()} · {abs(cfg.lat):.4f}°{lat_dir}  {abs(cfg.lon):.4f}°{lon_dir}
                · {climate.zone.upper()} ZONE
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════════════
#  Sidebar — GraphRAG + Comparison + Export
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

    # ── Cross-Station Comparison (outside fragment) ───────────
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    compare_options = [n for n in _all_stations().keys() if n != st.session_state.station]
    if compare_options:
        with st.expander("Cross-Station Compare", expanded=False):
            compare_to = st.selectbox(
                "Compare with",
                compare_options,
                key="compare_station_select",
                label_visibility="collapsed",
            )
            if compare_to and st.button("Compare", use_container_width=True, key="compare_btn"):
                # Run a quick 30-tick simulation for the comparison station
                compare_cfg = _all_stations()[compare_to]
                compare_sim = HydraSimulator(config=compare_cfg)
                compare_hist = {k: deque(maxlen=HISTORY_LEN) for k in _KEYS}
                for _ in range(30):
                    cs = compare_sim.step()
                    compare_hist["irradiance"].append(cs.helios.solar_irradiance_wm2)
                    compare_hist["desal"].append(cs.helios.desalination_rate_lhr)
                    compare_hist["membrane"].append(cs.aegis.membrane_integrity_pct)
                    compare_hist["biofouling"].append(cs.aegis.biofouling_risk_pct)
                    compare_hist["ph"].append(cs.sentinel.ph_level)
                    compare_hist["turbidity"].append(cs.sentinel.turbidity_ntu)
                    compare_hist["heavy_metal"].append(cs.sentinel.heavy_metal_ppm)
                    sc, _, _ = compute_wqi(
                        cs.sentinel.ph_level, cs.sentinel.turbidity_ntu,
                        cs.sentinel.heavy_metal_ppm,
                    )
                    compare_hist["wqi"].append(sc)
                    compare_hist["efficiency"].append(
                        compute_energy_efficiency(
                            cs.helios.desalination_rate_lhr,
                            cs.helios.solar_irradiance_wm2,
                        )
                    )

                rows = compare_stations(
                    st.session_state.hist, compare_hist,
                    st.session_state.station, compare_to,
                )
                st.markdown(
                    comparison_table(rows, st.session_state.station, compare_to),
                    unsafe_allow_html=True,
                )

    # ── Export & Summary (static, outside fragment) ──────────
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

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

    who_status, who_details = check_who_compliance(
        s.ph_level, s.turbidity_ntu, s.heavy_metal_ppm,
    )

    # ── 4a. Render: Alert Banner ──────────────────────────
    # Aggregate recent anomalies into summary
    recent = list(st.session_state.anomaly_events)
    alert_summary: dict[str, tuple] = {}  # type -> (severity, count)
    for evt in recent[-50:]:  # last 50 events
        typ, sev = evt[1], evt[2]
        if typ in alert_summary:
            old_sev, old_cnt = alert_summary[typ]
            alert_summary[typ] = (max(old_sev, sev), old_cnt + 1)
        else:
            alert_summary[typ] = (sev, 1)

    critical_alerts = [
        (typ, sev, cnt) for typ, (sev, cnt) in alert_summary.items() if sev >= 2
    ]
    critical_alerts.sort(key=lambda x: (-x[1], -x[2]))
    st.markdown(alert_banner(critical_alerts[:5]), unsafe_allow_html=True)

    # ── 4b. Render: WQI + WHO Badge ──────────────────────
    wqi_col, who_col = st.columns([3, 1])
    with wqi_col:
        st.plotly_chart(
            render_wqi_gauge(wqi_score, wqi_grade, wqi_color),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    with who_col:
        st.markdown(who_badge(who_status, who_details), unsafe_allow_html=True)

    # ── 4c. Render: Metric Cards (utils.theme) ────────────
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

    # ── 4d. Render: Energy Efficiency + Maintenance ────────
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

    # ── 4e. Render: Subsystem Gauges (components.charts) ──
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

_map_label = f"{cfg.name}, Thailand" if cfg.name in STATIONS else cfg.name
st.markdown(
    f'<div class="section-header">🗺 Deployment — {_map_label}</div>',
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

# ═══════════════════════════════════════════════════════════════════════════
#  Global Station Overview (renders once — all stations on one map)
# ═══════════════════════════════════════════════════════════════════════════

all_station_data = _all_stations()
if len(all_station_data) > 1:
    st.markdown(
        '<div class="section-header">🌍 Global Station Overview</div>',
        unsafe_allow_html=True,
    )

    # Collect WQI snapshots for each station (quick 5-tick sample)
    global_markers = []
    for sname, scfg in all_station_data.items():
        if sname == st.session_state.station:
            # Use live WQI from current session
            wqi_vals = [v for v in st.session_state.hist.get("wqi", deque()) if v is not None]
            wqi_avg = sum(wqi_vals) / len(wqi_vals) if wqi_vals else 50.0
        else:
            # Quick snapshot simulation
            snap_sim = HydraSimulator(config=scfg)
            snap_scores = []
            for _ in range(5):
                snap_state = snap_sim.step()
                sc, _, _ = compute_wqi(
                    snap_state.sentinel.ph_level,
                    snap_state.sentinel.turbidity_ntu,
                    snap_state.sentinel.heavy_metal_ppm,
                )
                snap_scores.append(sc)
            wqi_avg = sum(snap_scores) / len(snap_scores)

        global_markers.append({
            "name": sname,
            "lat": scfg.lat,
            "lon": scfg.lon,
            "wqi_score": wqi_avg,
        })

    st.plotly_chart(
        render_global_map(global_markers, active_name=st.session_state.station),
        use_container_width=True,
        config={"displayModeBar": False},
    )
