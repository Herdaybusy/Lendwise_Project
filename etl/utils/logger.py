"""
Logger
------
Centralised logging setup for the LendWise ETL system.
"""

import logging
import os
import sys


def get_logger(name: str) -> logging.Logger:

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    logger.propagate = False  # Prevent duplicate output from root logger

    return logger


# Root pipeline logger — imported by modules that don't need a specific name
# e.g. from etl.utils.logger import logger
logger = get_logger("lendwise.etl")
