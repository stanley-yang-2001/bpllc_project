"""
Phase 2 spike (docs/CUSTOM-MODEL-DESIGN.md, sections 4 and 9): can the API hand ONE chat request its own model, key and address?

The Agent's model is a node inside the shared flow. Before any Chat code is written this spike answers, on your machine:

  1. OVERRIDE    tweaks {model_name, api_key, base_url} on the model node -> the model call goes to THAT address, with THAT
                 model name and THAT key as "Authorization: Bearer ...", and the Agent's reply is the fake model's reply.
  2. PARALLEL    several learners at the same moment, each with their own model and key -> every call carries its own pair,
                 never another learner's. Calls that did not overlap in time prove nothing and are reported INCONCLUSIVE.
  3. CONTROL     a request with NO tweaks, sent after the overrides -> still goes to the shared model (the fake server saw
                 nothing new). An override must never stick to the shared flow.
  4. NO LEAK     the key does not appear anywhere in the response Langflow returned.
  5. STORED KEY  (reported beside the verdict, because it decides the design rather than whether the override works) does
                 Langflow keep the whole key in its database or message store? Only a masked "abcd...wxyz" form is fine.
  6. REAL        (optional) your real provider: the Agent must be able to drive a tool (the calculator) with that model.

Checks 1 to 5 cost nothing and need no second provider: the script starts a tiny OpenAI-compatible server of its own and points
the model node at it, using throwaway keys it invents. Check 3 sends one ordinary chat turn to the shared Groq model.

Setup (once, on the canvas)
  1. Duplicate the "language tutor" flow; name the copy "language tutor spike" and give it the endpoint name
     language-tutor-spike (flow settings). (If you already have that copy from the M0 spike, reuse it.)
  2. Open the Groq node in the copy -> </> Code -> paste the whole of custom_components/groq_language_model.py -> Check &
     Save. The node now has an advanced field "Base URL" (this is the only code change; the real flow is not touched).
  3. The node id is in the exported JSON (in the repo flow it is GroqLanguageModel-h5DsK); the display name
     "Groq (via OpenAI-compatible)" works as the tweaks key too:
       python -c "import json,sys; [print(n['id'], n['data']['node']['display_name']) for n in json.load(open(sys.argv[1]))['data']['nodes']]" spike.json

Run (inside the Langflow container, so that the fake model server is reachable at 127.0.0.1; standard library only, plus
psycopg2, which the container has, for the storage search):

    docker compose exec langflow python /app/scripts/spike_model_tweaks.py --flow language-tutor-spike --key GroqLanguageModel-h5DsK

  --key X              node id and/or display name to use as the tweaks key (repeat to compare; the node id is the safe one)
  --users 3            how many learners run at once in check 2 (at least 2)
  --hold 2.0           seconds each fake model call lasts, so that parallel calls overlap
  --skip-control       do not send the no-tweaks request (it uses Groq tokens: about 2000)
  --db-url URL         Langflow's own database, searched for the throwaway keys (default $LANGFLOW_DATABASE_URL, which the
                       Langflow container has; without it the storage check can only look at the message store)
  --real-model M --real-base-url U      also run check 6 against your real provider; the key is read from the environment
                                        variable SPIKE_REAL_API_KEY (not the command line, so it stays out of your history):
                                            set SPIKE_REAL_API_KEY=...
                                            docker compose exec -e SPIKE_REAL_API_KEY langflow python /app/scripts/spike_model_tweaks.py ...
  --advertise-host H   the host name Langflow must use to reach this script (default 127.0.0.1; use host.docker.internal
                       with --listen-host 0.0.0.0 when running the script on Windows instead of in the container)

Afterwards look at Langflow's own log, which this script cannot read:  docker compose logs langflow | findstr /C:"spike-key-"
(no line should come out). The result is printed and saved to scripts/spike_model_tweaks_<time>.json (git-ignored, keys cut to
their last four characters). Paste the printed report back.
"""

