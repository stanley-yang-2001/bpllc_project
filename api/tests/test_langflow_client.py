"""The Langflow client: what we send, how we read the answer, how failures are reported.

NOTE on fixtures: the response shapes below are modelled on what Step 10's checks parse. Milestone M0's
`scripts/capture_fixtures.py` records REAL responses; when they are in tests/fixtures/langflow/, the
`test_real_*` tests at the bottom run against them (they skip until then). A parser tested only against
shapes we invented is how the Tool Result Relay once passed its tests and failed in the real flow.
"""
import json
import os

import pytest

from app.errors import AppError
from app.services import langflow_client as lc

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "langflow")


def run_response(text, calls=()):
    blocks = [{"contents": [dict(c, type="tool_use") for c in calls]}] if calls else []
    return {"session_id": "s", "outputs": [{"outputs": [{"results": {"message": {
        "text": text, "content_blocks": blocks}}}]}]}


ADD = {"name": "Add Word", "tool_input": {"word": "bread"}, "output": "Added 'bread' to your Spanish vocabulary."}
STORY = {"name": "Story Generator Tool", "tool_input": {"language": "Spanish"}, "output": "Ana: Hola.\nBen: Hola, Ana."}


# --- what we send ------------------------------------------------------------------------------------

def test_session_id_is_built_from_the_user_and_a_client_part():
    part = "a" * 32
    assert lc.build_session_id(17, part) == f"u17-{part}"


@pytest.mark.parametrize("bad", ["", "short", "A" * 32, "g" * 32, "a" * 31, "a" * 33, "../" + "a" * 29, "u2-" + "a" * 29, None])
def test_a_malformed_client_session_part_is_rejected(bad):
    with pytest.raises(AppError) as err:
        lc.build_session_id(17, bad)
    assert err.value.code == "validation_error"


def test_two_users_with_the_same_client_part_get_different_sessions():
    part = "b" * 32
    assert lc.build_session_id(1, part) != lc.build_session_id(2, part)


def test_tweaks_carry_the_user_and_language_for_every_key():
    t = lc.build_tweaks(("Add Word", "Story Generator Tool"), 17, "es")
    assert t == {"Add Word": {"learner_id": "17", "active_language": "es"}, "Story Generator Tool": {"learner_id": "17", "active_language": "es"}}


def test_the_hidden_inputs_are_learner_id_and_active_language_only():
    """`language` is the story tool's VISIBLE argument (the Agent fills it in). The hidden default must not share its name."""
    for fields in lc.build_tweaks(("AddWord-WhP5g", "StoryGeneratorTool-RQpvc"), 17, "es").values():
        assert set(fields) == {"learner_id", "active_language"}


def test_the_learner_id_is_sent_as_a_string_never_an_integer():
    """Langflow silently drops a non-string value sent to a text field: an integer learner_id never reaches the tool.
    Found by the second live M0 spike run."""
    for fields in lc.build_tweaks(("Add Word", "Story Generator Tool"), 17, "es").values():
        assert isinstance(fields["learner_id"], str) and fields["learner_id"] == "17"
        assert all(isinstance(v, str) for v in fields.values())     # every tweak value is a string


def test_the_hidden_input_is_never_called_user_id():
    """Langflow gives every component a read-only `user_id` (the Langflow ACCOUNT's UUID) that shadows an input of that
    name, so a tool would silently receive the account id instead of the learner. Found by the M0 spike."""
    for keys in (("Add Word",), ("Add Word", "Story Generator Tool")):
        for fields in lc.build_tweaks(keys, 17, "es").values():
            assert "user_id" not in fields and fields["learner_id"] == "17"
    for reserved in ("user_id", "graph", "flow_id", "flow_name", "trace_name", "ctx", "tree"):
        assert all(reserved not in f for f in lc.build_tweaks(("K",), 1, "es").values())


def test_no_tweak_keys_means_no_tweaks_plan_b():
    assert lc.build_tweaks((), 17, "es") is None


def test_run_payload_shape():
    p = lc.build_run_payload("hello", "u1-" + "a" * 32, {"K": {"learner_id": "1"}})
    assert p == {"input_value": "hello", "input_type": "chat", "output_type": "chat",
                 "session_id": "u1-" + "a" * 32, "tweaks": {"K": {"learner_id": "1"}}}
    assert "tweaks" not in lc.build_run_payload("hello", "s", None)


