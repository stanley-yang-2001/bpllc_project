"""
Automated end-to-end routing tests (Step 10) — the Playground matrix, without the clicking.

Sends chat messages to your Langflow flow through its HTTP API, one fresh session per test
(a multi-turn session for the language-switching case), and checks each response with
routing_checks.py: right tool, right argument, reply identical to the tool output, story quality,
and the empty-vocabulary guard. It writes a readable report and a JSON file with every reply.

It never touches a real learner's data. It creates two THROWAWAY learners for the run: one "full" learner seeded with a few
words in English, Spanish, French and Japanese, and one "empty" learner with no words (for the empty-vocabulary test).
Every request is sent as one of them through Langflow tweaks (`learner_id` as a string, `active_language`): the same
mechanism the site uses, so this run also checks that the real tools read the learner they are given. Both learners
(and their words, by cascade) are deleted in a `finally` block, also on Ctrl+C. If the process is killed hard, the
leftovers are harmless; remove them with --cleanup-leftover.

Usage (flow id = the long id in the browser URL: localhost:7860/flow/<flow-id>):

    docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id <flow-id>

First time, check that the response is parsed correctly:

    docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id <flow-id> --only N1,S1 --debug

Useful options: --only A1,S2   --list   --repeat 3   --delay 20   --skip-empty-vocab   --cleanup-leftover
--tweak-keys  the tweak keys of the Add Word and Story Generator Tool nodes (default $LANGFLOW_TWEAK_KEYS, else the
              node ids in flows/language-tutor.json)
Authentication: --api-key / $LANGFLOW_API_KEY, otherwise it logs in with $LANGFLOW_SUPERUSER /
$LANGFLOW_SUPERUSER_PASSWORD (set in docker-compose.yml) and creates an API key named
"step10-routing-tests" (delete old ones under Settings -> Langflow API Keys if they pile up).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

from routing_checks import (  # noqa: E402
    CASES,
    TEST_WORD,
    evaluate_turn,
    final_text,
    find_tool_calls,
    with_tool_blocks,
    _walk_tool_dicts,
)


# --- HTTP helpers ------------------------------------------------------------------------------


class ApiError(Exception):
    pass


def _request(method, url, payload=None, headers=None, form=None, timeout=120):
    data, hdrs = None, dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise ApiError(f"HTTP {e.code} from {method} {url}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        raise ApiError(f"cannot reach {url}: {e.reason}")


def get_api_key(base_url, explicit=None):
    key = explicit or os.environ.get("LANGFLOW_API_KEY")
    if key:
        return key
    token = None
    try:
        token = _request("GET", f"{base_url}/api/v1/auto_login").get("access_token")
    except ApiError:
        pass
    if not token:
        user = os.environ.get("LANGFLOW_SUPERUSER", "admin")
        password = os.environ.get("LANGFLOW_SUPERUSER_PASSWORD", "admin123")
        try:
            token = _request("POST", f"{base_url}/api/v1/login", form={"username": user, "password": password})["access_token"]
        except (ApiError, KeyError) as e:
            raise ApiError(f"could not log in as {user!r} ({e}). Pass --api-key or set LANGFLOW_API_KEY "
                           "(create one under Settings -> Langflow API Keys).")
    created = _request("POST", f"{base_url}/api/v1/api_key/", payload={"name": "step10-routing-tests"},
                       headers={"Authorization": f"Bearer {token}"})
    if "api_key" not in created:
        raise ApiError(f"unexpected response creating an API key: {str(created)[:200]}")
    return created["api_key"]


DEFAULT_TWEAK_KEYS = "AddWord-WhP5g,StoryGeneratorTool-RQpvc"      # node ids in flows/language-tutor.json (verified in M0)


def build_tweaks(keys, learner_id, language):
    """What the site sends: the learner id as a STRING (Langflow silently drops other types on a text field) and the
    active language, for each tool node. The hidden inputs are learner_id and active_language."""
    return {key: {"learner_id": str(learner_id), "active_language": language} for key in keys}


def run_flow(base_url, flow_id, api_key, message, session_id, tweaks=None):
    payload = {"input_value": message, "input_type": "chat", "output_type": "chat", "session_id": session_id}
    if tweaks:
        payload["tweaks"] = tweaks
    return _request("POST", f"{base_url}/api/v1/run/{flow_id}?stream=false", payload=payload, headers={"x-api-key": api_key})


def stored_tool_blocks(base_url, api_key, session_id):
    """Best effort: tool calls from Langflow's stored messages for the session (the fallback when
    the run response doesn't carry them). Returns [] on any problem."""
    try:
        msgs = _request("GET", f"{base_url}/api/v1/monitor/messages?session_id={urllib.parse.quote(session_id)}",
                        headers={"x-api-key": api_key})
    except ApiError:
        return []
    if not isinstance(msgs, list):
        return []
    machine = [m for m in msgs if str(m.get("sender", "")).lower() in ("machine", "ai")]
    blocks = []
    if machine:
        _walk_tool_dicts(machine[-1], blocks)
    return blocks


