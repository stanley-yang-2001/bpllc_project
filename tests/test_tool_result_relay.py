"""
Tests for the Tool Result Relay component (Step 9 fix for the "Agent rewrites the tool output"
problem).

Background: the top-level Agent sometimes shortened, reworded, or added notes to the Story
Generator Tool's output, even with strict instructions. Prompt tuning cannot guarantee exact
relay because an LLM writes the final reply. The relay sits between the Agent and Chat Output
and replaces the Agent's text with the tool's own output whenever a tool was called. The Agent
still decides WHICH tool to call (LO 5 / LO 6); code decides WHAT the learner sees.

Written BEFORE the component. Run now and expect an ImportError; re-run after to confirm green.
These tests use real Langflow Message / ToolContent objects but no database and no network.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_tool_result_relay.py
"""

import sys

sys.path.insert(0, "/app/custom_components")

from langflow.schema.content_block import ContentBlock  # noqa: E402
from langflow.schema.content_types import ErrorContent, TextContent, ToolContent  # noqa: E402
from langflow.schema.message import Message  # noqa: E402

from tool_result_relay import (  # noqa: E402
    extract_last_tool_output,
    output_to_text,
    relay_message,
)

PASS = "PASS"
FAIL = "FAIL"
failures = []

STORY = "Anna: Hello, do you have water?\nBen: Yes, I have water today.\nAnna: Thank you, goodbye friend."


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def tool(output, name="story_generator_tool", error=None):
    return ToolContent(name=name, tool_input={"language": "English"}, output=output, error=error)


def agent_message(agent_text, *tool_contents):
    """A Message shaped like the Agent's reply: its own text plus a block of tool calls."""
    blocks = [ContentBlock(title="Agent Steps", contents=list(tool_contents))] if tool_contents else []
    return Message(text=agent_text, content_blocks=blocks)


# --- output_to_text: tool outputs arrive in several shapes ---------------------------------


def test_output_to_text_shapes():
    check("plain string is returned unchanged", output_to_text(STORY) == STORY)
    check("None becomes an empty string", output_to_text(None) == "")
    check("dict with a 'text' key uses it", output_to_text({"text": STORY}) == STORY)
    check("a Message uses its text", output_to_text(Message(text=STORY)) == STORY)
    check("a one-item list unwraps to its text", output_to_text([{"text": STORY}]) == STORY)
    check("whitespace-only output counts as empty", output_to_text("  \n ").strip() == "")


# --- extract_last_tool_output ----------------------------------------------------------------


def test_extract_returns_the_tool_output_exactly():
    msg = agent_message("Anna: Hello... (Note: intentionally short)", tool(STORY))
    check("returns the tool's output exactly", extract_last_tool_output(msg) == STORY)


def test_extract_returns_none_when_no_tool_was_called():
    msg = agent_message("Hi! How can I help you practice today?")
    check("no tool call -> None", extract_last_tool_output(msg) is None)


def test_extract_uses_the_last_tool_call():
    msg = agent_message("x", tool("first story"), tool("second story"))
    check("when the Agent calls the tool repeatedly, the last result wins", extract_last_tool_output(msg) == "second story")


def test_extract_skips_empty_and_errored_calls():
    msg = agent_message("x", tool("good story"), tool(""), tool("bad", error="boom"))
    check("empty and errored calls are skipped; the last good one is used", extract_last_tool_output(msg) == "good story")


def test_extract_ignores_non_tool_blocks():
    block = ContentBlock(title="Agent Steps", contents=[TextContent(text="thinking..."), ErrorContent(), tool(STORY)])
    msg = Message(text="x", content_blocks=[block])
    check("text/error blocks are ignored", extract_last_tool_output(msg) == STORY)


def test_extract_handles_odd_input():
    check("None message -> None", extract_last_tool_output(None) is None)
    check("a plain string -> None", extract_last_tool_output("just text") is None)


# --- relay_message ---------------------------------------------------------------------------


def test_relay_replaces_the_agents_text_with_the_tool_output():
    msg = agent_message("Anna: Hello, do you have water?\nBen: Yes, we have water today — ...", tool(STORY))
    out = relay_message(msg)
    check("reply text is exactly the tool output", out.text == STORY)


def test_relay_keeps_the_tool_call_blocks_for_the_playground_trace():
    msg = agent_message("rewritten", tool(STORY))
    out = relay_message(msg)
    kinds = [type(c).__name__ for b in out.content_blocks if hasattr(b, "contents") for c in b.contents]
    check("tool-call trace is still attached to the message", "ToolContent" in kinds)


def test_relay_returns_the_same_message_object_so_chat_output_updates_in_place():
    msg = agent_message("rewritten", tool(STORY))
    out = relay_message(msg)
    check("same Message object is returned (no duplicate chat bubble)", out is msg)


