# MechBay

An application for managing BattleTech miniature inventories and organizing forces for gameplay. Built with Flask, SQLAlchemy, and Bootstrap, MechBay provides an intuitive interface for tracking miniatures, building forces with drag-and-drop, and generating pick lists for gaming sessions. 

## Installation

### For Users (Windows Executable)

**Download the latest release:**
1. Visit the [Releases page](https://github.com/cantis/MechBay/releases)
2. Download `MechBay_vX.Y.Z-windows.zip`
3. Extract and run `MechBay.exe`
4. Browser opens automatically to http://127.0.0.1:5001

No Python installation required!

### For Developers

See [DEVELOPER.md](Docs/DEVELOPER.md) for full setup instructions.

## Features

### Miniature Inventory Management
- **Add, edit, duplicate, and delete** miniatures with detailed tracking
- **Fields tracked**: Prefix, Chassis, Variant, Series, Unique ID, Tonnage, Tray location
- **Import/Export** miniatures to/from JSON
- **Quick actions**: Double-click to edit, borderless icon buttons
- **Visual indicators**: Green borders for miniatures assigned to active force

### Force Management
- **Create and manage forces** with multiple lances
- **Drag-and-drop** miniatures between lances for easy organization
- **Lance templates** - Pre-defined configurations (Assault, Battle, Command, Fire Support, Heavy, Recon)
- **Auto-matching** - Templates automatically find miniatures matching chassis patterns
- **Force activation** - Set one force as active for quick miniature assignment
- **Print reports** - Generate printer-friendly pick lists with checkboxes for gathering miniatures
- **Export/Import forces** to/from JSON with full lance structure

### Lance Template System
- **Create custom templates** with chassis patterns (e.g., "Warhammer" matches all variants)
- **Edit and delete** templates through intuitive UI
- **Export/Import** all templates as a single JSON file (LanceTemplates_*.json)
- **Reusable configurations** - Apply templates to quickly build forces

## Quick Start

Using uv on Windows PowerShell:

```powershell
# Create/activate a virtual environment and install deps
uv sync

# Run the app
uv run python .\main.py
```

Then open http://127.0.0.1:5000 in your browser.

## Database Migrations

Apply database schema updates:

```powershell
uv run python -m app.migrations
```

## Tests and Lint

```powershell
uv run pytest -q
uv run ruff check .
```

## Seed Sample Data

Populate the database with sample miniatures and lance templates:

```powershell
uv run python -m app.seed
```

This creates 6 default lance templates:
- Assault Lance (4x 80-100 ton 'mechs)
- Battle Lance (4x 50-65 ton 'mechs)
- Command Lance (4x command variants)
- Fire Support Lance (4x long-range 'mechs)
- Heavy Lance (4x 60-75 ton 'mechs)
- Recon Lance (4x light/fast 'mechs)

## Import/Export Formats

### Miniatures (miniatures_export.json)
- **Export**: Produces JSON array of all miniature objects
- **Import**: Can overwrite (default) or merge by matching on `unique_id`

### Forces (forces/Force_*.json)
- **Export**: Includes force name, lances, and assigned miniatures with full details
- **Import**: Creates or updates forces with complete lance structure

### Lance Templates (lance_templates/LanceTemplates_*.json)
- **Export**: All templates with names, descriptions, and chassis patterns
- **Import**: Updates existing templates by name or creates new ones

## Project Structure

```
MechBay/
├── app/
│   ├── blueprints/        # Route handlers (miniatures, forces, lance_templates)
│   ├── models/            # SQLAlchemy models (Miniature, Force, Lance, etc.)
│   ├── services/          # Business logic layer
│   ├── templates/         # Jinja2 HTML templates
│   ├── static/            # CSS, JavaScript assets
│   ├── migrations.py      # Database schema migrations
│   └── seed.py            # Sample data population
├── tests/                 # pytest unit tests
├── main.py                # Application entry point
└── README.md
```

## Technology Stack

- **Backend**: Flask 3.x, SQLAlchemy ORM, SQLite database
- **Frontend**: Bootstrap 5, FontAwesome icons, SortableJS for drag-and-drop
- **Testing**: pytest with in-memory SQLite
- **Code Quality**: Ruff linter

## License

MechBay is open source software licensed under the [MIT License](LICENSE).

Copyright (c) 2025 Evan Young, Winnipeg, Canada

## Contributing

This project is currently in beta testing. Contributions, bug reports, and feature requests are welcome! Please feel free to open an issue or submit a pull request.

