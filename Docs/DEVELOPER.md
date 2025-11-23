# MechBay Developer Documentation

## Project Overview

MechBay is a Flask web application for managing BattleTech miniature inventories and organizing forces. It provides tools to track individual miniatures, organize them into forces and lances, and use reusable lance templates for quick force building. Focus is on physical miniature management rather than spicific mech versions that would be used in gameplay.

### Core Entities

- **Miniatures**: Individual models with properties like chassis, series ID, paint status, and storage location
- **Forces**: Collections of lances representing your army composition
- **Lance Templates**: Reusable configurations of 4 mechs that can auto-match miniatures from inventory
- **Lances**: Groups of miniatures within a force, with drag-and-drop ordering

### Technology Stack

- **Backend**: Flask 3.1+ with SQLAlchemy 2.0+ ORM
- **Database**: SQLite (default location: `%APPDATA%\MechBay\mechbay.db`)
- **Server**: Waitress WSGI server (production)
- **Frontend**: Bootstrap 5, FontAwesome, SortableJS for drag-and-drop
- **Package Manager**: UV (modern Python dependency manager)
- **Python**: 3.13+ required

### Platform Support

**Current**: Windows-only (database defaults to `%APPDATA%\MechBay`)

**Future**: Cross-platform support would require using `platformdirs` library or conditional logic for database paths:
- Linux: `~/.local/share/mechbay/`
- macOS: `~/Library/Application Support/MechBay/`

## Developer Setup

### Prerequisites

