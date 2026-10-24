"""Raw PSA / DepEd CSVs -> data/processed/presets.csv. Run with `make data`.

School years of each raw file are listed in data/README.md.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from schoolsim.presets_build import build_presets, load_psa_schools, load_wide, sanity_check

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "presets.csv"

SY_ENROLLMENT = "2020-2021"  # DepEd LIS via TeacherPH (psa_enrollment.csv)
SY_SCHOOLS = "2020-2021"  # PSA OpenSTAT Table 10.10 (psa_schools.csv)
SY_CLASSROOMS = "2019-2020"  # DepEd NSBI via TeacherPH (deped_classrooms.csv)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    enrollment = load_wide(RAW / "psa_enrollment.csv", SY_ENROLLMENT)
    schools = load_psa_schools(RAW / "psa_schools.csv", SY_SCHOOLS)
    classrooms = load_wide(RAW / "deped_classrooms.csv", SY_CLASSROOMS)

    presets = build_presets(enrollment, schools, classrooms)
    sanity_check(presets)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    presets.to_csv(OUT, index=False, lineterminator="\n")
    print(f"wrote {len(presets)} rows to {OUT}")


if __name__ == "__main__":
    main()