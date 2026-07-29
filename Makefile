# Makefile for NFL Betting System
# Cross-platform commands for development and deployment

.PHONY: help install test lint format clean data train predict

# Default target
help:
	@echo "NFL Betting System - Available Commands"
	@echo "========================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       Install all dependencies"
	@echo "  make install-dev   Install dev dependencies"
	@echo "  make setup         Complete first-time setup"
	@echo ""
	@echo "Development:"
	@echo "  make test          Run all tests"
	@echo "  make test-cov      Run tests with coverage report"
	@echo "  make lint          Run all linters"
	@echo "  make format        Auto-format code (black, isort)"
	@echo "  make type-check    Run mypy type checking"
	@echo ""
	@echo "Data & Training:"
	@echo "  make data          Download NFL data"
	@echo "  make features      Generate features"
	@echo "  make train         Train models"
	@echo "  make backtest      Run backtest validation"
	@echo ""
	@echo "Production:"
	@echo "  make predict       Generate daily predictions"
	@echo "  make pipeline      Run full production pipeline"
	@echo "  make dashboard     Launch performance dashboard"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean         Remove cache and temp files"
	@echo "  make clean-all     Deep clean (includes data)"
	@echo "  make update        Update dependencies"
	@echo ""

# Setup & Installation
install:
	pip install --upgrade pip
	pip install -r requirements.txt

install-dev: install
	pip install black ruff mypy isort pytest pytest-cov pytest-mock pre-commit
	pre-commit install

setup: install-dev
	@echo "Creating directory structure..."
	mkdir -p data/{raw,processed,schedules}
	mkdir -p models reports logs
	@echo "Copying API key template..."
	cp config/api_keys.env.template config/api_keys.env || true
	@echo ""
	@echo "Setup complete! Next steps:"
	@echo "1. Add your API keys to config/api_keys.env"
	@echo "2. Run: make data"
	@echo "3. Run: make train"

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term tests/
	@echo ""
	@echo "Coverage report generated: htmlcov/index.html"

test-fast:
	pytest tests/ -v -m "not slow"

# Code Quality
lint:
	@echo "Running Black..."
	black --check src/ scripts/ tests/
	@echo "Running Ruff..."
	ruff check src/ scripts/ tests/
	@echo "Running isort..."
	isort --check-only --profile black src/ scripts/ tests/

format:
	@echo "Formatting with Black..."
	black src/ scripts/ tests/
	@echo "Sorting imports..."
	isort --profile black src/ scripts/ tests/
	@echo "Code formatted successfully!"

type-check:
	mypy src/ --ignore-missing-imports --no-strict-optional

# Data & Features
data:
	python scripts/download_data.py

data-force:
	python scripts/download_data.py --force

features:
	python scripts/analyze_features.py

# Model Training
train:
	python scripts/train_model.py

train-tune:
	python scripts/tune_hyperparameters.py

backtest:
	python scripts/backtest.py

backtest-recent:
	python scripts/backtest.py --recent

# Production
predict:
	python scripts/generate_daily_picks.py

predict-grok:
	python scripts/generate_daily_picks_with_grok.py

pipeline:
	python scripts/production_daily_pipeline.py

dashboard:
	python scripts/generate_performance_dashboard.py

line-shop:
	python scripts/line_shopping.py

# Maintenance
clean:
	@echo "Cleaning cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml 2>/dev/null || true
	rm -rf dist/ build/ 2>/dev/null || true
	@echo "Clean complete!"

clean-all: clean
	@echo "WARNING: This will delete all data and models!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf data/ models/ reports/ logs/; \
		echo "Deep clean complete!"; \
	fi

update:
	pip install --upgrade pip
	pip install --upgrade -r requirements.txt

# Security
security-check:
	@echo "Running security scans..."
	pip install bandit trufflehog
	bandit -r src/ scripts/ -f screen
	trufflehog filesystem . --json


# Git helpers
git-clean-secrets:
	@echo "Removing BFG and temporary files..."
	rm -f bfg.jar sensitive_strings.txt replacements.txt

commit-check:
	pre-commit run --all-files

# Performance monitoring
profile:
	python -m cProfile -o profile.stats scripts/generate_daily_picks.py
	python -m pstats profile.stats

# API testing
test-api:
	python scripts/test_api_keys.py

# Weekly automation
weekly-tasks:
	@echo "Running weekly maintenance..."
	make data-force
	make train
	make backtest
	@echo "Weekly tasks complete!"

# System info
info:
	@echo "System Information:"
	@echo "==================="
	@python --version
	@echo ""
	@pip list | grep -E "xgboost|pandas|numpy|scikit-learn"
	@echo ""
	@echo "Data Status:"
	@ls -lh data/raw/ 2>/dev/null || echo "No data found"
	@echo ""
	@echo "Model Status:"
	@ls -lh models/ 2>/dev/null || echo "No models found"

