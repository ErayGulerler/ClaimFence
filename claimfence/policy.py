"""Expense operations. Each lookup uses the authenticated person's tenant."""
from .data import connection


class Rejected(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def public_claim(row):
    return {key: row[key] for key in ("id", "owner", "cents", "purpose", "status")}


def current_person(db, user_id):
    person = db.execute("SELECT * FROM people WHERE id = ?", (user_id,)).fetchone()
    if person is None:
        raise Rejected(401, "authentication required")
    return person


def visible_claim(db, person, claim_id):
    row = db.execute("""
        SELECT * FROM claims
        WHERE id = ? AND tenant = ?
          AND (owner = ? OR ? = 'reviewer')
    """, (claim_id, person["tenant"], person["id"], person["role"])).fetchone()
    if row is None:
        raise Rejected(404, "not found")
    return row


def list_claims(path, user_id):
    with connection(path) as db:
        db.execute("BEGIN")
        person = current_person(db, user_id)
        rows = db.execute("""
            SELECT * FROM claims
            WHERE tenant = ? AND (owner = ? OR ? = 'reviewer')
            ORDER BY id
        """, (person["tenant"], person["id"], person["role"]))
        return [public_claim(row) for row in rows]


def read_claim(path, user_id, claim_id):
    with connection(path) as db:
        db.execute("BEGIN")
        person = current_person(db, user_id)
        return public_claim(visible_claim(db, person, claim_id))


def approve_claim(path, user_id, claim_id):
    with connection(path) as db:
        # Serialize read/check/write so a competing approval sees the committed state.
        db.execute("BEGIN IMMEDIATE")
        person = current_person(db, user_id)
        row = visible_claim(db, person, claim_id)
        if person["role"] != "reviewer":
            raise Rejected(403, "forbidden")
        if row["owner"] == person["id"]:
            raise Rejected(403, "forbidden")
        if row["status"] != "pending":
            raise Rejected(409, "already decided")
        db.execute("UPDATE claims SET status = 'approved' WHERE id = ?", (claim_id,))
        db.execute("INSERT INTO approvals (claim_id, reviewer) VALUES (?, ?)",
                   (claim_id, person["id"]))
        return {"id": claim_id, "status": "approved"}
