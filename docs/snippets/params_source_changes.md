# Edits to params.yaml (apply together with the new references.yaml)

The new `references.yaml` drops three entries from the A3 version, so three parameters must point at their replacements. Until you do this, `tests/test_params.py` fails with "unknown source key".

In `params.yaml`, change only the `source:` line of these three parameters.

| Parameter | Old source line | New source line |
|---|---|---|
| `quanta_rate` | `source: [rudnick_milton_2003, cdph_quanta_appendix, wr_size_dependent_review]` | `source: [rudnick_milton_2003, azimi_stephens_2013]` |
| `breathing_rate` | `source: [buonanno_2020]` | `source: [epa_2011]` |
| `class_size` | `source: [deped_facilities_2010]` | `source: [team_assumption]` |

Why: the "size-dependent review" entry was filed under a section heading, not a real title, and is really Azimi & Stephens (2013); the CDPH table could not be opened to verify it; the breathing-rate paper could not be verified and the EPA handbook is a verified source for the same number; and no readable DepEd learners-per-classroom standard was found for the class-size default.
