"""Within-room seat risk (ticket #26a): who sits close to an infected student?

This is a separate, within-room view. The SEIR model assumes everyone mixes equally, so
nothing here feeds back into SEIR or the Results, Compare and Sensitivity tabs.

Equations (hours for exposure, m for distance, probabilities 0-1)::

    h_far = q * p * t * mf / Q                       per infector, well-mixed room (Wells-Riley)
    h_i   = sum_j h_far * (1 + kappa * exp(-d_ij / lam))
    P_i   = 1 - exp(-h_i)                            infection probability per school day

    q      quanta generation rate [quanta/h]
    p      breathing rate [m^3/h]
    t      exposure time [h]
    mf     mask factor in [0, 1], ``(1 - efficiency * compliance) ** 2`` [-]
    Q      ventilation airflow [m^3/h]
    d_ij   distance between student i and infected student j [m]
    kappa  near-field multiplier [-], UI range 0-10
    lam    near-field decay length [m], UI range 0.5-3

``kappa`` and ``lam`` are **team heuristics with no empirical validation** (params.yaml source:
``team_assumption``). With ``kappa = 0`` the model reduces to plain Wells-Riley and every
student who is not infected has the same risk.

Conventions:
    * Students marked infected get ``P = 0`` and are left out of ``expected_cases``.
    * Seats are ``(x along the length, y along the width)`` in metres. Low x is the front,
      next to the board.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

__all__ = ["expected_cases", "risk_map", "seat_grid"]

FIVE_DAYS = 5  # school days in the "five days" readout


def _require_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def seat_grid(n: int, length_m: float, width_m: float, margin_m: float = 0.75) -> np.ndarray:
    """Seat positions in metres, shape ``(n, 2)`` as ``(x along length, y along width)``.

    Seats fill row by row (row-major); columns run along the length, so low x is the front
    (board wall). Exactly ``n`` seats are returned, all at different positions and inside
    the room. The last row may be only partly filled.

    Args:
        n: class size [students], at least 1.
        length_m: room length [m], above 0.
        width_m: room width [m], above 0.
        margin_m: clear space kept between the walls and the seats [m]. Capped at a quarter
            of the shorter wall so small rooms still get a grid.

    Raises:
        ValueError: if ``n`` is not a whole number of at least 1, a dimension is not above
            zero, or the margin is negative.
    """
    if int(n) != n or n < 1:
        raise ValueError("n must be a whole number of at least 1")
    n = int(n)
    length_m = _require_finite("Room length", length_m)
    width_m = _require_finite("Room width", width_m)
    margin_m = _require_finite("Margin", margin_m)
    if length_m <= 0 or width_m <= 0:
        raise ValueError("Room dimensions must be above zero")
    if margin_m < 0:
        raise ValueError("Margin must not be negative")

    margin = min(margin_m, 0.25 * min(length_m, width_m))
    usable_l, usable_w = length_m - 2 * margin, width_m - 2 * margin
    cols = max(1, math.ceil(math.sqrt(n * usable_l / usable_w)))
    rows = math.ceil(n / cols)
    idx = np.arange(n)
    c, r = idx % cols, idx // cols
    x = margin + (c + 0.5) * usable_l / cols
    y = margin + (r + 0.5) * usable_w / rows
    return np.column_stack([x, y])


def _index_set(index_ids: Sequence[int], n: int) -> list[int]:
    """Sorted, de-duplicated infected seat positions, checked to lie inside ``0..n-1``."""
    index = sorted({int(i) for i in index_ids})
    if any(i < 0 or i >= n for i in index):
        raise ValueError("Infected seat is outside the room")
    return index


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
    """Infection probability ``P_i`` per seat for one school day, shape ``(n,)``.

    Any number of infected students is supported; their hazards add. Infected seats get 0.0.
    Same inputs always give the same output (no randomness).

    Args:
        seats: seat positions [m], shape ``(n, 2)``, e.g. from :func:`seat_grid`.
        index_ids: positions (row numbers of ``seats``) of the infected students.
        q: quanta generation rate [quanta/h], not negative.
        p: breathing rate [m^3/h], not negative.
        t: exposure time [h], not negative.
        Q: ventilation airflow [m^3/h], above 0.
        mask: mask factor [-] in 0-1 (not mask efficiency).
        kappa: near-field multiplier [-], not negative. Heuristic, unvalidated.
        lam: near-field decay length [m], above 0. Heuristic, unvalidated.

    Returns:
        Probabilities in [0, 1], one per seat.

    Raises:
        ValueError: on bad inputs (airflow or decay length not above zero, negative
            kappa/q/p/t, mask outside 0-1, non-finite numbers, wrong seat shape, or an
            infected seat outside the room).
    """
    seats = np.asarray(seats, dtype=float)
    if seats.ndim != 2 or seats.shape[1] != 2 or len(seats) == 0:
        raise ValueError("seats must have shape (n, 2) with at least one seat")
    q, p, t, Q, mask, kappa, lam = (
        _require_finite(name, v)
        for name, v in (("q", q), ("p", p), ("t", t), ("Q", Q), ("mask", mask), ("kappa", kappa), ("lam", lam))
    )
    if Q <= 0:
        raise ValueError("Airflow must be above zero")
    if lam <= 0:
        raise ValueError("Decay length must be above zero")
    if kappa < 0:
        raise ValueError("Near-field multiplier must not be negative")
    if q < 0 or p < 0 or t < 0:
        raise ValueError("Quanta rate, breathing rate and exposure time must not be negative")
    if not 0.0 <= mask <= 1.0:
        raise ValueError("Mask factor must be between 0 and 1")

    n = len(seats)
    index = _index_set(index_ids, n)
    if not index:
        return np.zeros(n)

    h_far = q * p * t * mask / Q
    dist = np.linalg.norm(seats[:, None, :] - seats[index][None, :, :], axis=2)  # (n, k) [m]
    hazard = h_far * (len(index) + kappa * np.exp(-dist / lam).sum(axis=1))
    prob = -np.expm1(-hazard)  # 1 - exp(-h), accurate when h is tiny
    prob[index] = 0.0
    return prob


def expected_cases(P: np.ndarray, index_ids: Sequence[int]) -> dict[str, float]:
    """Expected new cases [students] among the students who are not infected.

    ``next_day`` is the sum of their one-day probabilities. ``five_days`` is the expected
    number infected at least once in five school days, ``sum(1 - (1 - P_i) ** 5)``. It assumes
    the infected students stay in class and infectious and every day's exposure is the same,
    and it ignores onward spread from the new cases, so treat it as a rough scenario figure
    for comparing seating plans, not a forecast.

    Raises:
        ValueError: if a probability is outside 0-1 or an infected seat is outside the room.
    """
    P = np.asarray(P, dtype=float)
    if P.ndim != 1:
        raise ValueError("P must be one probability per seat")
    if P.size and (np.any(np.isnan(P)) or P.min() < 0.0 or P.max() > 1.0):
        raise ValueError("Probabilities must be between 0 and 1")
    keep = np.ones(len(P), dtype=bool)
    keep[_index_set(index_ids, len(P))] = False
    others = P[keep]
    with np.errstate(divide="ignore"):  # P == 1 gives log1p(-1) = -inf, which maps to 1 below
        five = -np.expm1(FIVE_DAYS * np.log1p(-others))
    return {"next_day": float(others.sum()), "five_days": float(five.sum())}