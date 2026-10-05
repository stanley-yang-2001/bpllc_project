"""
Automated end-to-end routing tests (Step 10) — the Playground matrix, without the clicking.

Sends chat messages to your Langflow flow through its HTTP API, one fresh session per test
(a multi-turn session for the language-switching case), and checks each response with
routing_checks.py: right tool, right argument, reply identical to the tool output, story quality,
and the empty-vocabulary guard. It writes a readable report and a JSON file with every reply.

It changes your database only briefly and puts everything back:
  * Add Word tests use a throwaway word ("autotestapple") that is deleted afterwards,
  * the empty-vocabulary test snapshots the `words` table, empties it, and restores it in a
    `finally` block (also on Ctrl+C). If the process is killed hard, run with --restore-leftover.

Usage (flow id = the long id in the browser URL: localhost:7860/flow/<flow-id>):

    docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id <flow-id>

First time, check that the response is parsed correctly:

    docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id <flow-id> --only N1,S1 --debug

Useful options: --only A1,S2   --list   --repeat 3   --delay 20   --skip-empty-vocab
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


def run_flow(base_url, flow_id, api_key, message, session_id):
    return _request(
        "POST", f"{base_url}/api/v1/run/{flow_id}?stream=false",
        payload={"input_value": message, "input_type": "chat", "output_type": "chat", "session_id": session_id},
        headers={"x-api-key": api_key},
    )


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

# Its own name, so a manual backup called `words_snapshot` never blocks (or is mistaken for) a run.
SNAPSHOT_TABLE = "words_autotest_snapshot"


class VocabDb:
    def __init__(self):
        import story_tool

        self._st = story_tool

    def _run(self, *statements, fetch=None):
        conn = self._st.get_connection()
        try:
            with conn.cursor() as cur:
                result = None
                for sql, params in statements:
                    cur.execute(sql, params)
                if fetch:
                    result = cur.fetchone()
            conn.commit()
            return result
        finally:
            conn.close()

    def words(self):
        conn = self._st.get_connection()
        try:
            return self._st.load_words(conn)
        finally:
            conn.close()

    def snapshot_exists(self):
        row = self._run((f"SELECT to_regclass('{SNAPSHOT_TABLE}') IS NOT NULL", None), fetch=True)
        return bool(row and row[0])

    def snapshot_and_empty(self):
        self._run((f"CREATE TABLE {SNAPSHOT_TABLE} AS SELECT * FROM words", None), ("DELETE FROM words", None))

    def restore(self):
        """Merge the snapshot back. Nothing is deleted, so a word added since the snapshot
        survives, and no snapshot row can collide with a newer row's id."""
        self._run((f"INSERT INTO words (word, created_at) SELECT word, created_at FROM {SNAPSHOT_TABLE} "
                   "ON CONFLICT (word) DO NOTHING", None),
                  (f"DROP TABLE {SNAPSHOT_TABLE}", None))

    def remove_test_word(self):
        # case-insensitive: an older Add Word kept the original case ("AutoTestApple")
        self._run(("DELETE FROM words WHERE lower(word) = %s", (TEST_WORD,)))


# --- running ----------------------------------------------------------------------------------


def run_case(case, args, api_key, vocab, repeat_index, debug_state):
    session_id = f"autotest-{case['id']}-{repeat_index}-{int(time.time())}"
    turn_results = []
    for turn_no, spec in enumerate(case["turns"], 1):
        error, resp = None, None
        started = time.time()
        try:
            resp = run_flow(args.base_url, args.flow_id, api_key, spec["say"], session_id)
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


def main(argv=None, db_factory=VocabDb):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flow-id")
    parser.add_argument("--base-url", default="http://localhost:7860")
    parser.add_argument("--api-key")
    parser.add_argument("--only", help="comma-separated case ids, e.g. A1,S2")
    parser.add_argument("--repeat", type=int, default=1, help="repeat every case N times (fresh sessions)")
    parser.add_argument("--delay", type=float, default=15.0, help="seconds to wait after a story request (rate limit + cache)")
    parser.add_argument("--max-oov", type=int, default=2)
    parser.add_argument("--skip-empty-vocab", action="store_true")
    parser.add_argument("--restore-leftover", action="store_true", help="restore words from a leftover snapshot and exit")
    parser.add_argument("--debug", action="store_true", help="print the first raw response and how it was parsed")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    if args.list:
        for c in CASES:
            print(f"{c['id']:4} {c['name']}  ({len(c['turns'])} turn{'s' if len(c['turns']) > 1 else ''})")
        return 0
    if not args.flow_id and not args.restore_leftover:
        parser.error("--flow-id is required (the id in the browser URL: localhost:7860/flow/<flow-id>)")

    db = db_factory()
    if args.restore_leftover:
        if db.snapshot_exists():
            db.restore()
            print(f"Merged the saved words back into `words` from {SNAPSHOT_TABLE} (nothing was deleted).")
        else:
            print("No leftover snapshot; nothing to restore.")
        return 0
    if db.snapshot_exists():
        print(f"A leftover `{SNAPSHOT_TABLE}` table exists: a previous run was interrupted while the vocabulary was empty.\n"
              "Run again with --restore-leftover first. It merges the saved words back and deletes nothing,\n"
              "so words added since are kept. (A manual backup named `words_snapshot` is not touched.)")
        return 2

    vocab = db.words()
    if not vocab.strip():
        print("The vocabulary is empty; seed it first (Upload Word File).")
        return 2

    try:
        api_key = get_api_key(args.base_url, args.api_key)
    except ApiError as e:
        print(f"Authentication problem: {e}")
        return 2

    cases = selected_cases(args.only)
    normal = [c for c in cases if not c.get("needs_empty_vocab")]
    empty = [] if args.skip_empty_vocab else [c for c in cases if c.get("needs_empty_vocab")]
    results, debug_state = [], {"shown": False}
    print(f"Flow {args.flow_id} at {args.base_url}; vocabulary has {len(vocab.split(','))} entries.\n")

    try:
        db.remove_test_word()  # a clean start in case a previous run was interrupted
        for repeat in range(1, args.repeat + 1):
            db.remove_test_word()  # every repeat starts clean, so A1 can add the word again
            for case in normal:
                results.append({"case": case["id"], "name": case["name"], "repeat": repeat,
                                "turns": run_case(case, args, api_key, vocab, repeat, debug_state)})
    except KeyboardInterrupt:
        print("\nInterrupted; cleaning up.")
    finally:
        db.remove_test_word()

    if empty:
        try:
            db.snapshot_and_empty()
            for case in empty:
                for repeat in range(1, args.repeat + 1):
                    results.append({"case": case["id"], "name": case["name"], "repeat": repeat,
                                    "turns": run_case(case, args, api_key, "", repeat, debug_state)})
        except KeyboardInterrupt:
            print("\nInterrupted; restoring the vocabulary.")
        finally:
            if db.snapshot_exists():
                db.restore()
                print("(vocabulary restored)")

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
