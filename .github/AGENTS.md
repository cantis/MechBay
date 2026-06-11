# MechBay Copilot Instructions

This repository uses scoped instruction files under `.github/instructions/`.
Follow those files when their `applyTo` patterns match the files being changed.

## Important project references

- Read `docs/ARCHITECTURE.md` before changing service boundaries, session handling, route patterns, or model relationships.
- Read `docs/TESTING.md` before adding or changing tests.
- Read `docs/SECURITY.md` before touching CSRF configuration, file uploads, input validation, logging, or secret key handling.
- Read `docs/DEVELOPMENT.md` for local setup, migration commands, Docker workflow, and environment variables.
- Read `docs/DESIGN.md` before changing UI layout, templates, flash messages, or reusable components.

## Overview

Flask web app for managing BattleTech miniature inventories and organizing forces. Three main entities: **Miniatures** (individual models), **Forces** (collections of lances), and **Lance Templates** (reusable lance configurations).

- **Backend**: Flask 3.1+, SQLAlchemy 2.0+, SQLite, Waitress (production)
- **Frontend**: Bootstrap 5.3, Font Awesome 6.4, SortableJS — all via CDN; server-rendered Jinja2
- **Package manager**: `uv` — use PowerShell for all commands
- **Python**: 3.13+ required

## Directory Layout

```
app/
  __init__.py           # Application factory: create_app()
  config.py             # Config class; reads from environment / .env
  extensions.py         # SQLAlchemy setup and session_scope()
  blueprints/           # Thin route controllers (one file per area)
  models/               # SQLAlchemy models (one file per model)
  services/             # Business logic (one file per domain)
  templates/            # Jinja2 templates; base.html + per-area folders
  static/               # Custom CSS and JS; libraries via CDN
tests/                  # pytest; conftest.py has all shared fixtures
docs/                   # Architecture, development, design, security docs
main.py                 # Dev entry point (debug=True, port 5001)
server.py               # Production entry point (Waitress)
Dockerfile              # Docker image
```

## Blueprint / Route Structure

| Blueprint         | Prefix             | File                                |
|-------------------|--------------------|-------------------------------------|
| `miniatures`      | `/miniatures`      | `app/blueprints/miniatures.py`      |
| `forces`          | `/forces`          | `app/blueprints/forces.py`          |
| `lance_templates` | `/lance-templates` | `app/blueprints/lance_templates.py` |
| *(root)*          | `/`                | registered in `app/__init__.py`     |

## Architecture Patterns

### Session Management

Always use `session_scope()` from `app/extensions.py`. Always `session.expunge()` objects before returning from service functions.

```python
from ..extensions import session_scope

def get_force_by_id(force_id: int) -> Force | None:
    with session_scope() as session:
        force = session.get(Force, force_id)
        if force:
            for lance in force.lances:
                _ = lance.miniatures
            session.expunge(force)  # Critical: prevents DetachedInstanceError
        return force
```

### Dual-Mode Routes (JSON + Form)

Routes support both JSON (AJAX) and form submissions. Standard JSON envelope:

```python
{"success": bool, "error": str | None, "data": dict | None}
```

HTTP status codes: `200` success · `400` bad input · `404` not found · `409` conflict

Rules:
1. Validate `int()` conversions in `try/except` at route level — return 400 on failure
2. Set flash messages **before** the `if is_json` check — JS uses `setTimeout(() => location.reload(), 100)`
3. Use `request.get_json(silent=True) or request.form` — `silent=True` prevents Content-Type errors
4. Always include `"success"` key in every JSON response

### SQLAlchemy Delete Pattern

```python
# ❌ Fails with joins
session.query(ForceMiniature).join(Lance).filter(...).delete()

# ✅ Correct
records = session.query(ForceMiniature).join(Lance).filter(...).all()
for record in records:
    session.delete(record)
```

## Key Model Relationships

- `Force` → many `Lance` (cascade delete)
- `Lance` → many `ForceMiniature` (join table with position ordering)
- `ForceMiniature` → one `Miniature` (reference, not cascade)
- `LanceTemplate` → many `LanceTemplateMiniature` (chassis patterns for auto-matching)

**Active Force**: Only one force can be `is_active=True` at a time.

**Miniature naming**: Chassis (`"Warhammer"`), Prefix (`"WHM"`), Type (`"WHM-6R"`). Template matching uses chassis name substring.

## Development Workflow

```powershell
uv sync                           # Install dependencies
uv run python .\main.py           # Start dev server (port 5001)
uv run python -m app.migrations   # Create/update schema
uv run python -m app.seed         # Load demo data
uv run pytest -q                  # Run tests
uv run ruff check .               # Lint
```

Tests use in-memory SQLite via `create_app({"DATABASE_URL": "sqlite+pysqlite:///:memory:"})`.

## Key Environment Variables

See `docs/DEVELOPMENT.md` for the full table.

- `SECRET_KEY` — Flask session/CSRF signing key (random ephemeral default; **set in production**)
- `DATABASE_URL` — defaults to `%APPDATA%\MechBay\mechbay.db` (Windows) or `/data/mechbay.db` (Docker)
- `DEBUG` — enables debug mode and colourized logs
- `TRUST_PROXY_HEADERS` — set `true` only behind a trusted reverse proxy
- `APPLICATION_ROOT` — path prefix for reverse-proxy deployments

## File Naming Conventions

Export files: `{EntityType}_YYYYMMDD_HHMMSS.json`
Generate with: `datetime.now().strftime("%Y%m%d_%H%M%S")`
