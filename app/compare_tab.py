"""Compare tab (ticket #12): what each option buys versus what it costs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from results_tab import weekend_spans
from theme import SCENARIO_COLORS, WEEKEND_FILL

from schoolsim.compare import comparison_csv, comparison_table, format_change, tradeoff_summary
from schoolsim.engine import Backend

BETTER = "background-color: rgba(46, 160, 67, 0.28)"  # lower attack rate than baseline
WORSE = "background-color: rgba(222, 98, 73, 0.28)"
STAR = "★ "


def _name(sid: str, label_of: Callable[[str], str], recommended_id: str | None) -> str:
    return f"{STAR}{label_of(sid)}" if sid == recommended_id else label_of(sid)


def display_table(table: pd.DataFrame, label_of: Callable[[str], str], recommended_id: str | None):
    """The table shown on screen, styled: green when infections fall, red when they rise."""
    df = pd.DataFrame(
        {
            "Scenario": [_name(s, label_of, recommended_id) for s in table["scenario"]],
            "Students infected": table["attack_rate_pct"].to_numpy(),
            "Change vs baseline": [format_change(v) for v in table["change_vs_baseline_pct"]],
            "Peak infectious": table["peak_infectious_pct"].to_numpy(),
            "Learner-days lost": table["learner_days_lost"].to_numpy(),
        }
    )

    def colour(value: str) -> str:
        if value.startswith("-"):
            return BETTER
        if value.startswith("+"):
            return WORSE
        return ""

    def bold_recommended(row: pd.Series) -> list[str]:
        is_rec = recommended_id is not None and row["Scenario"].startswith(STAR)
        return ["font-weight: 700" if is_rec else ""] * len(row)

    return df.style.map(colour, subset=["Change vs baseline"]).apply(bold_recommended, axis=1)


def build_bars(table: pd.DataFrame, label_of: Callable[[str], str], recommended_id: str | None) -> go.Figure:
    """Two panels sharing the scenario axis: infections on the left, learning lost on the right."""
    names = [_name(s, label_of, recommended_id) for s in table["scenario"]]
    colours = [SCENARIO_COLORS.get(s, "#7F8C9B") for s in table["scenario"]]
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.05,
        subplot_titles=("Students infected (%)", "Learner-days lost per student (days)"),
    )
    panels = (
        (table["attack_rate_pct"], "%{x:.1f}%", lambda v: f"{v:.1f}%", 1),
        (table["learner_days_lost"], "%{x:.1f} days", lambda v: f"{v:.1f}", 2),
    )
    for series, hover, fmt, col in panels:
        fig.add_trace(
            go.Bar(
                x=series,
                y=names,
                orientation="h",
                marker={"color": colours},
                text=[fmt(v) for v in series],
                textposition="outside",
                cliponaxis=False,
                hovertemplate=f"%{{y}}: {hover}<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=col,
        )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(rangemode="tozero")
    fig.update_xaxes(range=[0, 120], title_text="% of school", row=1, col=1)
    top = max(float(table["learner_days_lost"].max()), 1.0)
    fig.update_xaxes(range=[0, top * 1.25], title_text="days per student", row=1, col=2)
    fig.update_layout(height=60 + 46 * len(names), margin={"l": 10, "r": 30, "t": 40, "b": 10}, bargap=0.35)
    return fig


def build_overlay(
    results: Mapping[str, Any],
    ordered_ids: list[str],
    label_of: Callable[[str], str],
    recommended_id: str | None,
    *,
    sim_days: int,
    school_days_per_week: int,
) -> go.Figure:
    """Infectious curve of every scenario on one chart, weekends shaded."""
    fig = go.Figure()
    for sid in ordered_ids:
        if sid not in results:
            continue
        res = results[sid]
        fig.add_trace(
            go.Scatter(
                x=res.t,
                y=[v * 100 for v in res.I],
                mode="lines",
                name=_name(sid, label_of, recommended_id),
                line={"color": SCENARIO_COLORS.get(sid, "#7F8C9B"), "width": 3.2 if sid == "baseline" else 2.2},
                hovertemplate=f"{label_of(sid)}: %{{y:.1f}}%<extra></extra>",
            )
        )
    for start, end in weekend_spans(sim_days, school_days_per_week):
        fig.add_vrect(x0=start, x1=end, fillcolor=WEEKEND_FILL, line_width=0, layer="below")
    fig.update_layout(
        hovermode="x unified",
        height=420,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        legend={"orientation": "h", "yanchor": "top", "y": -0.22, "xanchor": "left", "x": 0},
        xaxis={"title": "Day of simulation (day 0 is a Monday; shaded = weekend)", "range": [0, sim_days], "dtick": 7},
        yaxis={"title": "Students infectious (% of school)", "rangemode": "tozero", "ticksuffix": "%"},
    )
    return fig


def render_compare(
    profile: Mapping[str, Any],
    values: Mapping[str, float],
    results: Mapping[str, Any],
    backend: Backend,
    recommended_id: str | None = None,
) -> None:
    """Draw the Compare tab.

    ``recommended_id`` is the scenario chosen by the recommender (ticket #14). Pass ``None``
    until that exists; the highlight appears automatically once it is set.
    """
    ids = backend.ordered_ids
    table = comparison_table(results, ids, backend.label, backend.attendance, values)

    st.caption(
        "Fewer infections usually cost learning time. Scenarios run from least to most disruptive. "
        "Inputs come from the sidebar."
    )
    summary = tradeoff_summary(table, backend.label)
    if summary:
        st.info(summary)

    st.dataframe(
        display_table(table, backend.label, recommended_id),
        hide_index=True,
        width="stretch",
        column_config={
            "Scenario": st.column_config.TextColumn("Scenario", help="Ordered from least to most disruptive."),
            "Students infected": st.column_config.NumberColumn(
                "Students infected", format="%.1f%%", help="Share of students infected over the simulation."
            ),
            "Change vs baseline": st.column_config.TextColumn(
                "Change vs baseline",
                help="Relative change in students infected compared with face-to-face as is. "
                "Negative (green) is better.",
            ),
            "Peak infectious": st.column_config.NumberColumn(
                "Peak infectious", format="%.1f%%", help="Highest share of students infectious at one time."
            ),
            "Learner-days lost": st.column_config.NumberColumn(
                "Learner-days lost",
                format="%.1f",
                help="Days of learning lost per student: illness plus days without face-to-face class.",
            ),
        },
    )
    if recommended_id:
        st.caption(f"{STAR.strip()} marks the recommended scenario.")

    st.download_button(
        "Download comparison (CSV)",
        data=comparison_csv(table),
        file_name="scenario_comparison.csv",
        mime="text/csv",
        key="download_comparison",
    )

    st.subheader("Infections versus learning time")
    st.plotly_chart(build_bars(table, backend.label, recommended_id), width="stretch", key="compare_bars")

    st.subheader("When each scenario peaks")
    st.plotly_chart(
        build_overlay(
            results,
            ids,
            backend.label,
            recommended_id,
            sim_days=int(values["sim_days"]),
            school_days_per_week=int(values["school_days_per_week"]),
        ),
        width="stretch",
        key="compare_overlay",
    )
    st.caption("Relative scenario simulation, not a forecast.")