import argparse
import json
import os
import sys
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import spike_stored_key as stored  # where Langflow keeps a key it was sent
import spike_tweaks as m0  # the Langflow HTTP helpers and the PASS/FAIL words of the M0 spike

PASS, FAIL, INCONCLUSIVE, ERROR = m0.PASS, m0.FAIL, m0.INCONCLUSIVE, m0.ERROR

MARKER = "MODELSPIKE"
MODEL_FIELD, KEY_FIELD, URL_FIELD = "model_name", "api_key", "base_url"       # input names on the model node
HELLO = "Say hello in one short sentence."
CALCULATOR = "Use your calculator tool to work out 17 times 23, then tell me the result."
CALCULATOR_ANSWER = "391"

_sleep = time.sleep      # replaced in tests


# --- the fake model server (an OpenAI-compatible /chat/completions that records what it was sent) -------------------------


class Call:
    """One request the fake model received."""

    def __init__(self, path, authorization, model, stream, t0, t1=0.0):
        self.path, self.authorization, self.model, self.stream, self.t0, self.t1 = path, authorization, model, stream, t0, t1

    def as_dict(self):
        return {"path": self.path, "model": self.model, "stream": self.stream, "t0": self.t0, "t1": self.t1,
                "authorization": redact(self.authorization)}


def redact(authorization) -> str:
    """Never keep a whole key in a saved file: keep only the last four characters."""
    value = (authorization or "").removeprefix("Bearer ").strip()
    return f"Bearer ...{value[-4:]}" if value else ""


def reply_text(model: str) -> str:
    return f"{MARKER} answered as {model}"


