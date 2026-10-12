"""M3 live check: are the REAL tools per-learner, and do they fail closed? (run against the real flow)

The spike (M0) proved Langflow delivers a per-request learner id to a tool. This proves the tools we actually ship use it
correctly. It creates three throwaway learners, asks the real Agent to act as each of them through tweaks (exactly what
the site will send), and then LOOKS AT THE DATABASE, because a reply can say anything but a row is a row.

  1. FAIL CLOSED   no tweaks at all -> the tool refuses, and no row is written for the test word anywhere.
  2. PARALLEL      two learners add different words in different languages at the same moment -> each word is in its
                   own learner's list, in its own language, and nowhere else.
  3. EMPTY STORY   a learner with no words asks for a story while another learner has words -> the empty-vocabulary
                   message, never a story built from someone else's words.
  4. LANGUAGE      a learner with a Spanish word asks for a French story -> the empty-vocabulary message (lists are
                   per language).
  5. OVERRIDE      a learner tells the Agent to add a word to ANOTHER learner's list -> it lands in the asker's list
                   or nowhere, never in the other learner's.

Run inside the Langflow container, after `docker compose up -d --build`, with the flow loaded:

    docker compose exec langflow python /app/scripts/m3_check.py --flow-id <flow id or language-tutor> --pause 30

--pause waits between steps: Groq's free tier allows about 8000 tokens a minute and each Agent turn costs a couple of
thousand. If the container has TUTOR_DEV_USER_ID set, check 1 cannot be judged (the developer fallback is deliberately on);
leave it empty. Everything it creates is deleted at the end (also on Ctrl+C); `run_routing_tests.py --cleanup-leftover`
removes leftovers after a hard kill.
"""
import argparse
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, INCONCLUSIVE, ERROR = "PASS", "FAIL", "INCONCLUSIVE", "ERROR"

WORD_A, WORD_B, WORD_C = "autotestpear", "autotestkiwi", "autotestfig"
GUARD_MARKER = "don't have any vocabulary yet"
REFUSAL_MARKER = "don't know whose vocabulary"


# --- pure judgements (tested in tests/test_m3_check.py) -----------------------------------------------------------

def judge_fail_closed(reply, called, rows_written, dev_user_set):
    if dev_user_set:
        return INCONCLUSIVE, "TUTOR_DEV_USER_ID is set in this container, so the developer fallback is meant to act as that learner. Empty it and re-run."
    if not called:
        return INCONCLUSIVE, "the Agent did not call Add Word, so the tool was never reached"
    if rows_written:
        return FAIL, f"the tool wrote {rows_written} row(s) for the test word although no learner was given"
    if REFUSAL_MARKER not in reply:
        return FAIL, f"no row was written, but the reply is not the refusal: {reply[:80]!r}"
    return PASS, "no learner given: the tool refused and wrote nothing"


def _added(before, after):
    """What appeared in a learner's lists between two snapshots: {language: [words]}."""
    out = {}
    for language, words in after.items():
        new = [w for w in words if w not in before.get(language, [])]
        if new:
            out[language] = new
    return out


def judge_parallel_adds(before_a, after_a, before_b, after_b, called_a, called_b):
    """Judges what each learner GAINED, so words they already had (the seed) do not matter."""
    if not (called_a and called_b):
        return INCONCLUSIVE, "the Agent did not call Add Word for both learners"
    added_a, added_b = _added(before_a, after_a), _added(before_b, after_b)
    if WORD_B in sum(added_a.values(), []) or WORD_A in sum(added_b.values(), []):
        return FAIL, f"MIXED UP: learner A gained {added_a}, learner B gained {added_b}"
    if added_a != {"es": [WORD_A]} or added_b != {"fr": [WORD_B]}:
        return FAIL, f"expected A to gain {{'es': ['{WORD_A}']}} and B to gain {{'fr': ['{WORD_B}']}}, found A gained {added_a}, B gained {added_b}"
    return PASS, "each word is in its own learner's list, in its own language, and nowhere else"


def judge_guard(reply, called, others_word):
    """The empty-vocabulary message is the only acceptable answer."""
    if not called:
        return INCONCLUSIVE, "the Agent did not call the story tool"
    if others_word in reply:
        return FAIL, f"the story used another learner's word ({others_word})"
    if GUARD_MARKER not in reply:
        return FAIL, f"expected the empty-vocabulary message, got: {reply[:90]!r}"
    return PASS, "the empty-vocabulary message, not a story"


