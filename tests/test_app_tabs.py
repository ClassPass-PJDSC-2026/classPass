"""End-to-end tests of the Compare tab, Seat map tab and privacy notices (tickets #12, #26b, #29)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from notices import AI_DISCLOSURE, DATA_NOTICE, FOOTER_NOTICE
from streamlit.testing.v1 import AppTest

from schoolsim import _stub_engine as stub
from schoolsim import spatial as sp
from schoolsim.engine import DISRUPTION_ORDER
from schoolsim.seating import seat_labels

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def placeholder_models(monkeypatch):
    monkeypatch.setitem(sys.modules, "schoolsim.scenarios", None)


def start() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def submit(at: AppTest) -> AppTest:
    return [b for b in at.sidebar.button if b.label == "Run simulation"][0].click().run()


def seat_tab(at):
    return at.tabs[2]


def seat_metrics(at) -> dict[str, str]:
    return {m.label: m.value for m in seat_tab(at).metric}


def press(at, key: str) -> AppTest:
    return seat_tab(at).button(key=key).click().run()


def expected_next_day(at) -> float:
    return float(seat_metrics(at)["Expected new cases, next school day"])


# --- #12 Compare ---------------------------------------------------------------------------

def test_compare_tab_renders_without_errors():
    at = start()
    assert not at.exception
    compare = at.tabs[1]
    assert len(compare.dataframe) == 1
    assert len(compare.get("plotly_chart")) == 2
    assert len(compare.get("download_button")) == 1


def test_compare_table_is_sorted_by_disruption_order():
    df = start().tabs[1].dataframe[0].value
    assert list(df["Scenario"]) == [stub.LABELS[s] for s in DISRUPTION_ORDER]


def test_compare_table_shows_signed_change_against_baseline():
    df = start().tabs[1].dataframe[0].value
    changes = list(df["Change vs baseline"])
    assert changes[0] == "0.0%" and all(c.startswith("-") for c in changes[1:])


def test_compare_tab_states_the_tradeoff():
    infos = [i.value for i in start().tabs[1].info]
    assert any("most protective option" in i and "learner-days lost" in i for i in infos)


def test_compare_tab_has_no_star_until_a_recommendation_exists():
    at = start()
    assert not any(str(s).startswith("★") for s in at.tabs[1].dataframe[0].value["Scenario"])


def test_compare_follows_the_sidebar_profile():
    at = start()
    before = list(at.tabs[1].dataframe[0].value["Students infected"])
    at.sidebar.slider(key="mask_pct").set_value(90)
    at = submit(at)
    assert list(at.tabs[1].dataframe[0].value["Students infected"]) != before and not at.exception


# --- #26b seat map -------------------------------------------------------------------------

def test_seat_map_tab_renders_with_its_warning_and_controls():
    at = start()
    assert not at.exception
    tab = seat_tab(at)
    assert any("heuristic" in w.value for w in tab.warning)
    assert [b.key for b in tab.button] == ["seat_front", "seat_back", "seat_random", "seat_clear"]
    assert len(tab.get("plotly_chart")) == 1


def test_no_infected_student_means_no_cases_and_a_prompt():
    at = start()
    assert seat_metrics(at)["Expected new cases, next school day"] == "0.00"
    assert any("No infected student placed" in i.value for i in seat_tab(at).info)


def test_front_button_places_one_infected_student_in_the_first_column():
    at = press(start(), "seat_front")
    seats = sp.seat_grid(at.session_state["profile"]["class_size"], 9.0, 7.0)
    labels = seat_labels(seats)
    (seat,) = at.session_state["index_seats"]
    assert labels.index(seat) % len({round(x, 6) for x in seats[:, 0]}) == 0
    assert expected_next_day(at) > 0 and seat_metrics(at)["Highest-risk seat"] != "–"


def test_back_button_changes_the_seat_and_the_risk_map():
    front = press(start(), "seat_front")
    back = press(start(), "seat_back")
    assert front.session_state["index_seats"] != back.session_state["index_seats"]
    assert not back.exception


def test_random_button_picks_a_seat_and_clear_empties_it():
    at = press(start(), "seat_random")
    assert len(at.session_state["index_seats"]) == 1
    at = press(at, "seat_clear")
    assert at.session_state["index_seats"] == [] and expected_next_day(at) == 0


def test_two_random_clicks_can_differ():
    at = press(start(), "seat_random")
    seen = {tuple(at.session_state["index_seats"])}
    for _ in range(6):
        at = press(at, "seat_random")
        seen.add(tuple(at.session_state["index_seats"]))
    assert len(seen) > 1


def test_choosing_seats_by_hand_updates_the_numbers():
    at = start()
    seat_tab(at).multiselect(key="index_seats").select("A1")
    at.run()
    one = expected_next_day(at)
    seat_tab(at).multiselect(key="index_seats").select("C4")
    at.run()
    assert expected_next_day(at) > one > 0


def test_near_field_multiplier_changes_the_risk():
    at = press(start(), "seat_front")
    with_near_field = expected_next_day(at)
    seat_tab(at).slider(key="near_field_kappa").set_value(0.0)
    at.run()
    assert expected_next_day(at) < with_near_field


def test_better_ventilation_lowers_expected_cases():
    at = press(start(), "seat_front")
    before = expected_next_day(at)
    at.sidebar.selectbox(key="ventilation").select("Good")
    at = submit(at)
    assert expected_next_day(at) < before


def test_seats_that_no_longer_exist_are_dropped_when_the_class_shrinks():
    at = start()
    seat_tab(at).multiselect(key="index_seats").select("E1")
    at.run()
    at.sidebar.number_input(key="class_size").set_value(5)
    at = submit(at)
    assert not at.exception
    assert "E1" not in at.session_state["index_seats"]


def test_seat_map_uses_the_real_spatial_model():
    assert not any("Placeholder seat-risk model" in c.value for c in seat_tab(start()).caption)


def test_near_field_sliders_are_labelled_as_assumptions():
    tab = seat_tab(start())
    for key in ("near_field_kappa", "near_field_lambda"):
        assert "team assumption" in tab.slider(key=key).help


# --- #29 notices ---------------------------------------------------------------------------

def test_footer_carries_both_notices():
    captions = [c.value for c in start().main.caption]
    assert FOOTER_NOTICE in captions and DATA_NOTICE in captions


def test_assumptions_tab_shows_the_privacy_notice():
    at = start()
    tab = at.tabs[5]
    assert any("Privacy and responsible use" in h.value for h in tab.subheader)
    text = " ".join(m.value for m in tab.markdown)
    assert "Synthetic and aggregate data only" in text and "Nothing is saved" in text
    assert "AI-generated draft" in text and AI_DISCLOSURE.split(".")[0] in text


def test_data_notice_says_not_to_enter_real_records():
    assert "Do not enter real student records" in DATA_NOTICE
