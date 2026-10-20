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
from results_tab import render_results  # noqa: E402

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

    tab_results, tab_compare, tab_sens, tab_assume = st.tabs(["Results", "Compare", "Sensitivity", "Assumptions"])
    with tab_results:
        render_results(profile, values, results, backend)
    with tab_compare:
        st.info("The scenario comparison is built in ticket #12.")
    with tab_sens:
        st.info("The sensitivity analysis is built in ticket #13.")
    with tab_assume:
        st.info("The assumptions page is built in ticket #15.")

    st.caption("Scenario simulation for decision support, not a medical forecast.")


main()
