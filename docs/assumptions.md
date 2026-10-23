# Model assumptions

Every number the simulator uses lives in [`params.yaml`](../params.yaml). This page explains where each value comes from, how sure we are, and where sources disagree. Full references are in [`references_apa7.md`](references_apa7.md) and are kept in [`references.yaml`](../references.yaml).

Results are **relative scenario comparisons, not forecasts**. A wide range is not a weakness: the sensitivity analysis varies every uncertain input across its range and reports whether the recommendation still holds.

**Default disease:** seasonal influenza. Other diseases are handled by calibrated R₀ mode (ticket #23).

## Parameter table

| Key | Base | Range | Unit | Source | Confidence |
|---|---|---|---|---|---|
| `quanta_rate` | 15 | 5–128 (log-uniform) | quanta/h | Rudnick & Milton (2003); Azimi & Stephens (2013) | low |
| `breathing_rate` | 0.5 | 0.3–0.6 | m³/h | U.S. EPA (2011) | low |
| `latent_days` | 1.0 | 0.5–2.0 | days | Carrat et al. (2008) | medium |
| `infectious_days` | 4.8 | 3.5–7.0 | days | Carrat et al. (2008) | medium |
| `mask_efficiency` | 0.3 | 0.0–0.6 | fraction | Leung et al. (2020) | low |
| `infectious_attendance` | 0.5 | 0.3–0.8 | fraction | Carrat et al. (2008); team assumption | low |
| `community_beta` | 0.1 | 0.05–0.2 | 1/day | team assumption | low |
| `initial_infected_frac` | 0.01 | 0.005–0.02 | fraction | team assumption | low |
| `class_size` | 45 | 5–80 | students | team assumption (regional presets override) | medium |
| `room_length` | 9.0 | 3–30 | m | DepEd (2017) | medium |
| `room_width` | 7.0 | 3–30 | m | DepEd (2017) | medium |
| `room_height` | 2.7 | 2.4–4.0 | m | DepEd (2010) | medium |
| `session_hours` | 6 | 4–8 | h | team assumption | low |
| `mask_compliance` | 0 | 0–1 | fraction | user input | high |
| `ach` | 4 | 0.5–20 | 1/h | Harvard Healthy Buildings Program (2020) | medium |
| `ach_poor` | 2 | fixed | 1/h | Harvard Healthy Buildings Program (2020); team assumption | medium |
| `ach_typical` | 4 | fixed | 1/h | Harvard Healthy Buildings Program (2020); team assumption | low |
| `ach_good` | 6 | fixed | 1/h | Harvard Healthy Buildings Program (2020) | medium |
| `school_days_per_week` | 5 | fixed | days | team assumption | high |
| `sim_days` | 60 | 30–60 | days | team decision | high |
| `sick_days_per_case` | 3 | 2–5 | days | team assumption | low |
| `online_learning_weight` | 0.3 | 0.1–0.5 | fraction | team assumption | low |
| `attack_rate_threshold` | 0.10 | 0.02–0.40 | fraction | team decision | high |
| `robustness_threshold` | 0.80 | 0.50–0.95 | fraction | team decision | high |
| `near_field_multiplier` | 3 | 0–10 | factor | team assumption (heuristic) | low |
| `near_field_decay_m` | 1.5 | 0.5–3 | m | team assumption (heuristic) | low |

"High" confidence on user inputs and team decisions means the value is a choice, not an estimate.

## Why each value

**`quanta_rate`.** Quanta are the infectious "doses" a sick person emits per hour; this is the most uncertain input in the model. Rudnick and Milton (2003) estimated about 15–128 quanta/h for influenza from an airliner outbreak, depending on steady-state or dynamic assumptions, as described in Azimi and Stephens (2013), who tabulate published influenza values of about 15–500 quanta/h. We use 15 as the base and 5–128 as the range. The lower bound of 5 is below the published range and is our own choice, so that milder spreaders are covered. Sampling is log-uniform because the plausible values cover more than an order of magnitude.

**`breathing_rate`.** The U.S. EPA's long-term mean inhalation rate for children aged 6 to under 11 is 12 m³/day (U.S. EPA, 2011), which is 0.5 m³/h averaged over 24 hours. Azimi et al. (2020) interpolate 12.96 m³/day for primary and 15.53 m³/day for secondary students from the same handbook (0.54 and 0.65 m³/h). A seated student breathes less than the daily average, so the range is 0.3–0.6 m³/h. The range is our choice; the handbook's short-term "sedentary" rates should be read to tighten it.

**`latent_days`, `infectious_days`.** In volunteer challenge studies, viral shedding rose sharply 0.5–1 day after infection and lasted 4.80 days on average (95% CI 4.31–5.29) (Carrat et al., 2008). Those volunteers were healthy adults; the paper notes no such data exist for children, who may shed longer, so the upper bound is widened to 7 days. Shedding is used as a proxy for infectiousness, which is a simplification.

**`mask_efficiency`.** How much a mask cuts infectious aerosol, applied once at emission and once at inhalation. Leung et al. (2020) found that surgical masks reduced influenza virus RNA in respiratory droplets, but the effect on influenza in fine aerosols was not shown. Because this model is aerosol-based, the range starts at 0 and the base is modest (0.3). A filtration-efficiency source for the upper bound is still needed.

**`infectious_attendance`.** About two-thirds of influenza infections in challenge studies were symptomatic (Carrat et al., 2008). If every symptomatic student stayed home, about a third of infectious students would still attend; that sets the lower bound near 0.3. Real attendance of sick students in Philippine schools is unknown, so the base (0.5) is a team assumption.

**`community_beta`.** Transmission outside school (home, transport, community). Applied every day, including weekends and online days, so online classes never reach zero risk. No direct source; varied in sensitivity.

**`initial_infected_frac`.** Share of students already infectious at the start of the simulation. Team assumption.

**`class_size`.** The default is a team assumption; regional presets from `data/processed/presets.csv` replace it. National averages from DepEd data are 32 learners per classroom in elementary, 39 in junior high and 36 in senior high, but actual classes in many highly urbanized areas often exceed 50 ("DepEd Projects Up to 28M Enrollees," 2026). We did not find a DepEd standard for learners per classroom that we could read and cite, so none is used.

**`room_length`, `room_width`.** DepEd's school-building standards give a classroom of 7.00 × 9.00 m measured from wall centres (DepEd, 2017). This was read on secondary sites; confirm it in the DepEd copy.

**`room_height`.** DepEd's facilities manual gives a minimum ceiling height of 2.70 m for naturally ventilated rooms (DepEd, 2010). Also read on a secondary site.

**`session_hours`.** Hours inside the classroom per day. Shift schedules vary; the user sets this.

**`ach` and presets.** The Harvard Healthy Buildings Program recommends targeting a combined 4–6 air changes per hour (ACH) for classrooms (Harvard T.H. Chan School of Public Health Healthy Buildings Program, 2020). We set Good at 6 (the top of that target) and Typical at 4 (the bottom). Poor is 2, below the target. Philippine public classrooms are mostly naturally ventilated and we found no measurements, so whether "windows open" reaches 4 ACH is our assumption (`ach_typical`, low confidence).

**`sick_days_per_case`, `online_learning_weight`.** Inputs to the learner-days-lost metric only; they do not affect infections. Both are team assumptions and are varied in sensitivity.

**`near_field_multiplier`, `near_field_decay_m`.** Used only by the seat map (ticket #26). The model adds extra risk for students sitting close to an infected student: the risk from the well-mixed room is multiplied by 1 + multiplier × exp(−distance / decay distance). Both numbers are team heuristics with no empirical validation and no source. Setting the multiplier to 0 gives the plain well-mixed model, in which every other student has the same risk. They do not affect the Results, Compare or Sensitivity tabs.

**`attack_rate_threshold`, `robustness_threshold`.** Policy choices for the recommender. The user can change the attack-rate threshold in the app.

## Regional presets (`scripts/make_presets.py`, ticket #8)

Regional defaults for class size and school size are built from three raw tables (provenance in [`data/README.md`](../data/README.md)) and written to `data/processed/presets.csv`. They are starting values that the user can override in the sidebar.

**How they are computed.** The three tables are standardised to canonical region and level names and merged on (region, level):

- `learners_per_classroom` = enrollment ÷ classrooms
- `learners_per_school` = enrollment ÷ schools

Elementary, JHS and SHS are the levels used. Rows missing any of enrollment, schools or classrooms are logged and left out of the output, never silently dropped, and the app falls back to its defaults for those combinations. Values outside 15–100 learners per classroom are flagged in the log as a sanity check.

**Sources.**

| Table | Source | School year |
|---|---|---|
| Enrollment (public; Elementary, JHS, SHS) | DepEd Learner Information System, via TeacherPH (`psa_enrollment.csv`) | 2020-2021 |
| Schools (public) | PSA OpenSTAT Table 10.10 (DepEd data) | 2020-2021 |
| Classrooms (public) | DepEd National School Building Inventory, via TeacherPH | 2019-2020 |

**Region names.** Names have changed over time, so every source label is mapped to one canonical label. The canonical labels match those the app already uses (sidebar and placeholder presets). Old or alternative spellings are accepted as aliases.

| Canonical label | Also accepted |
|---|---|
| NCR | National Capital Region, Metro Manila |
| CAR | Cordillera Administrative Region, Cordillera |
| Ilocos Region | Region I, Region 1 |
| Cagayan Valley | Region II, Region 2 |
| Central Luzon | Region III, Region 3 |
| CALABARZON | Region IV-A, Region 4A |
| MIMAROPA | Region IV-B, Region 4B, MIMAROPA Region |
| Bicol Region | Region V, Region 5 |
| Western Visayas | Region VI, Region 6 |
| Central Visayas | Region VII, Region 7 |
| NIR | Negros Island Region |
| Eastern Visayas | Region VIII, Region 8 |
| Zamboanga Peninsula | Region IX, Region 9 |
| Northern Mindanao | Region X, Region 10 |
| Davao Region | Region XI, Region 11 |
| SOCCSKSARGEN | Region XII, Region 12 |
| CARAGA | Region XIII, Region 13 |
| BARMM | ARMM, Autonomous Region in Muslim Mindanao, Bangsamoro Autonomous Region in Muslim Mindanao |

ARMM is treated as BARMM (renamed in 2019). Source labels that match no entry, such as national totals, are dropped and logged. The mapping lives in `REGION_ALIASES` in `src/schoolsim/presets_build.py`, and a test checks that every region in the app's placeholder table is a canonical label. All 17 regions in the three raw files match an entry above. NIR does not appear in any source.

**Limitations specific to presets.**

- **Learners per classroom is not class size.** Where schools run shifts, the same classroom serves more than one group per day, so learners per classroom overstates the number of students in a room at once. Treat the preset as a starting point and override it in the sidebar.
- **Regional averages hide the spread.** A regional figure says nothing about the crowded or sparse schools within the region.
- **Incomplete combinations.** Any region and level that is missing from one of the three sources has no preset, and the app uses the default class size for it.
- **Secondary source, hand-copied.** Enrollment and classroom counts were copied from TeacherPH's republication of DepEd statistics, not from the DepEd files, and five rows of each were spot-checked (see `data/README.md`).
- **Only 2019-2021 data.** The presets describe pre-2022 enrollment and buildings and do not reflect later changes.

## Calibrated R₀ mode

Physical mode (the default) takes the quanta rate as given and computes transmission from room properties. Calibrated R₀ mode inverts that: the user names a target R₀ for the baseline school, and the model solves for the quanta rate that reproduces it.

**Calibration is a modelling convenience, not a measurement.** It converts a literature-reported R₀ into a quanta rate that is self-consistent with the rest of the model's parameters. It does not make that quanta rate a better estimate of reality than the physical-mode default; it anchors the simulation to a quantity (R₀) with stronger empirical support than the quanta rate alone — particularly for influenza, where published quanta estimates span three orders of magnitude (see above).

Calibration solves:

    q* = (R0 · γ − β_comm) · (7 / school_days) · Q / (n · a · p · t · mf)

where γ = 1 / infectious_days, β_comm = community_beta, Q = airflow, n = class_size, a = infectious_attendance, p = breathing_rate, t = session_hours, mf = mask_factor. This is the unique q such that the baseline (face-to-face, 5 school days/week) reproduces the target R₀. Calibration succeeds only when target R₀ strictly exceeds the community-only R₀ = community_beta / γ; below that, classroom transmission cannot reduce total R₀ further and the mode reports an error.

After calibration, the quanta rate is fixed: ventilation, masks, class size and modality still change transmission from the calibrated baseline. Doubling ACH halves classroom β; doubling class size doubles it. This is what makes calibrated mode usable for scenario comparison — the R₀ anchor sets the scale, and physical interventions still move it.

### Disease presets

Presets set R₀, latent days and infectious days for a named disease. Values come from primary literature; derivations and confidence labels are in [`references.yaml`](../references.yaml) and summarised below.

| Preset | R₀ (range) | Latent days (range) | Infectious days (range) | Confidence |
|---|---|---|---|---|
| Influenza | 1.3 (1.1–1.6) | 1.0 (0.5–2.0) | 4.0 (3.0–6.0) | medium |
| COVID-19 (ancestral) | 2.9 (2.0–3.5) | 5.5 (3.5–6.0) | 8.0 (5.0–10.0) | medium |
| Measles | 15.0 (12.0–18.0) | 9.0 (7.0–11.0) | 8.0 (7.0–9.0) | high (infectious); medium (latent, R₀) |

**Latent period definition and derivations.** `latent_days` is 1/σ — exposure to onset of infectiousness. Some sources report the *incubation period* (exposure → symptom onset), which is systematically longer; where a preset value is derived rather than directly estimated, the derivation is stated.

- **Influenza (1.0 d).** Derived from Lessler et al.'s median incubation 1.4 d and Carrat et al.'s observation that viral shedding, and hence infectiousness, begins 0.5–1 d after challenge, before symptom onset. Range 0.5–2.0 covers the incubation CI and challenge-study timing.
- **COVID-19 ancestral (5.5 d).** Directly estimated by Xin et al. (2022) from exposure-traced cases; shorter than the corresponding incubation estimate of 6.9 d in the same data. **The preset is strain-specific:** Omicron latent is much shorter (~3.1 d), and Omicron R₀ is substantially higher. The preset pairs ancestral-strain R₀ with ancestral-strain latent so that the calibrated-quanta solution is internally consistent.
- **Measles (9.0 d).** **Derived.** CDC guidance places rash ~14 d after exposure and infectiousness 4 d before rash onset, giving a latent period of ≈9 d; range 7–11 covers variation in prodrome-to-rash timing. The commonly quoted 10–14 d figure is *incubation*, not latent, and must not be entered as `latent_days`.

**R₀ is setting-dependent.** The calibrated-R₀ mode assumes a fully susceptible classroom; population R₀ estimates (seasonal influenza, early-outbreak COVID-19, pre-vaccine-era measles) are population-level anchors, not classroom-specific. This is the correct interpretation of R₀ for the calibrated-quanta solve; the simulator presents *relative* scenario comparisons, not classroom-specific forecasts. For measles, Guerra et al. (2017) note that rigorous estimates vary more than the classic 12–18 range; the preset retains 12–18 as the operational range and should be treated as convention, not a measured constant.

**Omicron is not included.** The current source set supports an Omicron R₀ (pooled effective R 4.20, 95% CI 2.05–6.35) and Omicron latent period (~3.1 d for BA.1.1), but not an Omicron-specific infectious period. Borrowing the ancestral 8-day value would understate γ, and therefore understate the calibrated quanta rate and the resulting infection probability — an optimism we do not want in a decision-support tool. An Omicron preset would be added once an Omicron-specific infectious-period estimate is available.

In calibrated mode, the sensitivity analysis varies R₀ across the preset's range (via the calibrated quanta rate) rather than varying quanta directly. This is the reason calibrated mode is the safer default for scenario comparison: the R₀ uncertainty is what enters sensitivity, not the quanta uncertainty.

## Where sources disagree

**Influenza quanta span more than three orders of magnitude.**
- Rudnick and Milton (2003): about 15–128 quanta/h (airliner outbreak), within a published range of about 15–500 quanta/h (Azimi & Stephens, 2013).
- Bueno de Mesquita et al. (2020): 0.11 quanta/h (95% CI 0.088–0.12) from a controlled human challenge trial.

Outbreak-based estimates come from events where transmission happened, so they skew high. The challenge-trial estimate comes from volunteers in a controlled room, and the authors note that a minority of "supershedders" may pose great risk even in well-ventilated spaces, so a single low figure understates the tail. We use the outbreak-based range (5–128) because the tool models a school outbreak, and we exclude 0.11 and 500 as extremes. **Calibrated R₀ mode (#23) is the safer default for comparing scenarios, because it does not depend on picking one quanta value.**

**Masks and influenza aerosols.** Leung et al. (2020) showed an effect for influenza droplets but not for influenza aerosols, so mask benefits in this model may be overstated at the upper bound of `mask_efficiency`.

**Floor area per pupil.** Secondary sites quote different standards (about 1.0 m² per person in the building code's rules; a 7 × 8 m room for 56 pupils in an older chapter of DepEd's manual). We do not use a per-pupil standard.

## Low-confidence parameters

These values have weak or no direct evidence. Each is varied in the sensitivity analysis where it affects outcomes, and the recommendation reports how often it holds across them.

- `quanta_rate`: sources disagree by more than three orders of magnitude.
- `breathing_rate`: daily-average source; seated rate not yet confirmed.
- `mask_efficiency`: no influenza aerosol reduction shown in the main source.
- `infectious_attendance`: no Philippine data on sick students attending.
- `community_beta`: team assumption.
- `initial_infected_frac`: team assumption.
- `session_hours`: team assumption; user-editable.
- `ach_typical`: no measured ACH for Philippine classrooms.
- `sick_days_per_case`: team assumption.
- `online_learning_weight`: team assumption.
- `near_field_multiplier`: heuristic with no empirical validation; seat map only.
- `near_field_decay_m`: heuristic with no empirical validation; seat map only.

## Scenarios

Each scenario in `src/schoolsim/scenarios.py` applies one or more overrides to the baseline `SchoolProfile`. Every scenario shares identical non-scenario parameters, so results are directly comparable.

- **`baseline`** — current practice, no interventions.
- **`better_ventilation`** — `ach` raised to `ach_good` (6/h, Harvard "ideal" tier).
- **`smaller_classes`** — `class_size × 0.67`. **Limitation:** this assumes the school can create extra sections. If not, the scenario shows a potential benefit that isn't attainable.
- **`masks`** — `mask_compliance` raised to 0.8. Effectiveness depends on `mask_efficiency`, which is itself low-confidence (see parameter table).
- **`combined`** — better ventilation + masks. Effects multiply through `β_class`.
- **`hybrid`** — A/B cohorts: half the class in the room on any given day, each student attends half the days. Modelled as `class_size × 0.5` **and** SEIR `attendance = 0.5`, which compound to a 4× reduction in per-susceptible transmission vs baseline. The two halves are distinct: `class_size_mult` shrinks the room population, `attendance` shrinks the days each student is exposed.
- **`online`** — `attendance = 0`. Classroom transmission is zero; `community_beta` still applies every day, so online classes never reach zero risk.

## Limitations

- **Relative, not absolute.** Use results to compare options for the same school, not to predict case counts.
- **No Philippine classroom-level outbreak data.** Epidemiological values come from non-Philippine studies, mostly of adults.
- **Well-mixed air.** Wells-Riley assumes air in the room is evenly mixed and in steady state (Wells, 1955; Riley et al., 1978). Near-desk exposure is handled only by the separate, heuristic seat map (#26).
- **Homogeneous mixing across the school.** SEIR treats all students as one population (Keeling & Rohani, 2008); it ignores grade levels, friend groups and households.
- **Shedding as infectiousness.** Infectious period is approximated by viral shedding duration.
- **Learners per classroom is not class size** where schools run shifts; presets are a starting point that users can override.
- **Presets mix school years and definitions.** Enrollment, schools and classroom counts come from different school years, and "public" is defined slightly differently across the PSA tables (see "Regional presets").
- **Regional averages only.** Presets are region-by-level averages. No per-school data is used.
- **One disease at a time.** The default is influenza; other diseases rely on calibrated R₀ mode.

## Changes from the ticket's starting values

| Key | Ticket | Now | Reason |
|---|---|---|---|
| `quanta_rate` range | 5–100 | 5–128, log-uniform | Matches the Rudnick and Milton upper estimate; values span orders of magnitude |
| `latent_days` | 1.5 (1–2) | 1.0 (0.5–2) | Shedding rises 0.5–1 day after infection (Carrat et al., 2008) |
| `infectious_days` | 4 (3–6) | 4.8 (3.5–7) | Mean shedding 4.80 days; widened for children |
| `mask_efficiency` | 0.4 (0.2–0.6) | 0.3 (0–0.6) | Influenza aerosol reduction not shown (Leung et al., 2020) |
| ACH presets | 1 / 3 / 6 | 2 / 4 / 6 | Anchored to the Harvard 4–6 ACH target |
| `room_height` | 3.0 | 2.7 | DepEd minimum for naturally ventilated rooms |
| `breathing_rate` source | an unverified paper on SARS-CoV-2 quanta | U.S. EPA (2011) | Verified source for children's inhalation rates |
| `class_size` source | DepEd (2010) | team assumption | No readable DepEd learners-per-classroom standard found |
| new | – | `class_size`, `ach` | Needed as validated UI inputs |
| `sim_days` range | 60 (fixed) | 30–60, user-editable | Ticket #10 puts simulation days in the Advanced settings |

## Verification status

Every reference carries a `status`, the date it was checked, and where, in `references.yaml`. Statuses on 2026-10-21:

- **verified:** Wells (1955), Riley et al. (1978), Rudnick & Milton (2003), Azimi & Stephens (2013), Azimi et al. (2020), Bueno de Mesquita et al. (2020), Carrat et al. (2008), Leung et al. (2020), Keeling & Rohani (2008), McKay et al. (1979), Virtanen et al. (2020), McKinney (2010), U.S. EPA (2011), Harvard Healthy Buildings Program (2020), PSA (2024), and the news and policy sources used in the proposal background.
- **partial:** DepEd (2017) and DepEd (2010) (specific values read on secondary sites; confirm in the DepEd copy). Regional enrollment and classroom counts come from TeacherPH's republication of DepEd statistics (see "Regional presets"), not from a primary DepEd file.
- **partial (waiting for C2 and PM to confirm) (preset references, 2026-10-22):** Biggerstaff et al. (2014), Lessler et al. (2009), Carrat et al. (2008), Park et al. (2020), Alimohamadi et al. (2020), Xin et al. (2022), van Kampen et al. (2021), Guerra et al. (2017), CDC (2025).
