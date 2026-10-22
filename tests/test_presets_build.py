import logging

import pandas as pd
import pandas.testing as pdt

from schoolsim.presets import load_presets, lookup
from schoolsim.presets_build import REGION_ALIASES, build_presets, canonical_region, sanity_check


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