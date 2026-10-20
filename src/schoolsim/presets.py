"""Regional defaults (class size, school enrollment) for the sidebar.

The real table is ``data/processed/presets.csv`` from ticket #8. Until it exists, or if it
is missing columns, :func:`load_presets` returns a small PLACEHOLDER table and says so, so
the app still runs and the UI can label the numbers as placeholders.

Expected CSV columns: ``region, level, learners_per_classroom, learners_per_school``
(other columns from #8 are ignored). ``level`` is normalised to Elementary / JHS / SHS.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from schoolsim.params import REPO_ROOT

LOGGER = logging.getLogger(__name__)

DEFAULT_PRESETS_PATH = REPO_ROOT / "data" / "processed" / "presets.csv"
REQUIRED_COLUMNS = ("region", "level", "learners_per_classroom", "learners_per_school")
LEVELS = ("Elementary", "JHS", "SHS")

_LEVEL_ALIASES = {
    "elementary": "Elementary",
    "elem": "Elementary",
    "jhs": "JHS",
    "junior high": "JHS",
    "junior high school": "JHS",
    "shs": "SHS",
    "senior high": "SHS",
    "senior high school": "SHS",
}

# PLACEHOLDER values for development only. Not real data; replaced by presets.csv (#8).
_PLACEHOLDER_ROWS = [
    # region, level, learners_per_classroom, learners_per_school
    ("NCR", "Elementary", 42, 450),
    ("NCR", "JHS", 48, 900),
    ("NCR", "SHS", 40, 600),
    ("CALABARZON", "Elementary", 40, 400),
    ("CALABARZON", "JHS", 46, 800),
    ("CALABARZON", "SHS", 38, 550),
    ("Central Luzon", "Elementary", 38, 380),
    ("Central Luzon", "JHS", 44, 750),
    ("Central Luzon", "SHS", 37, 500),
    ("Central Visayas", "Elementary", 36, 350),
    ("Central Visayas", "JHS", 42, 700),
    ("Central Visayas", "SHS", 36, 480),
    ("Davao Region", "Elementary", 37, 360),
    ("Davao Region", "JHS", 43, 720),
    ("Davao Region", "SHS", 36, 470),
    ("BARMM", "Elementary", 45, 330),
    ("BARMM", "JHS", 47, 650),
    ("BARMM", "SHS", 40, 420),
]


def _placeholder() -> pd.DataFrame:
    return pd.DataFrame(_PLACEHOLDER_ROWS, columns=list(REQUIRED_COLUMNS))


def normalise_level(value: object) -> str:
    """Map a level label to Elementary / JHS / SHS; unknown labels are returned stripped."""
    text = str(value).strip()
    return _LEVEL_ALIASES.get(text.lower(), text)


def load_presets(path: str | Path | None = None) -> tuple[pd.DataFrame, bool]:
    """Load regional presets.

    Returns:
        ``(table, is_placeholder)``. ``table`` has ``REQUIRED_COLUMNS``; ``is_placeholder``
        is true when the built-in placeholder table was used because the file is missing,
        unreadable, or lacks required columns.
    """
    path = Path(path) if path is not None else DEFAULT_PRESETS_PATH
    if not path.exists():
        return _placeholder(), True
    try:
        raw = pd.read_csv(path)
        missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
        if missing:
            raise ValueError(f"missing columns: {', '.join(missing)}")
        table = raw[list(REQUIRED_COLUMNS)].copy()
        table["region"] = table["region"].astype(str).str.strip()
        table["level"] = table["level"].map(normalise_level)
        table["learners_per_classroom"] = pd.to_numeric(table["learners_per_classroom"], errors="coerce")
        table["learners_per_school"] = pd.to_numeric(table["learners_per_school"], errors="coerce")
        table = table.dropna(subset=["region", "level", "learners_per_classroom"]).reset_index(drop=True)
        if table.empty:
            raise ValueError("no usable rows")
        return table, False
    except Exception as exc:  # never let a bad data file crash the app
        LOGGER.warning("Could not read %s (%s); using placeholder presets", path, exc)
        return _placeholder(), True


def lookup(table: pd.DataFrame, region: str, level: str) -> dict[str, float | None]:
    """Preset row for a region and level.

    Returns ``{"learners_per_classroom": float | None, "learners_per_school": float | None}``;
    values are ``None`` when the combination is missing or not a number.
    """
    rows = table[(table["region"] == region) & (table["level"] == level)]
    if rows.empty:
        return {"learners_per_classroom": None, "learners_per_school": None}
    row = rows.iloc[0]

    def clean(x: object) -> float | None:
        return None if pd.isna(x) else float(x)

    return {
        "learners_per_classroom": clean(row["learners_per_classroom"]),
        "learners_per_school": clean(row["learners_per_school"]),
    }
