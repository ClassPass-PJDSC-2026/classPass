"""Tests for the Sensitivity tab (ticket #13), without a browser."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sensitivity_tab as st_tab
from streamlit.testing.v1 import AppTest
from theme import COMPARTMENT_COLORS

from schoolsim import sensitivity as sens
from schoolsim.engine import get_backend
from schoolsim.params import base_values, load_params
from schoolsim.scenarios import SchoolProfile

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
PARAMS = load_params()
PROFILE = SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0)
BACKEND = get_backend()


def test_with_sim_days_changes_only_the_horizon():
    out = st_tab.with_sim_days(PARAMS, 90)
    assert base_values(out)["sim_days"] == 90
    assert {k: v for k, v in base_values(out).items() if k != "sim_days"} == {
        k: v for k, v in base_values(PARAMS).items() if k != "sim_days"
    }


def test_tornado_has_one_pair_of_bars_per_parameter_and_a_base_line():
    table = sens.one_at_a_time(PROFILE, "baseline", PARAMS)
    base = sens._evaluate(PROFILE, "baseline", base_values(PARAMS), {})["attack_rate"]
    fig = st_tab.tornado_figure(table, base, "attack_rate", PARAMS)
    assert [t.name for t in fig.data] == ["Input at minimum", "Input at maximum"]
    assert all(len(t.y) == len(table) for t in fig.data)
    assert fig.data[0].marker.color == COMPARTMENT_COLORS["S"]
    assert fig.layout.shapes[0].x0 == pytest.approx(base * 100)


def test_tornado_bar_ends_match_the_table():
    table = sens.one_at_a_time(PROFILE, "baseline", PARAMS, "learner_days_lost")
    base = sens._evaluate(PROFILE, "baseline", base_values(PARAMS), {})["learner_days_lost"]
    fig = st_tab.tornado_figure(table, base, "learner_days_lost", PARAMS)
    ends = [b + x for b, x in zip([fig.data[1].base] * len(table), fig.data[1].x, strict=True)]
    assert ends == pytest.approx(list(table["metric_high"]))


def test_band_figure_has_one_point_per_scenario_in_disruption_order():
    band = sens.uncertainty_band(sens.latin_hypercube(PROFILE, PARAMS, n=20, seed=1))
    fig = st_tab.band_figure(band, "attack_rate", BACKEND.ordered_ids, BACKEND.labels)
    assert len(fig.data[0].x) == len(band)
    assert list(fig.data[0].x) == [BACKEND.label(s) for s in BACKEND.ordered_ids if s in set(band["scenario"])]
    assert all(lo >= 0 for lo in fig.data[0].error_y.arrayminus)


def test_tab_renders_in_the_app_with_the_real_engine():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert not [i for i in at.info if "ticket #13" in i.value]
    assert at.tabs[3].selectbox  # outcome and scenario pickers


def test_tab_degrades_without_the_real_engine(monkeypatch):
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", None)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("real simulation engine" in i.value for i in at.info)