def completion_body(model: str, text: str) -> dict:
    return {"id": "chatcmpl-spike", "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def stream_chunks(model: str, text: str) -> list:
    """The server-sent events of a streamed answer (the Agent streams)."""
    def chunk(delta, finish=None):
        body = {"id": "chatcmpl-spike", "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        return f"data: {json.dumps(body)}\n\n".encode()
    return [chunk({"role": "assistant", "content": ""}), chunk({"content": text}), chunk({}, "stop"), b"data: [DONE]\n\n"]


class FakeModelServer:
    """Answers every chat request with a fixed sentence naming the model it was asked for, and holds each call for `hold`
    seconds so that calls from different learners genuinely overlap."""

    def __init__(self, host="127.0.0.1", port=0, hold=0.0):
        self.hold, self.calls, self._lock = hold, [], threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                t0 = time.time()
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                model = str(body.get("model", ""))
                call = Call(self.path, self.headers.get("Authorization", ""), model, bool(body.get("stream")), t0)
                if outer.hold:
                    _sleep(outer.hold)
                call.t1 = time.time()
                with outer._lock:
                    outer.calls.append(call)
                text = reply_text(model)
                if call.stream:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for part in stream_chunks(model, text):
                        self.wfile.write(part)
                        self.wfile.flush()
                    return
                data = json.dumps(completion_body(model, text)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.port = self.server.server_address[1]
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def snapshot(self) -> list:
        with self._lock:
            return list(self.calls)


# --- pure logic (tested in tests/test_spike_model_tweaks.py) --------------------------------------------------------------


def new_key(label: str) -> str:
    """A throwaway key that cannot be mistaken for a real one."""
    return f"spike-key-{label}-{uuid.uuid4().hex[:12]}"


def build_model_tweaks(node_key: str, model: str, api_key: str, base_url: str) -> dict:
    return {node_key: {MODEL_FIELD: model, KEY_FIELD: api_key, URL_FIELD: base_url}}


def strings_in(obj) -> list:
    """Every string anywhere in a response, whatever the nesting (the shape of Langflow's answer is not relied on)."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            found.append(node)

    walk(obj)
    return found


def reply_texts(response) -> list:
    """The Agent's reply text: the values of `text` fields when there are any (Langflow's message objects), else every string."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "text" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(response)
    return found or strings_in(response)


def reply_mentions(response, model: str) -> bool:
    return any(reply_text(model) in text for text in strings_in(response))


def check_override(calls, model: str, api_key: str, response) -> tuple:
    """The fake model must have been called with this model and this key, and the Agent must have answered with its reply."""
    if not calls:
        return FAIL, ("the fake model was never called. Either the base_url tweak was dropped (the node has OLD code: paste "
                      "custom_components/groq_language_model.py into it and save), or the tweaks key matches no node")
    wrong_path = [c.path for c in calls if not c.path.rstrip("/").endswith("/chat/completions")]
    if wrong_path:
        return FAIL, f"the model was called at an unexpected path: {wrong_path[0]}"
    wrong_model = sorted({c.model for c in calls if c.model != model})
    if wrong_model:
        return FAIL, f"the model name tweak did not arrive: expected {model!r}, the model received {wrong_model}"
    wrong_key = [c for c in calls if c.authorization != f"Bearer {api_key}"]
    if wrong_key:
        return FAIL, f"the key tweak did not arrive: the model received {redact(wrong_key[0].authorization)!r} (an empty value means the key was dropped)"
    if not reply_mentions(response, model):
        return INCONCLUSIVE, f"{len(calls)} call(s) arrived correctly, but the Agent's reply does not contain the model's sentence"
    return PASS, f"{len(calls)} call(s) arrived with the tweaked model, key and address; the Agent answered with the model's reply"


def check_isolation(expectations: dict, calls) -> tuple:
    """expectations: {api_key: model}. Every call must carry a (key, model) pair that belongs together, and every pair must
    have arrived at least once."""
    if not calls:
        return FAIL, "the fake model was never called"
    seen = set()
    for c in calls:
        key = c.authorization.removeprefix("Bearer ")
        if key not in expectations:
            return FAIL, f"a call carried a key that no learner sent: {redact(c.authorization)!r} (model {c.model!r})"
        if c.model != expectations[key]:
            return FAIL, (f"MIXED UP: a call with the key ending {key[-4:]} asked for model {c.model!r}, "
                          f"but that learner sent {expectations[key]!r}")
        seen.add(key)
    missing = [k[-4:] for k in expectations if k not in seen]
    if missing:
        return FAIL, f"learner(s) whose key ends {missing} never reached the model"
    return PASS, f"{len(calls)} call(s), every one carried its own learner's model and key"


def calls_overlap(calls) -> bool:
    """Did calls carrying DIFFERENT keys run at the same time?"""
    for i, a in enumerate(calls):
        for b in calls[i + 1:]:
            if a.authorization != b.authorization and a.t0 < b.t1 and b.t0 < a.t1:
                return True
    return False


def check_overlap(calls, isolation_status) -> tuple:
    if isolation_status != PASS:
        return INCONCLUSIVE, "not evaluated: the parallel run did not pass cleanly"
    if calls_overlap(calls):
        return PASS, "calls of different learners overlapped in time"
    return INCONCLUSIVE, "no two learners' calls overlapped, so this run proves nothing (raise --hold or --users)"


def check_control(new_calls, response, error=None) -> tuple:
    """No tweaks: the fake model must not have been called, and its sentence must not be in the reply."""
    if error:
        return INCONCLUSIVE, (f"the request without tweaks failed ({error}), so this says nothing about leaking. Usually Groq's rate "
                              "limit (wait a minute and re-run) or no GROQ_API_KEY in the container")
    if new_calls:
        return FAIL, f"an override STUCK: a request without tweaks still reached the tweaked address ({len(new_calls)} call(s))"
    if any(MARKER in text for text in strings_in(response)):
        return FAIL, "a request without tweaks answered with the fake model's sentence"
    return PASS, "a request without tweaks went to the shared model; nothing reached the fake one"


def check_no_key_in_responses(keys, responses) -> tuple:
    haystack = "\n".join(text for r in responses for text in strings_in(r))
    leaked = [k[-4:] for k in keys if k in haystack]
    if leaked:
        return FAIL, f"a key ending {leaked} appears in a response Langflow returned"
    return PASS, "no key appears in any response"


def check_real(response, error=None) -> tuple:
    if error:
        return ERROR, error
    texts = [t for t in reply_texts(response) if t.strip()]
    if any(CALCULATOR_ANSWER in t for t in texts):
        return PASS, f"the Agent drove its calculator tool with your model ({CALCULATOR_ANSWER} appears in the reply)"
    sample = max(texts, key=len)[:160] if texts else "(no text)"
    return INCONCLUSIVE, f"your model answered but {CALCULATOR_ANSWER} is not in the reply (it may not support tool calls): {sample!r}"


NOT_IN_VERDICT = ("stored_key",)     # a finding about WHERE the key is kept: it decides the design, not whether the override works


def key_verdict(checks: dict) -> str:
    """PASS only when nothing failed, and the five free checks all passed. Where Langflow stores the key is reported next to
    the verdict, not inside it."""
    statuses = [status for name, (status, _) in checks.items() if name not in NOT_IN_VERDICT]
    if FAIL in statuses or ERROR in statuses:
        return FAIL
    required = [checks.get(name) for name in ("override", "parallel", "overlap", "control", "no_leak")]
    if all(c and c[0] == PASS for c in required):
        return PASS
    return INCONCLUSIVE


# --- the suite (Langflow and the fake model are injected, so it can be tested with fakes) ---------------------------------


def run_suite(run, server_calls, base_url, node_key, users=3, skip_control=False, real=None, inspectors=None) -> dict:
    """`run(message, session_id, tweaks)` -> parsed JSON response (or raises). `server_calls()` -> the fake model's calls so
    far. `real` is None or (model, base_url, api_key). `inspectors` is {name: (keys, session_ids) -> [Finding]}, see
    spike_stored_key.py; none means the storage check says it could not look."""
    checks, raw, secrets = {}, [], []

    def call(message, label, tweaks):
        session_id = m0.make_session_id(label)
        response = run(message, session_id, tweaks)
        raw.append({"label": label, "session_id": session_id, "tweaks": redact_tweaks(tweaks), "response": response})
        return response

    # 1. override, one learner
    model, key = "spike-model-solo", new_key("solo")
    secrets.append(key)
    before = len(server_calls())
    try:
        response = call(HELLO, "solo", build_model_tweaks(node_key, model, key, base_url))
        checks["override"] = check_override(server_calls()[before:], model, key, response)
    except Exception as e:  # noqa: BLE001
        checks["override"] = (ERROR, explain_error(str(e)))

    # 2. parallel, every learner at the same moment, each with their own model and key
    learners = [(f"p{i}", f"spike-model-{i}", new_key(str(i))) for i in range(users)]
    secrets.extend(k for _, _, k in learners)
    expectations = {k: m for _, m, k in learners}
    barrier, errors = threading.Barrier(users), []
    before = len(server_calls())

    def worker(learner):
        label, learner_model, learner_key = learner
        try:
            barrier.wait(timeout=30)
        except threading.BrokenBarrierError:
            pass
        try:
            return call(HELLO, label, build_model_tweaks(node_key, learner_model, learner_key, base_url))
        except Exception as e:  # noqa: BLE001
            errors.append(explain_error(str(e)))

    with ThreadPoolExecutor(max_workers=users) as pool:
        list(pool.map(worker, learners))
    new = server_calls()[before:]
    if errors:
        checks["parallel"] = (ERROR, f"{len(errors)} request(s) failed, first: {errors[0]}")
    else:
        checks["parallel"] = check_isolation(expectations, new)
    checks["overlap"] = check_overlap(new, checks["parallel"][0])

    # 3. control: no tweaks, after the overrides
    if skip_control:
        checks["control"] = (INCONCLUSIVE, "skipped (--skip-control)")
    else:
        before = len(server_calls())
        try:
            response = call(HELLO, "control", None)
            checks["control"] = check_control(server_calls()[before:], response)
        except Exception as e:  # noqa: BLE001
            checks["control"] = check_control([], None, error=explain_error(str(e)))

    # 4. the keys must not be in any response
    checks["no_leak"] = check_no_key_in_responses(secrets, [r["response"] for r in raw])

    # 4b. where Langflow keeps the keys (a design finding, not part of the verdict)
    findings, inspect_errors = stored.run_inspectors(inspectors or {}, secrets, [r["session_id"] for r in raw])
    checks["stored_key"] = stored.check_stored_key(findings, inspect_errors)

    # 5. your real provider (optional)
    if real:
        real_model, real_url, real_key = real
        try:
            response = call(CALCULATOR, "real", build_model_tweaks(node_key, real_model, real_key, real_url))
            checks["real_provider"] = check_real(response)
            if check_no_key_in_responses([real_key], [response])[0] == FAIL:
                checks["no_leak"] = (FAIL, "your real key appears in a response Langflow returned")
        except Exception as e:  # noqa: BLE001
            checks["real_provider"] = check_real(None, error=explain_error(safe_error(str(e), real_key)))

    return {"key": node_key, "checks": checks, "verdict": key_verdict(checks), "raw": raw}


def redact_tweaks(tweaks):
    if not tweaks:
        return tweaks
    return {node: {field: (f"...{value[-4:]}" if field == KEY_FIELD and isinstance(value, str) else value)
                   for field, value in fields.items()} for node, fields in tweaks.items()}


def safe_error(message: str, secret: str) -> str:
    return message.replace(secret, "***") if secret else message


def explain_error(message: str) -> str:
    """Add what Langflow 1.12.2's source says about the refusals a tweak can meet (read from the source, not from a run)."""
    low = message.lower()
    if "does not accept tweaks" in low or "declares which fields" in low or "field is protected" in low:
        return (message + " || Langflow refused the tweak: LANGFLOW_TWEAKS_POLICY is not 'permissive' (the default), "
                "or a field of the flow is marked api_editable, or the field is protected")
    if "404" in message and "flow not found" in low:
        return (message + " || Langflow accepts tweaks only from the account that owns the flow (it answers 404 to anyone "
                "else): use an API key of the owner (--api-key)")
    return message


def format_report(results: list, real_requested=False) -> str:
    lines = []
    for result in results:
        lines.append(f"\nTweaks key {result['key']!r}")
        for name, (status, detail) in result["checks"].items():
            lines.append(f"  {status:<12} {name:<14} {detail}")
        lines.append(f"  => per-request model override with this key: {result['verdict']}")
    passed = [r for r in results if r["verdict"] == PASS]
    lines.append("")
    if passed:
        names = ", ".join(repr(r["key"]) for r in passed)
        stored_status = [r["checks"].get("stored_key", (INCONCLUSIVE, ""))[0] for r in passed]
        if FAIL in stored_status:
            lines.append(f"THE OVERRIDE WORKS with key(s): {names}, BUT Langflow stores the whole key (see stored_key). Do not send "
                         "learners' real keys to Langflow as tweaks: build phase 2 with the API-side model proxy "
                         "(docs/CUSTOM-MODEL-DESIGN.md, section 9, option B).")
        else:
            lines.append(f"THE OVERRIDE WORKS with key(s): {names}. Phase 2 can be built on tweaks; write it in the changelog.")
            if INCONCLUSIVE in stored_status:
                lines.append("Where Langflow keeps the key was not fully checked (see stored_key): run it inside the Langflow container, "
                             "where the database address is known, before sending real keys.")
        if not real_requested:
            lines.append("Not yet shown: that YOUR provider's model can drive the Agent's tools. Re-run with --real-model and --real-base-url.")
        lines.append("Also look at Langflow's own log for the key: docker compose logs langflow | findstr /C:\"spike-key-\" "
                     "(on Windows; grep -c spike-key- elsewhere). No line should come out.")
    else:
        lines.append("The override is NOT proven. Read the FAIL / ERROR / INCONCLUSIVE lines above; if no key style works, phase 2 needs a "
                     "different route (for example one flow per provider, or the API calling the model itself).")
    return "\n".join(lines)


def database_connect(db_url: str):
    """A function that opens a psycopg2 connection to Langflow's own database. psycopg2 is imported only when it is called, so a
    missing module is reported by the storage check instead of stopping the whole run."""
    def connect():
        import psycopg2
        return psycopg2.connect(db_url)
    return connect


def main(argv=None):
    parser = argparse.ArgumentParser(description="Phase 2 spike: per-request model override (see the module docstring).")
    parser.add_argument("--base-url", default="http://localhost:7860", help="Langflow's address")
    parser.add_argument("--flow", required=True, help="flow id or endpoint name, e.g. language-tutor-spike")
    parser.add_argument("--key", action="append", required=True, help="tweaks key: the model node's id and/or display name")
    parser.add_argument("--users", type=int, default=3)
    parser.add_argument("--hold", type=float, default=2.0)
    parser.add_argument("--skip-control", action="store_true")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--advertise-host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="port of the fake model (0 = any free port)")
    parser.add_argument("--real-model")
    parser.add_argument("--real-base-url")
    parser.add_argument("--api-key", help="Langflow API key (else $LANGFLOW_API_KEY, else it logs in and creates one)")
    parser.add_argument("--db-url", default=os.environ.get("LANGFLOW_DATABASE_URL", ""),
                        help="Langflow's own database, searched for the throwaway keys (default $LANGFLOW_DATABASE_URL, which the "
                             "Langflow container has; search skipped when empty)")
    parser.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args(argv)
    if args.users < 2:
        parser.error("--users must be at least 2: one learner alone proves nothing about isolation")
    if bool(args.real_model) != bool(args.real_base_url):
        parser.error("--real-model and --real-base-url go together")
    real = None
    if args.real_model:
        real_key = os.environ.get("SPIKE_REAL_API_KEY", "")
        if not real_key:
            parser.error("set the environment variable SPIKE_REAL_API_KEY to your provider's key (it is not taken from the command line)")
        real = (args.real_model, args.real_base_url.rstrip("/"), real_key)

    base = args.base_url.rstrip("/")
    langflow_key = m0.get_api_key(base, args.api_key)
    url = f"{base}/api/v1/run/{args.flow}?stream=false"

    def run(message, session_id, tweaks):
        return m0._request("POST", url, payload=m0.build_payload(message, session_id, tweaks), headers={"x-api-key": langflow_key})

    inspectors = {"messages": stored.messages_inspector(lambda sid: m0._request(
        "GET", f"{base}/api/v1/monitor/messages?session_id={urllib.parse.quote(sid)}", headers={"x-api-key": langflow_key}))}
    if args.db_url:
        connect = database_connect(args.db_url)
        inspectors["database"] = stored.database_inspector(connect)

    results = []
    with FakeModelServer(args.listen_host, args.port, args.hold) as fake:
        model_url = f"http://{args.advertise_host}:{fake.port}/v1"
        print(f"Fake model listening on {args.listen_host}:{fake.port}; Langflow will be told {model_url}", flush=True)
        for node_key in args.key:
            print(f"Running the suite for key {node_key!r} ...", flush=True)
            results.append(run_suite(run, fake.snapshot, model_url, node_key, args.users, args.skip_control, real, inspectors))
    print(format_report(results, real_requested=bool(real)))

    out = os.path.join(args.out_dir, f"spike_model_tweaks_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nRaw responses saved to {out}")
    return 0 if any(r["verdict"] == PASS for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
