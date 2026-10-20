# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository. Read this before writing code.

## Project

**Classroom Outbreak Simulator** – Team Board Game, PJDSC 2026.
A Streamlit decision-support dashboard that simulates airborne disease spread in Philippine classrooms. It couples the **Wells-Riley** airborne infection equation with an **SEIR** model, compares interventions and class modalities, runs a sensitivity analysis, and gives a rule-based recommendation with a robustness score.

Outputs are **relative scenario comparisons, not forecasts**. Never write code, UI text, or docs that present results as predictions.

Deadline context: feature freeze **Oct 21, 23:59**; code freeze **Oct 23, 18:00**; submission **Oct 24**. After the feature freeze, only bug fixes, tests, docs and polish are allowed. Do not add features after the freeze.

## Setup and commands

```bash
make setup    # pip install -r requirements.txt && pip install -e .
make data     # python scripts/make_presets.py  → data/processed/presets.csv
make test     # pytest --cov=src/schoolsim --cov-report=term-missing
make lint     # ruff check .
make run      # streamlit run app/streamlit_app.py
```

Python 3.11. Dependencies are pinned with `==` in `requirements.txt`. Do not add a dependency without a reason in the PR description; pick versions at least two weeks old.

Before declaring any task done, run `make lint && make test` and confirm both pass.

## Repository layout

```
app/streamlit_app.py          # UI only: tabs Setup, Results, Compare, Sensitivity, Seat map, Assistant, Teacher log, Assumptions
src/schoolsim/
  params.py                   # loads params.yaml (value, min, max, unit, source)
  wells_riley.py              # room volume, airflow, infection probability, classroom beta
  seir.py                     # simulate (RK4, school-day schedule), simulate_batch (vectorised)
  scenarios.py                # SCENARIOS dict, run_scenario, run_all
  calibrate.py                # calibrated R0 mode: solve quanta for a target R0
  sensitivity.py              # one-at-a-time tornado, Latin hypercube Monte Carlo
  recommend.py                # rule-based recommender + robustness score
  metrics.py                  # attack rate, peak, learner-days lost
  spatial.py                  # seat grid, near-field risk map (heuristic)
  assistant.py                # AI assistant (Claude API) with template fallback
  templates.py                # parent advisory, memo, SMS, group-chat drafts (EN/Filipino)
  lms.py                      # LMSAdapter protocol, CSVAdapter; other adapters are stubs
scripts/make_presets.py       # raw PSA/DepEd CSVs → presets.csv
data/raw/  data/processed/  data/README.md
notebooks/validation.ipynb
tests/
params.yaml                   # single source of truth for every model parameter
docs/assumptions.md  docs/privacy_and_responsible_use.md
```

Keep the boundary strict: **all model logic lives in `src/schoolsim/` as pure functions; `app/` only reads inputs, calls the package, and renders.** No calculations in Streamlit callbacks beyond formatting.

## Model (do not change without a ticket)

```
V  = L · W · H                                   (m³)
Q  = ACH · V                                     (m³/h)
mf = (1 − mask_efficiency · mask_compliance)²    (emission × inhalation)
P  = 1 − exp(−I · q · p · t · mf / Q)            (Wells-Riley, per session)
β_class = n · a · q · p · t · mf / Q             (per school day; a = infectious_attendance)
λ(t) = (school_on(t) · attendance · β_class + β_comm) · I
dS = −λS,  dE = λS − σE,  dI = σE − γI,  dR = γI        (σ = 1/latent, γ = 1/infectious)
R0_eff = ((5/7) · attendance · β_class + β_comm) / γ
```

- Modalities: face-to-face `attendance=1`; hybrid `class_size×0.5`, `attendance=0.5`; online `attendance=0`.
- Integrator: fixed-step RK4, `dt = 0.05` day, β switches off on weekends. `solve_ivp` is used **only in tests** as a reference.
- Calibrated R₀ mode solves for `q` at the baseline profile; afterwards `q` is fixed so interventions still change transmission.
- `spatial.py` near-field terms (`kappa`, `lam`) are **team heuristics**. Any UI that shows them must label them as such.

## Coding rules

