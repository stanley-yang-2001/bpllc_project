# Testing: one command for everything

`scripts/run_all_checks.py` runs every check the project has and ends with one table (PASS / FAIL / SKIP, time, and what to do). It needs only Python on your machine, plus Docker and Node.js for the checks that use them. On Windows, from the project folder:

```
run-checks.bat                      # the unit checks (about 3 to 6 minutes the first time, the image is built once)
run-checks.bat --stack              # + the running stack: flow in step, container tests, browser tests
run-checks.bat --live               # + the slow checks that call Groq
run-checks.bat --all --up           # everything, starting the stack first
run-checks.bat --list               # every check and what its failure means
```

`python scripts/run_all_checks.py ...` and `make check-all ARGS="--stack"` do the same on macOS and Linux.

## The three groups

| Group | Runs with | Needs | Costs Groq tokens |
|---|---|---|---|
| **unit** (default) | nothing else | Docker (Python suites), Node 22+ (web) | no |
| **stack** (`--stack`) | the real stack up | Docker, the stack running (`--up` starts it), Node with Playwright | no |
| **live** (`--live`) | the real stack with `AI_MODE=live` and a Groq key | as stack | yes, several minutes, with pauses for the free tier's rate limit |

| Check | Group | What it covers |
|---|---|---|
| `core` | unit | `tutor_core` rules: word cleaning, story prompts, quality report, readings |
| `api` | unit | the server: routes, privacy between learners, migrations, model gate |
| `root` | unit | the checking scripts and tool wrappers (the five files that import Langflow run in `container-tests`) |
| `kanban` | unit | `cards.json` is well formed and `BOARD.md` lists the same cards |
| `web-types`, `web-unit`, `web-build` | unit | TypeScript, the component tests, the production build |
| `api-types` | unit | `web/openapi.json` and `schema.d.ts` match what the API produces now (fix: `make gen-api`) |
| `stack-health` | stack | the site (`:8080`) and Langflow (`:7860`) answer |
| `flow-sync` | stack | the flow file matches `custom_components/` (fix: `sync_flow_nodes.py`) |
| `container-tests` | stack | every test file inside the Langflow container, where the tools really run |
| `e2e` | stack | Playwright in a real browser: sign-up to saved story and practice |
| `m3-live` | live | a learner's tools fail closed: the Agent cannot reach another learner's words |
| `routing-live` | live | the chat routing matrix: the right tool and arguments for each request |
| `difficulty-live` | live | stories at Easy, Medium and Hard in all nine languages hit their targets (`--quick`: English and Chinese at Medium) |
| `text-tools-live` | live | pinyin, romaji, Korean romanization, English IPA, and translation |

## Your data is not touched

The Python suites do not run against your database. The API tests drop and rebuild the `tutor` schema, so `docker-compose.test.yml` starts its own Postgres (data kept in memory, nothing saved, a different compose project name `tutor-tests`) and removes it afterwards. The live checks sign up throwaway learners (addresses ending `.invalid`) and delete them at the end.

`--native` runs the Python suites with your own Python instead of Docker. It refuses to start unless `TEST_DATABASE_URL` is set, because the API tests **drop the `tutor` schema** in that database. Point it only at a throwaway one.

## Reading the result

* A **SKIP** means the check could not run (no Docker, stack not up, `AI_MODE` is `stub`): the note says why. It is not a failure.
* Each check's full output is in `test-reports/<date-time>/<check>.log`, with `summary.json` beside them. The folder is ignored by git.
* The exit code is 0 only if nothing failed, so it can sit in a script or CI job.
* Useful options: `--only core,api`, `--skip e2e`, `--fail-fast`, `--verbose` (show the output live), `--pause 30` (longer pauses between Groq calls), `--keep-test-db`, `--npm-ci`.

## Individual commands (what the runner calls)

```
make test-core | test-api | test-scripts | typecheck-web | test-web | check-api-types
docker compose exec -T langflow python /app/scripts/sync_flow_nodes.py --check
make test-langflow
cd web && npx playwright test
docker compose exec -T langflow python /app/scripts/m3_check.py --flow-id language-tutor --pause 30
docker compose exec -T langflow python /app/scripts/run_routing_tests.py --flow-id language-tutor --delay 20
docker compose exec -T api python scripts/difficulty_check.py --show
docker compose exec -T api python scripts/text_tools_check.py
```

## When you add a test

* A new test file that imports Langflow (directly or through `custom_components`) goes in `LANGFLOW_ONLY_TESTS` in `scripts/run_all_checks.py`; `tests/test_run_all_checks.py` fails if you forget.
* A new live check is one function and one `Stage(...)` line in the same file.
