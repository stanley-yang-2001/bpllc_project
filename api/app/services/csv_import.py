"""Adding words from a CSV file: reading the file, then adding the rows (each one checked like a word typed by hand)."""
from __future__ import annotations

import csv
import io

from tutor_core import vocab as tutor_vocab
from tutor_core.words import WordError, validate_meaning, validate_word

from ..db import cursor
from ..errors import validation_error


def parse_csv(raw: bytes, max_bytes: int, max_rows: int) -> list[tuple[int, str, str]]:
    """Return [(row_number, word, meaning)]. Row numbers match the file (header is row 1)."""
    if len(raw) > max_bytes:
        raise validation_error(f"File is larger than {max_bytes // 1000} KB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise validation_error("File must be UTF-8 text.")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        raise validation_error("File is empty.")
    cols = [c.strip().lower() for c in header]
    if "word" not in cols:
        raise validation_error("The first row must have a 'word' column.")
    wi = cols.index("word")
    mi = next((cols.index(n) for n in ("meaning", "definition") if n in cols), None)
    rows = []
    for n, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(rows) >= max_rows:
            raise validation_error(f"More than {max_rows} rows.")
        word = row[wi] if wi < len(row) else ""
        meaning = row[mi] if mi is not None and mi < len(row) else ""
        rows.append((n, word, meaning))
    return rows


def bulk_add(conn, user_id: int, language: str, rows: list[tuple[int, str, str]]) -> dict:
    added = duplicates = 0
    invalid: list[dict] = []
    with cursor(conn) as cur:
        for n, word, meaning in rows:
            try:
                w, m = validate_word(word, language), validate_meaning(meaning)
            except WordError as e:
                invalid.append({"row": n, "reason": str(e)})
                continue
            if tutor_vocab.insert_word(cur, user_id, language, w, m):
                added += 1
            else:
                duplicates += 1
        if added:
            tutor_vocab.note_language(cur, user_id, language)
    return {"added": added, "duplicates": duplicates, "invalid_count": len(invalid), "invalid": invalid[:20]}
