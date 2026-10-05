"""
Tests for scripts/routing_checks.py — the pure logic behind the automated routing tests
(scripts/run_routing_tests.py), which replace most of the manual Playground matrix.

The checks encode the failures actually seen in Step 9:
  * the Agent passing the WRONG language (copying the previous turn's),
  * the Agent refusing / answering without calling the tool,
  * the reply differing from the tool's Result (the relay problem),
  * a story that breaks the vocabulary / format rules,
  * an invented story instead of the empty-vocabulary message.

Written BEFORE the module. The synthetic responses below mimic Langflow's /api/v1/run output
(a chat message whose content_blocks hold the tool calls); the REAL response shape is confirmed
on the first live run (run_routing_tests.py --debug).

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_routing_checks.py
"""

import sys

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

from routing_checks import (  # noqa: E402
    CASES,
    evaluate_turn,
    final_text,
    find_tool_calls,
    with_tool_blocks,
)

PASS = "PASS"
FAIL = "FAIL"
failures = []

VOCAB = "hello, goodbye, please, thank you, yes, no, water, food, friend, house, today, tomorrow"

ENGLISH_STORY = (
    "Hello, I am Sam today.\nI want water.\nI see my friend near the house.\n"
    "I say please, can you give water?\nMy friend says yes and gives water.\nI say thank you."
)
SPANISH_STORY = (
    "Hola, soy Ana y digo hola.\nHoy tengo sed y quiero agua.\nLe pregunto a mi amigo si me da agua.\n"
    "Mi amigo dice si y me da agua.\nGracias, bebo y digo nos vemos manana."
)


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def tool_block(name, args, output, error=None):
    return {"type": "tool_use", "name": name, "tool_input": args, "output": output, "error": error}


def response(final, *tool_blocks, nested=False):
    """A /api/v1/run style response. `nested` wraps tool calls in a ContentBlock-like dict."""
    if nested and tool_blocks:
        blocks = [{"title": "Agent Steps", "contents": list(tool_blocks)}]
    else:
        blocks = list(tool_blocks)
    blocks.append({"type": "text", "text": final})
    return {
        "session_id": "s1",
        "outputs": [{"outputs": [{"results": {"message": {"text": final, "content_blocks": blocks}}}]}],
    }


def results_by_name(checks):
    return {c["check"]: c for c in checks}


# --- parsing ---------------------------------------------------------------------------------


def test_final_text_shapes():
    check("final text from results.message.text", final_text(response("Hello there")) == "Hello there")
    r = {"outputs": [{"outputs": [{"results": {"message": {"data": {"text": "From data"}}}}]}]}
    check("final text from results.message.data.text", final_text(r) == "From data")
    r = {"outputs": [{"outputs": [{"outputs": {"message": {"message": "From outputs"}}}]}]}
    check("final text from outputs.message.message", final_text(r) == "From outputs")
    check("garbage input gives an empty string", final_text({}) == "" and final_text(None) == "")


def test_find_tool_calls():
    calls = find_tool_calls(response("x", tool_block("story_generator_tool", {"language": "Spanish"}, SPANISH_STORY)))
    check("a flat tool call is found with its name, args and output",
          len(calls) == 1 and calls[0]["name"] == "story_generator_tool"
          and calls[0]["args"] == {"language": "Spanish"} and calls[0]["output"] == SPANISH_STORY)
    calls = find_tool_calls(response("x", tool_block("add_word", {"word": "bread"}, "Added", ), nested=True))
    check("a tool call wrapped in a ContentBlock is found too", len(calls) == 1 and calls[0]["name"] == "add_word")
    check("no tool call -> empty list", find_tool_calls(response("hi")) == [])
    calls = find_tool_calls(response("x", tool_block("t", {}, {"text": "wrapped"})))
    check("a structured output is unwrapped to text", calls[0]["output"] == "wrapped")


def test_with_tool_blocks():
    bare = response("Hola")
    bare["outputs"][0]["outputs"][0]["results"]["message"]["content_blocks"] = []
    fixed = with_tool_blocks(bare, [tool_block("story_generator_tool", {"language": "Spanish"}, "story")])
    check("tool blocks can be injected into a response that lacked them", len(find_tool_calls(fixed)) == 1)
    check("the original response is not modified", find_tool_calls(bare) == [])


# --- evaluating one turn ---------------------------------------------------------------------


STORY_SPEC = {"say": "Tell me a story in Spanish", "tool": "story",
              "arg": {"key": "language", "any_of": ["spanish", "español"]}, "story": "other"}


