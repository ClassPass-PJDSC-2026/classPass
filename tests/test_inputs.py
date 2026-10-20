"""Tests for schoolsim.inputs (ticket #10)."""

from __future__ import annotations

import pytest

from schoolsim.inputs import (
    VENTILATION_OPTIONS,
    clamp_int,
    describe_param,
    engine_values,
    resolve_ach,
    source_label,
    validate_inputs,
)
from schoolsim.params import base_values, load_params, load_references

PARAMS = load_params()
REFS = load_references()
VALUES = base_values(PARAMS)


def good_profile(**overrides):
    profile = {
        "class_size": 45, "length_m": 9.0, "width_m": 7.0, "height_m": 2.7, "ach": 4.0,
        "session_hours": 6.0, "mask_compliance": 0.0, "attack_rate_threshold": 0.10, "sim_days": 60,
    }
    profile.update(overrides)
    return profile


# --- validate_inputs ---------------------------------------------------------------------

def test_default_profile_is_valid():
    assert validate_inputs(good_profile(), PARAMS) == ([], [])


@pytest.mark.parametrize(
    "field, bad, label",
    [
        ("class_size", 4, "Students per class"),
        ("class_size", 81, "Students per class"),
        ("length_m", 2.9, "Room length"),
        ("width_m", 31, "Room width"),
        ("height_m", 2.0, "Room height"),
        ("ach", 0, "Air changes per hour"),
        ("ach", 0.4, "Air changes per hour"),
        ("ach", 25, "Air changes per hour"),
        ("session_hours", 3.5, "Hours in class per day"),
        ("mask_compliance", 1.2, "Mask use"),
        ("mask_compliance", -0.05, "Mask use"),
        ("attack_rate_threshold", 0.01, "Acceptable share infected"),
        ("sim_days", 10, "Simulation days"),
    ],
)
def test_out_of_range_is_an_error_naming_the_field(field, bad, label):
    errors, _ = validate_inputs(good_profile(**{field: bad}), PARAMS)
    assert len(errors) == 1 and errors[0].startswith(label)


def test_percent_fields_are_reported_as_percent():
    (error,), _ = validate_inputs(good_profile(mask_compliance=1.5), PARAMS)
    assert "0 and 100%" in error


def test_every_problem_is_reported():
    errors, _ = validate_inputs(good_profile(ach=0, class_size=500, sim_days=5), PARAMS)
    assert len(errors) == 3


@pytest.mark.parametrize("bad", [None, "9", True, float("nan")])
def test_non_numbers_are_errors(bad):
    errors, _ = validate_inputs(good_profile(length_m=bad), PARAMS)
    assert errors == ["Room length must be a number."]


def test_crowded_room_is_a_warning_not_an_error():
    errors, warnings = validate_inputs(good_profile(class_size=80, length_m=5.0, width_m=4.0), PARAMS)
    assert errors == []
    assert len(warnings) == 1 and "0.25 m²" in warnings[0]


def test_no_warning_for_standard_room():
    assert validate_inputs(good_profile(class_size=45), PARAMS)[1] == []


# --- ventilation -------------------------------------------------------------------------

@pytest.mark.parametrize(
    "option, key", [("Poor", "ach_poor"), ("Typical", "ach_typical"), ("Good", "ach_good")]
)
def test_ventilation_presets_come_from_params(option, key):
    assert resolve_ach(option, 99.0, VALUES) == VALUES[key]


def test_custom_ventilation_uses_typed_value():
    assert resolve_ach("Custom", 7.5, VALUES) == 7.5


def test_unknown_ventilation_raises():
    with pytest.raises(ValueError, match="Unknown ventilation"):
        resolve_ach("Turbo", 1.0, VALUES)


def test_ventilation_options_match_ticket():
    assert VENTILATION_OPTIONS == ("Poor", "Typical", "Good", "Custom")


# --- helpers -----------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [(44.6, 45), (3, 5), (200, 80), (47.5, 48)])
def test_clamp_int(value, expected):
    assert clamp_int(value, 5, 80) == expected


def test_engine_values_apply_sidebar_overrides():
    values = engine_values(PARAMS, good_profile(sim_days=30, attack_rate_threshold=0.2))
    assert values["sim_days"] == 30.0 and values["attack_rate_threshold"] == 0.2
    assert values["quanta_rate"] == PARAMS["quanta_rate"].value


# --- tooltips ----------------------------------------------------------------------------

def test_tooltip_has_unit_range_and_source():
    text = describe_param(PARAMS["room_length"], REFS)
    assert "Unit: m." in text and "Range: 3–30." in text and "DepEd Order No. 64, s. 2017" in text


def test_tooltip_can_show_percent():
    text = describe_param(PARAMS["mask_compliance"], REFS, scale=100, unit="%")
    assert "Unit: %." in text and "Range: 0–100." in text


def test_tooltip_omits_range_for_fixed_values():
    assert "Range" not in describe_param(PARAMS["ach_good"], REFS)


def test_source_label_prefers_references_short_field():
    assert source_label(["carrat_2008"], {"carrat_2008": {"short": "Carrat 2008"}}) == "Carrat 2008"


def test_source_label_falls_back_to_readable_key():
    assert source_label(["some_new_ref"], {}) == "some new ref"


def test_every_source_in_params_has_a_readable_label():
    for key, param in PARAMS.items():
        for source in param.source:
            label = source_label([source], REFS)
            assert "_" not in label, f"{key}: {source} has no short label"
