"""Loopback HTTP adapter. Only the Authorization header establishes identity."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import secrets
import sqlite3
import threading

from . import policy
from .data import PEOPLE

ITEM = re.compile(r"/claims/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(/approve)?")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Avoid storing request paths or credentials in the lab.

    def reply(self, status, data):
        payload = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        if status == 401:
            self.send_header("WWW-Authenticate", "Bearer")
        self.end_headers()
        self.wfile.write(payload)

    def dispatch(self):
        try:
            credentials = self.headers.get_all("Authorization", [])
            user_id = None
            if len(credentials) == 1:
                user_id = self.server.sessions.get(credentials[0])
            if user_id is None:
                raise policy.Rejected(401, "authentication required")
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") is not None or lengths not in ([], ["0"]):
                raise policy.Rejected(400, "this endpoint accepts no body")

            if self.command == "GET" and self.path == "/claims":
                result = policy.list_claims(self.server.db_path, user_id)
            else:
                match = ITEM.fullmatch(self.path)
                if match is None:
                    raise policy.Rejected(404, "not found")
                claim_id, approve = match.groups()
                if self.command == "POST" and approve:
                    result = policy.approve_claim(self.server.db_path, user_id, claim_id)
                elif self.command == "GET" and not approve:
                    result = policy.read_claim(self.server.db_path, user_id, claim_id)
                else:
                    raise policy.Rejected(405, "method not allowed")
            self.reply(200, result)
        except policy.Rejected as error:
            self.reply(error.status, {"error": str(error)})
        except sqlite3.Error:
            self.reply(500, {"error": "storage error"})

    do_GET = dispatch
    do_POST = dispatch


@contextmanager
def running(db_path, port=0):
    tokens = {user: secrets.token_urlsafe(32) for user, _, _ in PEOPLE}
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        server.db_path = db_path
        server.sessions = {"Bearer " + token: user for user, token in tokens.items()}
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", tokens
        finally:
            server.shutdown()
            thread.join()
