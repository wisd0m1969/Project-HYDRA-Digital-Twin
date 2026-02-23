"""Isolated, stateless UI fragments.

Every function here is a pure renderer:
    (data) → go.Figure | str

No session state mutations.  No side effects.
"""

from .charts import render_aegis_chart, render_gauge, render_helios_chart, render_sensor_chart
from .map_view import render_deployment_map
from .terminal import render_graphrag_log

__all__ = [
    "render_gauge",
    "render_helios_chart",
    "render_aegis_chart",
    "render_sensor_chart",
    "render_deployment_map",
    "render_graphrag_log",
]
