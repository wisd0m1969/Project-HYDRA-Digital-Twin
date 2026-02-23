"""Pure computation functions for HYDRA analytics features.

All functions are stateless:  (data) → result.
No side effects, no Streamlit references, no I/O.
"""

from __future__ import annotations

import csv
import io
from collections import deque
from typing import Optional, Sequence, Tuple, Union

DataSeq = Union[deque, Sequence[float]]

# ── WQI colour map ─────────────────────────────────────────────────────────

_WQI_GRADES: list[Tuple[int, str, str]] = [
    (90, "A", "#39ff14"),   # Excellent — neon green
    (70, "B", "#00f0ff"),   # Good      — neon cyan
    (50, "C", "#ffd700"),   # Fair      — neon gold
    (30, "D", "#ff8c00"),   # Poor      — neon amber
    (0,  "F", "#ff073a"),   # Critical  — neon red
]


def compute_wqi(
    ph: Optional[float],
    turbidity: Optional[float],
    heavy_metal: Optional[float],
) -> Tuple[float, str, str]:
    """Compute a 0-100 Water Quality Index from SENTINEL readings.

    Weights are re-normalised when sensors are offline (None).
    Returns ``(score, grade_letter, grade_color)``.
    """
    # Sub-index calculations  (0 = worst, 100 = best)
    components: list[Tuple[float, float]] = []  # (sub_score, weight)

    if ph is not None:
        # Optimal pH band = [6.5, 8.5].  Score degrades linearly outside.
        deviation = max(0.0, abs(ph - 7.5) - 1.0)  # 0 when inside [6.5,8.5]
        sub = max(0.0, 100.0 - deviation * 15.0)
        components.append((sub, 0.35))

    if turbidity is not None:
        # WHO ideal < 1 NTU.  Score drops linearly to 0 at 10 NTU.
        sub = max(0.0, 100.0 - turbidity * 10.0)
        components.append((sub, 0.35))

    if heavy_metal is not None:
        # WHO limit 0.01 PPM.  Score drops linearly to 0 at 0.05 PPM.
        sub = max(0.0, 100.0 - heavy_metal * 2000.0)
        components.append((sub, 0.30))

    if not components:
        return (0.0, "N/A", "#505068")

    total_weight = sum(w for _, w in components)
    score = sum(s * w for s, w in components) / total_weight
    score = max(0.0, min(100.0, score))

    for threshold, letter, color in _WQI_GRADES:
        if score >= threshold:
            return (score, letter, color)

    return (score, "F", "#ff073a")


def check_who_compliance(
    ph: Optional[float],
    turbidity: Optional[float],
    heavy_metal: Optional[float],
) -> Tuple[str, list[Tuple[str, str, str]]]:
    """Check WHO drinking water guideline compliance.

    Returns ``(status, details)`` where status is "PASS", "FAIL", or "PARTIAL".
    Details is a list of ``(parameter, value_str, result)`` tuples.
    """
    checks: list[Tuple[str, str, str]] = []

    if ph is not None:
        ok = 6.5 <= ph <= 8.5
        checks.append(("pH", f"{ph:.2f}", "PASS" if ok else "FAIL"))
    else:
        checks.append(("pH", "N/A", "OFFLINE"))

    if turbidity is not None:
        ok = turbidity < 1.0
        checks.append(("Turbidity", f"{turbidity:.2f} NTU", "PASS" if ok else "FAIL"))
    else:
        checks.append(("Turbidity", "N/A", "OFFLINE"))

    if heavy_metal is not None:
        ok = heavy_metal < 0.01
        checks.append(("Heavy Metal", f"{heavy_metal:.4f} PPM", "PASS" if ok else "FAIL"))
    else:
        checks.append(("Heavy Metal", "N/A", "OFFLINE"))

    results = [c[2] for c in checks]
    if all(r == "PASS" for r in results):
        status = "PASS"
    elif any(r == "FAIL" for r in results):
        status = "FAIL"
    else:
        status = "PARTIAL"

    return (status, checks)


