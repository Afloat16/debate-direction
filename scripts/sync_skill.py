"""Keep the wheel's portable skill identical to the repository distribution."""

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "debate-direction"
TARGET = ROOT / "src" / "debate_direction" / "_skill"


def snapshot(path):
    return {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        if snapshot(SOURCE) != snapshot(TARGET):
            raise SystemExit("Skill bundle differs. Run python scripts/sync_skill.py before building.")
        print("Skill bundle matches the portable source.")
    else:
        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(SOURCE, TARGET)
        print("Updated the bundled skill.")


if __name__ == "__main__":
    main()
