"""
Tests for scripts/spike_model_tweaks.py (phase 2 spike, docs/CUSTOM-MODEL-DESIGN.md).

A spike that cannot fail answers nothing, so the suite is driven against a FAKE Langflow that behaves in several ways,
some correct and some deliberately broken, and talks to the spike's real fake model server over a real socket:

  * correct          the model node honours model_name, api_key and base_url of its own request       -> PASS
  * old node code    the node has no base_url field, so the address tweak is dropped                    -> FAIL, says "old code"
  * key dropped      the key tweak never arrives                                                       -> FAIL
  * shared state     a global "current settings" (a race between learners)                              -> FAIL, mixed up
  * sticky           an override survives into the next request without tweaks                          -> FAIL
  * sequential       a lock, so no two learners' calls overlap                                          -> INCONCLUSIVE
  * leaky            the key is echoed in the response                                                  -> FAIL
  * control errors   the no-tweaks request fails (rate limit)                                           -> INCONCLUSIVE, not FAIL
  * real provider    reply with and without the calculator result                                       -> PASS / INCONCLUSIVE
  * stored key       Langflow keeps the whole key / only its masked form / could not be searched        -> FAIL / PASS / INCONCLUSIVE
                     (reported next to the verdict, never inside it: it decides the design, not whether the override works)

No Langflow, Postgres or Groq needed; standard library only. Run from the repo root:  python tests/test_spike_model_tweaks.py
(also collected by pytest).
"""

import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import spike_model_tweaks as s  # noqa: E402
import spike_stored_key as st  # noqa: E402

NODE = "GroqLanguageModel-test1"
HOLD = 0.25


