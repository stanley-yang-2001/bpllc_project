"""Runs every check the project has, in one command, and prints one table at the end.

Only the Python standard library is needed on your machine (plus Docker, and Node for the web checks). Run it from the
project folder:

    python scripts/run_all_checks.py                 # the unit checks: no real stack needed  (Windows: run-checks.bat)
    python scripts/run_all_checks.py --stack         # + the running stack: flow sync, container tests, browser tests
    python scripts/run_all_checks.py --live          # + the slow checks that call Groq (stories, chat routing, readings)
    python scripts/run_all_checks.py --all --up      # everything, starting the stack first
    python scripts/run_all_checks.py --list          # what exists, and what each one is for
    python scripts/run_all_checks.py --only core,api # just these;  --skip web-build  leaves one out

What the groups need:

    unit   Docker (the Python suites run in a throwaway container with its own database: docker-compose.test.yml, which cannot
           touch your real data) and Node (the web checks). Nothing else, the stack does not have to be running.
    stack  the real stack up (docker compose up -d --build, or add --up); Node with Playwright for the browser tests.
    live   the stack up with AI_MODE=live and a Groq key. These use Groq tokens and take several minutes; Groq's free tier is
           rate limited, so there are pauses. Nothing is run unless you pass --live (or --all).

--native runs the Python suites with YOUR Python instead of Docker. You must give a throwaway Postgres in TEST_DATABASE_URL:
the API tests drop its `tutor` schema. Never point it at the real database.

Every run writes the full output of each check to test-reports/<time>/ and a summary.json; the table at the end says which log
to open. The exit code is 0 only if nothing failed (a skipped check is not a failure, it says why it was skipped).
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
TEST_COMPOSE = "docker-compose.test.yml"
SITE = "http://127.0.0.1:8080"
LANGFLOW = "http://127.0.0.1:7860"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

# These import Langflow itself, which is only in the Langflow container: the "container tests" stage runs them there.
LANGFLOW_ONLY_TESTS = [
    "tests/test_routing_checks.py",
    "tests/test_routing_learner_db.py",
    "tests/test_routing_runner_with_fake_langflow.py",
    "tests/test_tool_result_relay.py",
    "tests/test_tool_wrappers.py",
]
NATIVE_DESELECT = "tests/test_m3_check.py::test_the_command"
# `make test-scripts` runs these on the host; the `root` stage already covers them under pytest, so the container-tests stage skips them.
HOST_ONLY_TESTS = ["test_spike_tweaks.py", "test_capture_fixtures.py", "test_cli_end_to_end.py", "test_groq_language_model.py"]


@dataclass
class Result:
    status: str
    detail: str = ""


@dataclass
class Stage:
    id: str
    group: str                       # unit | stack | live
    title: str
    why: str                         # what a failure of this one means
    run: Callable[["Runner"], Result]
    needs: tuple = ()                # docker, node, stack, live-ai, native-db


@dataclass
class Runner:
    args: argparse.Namespace
    report_dir: Path
    stage_log: list = field(default_factory=list)
    current: str = ""

    # ---- running commands -------------------------------------------------------------------------------------------
    def sh(self, cmd: list[str], cwd: Path | None = None, env: dict | None = None, timeout: int | None = None) -> int:
        """Runs one command, appends its output to the current stage's log (and shows it with --verbose). Returns the exit code."""
        log = self.report_dir / f"{self.current}.log"
        shown = " ".join(cmd)
        with open(log, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"$ {shown}\n")
            f.flush()
            full_env = {**os.environ, **(env or {})}
            try:
                proc = subprocess.Popen(cmd, cwd=str(cwd or ROOT), env=full_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            except FileNotFoundError:
                f.write(f"command not found: {cmd[0]}\n")
                return 127
            start = time.time()
            assert proc.stdout is not None
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace")
                f.write(line)
                if self.args.verbose:
                    sys.stdout.write("    " + line)
                if timeout and time.time() - start > timeout:
                    proc.kill()
                    f.write(f"\n[stopped after {timeout} seconds]\n")
                    return 124
            code = proc.wait()
            f.write(f"[exit {code}]\n\n")
            return code

    def tail(self, lines: int = 12) -> str:
        log = self.report_dir / f"{self.current}.log"
        try:
            text = log.read_text(encoding="utf-8", errors="replace").rstrip().splitlines()
        except OSError:
            return ""
        return "\n".join(text[-lines:])

    def compose(self, *args: str) -> list[str]:
        return ["docker", "compose", *args]

    def test_compose(self, *args: str) -> list[str]:
        return ["docker", "compose", "-f", TEST_COMPOSE, *args]

    def in_tests(self, cwd: str, argv: list[str], timeout: int | None = 1800) -> int:
        """Runs `python <argv>` in folder `cwd` (relative to the project): inside the throwaway test container, or with this machine's Python (--native)."""
        if self.args.native:
            url = os.environ["TEST_DATABASE_URL"]
            env = {"PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in ("tutor_core", "scripts", "custom_components")),
                   "ADMIN_DATABASE_URL": url, "DATABASE_URL": url}
            return self.sh([sys.executable, *argv], cwd=ROOT / cwd, env=env, timeout=timeout)
        inner = "cd " + (cwd or ".") + " && python " + " ".join(shlex.quote(a) for a in argv)
        return self.sh(self.test_compose("run", "--rm", "-T", "tests", "sh", "-c", inner), timeout=timeout)


def http_ok(url: str, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def finish(runner: Runner, code: int, ok_detail: str = "") -> Result:
    return Result(PASS, ok_detail) if code == 0 else Result(FAIL, runner.tail())


# ---- unit stages ------------------------------------------------------------------------------------------------------

def stage_core(r: Runner) -> Result:
    return finish(r, r.in_tests("tutor_core", ["-m", "pytest", "-q", "-p", "no:cacheprovider"]))


def stage_api(r: Runner) -> Result:
    return finish(r, r.in_tests("api", ["-m", "pytest", "-q", "-p", "no:cacheprovider"]))


def stage_root(r: Runner) -> Result:
    ignore = [f"--ignore={p}" for p in LANGFLOW_ONLY_TESTS]
    if r.args.native:       # this one runs the m3 script at /app/scripts and needs the `langflow` database user: only inside the test container
        ignore.append("--deselect=" + NATIVE_DESELECT)
    return finish(r, r.in_tests(".", ["-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", *ignore]))


def npm(r: Runner, *args: str) -> int:
    exe = shutil.which("npm")
    return r.sh([exe or "npm", *args], cwd=ROOT / "web")


def npx(r: Runner, *args: str) -> int:
    exe = shutil.which("npx")
    return r.sh([exe or "npx", *args], cwd=ROOT / "web")


def web_deps(r: Runner) -> int:
    """`npm ci` once per run, and only when node_modules is missing or older than package-lock.json."""
    mods, lock = ROOT / "web" / "node_modules", ROOT / "web" / "package-lock.json"
    if mods.is_dir() and lock.exists() and mods.stat().st_mtime >= lock.stat().st_mtime and not r.args.npm_ci:
        return 0
    return npm(r, "ci")


def stage_web_types(r: Runner) -> Result:
    return finish(r, web_deps(r) or npx(r, "tsc", "--noEmit"))


def stage_web_unit(r: Runner) -> Result:
    return finish(r, web_deps(r) or npx(r, "vitest", "run"))


def stage_web_build(r: Runner) -> Result:
    return finish(r, web_deps(r) or npx(r, "vite", "build"))


def stage_api_types(r: Runner) -> Result:
    """The generated web/openapi.json and schema.d.ts must match what the API produces now."""
    (ROOT / "test-reports").mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="apitypes-", dir=str(ROOT / "test-reports")))
    try:
        rel = tmp.relative_to(ROOT).as_posix()
        code = r.in_tests(".", ["api/scripts/dump_openapi.py", f"{rel}/openapi.json"])
        if code:
            return Result(FAIL, r.tail())
        code = web_deps(r) or npx(r, "--no-install", "openapi-typescript", str(tmp / "openapi.json"), "-o", str(tmp / "schema.d.ts"))
        if code:
            return Result(FAIL, r.tail())
        stale = [name for name, mine, theirs in (("web/openapi.json", tmp / "openapi.json", ROOT / "web" / "openapi.json"),
                                                  ("web/src/api/schema.d.ts", tmp / "schema.d.ts", ROOT / "web" / "src" / "api" / "schema.d.ts"))
                 if mine.read_bytes().replace(b"\r\n", b"\n") != theirs.read_bytes().replace(b"\r\n", b"\n")]
        if stale:
            return Result(FAIL, f"out of date: {', '.join(stale)}. Run:  make gen-api   (or: cd web && npm run gen:api)")
        return Result(PASS, "API types are up to date")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def stage_kanban(r: Runner) -> Result:
    """cards.json parses, every card has the fields the board script needs, and BOARD.md has the same number of cards."""
    cards = json.loads((ROOT / "docs" / "kanban" / "cards.json").read_text(encoding="utf-8"))
    need = {"title", "status", "summary", "labels"}
    bad = [c.get("title", "?") for c in cards if not need <= set(c) or c["status"] not in ("Done", "In review", "Backlog")]
    board = (ROOT / "docs" / "kanban" / "BOARD.md").read_text(encoding="utf-8")
    listed = sum(1 for line in board.splitlines() if line.startswith("- **"))
    if bad:
        return Result(FAIL, f"cards with missing fields or a wrong status: {bad[:5]}")
    if listed != len(cards):
        return Result(FAIL, f"BOARD.md lists {listed} cards but cards.json has {len(cards)}; regenerate BOARD.md")
    return Result(PASS, f"{len(cards)} cards")


