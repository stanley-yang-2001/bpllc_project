"""Pictures for words: the emoji check, what happens to an uploaded photo, who can see it, and where it shows up."""
import base64
import io

import psycopg2
import pytest
from PIL import Image, features

from app.errors import AppError
from app.services import pictures
from conftest import DB_URL, register

BREAD = "\U0001F35E"


def db(sql, *args):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def image_bytes(fmt="JPEG", size=(80, 60), color=(30, 120, 200), mode="RGB", **save):
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, fmt, **save)
    return out.getvalue()


def camera_jpeg(size=(2000, 1000)):
    """A big photo as a phone makes it: stored sideways with a note to turn it, and with the camera and the place it was taken in."""
    exif = Image.Exif()
    exif[0x0112] = 6                                          # orientation: turn 90 degrees to see it upright
    exif[0x010F] = "TestCamera"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (47.0, 36.0, 0.0), "W", (122.0, 20.0, 0.0)
    return image_bytes("JPEG", size, exif=exif)


def photo_of(data):
    return Image.open(io.BytesIO(data))


def add_word(client, word="bread", meaning="a food"):
    r = client.post("/api/words", json={"language": "en", "word": word, "meaning": meaning})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def put_photo(client, word_id, data, name="photo.jpg"):
    return client.put(f"/api/words/{word_id}/picture/photo", files={"file": (name, data, "image/jpeg")})


def put_emoji(client, word_id, emoji=BREAD):
    return client.put(f"/api/words/{word_id}/picture/emoji", json={"emoji": emoji})


# ------------------------------------------------------------------ the emoji check
@pytest.mark.parametrize("text", [
    BREAD, "⚽", "☀️", "❤️", "\U0001F44D\U0001F3FD",                   # a picture, a sign, a sign in picture form, with a skin tone
    "\U0001F468‍\U0001F469‍\U0001F467‍\U0001F466",                              # a family: four pictures joined
    "❤️‍\U0001F525", "\U0001F3F3️‍\U0001F308",                        # heart on fire, rainbow flag
    "\U0001F1EB\U0001F1F7",                                                                    # the flag of France
    "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",                 # the flag of England
    "1️⃣", "#️⃣", "©", " " + BREAD + " ",                             # keycaps, a sign used as emoji, spaces around
])
def test_these_are_one_emoji(text):
    assert pictures.clean_emoji(text) == text.strip()


@pytest.mark.parametrize("text", [
    "", " ", "a", "bread", "1", "#", BREAD + BREAD, BREAD + "a", "a" + BREAD, "<script>", "‮" + BREAD,      # nothing, text, two, a direction mark
    "‍" + BREAD, BREAD + "‍", "\U0001F1EB", "\U0001F1EB\U0001F1F7\U0001F1E9\U0001F1EA", "⃣",     # a lone joiner, half a flag, two flags
    "x" * 40, BREAD * 20, "\x00" + BREAD, "\U0001F3F4\U000E0067", None,
])
def test_these_are_not(text):
    with pytest.raises(AppError) as e:
        pictures.clean_emoji(text)
    assert e.value.status == 422


# ------------------------------------------------------------------ what becomes of a photo
def test_a_big_sideways_phone_photo_is_turned_scaled_and_stripped_of_what_the_camera_added():
    raw = camera_jpeg((2000, 1000))
    assert b"TestCamera" in raw and Image.open(io.BytesIO(raw)).getexif().get_ifd(0x8825)            # the input does carry it
    full, thumb = pictures.make_photo(raw)
    img = photo_of(full)
    assert img.format == "JPEG" and img.size == (256, 512)                  # turned upright (1000 x 2000), then scaled to 512 on the long side
    assert len(img.getexif()) == 0 and b"TestCamera" not in full and b"Exif" not in full          # no camera, no orientation note, no place
    assert photo_of(thumb).size == (48, 96)
    assert len(full) < 100_000 and len(thumb) < 10_000


