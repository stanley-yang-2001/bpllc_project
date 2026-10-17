# PYTHON=python on Windows (python3 is not a command there):  make check PYTHON=python
PYTHON ?= python3

# Needs a Postgres reachable at TEST_DATABASE_URL for the API tests (default matches api/tests/conftest.py).
.PHONY: check test-core test-scripts test-langflow test-api test-web typecheck-web check-api-types gen-api dev-api dev-web up

check: test-core test-scripts test-api typecheck-web test-web check-api-types
	@echo "all checks passed"

test-core:
	cd tutor_core && $(PYTHON) -m pytest -q

# The command-line scripts (spike, capture) and their end-to-end tests against a fake Langflow. Standard library only.
test-scripts:
	$(PYTHON) tests/test_spike_tweaks.py
	$(PYTHON) tests/test_capture_fixtures.py
	$(PYTHON) tests/test_groq_language_model.py
	$(PYTHON) tests/test_cli_end_to_end.py

# Everything that needs the langflow container (Langflow, tutor_core, Postgres with the api's migrations applied).
test-langflow:
	docker compose exec -T langflow sh -c 'rc=0; for t in /app/tests/test_*.py; do case "$$t" in */test_spike_tweaks.py|*/test_capture_fixtures.py|*/test_cli_end_to_end.py|*/test_groq_language_model.py) continue;; esac; echo "== $$t"; python "$$t" || rc=1; done; exit $$rc'

test-api:
	cd api && $(PYTHON) -m pytest -q

typecheck-web:
	cd web && npx tsc --noEmit

test-web:
	cd web && npx vitest run

check-api-types:
	./scripts/check_api_types.sh

gen-api:
	cd web && npm run gen:api

dev-api:            # needs DATABASE_URL and JWT_SECRET in the environment
	cd api && PYTHONPATH=../tutor_core uvicorn --factory app.main:app_factory --reload --port 8000

dev-web:
	cd web && npm run dev

up:
	docker compose up --build

# Real-browser tests against a running stack (docker compose up, or make dev-api + make dev-web).
# First time on a machine: cd web && npx playwright install chromium
.PHONY: e2e
e2e:
	cd web && npx playwright test
