# LendWise ETL — Developer Shortcuts
# Run `make help` to see all commands

.PHONY: help install test lint format run-local dry-run deploy

help:
	@echo ""
	@echo "LendWise ETL — Available Commands"
	@echo "-----------------------------------"
	@echo "  make install     Install all dependencies"
	@echo "  make test        Run unit tests with coverage"
	@echo "  make lint        Run flake8 + black + isort checks"
	@echo "  make format      Auto-format code with black + isort"
	@echo "  make run-local   Run full pipeline in local mode"
	@echo "  make dry-run     Run pipeline in cloud mode with dry_run=True"
	@echo "  make deploy      Deploy Cloud Function to GCP"
	@echo ""

install:
	pip install -r requirements.txt

test:
	pytest tests/unit/ -v --tb=short \
		--cov=etl --cov-report=term-missing --cov-fail-under=80

test-integration:
	RUN_MODE=local pytest tests/integration/ -v -m integration --tb=short

lint:
	flake8 . --max-line-length=100 --exclude=.git,__pycache__,.venv
	black --check --diff .
	isort --check-only --diff .

format:
	black .
	isort .

run-local:
	RUN_MODE=local python -c "from etl.pipelines.etl_pipeline import ETLPipeline; ETLPipeline(mode='local').run()"

dry-run:
	@echo "Running pipeline in dry-run mode (no GCS/BQ writes)..."
	python -c "from etl.pipelines.etl_pipeline import ETLPipeline; r = ETLPipeline(mode='cloud').run(dry_run=True); print(r)"

deploy:
	gcloud functions deploy lendwise-etl \
		--runtime python311 \
		--trigger-http \
		--entry-point etl_pipeline \
		--source . \
		--region europe-west2 \
		--set-env-vars GCP_PROJECT=$(GCP_PROJECT),BUCKET_NAME=$(BUCKET_NAME),BQ_DATASET=$(BQ_DATASET)
