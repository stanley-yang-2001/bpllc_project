"""Chat on a learner's own model, end to end (docs/CUSTOM-MODEL-DESIGN.md section 10): does the real stack keep the learner's key in the API?

It starts a small fake model provider (an OpenAI-style /chat/completions that follows a script), signs up throwaway learners, saves
the fake as one learner's own model, and then checks, through the real API and the real Langflow flow:

  1. SETUP      the learner can save the fake provider as their model (needs ALLOW_PRIVATE_MODEL_URLS=1 for this run).
  2. GREETING   a plain chat turn is answered by the fake provider, and every call it received carried the learner's real key and
                the saved model name: never the throwaway token Langflow was given.
  3. STORY      "tell me a story" makes the Agent call the Story Generator Tool, and the tool's own model call also reached the fake
                provider (through the API) with the real key.
  4. CONTROL    a learner who is not switched on is answered by the shared model and the fake provider hears nothing.
  5. WRONG KEY  when the provider refuses the key, the chat says to check the key (own_model_failed) and does NOT fall back to
                the shared model.
  6. AT REST    the real key is found in no table of the database (Langflow's messages, transactions and vertex builds included).

Needs the stack up with CHAT_OWN_MODEL=1, ALLOW_PRIVATE_MODEL_URLS=1 and a MODEL_KEY_SECRET (run-checks.bat adds them for this
check with docker-compose.own-model-check.yml and puts the stack back afterwards), AI_MODE=live and a Groq key (the control turn
uses the shared model). Run inside the api container:

    docker compose -f docker-compose.yml -f docker-compose.own-model-check.yml up -d api
    docker compose exec api python scripts/own_model_chat_check.py
    docker compose up -d api          # back to normal
"""
import argparse
import http.cookiejar
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PASSWORD = "Own-model-check-" + secrets.token_hex(6)
MODEL = "own-model-check-1"
MARKER = "OWN-MODEL-CHECK"
DELIMITER = "===STORY==="
DIALOGUE = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye, friend."
WORDS = ["hello", "goodbye", "please", "water", "friend", "house", "today", "bread"]


# --- the fake provider ------------------------------------------------------------------------------------------------------

def message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return ""


def decide(body: dict) -> dict:
    """What the scripted provider answers: {"kind": "tool" | "tool_call" | "final" | "plain", "text", "tool", "args"}."""
    messages = [m for m in body.get("messages", []) if isinstance(m, dict)]
    everything = " ".join(message_text(m) for m in messages)
    tools = [t.get("function", {}).get("name", "") for t in body.get("tools") or [] if isinstance(t, dict)]
    if DELIMITER in everything and not tools:
        return {"kind": "tool", "text": "Plan: a short chat\n" + DELIMITER + "\n" + DIALOGUE}      # the Story Generator Tool's own call
    if tools and messages and messages[-1].get("role") == "tool":
        return {"kind": "final", "text": f"{MARKER}: here is your text."}
    last_user = next((message_text(m) for m in reversed(messages) if m.get("role") == "user"), "")
    story_tool = next((n for n in tools if "story" in n.lower()), None)
    if tools and story_tool and "story" in last_user.lower():
        return {"kind": "tool_call", "tool": story_tool, "args": {"language": "English"}}
    return {"kind": "plain", "text": f"{MARKER}: hello from the fake provider."}


def completion(model: str, answer: dict) -> dict:
    message = {"role": "assistant", "content": answer.get("text")}
    finish = "stop"
    if answer["kind"] == "tool_call":
        message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_check1", "type": "function",
                   "function": {"name": answer["tool"], "arguments": json.dumps(answer["args"])}}]}
        finish = "tool_calls"
    return {"id": "chatcmpl-check", "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "finish_reason": finish, "message": message}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def stream_parts(model: str, answer: dict) -> list:
    def chunk(delta, finish=None):
        body = {"id": "chatcmpl-check", "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        return f"data: {json.dumps(body)}\n\n".encode()
    if answer["kind"] == "tool_call":
        first = {"role": "assistant", "content": None, "tool_calls": [{"index": 0, "id": "call_check1", "type": "function",
                 "function": {"name": answer["tool"], "arguments": ""}}]}
        args = {"tool_calls": [{"index": 0, "function": {"arguments": json.dumps(answer["args"])}}]}
        return [chunk(first), chunk(args), chunk({}, "tool_calls"), b"data: [DONE]\n\n"]
    return [chunk({"role": "assistant", "content": ""}), chunk({"content": answer["text"]}), chunk({}, "stop"), b"data: [DONE]\n\n"]


class FakeProvider:
    """Records every request (who asked, with which key and model, what kind of call) and answers by `decide`. A request without
    `expected_key` as its bearer is refused with 401, like a provider that does not know the key."""

    def __init__(self, expected_key: str, host="127.0.0.1", port=0):
        self.expected_key, self.calls, self._lock = expected_key, [], threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                auth = self.headers.get("Authorization", "")
                answer = decide(body)
                with outer._lock:
                    outer.calls.append({"path": self.path, "authorization": auth, "model": str(body.get("model", "")), "kind": answer["kind"],
                                        "stream": bool(body.get("stream"))})
                if auth != f"Bearer {outer.expected_key}":
                    data = json.dumps({"error": {"message": "Incorrect API key provided.", "type": "invalid_request_error"}}).encode()
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                model = str(body.get("model", ""))
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for part in stream_parts(model, answer):
                        self.wfile.write(part)
                        self.wfile.flush()
                    return
                data = json.dumps(completion(model, answer)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def snapshot(self) -> list:
        with self._lock:
            return list(self.calls)


# --- the API client and the report ------------------------------------------------------------------------------------------

class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, timeout=240):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "X-Requested-With": "tutor"})
        try:
            with self.opener.open(req, timeout=timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"error": {"message": raw.decode("utf-8", "replace")[:300]}}


