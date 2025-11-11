# MechBay

Flask web app to manage a BattleTech miniature inventory. This is phase 1: inventory control (no pilots/variants/forces).

## Quick start

Using uv on Windows PowerShell:

```powershell
# Create/activate a virtual environment and install deps
uv sync

# Run the app
uv run python .\main.py
```

Then open http://127.0.0.1:5000 in your browser.

## Tests and lint

```powershell
uv run pytest -q
uv run ruff check .
```

## Optional: seed sample data

```powershell
uv run python -m app.seed
```

## Import/Export

- Export produces a JSON array of miniature objects.
- Import can overwrite (default) or merge by matching on `unique_id`.

