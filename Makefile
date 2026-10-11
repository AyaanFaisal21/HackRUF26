PY=.venv/bin/python
PIP=.venv/bin/pip
export PYTHONPATH=backend

.PHONY: setup db-up db-down db-init fetch mock-data inbox load eval test api web demo

setup:            ## create venv and install backend + frontend deps
	python3 -m venv .venv && $(PIP) install -q -r backend/requirements.txt && cd frontend && npm install

db-up:            ## start local Tiger/TimescaleDB (docker)
	docker compose up -d --wait

db-down:
	docker compose down

db-init:          ## create hypertables, continuous aggregate, vector index
	$(PY) -m dayzero.cli init-db

fetch:            ## pull 300 serious FAERS reports from openFDA (no key needed)
	$(PY) -m dayzero.cli fetch --n 300 --out data/raw/faers.json

mock-data:        ## derive mock MedDRA list and mock reference safety information from the FAERS sample
	$(PY) -m dayzero.cli build-mock-data --faers data/raw/faers.json

inbox:            ## generate a synthetic messy inbox + answer key (offline templates)
	$(PY) -m dayzero.cli build-inbox --faers data/raw/faers.json --n 60 --seed 7 --out data/samples

load:             ## run the pipeline over the sample inbox and load Tiger
	$(PY) -m dayzero.cli load --inbox data/samples/inbox.json --answer-key data/samples/answer_key.json

load-trial:       ## load the CDISC pilot trial, generate daily symptom diaries, compute flags
	$(PY) -m dayzero.cli load-trial

eval:             ## score extraction, validity, day zero and duplicates against the answer key
	$(PY) -m dayzero.cli evaluate --inbox data/samples/inbox.json --answer-key data/samples/answer_key.json

test:
	$(PY) -m pytest -q backend/tests

api:              ## FastAPI on :8000
	$(PY) -m uvicorn dayzero.api:app --reload --port 8000

web:              ## Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

demo: db-up db-init load load-trial api
