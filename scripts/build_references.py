"""Regenerate the APA 7th reference list from references.yaml (ticket #19).

Writes docs/references_apa7.md and docs/references_apa7.html, and refreshes the generated
block in docs/proposal_text.md. Run from the repository root:

    python scripts/build_references.py          # write the files
    python scripts/build_references.py --check  # exit 1 if any file is out of date (used by CI/tests)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schoolsim.citations import render_html, render_markdown, replace_block  # noqa: E402
from schoolsim.params import load_references  # noqa: E402

MD_HEADER = (
    "# References (APA 7th)\n\n"
    "Generated from `references.yaml` by `scripts/build_references.py`. Do not edit by hand.\n"
    "Open `references_apa7.html` in a browser, select all and copy it to paste with the italics\n"
    "and the hanging indent.\n\n"
)


def expected_outputs() -> dict[Path, str]:
    refs = load_references()
    outputs = {
        ROOT / "docs" / "references_apa7.md": MD_HEADER + render_markdown(refs),
        ROOT / "docs" / "references_apa7.html": render_html(refs),
    }
    proposal = ROOT / "docs" / "proposal_text.md"
    if proposal.exists():
        outputs[proposal] = replace_block(proposal.read_text(encoding="utf-8"), render_markdown(refs))
    return outputs


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    for path, content in expected_outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        stale.append(path.relative_to(ROOT))
        if not check:
            path.write_text(content, encoding="utf-8")
    if check and stale:
        print("Out of date (run python scripts/build_references.py):", *stale, sep="\n  ")
        return 1
    print("References up to date." if not stale else f"Updated: {', '.join(map(str, stale))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
