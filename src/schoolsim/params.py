"""Load and validate model parameters from ``params.yaml``.

Every number the model uses comes from ``params.yaml``. Each parameter carries a base
value, a plausible range, a unit, and one or more source keys that must resolve to an
entry in ``references.yaml`` (or to a reserved key: ``team_assumption`` or
``team_decision``). Validation fails loudly, naming the offending key, so a bad edit
never reaches the app.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARAMS_PATH = REPO_ROOT / "params.yaml"
DEFAULT_REFERENCES_PATH = REPO_ROOT / "references.yaml"

REQUIRED_FIELDS = ("value", "min", "max", "unit", "description", "source", "confidence")
CONFIDENCE_LEVELS = frozenset({"low", "medium", "high"})
DISTRIBUTIONS = frozenset({"uniform", "loguniform"})
RESERVED_SOURCES = frozenset({"team_assumption", "team_decision"})


@dataclass(frozen=True)
class Param:
    """One model parameter as declared in ``params.yaml``.

    ``value``, ``min`` and ``max`` are in ``unit``. ``min == max == value`` marks a
    fixed parameter (e.g. a preset).
    """

    key: str
    value: float
    min: float
    max: float
    unit: str
    description: str
    source: tuple[str, ...]
    confidence: str
    in_sensitivity: bool = False
    user_editable: bool = False
    distribution: str = "uniform"

    @property
    def is_fixed(self) -> bool:
        return self.min == self.max


def _number(key: str, field: str, raw: Any) -> float:
    # bool is a subclass of int; reject it explicitly so `value: true` is caught.
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"{key}: '{field}' must be a number, got {raw!r}")
    if not math.isfinite(raw):
        raise ValueError(f"{key}: '{field}' must be finite, got {raw!r}")
    return float(raw)


def load_references(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Load ``references.yaml`` as ``{key: entry}``. Every entry needs an ``apa`` field."""
    path = Path(path) if path is not None else DEFAULT_REFERENCES_PATH
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping of reference keys")
    for key, entry in data.items():
        if not isinstance(entry, dict) or not entry.get("apa"):
            raise ValueError(f"reference {key}: missing 'apa' citation")
    return data


def _parse_param(key: str, raw: Any, reference_keys: frozenset[str] | None) -> Param:
    if not isinstance(raw, dict):
        raise ValueError(f"{key}: expected a mapping of fields")
    missing = [f for f in REQUIRED_FIELDS if f not in raw or raw[f] in (None, "")]
    if missing:
        raise ValueError(f"{key}: missing required field(s): {', '.join(missing)}")

    value = _number(key, "value", raw["value"])
    lo = _number(key, "min", raw["min"])
    hi = _number(key, "max", raw["max"])
    if not lo <= value <= hi:
        raise ValueError(f"{key}: requires min <= value <= max, got min={lo}, value={value}, max={hi}")

    confidence = str(raw["confidence"])
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"{key}: confidence must be one of {sorted(CONFIDENCE_LEVELS)}, got {confidence!r}")

    distribution = str(raw.get("distribution", "uniform"))
    if distribution not in DISTRIBUTIONS:
        raise ValueError(f"{key}: distribution must be one of {sorted(DISTRIBUTIONS)}, got {distribution!r}")
    if distribution == "loguniform" and lo <= 0:
        raise ValueError(f"{key}: loguniform distribution requires min > 0, got min={lo}")

    sources = raw["source"]
    sources = (sources,) if isinstance(sources, str) else tuple(sources)
    if not sources or not all(isinstance(s, str) and s for s in sources):
        raise ValueError(f"{key}: 'source' must be a non-empty key or list of keys")
    if reference_keys is not None:
        unknown = [s for s in sources if s not in reference_keys and s not in RESERVED_SOURCES]
        if unknown:
            raise ValueError(f"{key}: unknown source key(s) not in references: {', '.join(unknown)}")

    for flag in ("in_sensitivity", "user_editable"):
        if flag in raw and not isinstance(raw[flag], bool):
            raise ValueError(f"{key}: '{flag}' must be true or false")

    in_sensitivity = bool(raw.get("in_sensitivity", False))
    if in_sensitivity and lo == hi:
        raise ValueError(f"{key}: in_sensitivity is true but min == max, so there is no range to vary")

    return Param(
        key=key,
        value=value,
        min=lo,
        max=hi,
        unit=str(raw["unit"]),
        description=str(raw["description"]),
        source=sources,
        confidence=confidence,
        in_sensitivity=in_sensitivity,
        user_editable=bool(raw.get("user_editable", False)),
        distribution=distribution,
    )


def load_params(
    path: str | Path | None = None,
    references_path: str | Path | None = None,
    check_sources: bool = True,
) -> dict[str, Param]:
    """Load and validate ``params.yaml``.

    Args:
        path: params file; defaults to ``params.yaml`` at the repo root.
        references_path: references file; defaults to ``references.yaml`` at the repo root.
        check_sources: if true, every source key must exist in the references file.

    Returns:
        ``{key: Param}`` in file order.

    Raises:
        ValueError: naming the parameter key, for any schema or range problem.
    """
    path = Path(path) if path is not None else DEFAULT_PARAMS_PATH
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{path}: expected a non-empty mapping of parameters")

    reference_keys = frozenset(load_references(references_path)) if check_sources else None
    return {key: _parse_param(key, raw, reference_keys) for key, raw in data.items()}


def base_values(params: Mapping[str, Param]) -> dict[str, float]:
    """Base-case values, ``{key: value}``."""
    return {k: p.value for k, p in params.items()}


def ranges(params: Mapping[str, Param], only_sensitivity: bool = True) -> dict[str, tuple[float, float]]:
    """Plausible ranges, ``{key: (min, max)}``.

    With ``only_sensitivity=True`` (default) only parameters flagged ``in_sensitivity``
    are returned; these are the ones the tornado and Latin hypercube runs vary.
    """
    return {k: (p.min, p.max) for k, p in params.items() if p.in_sensitivity or not only_sensitivity}


def low_confidence(params: Mapping[str, Param]) -> list[str]:
    """Keys of parameters marked ``confidence: low``."""
    return [k for k, p in params.items() if p.confidence == "low"]
