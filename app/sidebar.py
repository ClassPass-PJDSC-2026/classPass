"""Sidebar: the school profile (ticket #10).

Layout notes:
- Region and Level sit OUTSIDE the form because changing them must update the class-size
  default immediately, and widgets inside ``st.form`` only update on submit.
- Everything else is inside one ``st.form`` so the model runs only when the user presses
  "Run simulation", not on every slider move.
- The profile is stored in ``st.session_state["profile"]`` and only changes after the
  submitted inputs pass validation, so invalid inputs never reach the engine.
- All defaults, limits and tooltips come from params.yaml.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from schoolsim.inputs import (
    VENTILATION_OPTIONS,
    clamp_int,
    describe_param,
    resolve_ach,
    validate_inputs,
)
from schoolsim.params import Param, base_values
from schoolsim.presets import LEVELS, lookup

LEVEL_LABELS = {
    "Elementary": "Elementary",
    "JHS": "Junior high school (JHS)",
    "SHS": "Senior high school (SHS)",
}


# --- State ---------------------------------------------------------------------------

def _regions_and_levels(presets: pd.DataFrame) -> tuple[list[str], list[str]]:
    regions = list(dict.fromkeys(presets["region"]))
    present = set(presets["level"])
    levels = [lv for lv in LEVELS if lv in present] + sorted(present - set(LEVELS))
    return regions, levels


def _limits(params: Mapping[str, Param]) -> dict[str, tuple[float, float]]:
    """Allowed range per widget key, from params.yaml (mask and threshold shown as %)."""
    p = params
    return {
        "class_size": (int(p["class_size"].min), int(p["class_size"].max)),
        "room_length": (p["room_length"].min, p["room_length"].max),
        "room_width": (p["room_width"].min, p["room_width"].max),
        "room_height": (p["room_height"].min, p["room_height"].max),
        "custom_ach": (p["ach"].min, p["ach"].max),
        "session_hours": (p["session_hours"].min, p["session_hours"].max),
        "mask_pct": (round(p["mask_compliance"].min * 100), round(p["mask_compliance"].max * 100)),
        "attack_threshold_pct": (
            round(p["attack_rate_threshold"].min * 100),
            round(p["attack_rate_threshold"].max * 100),
        ),
        "sim_days": (int(p["sim_days"].min), int(p["sim_days"].max)),
    }


def _defaults(params: Mapping[str, Param], presets: pd.DataFrame) -> dict[str, Any]:
    regions, levels = _regions_and_levels(presets)
    region = "NCR" if "NCR" in regions else regions[0]
    level = levels[0]
    preset = lookup(presets, region, level)["learners_per_classroom"]
    cs = params["class_size"]
    return {
        "region": region,
        "level": level,
        "class_size": clamp_int(preset if preset else cs.value, cs.min, cs.max),
        "room_length": float(params["room_length"].value),
        "room_width": float(params["room_width"].value),
        "room_height": float(params["room_height"].value),
        "ventilation": "Typical",
        "custom_ach": float(params["ach"].value),
        "session_hours": float(params["session_hours"].value),
        "mask_pct": round(params["mask_compliance"].value * 100),
        "attack_threshold_pct": round(params["attack_rate_threshold"].value * 100),
        "sim_days": int(params["sim_days"].value),
    }


def init_state(params: Mapping[str, Param], presets: pd.DataFrame) -> None:
    """Create widget state on first load and repair any stale or out-of-range values."""
    ss = st.session_state
    defaults = _defaults(params, presets)
    regions, levels = _regions_and_levels(presets)
    limits = _limits(params)

    for key, default in defaults.items():
        ss.setdefault(key, default)

    # Repair values that would make a widget raise (e.g. after params.yaml ranges change).
    for key, (lo, hi) in limits.items():
        value = ss[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
            ss[key] = defaults[key]
    for key, options in (("region", regions), ("level", levels), ("ventilation", VENTILATION_OPTIONS)):
        if ss[key] not in options:
            ss[key] = defaults[key]

    if "profile" not in ss:
        profile = build_profile(params, presets)
        _, warnings = validate_inputs(profile, params)
        ss["profile"] = profile
        ss["profile_errors"] = []
        ss["profile_warnings"] = warnings


def build_profile(params: Mapping[str, Param], presets: pd.DataFrame) -> dict[str, Any]:
    """Read the widget state into a profile dict (not yet validated)."""
    ss = st.session_state
    values = base_values(params)
    enrollment = lookup(presets, ss["region"], ss["level"])["learners_per_school"]
    return {
        "region": ss["region"],
        "level": ss["level"],
        "class_size": int(ss["class_size"]),
        "length_m": float(ss["room_length"]),
        "width_m": float(ss["room_width"]),
        "height_m": float(ss["room_height"]),
        "ventilation": ss["ventilation"],
        "ach": resolve_ach(ss["ventilation"], ss["custom_ach"], values),
        "session_hours": float(ss["session_hours"]),
        "mask_compliance": ss["mask_pct"] / 100,
        "attack_rate_threshold": ss["attack_threshold_pct"] / 100,
        "sim_days": int(ss["sim_days"]),
        "enrollment": int(round(enrollment)) if enrollment else None,
    }


# --- Callbacks -------------------------------------------------------------------------

def _apply_preset(params: Mapping[str, Param], presets: pd.DataFrame) -> None:
    """Region or level changed: reset class size to that region's default."""
    ss = st.session_state
    cs = params["class_size"]
    default = lookup(presets, ss["region"], ss["level"])["learners_per_classroom"]
    ss["class_size"] = clamp_int(default if default else cs.value, cs.min, cs.max)