# --- database (kept small so it can be faked in tests) -------------------------------------------

# Words for the throwaway "full" learner: enough for the matrix's English, Spanish, French and Japanese stories.
SEED_WORDS = {
    "en": ["hello", "water", "friend", "house", "today", "book", "bread", "mother", "father", "eat", "drink", "thank you"],
    "es": ["hola", "agua", "amigo", "casa", "pan", "madre", "libro", "gracias"],
    "fr": ["bonjour", "eau", "ami", "maison", "pain", "m\u00e8re", "livre", "merci"],
    "ja": ["\u307f\u305a", "\u3044\u3048", "\u3068\u3082\u3060\u3061", "\u307b\u3093", "\u3042\u308a\u304c\u3068\u3046", "\u3053\u3093\u306b\u3061\u306f"],
}
# A domain that cannot exist, so --cleanup-leftover can never match a real learner's address.
LEARNER_DOMAIN = "routing-test.invalid"


class LearnerDb:
    """Throwaway learners for a run. Only ever touches rows it created itself (by id), or, for --cleanup-leftover, rows
    whose address ends in the reserved routing-test.invalid domain."""

    def __init__(self):
        from tutor_core import db, vocab

        self._connect, self._vocab, self._created = db.connect, vocab, []

    def _run(self, sql, params=None, fetch=False):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() if fetch else None
            conn.commit()
            return rows
        finally:
            conn.close()

    def create(self, label):
        import uuid

        email = f"routing-{label}-{uuid.uuid4().hex[:10]}@{LEARNER_DOMAIN}"
        row = self._run("INSERT INTO tutor.users (email, password_hash, display_name) VALUES (%s, 'x', %s) RETURNING id",
                        (email, f"routing {label}"), fetch=True)
        self._created.append(row[0][0])
        return row[0][0]

    def seed(self, learner_id, words_by_language):
        conn = self._connect()
        try:
            for language, words in words_by_language.items():
                for word in words:
                    self._vocab.add_word(conn, learner_id, language, word)
        finally:
            conn.close()

    def words(self, learner_id, language="en"):
        conn = self._connect()
        try:
            return ", ".join(self._vocab.load_words(conn, learner_id, language))
        finally:
            conn.close()

    def remove_test_word(self, learner_id, language="en"):
        # case-insensitive, and only this learner's own entry
        self._run("DELETE FROM tutor.words WHERE user_id = %s AND language = %s AND lower(word) = %s",
                  (learner_id, language, TEST_WORD))

    def cleanup(self):
        """Delete the learners this run created (their words and languages go with them)."""
        if self._created:
            self._run("DELETE FROM tutor.users WHERE id = ANY(%s)", (list(self._created),))
            self._created = []

    def leftover_ids(self):
        rows = self._run("SELECT id FROM tutor.users WHERE email LIKE %s", (f"routing-%@{LEARNER_DOMAIN}",), fetch=True)
        return [r[0] for r in rows]

    def cleanup_leftover(self):
        ids = self.leftover_ids()
        if ids:
            self._run("DELETE FROM tutor.users WHERE id = ANY(%s)", (ids,))
        return len(ids)


