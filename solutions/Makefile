# Reference solutions — the student's coursework, done once as a sample.
# Needs a running stand: cd .. && make up

.PHONY: eval eval-clean eval-profile gate generate validate help

SET   ?= l03_reference
GATE  ?=
CASE  ?=

help:          ## show this help
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ —/'

eval:          ## run a set against the stand (SET=, GATE=, CASE=)
	cd evals && SET=$(SET) GATE=$(GATE) CASE=$(CASE) python runner.py

gate:          ## the blocking layer only: deterministic, single-run cases
	cd evals && SET=$(SET) GATE=daily python runner.py

eval-clean:    ## baseline: switch the stand to clean, then run
	curl -s -X PUT http://localhost:8000/api/_test/profile \
	  -H 'Content-Type: application/json' -d '{"profile":"clean"}' > /dev/null
	cd evals && SET=$(SET) GATE=daily python runner.py

eval-profile:  ## the lesson profile: PROFILE=lesson-03 make eval-profile
	curl -s -X PUT http://localhost:8000/api/_test/profile \
	  -H 'Content-Type: application/json' -d '{"profile":"$(PROFILE)"}' > /dev/null
	cd evals && SET=$(SET) GATE=daily python runner.py

generate:      ## regenerate the engine-derived cases
	cd evals && python generate_from_engines.py

validate:      ## load every set and print its coverage
	cd evals && python -c "import sys; sys.path.insert(0,'.'); \
	  from pathlib import Path; from loader import load, summarise, set_hash; \
	  [print(p.stem, set_hash(p), summarise(load(p))) for p in sorted(Path('sets').glob('*.jsonl'))]"
