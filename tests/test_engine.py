"""Tests for schoolsim.engine: real engine when present, placeholder otherwise."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import pytest

from schoolsim import engine
from schoolsim.params import base_values, load_params

VALUES = base_values(load_params())
PROFILE = {
    "class_size": 45, "length_m": 9.0, "width_m": 7.0, "height_m": 2.7, "ach": 4.0,
    "session_hours": 6.0, "mask_compliance": 0.0,
    "region": "NCR", "level": "JHS", "enrollment": 900,  # extra keys must be ignored
}


def force_stub(monkeypatch):
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", None)  # makes the import fail


def fake_scenarios(**missing):
    @dataclass(frozen=True)
    class SchoolProfile:
        class_size: int
        length_m: float
        width_m: float
        height_m: float
        ach: float
        session_hours: float
        mask_compliance: float

    calls = []

    def run_all(profile, values):
        calls.append((profile, values))
        return {"baseline": "result-a", "hybrid": "result-b"}

    mod = types.ModuleType("schoolsim.scenarios")
    mod.SCENARIOS = {"baseline": {}, "hybrid": {"attendance": 0.5}}
    mod.LABELS = {"baseline": "As is"}
    mod.SchoolProfile = SchoolProfile
    mod.run_all = run_all
    mod.calls = calls
    for name in missing:
        delattr(mod, name)
    return mod


def test_falls_back_to_placeholder_when_real_engine_is_absent(monkeypatch):
    force_stub(monkeypatch)
    backend = engine.get_backend()
    assert backend.name == "stub" and backend.is_placeholder
    assert "baseline" in backend.scenario_ids and "online" in backend.scenario_ids


def test_placeholder_runs_every_scenario(monkeypatch):
    force_stub(monkeypatch)
    results = engine.get_backend().run_all(PROFILE, VALUES)
    assert set(results) == set(engine.get_backend().scenario_ids)


def test_uses_real_engine_when_it_exists(monkeypatch):
    mod = fake_scenarios()
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", mod)
    backend = engine.get_backend()
    assert backend.name == "schoolsim" and not backend.is_placeholder
    assert backend.run_all(PROFILE, VALUES) == {"baseline": "result-a", "hybrid": "result-b"}


def test_real_engine_receives_only_profile_fields(monkeypatch):
    mod = fake_scenarios()
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", mod)
    engine.get_backend().run_all(PROFILE, VALUES)
    (profile, values), = mod.calls
    assert set(vars(profile)) == set(engine.PROFILE_FIELDS)
    assert values is VALUES or values == VALUES


@pytest.mark.parametrize("missing", ["LABELS", "run_all", "SchoolProfile", "SCENARIOS"])
def test_incomplete_real_engine_falls_back(monkeypatch, missing):
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", fake_scenarios(**{missing: None}))
    assert engine.get_backend().name == "stub"


def test_attendance_defaults_to_one_and_reads_scenario(monkeypatch):
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", fake_scenarios())
    backend = engine.get_backend()
    assert backend.attendance("baseline") == 1.0
    assert backend.attendance("hybrid") == 0.5


def test_label_falls_back_to_readable_id(monkeypatch):
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", fake_scenarios())
    backend = engine.get_backend()
    assert backend.label("baseline") == "As is"
    assert backend.label("hybrid") == "Hybrid"


def test_engine_value_errors_propagate_for_the_app_to_show(monkeypatch):
    force_stub(monkeypatch)
    bad = {**PROFILE, "ach": 0.0}
    with pytest.raises(ValueError, match="Air changes per hour"):
        engine.get_backend().run_all(bad, VALUES)
