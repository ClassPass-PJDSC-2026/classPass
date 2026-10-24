"""Tests for the teacher sick log and the generic CSV bridge (ticket B10)."""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import pytest

from schoolsim.lms import CSVAdapter, GoogleClassroomAdapter, MoodleAdapter, attendance_table
from schoolsim.sicklog import (
    assign_default_seats,
    demo_roster,
    i0_from_log,
    index_seats_from_log,
    normalize_log,
    with_i0,
)

LABELS = [f"{r}{c}" for r in "ABC" for c in range(1, 11)]
DAY = date(2026, 10, 21)


def sample_log(n: int = 30, sick: int = 3) -> pd.DataFrame:
    log = assign_default_seats(demo_roster(n), LABELS)
    log.loc[: sick - 1, "status"] = "sick"
    log.loc[: sick - 1, "onset_date"] = pd.Timestamp("2026-10-20")
    log.loc[: sick - 1, "reason_code"] = "fever"
    log.loc[sick, "status"] = "recovered"
    log.loc[sick, "return_date"] = pd.Timestamp("2026-10-21")
    return normalize_log(log)


def csv_bytes(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


# --- i0 and index seats ----------------------------------------------------------------------

def test_marking_three_students_sick_sets_i0_to_three_over_class_size():
    assert i0_from_log(sample_log(30, 3)) == pytest.approx(3 / 30)
    assert i0_from_log(sample_log(42, 3)) == pytest.approx(3 / 42)


def test_nobody_sick_leaves_the_engine_values_alone():
    values = {"initial_infected_frac": 0.01}
    assert i0_from_log(demo_roster(30)) == 0.0
    assert with_i0(values, 0.0) == values


def test_with_i0_overrides_without_mutating_the_input():
    values = {"initial_infected_frac": 0.01, "x": 1.0}
    out = with_i0(values, 0.1)
    assert out["initial_infected_frac"] == 0.1 and values["initial_infected_frac"] == 0.01


def test_index_seats_are_the_seats_of_sick_students_that_exist():
    log = sample_log(30, 3)
    assert index_seats_from_log(log, LABELS) == ["A1", "A2", "A3"]
    assert index_seats_from_log(log, ["A1"]) == ["A1"]


# --- round trips -----------------------------------------------------------------------------

def test_roster_csv_round_trip_gives_the_same_table():
    log = sample_log()
    back = CSVAdapter().import_roster(csv_bytes(log.to_csv(index=False)))
    pd.testing.assert_frame_equal(back, log)


def test_attendance_export_round_trip_gives_the_same_attendance_table():
    log = sample_log()
    adapter = CSVAdapter()
    data = adapter.export_attendance(log, on_date=DAY)
    back = adapter.import_roster(io.BytesIO(data))
    pd.testing.assert_frame_equal(attendance_table(back, DAY), attendance_table(log, DAY))
    assert adapter.export_attendance(back, on_date=DAY) == data


def test_attendance_export_has_the_agreed_columns_and_marks_sick_students_absent():
    data = CSVAdapter().export_attendance(sample_log(30, 3), on_date=DAY).decode("utf-8")
    lines = data.splitlines()
    assert lines[0] == "student_id,date,present,reason_code"
    assert lines[1] == "S001,2026-10-21,0,fever"
    assert lines[4] == "S004,2026-10-21,1,"  # the recovered student is present


def test_a_sick_student_is_present_before_onset_and_after_return():
    log = sample_log(30, 1)
    log.loc[0, "return_date"] = pd.Timestamp("2026-10-23")
    assert attendance_table(log, date(2026, 10, 19)).loc[0, "present"] == 1
    assert attendance_table(log, date(2026, 10, 22)).loc[0, "present"] == 0
    assert attendance_table(log, date(2026, 10, 23)).loc[0, "present"] == 1


# --- validation ------------------------------------------------------------------------------

@pytest.mark.parametrize("column", ["name", "Full_Name", "lrn", "email"])
def test_files_with_identifying_columns_are_rejected(column):
    with pytest.raises(ValueError, match="synthetic"):
        CSVAdapter().import_roster(csv_bytes(f"student_id,{column}\nS001,x\n"))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("seat\nA1\n", "student_id"),
        ("student_id\nS001\nS001\n", "unique"),
        ("student_id\n\n", "no student rows"),
        ("student_id,status\nS001,ill\n", "Unknown status"),
        ("student_id,reason_code\nS001,flu\n", "Unknown reason"),
        ("student_id,onset_date\nS001,21/10/2026\n", "YYYY-MM-DD"),
        ("student_id,onset_date,return_date\nS001,2026-10-21,2026-10-20\n", "before"),
    ],
)
def test_bad_rosters_give_a_readable_error(text, message):
    with pytest.raises(ValueError, match=message):
        CSVAdapter().import_roster(csv_bytes(text))


def test_roster_larger_than_the_limit_is_rejected():
    text = "student_id\n" + "\n".join(f"S{i:03d}" for i in range(1, 8))
    with pytest.raises(ValueError, match="limit"):
        CSVAdapter(max_rows=5).import_roster(csv_bytes(text))


def test_empty_file_gives_a_readable_error():
    with pytest.raises(ValueError, match="CSV"):
        CSVAdapter().import_roster(csv_bytes(""))


@pytest.mark.parametrize("adapter", [MoodleAdapter(), GoogleClassroomAdapter()])
def test_unimplemented_adapters_raise_not_implemented(adapter):
    with pytest.raises(NotImplementedError, match="roadmap"):
        adapter.import_roster(None)
    with pytest.raises(NotImplementedError, match="roadmap"):
        adapter.export_attendance(demo_roster(3))