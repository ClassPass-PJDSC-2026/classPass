"""Tests for schoolsim.params (ticket A3)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from schoolsim.params import (
    DEFAULT_PARAMS_PATH,
    REPO_ROOT,
    REQUIRED_FIELDS,
    Param,
    base_values,
    load_params,
    load_references,
    low_confidence,
    ranges,
)

ASSUMPTIONS_MD = REPO_ROOT / "docs" / "assumptions.md"

REFS = """
ref_a:
  apa: "Author, A. (2020). Title. Journal, 1(1), 1–2."
"""

VALID_PARAM = """
quanta_rate:
  value: 15.0
  min: 5.0
  max: 128.0
  unit: quanta/h
  description: test
  source: [ref_a]
  confidence: low
  in_sensitivity: true
  distribution: loguniform
fixed_preset:
  value: 4.0
  min: 4.0
  max: 4.0
  unit: 1/h
  description: test
  source: team_assumption
  confidence: medium
"""


def write(tmp_path: Path, params: str, refs: str = REFS) -> tuple[Path, Path]:
    p = tmp_path / "params.yaml"
    r = tmp_path / "references.yaml"
    p.write_text(textwrap.dedent(params), encoding="utf-8")
    r.write_text(textwrap.dedent(refs), encoding="utf-8")
    return p, r


# --- The real repo files ------------------------------------------------------

def test_repo_params_load():
    params = load_params()
    assert params, "params.yaml is empty"
    assert all(isinstance(p, Param) for p in params.values())


def test_repo_params_have_every_required_field():
    import yaml

    raw = yaml.safe_load(DEFAULT_PARAMS_PATH.read_text(encoding="utf-8"))
    for key, entry in raw.items():
        for field in REQUIRED_FIELDS:
            assert entry.get(field) not in (None, ""), f"{key} missing {field}"


def test_repo_sources_resolve_to_references():
    refs = load_references()
    for key, p in load_params().items():
        for s in p.source:
            assert s in refs or s in {"team_assumption", "team_decision"}, f"{key}: {s}"


def test_repo_ticket_parameters_present():
    expected = {
        "quanta_rate", "breathing_rate", "latent_days", "infectious_days", "mask_efficiency",
        "mask_compliance", "ach_poor", "ach_typical", "ach_good", "room_length", "room_width",
        "room_height", "session_hours", "community_beta", "infectious_attendance",
        "initial_infected_frac", "school_days_per_week", "sim_days", "sick_days_per_case",
        "online_learning_weight", "attack_rate_threshold", "robustness_threshold",
    }
    assert expected <= set(load_params())


def test_assumptions_doc_lists_every_parameter_and_every_low_confidence_item():
    text = ASSUMPTIONS_MD.read_text(encoding="utf-8")
    params = load_params()
    for key in params:
        assert f"`{key}`" in text, f"{key} not documented in docs/assumptions.md"
    low_section = text.split("## Low-confidence parameters", 1)[1].split("\n## ", 1)[0]
    for key in low_confidence(params):
        assert f"`{key}`" in low_section, f"low-confidence {key} not listed explicitly"


# --- Valid synthetic file -----------------------------------------------------

def test_valid_file_loads(tmp_path):
    p, r = write(tmp_path, VALID_PARAM)
    params = load_params(p, r)
    q = params["quanta_rate"]
    assert (q.value, q.min, q.max, q.unit) == (15.0, 5.0, 128.0, "quanta/h")
    assert q.source == ("ref_a",) and q.distribution == "loguniform"
    assert params["fixed_preset"].is_fixed
    assert params["fixed_preset"].source == ("team_assumption",)


def test_base_values_and_ranges(tmp_path):
    params = load_params(*write(tmp_path, VALID_PARAM))
    assert base_values(params) == {"quanta_rate": 15.0, "fixed_preset": 4.0}
    assert ranges(params) == {"quanta_rate": (5.0, 128.0)}
    assert ranges(params, only_sensitivity=False)["fixed_preset"] == (4.0, 4.0)
    assert low_confidence(params) == ["quanta_rate"]


def test_param_is_immutable(tmp_path):
    q = load_params(*write(tmp_path, VALID_PARAM))["quanta_rate"]
    with pytest.raises(AttributeError):
        q.value = 99.0  # type: ignore[misc]


# --- Invalid files: each error names the key ----------------------------------

def bad(field_lines: str, extra: str = "") -> str:
    return f"""
bad_key:
  unit: x
  description: test
  source: team_assumption
  confidence: low
{field_lines}
{extra}
"""


@pytest.mark.parametrize(
    "fields",
    [
        "  value: 10\n  min: 0\n  max: 5",    # value above max
        "  value: -1\n  min: 0\n  max: 5",    # value below min
        "  value: 3\n  min: 6\n  max: 5",     # min above max
    ],
)
def test_bad_range_raises_with_key_name(tmp_path, fields):
    with pytest.raises(ValueError, match="bad_key"):
        load_params(*write(tmp_path, bad(fields)))


def test_missing_field_raises(tmp_path):
    text = """
bad_key:
  value: 1
  min: 0
  max: 2
  description: no unit or source
  confidence: low
"""
    with pytest.raises(ValueError, match=r"bad_key: missing required field\(s\): unit, source"):
        load_params(*write(tmp_path, text))


def test_unknown_source_raises(tmp_path):
    text = VALID_PARAM.replace("[ref_a]", "[ref_a, not_a_ref]")
    with pytest.raises(ValueError, match="quanta_rate: unknown source key"):
        load_params(*write(tmp_path, text))


def test_unknown_source_allowed_when_check_disabled(tmp_path):
    text = VALID_PARAM.replace("[ref_a]", "[not_a_ref]")
    p, _ = write(tmp_path, text)
    assert "quanta_rate" in load_params(p, check_sources=False)


@pytest.mark.parametrize(
    "old, new, message",
    [
        ("  confidence: low", "  confidence: maybe", "confidence must be one of"),
        ("  confidence: low", "  confidence: low\n  distribution: normal", "distribution must be one of"),
        ("  confidence: low", "  confidence: low\n  in_sensitivity: yes please", "'in_sensitivity' must be"),
    ],
)
def test_bad_enums_raise(tmp_path, old, new, message):
    text = bad("  value: 1\n  min: 0\n  max: 2").replace(old, new)
    with pytest.raises(ValueError, match=message):
        load_params(*write(tmp_path, text))


def test_non_numeric_value_raises(tmp_path):
    with pytest.raises(ValueError, match="bad_key: 'value' must be a number"):
        load_params(*write(tmp_path, bad("  value: true\n  min: 0\n  max: 2")))


def test_loguniform_needs_positive_min(tmp_path):
    text = bad("  value: 1\n  min: 0\n  max: 2", "  distribution: loguniform")
    with pytest.raises(ValueError, match="loguniform distribution requires min > 0"):
        load_params(*write(tmp_path, text))


def test_sensitivity_param_needs_a_range(tmp_path):
    text = bad("  value: 1\n  min: 1\n  max: 1", "  in_sensitivity: true")
    with pytest.raises(ValueError, match="no range to vary"):
        load_params(*write(tmp_path, text))


def test_reference_without_apa_raises(tmp_path):
    p, r = write(tmp_path, VALID_PARAM, refs="ref_a:\n  url: https://example.org\n")
    with pytest.raises(ValueError, match="reference ref_a: missing 'apa'"):
        load_params(p, r)
