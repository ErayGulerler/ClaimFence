"""Prove the suite rejects isolated, deliberately weakened copies of the policy."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
# Require a specific symptom and case. A crash or an unrelated failure cannot score a kill.
FAULTS = [
    ("unscoped-item", "WHERE id = ? AND tenant = ?", "WHERE id = ? AND ? IS NOT NULL",
     "mara/read/vale", "status"),
    ("unscoped-list", "WHERE tenant = ? AND (owner", "WHERE ? IS NOT NULL AND (owner",
     "mara/list/all", "response body"),
    ("self-approval", 'if row["owner"] == person["id"]:', 'if row["owner"] == "":',
     "mara/approve/mara", "approval journal"),
    ("private-field", '"purpose", "status")', '"purpose", "status", "internal_note")',
     "lee/read/lee", "response body"),
]


def probe(directory):
    report_path = directory / "run.json"
    run = subprocess.run(
        [sys.executable, "-B", "-m", "checks.matrix", "--json", str(report_path)],
        cwd=directory, capture_output=True, text=True, timeout=120,
    )
    if run.returncode not in (0, 1) or not report_path.exists():
        raise RuntimeError(run.stderr or "Matrix did not produce a report")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if run.returncode != int(report["failed"] > 0):
        raise RuntimeError("Matrix exit code and report disagree")
    return report


def study():
    results = []
    with TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for package in ("claimfence", "checks"):
            shutil.copytree(ROOT / package, directory / package,
                            ignore=shutil.ignore_patterns("__pycache__"))
        source = directory / "claimfence" / "policy.py"
        original = source.read_text(encoding="utf-8")
        baseline = probe(directory)
        if baseline["failed"]:
            raise RuntimeError("Clean baseline failed. Repair the service before mutation testing.")
        for name, old, new, witness, symptom in FAULTS:
            if original.count(old) != 1:
                raise ValueError(f"Review mutation {name} after the policy source change.")
            source.write_text(original.replace(old, new), encoding="utf-8")
            report = probe(directory)
            case = next(r for r in report["cases"] if r["case"] == witness)
            detected = symptom in case["violations"]
            print(f"{name:15} {'DETECTED' if detected else 'MISSED':8} {witness} "
                  f"({report['failed']} failing cases)", flush=True)
            results.append({"fault": name, "detected": detected, "failing_cases": report["failed"],
                            "witness": case})
    return {"baseline_checks": baseline["total"], "baseline_failures": baseline["failed"],
            "mutations": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = study()
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(any(not result["detected"] for result in report["mutations"]))


if __name__ == "__main__":
    raise SystemExit(main())
