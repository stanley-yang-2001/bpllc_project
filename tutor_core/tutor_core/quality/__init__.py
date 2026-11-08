"""Story quality: does a passage follow the rules the story prompt states? (Step 10, LO 7; moved here in M6 so the web API and Langflow can import it.)

Pure functions only (no database, no network). The work is split by what each part decides:

    vocabulary.py   which words are allowed (the learner's list, its inflections, grammar words, basic verbs)
    language.py     is the passage written in the requested language?
    endings.py      does it end on a finished sentence?
    fluency.py      telegraphic, repeated or monotonous sentences
    score.py        a 0 to 100 score against the requirements (example bank)
    grammar/        grammar findings from built-in rules, LanguageTool and a model review, all as one `Hit`
    passage.py      scoring one passage against all the rules
    reporting.py    the report Story Studio shows, and batch scoring with the same rules
    variety.py      are the stories different from one another?
    cli.py          check passages pasted into a text file

This package keeps the one import path callers have always used (`tutor_core.quality.report`, `.check_passage`, ...), including the
underscore helpers that scripts and tests reach for, by re-exporting every module-level name of its parts.
"""
from . import cli, endings, fluency, language, passage, reporting, score, variety, vocabulary

for _part in (vocabulary, language, endings, passage, fluency, score, reporting, variety, cli):
    globals().update({k: v for k, v in vars(_part).items() if not k.startswith("__") and k not in ("annotations",)})
del _part
