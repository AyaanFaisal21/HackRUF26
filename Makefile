PY=.venv/bin/python
PIP=.venv/bin/pip
export PYTHONPATH=backend

.PHONY: setup db-up db-down db-init data load fill eval test api web demo compress check-db

setup:            ## create venv and install backend + frontend deps
	python3 -m venv .venv && $(PIP) install -q -r backend/requirements.txt && cd frontend && npm install

db-up:            ## start local Tiger/TimescaleDB (docker)
	docker compose up -d --wait

db-down:
	docker compose down

check-db:         ## confirm DATABASE_URL has TimescaleDB and pgvector
	$(PY) backend/scripts/check_db.py

db-init:          ## create the ledger: hypertables, continuous aggregate, vector index
	$(PY) -m sourced.cli init-db

data:             ## regenerate the two-clinic world and its answer key (deterministic, seed 7)
	$(PY) -m sourced.cli build-data

load:             ## generate the world, read every source into the ledger (oracle reader unless SOURCED_READER=model)
	$(PY) -m sourced.cli load

fill:             ## fill and verify the standard visit forms for 30 documented patients and the children
	$(PY) -m sourced.cli fill --patients 30 --reset

eval:             ## score fill rate, accuracy, receipts, planted traps against the answer key
	$(PY) -m sourced.cli evaluate --out docs/eval-sourced-$${SOURCED_READER:-oracle}.md

compress:         ## compress ledger chunks older than 120 days and print the size change
	$(PY) -m sourced.cli compress

test:
	$(PY) -m pytest -q backend/tests

api:              ## FastAPI on :8000
	$(PY) -m uvicorn sourced.api:app --reload --port 8000

web:              ## Vite dev server on :5173 (proxies /api to :8000, or API_URL)
	cd frontend && npm run dev

demo: db-up db-init load fill api
