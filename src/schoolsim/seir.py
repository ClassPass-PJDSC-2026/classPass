"""SEIR compartmental model for classroom airborne disease spread.

Deterministic model of airborne transmission in a school population.
The population is normalised to 1, so ``S + E + I + R = 1`` at all
times and results are independent of school size. Scale by enrollment
only for display.

Continuous-time ODE
-------------------

::

    lambda(t) = (school_on(t) * attendance * beta_class + beta_comm) * I

    dS/dt = -lambda(t) * S
    dE/dt =  lambda(t) * S - sigma * E
    dI/dt =  sigma * E - gamma * I
    dR/dt =  gamma * I

* ``school_on(t) = 1`` on school days (``int(t) % 7 < school_days_per_week``),
  0 otherwise. Day 0 is Monday.
* ``attendance`` is 1 for face-to-face, 0.5 for hybrid, 0 for online
  (set by the scenario layer, not here).
* ``beta_class`` [1/day] comes from :mod:`schoolsim.wells_riley`;
  ``beta_comm`` [1/day] is a background community transmission term.
* ``sigma = 1 / latent_period``, ``gamma = 1 / infectious_period``
  [1/day].

Units
-----
* ``days``, ``dt``, ``t`` : days [day].
* ``beta_class``, ``beta_comm``, ``sigma``, ``gamma`` : 1/day.
* ``attendance``, ``i0``, ``S``, ``E``, ``I``, ``R`` : dimensionless [-] in
  ``[0, 1]``.

Integration
-----------
Both :func:`simulate` and :func:`simulate_batch` use fixed-step RK4
with ``dt = 0.05`` day. We do not use ``scipy.integrate.solve_ivp`` in
production because the weekend on/off switching makes the RHS
discontinuous at day boundaries (``solve_ivp`` needs tiny step sizes
there and would choke), and the sensitivity analysis needs hundreds of
fast runs. ``solve_ivp`` is used only in tests as a reference
integrator on the continuous (no-weekend) variant.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


__all__ = [
    "SimResult",
    "r0_effective",
    "simulate",
    "simulate_batch",
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimResult:
    """Daily samples of one SEIR simulation, plus summary metrics.

    All compartment arrays are fractions of the school population and
    sum to 1 within numerical tolerance.

    Attributes
    ----------
    t : ndarray, shape (days + 1,)
        Sample times [day]. Always ``[0, 1, ..., days]``.
    S, E, I, R : ndarray, shape (days + 1,)
        Compartment fractions [-] at each sample time.
    attack_rate : float
        Fraction of the population newly infected during the run,
        excluding the initial seed. Equal to ``(1 - S_end) - i0``,
        which by conservation is also ``R_end + I_end + E_end - i0``.
    peak_infectious : float
        Maximum value of ``I`` over the daily samples [-].
    peak_day : int
        Day index at which ``I`` reaches its daily maximum.
    cumulative_infections : float
        Fraction of the population ever infected, including the seed.
        Equal to ``1 - S_end``.
    """

    t: NDArray[np.float64]
    S: NDArray[np.float64]
    E: NDArray[np.float64]
    I: NDArray[np.float64]
    R: NDArray[np.float64]
    attack_rate: float
    peak_infectious: float
    peak_day: int
    cumulative_infections: float


# ---------------------------------------------------------------------------
# Effective reproduction number
# ---------------------------------------------------------------------------


def r0_effective(
    beta_class: float,
    beta_comm: float,
    gamma: float,
    attendance: float,
    *,
    school_days_per_week: int = 5,
) -> float:
    """Effective basic reproduction number ``R0_eff`` [-].

    ``R0_eff = (school_days / 7 * attendance * beta_class + beta_comm) / gamma``

    The ``school_days / 7`` factor averages classroom transmission over
    a week; the community term acts every day.

    Parameters
    ----------
    beta_class : float
        Classroom transmission rate [1/day].
    beta_comm : float
        Community transmission rate [1/day].
    gamma : float
        Recovery rate [1/day]. Must be positive.
    attendance : float
        Fraction of students physically present [-], in [0, 1].
    school_days_per_week : int
        School days per week, in [0, 7].

    Returns
    -------
    float
        Effective R0 [-].

    Raises
    ------
    ValueError
        If ``gamma`` is not positive, ``attendance`` falls outside
        [0, 1], or ``school_days_per_week`` is not an integer in [0, 7].
    """
    if gamma <= 0:
        raise ValueError(f"gamma must be positive; got {gamma!r}.")
    if not (0.0 <= attendance <= 1.0):
        raise ValueError(f"attendance must be in [0, 1]; got {attendance!r}.")
    if not (0 <= school_days_per_week <= 7):
        raise ValueError(
            "school_days_per_week must be an integer in [0, 7]; "
            f"got {school_days_per_week!r}."
        )
    return (school_days_per_week / 7.0 * attendance * beta_class + beta_comm) / gamma


# ---------------------------------------------------------------------------
# Integration core
# ---------------------------------------------------------------------------


def _school_on(t: float, school_days_per_week: int) -> float:
    """Return 1.0 on a school day, 0.0 otherwise.

    ``t`` is in days; the day index is ``int(t)``. Day 0 is Monday.
    """
    return 1.0 if int(t) % 7 < school_days_per_week else 0.0


def _seir_rhs(
    t: float,
    S: ArrayLike,
    E: ArrayLike,
    I: ArrayLike,
    beta_class: ArrayLike,
    beta_comm: ArrayLike,
    sigma: ArrayLike,
    gamma: ArrayLike,
    attendance: ArrayLike,
    school_days_per_week: int,
) -> tuple:
    """SEIR right-hand side.

    Pure; accepts scalars or numpy arrays for ``S, E, I`` and the
    parameter arguments (they must broadcast). ``t`` and
    ``school_days_per_week`` are always scalars.
    """
    lam = (
        _school_on(t, school_days_per_week) * attendance * beta_class
        + beta_comm
    ) * I
    dS = -lam * S
    dE = lam * S - sigma * E
    dI = sigma * E - gamma * I
    dR = gamma * I
    return dS, dE, dI, dR


def _rk4_step(
    S: ArrayLike,
    E: ArrayLike,
    I: ArrayLike,
    R: ArrayLike,
    beta_class: ArrayLike,
    beta_comm: ArrayLike,
    sigma: ArrayLike,
    gamma: ArrayLike,
    attendance: ArrayLike,
    t_curr: float,
    dt: float,
    school_days_per_week: int,
) -> tuple:
    """One fixed-step RK4 update. Duck-typed over scalars and arrays.

    When ``S, E, I, R`` and the parameters are Python floats, the
    result is a tuple of Python floats. When they are numpy arrays
    (shape ``(n,)``), the result is a tuple of numpy arrays of the
    same shape. Either way, arithmetic is IEEE 754 double, so a
    scalar call and a length-1 batch call return bit-identical values.
    """
    dS1, dE1, dI1, dR1 = _seir_rhs(
        t_curr, S, E, I,
        beta_class, beta_comm, sigma, gamma, attendance, school_days_per_week,
    )
    dS2, dE2, dI2, dR2 = _seir_rhs(
        t_curr + 0.5 * dt,
        S + 0.5 * dt * dS1,
        E + 0.5 * dt * dE1,
        I + 0.5 * dt * dI1,
        beta_class, beta_comm, sigma, gamma, attendance, school_days_per_week,
    )
    dS3, dE3, dI3, dR3 = _seir_rhs(
        t_curr + 0.5 * dt,
        S + 0.5 * dt * dS2,
        E + 0.5 * dt * dE2,
        I + 0.5 * dt * dI2,
        beta_class, beta_comm, sigma, gamma, attendance, school_days_per_week,
    )
    dS4, dE4, dI4, dR4 = _seir_rhs(
        t_curr + dt,
        S + dt * dS3,
        E + dt * dE3,
        I + dt * dI3,
        beta_class, beta_comm, sigma, gamma, attendance, school_days_per_week,
    )
    h6 = dt / 6.0
    return (
        S + h6 * (dS1 + 2.0 * dS2 + 2.0 * dS3 + dS4),
        E + h6 * (dE1 + 2.0 * dE2 + 2.0 * dE3 + dE4),
        I + h6 * (dI1 + 2.0 * dI2 + 2.0 * dI3 + dI4),
        R + h6 * (dR1 + 2.0 * dR2 + 2.0 * dR3 + dR4),
    )


def _daily_indices(days: int, dt: float, n_steps: int) -> NDArray[np.intp]:
    """Index of the substep nearest each integer day 0..days."""
    return np.clip(
        np.round(np.arange(days + 1) / dt).astype(np.intp), 0, n_steps
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _check_common(days: int, dt: float, school_days_per_week: int) -> None:
    if days <= 0 or int(days) != days:
        raise ValueError(
            f"days must be a positive whole number; got {days!r}."
        )
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError(f"dt must be positive and finite; got {dt!r}.")
    if not (0 <= school_days_per_week <= 7):
        raise ValueError(
            "school_days_per_week must be an integer in [0, 7]; "
            f"got {school_days_per_week!r}."
        )


def _check_scalar(
    name: str, value: float, *, min_: float | None = None,
    max_: float | None = None, strict_min: bool = False, strict_max: bool = False,
) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite; got {value!r}.")
    if min_ is not None:
        if strict_min and value <= min_:
            raise ValueError(f"{name} must be greater than {min_}; got {value!r}.")
        if not strict_min and value < min_:
            raise ValueError(f"{name} must be at least {min_}; got {value!r}.")
    if max_ is not None:
        if strict_max and value >= max_:
            raise ValueError(f"{name} must be less than {max_}; got {value!r}.")
        if not strict_max and value > max_:
            raise ValueError(f"{name} must be at most {max_}; got {value!r}.")


def _check_array(
    name: str, arr: NDArray[np.float64], *, min_: float | None = None,
    max_: float | None = None, strict_min: bool = False,
) -> None:
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values.")
    if min_ is not None:
        bad = arr <= min_ if strict_min else arr < min_
        if np.any(bad):
            op = ">" if strict_min else ">="
            raise ValueError(
                f"{name} must be {op} {min_} for every sample; got {arr!r}."
            )
    if max_ is not None:
        if np.any(arr > max_):
            raise ValueError(
                f"{name} must be at most {max_} for every sample; got {arr!r}."
            )


def _validate_scalar_inputs(
    beta_class, beta_comm, sigma, gamma, attendance, i0, days, dt,
    school_days_per_week,
) -> None:
    _check_scalar("beta_class", beta_class, min_=0.0)
    _check_scalar("beta_comm", beta_comm, min_=0.0)
    _check_scalar("sigma", sigma, min_=0.0, strict_min=True)
    _check_scalar("gamma", gamma, min_=0.0, strict_min=True)
    _check_scalar("attendance", attendance, min_=0.0, max_=1.0)
    _check_scalar("i0", i0, min_=0.0, max_=1.0)
    _check_common(days, dt, school_days_per_week)


def _validate_array_inputs(
    beta_class, beta_comm, sigma, gamma, attendance, i0, days, dt,
    school_days_per_week,
) -> None:
    _check_array("beta_class", beta_class, min_=0.0)
    _check_array("beta_comm", beta_comm, min_=0.0)
    _check_array("sigma", sigma, min_=0.0, strict_min=True)
    _check_array("gamma", gamma, min_=0.0, strict_min=True)
    _check_array("attendance", attendance, min_=0.0, max_=1.0)
    _check_array("i0", i0, min_=0.0, max_=1.0)
    _check_common(days, dt, school_days_per_week)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def simulate(
    beta_class: float,
    beta_comm: float,
    sigma: float,
    gamma: float,
    attendance: float,
    i0: float,
    days: int,
    dt: float = 0.05,
    *,
    school_days_per_week: int = 5,
) -> SimResult:
    """Run a single SEIR simulation and return daily samples.

    Fixed-step RK4 with ``dt = 0.05`` day. The returned arrays are
    subsampled at ``t = 0, 1, ..., days``.

    Parameters
    ----------
    beta_class : float
        Classroom transmission rate [1/day], non-negative.
    beta_comm : float
        Community transmission rate [1/day], non-negative.
    sigma : float
        Rate E -> I [1/day], positive.
    gamma : float
        Rate I -> R [1/day], positive.
    attendance : float
        Fraction of students physically present [-], in [0, 1].
    i0 : float
        Initial infectious fraction [-], in [0, 1]. Initial state is
        ``S = 1 - i0, E = 0, I = i0, R = 0``.
    days : int
        Simulation length [day], positive integer.
    dt : float, optional
        Integration step [day], default 0.05.
    school_days_per_week : int, keyword-only
        School days per week, in [0, 7]. Default 5 (Mon-Fri).
        Set to 7 for a continuous (no-weekend) simulation.

    Returns
    -------
    SimResult
        Daily samples and summary metrics.

    Raises
    ------
    ValueError
        If any parameter is out of range.
    """
    _validate_scalar_inputs(
        beta_class, beta_comm, sigma, gamma, attendance, i0, days, dt,
        school_days_per_week,
    )

    days_i = int(days)
    n_steps = int(round(days_i / dt))

    S_list = [0.0] * (n_steps + 1)
    E_list = [0.0] * (n_steps + 1)
    I_list = [0.0] * (n_steps + 1)
    R_list = [0.0] * (n_steps + 1)

    S = 1.0 - i0
    E = 0.0
    I = i0
    R = 0.0
    S_list[0], E_list[0], I_list[0], R_list[0] = S, E, I, R

    for k in range(n_steps):
        t_curr = k * dt
        S, E, I, R = _rk4_step(
            S, E, I, R,
            beta_class, beta_comm, sigma, gamma, attendance,
            t_curr, dt, school_days_per_week,
        )
        if S < 0.0:
            S = 0.0
        if E < 0.0:
            E = 0.0
        if I < 0.0:
            I = 0.0
        if R < 0.0:
            R = 0.0
        S_list[k + 1], E_list[k + 1], I_list[k + 1], R_list[k + 1] = S, E, I, R

    daily_idx = _daily_indices(days_i, dt, n_steps)
    t_daily = np.arange(days_i + 1, dtype=np.float64)
    S_daily = np.asarray(S_list, dtype=np.float64)[daily_idx]
    E_daily = np.asarray(E_list, dtype=np.float64)[daily_idx]
    I_daily = np.asarray(I_list, dtype=np.float64)[daily_idx]
    R_daily = np.asarray(R_list, dtype=np.float64)[daily_idx]

    peak_idx = int(np.argmax(I_daily))
    cumulative = float(1.0 - S_daily[-1])

    return SimResult(
        t=t_daily,
        S=S_daily,
        E=E_daily,
        I=I_daily,
        R=R_daily,
        attack_rate=float(cumulative - i0),
        peak_infectious=float(I_daily[peak_idx]),
        peak_day=peak_idx,
        cumulative_infections=cumulative,
    )


def simulate_batch(
    beta_class: ArrayLike,
    beta_comm: ArrayLike,
    sigma: ArrayLike,
    gamma: ArrayLike,
    attendance: ArrayLike,
    i0: ArrayLike,
    days: int,
    dt: float = 0.05,
    *,
    school_days_per_week: int = 5,
) -> dict[str, NDArray[np.float64]]:
    """Vectorised RK4 over ``n`` parameter sets.

    Each input is a scalar or an array of shape ``(n,)``; scalars are
    broadcast. Runs the same RK4 update as :func:`simulate`, so a
    length-1 call produces values bit-identical to the scalar path.

    Parameters
    ----------
    beta_class, beta_comm, sigma, gamma, attendance, i0 :
        Array-like of shape ``(n,)`` (or scalars, broadcast to ``n``).
        See :func:`simulate` for units and ranges.
    days : int
        Simulation length [day], positive integer.
    dt : float, optional
        Integration step [day], default 0.05.
    school_days_per_week : int, keyword-only
        School days per week, in [0, 7]. Default 5.

    Returns
    -------
    dict of ndarray
        Keys mirror :class:`SimResult`:

        * ``t``: shape ``(days + 1,)`` — day values ``[0, 1, ..., days]``.
        * ``S, E, I, R``: shape ``(n, days + 1)``.
        * ``attack_rate, peak_infectious, cumulative_infections``:
          shape ``(n,)``.
        * ``peak_day``: shape ``(n,)``, integer dtype.

    Raises
    ------
    ValueError
        If any input is out of range or the inputs cannot be
        broadcast to a common 1-D shape.
    """
    # Broadcast to a common shape.
    try:
        bc, bm, sg, gm, at, i0v = np.broadcast_arrays(
            np.asarray(beta_class, dtype=np.float64),
            np.asarray(beta_comm, dtype=np.float64),
            np.asarray(sigma, dtype=np.float64),
            np.asarray(gamma, dtype=np.float64),
            np.asarray(attendance, dtype=np.float64),
            np.asarray(i0, dtype=np.float64),
        )
    except ValueError as exc:
        raise ValueError(
            f"seir.simulate_batch inputs must broadcast to a common shape: {exc}"
        ) from exc

    if bc.ndim == 0:
        bc, bm, sg, gm, at, i0v = (
            a.reshape(1) for a in (bc, bm, sg, gm, at, i0v)
        )
    elif bc.ndim != 1:
        raise ValueError(
            f"seir.simulate_batch inputs must be 1-D; got shape {bc.shape}."
        )

    _validate_array_inputs(
        bc, bm, sg, gm, at, i0v, days, dt, school_days_per_week,
    )

    n = bc.shape[0]
    days_i = int(days)
    n_steps = int(round(days_i / dt))

    S = 1.0 - i0v
    E = np.zeros(n, dtype=np.float64)
    I = i0v.copy()
    R = np.zeros(n, dtype=np.float64)

    S_arr = np.empty((n, n_steps + 1), dtype=np.float64)
    E_arr = np.empty((n, n_steps + 1), dtype=np.float64)
    I_arr = np.empty((n, n_steps + 1), dtype=np.float64)
    R_arr = np.empty((n, n_steps + 1), dtype=np.float64)
    S_arr[:, 0] = S
    E_arr[:, 0] = E
    I_arr[:, 0] = I
    R_arr[:, 0] = R

    for k in range(n_steps):
        t_curr = k * dt
        S, E, I, R = _rk4_step(
            S, E, I, R,
            bc, bm, sg, gm, at,
            t_curr, dt, school_days_per_week,
        )
        np.maximum(S, 0.0, out=S)
        np.maximum(E, 0.0, out=E)
        np.maximum(I, 0.0, out=I)
        np.maximum(R, 0.0, out=R)
        S_arr[:, k + 1] = S
        E_arr[:, k + 1] = E
        I_arr[:, k + 1] = I
        R_arr[:, k + 1] = R

    daily_idx = _daily_indices(days_i, dt, n_steps)
    t_daily = np.arange(days_i + 1, dtype=np.float64)
    S_daily = S_arr[:, daily_idx]
    E_daily = E_arr[:, daily_idx]
    I_daily = I_arr[:, daily_idx]
    R_daily = R_arr[:, daily_idx]

    peak_idx = np.argmax(I_daily, axis=1)
    peak_infectious = I_daily[np.arange(n), peak_idx]
    cumulative = 1.0 - S_daily[:, -1]
    attack = cumulative - i0v

    return {
        "t": t_daily,
        "S": S_daily,
        "E": E_daily,
        "I": I_daily,
        "R": R_daily,
        "attack_rate": attack,
        "peak_infectious": peak_infectious,
        "peak_day": peak_idx.astype(np.intp),
        "cumulative_infections": cumulative,
    }