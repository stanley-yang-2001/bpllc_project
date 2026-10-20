"""scripts/m3_check.py: the live check that the real tools are per-learner and fail closed (M3).

Two layers, because a check that cannot fail proves nothing (and because scripts/spike_tweaks.py once shipped with an option
nobody had run):
  * the pure judgements, case by case;
  * the whole script run as a COMMAND against a fake Langflow on a real socket. The fake executes the REAL tutor_core.tools
    against the REAL Postgres, so only Langflow and the Agent are faked. It is run healthy (must pass) and with each way a
    flow could be wrong (must fail): tools that ignore the learner, an Agent that controls the learner, an Agent that never
    calls a tool, a failing request, the developer fallback left on.

Needs the `tutor` schema (start the api once so its migrations have run). Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_m3_check.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg2

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

import m3_check as m3  # noqa: E402
from tutor_core import prompts, tools, vocab  # noqa: E402

DSN = os.environ.get("ADMIN_DATABASE_URL") or os.environ.get("DATABASE_URL") or "postgresql://langflow:langflow@postgres:5432/langflow"   # these create and delete learners
SCRIPT = "/app/scripts/m3_check.py"
failures = []
MODE = {"name": "healthy"}


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


# --- the pure judgements ----------------------------------------------------------------------------------------

def test_judgements():
    print("the judgements")
    P, F, I = m3.PASS, m3.FAIL, m3.INCONCLUSIVE
    refusal = "Couldn't add word: I don't know whose vocabulary this is."
    check("fail closed: refusal and nothing written passes", m3.judge_fail_closed(refusal, True, 0, False)[0] == P)
    check("fail closed: a row written fails", m3.judge_fail_closed(refusal, True, 1, False)[0] == F)
    check("fail closed: a success reply without a row still fails", m3.judge_fail_closed("Added 'x' to your English vocabulary.", True, 0, False)[0] == F)
    check("fail closed: no tool call is inconclusive", m3.judge_fail_closed("hi", False, 0, False)[0] == I)
    check("fail closed: the developer fallback makes it inconclusive, whatever else", m3.judge_fail_closed("Added", True, 1, True)[0] == I)
    seed_a, seed_b = {"es": ["hola"]}, {}
    ok = (seed_a, {"es": ["hola", m3.WORD_A]}, seed_b, {"fr": [m3.WORD_B]})
    check("parallel: each word gained in its own place passes (a seeded word does not matter)", m3.judge_parallel_adds(*ok, True, True)[0] == P)
    check("parallel: both words in A is MIXED UP", "MIXED UP" in m3.judge_parallel_adds(seed_a, {"es": ["hola", m3.WORD_A, m3.WORD_B]}, seed_b, {}, True, True)[1])
    check("parallel: A's word in B's list is MIXED UP", "MIXED UP" in m3.judge_parallel_adds(seed_a, {"es": ["hola"]}, seed_b, {"fr": [m3.WORD_A, m3.WORD_B]}, True, True)[1])
    check("parallel: a word in the wrong language fails", m3.judge_parallel_adds(seed_a, {"es": ["hola"], "en": [m3.WORD_A]}, seed_b, {"fr": [m3.WORD_B]}, True, True)[0] == F)
    check("parallel: a word that never arrived fails", m3.judge_parallel_adds(seed_a, {"es": ["hola"]}, seed_b, {"fr": [m3.WORD_B]}, True, True)[0] == F)
    check("parallel: a tool that was not called is inconclusive", m3.judge_parallel_adds(*ok, True, False)[0] == I)
    check("guard: the empty-vocabulary message passes", m3.judge_guard("You don't have any vocabulary yet! Tell me a word", True, m3.WORD_A)[0] == P)
    check("guard: a story fails", m3.judge_guard("Ana: Hola.", True, m3.WORD_A)[0] == F)
    check("guard: another learner's word in the reply fails first", "another learner's word" in m3.judge_guard(f"you have {m3.WORD_A}", True, m3.WORD_A)[1])
    check("guard: no tool call is inconclusive", m3.judge_guard("hi", False, m3.WORD_A)[0] == I)
    check("override: the other list untouched passes", m3.judge_override({"es": ["hola"]}, True)[0] == P)
    check("override: the word in the other list fails", m3.judge_override({"es": ["hola", m3.WORD_C]}, True)[0] == F)
    check("override: untouched but never tried is inconclusive", m3.judge_override({}, False)[0] == I)
    ck = [("a", m3.PASS, ""), ("b", m3.PASS, "")]
    check("verdict: all pass", m3.verdict_of(ck) == m3.PASS)
    check("verdict: one inconclusive is not a pass", m3.verdict_of(ck + [("c", m3.INCONCLUSIVE, "")]) == m3.INCONCLUSIVE)
    check("verdict: a failure beats everything", m3.verdict_of(ck + [("c", m3.INCONCLUSIVE, ""), ("d", m3.FAIL, "")]) == m3.FAIL)
    check("verdict: an error is a failure", m3.verdict_of(ck + [("c", m3.ERROR, "")]) == m3.FAIL)
    check("verdict: no checks is not a pass", m3.verdict_of([]) == m3.INCONCLUSIVE)


# --- a fake Langflow that runs the REAL tools -------------------------------------------------------------------

def connect():
    return psycopg2.connect(DSN)


class Groq:
    def __call__(self, prompt):
        return f"plan\n{prompts.DELIMITER}\nAna: Hola."


def block(name, args, text):
    return {"outputs": [{"outputs": [{"results": {"message": {"text": text, "content_blocks": [{"contents": [
        {"type": "tool_use", "id": uuid.uuid4().hex, "name": name, "tool_input": args, "output": text, "error": None}]}]}}}]}]}


def first_routing_learner():
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT min(id) FROM tutor.users WHERE email LIKE 'routing-%@routing-test.invalid'")
        return cur.fetchone()[0]


def agent(message, tweaks):
    mode = MODE["name"]
    cfg = next(iter(tweaks.values()), {}) if tweaks else {}
    learner, language = cfg.get("learner_id"), cfg.get("active_language")
    if mode == "shared_pool":                       # tools that ignore the learner and read one shared list
        learner = str(first_routing_learner())
    if mode == "agent_controls_learner":            # a flawed tool design: the learner comes from the Agent's words
        m = re.search(r"learner (\d+)", message)
        if m:
            learner = m.group(1)
    if mode == "skips_tools":
        return {"outputs": [{"outputs": [{"results": {"message": {"text": "Sure, done!", "content_blocks": []}}}]}]}
    m = re.match(r"Add the word (\S+)", message)
    if m:
        word = m.group(1)
        text = tools.add_word_for_agent(word, learner, language, connect=connect, env={})
        return block("add_word", {"word": word}, text)
    m = re.search(r"story in (\w+)", message)
    if m:
        if mode == "boom_on_story":
            raise RuntimeError("simulated failure")
        text = tools.story_for_agent(m.group(1), learner, language, connect=connect, env={}, call_groq_fn=Groq())
        return block("story_generator_tool", {"language": m.group(1)}, text)
    return {"outputs": [{"outputs": [{"results": {"message": {"text": "Hi!", "content_blocks": []}}}]}]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            data, code = agent(body["input_value"], body.get("tweaks")), 200
        except Exception as e:  # noqa: BLE001
            data, code = {"detail": str(e)}, 500
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def run_script(base, out, mode, env_extra=None, extra=()):
    MODE["name"] = mode
    env = {k: v for k, v in os.environ.items() if k not in ("TUTOR_DEV_USER_ID", "LANGFLOW_TWEAK_KEYS")}
    env["DATABASE_URL"] = DSN
    env.update(env_extra or {})
    return subprocess.run([sys.executable, SCRIPT, "--flow-id", "language-tutor", "--base-url", base, "--api-key", "fake", "--pause", "0",
                           "--out-dir", out, *extra], capture_output=True, text=True, timeout=180, env=env)


def routing_learners_left():
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM tutor.users WHERE email LIKE 'routing-%@routing-test.invalid'")
        return cur.fetchone()[0]


def lines_for(out, status, name):
    return re.search(rf"{status}\s+{re.escape(name)}", out) is not None


def test_the_command():
    print("the command, against a fake Langflow running the real tools")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    conn = connect()
    with conn.cursor() as cur:        # a real learner who happens to own a row for the test word: must not confuse or lose it
        cur.execute("INSERT INTO tutor.users (email, password_hash, display_name) VALUES (%s, 'x', 'bystander') RETURNING id", (f"bystander-{uuid.uuid4().hex[:8]}@example.com",))
        bystander = cur.fetchone()[0]
    conn.commit()
    vocab.add_word(conn, bystander, "es", m3.WORD_A)
    try:
        with tempfile.TemporaryDirectory() as out:
            r = run_script(base, out, "healthy")
            check("healthy tools: exit 0 and VERIFIED", r.returncode == 0 and "M3 TOOLS VERIFIED" in r.stdout, r.stdout[-700:] + r.stderr[-300:])
            names = ["fail closed (no learner given)", "parallel adds (two learners at once)", "empty learner gets no story built from others' words",
                     "a learner with Spanish words only gets no French story", "telling the Agent to write to another learner does not work", "cleanup"]
            check("every check passed, including cleanup", all(lines_for(r.stdout, "PASS", n) for n in names), r.stdout)
            check("the throwaway learners are gone", routing_learners_left() == 0)
            check("the bystander's own row for the test word was neither counted nor deleted", vocab.load_words(conn, bystander, "es") == [m3.WORD_A])
            saved = [f for f in os.listdir(out) if f.startswith("m3_check_")]
            data = json.load(open(os.path.join(out, saved[0]), encoding="utf-8"))
            check("the raw replies are saved, one per request", len(data["requests"]) == 6 and all("reply" in q for q in data["requests"]))
            sent = [q for q in data["requests"] if q["tag"].startswith("par-")]
            check("the two parallel requests were made as different learners in different languages",
                  len(sent) == 2 and sent[0]["learner_id"] != sent[1]["learner_id"] and {q["language"] for q in sent} == {"es", "fr"})

            r = run_script(base, out, "shared_pool")
            check("tools that ignore the learner: exit 1, NOT verified", r.returncode == 1 and "M3 NOT VERIFIED" in r.stdout, r.stdout[-400:])
            check("... the no-learner request is caught acting anyway", lines_for(r.stdout, "FAIL", "fail closed (no learner given)"), r.stdout)
            check("... and the mix-up between two learners is caught", lines_for(r.stdout, "FAIL", "parallel adds (two learners at once)") and "MIXED UP" in r.stdout, r.stdout)
            check("... and the learners are still cleaned up after a failing run", routing_learners_left() == 0)

            r = run_script(base, out, "agent_controls_learner")
            check("an Agent that can pick the learner: exit 1", r.returncode == 1 and lines_for(r.stdout, "FAIL", "telling the Agent to write to another learner does not work"), r.stdout[-500:])
            check("... while the checks that do not depend on it still pass", lines_for(r.stdout, "PASS", "fail closed (no learner given)") and lines_for(r.stdout, "PASS", "parallel adds (two learners at once)"))

            r = run_script(base, out, "skips_tools")
            check("an Agent that never calls a tool is INCONCLUSIVE, never a pass", r.returncode == 1 and "INCONCLUSIVE" in r.stdout and "M3 TOOLS VERIFIED" not in r.stdout, r.stdout[-500:])

            r = run_script(base, out, "boom_on_story")
            check("a failing request is an ERROR for its own step only", r.returncode == 1 and lines_for(r.stdout, "ERROR", "empty learner gets no story built from others' words")
                  and lines_for(r.stdout, "PASS", "parallel adds (two learners at once)"), r.stdout[-700:])
            check("... and the run still cleans up", routing_learners_left() == 0)

            r = run_script(base, out, "healthy", env_extra={"TUTOR_DEV_USER_ID": str(bystander)})
            check("with the developer fallback left on, check 1 is INCONCLUSIVE and says why",
                  r.returncode == 1 and lines_for(r.stdout, "INCONCLUSIVE", "fail closed (no learner given)") and "TUTOR_DEV_USER_ID" in r.stdout, r.stdout[-600:])

            r = run_script(base, out, "healthy", extra=("--tweak-keys", " , "))
            check("no tweak keys is refused before anything is created", r.returncode == 2 and "No tweak keys" in r.stdout and routing_learners_left() == 0, r.stdout)
            r = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True)
            check("--help lists --flow-id, --pause and --tweak-keys", all(x in r.stdout for x in ("--flow-id", "--pause", "--tweak-keys")))
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tutor.users WHERE id = %s", (bystander,))
        conn.commit()
        conn.close()
        server.shutdown()


def main():
    print("Running m3_check tests...\n")
    test_judgements()
    test_the_command()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
