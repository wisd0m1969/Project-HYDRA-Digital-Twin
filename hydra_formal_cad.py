"""Parametric 3D CAD model of Project HYDRA — zero-electricity water purifier.

Generates an OpenSCAD blueprint from Pydantic-validated physical constraints.
Every geometry function is pure: (spec) -> OpenSCADObject.

Dependencies:
    solidpython2>=2.0.0
    pydantic>=2.0.0

Usage:
    python hydra_formal_cad.py          -> writes hydra_blueprint.scad
    python -c "from hydra_formal_cad import SystemSpec; SystemSpec()"  -> validates defaults

Physical invariants enforced by Pydantic @model_validator:
    1. Conservation of Mass:  AEGIS internal volume >= HELIOS funnel volume
    2. Geometric Nesting:     AEGIS radius  <= HELIOS dish radius
    3. Stable Base:           SENTINEL base radius >= AEGIS cylinder radius

Architecture:
    HELIOS  (Top)    — Parabolic solar collection dish + graphene aerogel grid
    AEGIS   (Middle) — Threaded pressure cylinder + nanobiocatalytic membranes
    SENTINEL (Bottom) — Reservoir base + ESP32 IoT sensor ports (R=10mm)
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator
from solid2 import (
    cube,
    cylinder,
    difference,
    intersection,
    polygon,
    rotate,
    rotate_extrude,
    translate,
    union,
)

# ── Constants ──────────────────────────────────────────────────────────────
PROFILE_RESOLUTION: int = 64
SENSOR_PORT_RADIUS_MM: float = 10.0
OUTPUT_FILE: str = "hydra_blueprint.scad"


# ═══════════════════════════════════════════════════════════════════════════
#  Section 1 — Pydantic Physical Constraint Models
# ═══════════════════════════════════════════════════════════════════════════


class HeliosSpec(BaseModel, frozen=True):
    """HELIOS Solar Collection — parabolic dish with aerogel mounting grid.

    Geometry: paraboloid of revolution, y = x^2 / (4f).
    Funnel depth  h = R^2 / (4f).
    Interior volume V = pi * R^2 * h / 2  (half-paraboloid).
    """

    dish_radius: float = Field(
        default=75.0, gt=10.0, le=500.0, description="Outer dish radius [mm]"
    )
    focal_length: float = Field(
        default=50.0, gt=5.0, le=1000.0, description="Parabolic focal length [mm]"
    )
    wall_thickness: float = Field(
        default=3.0, gt=1.0, le=20.0, description="Shell wall thickness [mm]"
    )
    aerogel_grid_spacing: float = Field(
        default=10.0, gt=2.0, le=100.0, description="Aerogel rib spacing [mm]"
    )

    @field_validator("wall_thickness")
    @classmethod
    def wall_must_be_thin(cls, v: float, info) -> float:
        r = info.data.get("dish_radius", 75.0)
        if v >= r / 5.0:
            raise ValueError(
                f"wall_thickness ({v} mm) must be < dish_radius/5 ({r / 5.0:.1f} mm)"
            )
        return v

    @computed_field
    @property
    def funnel_height(self) -> float:
        """Dish depth: h = R^2 / (4f) [mm]."""
        return self.dish_radius**2 / (4.0 * self.focal_length)

    @computed_field
    @property
    def funnel_volume_ml(self) -> float:
        """Interior capacity: V = pi * R^2 * h / 2 / 1000 [mL]."""
        return math.pi * self.dish_radius**2 * self.funnel_height / 2.0 / 1000.0


class AegisSpec(BaseModel, frozen=True):
    """AEGIS Membrane Filtration — threaded pressure cylinder with internal layers.

    Internal volume: V = pi * (r - t)^2 * h.
    Screw threads modeled as additive annular ribs on the exterior wall.
    """

    cylinder_radius: float = Field(
        default=70.0, gt=10.0, le=400.0, description="Outer cylinder radius [mm]"
    )
    height: float = Field(
        default=120.0, gt=20.0, le=500.0, description="Cylinder height [mm]"
    )
    wall_thickness: float = Field(
        default=3.0, gt=1.0, le=20.0, description="Wall thickness [mm]"
    )
    membrane_layers: int = Field(
        default=3, ge=1, le=10, description="Number of internal membrane discs"
    )
    thread_pitch: float = Field(
        default=4.0, gt=1.0, le=20.0, description="Screw thread pitch [mm]"
    )
    thread_depth: float = Field(
        default=1.5, gt=0.5, le=5.0, description="Thread rib depth [mm]"
    )
    pressure_rating_bar: float = Field(
        default=2.0, gt=0.0, le=10.0, description="Design pressure [bar]"
    )

    @field_validator("thread_depth")
    @classmethod
    def thread_within_wall(cls, v: float, info) -> float:
        t = info.data.get("wall_thickness", 3.0)
        if v >= t:
            raise ValueError(
                f"thread_depth ({v} mm) must be < wall_thickness ({t} mm)"
            )
        return v

    @computed_field
    @property
    def internal_volume_ml(self) -> float:
        """pi * (r - t)^2 * h / 1000 [mL]."""
        inner_r = self.cylinder_radius - self.wall_thickness
        return math.pi * inner_r**2 * self.height / 1000.0


class SentinelSpec(BaseModel, frozen=True):
    """SENTINEL IoT Sensor Base — reservoir with radial ESP32 sensor ports.

    Reservoir volume = gross interior minus sensor-port penetration losses.
    Port radius is fixed at 10mm per hardware specification.
    """

    base_radius: float = Field(
        default=80.0, gt=20.0, le=500.0, description="Outer base radius [mm]"
    )
    height: float = Field(
        default=60.0, gt=20.0, le=300.0, description="Base height [mm]"
    )
    wall_thickness: float = Field(
        default=4.0, gt=2.0, le=25.0, description="Wall thickness [mm]"
    )
    sensor_port_radius: float = Field(
        default=SENSOR_PORT_RADIUS_MM,
        description="Sensor port hole radius [mm] — fixed at 10mm",
    )
    num_ports: int = Field(
        default=6, ge=1, le=12, description="Number of radial sensor ports"
    )

    @field_validator("num_ports")
    @classmethod
    def ports_fit_circumference(cls, v: int, info) -> int:
        r = info.data.get("base_radius", 80.0)
        port_r = info.data.get("sensor_port_radius", SENSOR_PORT_RADIUS_MM)
        min_circ = v * 2.0 * port_r * 1.2
        actual_circ = 2.0 * math.pi * r
        if min_circ > actual_circ:
            raise ValueError(
                f"{v} ports need {min_circ:.1f} mm circumference, "
                f"base provides only {actual_circ:.1f} mm"
            )
        return v

    @computed_field
    @property
    def reservoir_volume_ml(self) -> float:
        """(pi * r_inner^2 * h - port_losses) / 1000 [mL]."""
        inner_r = self.base_radius - self.wall_thickness
        gross = math.pi * inner_r**2 * self.height
        port_loss = (
            self.num_ports * math.pi * self.sensor_port_radius**2 * self.wall_thickness
        )
        return (gross - port_loss) / 1000.0


class SystemSpec(BaseModel, frozen=True):
    """Complete HYDRA assembly — cross-subsystem physics enforcement.

    Three algebraic invariants must hold simultaneously:
        1. Conservation of Mass:  AEGIS internal volume >= HELIOS funnel volume
        2. Geometric Nesting:     AEGIS radius <= HELIOS dish radius
        3. Stable Base:           SENTINEL base radius >= AEGIS cylinder radius

    Violation of any invariant raises a formal ValidationError.
    """

    helios: HeliosSpec = Field(default_factory=HeliosSpec)
    aegis: AegisSpec = Field(default_factory=AegisSpec)
    sentinel: SentinelSpec = Field(default_factory=SentinelSpec)

    @model_validator(mode="after")
    def enforce_physics(self) -> Self:
        # Invariant 1 — Conservation of Mass (flow capacity)
        if self.aegis.internal_volume_ml < self.helios.funnel_volume_ml:
            raise ValueError(
                f"Conservation of Mass violated: "
                f"AEGIS volume ({self.aegis.internal_volume_ml:.1f} mL) < "
                f"HELIOS funnel ({self.helios.funnel_volume_ml:.1f} mL)"
            )
        # Invariant 2 — Geometric Nesting (AEGIS fits inside HELIOS footprint)
        if self.aegis.cylinder_radius > self.helios.dish_radius:
            raise ValueError(
                f"Geometric Nesting violated: "
                f"AEGIS radius ({self.aegis.cylinder_radius} mm) > "
                f"HELIOS dish ({self.helios.dish_radius} mm)"
            )
        # Invariant 3 — Stable Base (SENTINEL wider than AEGIS)
        if self.sentinel.base_radius < self.aegis.cylinder_radius:
            raise ValueError(
                f"Stable Base violated: "
                f"SENTINEL radius ({self.sentinel.base_radius} mm) < "
                f"AEGIS radius ({self.aegis.cylinder_radius} mm)"
            )
        return self


# ═══════════════════════════════════════════════════════════════════════════
#  Section 2 — Pure Functional Geometry (solidpython2)
# ═══════════════════════════════════════════════════════════════════════════


def _parabolic_profile(
    radius: float,
    focal_length: float,
    n_points: int = PROFILE_RESOLUTION,
) -> list[list[float]]:
    """Generate 2D cross-section polygon for rotate_extrude.

    Returns points tracing the filled paraboloid cross-section in the
    positive-X half-plane: axis origin -> parabolic curve -> rim base -> close.

    The profile satisfies y = x^2 / (4f), with x in [0, radius].
    """
    curve: list[list[float]] = []
    for i in range(n_points + 1):
        x = radius * i / n_points
        y = x**2 / (4.0 * focal_length)
        curve.append([x, y])
    # Close polygon along the base back to origin
    curve.append([radius, 0.0])
    curve.append([0.0, 0.0])
    return curve


def build_helios(spec: HeliosSpec):
    """HELIOS parabolic dish with internal aerogel mounting grid.

    Pure function: (HeliosSpec) -> OpenSCADObject.

    Construction:
        1. Outer paraboloid shell via rotate_extrude of parabolic polygon
        2. Inner cavity (offset inward + upward by wall thickness)
        3. Boolean difference -> hollow dish
        4. Aerogel grid: radial ribs + concentric rings, clipped to interior
    """
    R = spec.dish_radius
    f = spec.focal_length
    t = spec.wall_thickness
    h = spec.funnel_height

    # ── Outer shell ────────────────────────────────────────
    outer_pts = _parabolic_profile(R, f)
    outer = rotate_extrude(angle=360)(polygon(points=outer_pts))

    # ── Inner cavity (wall-thickness offset) ───────────────
    inner_R = R - t
    inner_pts: list[list[float]] = []
    for i in range(PROFILE_RESOLUTION + 1):
        x = inner_R * i / PROFILE_RESOLUTION
        y = x**2 / (4.0 * f) + t  # shifted up by wall thickness
        inner_pts.append([x, y])
    inner_pts.append([inner_R, 0.0])
    inner_pts.append([0.0, 0.0])
    inner = rotate_extrude(angle=360)(polygon(points=inner_pts))

    dish = outer - inner

    # ── Aerogel grid (radial ribs + concentric rings) ──────
    grid_parts = []
    rib_thickness = 1.0  # mm

    # Radial ribs — thin walls from center outward
    n_ribs = max(4, int(360.0 / (spec.aerogel_grid_spacing * 2)))
    for i in range(n_ribs):
        angle = i * (360.0 / n_ribs)
        rib = translate([0, -rib_thickness / 2, t])(
            cube([inner_R, rib_thickness, h])
        )
        rib = rotate([0, 0, angle])(rib)
        grid_parts.append(rib)

    # Concentric rings — annular cylinders at grid spacing intervals
    n_rings = max(1, int(inner_R / spec.aerogel_grid_spacing))
    for i in range(1, n_rings + 1):
        ring_r = spec.aerogel_grid_spacing * i
        if ring_r >= inner_R:
            break
        ring = cylinder(r=ring_r + 0.5, h=h) - cylinder(r=ring_r - 0.5, h=h + 0.1)
        ring = translate([0, 0, t])(ring)
        grid_parts.append(ring)

    # Clip grid to interior cavity shape
    if grid_parts:
        raw_grid = union()(*grid_parts)
        clip_volume = rotate_extrude(angle=360)(
            polygon(points=_parabolic_profile(inner_R, f))
        )
        clip_volume = translate([0, 0, t])(clip_volume)
        trimmed_grid = intersection()(raw_grid, clip_volume)
        dish = dish + trimmed_grid

    return dish


def build_aegis(spec: AegisSpec):
    """AEGIS membrane pressure cylinder with screw threads and internal layers.

    Pure function: (AegisSpec) -> OpenSCADObject.

    Construction:
        1. Hollow cylinder (outer - inner)
        2. Additive annular thread ribs on exterior wall
        3. Internal membrane discs at equal spacing
    """
    R = spec.cylinder_radius
    h = spec.height
    t = spec.wall_thickness
    td = spec.thread_depth
    tp = spec.thread_pitch

    # ── Hollow cylinder body ───────────────────────────────
    outer = cylinder(r=R, h=h)
    inner = cylinder(r=R - t, h=h + 1)  # +1 for clean subtraction
    body = outer - inner

    # ── External screw threads (additive annular ribs) ─────
    thread_parts = []
    z = tp * 0.25  # offset start slightly from base
    while z < h - tp * 0.25:
        rib = translate([0, 0, z])(
            cylinder(r=R + td, h=tp * 0.4) - cylinder(r=R, h=tp * 0.4 + 0.1)
        )
        thread_parts.append(rib)
        z += tp
    if thread_parts:
        body = body + union()(*thread_parts)

    # ── Internal membrane layers (thin discs) ──────────────
    layer_spacing = h / (spec.membrane_layers + 1)
    membrane_parts = []
    for i in range(1, spec.membrane_layers + 1):
        z_pos = layer_spacing * i
        disc = translate([0, 0, z_pos])(cylinder(r=R - t - 0.5, h=1.0))
        membrane_parts.append(disc)
    if membrane_parts:
        body = body + union()(*membrane_parts)

    return body


def build_sentinel(spec: SentinelSpec):
    """SENTINEL IoT base reservoir with radially distributed sensor port holes.

    Pure function: (SentinelSpec) -> OpenSCADObject.

    Construction:
        1. Hollow cylinder with solid floor (wall_thickness thick)
        2. Horizontal cylindrical port holes through the wall at mid-height
    """
    R = spec.base_radius
    h = spec.height
    t = spec.wall_thickness
    pr = spec.sensor_port_radius

    # ── Hollow base with solid floor ───────────────────────
    outer = cylinder(r=R, h=h)
    inner = translate([0, 0, t])(cylinder(r=R - t, h=h - t + 1))
    body = outer - inner

    # ── Sensor port holes (radially distributed) ───────────
    angle_step = 360.0 / spec.num_ports
    port_parts = []
    for i in range(spec.num_ports):
        angle = i * angle_step
        # Horizontal cylinder penetrating the wall at mid-height
        port = cylinder(r=pr, h=t + 4)
        port = rotate([0, 90, 0])(port)
        port = translate([R - t - 2, 0, h / 2.0])(port)
        port = rotate([0, 0, angle])(port)
        port_parts.append(port)

    if port_parts:
        body = body - union()(*port_parts)

    return body


def assemble_hydra(helios_geom, aegis_geom, sentinel_geom, spec: SystemSpec):
    """Stack all three subsystems on the Z-axis.

    Pure function: (geom, geom, geom, SystemSpec) -> OpenSCADObject.

    Layout:
        z = 0                       : SENTINEL base (bottom)
        z = sentinel.height         : AEGIS cylinder (middle)
        z = sentinel.height + aegis.height : HELIOS dish (top)
    """
    z_aegis = spec.sentinel.height
    z_helios = spec.sentinel.height + spec.aegis.height

    return (
        sentinel_geom
        + translate([0, 0, z_aegis])(aegis_geom)
        + translate([0, 0, z_helios])(helios_geom)
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Section 3 — Main: Validate Physics & Export Blueprint
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # ── 1. Instantiate models — Pydantic validates all physics ──
    system = SystemSpec()

    # ── 2. Print formal validation proof ────────────────────────
    h = system.helios
    a = system.aegis
    s = system.sentinel

    print("=" * 64)
    print("  PROJECT HYDRA — Formal CAD Blueprint Generator")
    print("  Level 6 Physical Architecture | solidpython2 + Pydantic v2")
    print("=" * 64)

    print(f"\n  HELIOS  (Solar Collection Dish)")
    print(f"    dish_radius       = {h.dish_radius} mm")
    print(f"    focal_length      = {h.focal_length} mm")
    print(f"    wall_thickness    = {h.wall_thickness} mm")
    print(f"    aerogel_spacing   = {h.aerogel_grid_spacing} mm")
    print(f"    funnel_height     = {h.funnel_height:.2f} mm  [R^2/(4f)]")
    print(f"    funnel_volume     = {h.funnel_volume_ml:.1f} mL  [piR^2h/2]")

    print(f"\n  AEGIS  (Membrane Pressure Cylinder)")
    print(f"    cylinder_radius   = {a.cylinder_radius} mm")
    print(f"    height            = {a.height} mm")
    print(f"    wall_thickness    = {a.wall_thickness} mm")
    print(f"    membrane_layers   = {a.membrane_layers}")
    print(f"    thread_pitch      = {a.thread_pitch} mm")
    print(f"    thread_depth      = {a.thread_depth} mm")
    print(f"    pressure_rating   = {a.pressure_rating_bar} bar")
    print(f"    internal_volume   = {a.internal_volume_ml:.1f} mL  [pi(r-t)^2h]")

    print(f"\n  SENTINEL  (IoT Sensor Base)")
    print(f"    base_radius       = {s.base_radius} mm")
    print(f"    height            = {s.height} mm")
    print(f"    wall_thickness    = {s.wall_thickness} mm")
    print(f"    sensor_port_r     = {s.sensor_port_radius} mm  [FIXED]")
    print(f"    num_ports         = {s.num_ports}")
    print(f"    reservoir_volume  = {s.reservoir_volume_ml:.1f} mL")

    print(f"\n  {'─' * 56}")
    print(f"  Physics Invariant Validation:")
    print(
        f"    [PASS] Mass Conservation  : "
        f"{a.internal_volume_ml:.1f} mL >= {h.funnel_volume_ml:.1f} mL"
    )
    print(
        f"    [PASS] Geometric Nesting  : "
        f"{a.cylinder_radius} mm <= {h.dish_radius} mm"
    )
    print(
        f"    [PASS] Stable Base        : "
        f"{s.base_radius} mm >= {a.cylinder_radius} mm"
    )

    # ── 3. Build geometry via pure functions ─────────────────────
    helios_geom = build_helios(system.helios)
    aegis_geom = build_aegis(system.aegis)
    sentinel_geom = build_sentinel(system.sentinel)

    assembly = assemble_hydra(helios_geom, aegis_geom, sentinel_geom, system)

    # ── 4. Export to OpenSCAD ────────────────────────────────────
    output_path = Path(__file__).parent / OUTPUT_FILE
    assembly.save_as_scad(str(output_path))

    total_h = s.height + a.height + h.funnel_height
    print(f"\n  Assembly total height: {total_h:.1f} mm")
    print(f"  Exported -> {output_path}")
    print("=" * 64)
