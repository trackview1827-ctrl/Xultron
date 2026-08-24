.PHONY: setup dev migrate test typecheck build smoke check serve clean

setup:
	./scripts/bootstrap.sh

dev:
	./scripts/dev.sh

migrate:
	cd backend && .venv/bin/flask --app run.py db upgrade

test:
	cd backend && .venv/bin/pytest -q
	npm --prefix frontend test

typecheck:
	npm --prefix frontend run typecheck

build:
	npm --prefix frontend run build

smoke: build
	./scripts/release-smoke.sh

check:
	./scripts/check.sh

serve: build migrate
	cd backend && .venv/bin/python run.py

clean:
	rm -rf frontend/dist frontend/coverage backend/.pytest_cache backend/htmlcov
