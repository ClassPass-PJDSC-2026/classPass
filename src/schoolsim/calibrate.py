"""Calibrated R0 mode: solve for the quanta rate that reproduces a target R0.

Physical mode (the default) takes a quanta rate as given and computes transmission
from room properties. Calibrated mode inverts that: the user names a target R0 for
the baseline school, and this module solves for the quanta rate that produces it.
After calibration, ventilation, masks, class size and modality still change
transmission from that baseline - only the quanta rate is fixed.

Calibration is a modelling convenience, not a measurement. It converts a
literature-reported R0 into a quanta rate that is self-consistent with the rest
of the parameters in this model. It does not make that quanta rate a better
estimate of physical reality than the physical-mode default; it anchors the
simulation to a quantity (R0) with better empirical support than the quanta
rate alone.

The disease presets below are placeholders. Their R0 ranges are commonly cited
but not yet verified against a specific source; their latent and infectious
periods are order-of-magnitude figures. See the "Calibrated R0 mode" section
of ``docs/assumptions.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from .params import Param
from .scenarios import SchoolProfile
from .wells_riley import airflow, mask_factor, room_volume

__all__ = [
    "CUSTOM_R0_MAX",
    "CUSTOM_R0_MIN",
    "DISEASE_PRESETS",
    "DiseasePreset",
    "build_params_for_mode",
    "calibrate_quanta",
    "make_custom_preset",
]

# Bounds for the custom-R0 preset (see ticket #23 AC: "Custom R0 in 0.5-20").
CUSTOM_R0_MIN = 0.5
CUSTOM_R0_MAX = 20.0


@dataclass(frozen=True)
class DiseasePreset:
    """A named disease target for calibrated R0 mode.

    Attributes:
        name: Human-readable preset name.
        r0: Nominal R0 for the baseline school [-].
        r0_min: Lower bound of the plausible R0 range [-]; drives the lower
            end of sensitivity sampling in calibrated mode.
        r0_max: Upper bound of the plausible R0 range [-].
        latent_days: Days from infection to becoming infectious [days].
        latent_days_min: Lower bound for latent_days [days].
        latent_days_max: Upper bound for latent_days [days].
        infectious_days: Days a student stays infectious [days].
        infectious_days_min: Lower bound for infectious_days [days].
        infectious_days_max: Upper bound for infectious_days [days].
        source: Where the values came from (free text; presets below carry a
            placeholder marker until primary sources are available).
    """

    name: str
    r0: float
    r0_min: float
    r0_max: float
    latent_days: float
    latent_days_min: float
    latent_days_max: float
    infectious_days: float
    infectious_days_min: float
    infectious_days_max: float
    source: str


DISEASE_PRESETS: dict[str, DiseasePreset] = {
    "influenza": DiseasePreset(
        name="Seasonal influenza",
        r0=1.3,
        r0_min=1.0,
        r0_max=2.0,
        latent_days=1.0,
        latent_days_min=0.5,
        latent_days_max=2.0,
        infectious_days=4.8,
        infectious_days_min=3.5,
        infectious_days_max=7.0,
        source="placeholder; commonly cited range but not yet verified against a primary source",
    ),
    "covid": DiseasePreset(
        name="COVID-19",
        r0=3.0,
        r0_min=2.5,
        r0_max=3.5,
        latent_days=3.0,
        latent_days_min=2.0,
        latent_days_max=5.0,
        infectious_days=7.0,
        infectious_days_min=5.0,
        infectious_days_max=10.0,
        source="placeholder; commonly cited range but not yet verified against a primary source",
    ),
    "measles": DiseasePreset(
        name="Measles",
        r0=15.0,
        r0_min=12.0,
        r0_max=18.0,
        latent_days=10.0,
        latent_days_min=7.0,
        latent_days_max=14.0,
        infectious_days=7.0,
        infectious_days_min=4.0,
        infectious_days_max=9.0,
        source="placeholder; commonly cited range but not yet verified against a primary source",
    ),
}


def calibrate_quanta(
    target_r0: float,
    profile: SchoolProfile,
    params: Mapping[str, Param],
) -> float:
    """Solve for the quanta rate that reproduces ``target_r0`` at baseline.

    Baseline means face-to-face (attendance 1.0), no scenario overrides,
    calibrated at the given ``profile``'s ACH, class size, session hours and
    mask compliance. Solves::

        R0 = (school_days/7 * beta_class + community_beta) / gamma
        beta_class = N * a * q * p * t * mf / Q

    for the quanta rate ``q`` [quanta/h]::

        q = (R0 * gamma - community_beta) * (7 / school_days)
            * Q / (N * a * p * t * mf)

    Parameters:
        target_r0: Desired effective R0 at baseline [-] (must be strictly
            greater than the community-only R0).
        profile: Baseline classroom; ACH, class size, session hours and mask
            compliance define the calibration point.
        params: Model parameters. ``latent_days`` and ``infectious_days`` are
            used as given; callers wanting a disease preset's gamma must
            pre-substitute them (see :func:`build_params_for_mode`).

    Returns:
        Calibrated quanta rate [quanta/h].

    Raises:
        ValueError: If ``target_r0 <= 0``, if ``target_r0 * gamma <=
            community_beta`` (community transmission alone already exceeds the
            target), or if any denominator term is zero.
    """
    if target_r0 <= 0:
        raise ValueError(f"target_r0 must be positive; got {target_r0}")

    gamma = 1.0 / params["infectious_days"].value
    beta_comm = params["community_beta"].value
    community_only_r0 = beta_comm / gamma
    if target_r0 <= community_only_r0:
        raise ValueError(
            f"target_r0={target_r0:.3f} is not achievable: community transmission "
            f"alone gives R0={community_only_r0:.3f}. Set target_r0 above "
            f"{community_only_r0:.3f}, or lower community_beta."
        )

    volume = room_volume(profile.length_m, profile.width_m, profile.height_m)
    q_air = airflow(profile.ach, volume)
    mf = mask_factor(params["mask_efficiency"].value, profile.mask_compliance)
    n = float(profile.class_size)
    a = params["infectious_attendance"].value
    p = params["breathing_rate"].value
    t = profile.session_hours

    denominator = n * a * p * t * mf
    if denominator <= 0:
        raise ValueError(
            f"calibration is impossible: n*a*p*t*mf = {denominator}. "
            "Check class_size, session_hours and mask settings."
        )

    school_days = params["school_days_per_week"].value
    return (target_r0 * gamma - beta_comm) * (7.0 / school_days) * q_air / denominator


def make_custom_preset(target_r0: float) -> DiseasePreset:
    """Build a ``DiseasePreset`` for a user-supplied R0 with a 0.5-20 range.

    Latent and infectious periods default to the base (influenza) values so
    only R0 differs from the default preset.

    Raises:
        ValueError: If ``target_r0`` is outside ``[CUSTOM_R0_MIN, CUSTOM_R0_MAX]``.
    """
    if not CUSTOM_R0_MIN <= target_r0 <= CUSTOM_R0_MAX:
        raise ValueError(
            f"custom R0 must be in [{CUSTOM_R0_MIN}, {CUSTOM_R0_MAX}]; got {target_r0}"
        )
    return DiseasePreset(
        name=f"Custom (R0={target_r0:.2f})",
        r0=target_r0,
        r0_min=CUSTOM_R0_MIN,
        r0_max=CUSTOM_R0_MAX,
        latent_days=1.0,
        latent_days_min=0.5,
        latent_days_max=2.0,
        infectious_days=4.8,
        infectious_days_min=3.5,
        infectious_days_max=7.0,
        source="user input",
    )


def build_params_for_mode(
    base_params: Mapping[str, Param],
    mode: str,
    *,
    target_r0: float | None = None,
    profile: SchoolProfile | None = None,
    preset: DiseasePreset | None = None,
) -> dict[str, Param]:
    """Return a parameter dict for the given mode.

    Physical mode returns a shallow copy of ``base_params`` unchanged.
    Calibrated mode returns a copy with ``quanta_rate``, ``latent_days`` and
    ``infectious_days`` replaced. Downstream code (``scenarios``,
    ``sensitivity``) sees only ``Param`` objects and needs no mode awareness.

    Parameters:
        base_params: Parameters from ``params.load_params()``.
        mode: ``"physical"`` or ``"calibrated"``.
        target_r0: Target R0 at baseline [-]. Required for ``"calibrated"``.
        profile: Baseline classroom. Required for ``"calibrated"``.
        preset: Disease preset; defaults to ``DISEASE_PRESETS["influenza"]``.
            Its latent/infectious periods (with ranges) substitute the base
            params, and its ``r0_min``/``r0_max`` set the sensitivity range
            on the calibrated quanta rate.

    Returns:
        Parameter dict for the chosen mode.

    Raises:
        ValueError: If ``mode`` is unknown, if required arguments for the
            chosen mode are missing, or if calibration fails (see
            :func:`calibrate_quanta`).
    """
    if mode == "physical":
        return dict(base_params)
    if mode != "calibrated":
        raise ValueError(f"mode must be 'physical' or 'calibrated'; got {mode!r}")
    if target_r0 is None:
        raise ValueError("target_r0 is required for calibrated mode")
    if profile is None:
        raise ValueError("profile is required for calibrated mode")
    if preset is None:
        preset = DISEASE_PRESETS["influenza"]

    # Substitute disease-specific params *before* calibration, so
    # calibrate_quanta sees the same gamma downstream results will use.
    substituted = dict(base_params)
    substituted["latent_days"] = _replace_param(
        base_params["latent_days"],
        value=preset.latent_days,
        min_=preset.latent_days_min,
        max_=preset.latent_days_max,
        description=(
            f"{base_params['latent_days'].description} "
            f"(calibrated mode: {preset.name}; placeholder value, see assumptions.md)"
        ),
        source=("team_assumption",),
    )
    substituted["infectious_days"] = _replace_param(
        base_params["infectious_days"],
        value=preset.infectious_days,
        min_=preset.infectious_days_min,
        max_=preset.infectious_days_max,
        description=(
            f"{base_params['infectious_days'].description} "
            f"(calibrated mode: {preset.name}; placeholder value, see assumptions.md)"
        ),
        source=("team_assumption",),
    )

    q_calibrated = calibrate_quanta(target_r0, profile, substituted)

    # Sensitivity samples R0 across the preset's range. If the user's target
    # falls outside that range, widen the range to include it rather than
    # produce a Param whose value sits outside [min, max].
    effective_r0_min = min(preset.r0_min, target_r0)
    effective_r0_max = max(preset.r0_max, target_r0)
    try:
        q_min = calibrate_quanta(effective_r0_min, profile, substituted)
    except ValueError as exc:
        raise ValueError(
            f"cannot construct a calibrated sensitivity range for preset "
            f"{preset.name!r}: its lower bound R0={effective_r0_min:.2f} is "
            f"not achievable at these settings ({exc})"
        ) from exc
    try:
        q_max = calibrate_quanta(effective_r0_max, profile, substituted)
    except ValueError as exc:
        raise ValueError(
            f"cannot construct a calibrated sensitivity range for preset "
            f"{preset.name!r}: its upper bound R0={effective_r0_max:.2f} is "
            f"not achievable at these settings ({exc})"
        ) from exc

    substituted["quanta_rate"] = _replace_param(
        base_params["quanta_rate"],
        value=q_calibrated,
        min_=q_min,
        max_=q_max,
        description=(
            f"Quanta rate calibrated to R0={target_r0:.2f} ({preset.name}); "
            f"sensitivity spans R0 {effective_r0_min:.2f}-{effective_r0_max:.2f}. "
            f"Preset values are placeholders pending a primary source."
        ),
        source=("team_assumption",),
        in_sensitivity=True,
    )
    return substituted


def _replace_param(
    param: Param,
    *,
    value: float,
    min_: float,
    max_: float,
    description: str | None = None,
    source: tuple[str, ...] | None = None,
    in_sensitivity: bool | None = None,
) -> Param:
    """Return a copy of ``param`` with new value/min/max, other fields unchanged.

    ``source`` must be a tuple of reference keys (or reserved keys
    ``team_assumption`` / ``team_decision``), matching ``Param.source``'s
    type. Never pass a bare string: downstream code iterates
    ``Param.source`` and a string iterates characters.
    """
    return replace(
        param,
        value=value,
        min=min_,
        max=max_,
        description=description if description is not None else param.description,
        source=source if source is not None else param.source,
        in_sensitivity=(
            in_sensitivity if in_sensitivity is not None else param.in_sensitivity
        ),
    )