def test_relay_passes_the_agents_text_through_when_no_tool_was_called():
    msg = agent_message("Hi! Ask me for a story or add a word.")
    out = relay_message(msg)
    check("no tool call -> Agent's own text is untouched", out.text == "Hi! Ask me for a story or add a word.")


def test_relay_passes_through_when_every_tool_call_failed():
    msg = agent_message("Sorry, something went wrong.", tool("", error="boom"))
    out = relay_message(msg)
    check("only failed tool calls -> Agent's own text is untouched", out.text == "Sorry, something went wrong.")


def test_relay_accepts_a_plain_string():
    out = relay_message("hello")
    check("a plain string becomes a Message with that text", isinstance(out, Message) and out.text == "hello")


def test_relay_relays_add_word_confirmations_too():
    msg = agent_message("Added!", tool("Successfully added 'bread'.", name="add_word"))
    check("any tool's output is relayed, not just the story tool", relay_message(msg).text == "Successfully added 'bread'.")


# --- The REAL shape seen in Langflow: ToolContent sits directly in content_blocks ----------


def flat_agent_message(agent_text, *tool_contents):
    """Message as Langflow actually builds it: tool calls are top-level content_blocks entries
    (no ContentBlock wrapper), and the Agent's own text is a top-level TextContent."""
    return Message(text=agent_text, content_blocks=list(tool_contents))


def test_flat_tool_content_is_found():
    msg = flat_agent_message("Anna: ...... ... ...", tool(STORY))
    check("[real shape] a top-level ToolContent is found", extract_last_tool_output(msg) == STORY)


def test_flat_relay_replaces_the_agents_text():
    msg = flat_agent_message("Hello, I am ...", tool(STORY))
    out = relay_message(msg)
    check("[real shape] reply text becomes exactly the tool output", out.text == STORY)


def test_flat_relay_keeps_the_tool_call_and_leaves_one_text_block():
    msg = flat_agent_message("Hello, I am ...", tool(STORY))
    out = relay_message(msg)
    kinds = [type(b).__name__ for b in out.content_blocks]
    check("[real shape] tool call is still attached", kinds.count("ToolContent") == 1)
    check("[real shape] exactly one text block remains, holding the tool output",
          kinds.count("TextContent") == 1 and out.text == STORY)


def test_flat_last_good_call_wins_and_errors_are_skipped():
    msg = flat_agent_message("x", tool("first"), tool("second"), tool("bad", error="boom"), tool(""))
    check("[real shape] last successful non-empty call wins", extract_last_tool_output(msg) == "second")


def test_flat_no_tool_passes_agent_text_through():
    msg = flat_agent_message("Hi there!")
    check("[real shape] no tool call -> Agent text untouched", relay_message(msg).text == "Hi there!")


# --- Tool outputs recorded as structured data (the Result panel showed a 'text' box) -------


def test_structured_outputs():
    check("dict output with nested data/text is unwrapped", output_to_text({"data": {"text": STORY}}) == STORY)
    check("a JSON string holding {'text': ...} is unwrapped", output_to_text('{"text": "Hello there"}') == "Hello there")
    check("a Python-repr string holding {'text': ...} is unwrapped", output_to_text("{'text': 'Hello there'}") == "Hello there")
    check("a story that merely starts with '[' is NOT altered", output_to_text("[Scene] Anna: hi") == "[Scene] Anna: hi")
    check("a multi-line story is returned exactly (no stripping)", output_to_text(STORY) == STORY)


def main():
    print("Running Tool Result Relay tests...\n")
    test_output_to_text_shapes()
    test_extract_returns_the_tool_output_exactly()
    test_extract_returns_none_when_no_tool_was_called()
    test_extract_uses_the_last_tool_call()
    test_extract_skips_empty_and_errored_calls()
    test_extract_ignores_non_tool_blocks()
    test_extract_handles_odd_input()
    test_relay_replaces_the_agents_text_with_the_tool_output()
    test_relay_keeps_the_tool_call_blocks_for_the_playground_trace()
    test_relay_returns_the_same_message_object_so_chat_output_updates_in_place()
    test_relay_passes_the_agents_text_through_when_no_tool_was_called()
    test_relay_passes_through_when_every_tool_call_failed()
    test_relay_accepts_a_plain_string()
    test_relay_relays_add_word_confirmations_too()
    test_flat_tool_content_is_found()
    test_flat_relay_replaces_the_agents_text()
    test_flat_relay_keeps_the_tool_call_and_leaves_one_text_block()
    test_flat_last_good_call_wins_and_errors_are_skipped()
    test_flat_no_tool_passes_agent_text_through()
    test_structured_outputs()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
