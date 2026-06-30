# Build MechBay: A Flask Application

> **Superseded:** Original Phase 1 plan. Current app uses File → `.mechbay` / `.mbforce` save/load instead of JSON import/export pages.

You are GitHub Copilot in VSCode.
Your task is to generate a Python 3.13 Flask web application named **MechBay**, used to manage a BattleTech miniature inventory.

The app must use:
- Flask with Blueprints
- SQLAlchemy ORM
- Bootstrap 5 for the frontend
- SQLite for the database
- JSON import/export for backups
- Ruff for linting
- pytest for testing
- UV for dependency and environment management

---

## 🧠 Purpose

MechBay helps track physical BattleTech miniatures stored in trays.
Each miniature has a **unique ID** (used to locate the figure physically), a **prefix** (e.g., WHM), a **chassis** (e.g., Warhammer), and a **type** (Mech, Vehicle, Infantry, VTOL, or Support).
The app provides a searchable list, plus the ability to add, edit, delete, import, and export data.

This first version focuses on inventory control only — no variants, pilots, or force building yet.

---

## 🏗️ Project Layout

project_root/
│
├── app/
│ ├── init.py # Flask app factory
│ ├── config.py # configuration classes
│ ├── extensions.py # db setup (SQLAlchemy)
│ │
│ ├── models/
│ │ ├── init.py
│ │ └── miniature.py # Miniature model definition
│ │
│ ├── services/
│ │ ├── init.py
│ │ └── miniature_service.py # CRUD + JSON import/export
│ │
│ ├── blueprints/
│ │ ├── init.py
│ │ └── miniatures.py # Routes for listing, editing, importing
│ │
│ ├── templates/
│ │ ├── base.html
│ │ ├── navbar.html
│ │ └── miniatures/
│ │ ├── list.html
│ │ ├── add.html
│ │ └── edit.html
│ │
│ ├── static/
│ │ ├── css/
│ │ └── js/
│ │
│ └── app.db # SQLite database file
│
├── tests/
│ ├── init.py
│ ├── conftest.py
│ └── test_miniatures.py
│
├── .env
├── .ruff.toml
├── pyproject.toml
├── README.md


---

## 🗃️ Model — Miniature

Each record represents a single physical miniature.

**Fields:**
- `id` — primary key (autoincrement)
- `unique_id` — user-assigned ID code for the mini (string, required, unique)
- `prefix` — short model code like WHM or BNC (string, required)
- `chassis` — full miniature name (string, required)
- `type` — Mech, Vehicle, Infantry, VTOL, or Support (string, required)
- `status` — painting progress ('','New','Primed','Drybush','Detail','Base','Finished')
- `tray_id` — identifier for the tray or case where the miniature is stored
- `notes` — freeform text for details or remarks
- `created_at` — timestamp, defaults to current time

---

## 🌐 Routes (Blueprint: `miniatures.py`)

- `/` → redirect to `/miniatures`
- `/miniatures` → list all miniatures, searchable/sortable table
- `/miniatures/add` → form to add a new miniature
- `/miniatures/<id>/edit` → edit an existing miniature
- `/miniatures/<id>/delete` → delete miniature (confirmation modal)
- `/miniatures/export` → download JSON export of all minis
- `/miniatures/import` → upload JSON file to restore or merge inventory

---

## 🧠 Service Layer

`miniature_service.py` handles:
- CRUD database operations
- JSON import/export functions
- Optional “merge” mode for imports (default overwrite)

Expose methods like:
- `get_all_miniatures(search_query: str | None)`
- `add_miniature(data: dict)`
- `update_miniature(id: int, data: dict)`
- `delete_miniature(id: int)`
- `export_to_json(path: str)`
- `import_from_json(path: str, merge: bool)`

---

## 💄 UI / Templates

Use **Bootstrap 5**.

**`base.html`**
- Defines document structure, includes navbar and flash messages.
- Loads Bootstrap from CDN.

**`navbar.html`**
- Links:
  - *Inventory* → `/miniatures`
  - *Import/Export* → `/miniatures/import`
  - *About* → `/about`

**Miniature Pages**
- `list.html`: shows a Bootstrap table with search and sort
- `add.html`: form for adding new minis
- `edit.html`: form for updating existing minis
- Use modals for delete confirmation

---

## 🧪 Testing

Use `pytest` with the Arrange–Act–Assert pattern.

Create tests for:
- Adding a miniature
- Editing a miniature
- Deleting a miniature
- JSON import/export consistency

Use a temporary SQLite database for tests.

---

## 🧰 Environment & Linting

**Initialize project:**
```powershell
uv init
uv add flask sqlalchemy pytest ruff
```
