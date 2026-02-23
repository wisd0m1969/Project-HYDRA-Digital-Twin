"""Immutable dataclass models enforcing physical-law boundaries.

Every state object is frozen — state transitions produce new instances,
guaranteeing referential transparency across the simulation loop.

Physical invariants enforced:
    Solar irradiance  ∈ [0, 1 400] W/m²
    Desalination rate ∈ [0, ∞) L/hr
    Membrane          ∈ [0, 100] %
    Biofouling        ∈ [0, 100] %
    pH                ∈ [0, 14]
    Turbidity         ∈ [0, ∞) NTU
    Heavy-metal       ∈ [0, ∞) PPM
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── Helpers ────────────────────────────────────────────────────────────────


def _clamp(obj: object, attr: str, lo: float, hi: float) -> None:
    """Clamp a frozen-dataclass attribute within *[lo, hi]*."""
    val = getattr(obj, attr)
    clamped = max(lo, min(hi, val))
    if clamped != val:
        object.__setattr__(obj, attr, clamped)


# ── HELIOS ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HeliosState:
    """HELIOS Solar Core — solar irradiance and desalination output."""

    solar_irradiance_wm2: float   # W/m²  ∈ [0, 1400]
    desalination_rate_lhr: float  # L/hr  ∈ [0, ∞)
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        _clamp(self, "solar_irradiance_wm2", 0.0, 1400.0)
        _clamp(self, "desalination_rate_lhr", 0.0, float("inf"))


# ── AEGIS ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AegisState:
    """AEGIS Biological Defense — membrane integrity and biofouling."""

    membrane_integrity_pct: float  # %  ∈ [0, 100]
    biofouling_risk_pct: float     # %  ∈ [0, 100]
    quorum_quenching_active: bool
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        _clamp(self, "membrane_integrity_pct", 0.0, 100.0)
        _clamp(self, "biofouling_risk_pct", 0.0, 100.0)


# ── SENTINEL ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SentinelState:
    """SENTINEL IoT Sensors — water quality telemetry.

    Any sensor field may be ``None``, indicating the probe is offline.
    The UI layer must handle this with a SENSOR OFFLINE boundary.
    """

    ph_level: Optional[float]       # ∈ [0, 14]  or None
    turbidity_ntu: Optional[float]  # NTU ∈ [0, ∞) or None
    heavy_metal_ppm: Optional[float]  # PPM ∈ [0, ∞) or None
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if self.ph_level is not None:
            _clamp(self, "ph_level", 0.0, 14.0)
        if self.turbidity_ntu is not None:
            _clamp(self, "turbidity_ntu", 0.0, float("inf"))
        if self.heavy_metal_ppm is not None:
            _clamp(self, "heavy_metal_ppm", 0.0, float("inf"))


# ── Composite ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HydraState:
    """Complete HYDRA system snapshot — one per simulation tick."""

    helios: HeliosState
    aegis: AegisState
    sentinel: SentinelState
    tick: int = 0