def test_nothing_personal_is_sent_to_langflow():
    """Privacy (design 3D): Langflow and Groq receive only the numeric user id, language, session id and the
    learner's own message. Never the email, the display name or the password."""
    sent = []

    def transport(method, url, payload, headers, timeout):
        sent.append((method, url, json.dumps(payload), json.dumps(headers)))
        return run_response("ok")

    client = lc.LangflowClient("http://lf:7860", "language-tutor", "key-1", 30, ("Add Word",), transport)
    client.run(user_id=17, language="es", message="hello", session_id=lc.build_session_id(17, "c" * 32))
    everything = " ".join(" ".join(s) for s in sent)
    for secret in ("zebulon", "quux", "@example.com", "password"):
        assert secret not in everything.lower()
    assert '"learner_id": "17"' in everything and "u17-" in everything


# --- how we read the answer --------------------------------------------------------------------------

def test_a_plain_reply_has_no_tool_calls():
    r = lc.parse_run_response(run_response("Hola! How can I help?"))
    assert r.reply == "Hola! How can I help?" and r.tool_calls == []


def test_a_tool_call_is_reported_with_name_args_and_output():
    r = lc.parse_run_response(run_response(ADD["output"], [ADD]))
    assert r.reply == ADD["output"]
    assert [(c.name, c.args, c.output, c.failed) for c in r.tool_calls] == [
        ("Add Word", {"word": "bread"}, ADD["output"], False)]


def test_a_story_is_returned_exactly_as_written():
    r = lc.parse_run_response(run_response(STORY["output"], [STORY]))
    assert r.reply == "Ana: Hola.\nBen: Hola, Ana." and r.tool_calls[0].name == "Story Generator Tool"


def test_the_same_call_appearing_twice_is_reported_once():
    resp = run_response("x", [ADD])
    resp["outputs"][0]["outputs"][0]["results"]["message"]["data"] = {"content_blocks": [{"contents": [dict(ADD, type="tool_use")]}]}
    assert len(lc.parse_run_response(resp).tool_calls) == 1


def test_two_different_calls_are_both_reported_in_order():
    r = lc.parse_run_response(run_response("done", [ADD, STORY]))
    assert [c.name for c in r.tool_calls] == ["Add Word", "Story Generator Tool"]


def test_a_tool_error_flag_marks_the_call_failed():
    r = lc.parse_run_response(run_response("sorry", [dict(ADD, error="boom", output="")]))
    assert r.tool_calls[0].failed is True


def test_the_fixed_apology_text_marks_the_call_failed():
    apology = "I'm having trouble generating a story right now — please try again in a moment."
    r = lc.parse_run_response(run_response(apology, [dict(STORY, output=apology)]))
    assert r.tool_calls[0].failed is True and r.reply == apology      # the text is still passed through


@pytest.mark.parametrize("text, failed", [
    ("Couldn't add word: I don't know whose vocabulary this is.", True),
    ("Couldn't add word: Word is empty.", True),
    ("Add word failed: OperationalError", True),
    ("I can't write a story right now: I don't know whose vocabulary to use.", True),
    ("I can't write a story right now: I don't know which language to use.", True),
    ("Stories in German are not available yet.", True),
    ("I'm having trouble generating a story right now — please try again in a moment.", True),
    ("Added 'bread' to your Spanish vocabulary.", False),
    ("'bread' is already in your Spanish vocabulary.", False),
    ("You don't have any vocabulary yet! Tell me a word to add, and I'll remember it.", False),
    ("Ana: Hola.\nBen: Hola, Ana.", False),
])
def test_the_tools_own_refusal_messages_are_flagged_as_failures_and_normal_answers_are_not(text, failed):
    r = lc.parse_run_response(run_response(text, [dict(ADD, output=text)]))
    assert r.tool_calls[0].failed is failed and r.reply == text


def test_structured_tool_output_is_turned_into_text():
    r = lc.parse_run_response(run_response("x", [dict(ADD, output={"text": "Added 'bread'."})]))
    assert r.tool_calls[0].output == "Added 'bread'."
    r = lc.parse_run_response(run_response("x", [dict(ADD, output="[{'text': 'Added bread.'}]")]))
    assert r.tool_calls[0].output == "Added bread."


def test_args_that_are_not_a_dict_become_empty():
    assert lc.parse_run_response(run_response("x", [dict(ADD, tool_input="oops")])).tool_calls[0].args == {}


def test_reply_falls_back_to_the_last_tool_output_when_the_text_is_empty():
    assert lc.parse_run_response(run_response("", [ADD])).reply == ADD["output"]


