"""Build region x level presets from raw PSA / DepEd tables.

Units: enrollment in learners, classrooms and schools as counts,
learners_per_classroom and learners_per_school in learners.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from schoolsim.presets import normalise_level

LOGGER = logging.getLogger("schoolsim.presets_build")

KEYS = ["region", "level"]
NEEDED = ["enrollment", "schools", "classrooms"]
COLUMNS = [
    "region", "level", "sy_enrollment", "sy_classrooms", "enrollment", "schools",
    "classrooms", "learners_per_classroom", "learners_per_school",
]

# One canonical label per region. ARMM maps to BARMM (renamed 2019); NIR is kept
# separate only if a source lists it. Align these labels with what the app shows.
REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "NCR": ("National Capital Region", "Metro Manila"),
    "CAR": ("Cordillera Administrative Region", "Cordillera"),
    "Ilocos Region": ("Region I", "Region 1"),
    "Cagayan Valley": ("Region II", "Region 2"),
    "Central Luzon": ("Region III", "Region 3"),
    "CALABARZON": ("Region IV-A", "Region 4A"),
    "MIMAROPA": ("Region IV-B", "Region 4B", "MIMAROPA Region"),
    "Bicol Region": ("Region V", "Region 5"),
    "Western Visayas": ("Region VI", "Region 6"),
    "Central Visayas": ("Region VII", "Region 7"),
    "NIR": ("Negros Island Region",),
    "Eastern Visayas": ("Region VIII", "Region 8"),
    "Zamboanga Peninsula": ("Region IX", "Region 9"),
    "Northern Mindanao": ("Region X", "Region 10"),
    "Davao Region": ("Region XI", "Region 11"),
    "SOCCSKSARGEN": ("Region XII", "Region 12"),
    "CARAGA": ("Region XIII", "Region 13"),
    "BARMM": (
        "ARMM",
        "Autonomous Region in Muslim Mindanao",
        "Bangsamoro Autonomous Region in Muslim Mindanao",
    ),
}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


_LOOKUP = {
    _key(alias): canonical
    for canonical, aliases in REGION_ALIASES.items()
    for alias in (canonical, *aliases)
}


def canonical_region(name: object) -> str | None:
    """Map a source region label to its canonical name, or None if unknown."""
    text = str(name)
    for part in (text, text.split("(")[0], *re.findall(r"\(([^)]*)\)", text)):
        hit = _LOOKUP.get(_key(part))
        if hit:
            return hit
    return None


def standardise(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Canonical region and level names, numeric values, one row per (region, level)."""
    out = df.copy()
    mapped = out["region"].map(canonical_region)
    unmatched = sorted({str(r) for r in out.loc[mapped.isna(), "region"]})
    if unmatched:
        LOGGER.warning("%s: dropping unmatched regions: %s", source, unmatched)
    out["region"] = mapped
    out["level"] = out["level"].map(normalise_level)
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["region"])
    return out.groupby(KEYS, as_index=False).agg(value=("value", "sum"), sy=("sy", "first"))


def build_presets(
    enrollment: pd.DataFrame, schools: pd.DataFrame, classrooms: pd.DataFrame
) -> pd.DataFrame:
    """Merge the three tidy tables (region, level, value, sy) into the presets table."""
    e = standardise(enrollment, "enrollment").rename(
        columns={"value": "enrollment", "sy": "sy_enrollment"}
    )
    s = standardise(schools, "schools").rename(columns={"value": "schools"}).drop(columns="sy")
    c = standardise(classrooms, "classrooms").rename(
        columns={"value": "classrooms", "sy": "sy_classrooms"}
    )
    LOGGER.info("rows before merge: enrollment=%d schools=%d classrooms=%d", len(e), len(s), len(c))

    merged = e.merge(s, on=KEYS, how="outer").merge(c, on=KEYS, how="outer")
    LOGGER.info("rows after outer merge: %d", len(merged))

    incomplete = merged[merged[NEEDED].isna().any(axis=1)]
    for row in incomplete.itertuples():
        missing = [col for col in NEEDED if pd.isna(getattr(row, col))]
        LOGGER.warning("missing %s for %s / %s (row not in presets)", missing, row.region, row.level)

    full = merged.dropna(subset=NEEDED).copy()
    full["learners_per_classroom"] = full["enrollment"] / full["classrooms"].where(full["classrooms"] > 0)
    full["learners_per_school"] = full["enrollment"] / full["schools"].where(full["schools"] > 0)
    full = full.sort_values(KEYS).reset_index(drop=True)[COLUMNS]
    LOGGER.info("rows in presets: %d", len(full))
    return full.round({"learners_per_classroom": 2, "learners_per_school": 2})


def sanity_check(presets: pd.DataFrame, low: float = 15.0, high: float = 100.0) -> pd.DataFrame:
    """Log min / median / max learners per classroom by level; return rows outside [low, high]."""
    stats = presets.groupby("level")["learners_per_classroom"].agg(["min", "median", "max"])
    LOGGER.info("learners_per_classroom by level:\n%s", stats.round(1).to_string())
    col = presets["learners_per_classroom"]
    flagged = presets[(col < low) | (col > high)]
    for row in flagged.itertuples():
        LOGGER.warning(
            "FLAG %s / %s: %.1f learners per classroom outside %g-%g",
            row.region, row.level, row.learners_per_classroom, low, high,
        )
    return flagged