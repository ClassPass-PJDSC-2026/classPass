"""Tests for schoolsim.calibrate (calibrated R0 mode, ticket #23)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from schoolsim.calibrate import (
    CUSTOM_R0_MAX,
    CUSTOM_R0_MIN,
    DISEASE_PRESETS,
    build_params_for_mode,
    calibrate_quanta,
    make_custom_preset,
)
from schoolsim.params import load_params
from schoolsim.scenarios import SchoolProfile
from schoolsim.seir import r0_effective
from schoolsim.wells_riley import airflow, classroom_beta, mask_factor, room_volume


def _base_params():
    return load_params()


def _make_profile(params, *, ach=None, mask_compliance=None) -> SchoolProfile:
    return SchoolProfile(
        class_size=int(params["class_size"].value),
        length_m=params["room_length"].value,
        width_m=params["room_width"].value,
        height_m=params["room_height"].value,
        ach=ach if ach is not None else params["ach"].value,
        session_hours=params["session_hours"].value,
        mask_compliance=(
            mask_compliance if mask_compliance is not None else params["mask_compliance"].value
        ),
    )


def _beta_for(params, profile: SchoolProfile, *, quanta_rate: float) -> float:
    volume = room_volume(profile.length_m, profile.width_m, profile.height_m)
    q_air = airflow(profile.ach, volume)
    mf = mask_factor(params["mask_efficiency"].value, profile.mask_compliance)
    return classroom_beta(
        class_size=profile.class_size,
        quanta_rate=quanta_rate,
        breathing_rate=params["breathing_rate"].value,
        session_hours=profile.session_hours,
        airflow_m3h=q_air,
        mask=mf,
        infectious_attendance=params["infectious_attendance"].value,
    )


def _r0_for(params, profile: SchoolProfile, *, quanta_rate: float) -> float:
    beta = _beta_for(params, profile, quanta_rate=quanta_rate)
    gamma = 1.0 / params["infectious_days"].value
    return r0_effective(
        beta, params["community_beta"].value, gamma, attendance=1.0,
    )


# --- AC #1: baseline R0 in calibrated mode equals target within 0.1% ----------


def test_round_trip_target_r0():
    params = _base_params()
    profile = _make_profile(params)
    q = calibrate_quanta(1.5, profile, params)
    r0 = _r0_for(params, profile, quanta_rate=q)
    assert abs(r0 - 1.5) / 1.5 < 1e-6  # far tighter than the 1e-3 AC


def test_round_trip_with_each_preset():
    params = _base_params()
    profile = _make_profile(params)
    for preset_name, preset in DISEASE_PRESETS.items():
        adjusted = build_params_for_mode(
            params, "calibrated", target_r0=preset.r0, profile=profile, preset=preset,
        )
        r0 = _r0_for(adjusted, profile, quanta_rate=adjusted["quanta_rate"].value)
        assert abs(r0 - preset.r0) / preset.r0 < 1e-6, preset_name


# --- AC #2: target <= community-only R0 raises with a clear message -----------


def test_target_equal_to_community_only_r0_raises():
    params = _base_params()
    profile = _make_profile(params)
    gamma = 1.0 / params["infectious_days"].value
    community_only = params["community_beta"].value / gamma
    with pytest.raises(ValueError, match="not achievable"):
        calibrate_quanta(community_only, profile, params)


def test_target_below_community_only_r0_raises():
    params = _base_params()
    profile = _make_profile(params)
    gamma = 1.0 / params["infectious_days"].value
    community_only = params["community_beta"].value / gamma
    with pytest.raises(ValueError, match="not achievable"):
        calibrate_quanta(community_only - 0.1, profile, params)


def test_target_zero_raises():
    params = _base_params()
    profile = _make_profile(params)
    with pytest.raises(ValueError, match="positive"):
        calibrate_quanta(0.0, profile, params)


# --- AC #3: doubling ACH halves classroom beta (fixed q, varying ach) ---------


def test_doubling_ach_with_fixed_q_halves_beta():
    """Ventilation still acts after calibration: q fixed, ach doubled -> beta halves."""
    params = _base_params()
    profile = _make_profile(params)
    q = calibrate_quanta(1.5, profile, params)

    beta_base = _beta_for(params, profile, quanta_rate=q)
    profile_2x = replace(profile, ach=2.0 * profile.ach)
    beta_2x = _beta_for(params, profile_2x, quanta_rate=q)

    assert beta_2x / beta_base == pytest.approx(0.5, rel=1e-9)


def test_recalibrating_at_higher_ach_keeps_beta_constant():
    """Recalibrating for the new ACH gives the same beta - that's the point of calibration."""
    params = _base_params()
    profile = _make_profile(params)
    profile_2x = replace(profile, ach=2.0 * profile.ach)

    q_base = calibrate_quanta(1.5, profile, params)
    q_2x = calibrate_quanta(1.5, profile_2x, params)

    # Quanta doubles to compensate for the doubled airflow.
    assert q_2x / q_base == pytest.approx(2.0, rel=1e-9)

    # Beta is preserved.
    assert _beta_for(params, profile_2x, quanta_rate=q_2x) == pytest.approx(
        _beta_for(params, profile, quanta_rate=q_base), rel=1e-9
    )


