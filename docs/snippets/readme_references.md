## References and sources

All sources used by the model, the app and the proposal are listed in APA 7th in [docs/references_apa7.md](docs/references_apa7.md), generated from [references.yaml](references.yaml). Each entry records whether it was checked against the publisher, library or government record (`verified`) or still has an open detail (`partial`), the check date, and where it was checked. Model parameters cite their sources in [params.yaml](params.yaml), and [docs/assumptions.md](docs/assumptions.md) explains each value and where sources disagree.

To change the list, edit `references.yaml` and run `python scripts/build_references.py`. `python -m pytest tests/test_citations.py` checks that every citation in the app and docs has an entry and that every entry is cited somewhere.
