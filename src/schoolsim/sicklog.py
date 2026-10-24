"""Teacher sick log: pure functions behind the Teacher log tab (ticket B10).

Units: shares are fractions in 0-1 [-]; dates are calendar days. Nothing here touches a file,
database or network. Student IDs are synthetic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

STATUSES = ("healthy", "sick", "recovered")
# Generic categories, not diagnoses.
REASON_CODES = ("", "respiratory", "fever", "stomach", "other")
LOG_COLUMNS = ("student_id", "seat", "status", "onset_date", "return_date", "reason_code")
IDENTIFYING_COLUMNS = frozenset(
    {
        "name", "full_name", "first_name", "last_name", "middle_name", "given_name", "surname",
        "lrn", "birthdate", "birth_date", "dob", "email", "address", "phone", "guardian", "parent",
    }
)
ID_WIDTH = 3  # S001, S002, ...


def reject_identifying_columns(columns: Sequence[str]) -> None:
    """Raise ValueError if a column looks like it holds names or other identifying data."""
    banned = sorted({str(c).strip().lower() for c in columns} & IDENTIFYING_COLUMNS)
    if banned:
        raise ValueError(
            f"Remove the column(s) {', '.join(banned)} and upload again. "
            "The log accepts synthetic student IDs only."
        )

def _text(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        return pd.Series("", index=df.index, dtype=object)
    return df[name].fillna("").astype(str).str.strip()


def _dates(df: pd.DataFrame, name: str) -> pd.Series:
    """Column as datetime64[ns] at midnight; NaT where empty. Raises ValueError on bad dates."""
    if name not in df.columns:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    raw = df[name]
    parsed = pd.to_datetime(raw, errors="coerce", format="ISO8601")
    filled = raw.notna() & (raw.astype(str).str.strip() != "")
    if (parsed.isna() & filled).any():
        raise ValueError(f"Column '{name}' has a date that is not in YYYY-MM-DD form.")
    return parsed.dt.normalize()

def normalize_log(df: pd.DataFrame, *, max_rows: int | None = None) -> pd.DataFrame:
    """Validate a roster or log and return it with exactly ``LOG_COLUMNS``.

    Only ``student_id`` is required. Missing columns are filled: status ``healthy``, empty
    seat, dates and reason code. Raises ValueError with a readable message on bad input.
    """
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    reject_identifying_columns(df.columns)
    if "student_id" not in df.columns:
        raise ValueError("The file needs a 'student_id' column.")
    if df.empty:
        raise ValueError("The file has no student rows.")
    if max_rows is not None and len(df) > max_rows:
        raise ValueError(f"The roster has {len(df)} rows. The limit is {max_rows}.")

    ids = _text(df, "student_id")
    if (ids == "").any():
        raise ValueError("Every row needs a student_id.")
    if ids.duplicated().any():
        raise ValueError("Student IDs must be unique.")

    status = _text(df, "status").str.lower().replace("", "healthy")
    bad = sorted(set(status) - set(STATUSES))
    if bad:
        raise ValueError(f"Unknown status {bad}. Use one of: {', '.join(STATUSES)}.")

    reason = _text(df, "reason_code").str.lower()
    bad = sorted(set(reason) - set(REASON_CODES))
    if bad:
        raise ValueError(f"Unknown reason code {bad}. Use one of: {', '.join(c for c in REASON_CODES if c)}.")

    onset, back = _dates(df, "onset_date"), _dates(df, "return_date")
    if (back < onset).any():
        raise ValueError("A return date is before its onset date.")

    out = pd.DataFrame(
        {
            "student_id": ids,
            "seat": _text(df, "seat").str.upper(),
            "status": status,
            "onset_date": onset,
            "return_date": back,
            "reason_code": reason,
        }
    )
    return out[list(LOG_COLUMNS)].reset_index(drop=True)

def demo_roster(n: int) -> pd.DataFrame:
    """Synthetic roster of ``n`` students, all healthy, IDs S001..Snnn."""
    if n < 1:
        raise ValueError("The demo roster needs at least one student.")
    ids = [f"S{i:0{ID_WIDTH}d}" for i in range(1, n + 1)]
    return normalize_log(pd.DataFrame({"student_id": ids}))


def assign_default_seats(log: pd.DataFrame, labels: Sequence[str]) -> pd.DataFrame:
    """Fill blank seats with unused seat labels, in roster order. Existing seats are kept."""
    out = log.copy()
    free = iter(lab for lab in labels if lab not in set(out["seat"]))
    out["seat"] = [s if s else next(free, "") for s in out["seat"]]
    return out


def n_sick(log: pd.DataFrame) -> int:
    """Number of students with status ``sick``."""
    return int((log["status"] == "sick").sum())


def i0_from_log(log: pd.DataFrame) -> float:
    """Initial infected share [-]: students marked sick / roster size. 0 for an empty roster."""
    return n_sick(log) / len(log) if len(log) else 0.0


def index_seats_from_log(log: pd.DataFrame, valid_seats: Sequence[str]) -> list[str]:
    """Seat labels of sick students, without repeats, keeping only seats that exist in the room."""
    valid = set(valid_seats)
    sick = log.loc[log["status"] == "sick", "seat"]
    return list(dict.fromkeys(s for s in sick if s in valid))


def with_i0(values: Mapping[str, float], i0: float | None) -> dict[str, float]:
    """Copy of the engine values with ``initial_infected_frac`` replaced. ``None`` or 0 changes nothing."""
    out = dict(values)
    if i0:
        out["initial_infected_frac"] = float(i0)
    return out