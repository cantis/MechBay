# MechBay Architecture

## Overview

MechBay is a Flask/SQLAlchemy desktop web application for managing BattleTech miniature inventories. It uses an application factory pattern, a service layer for all business logic, and SQLite as its database. The frontend is server-rendered Jinja2 templates with Bootstrap 5.

## Directory Layout

```
app/
  __init__.py           # Application factory: create_app()
  config.py             # Config class; reads from environment / .env
  extensions.py         # SQLAlchemy engine, session, session_scope()
  logging.py            # Structlog setup (colorized dev / JSON prod)
  migrations.py         # Schema creation via Base.metadata.create_all()
  seed.py               # Demo data population
  blueprints/           # Thin route controllers — one file per area
  models/               # One file per SQLAlchemy model
  services/             # Business logic — one file per domain
  templates/            # Jinja2 templates; base.html + per-area folders
  static/               # CSS overrides and JS; main libraries via CDN
tests/                  # pytest; conftest.py provides all shared fixtures
docs/                   # Architecture, development, design, security docs
main.py                 # Development entry point (debug=True, port 5001)
server.py               # Production entry point (Waitress WSGI)
Dockerfile              # Docker image definition
```

## Blueprint / Route Structure

| Blueprint         | Prefix             | File                              |
|-------------------|--------------------|-----------------------------------|
| `miniatures`      | `/miniatures`      | `app/blueprints/miniatures.py`    |
| `forces`          | `/forces`          | `app/blueprints/forces.py`        |
| `lance_templates` | `/lance-templates` | `app/blueprints/lance_templates.py` |
| *(root)*          | `/`                | registered in `app/__init__.py`   |

Root routes: `/` (redirects to inventory), `/about`.

## Application Factory

`create_app(config_overrides)` in `app/__init__.py`:

1. Loads `Config` from environment / `.env`
2. Applies any `config_overrides` dict (used by tests for in-memory DB)
3. Conditionally installs `ProxyFix` if `TRUST_PROXY_HEADERS=True`
4. Configures structlog (colorized in debug, JSON in production)
5. Initialises CSRF protection via Flask-WTF (`WTF_CSRF_ENABLED=False` in test mode)
6. Calls `init_db(app)` to bind SQLAlchemy and create all tables
7. Auto-seeds the database on first run (if miniature count == 0)
8. Registers blueprints and error handlers

## Session Management

Always use `session_scope()` from `app/extensions.py`. Never use raw sessions.

```python
from ..extensions import session_scope

def get_force_by_id(force_id: int) -> Force | None:
    with session_scope() as session:
        force = session.get(Force, force_id)
        if force:
            # Eager-load all relationships needed outside the session
            for lance in force.lances:
                _ = lance.miniatures
            session.expunge(force)   # Critical — prevents DetachedInstanceError
        return force
```

Rules:
- `session.expunge()` every object before returning from a service function
- Service layer owns all DB transactions; blueprints call services only
- `expire_on_commit=False` is set on `SessionLocal` to reduce lazy-load surprises

## Dual-Mode Routes (JSON + Form)

Every mutating route supports both JSON (AJAX) and traditional form POST.

**Standard JSON envelope:**
```python
{"success": bool, "error": str | None, "data": dict | None}
```

**HTTP status codes:**
- `200` — success
- `400` — bad input (missing/invalid params)
- `404` — resource not found
- `409` — conflict (e.g. duplicate miniature in force)

**Pattern:**
```python
@bp.route("/<int:id>/remove-miniature", methods=["POST"])
def remove_miniature(id: int):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form   # silent=True avoids Content-Type errors
    miniature_id = data.get("miniature_id")

    if not miniature_id:
        if is_json:
            return jsonify({"success": False, "error": "Missing miniature_id"}), 400
        flash("Missing miniature ID", "danger")
        return redirect(url_for("forces.detail", id=id))

    try:
        miniature_id_int = int(miniature_id)
    except (TypeError, ValueError):
        if is_json:
            return jsonify({"success": False, "error": "Invalid miniature ID"}), 400
        flash("Invalid miniature ID", "danger")
        return redirect(url_for("forces.detail", id=id))

    success = force_service.remove_miniature_from_force(miniature_id_int, id)

    # Set flash BEFORE the is_json check — JS uses setTimeout + location.reload()
    flash("Miniature Removed" if success else "Miniature not found in force",
          "success" if success else "danger")

    if is_json:
        if success:
            return jsonify({"success": True}), 200
        return jsonify({"success": False, "error": "Miniature not found in force"}), 404
    return redirect(url_for("forces.detail", id=id))
```

Rules:
1. Validate `int()` conversions in `try/except` at route level — never in services
2. Set flash messages **before** the `if is_json` check when JS reloads the page
3. Always include `"success"` key in every JSON response
4. Use `request.get_json(silent=True) or request.form` — not `request.json`

## SQLAlchemy Delete Pattern

ORM `.delete()` fails when the query uses a join. Always fetch-then-delete:

```python
# ❌ Fails with joined queries
session.query(ForceMiniature).join(Lance).filter(...).delete()

# ✅ Correct
records = session.query(ForceMiniature).join(Lance).filter(...).all()
for record in records:
    session.delete(record)
```

## Model Relationships

```
Miniature  (individual physical model)
    ↑ referenced by
ForceMiniature  (join table with position order)
    ↓ belongs to
Lance  (group of up to 4 mechs within a force)
    ↓ belongs to (cascade delete)
Force  (named army collection; at most one is_active=True)

LanceTemplate  (reusable chassis pattern for auto-matching)
    ↓ has many
LanceTemplateMiniature  (chassis name patterns; not FK to Miniature)
```

**Active Force**: At most one `Force.is_active = True` at any time. Switching active force clears all others. Used for quick miniature assignment from the inventory screen.

**Lance template matching**: Uses chassis name substring — "Warhammer" matches "Warhammer WHM-6R" and "Warhammer WHM-7M".

## Error Handlers

Registered in `create_app()` for 400, 404, and 500:

- JSON requests → `{"success": false, "error": "..."}` with appropriate status code
- Browser requests → `app/templates/error.html` with `code`, `title`, `message`, `icon`, `color` params
- 400/404 log at WARNING; 500 logs at ERROR with full traceback

## Import / Export

All entities support JSON import/export via the web interface:

- **Export**: `send_file()` with a timestamped filename — `{EntityType}_YYYYMMDD_HHMMSS.json`
- **Import**: Merge mode (match on key field and upsert) or overwrite mode (truncate then insert)
- Max upload size: 10 MB (`MAX_CONTENT_LENGTH` in `Config`)
- Generate timestamps: `datetime.now().strftime("%Y%m%d_%H%M%S")`

## Structured Logging

Uses `structlog` throughout. Import pattern:

```python
import structlog
logger = structlog.get_logger()
logger.info("event_name", key=value, ...)
```

- Development (DEBUG=True): colourized console output
- Production: JSON lines to stdout (compatible with Docker log drivers)
- Test mode: WARNING level and above only