def test_a_small_picture_is_not_enlarged():
    full, thumb = pictures.make_photo(image_bytes("PNG", (50, 40)))
    assert photo_of(full).size == (50, 40) and photo_of(thumb).size == (50, 40)


def test_transparency_becomes_white():
    full, _ = pictures.make_photo(image_bytes("PNG", (40, 40), (255, 0, 0, 0), mode="RGBA"))          # fully transparent
    assert photo_of(full).getpixel((20, 20))[0:3] == (255, 255, 255)


def test_a_gif_gives_its_first_picture():
    frames = [Image.new("RGB", (30, 30), c) for c in ((255, 0, 0), (0, 0, 255))]
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:])
    full, _ = pictures.make_photo(out.getvalue())
    r, g, b = photo_of(full).getpixel((15, 15))
    assert r > 200 and b < 60


@pytest.mark.skipif(not features.check("webp"), reason="this Pillow has no WebP")
def test_webp_is_accepted():
    full, _ = pictures.make_photo(image_bytes("WEBP", (64, 64)))
    assert photo_of(full).format == "JPEG"


@pytest.mark.parametrize("raw", [
    b"", b"hello", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"<html><body>hi</body></html>",
    b"\xff\xd8\xff\xe0" + b"\x00" * 50,                                          # starts like a JPEG, is not one
    image_bytes("JPEG")[:200],                                                    # a JPEG cut off
    image_bytes("BMP"), image_bytes("TIFF"),                                      # real pictures of a kind we do not take
    b"PK\x03\x04" + b"\x00" * 100,                                                # a zip
])
def test_a_file_that_is_not_a_usable_picture_is_refused(raw):
    with pytest.raises(AppError) as e:
        pictures.make_photo(raw)
    assert e.value.status == 422


def test_a_picture_with_too_many_pixels_is_refused_before_it_is_decoded():
    huge = image_bytes("PNG", (5000, 4000), 0, mode="1")                          # 20 million pixels, a few KB in the file
    assert len(huge) < 100_000
    with pytest.raises(AppError, match="too many pixels"):
        pictures.make_photo(huge)


def test_a_file_over_the_size_limit_is_refused():
    with pytest.raises(AppError, match="too big"):
        pictures.make_photo(b"\xff" * (pictures.MAX_UPLOAD_BYTES + 1))


# ------------------------------------------------------------------ the routes
def test_an_emoji_is_set_shows_in_the_list_and_can_be_replaced(client):
    register(client, "alice")
    wid = add_word(client)
    assert client.get("/api/words", params={"language": "en"}).json()["items"][0]["picture"] is None
    r = put_emoji(client, wid)
    assert r.status_code == 200 and r.json() == {"kind": "emoji", "emoji": BREAD, "url": None, "thumb_url": None}
    assert client.get("/api/words", params={"language": "en"}).json()["items"][0]["picture"] == r.json()
    assert put_emoji(client, wid, "\U0001F9C0").json()["emoji"] == "\U0001F9C0"
    assert db("SELECT count(*) FROM tutor.word_pictures")[0][0] == 1


@pytest.mark.parametrize("emoji", ["", "bread", BREAD + BREAD, "x" * 100])
def test_a_bad_emoji_is_refused_and_changes_nothing(client, emoji):
    register(client, "alice")
    wid = add_word(client)
    put_emoji(client, wid)
    assert put_emoji(client, wid, emoji).status_code == 422
    assert client.get("/api/words", params={"language": "en"}).json()["items"][0]["picture"]["emoji"] == BREAD


