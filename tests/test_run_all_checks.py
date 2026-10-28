"""Tests for scripts/run_all_checks.py: which checks a given set of options picks, the guards that stop it from touching a real
database, the table, and that it lists only files that exist. Nothing is run for real: the stages are swapped for fakes.

Run:  python -m pytest tests/test_run_all_checks.py -q     (or python tests/test_run_all_checks.py)
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_all_checks as rc  # noqa: E402


def ids(*argv):
    return [s.id for s in rc.selected(rc.parse(list(argv)))]


def test_default_is_only_the_unit_checks():
    chosen = rc.selected(rc.parse([]))
    assert chosen and {s.group for s in chosen} == {"unit"}
    assert "api" in ids() and "e2e" not in ids() and "m3-live" not in ids()


def test_stack_adds_stack_checks_but_no_model_calls():
    got = {s.group for s in rc.selected(rc.parse(["--stack"]))}
    assert got == {"unit", "stack"}


def test_live_and_all_include_everything():
    everything = [s.id for s in rc.STAGES]
    assert ids("--live") == everything and ids("--all") == everything


def test_only_keeps_the_order_given_and_skip_removes():
    assert ids("--only", "web-unit,core") == ["web-unit", "core"]
    assert "api" not in ids("--skip", "api")


def test_up_puts_the_stack_start_first_only_when_a_stack_check_is_chosen():
    assert ids("--stack", "--up")[0] == "stack-up"
    assert "stack-up" not in ids("--up")


def test_unknown_check_names_stop_with_a_message():
    for argv in (["--only", "nope"], ["--skip", "nope"]):
        try:
            rc.selected(rc.parse(argv))
        except SystemExit as e:
            assert "nope" in str(e)
        else:
            raise AssertionError("an unknown check name was accepted")


def test_native_needs_a_throwaway_database_url(monkeypatch=None):
    saved = os.environ.pop("TEST_DATABASE_URL", None)
    try:
        assert "TEST_DATABASE_URL" in (rc.native_guard(rc.parse(["--native"])) or "")
        assert rc.native_guard(rc.parse([])) is None
        os.environ["TEST_DATABASE_URL"] = "postgresql://x@localhost/t"
        assert rc.native_guard(rc.parse(["--native"])) is None
    finally:
        os.environ.pop("TEST_DATABASE_URL", None)
        if saved is not None:
            os.environ["TEST_DATABASE_URL"] = saved


def test_every_stage_has_a_group_a_reason_and_a_unique_id():
    assert len({s.id for s in rc.STAGES}) == len(rc.STAGES)
    for s in rc.STAGES:
        assert s.group in ("unit", "stack", "live") and s.title and s.why and callable(s.run)


def test_the_files_it_names_exist():
    for p in rc.LANGFLOW_ONLY_TESTS:
        assert (ROOT / p).is_file(), p
    for n in rc.HOST_ONLY_TESTS:
        assert (ROOT / "tests" / n).is_file(), n
    assert (ROOT / rc.NATIVE_DESELECT.split("::")[0]).is_file()
    assert (ROOT / rc.TEST_COMPOSE).is_file()
    assert (ROOT / "run-checks.bat").is_file()


def test_nothing_outside_the_langflow_list_needs_langflow():
    """Collecting every other test must not fail on an import: a new test that needs Langflow has to be added to LANGFLOW_ONLY_TESTS."""
    import subprocess
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in ("tutor_core", "scripts", "custom_components"))}
    cmd = [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q", "-p", "no:cacheprovider",
           "--ignore=tests/test_run_all_checks.py", *[f"--ignore={p}" for p in rc.LANGFLOW_ONLY_TESTS]]
    out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout[-800:] + out.stderr[-400:]


def test_test_compose_never_mounts_the_real_database():
    text = (ROOT / rc.TEST_COMPOSE).read_text(encoding="utf-8")
    assert "test-db" in text and "tmpfs" in text
    assert "postgres:5432" not in text and "pgdata" not in text


def test_table_and_exit_code(tmp_path=None):
    rows = [("core", rc.PASS, 3.2, ""), ("api", rc.FAIL, 40.0, "1 failed"), ("e2e", rc.SKIP, 0.0, "stack not running")]
    out = rc.table(rows)
    assert "core" in out and "FAIL" in out and "1 failed" in out and "stack not running" in out


def test_main_exit_codes_with_fake_stages():
    import tempfile
    saved_stages, saved_by_id, saved_root = list(rc.STAGES), dict(rc.BY_ID), rc.ROOT
    ok = rc.Stage("fake-ok", "unit", "ok", "never", lambda r: rc.Result(rc.PASS))
    bad = rc.Stage("fake-bad", "unit", "bad", "a fake failed", lambda r: rc.Result(rc.FAIL, "boom"))
    boom = rc.Stage("fake-boom", "unit", "boom", "raises", lambda r: 1 / 0)
    try:
        with tempfile.TemporaryDirectory() as d:
            rc.ROOT = Path(d)
            rc.STAGES[:] = [ok]
            rc.BY_ID.clear(); rc.BY_ID.update({s.id: s for s in rc.STAGES})
            assert rc.main([]) == 0
            rc.STAGES[:] = [ok, bad, boom]
            rc.BY_ID.clear(); rc.BY_ID.update({s.id: s for s in rc.STAGES})
            assert rc.main([]) == 1
            summaries = sorted(Path(d, "test-reports").glob("*/summary.json"))
            data = json.loads(summaries[-1].read_text(encoding="utf-8"))
            assert [r["result"] for r in data] == ["PASS", "FAIL", "FAIL"]
            assert rc.main(["--fail-fast"]) == 1
            data = json.loads(sorted(Path(d, "test-reports").glob("*/summary.json"))[-1].read_text(encoding="utf-8"))
            assert [r["result"] for r in data] == ["PASS", "FAIL", "SKIP"]
    finally:
        rc.STAGES[:] = saved_stages
        rc.BY_ID.clear(); rc.BY_ID.update(saved_by_id)
        rc.ROOT = saved_root


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  FAIL  {name}: {e!r}")
    sys.exit(1 if failed else 0)
