# ClassPass: Classroom Outbreak Simulator

**Compare how ventilation, masks, class size, and class format change an airborne outbreak.**

[![CI](https://github.com/labillescharlene21-lab/classPass/actions/workflows/ci.yml/badge.svg)](https://github.com/labillescharlene21-lab/classPass/actions/workflows/ci.yml)

* **Live Demo:** Currently runs locally. See the Quickstart below.
*   **Demo Video:** [Link to be added Oct 24]

## Problem
School administrators currently have to choose between in-person, hybrid, or online classes without clear, data-driven tools to evaluate the risk of airborne disease transmission. Decisions are often made based on intuition rather than modeling. ClassPass solves this by providing a simulation tool that couples an environmental Wells-Riley model with an epidemiological SEIR model. This allows decision-makers to compare the relative impacts of interventions like improved ventilation, mask mandates, and smaller class sizes.

## Screenshot
![alt text](image.png)

## How It Works
The simulation follows a two-step pipeline: 

mermaid
graph TD
    A[Input: params.yaml & Sidebar] --> B(Wells-Riley Model)
    B --> C{Calculate Transmission Rate β}
    C --> D(SEIR Model)
    D --> E[RK4 ODE Solver]
    E --> F[Results & Sensitivity Dashboard]
Regional enrollment and school figures: Philippine Statistics Authority, OpenSTAT (source agency: Department of Education), https://openstat.psa.gov.ph, licensed under CC BY 4.0 (terms: https://openstat.psa.gov.ph/Terms). Accessed [date]. We filtered, merged and divided the figures to compute learners per classroom by region and level. Changes were made by the project team. This project is not endorsed by the PSA or DepEd.

## LMS integration roadmap

The Teacher log tab keeps a roster and sick log in the browser session only, sets the initial infected share (i0) and index-case seats for the simulation, and exports a **generic CSV**. It does not connect to any learning platform.

| Item | Status |
|---|---|
| Roster CSV import (`student_id`, optional `seat, status, onset_date, return_date, reason_code`) | Implemented (`CSVAdapter`) |
| Generic attendance CSV export (`student_id, date, present, reason_code`; `present` is 1 or 0) | Implemented (`CSVAdapter`) |
| Moodle adapter | **Not implemented.** Stub raises `NotImplementedError` |
| Google Classroom adapter | **Not implemented.** Stub raises `NotImplementedError` |
| Any live login, API call, or sync with an LMS | **Not implemented** |

**Compatibility.** Moodle and Google Classroom have no universal attendance CSV. The export is not tested against, and makes no claim to work with, either platform's import. Check the target format before using it.

**Moodle (planned).** Moodle attendance is not part of core. It comes from the Attendance plugin, which publishes web service functions on sites that run a recent version. Function names depend on the site and are listed under Site administration > Plugins > Web services > API documentation. Roster and attendance would be separate calls. See the [Moodle Web services docs](https://docs.moodle.org/en/Web_services) and this [community thread on the Attendance API](https://moodle.org/mod/forum/discuss.php?d=428987).

**Google Classroom (planned, roster only).** The [Classroom API](https://developers.google.com/workspace/classroom/guides/import-rosters) can list a course's students (`courses.students.list`, scope `classroom.rosters.readonly`). The documentation we reviewed does not mention attendance, so we know of no way to write attendance back. Reading student emails needs a sensitive scope that requires Google verification.

**Privacy blocker.** Real integrations return student names and emails. The prototype accepts synthetic IDs only, so a real integration needs a Data Privacy Act (RA 10173) review first. See [docs/privacy_and_responsible_use.md](docs/privacy_and_responsible_use.md).
