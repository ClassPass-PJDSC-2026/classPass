"""Privacy and responsible-use wording shown in the app (ticket #29).

One place for the text so the footer, the Assumptions tab and the AI assistant tab (#27)
say the same thing. The reasoning and sources are in docs/privacy_and_responsible_use.md.
Keep every statement here true of the code; tests/test_privacy.py checks the main ones.
"""

from __future__ import annotations

import streamlit as st

FOOTER_NOTICE = "Scenario simulation for decision support, not a medical forecast."
DATA_NOTICE = "Synthetic and aggregate data only. Nothing you enter is saved. Do not enter real student records."

NOTICE_POINTS = (
    (
        "Synthetic and aggregate data only",
        "The school profile is a class size, a room size and a ventilation setting. It is not information "
        "about any student. Do not enter or upload real student names, IDs or health records.",
    ),
    (
        "Nothing is saved",
        "What you enter lives only in your browser session. The app does not write it to a file or a database.",
    ),
    (
        "Simulation, not a forecast",
        "Results compare options for the same school. They do not predict case counts and are not medical advice.",
    ),
)

AI_DISCLOSURE = (
    "AI-generated draft. Review it before you send it. The assistant sees only summary numbers from the "
    "simulation (scenario results and settings). It is never given student names or IDs. It does not give "
    "medical advice; for health decisions, follow the school nurse and Department of Health guidance."
)


def render_privacy_notice() -> None:
    """The full notice, for the Assumptions tab."""
    st.subheader("Privacy and responsible use")
    for title, text in NOTICE_POINTS:
        st.markdown(f"**{title}.** {text}")
    st.markdown(f"**AI assistant.** {AI_DISCLOSURE}")
    st.caption("Details, data flow and sources: docs/privacy_and_responsible_use.md in the repository.")
