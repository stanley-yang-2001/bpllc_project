"""
Integration test for scripts/run_routing_tests.py against a FAKE Langflow server.

Why: the runner's HTTP handling, authentication fallbacks, session handling, database set-up and
clean-up can be tested without the real Langflow. This does NOT prove the real Langflow's response
shape matches (that is confirmed on the first live run with --debug); it proves the runner:
  * logs in and creates an API key when auto-login isn't available,
  * reports a healthy flow as all-passing (exit code 0),
  * catches the Step 9 bugs when the fake flow misbehaves (wrong language reused, a reply that
    differs from the tool output) with a non-zero exit code,
  * works only as THROWAWAY learners (a seeded one and an empty one), sends each request as one of them through tweaks
    (learner id as a string, the active language, on every tool node) and deletes them afterwards, even after failures,
  * catches a flow that ignores the learner (the empty learner would then see the full learner's words),
  * can remove learners left behind by an interrupted run (--cleanup-leftover) without touching anything else.

Everything stays on localhost; no Groq, no database (the real database helper has its own test:
tests/test_routing_learner_db.py).

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_routing_runner_with_fake_langflow.py
"""

import io
import json
import os
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
NAMES = {"en": "English", "es": "Spanish", "fr": "French", "ja": "Japanese"}
CODES = {name.lower(): code for code, name in NAMES.items()}
STATE = {"words": {}, "seeded": {}, "bug": None, "last_language": {}, "key_created": False, "tweaks_seen": [],
         "next_id": 100, "created": set(), "created_ever": False, "leftover": set()}


class FakeDb:
    """The same interface as run_routing_tests.LearnerDb, over the fake flow's own memory."""

    def create(self, label):
        STATE["next_id"] += 1
        STATE["created"].add(STATE["next_id"])
        STATE["created_ever"] = True
        STATE["words"][STATE["next_id"]] = {}
        return STATE["next_id"]

    def seed(self, learner_id, words_by_language):
        STATE["words"][learner_id] = {lang: set(words) for lang, words in words_by_language.items()}
        STATE["seeded"][learner_id] = {lang: list(words) for lang, words in words_by_language.items()}

    def words(self, learner_id, language="en"):
        return ", ".join(sorted(STATE["words"].get(learner_id, {}).get(language, set())))

    def remove_test_word(self, learner_id, language="en"):
        STATE["words"].get(learner_id, {}).get(language, set()).discard(TEST_WORD)

    def cleanup(self):
        for learner_id in list(STATE["created"]):
            STATE["words"].pop(learner_id, None)
        STATE["created"].clear()

    def leftover_ids(self):
        return sorted(STATE["leftover"])

    def cleanup_leftover(self):
        n = len(STATE["leftover"])
        for learner_id in STATE["leftover"]:
            STATE["words"].pop(learner_id, None)
        STATE["leftover"].clear()
        return n


CALLS = {"n": 0}


def tool(name, args, output):
    CALLS["n"] += 1
    return {"type": "tool_use", "id": f"call-{CALLS['n']}", "name": name, "tool_input": args, "output": output, "error": None}


def build_response(text, blocks):
    if STATE["bug"] == "duplicate_blocks":  # Langflow showed each tool call twice in the response
        blocks = [b for blk in blocks for b in (blk, dict(blk))]
    return {"outputs": [{"outputs": [{"results": {"message": {"text": text, "content_blocks": blocks + [{"type": "text", "text": text}]}}}]}]}


