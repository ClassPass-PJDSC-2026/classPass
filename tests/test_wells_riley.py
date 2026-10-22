"""Tests for schoolsim.wells_riley: formulas, monotonicity, validation."""

from __future__ import annotations

import math

import numpy as np
import pytest

from schoolsim.seir import simulate
from schoolsim.wells_riley import (
    airflow,
    classroom_beta,
    infection_probability,
    mask_factor,
    room_volume,
)

# A typical classroom: 8 x 7 x 3 m, 6 ACH.
VOLUME = 8 * 7 * 3  # 168 m^3
Q = 6 * VOLUME  # 1008 m^3/h


# ---------------------------------------------------------------------------
# room_volume / airflow / mask_factor
# ---------------------------------------------------------------------------


def test_room_volume_scalar_returns_float():
    v = room_volume(8, 7, 3)
    assert isinstance(v, float)
    assert v == pytest.approx(168.0)


def test_room_volume_array_broadcasts():
    v = room_volume([8, 10], 7, 3)
    np.testing.assert_allclose(v, [168.0, 210.0])


def test_room_volume_negative_raises():
    with pytest.raises(ValueError, match="length_m"):
        room_volume(-1, 7, 3)


def test_airflow_value():
    assert airflow(6, 168) == pytest.approx(1008.0)


def test_airflow_array():
    np.testing.assert_allclose(airflow([3, 6], 168), [504.0, 1008.0])


def test_airflow_zero_raises():
    with pytest.raises(ValueError, match="positive"):
        airflow(0, 168)


def test_airflow_negative_input_raises():
    with pytest.raises(ValueError, match="ach"):
        airflow(-1, 168)
    with pytest.raises(ValueError, match="volume_m3"):
        airflow(6, -1)


def test_mask_factor_values():
    assert mask_factor(0.9, 1.0) == pytest.approx(0.01)
    assert mask_factor(0.9, 0.0) == pytest.approx(1.0)
    assert mask_factor(0.0, 1.0) == pytest.approx(1.0)
    assert mask_factor(1.0, 1.0) == pytest.approx(0.0)


def test_mask_factor_array_and_range():
    out = mask_factor([0.0, 0.5, 1.0], 1.0)
    np.testing.assert_allclose(out, [1.0, 0.25, 0.0])
    assert np.all((out >= 0) & (out <= 1))


@pytest.mark.parametrize("eff,comp", [(1.1, 0.5), (-0.1, 0.5), (0.5, 1.1), (0.5, -0.1)])
def test_mask_factor_out_of_range_raises(eff, comp):
    with pytest.raises(ValueError):
        mask_factor(eff, comp)


# ---------------------------------------------------------------------------
# infection_probability
# ---------------------------------------------------------------------------


def test_probability_matches_formula():
    p = infection_probability(1, 25, 0.5, 1.0, 1000.0)
    assert p == pytest.approx(1 - math.exp(-(1 * 25 * 0.5 * 1.0) / 1000.0))


def test_probability_zero_infectors_is_zero():
    assert infection_probability(0, 25, 0.5, 6, Q) == 0.0


def test_probability_zero_time_is_zero():
    assert infection_probability(2, 25, 0.5, 0, Q) == 0.0


def test_probability_in_unit_interval_and_saturates():
    p = infection_probability(50, 1e4, 1.0, 100, 1.0)
    assert 0.0 <= p <= 1.0
    assert p == pytest.approx(1.0)


def test_probability_increases_with_infectors_and_time():
    base = infection_probability(1, 25, 0.5, 2, Q)
    assert infection_probability(3, 25, 0.5, 2, Q) > base
    assert infection_probability(1, 25, 0.5, 6, Q) > base


def test_probability_decreases_with_ventilation_and_masks():
    base = infection_probability(1, 25, 0.5, 6, Q)
    assert infection_probability(1, 25, 0.5, 6, 2 * Q) < base
    assert infection_probability(1, 25, 0.5, 6, Q, mask=mask_factor(0.9, 0.8)) < base


def test_probability_default_mask_is_no_protection():
    assert infection_probability(1, 25, 0.5, 6, Q) == pytest.approx(
        infection_probability(1, 25, 0.5, 6, Q, mask=1.0)
    )


def test_probability_array_input():
    out = infection_probability([0, 1, 2], 25, 0.5, 6, Q)
    assert isinstance(out, np.ndarray)
    assert out.shape == (3,)
    assert out[0] == 0.0
    assert np.all(np.diff(out) > 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(n_infectors=-1),
        dict(quanta_rate=-1),
        dict(breathing_rate=-1),
        dict(session_hours=-1),
        dict(airflow_m3h=0),
        dict(airflow_m3h=-5),
        dict(mask=1.5),
        dict(mask=-0.1),
    ],
)
def test_probability_validation(kwargs):
    args = dict(
        n_infectors=1, quanta_rate=25, breathing_rate=0.5,
        session_hours=6, airflow_m3h=Q, mask=1.0,
    )
    args.update(kwargs)
    with pytest.raises(ValueError):
        infection_probability(**args)


# ---------------------------------------------------------------------------
# classroom_beta
# ---------------------------------------------------------------------------


def test_beta_matches_formula():
    beta = classroom_beta(30, 25, 0.5, 6, Q, mask=0.5, infectious_attendance=0.8)
    expected = 30 * 0.8 * 25 * 0.5 * 6 * 0.5 / Q
    assert isinstance(beta, float)
    assert beta == pytest.approx(expected)


def test_beta_online_is_zero():
    assert classroom_beta(30, 25, 0.5, 6, Q, infectious_attendance=0.0) == 0.0


