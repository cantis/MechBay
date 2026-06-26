# MechBay Development Guide

## Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git
- Windows (database defaults to `%APPDATA%\MechBay`; Docker works cross-platform)

## Initial Setup

```powershell
# Clone and enter project
git clone https://github.com/cantis/MechBay.git
cd MechBay

# Install dependencies
uv sync

# Create database tables
uv run python -m app.migrations

# (Optional) Load demo data
uv run python -m app.seed

# Start development server
uv run python main.py
```

The development server starts on `http://127.0.0.1:5001` (debug=True).

## Environment Variables

Create a `.env` file in the project root. All variables are optional — the app runs with sensible defaults.

| Variable               | Default                                   | Description                                              |
|------------------------|-------------------------------------------|----------------------------------------------------------|
| `SECRET_KEY`           | Random (ephemeral)                        | Flask session signing key. **Set in production.**        |
| `WTF_CSRF_SECRET_KEY`  | Falls back to `SECRET_KEY`                | CSRF token signing key                                   |
| `DATABASE_URL`         | `sqlite:///%APPDATA%/MechBay/mechbay.db`  | SQLAlchemy connection string. `/data/mechbay.db` in Docker |
| `DEBUG`                | `false`                                   | Enables Flask debug mode and colourized logs             |
| `APPLICATION_ROOT`     | `/`                                       | Path prefix when hosted behind a reverse proxy           |
| `TRUST_PROXY_HEADERS`  | `false`                                   | Set `true` only behind a trusted reverse proxy           |

> **Warning**: If `SECRET_KEY` is not set, a random key is generated on each restart, invalidating all existing sessions. Always set it in production.

See `.env.example` for a template.

## Database Operations

### Schema creation

```powershell
uv run python -m app.migrations
```

Creates all tables using `Base.metadata.create_all()`. Also runs automatically on app startup via `init_db()`. There is **no Alembic**; schema changes require manual `ALTER` statements or dropping and recreating the database.

### Seed data

```powershell
uv run python -m app.seed
```

Populates the database with:
- 2 sample miniatures (Warhammer WHM-6R, Banshee BNC-3E)
- 6 lance templates (Command, Assault, Heavy, Fire Support, Recon, Battle)

**Auto-seeding**: Removed. Use **File → Load sample data…** or `uv run python -m app.seed`. On startup, `restore_session()` reloads a linked `.mechbay` file when the database is empty.

## Running Tests and Lint

```powershell
# Run all tests
uv run pytest -q

# Unit tests only (fast)
uv run pytest tests/*_unit.py -v

# Integration tests only
uv run pytest tests/ -m slow

# Lint with ruff
uv run ruff check .

# Coverage report
uv run pytest --cov=app
```

See `docs/TESTING.md` for full test conventions, fixture descriptions, and parallel execution.

## Docker Workflow

### Build and run locally

```powershell
# Build image
docker build -t mechbay .

# Run container (data persisted to a named volume)
docker run -d `
  -p 5000:5000 `
  -v mechbay_data:/data `
  -e SECRET_KEY=change-me `
  --name mechbay `
  mechbay
```

The container stores the database at `/data/mechbay.db`.

### Environment variables in Docker

Pass variables via `-e` flags or a `.env` file:

```powershell
docker run -d `
  -p 5000:5000 `
  -v mechbay_data:/data `
  --env-file .env `
  --name mechbay `
  mechbay
```

### Entrypoint

`scripts/entrypoint.sh` seeds the database (if empty) and starts Waitress on port 5000.

## Build and Packaging (Windows Standalone)

MechBay can be packaged as a standalone Windows `.exe` using PyInstaller.

```powershell
# Run the build script
.\build.ps1
```

The spec file is `mechbay.spec`. The output lands in `build/mechbay/`. The packaged app runs without a Python installation.

## Linting and Code Style

```powershell
# Check all Python files
uv run ruff check .

# Auto-fix fixable issues
uv run ruff check . --fix
```

Python-specific conventions (typing, model layout, service responsibilities) are in `.github/instructions/python.instructions.md`.
