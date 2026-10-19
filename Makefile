.PHONY: setup sample data data-sample train evaluate report lint test clean

PY ?= python

setup:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .

sample:
	$(PY) scripts/make_sample_data.py

data:
	$(PY) scripts/make_dataset.py

data-sample:
	$(PY) scripts/make_dataset.py --sample

train:
	$(PY) scripts/train.py

evaluate:
	$(PY) scripts/evaluate.py

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