- Python 3.13 or higher
- UV package manager ([install guide](https://github.com/astral-sh/uv))
- Git

### Initial Setup

```powershell
# Clone repository
git clone https://github.com/cantis/MechBay.git
cd MechBay

# Install dependencies
uv sync

# Create database and tables
uv run python -m app.migrations

# (Optional) Load demo data
uv run python -m app.seed

# Run development server
uv run python main.py
```

The server will start on `http://127.0.0.1:5001` and automatically open in your browser.

### Environment Configuration

Create a `.env` file in the project root to customize settings:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///custom/path/to/database.db
DEBUG=true
```

See `.env.example` for all available options.

## Architecture Patterns

### Session Management

**Critical Pattern**: Always use the `session_scope()` context manager from `app/extensions.py` for database operations.

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

**Key Rules**:
- Always `session.expunge()` objects before returning from service functions to prevent `DetachedInstanceError`
- Service layer (`app/services/`) handles all business logic and DB transactions
- Blueprints (`app/blueprints/`) are thin controllers that call services

### Dual-Mode Routes (JSON + Form)

Routes support both JSON (AJAX) and traditional form submissions:

```python
@bp.route("/<int:id>/add-miniature", methods=["POST"])
def add_miniature(id: int):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form

    # ... business logic ...

    if is_json:
        return jsonify({"success": True}), 200
    else:
        flash("Miniature added to lance", "success")
        return redirect(url_for("miniatures.list_miniatures"))
```

**Important**: Set flash messages BEFORE the `if is_json` check when using AJAX + page reload pattern. JavaScript uses `setTimeout(() => location.reload(), 100)` to allow flash messages to persist.

### SQLAlchemy Delete Pattern

Cannot call `.delete()` on queries with joins. Use this pattern:

```python
# ❌ Fails with joins
session.query(ForceMiniature).join(Lance).filter(...).delete()

# ✅ Correct pattern
records = session.query(ForceMiniature).join(Lance).filter(...).all()
for record in records:
    session.delete(record)
```

## Project Structure

```
MechBay/
├── app/
│   ├── __init__.py           # Flask app factory, routes, auto-seeding
│   ├── config.py             # Configuration classes
│   ├── extensions.py         # SQLAlchemy setup and session_scope()
│   ├── migrations.py         # Database schema creation
│   ├── seed.py               # Demo data population
│   ├── blueprints/           # Route controllers
│   │   ├── forces.py
│   │   ├── lance_templates.py
│   │   └── miniatures.py
│   ├── models/               # SQLAlchemy models
│   │   ├── force.py
│   │   ├── lance.py
│   │   ├── miniature.py
│   │   ├── force_miniature.py
│   │   ├── lance_template.py
│   │   └── lance_template_miniature.py
│   ├── services/             # Business logic layer
│   │   ├── force_service.py
│   │   ├── lance_template_service.py
│   │   └── miniature_service.py
│   ├── templates/            # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── navbar.html
│   │   ├── about.html
│   │   ├── forces/
│   │   ├── lance_templates/
│   │   └── miniatures/
│   └── static/               # CSS and JavaScript (mostly CDN-based)
├── tests/                    # Pytest test suite
│   ├── conftest.py           # Test fixtures (in-memory DB)
│   └── test_miniatures.py
├── Docs/                     # Documentation
├── main.py                   # Application entry point
├── mechbay.spec              # PyInstaller configuration
├── build.ps1                 # Build and packaging script
├── pyproject.toml            # Project metadata and dependencies
└── .env.example              # Environment variable template
```

## Database Operations

### Schema Creation

```powershell
uv run python -m app.migrations
```

Creates all tables using SQLAlchemy `Base.metadata.create_all()`. Also runs automatically on first app startup via `init_db()` in `app/__init__.py`.

**Note**: No Alembic migrations - uses simple "create if not exists" pattern. Schema changes require manual ALTER statements or DB recreation.

### Seed Data

```powershell
uv run python -m app.seed
```

Populates database with:
- 2 sample miniatures (Warhammer WHM and Banshee BNC)
- 6 lance templates (Command, Assault, Heavy, Fire Support, Recon, Battle)

**Auto-seeding**: On first run, if database is empty (0 miniatures), seed data is automatically loaded with console message "Demo data loaded: X records created".

### Key Relationships

- `Force` → many `Lance` (cascade delete)
- `Lance` → many `ForceMiniature` (join table with position ordering)
- `ForceMiniature` → one `Miniature` (reference, not cascade)
- `LanceTemplate` → many `LanceTemplateMiniature` (chassis patterns)

**Active Force**: Only one force can be `is_active=True` at a time. Used for quick miniature assignment from inventory screen.

### Import/Export

All entities support JSON import/export via web interface:
- **Export**: Downloads timestamped JSON file (e.g., `Miniature_Inventory_20251123_143025.json`)
- **Import**: Supports merge mode (match on key field) or overwrite mode
- File naming convention: `{EntityType}_YYYYMMDD_HHMMSS.json`

## Testing

### Run Test Suite

```powershell
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_miniatures.py

# Run with coverage
uv run pytest --cov=app
```

### Test Configuration

Tests use in-memory SQLite database via `conftest.py` fixture:

```python
@pytest.fixture(scope="function")
def app():
    """Create test app with in-memory database."""
    return create_app({"DATABASE_URL": "sqlite+pysqlite:///:memory:"})
```

Each test gets a fresh database, ensuring test isolation.

## Build and Packaging

### Development Build

```powershell
# Install/update dependencies
uv sync

# Run development server
uv run python main.py
```

### Production Build

```powershell
# Run automated build script (bumps version, builds, packages)
.\build.ps1
```

Build script automates:
1. Bump patch version in `pyproject.toml` via `uv version --bump patch`
2. Extract new version number
3. Sync dependencies with `uv sync`
4. Build executable with PyInstaller using `mechbay.spec`
5. Create distribution folder `dist/MechBay_vX.Y.Z/` with:
   - Executable folder
   - `.env.example` file
   - `README.txt` with user instructions
6. Create ZIP archive `dist/MechBay_vX.Y.Z.zip` for distribution

### PyInstaller Configuration

The `mechbay.spec` file configures:
- **Entry point**: `main.py`
- **Data files**: `app/templates/` directory bundled
- **Hidden imports**: SQLAlchemy, Waitress, Flask, dotenv
- **Build mode**: Single-folder distribution (COLLECT)
- **Console**: Enabled (shows startup messages and logs)
- **Compression**: UPX enabled

### Manual Build Commands

```powershell
# Bump version manually
uv version --bump patch    # or 'minor' or 'major'

# Build executable
uv run pyinstaller mechbay.spec --clean

# Executable located in: dist/MechBay/MechBay.exe
```

## Continuous Integration & Deployment

MechBay uses GitHub Actions for automated testing, building, and releases.

### CI Workflow (`.github/workflows/ci.yml`)

**Triggers**: Push to `main` or `PackageForDistro` branches, or pull requests to `main`

**Actions**:
- ✅ Runs all pytest tests
- ✅ Runs Ruff linter
- ✅ Verifies app initialization
- ❌ Fails build if any checks fail

This ensures code quality and prevents regressions from being merged.

### Release Workflow (`.github/workflows/release.yml`)

**Triggers**: Manually creating a GitHub release

**Actions**:
1. Sets up Python 3.13 and UV environment
2. Installs dependencies and PyInstaller
3. Extracts version from git tag
4. Builds Windows executable with PyInstaller
5. Creates distribution folder with executable, `.env.example`, and user README
6. Creates ZIP archive `MechBay_vX.Y.Z-windows.zip`
7. Uploads ZIP to GitHub release as downloadable asset
8. Stores build artifacts for 30 days

### Creating a Release

**Recommended workflow:**

```powershell
# Bump version locally
uv version --bump patch  # or 'minor' or 'major'

# Commit version change
git add pyproject.toml
git commit -m "Bump version to $(Select-String -Path pyproject.toml -Pattern 'version = ""(.+)""' | ForEach-Object { $_.Matches.Groups[1].Value })"
git push

# Create release on GitHub.com:
# 1. Go to Releases → Draft a new release
# 2. Create tag: v0.1.1 (matching pyproject.toml version)
# 3. Set title: Release v0.1.1
# 4. Add release notes describing changes
# 5. Click "Publish release"
# GitHub Actions automatically builds and attaches Windows ZIP
```

### Distributing to Users

After release is published with attached ZIP:

1. Share GitHub release URL with users (e.g., your brothers)
2. They download `MechBay_vX.Y.Z-windows.zip` from release page
3. Extract and run `MechBay.exe`
4. Application runs with no additional setup required

### Monitoring Builds

- **Actions Tab**: View workflow runs and build logs
- **Releases Page**: See all published releases with downloadable assets
- **Build Artifacts**: Access 30-day stored builds even without creating releases

### Troubleshooting CI/CD

**Tests fail on push:**
- Check Actions tab for detailed error logs
- Run `uv run pytest -v` locally to reproduce
- Fix issues before merging to main

**Release build fails:**
- Verify PyInstaller spec is correct
- Check that all dependencies are in `pyproject.toml`
- Test local build with `uv run pyinstaller mechbay.spec`

## Code Quality

### Linting

```powershell
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .
```

### Code Style

- Follow PEP 8 conventions
- Use type hints for function signatures
- Prefer f-strings over `.format()` or `%` formatting
- Use `from __future__ import annotations` for forward references
- Service functions should be pure and stateless
- Always use `session_scope()` context manager for DB access

## Frontend Patterns

### SortableJS Drag-and-Drop

Forces detail page uses SortableJS for miniature reordering between lances:

1. User drags miniature to new position
2. UI updates immediately (optimistic)
3. POST request to backend with new positions
4. Backend validates and saves
5. On error, page reloads to show correct state

### Editable Elements

Double-click elements with `.editable-lance-name` class to edit inline:
- Uses JavaScript `prompt()` for input
- Fetch API to save changes
- Updates DOM on success without reload

### Auto-Fading Flash Messages

Flash messages auto-dismiss after 3 seconds using Bootstrap Alert component (see `base.html`). Includes close button with `alert-dismissible fade show` classes.

## API Endpoints

### Health Check

```
GET /health
```

Returns JSON with app status and version:

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### Main Routes

- `/` - Redirects to miniatures list
- `/about` - About page with version info
- `/miniatures` - List all miniatures (search, sort, filter)
- `/miniatures/add` - Add new miniature
- `/miniatures/<id>/edit` - Edit miniature
- `/miniatures/<id>/delete` - Delete miniature
- `/miniatures/export` - Export all miniatures to JSON
- `/miniatures/import` - Import miniatures from JSON
- `/forces` - List all forces
- `/forces/<id>` - Force detail with drag-drop lance management
- `/forces/<id>/export` - Export force to JSON
- `/forces/import` - Import force from JSON
- `/lance_templates` - List all lance templates
- `/lance_templates/<id>` - Template detail
- `/lance_templates/export` - Export templates to JSON
- `/lance_templates/import` - Import templates from JSON

## Future Considerations

### Cross-Platform Support

**Current limitation**: Database path uses Windows-specific `AppData/Roaming`.

**Solution options**:
1. Use `platformdirs` library (recommended):
   ```python
   from platformdirs import user_data_dir
   db_dir = Path(user_data_dir("MechBay", "YourOrg"))
   ```

2. Manual OS detection:
   ```python
   import sys
   if sys.platform == "win32":
       db_dir = Path.home() / "AppData" / "Roaming" / "MechBay"
   elif sys.platform == "darwin":
       db_dir = Path.home() / "Library" / "Application Support" / "MechBay"
   else:  # Linux
       db_dir = Path.home() / ".local" / "share" / "mechbay"
   ```

### Deployment Options

**Current**: Waitress WSGI server (Windows-focused)

**Alternatives**:
- **Gunicorn**: Industry standard, but Linux/macOS only
- **Docker**: Containerized deployment, cross-platform
- **Cloud**: Deploy to Heroku, Railway, Render, etc.

### Database Migrations

**Current**: Simple `create_all()` approach, no versioned migrations.

**Future**: Consider Alembic for:
- Schema versioning
- Automated migration generation
- Safe schema upgrades without data loss

### Game Mechanics Scope

**Current focus**: Physical miniature inventory management only.

**Out of scope**:
- Pilot skills and experience
- Special abilities or equipment loadouts
- Damage tracking
- Campaign management
- Force balancing by BV (Battle Value)

This is intentional - MechBay focuses on the "what do I own and where is it?" problem, not recreating MegaMek or other game management tools.

### Additional Features to Consider

- **Batch operations**: Edit/delete multiple miniatures at once
- **Advanced search**: Filter by multiple criteria simultaneously
- **Photos**: Upload images of painted miniatures
- **Tags**: Custom labels/categories beyond series and status
- **Reports**: Inventory statistics, paint progress tracking
- **Backup automation**: Scheduled database backups
- **Multi-user**: User accounts and shared inventories (requires authentication)

## Contributing

This is currently a personal project, but contributions are welcome! When contributing:

1. Follow existing code patterns (especially session management)
2. Add tests for new features
3. Run linter before committing: `uv run ruff check .`
4. Update this documentation for architecture changes
5. Test both JSON API and form submission modes for new routes

## Support

- **Repository**: https://github.com/cantis/MechBay
- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Documentation**: Check `Docs/` folder and inline code comments

## License

[Add license information here]

---

*Last updated: November 2025*
