# Proposal text (ticket #19)

Paste-ready text for the PJDSC 2026 proposal, written 2026-10-21. Citations are APA 7th. Every citation here resolves to an entry in `references.yaml`, which `tests/test_citations.py` checks. The reference list at the end is generated; edit `references.yaml` and run `python scripts/build_references.py` instead of editing it by hand.

Open items for the team are listed in section 6.

## 1. Background (replaces the sample Background; about 225 words)

Philippine public schools are crowded. DepEd's school year 2024–2025 data give 32 learners per classroom in elementary, 39 in junior high and 36 in senior high, yet in many highly urbanized areas actual classes often exceed 50 ("DepEd Projects Up to 28M Enrollees," 2026). Behind the averages is a classroom backlog: DepEd estimated about 144,000 classrooms, while the Second Congressional Commission on Education (EDCOM 2) reported more than 166,000 (Cariaso, 2026). Ageing school buildings are expected to remain a problem as well (Abrigo et al., 2025).

Crowded rooms matter for airborne disease because students share the same air. A Wells–Riley model of US schools found that combining better ventilation, filtration and air purification could cut infections among students by about half (Azimi et al., 2020), and DepEd names ventilation among its school-building design considerations (Department of Education, 2017).

The decision problem is real. In October 2025, DepEd National Capital Region suspended face-to-face classes in all Metro Manila public schools, giving rising influenza-like illness (ILI) among learners and staff as a primary reason. The Department of Health replied that cases were within the usual rainy-season rise and below the outbreak threshold, that influenza spreads very fast in poorly ventilated rooms, and that it wished it had been consulted (Philippine News Agency, 2025). Administrators need a way to compare their options before they decide.

*If the template leaves less room, drop the second paragraph and the first sentence of the third.*

## 2. Corrections to the existing proposal text

| Section | Current text | Replace with | Why |
|---|---|---|---|
| Executive summary | "deployed within 10 days" | "built and deployed within the competition's five-day window (October 20–24, 2026)" | The schedule is five days. |
| Executive summary | "Python engine couples a Susceptible-Exposed-Infectious-Recovered (SEIR) model with the Wells-Riley airborne infection equation" | Keep, and add the citations: "(Keeling & Rohani, 2008; Riley et al., 1978)" | Sources. |
| Problem | "School admins may be hesitant to take action as they are not sure what measures to take or what may happen in these type of occasions." | "School administrators may hesitate to act because they are unsure which measures to take or what would happen in these situations." | "admins" is informal; "these type of occasions" is ungrammatical. |
| Objectives, bullet 1 | "Develop and validate a Python-based mathematical engine within 4 days" | "Develop and validate a Python-based mathematical engine by October 21 that integrates SEIR disease spread and Wells–Riley airborne transmission, using literature-backed parameters." | The 4/8/10-day plan no longer matches the schedule. |
| Objectives, bullet 2 | "within 8 days … automated AI class modality recommendations" | "by October 22 … automated, explainable class-format recommendations" | The recommender is rule-based so administrators can see why. |
| Objectives, bullet 3 | "by Day 10 to ensure zero execution errors" | "by October 23 so the demonstrated workflow runs without execution errors" | "Zero errors" cannot be promised; the demonstrated workflow can. |
| Scope & Limitations | "…assumptions from the literature; as well, it should be noted that this tool will work only on a relative level" | "…assumptions from the literature. It should also be noted that the tool works only at a relative level and does not predict exact numbers." | Run-on sentence. |
| Methodology | "open data on from Philippine DepEd enrollment" | See the revised Methodology below. | Typo ("on from"). |
| Methodology | "number of students per class, size of classroom, floor plan, ventilation" | "students per class, room length, width and height, ventilation" | The floor-plan input was cut. |
| Methodology | "the programming languages Python and SciPy" | "the Python language and the SciPy library" | SciPy is a library, not a language. |
| Methodology | "Harvard Healthy Buildings Classroom Ventilation Guidelines" | "the Harvard Healthy Buildings Program's *Risk reduction strategies for reopening schools*" | Use the report's actual title. |
| Methodology | "Over the course of 10 development days" | "Over a five-day sprint" | Schedule. |
| References | "List your references here in APA 7th Edition format." | The generated list in section 5. | Placeholder text. |

## 3. Revised Methodology (replaces the three Methodology paragraphs)

