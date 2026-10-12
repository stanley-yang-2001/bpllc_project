"""What the Groq request asks for. Ported from tests/test_empty_response_handling.py (M3): these were about call_groq,
not the story pipeline, and need no Langflow or database."""
import json
from unittest.mock import MagicMock, patch

from tutor_core import groq


def capture_payload():
    captured = {}

    def fake_urlopen(req, timeout=30):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        body = json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = body.encode("utf-8")
        return cm

    with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True):
        with patch("tutor_core.groq.urllib.request.urlopen", side_effect=fake_urlopen):
            groq.call_groq("hello")
    return captured["payload"]


def test_max_tokens_leaves_room_for_the_answer_after_the_models_hidden_reasoning():
    assert capture_payload().get("max_tokens", 0) >= 1500          # with 400, reasoning used 398 and the story came back empty


def test_the_request_asks_for_low_reasoning_effort():
    assert capture_payload().get("reasoning_effort") == "low"


def test_the_request_targets_the_story_model_and_sends_the_prompt_as_the_user_message():
    payload = capture_payload()
    assert payload.get("model") == "openai/gpt-oss-120b"
    assert payload["messages"] == [{"role": "user", "content": "hello"}]
