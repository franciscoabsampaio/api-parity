# Utility targets for api-parity development.
# Run `make help` to see every available target.

.DEFAULT_GOAL := help

PY ?= python3

CORE_DIR := api-parity
PY_DIR   := api-parity-py
RS_DIR   := api-parity-rs

CORE_VENV := $(CORE_DIR)/.venv
PY_VENV   := $(PY_DIR)/.venv

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Dev environment
# ---------------------------------------------------------------------------
# The venv directory itself is the make target — when its pyproject.toml
# changes, the install step re-runs and `touch` bumps the dir mtime.

$(CORE_VENV): $(CORE_DIR)/pyproject.toml
	$(PY) -m venv $@
	$@/bin/pip install -q -e $(CORE_DIR) pytest build
	@touch $@

$(PY_VENV): $(PY_DIR)/pyproject.toml
	$(PY) -m venv $@
	$@/bin/pip install -q -e $(PY_DIR) pytest build
	@touch $@

.PHONY: setup
setup: $(CORE_VENV) $(PY_VENV) ## Create dev venvs and install both Python packages editable

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

.PHONY: test test-core test-py test-rs
test: test-core test-py test-rs ## Run every test suite

test-core: $(CORE_VENV) ## Run api-parity (differ) tests
	$(CORE_VENV)/bin/pytest $(CORE_DIR)/tests -q

test-py: $(PY_VENV) ## Run api-parity-py tests
	$(PY_VENV)/bin/pytest $(PY_DIR)/tests -q

test-rs: ## Run api-parity-rs tests
	cd $(RS_DIR) && cargo test --workspace --all-features

# ---------------------------------------------------------------------------
# Release tagging
# ---------------------------------------------------------------------------
# Usage: make tag-core VERSION=0.0.2

.PHONY: tag-core tag-py tag-rs _check-version
tag-core: _check-version ## Tag and push v$$VERSION for the differ
	git tag -a "v$(VERSION)" -m "v$(VERSION)"
	git push origin "v$(VERSION)"

tag-py: _check-version ## Tag and push py-v$$VERSION for api-parity-py
	git tag -a "py-v$(VERSION)" -m "py-v$(VERSION)"
	git push origin "py-v$(VERSION)"

tag-rs: _check-version ## Tag and push rs-v$$VERSION for api-parity-rs
	git tag -a "rs-v$(VERSION)" -m "rs-v$(VERSION)"
	git push origin "rs-v$(VERSION)"

_check-version:
	@test -n "$(VERSION)" || (echo "VERSION=X.Y.Z is required" >&2; exit 1)
