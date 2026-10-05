"""
Integration test for scripts/run_routing_tests.py against a FAKE Langflow server.

Why: the runner's HTTP handling, authentication fallbacks, session handling, database set-up and
clean-up can be tested without the real Langflow. This does NOT prove the real Langflow's response
shape matches (that is confirmed on the first live run with --debug); it proves the runner:
  * logs in and creates an API key when auto-login isn't available,
  * reports a healthy flow as all-passing (exit code 0),
  * catches the Step 9 bugs when the fake flow misbehaves (wrong language reused, a reply that
    differs from the tool output) with a non-zero exit code,
  * adds and removes its test word, empties and restores the vocabulary (even after a failure),
  * refuses to run over a leftover snapshot, and can restore it.

Everything stays on localhost; no Groq, no database.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_routing_runner_with_fake_langflow.py
"""

import io
import json
import re
import sys
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

import run_routing_tests  # noqa: E402
from routing_checks import TEST_WORD  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []

STORIES = {
    "english": "Hello, I am Sam today.\nI want water.\nI see my friend near the house.\n"
               "I say please, can you give water?\nMy friend says yes and gives water.\nI say thank you.",
    "spanish": "Hola, soy Ana y digo hola.\nHoy tengo sed y quiero agua.\nLe pregunto a mi amigo si me da agua.\n"
               "Mi amigo dice si y me da agua.\nGracias, bebo y digo nos vemos manana.",
    "french": "Bonjour, je suis Marie et je dis bonjour.\nAujourd'hui j'ai soif et je veux de l'eau.\n"
              "Je demande de l'eau a mon ami.\nMon ami dit oui et me donne de l'eau.\nMerci, je dis a demain.",
    "japanese": "こんにちは、私はサムです。\n今日は水がほしいです。\n友達に会います。\n友達は水をくれます。\nありがとう、さようなら。",
}
GUARD = "You don't have any vocabulary yet! Add some words first."
STATE = {"words": set(), "bug": None, "last_language": {}, "key_created": False}


class FakeDb:
    snapshot = None

    def words(self):
        return ", ".join(sorted(STATE["words"]))

    def snapshot_exists(self):
        return FakeDb.snapshot is not None

    def snapshot_and_empty(self):
        FakeDb.snapshot = set(STATE["words"])
        STATE["words"].clear()

    def restore(self):  # merge: words added meanwhile are kept
        STATE["words"] |= FakeDb.snapshot
        FakeDb.snapshot = None

    def remove_test_word(self):
        STATE["words"].discard(TEST_WORD)


CALLS = {"n": 0}


def tool(name, args, output):
    CALLS["n"] += 1
    return {"type": "tool_use", "id": f"call-{CALLS['n']}", "name": name, "tool_input": args, "output": output, "error": None}


def build_response(text, blocks):
    if STATE["bug"] == "duplicate_blocks":  # Langflow showed each tool call twice in the response
        blocks = [b for blk in blocks for b in (blk, dict(blk))]
    return {"outputs": [{"outputs": [{"results": {"message": {"text": text, "content_blocks": blocks + [{"type": "text", "text": text}]}}}]}]}


