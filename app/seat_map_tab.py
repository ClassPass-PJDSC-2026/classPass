"""Seat map tab (ticket #26b): place infected students and see who nearby is at risk.

The seat-risk model is ``schoolsim.spatial`` (ticket #26a). Until that is merged this tab
uses the placeholder in ``schoolsim._stub_spatial`` and says so on screen.

Shared state (other tabs, e.g. the teacher log in #28, can read or set these):
    st.session_state["index_seats"]   list of seat labels of infected students, e.g. ["B3"]
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from functools import partial
from types import SimpleNamespace
from typing import Any

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from theme import COMPARTMENT_COLORS

from schoolsim.params import Param
from schoolsim.seating import (
    nearest_label,
    quick_pick,
    risk_inputs,
    seat_dims,
    seat_labels,
    toggle_seats,
)

# Fallback (value, min, max) for the two heuristic settings if params.yaml does not define them.
HEURISTIC_DEFAULTS = {
    "near_field_multiplier": (3.0, 0.0, 10.0),
    "near_field_decay_m": (1.5, 0.5, 3.0),
}
CHART_WIDTH_PX = 700  # used only to size the seat markers
CHART_HEIGHT_PX = 440


def get_spatial() -> tuple[SimpleNamespace, bool]:
    """``(model functions, is_placeholder)``: the real model if it is merged, else the stub."""
    try:
        mod = importlib.import_module("schoolsim.spatial")
        return SimpleNamespace(seat_grid=mod.seat_grid, risk_map=mod.risk_map, expected_cases=mod.expected_cases), False
    except (ImportError, AttributeError):
        from schoolsim import _stub_spatial as mod

        return SimpleNamespace(seat_grid=mod.seat_grid, risk_map=mod.risk_map, expected_cases=mod.expected_cases), True


def heuristic_setting(params: Mapping[str, Param], key: str) -> tuple[float, float, float]:
    """``(value, min, max)`` for a heuristic setting, from params.yaml when present."""
    p = params.get(key)
    return (p.value, p.min, p.max) if p is not None else HEURISTIC_DEFAULTS[key]


def marker_size(seats: np.ndarray, length_m: float, width_m: float) -> float:
    """Marker size in pixels so seats fill most of their grid cell."""
    cols, rows = seat_dims(seats)
    cell_w = CHART_WIDTH_PX * (length_m / (length_m + 0.6)) / cols * 0.8
    cell_h = CHART_HEIGHT_PX * (width_m / (width_m + 0.6)) / rows * 0.8
    return float(min(max(0.7 * min(cell_w, cell_h), 11), 34))


def build_figure(
    seats: np.ndarray,
    labels: list[str],
    risk: np.ndarray,
    infected: list[str],
    length_m: float,
    width_m: float,
) -> go.Figure:
    """Top-down room: seats coloured by infection risk, infected students marked in red."""
    is_infected = np.array([lab in infected for lab in labels])
    size = marker_size(seats, length_m, width_m)
    top = float(max(risk[~is_infected].max(initial=0.0), 0.01))
    has_infected = bool(is_infected.any())
    seat_marker: dict = {
        "symbol": "square",
        "size": size,
        "line": {"width": 1, "color": "rgba(128,128,128,0.7)"},
    }
    if has_infected:  # colour by risk only once someone is infected; otherwise a neutral grid
        seat_marker.update(
            color=risk[~is_infected],
            colorscale="YlOrRd",
            cmin=0.0,
            cmax=top,
            colorbar={
                "title": {"text": "Risk, next school day"},
                "tickformat": ".1%" if top < 0.05 else ".0%",
                "thickness": 14,
            },
        )
    else:
        seat_marker.update(color="rgba(150,160,170,0.55)")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=seats[~is_infected, 0],
            y=seats[~is_infected, 1],
            mode="markers",
            name="Seat (colour = infection risk)" if has_infected else "Seat",
            marker=seat_marker,
            customdata=np.column_stack([np.array(labels)[~is_infected], risk[~is_infected]]),
            hovertemplate="Seat %{customdata[0]}<br>Infection risk %{customdata[1]:.1%}<extra></extra>",
            selected={"marker": {"opacity": 1}},
            unselected={"marker": {"opacity": 1}},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=seats[is_infected, 0],
            y=seats[is_infected, 1],
            mode="markers+text",
            name="Infected student",
            text=["×"] * int(is_infected.sum()),
            textfont={"color": "white", "size": max(size * 0.8, 12)},
            marker={
                "symbol": "square",
                "size": size,
                "color": COMPARTMENT_COLORS["I"],
                "line": {"width": 2, "color": "rgba(60,10,0,0.9)"},
            },
            customdata=np.array(labels)[is_infected],
            hovertemplate="Seat %{customdata}<br>Infected student<extra></extra>",
            selected={"marker": {"opacity": 1}},
            unselected={"marker": {"opacity": 1}},
        )
    )
    wall = {"width": 3, "color": "rgba(128,128,128,0.9)"}
    board = {"width": 8, "color": "rgba(128,128,128,0.95)"}
    fig.add_shape(type="rect", x0=0, y0=0, x1=length_m, y1=width_m, line=wall)
    fig.add_shape(type="line", x0=0, x1=0, y0=0.25 * width_m, y1=0.75 * width_m, line=board)
    fig.add_annotation(x=-0.05, y=0.5 * width_m, text="Board", textangle=-90, showarrow=False, xanchor="right")
    fig.update_layout(
        height=CHART_HEIGHT_PX,
        margin={"l": 30, "r": 10, "t": 10, "b": 40},
        dragmode=False,
        clickmode="event+select",
        legend={"orientation": "h", "yanchor": "top", "y": -0.12, "xanchor": "left", "x": 0},
        xaxis={
            "range": [-0.5, length_m + 0.1],
            "title": "Length (m), board on the left",
            "showgrid": False,
            "zeroline": False,
        },
        yaxis={
            "range": [-0.1, width_m + 0.1],
            "title": "Width (m)",
            "showgrid": False,
            "zeroline": False,
            "scaleanchor": "x",
            "scaleratio": 1,
        },
    )
    return fig


# --- Callbacks -------------------------------------------------------------------------

def _points(state: Any) -> list[dict]:
    """Selected points from a Streamlit plotly selection state, whatever its container type."""
    if not state:
        return []
    try:
        return list(state["selection"]["points"])
    except (KeyError, TypeError):
        return []


def _on_seat_click(chart_key: str, seats: np.ndarray, labels: list[str]) -> None:
    ss = st.session_state
    clicked = [nearest_label(seats, labels, pt["x"], pt["y"]) for pt in _points(ss.get(chart_key))]
    ss["index_seats"] = toggle_seats(ss.get("index_seats", []), clicked)
    ss["seat_chart_nonce"] = ss.get("seat_chart_nonce", 0) + 1  # new chart key clears the selection


def _set_seats(seats_to_set: list[str]) -> None:
    st.session_state["index_seats"] = seats_to_set


def _pick(which: str, seats: np.ndarray, labels: list[str]) -> None:
    ss = st.session_state
    ss["seat_random_nonce"] = ss.get("seat_random_nonce", 0) + 1
    _set_seats([quick_pick(seats, labels, which, seed=ss["seat_random_nonce"])])


# --- Tab -------------------------------------------------------------------------------

def render_seat_map(profile: Mapping[str, Any], values: Mapping[str, float], params: Mapping[str, Param]) -> None:
    """Draw the Seat map tab for the sidebar's school profile."""
    ss = st.session_state
    spatial, is_placeholder = get_spatial()

    n, length_m, width_m = int(profile["class_size"]), float(profile["length_m"]), float(profile["width_m"])
    seats = spatial.seat_grid(n, length_m, width_m)
    labels = seat_labels(seats)
    ss.setdefault("seat_chart_nonce", 0)
    ss["index_seats"] = [s for s in ss.get("index_seats", []) if s in labels]  # drop seats that no longer exist

    st.warning("The near-field effect is a heuristic. Use this map to compare seats, not to predict cases.")
    if is_placeholder:
        st.caption("Placeholder seat-risk model in use until the spatial model (#26a) is merged.")
    st.caption(
        "Click a seat to mark a student as infected, and click it again to undo. "
        "Change ventilation or masks in the sidebar and press Run simulation to see the risk change."
    )

    b1, b2, b3, b4 = st.columns(4)
    b1.button("Front of room", key="seat_front", on_click=_pick, args=("front", seats, labels), width="stretch")
    b2.button("Back of room", key="seat_back", on_click=_pick, args=("back", seats, labels), width="stretch")
    b3.button("Random seat", key="seat_random", on_click=_pick, args=("random", seats, labels), width="stretch")
    b4.button("Clear", key="seat_clear", on_click=_set_seats, args=([],), width="stretch")

    st.multiselect(
        "Infected students (seats)",
        labels,
        key="index_seats",
        help="Seat labels: the letter is the row, the number is the column counted from the board.",
    )

    kappa_default, kappa_lo, kappa_hi = heuristic_setting(params, "near_field_multiplier")
    lam_default, lam_lo, lam_hi = heuristic_setting(params, "near_field_decay_m")
    with st.expander("Near-field settings (heuristic)"):
        st.caption(
            "These two numbers are team assumptions with no empirical validation. "
            "Set the multiplier to 0 to see only the well-mixed room."
        )
        ss.setdefault("near_field_kappa", float(kappa_default))
        ss.setdefault("near_field_lambda", float(lam_default))
        st.slider(
            "Near-field multiplier (extra risk right next to an infected student)",
            min_value=float(kappa_lo),
            max_value=float(kappa_hi),
            step=0.5,
            key="near_field_kappa",
            help=f"Unit: factor. Range: {kappa_lo:g}–{kappa_hi:g}. Source: team assumption (heuristic).",
        )
        st.slider(
            "Near-field decay distance (m)",
            min_value=float(lam_lo),
            max_value=float(lam_hi),
            step=0.1,
            key="near_field_lambda",
            help=f"Unit: m. Range: {lam_lo:g}–{lam_hi:g}. Source: team assumption (heuristic).",
        )

    index_ids = [labels.index(s) for s in ss["index_seats"]]
    risk = spatial.risk_map(
        seats,
        index_ids,
        **risk_inputs(profile, values),
        kappa=float(ss["near_field_kappa"]),
        lam=float(ss["near_field_lambda"]),
    )
    expected = spatial.expected_cases(risk, index_ids)

    others = np.delete(risk, index_ids) if index_ids else risk
    if index_ids and len(others):
        worst = int(np.argmax(np.where(np.isin(np.arange(n), index_ids), -1.0, risk)))
        worst_text = f"{labels[worst]} · {risk[worst]:.1%}"
    else:
        worst_text = "–"

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Expected new cases, next school day",
        f"{expected['next_day']:.2f}",
        help="Sum of every other student's infection probability for one school day.",
    )
    m2.metric(
        "Over five school days",
        f"{expected['five_days']:.1f}",
        help="Upper bound: assumes the infected students stay infectious and ignores people already infected.",
    )
    m3.metric("Highest-risk seat", worst_text, help="Seat with the highest infection probability next school day.")

    if not index_ids:
        st.info("No infected student placed yet. Click a seat on the map or use the buttons above.")

    chart_key = f"seat_chart_{ss['seat_chart_nonce']}"
    st.plotly_chart(
        build_figure(seats, labels, risk, ss["index_seats"], length_m, width_m),
        width="stretch",
        key=chart_key,
        on_select=partial(_on_seat_click, chart_key, seats, labels),
        selection_mode="points",
        config={"displayModeBar": False},
    )
    st.caption(f"{n} students, {length_m:g} × {width_m:g} m room. Relative scenario simulation, not a forecast.")
