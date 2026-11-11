"""key_status.py with a fake Groq: headers and refusals are read, keys are never written (11 Nov 2026)."""
import io
import json
import sys
import urllib.error

sys.path[:0] = ["tutor_core", "scripts"]
import key_status  # noqa: E402


class Resp:
    def __init__(self, headers, status=200):
        self.headers, self.status = headers, status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_reads_the_headers_and_never_stores_the_key(tmp_path):
    seen = []

    def opener(req, timeout=0):
        seen.append(req.get_header("Authorization"))
        return Resp({"x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "7990", "x-ratelimit-reset-tokens": "75ms",
                     "x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "940", "x-ratelimit-reset-requests": "1m26s"})
    env = {"GROQ_API_KEY": "secretkey1", "GROQ_API_KEY_2": "secretkey2", "GROQ_MODEL": "m"}
    out = tmp_path / "s.json"
    rows = key_status.main(["--out", str(out)], opener=opener, environ=env)
    assert [r["var"] for r in rows] == ["GROQ_API_KEY", "GROQ_API_KEY_2"] and rows[0]["remaining_tokens"] == 7990 and rows[0]["limit_requests"] == 1000
    assert seen == ["Bearer secretkey1", "Bearer secretkey2"]
    saved = out.read_text()
    assert "secretkey" not in saved and json.loads(saved)["keys"][1]["family"] == "GROQ_API_KEY"


def test_a_refused_key_reports_which_limit(tmp_path):
    msg = b'{"error":{"message":"Rate limit reached on tokens per day (TPD): Limit 200000, Used 199500, Requested 1. Please try again in 5m37s"}}'

    def opener(req, timeout=0):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {"x-ratelimit-remaining-requests": "0"}, io.BytesIO(msg))
    rows = key_status.main(["--out", str(tmp_path / "s.json")], opener=opener, environ={"GROQ_API_KEY": "k", "GROQ_MODEL": "m"})
    assert not rows[0]["ok"] and rows[0]["http"] == 429 and rows[0]["refused"] == {"kind": "TPD", "limit": 200000, "used": 199500, "try_again_in": "5m37s"}
    assert rows[0]["remaining_requests"] == 0


def test_missing_key_and_unset_qwen_model_are_skipped(tmp_path):
    rows = key_status.main(["--out", str(tmp_path / "s.json")], opener=lambda *a, **k: Resp({}), environ={"GROQ_API_KEY": "k", "GROQ_QWEN_API_KEY": "q"})
    assert [r["family"] for r in rows] == ["GROQ_API_KEY"]
