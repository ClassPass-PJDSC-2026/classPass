import logging

import pandas as pd
import pandas.testing as pdt
import pytest

from schoolsim.params import REPO_ROOT
from schoolsim.presets import load_presets, lookup
from schoolsim.presets_build import (
    REGION_ALIASES,
    build_presets,
    canonical_region,
    load_psa_schools,
    load_wide,
    sanity_check,
)


def test_every_placeholder_region_is_a_canonical_region(tmp_path):
    placeholder, _ = load_presets(tmp_path / "nope.csv")
    assert set(placeholder["region"]) <= set(REGION_ALIASES)

def tidy(rows, sy):
    return pd.DataFrame(rows, columns=["region", "level", "value"]).assign(sy=sy)


ENROLLMENT = tidy(
    [("National Capital Region", "Elementary", 900), ("NCR", "JHS", 600),
     ("ARMM", "Elementary", 500), ("Philippines", "Elementary", 9999)],
    "2023-2024",
)
SCHOOLS = tidy([("NCR", "Elementary", 3), ("NCR", "JHS", 2), ("BARMM", "Elementary", 5)], "2022-2023")
CLASSROOMS = tidy([("Region XIII", "JHS", 1), ("NCR", "Elementary", 20), ("NCR", "JHS", 10)], "2022-2023")


def test_aliases_merge_and_values_are_computed():
    out = build_presets(ENROLLMENT, SCHOOLS, CLASSROOMS)
    row = out[(out.region == "NCR") & (out.level == "Elementary")].iloc[0]
    assert row.learners_per_classroom == 45.0 and row.learners_per_school == 300.0
    assert row.sy_enrollment == "2023-2024" and row.sy_classrooms == "2022-2023"


def test_incomplete_rows_are_logged_not_silently_dropped(caplog):
    caplog.set_level(logging.WARNING, logger="schoolsim.presets_build")
    out = build_presets(ENROLLMENT, SCHOOLS, CLASSROOMS)
    assert "BARMM" not in set(out.region)
    assert "BARMM" in caplog.text and "Philippines" in caplog.text


def test_build_is_idempotent():
    pdt.assert_frame_equal(
        build_presets(ENROLLMENT, SCHOOLS, CLASSROOMS), build_presets(ENROLLMENT, SCHOOLS, CLASSROOMS)
    )


def test_sanity_check_flags_values_outside_the_range():
    out = build_presets(ENROLLMENT, SCHOOLS, CLASSROOMS)
    assert sanity_check(out, low=15, high=100).empty

    too_low = sanity_check(out, low=50, high=100)
    assert list(too_low["level"]) == ["Elementary"]  # 45 < 50

    too_high = sanity_check(out, low=15, high=50)
    assert list(too_high["level"]) == ["JHS"]  # 60 > 50


def test_region_names_with_parentheses():
    assert canonical_region("Region IV-A (CALABARZON)") == "CALABARZON"
    assert canonical_region("unknown place") is None

def test_output_is_readable_by_the_loader(tmp_path):
    path = tmp_path / "presets.csv"
    build_presets(ENROLLMENT, SCHOOLS, CLASSROOMS).to_csv(path, index=False)
    table, placeholder = load_presets(path)
    assert placeholder is False
    assert lookup(table, "NCR", "Elementary")["learners_per_classroom"] == 45.0

RAW = REPO_ROOT / "data" / "raw"


def test_load_wide_melts_levels(tmp_path):
    path = tmp_path / "wide.csv"
    path.write_text("Region,Elementary,Junior High School\nRegion I,10,5\nNCR,20,8\n", encoding="utf-8")
    out = load_wide(path, "2020-2021")
    assert list(out.columns) == ["region", "level", "value", "sy"]
    assert len(out) == 4 and set(out["sy"]) == {"2020-2021"}
    assert out[(out.region == "NCR") & (out.level == "Junior High School")]["value"].iloc[0] == 8


def test_load_psa_schools_handles_title_line_dots_and_type(tmp_path):
    path = tmp_path / "schools.csv"
    path.write_text(
        '"TABLE 10.10 Number of Schools"\n\n'
        '"Geolocation";"Level of Education";"Type of School";"2020-2021"\n'
        '"..NCR";"Elementary";"Public";519\n'
        '"..NCR";"Elementary";"Private";700\n',
        encoding="utf-8",
    )
    out = load_psa_schools(path, "2020-2021")
    assert len(out) == 1
    assert out.iloc[0]["region"] == "NCR" and out.iloc[0]["value"] == 519


def test_real_raw_files_give_a_complete_presets_table():
    out = build_presets(
        load_wide(RAW / "psa_enrollment.csv", "2020-2021"),
        load_psa_schools(RAW / "psa_schools.csv", "2020-2021"),
        load_wide(RAW / "deped_classrooms.csv", "2019-2020"),
    )
    assert len(out) == 51  # 17 regions x 3 levels
    assert out["learners_per_classroom"].notna().all()
    row = out[(out.region == "NCR") & (out.level == "Elementary")].iloc[0]
    assert row.learners_per_classroom == pytest.approx(45.08, abs=0.01)  # TeacherPH prints 45.08
    assert sanity_check(out).empty