"""Reading the model's answer: the passage after the delimiter."""
from __future__ import annotations

from .templates import DELIMITER

def extract_final_passage(raw_text, delimiter: str = DELIMITER) -> str:
    if not raw_text:
        return ""
    if delimiter in raw_text:
        _, _, after = raw_text.partition(delimiter)
        return after.strip()
    return raw_text.strip()