def test_a_good_story_turn_passes_every_check():
    resp = response(SPANISH_STORY, tool_block("story_generator_tool", {"language": "Spanish"}, SPANISH_STORY))
    checks = evaluate_turn(STORY_SPEC, resp, VOCAB)
    check("every check passes for a correct story turn", all(c["ok"] for c in checks))


def test_wrong_language_argument_is_caught():
    resp = response(ENGLISH_STORY, tool_block("story_generator_tool", {"language": "English"}, ENGLISH_STORY))
    c = results_by_name(evaluate_turn(STORY_SPEC, resp, VOCAB))
    check("the Step 9 bug (previous language reused) fails the argument check", not c["tool argument"]["ok"])


def test_no_tool_call_is_caught():
    resp = response("I can only generate stories in languages other than English.")
    c = results_by_name(evaluate_turn(STORY_SPEC, resp, VOCAB))
    check("answering without calling the story tool fails", not c["tool called"]["ok"])


def test_reply_that_differs_from_the_tool_output_is_caught():
    resp = response("Hola, soy Ana ... (Note: short)", tool_block("story_generator_tool", {"language": "Spanish"}, SPANISH_STORY))
    c = results_by_name(evaluate_turn(STORY_SPEC, resp, VOCAB))
    check("the relay check fails when the reply is not the tool's output", not c["reply equals tool output"]["ok"])


def test_english_story_quality_uses_the_vocabulary_rules():
    spec = {"say": "Tell me a story in English", "tool": "story",
            "arg": {"key": "language", "any_of": ["english"]}, "story": "english"}
    good = response(ENGLISH_STORY, tool_block("story_generator_tool", {"language": "English"}, ENGLISH_STORY))
    check("a clean English story passes the quality check", results_by_name(evaluate_turn(spec, good, VOCAB))["story quality"]["ok"])
    bad_text = "Hello, I bake bread and share cake with neighbors at the market. I eat. I drink. Yes. No."
    bad = response(bad_text, tool_block("story_generator_tool", {"language": "English"}, bad_text))
    check("an English story full of stray words fails the quality check", not results_by_name(evaluate_turn(spec, bad, VOCAB))["story quality"]["ok"])


def test_no_tool_expected():
    spec = {"say": "hi", "tool": None}
    check("a greeting answered without a tool passes",
          all(c["ok"] for c in evaluate_turn(spec, response("Hi! Ask me for a story or add a word."), VOCAB)))
    resp = response("Hello", tool_block("story_generator_tool", {"language": "English"}, "story text"))
    check("calling a tool for a greeting fails", not results_by_name(evaluate_turn(spec, resp, VOCAB))["tool called"]["ok"])
    check("an empty reply fails", not results_by_name(evaluate_turn(spec, response(""), VOCAB))["reply not empty"]["ok"])


def test_add_word_turns():
    spec = {"say": "Add the word autotestapple", "tool": "add_word",
            "arg": {"key": "word", "any_of": ["autotestapple"]}, "reply_any": ["added"]}
    ok = response("Added 'autotestapple' to your vocabulary.",
                  tool_block("add_word", {"word": "autotestapple"}, "Added 'autotestapple' to your vocabulary."))
    check("a correct add-word turn passes", all(c["ok"] for c in evaluate_turn(spec, ok, VOCAB)))
    upper = response("'autotestapple' is already in your vocabulary.",
                     tool_block("add_word", {"word": "AutoTestApple"}, "'autotestapple' is already in your vocabulary."))
    spec2 = dict(spec, reply_any=["already"])
    check("argument comparison ignores case", all(c["ok"] for c in evaluate_turn(spec2, upper, VOCAB)))
    wrong = response("Added 'banana'.", tool_block("add_word", {"word": "banana"}, "Added 'banana'."))
    check("the wrong word argument fails", not results_by_name(evaluate_turn(spec, wrong, VOCAB))["tool argument"]["ok"])
    check("a reply missing the expected wording fails",
          not results_by_name(evaluate_turn(dict(spec, reply_any=["already"]), ok, VOCAB))["reply wording"]["ok"])


def test_empty_vocabulary_guard():
    spec = {"say": "Tell me a story in English", "tool": "story", "expect_guard": True,
            "arg": {"key": "language", "any_of": ["english"]}}
    msg = "You don't have any vocabulary yet! Add some words first."
    good = response(msg, tool_block("story_generator_tool", {"language": "English"}, msg))
    check("the empty-vocabulary message passes the guard check", results_by_name(evaluate_turn(spec, good, ""))["empty-vocabulary guard"]["ok"])
    invented = response(ENGLISH_STORY, tool_block("story_generator_tool", {"language": "English"}, msg))
    check("an invented story instead of the message fails the guard check",
          not results_by_name(evaluate_turn(spec, invented, ""))["empty-vocabulary guard"]["ok"])


