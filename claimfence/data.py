"""Synthetic records and a small SQLite store."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

PEOPLE = [
    ("lee", "north", "employee"),
    ("mara", "north", "reviewer"),
    ("oren", "north", "employee"),
    ("vale", "south", "reviewer"),
]
# Stable IDs make the two HTTP transcripts easy to compare.
CLAIMS = [
    ("a391f982-7f70-4df2-9099-e8a040b70b4d", "north", "lee", 16400, "Rail fare", "sample-review-A"),
    ("adf72f05-60b7-494d-846a-c96691ea6ee0", "north", "mara", 7800, "Client lunch", "sample-review-B"),
    ("b6ea1a07-335e-44ca-8450-a332f5b36da0", "north", "oren", 22500, "Hotel stay", "sample-review-C"),
    ("d3ca7323-cc89-4d32-a40a-754329113ae7", "south", "vale", 9100, "Airport transfer", "sample-review-D"),
]

@contextmanager
def connection(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path: Path):
    with connection(path) as db:
        db.executescript("""
            CREATE TABLE people (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, role TEXT NOT NULL
            );
            CREATE TABLE claims (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, owner TEXT NOT NULL,
                cents INTEGER NOT NULL, purpose TEXT NOT NULL, internal_note TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved'))
            );
            CREATE TABLE approvals (
                claim_id TEXT PRIMARY KEY, reviewer TEXT NOT NULL,
                decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        db.executemany("INSERT INTO people VALUES (?, ?, ?)", PEOPLE)
        db.executemany("""
            INSERT INTO claims (id, tenant, owner, cents, purpose, internal_note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, CLAIMS)
