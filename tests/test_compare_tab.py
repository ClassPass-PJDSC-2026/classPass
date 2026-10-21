"""Tests for the Compare tab's table and charts (ticket #12), without launching Streamlit."""

from __future__ import annotations

import compare_tab as ct
import pytest
from theme import SCENARIO_COLORS

from schoolsim import _stub_engine as stub
from schoolsim import engine
from schoolsim.compare import comparison_table
from schoolsim.params import base_values, load_params

VALUES = base_values(load_params())
RESULTS = stub.run_all(stub.SchoolProfile(45, 9.0, 7.0, 2.7, 4.0, 6.0, 0.0), VALUES)
ORDER = list(engine.DISRUPTION_ORDER)
TABLE = comparison_table(RESULTS, ORDER, stub.LABELS.get, lambda s: stub.SCENARIOS[s].get("attendance", 1.0), VALUES)
LABEL = stub.LABELS.get


def test_table_is_in_disruption_order_with_the_ticket_columns():
    styled = ct.display_table(TABLE, LABEL, None)
    df = styled.data
    assert list(df["Scenario"]) == [LABEL(s) for s in ORDER]
    assert list(df.columns) == [
        "Scenario", "Students infected", "Change vs baseline", "Peak infectious", "Learner-days lost",
    ]


def test_change_column_has_sign_and_colour():
    html = ct.display_table(TABLE, LABEL, None).to_html()
    assert "-" in html and ct.BETTER in html  # online: infections fall
    assert ct.WORSE not in html  # no scenario in this run makes infections worse


def test_a_scenario_that_is_worse_than_baseline_is_red():
    worse = TABLE.copy()
    worse.loc[worse["scenario"] == "online", "change_vs_baseline_pct"] = 25.0
    assert ct.WORSE in ct.display_table(worse, LABEL, None).to_html()


def test_baseline_row_has_no_colour():
    styled = ct.display_table(TABLE, LABEL, None)
    assert styled.data.loc[0, "Change vs baseline"] == "0.0%"


def test_recommended_scenario_is_starred_and_bold():
    styled = ct.display_table(TABLE, LABEL, "hybrid")
    names = list(styled.data["Scenario"])
    assert names[ORDER.index("hybrid")] == "★ Hybrid, A/B cohorts"
    assert sum(n.startswith("★") for n in names) == 1
    assert "font-weight: 700" in styled.to_html()


def test_nothing_is_starred_without_a_recommendation():
    assert not any(n.startswith("★") for n in ct.display_table(TABLE, LABEL, None).data["Scenario"])


def test_bar_chart_shows_infections_and_learning_side_by_side():
    fig = ct.build_bars(TABLE, LABEL, None)
    assert len(fig.data) == 2
    assert list(fig.data[0].x) == pytest.approx(list(TABLE["attack_rate_pct"]))
    assert list(fig.data[1].x) == pytest.approx(list(TABLE["learner_days_lost"]))
    assert list(fig.data[0].y) == [LABEL(s) for s in ORDER]
    assert fig.layout.annotations[0].text == "Students infected (%)"
    assert "Learner-days lost" in fig.layout.annotations[1].text


def test_bars_use_one_colour_per_scenario():
    fig = ct.build_bars(TABLE, LABEL, None)
    assert list(fig.data[0].marker.color) == [SCENARIO_COLORS[s] for s in ORDER]
    assert list(fig.data[1].marker.color) == list(fig.data[0].marker.color)


def test_bars_start_with_baseline_at_the_top():
    assert ct.build_bars(TABLE, LABEL, None).layout.yaxis.autorange == "reversed"


def test_overlay_has_a_line_per_scenario_in_order():
    fig = ct.build_overlay(RESULTS, ORDER, LABEL, None, sim_days=60, school_days_per_week=5)
    assert [t.name for t in fig.data] == [LABEL(s) for s in ORDER]
    assert [t.line.color for t in fig.data] == [SCENARIO_COLORS[s] for s in ORDER]


def test_overlay_baseline_line_is_thickest():
    fig = ct.build_overlay(RESULTS, ORDER, LABEL, None, sim_days=60, school_days_per_week=5)
    widths = {t.name: t.line.width for t in fig.data}
    assert widths[LABEL("baseline")] == max(widths.values())


def test_overlay_values_are_percent_of_the_school():
    fig = ct.build_overlay(RESULTS, ORDER, LABEL, None, sim_days=60, school_days_per_week=5)
    base = next(t for t in fig.data if t.name == LABEL("baseline"))
    assert max(base.y) == pytest.approx(RESULTS["baseline"].peak_infectious * 100)


def test_overlay_shades_weekends_and_labels_axes():
    fig = ct.build_overlay(RESULTS, ORDER, LABEL, None, sim_days=60, school_days_per_week=5)
    assert len(fig.layout.shapes) == 8
    assert "Day" in fig.layout.xaxis.title.text and "infectious" in fig.layout.yaxis.title.text


def test_overlay_marks_the_recommended_scenario():
    fig = ct.build_overlay(RESULTS, ORDER, LABEL, "online", sim_days=60, school_days_per_week=5)
    assert fig.data[-1].name.startswith("★")
