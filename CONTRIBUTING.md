# Contributing to Chess Opening Intelligence

## Branch Strategy

```
feat/xxx  →  dev  →  main
```

- **Never push directly to `main`.**
- Create feature branches from `dev`: `git checkout -b feat/your-feature dev`
- Open a PR to `dev` when your feature is ready.
- `main` is updated only via merge from `dev` after validation.

### Branch naming

| Type | Format | Example |
|------|--------|---------|
| Feature | `feat/short-description` | `feat/puzzle-pipeline` |
| Fix | `fix/short-description` | `fix/elo-bracket-edge` |
| Docs | `docs/short-description` | `docs/readme-update` |
| Chore | `chore/short-description` | `chore/update-deps` |

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add puzzle ingestion pipeline
fix: handle null ECO codes in clean step
docs: update README with key findings
chore: bump polars to 1.2
test: add integration tests for DuckDB load
```

## Development Setup

```bash
# Install all dependency groups
pip install -e ".[dev,notebook,dashboard]"

# Install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
# All tests
make test

# By category
make test-unit           # Fast, no I/O
make test-integration    # Uses temp files and DuckDB
make test-sql            # SQL logic against temp DuckDB

# With coverage
make test-cov
```

## Code Style

- **Type hints** on all function signatures.
- **Polars** for pipeline logic — never `pandas` in pipeline scripts.
- **`pathlib.Path`** for all file paths — never raw strings.
- **`if __name__ == "__main__":`** guard in all pipeline scripts.
- **Docstrings** on all public functions (Google style).
- Run `make lint` before committing.

## Project Conventions

### Python
- All constants defined in `pipeline/config.py` — single source of truth.
- Pipeline logging uses `pipeline/logger.py` — never bare `print()`.
- Data quality checks use `pipeline/validators.py`.

### SQL
- Execution order: `schema.sql → macros.sql → views.sql → metrics.sql`.
- All columns and tables in `snake_case`.
- Complex queries use named CTEs (no nested subqueries).
- Reusable formulas go in `macros.sql`.