def test_stored_messages_are_the_fallback_for_tool_calls():
    stored = [{"sender": "User", "text": "add bread"},
              {"sender": "Machine", "content_blocks": [{"contents": [dict(ADD, type="tool_use")]}]}]
    r = lc.parse_run_response(run_response("Added."), stored_messages=stored)
    assert [c.name for c in r.tool_calls] == ["Add Word"]


def test_an_unrecognised_shape_gives_an_empty_result_not_a_crash():
    for odd in ({}, {"outputs": []}, {"outputs": [{}]}, [], "text", None):
        r = lc.parse_run_response(odd)
        assert r.reply == "" and r.tool_calls == []


# --- the client end to end, with a fake transport ----------------------------------------------------

def make(transport, keys=("Add Word",)):
    return lc.LangflowClient("http://lf:7860/", "language-tutor", "key-1", 30, keys, transport)


def test_run_calls_the_flow_by_name_with_the_api_key():
    calls = []

    def transport(method, url, payload, headers, timeout):
        calls.append((method, url, payload, headers, timeout))
        return run_response("hi")

    make(transport).run(user_id=3, language="fr", message="salut", session_id="u3-" + "d" * 32)
    method, url, payload, headers, timeout = calls[0]
    assert (method, url) == ("POST", "http://lf:7860/api/v1/run/language-tutor?stream=false")
    assert headers["x-api-key"] == "key-1" and timeout == 30
    assert payload["tweaks"] == {"Add Word": {"learner_id": "3", "active_language": "fr"}}


def test_the_stored_messages_are_fetched_only_when_no_tool_call_was_seen():
    urls = []

    def transport(method, url, payload, headers, timeout):
        urls.append(url)
        return run_response("hi") if method == "POST" else [{"sender": "Machine", "content_blocks": [{"contents": [dict(ADD, type="tool_use")]}]}]

    r = make(transport).run(user_id=3, language="fr", message="m", session_id="u3-" + "d" * 32)
    assert any("monitor/messages?session_id=u3-" in u for u in urls) and r.tool_calls[0].name == "Add Word"
    urls.clear()
    make(lambda *a: (urls.append(a[1]), run_response("x", [ADD]))[1]).run(user_id=3, language="fr", message="m", session_id="u3-" + "d" * 32)
    assert len(urls) == 1                           # tool call found in the run response: no second request


def test_a_failing_stored_messages_lookup_is_ignored():
    def transport(method, url, payload, headers, timeout):
        if method == "GET":
            raise lc.TransportError("http", 500, "boom")
        return run_response("just text")

    assert make(transport).run(user_id=3, language="fr", message="m", session_id="u3-" + "d" * 32).reply == "just text"


def test_an_empty_answer_is_an_ai_failure():
    with pytest.raises(AppError) as err:
        make(lambda *a: run_response("")).run(user_id=3, language="fr", message="m", session_id="u3-" + "d" * 32)
    assert err.value.code == "ai_failed" and err.value.status == 502


@pytest.mark.parametrize("error, code, status", [
    (lc.TransportError("unreachable", None, "refused"), "langflow_unavailable", 503),
    (lc.TransportError("timeout", None, "slow"), "ai_failed", 502),
    (lc.TransportError("http", 429, "rate"), "tutor_busy", 429),
    (lc.TransportError("http", 401, "bad key"), "langflow_unavailable", 503),
    (lc.TransportError("http", 404, "no flow"), "langflow_unavailable", 503),
    (lc.TransportError("http", 500, "oops"), "ai_failed", 502),
    (lc.TransportError("http", 502, "oops"), "ai_failed", 502),
    (lc.TransportError("badjson", 200, "not json"), "ai_failed", 502),
])
def test_transport_failures_become_the_documented_errors(error, code, status):
    def transport(*a):
        raise error

    with pytest.raises(AppError) as err:
        make(transport).run(user_id=3, language="fr", message="m", session_id="u3-" + "d" * 32)
    assert (err.value.code, err.value.status) == (code, status)
    assert "http" not in err.value.message.lower() and "groq" not in err.value.message.lower()   # nothing technical reaches the learner


# --- tool names ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, shown", [
    ("add_word", "Add Word"), ("Add Word", "Add Word"), ("AddWord", "Add Word"), ("ADD_WORD", "Add Word"),
    ("story_generator_tool", "Story Generator Tool"), ("Story Generator Tool", "Story Generator Tool"),
    ("spike_who_am_i", "Spike Who Am I"), ("some_new_tool", "Some New Tool"),
    ("Who Am I (spike)", "Who Am I (spike)"), ("", "tool"), (None, "tool"),
])
def test_tool_names_are_shown_by_their_canvas_names(raw, shown):
    assert lc.canonical_tool_name(raw) == shown