def test_beta_scaling():
    base = classroom_beta(30, 25, 0.5, 6, Q)
    assert classroom_beta(60, 25, 0.5, 6, Q) == pytest.approx(2 * base)
    assert classroom_beta(30, 25, 0.5, 6, 2 * Q) == pytest.approx(base / 2)
    assert classroom_beta(30, 25, 0.5, 6, Q, mask=0.25) == pytest.approx(base / 4)


def test_beta_array_broadcast():
    out = classroom_beta([20, 30, 40], 25, 0.5, 6, Q)
    assert out.shape == (3,)
    assert np.all(np.diff(out) > 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(class_size=-1),
        dict(quanta_rate=-1),
        dict(breathing_rate=-1),
        dict(session_hours=-1),
        dict(airflow_m3h=0),
        dict(mask=2.0),
        dict(infectious_attendance=-0.1),
        dict(infectious_attendance=1.1),
    ],
)
def test_beta_validation(kwargs):
    args = dict(
        class_size=30, quanta_rate=25, breathing_rate=0.5,
        session_hours=6, airflow_m3h=Q, mask=1.0, infectious_attendance=1.0,
    )
    args.update(kwargs)
    with pytest.raises(ValueError):
        classroom_beta(**args)


# ---------------------------------------------------------------------------
# Integration: Wells-Riley beta drives the SEIR model
# ---------------------------------------------------------------------------


def _attack_rate(ach: float, mask: float = 1.0) -> float:
    beta = classroom_beta(30, 25, 0.5, 6, airflow(ach, VOLUME), mask=mask)
    return simulate(
        beta_class=beta, community_beta=0.0, sigma=1 / 3, gamma=1 / 5,
        attendance=1.0, initial_infected_frac=0.01, sim_days=90,
    ).attack_rate


def test_better_ventilation_lowers_attack_rate():
    assert _attack_rate(ach=2) > _attack_rate(ach=6) > _attack_rate(ach=12)


def test_masks_lower_attack_rate():
    assert _attack_rate(ach=4, mask=mask_factor(0.9, 0.9)) < _attack_rate(ach=4)

# ---------------------------------------------------------------------------
# Monotonicity sweeps (parametrised)
# ---------------------------------------------------------------------------

P_BASE = dict(
    n_infectors=1.0, quanta_rate=15.0, breathing_rate=0.5,
    session_hours=6.0, airflow_m3h=567.0, mask=1.0,
)
B_BASE = dict(
    class_size=30.0, quanta_rate=15.0, breathing_rate=0.5,
    session_hours=6.0, airflow_m3h=567.0, mask=1.0, infectious_attendance=1.0,
)

INCREASING = [
    ("quanta_rate", (1.0, 15.0, 50.0)),
    ("breathing_rate", (0.3, 0.5, 0.8)),
    ("session_hours", (1.0, 3.0, 6.0, 8.0)),
]
DECREASING = [
    ("airflow_m3h", (100.0, 567.0, 2000.0)),
    ("mask", (1.0, 0.5, 0.1, 0.0)),
]


def _strictly(values, up: bool) -> bool:
    pairs = list(zip(values, values[1:], strict=False))
    return all(a < b for a, b in pairs) if up else all(a > b for a, b in pairs)


@pytest.mark.parametrize("name,sweep", INCREASING + [("n_infectors", (0.0, 1.0, 2.0, 5.0))])
def test_probability_strictly_increasing(name, sweep):
    out = [infection_probability(**{**P_BASE, name: v}) for v in sweep]
    assert _strictly(out, up=True), (name, out)


@pytest.mark.parametrize("name,sweep", DECREASING)
def test_probability_strictly_decreasing(name, sweep):
    out = [infection_probability(**{**P_BASE, name: v}) for v in sweep]
    assert _strictly(out, up=False), (name, out)


@pytest.mark.parametrize(
    "name,sweep",
    INCREASING + [("class_size", (10.0, 30.0, 50.0)), ("infectious_attendance", (0.1, 0.5, 1.0))],
)
def test_beta_strictly_increasing(name, sweep):
    out = [classroom_beta(**{**B_BASE, name: v}) for v in sweep]
    assert _strictly(out, up=True), (name, out)


@pytest.mark.parametrize("name,sweep", DECREASING)
def test_beta_strictly_decreasing(name, sweep):
    out = [classroom_beta(**{**B_BASE, name: v}) for v in sweep]
    assert _strictly(out, up=False), (name, out)


@pytest.mark.parametrize("name,sweep", [("efficiency", (0.0, 0.3, 0.7, 1.0)), ("compliance", (0.0, 0.4, 1.0))])
def test_mask_factor_strictly_decreasing(name, sweep):
    other = "compliance" if name == "efficiency" else "efficiency"
    out = [mask_factor(**{name: v, other: 1.0}) for v in sweep]
    assert _strictly(out, up=False), (name, out)


@pytest.mark.parametrize("quanta", [1.0, 15.0, 100.0])
@pytest.mark.parametrize("q_air", [50.0, 567.0, 5000.0])
@pytest.mark.parametrize("infectors", [0.0, 1.0, 5.0])
def test_probability_stays_in_unit_interval(infectors, quanta, q_air):
    p = infection_probability(infectors, quanta, 0.5, 6.0, q_air)
    assert 0.0 <= p <= 1.0


def test_beta_equals_n_times_attendance_times_neg_log_one_minus_p():
    p_one = infection_probability(1, 15.0, 0.5, 6.0, 567.0)
    assert classroom_beta(30, 15.0, 0.5, 6.0, 567.0) == pytest.approx(30 * -math.log(1.0 - p_one))
