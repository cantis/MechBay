# MechBay Security Guide

## Scope

MechBay is a single-user (or small household) desktop application. There is no authentication system — anyone who can reach the web server is treated as the owner. Security priorities are: protecting the local database from accidental data loss, preventing unsafe input from corrupting data, keeping secrets out of source control, and not accidentally exposing the app to the network.

Read this file before touching: CSRF configuration, file upload handling, input validation, structured logging, proxy / networking settings, or secret key management.

## No Authentication

MechBay has no login system. This is intentional for a local desktop tool.

**Consequences:**
- Never add a multi-user feature without also adding authentication and per-user data isolation.
- Do not expose the development server (`main.py`) to a public or shared network. It binds to `127.0.0.1` only.
- The Docker / Waitress production server binds to `0.0.0.0:5000`. Apply firewall rules or reverse-proxy ACLs if deploying in a shared environment.

## CSRF Protection

Flask-WTF `CSRFProtect` is initialised in `create_app()` and protects all POST/PUT/DELETE routes automatically.

- CSRF token is injected into every page via `<meta name="csrf-token" content="{{ csrf_token() }}">` in `base.html`.
- AJAX requests must include the token:

```javascript
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
});
```

- CSRF validation is **disabled** only when `TESTING=True` in test config, so the test client can POST without tokens.
- Never disable `WTF_CSRF_ENABLED` in non-test configurations.

## Secret Key

`SECRET_KEY` signs Flask sessions and CSRF tokens. Rules:

- **Never commit** a real secret key to source control.
- If `SECRET_KEY` is not set in the environment, the app generates a random ephemeral key on startup and logs a warning. This is acceptable for local desktop use but means sessions are invalidated on every restart.
- In any persistent deployment (Docker, shared server), set `SECRET_KEY` via environment variable or `.env` file.
- `WTF_CSRF_SECRET_KEY` defaults to `SECRET_KEY` if not set separately.

## Input Validation

Validate at route boundaries before passing values to services.

- Always convert ID parameters with `int()` wrapped in `try/except (TypeError, ValueError)`. Return 400 on failure.
- Strip and validate string inputs (name fields, etc.) at the route level.
- Services assume inputs are already validated; do not add route-level validation inside service functions.
- Do not trust hidden form fields for access control, roles, or pricing.

## File Uploads

Import routes accept JSON files only.

- Maximum upload size: **10 MB** (`MAX_CONTENT_LENGTH = 10 * 1024 * 1024` in `Config`). Flask enforces this and returns 413 automatically.
- Do not save uploaded files to disk; parse them directly in memory using `request.data` or `request.files`.
- Validate that uploaded JSON is well-formed before processing; catch `json.JSONDecodeError` and return 400.
- Import functions in services must handle malformed or unexpected JSON fields gracefully.

## Proxy and Networking

`TRUST_PROXY_HEADERS` defaults to `False`. Set it to `True` **only** when:

1. The app is behind a trusted reverse proxy (nginx, Caddy, etc.)
2. That proxy strips any client-supplied forwarded headers and sets its own

When enabled, `ProxyFix` is applied with `x_for=1, x_proto=1, x_host=1, x_prefix=1`. Setting this incorrectly allows clients to spoof their IP address.

## Structured Logging

MechBay uses `structlog` for all logging.

**Do log:**
- Application startup event (`app_startup`) with version, debug flag, DB URL (not credentials)
- Database rollback events
- 400/404 errors at WARNING
- 500 errors at ERROR with traceback

**Do not log:**
- Passwords or tokens
- Full connection strings containing credentials
- Personal data or miniature inventory contents in error messages
- Request/response bodies

Error handlers return generic messages to the browser; detailed context stays server-side.

## Database

- SQLite database stored at `%APPDATA%\MechBay\mechbay.db` (Windows desktop) or `/data/mechbay.db` (Docker).
- The directory is created automatically if it does not exist.
- There is no Alembic migration history. Schema changes require manual SQL or DB recreation.
- All queries go through SQLAlchemy ORM — no string-concatenated SQL.
- Use `session_scope()` for all DB access; never execute raw SQL strings with user input.

## Dependency Management

- Dependencies are pinned in `uv.lock`. Do not leave version constraints floating.
- Keep the `uv.lock` file committed to source control for reproducible installs.
- Review new dependencies before adding them; prefer well-maintained packages for non-trivial functionality.
