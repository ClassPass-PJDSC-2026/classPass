"""Sensitivity tab (ticket #13): which uncertain inputs matter, and how wide the outcomes are.

Two views, both from ``schoolsim.sensitivity``:
    Tornado   one input at a time moves from its minimum to its maximum, others at base.
    Band      Latin hypercube Monte Carlo moves every input at once; shows the 5th, 50th
              and 95th percentile of each scenario's outcome.

Scenario comparison, not a forecast. ``schoolsim.sensitivity`` needs the real engine, so
it is imported inside the functions and the tab degrades to a message without it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from theme import COMPARTMENT_COLORS, SCENARIO_COLORS

from schoolsim.engine import PROFILE_FIELDS, Backend
from schoolsim.params import Param

# metric key -> (label, display multiplier, axis title)
METRIC_INFO = {
    "attack_rate": ("Attack rate", 100.0, "Percent of students infected"),
    "peak_infectious": ("Peak infectious", 100.0, "Percent of students infectious at the peak"),
    "learner_days_lost": ("Learner-days lost", 1.0, "Learner-days lost per student"),
}
DEFAULT_N = 300
DEFAULT_SEED = 42

def with_sim_days(params: Mapping[str, Param], sim_days: float) -> dict[str, Param]:
    """Params with ``sim_days`` set to the sidebar's horizon, as ``engine_values`` does for the
    Results and Compare tabs, so all tabs simulate the same number of days."""
    out = dict(params)
    if "sim_days" in out:
        out["sim_days"] = replace(out["sim_days"], value=float(sim_days))
    return out


def param_label(param: Param) -> str:
    return f"{param.key.replace('_', ' ')} ({param.unit})" if param.unit else param.key.replace("_", " ")

@st.cache_data(show_spinner="Running the one-at-a-time analysis…")
def _tornado(profile: dict, params: dict, scenario: str, metric: str) -> tuple[pd.DataFrame, float]:
    from schoolsim import sensitivity as sens
    from schoolsim.params import base_values
    from schoolsim.scenarios import SchoolProfile

    school = SchoolProfile(**profile)
    table = sens.one_at_a_time(school, scenario, params, metric)
    base = sens._evaluate(school, scenario, base_values(params), {})[metric]
    return table, base


@st.cache_data(show_spinner="Running the Latin hypercube analysis…")
def _band(profile: dict, params: dict, n: int, seed: int) -> pd.DataFrame:
    from schoolsim import sensitivity as sens
    from schoolsim.scenarios import SchoolProfile

    return sens.latin_hypercube(SchoolProfile(**profile), params, n=n, seed=seed)

def tornado_figure(table: pd.DataFrame, base: float, metric: str, params: Mapping[str, Param]) -> go.Figure:
    """Horizontal bars from the base-case outcome to the outcome at each input's min and max."""
    _, scale, axis_title = METRIC_INFO[metric]
    labels = [param_label(params[k]) if k in params else k for k in table["param"]]
    fig = go.Figure()
    for name, value_col, metric_col, colour in (
        ("Input at minimum", "low_value", "metric_low", COMPARTMENT_COLORS["S"]),
        ("Input at maximum", "high_value", "metric_high", COMPARTMENT_COLORS["I"]),
    ):
        outcome = table[metric_col] * scale
        fig.add_trace(
            go.Bar(
                y=labels,
                x=outcome - base * scale,
                base=base * scale,
                orientation="h",
                name=name,
                marker_color=colour,
                customdata=list(zip(table[value_col], outcome, strict=True)),
                hovertemplate=(
                    "%{y}<br>input = %{customdata[0]:.4g}<br>outcome = %{customdata[1]:.2f}"
                    f"<extra>{name}</extra>"
                ),
            )
        )
    fig.add_vline(x=base * scale, line_width=1, line_dash="dot", line_color="rgba(128,128,128,0.8)")
    fig.update_layout(
        barmode="overlay",
        height=max(320, 34 * len(labels) + 120),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=axis_title,
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", y=1.08),
    )
    return fig

def band_figure(band: pd.DataFrame, metric: str, order: list[str], labels: Mapping[str, str]) -> go.Figure:
    """Median per scenario with a 5th to 95th percentile range."""
    _, scale, axis_title = METRIC_INFO[metric]
    band = band.set_index("scenario").loc[[s for s in order if s in set(band["scenario"])]]
    fig = go.Figure(
        go.Scatter(
            x=[labels.get(s, s) for s in band.index],
            y=band["median"] * scale,
            mode="markers",
            marker=dict(size=11, color=[SCENARIO_COLORS.get(s, "#7F8C9B") for s in band.index]),
            error_y=dict(
                type="data",
                symmetric=False,
                array=(band["high"] - band["median"]) * scale,
                arrayminus=(band["median"] - band["low"]) * scale,
                thickness=2,
                width=6,
            ),
            customdata=list(zip(band["low"] * scale, band["high"] * scale, strict=True)),
            hovertemplate=(
                "%{x}<br>median %{y:.2f}"
                "<br>5th to 95th: %{customdata[0]:.2f} to %{customdata[1]:.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title=axis_title,
        yaxis_rangemode="tozero",
        showlegend=False,
    )
    return fig

def render_sensitivity(
    profile: Mapping[str, Any], params: Mapping[str, Param], backend: Backend
) -> None:
    if backend.is_placeholder:
        st.info("The sensitivity analysis needs the real simulation engine, which is not available here.")
        return

    st.subheader("Sensitivity")
    st.caption(
        "Every uncertain input is varied across its plausible range from params.yaml. "
        "This shows which inputs matter and how wide the outcomes are. It is a scenario "
        "comparison, not a forecast."
    )

    active = with_sim_days(params, profile["sim_days"])
    school = {k: profile[k] for k in PROFILE_FIELDS}

    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    metric = c1.selectbox(
        "Outcome", list(METRIC_INFO), format_func=lambda m: METRIC_INFO[m][0], key="sens_metric"
    )
    scenario = c2.selectbox(
        "Scenario for the tornado", backend.ordered_ids, format_func=backend.label, key="sens_scenario"
    )
    n = c3.slider("Samples", 50, 500, DEFAULT_N, step=50, key="sens_n")
    seed = int(c4.number_input("Seed", min_value=0, value=DEFAULT_SEED, step=1, key="sens_seed"))

    try:
        table, base = _tornado(school, active, scenario, metric)
        lhs = _band(school, active, n, seed)
    except ValueError as exc:
        st.error(str(exc))
        return

    from schoolsim.sensitivity import uncertainty_band

    st.markdown(f"**One input at a time: {backend.label(scenario)}**")
    st.caption(
        "Each bar runs from the base-case outcome (dotted line) to the outcome with that input "
        "at its minimum or maximum. Longest bars matter most."
    )
    st.plotly_chart(tornado_figure(table, base, metric, active), width="stretch", key="sens_tornado")

    band = uncertainty_band(lhs, metric)
    st.markdown("**All inputs at once: every scenario**")
    st.caption(f"Median and 5th to 95th percentile over {n} Latin hypercube samples (seed {seed}).")
    st.plotly_chart(band_figure(band, metric, backend.ordered_ids, backend.labels), width="stretch", key="sens_band")

    with st.expander("Show the numbers"):
        _, scale, _ = METRIC_INFO[metric]
        shown = band.assign(
            scenario=band["scenario"].map(backend.label),
            **{c: (band[c] * scale).round(2) for c in ("low", "median", "high")},
        )
        st.dataframe(shown, hide_index=True, width="stretch")
        st.dataframe(table.round(4), hide_index=True, width="stretch")