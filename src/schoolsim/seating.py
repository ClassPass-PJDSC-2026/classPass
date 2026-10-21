"""Seat labels, click handling and inputs for the seat map (ticket #26b). Pure functions.

Seats are labelled by row and column, e.g. ``B3`` is the second row, third column. Columns
run along the room's length starting at the board wall, so column 1 is the front.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

ROW_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _ranks(values: np.ndarray) -> np.ndarray:
    """Rank of each value among the distinct values (0 for the smallest), ignoring tiny noise."""
    rounded = np.round(values, 6)
    unique = np.unique(rounded)
    return np.searchsorted(unique, rounded)


def seat_dims(seats: np.ndarray) -> tuple[int, int]:
    """``(columns, rows)`` of a seat grid."""
    return len(np.unique(np.round(seats[:, 0], 6))), len(np.unique(np.round(seats[:, 1], 6)))


def seat_labels(seats: np.ndarray) -> list[str]:
    """One label per seat, e.g. ``["A1", "A2", ..., "B1", ...]``."""
    cols = _ranks(seats[:, 0])
    rows = _ranks(seats[:, 1])
    if rows.max(initial=0) >= len(ROW_LETTERS):
        raise ValueError("Too many seat rows to label")
    return [f"{ROW_LETTERS[r]}{c + 1}" for r, c in zip(rows, cols, strict=True)]


def nearest_label(seats: np.ndarray, labels: Sequence[str], x: float, y: float) -> str:
    """Label of the seat closest to the point ``(x, y)`` in metres."""
    d = np.hypot(seats[:, 0] - x, seats[:, 1] - y)
    return labels[int(d.argmin())]


def toggle_seats(current: Sequence[str], clicked: Sequence[str]) -> list[str]:
    """Add each clicked seat if it is not infected yet, remove it if it is."""
    out = list(current)
    for label in clicked:
        if label in out:
            out.remove(label)
        else:
            out.append(label)
    return out


def quick_pick(seats: np.ndarray, labels: Sequence[str], which: str, seed: int = 0) -> str:
    """One seat chosen by position: ``front``, ``back`` (middle of that column) or ``random``."""
    if which == "random":
        return random.Random(seed).choice(list(labels))
    if which not in {"front", "back"}:
        raise ValueError(f"Unknown quick pick: {which!r}")
    x = seats[:, 0]
    column = np.flatnonzero(np.isclose(x, x.min() if which == "front" else x.max()))
    middle = column[np.argsort(seats[column, 1])][len(column) // 2]
    return labels[int(middle)]


def risk_inputs(profile: Mapping[str, Any], values: Mapping[str, float]) -> dict[str, float]:
    """Arguments for ``risk_map`` taken from the sidebar profile and params.yaml.

    Same equations as ticket #5: airflow Q = ACH x room volume, and the mask factor
    (1 - efficiency x compliance)². Swap in ``wells_riley.airflow`` and ``mask_factor`` once
    that module is merged.
    """
    volume = profile["length_m"] * profile["width_m"] * profile["height_m"]
    return {
        "q": float(values["quanta_rate"]),
        "p": float(values["breathing_rate"]),
        "t": float(profile["session_hours"]),
        "Q": float(profile["ach"] * volume),
        "mask": float((1.0 - values["mask_efficiency"] * profile["mask_compliance"]) ** 2),
    }