The solution uses open data from the Philippine Statistics Authority's OpenSTAT, which publishes Department of Education enrollment and school counts (Philippine Statistics Authority, n.d., 2024), together with DepEd school-building standards (Department of Education, 2010, 2017) to set regional defaults for class size and room dimensions. The team uses Python and pandas (McKinney, 2010) to clean and merge the data. Users then describe their own classroom: students per class, room length, width and height, ventilation, hours in class and mask use. Epidemiological and ventilation parameters come from the literature, including the Harvard Healthy Buildings Program's guidance for schools (Harvard T.H. Chan School of Public Health Healthy Buildings Program, 2020) and work on the Wells–Riley model (Riley et al., 1978; Rudnick & Milton, 2003; Wells, 1955). Each parameter is stored with its range and source.

The Wells–Riley equation gives the risk of airborne infection inside a classroom, which sets the daily classroom transmission rate of a Susceptible-Exposed-Infectious-Recovered (SEIR) model (Keeling & Rohani, 2008) written in Python. Users compare a baseline with lower occupancy, better ventilation, mask use, and in-person, hybrid or online classes. A sensitivity analysis varies the uncertain parameters with Latin hypercube sampling (McKay et al., 1979), implemented with the SciPy library (Virtanen et al., 2020), to show whether the recommendation holds across plausible values.

Over a five-day sprint (October 20–24, 2026), the dashboard is built with Streamlit and Plotly to show transmission curves, scenario comparisons, risk estimates, recommendations and the model's assumptions. Testing covers mathematical accuracy, expected model behavior, sensitivity analysis and reproducibility. Because public data on Philippine classrooms and outbreaks are limited, assumed values fill the gaps and the results are scenario simulations only.

## 4. Scope update (add to Scope & Limitations once the October 21 go/no-go is done)

In addition to the dashboard, the prototype includes some or all of the following, depending on what ships: a calibration mode that sets the disease's effective reproduction number, a seat map that compares relative risk by seat for an infected student, an AI assistant that explains results and drafts notices for a person to review, and a teacher sick log with a generic CSV export. These features use synthetic data only and collect no real student records. *Delete any feature that is cut.*

## 5. References (APA 7th)

Alphabetical, with a hanging indent in the final document. Open `docs/references_apa7.html` in a browser, select all, and paste to keep the italics and the indent.

<!-- REFERENCES:START (generated by scripts/build_references.py; edit references.yaml instead) -->

Abrigo, M. R. M., Perez, T. D. S., Quejada, N. A. M., Daga, E. D. J. C., Estopace, K. M., Lingatong, E. E., Relos, C. M. L., Paquibot, J. L., & Gavan, D. S. A. (2025). *Low fertility, ageing buildings, and school congestion in the Philippines: Tailwinds, headwinds, and some policy options* (PIDS Discussion Paper No. 2025-10). Philippine Institute for Development Studies. https://doi.org/10.62986/dp2025.10

Azimi, P., Keshavarz, Z., Cedeno Laurent, J. G., & Allen, J. G. (2020). Estimating the nationwide transmission risk of measles in US schools and impacts of vaccination and supplemental infection control strategies. *BMC Infectious Diseases, 20*, Article 497. https://doi.org/10.1186/s12879-020-05200-6

Azimi, P., & Stephens, B. (2013). HVAC filtration for controlling infectious airborne disease transmission in indoor environments: Predicting risk reductions and operational costs. *Building and Environment, 70*, 150–160. https://doi.org/10.1016/j.buildenv.2013.08.025

Bueno de Mesquita, P. J., Noakes, C. J., & Milton, D. K. (2020). Quantitative aerobiologic analysis of an influenza human challenge-transmission trial. *Indoor Air, 30*(6), 1189–1198. https://doi.org/10.1111/ina.12701

Cariaso, B. (2026, July 25). DepEd still faces backlog of 166,000 classrooms. *The Philippine Star*. https://www.philstar.com/headlines/2026/07/25/2544543/deped-still-faces-backlog-166000-classrooms

Carrat, F., Vergu, E., Ferguson, N. M., Lemaitre, M., Cauchemez, S., Leach, S., & Valleron, A.-J. (2008). Time lines of infection and disease in human influenza: A review of volunteer challenge studies. *American Journal of Epidemiology, 167*(7), 775–785. https://doi.org/10.1093/aje/kwm375

Data Privacy Act of 2012, Republic Act No. 10173 (2012) (Phil.). https://privacy.gov.ph/wp-content/uploads/2017/03/DPA-of-2012.pdf

