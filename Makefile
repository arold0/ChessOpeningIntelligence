# ──────────────────────────────────────────────
# Chess Opening Intelligence — Makefile
# ──────────────────────────────────────────────

.PHONY: install install-dev install-all test test-unit test-integration test-sql lint format pipeline sample clean help

# ── Installation ──────────────────────────────

install: ## Install core dependencies
	pip install -e .

install-dev: ## Install core + dev dependencies
	pip install -e ".[dev]"

install-all: ## Install all dependency groups
	pip install -e ".[dev,notebook,dashboard]"

# ── Testing ───────────────────────────────────

test: ## Run all tests
	pytest tests/ -v --tb=short

test-unit: ## Run only unit tests
	pytest tests/unit/ -v -m unit

test-integration: ## Run only integration tests
	pytest tests/integration/ -v -m integration

test-sql: ## Run only SQL logic tests
	pytest tests/sql/ -v -m sql

test-cov: ## Run tests with coverage report
	pytest tests/ -v --cov=pipeline --cov-report=html --cov-report=term-missing

# ── Code Quality ──────────────────────────────

lint: ## Check code style with ruff
	ruff check pipeline/ tests/

format: ## Auto-format code with ruff
	ruff format pipeline/ tests/

# ── Pipeline ──────────────────────────────────

pipeline: ## Run the full pipeline (L1 → L2 → L3)
	python -m pipeline.run_pipeline --step all

sample: ## Generate sample data for development
	python -m pipeline.run_pipeline --sample --month 2015-01

# ── Maintenance ───────────────────────────────

clean: ## Remove generated data files (keeps sample/)
	rm -rf data/raw/*.parquet data/clean/*
	@echo "Cleaned raw and clean data directories."

# ── Help ──────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
