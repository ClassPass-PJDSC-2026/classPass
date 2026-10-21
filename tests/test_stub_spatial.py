"""Sanity tests for the TEMPORARY stub seat-risk model. Delete with schoolsim/_stub_spatial.py."""

from __future__ import annotations

import time

import numpy as np
import pytest

from schoolsim import _stub_spatial as sp

INPUTS = {"q": 15.0, "p": 0.5, "t": 6.0, "Q": 680.0, "mask": 1.0}


def test_grid_has_one_seat_per_student_inside_the_room():
    seats = sp.seat_grid(42, 9.0, 7.0)
    assert seats.shape == (42, 2)
    assert (seats[:, 0] > 0).all() and (seats[:, 0] < 9.0).all()
    assert (seats[:, 1] > 0).all() and (seats[:, 1] < 7.0).all()


def test_seats_do_not_overlap():
    seats = sp.seat_grid(80, 9.0, 7.0)
    assert len({(round(x, 6), round(y, 6)) for x, y in seats}) == 80


def test_grid_is_row_major_with_columns_along_the_length():
    seats = sp.seat_grid(12, 9.0, 7.0)
    assert seats[0, 0] < seats[1, 0] and seats[0, 1] == seats[1, 1]


@pytest.mark.parametrize("n, length, width", [(0, 9, 7), (5, 0, 7), (5, 9, -1)])
def test_grid_rejects_bad_input(n, length, width):
    with pytest.raises(ValueError):
        sp.seat_grid(n, length, width)


def test_without_near_field_everyone_has_the_same_risk():
    """Ticket #26 acceptance: kappa = 0 gives equal risk for all other students."""
    seats = sp.seat_grid(42, 9.0, 7.0)
    risk = sp.risk_map(seats, [10], **INPUTS, kappa=0.0)
    others = np.delete(risk, 10)
    assert np.allclose(others, others[0]) and others[0] > 0


def test_risk_falls_with_distance_from_the_infected_student():
    seats = sp.seat_grid(42, 9.0, 7.0)
    risk = sp.risk_map(seats, [0], **INPUTS, kappa=3.0)
    dist = np.linalg.norm(seats - seats[0], axis=1)
    order = np.argsort(dist)[1:]
    assert risk[order[0]] > risk[order[-1]]
    assert np.all(np.diff(risk[order]) <= 1e-12)


def test_infected_students_have_zero_risk_and_no_one_is_negative():
    seats = sp.seat_grid(42, 9.0, 7.0)
    risk = sp.risk_map(seats, [3, 20], **INPUTS)
    assert risk[3] == 0.0 and risk[20] == 0.0 and (risk >= 0).all() and (risk <= 1).all()


def test_no_infected_students_means_no_risk():
    assert not sp.risk_map(sp.seat_grid(10, 9.0, 7.0), [], **INPUTS).any()


def test_expected_cases_rise_with_the_near_field_multiplier():
    seats = sp.seat_grid(42, 9.0, 7.0)
    cases = [sp.expected_cases(sp.risk_map(seats, [10], **INPUTS, kappa=k), [10])["next_day"] for k in (0, 2, 5, 10)]
    assert cases == sorted(cases) and cases[0] < cases[-1]


def test_expected_cases_fall_with_better_ventilation():
    seats = sp.seat_grid(42, 9.0, 7.0)
    low = sp.expected_cases(sp.risk_map(seats, [10], **{**INPUTS, "Q": 340.0}), [10])["next_day"]
    high = sp.expected_cases(sp.risk_map(seats, [10], **{**INPUTS, "Q": 1020.0}), [10])["next_day"]
    assert high < low


def test_masks_lower_expected_cases():
    seats = sp.seat_grid(42, 9.0, 7.0)
    bare = sp.expected_cases(sp.risk_map(seats, [10], **INPUTS), [10])["next_day"]
    masked = sp.expected_cases(sp.risk_map(seats, [10], **{**INPUTS, "mask": 0.5}), [10])["next_day"]
    assert masked < bare


def test_more_infected_students_mean_more_expected_cases():
    seats = sp.seat_grid(42, 9.0, 7.0)
    one = sp.expected_cases(sp.risk_map(seats, [10], **INPUTS), [10])["next_day"]
    two = sp.expected_cases(sp.risk_map(seats, [10, 30], **INPUTS), [10, 30])["next_day"]
    assert two > one


def test_five_days_is_between_one_day_and_five_times_one_day():
    seats = sp.seat_grid(42, 9.0, 7.0)
    risk = sp.risk_map(seats, [10], **INPUTS)
    e = sp.expected_cases(risk, [10])
    assert e["next_day"] < e["five_days"] <= 5 * e["next_day"] + 1e-9


@pytest.mark.parametrize(
    "kwargs",
    [{"Q": 0.0}, {"lam": 0.0}, {"kappa": -1.0}],
)
def test_bad_inputs_raise(kwargs):
    seats = sp.seat_grid(10, 9.0, 7.0)
    with pytest.raises(ValueError):
        sp.risk_map(seats, [1], **{**INPUTS, **kwargs})


def test_infected_seat_outside_the_room_raises():
    with pytest.raises(ValueError, match="outside"):
        sp.risk_map(sp.seat_grid(10, 9.0, 7.0), [10], **INPUTS)


def test_an_80_seat_room_updates_in_under_200_ms():
    seats = sp.seat_grid(80, 9.0, 7.0)
    start = time.perf_counter()
    sp.expected_cases(sp.risk_map(seats, [5, 40], **INPUTS), [5, 40])
    assert time.perf_counter() - start < 0.2
