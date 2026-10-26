.DEFAULT_GOAL := help
.PHONY: help setup data test unit cov lint fmt fix types pc check package clean

UV_RUN_CMD = uv run --no-sync

help:
	@echo "Usage: make <target>"
	@echo "  setup   Install deps and git hooks for development"
	@echo "  data    Fetch CEP Aberto dumps and build the offline SQLite database"
	@echo "  test    Run the unit suite and collect coverage"
	@echo "  unit    Run unit tests only (no coverage)"
	@echo "  cov     Report coverage from the last run (no re-run)"
	@echo "  lint    Lint with ruff"
	@echo "  fmt     Format with ruff"
	@echo "  fix     Apply the fixes lint reports, then format"
	@echo "  types   Type check with ty"
	@echo "  pc      Run all pre-commit hooks on all files"
	@echo "  check   Run tests, coverage report, and pre-commit"
	@echo "  package Build the sdist and wheel into dist/"
	@echo "  clean   Clean development environment"

setup:
	uv venv --clear --python $$(cat .python-version)
	uv sync --all-groups
	$(UV_RUN_CMD) pre-commit install

# Requires CEPABERTO_COOKIE and CEPABERTO_TOKEN in the environment. The fetch
# step downloads the per-state dumps AND the cities/states reference tables;
# the load step joins them into src/cepx_data/data/cepx.sqlite.
data:
	$(UV_RUN_CMD) python tools/fetch_cepaberto.py --out dumps
	$(UV_RUN_CMD) python tools/load_cepaberto.py "dumps/*.cepaberto_*.csv" \
		--cities dumps/cities.csv --states dumps/states.csv

test:
	$(UV_RUN_CMD) coverage run
	$(UV_RUN_CMD) coverage report

unit:
	$(UV_RUN_CMD) pytest -m unit

cov:
	$(UV_RUN_CMD) coverage report
	$(UV_RUN_CMD) coverage html

lint:
	$(UV_RUN_CMD) ruff check .

fmt:
	$(UV_RUN_CMD) ruff format .

# `fmt` only reformats. Most of what `lint` reports is fixable, but by a
# different command, so this is the loop to run after a red `lint`.
fix:
	$(UV_RUN_CMD) ruff check . --fix
	$(UV_RUN_CMD) ruff format .

types:
	$(UV_RUN_CMD) ty check

pc:
	$(UV_RUN_CMD) pre-commit run --all-files

check: test pc

package:
	uv build

clean:
	@for ext in mo pot pyc; do \
		find . -type f -name "*.$$ext" -delete; \
	done
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@rm -rf .coverage .ruff_cache .pytest_cache .ty_cache htmlcov dist dumps
