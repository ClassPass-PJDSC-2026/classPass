"""Pure helpers behind the Streamlit sidebar (ticket #10).

Everything here is plain Python so it can be unit-tested without Streamlit. The app calls
:func:`validate_inputs` before running the engine; if it returns errors, the engine is not
called.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from schoolsim.params import Param

VENTILATION_OPTIONS = ("Poor", "Typical", "Good", "Custom")
VENTILATION_PARAM = {"Poor": "ach_poor", "Typical": "ach_typical", "Good": "ach_good"}
VENTILATION_CAPTIONS = {
    "Poor": "windows mostly closed",
    "Typical": "windows open",
    "Good": "windows open plus fans or an air cleaner",
}

# Warn below this floor area per student (m²). Bug-bash rule from the ticket list.
MIN_AREA_PER_STUDENT_M2 = 1.0

# Labels for the reserved source keys that have no entry in references.yaml.
_RESERVED_LABELS = {
    "team_assumption": "team assumption",
    "team_decision": "team decision",
}


def source_label(keys: tuple[str, ...] | list[str], refs: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    """Human-readable source text for tooltips, e.g. ``"Carrat et al. (2008), team assumption"``.

    The label comes from the ``short`` field of the entry in references.yaml."""
    refs = refs or {}
    labels = []
    for key in keys:
        label = refs.get(key, {}).get("short") or _RESERVED_LABELS.get(key) or key.replace("_", " ")
        labels.append(label)
    return ", ".join(labels)


def _fmt(x: float) -> str:
    return f"{x:g}"


def describe_param(
    param: Param,
    refs: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    scale: float = 1.0,
    unit: str | None = None,
) -> str:
    """Tooltip text: description, unit, range and source for one parameter.

    ``scale`` and ``unit`` let fractions be shown as percentages (``scale=100, unit="%"``).
    """
    shown_unit = unit if unit is not None else param.unit
    lo, hi = param.min * scale, param.max * scale
    parts = [f"{param.description}.", f"Unit: {shown_unit}."]
    if lo != hi:
        parts.append(f"Range: {_fmt(lo)}–{_fmt(hi)}.")
    parts.append(f"Source: {source_label(param.source, refs)}.")
    return " ".join(parts)


def resolve_ach(ventilation: str, custom_ach: float, values: Mapping[str, float]) -> float:
    """Air changes per hour for a ventilation choice (Poor / Typical / Good / Custom)."""
    if ventilation == "Custom":
        return float(custom_ach)
    if ventilation not in VENTILATION_PARAM:
        raise ValueError(f"Unknown ventilation option: {ventilation!r}")
    return float(values[VENTILATION_PARAM[ventilation]])


def clamp_int(value: float, lo: float, hi: float) -> int:
    """Round to a whole number and keep it inside [lo, hi]."""
    return int(min(max(round(value), lo), hi))


def validate_inputs(profile: Mapping[str, Any], params: Mapping[str, Param]) -> tuple[list[str], list[str]]:
    """Check a sidebar profile against the ranges in params.yaml.

    Args:
        profile: keys ``class_size, length_m, width_m, height_m, ach, session_hours,
            mask_compliance (0-1), attack_rate_threshold (0-1), sim_days``.
        params: parsed params.yaml.

    Returns:
        ``(errors, warnings)``. If ``errors`` is not empty the engine must not be called.
    """
    errors: list[str] = []
    warnings: list[str] = []

    checks = [
        ("class_size", "class_size", "Students per class", ""),
        ("length_m", "room_length", "Room length", " m"),
        ("width_m", "room_width", "Room width", " m"),
        ("height_m", "room_height", "Room height", " m"),
        ("ach", "ach", "Air changes per hour", ""),
        ("session_hours", "session_hours", "Hours in class per day", " h"),
        ("mask_compliance", "mask_compliance", "Mask use", ""),
        ("attack_rate_threshold", "attack_rate_threshold", "Acceptable share infected", ""),
        ("sim_days", "sim_days", "Simulation days", ""),
    ]
    for field, key, label, unit in checks:
        value = profile.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            errors.append(f"{label} must be a number.")
            continue
        p = params[key]
        if not p.min <= value <= p.max:
            scale = 100 if key in {"mask_compliance", "attack_rate_threshold"} else 1
            suffix = "%" if scale == 100 else unit
            errors.append(
                f"{label} must be between {_fmt(p.min * scale)} and {_fmt(p.max * scale)}{suffix}."
            )

    if not errors:
        area = profile["length_m"] * profile["width_m"]
        per_student = area / profile["class_size"]
        if per_student < MIN_AREA_PER_STUDENT_M2:
            warnings.append(
                f"Only {per_student:.2f} m² of floor per student. "
                "That is very crowded; check the class size and room size."
            )
    return errors, warnings


def engine_values(params: Mapping[str, Param], profile: Mapping[str, Any]) -> dict[str, float]:
    """Parameter values for the engine: params.yaml base values plus the sidebar's overrides."""
    values = {key: p.value for key, p in params.items()}
    values["sim_days"] = float(profile["sim_days"])
    values["attack_rate_threshold"] = float(profile["attack_rate_threshold"])
    return values
