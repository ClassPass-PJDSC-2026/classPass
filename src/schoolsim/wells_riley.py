"""Wells-Riley airborne infection model for classroom transmission.

This module converts the physical characteristics of a classroom
(dimensions, ventilation, mask use) into a per-school-day transmission
rate (``beta``) suitable for an SEIR model. It is pure: no I/O, no
global state, and every public function accepts scalars or NumPy
arrays for vectorised batch simulations.

Equations
---------
Room volume [m^3]::

    V = L * W * H

Airflow [m^3/h]::

    Q = ACH * V

Mask factor (dimensionless, applied to both emission and inhalation)::

    mf = (1 - efficiency * compliance) ** 2

Wells-Riley per-session infection probability [-]::

    P = 1 - exp(-I * q * p * t * mf / Q)

    I  : number of infectors present in the room [people]
    q  : quanta generation rate [quanta/h]
    p  : breathing rate [m^3/h]
    t  : exposure time [h]
    mf : mask factor in [0, 1] (see :func:`mask_factor`)
    Q  : ventilation airflow [m^3/h]

Per-school-day transmission rate [1/day]::

    beta = N * a * q * p * t * mf / Q

    N : class size [students]
    a : infectious attendance fraction [-]

The factor ``N * a`` arises from homogeneous mixing: in a class of
``N`` students where a fraction ``I/N`` is infected, the expected
number of infectors present on a school day is
``N * (I/N) * a = I * a``, so the force of infection is
``beta * I/N``.

Notes
-----
* Wells-Riley assumes a well-mixed room at steady state. This is a
  modelling limitation, not an implementation detail.
* The exponent of Wells-Riley is the per-session hazard, so using it
  directly as a daily rate is exact (no approximation needed).
* All functions are pure and accept ``numpy.ndarray`` inputs so
  ``simulate_batch`` and sensitivity runs stay fast.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "airflow",
    "classroom_beta",
    "infection_probability",
    "mask_factor",
    "room_volume",
]


def _to_array(value: ArrayLike) -> NDArray[np.float64]:
    return np.asarray(value, dtype=float)


def _scalar_or_array(value: ArrayLike) -> float | NDArray[np.float64]:
    arr = _to_array(value)
    if arr.ndim == 0:
        return float(arr)
    return arr


def _check_non_negative(name: str, value: ArrayLike) -> NDArray[np.float64]:
    arr = _to_array(value)
    if np.any(arr < 0):
        raise ValueError(f"{name} must be non-negative; got {value!r}.")
    return arr


def _check_unit_interval(name: str, value: ArrayLike) -> NDArray[np.float64]:
    arr = _to_array(value)
    if np.any((arr < 0) | (arr > 1)):
        raise ValueError(
            f"{name} must be in the closed interval [0, 1]; got {value!r}."
        )
    return arr


def _check_airflow(value: ArrayLike) -> NDArray[np.float64]:
    arr = _to_array(value)
    if np.any(arr <= 0):
        raise ValueError(
            "airflow_m3h must be positive; check ACH and room volume."
        )
    return arr


def room_volume(
    length_m: ArrayLike,
    width_m: ArrayLike,
    height_m: ArrayLike,
) -> float | NDArray[np.float64]:
    """Classroom volume ``V = L * W * H`` in cubic metres [m^3].

    Parameters
    ----------
    length_m, width_m, height_m :
        Room dimensions in metres. Scalars or arrays; arrays broadcast.

    Returns
    -------
    float | ndarray
        Volume [m^3]. A Python ``float`` for scalar inputs, an
        ``ndarray`` for array inputs.

    Raises
    ------
    ValueError
        If any dimension is negative.
    """
    length = _check_non_negative("length_m", length_m)
    width = _check_non_negative("width_m", width_m)
    height = _check_non_negative("height_m", height_m)
    return _scalar_or_array(length * width * height)


def airflow(
    ach: ArrayLike,
    volume_m3: ArrayLike,
) -> float | NDArray[np.float64]:
    """Ventilation airflow ``Q = ACH * V`` in cubic metres per hour [m^3/h].

    Parameters
    ----------
    ach :
        Air changes per hour [1/h]. Non-negative.
    volume_m3 :
        Room volume [m^3]. Non-negative.

    Returns
    -------
    float | ndarray
        Airflow Q [m^3/h].

    Raises
    ------
    ValueError
        If ``ach`` or ``volume_m3`` is negative, or if the resulting
        airflow is zero (a room with no ventilation cannot be modelled
        by Wells-Riley; the UI should surface this message).
    """
    ach_arr = _check_non_negative("ach", ach)
    vol_arr = _check_non_negative("volume_m3", volume_m3)
    q = ach_arr * vol_arr
    return _scalar_or_array(_check_airflow(q))


def mask_factor(
    efficiency: ArrayLike,
    compliance: ArrayLike,
) -> float | NDArray[np.float64]:
    """Mask factor ``mf = (1 - efficiency * compliance) ** 2`` [-].

    Applied to both emission and inhalation, hence the square.
    A value of 1 means no protection; 0 means perfect protection.

    Parameters
    ----------
    efficiency :
        Mask filtration efficiency [-], in [0, 1].
    compliance :
        Fraction of people wearing masks correctly [-], in [0, 1].

    Returns
    -------
    float | ndarray
        Mask factor in [0, 1].
    """
    eff = _check_unit_interval("efficiency", efficiency)
    comp = _check_unit_interval("compliance", compliance)
    return _scalar_or_array((1.0 - eff * comp) ** 2)


def infection_probability(
    n_infectors: ArrayLike,
    quanta_rate: ArrayLike,
    breathing_rate: ArrayLike,
    session_hours: ArrayLike,
    airflow_m3h: ArrayLike,
    mask: ArrayLike = 1.0,
) -> float | NDArray[np.float64]:
    """Wells-Riley per-session infection probability ``P`` [-].

    ``P = 1 - exp(-I * q * p * t * mask / Q)``.

    Parameters
    ----------
    n_infectors :
        Number of infectors in the room [people]. If 0, returns 0.
    quanta_rate :
        Quanta generation rate [quanta/h].
    breathing_rate :
        Breathing rate [m^3/h].
    session_hours :
        Exposure time [h].
    airflow_m3h :
        Ventilation airflow Q [m^3/h]. Must be positive.
    mask :
        Mask factor (dimensionless multiplier in [0, 1]) produced by
        :func:`mask_factor`. Default 1.0 means no protection.

    Returns
    -------
    float | ndarray
        Probability of infection in [0, 1].

    Raises
    ------
    ValueError
        If any input is negative, if ``airflow_m3h`` is not positive,
        or if ``mask`` falls outside [0, 1].
    """
    infectors = _check_non_negative("n_infectors", n_infectors)
    q = _check_non_negative("quanta_rate", quanta_rate)
    p = _check_non_negative("breathing_rate", breathing_rate)
    t = _check_non_negative("session_hours", session_hours)
    q_air = _check_airflow(airflow_m3h)
    mf = _check_unit_interval("mask", mask)

    exponent = infectors * q * p * t * mf / q_air
    probability = 1.0 - np.exp(-exponent)
    probability = np.clip(probability, 0.0, 1.0)
    return _scalar_or_array(probability)


def classroom_beta(
    class_size: ArrayLike,
    quanta_rate: ArrayLike,
    breathing_rate: ArrayLike,
    session_hours: ArrayLike,
    airflow_m3h: ArrayLike,
    mask: ArrayLike = 1.0,
    infectious_attendance: ArrayLike = 1.0,
) -> float | NDArray[np.float64]:
    """Per-school-day transmission rate ``beta`` [1/day].

    ``beta = N * a * q * p * t * mask / Q``.

    See the module docstring for the homogeneous-mixing derivation.

    Parameters
    ----------
    class_size :
        Number of students in the class [students].
    quanta_rate :
        Quanta generation rate [quanta/h].
    breathing_rate :
        Breathing rate [m^3/h].
    session_hours :
        Hours of in-person exposure per school day [h].
    airflow_m3h :
        Ventilation airflow Q [m^3/h]. Must be positive.
    mask :
        Mask factor (dimensionless multiplier in [0, 1]).
    infectious_attendance :
        Fraction of the class physically present on a typical day [-],
        in [0, 1]. Face-to-face = 1, hybrid = 0.5, online = 0.

    Returns
    -------
    float | ndarray
        Transmission rate [1/day]. Online modality (attendance 0)
        therefore yields beta = 0.

    Raises
    ------
    ValueError
        If any input is negative, if ``airflow_m3h`` is not positive,
        or if ``mask`` or ``infectious_attendance`` fall outside [0, 1].
    """
    n = _check_non_negative("class_size", class_size)
    q = _check_non_negative("quanta_rate", quanta_rate)
    p = _check_non_negative("breathing_rate", breathing_rate)
    t = _check_non_negative("session_hours", session_hours)
    q_air = _check_airflow(airflow_m3h)
    mf = _check_unit_interval("mask", mask)
    a = _check_unit_interval("infectious_attendance", infectious_attendance)

    beta = n * a * q * p * t * mf / q_air
    return _scalar_or_array(beta)