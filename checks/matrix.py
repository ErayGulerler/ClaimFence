"""Send real HTTP requests and compare their effects against the policy table."""
import argparse
import csv
import json
from copy import deepcopy
from itertools import product
from pathlib import Path

from .lab import lab, request, snapshot

MISSING = "00000000-0000-4000-8000-000000000000"
ACTORS = {"lee", "mara", "oren", "vale", "guest"}
OWNERS = {"lee", "mara", "oren", "vale", "missing"}
MESSAGES = {401: "authentication required", 403: "forbidden", 404: "not found"}


def load_matrix():
    with Path(__file__).with_name("policy.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    pairs = [(r["actor"], r["claim_owner"]) for r in rows]
    if set(pairs) != set(product(ACTORS, OWNERS)) or len(set(pairs)) != len(rows):
        raise ValueError("Matrix must cover each actor/owner pair exactly once.")
    return rows


def expected_view(claim):
    # The external contract is intentionally independent of the service serializer.
    return {key: claim[key] for key in ("id", "owner", "cents", "purpose", "status")}


def check(actor, operation, owner, expected_status, visible_owners=()):
    with lab() as (db, url, tokens):
        before, old_events = snapshot(db)
        by_owner = {row["owner"]: row for row in before}
        claim_id = by_owner[owner]["id"] if owner in by_owner else MISSING
        method, route = "GET", "/claims"
        expected_claims, expected_events = deepcopy(before), list(old_events)
        if operation != "list":
            route += "/" + claim_id
        if operation == "approve":
            method, route = "POST", route + "/approve"

        if expected_status != 200:
            expected_body = {"error": MESSAGES[expected_status]}
        elif operation == "list":
            expected_body = [expected_view(c) for c in before if c["owner"] in visible_owners]
        elif operation == "read":
            expected_body = expected_view(by_owner[owner])
        else:
            expected_body = {"id": claim_id, "status": "approved"}
            next(c for c in expected_claims if c["id"] == claim_id)["status"] = "approved"
            expected_events.append({"claim_id": claim_id, "reviewer": actor})

        status, body = request(url, tokens.get(actor), method, route)
        after, events = snapshot(db)
        result = {
            "case": f"{actor}/{operation}/{owner}", "request": f"{method} {route}",
            "expected_status": expected_status, "actual_status": status, "violations": [],
        }
        if status != expected_status:
            result["violations"].append("status")
        if body != expected_body:
            result["violations"].append("response body")
        if after != expected_claims:
            result["violations"].append("claim state")
        if events != expected_events:
            result["violations"].append("approval journal")
        if result["violations"]:
            result.update(expected_body=expected_body, actual_body=body,
                          observed_events=events)
        return result


def run_matrix():
    rows = load_matrix()
    results = []
    for actor in sorted(ACTORS):
        cases = [r for r in rows if r["actor"] == actor]
        visible = [r["claim_owner"] for r in cases if r["read"] == "200"]
        results.append(check(actor, "list", "all", 401 if actor == "guest" else 200, visible))
        for row in cases:
            for operation in ("read", "approve"):
                results.append(check(actor, operation, row["claim_owner"], int(row[operation])))
    failed = sum(bool(r["violations"]) for r in results)
    return {"total": len(results), "passed": len(results) - failed, "failed": failed, "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run_matrix()
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Authorization matrix: {report['passed']}/{report['total']} passed.")
    for case in report["cases"]:
        if case["violations"]:
            print("FAIL", case["case"], ", ".join(case["violations"]))
    return int(report["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
