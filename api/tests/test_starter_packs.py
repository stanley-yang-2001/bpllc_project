"""Starter packs: one click adds a pack of everyday words; existing words are never touched; the English gloss is stored as the
meaning only for a learner who wants English meanings."""
from fastapi.testclient import TestClient

from conftest import HEADERS


def packs(c, language="es"):
    return c.get("/api/words/starter-packs", params={"language": language}).json()


def words(c, language="es"):
    return {w["word"]: w["meaning"] for w in c.get("/api/words", params={"language": language, "limit": 200}).json()["items"]}


def test_needs_login(app):
    anon = TestClient(app, headers=HEADERS)
    assert anon.get("/api/words/starter-packs?language=es").status_code == 401
    assert anon.post("/api/words/starter-packs", json={"language": "es", "pack": "basics"}).status_code == 401


def test_lists_the_four_packs_with_what_is_left(make_user):
    c = make_user("alice")
    body = packs(c)
    assert [p["id"] for p in body["items"]] == ["basics", "food", "people", "numbers"]
    assert all(p["total"] == 12 and p["remaining"] == 12 for p in body["items"])
    assert body["gloss_available"] is True                                      # an English reader, meanings in their own language
    c.post("/api/words", json={"language": "es", "word": "hola"})
    c.post("/api/words", json={"language": "es", "word": "agua"})
    left = {p["id"]: p["remaining"] for p in packs(c)["items"]}
    assert left == {"basics": 11, "food": 11, "people": 12, "numbers": 12}


def test_adding_a_pack_stores_the_words_with_english_meanings(make_user):
    c = make_user("alice")
    r = c.post("/api/words/starter-packs", json={"language": "es", "pack": "basics"})
    assert r.status_code == 200 and r.json() == {"added": 12, "duplicates": 0, "with_meaning": True}
    got = words(c)
    assert len(got) == 12 and got["hola"] == "hello" and got["gracias"] == "thank you"
    assert packs(c)["items"][0]["remaining"] == 0


def test_a_second_click_adds_nothing_and_never_changes_a_word_the_learner_already_has(make_user):
    c = make_user("alice")
    c.post("/api/words", json={"language": "es", "word": "hola", "meaning": "my own note"})
    r = c.post("/api/words/starter-packs", json={"language": "es", "pack": "basics"})
    assert r.json()["added"] == 11 and r.json()["duplicates"] == 1
    assert words(c)["hola"] == "my own note"
    assert c.post("/api/words/starter-packs", json={"language": "es", "pack": "basics"}).json()["added"] == 0


def test_a_learner_who_wants_meanings_in_the_study_language_gets_words_without_meanings(make_user):
    c = make_user("alice")
    assert c.patch("/api/me/preferences", json={"meaning_mode": "study"}).status_code == 200
    assert packs(c)["gloss_available"] is False
    r = c.post("/api/words/starter-packs", json={"language": "es", "pack": "food"})
    assert r.json() == {"added": 12, "duplicates": 0, "with_meaning": False}
    assert set(words(c).values()) == {None}


def test_both_mode_also_leaves_meanings_for_the_tutor(make_user):
    c = make_user("alice")
    c.patch("/api/me/preferences", json={"meaning_mode": "both"})
    assert packs(c)["gloss_available"] is False


def test_a_learner_whose_own_language_is_not_english_gets_words_without_meanings(make_user):
    c = make_user("alice")
    assert c.patch("/api/me", json={"native_language": "fr"}).status_code == 200
    assert packs(c)["gloss_available"] is False
    assert c.post("/api/words/starter-packs", json={"language": "es", "pack": "numbers"}).json()["with_meaning"] is False


def test_english_words_never_get_a_gloss(make_user):
    c = make_user("alice")
    r = c.post("/api/words/starter-packs", json={"language": "en", "pack": "basics"})
    assert r.json() == {"added": 12, "duplicates": 0, "with_meaning": False}
    assert words(c, "en")["hello"] is None


def test_every_language_has_every_pack_and_adds_cleanly(make_user):
    c = make_user("alice")
    for lang in ["en", "es", "fr", "de", "it", "pt", "ja", "zh", "ko"]:
        for pack in ["basics", "food", "people", "numbers"]:
            r = c.post("/api/words/starter-packs", json={"language": lang, "pack": pack})
            assert r.status_code == 200 and r.json()["added"] + r.json()["duplicates"] == 12, (lang, pack, r.text)


def test_unknown_pack_or_language_is_refused(make_user):
    c = make_user("alice")
    assert c.post("/api/words/starter-packs", json={"language": "es", "pack": "nope"}).status_code == 404
    assert c.post("/api/words/starter-packs", json={"language": "xx", "pack": "basics"}).status_code in (400, 404, 422)
    assert c.get("/api/words/starter-packs?language=xx").status_code in (400, 404, 422)


def test_a_pack_adds_the_language_to_the_learners_languages(make_user):
    c = make_user("alice")
    c.post("/api/words/starter-packs", json={"language": "ja", "pack": "basics"})
    assert "ja" in c.get("/api/me").json()["languages"]


def test_other_peoples_lists_are_not_touched(make_user):
    alice, bob = make_user("alice"), make_user("bob")
    alice.post("/api/words/starter-packs", json={"language": "es", "pack": "basics"})
    assert words(bob) == {} and packs(bob)["items"][0]["remaining"] == 12
