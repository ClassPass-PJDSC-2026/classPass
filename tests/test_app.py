"""End-to-end tests of the Streamlit app (tickets #10 and #11) using Streamlit's AppTest."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from schoolsim import _stub_engine as stub
from schoolsim.inputs import describe_param
from schoolsim.params import load_params, load_references
from schoolsim.presets import load_presets, lookup

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
PARAMS = load_params()
REFS = load_references()
PRESETS, _ = load_presets()


@pytest.fixture(autouse=True)
def placeholder_engine(monkeypatch):
    """Run against the stub even after the real engine is merged, so these tests stay stable."""
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", None)
    monkeypatch.setitem(sys.modules, "schoolsim.spatial", None)


def start() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def submit(at: AppTest) -> AppTest:
    """Press Run simulation. Form edits only apply when set in the same run as the submit."""
    return [b for b in at.sidebar.button if b.label == "Run simulation"][0].click().run()


def metrics(at: AppTest) -> dict[str, str]:
    """KPI cards of the Results tab (the first tab)."""
    return {m.label: m.value for m in at.tabs[0].metric}


def deltas(at: AppTest) -> dict[str, str]:
    return {m.label: m.delta for m in at.tabs[0].metric}


def default_class_size(region: str, level: str) -> int:
    return round(lookup(PRESETS, region, level)["learners_per_classroom"])


# --- #10 sidebar -------------------------------------------------------------------------

def test_loads_without_errors_and_shows_a_chart_on_first_load():
    at = start()
    assert not at.exception
    assert len(at.tabs[0].get("plotly_chart")) == 1
    assert len(at.tabs[0].metric) == 5


def test_profile_is_stored_in_session_state():
    profile = start().session_state["profile"]
    assert profile["class_size"] == default_class_size(profile["region"], profile["level"])
    assert profile["ach"] == PARAMS["ach_typical"].value


def test_region_change_updates_class_size_default():
    at = start()
    at.sidebar.selectbox(key="region").select("BARMM").run()
    assert at.sidebar.number_input(key="class_size").value == default_class_size("BARMM", "Elementary")


def test_level_change_updates_class_size_default():
    at = start()
    at.sidebar.selectbox(key="level").select("JHS").run()
    assert at.sidebar.number_input(key="class_size").value == default_class_size("NCR", "JHS")


def test_user_edit_is_kept_until_region_changes_again():
    at = start()
    at.sidebar.number_input(key="class_size").set_value(52)
    at = submit(at)
    assert at.sidebar.number_input(key="class_size").value == 52
    assert at.session_state["profile"]["class_size"] == 52
    at.sidebar.selectbox(key="region").select("CALABARZON").run()
    assert at.sidebar.number_input(key="class_size").value == default_class_size("CALABARZON", "Elementary")


def test_deped_standard_room_button_fills_the_dimensions():
    at = start()
    at.sidebar.number_input(key="room_length").set_value(12.0)
    at = submit(at)
    assert at.sidebar.number_input(key="room_length").value == 12.0
    [b for b in at.sidebar.button if b.key == "std_room"][0].click().run()
    assert [at.sidebar.number_input(key=k).value for k in ("room_length", "room_width", "room_height")] == [
        PARAMS["room_length"].value, PARAMS["room_width"].value, PARAMS["room_height"].value,
    ]


@pytest.mark.parametrize(
    "option, key", [("Poor", "ach_poor"), ("Typical", "ach_typical"), ("Good", "ach_good")]
)
def test_ventilation_choice_sets_ach(option, key):
    at = start()
    at.sidebar.selectbox(key="ventilation").select(option)
    at = submit(at)
    assert at.session_state["profile"]["ach"] == PARAMS[key].value


def test_custom_ventilation_uses_typed_ach():
    at = start()
    at.sidebar.selectbox(key="ventilation").select("Custom")
    at.sidebar.number_input(key="custom_ach").set_value(9.0)
    at = submit(at)
    assert at.session_state["profile"]["ach"] == 9.0


def test_changing_inputs_does_not_run_the_model_until_submit():
    at = start()
    before = metrics(at)
    at.sidebar.slider(key="mask_pct").set_value(80)
    at.run()
    assert metrics(at) == before
    at.sidebar.slider(key="mask_pct").set_value(80)
    at = submit(at)
    assert metrics(at) != before


NUMBER_LIMITS = {  # widget key -> (params key, scale)
    "class_size": ("class_size", 1),
    "room_length": ("room_length", 1),
    "room_width": ("room_width", 1),
    "room_height": ("room_height", 1),
    "custom_ach": ("ach", 1),
    "session_hours": ("session_hours", 1),
    "mask_pct": ("mask_compliance", 100),
    "attack_threshold_pct": ("attack_rate_threshold", 100),
    "sim_days": ("sim_days", 1),
}


@pytest.mark.parametrize("widget_key", list(NUMBER_LIMITS))
def test_numeric_inputs_use_the_ranges_in_params_yaml(widget_key):
    at = start()
    param_key, scale = NUMBER_LIMITS[widget_key]
    widgets = list(at.sidebar.number_input) + list(at.sidebar.slider)
    w = next(w for w in widgets if w.key == widget_key)
    assert w.min == pytest.approx(PARAMS[param_key].min * scale)
    assert w.max == pytest.approx(PARAMS[param_key].max * scale)


@pytest.mark.parametrize("widget_key", list(NUMBER_LIMITS))
def test_every_numeric_input_has_a_tooltip_with_unit_and_source(widget_key):
    at = start()
    widgets = list(at.sidebar.number_input) + list(at.sidebar.slider)
    w = next(w for w in widgets if w.key == widget_key)
    assert "Unit:" in w.help and "Source:" in w.help


def test_selects_have_tooltips():
    at = start()
    for key in ("region", "level", "ventilation"):
        assert at.sidebar.selectbox(key=key).help
    assert "Source:" in at.sidebar.selectbox(key="ventilation").help


def test_tooltip_matches_the_parameter_file():
    at = start()
    assert at.sidebar.number_input(key="room_width").help == describe_param(PARAMS["room_width"], REFS)


def test_invalid_profile_shows_an_error_and_never_reaches_the_engine(monkeypatch):
    calls = []
    original = stub.run_all
    monkeypatch.setattr(stub, "run_all", lambda *a, **k: calls.append(a) or original(*a, **k))
    at = start()
    calls.clear()
    monkeypatch.setattr(
        sys.modules["sidebar"], "validate_inputs", lambda profile, params: (["Air changes per hour is too low."], [])
    )
    at.sidebar.number_input(key="class_size").set_value(30)
    at = submit(at)
    assert [e.value for e in at.sidebar.error] == ["Air changes per hour is too low."]
    assert at.session_state["profile"]["class_size"] != 30
    assert calls == []
    assert not at.exception


def test_crowded_room_shows_a_warning_but_still_runs():
    at = start()
    at.sidebar.number_input(key="class_size").set_value(80)
    at.sidebar.number_input(key="room_length").set_value(5.0)
    at.sidebar.number_input(key="room_width").set_value(4.0)
    at = submit(at)
    assert any("very crowded" in w.value for w in at.sidebar.warning)
    assert at.session_state["profile"]["class_size"] == 80 and not at.exception


def test_stale_out_of_range_state_is_repaired_instead_of_crashing():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["class_size"] = 5000
    at.session_state["room_length"] = -4.0
    at.session_state["ventilation"] = "Hurricane"
    at.run()
    assert not at.exception
    assert 5 <= at.sidebar.number_input(key="class_size").value <= 80


# --- #11 results -------------------------------------------------------------------------

def test_kpi_row_has_the_five_kpis():
    assert list(metrics(start())) == [
        "Students infected", "Peak infectious", "Peak day", "Learner-days lost", "Effective R0",
    ]


def test_kpis_show_the_simresult_values():
    at = start()
    res = stub.run_all(
        stub.SchoolProfile(**{k: at.session_state["profile"][k] for k in (
            "class_size", "length_m", "width_m", "height_m", "ach", "session_hours", "mask_compliance")}),
        {**{k: p.value for k, p in PARAMS.items()}},
    )["baseline"]
    shown = metrics(at)
    assert shown["Students infected"] == f"{res.attack_rate * 100:.1f}%"
    assert shown["Peak infectious"] == f"{res.peak_infectious * 100:.1f}%"
    assert shown["Peak day"] == f"Day {res.peak_day}"
    assert shown["Effective R0"] == f"{res.r0_effective:.2f}"


def test_baseline_has_no_deltas_other_scenarios_compare_with_it():
    at = start()
    assert all(not d for d in deltas(at).values())
    at.selectbox(key="scenario").select("online").run()
    assert not at.exception
    assert deltas(at)["Students infected"].endswith("pp")
    assert deltas(at)["Students infected"].startswith("-")


def test_every_scenario_renders():
    at = start()
    for scenario in stub.SCENARIOS:
        at.selectbox(key="scenario").select(scenario).run()
        assert not at.exception, scenario
        assert len(at.tabs[0].get("plotly_chart")) == 1


def test_percent_and_number_toggle_both_render():
    at = start()
    for mode in ("Number of students", "Percent of students"):
        at.radio(key="display_mode").set_value(mode).run()
        assert not at.exception
    at.radio(key="display_mode").set_value("Number of students").run()
    assert any("rounded to whole students" in c.value for c in at.caption)


def test_forecast_disclaimer_is_under_the_chart_and_in_the_footer():
    captions = [c.value for c in start().caption]
    assert "Relative scenario simulation, not a forecast." in captions
    assert "Scenario simulation for decision support, not a medical forecast." in captions


def test_placeholder_engine_is_announced():
    assert any("Placeholder engine" in w.value for w in start().warning)


def test_simulation_length_follows_the_advanced_setting():
    at = start()
    at.sidebar.slider(key="sim_days").set_value(30)
    at = submit(at)
    assert at.session_state["profile"]["sim_days"] == 30 and not at.exception


def test_engine_error_is_shown_not_raised(monkeypatch):
    def boom(*_args, **_kwargs):
        raise ValueError("Air changes per hour must be above zero.")

    at = start()
    monkeypatch.setattr(stub, "run_all", boom)
    at.sidebar.number_input(key="class_size").set_value(33)
    at = submit(at)
    assert not at.exception
    assert any("Air changes per hour" in e.value for e in at.error)
