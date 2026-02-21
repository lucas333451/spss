#!/usr/bin/env python3
"""Single source of truth for scene mapping.

This module defines how (Order, Block/Round, Position) maps to (WWR, Condition).

Why:
- Both wide→long conversion and group_manifest generation must use identical mapping.
- Keeping mapping here prevents drift and makes the audit trail clearer for reviewers.

Conventions:
- Order: 1..N (currently 1..2)
- Block: 1..2 (Block1=Round1, Block2=Round2)
- Position: 1..6 within each block
- Condition: "C0" or "C1"
"""

from __future__ import annotations

from typing import Tuple

# mapping[Order][Block][Position] = (WWR, Condition)
MAPPING = {
    1: {
        1: {1: (45, "C1"), 2: (15, "C0"), 3: (75, "C1"), 4: (45, "C0"), 5: (15, "C1"), 6: (75, "C0")},
        2: {1: (45, "C0"), 2: (45, "C1"), 3: (75, "C0"), 4: (75, "C1"), 5: (15, "C0"), 6: (15, "C1")},
    },
    2: {
        1: {1: (45, "C1"), 2: (15, "C0"), 3: (75, "C1"), 4: (75, "C0"), 5: (15, "C1"), 6: (45, "C0")},
        2: {1: (15, "C0"), 2: (15, "C1"), 3: (45, "C1"), 4: (75, "C0"), 5: (45, "C0"), 6: (75, "C1")},
    },
}


def get_wwr_cond(order: int, block: int, pos: int) -> Tuple[int | float, str | None]:
    """Return (WWR, Condition) for a given order/block/position.

    Returns (nan, None) if mapping not found.
    """
    try:
        wwr, cond = MAPPING[int(order)][int(block)][int(pos)]
        return int(wwr), str(cond)
    except Exception:
        return float("nan"), None


def scene_id(wwr: int, cond: str) -> str:
    return f"WWR{int(wwr)}_{cond}"
