.PHONY: setup data train evaluate score report lint test clean all

PY ?= python

setup:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .

data:
	$(PY) scripts/make_dataset.py

train:
	$(PY) scripts/train.py

evaluate:
	$(PY) scripts/evaluate.py

score:
	$(PY) scripts/score_submission.py reports/submission.csv

all: data train evaluate

report:
	$(PY) scripts/make_figures.py

lint:
	ruff check src scripts tests
	ruff format --check src scripts tests

test:
	$(PY) -m pytest -q

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
