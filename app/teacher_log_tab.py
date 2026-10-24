"""Teacher log tab (ticket B10): roster, sick log, bridge to the simulation, generic CSV export.

Shared state (session only, never written anywhere):
    log_base      table the editor starts from
    log           last valid edited table
    i0_override   initial infected share used by the simulation (read in streamlit_app.py)
    index_seats   seat labels shared with the Seat map tab
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import streamlit as st
from notices import LOG_BANNER

from schoolsim import spatial
from schoolsim.lms import CSVAdapter
from schoolsim.params import Param
from schoolsim.seating import seat_labels
from schoolsim.sicklog import (
    REASON_CODES,
    STATUSES,
    assign_default_seats,
    demo_roster,
    i0_from_log,
    index_seats_from_log,
    n_sick,
    normalize_log,
)

EXPORT_NAME = "attendance_export.csv"


def _room_labels(profile: Mapping) -> list[str]:
    seats = spatial.seat_grid(int(profile["class_size"]), float(profile["length_m"]), float(profile["width_m"]))
    return seat_labels(seats)


def _set_log(log) -> None:
    ss = st.session_state
    ss["log_base"] = log
    ss["log"] = log
    ss["log_nonce"] = ss.get("log_nonce", 0) + 1  # new editor key drops old edits


def _on_demo(profile: Mapping) -> None:
    st.session_state.pop("log_error", None)
    _set_log(assign_default_seats(demo_roster(int(profile["class_size"])), _room_labels(profile)))


def _on_use(log, labels: list[str]) -> None:
    ss = st.session_state
    ss["i0_override"] = i0_from_log(log)
    ss["index_seats"] = index_seats_from_log(log, labels)
    ss["seats_from_log"] = True


def _on_clear() -> None:
    ss = st.session_state
    for key in ("log_base", "log", "i0_override", "log_upload_id", "log_error"):
        ss.pop(key, None)
    if ss.pop("seats_from_log", False):
        ss["index_seats"] = []
    ss["log_nonce"] = ss.get("log_nonce", 0) + 1
    ss["upload_nonce"] = ss.get("upload_nonce", 0) + 1  # resets the file uploader

def render_teacher_log(profile: Mapping, params: Mapping[str, Param]) -> None:
    """Draw the Teacher log tab."""
    ss = st.session_state
    labels = _room_labels(profile)
    max_rows = int(params["class_size"].max)

    st.warning(LOG_BANNER)
    st.caption("The roster and log stay in this browser session. Nothing is written to disk or a database.")

    c1, c2 = st.columns(2)
    c1.button("Generate demo roster", key="log_demo", on_click=_on_demo, args=(profile,), width="stretch")
    uploaded = c2.file_uploader(
        "Upload roster CSV",
        type="csv",
        key=f"log_upload_{ss.get('upload_nonce', 0)}",
        help="Needs a student_id column. Optional: seat, status, onset_date, return_date, reason_code. "
        "Files with name columns are rejected.",
    )
    if uploaded is not None and ss.get("log_upload_id") != uploaded.file_id:
        ss["log_upload_id"] = uploaded.file_id
        try:
            roster = CSVAdapter(max_rows=max_rows).import_roster(uploaded)
            ss.pop("log_error", None)
            _set_log(assign_default_seats(roster, labels))
        except ValueError as exc:
            ss["log_error"] = str(exc)
    if ss.get("log_error"):
        st.error(ss["log_error"])

    if ss.get("log_base") is None:
        st.info("Generate a demo roster or upload a roster CSV to start.")
        return

    n_roster = len(ss["log_base"])
    if n_roster != int(profile["class_size"]):
        st.warning(
            f"The roster has {n_roster} students but the sidebar class size is {int(profile['class_size'])}. "
            "The initial infected share uses the roster size."
        )

    edited = st.data_editor(
        ss["log_base"],
        key=f"log_editor_{ss['log_nonce']}",
        num_rows="fixed",
        hide_index=True,
        width="stretch",
        disabled=["student_id", "seat"],
        column_config={
            "student_id": st.column_config.TextColumn("Student ID (synthetic)"),
            "seat": st.column_config.TextColumn("Seat"),
            "status": st.column_config.SelectboxColumn("Status", options=list(STATUSES), required=True),
            "onset_date": st.column_config.DateColumn("Onset date", format="YYYY-MM-DD"),
            "return_date": st.column_config.DateColumn("Return date", format="YYYY-MM-DD"),
            "reason_code": st.column_config.SelectboxColumn(
                "Reason code", options=[c for c in REASON_CODES if c]
            ),
        },
    )
    try:
        ss["log"] = normalize_log(edited)
    except ValueError as exc:
        st.error(f"{exc} Showing the last valid version.")
    log = ss["log"]

    i0 = i0_from_log(log)
    m1, m2 = st.columns(2)
    m1.metric("Students marked sick", f"{n_sick(log)} of {len(log)}")
    m2.metric("Initial infected share, i0", f"{i0:.1%}", help="Students marked sick / roster size. Unit: fraction.")

    st.button(
        "Use in simulation",
        key="log_use",
        type="primary",
        on_click=_on_use,
        args=(log, labels),
        help="Sets i0 and the index-case seats on the Seat map. Press again after you change the log.",
    )
    applied = ss.get("i0_override")
    if applied:
        st.success(f"The simulation uses i0 = {applied:.1%} and index seats: {', '.join(ss['index_seats']) or 'none'}.")
    else:
        default = params["initial_infected_frac"].value
        st.caption(f"Not applied. The simulation uses the default i0 = {default:.1%} (params.yaml).")

    st.subheader("Export")
    on_date = st.date_input("Attendance date", value=date.today(), key="log_export_date")
    st.download_button(
        "Download attendance_export.csv",
        data=CSVAdapter().export_attendance(log, on_date=on_date),
        file_name=EXPORT_NAME,
        mime="text/csv",
        key="log_download",
    )
    st.caption(
        "Generic CSV: student_id, date, present (1 = present, 0 = absent), reason_code. "
        "It is not a Moodle or Google Classroom import file."
    )

    st.button("Clear data", key="log_clear", on_click=_on_clear)