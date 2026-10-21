"""Guards for the privacy claims in docs/privacy_and_responsible_use.md (ticket #29).

The document says the app does not write user input to disk, a database or the page address.
These checks scan the code so that claim stays true. They are deliberately strict: if one
fails, either fix the code or update the document and get the change reviewed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = (ROOT / "app", ROOT / "src" / "schoolsim")
DOC = ROOT / "docs" / "privacy_and_responsible_use.md"

FORBIDDEN_IMPORTS = {"sqlite3", "shelve", "pickle", "dbm", "tempfile"}
FORBIDDEN_METHODS = {
    "write_text", "write_bytes", "to_parquet", "to_pickle", "to_excel", "to_json", "to_feather", "to_hdf",
}
FORBIDDEN_ATTRIBUTES = {"query_params", "experimental_set_query_params"}


def code_files():
    return sorted(p for d in CODE_DIRS for p in d.rglob("*.py"))


def violations_in_source(source: str) -> list[str]:
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [f"imports {a.name}" for a in node.names if a.name.split(".")[0] in FORBIDDEN_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in FORBIDDEN_IMPORTS:
            found.append(f"imports from {node.module}")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            found.append(f"uses {node.attr} (page address)")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if mode and any(c in str(mode) for c in "wax+"):
                    found.append(f"opens a file for writing (mode {mode!r})")
            elif isinstance(func, ast.Attribute):
                if func.attr in FORBIDDEN_METHODS:
                    found.append(f"calls .{func.attr}()")
                if func.attr == "to_csv" and (node.args or any(k.arg == "path_or_buf" for k in node.keywords)):
                    found.append("calls .to_csv() with a destination (use no path to get bytes)")
    return found


def violations(path: Path) -> list[str]:
    return [f"{path.relative_to(ROOT)}: {v}" for v in violations_in_source(path.read_text(encoding="utf-8"))]


def test_the_scan_covers_the_app_and_the_package():
    names = {p.name for p in code_files()}
    assert {"streamlit_app.py", "sidebar.py", "params.py", "inputs.py"} <= names


def test_no_code_writes_user_input_to_disk_a_database_or_the_page_address():
    problems = [v for p in code_files() for v in violations(p)]
    assert not problems, "Privacy document says nothing is saved:\n" + "\n".join(problems)


@pytest.mark.parametrize(
    "snippet",
    [
        "open('x.txt', 'w')",
        "open('x.txt', mode='a')",
        "open('x.txt', 'r+')",
        "import sqlite3",
        "from pickle import dump",
        "df.to_csv('out.csv')",
        "df.to_csv(path_or_buf='out.csv')",
        "p.write_text('x')",
        "df.to_parquet('x.parquet')",
        "st.query_params['a'] = 1",
    ],
)
def test_the_scanner_catches_what_it_should(snippet):
    assert violations_in_source(f"import streamlit as st\n{snippet}\n"), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        "with open('params.yaml', encoding='utf-8') as f:\n    data = f.read()",
        "with open('params.yaml', 'r') as f:\n    data = f.read()",
        "csv = df.to_csv(index=False)",
        "data = df.to_csv(index=False).encode('utf-8')",
        "x = st.session_state['a']",
    ],
)
def test_the_scanner_allows_reading_and_in_memory_output(snippet):
    assert violations_in_source(snippet) == [], snippet


# --- the document --------------------------------------------------------------------------

def test_document_exists_and_has_the_required_sections():
    text = DOC.read_text(encoding="utf-8")
    for heading in (
        "What each feature handles",
        "Data flow",
        "AI assistant disclosure",
        "Third-party processing",
        "Data-source terms and attribution",
        "Checklist for the bug bash",
        "Open items before sign-off",
        "Sources",
    ):
        assert heading in text, f"missing section: {heading}"


def test_every_source_tag_used_in_the_text_is_defined_in_the_sources_table():
    text = DOC.read_text(encoding="utf-8")
    used = set(re.findall(r"\[(L\d+)(?: §[^\]]*)?\]", text))
    defined = set(re.findall(r"^\| (L\d+) \|", text, re.MULTILINE))
    assert used and used <= defined, f"undefined source tags: {sorted(used - defined)}"


def test_every_defined_source_has_a_link_and_a_status():
    text = DOC.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (L\d+) \|(.*)$", text, re.MULTILINE)
    assert rows
    for tag, rest in rows:
        assert "https://" in rest, f"{tag} has no link"
        assert re.search(r"Verified|Partial", rest), f"{tag} has no status"


def test_the_document_links_the_primary_sources():
    text = DOC.read_text(encoding="utf-8")
    assert "privacy.gov.ph" in text and "openstat.psa.gov.ph/Terms" in text


def test_the_document_names_the_attribution_text():
    text = DOC.read_text(encoding="utf-8")
    assert "Philippine Statistics Authority, OpenSTAT" in text and "not endorsed by the PSA or DepEd" in text