Department of Education. (2010). *Educational facilities manual (Revised edition of the 2007 Handbook on educational facilities)*. https://rtei.okfn.org/documents/Educational_Facilities_Manual._Rev_ed_of_the_2007_Handbook_on_Educational_Facilities.pdf

Department of Education. (2017). *Establishing the minimum performance standards and specifications for DepEd school buildings* (DepEd Order No. 64, s. 2017). https://deped.gov.ph/?p=1768

DepEd projects up to 28M enrollees. (2026, May 31). *Daily Tribune*. https://tribune.net.ph/2026/05/31/deped-projects-up-to-28m-enrollees

Harvard T.H. Chan School of Public Health Healthy Buildings Program. (2020). *Risk reduction strategies for reopening schools* [Report]. https://healthybuildings.hsph.harvard.edu/research/schools/risk-reduction-strategies-for-reopening-schools/healthy-buildings

Keeling, M. J., & Rohani, P. (2008). *Modeling infectious diseases in humans and animals*. Princeton University Press.

Leung, N. H. L., Chu, D. K. W., Shiu, E. Y. C., Chan, K.-H., McDevitt, J. J., Hau, B. J. P., Yen, H.-L., Li, Y., Ip, D. K. M., Peiris, J. S. M., Seto, W.-H., Leung, G. M., Milton, D. K., & Cowling, B. J. (2020). Respiratory virus shedding in exhaled breath and efficacy of face masks. *Nature Medicine, 26*(5), 676–680. https://doi.org/10.1038/s41591-020-0843-2

McKay, M. D., Beckman, R. J., & Conover, W. J. (1979). A comparison of three methods for selecting values of input variables in the analysis of output from a computer code. *Technometrics, 21*(2), 239–245.

McKinney, W. (2010). Data structures for statistical computing in Python. In S. van der Walt & J. Millman (Eds.), *Proceedings of the 9th Python in Science Conference* (pp. 56–61). https://doi.org/10.25080/Majora-92bf1922-00a

Philippine News Agency. (2025, October 15). DOH: No outbreak of influenza-like illnesses. *SunStar*. https://www.sunstar.com.ph/manila/doh-no-outbreak-of-influenza-like-illnesses

Philippine Statistics Authority. (2024). *Number of public and private schools by region and level of education: SY 2019-2020 to 2022-2023* [Data set]. OpenSTAT. https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/DB__3E__CH__EL/0051C8ESCH0.px

Philippine Statistics Authority. (n.d.). *Enrollment in public and private schools by level of education* [Data set]. OpenSTAT. Retrieved [date of download], from https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/DB__1C/1001C8EEPS0.px

Riley, E. C., Murphy, G., & Riley, R. L. (1978). Airborne spread of measles in a suburban elementary school. *American Journal of Epidemiology, 107*(5), 421–432. https://doi.org/10.1093/oxfordjournals.aje.a112560

Rudnick, S. N., & Milton, D. K. (2003). Risk of indoor airborne infection transmission estimated from carbon dioxide concentration. *Indoor Air, 13*(3), 237–245. https://doi.org/10.1034/j.1600-0668.2003.00189.x

U.S. Environmental Protection Agency. (2011). Chapter 6: Inhalation rates. In *Exposure factors handbook: 2011 edition* (EPA/600/R-09/052F). https://www.epa.gov/expobox/exposure-factors-handbook-chapter-6

Virtanen, P., Gommers, R., Oliphant, T. E., Haberland, M., Reddy, T., Cournapeau, D., Burovski, E., Peterson, P., Weckesser, W., Bright, J., van der Walt, S. J., Brett, M., Wilson, J., Millman, K. J., Mayorov, N., Nelson, A. R. J., Jones, E., Kern, R., Larson, E., . . . SciPy 1.0 Contributors. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python. *Nature Methods, 17*(3), 261–272. https://doi.org/10.1038/s41592-019-0686-2

Wells, W. F. (1955). *Airborne contagion and air hygiene: An ecological study of droplet infections*. Harvard University Press.

<!-- REFERENCES:END -->

## 6. Open items

1. **Partial references** (see `status` in `references.yaml`): the PSA enrollment table needs its update date and your download date; DepEd (2017) and DepEd (2010) need their specific values confirmed in the DepEd copies.
2. **News figures change.** Recheck the classroom backlog (Cariaso, 2026) and the DepEd ratios the day before submission.
3. **Template space.** The Background and References boxes are small. The Background is written to fit with the two cuts noted in section 1; the references may need a smaller font or a second page. APA asks for a hanging indent.
4. **Page limits.** I did not find the competition's page or reference limits. Check the guidelines.
