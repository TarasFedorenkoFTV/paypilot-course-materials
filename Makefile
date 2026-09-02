# PayPilot stand — one command per action (ТЗ §5.9)

.PHONY: up down reset doctor test smoke walkthrough calibrate catalog dev help

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

walkthrough:   ## walk the lab steps of all 14 lessons (ТЗ 10.3)
	python scripts/walkthrough.py

calibrate:     ## acceptance run: measure every defect on profile vs clean
	python scripts/calibrate.py

catalog:       ## regenerate docs/defect-catalog.md from the measured report
	python scripts/gen_catalog.py

dev:           ## run locally without docker
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
