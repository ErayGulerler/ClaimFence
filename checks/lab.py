from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import http.client
import json
from urllib.parse import urlsplit

from claimfence.data import connection, initialize
from claimfence.server import running


@contextmanager
def lab():
    with TemporaryDirectory() as directory:
        db_path = Path(directory) / "expenses.db"
        initialize(db_path)
        with running(db_path) as (url, tokens):
            yield db_path, url, tokens


def request(url, token, method, route, *, headers=None, body=None):
    headers = dict(headers or {})
    if token:
        headers["Authorization"] = "Bearer " + token
    address = urlsplit(url)
    client = http.client.HTTPConnection(address.hostname, address.port, timeout=10)
    try:
        client.request(method, route, headers=headers, body=body)
        response = client.getresponse()
        return response.status, json.loads(response.read())
    finally:
        client.close()


def snapshot(db_path):
    with connection(db_path) as db:
        claims = [dict(row) for row in db.execute("SELECT * FROM claims ORDER BY id")]
        events = [dict(row) for row in db.execute(
            "SELECT claim_id, reviewer FROM approvals ORDER BY claim_id")]
        return claims, events