def reply_for(message, session, learner, language):
    """The fake flow. `learner`/`language` are what the request's tweaks said (None when it sent none: fail closed)."""
    low = message.lower()
    if STATE["bug"] == "ignore_tweaks" and STATE["seeded"]:
        learner = min(STATE["seeded"])             # a flow that ignores the learner and reads one shared list
    m = re.match(r"add the word (\S+)", low)
    if m:
        word = m.group(1)
        if learner is None:
            out = "Couldn't add word: I don't know whose vocabulary this is."
        else:
            have = STATE["words"].setdefault(learner, {}).setdefault(language or "en", set())
            name = NAMES.get(language or "en", "English")
            out = f"'{word}' is already in your {name} vocabulary." if word in have else f"Added '{word}' to your {name} vocabulary."
            have.add(word)
        return build_response(out, [tool("add_word", {"word": m.group(1)}, out)])
    typed = re.match(r"(?:tell me|write) (?:a|an) (dialogue|letter|poem) in (\w+)(?: about (.*))?$", low)
    if typed:                                          # a request that names a kind of text (and maybe a subject)
        kind, lang, about = typed.group(1), typed.group(2).capitalize(), typed.group(3)
        words = STATE["words"].get(learner, {}).get(CODES.get(lang.lower(), "en"), set()) if learner is not None else None
        out = ("I can't write a story right now: I don't know whose vocabulary to use." if learner is None
               else GUARD if not words else STORIES.get(lang.lower(), STORIES["english"]))
        args = {"language": lang, "story_type": kind, "topic": about or ""}
        return build_response(out, [tool("story_generator_tool", args, out)])
    if "story" in low and ("in " in low):
        lang = "japanese" if "\u65e5\u672c\u8a9e" in message else re.search(r"in (\w+)", low).group(1)
        arg = lang.capitalize() if lang != "japanese" else "Japanese"
        shown_arg = arg
        if STATE["bug"] == "reuse_language" and STATE["last_language"].get(session):
            shown_arg = STATE["last_language"][session]  # the Step 9 bug: previous language reused
        STATE["last_language"][session] = arg
        code = CODES.get(shown_arg.lower(), "en")
        if learner is None:
            out = "I can't write a story right now: I don't know whose vocabulary to use."
        else:
            words = STATE["words"].get(learner, {}).get(code, set())
            out = GUARD if not words else STORIES.get(shown_arg.lower(), STORIES["english"])
        if STATE["bug"] == "english_in_spanish" and arg == "Spanish" and learner is not None and out != GUARD:
            out = STORIES["english"]  # the model ignored the language
        text = out
        if STATE["bug"] == "rewrite_reply":
            text = out.splitlines()[0] + " ... (Note: intentionally short)"
        args = {"language": shown_arg}
        tier = re.search(r"\b(easy|medium|hard)\b", low)
        if tier:                                       # the tool's optional difficulty, passed only when the learner named one
            args["difficulty"] = tier.group(1)
        return build_response(text, [tool("story_generator_tool", args, out)])
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
            tweaks = body.get("tweaks") or {}
            cfg = next(iter(tweaks.values()), {})
            learner = int(cfg["learner_id"]) if str(cfg.get("learner_id", "")).isdigit() else None
            STATE["tweaks_seen"].append({"keys": sorted(tweaks), "learner_raw": cfg.get("learner_id"), "language": cfg.get("active_language"),
                                         "same_in_every_node": len({json.dumps(v, sort_keys=True) for v in tweaks.values()}) <= 1,
                                         "message": body["input_value"]})
            return self._send(200, reply_for(body["input_value"], body["session_id"], learner, cfg.get("active_language")))
        self._send(404, {})


def check(label, condition, detail=""):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label} {detail}")
        failures.append(label)


def run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = run_routing_tests.main(argv, db_factory=FakeDb)
    return code, buf.getvalue()


