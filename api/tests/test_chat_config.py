"""Settings for chat: safe defaults, and refusing to start with a half-configured live chat."""
import pytest

from app.config import ConfigError, load_settings
from app.services.chat import NotReadyChat, make_chat_client
from app.services.chat_stub import StubChat
from app.services.langflow_client import LangflowClient

BASE = {"DATABASE_URL": "postgresql://x", "JWT_SECRET": "s" * 40}


def env(**extra):
    return {**BASE, **extra}


def test_defaults_are_safe():
    s = load_settings(env())
    assert s.ai_mode == "live" and s.langflow_per_user_tools is False
    assert s.langflow_url == "http://langflow:7860" and s.langflow_flow == "language-tutor"
    assert s.langflow_tweak_keys == ("AddWord-WhP5g", "StoryGeneratorTool-RQpvc")
    assert (s.ai_gate_slots, s.ai_gate_wait, s.langflow_timeout) == (2, 5.0, 100)


def test_values_come_from_the_environment():
    s = load_settings(env(LANGFLOW_URL="http://lf:1/ ", LANGFLOW_FLOW="spike", LANGFLOW_API_KEY=" k ", AI_GATE_SLOTS="3",
                          AI_GATE_WAIT="1.5", LANGFLOW_TIMEOUT="30", LANGFLOW_PER_USER_TOOLS="1"))
    assert (s.langflow_url, s.langflow_flow, s.langflow_api_key) == ("http://lf:1/", "spike", "k")
    assert (s.ai_gate_slots, s.ai_gate_wait, s.langflow_timeout, s.langflow_per_user_tools) == (3, 1.5, 30, True)


def test_tweak_keys_can_be_listed_or_emptied():
    assert load_settings(env(LANGFLOW_TWEAK_KEYS="A, B ,,C")).langflow_tweak_keys == ("A", "B", "C")
    assert load_settings(env(LANGFLOW_TWEAK_KEYS="")).langflow_tweak_keys == ()        # Plan B: no tweaks


@pytest.mark.parametrize("bad", [{"AI_GATE_SLOTS": "0"}, {"AI_GATE_WAIT": "-1"}, {"LANGFLOW_TIMEOUT": "0"}])
def test_nonsense_limits_stop_the_app_at_startup(bad):
    with pytest.raises(ConfigError):
        load_settings(env(**bad))


def test_live_chat_needs_an_api_key_once_it_is_switched_on():
    with pytest.raises(ConfigError, match="LANGFLOW_API_KEY"):
        load_settings(env(LANGFLOW_PER_USER_TOOLS="1"))
    load_settings(env(LANGFLOW_PER_USER_TOOLS="1", LANGFLOW_API_KEY="k"))
    load_settings(env(AI_MODE="stub", LANGFLOW_PER_USER_TOOLS="1"))                  # stub never calls Langflow


def test_the_right_tutor_is_chosen():
    pool = lambda: None  # noqa: E731
    assert isinstance(make_chat_client(load_settings(env(AI_MODE="stub")), pool), StubChat)
    assert isinstance(make_chat_client(load_settings(env()), pool), NotReadyChat)
    live = make_chat_client(load_settings(env(LANGFLOW_PER_USER_TOOLS="1", LANGFLOW_API_KEY="k", LANGFLOW_TWEAK_KEYS="X")), pool)
    assert isinstance(live, LangflowClient) and live.tweak_keys == ("X",) and live.api_key == "k"
