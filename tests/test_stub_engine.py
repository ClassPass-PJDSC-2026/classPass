"""Sanity tests for the TEMPORARY stub engine. Delete with schoolsim/_stub_engine.py."""

from __future__ import annotations

import numpy as np
import pytest

from schoolsim import _stub_engine as stub
from schoolsim.params import base_values, load_params

VALUES = base_values(load_params())
PROFILE = stub.SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0)


@pytest.fixture(scope="module")
def results():
    return stub.run_all(PROFILE, VALUES)


def test_all_scenarios_are_returned(results):
    assert set(results) == set(stub.SCENARIOS) == set(stub.LABELS)


def test_compartments_conserve_population_and_stay_non_negative(results):
    for res in results.values():
        total = res.S + res.E + res.I + res.R
        assert np.allclose(total, 1.0, atol=1e-6)
        assert min(res.S.min(), res.E.min(), res.I.min(), res.R.min()) >= 0


def test_one_sample_per_day(results):
    assert len(results["baseline"].t) == int(VALUES["sim_days"]) + 1


def test_interventions_lower_the_attack_rate(results):
    a = {k: v.attack_rate for k, v in results.items()}
    assert a["online"] < a["hybrid"] < a["baseline"]
    assert a["better_ventilation"] < a["baseline"]
    assert a["masks"] < a["baseline"]
    assert a["smaller_classes"] < a["baseline"]
    assert a["combined"] < min(a["better_ventilation"], a["masks"])


def test_online_has_no_classroom_transmission(results):
    only_community = ((5 / 7) * 0 * 1 + VALUES["community_beta"]) * VALUES["infectious_days"]
    assert results["online"].r0_effective == pytest.approx(only_community)


def test_peak_day_matches_the_curve(results):
    res = results["baseline"]
    assert res.peak_infectious == res.I.max() and res.I[res.peak_day] == res.I.max()


def test_deterministic():
    a = stub.run_scenario(PROFILE, "baseline", VALUES)
    b = stub.run_scenario(PROFILE, "baseline", VALUES)
    assert np.array_equal(a.I, b.I)


def test_zero_airflow_is_a_clear_error():
    bad = stub.SchoolProfile(45, 9.0, 7.0, 2.7, 0.0, 6.0, 0.0)
    with pytest.raises(ValueError, match="Air changes per hour"):
        stub.run_all(bad, VALUES)


def test_unknown_scenario_raises():
    with pytest.raises(ValueError, match="Unknown scenario"):
        stub.run_scenario(PROFILE, "teleport", VALUES)
