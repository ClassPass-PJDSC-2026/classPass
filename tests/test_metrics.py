"""Tests for schoolsim.metrics (ticket #11)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from schoolsim import _stub_engine as stub
from schoolsim.metrics import kpi_summary, learner_days_lost, school_days_in_horizon
from schoolsim.params import base_values, load_params


def result(cum=0.5, **kw):
    base = {"attack_rate": cum, "peak_infectious": 0.2, "peak_day": 11, "cumulative_infections": cum,
            "r0_effective": 2.5}
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("sim_days, expected", [(1, 1), (5, 5), (7, 5), (30, 22), (60, 44)])
def test_school_days_in_horizon(sim_days, expected):
    assert school_days_in_horizon(sim_days) == expected


def test_school_days_depend_on_week_length():
    assert school_days_in_horizon(14, school_days_per_week=6) == 12


@pytest.mark.parametrize("sim_days, per_week", [(0, 5), (-3, 5), (60, 0), (60, 8)])
def test_school_days_rejects_bad_input(sim_days, per_week):
    with pytest.raises(ValueError):
        school_days_in_horizon(sim_days, per_week)


def test_face_to_face_counts_only_illness():
    assert learner_days_lost(result(0.4), 1.0, 3.0, 0.3, 60) == pytest.approx(1.2)


def test_online_adds_learning_lost_on_every_school_day():
    # 0.01 infected * 3 sick days + 44 school days * 0.3 weight
    assert learner_days_lost(result(0.01), 0.0, 3.0, 0.3, 60) == pytest.approx(0.03 + 13.2)


def test_hybrid_is_half_the_online_learning_loss():
    online = learner_days_lost(result(0.0), 0.0, 3.0, 0.3, 60)
    hybrid = learner_days_lost(result(0.0), 0.5, 3.0, 0.3, 60)
    assert hybrid == pytest.approx(online / 2)


@pytest.mark.parametrize("attendance", [-0.1, 1.1])
def test_attendance_must_be_a_share(attendance):
    with pytest.raises(ValueError, match="attendance"):
        learner_days_lost(result(), attendance, 3.0, 0.3, 60)


def test_negative_weights_rejected():
    with pytest.raises(ValueError):
        learner_days_lost(result(), 1.0, -1.0, 0.3, 60)


def test_kpis_match_simresult_exactly():
    """Acceptance criterion: KPIs shown on the tab equal the SimResult values."""
    values = base_values(load_params())
    for name, res in stub.run_all(
        stub.SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0), values
    ).items():
        kpi = kpi_summary(res, stub.SCENARIOS[name].get("attendance", 1.0), values)
        assert kpi["attack_rate"] == res.attack_rate
        assert kpi["peak_infectious"] == res.peak_infectious
        assert kpi["peak_day"] == res.peak_day
        assert kpi["r0_effective"] == res.r0_effective


def test_kpi_summary_without_r0_returns_none():
    res = SimpleNamespace(attack_rate=0.1, peak_infectious=0.05, peak_day=9, cumulative_infections=0.1)
    values = {"sick_days_per_case": 3, "online_learning_weight": 0.3, "sim_days": 60, "school_days_per_week": 5}
    assert kpi_summary(res, 1.0, values)["r0_effective"] is None
