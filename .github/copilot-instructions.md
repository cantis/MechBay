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
Routes support both JSON (AJAX) and form submissions. Detect request type and respond appropriately:

```python
@bp.route("/<int:id>/add-miniature", methods=["POST"])
def add_miniature(id: int):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form  # silent=True prevents Content-Type errors

    # ... business logic ...

    if is_json:
        return jsonify({"success": True}), 200
    else:
        flash("Miniature added to lance", "success")
        return redirect(url_for("miniatures.list_miniatures"))
```

**Key**: Set flash messages BEFORE the `if is_json` check when using AJAX + page reload (see `forces.remove_miniature`). JavaScript uses `setTimeout(() => location.reload(), 100)` to allow flash message to persist.

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
