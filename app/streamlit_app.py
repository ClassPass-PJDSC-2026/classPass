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
from sensitivity_tab import render_sensitivity  # noqa: E402
from teacher_log_tab import render_teacher_log  # noqa: E402

from schoolsim.calibrate import (  # noqa: E402
    DISEASE_PRESETS,
    build_params_for_mode,
    make_custom_preset,
)
from schoolsim.engine import PROFILE_FIELDS, get_backend  # noqa: E402
from schoolsim.inputs import engine_values  # noqa: E402
from schoolsim.params import load_params, load_references  # noqa: E402
from schoolsim.presets import load_presets  # noqa: E402
from schoolsim.sicklog import with_i0  # noqa: E402

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


def _build_active_params(params, profile, mode, preset_key, target_r0, profile_cls):
    """Params for the requested mode. Raises ValueError if calibration fails."""
    if mode != "Calibrated":
        return params, "physical", None
    school_profile = profile_cls(**{k: profile[k] for k in PROFILE_FIELDS})
    if preset_key == "custom":
        preset = make_custom_preset(float(target_r0))
    else:
        preset = DISEASE_PRESETS[preset_key]
    active = build_params_for_mode(
        params, "calibrated",
        target_r0=preset.r0, profile=school_profile, preset=preset,
    )
    return active, "calibrated", preset.name


def _active_params(params, profile, profile_cls):
    """Mode/preset/target from *submitted* state, so widget changes don't re-run the sim."""
    ss = st.session_state
    return _build_active_params(
        params, profile,
        ss.get("active_mode", "Physical"),
        ss.get("active_preset_key", "influenza"),
        ss.get("active_target_r0", 1.5),
        profile_cls,
    )


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
    try:
        active_params, transmission_mode, preset_name = _active_params(
            params, profile, backend.profile_cls
        )
    except ValueError as exc:
        st.error(f"Cannot run calibrated mode: {exc}")
        st.info("Change the target R0 or switch to Physical mode, then press Run simulation.")
        st.stop()

    values = engine_values(active_params, profile)
    values = with_i0(values, st.session_state.get("i0_override"))
    calibrated_quanta = (
        active_params["quanta_rate"].value if transmission_mode == "calibrated" else None
    )

    try:
        results = _run_all(backend.name, {k: profile[k] for k in PROFILE_FIELDS}, values)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    except Exception:
        LOGGER.exception("Simulation failed")
        st.error("The simulation could not run with these inputs. Change them and press Run simulation.")
        st.stop()

    tab_results, tab_compare, tab_seats, tab_sens, tab_log, tab_assume = st.tabs(
        ["Results", "Compare", "Seat map", "Sensitivity", "Teacher log", "Assumptions"]
    )
    with tab_results:
        render_results(
            profile, values, results, backend,
            transmission_mode=transmission_mode,
            calibrated_quanta=calibrated_quanta,
            preset_name=preset_name,
        )
    with tab_compare:
        render_compare(profile, values, results, backend, _recommended_id())
    with tab_seats:
        render_seat_map(profile, values, params)
    with tab_sens:
        render_sensitivity(profile, active_params, backend)
    with tab_log:
        render_teacher_log(profile, params)
    with tab_assume:
        with open("docs/assumptions.md", encoding="utf-8") as f:
            st.markdown(f.read())
        render_privacy_notice()

    st.caption(FOOTER_NOTICE)
    st.caption(DATA_NOTICE)


main()
