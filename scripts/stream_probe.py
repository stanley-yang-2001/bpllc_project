"""Does Langflow send the Agent's words as they are written? (chat streaming, docs/CUSTOM-MODEL-DESIGN.md section 11)

Run inside the Langflow container; it asks the tutor flow a plain question with ?stream=true and prints every event with the
time it arrived, then says what it found. It uses the same login as the other scripts (--api-key, $LANGFLOW_API_KEY, or it logs in).

    docker compose exec langflow python /app/scripts/stream_probe.py

Reading the result: "token events: N" with N above 1 and the first one well before the end means words DO arrive as they are
written, so the chat page can show them. N of 0 or 1 means Langflow's Agent sends the answer whole: streaming cannot help.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MESSAGE = "Explain in about 120 words how to choose between 'ser' and 'estar' in Spanish."


def summarize(events) -> dict:
    """events: [(seconds, event name, data)] -> what the page could show. Pure, so it is tested."""
    kinds: dict = {}
    for _, name, _ in events:
        kinds[name] = kinds.get(name, 0) + 1
    tokens = [e for e in events if e[1] == "token" and isinstance(e[2], dict) and isinstance(e[2].get("chunk"), str) and e[2]["chunk"]]
    end = next((e for e in events if e[1] == "end"), None)
    first, last = (tokens[0][0], tokens[-1][0]) if tokens else (None, None)
    spread = None if not tokens or end is None else round(end[0] - first, 2)
    if not tokens:
        verdict = "NO word events: Langflow sends the answer whole, so streaming cannot show words early."
    elif len(tokens) == 1 or (spread is not None and spread < 0.3):
        verdict = "The words arrive in one burst at the end: the page would show them no earlier than today."
    else:
        verdict = "Words arrive while the answer is written: the chat page can show them as they come."
    return {"events": kinds, "token_events": len(tokens), "first_token_s": first, "last_token_s": last, "end_s": end[0] if end else None,
            "seconds_between_first_word_and_end": spread, "verdict": verdict}


def stream_events(url: str, payload: dict, key: str, timeout: float = 150):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "x-api-key": key})
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                yield round(time.monotonic() - start, 2), event.get("event"), event.get("data")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://localhost:7860")
    parser.add_argument("--flow", default="language-tutor")
    parser.add_argument("--api-key")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    args = parser.parse_args(argv)
    import spike_tweaks as m0
    key = m0.get_api_key(args.base, args.api_key)
    payload = m0.build_payload(args.message, f"probe-{uuid.uuid4().hex}")
    url = f"{args.base}/api/v1/run/{urllib.parse.quote(args.flow, safe='')}?stream=true"
    events = []
    try:
        for seconds, name, data in stream_events(url, payload, key):
            events.append((seconds, name, data))
            shown = json.dumps(data, ensure_ascii=False)
            print(f"{seconds:7.2f}s  {name:<12} {shown[:90]}", flush=True)
    except (urllib.error.URLError, OSError) as e:
        print(f"could not read the stream: {e}")
        return 2
    print()
    for k, v in summarize(events).items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
