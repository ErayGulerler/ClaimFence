"""Rebuild the evidence and exit nonzero if a check fails."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    (ROOT / "evidence").mkdir(exist_ok=True)
    commands = (
        ["-m", "unittest", "discover", "-s", "tests", "-v"],
        ["-m", "checks.matrix", "--json", "evidence/matrix.json"],
        ["-m", "checks.mutations", "--json", "evidence/mutations.json"],
    )
    for command in commands:
        result = subprocess.run([sys.executable, "-B", *command], cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
