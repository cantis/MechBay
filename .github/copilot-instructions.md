# MechBay Copilot Instructions

## Project Overview
Flask web app for managing BattleTech miniature inventories and organizing forces. Three main entities: **Miniatures** (individual models), **Forces** (collections of lances), and **Lance Templates** (reusable lance configurations).

## Architecture Patterns

### Session Management
- Use `session_scope()` context manager from `app/extensions.py` for all DB operations
- Always `session.expunge()` objects before returning from service functions to prevent detached instance errors
- Service layer (`app/services/`) handles all business logic and DB transactions
- Blueprints (`app/blueprints/`) are thin controllers that call services

Example:
```python
from ..extensions import session_scope

def get_force_by_id(force_id: int) -> Force | None:
    with session_scope() as session:
        force = session.get(Force, force_id)
        if force:
            # Eager load relationships within session
            for lance in force.lances:
                _ = lance.miniatures
            session.expunge(force)  # Critical: make accessible outside session
        return force
```

### Dual-Mode Routes (JSON + Form)
Routes support both JSON (AJAX) and form submissions. Detect request type and respond appropriately.

**Standard JSON envelope** — all JSON responses use this shape:
```python
{"success": bool, "error": str | None, "data": dict | None}
```
- `success`: always present
- `error`: human-readable message on failure, `None` on success
- `data`: optional payload (e.g., created entity fields)

**HTTP status codes**:
- `200` — success
- `400` — bad input (missing params, invalid IDs, unknown action)
- `404` — resource not found
- `409` — conflict (e.g., duplicate miniature in force)

**Dual-mode pattern**:
```python
@bp.route("/<int:id>/remove-miniature", methods=["POST"])
def remove_miniature(id: int):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form
    miniature_id = data.get("miniature_id")

    if not miniature_id:
        if is_json:
            return jsonify({"success": False, "error": "Missing miniature_id"}), 400
        flash("Missing miniature ID", "danger")
        return redirect(url_for("forces.detail", id=id))

    # Validate int conversion at route boundary
    try:
        miniature_id_int = int(miniature_id)
    except (TypeError, ValueError):
        if is_json:
            return jsonify({"success": False, "error": "Invalid miniature ID"}), 400
        flash("Invalid miniature ID", "danger")
        return redirect(url_for("forces.detail", id=id))

    success = force_service.remove_miniature_from_force(miniature_id_int, id)

    # Set flash BEFORE the is_json check — JS uses setTimeout + reload
    if success:
        flash("Miniature Removed", "success")
    else:
        flash("Miniature not found in force", "danger")

    if is_json:
        if success:
            return jsonify({"success": True}), 200
        return jsonify({"success": False, "error": "Miniature not found in force"}), 404
    return redirect(url_for("forces.detail", id=id))
```

**Rules**:
1. Always validate `int()` conversions in try/except at route level, return 400
2. Set flash messages BEFORE the `if is_json` check when JS uses `setTimeout(() => location.reload(), 100)`
3. Use `request.get_json(silent=True) or request.form` — `silent=True` prevents Content-Type errors
4. Include `"success"` key in every JSON response

### SQLAlchemy Delete Pattern
Cannot call `.delete()` on queries with joins. Use this pattern instead:

```python
# ❌ Fails with joins
session.query(ForceMiniature).join(Lance).filter(...).delete()

# ✅ Correct pattern
records = session.query(ForceMiniature).join(Lance).filter(...).all()
for record in records:
    session.delete(record)
```

## File Naming Conventions
- Export files use timestamp format: `{EntityType}_YYYYMMDD_HHMMSS.json`
- Example: `Miniature_Inventory_20251120_143025.json`
- Generate with: `datetime.now().strftime("%Y%m%d_%H%M%S")`

## Frontend Patterns

### SortableJS Drag-and-Drop
Forces page uses SortableJS for miniature reordering between lances. On drop:
1. Update UI immediately (optimistic)
2. POST new positions to backend
3. Backend validates and saves

### Auto-Fading Flash Messages
Flash messages auto-dismiss after 3 seconds using Bootstrap Alert component (see `app/templates/base.html`). Include close button with `alert-dismissible fade show` classes.

### Editable Elements
Double-click elements with `.editable-lance-name` class to edit inline. Use `prompt()` for input, fetch API to save, update DOM on success.

### Custom Error Handlers
App registers handlers for 400, 404, and 500 in `app/__init__.py`. Each handler:
- Supports dual-mode: JSON requests get `{"success": false, "error": "..."}`, browser requests get branded error page
- Logs at WARNING (400/404) or ERROR with traceback (500)
- Uses shared `app/templates/error.html` template with `code`, `title`, `message`, `icon`, `color` params

## Development Workflow

### Running the App
```powershell
uv sync                      # Install dependencies
uv run python .\main.py      # Start dev server (debug=True)
```

### Database Operations
```powershell
uv run python -m app.migrations  # Create/update schema
uv run python -m app.seed        # Populate sample data (6 lance templates)
```

### Testing
```powershell
uv run pytest -q            # Run tests (uses in-memory SQLite)
uv run ruff check .         # Lint
```

Tests use `conftest.py` fixture that creates fresh in-memory DB per test via `create_app({"DATABASE_URL": "sqlite+pysqlite:///:memory:"})`.

## Key Relationships
- `Force` → many `Lance` (cascade delete)
- `Lance` → many `ForceMiniature` (join table with position ordering)
- `ForceMiniature` → one `Miniature` (reference, not cascade)
- `LanceTemplate` → many `LanceTemplateMiniature` (chassis patterns for auto-matching)

**Active Force**: Only one force can be `is_active=True` at a time. Used for quick miniature assignment from inventory screen.

### Miniature Naming Convention
- **Chassis**: Base model name (e.g., "Warhammer")
- **Prefix**: Chassis designator/acronym (e.g., "WHM")
- **Type**: Variant code (e.g., "WHM-6R", "WHM-7M")

Lance template matching uses chassis name - "Warhammer" pattern matches both "Warhammer WHM-6R" and "Warhammer WHM-7M" variants.

## Import/Export
All import functions support merge mode (match on key field) or overwrite mode. Export generates timestamped filenames. See `app/services/*_service.py` for implementations.

## Future Considerations
- **Deployment**: Plans to migrate to Gunicorn + Docker for production
- **Scope**: Currently focused on physical miniature inventory management, not game mechanics (pilot skills, special abilities, detailed loadouts)