def compare_stations(
    hist_a: dict[str, deque],
    hist_b: dict[str, deque],
    name_a: str,
    name_b: str,
) -> list[dict[str, str]]:
    """Compare two station histories and return delta metrics.

    Returns list of ``{metric, station_a, station_b, delta, winner}`` dicts.
    """

    def _avg(seq: deque) -> Optional[float]:
        vals = [v for v in seq if v is not None]
        return sum(vals) / len(vals) if vals else None

    metrics = [
        ("Avg Irradiance", "irradiance", "W/m²", True),    # higher is better
        ("Avg Membrane", "membrane", "%", True),             # higher is better
        ("Avg pH", "ph", "", None),                          # neutral
        ("Avg Turbidity", "turbidity", "NTU", False),        # lower is better
        ("Avg Heavy Metal", "heavy_metal", "PPM", False),    # lower is better
        ("Avg WQI", "wqi", "", True),                        # higher is better
    ]

    rows: list[dict[str, str]] = []
    for label, key, unit, higher_better in metrics:
        a_val = _avg(hist_a.get(key, deque()))
        b_val = _avg(hist_b.get(key, deque()))

        a_str = f"{a_val:.2f}" if a_val is not None else "N/A"
        b_str = f"{b_val:.2f}" if b_val is not None else "N/A"

        if a_val is not None and b_val is not None:
            delta = a_val - b_val
            delta_str = f"{delta:+.2f} {unit}"
            if higher_better is True:
                winner = name_a if delta > 0 else name_b
            elif higher_better is False:
                winner = name_a if delta < 0 else name_b
            else:
                winner = "—"
        else:
            delta_str = "—"
            winner = "—"

        rows.append({
            "metric": label,
            name_a: a_str,
            name_b: b_str,
            "delta": delta_str,
            "winner": winner,
        })

    return rows


def compute_energy_efficiency(
    desal_rate: float,
    irradiance: float,
) -> Optional[float]:
    """Compute L/kWh energy efficiency.

    Returns ``None`` during night cycle (irradiance < 10 W/m²).
    """
    if irradiance < 10.0:
        return None
    # Convert irradiance W/m² to kW (assuming 1 m² panel)
    kw = irradiance / 1000.0
    return desal_rate / kw if kw > 0 else None


def predict_maintenance(
    membrane_history: DataSeq,
    threshold: float = 80.0,
) -> Tuple[Optional[int], float, float]:
    """OLS linear regression on membrane integrity history.

    Returns ``(ticks_remaining, slope, intercept)``.
    ``ticks_remaining`` is ``None`` if slope >= 0 (improving/stable)
    or history has < 10 points.
    """
    data = [v for v in membrane_history if v is not None]
    n = len(data)

    if n < 10:
        return (None, 0.0, 0.0)

    # Simple OLS:  y = slope * x + intercept
    sx = sum(range(n))
    sy = sum(data)
    sx2 = sum(i * i for i in range(n))
    sxy = sum(i * y for i, y in enumerate(data))

    denom = n * sx2 - sx * sx
    if denom == 0:
        return (None, 0.0, data[-1] if data else 0.0)

    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n

    if slope >= 0:
        return (None, slope, intercept)

    # Project: at which future tick does the line cross threshold?
    current_x = n - 1
    current_y = slope * current_x + intercept
    if current_y <= threshold:
        return (0, slope, intercept)  # Already below threshold

    ticks_to_threshold = int((threshold - current_y) / slope)
    return (max(0, ticks_to_threshold), slope, intercept)


def build_session_summary(
    hist: dict[str, deque],
    anomaly_count: int,
    tick: int,
) -> dict[str, str]:
    """Compute session summary statistics from history deques."""

    def _avg(seq: deque) -> str:
        vals = [v for v in seq if v is not None]
        if not vals:
            return "N/A"
        return f"{sum(vals) / len(vals):.1f}"

    def _minmax(seq: deque) -> str:
        vals = [v for v in seq if v is not None]
        if not vals:
            return "N/A"
        return f"{min(vals):.1f} – {max(vals):.1f}"

    return {
        "Ticks Elapsed": str(tick),
        "Avg Irradiance": f"{_avg(hist.get('irradiance', deque()))} W/m²",
        "Irradiance Range": _minmax(hist.get("irradiance", deque())),
        "Avg Membrane": f"{_avg(hist.get('membrane', deque()))} %",
        "Avg pH": _avg(hist.get("ph", deque())),
        "Anomalies Detected": str(anomaly_count),
    }


def build_csv(hist: dict[str, deque]) -> str:
    """Build a CSV string from history deques."""
    output = io.StringIO()
    writer = csv.writer(output)

    keys = list(hist.keys())
    writer.writerow(["tick"] + keys)

    max_len = max((len(d) for d in hist.values()), default=0)
    for i in range(max_len):
        row = [i + 1]
        for k in keys:
            d = hist[k]
            row.append(d[i] if i < len(d) else "")
        writer.writerow(row)

    return output.getvalue()
