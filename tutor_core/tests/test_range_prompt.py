from tutor_core import difficulty as d
from tutor_core.difficulty.note import LEVELS, prompt_note, size_range
from tutor_core.prompts import build_story_prompt


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("STORY_RANGE_PROMPT", raising=False)
    note = prompt_note("es", d.resolve("easy"))
    assert "about 60 words" in note and "Level A1" not in note


def test_range_and_level_when_on(monkeypatch):
    monkeypatch.setenv("STORY_RANGE_PROMPT", "1")
    note = prompt_note("es", d.resolve("easy"))
    assert "between 51 and 69 words" in note and LEVELS["easy"] in note
    assert LEVELS["hard"] in prompt_note("es", d.resolve("hard"))
    assert LEVELS["medium"] in prompt_note("es", d.resolve("custom", length=100))
    assert "characters" in prompt_note("zh", d.resolve("medium"))
    assert size_range(100) == (85, 115)


def test_sentence_count_follows_the_level(monkeypatch):
    monkeypatch.setenv("STORY_RANGE_PROMPT", "1")
    easy = build_story_prompt("Spanish", "casa, mar", difficulty=d.resolve("easy"), vocab_in_target=True)
    assert "about 6 words each" in easy
    monkeypatch.setenv("STORY_RANGE_PROMPT", "0")
    assert "about 10 words each" in build_story_prompt("Spanish", "casa, mar", difficulty=d.resolve("easy"), vocab_in_target=True)


def test_cache_key_differs_when_on(monkeypatch):
    from tutor_core.story import StoryRequest
    r = StoryRequest(1, "es", None, None, None, d.resolve("easy"))
    monkeypatch.setenv("STORY_RANGE_PROMPT", "0")
    a = r.cache_key()
    monkeypatch.setenv("STORY_RANGE_PROMPT", "1")
    assert r.cache_key() != a