# --- running ----------------------------------------------------------------------------------


def run_case(case, args, api_key, vocab, repeat_index, debug_state, tweaks=None):
    session_id = f"autotest-{case['id']}-{repeat_index}-{int(time.time())}"
    turn_results = []
    for turn_no, spec in enumerate(case["turns"], 1):
        error, resp = None, None
        started = time.time()
        try:
            resp = run_flow(args.base_url, args.flow_id, api_key, spec["say"], session_id, tweaks)
            latency = time.time() - started
            if spec.get("tool") not in (None, "either") and not find_tool_calls(resp):
                blocks = stored_tool_blocks(args.base_url, api_key, session_id)
                if blocks:
                    resp = with_tool_blocks(resp, blocks)
        except ApiError as e:
            error = str(e)
            latency = time.time() - started

        if args.debug and not debug_state["shown"] and resp is not None:
            debug_state["shown"] = True
            print("\n--- DEBUG: first raw response (truncated) ---")
            print(json.dumps(resp, ensure_ascii=False, indent=2)[:3500])
            print("--- DEBUG: parsed -> reply:", repr(final_text(resp))[:200])
            print("--- DEBUG: parsed -> tool calls:", json.dumps(find_tool_calls(resp), ensure_ascii=False)[:600], "---\n")

        checks = evaluate_turn(spec, resp, vocab, error=error, max_oov=args.max_oov)
        turn_results.append({"turn": turn_no, "say": spec["say"], "latency": latency, "reply": final_text(resp) if resp else "",
                             "tool_calls": find_tool_calls(resp) if resp else [], "checks": checks})
        report_turn(case, turn_no, len(case["turns"]), spec, checks)
        story_turn = spec.get("tool") in ("story", "either")
        time.sleep(args.delay if story_turn else min(2.0, args.delay))
    return turn_results


def report_turn(case, turn_no, n_turns, spec, checks):
    label = f"{case['id']}" + (f".{turn_no}" if n_turns > 1 else "")
    failed = [c for c in checks if not c["ok"] and not c.get("info")]
    status = "FAIL" if failed else "PASS"
    print(f"[{status}] {label:5} {case['name'] if n_turns == 1 else spec['say']}")
    for c in checks:
        if not c["ok"] or c.get("info"):
            mark = "info" if c.get("info") else "  x "
            print(f"         {mark} {c['check']}: {c['detail']}")


def selected_cases(only):
    if not only:
        return list(CASES)
    wanted = {x.strip().upper() for x in only.split(",") if x.strip()}
    chosen = [c for c in CASES if c["id"].upper() in wanted]
    unknown = wanted - {c["id"].upper() for c in CASES}
    if unknown:
        raise SystemExit(f"unknown case id(s): {sorted(unknown)}; use --list")
    return chosen