# ---- stack stages -----------------------------------------------------------------------------------------------------

def stage_stack_up(r: Runner) -> Result:
    code = r.sh(r.compose("up", "-d", "--build"), timeout=1800)
    if code:
        return Result(FAIL, r.tail())
    for _ in range(60):
        if http_ok(f"{SITE}/api/health/live") and http_ok(f"{LANGFLOW}/health"):
            return Result(PASS, "site and Langflow are answering")
        time.sleep(5)
    return Result(FAIL, f"started, but {SITE}/api/health/live or {LANGFLOW}/health did not answer within 5 minutes; see: docker compose logs")


def stage_stack_health(r: Runner) -> Result:
    site, lf = http_ok(f"{SITE}/api/health/live"), http_ok(f"{LANGFLOW}/health")
    (r.report_dir / f"{r.current}.log").write_text(f"{SITE}/api/health/live: {'ok' if site else 'no answer'}\n{LANGFLOW}/health: {'ok' if lf else 'no answer'}\n", encoding="utf-8")
    if site and lf:
        return Result(PASS, "site and Langflow answer")
    return Result(FAIL, f"no answer from: {', '.join(n for n, ok in (('the site (' + SITE + ')', site), ('Langflow (' + LANGFLOW + ')', lf)) if not ok)}. Start it:  docker compose up -d --build   (or pass --up)")


