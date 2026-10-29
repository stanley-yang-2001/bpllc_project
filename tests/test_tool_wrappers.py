"""The Langflow wrappers for Add Word, Story Generator Tool and Word Loader (M3).

The logic is tested in api/tests/test_tutor_tools.py. What is checked here is what only the wrapper decides:
  * which inputs the AGENT can see (tool mode) and which are hidden from it;
  * that the hidden inputs are named so Langflow does not shadow them, and are text fields (Langflow silently drops
    non-string tweaks on those);
  * that the wrapper hands exactly the right values to the tested function.

    docker compose exec langflow python /app/tests/test_tool_wrappers.py
"""
import sys

sys.path.insert(0, "/app/custom_components")

import add_word  # noqa: E402
import story_tool  # noqa: E402
import word_loader  # noqa: E402

failures = []

# Names Langflow reserves on every component (found by the M0 spike): an input with one of these is silently shadowed.
RESERVED = {"trace_name", "graph", "user_id", "flow_id", "flow_name", "tracing_service", "tree", "template_config",
            "enabled_tools", "ctx"}


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


def inputs_of(cls):
    return {i.name: i for i in cls.inputs}


def test_what_the_agent_can_see():
    print("what the Agent can see")
    for cls, visible in ((add_word.AddWord, ["word"]), (story_tool.StoryGeneratorTool, ["difficulty", "language", "story_type", "topic"]),
                         (word_loader.WordLoader, [])):
        tool_inputs = sorted(n for n, i in inputs_of(cls).items() if getattr(i, "tool_mode", False))
        check(f"{cls.__name__}: the Agent can fill in only {visible}", tool_inputs == visible, str(tool_inputs))


def test_the_hidden_inputs():
    print("the hidden inputs")
    for cls in (add_word.AddWord, story_tool.StoryGeneratorTool, word_loader.WordLoader):
        ins = inputs_of(cls)
        for name in ("learner_id", "active_language"):
            check(f"{cls.__name__} has a hidden {name}", name in ins and ins[name].tool_mode is False and ins[name].advanced is True)
            check(f"{cls.__name__}.{name} is a plain text field (non-strings are dropped by Langflow)",
                  name in ins and type(ins[name]).__name__ == "StrInput")
            check(f"{cls.__name__}.{name} defaults to empty (so a missing tweak means 'nobody')", name in ins and ins[name].value == "")
        check(f"{cls.__name__} uses no name Langflow reserves", not (set(ins) & RESERVED), str(set(ins) & RESERVED))
        check(f"{cls.__name__} has no input called user_id", "user_id" not in ins)


def test_the_wrappers_hand_over_the_right_values():
    print("what the wrappers pass on")
    seen = {}
    add_word.add_word_for_agent = lambda *a: (seen.setdefault("add", a), "added")[1]
    story_tool.story_for_agent = lambda *a, **kw: (seen.setdefault("story", a), seen.setdefault("story_kw", kw), "a story")[2]
    word_loader.vocabulary_for_agent = lambda *a: (seen.setdefault("list", a), "uno, dos")[1]

    out = add_word.AddWord(word="bread", learner_id="17", active_language="es").run()
    check("Add Word passes (word, learner_id, active_language) and returns the text", seen["add"] == ("bread", "17", "es") and out == "added", str(seen))
    out = story_tool.StoryGeneratorTool(language="French", story_type="dialogue", topic="a market", difficulty="easy", learner_id="17",
                                        active_language="es", set_ids="0,4").run()
    check("Story tool passes (language, learner_id, active_language, story_type, topic, difficulty) and set_ids, and returns the story as a message",
          seen["story"] == ("French", "17", "es", "dialogue", "a market", "easy") and seen["story_kw"] == {"set_ids": "0,4"} and out.text == "a story", str(seen))
    seen.clear()
    story_tool.StoryGeneratorTool(language="French", learner_id="17", active_language="es").run()
    check("with no type or topic the Story tool passes them on blank (None or an empty string), and the tool then chooses",
          seen["story"][:3] == ("French", "17", "es") and all(not v for v in seen["story"][3:]) and len(seen["story"]) == 6, str(seen))
    out = word_loader.WordLoader(learner_id="17", active_language="es").run()
    check("Word Loader passes (learner_id, active_language)", seen["list"] == ("17", "es") and out.text == "uno, dos", str(seen))

    seen.clear()
    add_word.AddWord(word="bread").run()
    check("with no hidden values set, Add Word passes empty values on (the tool then refuses)", seen["add"] == ("bread", "", ""), str(seen))


def main():
    print("Running tool wrapper tests...\n")
    test_what_the_agent_can_see()
    test_the_hidden_inputs()
    test_the_wrappers_hand_over_the_right_values()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
