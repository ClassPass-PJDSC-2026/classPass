"""Tests for schoolsim.scenarios: ordering, wiring, extensibility."""

from __future__ import annotations

import numpy as np
import pytest

from schoolsim.params import base_values, load_params
from schoolsim.scenarios import (
    INTERVENTION_ORDER,
    LABELS,
    SCENARIOS,
    SchoolProfile,
    get_label,
    run_all,
    run_scenario,
)


@pytest.fixture(scope="module")
def values():
    return base_values(load_params())


@pytest.fixture(scope="module")
def profile(values):
    return SchoolProfile(
        class_size=int(values["class_size"]),
        length_m=values["room_length"],
        width_m=values["room_width"],
        height_m=values["room_height"],
        ach=values["ach"],
        session_hours=values["session_hours"],
        mask_compliance=values["mask_compliance"],
    )


@pytest.fixture(scope="module")
def results(profile, values):
    return run_all(profile, values)


def test_all_scenarios_present_in_intervention_order(results):
    assert set(results) == set(SCENARIOS)
    assert list(results) == list(INTERVENTION_ORDER)


def test_every_scenario_has_a_label():
    for name in SCENARIOS:
        assert name in LABELS
        assert get_label(name) == LABELS[name]


def test_get_label_falls_back_to_name():
    assert get_label("not_a_scenario") == "not_a_scenario"


def test_non_scenario_parameters_identical_across_runs(results):
    t_ref = results["baseline"].t
    for name, r in results.items():
        assert np.array_equal(r.t, t_ref), name


def test_online_lt_hybrid_lt_face_to_face(results):
    assert results["online"].attack_rate < results["hybrid"].attack_rate
    assert results["hybrid"].attack_rate < results["baseline"].attack_rate


def test_hybrid_lt_smaller_classes_lt_baseline(results):
    assert results["hybrid"].attack_rate < results["smaller_classes"].attack_rate
    assert results["smaller_classes"].attack_rate < results["baseline"].attack_rate


@pytest.mark.parametrize("name", ["better_ventilation", "masks", "smaller_classes", "combined"])
def test_each_intervention_beats_baseline(results, name):
    assert results[name].attack_rate < results["baseline"].attack_rate


def test_combined_beats_its_components(results):
    assert results["combined"].attack_rate < results["better_ventilation"].attack_rate
    assert results["combined"].attack_rate < results["masks"].attack_rate


def test_empty_override_scenario_equals_baseline(profile, values, results, monkeypatch):
    monkeypatch.setitem(SCENARIOS, "_test_scenario", {})
    r = run_scenario(profile, "_test_scenario", values)
    assert np.array_equal(r.S, results["baseline"].S)


def test_added_scenario_is_appended_after_intervention_order(profile, values, monkeypatch):
    monkeypatch.setitem(SCENARIOS, "_test_scenario", {"attendance": 0.25})
    out = run_all(profile, values)
    assert list(out)[-1] == "_test_scenario"
    assert list(out)[: len(INTERVENTION_ORDER)] == list(INTERVENTION_ORDER)


def test_unknown_scenario_raises(profile, values):
    with pytest.raises(ValueError, match="Unknown scenario"):
        run_scenario(profile, "does_not_exist", values)


def test_unknown_override_key_raises(profile, values, monkeypatch):
    monkeypatch.setitem(SCENARIOS, "_bad", {"nonsense": 1})
    with pytest.raises(ValueError, match="Unknown scenario override key"):
        run_scenario(profile, "_bad", values)


def test_better_ventilation_and_smaller_classes_only_tie_by_coincidence(values):
    """At baseline params both scale beta_class by 2/3. Vary the profile and they differ."""
    odd = SchoolProfile(
        class_size=47, length_m=9, width_m=7, height_m=2.7,
        ach=8.5, session_hours=6, mask_compliance=0.0,
    )
    out = run_all(odd, values)
    assert out["better_ventilation"].attack_rate != out["smaller_classes"].attack_rate


def test_run_is_deterministic(profile, values):
    a = run_scenario(profile, "hybrid", values)
    b = run_scenario(profile, "hybrid", values)
    assert np.array_equal(a.I, b.I)
    assert a.attack_rate == b.attack_rate