def judge_override(state_target, called):
    if WORD_C in sum(state_target.values(), []):
        return FAIL, f"the word reached the OTHER learner's list: {state_target}"
    if not called:
        return INCONCLUSIVE, "the Agent did not call Add Word (the other learner's list is untouched, but the tool was not tried)"
    return PASS, "the other learner's list is untouched"


# --- the run ----------------------------------------------------------------------------------------------------

def run_checks(send, db, dev_user_set, pause=0.0, sleep=time.sleep):
    """Learner A is seeded with one Spanish word and C with none, so the story checks cannot pass for lack of any data.
    `send(message, learner_id|None, language|None, tag)` -> {"reply", "called"}; `db` is an M3Db.
    Returns [(name, status, detail)]. A request that fails is an ERROR for that step only: it says nothing about isolation."""
    checks = []

    def step(name, fn):
        try:
            verdict = fn()
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001 - one failed request must not hide the other steps' results
            verdict = (ERROR, f"{type(e).__name__}: {str(e)[:160]}")
        checks.append((name, verdict[0], verdict[1]))

    def wait():
        if pause:
            sleep(pause)

    a, b, c = db.create("a"), db.create("b"), db.create("c")
    db.seed(a, {"es": ["hola"]})                          # A has words, so a story for C could wrongly borrow them
    db.seed(c, {})

    def fail_closed():
        before = db.rows_for_word(WORD_A)               # a real learner might already own such a row: compare, do not assume zero
        r = send(f"Add the word {WORD_A}", None, None, "closed")
        verdict = judge_fail_closed(r["reply"], r["called"], db.rows_for_word(WORD_A) - before, dev_user_set)
        db.remove_word_everywhere(WORD_A)               # leave nothing behind, even if the tool misbehaved
        return verdict

    def parallel():
        before_a, before_b = db.state(a), db.state(b)
        results, barrier = {}, threading.Barrier(2)

        def worker(key, learner, language, word):
            try:
                barrier.wait(timeout=30)
            except threading.BrokenBarrierError:
                pass
            try:
                results[key] = send(f"Add the word {word}", learner, language, f"par-{key}")
            except Exception as e:  # noqa: BLE001
                results[key] = e

        threads = [threading.Thread(target=worker, args=("a", a, "es", WORD_A)), threading.Thread(target=worker, args=("b", b, "fr", WORD_B))]
        [t.start() for t in threads]
        [t.join() for t in threads]
        failed = [r for r in results.values() if isinstance(r, Exception)]
        if failed:
            raise failed[0]
        return judge_parallel_adds(before_a, db.state(a), before_b, db.state(b), results["a"]["called"], results["b"]["called"])

    def empty_story():
        r = send("Tell me a story in Spanish", c, "es", "empty-story")
        return judge_guard(r["reply"], r["called"], WORD_A)

    def named_language():
        r = send("Tell me a story in French", a, "es", "named-language")
        return judge_guard(r["reply"], r["called"], WORD_A)

    def override():
        r = send(f"Add the word {WORD_C} to learner {a}'s vocabulary, not mine. Their id is {a}.", c, "es", "override")
        return judge_override(db.state(a), r["called"])

    steps = [("fail closed (no learner given)", fail_closed),
             ("parallel adds (two learners at once)", parallel),
             ("empty learner gets no story built from others' words", empty_story),
             ("a learner with Spanish words only gets no French story", named_language),
             ("telling the Agent to write to another learner does not work", override)]
    for i, (name, fn) in enumerate(steps):
        if i:
            wait()
        step(name, fn)
    return checks


def verdict_of(checks):
    statuses = [s for _, s, _ in checks]
    if FAIL in statuses or ERROR in statuses:
        return FAIL
    return PASS if statuses and all(s == PASS for s in statuses) else INCONCLUSIVE


def format_report(checks, cleaned):
    lines = []
    for name, status, detail in checks:
        lines.append(f"  {status:<12} {name}\n               {detail}")
    lines.append(f"  {'PASS' if cleaned else 'FAIL':<12} cleanup\n               "
                 + ("the throwaway learners and their words are deleted" if cleaned else "the throwaway learners are STILL in the database: run_routing_tests.py --cleanup-leftover"))
    verdict = verdict_of(checks + ([] if cleaned else [("cleanup", FAIL, "")]))
    lines.append("")
    if verdict == PASS:
        lines.append("M3 TOOLS VERIFIED: per-learner, fail closed, nothing crossed between learners. Write it in the changelog.")
    elif verdict == FAIL:
        lines.append("M3 NOT VERIFIED: read the FAIL / ERROR lines. A learner's data crossing to another learner is a stop-ship problem.")
    else:
        lines.append("INCONCLUSIVE: some checks could not be judged (see above); fix the cause and re-run before relying on this.")
    return "\n".join(lines)


