"""Pastel header colors for lance cards and matching inventory badges."""

from __future__ import annotations

import random

# Light backgrounds with sufficient contrast for dark text.
LANCE_HEADER_PALETTE: tuple[str, ...] = (
    "#ffe4e6",  # rose
    "#ffedd5",  # orange
    "#fef9c3",  # yellow
    "#dcfce7",  # green
    "#dbeafe",  # blue
    "#e0e7ff",  # indigo
    "#f3e8ff",  # purple
    "#fce7f3",  # pink
    "#ccfbf1",  # teal
    "#cffafe",  # cyan
    "#fae8ff",  # fuchsia
    "#ecfccb",  # lime
)


def pick_lance_header_color(used_colors: set[str] | None = None) -> str:
    """Return a random palette color, preferring one not already used in the force."""
    used = used_colors or set()
    available = [c for c in LANCE_HEADER_PALETTE if c not in used]
    pool = available or list(LANCE_HEADER_PALETTE)
    return random.choice(pool)
