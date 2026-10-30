"""The Langflow image has the word-splitting and lemma packages the story checks use (backlog card: install the extras in the image).

Without them a Chinese, Japanese or Korean story is checked on whole lines, and Spanish or French verb forms are not matched to the
word the learner added, so the same story can pass in the API and fail in chat (or the other way round).

    docker compose exec langflow python /app/tests/test_langflow_extras.py
"""
import importlib
import sys

PACKAGES = {"simplemma": "verb forms matched to the everyday word (Spanish, French and others)",
            "rjieba": "Chinese word splitting", "janome": "Japanese word splitting", "kiwipiepy": "Korean word splitting"}

failures = []
for name, why in PACKAGES.items():
    try:
        importlib.import_module(name)
        print(f"  PASS  {name} is installed ({why})")
    except Exception as e:           # a missing package, or one that cannot load
        failures.append(name)
        print(f"  FAIL  {name}: {type(e).__name__}: {e} ({why})")

try:
    from tutor_core import splitter
    for language, text in (("zh", "我喜欢喝水"), ("ja", "水を飲みます"), ("ko", "나는 물을 마셔요")):
        parts = splitter.split(text, language)
        ok = bool(parts) and len(parts) > 1
        print(f"  {'PASS' if ok else 'FAIL'}  {language} text is split into words")
        if not ok:
            failures.append(f"split-{language}")
except Exception as e:
    failures.append("splitter")
    print(f"  FAIL  tutor_core.splitter: {type(e).__name__}: {e}")

if failures:
    print("\nFAILED:", ", ".join(failures))
    sys.exit(1)
print("\nAll tests passed.")
