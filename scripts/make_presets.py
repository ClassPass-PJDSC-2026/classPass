"""Generate preset scenario files into data/processed/. Placeholder."""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"make_presets: nothing to generate yet (output dir: {OUT})")


if __name__ == "__main__":
    main()