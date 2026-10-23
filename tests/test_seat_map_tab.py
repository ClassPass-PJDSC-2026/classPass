"""Tests for the seat map tab's logic and chart (ticket #26b), without launching Streamlit."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
import seat_map_tab as sm
from theme import COMPARTMENT_COLORS

from schoolsim import spatial as sp
from schoolsim.params import load_params
from schoolsim.seating import seat_labels

PARAMS = load_params()


def setup_room(n=42, length=9.0, width=7.0, infected=()):
    seats = sp.seat_grid(n, length, width)
    labels = seat_labels(seats)
    idx = [labels.index(s) for s in infected]
    risk = sp.risk_map(seats, idx, q=15.0, p=0.5, t=6.0, Q=680.0, mask=1.0)
    return seats, labels, risk


# --- heuristic settings ----------------------------------------------------------------------

def test_heuristic_settings_fall_back_to_the_ticket_values_when_not_in_params():
    assert sm.heuristic_setting({}, "near_field_multiplier") == (3.0, 0.0, 10.0)
    assert sm.heuristic_setting({}, "near_field_decay_m") == (1.5, 0.5, 3.0)


def test_heuristic_settings_come_from_params_when_present():
    fake = {"near_field_decay_m": SimpleNamespace(value=2.0, min=1.0, max=4.0)}
    assert sm.heuristic_setting(fake, "near_field_decay_m") == (2.0, 1.0, 4.0)


# --- chart -----------------------------------------------------------------------------------

def test_every_student_appears_exactly_once():
    seats, labels, risk = setup_room(infected=["B3"])
    fig = sm.build_figure(seats, labels, risk, ["B3"], 9.0, 7.0)
    assert len(fig.data[0].x) + len(fig.data[1].x) == 42
    assert len(fig.data[1].x) == 1 and fig.data[1].marker.color == COMPARTMENT_COLORS["I"]


def test_infected_seats_are_not_coloured_by_risk():
    seats, labels, risk = setup_room(infected=["B3", "C5"])
    fig = sm.build_figure(seats, labels, risk, ["B3", "C5"], 9.0, 7.0)
    assert len(fig.data[0].marker.color) == 40


def test_seat_hover_shows_label_and_risk():
    seats, labels, risk = setup_room(infected=["B3"])
    fig = sm.build_figure(seats, labels, risk, ["B3"], 9.0, 7.0)
    assert "Infection risk" in fig.data[0].hovertemplate and "Seat" in fig.data[0].hovertemplate
    assert fig.data[0].customdata.shape == (41, 2)


def test_chart_with_no_infected_students_still_draws():
    seats, labels, risk = setup_room()
    fig = sm.build_figure(seats, labels, risk, [], 9.0, 7.0)
    assert len(fig.data[0].x) == 42 and len(fig.data[1].x) == 0
    assert fig.data[0].marker.colorbar.title.text is None  # no risk scale until someone is infected


def test_colour_scale_tops_out_at_the_riskiest_seat():
    seats, labels, risk = setup_room(infected=["A1"])
    fig = sm.build_figure(seats, labels, risk, ["A1"], 9.0, 7.0)
    assert fig.data[0].marker.cmax == pytest.approx(risk.max())


def test_risk_scale_appears_once_someone_is_infected():
    seats, labels, risk = setup_room(infected=["B3"])
    fig = sm.build_figure(seats, labels, risk, ["B3"], 9.0, 7.0)
    assert fig.data[0].marker.colorbar.title.text == "Risk, next school day"


def test_small_risks_get_a_decimal_on_the_scale():
    seats, labels, _ = setup_room(infected=["B3"])
    tiny = np.full(len(labels), 0.004)
    fig = sm.build_figure(seats, labels, tiny, ["B3"], 9.0, 7.0)
    assert fig.data[0].marker.colorbar.tickformat == ".1%"


def test_chart_shows_the_board_and_uses_metres_on_both_axes():
    seats, labels, risk = setup_room()
    fig = sm.build_figure(seats, labels, risk, [], 9.0, 7.0)
    assert any(a.text == "Board" for a in fig.layout.annotations)
    assert "(m)" in fig.layout.xaxis.title.text and "(m)" in fig.layout.yaxis.title.text
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.clickmode == "event+select"


@pytest.mark.parametrize("n", [5, 30, 80])
def test_marker_size_stays_readable(n):
    seats = sp.seat_grid(n, 9.0, 7.0)
    assert 11 <= sm.marker_size(seats, 9.0, 7.0) <= 34


# --- click handling --------------------------------------------------------------------------

class FakeStreamlit:
    def __init__(self, state):
        self.session_state = state


def click_on(monkeypatch, state, seats, labels, points):
    state["chart"] = {"selection": {"points": points}}
    monkeypatch.setattr(sm, "st", FakeStreamlit(state))
    sm._on_seat_click("chart", seats, labels)


def test_clicking_a_seat_marks_it_infected(monkeypatch):
    seats, labels, _ = setup_room()
    state = {"index_seats": []}
    click_on(monkeypatch, state, seats, labels, [{"x": seats[7, 0], "y": seats[7, 1]}])
    assert state["index_seats"] == [labels[7]]


def test_clicking_it_again_undoes_it(monkeypatch):
    seats, labels, _ = setup_room()
    state = {"index_seats": [labels[7]]}
    click_on(monkeypatch, state, seats, labels, [{"x": seats[7, 0], "y": seats[7, 1]}])
    assert state["index_seats"] == []


def test_clicking_several_seats_toggles_each(monkeypatch):
    seats, labels, _ = setup_room()
    state = {"index_seats": [labels[1]]}
    pts = [{"x": seats[i, 0], "y": seats[i, 1]} for i in (1, 2)]
    click_on(monkeypatch, state, seats, labels, pts)
    assert state["index_seats"] == [labels[2]]


def test_every_click_gets_a_fresh_chart_so_the_selection_clears(monkeypatch):
    seats, labels, _ = setup_room()
    state = {"index_seats": [], "seat_chart_nonce": 4}
    click_on(monkeypatch, state, seats, labels, [{"x": seats[0, 0], "y": seats[0, 1]}])
    assert state["seat_chart_nonce"] == 5


@pytest.mark.parametrize("bad_state", [None, {}, {"selection": {}}, {"selection": None}])
def test_missing_or_odd_selection_state_is_ignored(monkeypatch, bad_state):
    seats, labels, _ = setup_room()
    state = {"index_seats": ["A1"], "chart": bad_state}
    monkeypatch.setattr(sm, "st", FakeStreamlit(state))
    sm._on_seat_click("chart", seats, labels)
    assert state["index_seats"] == ["A1"]


def test_points_helper_reads_selection_objects_and_dicts():
    assert sm._points({"selection": {"points": [{"x": 1, "y": 2}]}}) == [{"x": 1, "y": 2}]
    assert sm._points(None) == [] and sm._points([]) == []
