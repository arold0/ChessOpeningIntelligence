"""
Chess Opening Intelligence — Pipeline Logger

Structured logging for pipeline execution. Produces output matching the
format specified in DESIGN.md §9.2:

    [INGEST]  source=lichess_2015-01.pgn.zst  rows_raw=1497237  runtime=142s
    [CLEAN]   rows_in=1497237  rows_out=1441089  dropped=56148  reason=filters
    [LOAD]    table=games  rows_loaded=1441089  matches_clean=True
    [QUALITY] elo_range=PASS  eco_fk=PASS  null_rate_eco=0.3%=PASS
"""

from __future__ import annotations

import logging
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from pipeline.config import LOG_LEVEL, LOGS_DIR

# ── Directory setup ───────────────────────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class PipelineFormatter(logging.Formatter):
    """Custom formatter that produces pipeline-style structured log output.

    Format: [STEP]  key=value  key=value  ...

    The step name is extracted from the logger name. For example, a logger
    named "pipeline.ingest" will produce lines prefixed with [INGEST].
    """

    def format(self, record: logging.LogRecord) -> str:
        # Extract step name from logger name (e.g. "pipeline.ingest" → "INGEST")
        parts = record.name.split(".")
        step = parts[-1].upper() if len(parts) > 1 else "PIPELINE"

        timestamp = self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S")
        level = record.levelname[0]  # I, W, E, D

        return f"{timestamp} {level} [{step:8s}] {record.getMessage()}"


def get_logger(step_name: str) -> logging.Logger:
    """Create a pipeline logger for a specific step.

    Each logger writes to both stdout and a rotating log file in logs/.

    Args:
        step_name: Pipeline step name (e.g. "ingest", "clean", "load").
                   Used as the log prefix in brackets.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(f"pipeline.{step_name}")

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = PipelineFormatter()

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (logs/pipeline.log)
    file_handler = logging.FileHandler(LOGS_DIR / "pipeline.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def log_step(step_name: str) -> Callable:
    """Decorator that logs the start, end, and duration of a pipeline step.

    Usage:
        @log_step("ingest")
        def ingest_games(source_path: Path) -> int:
            ...

    The decorated function's return value is logged as `result=<value>`.
    If the function raises an exception, the error is logged and re-raised.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(step_name)
            func_name = func.__name__
            logger.info(f"start  func={func_name}")

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                logger.info(f"done   func={func_name}  runtime={elapsed:.1f}s  result={result}")
                return result
            except Exception as exc:
                elapsed = time.perf_counter() - start_time
                logger.error(f"FAIL   func={func_name}  runtime={elapsed:.1f}s  error={exc}")
                raise

        return wrapper
    return decorator


def log_quality_check(
    logger: logging.Logger,
    check_name: str,
    passed: bool,
    detail: str = "",
) -> None:
    """Log a data quality check result in a standardized format.

    Args:
        logger: Logger instance (typically from get_logger("quality")).
        check_name: Name of the quality check (e.g. "elo_range", "eco_fk").
        passed: Whether the check passed.
        detail: Optional detail string (e.g. "null_rate=0.3%").
    """
    status = "PASS" if passed else "FAIL"
    detail_str = f"  {detail}" if detail else ""
    level = logging.INFO if passed else logging.ERROR
    logger.log(level, f"{check_name}={status}{detail_str}")
