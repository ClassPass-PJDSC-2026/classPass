"""Outcome metrics shown on the Results tab (ticket #11).

These functions only read attributes from a ``SimResult`` (duck-typed), so they work with
the real engine and the placeholder alike.

Assumption (goes in docs/assumptions.md): learner-days lost counts school days missed to
illness plus the learning lost on days a student is not in a face-to-face class.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def school_days_in_horizon(sim_days: int, school_days_per_week: int = 5) -> int:
    """Number of face-to-face school days in ``sim_days`` days, day 0 being a Monday."""
    if sim_days <= 0:
        raise ValueError(f"sim_days must be positive, got {sim_days}")
    if not 0 < school_days_per_week <= 7:
        raise ValueError(f"school_days_per_week must be in 1-7, got {school_days_per_week}")
    return sum(1 for d in range(int(sim_days)) if d % 7 < school_days_per_week)


def learner_days_lost(
    result: Any,
    attendance: float,
    sick_days_per_case: float,
    online_weight: float,
    sim_days: int,
    school_days_per_week: int = 5,
) -> float:
    """Learner-days lost per student over the simulation.

    = cumulative_infections * sick_days_per_case
      + (1 - attendance) * school_days_in_horizon * online_weight

    Args:
        result: simulation result; ``cumulative_infections`` is the share of students
            infected (fraction of the school population, 0-1).
        attendance: share of school days a student is in a face-to-face class
            (1 face-to-face, 0.5 hybrid, 0 online).
        sick_days_per_case: school days missed per infected student (days).
        online_weight: learning lost on a non-face-to-face day, relative to a day
            missed through illness (fraction, 0-1).
        sim_days: length of the simulation (days).
        school_days_per_week: face-to-face school days per week.

    Returns:
        Learner-days lost per student (days).
    """
    if not 0.0 <= attendance <= 1.0:
        raise ValueError(f"attendance must be between 0 and 1, got {attendance}")
    if sick_days_per_case < 0 or online_weight < 0:
        raise ValueError("sick_days_per_case and online_weight must not be negative")
    days = school_days_in_horizon(sim_days, school_days_per_week)
    return float(result.cumulative_infections * sick_days_per_case + (1.0 - attendance) * days * online_weight)


def kpi_summary(result: Any, attendance: float, values: Mapping[str, float]) -> dict[str, float | int | None]:
    """The five KPIs on the Results tab, taken directly from ``result``.

    Args:
        result: simulation result.
        attendance: scenario attendance (see :func:`learner_days_lost`).
        values: parameter values keyed as in params.yaml (``sick_days_per_case``,
            ``online_learning_weight``, ``sim_days``, ``school_days_per_week``).

    Returns:
        ``attack_rate`` and ``peak_infectious`` (fractions), ``peak_day`` (day number),
        ``learner_days_lost`` (days per student) and ``r0_effective`` (``None`` if the
        result does not report it).
    """
    return {
        "attack_rate": result.attack_rate,
        "peak_infectious": result.peak_infectious,
        "peak_day": result.peak_day,
        "learner_days_lost": learner_days_lost(
            result,
            attendance,
            values["sick_days_per_case"],
            values["online_learning_weight"],
            int(values["sim_days"]),
            int(values["school_days_per_week"]),
        ),
        "r0_effective": getattr(result, "r0_effective", None),
    }
