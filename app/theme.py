"""Shared colours for every tab (ticket #11 note: one colour per compartment, one per scenario).

Chosen to stay readable on both Streamlit's light and dark backgrounds.
"""

from __future__ import annotations

COMPARTMENT_COLORS = {
    "S": "#5B84B1",  # healthy
    "E": "#E1A53A",  # exposed
    "I": "#DE6249",  # infectious
    "R": "#4E9E72",  # recovered
}

COMPARTMENT_LABELS = {
    "S": "Healthy",
    "E": "Exposed",
    "I": "Infectious",
    "R": "Recovered",
}

SCENARIO_COLORS = {
    "baseline": "#7F8C9B",
    "better_ventilation": "#1AA6B7",
    "smaller_classes": "#9B6BD1",
    "masks": "#E07BA0",
    "combined": "#0F7B5F",
    "hybrid": "#A5843B",
    "online": "#2F5DA8",
}

# Neutral grey that works on light and dark backgrounds.
WEEKEND_FILL = "rgba(128, 128, 128, 0.16)"
WEEKEND_LEGEND_COLOR = "rgba(128, 128, 128, 0.45)"
