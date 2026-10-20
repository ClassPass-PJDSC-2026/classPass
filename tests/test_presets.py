"""Tests for schoolsim.presets (ticket #10 data source)."""

from __future__ import annotations

import logging

import pytest

from schoolsim.presets import LEVELS, REQUIRED_COLUMNS, load_presets, lookup, normalise_level


def write_csv(tmp_path, text):
    path = tmp_path / "presets.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_gives_placeholder(tmp_path):
    table, placeholder = load_presets(tmp_path / "nope.csv")
    assert placeholder is True
    assert set(REQUIRED_COLUMNS) <= set(table.columns)


def test_placeholder_covers_every_level_for_every_region(tmp_path):
    table, _ = load_presets(tmp_path / "nope.csv")
    for region, group in table.groupby("region"):
        assert set(group["level"]) == set(LEVELS), region


def test_real_file_is_used_and_cleaned(tmp_path):
    path = write_csv(
        tmp_path,
        "region,level,learners_per_classroom,learners_per_school,extra\n"
        " Region IV-A ,Junior High School,47.4,880,x\n"
        "Region IV-A,Senior High School,39,500,y\n"
        "Region IV-A,Elementary,41,410,z\n",
    )
    table, placeholder = load_presets(path)
    assert placeholder is False
    assert list(table.columns) == list(REQUIRED_COLUMNS)
    assert set(table["region"]) == {"Region IV-A"}
    assert set(table["level"]) == {"JHS", "SHS", "Elementary"}


def test_missing_columns_fall_back_and_log(tmp_path, caplog):
    path = write_csv(tmp_path, "region,level\nNCR,JHS\n")
    with caplog.at_level(logging.WARNING):
        table, placeholder = load_presets(path)
    assert placeholder is True and not table.empty
    assert "missing columns" in caplog.text


def test_unreadable_file_falls_back(tmp_path):
    path = tmp_path / "presets.csv"
    path.write_bytes(b"\x00\x01\x02 not a csv \xff\xfe")
    assert load_presets(path)[1] is True


def test_rows_without_class_size_are_dropped(tmp_path):
    path = write_csv(
        tmp_path,
        "region,level,learners_per_classroom,learners_per_school\nA,JHS,,500\nB,JHS,44,600\n",
    )
    table, placeholder = load_presets(path)
    assert placeholder is False
    assert list(table["region"]) == ["B"]


def test_all_rows_unusable_falls_back(tmp_path):
    path = write_csv(tmp_path, "region,level,learners_per_classroom,learners_per_school\nA,JHS,,500\n")
    assert load_presets(path)[1] is True


@pytest.mark.parametrize(
    "raw, expected",
    [("Elementary", "Elementary"), ("junior high school", "JHS"), (" SHS ", "SHS"), ("Grade 12", "Grade 12")],
)
def test_normalise_level(raw, expected):
    assert normalise_level(raw) == expected


def test_lookup_hit_and_miss(tmp_path):
    table, _ = load_presets(tmp_path / "nope.csv")
    hit = lookup(table, "NCR", "JHS")
    assert hit["learners_per_classroom"] == 48 and hit["learners_per_school"] == 900
    assert lookup(table, "Atlantis", "JHS") == {"learners_per_classroom": None, "learners_per_school": None}


def test_lookup_nan_school_size_is_none(tmp_path):
    path = write_csv(
        tmp_path,
        "region,level,learners_per_classroom,learners_per_school\nA,JHS,44,\n",
    )
    table, _ = load_presets(path)
    assert lookup(table, "A", "JHS") == {"learners_per_classroom": 44.0, "learners_per_school": None}
