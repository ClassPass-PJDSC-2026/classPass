"""Final-size check: the strongest correctness test for the SEIR integrator.

With weekends off, constant beta, no community term and a tiny seed, the fraction ever
infected z must satisfy z = 1 - exp(-R0 * z).
"""

from __future__ import annotations

import math

import pytest

from schoolsim.seir import r0_effective, simulate

SIGMA = 0.5
GAMMA = 0.2
I0 = 1e-5


def final_size(r0: float) -> float:
    """Largest root of z = 1 - exp(-r0 * z), by fixed-point iteration from z = 1."""
    z = 1.0
    for _ in range(100_000):
        z_new = 1.0 - math.exp(-r0 * z)
        if abs(z_new - z) < 1e-14:
            return z_new
        z = z_new
    return z


def run(r0: float):
    return simulate(
        beta_class=r0 * GAMMA,
        community_beta=0.0,
        sigma=SIGMA,
        gamma=GAMMA,
        attendance=1.0,
        initial_infected_frac=I0,
        sim_days=365,
        school_days_per_week=7,
    )


@pytest.mark.parametrize("r0", [1.5, 2.0, 3.0])
def test_attack_rate_matches_final_size_relation(r0):
    res = run(r0)
    assert res.attack_rate == pytest.approx(final_size(r0), rel=0.01)


@pytest.mark.parametrize("r0", [1.5, 2.0, 3.0])
def test_epidemic_has_burned_out_by_day_365(r0):
    res = run(r0)
    assert res.I[-1] < 1e-4
    assert res.E[-1] < 1e-4


@pytest.mark.parametrize("r0", [1.5, 2.0, 3.0])
def test_r0_effective_matches_the_r0_used(r0):
    assert r0_effective(r0 * GAMMA, 0.0, GAMMA, 1.0, school_days_per_week=7) == pytest.approx(r0)


def test_final_size_grows_with_r0():
    sizes = [run(r0).attack_rate for r0 in (1.5, 2.0, 3.0)]
    assert sizes == sorted(sizes)