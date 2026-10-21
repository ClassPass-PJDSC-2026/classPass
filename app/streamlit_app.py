"""Classroom Outbreak Simulator, Team Board Game, PJDSC 2026.

Run with ``make run`` or ``streamlit run app/streamlit_app.py``.

This file only wires things together: it reads inputs from the sidebar, calls the
simulation through ``schoolsim.engine`` and renders. No model maths lives here.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SRC_DIR = APP_DIR.parent / "src"
for _path in (APP_DIR, SRC_DIR):  # lets `streamlit run` work without `pip install -e .`
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Classroom Outbreak Simulator", page_icon="🏫", layout="wide")

import sidebar  # noqa: E402
from compare_tab import render_compare  # noqa: E402
from notices import DATA_NOTICE, FOOTER_NOTICE, render_privacy_notice  # noqa: E402
from results_tab import render_results  # noqa: E402
from seat_map_tab import render_seat_map  # noqa: E402

from schoolsim.engine import PROFILE_FIELDS, get_backend  # noqa: E402
from schoolsim.inputs import engine_values  # noqa: E402
from schoolsim.params import load_params, load_references  # noqa: E402
from schoolsim.presets import load_presets  # noqa: E402

LOGGER = logging.getLogger("schoolsim.app")


@st.cache_data(show_spinner=False)
def _params():
    return load_params()


@st.cache_data(show_spinner=False)
def _references():
    return load_references()


@st.cache_data(show_spinner=False)
def _presets():
    return load_presets()


@st.cache_data(show_spinner=False)
def _run_all(engine_name: str, profile: dict, values: dict) -> dict:
    """Run every scenario. ``engine_name`` is part of the cache key so switching from the
    placeholder to the real engine never serves old results."""
    return get_backend().run_all(profile, values)


def _recommended_id() -> str | None:
    """Scenario chosen by the recommender (ticket #14). None until that exists.

    When recommend.py is merged, call it here and return its scenario id; the Compare tab
    then highlights that row automatically.
    """
    return None


def main() -> None:
    try:
        params = _params()
        refs = _references()
    except Exception as exc:  # a bad params.yaml must show a message, not a stack trace
        LOGGER.exception("Could not load parameters")
        st.error(f"Could not load the model parameters: {exc}")
        st.stop()
    presets, presets_are_placeholder = _presets()
    backend = get_backend()

    sidebar.init_state(params, presets)
    sidebar.render_sidebar(params, refs, presets, presets_are_placeholder)

    st.title("Classroom Outbreak Simulator")
    st.caption("Compare how ventilation, masks, class size and class format change an airborne outbreak.")
    if backend.is_placeholder:
        st.warning("Placeholder engine in use until the Wells-Riley and SEIR engine (#5, #6, #9) is merged.")

    profile = st.session_state["profile"]
    values = engine_values(params, profile)
    try:
        results = _run_all(backend.name, {k: profile[k] for k in PROFILE_FIELDS}, values)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    except Exception:
        LOGGER.exception("Simulation failed")
        st.error("The simulation could not run with these inputs. Change them and press Run simulation.")
        st.stop()

    tab_results, tab_compare, tab_seats, tab_sens, tab_assume = st.tabs(
        ["Results", "Compare", "Seat map", "Sensitivity", "Assumptions"]
    )
    with tab_results:
        render_results(profile, values, results, backend)
    with tab_compare:
        render_compare(profile, values, results, backend, _recommended_id())
    with tab_seats:
        render_seat_map(profile, values, params)
    with tab_sens:
        st.info("The sensitivity analysis is built in ticket #13.")
    with tab_assume:
        st.info("The full assumptions table is built in ticket #15.")
        render_privacy_notice()

    st.caption(FOOTER_NOTICE)
    st.caption(DATA_NOTICE)


main()
