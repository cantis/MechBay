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
  models/               # One file per SQLAlchemy model (flat — see note below)
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

| Blueprint         | Prefix             | File                                 |
|--------------------|--------------------|--------------------------------------|
| `miniatures`       | `/miniatures`      | `app/blueprints/miniatures.py`       |
| `forces`           | `/forces`          | `app/blueprints/forces.py`           |
| `alpha_strike`     | `/forces`          | `app/blueprints/alpha_strike.py`     |
| `lance_templates`  | `/lance-templates` | `app/blueprints/lance_templates.py`  |
| `campaigns`        | `/campaigns`       | `app/blueprints/campaigns.py`        |
| `contracts`        | *(none — routes are `/campaigns/...`, `/contracts/...`, `/sorties/...`)* | `app/blueprints/contracts.py` |
| `files`            | `/files`           | `app/blueprints/files.py`            |
| *(root)*           | `/`                | registered in `app/__init__.py`      |

Root routes: `/` (redirects to inventory), `/about`.

Note: `contracts.py` declares its blueprint with no `url_prefix` and defines routes under three different path roots (`/campaigns/<id>/contracts`, `/contracts/...`, `/sorties/...`, `/sortie-units/...`). It is really "the rest of the Chaos Campaign gameplay loop" (contracts, sorties, after-action) split out of `campaigns.py` for file size, not a separate resource area — see [Campaign Domain](#campaign-domain-chaos-campaign) below.

## Application Factory

`create_app(config_overrides)` in `app/__init__.py`:

1. Loads `Config` from environment / `.env`
2. Applies any `config_overrides` dict (used by tests for in-memory DB)
3. Conditionally installs `ProxyFix` if `TRUST_PROXY_HEADERS=True`
4. Configures structlog (colorized in debug, JSON in production)
5. Initialises CSRF protection via Flask-WTF (`WTF_CSRF_ENABLED=False` in test mode)
6. Calls `init_db(app)` to bind SQLAlchemy and create all tables
7. Restores the linked document session via `session_restore_service.restore_session()` (skipped in test mode)
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
            session.expunge(force)  # Critical — prevents DetachedInstanceError
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
    data = request.get_json(silent=True) or request.form  # silent=True avoids Content-Type errors
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
    flash(
        "Miniature Removed" if success else "Miniature not found in force",
        "success" if success else "danger",
    )

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

MechBay's models fall into two domains that share only the `Miniature` table as a bridge: the **Inventory domain** (what miniatures you physically own, and how they're organized for tabletop play) and the **Campaign domain** (persistent, narrative campaign state that consumes miniatures as raw material).

### Inventory Domain

```
Miniature  (individual physical model)
    ↑ referenced by
ForceMiniature  (join table with position order)
    ↓ belongs to
Lance  (group of up to 4 mechs within a force)
    ↓ belongs to (cascade delete)
Force  (named army collection; at most one is_active=True)
    ↓ has one (optional)
AlphaStrikeForce  (Alpha Strike point-budget settings for a force)

ForceMiniature
    ↓ has one (optional)
AlphaStrikeAssignment  (frozen MUL stats used for Alpha Strike play)

LanceTemplate  (reusable chassis pattern for auto-matching)
    ↓ has many
LanceTemplateMiniature  (chassis name patterns; not FK to Miniature)
```

**Active Force**: At most one `Force.is_active = True` at any time. Switching active force clears all others. Used for quick miniature assignment from the inventory screen.

**Lance template matching**: Uses chassis name substring — "Warhammer" matches "Warhammer WHM-6R" and "Warhammer WHM-7M".

### Campaign Domain (Chaos Campaign)