- **Units in every docstring.** Hours for Wells-Riley, days for SEIR, m³, m³/h, quanta/h, probabilities 0–1.
- **No magic numbers.** Every parameter value, default and range comes from `params.yaml` via `params.py`. UI defaults read from it too.
- **New parameter?** Add it to `params.yaml` with `value, min, max, unit, source, confidence`, and add a row to `docs/assumptions.md`. If there is no source, set `source: team assumption`.
- **Determinism.** Any randomness takes a `seed` argument (default `42`). Same inputs must give identical outputs.
- **Vectorisable.** Engine functions must accept numpy arrays so `simulate_batch` and sensitivity runs stay fast.
- **Validation.** Raise `ValueError` with a human-readable message for invalid inputs (e.g. `Q == 0`). The UI catches these and shows `st.error`; it must never crash.
- Type hints on public functions; frozen dataclasses for results (`SimResult`, `Recommendation`).
- Cache expensive calls in the app with `st.cache_data`, keyed on hashable inputs.
- Style: ruff defaults, line length from `pyproject.toml`. Don't reformat unrelated files.

## Testing requirements

Every engine change needs tests. Existing invariants that must keep passing:

- S + E + I + R = 1 within 1e-6; no negative compartments
- More ACH, smaller class, or more masks → lower attack rate (parametrised tests)
- Online → classroom β = 0
- RK4 matches `solve_ivp` within 1% attack rate (no weekend switching)
- Final-size relation z = 1 − exp(−R0·z) within 1% for R0 ∈ {1.5, 2, 3}
- Calibrated mode reproduces the target R₀ within 0.1%
- `spatial.risk_map` with `kappa = 0` gives equal risk for all students
- Assistant payload builder never contains student names or IDs

Coverage target on `src/schoolsim/`: 90%. Tests must run in under 30 s.

## Performance budgets

- `simulate` (60 days): < 50 ms
- Latin hypercube sensitivity (n ≈ 200–300, all scenarios): < 10 s on Streamlit Cloud
- Seat map update (n = 80): < 200 ms
If a change breaks a budget, reduce sample size and document it rather than shipping a slow app.

## AI assistant rules (`assistant.py`)

- API key only from `st.secrets["ANTHROPIC_API_KEY"]`. Never hardcode, log, or commit keys. `.streamlit/secrets.toml` stays in `.gitignore`.
- Model name from config (`ANTHROPIC_MODEL`); check the current model string in the Claude docs.
- Ground every call in a JSON summary of the current run. The assistant discusses only those results.
- System prompt must forbid medical advice, diagnosis, and identifying individual students, and must state results are simulations.
- Per-session message cap and `max_tokens` cap.
- **Always** fall back to `templates.py` when there is no key, an API error, or the cap is hit. The demo must work with no network access to the API.

## Privacy and data rules

Student health information is sensitive personal information under the Philippine Data Privacy Act of 2012 (RA 10173).

- Use **synthetic data only**. Never add real student records, names, or photos to the repo, tests, fixtures, or screenshots.
- Teacher log data lives in `st.session_state` only. No writing to disk, databases, or URLs.
- Only aggregated numbers may be sent to the AI API. Never send roster names or IDs.
- Raw data in `data/raw/` must have provenance in `data/README.md`: source, URL, access date, school year, filters.

## Scope guardrails

In scope: everything in tickets #1–#29. Out of scope (do not build): user accounts, saving or persistence, PDF export, real LMS API integration (Moodle/Google Classroom adapters stay as documented stubs), per-school DepEd lookup, auto-sending messages.

If a feature is at risk, ship its documented fallback (see "Scope tiers" in the issues file) instead of a half-working version.

## Git workflow

- Branches: `feat/<issue>-short-name`, `fix/<issue>-…`, `docs/<issue>-…`. Never commit to `main`.
- PR title `#<issue> <summary>`, body includes `Closes #N`, what changed, how it was tested, screenshots for UI.
- One approval from any team member; CI must be green. Squash merge.
- Keep PRs small. Do not mix refactors with features.
- After the v1.0 tag (Oct 23, 18:00) only `fix/` branches merge.

## Writing and UI text

- Say "scenario simulation" or "estimate", never "prediction" or "forecast".
- Show units on every input, metric, and axis.
- Tooltips cite the parameter's source key from `params.yaml`.
- The recommender is "automated, explainable, rule-based". Do not call it AI. The AI label belongs only to the assistant tab.
- Footer on every page: scenario simulation for decision support, not a medical forecast.

## When unsure

Check the relevant ticket in the issues file and `docs/assumptions.md` first. If the ticket doesn't answer it, leave a `TODO(#issue):` comment with the open question and raise it in the PR instead of guessing. Do not change equations, parameter values, or scope on your own.