def test_a_snake_case_tool_name_from_langflow_is_reported_by_its_display_name():
    """Live runs name the tool `add_word`; the page refreshes the vocabulary when it sees `Add Word`."""
    r = lc.parse_run_response(run_response("Added.", [dict(ADD, name="add_word")]))
    assert r.tool_calls[0].name == "Add Word"


# --- real captured fixtures (skipped until M0's capture has been run and reviewed) -------------------

def _fixture(name):
    path = os.path.join(FIXTURES, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not captured yet (run scripts/capture_fixtures.py, move the files to tests/fixtures/langflow/)")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_real_whoami_run_parses_correctly():
    """The first REAL response (M0 spike, Langflow 1.12.2). It appears in two places in the response (content_blocks under
    `message` and under `message.data`), reply text is the tool's exact output, and the tool is named `spike_who_am_i`."""
    resp = _fixture("whoami_run.json")
    r = lc.parse_run_response(resp)
    assert r.reply.startswith("WHOAMI learner_id=101 language=es")
    assert len(r.tool_calls) == 1                                   # one call, found at two paths
    call = r.tool_calls[0]
    assert (call.name, call.args, call.failed) == ("Spike Who Am I", {"note": "x"}, False)
    assert call.output == r.reply                                   # the relay delivers the tool's output as the reply
    assert lc.reply_text(resp) == r.reply and len(list(lc.walk_tool_blocks(resp))) == 2


def test_real_greeting_run_parses_to_a_reply_without_tool_calls():
    r = lc.parse_run_response(_fixture("greeting_run.json"))
    assert r.reply.strip() and r.tool_calls == []


def test_real_story_run_parses_to_the_story_and_one_tool_call():
    r = lc.parse_run_response(_fixture("story_run.json"))
    assert r.reply.strip() and [c.name for c in r.tool_calls] == ["Story Generator Tool"]
    assert r.tool_calls[0].output.strip() == r.reply.strip()        # the relay delivers the tool's exact output


def test_real_stored_messages_contain_the_tool_call_too():
    r = lc.parse_run_response({}, stored_messages=_fixture("story_messages.json"))
    assert [c.name for c in r.tool_calls] == ["Story Generator Tool"]


def test_the_reply_language_note_names_only_the_language_and_goes_in_front_of_the_message():
    assert lc.with_reply_language("tell me a story", None) == "tell me a story"
    assert lc.with_reply_language("tell me a story", "") == "tell me a story"
    assert "English" in lc.with_reply_language("你好", "English")          # a learner studying English writing in Chinese
    out = lc.with_reply_language("hola", "Korean")
    assert out.endswith("\n\nhola") and "Korean" in out and out.startswith("[Note for the tutor:") and "call the story tool with language \"Korean\"" in out
    assert "Tool names and every other tool argument stay exactly as they are" in out


def _story_block(text, **args):
    return {"type": "tool_use", "name": "story_generator_tool", "tool_input": {"language": "English", **args}, "output": text}


def test_a_reply_with_several_story_calls_keeps_only_the_one_it_shows():
    resp = {"outputs": [{"outputs": [{"results": {"message": {"text": "Anna: Hi.\nBen: Hello."},
            "blocks": [_story_block("Old story one."), _story_block("Another old one.", topic="x"), _story_block("Anna: Hi.\nBen: Hello.", topic="y")]}}]}]}
    out = lc.parse_run_response(resp)
    stories = [c for c in out.tool_calls if c.name == "Story Generator Tool"]
    assert len(stories) == 1 and stories[0].output == "Anna: Hi.\nBen: Hello."


def test_the_chosen_sets_reach_only_the_story_tool_as_a_string():
    t = lc.build_tweaks(("AddWord-WhP5g", "StoryGeneratorTool-RQpvc"), 17, "es", [0, 3])
    assert t["StoryGeneratorTool-RQpvc"]["set_ids"] == "0,3" and "set_ids" not in t["AddWord-WhP5g"]
    assert "set_ids" not in lc.build_tweaks(("StoryGeneratorTool-RQpvc",), 17, "es")["StoryGeneratorTool-RQpvc"]
    assert "set_ids" not in lc.build_tweaks(("StoryGeneratorTool-RQpvc",), 17, "es", [])["StoryGeneratorTool-RQpvc"]
