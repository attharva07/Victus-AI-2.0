PYTHON ?= python

.PHONY: lint test coverage report

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest -q --disable-warnings

coverage:
	$(PYTHON) -m pytest --cov=victus --cov-report=term-missing --cov-report=xml

report:
	$(PYTHON) scripts/quality_report.py