# --- AC #5: sensitivity varies R0 range, not raw quanta -----------------------


def test_calibrated_quanta_param_range_spans_preset_r0_range():
    params = _base_params()
    profile = _make_profile(params)
    preset = DISEASE_PRESETS["influenza"]
    adjusted = build_params_for_mode(
        params, "calibrated", target_r0=1.5, profile=profile, preset=preset,
    )
    q_param = adjusted["quanta_rate"]
    assert q_param.in_sensitivity is True
    assert q_param.min < q_param.value < q_param.max
    # q_min should reproduce preset.r0_min, q_max should reproduce preset.r0_max.
    r0_at_min = _r0_for(adjusted, profile, quanta_rate=q_param.min)
    r0_at_max = _r0_for(adjusted, profile, quanta_rate=q_param.max)
    assert r0_at_min == pytest.approx(preset.r0_min, rel=1e-6)
    assert r0_at_max == pytest.approx(preset.r0_max, rel=1e-6)


def test_calibrated_range_widens_to_include_out_of_range_target():
    """target_r0 outside the preset's range expands the sensitivity range rather
    than producing a Param whose value sits outside [min, max]."""
    params = _base_params()
    profile = _make_profile(params)
    preset = DISEASE_PRESETS["influenza"]  # r0_max = 2.0
    adjusted = build_params_for_mode(
        params, "calibrated", target_r0=3.0, profile=profile, preset=preset,
    )
    q_param = adjusted["quanta_rate"]
    assert q_param.min <= q_param.value <= q_param.max
    # Range now extends up to R0=3.0, not preset.r0_max=2.0.
    r0_at_max = _r0_for(adjusted, profile, quanta_rate=q_param.max)
    assert r0_at_max == pytest.approx(3.0, rel=1e-6)


def test_calibrated_mode_substitutes_latent_and_infectious_days():
    params = _base_params()
    profile = _make_profile(params)
    covid = DISEASE_PRESETS["covid"]
    adjusted = build_params_for_mode(
        params, "calibrated", target_r0=3.0, profile=profile, preset=covid,
    )
    assert adjusted["latent_days"].value == covid.latent_days
    assert adjusted["infectious_days"].value == covid.infectious_days


def test_physical_mode_returns_params_unchanged():
    params = _base_params()
    result = build_params_for_mode(params, "physical")
    assert result == dict(params)
    assert result["quanta_rate"] is params["quanta_rate"]  # not replaced


# --- AC #6: custom R0 in 0.5-20 -----------------------------------------------


def test_custom_preset_within_bounds_ok():
    for target in (CUSTOM_R0_MIN, 1.5, 10.0, CUSTOM_R0_MAX):
        preset = make_custom_preset(target)
        assert preset.r0 == target
        assert preset.r0_min == CUSTOM_R0_MIN
        assert preset.r0_max == CUSTOM_R0_MAX


@pytest.mark.parametrize("target", [0.4, 0.0, -1.0, 20.1, 100.0])
def test_custom_preset_out_of_bounds_raises(target):
    with pytest.raises(ValueError, match="custom R0"):
        make_custom_preset(target)


# --- Determinism and defensive errors ----------------------------------------


def test_calibration_is_deterministic():
    params = _base_params()
    profile = _make_profile(params)
    assert calibrate_quanta(1.5, profile, params) == calibrate_quanta(1.5, profile, params)


def test_unknown_mode_raises():
    params = _base_params()
    with pytest.raises(ValueError, match="mode"):
        build_params_for_mode(params, "sorcery")


def test_calibrated_mode_missing_target_raises():
    params = _base_params()
    profile = _make_profile(params)
    with pytest.raises(ValueError, match="target_r0"):
        build_params_for_mode(params, "calibrated", profile=profile)


def test_calibrated_mode_missing_profile_raises():
    params = _base_params()
    with pytest.raises(ValueError, match="profile"):
        build_params_for_mode(params, "calibrated", target_r0=1.5)


def test_calibration_with_masks_worn_works():
    """Mask factor is in the denominator; a masked class needs a higher quanta rate."""
    params = _base_params()
    profile_unmasked = _make_profile(params, mask_compliance=0.0)
    profile_masked = _make_profile(params, mask_compliance=0.8)
    q_unmasked = calibrate_quanta(1.5, profile_unmasked, params)
    q_masked = calibrate_quanta(1.5, profile_masked, params)
    assert q_masked > q_unmasked  # more quanta needed to overcome masks
    assert _r0_for(params, profile_masked, quanta_rate=q_masked) == pytest.approx(1.5, rel=1e-6)