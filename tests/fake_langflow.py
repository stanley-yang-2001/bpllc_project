"""A tiny fake Langflow on a real local socket, for testing the command-line scripts end to end.

It speaks just enough of the API that scripts/spike_tweaks.py and scripts/capture_fixtures.py use:
  GET  /api/v1/auto_login                      -> a token
  POST /api/v1/api_key/                        -> an API key
  POST /api/v1/run/<flow>?stream=false         -> a run response (see below)
  GET  /api/v1/monitor/messages?session_id=    -> the stored messages of that session
  GET  /api/v1/monitor/messages/sessions       -> the stored session ids
  DELETE /api/v1/monitor/messages/session/<id> -> forgets that session

A run behaves like the Who Am I spike flow when the message mentions "Who Am I" (the tool reports the
`learner_id` and `language` of the tweaks for the key it is given, holding 0.3 s so parallel calls overlap), and
like the real tutor otherwise (a story request returns a tool call). `legacy=True` prints the ORIGINAL spike code's field name (user_id). `shadow=True` reproduces the first live run's
bug: the tool reports a fixed "Langflow account" id instead of the learner. Like Langflow's parameter handler, a
tweak sent to a text field as anything but a string is silently dropped (second live run: an integer learner_id
vanished while the string `language` arrived).
"""
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ACCOUNT = "784d78de-8532-42c1-990e-d6b50f77beb0"


class FakeLangflow:
    def __init__(self, key="K", shadow=False, legacy=False):
        self.key, self.shadow, self.legacy = key, shadow, legacy
        self.sessions: dict[str, list] = {}
        self.requests: list[tuple] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                url = urlparse(self.path)
                outer.requests.append(("GET", url.path))
                if url.path == "/api/v1/auto_login":
                    return self._send(200, {"access_token": "t"})
                if url.path == "/api/v1/monitor/messages/sessions":
                    return self._send(200, list(outer.sessions))
                if url.path == "/api/v1/monitor/messages":
                    return self._send(200, outer.sessions.get(parse_qs(url.query).get("session_id", [""])[0], []))
                self._send(404, {"detail": "not found"})

            def do_DELETE(self):
                url = urlparse(self.path)
                outer.requests.append(("DELETE", url.path))
                m = re.match(r"/api/v1/monitor/messages/session/(.+)", url.path)
                if m:
                    outer.sessions.pop(m.group(1), None)
                    return self._send(200, {"message": "deleted"})
                self._send(404, {"detail": "not found"})

            def do_POST(self):
                url = urlparse(self.path)
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                outer.requests.append(("POST", url.path, self.headers.get("x-api-key")))
                if url.path == "/api/v1/api_key/":
                    return self._send(200, {"api_key": "fake-api-key"})
                if url.path.startswith("/api/v1/run/"):
                    if self.headers.get("x-api-key") != "fake-api-key":
                        return self._send(403, {"detail": "bad key"})
                    return self._send(200, outer.run(body))
                self._send(404, {"detail": "not found"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def run(self, body):
        message, session = body.get("input_value", ""), body.get("session_id", "")
        if "who am i" in message.lower():
            t0 = time.time()
            time.sleep(0.3)
            cfg = {k: v for k, v in (body.get("tweaks") or {}).get(self.key, {}).items() if isinstance(v, str)}
            learner = ACCOUNT if self.shadow else str(cfg.get("learner_id", "NONE"))
            field = "user_id" if self.legacy else "learner_id"      # legacy = the original spike code on the canvas
            text = (f"WHOAMI {field}={learner} language={cfg.get('language', 'NONE')} langflow_user={ACCOUNT} "
                    f"session=NONE graph_session={session} t0={t0:.3f} t1={time.time():.3f} thread=1")
            calls = [{"type": "tool_use", "name": "spike_who_am_i", "tool_input": {"note": "x"}, "output": text}]
        elif "story" in message.lower():
            text = "Ana: Hola.\nBen: Hola, Ana."
            calls = [{"type": "tool_use", "name": "story_generator_tool", "tool_input": {"language": "Spanish"}, "output": text}]
        else:
            text, calls = "Hello! How can I help?", []
        self.sessions[session] = [{"sender": "User", "text": message},
                                  {"sender": "Machine", "text": text, "content_blocks": [{"contents": calls}] if calls else []}]
        return {"session_id": session, "outputs": [{"outputs": [{"results": {"message": {
            "text": text, "content_blocks": [{"contents": calls}] if calls else []}}}]}]}
