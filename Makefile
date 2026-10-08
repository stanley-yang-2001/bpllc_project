# Needs a Postgres reachable at TEST_DATABASE_URL for the API tests (default matches api/tests/conftest.py).
.PHONY: check test-core test-api test-web typecheck-web check-api-types gen-api dev-api dev-web up

check: test-core test-api typecheck-web test-web check-api-types
	@echo "all checks passed"

test-core:
	cd tutor_core && python3 -m pytest -q

test-api:
	cd api && python3 -m pytest -q

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
