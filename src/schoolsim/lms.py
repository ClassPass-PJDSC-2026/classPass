"""LMS bridge (ticket B10): a generic CSV adapter, plus documented stubs for real LMS adapters.

Only ``CSVAdapter`` is implemented. The attendance export is a *generic CSV*. Moodle and
Google Classroom have no universal attendance CSV, so this file makes no compatibility claim.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

import pandas as pd

from schoolsim.sicklog import normalize_log, reject_identifying_columns

ATTENDANCE_COLUMNS = ("student_id", "date", "present", "reason_code")
_TRUE = {"1", "true", "yes", "y", "present"}
_FALSE = {"0", "false", "no", "n", "absent"}


class LMSAdapter(Protocol):
    def import_roster(self, file: Any) -> pd.DataFrame: ...

    def export_attendance(self, log: pd.DataFrame, on_date: date | None = None) -> bytes: ...


def attendance_table(log: pd.DataFrame, on_date: date) -> pd.DataFrame:
    """One row per student for one day. ``present`` is 1 or 0.

    A student is absent when status is ``sick``, the onset date (if any) is on or before the
    day, and the return date (if any) is after it. ``reason_code`` is filled for absences only.
    """
    day = pd.Timestamp(on_date).normalize()
    started = log["onset_date"].isna() | (log["onset_date"] <= day)
    not_back = log["return_date"].isna() | (day < log["return_date"])
    absent = (log["status"] == "sick") & started & not_back
    return pd.DataFrame(
        {
            "student_id": log["student_id"],
            "date": day.strftime("%Y-%m-%d"),
            "present": (~absent).astype(int),
            "reason_code": log["reason_code"].where(absent, ""),
        }
    )[list(ATTENDANCE_COLUMNS)]

def _attendance_to_log(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn an attendance export back into a log. Several dates: the latest row per student wins."""
    missing = [c for c in ATTENDANCE_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"The attendance file is missing: {', '.join(missing)}.")
    present = raw["present"].str.strip().str.lower()
    unknown = sorted(set(present) - _TRUE - _FALSE)
    if unknown:
        raise ValueError(f"Unknown 'present' value {unknown}. Use 1 or 0.")
    ordered = (
        raw.assign(_absent=~present.isin(_TRUE))
        .sort_values("date", kind="stable")
        .drop_duplicates("student_id", keep="last")
    )
    absent = ordered["_absent"]
    return pd.DataFrame(
        {
            "student_id": ordered["student_id"],
            "status": absent.map({True: "sick", False: "healthy"}),
            "onset_date": ordered["date"].where(absent, ""),
            "reason_code": ordered["reason_code"].where(absent, ""),
        }
    )

class CSVAdapter:
    """Implemented. Reads a roster CSV (or an attendance export) and writes a generic attendance CSV.

    Roster CSV columns: ``student_id`` (required); optional ``seat, status, onset_date,
    return_date, reason_code`` (dates as YYYY-MM-DD).
    """

    def __init__(self, max_rows: int | None = None) -> None:
        self.max_rows = max_rows

    def import_roster(self, file: Any) -> pd.DataFrame:
        try:
            raw = pd.read_csv(
                file,
                dtype=str,
                keep_default_na=False,
                nrows=None if self.max_rows is None else self.max_rows + 1,
            )
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            raise ValueError("The file could not be read as a CSV.") from exc
        raw.columns = [str(c).strip().lower() for c in raw.columns]
        reject_identifying_columns(raw.columns)
        if "present" in raw.columns:
            raw = _attendance_to_log(raw)
        return normalize_log(raw, max_rows=self.max_rows)

    def export_attendance(self, log: pd.DataFrame, on_date: date | None = None) -> bytes:
        """UTF-8 CSV with columns student_id, date, present (1/0), reason_code."""
        table = attendance_table(log, on_date or date.today())
        return table.to_csv(index=False, lineterminator="\n").encode("utf-8")


_ROADMAP = "{} adapter is not implemented. See the 'LMS integration roadmap' section of the README."


class MoodleAdapter:
    """Stub. Roadmap only."""

    def import_roster(self, file: Any) -> pd.DataFrame:
        raise NotImplementedError(_ROADMAP.format("Moodle"))

    def export_attendance(self, log: pd.DataFrame, on_date: date | None = None) -> bytes:
        raise NotImplementedError(_ROADMAP.format("Moodle"))


class GoogleClassroomAdapter:
    """Stub. Roadmap only."""

    def import_roster(self, file: Any) -> pd.DataFrame:
        raise NotImplementedError(_ROADMAP.format("Google Classroom"))

    def export_attendance(self, log: pd.DataFrame, on_date: date | None = None) -> bytes:
        raise NotImplementedError(_ROADMAP.format("Google Classroom"))