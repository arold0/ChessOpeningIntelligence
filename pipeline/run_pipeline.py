"""
Chess Opening Intelligence — Pipeline Orchestrator

CLI entry point for running pipeline steps in sequence.
Supports running individual steps or the full pipeline.

Usage:
    python -m pipeline.run_pipeline --step all
    python -m pipeline.run_pipeline --step ingest --month 2015-01
    python -m pipeline.run_pipeline --step clean
    python -m pipeline.run_pipeline --step load
    python -m pipeline.run_pipeline --dry-run --step all
"""

from __future__ import annotations

import argparse
import sys

from pipeline.logger import get_logger

logger = get_logger("orchestrator")

# ── Step registry ─────────────────────────────────────────────────────────────
# Each step maps to its module's main() function.
# These will be populated as pipeline scripts are implemented.
STEPS: dict[str, str] = {
    "ingest": "pipeline.01_ingest_games",
    "ingest_puzzles": "pipeline.02_ingest_puzzles",
    "clean": "pipeline.03_clean_games",
    "clean_puzzles": "pipeline.04_clean_puzzles",
    "load": "pipeline.05_load_duckdb",
}

STEP_ORDER: list[str] = [
    "ingest",
    "ingest_puzzles",
    "clean",
    "clean_puzzles",
    "load",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the pipeline orchestrator.

    Args:
        argv: Optional list of arguments (defaults to sys.argv).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Chess Opening Intelligence — Pipeline Orchestrator",
    )
    parser.add_argument(
        "--step",
        choices=[*STEPS.keys(), "all"],
        default="all",
        help="Pipeline step to run (default: all)",
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Month to process, e.g. '2015-01' (applies to ingest/clean steps)",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Process only sample data for development",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without executing pipeline steps",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    """Execute pipeline steps based on parsed arguments.

    Args:
        args: Parsed command-line arguments.
    """
    steps_to_run = STEP_ORDER if args.step == "all" else [args.step]

    if args.dry_run:
        logger.info(f"dry_run=True  steps={steps_to_run}")
        logger.info("configuration is valid — no steps executed")
        return

    logger.info(f"start  steps={steps_to_run}  month={args.month}  sample={args.sample}")

    for step_name in steps_to_run:
        logger.info(f"step={step_name}  status=pending")
        # TODO: Import and execute each step's main() function
        # once pipeline scripts are implemented.
        logger.info(f"step={step_name}  status=not_implemented")

    logger.info("pipeline complete")


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    try:
        run(args)
    except Exception as exc:
        logger.error(f"pipeline failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
