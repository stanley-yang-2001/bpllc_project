"""Name, place and time of day chosen by code, not by the model (20 Nov 2026). Used only with StoryOptions.writer_v2.

Left to itself the writer picks the same few things: in the 150 English stories of the 19 Nov round "Maya" is the main character of 22, and "today" is in 77. A model asked for
"a random name" still chooses its favourite, so the code draws from short lists, one draw per story, from the same `rng` the word sample uses (a seeded run draws the same).

Names exist for English, Spanish, French and German, names that are ordinary in that language; for another language no name is given and the model chooses (a name list written
without a native speaker could put a wrong name in a Korean story, and a wrong name is worse than a repeated one). The place and the time of day are the same for every language: they
are given in English inside an English instruction, and the model writes them in the target language.
A diary or a letter is in the first person, so it gets a place and a time but no name; a dialogue gets two names for its two speakers."""
from __future__ import annotations

import random
from typing import Optional

NAMES = {
    "en": ["Tom", "Sara", "Ben", "Lily", "Omar", "Nina", "Jack", "Rosa", "Sam", "Ella", "Dan", "Ruth"],
    "es": ["Lucía", "Pablo", "Marta", "Diego", "Inés", "Javier", "Carmen", "Hugo", "Elena", "Raúl"],
    "fr": ["Camille", "Julien", "Léa", "Hugo", "Manon", "Théo", "Claire", "Nicolas", "Inès", "Paul"],
    "de": ["Lena", "Jonas", "Hanna", "Felix", "Greta", "Tim", "Mara", "Lukas", "Nele", "Paul"],
}
PLACES = ["a small bakery", "a bus stop", "a market", "a kitchen", "a park by a river", "a train station", "a library", "a street with shops", "a school yard",
          "a garden", "a café near the station", "a small hotel", "a hardware shop", "a lake", "a neighbour's flat", "a football field"]
TIMES = ["early morning", "a late morning", "just before lunch", "a quiet afternoon", "late afternoon", "early evening", "a rainy evening", "a cold winter morning",
         "a hot summer afternoon", "a Sunday"]
FIRST_PERSON = ("diary", "letter")


def pick(language: str, kind: Optional[str], rng=None) -> dict:
    """{"names": [...], "place": ..., "time": ...}: two names for a dialogue, one for a third-person text, none for a first-person kind or a language with no list."""
    rng = rng or random
    names = NAMES.get(language) or []
    if kind in FIRST_PERSON or not names:
        chosen = []
    else:
        chosen = rng.sample(names, 2 if kind == "dialogue" else 1)
    return {"names": chosen, "place": rng.choice(PLACES), "time": rng.choice(TIMES)}


def note(language: str, kind: Optional[str], rng=None) -> str:
    """One instruction for the prompt, for example 'Setting: a small bakery, early evening. The main character is called Lena.'"""
    s = pick(language, kind, rng)
    out = f"Setting: {s['place']}, {s['time']}."
    if len(s["names"]) == 2:
        out += f" The two speakers are called {s['names'][0]} and {s['names'][1]}."
    elif s["names"]:
        out += f" The main character is called {s['names'][0]}."
    elif kind in FIRST_PERSON:
        out += " Write in the first person; no name is needed."
    return out