def _reset_room(params: Mapping[str, Param]) -> None:
    ss = st.session_state
    ss["room_length"] = float(params["room_length"].value)
    ss["room_width"] = float(params["room_width"].value)
    ss["room_height"] = float(params["room_height"].value)


def _handle_submit(params: Mapping[str, Param], presets: pd.DataFrame) -> None:
    ss = st.session_state
    profile = build_profile(params, presets)
    errors, warnings = validate_inputs(profile, params)
    ss["profile_errors"] = errors
    ss["profile_warnings"] = warnings
    if not errors:  # only valid profiles replace the one the engine runs on
        ss["profile"] = profile


# --- Rendering -------------------------------------------------------------------------

def _ventilation_label(params: Mapping[str, Param]):
    names = {"Poor": "ach_poor", "Typical": "ach_typical", "Good": "ach_good"}

    def fmt(option: str) -> str:
        if option == "Custom":
            return "Custom"
        return f"{option} · {params[names[option]].value:g} ACH"

    return fmt


def render_sidebar(
    params: Mapping[str, Param],
    refs: Mapping[str, Mapping[str, Any]],
    presets: pd.DataFrame,
    is_placeholder: bool,
) -> None:
    """Draw the sidebar and update ``st.session_state["profile"]`` on a valid submit."""
    sb = st.sidebar
    regions, levels = _regions_and_levels(presets)
    limits = _limits(params)
    tip = lambda key, **kw: describe_param(params[key], refs, **kw)  # noqa: E731

    sb.header("School profile")

    sb.selectbox(
        "Region",
        regions,
        key="region",
        on_change=_apply_preset,
        args=(params, presets),
        help="Sets the default class size from DepEd/PSA enrollment and classroom data. "
        "You can still change the class size below.",
    )
    sb.selectbox(
        "Level",
        levels,
        key="level",
        format_func=lambda v: LEVEL_LABELS.get(v, v),
        on_change=_apply_preset,
        args=(params, presets),
        help="School level. Changing it resets the class-size default for that level.",
    )
    if is_placeholder:
        sb.caption("Regional class sizes are placeholders until the presets file (#8) is built.")

    L, W, H = params["room_length"], params["room_width"], params["room_height"]
    sb.button(
        f"Use DepEd standard room ({L.value:g} × {W.value:g} × {H.value:g} m)",
        key="std_room",
        on_click=_reset_room,
        args=(params,),
        help="Fills the three room dimensions below with the standard classroom size.",
    )

    with sb.form("profile_form"):
        lo, hi = limits["class_size"]
        st.number_input(
            "Students per class",
            min_value=lo,
            max_value=hi,
            step=1,
            key="class_size",
            help=tip("class_size"),
        )

        st.caption("Room size (metres)")
        c1, c2, c3 = st.columns(3)
        for col, key, label, step in (
            (c1, "room_length", "Length", 0.5),
            (c2, "room_width", "Width", 0.5),
            (c3, "room_height", "Height", 0.1),
        ):
            lo, hi = limits[key]
            with col:
                st.number_input(
                    label,
                    min_value=float(lo),
                    max_value=float(hi),
                    step=step,
                    format="%.1f",
                    key=key,
                    help=tip(key),
                )

        st.selectbox(
            "Ventilation",
            VENTILATION_OPTIONS,
            key="ventilation",
            format_func=_ventilation_label(params),
            help="Air changes per hour (ACH) of clean air. Poor, Typical and Good use "
            f"{params['ach_poor'].value:g}, {params['ach_typical'].value:g} and "
            f"{params['ach_good'].value:g} ACH. Choose Custom to type your own value below. "
            f"Source: {describe_param(params['ach_good'], refs).split('Source: ')[-1]}",
        )
        lo, hi = limits["custom_ach"]
        st.number_input(
            "Custom air changes per hour (ACH)",
            min_value=float(lo),
            max_value=float(hi),
            step=0.5,
            format="%.1f",
            key="custom_ach",
            help="Used only when Ventilation is set to Custom. " + tip("ach"),
        )

        lo, hi = limits["session_hours"]
        st.slider(
            "Hours in class per day",
            min_value=float(lo),
            max_value=float(hi),
            step=0.5,
            format="%.1f",
            key="session_hours",
            help=tip("session_hours"),
        )

        lo, hi = limits["mask_pct"]
        st.slider(
            "Students wearing masks",
            min_value=int(lo),
            max_value=int(hi),
            step=5,
            format="%d%%",
            key="mask_pct",
            help=tip("mask_compliance", scale=100, unit="%"),
        )

        with st.expander("Advanced"):
            lo, hi = limits["attack_threshold_pct"]
            st.slider(
                "Acceptable share of students infected",
                min_value=int(lo),
                max_value=int(hi),
                step=1,
                format="%d%%",
                key="attack_threshold_pct",
                help=tip("attack_rate_threshold", scale=100, unit="%"),
            )
            lo, hi = limits["sim_days"]
            if lo < hi:
                st.slider(
                    "Simulation days",
                    min_value=int(lo),
                    max_value=int(hi),
                    step=5 if (hi - lo) % 5 == 0 else 1,
                    key="sim_days",
                    help=tip("sim_days"),
                )
            else:
                st.caption(f"Simulation length: {int(lo)} days (fixed). {tip('sim_days')}")

        submitted = st.form_submit_button("Run simulation", type="primary")

    if submitted:
        _handle_submit(params, presets)

    for message in st.session_state.get("profile_errors", []):
        sb.error(message)
    for message in st.session_state.get("profile_warnings", []):
        sb.warning(message)
    sb.caption("Results update when you press Run simulation.")
