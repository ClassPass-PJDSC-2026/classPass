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

from .seir import SimResult, r0_effective, simulate
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


def _resolve(value, values: Mapping[str, float]):
    """Resolve a scenario override: strings are keys in ``values``, others literals."""
    return values[value] if isinstance(value, str) else value


def _apply_overrides(
    profile: SchoolProfile, overrides: Mapping, values: Mapping[str, float]
) -> tuple[SchoolProfile, float]:
    """Apply scenario overrides, returning ``(effective_profile, attendance)``."""
    attendance = 1.0
    class_size_mult = 1.0
    updates: dict = {}
    for key, value in overrides.items():
        resolved = _resolve(value, values)
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
    profile: SchoolProfile, name: str, values: Mapping[str, float]
) -> SimResult:
    """Run one named scenario and return its :class:`SimResult`.

    Parameters
    ----------
    profile : SchoolProfile
        User-facing classroom characteristics (baseline).
    name : str
        Key in :data:`SCENARIOS`.
    values : Mapping[str, float]
        Parameter values from ``engine_values()`` — ``{key: float}``, keys as in
        ``params.yaml``. This matches the contract in ``engine.py``.

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
    effective_profile, attendance = _apply_overrides(profile, SCENARIOS[name], values)

    volume = room_volume(
        effective_profile.length_m,
        effective_profile.width_m,
        effective_profile.height_m,
    )
    q_air = airflow(effective_profile.ach, volume)
    mf = mask_factor(values["mask_efficiency"], effective_profile.mask_compliance)
    beta_class = classroom_beta(
        class_size=effective_profile.class_size,
        quanta_rate=values["quanta_rate"],
        breathing_rate=values["breathing_rate"],
        session_hours=effective_profile.session_hours,
        airflow_m3h=q_air,
        mask=mf,
        infectious_attendance=values["infectious_attendance"],
    )
    result = simulate(
        beta_class=beta_class,
        community_beta=values["community_beta"],
        sigma=1.0 / values["latent_days"],
        gamma=1.0 / values["infectious_days"],
        attendance=attendance,
        initial_infected_frac=values["initial_infected_frac"],
        sim_days=int(values["sim_days"]),
        school_days_per_week=int(values["school_days_per_week"]),
    )
    return replace(
        result,
        r0_effective=r0_effective(
            beta_class=beta_class,
            community_beta=values["community_beta"],
            gamma=1.0 / values["infectious_days"],
            attendance=attendance,
            school_days_per_week=int(values["school_days_per_week"]),
        ),
    )


def run_all(
    profile: SchoolProfile, values: Mapping[str, float]
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
    return {name: run_scenario(profile, name, values) for name in ordered}