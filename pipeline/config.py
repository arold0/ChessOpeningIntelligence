"""
Chess Opening Intelligence — Pipeline Configuration

Single source of truth for all shared constants, paths, brackets,
and filter rules used across pipeline scripts.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv()

# ── Project paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
DATA_SOURCE: Path = DATA_DIR / "source"      # .zst download files (L1 input)
DATA_RAW: Path = DATA_DIR / "raw"            # L1 output: raw parquet
DATA_CLEAN: Path = DATA_DIR / "clean"        # L2 output: partitioned parquet
DATA_SAMPLE: Path = DATA_DIR / "sample"      # Committed dev/test samples
SQL_DIR: Path = PROJECT_ROOT / "sql"
LOGS_DIR: Path = PROJECT_ROOT / "logs"

# ── DuckDB ────────────────────────────────────────────────────────────────────
DUCKDB_PATH: Path = Path(os.getenv("DUCKDB_PATH", str(DATA_DIR / "chess_oi.duckdb")))

# ── Pipeline parameters ──────────────────────────────────────────────────────
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "100000"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Elo configuration ────────────────────────────────────────────────────────
ELO_MIN: int = 600
ELO_MAX: int = 2800
MIN_MOVES: int = 5

# Elo bracket boundaries — single source of truth for Python and SQL
# Each tuple: (lower_bound_inclusive, upper_bound_exclusive, label)
ELO_BRACKETS: list[tuple[int, int, str]] = [
    (0, 800, "<800"),
    (800, 1000, "800-999"),
    (1000, 1200, "1000-1199"),
    (1200, 1400, "1200-1399"),
    (1400, 1600, "1400-1599"),
    (1600, 1800, "1600-1799"),
    (1800, 2000, "1800-1999"),
    (2000, 2200, "2000-2199"),
    (2200, 9999, "2200+"),
]

# ── Time control classification ───────────────────────────────────────────────
# Based on base time in seconds (increment is ignored for classification)
# Lichess standard: https://lichess.org/faq#time-controls
TIME_CLASS_THRESHOLDS: list[tuple[int, str]] = [
    (29, "ultrabullet"),     # < 30s
    (179, "bullet"),         # 30s – 179s
    (479, "blitz"),          # 180s – 479s
    (1499, "rapid"),         # 480s – 1499s
    (99999, "classical"),    # 1500s+
]

# ── Filter rules (DESIGN.md §2.3) ────────────────────────────────────────────
VALID_VARIANTS: set[str] = {"standard"}
BOT_TITLES: set[str] = {"BOT"}
MIN_BASE_TIME_SECONDS: int = 30

# ── Data quality thresholds ───────────────────────────────────────────────────
MIN_GAMES_FOR_CONFIDENCE: int = 500   # Below this → "low confidence" flag
MIN_PUZZLE_RATING: int = 400
MAX_PUZZLE_RATING: int = 3000
CP_LOSS_BLUNDER_THRESHOLD: int = 200  # cp_loss > 200 = blunder
CP_LOSS_MISTAKE_THRESHOLD: int = 100  # cp_loss > 100 = mistake


def elo_bracket(elo: int) -> str:
    """Classify an Elo rating into its bracket label.

    Uses the same boundaries as the DuckDB macro `elo_bracket()` in
    sql/macros.sql to ensure consistency between Python and SQL layers.

    Args:
        elo: Player Elo rating (expected range: 600–2800).

    Returns:
        Bracket label string, e.g. "1200-1399".
    """
    for lower, upper, label in ELO_BRACKETS:
        if lower <= elo < upper:
            return label
    return "2200+"


def classify_time_control(time_control: str) -> str:
    """Classify a Lichess time control string into a time class.

    Parses the base time from strings like "600+0" or "180+2" and maps
    it to a standard time class (bullet, blitz, rapid, classical).

    Args:
        time_control: Raw time control string from Lichess PGN.

    Returns:
        Time class string, e.g. "blitz".
    """
    try:
        base_seconds = int(time_control.split("+")[0])
    except (ValueError, AttributeError):
        return "unknown"

    for threshold, label in TIME_CLASS_THRESHOLDS:
        if base_seconds <= threshold:
            return label
    return "classical"
