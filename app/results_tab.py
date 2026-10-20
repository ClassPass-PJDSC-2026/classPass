"""Results tab (ticket #11): KPIs and the S/E/I/R chart for one scenario."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from theme import COMPARTMENT_COLORS, COMPARTMENT_LABELS, WEEKEND_FILL, WEEKEND_LEGEND_COLOR

from schoolsim.engine import Backend
from schoolsim.metrics import kpi_summary

PERCENT = "Percent of students"
NUMBER = "Number of students"
LEVEL_NAMES = {"Elementary": "Elementary", "JHS": "JHS", "SHS": "SHS"}


# --- Formatting ------------------------------------------------------------------------

def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _kpi_texts(kpi: Mapping[str, Any]) -> dict[str, str]:
    r0 = kpi["r0_effective"]
    return {
        "attack_rate": _pct(kpi["attack_rate"]),
        "peak_infectious": _pct(kpi["peak_infectious"]),
        "peak_day": f"Day {kpi['peak_day']}",
        "learner_days_lost": f"{kpi['learner_days_lost']:.1f}",
        "r0_effective": "–" if r0 is None or r0 != r0 else f"{r0:.2f}",
    }


def _kpi_deltas(kpi: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, str | None]:
    """Change versus the baseline scenario, as short text for ``st.metric``."""
    r0, r0_base = kpi["r0_effective"], base["r0_effective"]
    r0_delta = None
    if r0 is not None and r0_base is not None and r0 == r0 and r0_base == r0_base:
        r0_delta = f"{r0 - r0_base:+.2f}"
    return {
        "attack_rate": f"{(kpi['attack_rate'] - base['attack_rate']) * 100:+.1f} pp",
        "peak_infectious": f"{(kpi['peak_infectious'] - base['peak_infectious']) * 100:+.1f} pp",
        "peak_day": f"{kpi['peak_day'] - base['peak_day']:+d} days",
        "learner_days_lost": f"{kpi['learner_days_lost'] - base['learner_days_lost']:+.1f}",
        "r0_effective": r0_delta,
    }


# --- Chart -----------------------------------------------------------------------------

def weekend_spans(sim_days: int, school_days_per_week: int) -> list[tuple[int, int]]:
    """Day ranges ``(start, end)`` with no school, for shading. Day 0 is a Monday."""
    spans = []
    start = school_days_per_week
    while start < sim_days:
        spans.append((start, min(start + (7 - school_days_per_week), sim_days)))
        start += 7
    return spans


def build_figure(
    result: Any,
    baseline: Any | None,
    *,
    mode: str,
    population: int,
    sim_days: int,
    school_days_per_week: int,
) -> go.Figure:
    """Line chart of S, E, I, R by day, with weekends shaded."""
    as_percent = mode == PERCENT

    def series(arr: np.ndarray) -> np.ndarray:
        return np.asarray(arr) * 100 if as_percent else np.round(np.asarray(arr) * population)

    hover = "%{y:.1f}%" if as_percent else "%{y:,.0f} students"
    fig = go.Figure()
    for key in ("S", "E", "I", "R"):
        fig.add_trace(
            go.Scatter(
                x=result.t,
                y=series(getattr(result, key)),
                mode="lines",
                name=COMPARTMENT_LABELS[key],
                line={"color": COMPARTMENT_COLORS[key], "width": 2.5},
                hovertemplate=f"{COMPARTMENT_LABELS[key]}: {hover}<extra></extra>",
            )
        )
    if baseline is not None:
        fig.add_trace(
            go.Scatter(
                x=baseline.t,
                y=series(baseline.I),
                mode="lines",
                name="Infectious, face-to-face as is",
                line={"color": COMPARTMENT_COLORS["I"], "width": 1.8, "dash": "dash"},
                opacity=0.6,
                hovertemplate=f"Infectious as is: {hover}<extra></extra>",
            )
        )
    for start, end in weekend_spans(sim_days, school_days_per_week):
        fig.add_vrect(x0=start, x1=end, fillcolor=WEEKEND_FILL, line_width=0, layer="below")
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name="Weekend (no school)",
            marker={"symbol": "square", "size": 12, "color": WEEKEND_LEGEND_COLOR},
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        hovermode="x unified",
        height=430,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        xaxis={"title": "Day of simulation (day 0 is a Monday)", "range": [0, sim_days], "dtick": 7},
        yaxis={
            "title": "Students (% of school)" if as_percent else "Students (number)",
            "rangemode": "tozero",
            **({"range": [0, 100], "ticksuffix": "%"} if as_percent else {}),
        },
    )
    return fig


# --- Tab -------------------------------------------------------------------------------

def render_results(
    profile: Mapping[str, Any],
    values: Mapping[str, float],
    results: Mapping[str, Any],
    backend: Backend,
) -> None:
    """Draw the Results tab for the scenario chosen in the select box."""
    st.caption(
        f"{profile['region']} · {LEVEL_NAMES.get(profile['level'], profile['level'])} · "
        f"{profile['class_size']} students per class · "
        f"room {profile['length_m']:g} × {profile['width_m']:g} × {profile['height_m']:g} m · "
        f"{profile['ach']:g} air changes/hour · {profile['session_hours']:g} h/day · "
        f"{round(profile['mask_compliance'] * 100)}% masks"
    )

    selected = st.selectbox(
        "Scenario",
        backend.scenario_ids,
        format_func=backend.label,
        key="scenario",
        help="Pick a scenario to see its results. Changes in the cards are compared with "
        "face-to-face classes as they are now.",
    )
    result = results[selected]
    show_delta = selected != "baseline" and "baseline" in results

    kpi = kpi_summary(result, backend.attendance(selected), values)
    texts = _kpi_texts(kpi)
    deltas = (
        _kpi_deltas(kpi, kpi_summary(results["baseline"], backend.attendance("baseline"), values))
        if show_delta
        else {}
    )

    cards = (
        ("attack_rate", "Students infected", "inverse", "Share of students infected over the whole simulation."),
        ("peak_infectious", "Peak infectious", "inverse", "Highest share of students infectious at one time."),
        ("peak_day", "Peak day", "normal", "Day on which the most students are infectious. Later is better."),
        (
            "learner_days_lost",
            "Learner-days lost",
            "inverse",
            "Learning days lost per student: school days missed through illness plus the learning "
            "lost on days without face-to-face class. Team assumption; see the assumptions page.",
        ),
        (
            "r0_effective",
            "Effective R0",
            "inverse",
            "Average number of students one infectious student infects when everyone is susceptible.",
        ),
    )
    for col, (key, label, color, help_text) in zip(st.columns(len(cards)), cards, strict=True):
        with col:
            st.metric(label, texts[key], delta=deltas.get(key), delta_color=color, help=help_text)

    mode = st.radio("Show students as", [PERCENT, NUMBER], horizontal=True, key="display_mode")
    enrollment = profile.get("enrollment")
    population = int(enrollment) if enrollment else int(profile["class_size"])

    fig = build_figure(
        result,
        results["baseline"] if show_delta else None,
        mode=mode,
        population=population,
        sim_days=int(values["sim_days"]),
        school_days_per_week=int(values["school_days_per_week"]),
    )
    st.plotly_chart(fig, width="stretch", key="results_chart")

    if mode == NUMBER:
        basis = "school enrollment from the regional presets" if enrollment else "one class"
        st.caption(f"Counts assume {population:,} students ({basis}), rounded to whole students.")
    st.caption("Relative scenario simulation, not a forecast.")
