"""Compare story-generation methods on one fixed set of requests (7 Nov 2026).

    variants.py      the methods, one row each: baseline, range prompt, two-pass, candidates, judge, repair, proofread, examples
    fixed_set.py     the fixed requests (same words, level, kind and topic every run, DB-free)
    runner.py        runs every request with every variant, rate-limit safe, timed, resumable, saved after each story
    report.py        the numbers and ONE html page: a column per method, a tab per language

Run it with scripts/run_story_methods.py.
"""