def test_info_cases_never_fail():
    spec = {"say": "Tell me a story", "tool": "either", "info": True}
    checks = evaluate_turn(spec, response("Which language would you like?"), VOCAB)
    check("informational turns are marked and never counted as failures", all(c["ok"] or c.get("info") for c in checks))


def test_request_error():
    checks = evaluate_turn({"say": "hi", "tool": None}, None, VOCAB, error="HTTP 500")
    check("a failed request is reported as a failed check, not an exception",
          len(checks) == 1 and not checks[0]["ok"] and "HTTP 500" in checks[0]["detail"])


# --- language correctness and duplicate tool calls (both found in the first live run) -----------


def test_story_must_be_in_the_requested_language():
    spec = dict(STORY_SPEC, language="Spanish")
    english_for_spanish = response(ENGLISH_STORY, tool_block("story_generator_tool", {"language": "Spanish"}, ENGLISH_STORY))
    c = results_by_name(evaluate_turn(spec, english_for_spanish, VOCAB))
    check("an English story returned for a Spanish request fails the quality check",
          not c["story quality"]["ok"] and "english" in c["story quality"]["detail"].lower())
    good = response(SPANISH_STORY, tool_block("story_generator_tool", {"language": "Spanish"}, SPANISH_STORY))
    check("a real Spanish story passes", results_by_name(evaluate_turn(spec, good, VOCAB))["story quality"]["ok"])
    mixed = "Bonjour, je suis L\u00e9a today.\nJ'ai soif et je veux water.\nJe demande \u00e0 ami please water.\nIl dit oui et me donne water.\nJe dis thank you et bois water.\nTomorrow je aiderai ami gentil."
    spec_fr = {"say": "Story in French", "tool": "story", "language": "French",
               "arg": {"key": "language", "any_of": ["french"]}, "story": "other"}
    resp = response(mixed, tool_block("story_generator_tool", {"language": "French"}, mixed))
    check("French with English words left in fails", not results_by_name(evaluate_turn(spec_fr, resp, VOCAB))["story quality"]["ok"])


def test_duplicate_tool_calls_are_collapsed():
    block = dict(tool_block("story_generator_tool", {"language": "Spanish"}, "story"), id="call-1")
    check("the same call (same id) appearing twice counts once", len(find_tool_calls(response("x", block, dict(block)))) == 1)
    other = dict(block, id="call-2")
    check("two genuine calls (different ids) are both kept", len(find_tool_calls(response("x", block, other))) == 2)
    plain = tool_block("story_generator_tool", {"language": "Spanish"}, "story")
    check("identical calls without ids are collapsed too", len(find_tool_calls(response("x", plain, dict(plain)))) == 1)
    check("the call id is reported", find_tool_calls(response("x", block))[0]["id"] == "call-1")


# --- the case catalogue ----------------------------------------------------------------------


def test_case_catalogue():
    ids = [c["id"] for c in CASES]
    check("case ids are unique", len(ids) == len(set(ids)))
    check("every case has an id, a name and at least one turn with something to say",
          all(c["id"] and c["name"] and c["turns"] and all(t["say"] for t in c["turns"]) for c in CASES))
    check("the language-switching sequence is covered (4 turns, one session)",
          any(len(c["turns"]) == 4 for c in CASES))
    check("an empty-vocabulary case is flagged so the runner can set it up",
          any(c.get("needs_empty_vocab") for c in CASES))
    check("every non-English story case names its language, so the language check runs",
          all(t.get("language") for c in CASES for t in c["turns"] if t.get("story") == "other"))
    check("story, add-word and no-tool expectations are all represented",
          {t.get("tool") for c in CASES for t in c["turns"]} >= {"story", "add_word", None})


def main():
    print("Running routing check tests...\n")
    test_final_text_shapes()
    test_find_tool_calls()
    test_with_tool_blocks()
    test_a_good_story_turn_passes_every_check()
    test_wrong_language_argument_is_caught()
    test_no_tool_call_is_caught()
    test_reply_that_differs_from_the_tool_output_is_caught()
    test_english_story_quality_uses_the_vocabulary_rules()
    test_no_tool_expected()
    test_add_word_turns()
    test_empty_vocabulary_guard()
    test_info_cases_never_fail()
    test_story_must_be_in_the_requested_language()
    test_duplicate_tool_calls_are_collapsed()
    test_request_error()
    test_case_catalogue()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