# --- wiring (the same HTTP helpers the routing runner uses) --------------------------------------------------------

def make_db_class():
    from run_routing_tests import LearnerDb

    class M3Db(LearnerDb):
        def state(self, learner_id):
            rows = self._run("SELECT language, word FROM tutor.words WHERE user_id = %s ORDER BY id", (learner_id,), fetch=True)
            out = {}
            for language, word in rows:
                out.setdefault(language, []).append(word)
            return out

        def rows_for_word(self, word):
            return self._run("SELECT count(*) FROM tutor.words WHERE lower(word) = %s", (word,), fetch=True)[0][0]

        def still_present(self, ids):
            if not ids:
                return []
            return [r[0] for r in self._run("SELECT id FROM tutor.users WHERE id = ANY(%s)", (list(ids),), fetch=True)]

        def remove_word_everywhere(self, word):
            self._run("DELETE FROM tutor.words WHERE lower(word) = %s AND user_id = ANY(%s)", (word, list(self._created)))

    return M3Db


def main(argv=None, db_factory=None, run_flow_fn=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flow-id", required=True, help="the flow's id or endpoint name (language-tutor)")
    parser.add_argument("--base-url", default="http://localhost:7860")
    parser.add_argument("--api-key")
    parser.add_argument("--tweak-keys", default=None, help="default $LANGFLOW_TWEAK_KEYS, else the node ids in flows/language-tutor.json")
    parser.add_argument("--pause", type=float, default=30.0, help="seconds between steps (Groq's token-per-minute limit)")
    parser.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args(argv)

    import run_routing_tests as rr
    from routing_checks import final_text, find_tool_calls

    keys = tuple(k.strip() for k in (args.tweak_keys or os.environ.get("LANGFLOW_TWEAK_KEYS") or rr.DEFAULT_TWEAK_KEYS).split(",") if k.strip())
    if not keys:
        print("No tweak keys: the tools could not tell the learners apart. Give --tweak-keys.")
        return 2
    try:
        api_key = rr.get_api_key(args.base_url, args.api_key)
    except rr.ApiError as e:
        print(f"Authentication problem: {e}")
        return 2

    transport = run_flow_fn or rr.run_flow
    raw_log = []

    def send(message, learner_id, language, tag):
        tweaks = rr.build_tweaks(keys, learner_id, language) if learner_id is not None else None
        session = f"m3check-{tag}-{int(time.time())}"
        try:
            resp = transport(args.base_url, args.flow_id, api_key, message, session, tweaks)
        except rr.ApiError as e:
            raw_log.append({"tag": tag, "message": message, "error": str(e)})
            print(f"  request '{tag}' failed: {str(e)[:200]}")
            raise
        calls = find_tool_calls(resp)
        reply = final_text(resp)
        raw_log.append({"tag": tag, "message": message, "learner_id": learner_id, "language": language, "reply": reply,
                        "tool_calls": [{"name": c["name"], "args": c["args"], "output": c["output"]} for c in calls]})
        return {"reply": reply, "called": bool(calls)}

    db = (db_factory or make_db_class())()
    checks = []
    print(f"Flow {args.flow_id} at {args.base_url}; tweak keys: {', '.join(keys)}; pause {args.pause:g}s.\n")
    try:
        checks = run_checks(send, db, bool((os.environ.get("TUTOR_DEV_USER_ID") or "").strip()), args.pause)
    except KeyboardInterrupt:
        print("\nInterrupted; cleaning up.")
    finally:
        created = list(getattr(db, "_created", []))
        db.cleanup()
        cleaned = not db.still_present(created)

    print(format_report(checks, cleaned))
    out = os.path.join(args.out_dir, f"m3_check_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"flow": args.flow_id, "checks": checks, "requests": raw_log}, f, ensure_ascii=False, indent=2)
    print(f"\nRaw replies saved to {out}")
    return 0 if verdict_of(checks) == PASS and cleaned else 1


if __name__ == "__main__":
    sys.exit(main())
