import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from checks.lab import lab, request, snapshot
from claimfence.data import CLAIMS, connection


class ExpenseWorkflow(unittest.TestCase):
    def setUp(self):
        self.db, self.url, self.tokens = self.enterContext(lab())
        self.route = f"/claims/{CLAIMS[0][0]}/approve"

    def approve(self, actor="mara", **kwargs):
        return request(self.url, self.tokens[actor], "POST", self.route, **kwargs)

    def test_two_review_requests_commit_once(self):
        barrier = Barrier(2)

        def submit():
            barrier.wait(timeout=5)
            return self.approve()[0]

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            self.assertEqual(sorted(f.result() for f in futures), [200, 409])
        claims, events = snapshot(self.db)
        self.assertEqual([c["id"] for c in claims if c["status"] == "approved"], [CLAIMS[0][0]])
        self.assertEqual(events, [{"claim_id": CLAIMS[0][0], "reviewer": "mara"}])

    def test_repeat_returns_conflict(self):
        self.assertEqual(self.approve()[0], 200)
        before = snapshot(self.db)
        self.assertEqual(self.approve(), (409, {"error": "already decided"}))
        self.assertEqual(snapshot(self.db), before)

    def test_journal_failure_rolls_back_approval(self):
        with connection(self.db) as db:
            db.execute("""CREATE TRIGGER fail_journal BEFORE INSERT ON approvals
                          BEGIN SELECT RAISE(ABORT, 'injected lab fault'); END""")
        before = snapshot(self.db)
        self.assertEqual(self.approve(), (500, {"error": "storage error"}))
        self.assertEqual(snapshot(self.db), before)
        with connection(self.db) as db:
            db.execute("DROP TRIGGER fail_journal")
        self.assertEqual(self.approve()[0], 200)

    def test_spoofed_role_does_not_grant_approval(self):
        before = snapshot(self.db)
        result = self.approve("lee", headers={"X-Role": "reviewer", "X-User": "mara"})
        self.assertEqual(result, (403, {"error": "forbidden"}))
        self.assertEqual(snapshot(self.db), before)

    def test_spoofed_tenant_does_not_reveal_south_claim(self):
        status, body = request(self.url, self.tokens["mara"], "GET", f"/claims/{CLAIMS[3][0]}",
                               headers={"X-Tenant": "south"})
        self.assertEqual((status, body), (404, {"error": "not found"}))

    def test_approval_rejects_supplied_properties(self):
        before = snapshot(self.db)
        result = self.approve(body='{"reviewer":"vale","status":"approved"}')
        self.assertEqual(result, (400, {"error": "this endpoint accepts no body"}))
        self.assertEqual(snapshot(self.db), before)

    def test_unknown_bearer_token(self):
        self.assertEqual(request(self.url, "made-up", "GET", "/claims"),
                         (401, {"error": "authentication required"}))

    def test_ambiguous_credentials(self):
        headers = {"authorization": "Bearer " + self.tokens["vale"]}
        self.assertEqual(request(self.url, self.tokens["mara"], "GET", "/claims", headers=headers),
                         (401, {"error": "authentication required"}))

    def test_read_request_cannot_approve(self):
        before = snapshot(self.db)
        self.assertEqual(request(self.url, self.tokens["mara"], "GET", self.route)[0], 405)
        self.assertEqual(snapshot(self.db), before)
