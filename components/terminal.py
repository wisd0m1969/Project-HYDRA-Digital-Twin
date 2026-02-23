"""GraphRAG log renderer — read-only, auto-scrolling terminal.

Accepts a sequence of reasoning-log strings and returns a single
HTML block styled by ``utils.theme.GLOBAL_CSS``.  The terminal uses
CSS ``flex-direction: column-reverse`` so the newest entries are
always visible without JavaScript-based scrolling.

Stateless:  (log_lines) → HTML string.
"""

from __future__ import annotations

import html as _html
from collections import deque
from typing import Sequence, Union


def render_graphrag_log(lines: Union[deque, Sequence[str]]) -> str:
    """Return a styled HTML terminal block from reasoning log lines.

    Lines are rendered newest-first inside a ``column-reverse`` flex
    container so the most recent entries stay pinned at the bottom
    of the visible viewport.

    All content is escaped via ``html.escape()`` to prevent injection
    of arbitrary markup through crafted log strings.
    """
    parts: list[str] = []
    for line in reversed(list(lines)):
        if "\u26a0" in line:       # ⚠
            cls = "warn"
        elif "\u2717" in line:     # ✗
            cls = "error"
        elif "\u2713" in line:     # ✓
            cls = "ok"
        else:
            cls = ""
        escaped = _html.escape(line, quote=True)
        parts.append(f'<div class="{cls}">{escaped}</div>')

    return f'<div class="graphrag-terminal">{"".join(parts)}</div>'