def main(argv=None, db_factory=LearnerDb):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flow-id")
    parser.add_argument("--base-url", default="http://localhost:7860")
    parser.add_argument("--api-key")
    parser.add_argument("--only", help="comma-separated case ids, e.g. A1,S2")
    parser.add_argument("--repeat", type=int, default=1, help="repeat every case N times (fresh sessions)")
    parser.add_argument("--delay", type=float, default=15.0, help="seconds to wait after a story request (rate limit + cache)")
    parser.add_argument("--max-oov", type=int, default=5)
    parser.add_argument("--skip-empty-vocab", action="store_true")
    parser.add_argument("--cleanup-leftover", action="store_true",
                        help="delete throwaway routing learners left by an interrupted run, and exit")
    parser.add_argument("--tweak-keys", default=None,
                        help="tweak keys of the Add Word and Story Generator Tool nodes, comma-separated "
                             "(default $LANGFLOW_TWEAK_KEYS, else the node ids in flows/language-tutor.json)")
    parser.add_argument("--debug", action="store_true", help="print the first raw response and how it was parsed")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    if args.list:
        for c in CASES:
            print(f"{c['id']:4} {c['name']}  ({len(c['turns'])} turn{'s' if len(c['turns']) > 1 else ''})")
        return 0
    if not args.flow_id and not args.cleanup_leftover:
        parser.error("--flow-id is required (the id in the browser URL: localhost:7860/flow/<flow-id>)")

    db = db_factory()
    if args.cleanup_leftover:
        print(f"Removed {db.cleanup_leftover()} throwaway routing learner(s) left by an interrupted run.")
        return 0
    leftovers = db.leftover_ids()
    if leftovers:
        print(f"Note: {len(leftovers)} throwaway routing learner(s) from an interrupted run are still in the database "
              "(harmless). Remove them with --cleanup-leftover.\n")

    try:
        api_key = get_api_key(args.base_url, args.api_key)
    except ApiError as e:
        print(f"Authentication problem: {e}")
        return 2

    keys = tuple(k.strip() for k in (args.tweak_keys or os.environ.get("LANGFLOW_TWEAK_KEYS") or DEFAULT_TWEAK_KEYS).split(",") if k.strip())
    if not keys:
        print("No tweak keys: the tools could not tell the learners apart. Give --tweak-keys (or set LANGFLOW_TWEAK_KEYS).")
        return 2

    cases = selected_cases(args.only)
    normal = [c for c in cases if not c.get("needs_empty_vocab")]
    empty = [] if args.skip_empty_vocab else [c for c in cases if c.get("needs_empty_vocab")]
    results, debug_state = [], {"shown": False}

    try:                                    # everything below runs as throwaway learners, deleted in the finally
        full = db.create("full")
        db.seed(full, SEED_WORDS)
        empty_learner = db.create("empty") if empty else None
        vocab = db.words(full, "en")
        print(f"Flow {args.flow_id} at {args.base_url}; learner {full} has {len(vocab.split(','))} English words"
              + (f", learner {empty_learner} has none" if empty_learner else "") + f"; tweak keys: {', '.join(keys)}.\n")
        full_tweaks = build_tweaks(keys, full, "en")

        for repeat in range(1, args.repeat + 1):
            db.remove_test_word(full)       # every repeat starts clean, so A1 can add the word again
            for case in normal:
                results.append({"case": case["id"], "name": case["name"], "repeat": repeat,
                                "turns": run_case(case, args, api_key, vocab, repeat, debug_state, full_tweaks)})
        if empty:
            empty_tweaks = build_tweaks(keys, empty_learner, "en")
            for case in empty:
                for repeat in range(1, args.repeat + 1):
                    results.append({"case": case["id"], "name": case["name"], "repeat": repeat,
                                    "turns": run_case(case, args, api_key, "", repeat, debug_state, empty_tweaks)})
    except KeyboardInterrupt:
        print("\nInterrupted; cleaning up.")
    finally:
        db.cleanup()
        print("(throwaway learners removed)")

    total_turns = sum(len(r["turns"]) for r in results)
    failed_turns = sum(1 for r in results for t in r["turns"] if any(not c["ok"] and not c.get("info") for c in t["checks"]))
    failed_cases = sorted({r["case"] for r in results for t in r["turns"] if any(not c["ok"] and not c.get("info") for c in t["checks"])})
    print(f"\nTurns: {total_turns - failed_turns}/{total_turns} passed" + (f"   Failing cases: {', '.join(failed_cases)}" if failed_cases else ""))
    lat = sorted(t["latency"] for r in results for t in r["turns"] if t.get("latency") is not None)
    if lat:
        print(f"Turn latency (Agent + tool + relay), {len(lat)} turns: p50 {lat[len(lat) // 2]:.1f}s, "
              f"p90 {lat[min(len(lat) - 1, int(len(lat) * 0.9))]:.1f}s")

    out = args.out or f"/app/scripts/routing_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"flow_id": args.flow_id, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out}")
    return 1 if failed_turns else 0


if __name__ == "__main__":
    sys.exit(main())
