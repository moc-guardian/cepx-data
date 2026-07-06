.DEFAULT_GOAL := help
.PHONY: help setup data unit cov pc check package clean

UV_RUN_CMD = uv run --no-sync

help:
	@echo "Usage: make <target>"
	@echo "  setup   Install deps and git hooks for development"
	@echo "  data    Fetch CEP Aberto dumps and build the offline SQLite database"
	@echo "  unit    Run unit tests and collect coverage"
	@echo "  cov     Report coverage from the last run (no re-run)"
	@echo "  pc      Run all pre-commit hooks on all files"
	@echo "  check   Run unit tests, coverage report, and pre-commit"
	@echo "  package Build the sdist and wheel into dist/"
	@echo "  clean   Clean development environment"

setup:
	uv venv --clear --python 3.14
	uv sync --all-groups
	$(UV_RUN_CMD) pre-commit install

# Requires CEPABERTO_COOKIE and CEPABERTO_TOKEN in the environment. The fetch
# step downloads the per-state dumps AND the cities/states reference tables;
# the load step joins them into src/cepx_data/data/cepx.sqlite.
data:
	$(UV_RUN_CMD) python tools/fetch_cepaberto.py --out dumps
	$(UV_RUN_CMD) python tools/load_cepaberto.py "dumps/*.cepaberto_*.csv" \
		--cities dumps/cities.csv --states dumps/states.csv

unit:
	$(UV_RUN_CMD) pytest -m unit

cov:
	$(UV_RUN_CMD) coverage report
	$(UV_RUN_CMD) coverage html

pc:
	$(UV_RUN_CMD) pre-commit run --all-files

check: unit cov pc

package:
	uv build

clean:
	@for ext in mo pot pyc; do \
		find . -type f -name "*.$$ext" -delete; \
	done
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@rm -rf .coverage .ruff_cache .pytest_cache htmlcov dist dumps
