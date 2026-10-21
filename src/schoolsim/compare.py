"""Scenario comparison for the Compare tab (ticket #12). Pure functions, no Streamlit.

``comparison_table`` turns the results of every scenario into one row per scenario, in
disruption order (least to most disruptive), with the change in attack rate versus the
baseline. ``comparison_csv`` is what the download button serves.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pandas as pd

from schoolsim.metrics import kpi_summary

COLUMNS = (
    "scenario",
    "label",
    "attack_rate_pct",
    "change_vs_baseline_pct",
    "peak_infectious_pct",
    "peak_day",
    "learner_days_lost",
    "r0_effective",
)

CSV_HEADERS = {
    "scenario": "scenario_id",
    "label": "scenario",
    "attack_rate_pct": "attack_rate_pct",
    "change_vs_baseline_pct": "change_vs_baseline_pct",
    "peak_infectious_pct": "peak_infectious_pct",
    "peak_day": "peak_day",
    "learner_days_lost": "learner_days_lost_per_student",
    "r0_effective": "r0_effective",
}


def comparison_table(
    results: Mapping[str, Any],
    ordered_ids: Sequence[str],
    label: Callable[[str], str],
    attendance: Callable[[str], float],
    values: Mapping[str, float],
    baseline_id: str = "baseline",
) -> pd.DataFrame:
    """One row per scenario, in ``ordered_ids`` order.

    Args:
        results: ``{scenario id: SimResult}``.
        ordered_ids: scenario ids, least to most disruptive.
        label: scenario id -> display name.
        attendance: scenario id -> share of school days attended face-to-face.
        values: parameter values (see ``metrics.kpi_summary``).
        baseline_id: scenario the changes are measured against.

    Returns:
        DataFrame with ``COLUMNS``. Percent columns are 0-100. ``change_vs_baseline_pct``
        is the relative change in attack rate versus the baseline (negative is better), and
        is NaN for every row if the baseline attack rate is zero.
    """
    if baseline_id not in results:
        raise ValueError(f"Baseline scenario '{baseline_id}' is missing from the results")
    base_attack = results[baseline_id].attack_rate

    rows = []
    for sid in ordered_ids:
        if sid not in results:
            continue
        kpi = kpi_summary(results[sid], attendance(sid), values)
        change = (kpi["attack_rate"] - base_attack) / base_attack * 100 if base_attack > 0 else math.nan
        r0 = kpi["r0_effective"]
        rows.append(
            {
                "scenario": sid,
                "label": label(sid),
                "attack_rate_pct": kpi["attack_rate"] * 100,
                "change_vs_baseline_pct": change,
                "peak_infectious_pct": kpi["peak_infectious"] * 100,
                "peak_day": kpi["peak_day"],
                "learner_days_lost": kpi["learner_days_lost"],
                "r0_effective": math.nan if r0 is None else r0,
            }
        )
    return pd.DataFrame(rows, columns=list(COLUMNS))


def format_change(value: float) -> str:
    """``+12.3%`` / ``-97.5%`` / ``0.0%``; ``–`` when undefined."""
    if value is None or value != value:
        return "–"
    if abs(value) < 0.05:
        return "0.0%"
    return f"{value:+.1f}%"


def tradeoff_summary(table: pd.DataFrame, label_of: Callable[[str], str]) -> str | None:
    """One sentence on the infections-versus-learning trade-off of the most protective option.

    Returns ``None`` if there is nothing to compare (no baseline row or only one scenario).
    """
    if len(table) < 2 or "baseline" not in set(table["scenario"]):
        return None
    base = table[table["scenario"] == "baseline"].iloc[0]
    others = table[table["scenario"] != "baseline"]
    best = others.sort_values(["attack_rate_pct", "learner_days_lost"]).iloc[0]
    cut = base["attack_rate_pct"] - best["attack_rate_pct"]
    cost = best["learner_days_lost"] - base["learner_days_lost"]
    if cut <= 0:
        return "No scenario lowers the share of students infected compared with face-to-face as is."
    if cost >= 0.05:
        cost_text = f"adds {cost:.1f} learner-days lost per student"
    elif cost <= -0.05:
        cost_text = f"also cuts learner-days lost by {abs(cost):.1f} per student"
    else:
        cost_text = "leaves learner-days lost per student unchanged"
    return (
        f"The most protective option, {label_of(best['scenario']).lower()}, lowers infections by "
        f"{cut:.1f} percentage points but {cost_text}."
        if cost >= 0.05
        else f"The most protective option, {label_of(best['scenario']).lower()}, lowers infections by "
        f"{cut:.1f} percentage points and {cost_text}."
    )


def comparison_csv(table: pd.DataFrame) -> bytes:
    """CSV bytes for the download button: numeric columns, one row per scenario, UTF-8."""
    out = table[list(COLUMNS)].rename(columns=CSV_HEADERS).copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].round(4)
    return out.to_csv(index=False).encode("utf-8")
