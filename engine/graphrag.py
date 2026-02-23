"""Simulated 14,000-node GraphRAG autonomous reasoning engine.

Produces deterministic, context-aware reasoning traces that react
to anomaly triggers in HYDRA telemetry.  Output is formatted as
timestamped terminal log lines consumed by ``components.terminal``.

This module is a pure function of ``HydraState`` — no side effects.
"""

from __future__ import annotations

import random
from datetime import datetime

from core.models import HydraState


class GraphRAGEngine:
    """Generates reasoning log entries from a ``HydraState`` snapshot."""

    def __init__(self, seed: int = 99) -> None:
        self._rng = random.Random(seed)

    def analyze(self, state: HydraState) -> list[str]:
        """Return a list of reasoning log lines for the current tick."""
        ts = datetime.now().strftime("%H:%M:%S")
        lines: list[str] = []

        # ── Heartbeat traversal ────────────────────────────
        nodes = self._rng.randint(12, 47)
        lines.append(
            f"[{ts}] TRAVERSE neo4j://hydra/graph "
            f"→ {nodes} nodes visited  tick={state.tick}"
        )

        # ── HELIOS ─────────────────────────────────────────
        irr = state.helios.solar_irradiance_wm2
        if irr < 200:
            lines.append(
                f"[{ts}] ⚠ LOW IRRADIANCE: {irr:.0f} W/m² — night cycle detected"
            )
            lines.append(
                f"[{ts}] QUERY (HELIOS)-[:POWERS]->(DESAL) → capacity reduced"
            )
        elif irr > 1100:
            lines.append(
                f"[{ts}] PEAK SOLAR: {irr:.0f} W/m² — maximum desalination window"
            )

        # ── AEGIS ──────────────────────────────────────────
        bio = state.aegis.biofouling_risk_pct
        mem = state.aegis.membrane_integrity_pct

        if bio > 25:
            conf = self._rng.uniform(0.82, 0.97)
            lines.append(
                f"[{ts}] ⚠ BIOFOULING RISK: {bio:.1f}% exceeds threshold(25%)"
            )
            lines.append(
                f"[{ts}] INFERENCE: Engage QuorumQuenching — confidence P={conf:.2f}"
            )
            if state.aegis.quorum_quenching_active:
                lines.append(
                    f"[{ts}] ✓ QQ_STATUS: ACTIVE — suppressing biofilm AHL signals"
                )

        if mem < 80:
            lines.append(
                f"[{ts}] ⚠ MEMBRANE DEGRADATION: {mem:.1f}% — maintenance required"
            )

        # ── SENTINEL ───────────────────────────────────────
        s = state.sentinel

        if s.ph_level is None:
            lines.append(
                f"[{ts}] ✗ SENSOR FAULT: pH probe — NaN/None boundary triggered"
            )
        elif s.ph_level < 6.5 or s.ph_level > 8.5:
            chain = self._rng.randint(2, 5)
            p = self._rng.uniform(0.60, 0.92)
            lines.append(
                f"[{ts}] ⚠ pH ANOMALY: {s.ph_level:.2f} outside safe band [6.5–8.5]"
            )
            lines.append(
                f"[{ts}] CAUSAL CHAIN: {chain} nodes → mineral runoff (P={p:.2f})"
            )

        if s.turbidity_ntu is None:
            lines.append(f"[{ts}] ✗ SENSOR FAULT: turbidity probe offline")
        elif s.turbidity_ntu > 4.0:
            lines.append(
                f"[{ts}] ⚠ TURBIDITY SPIKE: {s.turbidity_ntu:.2f} NTU — "
                f"sediment event probable"
            )

        if s.heavy_metal_ppm is None:
            lines.append(f"[{ts}] ✗ SENSOR FAULT: heavy metal probe offline")
        elif s.heavy_metal_ppm > 0.01:
            lines.append(
                f"[{ts}] ⚠ HEAVY METAL: {s.heavy_metal_ppm:.4f} PPM > WHO limit"
            )

        # ── Synthesis ──────────────────────────────────────
        anomalies = sum(
            [
                irr < 200,
                bio > 25,
                mem < 80,
                s.ph_level is not None and (s.ph_level < 6.5 or s.ph_level > 8.5),
                s.turbidity_ntu is not None and s.turbidity_ntu > 4.0,
                s.heavy_metal_ppm is not None and s.heavy_metal_ppm > 0.01,
                s.ph_level is None,
                s.turbidity_ntu is None,
                s.heavy_metal_ppm is None,
            ]
        )

        if anomalies == 0:
            total = self._rng.randint(13_800, 14_200)
            lines.append(
                f"[{ts}] ✓ SYSTEM NOMINAL — all {total:,} graph nodes green"
            )
        else:
            lvl = min(anomalies, 4)
            noun = "anomaly" if anomalies == 1 else "anomalies"
            lines.append(
                f"[{ts}] SYNTHESIS: {anomalies} {noun} — escalation level {lvl}"
            )

        return lines
