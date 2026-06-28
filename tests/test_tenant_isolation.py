"""Changing another customer's workload must leave our API view unchanged."""
import random
import unittest
from uuid import UUID

from checks.lab import lab, request, snapshot
from checks.matrix import MISSING
from claimfence.data import connection


class TenantIsolation(unittest.TestCase):
    def test_foreign_claims_are_indistinguishable_from_missing_ids(self):
        rng = random.Random(336)  # Repeatable inputs on each CI run.
        with lab() as (db_path, url, tokens):
            outsiders = []
            for index in range(24):
                claim_id = str(UUID(int=rng.getrandbits(128), version=4))
                tenant = rng.choice(("east", "west", "central"))
                outsiders.append((claim_id, tenant, tenant + "-employee",
                                  rng.randint(1, 200_000), f"Site visit {index}", "internal"))

            actors = ("lee", "mara")
            lists = {a: request(url, tokens[a], "GET", "/claims") for a in actors}
            with connection(db_path) as db:
                for tenant in ("east", "west", "central"):
                    db.execute("INSERT INTO people VALUES (?, ?, 'employee')",
                               (tenant + "-employee", tenant))
                db.executemany("""
                    INSERT INTO claims (id, tenant, owner, cents, purpose, internal_note)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, outsiders)

            before = snapshot(db_path)
            for actor in actors:
                self.assertEqual(lists[actor][0], 200)
                self.assertEqual(request(url, tokens[actor], "GET", "/claims"), lists[actor])
                for method, suffix in (("GET", ""), ("POST", "/approve")):
                    missing = request(url, tokens[actor], method, f"/claims/{MISSING}{suffix}")
                    self.assertEqual(missing, (404, {"error": "not found"}))
                    for claim_id, *_ in outsiders:
                        with self.subTest(actor=actor, method=method, claim=claim_id):
                            actual = request(url, tokens[actor], method, f"/claims/{claim_id}{suffix}")
                            self.assertEqual(actual, missing)
            self.assertEqual(snapshot(db_path), before)

    def test_demotion_takes_effect_on_next_request(self):
        with lab() as (db_path, url, tokens):
            status, claims = request(url, tokens["mara"], "GET", "/claims")
            self.assertEqual(status, 200)
            peer = next(c for c in claims if c["owner"] == "lee")
            with connection(db_path) as db:
                db.execute("UPDATE people SET role = 'employee' WHERE id = 'mara'")
            before = snapshot(db_path)
            result = request(url, tokens["mara"], "POST", f"/claims/{peer['id']}/approve")
            self.assertEqual(result, (404, {"error": "not found"}))
            self.assertEqual(snapshot(db_path), before)
