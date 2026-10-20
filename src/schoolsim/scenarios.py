"""Scenario definitions and runner.

Maps a user-facing :class:`SchoolProfile` plus a scenario name to the
model parameters of the coupled Wells-Riley + SEIR simulation. Every
scenario shares identical non-scenario parameters, so results are
directly comparable.

Scenario overrides (values in :data:`SCENARIOS`) are dicts mapping a
profile field to a value. The special key ``class_size_mult``
multiplies ``profile.class_size``; ``attendance`` overrides the SEIR
attendance (default 1.0). Any string value is interpreted as a key
into ``params``; numeric values are used as literals.

See ``docs/assumptions.md`` for the modelling rationale of each
scenario.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, replace

from .params import Param
from .seir import SimResult, simulate
from .wells_riley import airflow, classroom_beta, mask_factor, room_volume

__all__ = [
    "INTERVENTION_ORDER",
    "LABELS",
    "SCENARIOS",
    "SchoolProfile",
    "get_label",
    "run_all",
    "run_scenario",
]


@dataclass(frozen=True)
class SchoolProfile:
    """User-facing classroom characteristics.

    Attributes
    ----------
    class_size : int
        Number of students [students].
    length_m, width_m, height_m : float
        Room dimensions [m].
    ach : float
        Air changes per hour [1/h]. Current (baseline) ventilation.
    session_hours : float
        In-person hours per school day [h].
    mask_compliance : float
        Fraction of students wearing masks correctly [-], in [0, 1].
    """

    class_size: int
    length_m: float
    width_m: float
    height_m: float
    ach: float
    session_hours: float
    mask_compliance: float


SCENARIOS: dict[str, dict] = {
    "baseline": {},
    "better_ventilation": {"ach": "ach_good"},
    "smaller_classes": {"class_size_mult": 0.67},
    "masks": {"mask_compliance": 0.8},
    "combined": {"ach": "ach_good", "mask_compliance": 0.8},
    "hybrid": {"class_size_mult": 0.5, "attendance": 0.5},
    "online": {"attendance": 0.0},
}

LABELS: dict[str, str] = {
    "baseline": "Baseline (current practice)",
    "better_ventilation": "Better ventilation",
    "smaller_classes": "Smaller classes",
    "masks": "Masks",
    "combined": "Better ventilation + masks",
    "hybrid": "Hybrid (A/B cohorts)",
    "online": "Fully online",
}

# Ordering by disruption to normal school life (used by #14).
INTERVENTION_ORDER: tuple[str, ...] = (
    "baseline",
    "better_ventilation",
    "masks",
    "combined",
    "smaller_classes",
    "hybrid",
    "online",
)

_PROFILE_FIELDS = frozenset(f.name for f in fields(SchoolProfile))
_SPECIAL_KEYS = frozenset({"class_size_mult", "attendance"})


def get_label(name: str) -> str:
    """Human-readable label for a scenario. Falls back to ``name``."""
    return LABELS.get(name, name)


def _resolve(value, params: Mapping[str, Param]):
    """Resolve a scenario override: strings are params lookups, others literals."""
    return params[value].value if isinstance(value, str) else value


def _apply_overrides(
    profile: SchoolProfile, overrides: Mapping, params: Mapping[str, Param]
) -> tuple[SchoolProfile, float]:
    """Apply scenario overrides, returning ``(effective_profile, attendance)``."""
    attendance = 1.0
    class_size_mult = 1.0
    updates: dict = {}
    for key, value in overrides.items():
        resolved = _resolve(value, params)
        if key == "class_size_mult":
            class_size_mult = resolved
        elif key == "attendance":
            attendance = resolved
        elif key in _PROFILE_FIELDS:
            updates[key] = resolved
        else:
            raise ValueError(
                f"Unknown scenario override key: {key!r}. "
                f"Expected one of {sorted(_PROFILE_FIELDS | _SPECIAL_KEYS)}."
            )
    if class_size_mult != 1.0:
        updates["class_size"] = round(profile.class_size * class_size_mult)
    if updates:
        profile = replace(profile, **updates)
    return profile, attendance


def run_scenario(
    profile: SchoolProfile, name: str, params: Mapping[str, Param]
) -> SimResult:
    """Run one named scenario and return its :class:`SimResult`.

    Parameters
    ----------
    profile : SchoolProfile
        User-facing classroom characteristics (baseline).
    name : str
        Key in :data:`SCENARIOS`.
    params : Mapping[str, Param]
        Model parameters from ``load_params()`` (#3).

    Raises
    ------
    ValueError
        If ``name`` is not a known scenario, or an override key is
        invalid.
    """
    if name not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario {name!r}. Known: {sorted(SCENARIOS)}."
        )
    effective_profile, attendance = _apply_overrides(
        profile, SCENARIOS[name], params
    )

    volume = room_volume(
        effective_profile.length_m,
        effective_profile.width_m,
        effective_profile.height_m,
    )
    q_air = airflow(effective_profile.ach, volume)
    mf = mask_factor(
        params["mask_efficiency"].value, effective_profile.mask_compliance
    )
    beta_class = classroom_beta(
        class_size=effective_profile.class_size,
        quanta_rate=params["quanta_rate"].value,
        breathing_rate=params["breathing_rate"].value,
        session_hours=effective_profile.session_hours,
        airflow_m3h=q_air,
        mask=mf,
        infectious_attendance=params["infectious_attendance"].value,
    )
    return simulate(
        beta_class=beta_class,
        community_beta=params["community_beta"].value,
        sigma=1.0 / params["latent_days"].value,
        gamma=1.0 / params["infectious_days"].value,
        attendance=attendance,
        initial_infected_frac=params["initial_infected_frac"].value,
        sim_days=int(params["sim_days"].value),
        school_days_per_week=int(params["school_days_per_week"].value),
    )


def run_all(
    profile: SchoolProfile, params: Mapping[str, Param]
) -> dict[str, SimResult]:
    """Run every scenario defined in :data:`SCENARIOS`.

    Returns scenarios in :data:`INTERVENTION_ORDER`; any scenario not
    listed there is appended at the end in ``SCENARIOS`` insertion order.
    Adding a scenario therefore only requires editing :data:`SCENARIOS`
    (and optionally :data:`LABELS` / :data:`INTERVENTION_ORDER` for
    display and ordering).
    """
    ordered = list(INTERVENTION_ORDER) + [
        name for name in SCENARIOS if name not in INTERVENTION_ORDER
    ]
    return {name: run_scenario(profile, name, params) for name in ordered}