class Report:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, ok))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)
        return ok

    @property
    def failed(self):
        return [n for n, ok in self.rows if not ok]


def error_of(body) -> dict:
    return (body or {}).get("error") or {} if isinstance(body, dict) else {}


def with_retry(call, delay=20):
    """The shared model may say "busy" (429): wait as long as the API says (at least `delay`) and try again, up to four times."""
    status, body = call()
    for _ in range(4):
        if status != 429:
            break
        time.sleep(max(delay, (error_of(body).get("retry_after") or 0) + 5))
        status, body = call()
    return status, body


def session_id() -> str:
    return secrets.token_hex(16)


# --- database scan ----------------------------------------------------------------------------------------------------------

def scan_for(connect, needle: str) -> list:
    """Every "schema.table.column" whose text contains `needle` (JSON columns are searched as text). Reads only."""
    sql = ("SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
           "AND data_type IN ('text', 'character varying', 'json', 'jsonb') ORDER BY 1, 2, 3")
    hits = []
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = cur.fetchall()
        for schema, table, column in columns:
            ident = lambda s: '"' + s.replace('"', '""') + '"'      # noqa: E731
            with conn.cursor() as cur:
                cur.execute(f"SELECT 1 FROM {ident(schema)}.{ident(table)} WHERE {ident(column)}::text LIKE %s LIMIT 1", ("%" + needle + "%",))
                if cur.fetchone():
                    hits.append(f"{schema}.{table}.{column}")
    finally:
        conn.close()
    return hits


# --- the checks -------------------------------------------------------------------------------------------------------------

def sign_up(base, label):
    c = Client(base)
    email = f"check-{secrets.token_hex(5)}@own-model-check.invalid"
    status, body = c.call("POST", "/api/auth/register", {"email": email, "password": PASSWORD, "display_name": label, "language": "en", "accept_privacy": True})
    if status != 201:
        sys.exit(f"could not create the throwaway learner ({status}): {body}")
    return c, email


def switch_on(connect, email):
    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE tutor.users SET custom_model_enabled = true WHERE email = %s", (email,))
    finally:
        conn.close()


def chat(c, message):
    return with_retry(lambda: c.call("POST", "/api/chat", {"message": message, "language": "en", "session_id": session_id()}))