def call_model(base_url, model, api_key, stream=False):
    """What a Langflow model node does: one /chat/completions request. Returns the model's sentence."""
    req = urllib.request.Request(
        f"{base_url}/chat/completions", method="POST",
        data=json.dumps({"model": model, "stream": stream, "messages": [{"role": "user", "content": "hi"}]}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode()
    if stream:
        return "".join(json.loads(line[6:])["choices"][0]["delta"].get("content", "")
                       for line in body.splitlines() if line.startswith("data: {"))
    return json.loads(body)["choices"][0]["message"]["content"]


def shared_reply(message):
    """The shared Groq model (not the fake one)."""
    return {"outputs": [{"outputs": [{"results": {"message": {"text": "Hello from the shared model."}}}]}]}


class FakeFlow:
    """A fake Langflow `run` function with switchable behaviour."""

    def __init__(self, base_url_dropped=False, key_dropped=False, shared_state=False, sticky=False, sequential=False,
                 leaky=False, control_error=False, real_text=None):
        self.__dict__.update(locals())
        self.lock = threading.Lock()
        self.current = None       # the shared-state / sticky memory

    def __call__(self, message, session_id, tweaks):
        fields = dict((tweaks or {}).get(NODE, {}))
        if message == s.CALCULATOR and self.real_text is not None:
            return {"outputs": [{"outputs": [{"results": {"message": {"text": self.real_text}}}]}]}
        if self.base_url_dropped:
            fields.pop(s.URL_FIELD, None)
        if self.key_dropped:
            fields[s.KEY_FIELD] = ""
        if self.shared_state:
            self.current = fields or self.current
            threading_barrier_pause()
            fields = self.current or {}
        if self.sticky:
            if fields:
                self.current = fields
            fields = fields or self.current or {}
        if not fields.get(s.URL_FIELD):
            if self.control_error and not tweaks:
                raise RuntimeError("HTTP 429 from POST /run: rate limit")
            return shared_reply(message)
        if self.sequential:
            with self.lock:
                text = call_model(fields[s.URL_FIELD], fields[s.MODEL_FIELD], fields[s.KEY_FIELD], stream=True)
        else:
            text = call_model(fields[s.URL_FIELD], fields[s.MODEL_FIELD], fields[s.KEY_FIELD], stream=True)
        if self.leaky:
            text += f" (using {fields[s.KEY_FIELD]})"
        return {"outputs": [{"outputs": [{"results": {"message": {"text": text}}}]}]}


def threading_barrier_pause():
    import time
    time.sleep(0.05)


CLEAN = {"database": lambda keys, sessions: [], "messages": lambda keys, sessions: []}     # inspectors that find nothing


def suite(flow, users=3, skip_control=False, real=None, hold=HOLD, inspectors=CLEAN):
    with s.FakeModelServer(hold=hold) as fake:
        base = f"http://127.0.0.1:{fake.port}/v1"
        return s.run_suite(flow, fake.snapshot, base, NODE, users, skip_control, real, inspectors)


def statuses(result):
    return {name: status for name, (status, _) in result["checks"].items()}


# --- pure helpers ---------------------------------------------------------------------------------------------------------


def test_redaction_keeps_only_the_last_four_characters():
    assert s.redact("Bearer sk-secret-1234") == "Bearer ...1234"
    assert s.redact("Bearer ") == "" and s.redact(None) == ""
    tweaks = s.redact_tweaks(s.build_model_tweaks(NODE, "m", "sk-secret-1234", "http://x/v1"))
    assert tweaks[NODE][s.KEY_FIELD] == "...1234" and tweaks[NODE][s.MODEL_FIELD] == "m"
    assert s.redact_tweaks(None) is None
    assert s.safe_error("bad key sk-secret-1234 here", "sk-secret-1234") == "bad key *** here"


def test_tweaks_name_the_three_fields_of_the_model_node():
    tweaks = s.build_model_tweaks("N", "gpt", "k", "https://a/v1")
    assert tweaks == {"N": {"model_name": "gpt", "api_key": "k", "base_url": "https://a/v1"}}


def test_the_fake_model_answers_plain_and_streamed_requests_and_records_them():
    with s.FakeModelServer() as fake:
        base = f"http://127.0.0.1:{fake.port}/v1"
        assert call_model(base, "alpha", "key-a") == s.reply_text("alpha")
        assert call_model(base, "beta", "key-b", stream=True) == s.reply_text("beta")
        calls = fake.snapshot()
    assert [(c.model, c.authorization, c.stream) for c in calls] == [
        ("alpha", "Bearer key-a", False), ("beta", "Bearer key-b", True)]
    assert all(c.path == "/v1/chat/completions" and c.t1 >= c.t0 for c in calls)
    assert "key-a" not in json.dumps([c.as_dict() for c in calls])


def test_check_override_reasons():
    ok = s.Call("/v1/chat/completions", "Bearer k", "m", True, 0, 1)
    reply = {"x": s.reply_text("m")}
    assert s.check_override([ok], "m", "k", reply)[0] == s.PASS
    assert s.check_override([], "m", "k", reply)[0] == s.FAIL
    assert "OLD code" in s.check_override([], "m", "k", reply)[1]
    assert s.check_override([s.Call("/v1/chat/completions", "Bearer k", "other", True, 0, 1)], "m", "k", reply)[0] == s.FAIL
    assert s.check_override([s.Call("/v1/chat/completions", "Bearer ", "m", True, 0, 1)], "m", "k", reply)[0] == s.FAIL
    assert s.check_override([s.Call("/v1/other", "Bearer k", "m", True, 0, 1)], "m", "k", reply)[0] == s.FAIL
    assert s.check_override([ok], "m", "k", {"x": "no sentence"})[0] == s.INCONCLUSIVE


def test_check_isolation_and_overlap():
    a = s.Call("/v1/chat/completions", "Bearer ka", "ma", True, 0, 2)
    b = s.Call("/v1/chat/completions", "Bearer kb", "mb", True, 1, 3)
    expectations = {"ka": "ma", "kb": "mb"}
    assert s.check_isolation(expectations, [a, b])[0] == s.PASS
    assert s.check_isolation(expectations, [])[0] == s.FAIL
    swapped = s.Call("/v1/chat/completions", "Bearer ka", "mb", True, 0, 1)
    assert "MIXED UP" in s.check_isolation(expectations, [swapped, b])[1]
    assert s.check_isolation(expectations, [a])[0] == s.FAIL                      # kb never arrived
    stranger = s.Call("/v1/chat/completions", "Bearer zz", "ma", True, 0, 1)
    assert s.check_isolation(expectations, [a, b, stranger])[0] == s.FAIL
    assert s.calls_overlap([a, b])
    later = s.Call("/v1/chat/completions", "Bearer kb", "mb", True, 5, 6)
    assert not s.calls_overlap([a, later])
    assert s.check_overlap([a, later], s.PASS)[0] == s.INCONCLUSIVE
    assert s.check_overlap([a, b], s.FAIL)[0] == s.INCONCLUSIVE
    twin = s.Call("/v1/chat/completions", "Bearer ka", "ma", True, 1, 3)           # same learner twice is not isolation evidence
    assert not s.calls_overlap([a, twin])


def test_check_control_and_leak_and_real():
    assert s.check_control([], {"x": "Hello"})[0] == s.PASS
    assert s.check_control([s.Call("/", "", "m", True, 0, 1)], {"x": "Hello"})[0] == s.FAIL
    assert s.check_control([], {"x": s.reply_text("m")})[0] == s.FAIL
    assert s.check_control([], None, error="429 rate limit")[0] == s.INCONCLUSIVE
    assert s.check_no_key_in_responses(["secret-key-1"], [{"a": ["fine"]}])[0] == s.PASS
    assert s.check_no_key_in_responses(["secret-key-1"], [{"a": ["x secret-key-1 y"]}])[0] == s.FAIL
    assert s.check_real({"t": "It is 391."})[0] == s.PASS
    assert s.check_real({"t": "I cannot."})[0] == s.INCONCLUSIVE
    assert s.check_real(None, error="HTTP 400")[0] == s.ERROR


def test_verdict_needs_every_free_check():
    good = {n: (s.PASS, "") for n in ("override", "parallel", "overlap", "control", "no_leak")}
    assert s.key_verdict(good) == s.PASS
    assert s.key_verdict({**good, "control": (s.INCONCLUSIVE, "")}) == s.INCONCLUSIVE
    assert s.key_verdict({**good, "override": (s.FAIL, "")}) == s.FAIL
    assert s.key_verdict({**good, "real_provider": (s.ERROR, "")}) == s.FAIL
    assert s.key_verdict({**good, "real_provider": (s.INCONCLUSIVE, "")}) == s.PASS


# --- the whole suite against a fake Langflow ---------------------------------------------------------------------------------


def test_suite_correct_flow_passes():
    result = suite(FakeFlow())
    assert result["verdict"] == s.PASS, result["checks"]
    assert statuses(result) == {"override": s.PASS, "parallel": s.PASS, "overlap": s.PASS, "control": s.PASS, "no_leak": s.PASS,
                                "stored_key": s.PASS}


def test_suite_says_old_node_code_when_the_address_is_dropped():
    result = suite(FakeFlow(base_url_dropped=True))
    assert result["verdict"] == s.FAIL
    assert result["checks"]["override"][0] == s.FAIL and "OLD code" in result["checks"]["override"][1]


def test_suite_catches_a_dropped_key():
    result = suite(FakeFlow(key_dropped=True))
    assert result["verdict"] == s.FAIL and result["checks"]["override"][0] == s.FAIL
    assert "key tweak" in result["checks"]["override"][1]


def test_suite_catches_a_race_between_learners():
    result = suite(FakeFlow(shared_state=True), users=4)
    assert result["verdict"] == s.FAIL
    assert result["checks"]["parallel"][0] == s.FAIL


def test_suite_catches_an_override_that_sticks():
    result = suite(FakeFlow(sticky=True))
    assert result["verdict"] == s.FAIL
    assert result["checks"]["control"][0] == s.FAIL and "STUCK" in result["checks"]["control"][1]


def test_suite_does_not_pass_without_overlap():
    result = suite(FakeFlow(sequential=True), hold=0.05)
    assert result["checks"]["parallel"][0] == s.PASS
    assert result["checks"]["overlap"][0] == s.INCONCLUSIVE
    assert result["verdict"] == s.INCONCLUSIVE


def test_suite_catches_a_leaked_key():
    result = suite(FakeFlow(leaky=True))
    assert result["checks"]["no_leak"][0] == s.FAIL and result["verdict"] == s.FAIL


def test_a_failing_control_request_is_inconclusive_not_a_failure():
    result = suite(FakeFlow(control_error=True))
    assert result["checks"]["control"][0] == s.INCONCLUSIVE
    assert "rate limit" in result["checks"]["control"][1]
    assert result["verdict"] == s.INCONCLUSIVE


def test_skip_control_sends_no_request_without_tweaks():
    seen = []

    def run(message, session_id, tweaks):
        seen.append(tweaks)
        return FakeFlow()(message, session_id, tweaks)
    result = suite(run, skip_control=True)
    assert all(t for t in seen), "a request without tweaks was sent"
    assert result["checks"]["control"][0] == s.INCONCLUSIVE and result["verdict"] == s.INCONCLUSIVE


def test_real_provider_check_and_its_key_never_reaches_the_saved_output():
    real = ("real-model", "https://provider.example/v1", "sk-REAL-SECRET-9999")
    result = suite(FakeFlow(real_text="17 times 23 is 391."), real=real)
    assert result["checks"]["real_provider"][0] == s.PASS and result["verdict"] == s.PASS
    saved = json.dumps(result, default=str)
    assert "sk-REAL-SECRET-9999" not in saved and "spike-key-" not in saved
    weak = suite(FakeFlow(real_text="I do not know."), real=real)
    assert weak["checks"]["real_provider"][0] == s.INCONCLUSIVE and weak["verdict"] == s.PASS

    def failing(message, session_id, tweaks):
        if message == s.CALCULATOR:
            raise RuntimeError("HTTP 400: sk-REAL-SECRET-9999 does not support tools")
        return FakeFlow()(message, session_id, tweaks)
    broken = suite(failing, real=real)
    status, detail = broken["checks"]["real_provider"]
    assert status == s.ERROR and "sk-REAL-SECRET-9999" not in detail and "***" in detail and broken["verdict"] == s.FAIL


# --- where Langflow keeps the key (spike_stored_key.py) ---------------------------------------------------------------------


KEY = "spike-key-solo-0123456789ab"


def like_to_regex(pattern):
    """The LIKE patterns of spike_stored_key, as a regex (the fake database below has no LIKE)."""
    import re
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        out.append(".*" if c == "%" else "." if c == "_" else re.escape(c))
        i += 1
    return re.compile("".join(out), re.S)


class FakeCursor:
    """A cursor over {(schema, table): {column: [cell, ...]}} that understands only the two statements the scan sends."""

    def __init__(self, tables):
        self.tables, self.result, self.statements = tables, [], []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        if "information_schema.columns" in sql:
            self.result = [(sc, t, c) for (sc, t), cols in self.tables.items() for c in cols]
            return
        import re
        m = re.match(r'SELECT count\(\*\) FROM "((?:[^"]|"")*)"\."((?:[^"]|"")*)" WHERE "((?:[^"]|"")*)"::text LIKE ANY\(%s\)$', sql)
        assert m, f"unexpected statement: {sql}"
        schema, table, column = (g.replace('""', '"') for g in m.groups())
        patterns = [like_to_regex(p) for p in params[0]]
        n = sum(1 for cell in self.tables[(schema, table)][column] if any(p.fullmatch(cell) for p in patterns))
        self.result = [(n,)]

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0]

    def close(self):
        pass


def test_langflow_masks_like_its_source_does():
    assert st.langflow_mask("abcdefghijkl") == "***REDACTED***"         # 12 characters: too short to show a part
    assert st.langflow_mask("abcdefghijklm") == "abcd...jklm"
    assert st.langflow_mask(KEY) == "spik...89ab"


def test_identifiers_and_patterns_are_quoted():
    assert st.quote_identifier('a"b') == '"a""b"'
    assert st.like_pattern("a_b%c\\d") == "%a\\_b\\%c\\\\d%"
    assert like_to_regex(st.like_pattern("a_b%c")).fullmatch("xxa_b%cyy")
    assert not like_to_regex(st.like_pattern("a_b")).fullmatch("xxaXbyy")          # an escaped underscore is not a wildcard


def test_scan_finds_a_whole_key_and_a_masked_one_in_the_right_columns():
    tables = {
        ("public", "transaction"): {"inputs": ['{"api_key": "spik...89ab", "model_name": "m"}'], "status": ["success"]},
        ("public", "vertex_build"): {"params": [f"api_key={KEY}"], "data": ["{}"]},
        ("public", "flow"): {"data": ["nothing here"]},
        ('odd"schema', 'ta"ble'): {"co\"l": ["nothing"]},
    }
    cursor = FakeCursor(tables)
    findings = st.scan_database(cursor, [KEY])
    assert sorted(findings) == sorted([st.Finding("database transaction.inputs", st.MASKED),
                                       st.Finding("database vertex_build.params", st.FULL)])
    assert len(cursor.statements) == 1 + 2 * 6, "two queries per column, however many keys"
    assert KEY not in "".join(sql for sql, _ in cursor.statements), "the key goes in as a parameter, never into the SQL text"


def test_scan_of_a_short_key_looks_for_the_whole_key_only():
    cursor = FakeCursor({("public", "t"): {"c": ["x"]}})
    st.scan_database(cursor, ["short-key"])
    assert len(cursor.statements) == 1 + 1


def test_database_inspector_closes_what_it_opens():
    log = []

    class Conn:
        def cursor(self):
            cur = FakeCursor({("public", "t"): {"c": [KEY]}})
            close = cur.close
            cur.close = lambda: (log.append("cursor"), close())
            return cur

        def close(self):
            log.append("connection")
    assert st.database_inspector(Conn)([KEY], []) == [st.Finding("database t.c", st.FULL)]
    assert log == ["cursor", "connection"]


def test_messages_inspector():
    stored = {"s1": [{"text": f"hello {KEY}"}], "s2": [{"text": "key was spik...89ab"}], "s3": [{"text": "clean"}]}
    inspect = st.messages_inspector(lambda sid: stored[sid])
    found = inspect([KEY], ["s1", "s2", "s3"])
    assert [(f.where.split(",")[1].strip(), f.kind) for f in found] == [("session s1", st.FULL), ("session s2", st.MASKED)]


def test_run_inspectors_reports_a_failing_one_instead_of_stopping():
    def boom(keys, sessions):
        raise RuntimeError("no psycopg2")
    findings, errors = st.run_inspectors({"database": boom, "messages": lambda k, s: [st.Finding("m", st.MASKED)]}, [KEY], [])
    assert findings == {"messages": [st.Finding("m", st.MASKED)]} and errors == {"database": "RuntimeError: no psycopg2"}


def test_check_stored_key_outcomes():
    whole = {"database": [st.Finding("database vertex_build.params", st.FULL)], "messages": []}
    status, detail = st.check_stored_key(whole, {})
    assert status == s.FAIL and "WHOLE key" in detail and "vertex_build.params" in detail
    masked = {"database": [st.Finding("database transaction.inputs", st.MASKED)], "messages": []}
    status, detail = st.check_stored_key(masked, {})
    assert status == s.PASS and "masked form" in detail and "transaction.inputs" in detail
    assert st.check_stored_key({"database": [], "messages": []}, {})[0] == s.PASS
    status, detail = st.check_stored_key({"messages": []}, {"database": "ImportError: no psycopg2"})
    assert status == s.INCONCLUSIVE and "database: ImportError" in detail
    status, detail = st.check_stored_key({"messages": []}, {})
    assert status == s.INCONCLUSIVE and "not configured" in detail
    assert st.check_stored_key({"messages": [st.Finding("m", st.FULL)]}, {"database": "x"})[0] == s.FAIL      # found something: no need to look further


def test_a_stored_whole_key_is_a_finding_next_to_the_verdict_not_inside_it():
    leaking = {"database": lambda keys, sessions: [st.Finding("database vertex_build.params", st.FULL)], "messages": lambda k, sn: []}
    result = suite(FakeFlow(), inspectors=leaking)
    assert result["checks"]["stored_key"][0] == s.FAIL
    assert result["verdict"] == s.PASS, "the override itself works"
    report = s.format_report([result])
    assert "BUT Langflow stores the whole key" in report and "proxy" in report and "section 9" in report


def test_the_report_warns_when_the_storage_check_could_not_run():
    result = suite(FakeFlow(), inspectors={})
    assert result["checks"]["stored_key"][0] == s.INCONCLUSIVE and result["verdict"] == s.PASS
    assert "not fully checked" in s.format_report([result])
    assert "findstr" in s.format_report([result])


def test_the_suite_gives_the_inspectors_the_keys_it_sent_and_the_sessions_it_used():
    seen = {}

    def spy(keys, sessions):
        seen["keys"], seen["sessions"] = list(keys), list(sessions)
        return []
    result = suite(FakeFlow(), users=2, inspectors={"database": spy, "messages": spy})
    assert len(seen["keys"]) == 3 and all(k.startswith("spike-key-") for k in seen["keys"])       # solo + two parallel learners
    assert len(seen["sessions"]) == 4 and all(sid.startswith("u") for sid in seen["sessions"])     # + the control request
    assert result["checks"]["stored_key"][0] == s.PASS


def test_errors_get_the_explanation_the_langflow_source_gives():
    refused = s.explain_error("HTTP 422 from POST /run: {'detail': 'This deployment does not accept tweaks.'}")
    assert "LANGFLOW_TWEAKS_POLICY" in refused and "does not accept tweaks" in refused
    assert "api_editable" in s.explain_error("HTTP 422 ... This flow declares which fields the API may set.")
    assert "owns the flow" in s.explain_error("HTTP 404 from POST /run: Flow not found")
    assert s.explain_error("HTTP 500: something else") == "HTTP 500: something else"


def test_a_refused_tweak_reaches_the_report_with_its_explanation():
    def refusing(message, session_id, tweaks):
        if tweaks:
            raise RuntimeError("HTTP 422 from POST /run: This deployment does not accept tweaks.")
        return shared_reply(message)
    result = suite(refusing)
    assert result["checks"]["override"][0] == s.ERROR and "LANGFLOW_TWEAKS_POLICY" in result["checks"]["override"][1]
    assert result["checks"]["parallel"][0] == s.ERROR and "LANGFLOW_TWEAKS_POLICY" in result["checks"]["parallel"][1]
    assert result["verdict"] == s.FAIL


def test_scan_database_against_a_real_postgres():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        return skip("TEST_DATABASE_URL is not set")
    try:
        import psycopg2
    except ImportError:
        return skip("psycopg2 is not installed")
    schema = "spikescan_" + os.urandom(4).hex()
    key = s.new_key("pg")
    connection = psycopg2.connect(url)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{schema}"')
            cursor.execute(f'CREATE TABLE "{schema}"."transaction" (id int, inputs json, note text)')
            cursor.execute(f'CREATE TABLE "{schema}"."vertex_build" (id int, params text, data jsonb)')
            cursor.execute(f'CREATE TABLE "{schema}"."blob" (id int, raw bytea)')
            cursor.execute(f'INSERT INTO "{schema}"."transaction" VALUES (1, %s::json, %s)',
                           (json.dumps({"api_key": st.langflow_mask(key)}), "fine"))
            cursor.execute(f'INSERT INTO "{schema}"."vertex_build" VALUES (1, %s, %s::jsonb)', (f"key={key}", "{}"))
            cursor.execute(f'INSERT INTO "{schema}"."blob" VALUES (1, %s)', (psycopg2.Binary(key.encode()),))
        found = st.database_inspector(lambda: psycopg2.connect(url))([key], [])
        mine = sorted((f.where, f.kind) for f in found if f.where.split(".")[0].split()[1] in ("transaction", "vertex_build", "blob"))
        assert mine == [("database transaction.inputs", st.MASKED), ("database vertex_build.params", st.FULL)], mine
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.close()


# --- the spike's own copy of the flow, and "nothing was tested" -------------------------------------------------------------


def repo_flow():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "flows", "language-tutor.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def groq_node(flow):
    return next(n for n in flow["data"]["nodes"] if n["id"] == s.MODEL_NODE_ID)


def test_the_spike_flow_is_the_repo_flow_with_the_current_model_node():
    flow = repo_flow()
    before = json.dumps(flow, sort_keys=True)
    body = s.build_spike_flow(flow, "CODE", "abc123abc123", s.GROQ_URL)
    assert json.dumps(flow, sort_keys=True) == before, "the original flow must not be changed"
    inner = groq_node(body)["data"]["node"]
    assert inner["template"]["code"]["value"] == "CODE" and inner["metadata"]["code_hash"] == "abc123abc123"
    field = inner["template"]["base_url"]
    assert field["name"] == "base_url" and field["value"] == s.GROQ_URL and field["advanced"] is True
    assert field["_input_type"] == "StrInput" and field["type"] == "str" and field["display_name"] == "Base URL"
    assert inner["field_order"] == ["api_key", "model_name", "base_url"]
    assert inner["template"]["model_name"]["name"] == "model_name", "the field it was cloned from is untouched"
    assert body["endpoint_name"] == s.SPIKE_ENDPOINT and body["name"] == s.SPIKE_NAME and "id" not in body
    others = lambda f: {n["id"]: n for n in f["data"]["nodes"] if n["id"] != s.MODEL_NODE_ID}      # noqa: E731
    assert others(body) == others(flow), "no other node is touched"
    assert body["data"]["edges"] == flow["data"]["edges"]
    assert "id" in flow and flow["endpoint_name"] == "language-tutor"


def test_the_spike_flow_field_order_is_not_doubled_and_a_missing_node_is_refused():
    once = s.build_spike_flow(repo_flow(), "C", "h", s.GROQ_URL)
    twice = s.build_spike_flow(once, "C", "h", s.GROQ_URL)
    assert groq_node(twice)["data"]["node"]["field_order"].count("base_url") == 1
    try:
        s.build_spike_flow(repo_flow(), "C", "h", s.GROQ_URL, node_id="NoSuchNode")
    except ValueError as e:
        assert "NoSuchNode" in str(e) and "--key" in str(e)
    else:
        raise AssertionError("a missing model node must be refused")


def test_the_spike_flow_matches_the_component_file():
    """The code the spike pastes in is the component file, and it declares the field that the flow copy gets."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "custom_components", "groq_language_model.py")
    source = open(path, encoding="utf-8").read()
    assert 'name="base_url"' in source and s.GROQ_URL in source


def test_nothing_sent_means_nothing_was_tested():
    """When no request carrying a key reached Langflow (a 404, say), 'the key was found nowhere' is not a finding."""
    def missing(message, session_id, tweaks):
        raise RuntimeError("HTTP 404 from POST /run: Flow identifier language-tutor-spike not found")
    result = suite(missing, inspectors=CLEAN)
    assert result["checks"]["stored_key"][0] == s.INCONCLUSIVE and "nothing was tested" in result["checks"]["stored_key"][1]
    assert result["checks"]["no_leak"][0] == s.INCONCLUSIVE
    assert result["verdict"] == s.FAIL


def test_a_missing_flow_points_at_create_flow():
    hint = s.explain_error("HTTP 404 from POST http://x/api/v1/run/language-tutor-spike: Flow identifier language-tutor-spike not found")
    assert "--create-flow" in hint
    assert "owns the flow" in s.explain_error("HTTP 404 from POST /run: Flow not found"), "the other 404 keeps its own hint"


def test_the_storage_search_waits_for_langflow_to_write_its_records():
    slept, seen = [], []
    real = s.time.sleep
    s.time.sleep = slept.append
    try:
        suite_inspectors = {"database": lambda keys, sessions: seen.append(list(slept)) or [], "messages": lambda keys, sessions: []}
        with s.FakeModelServer(hold=0.0) as fake:
            base = f"http://127.0.0.1:{fake.port}/v1"
            s.run_suite(lambda m, sid, tw: shared_reply(m), fake.snapshot, base, NODE, 2, True, None, suite_inspectors, settle=7.0)
    finally:
        s.time.sleep = real
    assert 7.0 in slept and seen and 7.0 in seen[0], "the wait comes before the search"


def test_the_saved_file_keeps_the_verdict_and_the_replies_but_not_the_response_bodies():
    result = suite(lambda m, sid, tw: shared_reply(m), skip_control=True)
    slim = s.compact_results([result])[0]
    assert slim["verdict"] == result["verdict"] and slim["checks"] == result["checks"]
    assert slim["raw"] and all(set(r) == {"label", "session_id", "tweaks", "reply"} for r in slim["raw"])
    assert slim["raw"][0]["reply"] == ["Hello from the shared model."]
    assert len(json.dumps(slim)) < len(json.dumps(result)), "smaller than the full results"
    assert "raw" in result, "the original is not changed"


def test_report_text():
    good, bad = suite(FakeFlow()), suite(FakeFlow(base_url_dropped=True))
    report = s.format_report([good])
    assert "THE OVERRIDE WORKS" in report and "--real-model" in report
    assert "--real-model" not in s.format_report([good], real_requested=True)
    assert "NOT proven" in s.format_report([bad])


RUNNING_AS_SCRIPT = False


def skip(reason):
    """pytest reports a skip; run as a script it only says so."""
    if RUNNING_AS_SCRIPT:
        print(f"        (skipped: {reason})")
        return None
    import pytest
    pytest.skip(reason)


def main():
    global RUNNING_AS_SCRIPT
    RUNNING_AS_SCRIPT = True
    names = sorted(n for n in globals() if n.startswith("test_"))
    failed = []
    for name in names:
        try:
            globals()[name]()
            print(f"  PASS  {name}")
        except AssertionError as e:
            print(f"  FAIL  {name} {e}")
            failed.append(name)
    print()
    if failed:
        print(f"{len(failed)} test(s) failed: {failed}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
