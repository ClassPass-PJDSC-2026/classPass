"""Tests for schoolsim.compare and the disruption ordering (ticket #12)."""

from __future__ import annotations

import io
import math
import sys
import types
from types import SimpleNamespace

import pandas as pd
import pytest

from schoolsim import _stub_engine as stub
from schoolsim import engine
from schoolsim.compare import (
    COLUMNS,
    comparison_csv,
    comparison_table,
    format_change,
    tradeoff_summary,
)
from schoolsim.params import base_values, load_params

VALUES = base_values(load_params())
PROFILE = stub.SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0)
RESULTS = stub.run_all(PROFILE, VALUES)
ORDER = list(engine.DISRUPTION_ORDER)


def attendance(sid: str) -> float:
    return stub.SCENARIOS[sid].get("attendance", 1.0)


def table(results=RESULTS, ids=ORDER):
    return comparison_table(results, ids, stub.LABELS.get, attendance, VALUES)


def fake_result(attack, **kw):
    base = {"attack_rate": attack, "peak_infectious": attack / 2, "peak_day": 10, "cumulative_infections": attack,
            "r0_effective": 2.0}
    base.update(kw)
    return SimpleNamespace(**base)


# --- table -------------------------------------------------------------------------------

def test_rows_follow_the_given_order():
    assert list(table()["scenario"]) == ORDER


def test_unknown_ids_are_skipped():
    assert list(table(ids=["baseline", "ghost", "online"])["scenario"]) == ["baseline", "online"]


def test_columns_match_the_ticket():
    assert tuple(table().columns) == COLUMNS


def test_baseline_change_is_zero_and_others_are_relative():
    t = table().set_index("scenario")
    base = RESULTS["baseline"].attack_rate
    assert t.loc["baseline", "change_vs_baseline_pct"] == 0.0
    expected = (RESULTS["online"].attack_rate - base) / base * 100
    assert t.loc["online", "change_vs_baseline_pct"] == pytest.approx(expected)
    assert t.loc["online", "change_vs_baseline_pct"] < 0 < t.loc["baseline", "learner_days_lost"]


def test_values_match_the_simresult_exactly():
    t = table().set_index("scenario")
    for sid, res in RESULTS.items():
        assert t.loc[sid, "attack_rate_pct"] == res.attack_rate * 100
        assert t.loc[sid, "peak_infectious_pct"] == res.peak_infectious * 100
        assert t.loc[sid, "peak_day"] == res.peak_day


def test_change_is_undefined_when_baseline_has_no_infections():
    results = {"baseline": fake_result(0.0), "online": fake_result(0.0)}
    t = comparison_table(results, ["baseline", "online"], str, lambda s: 1.0, VALUES)
    assert t["change_vs_baseline_pct"].isna().all()


def test_missing_baseline_is_an_error():
    with pytest.raises(ValueError, match="Baseline"):
        comparison_table({"online": fake_result(0.1)}, ["online"], str, lambda s: 1.0, VALUES)


def test_missing_r0_becomes_nan():
    results = {"baseline": fake_result(0.5, r0_effective=None)}
    t = comparison_table(results, ["baseline"], str, lambda s: 1.0, VALUES)
    assert math.isnan(t.loc[0, "r0_effective"])


# --- formatting and summary --------------------------------------------------------------

@pytest.mark.parametrize(
    "value, text",
    [(-97.46, "-97.5%"), (12.34, "+12.3%"), (0.0, "0.0%"), (0.04, "0.0%"), (float("nan"), "–"), (None, "–")],
)
def test_format_change(value, text):
    assert format_change(value) == text


def test_tradeoff_summary_names_the_most_protective_option():
    text = tradeoff_summary(table(), stub.LABELS.get)
    assert "online classes" in text and "percentage points" in text and "adds" in text and "learner-days lost" in text


def test_tradeoff_summary_when_learning_also_improves():
    results = {"baseline": fake_result(0.8), "masks": fake_result(0.2)}
    t = comparison_table(results, ["baseline", "masks"], str, lambda s: 1.0, VALUES)
    base_days = t.loc[t["scenario"] == "baseline", "learner_days_lost"].iloc[0]
    t.loc[t["scenario"] == "masks", "learner_days_lost"] = base_days - 1.5
    text = tradeoff_summary(t, str)
    assert "also cuts learner-days lost by 1.5" in text and " and " in text


def test_tradeoff_summary_when_learning_is_unchanged():
    results = {"baseline": fake_result(0.8), "masks": fake_result(0.2)}
    t = comparison_table(results, ["baseline", "masks"], str, lambda s: 1.0, VALUES)
    t["learner_days_lost"] = 2.0  # same learning cost in both scenarios
    assert "unchanged" in tradeoff_summary(t, str)


def test_tradeoff_summary_when_nothing_helps():
    results = {"baseline": fake_result(0.3), "masks": fake_result(0.4)}
    t = comparison_table(results, ["baseline", "masks"], str, lambda s: 1.0, VALUES)
    assert tradeoff_summary(t, str).startswith("No scenario lowers")


def test_tradeoff_summary_needs_a_baseline_and_a_comparison():
    assert tradeoff_summary(table(ids=["baseline"]), str) is None
    assert tradeoff_summary(table(ids=["online", "hybrid"]), str) is None


# --- CSV ---------------------------------------------------------------------------------

def test_csv_has_one_row_per_scenario_and_numeric_columns():
    df = pd.read_csv(io.BytesIO(comparison_csv(table())))
    assert len(df) == len(ORDER)
    assert list(df["scenario_id"]) == ORDER
    assert df["attack_rate_pct"].dtype.kind == "f" and df["learner_days_lost_per_student"].dtype.kind == "f"


def test_csv_values_match_the_table():
    t = table()
    df = pd.read_csv(io.BytesIO(comparison_csv(t)))
    assert df["attack_rate_pct"].tolist() == pytest.approx(t["attack_rate_pct"].round(4).tolist())
    assert df["change_vs_baseline_pct"].iloc[0] == 0.0


def test_csv_is_utf_8_with_a_header():
    data = comparison_csv(table())
    assert data.decode("utf-8").splitlines()[0].startswith("scenario_id,scenario,attack_rate_pct")


# --- disruption order in the engine adapter ------------------------------------------------

def test_stub_backend_orders_by_disruption_not_dict_order(monkeypatch):
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", None)
    backend = engine.get_backend()
    assert backend.ordered_ids == ORDER
    assert backend.scenario_ids != ORDER  # the dict order differs, which is why the order is explicit


def test_unknown_scenarios_go_last(monkeypatch):
    mod = types.ModuleType("schoolsim.scenarios")
    mod.SCENARIOS = {"zzz_new": {}, "online": {}, "baseline": {}}
    mod.LABELS = {}
    mod.SchoolProfile = object
    mod.run_all = lambda *a: {}
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", mod)
    assert engine.get_backend().ordered_ids == ["baseline", "online", "zzz_new"]


def test_real_engine_can_supply_its_own_order(monkeypatch):
    mod = types.ModuleType("schoolsim.scenarios")
    mod.SCENARIOS = {"a": {}, "b": {}, "baseline": {}}
    mod.LABELS = {}
    mod.SchoolProfile = object
    mod.run_all = lambda *a: {}
    mod.DISRUPTION_ORDER = ("baseline", "b", "a")
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", mod)
    assert engine.get_backend().ordered_ids == ["baseline", "b", "a"]
