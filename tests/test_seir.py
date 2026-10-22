"""Tests for schoolsim.seir: invariants, validation, batch/scalar parity."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from schoolsim.seir import SimResult, r0_effective, simulate, simulate_batch

BASE = dict(
    beta_class=0.8,
    community_beta=0.01,
    sigma=1 / 3,
    gamma=1 / 5,
    attendance=1.0,
    initial_infected_frac=0.01,
    sim_days=60,
)


def run(**overrides) -> SimResult:
    return simulate(**{**BASE, **overrides})


# ---------------------------------------------------------------------------
# r0_effective
# ---------------------------------------------------------------------------


def test_r0_effective_value():
    # (5/7 * 1.0 * 0.7 + 0.1) / 0.2 = 3.0
    assert r0_effective(0.7, 0.1, 0.2, 1.0) == pytest.approx(3.0)


def test_r0_effective_online_is_community_only():
    assert r0_effective(0.7, 0.1, 0.2, 0.0) == pytest.approx(0.1 / 0.2)


def test_r0_effective_school_days_per_week():
    full = r0_effective(0.7, 0.0, 0.2, 1.0, school_days_per_week=7)
    assert full == pytest.approx(0.7 / 0.2)
    assert r0_effective(0.7, 0.0, 0.2, 1.0, school_days_per_week=0) == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(gamma=0.0),
        dict(gamma=-0.1),
        dict(attendance=1.5),
        dict(attendance=-0.1),
        dict(school_days_per_week=8),
        dict(school_days_per_week=-1),
    ],
)
def test_r0_effective_validation(kwargs):
    args = dict(beta_class=0.7, community_beta=0.1, gamma=0.2, attendance=1.0)
    args.update(kwargs)
    with pytest.raises(ValueError):
        r0_effective(**args)


# ---------------------------------------------------------------------------
# simulate: structure and invariants
# ---------------------------------------------------------------------------


def test_result_shapes_and_time_axis():
    res = run()
    assert isinstance(res, SimResult)
    for arr in (res.t, res.S, res.E, res.I, res.R):
        assert arr.shape == (BASE["sim_days"] + 1,)
    np.testing.assert_array_equal(res.t, np.arange(BASE["sim_days"] + 1))


def test_initial_state():
    res = run(initial_infected_frac=0.02)
    assert res.S[0] == pytest.approx(0.98)
    assert res.E[0] == 0.0
    assert res.I[0] == pytest.approx(0.02)
    assert res.R[0] == 0.0


def test_population_conserved():
    res = run()
    total = res.S + res.E + res.I + res.R
    np.testing.assert_allclose(total, 1.0, atol=1e-9)


def test_compartments_non_negative_and_bounded():
    res = run(beta_class=3.0)
    for arr in (res.S, res.E, res.I, res.R):
        assert np.all(arr >= 0.0)
        assert np.all(arr <= 1.0 + 1e-9)


def test_summary_metrics_consistent():
    res = run()
    assert res.peak_infectious == pytest.approx(res.I.max())
    assert res.peak_day == int(np.argmax(res.I))
    assert res.cumulative_infections == pytest.approx(1.0 - res.S[-1])
    assert res.attack_rate == pytest.approx(
        res.cumulative_infections - BASE["initial_infected_frac"]
    )
    # Conservation form: attack = E_end + I_end + R_end - seed.
    assert res.attack_rate == pytest.approx(
        res.E[-1] + res.I[-1] + res.R[-1] - BASE["initial_infected_frac"], abs=1e-9
    )


def test_result_is_frozen():
    res = run()
    with pytest.raises(FrozenInstanceError):
        res.attack_rate = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# simulate: epidemiological behaviour
# ---------------------------------------------------------------------------


def test_no_seed_means_no_outbreak():
    res = run(initial_infected_frac=0.0)
    assert np.all(res.I == 0.0)
    assert np.all(res.S == 1.0)
    assert res.attack_rate == 0.0


def test_online_without_community_has_no_spread():
    res = run(attendance=0.0, community_beta=0.0)
    assert res.attack_rate == pytest.approx(0.0, abs=1e-12)


def test_no_school_days_without_community_has_no_spread():
    res = run(school_days_per_week=0, community_beta=0.0)
    assert res.attack_rate == pytest.approx(0.0, abs=1e-12)


def test_higher_beta_gives_bigger_outbreak():
    low = run(beta_class=0.4)
    high = run(beta_class=1.2)
    assert high.peak_infectious > low.peak_infectious
    assert high.attack_rate > low.attack_rate
    assert high.peak_day <= low.peak_day


def test_lower_attendance_reduces_attack_rate():
    full = run(attendance=1.0)
    hybrid = run(attendance=0.5)
    online = run(attendance=0.0)
    assert full.attack_rate > hybrid.attack_rate > online.attack_rate


def test_more_school_days_increases_attack_rate():
    five = run(school_days_per_week=5)
    seven = run(school_days_per_week=7)
    assert seven.attack_rate > five.attack_rate


def test_subcritical_does_not_take_off():
    # R0_eff ~ 0.36 < 1: new infections stay below the initial seed.
    res = run(beta_class=0.1, community_beta=0.0)
    assert res.attack_rate < BASE["initial_infected_frac"]


def test_dt_convergence():
    coarse = run(dt=0.1)
    fine = run(dt=0.05)
    assert coarse.attack_rate == pytest.approx(fine.attack_rate, abs=5e-3)


def test_matches_scipy_reference_without_weekends():
    solve_ivp = pytest.importorskip("scipy.integrate").solve_ivp
    p = BASE
    f = p["initial_infected_frac"]

    def rhs(_t, y):
        S, E, infectious, _R = y
        lam = (p["attendance"] * p["beta_class"] + p["community_beta"]) * infectious
        return [
            -lam * S,
            lam * S - p["sigma"] * E,
            p["sigma"] * E - p["gamma"] * infectious,
            p["gamma"] * infectious,
        ]

    days = np.arange(p["sim_days"] + 1)
    ref = solve_ivp(
        rhs, (0, p["sim_days"]), [1 - f, 0.0, f, 0.0],
        t_eval=days, rtol=1e-10, atol=1e-12,
    )
    res = run(school_days_per_week=7)
    ref_attack = (1.0 - ref.y[0][-1]) - f
    # Acceptance criterion (#6): attack rate within 1% of the scipy reference.
    assert abs(res.attack_rate - ref_attack) / ref_attack < 0.01


# ---------------------------------------------------------------------------
# simulate: validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        dict(beta_class=-0.1),
        dict(community_beta=-0.1),
        dict(sigma=0.0),
        dict(gamma=0.0),
        dict(attendance=1.1),
        dict(attendance=-0.1),
        dict(initial_infected_frac=1.5),
        dict(initial_infected_frac=-0.1),
        dict(beta_class=float("nan")),
        dict(sim_days=0),
        dict(sim_days=10.5),
        dict(dt=0.0),
        dict(dt=float("nan")),
        dict(school_days_per_week=8),
        dict(school_days_per_week=-1),
    ],
)
def test_simulate_validation(overrides):
    with pytest.raises(ValueError):
        run(**overrides)


# ---------------------------------------------------------------------------
# simulate_batch
# ---------------------------------------------------------------------------


def _batch_kwargs(**overrides):
    kw = {k: v for k, v in BASE.items()}
    kw.update(overrides)
    return kw


def test_batch_keys_shapes_dtypes():
    out = simulate_batch(**_batch_kwargs(beta_class=[0.4, 0.8, 1.2]))
    days = BASE["sim_days"] + 1
    assert out["t"].shape == (days,)
    for key in ("S", "E", "I", "R"):
        assert out[key].shape == (3, days)
    for key in ("attack_rate", "peak_infectious", "cumulative_infections", "peak_day"):
        assert out[key].shape == (3,)
    assert np.issubdtype(out["peak_day"].dtype, np.integer)


def test_batch_all_scalars_gives_single_run():
    out = simulate_batch(**_batch_kwargs())
    assert out["S"].shape == (1, BASE["sim_days"] + 1)


def test_batch_length_one_is_bit_identical_to_scalar():
    ref = run()
    out = simulate_batch(**_batch_kwargs())
    np.testing.assert_array_equal(out["S"][0], ref.S)
    np.testing.assert_array_equal(out["E"][0], ref.E)
    np.testing.assert_array_equal(out["I"][0], ref.I)
    np.testing.assert_array_equal(out["R"][0], ref.R)
    assert out["attack_rate"][0] == ref.attack_rate
    assert out["peak_day"][0] == ref.peak_day


def test_batch_matches_scalar_for_each_row():
    betas = [0.4, 0.8, 1.2]
    attendances = [1.0, 0.5, 0.0]
    out = simulate_batch(
        **_batch_kwargs(beta_class=betas, attendance=attendances)
    )
    for i, (b, a) in enumerate(zip(betas, attendances, strict=True)):
        ref = run(beta_class=b, attendance=a)
        np.testing.assert_allclose(out["I"][i], ref.I, rtol=1e-12, atol=1e-15)
        assert out["attack_rate"][i] == pytest.approx(ref.attack_rate)
        assert out["peak_day"][i] == ref.peak_day


def test_batch_conserves_population():
    out = simulate_batch(**_batch_kwargs(beta_class=[0.2, 1.0, 2.5]))
    total = out["S"] + out["E"] + out["I"] + out["R"]
    np.testing.assert_allclose(total, 1.0, atol=1e-9)


def test_batch_mismatched_shapes_raise():
    with pytest.raises(ValueError, match="broadcast"):
        simulate_batch(**_batch_kwargs(beta_class=[0.4, 0.8, 1.2], gamma=[0.2, 0.3]))


def test_batch_rejects_2d_input():
    with pytest.raises(ValueError, match="1-D"):
        simulate_batch(**_batch_kwargs(beta_class=[[0.4, 0.8], [1.0, 1.2]]))


@pytest.mark.parametrize(
    "overrides",
    [
        dict(beta_class=[0.4, -0.1]),
        dict(community_beta=[0.01, -0.01]),
        dict(sigma=[0.3, 0.0]),
        dict(gamma=[0.2, 0.0]),
        dict(attendance=[1.0, 1.2]),
        dict(initial_infected_frac=[0.01, 1.5]),
        dict(beta_class=[0.4, float("nan")]),
        dict(sim_days=0),
        dict(dt=-0.05),
        dict(school_days_per_week=9),
    ],
)
def test_batch_validation(overrides):
    with pytest.raises(ValueError):
        simulate_batch(**_batch_kwargs(**overrides))

def test_simulate_is_deterministic():
    a = run()
    b = run()
    for key in ("t", "S", "E", "I", "R"):
        assert np.array_equal(getattr(a, key), getattr(b, key)), key
    assert a.attack_rate == b.attack_rate
    assert a.peak_day == b.peak_day