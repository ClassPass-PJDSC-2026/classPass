"""TEMPORARY stand-in for the seat-risk model (ticket #26a, ``schoolsim/spatial.py``).

It exists so the seat map UI (#26b) can be built and tested before D2 merges the real
model. It follows the equations and signatures in ticket #26. The seat map uses the real
``schoolsim.spatial`` automatically as soon as it exists.

DELETE THIS FILE (and tests/test_stub_spatial.py) when #26a is merged.

Model (a heuristic, not validated):
    h_far = q * p * t * mask / Q                        per infector, well-mixed room
    h_i   = sum over infectors j of h_far * (1 + kappa * exp(-d_ij / lam))
    P_i   = 1 - exp(-h_i)                               infection probability per school day
Units: q quanta/h, p m³/h, t h, Q m³/h, distances in m. ``mask`` is the mask factor (0-1),
i.e. ``(1 - efficiency * compliance) ** 2``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def seat_grid(n: int, length_m: float, width_m: float, margin_m: float = 0.75) -> np.ndarray:
    """Seat positions in metres, shape ``(n, 2)`` as ``(x along length, y along width)``.

    Seats fill row by row; columns run along the length, so low x is the front (board wall).
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    if length_m <= 0 or width_m <= 0:
        raise ValueError("Room dimensions must be above zero")
    margin = min(margin_m, 0.25 * min(length_m, width_m))
    usable_l, usable_w = length_m - 2 * margin, width_m - 2 * margin
    cols = max(1, math.ceil(math.sqrt(n * usable_l / usable_w)))
    rows = math.ceil(n / cols)
    idx = np.arange(n)
    c, r = idx % cols, idx // cols
    x = margin + (c + 0.5) * usable_l / cols
    y = margin + (r + 0.5) * usable_w / rows
    return np.column_stack([x, y])


def risk_map(
    seats: np.ndarray,
    index_ids: Sequence[int],
    q: float,
    p: float,
    t: float,
    Q: float,
    mask: float,
    kappa: float = 3.0,
    lam: float = 1.5,
) -> np.ndarray:
    """Infection probability per seat for one school day. Infected seats get 0.0."""
    n = len(seats)
    if Q <= 0:
        raise ValueError("Airflow must be above zero")
    if lam <= 0:
        raise ValueError("Decay length must be above zero")
    if kappa < 0:
        raise ValueError("Near-field multiplier must not be negative")
    index = sorted(set(int(i) for i in index_ids))
    if any(i < 0 or i >= n for i in index):
        raise ValueError("Infected seat is outside the room")
    if not index:
        return np.zeros(n)

    h_far = q * p * t * mask / Q
    dist = np.linalg.norm(seats[:, None, :] - seats[index][None, :, :], axis=2)  # (n, k)
    hazard = h_far * (len(index) + kappa * np.exp(-dist / lam).sum(axis=1))
    prob = 1.0 - np.exp(-hazard)
    prob[index] = 0.0
    return prob


def expected_cases(P: np.ndarray, index_ids: Sequence[int]) -> dict[str, float]:
    """Expected new cases among the other students.

    ``five_days`` assumes the infected students stay infectious and ignores depletion, so it
    is an upper bound.
    """
    mask = np.ones(len(P), dtype=bool)
    mask[list(set(int(i) for i in index_ids))] = False
    others = np.asarray(P)[mask]
    return {
        "next_day": float(others.sum()),
        "five_days": float((1.0 - (1.0 - others) ** 5).sum()),
    }
