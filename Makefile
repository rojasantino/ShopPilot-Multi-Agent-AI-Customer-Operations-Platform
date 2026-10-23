.PHONY: setup up down logs test test-int lint eval psql
setup:        ## local venv for development
	python -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements-dev.txt -r frontend/requirements.txt
	cp -n .env.example .env || true
up:           ## start everything (db, redis, api, ui)
	cp -n .env.example .env || true
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f api
test:         ## fast unit tests (no Docker needed)
	cd backend && python -m pytest -q
test-int:     ## real pgvector tests (needs the db container running)
	cd backend && TEST_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/shoppilot python -m pytest -q
lint:
	cd backend && ruff check . && ruff format --check .
eval:         ## routing quality on the fixed test set
	cd backend && python -m evals.run_routing_eval
psql:         ## look inside the vector table
	docker compose exec db psql -U app -d shoppilot
