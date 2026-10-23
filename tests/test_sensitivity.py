import time

import numpy as np
import pandas.testing as pdt
import pytest

from schoolsim import sensitivity as sens
from schoolsim.params import base_values, load_params, ranges
from schoolsim.scenarios import SCENARIOS, SchoolProfile, run_scenario

PARAMS = load_params()
BASE = base_values(PARAMS)
PROFILE = SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0)
BOUNDS = {k: b for k, b in ranges(PARAMS, only_sensitivity=True).items() if k not in sens.STRUCTURAL}


def test_oat_has_one_row_per_sensitivity_parameter():
    out = sens.one_at_a_time(PROFILE, "baseline", PARAMS)
    assert list(out.columns) == sens.OAT_COLUMNS
    assert sorted(out["param"]) == sorted(ranges(PARAMS, only_sensitivity=True))


def test_oat_is_sorted_by_swing_and_swing_is_the_gap():
    out = sens.one_at_a_time(PROFILE, "baseline", PARAMS)
    assert out["swing"].is_monotonic_decreasing
    assert np.allclose(out["swing"], (out["metric_high"] - out["metric_low"]).abs())


def test_oat_matches_a_direct_run():
    key = next(k for k in BOUNDS if k not in sens.PROFILE_KEYS)
    lo, hi = BOUNDS[key]
    row = sens.one_at_a_time(PROFILE, "baseline", PARAMS).set_index("param").loc[key]
    assert row["metric_low"] == pytest.approx(run_scenario(PROFILE, "baseline", {**BASE, key: lo}).attack_rate)
    assert row["metric_high"] == pytest.approx(run_scenario(PROFILE, "baseline", {**BASE, key: hi}).attack_rate)


def test_oat_rejects_unknown_metric():
    with pytest.raises(ValueError):
        sens.one_at_a_time(PROFILE, "baseline", PARAMS, metric="nonsense")


def test_lhs_same_seed_gives_identical_output():
    a = sens.latin_hypercube(PROFILE, PARAMS, n=30, seed=7)
    b = sens.latin_hypercube(PROFILE, PARAMS, n=30, seed=7)
    pdt.assert_frame_equal(a, b)


def test_lhs_different_seed_differs():
    a = sens.latin_hypercube(PROFILE, PARAMS, n=30, seed=1)
    b = sens.latin_hypercube(PROFILE, PARAMS, n=30, seed=2)
    assert not a[next(iter(BOUNDS))].equals(b[next(iter(BOUNDS))])


def test_lhs_shape_columns_and_bounds():
    n = 25
    out = sens.latin_hypercube(PROFILE, PARAMS, n=n, seed=42)
    assert len(out) == n * len(SCENARIOS)
    assert list(out.columns) == ["sample_id", *BOUNDS, "scenario", *sens.METRICS]
    assert {"scenario", "attack_rate"} <= set(out.columns)  # contract with recommend.py (#14)
    assert set(out["scenario"]) == set(SCENARIOS)
    for key, (lo, hi) in BOUNDS.items():
        assert out[key].between(lo, hi).all(), key


def test_lhs_rejects_bad_n():
    with pytest.raises(ValueError):
        sens.latin_hypercube(PROFILE, PARAMS, n=0)


def test_batch_matches_one_by_one_runs():
    out = sens.latin_hypercube(PROFILE, PARAMS, n=4, seed=3)
    for row in out.to_dict("records"):
        direct = sens._evaluate(PROFILE, row["scenario"], BASE, {k: row[k] for k in BOUNDS})
        for m in sens.METRICS:
            assert row[m] == pytest.approx(direct[m], rel=1e-9, abs=1e-12), (row["scenario"], m)


def test_uncertainty_band_is_ordered_and_combined_beats_baseline():
    band = sens.uncertainty_band(sens.latin_hypercube(PROFILE, PARAMS, n=60, seed=42)).set_index("scenario")
    assert ((band["low"] <= band["median"]) & (band["median"] <= band["high"])).all()
    assert band.loc["combined", "median"] <= band.loc["baseline", "median"]


def test_lhs_300_samples_all_scenarios_within_budget():
    start = time.perf_counter()
    out = sens.latin_hypercube(PROFILE, PARAMS, n=300, seed=42)
    elapsed = time.perf_counter() - start
    assert len(out) == 300 * len(SCENARIOS)
    assert elapsed < 10, f"LHS took {elapsed:.1f}s; budget is 10 s on Streamlit Cloud"