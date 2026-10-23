"""Sensitivity analysis: one-at-a-time (tornado) and Latin hypercube Monte Carlo.

Scenario comparison, not a forecast. attack_rate and peak_infectious are fractions of
students (0-1); learner_days_lost is in learner-days per student.

Sampling inside each range is uniform, or log-uniform where params.yaml says so. This is a
stated assumption (docs/assumptions.md). The module reads only Param attributes (value, min,
max, distribution) and never branches on calibrated mode, so ticket #23 needs no change here.
Column names ``scenario`` and ``attack_rate`` are read by recommend.py (#14); do not rename.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, replace
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import qmc

from schoolsim.metrics import kpi_summary, school_days_in_horizon
from schoolsim.params import Param, base_values, ranges
from schoolsim.scenarios import INTERVENTION_ORDER, SCENARIOS, SchoolProfile, run_scenario
from schoolsim.seir import simulate_batch
from schoolsim.wells_riley import airflow, classroom_beta, mask_factor, room_volume

METRICS = ("attack_rate", "peak_infectious", "learner_days_lost")
OAT_COLUMNS = ["param", "low_value", "high_value", "metric_low", "metric_high", "swing"]

# params.yaml key -> SchoolProfile field, for inputs the profile (not `values`) controls.
PROFILE_KEYS = {
    "class_size": "class_size",
    "room_length": "length_m",
    "room_width": "width_m",
    "room_height": "height_m",
    "ach": "ach",
    "session_hours": "session_hours",
    "mask_compliance": "mask_compliance",
}
# Fixed for a whole simulate_batch call, so Latin hypercube holds them at their base value.
STRUCTURAL = frozenset({"sim_days", "school_days_per_week"})


def _scenario_names() -> list[str]:
    return list(INTERVENTION_ORDER) + [n for n in SCENARIOS if n not in INTERVENTION_ORDER]


def _attendance(name: str, values: Mapping[str, Any]) -> float:
    value = SCENARIOS[name].get("attendance", 1.0)
    return values[value] if isinstance(value, str) else value


def _with_profile_overrides(profile: SchoolProfile, varied: Mapping[str, float]) -> SchoolProfile:
    updates = {}
    for key, field in PROFILE_KEYS.items():
        if key in varied:
            value = varied[key]
            updates[field] = round(value) if field == "class_size" else value
    return replace(profile, **updates) if updates else profile


def _evaluate(
    profile: SchoolProfile, scenario: str, base: Mapping[str, float], varied: Mapping[str, float]
) -> dict[str, float]:
    """One scenario, one parameter set (``varied`` overrides ``base``) -> {metric: value}."""
    values = {**base, **varied}
    result = run_scenario(_with_profile_overrides(profile, varied), scenario, values)
    kpis = kpi_summary(result, _attendance(scenario, values), values)
    return {m: float(kpis[m]) for m in METRICS}


def _arr(x: Any, n: int) -> np.ndarray:
    return np.broadcast_to(np.asarray(x, dtype=np.float64), (n,)).copy()


def _scenario_inputs(
    name: str, values: Mapping[str, Any], profile_fields: Mapping[str, Any]
) -> tuple[dict[str, Any], Any]:
    """Per-sample profile fields and attendance for one scenario.

    Mirrors scenarios._apply_overrides but accepts arrays. A test checks the two agree.
    """
    eff = dict(profile_fields)
    attendance: Any = 1.0
    class_size_mult = 1.0
    for key, value in SCENARIOS[name].items():
        resolved = values[value] if isinstance(value, str) else value
        if key == "class_size_mult":
            class_size_mult = resolved
        elif key == "attendance":
            attendance = resolved
        else:
            eff[key] = resolved
    if class_size_mult != 1.0:
        eff["class_size"] = np.round(np.asarray(eff["class_size"], dtype=np.float64) * class_size_mult)
    return eff, attendance


def _evaluate_batch(
    profile: SchoolProfile, base: Mapping[str, float], columns: Mapping[str, np.ndarray]
) -> dict[str, dict[str, np.ndarray]]:
    """All scenarios for n samples -> {scenario: {metric: array of length n}}.

    ``columns`` holds n values for each varied parameter; everything else stays at base.
    One vectorised simulate_batch call per scenario (no Python loop over samples).
    """
    n = len(next(iter(columns.values())))
    values: dict[str, Any] = {**base, **{k: v for k, v in columns.items() if k not in PROFILE_KEYS}}
    profile_fields: dict[str, Any] = {f.name: getattr(profile, f.name) for f in fields(profile)}
    for key, field in PROFILE_KEYS.items():
        if key in columns:
            profile_fields[field] = np.round(columns[key]) if field == "class_size" else columns[key]

    sim_days = int(base["sim_days"])
    school_days = int(base["school_days_per_week"])
    days = school_days_in_horizon(sim_days, school_days)

    out: dict[str, dict[str, np.ndarray]] = {}
    for name in _scenario_names():
        eff, attendance = _scenario_inputs(name, values, profile_fields)
        q_air = airflow(eff["ach"], room_volume(eff["length_m"], eff["width_m"], eff["height_m"]))
        mf = mask_factor(values["mask_efficiency"], eff["mask_compliance"])
        beta = classroom_beta(
            class_size=eff["class_size"],
            quanta_rate=values["quanta_rate"],
            breathing_rate=values["breathing_rate"],
            session_hours=eff["session_hours"],
            airflow_m3h=q_air,
            mask=mf,
            infectious_attendance=values["infectious_attendance"],
        )
        sim = simulate_batch(
            beta_class=_arr(beta, n),
            community_beta=_arr(values["community_beta"], n),
            sigma=_arr(1.0 / np.asarray(values["latent_days"], dtype=np.float64), n),
            gamma=_arr(1.0 / np.asarray(values["infectious_days"], dtype=np.float64), n),
            attendance=_arr(attendance, n),
            initial_infected_frac=_arr(values["initial_infected_frac"], n),
            sim_days=sim_days,
            school_days_per_week=school_days,
        )
        lost = (
            sim["cumulative_infections"] * values["sick_days_per_case"]
            + (1.0 - attendance) * days * values["online_learning_weight"]
        )
        out[name] = {
            "attack_rate": sim["attack_rate"],
            "peak_infectious": sim["peak_infectious"],
            "learner_days_lost": _arr(lost, n),
        }
    return out


def one_at_a_time(
    profile: SchoolProfile, scenario: str, params: Mapping[str, Param], metric: str = "attack_rate"
) -> pd.DataFrame:
    """Tornado data: each in_sensitivity parameter at its min and max, others at base.

    Returns one row per parameter, sorted by swing (largest first), with columns
    param, low_value, high_value, metric_low, metric_high, swing.
    """
    if metric not in METRICS:
        raise ValueError(f"metric must be one of {METRICS}, got {metric!r}")
    bounds = ranges(params, only_sensitivity=True)
    if not bounds:
        raise ValueError("no parameters are marked in_sensitivity in params.yaml")
    base = base_values(params)
    rows = []
    for key, (lo, hi) in bounds.items():
        low = _evaluate(profile, scenario, base, {key: lo})[metric]
        high = _evaluate(profile, scenario, base, {key: hi})[metric]
        rows.append(
            {
                "param": key,
                "low_value": lo,
                "high_value": hi,
                "metric_low": low,
                "metric_high": high,
                "swing": abs(high - low),
            }
        )
    out = pd.DataFrame(rows, columns=OAT_COLUMNS)
    return out.sort_values("swing", ascending=False, kind="stable").reset_index(drop=True)


def _scale(unit: np.ndarray, param: Param, lo: float, hi: float) -> np.ndarray:
    """Map samples in [0, 1) to [lo, hi], log-uniformly when the parameter says so."""
    if param.distribution == "loguniform":
        return np.exp(np.log(lo) + unit * (np.log(hi) - np.log(lo)))
    return lo + unit * (hi - lo)


def latin_hypercube(
    profile: SchoolProfile, params: Mapping[str, Param], n: int = 300, seed: int = 42
) -> pd.DataFrame:
    """Latin hypercube Monte Carlo over the in_sensitivity parameters, all scenarios.

    sim_days and school_days_per_week are held at base (see STRUCTURAL). Returns n rows per
    scenario with columns sample_id, <param values...>, scenario, attack_rate,
    peak_infectious, learner_days_lost. The same seed gives identical output.
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    bounds = {k: b for k, b in ranges(params, only_sensitivity=True).items() if k not in STRUCTURAL}
    if not bounds:
        raise ValueError("no parameters to sample: none are marked in_sensitivity in params.yaml")
    keys = list(bounds)
    unit = qmc.LatinHypercube(d=len(keys), seed=seed).random(n)
    samples = {k: _scale(unit[:, i], params[k], *bounds[k]) for i, k in enumerate(keys)}

    results = _evaluate_batch(profile, base_values(params), samples)
    frames = [
        pd.DataFrame(
            {
                "sample_id": np.arange(n),
                **samples,
                "scenario": scenario,
                **{m: np.asarray(metrics[m]) for m in METRICS},
            }
        )
        for scenario, metrics in results.items()
    ]
    return pd.concat(frames, ignore_index=True)


def uncertainty_band(lhs: pd.DataFrame, metric: str = "attack_rate") -> pd.DataFrame:
    """5th, 50th and 95th percentile of ``metric`` per scenario, from latin_hypercube output."""
    grouped = lhs.groupby("scenario", sort=False)[metric]
    return pd.DataFrame(
        {"low": grouped.quantile(0.05), "median": grouped.median(), "high": grouped.quantile(0.95)}
    ).reset_index()