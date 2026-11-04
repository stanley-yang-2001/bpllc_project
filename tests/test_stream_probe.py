"""scripts/stream_probe.py: how it reads Langflow's event stream (no Langflow needed)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import stream_probe as p  # noqa: E402


def tok(t, text="a"):
    return (t, "token", {"chunk": text})


def test_words_that_arrive_over_time_are_streaming():
    r = p.summarize([(0.1, "add_message", {}), tok(1.0), tok(1.4), tok(2.0), (3.0, "end", {})])
    assert r["token_events"] == 3 and r["seconds_between_first_word_and_end"] == 2.0 and "as they come" in r["verdict"]


def test_one_burst_or_a_single_token_is_no_gain():
    assert "one burst" in p.summarize([tok(5.0), tok(5.05), tok(5.1), (5.2, "end", {})])["verdict"]
    assert "one burst" in p.summarize([tok(5.0), (5.1, "end", {})])["verdict"]


def test_no_token_events_means_no_streaming():
    r = p.summarize([(0.5, "add_message", {}), (4.0, "end", {})])
    assert r["token_events"] == 0 and "NO word events" in r["verdict"]


def test_empty_or_odd_chunks_do_not_count():
    assert p.summarize([(1.0, "token", {"chunk": ""}), (1.1, "token", "x"), (2.0, "end", {})])["token_events"] == 0


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"[PASS] {name}")
            except AssertionError as e:
                fails += 1
                print(f"[FAIL] {name} {e}")
    print("All tests passed." if not fails else f"{fails} failed")
    sys.exit(1 if fails else 0)