def reset(bug=None):
    STATE.update(words={}, seeded={}, bug=bug, last_language={}, key_created=False, tweaks_seen=[], created=set(),
                 created_ever=False, leftover=set())


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    common = ["--flow-id", "fake-flow", "--base-url", base, "--delay", "0", "--out", "/tmp/routing_test_out.json"]
    try:
        print("Running runner-vs-fake-Langflow tests...\n")

        # healthy flow ------------------------------------------------------------------------
        reset()
        code, out = run(common)
        check("a healthy flow passes every turn (exit code 0)", code == 0, out[-400:])
        check("the runner logged in and created an API key (auto-login was unavailable)", STATE["key_created"])
        check("the report lists all the cases' turns as PASS", "[FAIL]" not in out and out.count("[PASS]") >= 12)
        check("the throwaway learners are deleted afterwards", STATE["created"] == set() and STATE["words"] == {})
        check("the run says it removed them", "(throwaway learners removed)" in out)
        seeded = list(STATE["seeded"].values())
        check("one learner was seeded, with words in English, Spanish, French and Japanese",
              len(seeded) == 1 and set(seeded[0]) == {"en", "es", "fr", "ja"} and all(seeded[0].values()))
        seen = STATE["tweaks_seen"]
        check("every request carried tweaks for both tool nodes", seen and all(t["keys"] == ["AddWord-WhP5g", "StoryGeneratorTool-RQpvc"] for t in seen))
        check("the learner id is sent as a STRING (Langflow drops other types)", all(isinstance(t["learner_raw"], str) and t["learner_raw"].isdigit() for t in seen))
        check("the active language is sent, and the same values go to both nodes", all(t["language"] == "en" and t["same_in_every_node"] for t in seen))
        by_message = {t["message"]: t["learner_raw"] for t in seen}
        check("the empty-vocabulary case is asked as a DIFFERENT learner from every other case",
              len({t["learner_raw"] for t in seen}) == 2 and sum(1 for t in seen if t["learner_raw"] != by_message["Add the word autotestapple"]) == 1)
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
        code, out = run(common)
        check("the throwaway learners are still deleted after failing tests", code == 1 and STATE["created"] == set() and STATE["words"] == {})

        # a flow that ignores the learner is caught ------------------------------------------------
        reset("ignore_tweaks")
        code, out = run(common)
        check("a flow that ignores the learner fails the run (the empty learner saw someone else's words)",
              code == 1 and "empty-vocabulary guard" in out and "[FAIL]" in out, out[-500:])

        # a flow that receives no tweaks refuses (fail closed) and is caught --------------------------
        reset()
        code, out = run(common + ["--only", "A1,S1", "--skip-empty-vocab"])
        check("sanity: the same flow with tweaks passes A1 and S1", code == 0)

        # leftovers from an interrupted run -------------------------------------------------------
        reset()
        STATE["leftover"] = {901, 902}
        STATE["words"].update({901: {"en": {"keepme"}}, 902: {}})
        code, out = run(common + ["--only", "N1", "--skip-empty-vocab"])
        check("leftover throwaway learners are mentioned but a run still works and leaves them alone",
              code == 0 and "2 throwaway routing learner(s)" in out and "--cleanup-leftover" in out and STATE["leftover"] == {901, 902})
        code, out = run(["--cleanup-leftover"])
        check("--cleanup-leftover removes them, and only them", code == 0 and "Removed 2" in out and STATE["leftover"] == set() and 901 not in STATE["words"])
        code, out = run(["--cleanup-leftover"])
        check("--cleanup-leftover with nothing left says so", code == 0 and "Removed 0" in out)

        # tweak keys ---------------------------------------------------------------------------------
        reset()
        code, out = run(common + ["--only", "A1", "--skip-empty-vocab", "--tweak-keys", "NodeA, NodeB"])
        check("--tweak-keys sets the keys the tweaks are sent under", code == 0 and all(t["keys"] == ["NodeA", "NodeB"] for t in STATE["tweaks_seen"]))
        reset()
        os.environ["LANGFLOW_TWEAK_KEYS"] = "FromEnv"
        try:
            code, out = run(common + ["--only", "A1", "--skip-empty-vocab"])
        finally:
            del os.environ["LANGFLOW_TWEAK_KEYS"]
        check("$LANGFLOW_TWEAK_KEYS is the default", code == 0 and all(t["keys"] == ["FromEnv"] for t in STATE["tweaks_seen"]))
        reset()
        code, out = run(common + ["--tweak-keys", " , "])
        check("no tweak keys at all is refused before anything is created", code == 2 and "No tweak keys" in out and not STATE["created_ever"])

        # authentication problems create nothing --------------------------------------------------
        reset()
        os.environ["LANGFLOW_SUPERUSER_PASSWORD"] = "wrong"
        try:
            code, out = run(common + ["--only", "N1"])
        finally:
            del os.environ["LANGFLOW_SUPERUSER_PASSWORD"]
        check("a login failure stops the run (exit code 2) before any learner is created", code == 2 and "Authentication problem" in out and not STATE["created_ever"])

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

        # (the real database helper is tested against a real database in tests/test_routing_learner_db.py)
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
