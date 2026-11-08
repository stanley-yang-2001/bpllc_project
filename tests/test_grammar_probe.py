"""The grammar probe corpus: built-in rules must raise no false alarm on the clean texts and keep a floor of recall.
    PYTHONPATH=tutor_core:scripts python tests/test_grammar_probe.py"""
import sys

sys.path[:0] = ["tutor_core", "scripts"]

from grammar_probe import build_layers, probe  # noqa: E402

failures = []


def check(label, ok, detail=""):
    print(("PASS" if ok else "FAIL"), label, detail if not ok else "")
    if not ok:
        failures.append(label)


def test_rules_layer():
    report = probe({"rules": build_layers(False)["rules"]})
    r = report["layers"]["rules"]
    check("no false alarm on any clean text", r["false_alarms"] == 0, str(r["by_language"]))
    check("the built-in rules find at least 40% of the injected mistakes", r["recall"] >= 0.4, str(r["recall"]))
    check("one injected mistake lowers the grammar part in at least 40% of cases", report["score_drop"]["share_that_lower_the_score"] >= 0.4)


def test_probe_with_a_fake_audit_layer_counts_overlaps():
    from tutor_core.quality.grammar import Hit
    perfect = lambda text, code: [Hit("audit", "x", "", start=0, end=len(text))]      # noqa: E731 - "finds" everything, also in clean text
    r = probe({"all": perfect}, ["es"])["layers"]["all"]
    check("a layer that flags everything has full recall and false alarms", r["recall"] == 1.0 and r["false_alarms"] == 1)


if __name__ == "__main__":
    test_rules_layer()
    test_probe_with_a_fake_audit_layer_counts_overlaps()
    print("\nFAILED:", failures) if failures else print("\nall passed")
    sys.exit(1 if failures else 0)
