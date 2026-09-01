# PayPilot stand — one command per action (ТЗ §5.9)

.PHONY: up down reset doctor test dev

up:            ## start everything (docker)
	docker compose up --build -d

down:          ## stop and clean up
	docker compose down -v

reset:         ## return DB state to the seed
	curl -s -X POST http://localhost:8000/api/_test/reset

doctor:        ## diagnose the environment
	python scripts/doctor.py

test:          ## run the stand's own test suite
	python -m pytest tests/ -q

dev:           ## run locally without docker
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