def test_a_photo_is_kept_small_and_served_only_to_its_owner(client, make_user):
    register(client, "alice")
    wid = add_word(client)
    r = put_photo(client, wid, camera_jpeg())
    assert r.status_code == 200, r.text
    pic = r.json()
    assert pic["kind"] == "photo" and pic["emoji"] is None
    assert pic["url"].startswith(f"/api/words/{wid}/picture?v=") and pic["thumb_url"] == pic["url"] + "&size=thumb"
    full, thumb = client.get(pic["url"]), client.get(pic["thumb_url"])
    assert full.status_code == 200 and full.headers["content-type"] == "image/jpeg" and full.headers["cache-control"] == "no-store"
    assert photo_of(full.content).size == (256, 512) and photo_of(thumb.content).size == (48, 96) and b"TestCamera" not in full.content
    assert client.get("/api/words", params={"language": "en"}).json()["items"][0]["picture"] == pic
    bob = make_user("bob")
    assert bob.get(pic["url"]).status_code == 404                                       # someone else's word
    assert put_photo(bob, wid, image_bytes()).status_code == 404
    assert put_emoji(bob, wid).status_code == 404 and bob.delete(f"/api/words/{wid}/picture").status_code == 404
    assert client.get(pic["url"]).status_code == 200                                    # and bob changed nothing


def test_a_new_photo_has_a_new_address_and_an_emoji_takes_the_photos_place(client):
    register(client, "alice")
    wid = add_word(client)
    first = put_photo(client, wid, image_bytes(color=(255, 0, 0))).json()
    second = put_photo(client, wid, image_bytes(color=(0, 0, 255))).json()
    assert first["url"] != second["url"]
    assert db("SELECT count(*) FROM tutor.word_pictures")[0][0] == 1
    assert put_emoji(client, wid).json()["kind"] == "emoji"
    assert client.get(second["url"]).status_code == 404                                 # the photo is gone
    assert db("SELECT kind, image IS NULL, thumb IS NULL FROM tutor.word_pictures") == [("emoji", True, True)]
    put_photo(client, wid, image_bytes())
    assert db("SELECT kind, emoji IS NULL FROM tutor.word_pictures") == [("photo", True)]


def test_a_bad_upload_is_refused_and_keeps_the_picture_the_word_had(client):
    register(client, "alice")
    wid = add_word(client)
    put_emoji(client, wid)
    for data in (b"not a picture", b"", image_bytes("BMP")):
        r = put_photo(client, wid, data)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert client.put(f"/api/words/{wid}/picture/photo").status_code == 422             # no file at all
    assert client.get("/api/words", params={"language": "en"}).json()["items"][0]["picture"]["emoji"] == BREAD


def test_the_size_must_be_full_or_thumb(client):
    register(client, "alice")
    wid = add_word(client)
    put_photo(client, wid, image_bytes())
    assert client.get(f"/api/words/{wid}/picture?size=huge").status_code == 422
    assert client.get(f"/api/words/{wid}/picture").status_code == 200


def test_a_word_with_an_emoji_or_nothing_has_no_photo_to_fetch(client):
    register(client, "alice")
    wid = add_word(client)
    assert client.get(f"/api/words/{wid}/picture").status_code == 404
    put_emoji(client, wid)
    assert client.get(f"/api/words/{wid}/picture").status_code == 404
    assert client.get("/api/words/99999/picture").status_code == 404


def test_removing_a_picture_keeps_the_word_and_can_be_repeated(client):
    register(client, "alice")
    wid = add_word(client)
    put_photo(client, wid, image_bytes())
    assert client.delete(f"/api/words/{wid}/picture").status_code == 204
    assert client.delete(f"/api/words/{wid}/picture").status_code == 204
    assert client.get("/api/words", params={"language": "en"}).json()["items"][0]["picture"] is None
    assert db("SELECT count(*) FROM tutor.word_pictures")[0][0] == 0 and db("SELECT count(*) FROM tutor.words")[0][0] == 1


def test_photos_are_limited_per_learner_but_emoji_and_replacing_are_not(client, monkeypatch):
    monkeypatch.setattr(pictures, "MAX_PHOTOS", 2)
    register(client, "alice")
    a, b, c = (add_word(client, w) for w in ("one", "two", "three"))
    assert put_photo(client, a, image_bytes()).status_code == 200 and put_photo(client, b, image_bytes()).status_code == 200
    r = put_photo(client, c, image_bytes())
    assert r.status_code == 422 and "2 photos" in r.json()["error"]["message"]
    assert put_photo(client, a, image_bytes(color=(1, 2, 3))).status_code == 200            # a new photo for a word that has one
    assert put_emoji(client, c).status_code == 200                                          # an emoji is not a photo


