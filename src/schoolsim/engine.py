"""Single entry point the Streamlit app uses to run simulations.

The app never imports the engine modules directly. It calls :func:`get_backend`, which
returns the real engine (``schoolsim.scenarios``, tickets #5, #6, #9) when it exists and
a clearly-marked placeholder otherwise. If the real engine's function names or arguments
differ from the tickets, this is the only file that needs changing.

Expected real API (ticket #9):
    SCENARIOS: dict[str, dict]            scenario id -> definition (optional "attendance")
    DISRUPTION_ORDER: tuple[str, ...]     optional; least to most disruptive (defaults to the list above)
    LABELS: dict[str, str]                scenario id -> human-readable label
    SchoolProfile(class_size, length_m, width_m, height_m, ach, session_hours, mask_compliance)
    run_all(profile, values) -> dict[str, SimResult]
where ``values`` is ``{parameter key: number}`` (see ``params.base_values``) and each
``SimResult`` has ``t, S, E, I, R, attack_rate, peak_infectious, peak_day,
cumulative_infections`` and optionally ``r0_effective``.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

# Least to most disruptive (ticket #9). "≈" ties (ventilation, masks, combined) keep this order.
DISRUPTION_ORDER = (
    "baseline",
    "better_ventilation",
    "masks",
    "combined",
    "smaller_classes",
    "hybrid",
    "online",
)

PROFILE_FIELDS = (
    "class_size",
    "length_m",
    "width_m",
    "height_m",
    "ach",
    "session_hours",
    "mask_compliance",
)


@dataclass(frozen=True)
class Backend:
    name: str  # "schoolsim" (real engine) or "stub" (placeholder)
    scenarios: Mapping[str, Mapping[str, Any]]
    labels: Mapping[str, str]
    profile_cls: type
    _run_all: Callable[..., Mapping[str, Any]]
    _order: tuple[str, ...] = DISRUPTION_ORDER

    @property
    def is_placeholder(self) -> bool:
        return self.name == "stub"

    @property
    def scenario_ids(self) -> list[str]:
        return list(self.scenarios)

    @property
    def ordered_ids(self) -> list[str]:
        """Scenario ids from least to most disruptive; unknown ids go last in their own order."""
        known = [sid for sid in self._order if sid in self.scenarios]
        return known + [sid for sid in self.scenarios if sid not in known]

    def label(self, scenario_id: str) -> str:
        return self.labels.get(scenario_id, scenario_id.replace("_", " ").capitalize())

    def attendance(self, scenario_id: str) -> float:
        """Share of students attending face-to-face in this scenario (1 unless defined)."""
        return float(self.scenarios[scenario_id].get("attendance", 1.0))

    def run_all(self, profile: Mapping[str, Any], values: Mapping[str, float]) -> dict[str, Any]:
        """Run every scenario.

        Args:
            profile: dict with the ``PROFILE_FIELDS`` keys (extra keys are ignored).
            values: parameter values keyed as in params.yaml.

        Raises:
            ValueError: for inputs the engine cannot simulate (the app shows the message).
        """
        school = self.profile_cls(**{k: profile[k] for k in PROFILE_FIELDS})
        return dict(self._run_all(school, values))


def get_backend() -> Backend:
    """Return the real engine if it is importable, otherwise the placeholder."""
    try:
        mod = importlib.import_module("schoolsim.scenarios")
        order = tuple(getattr(mod, "DISRUPTION_ORDER", DISRUPTION_ORDER))
        return Backend("schoolsim", mod.SCENARIOS, mod.LABELS, mod.SchoolProfile, mod.run_all, order)
    except (ImportError, AttributeError):
        from schoolsim import _stub_engine as stub

        return Backend("stub", stub.SCENARIOS, stub.LABELS, stub.SchoolProfile, stub.run_all)
