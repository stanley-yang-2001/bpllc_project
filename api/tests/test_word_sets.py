"""Vocabulary sets (migration 0012): General is the words in no set; sets are per learner and language; moving is by id; a
story can use only chosen sets; deleting a set never deletes words; nobody can touch another learner's sets."""
import pytest

from tutor_core import vocab
from tutor_core.story import generate_story


def add(c, word, language="en", **extra):
    r = c.post("/api/words", json={"language": language, "word": word, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def make_set(c, name="Food", language="en"):
    r = c.post("/api/sets", json={"language": language, "name": name})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_new_word_is_in_general_and_sets_start_empty(make_user):
    c = make_user("alice")
    w = add(c, "water")
    assert w["set_id"] is None
    s = make_set(c)
    assert s["count"] == 0 and s["name"] == "Food"
    assert c.get("/api/sets?language=en").json() == {"items": [{"id": s["id"], "language": "en", "name": "Food", "count": 0}],
                                                    "general_count": 1, "total_count": 1}


def test_move_words_to_a_set_and_back_and_filter_the_list(make_user):
    c = make_user("alice")
    ids = [add(c, w)["id"] for w in ("water", "bread", "milk")]
    s = make_set(c)
    assert c.post("/api/words/move", json={"ids": ids[:2], "set_id": s["id"]}).json() == {"moved": 2}
    assert {w["word"] for w in c.get(f"/api/words?language=en&set={s['id']}").json()["items"]} == {"water", "bread"}
    assert [w["word"] for w in c.get("/api/words?language=en&set=general").json()["items"]] == ["milk"]
    assert c.get("/api/words?language=en&set=all").json()["total"] == 3
    assert c.post("/api/words/move", json={"ids": [ids[0]], "set_id": None}).json() == {"moved": 1}
    assert c.get("/api/sets?language=en").json()["general_count"] == 2
    assert c.get("/api/words?language=en&set=banana").status_code == 422


def test_add_a_word_straight_into_a_set(make_user):
    c = make_user("alice")
    s = make_set(c)
    assert add(c, "cheese", set_id=s["id"])["set_id"] == s["id"]
    assert c.post("/api/words", json={"language": "en", "word": "ham", "set_id": 9999}).status_code == 404


def test_names_are_unique_per_language_ignoring_case_and_general_is_reserved(make_user):
    c = make_user("alice")
    make_set(c, "Food")
    assert c.post("/api/sets", json={"language": "en", "name": "food"}).status_code == 409
    make_set(c, "Food", "es")                                           # another language may reuse the name
    for bad in ("", "   ", "General", "x" * 41):
        assert c.post("/api/sets", json={"language": "en", "name": bad}).status_code == 422
    assert c.post("/api/sets", json={"language": "xx", "name": "A"}).status_code in (404, 422)


def test_at_most_twenty_sets_per_language(make_user):
    c = make_user("alice")
    for i in range(20):
        make_set(c, f"Set {i}")
    assert c.post("/api/sets", json={"language": "en", "name": "One more"}).status_code == 422
    make_set(c, "Spanish one", "es")


def test_rename_and_delete_a_set_never_deletes_its_words(make_user):
    c = make_user("alice")
    s = make_set(c)
    w = add(c, "water", set_id=s["id"])
    assert c.patch(f"/api/sets/{s['id']}", json={"name": "Drinks"}).json()["name"] == "Drinks"
    assert c.patch(f"/api/sets/{s['id']}", json={"name": "General"}).status_code == 422
    assert c.delete(f"/api/sets/{s['id']}").json() == {"moved_to_general": 1}
    words = c.get("/api/words?language=en&set=general").json()["items"]
    assert [x["id"] for x in words] == [w["id"]] and words[0]["set_id"] is None
    assert c.delete(f"/api/sets/{s['id']}").status_code == 404


def test_nobody_else_can_see_rename_delete_or_fill_your_set(make_user):
    a, b = make_user("alice"), make_user("bob")
    s = make_set(a)
    word = add(b, "bob-word")
    assert b.get("/api/sets?language=en").json()["items"] == []
    assert b.patch(f"/api/sets/{s['id']}", json={"name": "Mine"}).status_code == 404
    assert b.delete(f"/api/sets/{s['id']}").status_code == 404
    assert b.post("/api/words/move", json={"ids": [word["id"]], "set_id": s["id"]}).status_code == 404
    assert b.post("/api/words", json={"language": "en", "word": "sneaky", "set_id": s["id"]}).status_code == 404
    assert a.get("/api/sets?language=en").json()["items"][0]["count"] == 0
    # a's words cannot be moved by b either
    own = add(a, "alice-word")
    assert b.post("/api/words/move", json={"ids": [own["id"]], "set_id": None}).json() == {"moved": 0}


def test_words_of_another_language_are_not_moved_into_a_set(make_user):
    c = make_user("alice")
    es = add(c, "agua", "es")
    s = make_set(c)
    assert c.post("/api/words/move", json={"ids": [es["id"]], "set_id": s["id"]}).json() == {"moved": 0}


def test_stories_use_only_the_chosen_sets(conn, make_user):
    c = make_user("alice")
    uid = c.get("/api/me").json()["id"]
    s = make_set(c, "Food")
    for w in ("water", "bread"):
        add(c, w)
    for w in ("cheese", "apple"):
        add(c, w, set_id=s["id"])
    assert vocab.load_words(conn, uid, "en") == ["water", "bread", "cheese", "apple"]
    assert vocab.load_words(conn, uid, "en", [0]) == ["water", "bread"]
    assert vocab.load_words(conn, uid, "en", [s["id"]]) == ["cheese", "apple"]
    assert vocab.load_words(conn, uid, "en", [0, s["id"]]) == ["water", "bread", "cheese", "apple"]
    assert vocab.load_words(conn, uid, "en", []) == []
    prompts = []

    def call(prompt):
        prompts.append(prompt)
        return "plan\n===STORY===\nAna: Hello."
    r = generate_story(conn, uid, "en", call_groq_fn=call, use_cache=False, set_ids=[s["id"]])
    assert "cheese" in prompts[-1] and "water" not in prompts[-1] and r.words_total == 2
    assert generate_story(conn, uid, "en", call_groq_fn=call, use_cache=False, set_ids=[]).reason == "empty_vocabulary"


def test_another_learners_set_id_gives_no_words(conn, make_user):
    a, b = make_user("alice"), make_user("bob")
    s = make_set(a)
    add(a, "secret", set_id=s["id"])
    bid = b.get("/api/me").json()["id"]
    add(b, "bobs")
    assert vocab.load_words(conn, bid, "en", [s["id"]]) == []
    with pytest.raises(vocab.VocabError):
        vocab.load_words(conn, bid, "en", ["1; DROP TABLE tutor.words"])
    with pytest.raises(vocab.VocabError):
        vocab.load_words(conn, bid, "en", [-1])


def test_download_my_data_includes_sets(make_user):
    c = make_user("alice")
    s = make_set(c, "Food")
    add(c, "cheese", set_id=s["id"])
    r = c.get("/api/me/export")
    assert r.status_code == 200
    data = r.json()
    assert data["word_sets"][0]["name"] == "Food" and data["words"][0]["set_name"] == "Food"


# --- the one set-filter clause (used by the vocabulary list, "write missing meanings" and practice) -----------------------

def test_filter_clause_all_general_id_and_a_bad_value():
    import pytest
    from app.errors import AppError
    from app.services.word_sets import filter_clause
    assert filter_clause(None) == ("", []) and filter_clause("all") == ("", []) and filter_clause("") == ("", [])
    assert filter_clause("general") == (" AND set_id IS NULL", [])
    assert filter_clause("12") == (" AND set_id = %s", [12]) and filter_clause(12) == (" AND set_id = %s", [12])
    assert filter_clause("general", "w.set_id") == (" AND w.set_id IS NULL", [])
    assert filter_clause("3", "w.set_id") == (" AND w.set_id = %s", [3])
    for bad in ("nope", "1; DROP TABLE x", "-1", "1.5"):
        with pytest.raises(AppError):
            filter_clause(bad)