def test_one_learners_photos_do_not_count_for_another(client, make_user, monkeypatch):
    monkeypatch.setattr(pictures, "MAX_PHOTOS", 1)
    bob = make_user("bob")
    put_photo(bob, add_word(bob), image_bytes())
    register(client, "alice")
    assert put_photo(client, add_word(client), image_bytes()).status_code == 200


# ------------------------------------------------------------------ where it shows up
def test_a_picture_goes_with_the_word_when_it_is_edited(client):
    register(client, "alice")
    wid = add_word(client)
    put_emoji(client, wid)
    r = client.patch(f"/api/words/{wid}", json={"meaning": "baked food"})
    assert r.status_code == 200 and r.json()["picture"]["emoji"] == BREAD


def test_the_flashcard_carries_the_picture(client):
    register(client, "alice")
    with_pic, without = add_word(client, "bread", "a food"), add_word(client, "stone", "a rock")
    put_emoji(client, with_pic)
    cards = {c["word"]: c["picture"] for c in client.get("/api/practice/flashcards?language=en").json()["items"]}
    assert cards == {"bread": {"kind": "emoji", "emoji": BREAD, "url": None, "thumb_url": None}, "stone": None}


def test_the_reader_card_carries_the_picture(client):
    register(client, "alice")
    wid = add_word(client)
    put_photo(client, wid, image_bytes())
    body = client.post("/api/reading/gloss", json={"language": "en", "text": "She ate the bread."}).json()
    assert [w["word"] for w in body["words"]] == ["bread"] and body["words"][0]["picture"]["kind"] == "photo"
    assert client.get(body["words"][0]["picture"]["thumb_url"]).status_code == 200


# ------------------------------------------------------------------ the learner's data
def test_download_my_data_has_the_pictures_and_a_photo_opens(client):
    register(client, "alice")
    wid, other = add_word(client), add_word(client, "cheese", "a food")
    put_emoji(client, other)
    put_photo(client, wid, image_bytes(size=(60, 40)))
    rows = {r["word"]: r for r in client.get("/api/me/export").json()["word_pictures"]}
    assert rows["cheese"]["kind"] == "emoji" and rows["cheese"]["emoji"] == BREAD and rows["cheese"]["photo"] is None
    prefix = "data:image/jpeg;base64,"
    assert rows["bread"]["kind"] == "photo" and rows["bread"]["photo"].startswith(prefix) and rows["bread"]["emoji"] is None
    assert photo_of(base64.b64decode(rows["bread"]["photo"][len(prefix):])).size == (60, 40)
    assert set(rows["bread"]) == {"language", "word", "kind", "emoji", "photo", "created_at", "updated_at"}


def test_a_picture_goes_when_its_word_goes(client):
    register(client, "alice")
    wid = add_word(client)
    put_photo(client, wid, image_bytes())
    assert client.post("/api/words/delete", json={"ids": [wid]}).status_code == 200
    assert db("SELECT count(*) FROM tutor.word_pictures")[0][0] == 0


def test_pictures_go_with_the_account_and_other_accounts_keep_theirs(client, make_user):
    bob = make_user("bob")
    put_emoji(bob, add_word(bob, "keep"))
    register(client, "alice")
    put_photo(client, add_word(client), image_bytes())
    put_emoji(client, add_word(client, "cheese"))
    assert db("SELECT count(*) FROM tutor.word_pictures")[0][0] == 3
    assert client.post("/api/me/delete", json={"password": "password123"}).status_code == 204
    assert db("SELECT count(*) FROM tutor.word_pictures")[0][0] == 1
    assert bob.get("/api/words", params={"language": "en"}).json()["items"][0]["picture"]["emoji"] == BREAD


