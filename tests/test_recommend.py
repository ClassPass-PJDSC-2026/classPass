"""Unit tests for the rule-based recommender (ticket #14)."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from schoolsim.params import load_params
from schoolsim.recommend import ONLINE_SCENARIO, recommend
from schoolsim.scenarios import INTERVENTION_ORDER

BASE, SECOND, THIRD = INTERVENTION_ORDER[0], INTERVENTION_ORDER[1], INTERVENTION_ORDER[2]
EXPLICIT = {"attack_threshold": 0.10, "robustness_threshold": 0.80}


def make_lhs(rates_by_scenario: dict[str, list[float]]) -> pd.DataFrame:
    """One row per (scenario, sample) with the given attack rates."""
    return pd.DataFrame(
        [
            {"sample_id": f"{scenario}-{index}", "scenario": scenario, "attack_rate": rate}
            for scenario, rates in rates_by_scenario.items()
            for index, rate in enumerate(rates)
        ]
    )


def test_all_scenarios_safe_picks_baseline():
    lhs = make_lhs({scenario: [0.01] * 5 for scenario in (BASE, SECOND, THIRD)})
    rec = recommend(lhs, **EXPLICIT)
    assert rec.scenario == BASE
    assert rec.robustness == pytest.approx(1.0)


def test_nothing_safe_returns_online():
    lhs = make_lhs({BASE: [0.4, 0.5], SECOND: [0.3, 0.45], ONLINE_SCENARIO: [0.02, 0.03]})
    rec = recommend(lhs, **EXPLICIT)
    assert rec.scenario == ONLINE_SCENARIO
    assert rec.robustness == pytest.approx(1.0)


def test_online_returned_even_when_it_also_misses_threshold():
    lhs = make_lhs({BASE: [0.4], ONLINE_SCENARIO: [0.3]})
    rec = recommend(lhs, **EXPLICIT)
    assert rec.scenario == ONLINE_SCENARIO
    assert rec.robustness == pytest.approx(0.0)


def test_no_qualifier_and_no_online_raises():
    lhs = make_lhs({BASE: [0.4], SECOND: [0.3]})
    with pytest.raises(ValueError):
        recommend(lhs, **EXPLICIT)


def test_attack_threshold_change_flips_pick():
    lhs = make_lhs({BASE: [0.05] * 6 + [0.20] * 4, SECOND: [0.05] * 9 + [0.30]})
    assert recommend(lhs, attack_threshold=0.10, robustness_threshold=0.80).scenario == SECOND
    assert recommend(lhs, attack_threshold=0.20, robustness_threshold=0.80).scenario == BASE


def test_robustness_threshold_change_flips_pick():
    lhs = make_lhs({BASE: [0.05] * 8 + [0.20] * 2, SECOND: [0.05] * 10})
    assert recommend(lhs, attack_threshold=0.10, robustness_threshold=0.80).scenario == BASE
    assert recommend(lhs, attack_threshold=0.10, robustness_threshold=0.90).scenario == SECOND


def test_deterministic_for_same_input():
    lhs = make_lhs({BASE: [0.05, 0.2], SECOND: [0.01, 0.02]})
    assert recommend(lhs, **EXPLICIT) == recommend(lhs, **EXPLICIT)


def test_nan_and_inf_count_as_failures():
    lhs = make_lhs({BASE: [0.01, 0.01, 0.01, 0.01, math.nan, math.inf]})
    rec = recommend(lhs, attack_threshold=0.10, robustness_threshold=0.60)
    assert rec.robustness == pytest.approx(4 / 6)


def test_reason_states_robustness_and_avoids_certainty_claims():
    lhs = make_lhs({BASE: [0.05] * 3 + [0.5], SECOND: [0.05] * 4})
    rec = recommend(lhs, **EXPLICIT)
    assert f"{rec.robustness:.0%}" in rec.reason
    lowered = rec.reason.lower()
    for banned in ("predict", "forecast", " ai ", "certain", "guarantee"):
        assert banned not in lowered


def test_learner_days_clause_when_column_present():
    lhs = make_lhs({BASE: [0.5, 0.5], SECOND: [0.01, 0.01]})
    lhs["learner_days_lost"] = [5.0, 5.0, 8.0, 8.0]
    rec = recommend(lhs, **EXPLICIT)
    assert rec.scenario == SECOND
    assert "5.0" in rec.reason
    assert "8.0" in rec.reason


def test_no_learner_days_clause_when_column_absent():
    lhs = make_lhs({BASE: [0.5, 0.5], SECOND: [0.01, 0.01]})
    assert "learner-days" not in recommend(lhs, **EXPLICIT).reason


def test_runner_up_is_most_robust_alternative():
    lhs = make_lhs({BASE: [0.05] * 10, SECOND: [0.05] * 9 + [0.3], THIRD: [0.05] * 10})
    rec = recommend(lhs, **EXPLICIT)
    assert rec.scenario == BASE
    assert rec.runner_up == THIRD  # tie on 1.0; later in INTERVENTION_ORDER wins


def test_single_scenario_has_no_runner_up():
    rec = recommend(make_lhs({BASE: [0.01]}), **EXPLICIT)
    assert rec.runner_up is None


def test_scenarios_outside_intervention_order_are_ignored():
    lhs = make_lhs({BASE: [0.01], "not_a_real_scenario": [0.01]})
    rec = recommend(lhs, **EXPLICIT)
    assert rec.scenario == BASE
    assert rec.runner_up is None


def test_missing_required_column_raises():
    lhs = pd.DataFrame({"scenario": [BASE]})
    with pytest.raises(ValueError):
        recommend(lhs, **EXPLICIT)


def test_empty_frame_raises():
    with pytest.raises(ValueError):
        recommend(pd.DataFrame({"scenario": [], "attack_rate": []}), **EXPLICIT)


@pytest.mark.parametrize(
    ("attack_threshold", "robustness_threshold"),
    [(0.0, 0.8), (1.5, 0.8), (0.1, 0.0), (0.1, 1.2)],
)
def test_out_of_range_thresholds_raise(attack_threshold, robustness_threshold):
    lhs = make_lhs({BASE: [0.01]})
    with pytest.raises(ValueError):
        recommend(lhs, attack_threshold=attack_threshold, robustness_threshold=robustness_threshold)


def test_defaults_are_read_from_params_yaml():
    params = load_params()
    lhs = make_lhs({BASE: [0.05] * 6 + [0.30] * 4, SECOND: [0.05] * 9 + [0.30]})
    explicit = recommend(
        lhs,
        attack_threshold=float(params["attack_rate_threshold"].value),
        robustness_threshold=float(params["robustness_threshold"].value),
    )
    assert recommend(lhs) == explicit