import io

from conftest import register


def add(client, word, language="en", **extra):
    return client.post("/api/words", json={"language": language, "word": word, **extra})


def test_add_normalizes_and_lists(client):
    register(client)
    r = add(client, '  "Bread." ', meaning="el pan")
    assert r.status_code == 201 and r.json()["word"] == "bread" and r.json()["meaning"] == "el pan"
    add(client, "water")
    page = client.get("/api/words", params={"language": "en"}).json()
    assert page["total"] == 2 and [w["word"] for w in page["items"]] == ["water", "bread"]   # newest first


def test_duplicate_is_conflict(client):
    register(client)
    add(client, "bread")
    r = add(client, "BREAD.")
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_invalid_words_rejected(client):
    register(client)
    for bad in ["", "a1", "x" * 41, "<script>"]:
        r = add(client, bad)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", bad
    assert add(client, "ok", language="xx").status_code == 422
    assert client.get("/api/words", params={"language": "en"}).json()["total"] == 0


def test_languages_are_separate_lists_and_german_keeps_case(client):
    register(client)
    add(client, "agua", "es")
    add(client, "Haus", "de")
    assert client.get("/api/words", params={"language": "en"}).json()["total"] == 0
    assert client.get("/api/words", params={"language": "de"}).json()["items"][0]["word"] == "Haus"
    assert "es" in client.get("/api/me").json()["languages"]       # adding a word registers the language


def test_search_escapes_wildcards(client):
    register(client)
    for w, m in [("bread", "the loaf"), ("water", None), ("rice", "50%")]:
        add(client, w, meaning=m)
    q = lambda s: [w["word"] for w in client.get("/api/words", params={"language": "en", "q": s}).json()["items"]]
    assert q("brea") == ["bread"] and q("LOAF") == ["bread"]
    assert q("%") == ["rice"] and q("_") == []                    # literal match, not a wildcard


def test_pagination(client):
    register(client)
    for i in range(5):
        add(client, f"word{chr(97 + i)}")
    page = client.get("/api/words", params={"language": "en", "limit": 2, "offset": 2}).json()
    assert page["total"] == 5 and len(page["items"]) == 2
    assert client.get("/api/words", params={"language": "en", "limit": 500}).status_code == 422


def test_patch_word(client):
    register(client)
    wid = add(client, "bread").json()["id"]
    other = add(client, "water").json()["id"]
    r = client.patch(f"/api/words/{wid}", json={"meaning": "pan"})
    assert r.json()["meaning"] == "pan" and r.json()["word"] == "bread"
    assert client.patch(f"/api/words/{wid}", json={"meaning": None}).json()["meaning"] is None   # clear it
    assert client.patch(f"/api/words/{wid}", json={"word": "Water"}).status_code == 409
    assert client.patch(f"/api/words/{other}", json={"word": "agua!"}).json()["word"] == "agua"
    assert client.patch("/api/words/9999", json={"meaning": "x"}).status_code == 404


def test_bulk_delete(client):
    register(client)
    ids = [add(client, w).json()["id"] for w in ("a1b".replace("1", "o"), "bread", "water")]
    assert client.post("/api/words/delete", json={"ids": ids[:2] + [9999]}).json() == {"deleted": 2}
    assert client.get("/api/words", params={"language": "en"}).json()["total"] == 1
    assert client.post("/api/words/delete", json={"ids": []}).status_code == 422


def csv_file(text: str, name="words.csv"):
    return {"file": (name, io.BytesIO(text.encode("utf-8")), "text/csv")}


def test_csv_upload_counts(client):
    register(client)
    body = "word,definition\nhello,a greeting\nhello,again\nWater.,\nbad1,x\n,\nthank you,gracias\n"
    r = client.post("/api/words/upload", data={"language": "en"}, files=csv_file(body))
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["added"], out["duplicates"], out["invalid_count"]) == (3, 1, 1)
    assert out["invalid"][0]["row"] == 5
    words = {w["word"]: w["meaning"] for w in client.get("/api/words", params={"language": "en"}).json()["items"]}
    assert words == {"hello": "a greeting", "water": None, "thank you": "gracias"}


def test_csv_utf8_bom_and_meaning_column(client):
    register(client)
    body = "\ufeffMeaning,Word\nel agua,agua\n"
    out = client.post("/api/words/upload", data={"language": "es"}, files=csv_file(body)).json()
    assert out["added"] == 1
    assert client.get("/api/words", params={"language": "es"}).json()["items"][0]["meaning"] == "el agua"


def test_csv_rejections(client):
    register(client)
    up = lambda body, **kw: client.post("/api/words/upload", data={"language": "en"}, files=body, **kw)
    assert up(csv_file("term\nbread\n")).status_code == 422                       # no word column
    assert up({"file": ("w.csv", io.BytesIO(b"word\n\xff\xfe\n"), "text/csv")}).status_code == 422   # not UTF-8
    assert up(csv_file("")).status_code == 422
    assert up(csv_file("word\n" + "x\n" * 10)).status_code == 200
    big = "word\n" + "".join(f"w{'a' * 5}\n" for _ in range(200_000))
    assert up(csv_file(big)).status_code == 422                                    # over 1 MB


def test_csv_row_limit(app, client):
    register(client)
    old = app.state.settings.upload_max_rows
    app.state.settings.upload_max_rows = 3
    try:
        r = client.post("/api/words/upload", data={"language": "en"}, files=csv_file("word\na\nb\nc\nd\n"))
        assert r.status_code == 422
    finally:
        app.state.settings.upload_max_rows = old


def test_starter_vocabulary_sample_file(client):
    import pathlib
    register(client)
    sample = pathlib.Path(__file__).resolve().parents[2] / "sample_data" / "starter_vocabulary.csv"
    r = client.post("/api/words/upload", data={"language": "en"}, files={"file": ("s.csv", sample.read_bytes(), "text/csv")})
    assert r.status_code == 200 and r.json()["added"] >= 10 and r.json()["invalid_count"] == 0
