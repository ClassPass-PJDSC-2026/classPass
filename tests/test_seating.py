"""Tests for schoolsim.seating (ticket #26b helpers)."""

from __future__ import annotations

import numpy as np
import pytest

from schoolsim import spatial as sp
from schoolsim.params import base_values, load_params
from schoolsim.seating import (
    nearest_label,
    quick_pick,
    risk_inputs,
    seat_dims,
    seat_labels,
    toggle_seats,
)

VALUES = base_values(load_params())


def grid(n=42, length=9.0, width=7.0):
    seats = sp.seat_grid(n, length, width)
    return seats, seat_labels(seats)


def test_one_unique_label_per_seat():
    for n in (1, 5, 30, 42, 80):
        seats, labels = grid(n)
        assert len(labels) == n and len(set(labels)) == n


def test_labels_run_row_by_row_from_the_board():
    seats, labels = grid(42)
    cols, _ = seat_dims(seats)
    assert labels[0] == "A1" and labels[1] == "A2"
    assert labels[cols] == "B1"  # second row, first column


def test_partial_last_row_is_labelled():
    seats, labels = grid(10)
    cols, rows = seat_dims(seats)
    assert cols * rows >= 10 and labels[-1][0] == "ABCDEFGHIJ"[rows - 1]


def test_seat_dims_match_the_grid():
    seats, _ = grid(42)
    cols, rows = seat_dims(seats)
    assert (rows - 1) * cols < 42 <= rows * cols  # only the last row may be partly empty


def test_nearest_label_finds_the_exact_seat():
    seats, labels = grid(42)
    for i in (0, 17, 41):
        assert nearest_label(seats, labels, seats[i, 0], seats[i, 1]) == labels[i]


def test_nearest_label_tolerates_small_offsets():
    seats, labels = grid(42)
    assert nearest_label(seats, labels, seats[5, 0] + 0.1, seats[5, 1] - 0.1) == labels[5]


def test_toggle_adds_removes_and_keeps_order():
    assert toggle_seats([], ["B3"]) == ["B3"]
    assert toggle_seats(["B3"], ["B3"]) == []
    assert toggle_seats(["B3", "C1"], ["B3", "D2"]) == ["C1", "D2"]


def test_toggle_does_not_change_its_input():
    current = ["A1"]
    toggle_seats(current, ["B2"])
    assert current == ["A1"]


def test_front_and_back_picks_are_in_the_first_and_last_column():
    seats, labels = grid(42)
    cols, _ = seat_dims(seats)
    assert labels.index(quick_pick(seats, labels, "front")) % cols == 0
    assert labels.index(quick_pick(seats, labels, "back")) % cols == cols - 1


def test_front_pick_is_towards_the_middle_of_the_column():
    seats, labels = grid(42)
    i = labels.index(quick_pick(seats, labels, "front"))
    col = np.flatnonzero(np.isclose(seats[:, 0], seats[:, 0].min()))
    assert seats[col, 1].min() < seats[i, 1] < seats[col, 1].max()


def test_random_pick_is_deterministic_for_a_seed_and_varies_across_seeds():
    seats, labels = grid(42)
    assert quick_pick(seats, labels, "random", seed=3) == quick_pick(seats, labels, "random", seed=3)
    assert len({quick_pick(seats, labels, "random", seed=s) for s in range(20)}) > 1


def test_unknown_quick_pick_raises():
    seats, labels = grid(10)
    with pytest.raises(ValueError):
        quick_pick(seats, labels, "ceiling")


def test_risk_inputs_follow_the_wells_riley_terms():
    profile = {"length_m": 9.0, "width_m": 7.0, "height_m": 2.7, "ach": 4.0, "session_hours": 6.0,
               "mask_compliance": 0.5}
    r = risk_inputs(profile, VALUES)
    assert r["Q"] == pytest.approx(4.0 * 9 * 7 * 2.7)
    assert r["mask"] == pytest.approx((1 - VALUES["mask_efficiency"] * 0.5) ** 2)
    assert (r["q"], r["p"], r["t"]) == (VALUES["quanta_rate"], VALUES["breathing_rate"], 6.0)


def test_no_masks_gives_a_mask_factor_of_one():
    profile = {"length_m": 9.0, "width_m": 7.0, "height_m": 2.7, "ach": 4.0, "session_hours": 6.0,
               "mask_compliance": 0.0}
    assert risk_inputs(profile, VALUES)["mask"] == 1.0
