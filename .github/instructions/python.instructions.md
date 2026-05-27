---
applyTo: "**/*.py"
---

Repository-specific Python style and instructions

These instructions capture Python-specific conventions used in this repository. Keep them short and actionable.

- Naming and typing:
  - Follow PEP 8 naming for modules, functions, classes, and variables.
  - Add type annotations for all functions and variables. Prefer `X | None` for optionals (not `Optional[X]`).
  - Use modern built-in union types (e.g., `str | None`, `list[int]`).

- Imports and formatting:
  - Keep imports sorted and grouped as enforced by `ruff`.
  - Run linting and formatting with the project wrapper: `uv run ruff check .` and `uv run ruff format .`.

- Models and typing:
  - One model per file under `src/models/` (avoid a single `models.py`).
  - SQLAlchemy model classes should include explicit `__init__` methods to aid type checkers and IDEs.
  - Store datetimes as ISO 8601 strings with UTC timezone (use timezone-aware datetimes everywhere).

- Application structure and separation of concerns:
  - Use the application factory pattern in `src/app.py` and register Blueprints there.
  - Keep routes thin: push business logic into the `services/` layer. Services should be the primary place for complex logic and DB interactions.

- Logging and diagnostics:
  - Do not add application-level logging unless a reviewer or a task explicitly requests it.

- Tests:
  - Write tests using Arrange / Act / Assert structure.
  - Use `with app.app_context():` for DB operations in tests.
  - Import models inside test functions (to avoid circular imports).
  - Use direct route paths (e.g., `/followups`) in tests instead of `url_for()` to avoid Flask context issues.

- Miscellaneous:
  - Follow repository conventions from `.github/AGENTS.md` for commands and environment usage (PowerShell + `uv` wrapper, set `PYTHONPATH` as required when running tests or CLI tasks).

