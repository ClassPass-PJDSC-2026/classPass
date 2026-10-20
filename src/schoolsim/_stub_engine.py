"""TEMPORARY stand-in for the real engine (#5 wells_riley, #6 seir, #9 scenarios).

It exists only so the Streamlit UI (#10, #11) can be built and tested before D1 merges
the real engine. It implements the same equations as the tickets, so numbers should be
close, but it is not validated. ``schoolsim.engine`` uses the real engine automatically
as soon as ``schoolsim.scenarios`` exports ``SCENARIOS``, ``LABELS``, ``SchoolProfile``
and ``run_all``.

DELETE THIS FILE (and tests/test_stub_engine.py) when #5, #6 and #9 are merged.

Units: hours for Wells-Riley, days for SEIR, m³, m³/h, quanta/h. Compartments S, E, I, R
are fractions of the school population (they sum to 1).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

STEPS_PER_DAY = 20  # RK4 step dt = 0.05 day


@dataclass(frozen=True, eq=False)
class SimResult:
    """One simulation. ``t`` and S/E/I/R have one sample per day, day 0 to sim_days."""

    t: np.ndarray
    S: np.ndarray
    E: np.ndarray
    I: np.ndarray  # noqa: E741
    R: np.ndarray
    attack_rate: float  # share of the school infected during the run (fraction)
    peak_infectious: float  # highest share infectious at one time (fraction)
    peak_day: int  # day on which the peak occurs
    cumulative_infections: float  # new infections as a fraction of the school population
    r0_effective: float  # baseline-style effective R0 for this scenario


@dataclass(frozen=True)
class SchoolProfile:
    class_size: int
    length_m: float
    width_m: float
    height_m: float
    ach: float
    session_hours: float
    mask_compliance: float


SCENARIOS: dict[str, dict] = {
    "baseline": {},
    "better_ventilation": {"ach": "ach_good"},
    "smaller_classes": {"class_size_mult": 0.67},
    "masks": {"mask_compliance": 0.8},
    "combined": {"ach": "ach_good", "mask_compliance": 0.8},
    "hybrid": {"class_size_mult": 0.5, "attendance": 0.5},
    "online": {"attendance": 0.0},
}

LABELS: dict[str, str] = {
    "baseline": "Face-to-face, as is",
    "better_ventilation": "Face-to-face, better ventilation",
    "smaller_classes": "Smaller classes",
    "masks": "Face-to-face, masks",
    "combined": "Face-to-face, ventilation + masks",
    "hybrid": "Hybrid, A/B cohorts",
    "online": "Online classes",
}


def _rk4_step(state, beta, sigma, gamma, dt):
    def f(s):
        S, E, I, _ = s  # noqa: E741
        lam = beta * I * S
        return (-lam, lam - sigma * E, sigma * E - gamma * I, gamma * I)

    def add(s, k, h):
        return tuple(a + h * b for a, b in zip(s, k, strict=True))

    k1 = f(state)
    k2 = f(add(state, k1, dt / 2))
    k3 = f(add(state, k2, dt / 2))
    k4 = f(add(state, k3, dt))
    return tuple(
        a + dt / 6 * (b + 2 * c + 2 * d + e)
        for a, b, c, d, e in zip(state, k1, k2, k3, k4, strict=True)
    )


def run_scenario(profile: SchoolProfile, name: str, values: Mapping[str, float]) -> SimResult:
    """Run one scenario. ``values`` maps parameter keys (params.yaml) to numbers."""
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {name}")
    spec = SCENARIOS[name]

    n = max(1, round(profile.class_size * spec.get("class_size_mult", 1.0)))
    ach = profile.ach
    if "ach" in spec:
        ach = max(ach, values[spec["ach"]])
    mask = max(profile.mask_compliance, spec.get("mask_compliance", 0.0))
    attendance = spec.get("attendance", 1.0)

    if ach <= 0:
        raise ValueError("Air changes per hour must be above zero.")
    volume = profile.length_m * profile.width_m * profile.height_m
    if volume <= 0:
        raise ValueError("Room dimensions must be above zero.")

    airflow = ach * volume  # m³/h
    mask_factor = (1 - values["mask_efficiency"] * mask) ** 2
    beta_class = (
        n
        * values["infectious_attendance"]
        * values["quanta_rate"]
        * values["breathing_rate"]
        * profile.session_hours
        * mask_factor
        / airflow
    )  # per school day
    beta_comm = values["community_beta"]
    sigma = 1 / values["latent_days"]
    gamma = 1 / values["infectious_days"]
    school_days = int(values["school_days_per_week"])
    days = int(values["sim_days"])
    i0 = values["initial_infected_frac"]

    state = (1 - i0, 0.0, i0, 0.0)
    samples = [state]
    dt = 1 / STEPS_PER_DAY
    for d in range(days):
        beta = (d % 7 < school_days) * attendance * beta_class + beta_comm
        for _ in range(STEPS_PER_DAY):
            state = _rk4_step(state, beta, sigma, gamma, dt)
        samples.append(state)

    arr = np.clip(np.array(samples), 0.0, 1.0)
    S, E, I, R = (arr[:, i] for i in range(4))  # noqa: E741
    new_infections = float((1 - i0) - S[-1])
    r0 = ((school_days / 7) * attendance * beta_class + beta_comm) / gamma
    return SimResult(
        t=np.arange(days + 1, dtype=float),
        S=S,
        E=E,
        I=I,
        R=R,
        attack_rate=new_infections,
        peak_infectious=float(I.max()),
        peak_day=int(I.argmax()),
        cumulative_infections=new_infections,
        r0_effective=float(r0) if math.isfinite(r0) else float("nan"),
    )


def run_all(profile: SchoolProfile, values: Mapping[str, float]) -> dict[str, SimResult]:
    """Run every scenario with identical non-scenario parameters."""
    return {name: run_scenario(profile, name, values) for name in SCENARIOS}
