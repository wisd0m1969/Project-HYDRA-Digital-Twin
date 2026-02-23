"""Deterministic HYDRA telemetry simulator.

Uses a seeded PRNG so every sequence is perfectly reproducible.
Sensor signals follow bounded sinusoidal curves with Gaussian noise
to approximate realistic field conditions at Doi Inthanon.

This module contains ZERO side effects.  ``step()`` is a pure
state-transition function:  (tick_n) → HydraState_n+1.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.models import AegisState, HeliosState, HydraState, SentinelState


@dataclass(frozen=True)
class StationConfig:
    """Configuration for a HYDRA deployment station."""
    name: str
    seed: int
    lat: float
    lon: float
    altitude_m: int
    irradiance_base: float = 700.0
    membrane_base: float = 85.0


STATIONS: dict[str, StationConfig] = {
    "Doi Inthanon": StationConfig(
        name="Doi Inthanon", seed=42,
        lat=18.5883, lon=98.4861, altitude_m=2565,
    ),
    "Chiang Rai": StationConfig(
        name="Chiang Rai", seed=137,
        lat=19.9105, lon=99.8406, altitude_m=580,
        irradiance_base=750.0, membrane_base=82.0,
    ),
    "Nan": StationConfig(
        name="Nan", seed=256,
        lat=18.7756, lon=100.7730, altitude_m=240,
        irradiance_base=680.0, membrane_base=88.0,
    ),
}


# ── Custom Station Factory ────────────────────────────────────────────────


def seed_from_coordinates(lat: float, lon: float) -> int:
    """Deterministic 32-bit seed from lat/lon via SHA-256."""
    key = f"{lat:.6f},{lon:.6f}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def irradiance_base_from_latitude(lat: float) -> float:
    """Estimate baseline solar irradiance from latitude (cosine model).

    Range [400, 800] W/m².  Equator=800, poles=400.
    """
    return 400.0 + 400.0 * math.cos(math.radians(abs(lat)))


def membrane_base_from_latitude(lat: float) -> float:
    """Estimate membrane baseline from latitude.

    Range [77, 90]%.  Accounts for biofouling pressure in warm climates.
    """
    return 80.0 + 10.0 * (1.0 - 0.3 * math.cos(math.radians(abs(lat))))


def build_custom_station(
    lat: float,
    lon: float,
    name: str = "",
) -> StationConfig:
    """Create a StationConfig from user-supplied coordinates.

    Pure function: ``(lat, lon, name?) → StationConfig``.
    Seed and base parameters are derived deterministically from coordinates.
    """
    if not name:
        name = f"Custom ({lat:.2f}, {lon:.2f})"
    return StationConfig(
        name=name,
        seed=seed_from_coordinates(lat, lon),
        lat=lat,
        lon=lon,
        altitude_m=0,
        irradiance_base=irradiance_base_from_latitude(lat),
        membrane_base=membrane_base_from_latitude(lat),
    )


class HydraSimulator:
    """Produces one ``HydraState`` per ``step()`` call."""

    def __init__(
        self,
        seed: int = 42,
        config: Optional[StationConfig] = None,
    ) -> None:
        self._config = config
        self._rng = random.Random(config.seed if config else seed)
        self._tick = 0
        self._irr_base = config.irradiance_base if config else 700.0
        self._mem_base = config.membrane_base if config else 85.0

    def step(self) -> HydraState:
        self._tick += 1
        t = self._tick
        now = datetime.now()
        return HydraState(
            helios=self._helios(t, now),
            aegis=self._aegis(t, now),
            sentinel=self._sentinel(t, now),
            tick=t,
        )

    # ── HELIOS ─────────────────────────────────────────────

    def _helios(self, t: int, ts: datetime) -> HeliosState:
        # Day / night cycle — period ≈ 120 ticks
        irradiance = self._irr_base + 500.0 * math.sin(2.0 * math.pi * t / 120.0)
        irradiance += self._rng.gauss(0.0, 20.0)
        irradiance = max(0.0, irradiance)

        # Desalination rate tracks irradiance with lag + noise
        desal = irradiance * 0.008 + self._rng.gauss(0.0, 0.1)

        return HeliosState(
            solar_irradiance_wm2=irradiance,
            desalination_rate_lhr=max(0.0, desal),
            timestamp=ts,
        )

    # ── AEGIS ──────────────────────────────────────────────

    def _aegis(self, t: int, ts: datetime) -> AegisState:
        # Slow maintenance cycle — period ≈ 300 ticks
        membrane = self._mem_base + 10.0 * math.sin(2.0 * math.pi * t / 300.0)
        membrane += self._rng.gauss(0.0, 1.0)

        biofouling = 100.0 - membrane + self._rng.gauss(0.0, 2.0)

        return AegisState(
            membrane_integrity_pct=membrane,
            biofouling_risk_pct=biofouling,
            quorum_quenching_active=biofouling > 20.0,
            timestamp=ts,
        )

    # ── SENTINEL ───────────────────────────────────────────

    def _sentinel(self, t: int, ts: datetime) -> SentinelState:
        fail = 0.03  # 3 % chance any probe goes offline

        ph: Optional[float] = 7.0 + 0.5 * math.sin(2.0 * math.pi * t / 80.0)
        ph += self._rng.gauss(0.0, 0.1)
        if self._rng.random() < fail:
            ph = None

        turb: Optional[float] = 2.0 + 1.5 * math.sin(2.0 * math.pi * t / 150.0)
        turb += self._rng.gauss(0.0, 0.3)
        turb = max(0.0, turb)  # NTU cannot be negative
        if self._rng.random() < fail:
            turb = None

        metal: Optional[float] = 0.005 + 0.003 * math.sin(2.0 * math.pi * t / 200.0)
        metal += self._rng.gauss(0.0, 0.001)
        metal = max(0.0, metal)  # PPM cannot be negative
        if self._rng.random() < fail:
            metal = None

        return SentinelState(
            ph_level=ph,
            turbidity_ntu=turb,
            heavy_metal_ppm=metal,
            timestamp=ts,
        )
