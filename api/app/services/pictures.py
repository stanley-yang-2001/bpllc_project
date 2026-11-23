"""Pictures for words: one per word, either an emoji or the learner's own photo.

A photo is never stored as it came. It is opened as an image (a file that only says it is one is refused), turned the right way up, drawn on
white (no transparency), scaled down to FULL pixels on its long side and written again as a JPEG. That drops everything the camera added,
the place the photo was taken included, and a file that is not really a picture. A small copy (THUMB pixels) is kept for lists."""
from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

from ..db import cursor
from ..errors import not_found, validation_error

FULL = 512                       # pixels on the long side of the stored photo
THUMB = 96                       # and of the small copy that lists use
MAX_UPLOAD_BYTES = 1_500_000     # what is read of an upload; the page shrinks a photo to about 100 KB first, and nginx allows 2 MB
MAX_PIXELS = 16_000_000          # a picture with more pixels than this (4000 x 4000) is refused before it is decoded
MAX_PHOTOS = 200                 # per learner (emoji have no limit: they take a few bytes)
FORMATS = ("JPEG", "PNG", "WEBP", "GIF")
MAX_EMOJI_CHARS = 16             # the longest emoji sequences (a family with skin tones, a flag of a region) are 11 characters or fewer

NOT_A_PICTURE = "That file isn't a picture we can use. Choose a JPEG, PNG, WebP or GIF image."


# ---------------------------------------------------------------- emoji
# Where the emoji (and the signs that are used as emoji) are in Unicode. Anything outside these ranges is not accepted, so the field
# cannot hold letters, digits, control or direction characters, only a picture.
_PICTOGRAPHS = ((0xA9, 0xA9), (0xAE, 0xAE), (0x203C, 0x203C), (0x2049, 0x2049), (0x2122, 0x2122), (0x2139, 0x2139), (0x2190, 0x21FF),
                (0x2300, 0x23FF), (0x24C2, 0x24C2), (0x25A0, 0x25FF), (0x2600, 0x27BF), (0x2900, 0x297F), (0x2B00, 0x2BFF), (0x3030, 0x3030),
                (0x303D, 0x303D), (0x3297, 0x3297), (0x3299, 0x3299), (0x1F000, 0x1FAFF))
_ZWJ = "‍"                  # joins the parts of one emoji (a family, a person with a job)
_VS16 = "️"                 # asks for the picture form of a sign
_KEYCAP = "⃣"
_TONES = "\U0001F3FB\U0001F3FC\U0001F3FD\U0001F3FE\U0001F3FF"
_REGIONAL = range(0x1F1E6, 0x1F200)           # two of these make a country flag
_BLACK_FLAG, _TAG_CANCEL = "\U0001F3F4", "\U000E007F"      # the flag of a region: the black flag, tag letters, then the cancel tag


def _pictograph(ch: str) -> bool:
    cp = ord(ch)
    return cp not in _REGIONAL and any(low <= cp <= high for low, high in _PICTOGRAPHS)       # a flag's letters only count in pairs


def _part(text: str) -> bool:
    """One picture: a pictograph, then at most a picture-form mark and a skin tone."""
    return 0 < len(text) <= 3 and _pictograph(text[0]) and all(c == _VS16 or c in _TONES for c in text[1:])


def is_emoji(text: str) -> bool:
    """True for exactly one emoji: a picture, a keycap (1️⃣), a country flag, a flag of a region, or pictures joined with the zero-width joiner."""
    if not text or len(text) > MAX_EMOJI_CHARS:
        return False
    if text[-1] == _KEYCAP:
        return text[0] in "#*0123456789" and text[1:-1] in ("", _VS16)
    if len(text) == 2 and all(ord(c) in _REGIONAL for c in text):
        return True
    if text[0] == _BLACK_FLAG and len(text) > 2 and text[-1] == _TAG_CANCEL:
        return all(0xE0020 <= ord(c) <= 0xE007E for c in text[1:-1])
    return all(_part(p) for p in text.split(_ZWJ))


def clean_emoji(text) -> str:
    text = (text or "").strip()
    if not is_emoji(text):
        raise validation_error("Choose one emoji.")
    return text


# ---------------------------------------------------------------- photos
def _bad(message: str = NOT_A_PICTURE):
    return validation_error(message)


def _jpeg(img: Image.Image, size: int, quality: int) -> bytes:
    small = img.copy()
    small.thumbnail((size, size), Image.Resampling.LANCZOS)         # only ever shrinks
    out = io.BytesIO()
    small.save(out, "JPEG", quality=quality, optimize=True)          # nothing but the pixels is written: no camera data, no location
    return out.getvalue()