def stage_flow_sync(r: Runner) -> Result:
    return finish(r, r.sh(r.compose("exec", "-T", "langflow", "python", "/app/scripts/sync_flow_nodes.py", "--check")))


def stage_container_tests(r: Runner) -> Result:
    skip = "|".join(f"*/{n}" for n in HOST_ONLY_TESTS)
    loop = f'rc=0; for t in /app/tests/test_*.py; do case "$t" in {skip}) continue;; esac; echo "== $t"; python "$t" || rc=1; done; exit $rc'
    return finish(r, r.sh(r.compose("exec", "-T", "langflow", "sh", "-c", loop), timeout=1800))


def stage_e2e(r: Runner) -> Result:
    code = web_deps(r) or npx(r, "playwright", "install", "chromium") or npx(r, "playwright", "test")
    return finish(r, code)


# ---- live stages ------------------------------------------------------------------------------------------------------

def stage_m3(r: Runner) -> Result:
    return finish(r, r.sh(r.compose("exec", "-T", "langflow", "python", "/app/scripts/m3_check.py", "--flow-id", "language-tutor", "--pause", str(r.args.pause)), timeout=3600))


def stage_routing(r: Runner) -> Result:
    return finish(r, r.sh(r.compose("exec", "-T", "langflow", "python", "/app/scripts/run_routing_tests.py", "--flow-id", "language-tutor", "--delay", str(r.args.pause)), timeout=5400))


