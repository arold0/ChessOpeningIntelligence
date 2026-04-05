"""
Chess Opening Intelligence — Pipeline Package

Data pipeline for ingesting, cleaning, and loading Lichess chess data
into DuckDB for analytical processing.

Pipeline layers:
    L1 — Ingest: PGN .zst / puzzle CSV → raw parquet
    L2 — Clean:  Raw parquet → partitioned clean parquet
    L3 — Load:   Clean parquet → DuckDB tables
    L4 — Analyse: DuckDB views → metrics + dashboards
"""
