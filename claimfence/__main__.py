"""Start a fresh local lab for manual requests."""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from .data import initialize, CLAIMS
from .server import running


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    with TemporaryDirectory() as directory:
        path = Path(directory) / "expenses.db"
        initialize(path)
        with running(path, args.port) as (url, tokens):
            print("Disposable local API:", url)
            for user, token in tokens.items():
                print(f"{user} bearer token: {token}")
            print("Example (use curl.exe in Windows PowerShell):")
            print(f'curl -H "Authorization: Bearer {tokens["mara"]}" {url}/claims/{CLAIMS[0][0]}')
            print("Press Ctrl+C to discard the lab.", flush=True)
            try:
                Event().wait()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