def stage_difficulty(r: Runner) -> Result:
    langs, tiers = ("en,zh", "medium") if r.args.quick else ("en,es,fr,zh,ja,ko", "easy,medium,hard")
    cmd = r.compose("exec", "-T", "api", "python", "scripts/difficulty_check.py", "--base", "http://localhost:8000", "--languages", langs, "--tiers", tiers, "--delay", str(r.args.pause), "--show")
    return finish(r, r.sh(cmd, timeout=7200))


def stage_text_tools(r: Runner) -> Result:
    return finish(r, r.sh(r.compose("exec", "-T", "api", "python", "scripts/text_tools_check.py", "--base", "http://localhost:8000", "--delay", str(max(5, r.args.pause // 2))), timeout=3600))


STAGES: list[Stage] = [
    Stage("core", "unit", "tutor_core tests", "a shared rule is wrong (word cleaning, story prompts, quality report, readings)", stage_core, ("docker",)),
    Stage("api", "unit", "API tests (own Postgres)", "the server misbehaves or one learner can see another's data", stage_api, ("docker",)),
    Stage("root", "unit", "script and tool tests", "a checking script or the tool wrappers broke (the Langflow-only files run in `container-tests`)", stage_root, ("docker",)),
    Stage("kanban", "unit", "kanban cards", "cards.json is malformed or BOARD.md is out of step", stage_kanban),
    Stage("web-types", "unit", "web: TypeScript check", "a type error in the site", stage_web_types, ("node",)),
    Stage("web-unit", "unit", "web: component tests (vitest)", "a page or component renders or reacts wrongly", stage_web_unit, ("node",)),
    Stage("web-build", "unit", "web: production build", "the site does not build", stage_web_build, ("node",)),
    Stage("api-types", "unit", "web: API types up to date", "the API changed and web/openapi.json or schema.d.ts was not regenerated", stage_api_types, ("docker", "node")),
    Stage("stack-health", "stack", "the stack answers", "the stack is not up", stage_stack_health),
    Stage("flow-sync", "stack", "flow in step with the tool code", "custom_components/ was edited without running sync_flow_nodes.py, so Langflow would run old code", stage_flow_sync, ("stack",)),
    Stage("container-tests", "stack", "tests inside the Langflow container", "a tool component, the relay or the routing checker broke where it really runs", stage_container_tests, ("stack",)),
    Stage("e2e", "stack", "browser tests (Playwright)", "the whole site does not work in a real browser, sign-up to saved story and practice", stage_e2e, ("stack", "node")),
    Stage("m3-live", "live", "per-learner tools fail closed (m3_check)", "a learner could reach another learner's words through the Agent", stage_m3, ("stack", "live-ai")),
    Stage("routing-live", "live", "chat routing matrix", "the Agent picks the wrong tool or passes the wrong arguments", stage_routing, ("stack", "live-ai")),
    Stage("difficulty-live", "live", "stories at each difficulty (difficulty_check)", "stories miss their length, own-word or unusual-word targets, or come back in the wrong language", stage_difficulty, ("stack", "live-ai")),
    Stage("text-tools-live", "live", "pronunciation and translation (text_tools_check)", "pinyin, romaji, Korean, IPA or translations come back wrong", stage_text_tools, ("stack", "live-ai")),
]
BY_ID = {s.id: s for s in STAGES}
STACK_UP_STAGE = Stage("stack-up", "stack", "start the stack", "docker compose up failed", stage_stack_up, ("docker",))


# ---- choosing and checking ----------------------------------------------------------------------------------------------

def selected(args: argparse.Namespace) -> list[Stage]:
    groups = {"unit"}
    if args.stack or args.live or args.all:
        groups.add("stack")
    if args.live or args.all:
        groups.add("live")
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [w for w in wanted if w not in BY_ID]
        if unknown:
            raise SystemExit(f"unknown check(s): {', '.join(unknown)}. See --list.")
        chosen = [BY_ID[w] for w in wanted]
    else:
        chosen = [s for s in STAGES if s.group in groups]
    skipped = {x.strip() for x in (args.skip or "").split(",") if x.strip()}
    unknown = skipped - set(BY_ID)
    if unknown:
        raise SystemExit(f"unknown check(s) in --skip: {', '.join(sorted(unknown))}. See --list.")
    chosen = [s for s in chosen if s.id not in skipped]
    if args.up and any(s.group != "unit" for s in chosen):
        chosen = [STACK_UP_STAGE] + chosen
    return chosen


def missing_need(need: str, args: argparse.Namespace, state: dict) -> str | None:
    """Why a check cannot run, or None."""
    if need == "docker":
        if args.native:
            return None if os.environ.get("TEST_DATABASE_URL") else "--native needs TEST_DATABASE_URL (a throwaway Postgres; the API tests drop its `tutor` schema)"
        if not shutil.which("docker"):
            return "Docker is not installed or not on PATH (or use --native)"
        return state.setdefault("docker_daemon", docker_daemon_message())
    if need == "node":
        return None if shutil.which("node") and shutil.which("npm") else "Node.js 22 or later is not installed (https://nodejs.org)"
    if need == "stack":
        if not shutil.which("docker"):
            return "Docker is not installed or not on PATH"
        return None if state.get("stack_up") else f"the stack is not running at {SITE}; start it with `docker compose up -d --build` or pass --up"
    if need == "live-ai":
        return state.get("live_ai_problem")
    return None


def docker_daemon_message() -> str | None:
    try:
        out = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return "Docker does not answer; start Docker Desktop"
    return None if out.returncode == 0 else "Docker does not answer; start Docker Desktop and wait until it says it is running"


def live_ai_problem() -> str | None:
    """The live checks are meaningless against the stand-in, and cost nothing but time to refuse up front."""
    try:
        out = subprocess.run(["docker", "compose", "exec", "-T", "api", "printenv", "AI_MODE"], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    except (OSError, subprocess.TimeoutExpired):
        return None
    mode = out.stdout.strip() or "live"
    if out.returncode == 0 and mode != "live":
        return f"the API runs with AI_MODE={mode}; set AI_MODE=live in .env and restart: docker compose up -d"
    return None


def native_guard(args: argparse.Namespace) -> str | None:
    if args.native and not os.environ.get("TEST_DATABASE_URL"):
        return "--native needs TEST_DATABASE_URL set to a throwaway Postgres, for example postgresql://langflow:testpw@localhost:5432/langflow_test"
    return None


# ---- output -------------------------------------------------------------------------------------------------------------

def table(rows: list[tuple[str, str, float, str]]) -> str:
    """rows: (check, result, seconds, detail)."""
    body = [(i, st, f"{t:.0f}s" if t >= 1 else "-", (d.splitlines() or [""])[0] if st != PASS or d else "") for i, st, t, d in rows]
    head = ("check", "result", "time", "note")
    widths = [max(len(r[k]) for r in [head] + body) for k in range(3)]
    fmt = lambda r: "  ".join(r[k].ljust(widths[k]) for k in range(3)) + "  " + r[3]
    return "\n".join([fmt(head), "  ".join("-" * w for w in widths)] + [fmt(r) for r in body])


def print_list() -> None:
    print("group  check             what a failure means")
    for s in STAGES:
        print(f"{s.group:<6} {s.id:<17} {s.title}  ->  {s.why}")
    print("\nunit = runs by default; stack = --stack; live = --live (uses Groq tokens). --up starts the stack first.")


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stack", action="store_true", help="also the checks that need the running stack (no Groq calls)")
    ap.add_argument("--live", action="store_true", help="also the slow checks that call Groq (includes --stack)")
    ap.add_argument("--all", action="store_true", help="everything (same as --live)")
    ap.add_argument("--up", action="store_true", help="run `docker compose up -d --build` first and wait for the stack")
    ap.add_argument("--only", help="comma-separated check ids (see --list); runs just those")
    ap.add_argument("--skip", help="comma-separated check ids to leave out")
    ap.add_argument("--list", action="store_true", help="list the checks and exit")
    ap.add_argument("--fail-fast", action="store_true", help="stop at the first failure (default: run everything and report)")
    ap.add_argument("--quick", action="store_true", help="shorter live difficulty check (English and Chinese at Medium)")
    ap.add_argument("--pause", type=int, default=20, help="seconds between Groq calls in the live checks (the free tier is rate limited)")
    ap.add_argument("--native", action="store_true", help="run the Python suites with this machine's Python (needs TEST_DATABASE_URL)")
    ap.add_argument("--npm-ci", action="store_true", help="reinstall the web packages even if they look current")
    ap.add_argument("--verbose", action="store_true", help="show each check's output as it runs")
    ap.add_argument("--keep-test-db", action="store_true", help="leave the throwaway test containers running afterwards")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse(argv)
    if args.list:
        print_list()
        return 0
    problem = native_guard(args)
    if problem:
        print(problem)
        return 2
    chosen = selected(args)
    if not chosen:
        print("nothing to run")
        return 0
    report_dir = ROOT / "test-reports" / time.strftime("%Y%m%d-%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=True)
    runner = Runner(args, report_dir)
    state: dict = {"stack_up": http_ok(f"{SITE}/api/health/live")}
    rows: list[tuple[str, str, float, str]] = []     # (check, result, seconds, detail)
    print(f"{len(chosen)} checks. Logs: {report_dir}\n")
    stopped = False
    for stage in chosen:
        runner.current = stage.id
        if stopped:
            rows.append((stage.id, SKIP, 0.0, "stopped after the first failure (--fail-fast)"))
            continue
        if "live-ai" in stage.needs and "live_ai_problem" not in state and state["stack_up"]:
            state["live_ai_problem"] = live_ai_problem()
        reason = next((m for n in stage.needs if (m := missing_need(n, args, state))), None)
        if reason:
            rows.append((stage.id, SKIP, 0.0, reason))
            print(f"  SKIP  {stage.id:<17} {reason}")
            continue
        print(f"  ...   {stage.id:<17} {stage.title}", flush=True)
        t0 = time.time()
        try:
            res = stage.run(runner)
        except Exception as exc:        # a bug in this script must not hide the other results
            res = Result(FAIL, f"the runner itself failed: {exc!r}")
        dt = time.time() - t0
        rows.append((stage.id, res.status, dt, res.detail))
        print(f"  {res.status:<5} {stage.id:<17} {dt:.0f}s")
        if stage.id == "stack-up" and res.status == PASS:
            state["stack_up"] = True
        if res.status == FAIL and args.fail_fast:
            stopped = True
    used_test_containers = not args.native and any("docker" in s.needs and s.group == "unit" for s in chosen)
    if used_test_containers and not args.keep_test_db and shutil.which("docker"):
        subprocess.run(["docker", "compose", "-f", TEST_COMPOSE, "down", "-v", "--remove-orphans"], capture_output=True, cwd=str(ROOT))
    failed = [r for r in rows if r[1] == FAIL]
    skipped = [r for r in rows if r[1] == SKIP]
    print("\n" + table(rows))
    for name, _, _, detail in failed:
        why = (BY_ID.get(name) or STACK_UP_STAGE).why
        print(f"\n--- {name} failed: {why}\n{detail}\n(full log: {report_dir / (name + '.log')})")
    passed = sum(1 for r in rows if r[1] == PASS)
    print(f"\n{passed} passed, {len(failed)} failed, {len(skipped)} skipped.  Logs and summary.json: {report_dir}")
    if skipped:
        print("A skipped check did not run; the table says why. It is not a failure.")
    (report_dir / "summary.json").write_text(json.dumps([{"check": n, "result": st, "seconds": round(t, 1), "detail": d} for n, st, t, d in rows], indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