def make_photo(raw: bytes) -> tuple[bytes, bytes]:
    """The stored photo and its small copy, both JPEG, made from an uploaded file. Raises a validation error for anything else."""
    if not raw:
        raise _bad("Choose a picture to upload.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise _bad(f"That picture is too big. Choose one under {MAX_UPLOAD_BYTES / 1_000_000:.1f} MB.")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in FORMATS:
            raise _bad()
        if img.width * img.height > MAX_PIXELS:
            raise _bad("That picture has too many pixels. Choose a smaller one.")
        if img.format == "JPEG":
            img.draft("RGB", (FULL * 2, FULL * 2))                   # the decoder can skip detail we would throw away
        img = ImageOps.exif_transpose(img)                           # a phone photo is often stored sideways with a note on how to turn it
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            flat = Image.new("RGB", rgba.size, (255, 255, 255))
            flat.paste(rgba, mask=rgba.getchannel("A"))
            img = flat
        else:
            img = img.convert("RGB")
        return _jpeg(img, FULL, 82), _jpeg(img, THUMB, 78)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise _bad()


# ---------------------------------------------------------------- the database
def _describe(word_id: int, row: dict) -> dict:
    if row["kind"] == "emoji":
        return {"kind": "emoji", "emoji": row["emoji"], "url": None, "thumb_url": None}
    url = f"/api/words/{word_id}/picture?v={row['version']}"          # the number changes with the photo, so a changed photo is a new address
    return {"kind": "photo", "emoji": None, "url": url, "thumb_url": url + "&size=thumb"}


_COLS = "word_id, kind, emoji, (extract(epoch FROM updated_at) * 1000000)::bigint AS version"


def _owned(cur, user_id: int, word_id: int) -> None:
    cur.execute("SELECT 1 FROM words WHERE id = %s AND user_id = %s", (word_id, user_id))
    if not cur.fetchone():
        raise not_found("Word not found.")


def by_word(conn, word_ids) -> dict[int, dict]:
    """{word id: picture} for the words that have one. The caller has already established whose words these are."""
    ids = list({int(i) for i in word_ids})
    if not ids:
        return {}
    with cursor(conn) as cur:
        cur.execute(f"SELECT {_COLS} FROM word_pictures WHERE word_id = ANY(%s)", (ids,))
        return {r["word_id"]: _describe(r["word_id"], r) for r in cur.fetchall()}


def attach(conn, rows: list[dict], key: str = "id") -> list[dict]:
    """Puts each word's picture (or None) on its row, in one query for all of them."""
    found = by_word(conn, [r[key] for r in rows])
    for r in rows:
        r["picture"] = found.get(r[key])
    return rows


def set_emoji(conn, user_id: int, word_id: int, emoji) -> dict:
    emoji = clean_emoji(emoji)
    with cursor(conn) as cur:
        _owned(cur, user_id, word_id)
        cur.execute(f"INSERT INTO word_pictures (word_id, user_id, kind, emoji) VALUES (%s, %s, 'emoji', %s) "
                    f"ON CONFLICT (word_id) DO UPDATE SET kind = 'emoji', emoji = EXCLUDED.emoji, image = NULL, thumb = NULL, updated_at = clock_timestamp() "
                    f"RETURNING {_COLS}", (word_id, user_id, emoji))
        return _describe(word_id, cur.fetchone())


def set_photo(conn, user_id: int, word_id: int, raw: bytes) -> dict:
    with cursor(conn) as cur:
        _owned(cur, user_id, word_id)
        cur.execute("SELECT count(*) AS n FROM word_pictures WHERE user_id = %s AND kind = 'photo' AND word_id <> %s", (user_id, word_id))
        if cur.fetchone()["n"] >= MAX_PHOTOS:
            raise validation_error(f"You can keep {MAX_PHOTOS} photos. Remove one, or use an emoji for this word.")
        image, thumb = make_photo(raw)
        cur.execute(f"INSERT INTO word_pictures (word_id, user_id, kind, image, thumb) VALUES (%s, %s, 'photo', %s, %s) "
                    f"ON CONFLICT (word_id) DO UPDATE SET kind = 'photo', emoji = NULL, image = EXCLUDED.image, thumb = EXCLUDED.thumb, "
                    f"updated_at = clock_timestamp() RETURNING {_COLS}", (word_id, user_id, image, thumb))
        return _describe(word_id, cur.fetchone())


def photo(conn, user_id: int, word_id: int, small: bool = False) -> bytes:
    with cursor(conn) as cur:
        cur.execute(f"SELECT {'thumb' if small else 'image'} AS data FROM word_pictures WHERE word_id = %s AND user_id = %s AND kind = 'photo'",
                    (word_id, user_id))
        row = cur.fetchone()
    if not row:
        raise not_found("This word has no photo.")
    return bytes(row["data"])


def remove(conn, user_id: int, word_id: int) -> None:
    """Takes the picture off the word (no error if it had none)."""
    with cursor(conn) as cur:
        _owned(cur, user_id, word_id)
        cur.execute("DELETE FROM word_pictures WHERE word_id = %s AND user_id = %s", (word_id, user_id))


def export_rows(conn, user_id: int) -> list[dict]:
    """Every picture the learner has, for "Download my data": a photo as a data address, which any browser opens."""
    with cursor(conn) as cur:
        cur.execute("SELECT w.language, w.word, p.kind, p.emoji, p.image, p.created_at, p.updated_at FROM word_pictures p "
                    "JOIN words w ON w.id = p.word_id WHERE p.user_id = %s ORDER BY w.language, w.word", (user_id,))
        rows = cur.fetchall()
    for r in rows:
        data = r.pop("image")
        r["photo"] = "data:image/jpeg;base64," + base64.b64encode(bytes(data)).decode("ascii") if data is not None else None
    return rows
