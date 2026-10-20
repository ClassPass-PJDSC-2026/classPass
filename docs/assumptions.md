

# Model assumptions

Every number the simulator uses lives in [`params.yaml`](../params.yaml). This page explains where each value comes from, how sure we are, and where sources disagree. Full citations are in [`references.yaml`](../references.yaml).

Results are **relative scenario comparisons, not forecasts**. A wide range is not a weakness: the sensitivity analysis varies every uncertain input across its range and reports whether the recommendation still holds.

**Default disease:** seasonal influenza. Other diseases are handled by calibrated R₀ mode (ticket #25).

## Parameter table

| Key | Base | Range | Unit | Source | Confidence |
|---|---|---|---|---|---|
| `quanta_rate` | 15 | 5–128 (log-uniform) | quanta/h | Rudnick & Milton (2003); CDPH appendix; size-dependent W-R review | low |
| `breathing_rate` | 0.5 | 0.3–0.6 | m³/h | Buonanno et al. (2020) *(unverified)* | low |
| `latent_days` | 1.0 | 0.5–2.0 | days | Carrat et al. (2008) | medium |
| `infectious_days` | 4.8 | 3.5–7.0 | days | Carrat et al. (2008) | medium |
| `mask_efficiency` | 0.3 | 0.0–0.6 | fraction | Leung et al. (2020) | low |
| `infectious_attendance` | 0.5 | 0.3–0.8 | fraction | Carrat et al. (2008); team assumption | low |
| `community_beta` | 0.1 | 0.05–0.2 | 1/day | team assumption | low |
| `initial_infected_frac` | 0.01 | 0.005–0.02 | fraction | team assumption | low |
| `class_size` | 45 | 5–80 | students | DepEd (2010) | medium |
| `room_length` | 9.0 | 3–30 | m | DepEd Order No. 64, s. 2017 | medium |
| `room_width` | 7.0 | 3–30 | m | DepEd Order No. 64, s. 2017 | medium |
| `room_height` | 2.7 | 2.4–4.0 | m | DepEd (2010) | medium |
| `session_hours` | 6 | 4–8 | h | team assumption | low |
| `mask_compliance` | 0 | 0–1 | fraction | user input | high |
| `ach` | 4 | 0.5–20 | 1/h | Harvard HBP (2020) | medium |
| `ach_poor` | 2 | fixed | 1/h | Harvard HBP (2020); team assumption | medium |
| `ach_typical` | 4 | fixed | 1/h | Harvard HBP (2020); team assumption | low |
| `ach_good` | 6 | fixed | 1/h | Harvard HBP (2020) | medium |
| `school_days_per_week` | 5 | fixed | days | team assumption | high |
| `sim_days` | 60 | fixed | days | team decision | high |
| `sick_days_per_case` | 3 | 2–5 | days | team assumption | low |
| `online_learning_weight` | 0.3 | 0.1–0.5 | fraction | team assumption | low |
| `attack_rate_threshold` | 0.10 | 0.02–0.40 | fraction | team decision | high |
| `robustness_threshold` | 0.80 | 0.50–0.95 | fraction | team decision | high |

"High" confidence on user inputs and team decisions means the value is a choice, not an estimate.

## Why each value

**`quanta_rate`.** Quanta are the infectious "doses" a sick person emits per hour; this is the most uncertain input in the model. Rudnick & Milton (2003) estimated about 15–128 quanta/h for influenza from an airliner outbreak, depending on steady-state or dynamic assumptions. We use the lower end (15) as the base and the full span as the range. Sampling is log-uniform because the plausible values cover more than an order of magnitude.

**`breathing_rate`.** Typical inhalation for a seated or lightly active student. To be confirmed against Buonanno et al. (2020) or another exposure-factors source before submission.

**`latent_days`, `infectious_days`.** In volunteer challenge studies, viral shedding rose sharply 0.5–1 day after infection and lasted 4.80 days on average (95% CI 4.31–5.29) (Carrat et al., 2008). Those volunteers were healthy adults; the paper notes no such data exist for children, who may shed longer, so the upper bound is widened to 7 days. Shedding is used as a proxy for infectiousness, which is a simplification.

**`mask_efficiency`.** How much a mask cuts infectious aerosol, applied once at emission and once at inhalation. Leung et al. (2020) found surgical masks reduced influenza RNA in respiratory droplets but not significantly in fine aerosols. Because this model is aerosol-based, the range starts at 0 and the base is modest (0.3). A filtration-efficiency source for the upper bound is still needed.

**`infectious_attendance`.** About two-thirds of influenza infections in challenge studies were symptomatic (Carrat et al., 2008). If every symptomatic student stayed home, about a third of infectious students would still attend; that sets the lower bound near 0.3. Real attendance of sick students in Philippine schools is unknown, so the base (0.5) is a team assumption.

**`community_beta`.** Transmission outside school (home, transport, community). Applied every day, including weekends and online days, so online classes never reach zero risk. No direct source; varied in sensitivity.

**`initial_infected_frac`.** Share of students already infectious at the start of the simulation. Team assumption.

**`class_size`, `room_*`.** DepEd specifies 7.00 × 9.00 m classrooms measured from wall centres (DepEd Order No. 64, s. 2017) and a 2.70 m ceiling for naturally ventilated rooms (DepEd, 2010). The 1.40 m² per place standard caps a 63 m² room at 45 students. Regional presets from `data/processed/presets.csv` replace the class-size default once ticket #8 is done.

**`session_hours`.** Hours inside the classroom per day. Shift schedules vary; the user sets this.

**`ach` and presets.** Harvard's Healthy Buildings Program grades classroom air changes as low (<3), bare minimum (3–4), good (4–5), excellent (5–6) and ideal (6+), with a target of at least 5. Philippine public classrooms are mostly naturally ventilated and we found no measurements, so which tier "windows open" falls in is our assumption (`ach_typical`, low confidence).

**`sick_days_per_case`, `online_learning_weight`.** Inputs to the learner-days-lost metric only; they do not affect infections. Both are team assumptions and are varied in sensitivity.

**`attack_rate_threshold`, `robustness_threshold`.** Policy choices for the recommender. The user can change the attack-rate threshold in the app.

## Where sources disagree

**Influenza quanta span more than three orders of magnitude.**
- Rudnick & Milton (2003): about 15–128 quanta/h (airliner outbreak).
- CDPH compilation: values including 15–50, 79, 128 and 515 quanta/h from different studies.
- Bueno de Mesquita et al. (2020): 0.11 quanta/h (95% CI 0.088–0.12) from a controlled human challenge trial.

Outbreak-based estimates come from events where transmission happened, so they skew high. The challenge-trial estimate comes from mildly ill volunteers in a controlled room, so it may skew low. We use the outbreak-based range (5–128) because the tool models a school outbreak, and we exclude 0.11 and 515 as extremes. **Calibrated R₀ mode (#25) is the safer default for comparing scenarios, because it does not depend on picking one quanta value.**

**Masks and influenza aerosols.** Leung et al. (2020) showed a clear effect for droplets but not for influenza aerosols, so mask benefits in this model may be overstated at the upper bound of `mask_efficiency`.

## Low-confidence parameters

These values have weak or no direct evidence. Each is varied in the sensitivity analysis where it affects outcomes, and the recommendation reports how often it holds across them.

- `quanta_rate`: sources disagree by more than three orders of magnitude.
- `breathing_rate`: source not yet verified.
- `mask_efficiency`: no significant influenza aerosol reduction found in the main source.
- `infectious_attendance`: no Philippine data on sick students attending.
- `community_beta`: team assumption.
- `initial_infected_frac`: team assumption.
- `session_hours`: team assumption; user-editable.
- `ach_typical`: no measured ACH for Philippine classrooms.
- `sick_days_per_case`: team assumption.
- `online_learning_weight`: team assumption.

## Limitations

- **Relative, not absolute.** Use results to compare options for the same school, not to predict case counts.
- **No Philippine classroom-level outbreak data.** Epidemiological values come from non-Philippine studies, mostly of adults.
- **Well-mixed air.** Wells-Riley assumes air in the room is evenly mixed and in steady state. Near-desk exposure is handled only by the separate, heuristic seat map (#26).
- **Homogeneous mixing across the school.** SEIR treats all students as one population; it ignores grade levels, friend groups and households.
- **Shedding as infectiousness.** Infectious period is approximated by viral shedding duration.
- **Learners per classroom is not class size** where schools run shifts; presets are a starting point that users can override.
- **One disease at a time.** The default is influenza; other diseases rely on calibrated R₀ mode.

## Changes from the ticket's starting values

| Key | Ticket | Now | Reason |
|---|---|---|---|
| `quanta_rate` range | 5–100 | 5–128, log-uniform | Matches Rudnick & Milton's upper estimate; values span orders of magnitude |
| `latent_days` | 1.5 (1–2) | 1.0 (0.5–2) | Shedding rises 0.5–1 day after infection (Carrat et al., 2008) |
| `infectious_days` | 4 (3–6) | 4.8 (3.5–7) | Mean shedding 4.80 days; widened for children |
| `mask_efficiency` | 0.4 (0.2–0.6) | 0.3 (0–0.6) | No significant aerosol reduction for influenza (Leung et al., 2020) |
| ACH presets | 1 / 3 / 6 | 2 / 4 / 6 | Mapped to Harvard HBP tiers |
| `room_height` | 3.0 | 2.7 | DepEd minimum for naturally ventilated rooms |
| new | – | `class_size`, `ach` | Needed as validated UI inputs |

## Verification status

See `status` and `notes` in `references.yaml`. Before submission, every reference must be `verified`:

- **verified:** Rudnick & Milton (2003), Bueno de Mesquita et al. (2020), Carrat et al. (2008)
- **partial:** CDPH appendix (year), size-dependent W-R review (authors, year, journal), Leung et al. (2020) (volume, pages), Harvard HBP (report title, date), DepEd Order No. 64 s. 2017 and DepEd (2010) (read via secondary sites; need DepEd copies)
- **unverified:** Buonanno et al. (2020)