def run_checks(base, connect, fake_host="127.0.0.1", settle=8.0, retry_delay=20.0) -> Report:
    rep = Report()
    key = f"own-model-check-key-{secrets.token_hex(8)}"
    created = []
    with FakeProvider(key) as fake:
        a, email_a = sign_up(base, "Own model check A")
        created.append((a, email_a))
        b, email_b = sign_up(base, "Own model check B")
        created.append((b, email_b))
        try:
            switch_on(connect, email_a)
            for w in WORDS:
                a.call("POST", "/api/words", {"language": "en", "word": w})
                b.call("POST", "/api/words", {"language": "en", "word": w})
            status, body = a.call("PUT", "/api/me/model", {"model": MODEL, "base_url": f"http://{fake_host}:{fake.port}/v1", "api_key": key})
            if not rep.check("SETUP   the fake provider can be saved as the learner's model", status == 200, f"HTTP {status} {error_of(body).get('message', '')}"):
                print("          Run this through run-checks.bat (or with docker-compose.own-model-check.yml): it needs ALLOW_PRIVATE_MODEL_URLS=1 and MODEL_KEY_SECRET.")
                return rep

            # GREETING
            status, body = chat(a, "Hello! Reply with one short sentence.")
            calls = fake.snapshot()
            reply = (body or {}).get("reply", "") if status == 200 else ""
            if status == 503 and error_of(body).get("code") == "langflow_unavailable":
                rep.check("GREETING live chat is switched on in this stack", False, "the chat tutor is off: set LANGFLOW_API_KEY and LANGFLOW_PER_USER_TOOLS=1 in .env first")
                return rep
            if status == 200 and not calls:
                rep.check("GREETING a plain turn is answered by the learner's own model", False,
                          "the fake provider heard nothing: is CHAT_OWN_MODEL=1 in the API, and was Langflow rebuilt with the new flow?")
            else:
                rep.check("GREETING a plain turn is answered by the learner's own model", status == 200 and MARKER in reply, f"HTTP {status}: {reply[:80] or error_of(body).get('message', '')}")
            rep.check("GREETING every call to the provider carried the real key and the saved model name",
                      bool(calls) and all(c["authorization"] == f"Bearer {key}" and c["model"] == MODEL for c in calls),
                      f"{len(calls)} call(s); keys seen: {sorted({c['authorization'][:14] for c in calls})}")
            rep.check("GREETING no throwaway token reached the provider", not any("tt-" in c["authorization"] for c in calls))

            # STORY
            before = len(fake.snapshot())
            status, body = chat(a, "Tell me a short story in English.")
            new = fake.snapshot()[before:]
            tool_calls = (body or {}).get("tool_calls", []) if status == 200 else []
            story = [t for t in tool_calls if "story" in str(t.get("name", "")).lower()]
            rep.check("STORY    the Agent called the Story Generator Tool", bool(story), f"HTTP {status}; tools: {[t.get('name') for t in tool_calls]}; {error_of(body).get('message', '')}")
            rep.check("STORY    the story is the one the learner's own model wrote", bool(story) and "Ana: Hello, friend." in story[0].get("output", ""),
                      (story[0].get("output", "") if story else "")[:80])
            rep.check("STORY    the tool's own model call also went to the provider, with the real key",
                      any(c["kind"] == "tool" and c["authorization"] == f"Bearer {key}" for c in new), f"kinds seen: {[c['kind'] for c in new]}")

            # CONTROL
            heard = len(fake.snapshot())
            status, body = chat(b, "Hello! Reply with one short sentence.")
            rep.check("CONTROL  a learner who is not switched on is answered by the shared model", status == 200 and bool((body or {}).get("reply")),
                      f"HTTP {status} {error_of(body).get('message', '')}")
            rep.check("CONTROL  the provider heard nothing from that learner", len(fake.snapshot()) == heard)

            # WRONG KEY
            fake.expected_key = key + "-changed"
            heard = len(fake.snapshot())
            status, body = chat(a, "Hello again! Reply with one short sentence.")
            err = error_of(body)
            # The refusal may end the turn (HTTP 502, own_model_failed) or, if the Agent covers for the failed call, come back with the
            # answer and a notice. Either way it must name the key and must not be answered by the shared model.
            said = err.get("message", "") if status != 200 else (body or {}).get("notice") or ""
            refused = (status == 502 and err.get("code") == "own_model_failed") or (status == 200 and bool((body or {}).get("notice")))
            rep.check("WRONG KEY the chat says the provider refused, and does not fall back to the shared model",
                      refused and "Check the key" in said, f"HTTP {status} {err.get('code')}: {said[:100]}")
            rep.check("WRONG KEY the provider was asked (so the refusal was real)", len(fake.snapshot()) > heard)
            rep.check("WRONG KEY the real key is not in the error", key not in json.dumps(body))

            # AT REST
            time.sleep(settle)                     # Langflow writes some records a moment after it answers
            hits = scan_for(connect, key)
            rep.check("AT REST  the real key is in no table of the database", not hits, "found in: " + ", ".join(hits) if hits else "")
        finally:
            for client, email in created:
                s, _ = client.call("POST", "/api/me/delete", {"password": PASSWORD})
                print(f"throwaway learner {email} " + ("deleted" if s == 204 else f"NOT deleted ({s}); delete it by hand"))
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000", help="API address as seen from where the script runs")
    ap.add_argument("--db-url", default=os.environ.get("DATABASE_URL", ""), help="the database the API uses (default $DATABASE_URL)")
    ap.add_argument("--fake-host", default="127.0.0.1", help="the address the API uses to reach this script's fake provider")
    ap.add_argument("--settle", type=float, default=8.0, help="seconds to wait before searching the database")
    ap.add_argument("--delay", type=float, default=20.0, help="minimum seconds to wait when the shared model says it is busy")
    a = ap.parse_args(argv)
    if not a.db_url:
        sys.exit("No database address: pass --db-url or run inside the api container (it has DATABASE_URL).")
    import psycopg2
    rep = run_checks(a.base, lambda: psycopg2.connect(a.db_url), a.fake_host, a.settle, a.delay)
    print(f"\n{len(rep.rows) - len(rep.failed)} of {len(rep.rows)} checks passed")
    for name in rep.failed:
        print(f"  FAILED: {name}")
    return 0 if rep.rows and not rep.failed else 1


if __name__ == "__main__":
    sys.exit(main())
