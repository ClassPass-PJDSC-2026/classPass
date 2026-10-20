"""Tests for the Results tab chart (ticket #11), without launching Streamlit."""

from __future__ import annotations

import numpy as np
import pytest
import results_tab as rt
from theme import COMPARTMENT_COLORS, COMPARTMENT_LABELS

from schoolsim import _stub_engine as stub
from schoolsim.params import base_values, load_params

VALUES = base_values(load_params())
RESULTS = stub.run_all(stub.SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0), VALUES)
POP = 900


def fig(mode=rt.PERCENT, scenario="hybrid", ghost=True, sim_days=60):
    return rt.build_figure(
        RESULTS[scenario],
        RESULTS["baseline"] if ghost else None,
        mode=mode,
        population=POP,
        sim_days=sim_days,
        school_days_per_week=5,
    )


def trace(figure, name):
    return next(t for t in figure.data if t.name == name)


@pytest.mark.parametrize("sim_days, expected", [(60, 8), (30, 4), (5, 0), (6, 1)])
def test_weekend_span_count(sim_days, expected):
    assert len(rt.weekend_spans(sim_days, 5)) == expected


def test_weekend_spans_are_saturday_and_sunday():
    spans = rt.weekend_spans(60, 5)
    assert spans[0] == (5, 7) and spans[1] == (12, 14) and spans[-1] == (54, 56)


def test_weekend_spans_are_clipped_to_the_horizon():
    assert rt.weekend_spans(6, 5) == [(5, 6)]


def test_chart_has_one_line_per_compartment_with_theme_colours():
    f = fig()
    for key, label in COMPARTMENT_LABELS.items():
        assert trace(f, label).line.color == COMPARTMENT_COLORS[key]


def test_percent_mode_uses_percent_scale():
    f = fig(rt.PERCENT)
    y = np.asarray(trace(f, "Infectious").y)
    assert y.max() == pytest.approx(RESULTS["hybrid"].peak_infectious * 100)
    assert f.layout.yaxis.title.text == "Students (% of school)"
    assert tuple(f.layout.yaxis.range) == (0, 100)


def test_number_mode_uses_enrollment_and_whole_students():
    f = fig(rt.NUMBER)
    for label in COMPARTMENT_LABELS.values():
        y = np.asarray(trace(f, label).y)
        assert np.array_equal(y, np.round(y)), f"{label} has fractional students"
    expected = np.round(RESULTS["hybrid"].I * POP)
    assert np.array_equal(np.asarray(trace(f, "Infectious").y), expected)
    assert f.layout.yaxis.title.text == "Students (number)"


def test_axes_have_titles_with_units():
    f = fig()
    assert "Day" in f.layout.xaxis.title.text
    assert "Students" in f.layout.yaxis.title.text


def test_weekends_are_shaded_and_in_the_legend():
    f = fig()
    assert len(f.layout.shapes) == 8
    assert trace(f, "Weekend (no school)").showlegend is not False


def test_baseline_ghost_line_only_when_requested():
    assert any(t.name == "Infectious, face-to-face as is" for t in fig(ghost=True).data)
    assert not any(t.name == "Infectious, face-to-face as is" for t in fig(ghost=False).data)


def test_x_axis_follows_simulation_length():
    stub_values = {**VALUES, "sim_days": 30}
    res = stub.run_all(stub.SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0), stub_values)
    f = rt.build_figure(res["baseline"], None, mode=rt.PERCENT, population=POP, sim_days=30, school_days_per_week=5)
    assert tuple(f.layout.xaxis.range) == (0, 30) and len(f.layout.shapes) == 4


def test_kpi_text_formatting():
    kpi = {"attack_rate": 0.9842, "peak_infectious": 0.409, "peak_day": 12, "learner_days_lost": 3.04,
           "r0_effective": 5.2399}
    assert rt._kpi_texts(kpi) == {
        "attack_rate": "98.4%", "peak_infectious": "40.9%", "peak_day": "Day 12",
        "learner_days_lost": "3.0", "r0_effective": "5.24",
    }


def test_missing_r0_shows_a_dash_and_no_delta():
    kpi = {"attack_rate": 0.5, "peak_infectious": 0.2, "peak_day": 10, "learner_days_lost": 2.0, "r0_effective": None}
    base = {**kpi, "r0_effective": 3.0}
    assert rt._kpi_texts(kpi)["r0_effective"] == "–"
    assert rt._kpi_deltas(kpi, base)["r0_effective"] is None


def test_deltas_compare_with_baseline():
    kpi = {"attack_rate": 0.10, "peak_infectious": 0.05, "peak_day": 20, "learner_days_lost": 7.0, "r0_effective": 1.5}
    base = {"attack_rate": 0.90, "peak_infectious": 0.40, "peak_day": 12, "learner_days_lost": 2.5, "r0_effective": 4.0}
    d = rt._kpi_deltas(kpi, base)
    assert d["attack_rate"] == "-80.0 pp" and d["peak_day"] == "+8 days"
    assert d["learner_days_lost"] == "+4.5" and d["r0_effective"] == "-2.50"
