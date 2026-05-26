"""
Cloud Function Entry Point — main.py
--------------------------------------
HTTP-triggered Cloud Function that runs the full ETL pipeline.

Deploy with:
    gcloud functions deploy lendwise-etl \
        --runtime python311 \
        --trigger-http \
        --entry-point etl_pipeline \
        --source . \
        --set-env-vars GCP_PROJECT=...,BUCKET_NAME=...,BQ_DATASET=...

Supports an optional JSON body:
    { "dry_run": true }   → runs transforms + validation but skips all loads
    { "dry_run": false }  → full run (default)
"""

import functions_framework
from flask import Request, jsonify

from etl.pipelines.etl_pipeline import ETLPipeline
from etl.utils.validators import ValidationError
from etl.utils.logger import get_logger

logger = get_logger("lendwise.main")


@functions_framework.http
def etl_pipeline(request: Request):
    """
    Cloud Function HTTP handler.
    Returns a JSON response with pipeline result metadata.
    """
    body = request.get_json(silent=True) or {}
    dry_run: bool = body.get("dry_run", False)

    logger.info(
        "Cloud Function triggered | dry_run=%s | source=%s",
        dry_run,
        request.remote_addr,
    )

    try:
        pipeline = ETLPipeline(mode="cloud")
        result = pipeline.run(dry_run=dry_run)
        return jsonify(result), 200

    except ValidationError as exc:
        logger.error("Pipeline aborted — validation gate failed")
        return (
            jsonify(
                {
                    "status": "validation_failure",
                    "error": str(exc),
                }
            ),
            422,
        )

    except Exception as exc:
        logger.exception("Pipeline failed with unexpected error")
        return (
            jsonify(
                {
                    "status": "error",
                    "error": str(exc),
                }
            ),
            500,
        )
