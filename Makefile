PYTHON ?= python

.PHONY: setup lint test cov mutate local-check record docs

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m pre_commit install

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy src/ytmcp/domain
	lint-imports

test:
	$(PYTHON) -m pytest -m "not live"

cov:
	$(PYTHON) -m pytest -m "not live" --cov=ytmcp --cov-report=term-missing --cov-fail-under=80

mutate:
	$(PYTHON) -m mutmut run

local-check:
	@echo "local-check is not implemented yet (build items B32, first version in Stage 2)"
	@exit 1

record:
	$(PYTHON) scripts/record_fixtures.py --dry-run

docs:
	@echo "docs target is not implemented yet"
	@exit 1
