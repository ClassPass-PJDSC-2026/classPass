"""Tests for the reference list and citation checks (ticket #19).

Acceptance criteria covered:
- every in-text citation in the app, README snippets, docs and proposal text has an entry in references.yaml
- every entry in references.yaml is cited somewhere
- no reference without a verified source (each entry records status, date and where it was checked)
- the APA 7th list is complete, ordered and in sync with the generated files
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from schoolsim import citations as c
from schoolsim.params import REPO_ROOT, load_params, load_references

REFS = load_references()
ROOT = REPO_ROOT
RESERVED = {"team_assumption", "team_decision"}


# --- Which files are scanned ----------------------------------------------------------------

def scanned_files() -> list[Path]:
    """Texts whose citations must resolve. The generated reference list itself is excluded."""
    files = [ROOT / "README.md"]
    files += sorted((ROOT / "docs").glob("*.md"))
    files += sorted((ROOT / "docs" / "snippets").glob("*.md"))
    files += sorted((ROOT / "app").glob("*.py"))
    files += sorted((ROOT / "src" / "schoolsim").glob("*.py"))
    skip = {"references_apa7.md", "citations.py"}  # the generated list; the checker's own examples
    return [f for f in files if f.exists() and f.name not in skip]


def read_without_generated_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return re.sub(re.escape(c.START_MARK) + r".*?" + re.escape(c.END_MARK), "", text, flags=re.DOTALL)


def scan() -> tuple[dict[str, list[str]], set[str]]:
    unknown: dict[str, list[str]] = {}
    cited: set[str] = set()
    for path in scanned_files():
        bad, keys = c.check_text(read_without_generated_block(path), REFS)
        if bad:
            unknown[str(path.relative_to(ROOT))] = bad
        cited |= keys
    return unknown, cited


# --- Acceptance criteria ----------------------------------------------------------------------

def test_every_citation_in_the_text_has_a_reference():
    unknown, _ = scan()
    assert not unknown, "Citations with no entry in references.yaml:\n" + "\n".join(
        f"  {file}: {', '.join(items)}" for file, items in unknown.items()
    )


def test_every_reference_is_cited_somewhere():
    _, cited = scan()
    from_params = {s for p in load_params().values() for s in p.source}
    uncited = sorted(set(REFS) - cited - from_params)
    assert not uncited, f"References that nothing cites: {uncited}"


def test_every_parameter_source_exists():
    keys = {s for p in load_params().values() for s in p.source}
    assert c.unresolved_keys(keys, REFS, RESERVED) == []


def test_the_reference_file_is_sound():
    assert c.validate_entries(REFS) == []


def test_every_entry_records_how_and_when_it_was_checked():
    for key, entry in REFS.items():
        assert entry["status"] in c.STATUSES, key
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry["verified_on"])), key
        assert len(str(entry["checked_via"])) > 10, key


def test_partial_entries_say_what_is_left_to_do():
    for key, entry in REFS.items():
        if entry["status"] == "partial":
            assert len(str(entry.get("notes", ""))) > 40, f"{key} is partial but does not say what is open"


def test_no_verified_entry_has_a_placeholder():
    for key, entry in REFS.items():
        if entry["status"] == "verified":
            apa = entry["apa"].replace("[Report]", "").replace("[Data set]", "")
            assert not re.search(r"\[[^\]]*\]\s*(?:,|\.)|TODO", apa), key


# --- APA 7th form -----------------------------------------------------------------------------

def test_list_is_alphabetical_with_the_second_author_rule():
    lines = [re.sub(r"[*&]", "", line).lower() for line in c.apa_lines(REFS)]
    firsts = [line.split(",")[0].split(".")[0] for line in lines]
    assert firsts == sorted(firsts, key=lambda s: s)  # first author order
    azimi = [i for i, line in enumerate(lines) if line.startswith("azimi")]
    assert "keshavarz" in lines[azimi[0]] and "stephens" in lines[azimi[1]]


def test_same_author_entries_are_in_year_order():
    lines = c.apa_lines(REFS)
    dept = [line for line in lines if line.startswith("Department of Education.")]
    years = [int(re.search(r"\((\d{4})\)", line).group(1)) for line in dept]
    assert years == sorted(years) and len(years) == 2


def test_every_entry_has_a_year_in_parentheses():
    for key, entry in REFS.items():
        assert re.search(r"\((?:\d{4}|n\.d\.)(?:, [A-Z][a-z]+ \d{1,2})?\)", entry["apa"]) or entry["year"] is None, key


def test_dois_are_written_as_https_links():
    for key, entry in REFS.items():
        if entry.get("doi"):
            assert f"https://doi.org/{entry['doi']}" in entry["apa"], key
            assert re.fullmatch(r"10\.\d{4,9}/\S+", entry["doi"]), key


def test_journal_name_and_volume_are_italic_but_the_issue_is_not():
    apa = REFS["carrat_2008"]["apa"]
    assert "*American Journal of Epidemiology, 167*(7)" in apa


def test_book_titles_are_italic_and_article_titles_are_not():
    assert "*Modeling infectious diseases in humans and animals*" in REFS["keeling_rohani_2008"]["apa"]
    assert "*Airborne spread of measles" not in REFS["riley_1978"]["apa"]


def test_titles_use_sentence_case():
    for key in ("carrat_2008", "azimi_2020", "leung_2020", "riley_1978", "rudnick_milton_2003"):
        title = re.search(r"\)\.\s+(.*?)\.\s+\*", REFS[key]["apa"]).group(1)
        words = title.replace(":", " :").split()
        capitals = [w for w in words[1:] if w[:1].isupper() and not w.isupper() and w not in {"US", "HVAC"}]
        assert len(capitals) <= 2, f"{key}: title not in sentence case: {title}"


def test_more_than_twenty_authors_use_the_ellipsis_form():
    apa = REFS["virtanen_2020"]["apa"]
    before_ellipsis = apa.split(". . .")[0]
    assert apa.count(". . .") == 1 and "SciPy 1.0 Contributors. (2020)" in apa
    assert len(re.findall(r"[A-Z][a-z]+, [A-Z]\.", before_ellipsis)) == 19


def test_up_to_twenty_authors_are_all_listed_with_an_ampersand():
    apa = REFS["leung_2020"]["apa"]
    assert ", & Cowling, B. J. (2020)" in apa and "Peiris, J. S. M." in apa


def test_news_without_a_byline_puts_the_title_first():
    lines = [line for line in c.apa_lines(REFS) if "Daily Tribune" in line]
    assert len(lines) == 1 and lines[0].startswith("DepEd projects up to 28M enrollees. (2026, May 31).")


def test_statute_form():
    assert REFS["ra10173_2012"]["apa"].startswith("Data Privacy Act of 2012, Republic Act No. 10173 (2012)")


# --- Generated files stay in sync ------------------------------------------------------------

def _script():
    spec = importlib.util.spec_from_file_location("build_references", ROOT / "scripts" / "build_references.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_files_are_up_to_date():
    for path, expected in _script().expected_outputs().items():
        assert path.read_text(encoding="utf-8") == expected, (
            f"{path.relative_to(ROOT)} is out of date: run python scripts/build_references.py"
        )


def test_proposal_text_contains_the_full_list():
    text = (ROOT / "docs" / "proposal_text.md").read_text(encoding="utf-8")
    block = text.split(c.START_MARK)[1].split(c.END_MARK)[0]
    for line in c.apa_lines(REFS):
        assert line in block


def test_html_has_a_hanging_indent_italics_and_links():
    page = c.render_html(REFS)
    assert "text-indent:-0.5in" in page and "padding-left:0.5in" in page
    assert "<i>Indoor Air, 13</i>" in page
    assert '<a href="https://doi.org/10.1093/aje/kwm375">' in page
    assert "*" not in page.split("<body>")[1]
    assert "&amp;" in page and " & " not in page.split("<body>")[1]


def test_markdown_italics_are_balanced():
    for line in c.apa_lines(REFS):
        assert line.count("*") % 2 == 0, line


def test_every_entry_is_in_the_generated_list():
    assert len(c.apa_lines(REFS)) == len(REFS)


# --- Proposal text -------------------------------------------------------------------------------

def proposal() -> str:
    return (ROOT / "docs" / "proposal_text.md").read_text(encoding="utf-8")


def test_background_fits_the_template_and_cites_its_claims():
    section = proposal().split("## 1. Background")[1].split("## 2.")[0].split("\n", 1)[1].split("*If the template")[0]
    assert len(re.findall(r"[\w'’\-–]+", section)) <= 240
    for topic in ("classroom", "ventilation", "influenza-like illness"):
        assert topic in section
    assert len(c.find_citations(section)) >= 6


def test_background_covers_class_size_shortage_ventilation_and_ili():
    section = proposal().split("## 1. Background")[1].split("## 2.")[0].lower()
    for phrase in ("learners per classroom", "backlog", "ventilat", "influenza-like illness"):
        assert phrase in section


def test_methodology_cites_every_method_and_tool():
    section = proposal().split("## 3. Revised Methodology")[1].split("## 4.")[0]
    _, cited = c.check_text(section, REFS)
    assert {"riley_1978", "wells_1955", "rudnick_milton_2003", "keeling_rohani_2008", "mckay_1979", "virtanen_2020",
            "mckinney_2010", "harvard_hbp_2020", "psa_schools_2024", "psa_enrollment"} <= cited


def test_methodology_has_the_known_typos_fixed():
    section = proposal().split("## 3. Revised Methodology")[1].split("## 4.")[0]
    for typo in ("on from", "programming languages Python and SciPy", "10 development days", "floor plan"):
        assert typo not in section


def test_corrections_table_lists_the_original_typos():
    table = proposal().split("## 2. Corrections")[1].split("## 3.")[0]
    for original in ("on from", "these type of occasions", "10 days", "programming languages Python and SciPy"):
        assert original in table


# --- Checker behaviour ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("Rudnick & Milton", "rudnick and milton"),
        ("Rudnick and Milton", "rudnick and milton"),
        ("Carrat et al.", "carrat"),
        ("The Philippine Star", "philippine star"),
        ('"DepEd Projects"', "deped projects"),
        ("  Wells ,", "wells"),
    ],
)
def test_normalise_author(text, expected):
    assert c.normalise_author(text) == expected


@pytest.mark.parametrize(
    "text, authors, years",
    [
        ("(Wells, 1955)", ["wells"], ["1955"]),
        ("(Wells, 1955; Riley et al., 1978)", ["wells", "riley"], ["1955", "1978"]),
        ("(Philippine Statistics Authority, n.d., 2024)", ["philippine statistics authority"] * 2, ["n.d.", "2024"]),
        ('("DepEd Projects Up to 28M Enrollees," 2026)', ["deped projects up to 28m enrollees"], ["2026"]),
        ("Carrat et al. (2008) found", ["carrat"], ["2008"]),
        ("Rudnick & Milton (2003)", ["milton"], ["2003"]),
    ],
)
def test_find_citations(text, authors, years):
    found = c.find_citations(text)
    assert [x.author for x in found] == authors and [x.year for x in found] == years


def test_text_without_citations_finds_none():
    assert c.find_citations("Class size is 45 (see Table 3) and ACH is 4 (windows open).") == []


def test_unknown_citations_are_reported_and_known_ones_are_not():
    unknown, cited = c.check_text("(Wells, 1955) and (Nobody et al., 1999) and Ghost & Writer (2001).", REFS)
    assert "wells_1955" in cited
    assert "(Nobody et al., 1999)" in unknown and any("Ghost & Writer (2001)" in u for u in unknown)


def test_multi_word_surnames_resolve():
    unknown, cited = c.check_text("Bueno de Mesquita et al. (2020) measured it.", REFS)
    assert unknown == [] and "bueno_de_mesquita_2020" in cited


def test_aliases_resolve():
    _, cited = c.check_text("(Harvard HBP, 2020) and (PSA, 2024)", REFS)
    assert {"harvard_hbp_2020", "psa_schools_2024"} <= cited


def test_wrong_year_is_unknown():
    unknown, _ = c.check_text("(Carrat et al., 2009)", REFS)
    assert unknown == ["(Carrat et al., 2009)"]


def test_statutes_count_as_cited_by_name():
    _, cited = c.check_text("under the Data Privacy Act of 2012 (RA 10173)", REFS)
    assert "ra10173_2012" in cited


def test_replace_block_swaps_only_the_marked_part():
    text = f"before\n{c.START_MARK}\nold\n{c.END_MARK}\nafter\n"
    out = c.replace_block(text, "new list")
    assert "new list" in out and "old" not in out and out.startswith("before") and out.endswith("after\n")
    with pytest.raises(ValueError):
        c.replace_block("no markers", "x")


def entry(**kw):
    base = {
        "author": "Smith",
        "year": 2020,
        "short": "Smith (2020)",
        "apa": "Smith, A. (2020). Title. *Journal, 1*(1), 1–2.",
        "status": "verified",
        "verified_on": "2026-10-21",
        "checked_via": "PubMed record",
    }
    base.update(kw)
    return base


def test_validation_catches_problems():
    assert c.validate_entries({"a": entry()}) == []
    assert any("missing 'checked_via'" in p for p in c.validate_entries({"a": entry(checked_via="")}))
    assert any("status must be" in p for p in c.validate_entries({"a": entry(status="maybe")}))
    assert any("placeholder" in p for p in c.validate_entries({"a": entry(apa="Smith, A. (2020). Title [date]. X.")}))
    assert any("year 2021" in p for p in c.validate_entries({"a": entry(year=2021)}))
    assert any("DOI" in p for p in c.validate_entries({"a": entry(doi="10.1/abc")}))
    assert any("same author and year" in p for p in c.validate_entries({"a": entry(), "b": entry()}))


def test_unresolved_keys():
    assert c.unresolved_keys(["wells_1955", "nope", "team_assumption"], REFS, RESERVED) == ["nope"]


@pytest.mark.parametrize("text", ["(October 20–24, 2026)", "(Oct. 14, 2025)", "(May 31, 2026)", "(July 25, 2026)"])
def test_dates_in_parentheses_are_not_citations(text):
    assert c.find_citations(text) == []


def test_a_date_next_to_a_real_citation_does_not_hide_it():
    found = c.find_citations("In the sprint (October 20–24, 2026) we follow Wells (1955) and (Riley et al., 1978).")
    assert {(x.author, x.year) for x in found} == {("wells", "1955"), ("riley", "1978")}
