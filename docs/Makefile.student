# PayPilot stand — one command per action

.PHONY: up down reset doctor test smoke dev help

help:          ## show this help
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ —/'

up:            ## start everything (stand + Phoenix)
	docker compose up --build -d

down:          ## stop and clean up
	docker compose down -v

reset:         ## return DB state to the seed
	curl -s -X POST http://localhost:8000/api/_test/reset

doctor:        ## diagnose the environment
	python scripts/doctor.py

test:          ## run the stand's own unit tests
	python -m pytest tests/ -q

smoke:         ## check every stand surface answers (no API key needed)
	python scripts/ci_smoke.py

dev:           ## run locally without docker
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
