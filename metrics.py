"""
Metrics
-------
Lightweight execution timing utilities.

The decorator pattern here is handy for wrapping pipeline steps — you get
timing information in the logs without cluttering every function with
start/stop time boilerplate.

Usage:
    from metrics import Metrics

    class MyTransformer:
        @Metrics.time_execution
        def clean(self, df):
            ...
"""

import functools
import time
from typing import Callable, Any

from etl.utils.logger import get_logger

logger = get_logger("lendwise.metrics")


class Metrics:

    @staticmethod
    def time_execution(func: Callable) -> Callable:
        """
        Decorator that logs how long a function took to run.
        Works on both regular functions and methods.
        """

        @functools.wraps(func)  # Preserves the original function's name and docstring
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            # TO block log execution time even if the function raises an error
            try:
                result = func(*args, **kwargs)
                elapsed = time.monotonic() - start
                logger.info("%s completed in %.2fs", func.__qualname__, elapsed)
                return result
            except Exception as exc:
                elapsed = time.monotonic() - start
                logger.error(
                    "%s failed after %.2fs: %s", func.__qualname__, elapsed, exc
                )
                raise

        return wrapper

    @staticmethod
    def log_row_counts(datasets: dict) -> None:
        """
        Logs the row count for each DataFrame in a dict.
        Useful as a quick sanity check after extraction or transformation.
        """
        for name, df in datasets.items():
            logger.info("Row count — %s: %d", name, len(df))