def test_the_table_cannot_hold_a_picture_that_is_neither_an_emoji_nor_a_photo(client):
    register(client, "alice")
    wid = add_word(client)
    for sql in ("INSERT INTO tutor.word_pictures (word_id, user_id, kind) VALUES (%s, 1, 'emoji')",                                  # an emoji with no emoji
                "INSERT INTO tutor.word_pictures (word_id, user_id, kind, emoji, image, thumb) VALUES (%s, 1, 'emoji', 'x', 'a', 'b')",
                "INSERT INTO tutor.word_pictures (word_id, user_id, kind, image) VALUES (%s, 1, 'photo', 'a')",                       # no small copy
                "INSERT INTO tutor.word_pictures (word_id, user_id, kind, emoji) VALUES (%s, 1, 'sticker', 'x')"):
        with pytest.raises(psycopg2.errors.CheckViolation):
            db(sql, wid)


def test_every_emoji_in_the_pickers_grid_is_accepted_by_the_server():
    """The grid is web/src/pictures/emojis.json; a click on one the server refuses would show the learner an error for a button we offered."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "web" / "src" / "pictures" / "emojis.json"
    if not path.exists():
        pytest.skip("the web folder is not here")
    groups = json.loads(path.read_text(encoding="utf-8"))
    refused = [e for items in groups.values() for e in items if not pictures.is_emoji(e)]
    assert not refused


# ------------------------------------------------------------------ the picture quiz
def test_the_picture_quiz_asks_only_about_pictured_words_and_offers_words(client):
    register(client, "alice")
    ids = {w: add_word(client, w, m) for w, m in (("bread", "a food"), ("stone", "a rock"), ("milk", "a drink"), ("tree", None), ("door", "an entry"))}
    put_emoji(client, ids["bread"])
    put_photo(client, ids["tree"], image_bytes())                       # a word with no meaning can still be asked
    body = client.get("/api/practice/choices", params={"language": "en", "direction": "picture"}).json()
    items = {i["answer"]: i for i in body["items"]}
    assert set(items) == {"bread", "tree"} and body["total"] == 2
    bread = items["bread"]
    assert bread["direction"] == "picture" and bread["prompt"] == "a food" and bread["picture"]["emoji"] == BREAD
    assert len(bread["choices"]) == 4 and "bread" in bread["choices"] and set(bread["choices"]) <= set(ids)
    assert items["tree"]["prompt"] == "" and items["tree"]["picture"]["kind"] == "photo"


def test_the_picture_quiz_needs_a_picture_and_two_words(client):
    register(client, "alice")
    a = add_word(client, "bread", "a food")
    assert client.get("/api/practice/choices", params={"language": "en", "direction": "picture"}).json()["items"] == []
    put_emoji(client, a)
    assert client.get("/api/practice/choices", params={"language": "en", "direction": "picture"}).json()["items"] == []     # one word: nothing to choose between
    add_word(client, "stone", "a rock")
    assert len(client.get("/api/practice/choices", params={"language": "en", "direction": "picture"}).json()["items"]) == 1


def test_the_picture_quiz_with_due_only_and_an_unknown_direction(client):
    register(client, "alice")
    a, b = add_word(client, "bread", "a food"), add_word(client, "stone", "a rock")
    put_emoji(client, a)
    r = client.get("/api/practice/choices", params={"language": "en", "direction": "picture", "due": "true"}).json()
    assert [i["answer"] for i in r["items"]] == ["bread"]
    assert client.get("/api/practice/choices", params={"language": "en", "direction": "sound"}).status_code == 422


def test_an_answer_to_a_picture_question_is_recorded_with_its_direction(client):
    register(client, "alice")
    a = add_word(client)
    r = client.post("/api/practice/answers", json={"answers": [{"word_id": a, "correct": True, "mode": "choices", "direction": "picture"}]})
    assert r.status_code == 204, r.text
    assert db("SELECT mode, direction FROM tutor.review_log") == [("choices", "picture")]
