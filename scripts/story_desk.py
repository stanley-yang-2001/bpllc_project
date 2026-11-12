#!/usr/bin/env python3
"""The Story Test Desk on your own computer, live while a test runs (11 Nov 2026). Standard library only; listens on 127.0.0.1 only.

  python scripts\\story_desk.py            then open http://localhost:8090  (it opens itself)

Every 10 seconds the page reads test-reports\\overnight-*\\ and scripts\\*.json again. Nothing is sent anywhere and nothing is changed, except
the "Check keys now" button, which runs scripts/key_status.py inside the Langflow container (one request per key) when you press it."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from story_eval import desk  # noqa: E402

KEY_COMMAND = ["docker", "compose", "exec", "-T", "langflow", "python", "/app/scripts/key_status.py", "--out", "/app/scripts/key_status.json"]


def make_handler(root: Path, run_command=subprocess.run):
    reports, scripts = root / "test-reports", root / "scripts"
    page = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + (HERE / "story_eval" / "desk.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, kind: str):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                self._send(200, page.replace("/*DATA*/null", "null").encode("utf-8"), "text/html; charset=utf-8")
            elif url.path == "/api/state":
                run = (parse_qs(url.query).get("run") or [None])[0]
                self._send(200, json.dumps(desk.collect(reports, scripts, run), ensure_ascii=False).encode("utf-8"), "application/json")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if urlparse(self.path).path != "/api/key-status":
                return self._send(404, b"not found", "text/plain")
            try:
                done = run_command(KEY_COMMAND, cwd=str(root), capture_output=True, text=True, timeout=180)
                body = {"ok": done.returncode == 0, "output": (done.stdout or "")[-2000:], "error": (done.stderr or "")[-600:]}
            except Exception as error:      # noqa: BLE001 - shown on the page
                body = {"ok": False, "output": "", "error": f"{type(error).__name__}: {error}"}
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def log_message(self, *args):      # quiet
            pass
    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--root", default=str(HERE.parent), help="the project folder (default: the one this script is in)")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(Path(args.root)))
    url = f"http://localhost:{args.port}"
    print(f"Story Test Desk: {url}   (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
