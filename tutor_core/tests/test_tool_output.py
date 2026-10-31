"""The one parser for a tool call's recorded output (used by the Langflow relay and by the API)."""
from tutor_core.tool_output import output_to_text, parse_structured_string


def test_plain_text_is_returned_exactly():
    assert output_to_text("Hola.  \nAdiós.") == "Hola.  \nAdiós."
    assert output_to_text(None) == "" and output_to_text("   ") == "   "


def test_json_and_python_repr_strings_are_unwrapped():
    assert output_to_text('{"text": "Hello"}') == "Hello"
    assert output_to_text("{'text': 'Hello'}") == "Hello"
    assert output_to_text('{"data": {"text": "Deep"}}') == "Deep"


def test_a_story_that_merely_starts_with_a_bracket_is_not_altered():
    assert output_to_text("[Scene one] Ana walks home.") == "[Scene one] Ana walks home."
    assert parse_structured_string("[Scene one] Ana") is None


def test_lists_are_joined_and_empty_parts_dropped():
    assert output_to_text(["One", "", {"text": "Two"}]) == "One\nTwo"


def test_objects_with_a_text_attribute_are_read_and_unusable_dicts_become_empty():
    class Message:
        text = "From a Message"
    assert output_to_text(Message()) == "From a Message"
    assert output_to_text({"unknown": 1}) == ""


def test_the_depth_is_limited():
    nested = {"text": {"text": {"text": {"text": {"text": {"text": {"text": {"text": "too deep"}}}}}}}}
    assert output_to_text(nested) == ""