def reply_for(message, session):
    low = message.lower()
    m = re.match(r"add the word (\S+)", low)
    if m:
        word = m.group(1)
        out = f"'{word}' is already in your vocabulary." if word in STATE["words"] else f"Added '{word}' to your vocabulary."
        STATE["words"].add(word)
        return build_response(out, [tool("add_word", {"word": m.group(1)}, out)])
    if "story" in low and ("in " in low):
        lang = "japanese" if "日本語" in message else re.search(r"in (\w+)", low).group(1)
        arg = lang.capitalize() if lang != "japanese" else "Japanese"
        shown_arg = arg
        if STATE["bug"] == "reuse_language" and STATE["last_language"].get(session):
            shown_arg = STATE["last_language"][session]  # the Step 9 bug: previous language reused
        STATE["last_language"][session] = arg
        out = GUARD if not STATE["words"] else STORIES.get(shown_arg.lower(), STORIES["english"])
        if STATE["bug"] == "english_in_spanish" and arg == "Spanish" and STATE["words"]:
            out = STORIES["english"]  # the model ignored the language
        text = out
        if STATE["bug"] == "rewrite_reply":
            text = out.splitlines()[0] + " ... (Note: intentionally short)"
        return build_response(text, [tool("story_generator_tool", {"language": shown_arg}, out)])
    if "story" in low:
        return build_response("Which language would you like?", [])
    return build_response("Hi! Ask me for a story or add a word.", [])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/v1/auto_login"):
            self._send(404, {"detail": "auto login disabled"})
        else:
            self._send(404, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        if self.path == "/api/v1/login":
            ok = "username=admin" in raw and "password=admin123" in raw
            return self._send(200, {"access_token": "jwt-test"}) if ok else self._send(401, {"detail": "bad login"})
        if self.path == "/api/v1/api_key/":
            if self.headers.get("Authorization") != "Bearer jwt-test":
                return self._send(401, {})
            STATE["key_created"] = True
            return self._send(200, {"api_key": "sk-test"})
        if self.path.startswith("/api/v1/run/"):
            if self.headers.get("x-api-key") != "sk-test":
                return self._send(403, {"detail": "invalid key"})
            body = json.loads(raw)
            return self._send(200, reply_for(body["input_value"], body["session_id"]))
        self._send(404, {})


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = run_routing_tests.main(argv, db_factory=FakeDb)
    return code, buf.getvalue()


def reset(bug=None):
    STATE.update(words={"hello", "goodbye", "please", "thank you", "yes", "no", "water", "food", "friend", "house", "today", "tomorrow"},
                 bug=bug, last_language={}, key_created=False)
    FakeDb.snapshot = None


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    common = ["--flow-id", "fake-flow", "--base-url", base, "--delay", "0", "--out", "/tmp/routing_test_out.json"]
    original_words = None
    try:
        print("Running runner-vs-fake-Langflow tests...\n")

        # healthy flow ------------------------------------------------------------------------
        reset()
        original_words = set(STATE["words"])
        code, out = run(common)
        check("a healthy flow passes every turn (exit code 0)", code == 0)
        check("the runner logged in and created an API key (auto-login was unavailable)", STATE["key_created"])
        check("the report lists all the cases' turns as PASS", "[FAIL]" not in out and out.count("[PASS]") >= 12)
        check("the throwaway word is removed afterwards", TEST_WORD not in STATE["words"])
        check("the vocabulary is restored after the empty-vocabulary test", STATE["words"] == original_words and FakeDb.snapshot is None)
        saved = json.load(open("/tmp/routing_test_out.json"))
        check("a JSON report is written with every reply", len(saved["results"]) >= 10 and saved["results"][0]["turns"][0]["reply"])

        # the Step 9 bug: previous language reused ---------------------------------------------
        reset("reuse_language")
        code, out = run(common + ["--only", "M1"])
        check("a reused language argument is caught (non-zero exit)", code == 1)
        check("the report names the failing check", "tool argument" in out and "[FAIL]" in out)

        # reply differs from tool output --------------------------------------------------------
        reset("rewrite_reply")
        code, out = run(common + ["--only", "S2"])
        check("a reply that differs from the tool output is caught", code == 1 and "reply equals tool output" in out)

        # cleanup survives failures ------------------------------------------------------------
        reset("rewrite_reply")
        original_words = set(STATE["words"])
        code, out = run(common)
        check("the database is still restored after failing tests", STATE["words"] == original_words and FakeDb.snapshot is None)

        # leftover snapshot protection -----------------------------------------------------------
        reset()
        FakeDb.snapshot = {"water", "friend"}
        STATE["words"] = set()
        code, out = run(common)
        check("a leftover snapshot stops the run (exit code 2) instead of risking data", code == 2 and "--restore-leftover" in out)
        code, out = run(["--restore-leftover"])
        check("--restore-leftover puts the words back", STATE["words"] == {"water", "friend"} and FakeDb.snapshot is None)
        FakeDb.snapshot = {"water"}
        STATE["words"] = {"newword"}
        run(["--restore-leftover"])
        check("--restore-leftover keeps words added since the snapshot (it merges)", STATE["words"] == {"newword", "water"})

        # misc options ---------------------------------------------------------------------------
        reset()
        code, out = run(["--list"])
        check("--list prints the cases", code == 0 and "M1" in out and "E1" in out)
        reset()
        code, out = run(common + ["--only", "N1,S1", "--skip-empty-vocab"])
        check("--only runs just the chosen cases", code == 0 and "N1" in out and "A1" not in out)
        reset()
        code, out = run(common + ["--api-key", "wrong", "--only", "N1"])
        check("a rejected API key is reported as a failed request, not a crash", code == 1 and "request" in out)

        # --repeat: the throwaway word must be cleaned up between repeats (found in the first live run)
        reset()
        code, out = run(common + ["--repeat", "2", "--only", "A1,A2,A3", "--skip-empty-vocab"])
        check("--repeat 2 passes on a healthy flow (A1 sees a clean state each repeat)", code == 0)

        # a story in the wrong language is caught (found in the first live run)
        reset("english_in_spanish")
        code, out = run(common + ["--only", "S2"])
        check("an English story for a Spanish request fails the run", code == 1 and "story quality" in out and "english" in out.lower())

        # the response listed every tool call twice
        reset("duplicate_blocks")
        code, out = run(common + ["--only", "S2", "--skip-empty-vocab"])
        saved = json.load(open("/tmp/routing_test_out.json"))
        check("duplicate tool calls in the response are recorded once", code == 0 and len(saved["results"][0]["turns"][0]["tool_calls"]) == 1)

        # latency is recorded per turn
        reset()
        run(common + ["--only", "N1", "--skip-empty-vocab"])
        saved = json.load(open("/tmp/routing_test_out.json"))
        check("each turn's latency is saved", isinstance(saved["results"][0]["turns"][0]["latency"], float))

        # the real database helper: names and SQL (a manual `words_snapshot` backup must not interfere)
        executed = []

        class Cur:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def execute(self, sql, params=None): executed.append((" ".join(sql.split()), params))
            def fetchone(self): return (False,)

        class Conn:
            def cursor(self): return Cur()
            def commit(self): pass
            def close(self): pass

        fake_story_tool = type("ST", (), {"get_connection": staticmethod(lambda: Conn())})
        real_db = object.__new__(run_routing_tests.VocabDb)
        real_db._st = fake_story_tool
        real_db.snapshot_and_empty()
        executed_before_restore = len(executed)
        real_db.restore()
        restore_sql = " | ".join(q for q, _ in executed[executed_before_restore:])
        real_db.remove_test_word(); real_db.snapshot_exists()
        sql = " | ".join(q for q, _ in executed)
        check("the runner's snapshot has its own table name, not the manual words_snapshot", "words_autotest_snapshot" in sql and "words_snapshot" not in sql.replace("words_autotest_snapshot", ""))
        check("restoring merges missing words back instead of replacing the table (nothing added meanwhile is lost)",
              "INSERT INTO words (word, created_at) SELECT word, created_at FROM words_autotest_snapshot ON CONFLICT (word) DO NOTHING" in sql
              and "DELETE" not in restore_sql.upper().replace("ON CONFLICT (WORD) DO NOTHING", ""))
        check("the throwaway word is removed case-insensitively", any("lower(word) = %s" in q for q, _ in executed))
    finally:
        server.shutdown()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