The campaign system implements the *MechWarrior: Destiny* "Hot Spots" / Chaos Campaign ruleset (see `docs/next_steps.md` and the campaign prompt notes for source material). Internally this is simply named `Campaign`, `CampaignUnit`, etc. — there is currently only one campaign ruleset, but **a second one ("Aces") is planned**, so treat every model/route/service in this section as "Chaos Campaign", not "campaigns in general." See [Preparing for a Second Campaign System](#preparing-for-a-second-campaign-system-aces) below.

```
Campaign  (one played-through campaign: warchest, reputation, current month/location)
    ├── CampaignLance          (organizational grouping of units, order-only — no rules of its own)
    │       ↓ has many
    │   CampaignUnit           (a 'Mech committed to the campaign: condition, damage, salvage)
    │       ↑ optionally linked to Miniature (physical model backing this campaign unit)
    │
    ├── CampaignPilot           (MechWarrior: skills, wounds, edge, preferred unit)
    │
    ├── Contract                (an employment contract: pay %, salvage/command rights, months)
    │       ↓ has many
    │   ContractUnit            (join table: which CampaignUnits are committed to this contract)
    │       ↓ has many
    │   Sortie                  ("one tabletop battle" — a Track, in Hot Spots terms)
    │       ↓ has many
    │   SortieUnit              (frozen pilot+unit+config snapshot as fielded in that battle)
    │
    ├── WarchestTransaction     (audit log of every warchest debit/credit)
    ├── TravelEvent             (jumps between contracts; warchest cost)
    ├── DamageEvent             (damage taken by a CampaignUnit in a Sortie)
    ├── RepairOrder             (queued/completed repair, tied to a DamageEvent's unit)
    ├── RearmOrder              (queued/completed ammo/ordnance resupply)
    ├── PilotInjuryEvent        (wound/death log for a CampaignPilot)
    └── UnitConfigurationEvent  (OmniMech reconfiguration history)
```

Key flow: a `Force` is "graduated" into a `Campaign` (`campaign_service.create_campaign_from_force`), snapshotting each `ForceMiniature` into a `CampaignUnit` — from that point on, the campaign's units are independent of the inventory/force records that seeded them. Gameplay proceeds *Contract → Sortie → after-action* (`after_action_service.apply_after_action`), which is where damage/repair/rearm/injury events and warchest transactions get created, and `campaign_service.advance_campaign_month` rolls the calendar forward between contracts.

**Naming note**: `CampaignUnit`/`SortieUnit` duplicate most of `CampaignUnit`'s MUL snapshot fields (chassis, variant, tonnage, `mul_snapshot_json`, …) by design — `SortieUnit` is a frozen copy so that later edits to (or deletion of) a `CampaignUnit` never rewrite history for a battle that already happened.

## Error Handlers

Registered in `create_app()` for 400, 404, and 500:

- JSON requests → `{"success": false, "error": "..."}` with appropriate status code
- Browser requests → `app/templates/error.html` with `code`, `title`, `message`, `icon`, `color` params
- 400/404 log at WARNING; 500 logs at ERROR with full traceback

## Import / Export

MechBay uses document-based save/load instead of standalone JSON export pages:

- **Inventory**: `.mechbay` project files (miniatures, lance templates, settings) via **File** menu
- **Forces**: `.mbforce` files via **Save force** / **File → Open force**
- **Jeff's BT Tools**: per-lance or all-lances export for external play tools
- **Legacy JSON**: old miniature/template export files can still be opened via **File → Open inventory**

### Session restore

On startup (desktop deployments), `restore_session()`:

1. Loads the linked `.mechbay` file when the database is empty but `documents.json` has a valid path
2. Prunes missing inventory paths and stale force file links
3. Clears dirty flags when on-disk files match the current database content

Linked paths and dirty state live in `%APPDATA%\MechBay\documents.json`. Sample/demo data is **not** loaded automatically; use **File → Load sample data…** or `uv run python -m app.seed`.

Legacy `/miniatures/export`, `/miniatures/import`, `/forces/import`, `/forces/<id>/export`, and `/lance-templates/export|import` URLs were removed; use the File menu instead.

Max upload size: 10 MB (`MAX_CONTENT_LENGTH` in `Config`).

## Preparing for a Second Campaign System (Aces)

Today's `Campaign`/`CampaignUnit`/`Contract`/`Sortie`/... models, the `campaigns`/`contracts` blueprints, and `campaign_service`/`contract_service`/`after_action_service` are all one ruleset (Chaos Campaign) wearing generic names. A second, different campaign system ("Aces") is planned. Before it arrives, worth deciding deliberately:

1. **Namespace the existing system now, while there's only one.** Renaming `Campaign` → `ChaosCampaign` (and its 12 related models) is a small, mechanical change today; it becomes a much bigger one once Aces exists alongside it and both are live in production data. Concretely: `app/models/chaos_campaign/` (or a `chaos_` prefix per file), tables renamed with a `chaos_campaign_` prefix or left as-is with a comment — but the Python class names should stop being the generic word `Campaign` before a second, differently-shaped `Campaign` needs to exist too.
2. **Group by domain, not by flat file list.** `app/models/` currently mixes inventory models and 13 campaign models in one flat directory, and `app/models/__init__.py` is a 25-line undifferentiated import list. Once Aces adds its own model set, a flat `models/` will be ~25-35 files with no visual grouping. Subpackages (`models/inventory/`, `models/chaos_campaign/`, `models/aces_campaign/`) — or at minimum a naming convention plus grouped `__init__.py` sections — make "which system owns this table" answerable at a glance.
3. **Decide the shared surface before building Aces, not during.** The natural shared layer is: `Miniature` (physical inventory) and `Force` (the thing you graduate *from*). Everything else Chaos Campaign has — warchest, contracts, sorties, damage/repair/rearm, pilot injuries — is ruleset-specific and should not be assumed reusable. Aces likely wants its own unit/pilot/session model shaped around its own rules, not `CampaignUnit`/`CampaignPilot` reused or subclassed. Trying to force both rulesets through one shared `Campaign` table (e.g. via a `campaign_type` discriminator column) will pull in Chaos-Campaign-only columns (`warchest_balance`, `reputation`, `scale`) that make no sense for Aces and vice versa — two separate top-level tables (`chaos_campaigns`, `aces_campaigns`) are simpler than one polymorphic one here.
4. **Split blueprints/services along the same line.** `campaigns.py` + `contracts.py` (981 lines) and `campaign_service.py` + `contract_service.py` + `after_action_service.py` (2,883 lines) are already large for a single ruleset. Renaming them to `chaos_campaigns.py` / `chaos_campaign_service.py` etc. now avoids a later choice between "cram Aces routes into the same file" and "do the rename later under time pressure while also shipping a feature."
5. **Give the top-level `Campaign` concept (whichever one) a `system`/`kind` marker only if a shared list view needs to enumerate both.** If the UI ever needs "show me all campaigns, Chaos or Aces, on one screen," that's a good reason for a thin shared read-model or a common interface — but don't build that abstraction speculatively; add it when the second system exists and that screen is actually needed.

None of this blocks current work — it's a suggestion to do the `Campaign` → `ChaosCampaign` rename (item 1) as a low-risk, high-value cleanup *before* Aces work starts, since it only gets more expensive later.

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
