from __future__ import annotations

import structlog
from flask import (
    Blueprint,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from ..services import force_service
from ..services.miniature_service import (
    add_miniature,
    bulk_update_miniatures,
    delete_miniature,
    get_all_miniatures,
    get_distinct_factions,
    get_miniature_by_id,
    get_next_unique_id,
    update_miniature,
)

logger = structlog.get_logger()

bp = Blueprint("miniatures", __name__, url_prefix="/miniatures")

_FILTER_KEYS = ("series", "faction", "q", "sort", "direction")
_FILTER_DEFAULTS = {"series": "All", "faction": "All", "q": "", "sort": "", "direction": ""}


def _filter_params_with_defaults(source=None, prefix=""):
    """Extract filter params with defaults for template re-rendering."""
    src = source or request.args
    return {k: src.get(f"{prefix}{k}", _FILTER_DEFAULTS[k]) for k in _FILTER_KEYS}


def _preserve_filters(source, prefix="return_"):
    """Extract non-empty filter params from form data for redirect URLs."""
    return {k: v for k in _FILTER_KEYS if (v := source.get(f"{prefix}{k}"))}


def _duplicate_unique_id_error(
    series: str, unique_id: int, *, exclude_id: int | None = None
) -> str | None:
    """Return an error message when series+unique_id is taken by another record."""
    from sqlalchemy import and_

    from ..extensions import session_scope
    from ..models.miniature import Miniature

    with session_scope() as session:
        query = session.query(Miniature).filter(
            and_(Miniature.series == series, Miniature.unique_id == unique_id)
        )
        if exclude_id is not None:
            query = query.filter(Miniature.id != exclude_id)
        if query.first():
            next_unique = get_next_unique_id(series)
            return (
                f"ID {unique_id} already exists in Series {series}. "
                f"Next available: {next_unique}"
            )
    return None


@bp.route("")
def list_miniatures():
    q = request.args.get("q")
    sort = request.args.get("sort")
    direction = request.args.get("direction")
    series_filter = request.args.get("series", "All")
    faction_filter = request.args.get("faction", "All")
    VALID_PAGE_SIZES = [20, 30, 40, 50, 100]
    per_page_raw = request.args.get("per_page") or request.cookies.get("mechbay_per_page")
    try:
        per_page = int(per_page_raw) if per_page_raw else 50
    except (TypeError, ValueError):
        per_page = 50
    if per_page not in VALID_PAGE_SIZES:
        per_page = 50
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    # Get available factions for filter UI
    factions = get_distinct_factions()

    result = get_all_miniatures(
        q,
        sort=sort,
        direction=direction,
        series_filter=series_filter,
        faction_filter=faction_filter,
        page=page,
        per_page=per_page,
    )
    minis, total_count = result  # type: ignore[misc]
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    # Clamp page to valid range. If the original page was out of bounds the query
    # returned an empty offset slice — re-run it against the clamped page so the
    # rendered rows and pagination stay consistent.
    if page > total_pages:
        page = total_pages
        result = get_all_miniatures(
            q,
            sort=sort,
            direction=direction,
            series_filter=series_filter,
            faction_filter=faction_filter,
            page=page,
            per_page=per_page,
        )
        minis, _ = result  # type: ignore[misc]

    # Show message if filtered results are empty
    if not minis and (series_filter != "All" or faction_filter != "All" or q):
        flash("No records found matching filter", "info")

    # Get active force info for UI
    active_force = force_service.get_active_force()
    force_assignments: dict[int, force_service.ForceMiniatureAssignment] = {}
    lances = []

    if active_force:
        force_assignments = force_service.get_force_miniature_assignments(active_force.id)
        lances = active_force.lances

    building_inventory_faction = (
        active_force.inventory_faction if active_force and active_force.inventory_faction else None
    )

    show_empty_inventory_prompt = (
        total_count == 0
        and series_filter == "All"
        and faction_filter == "All"
        and not q
    )

    resp = make_response(
        render_template(
            "miniatures/list.html",
            miniatures=minis,
            query=q,
            sort=sort,
            direction=direction,
            series_filter=series_filter,
            faction_filter=faction_filter,
            factions=factions,
            active_force=active_force,
            building_inventory_faction=building_inventory_faction,
            force_assignments=force_assignments,
            lances=lances,
            page=page,
            per_page=per_page,
            total_count=total_count,
            total_pages=total_pages,
            valid_page_sizes=VALID_PAGE_SIZES,
            show_empty_inventory_prompt=show_empty_inventory_prompt,
        )
    )
    resp.set_cookie(
        "mechbay_per_page", str(per_page), max_age=60 * 60 * 24 * 365, samesite="Lax", httponly=True
    )
    return resp


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        form = request.form
        errors: dict[str, str] = {}

        unique_id_raw = form.get("unique_id", "").strip()
        try:
            unique_id = int(unique_id_raw)
            if unique_id < 1:
                errors["unique_id"] = "Unique ID must be a positive integer"
        except (TypeError, ValueError):
            unique_id = None
            errors["unique_id"] = "Unique ID must be an integer"

        series = form.get("series", "A") or "A"
        prefix = form.get("prefix", "").strip()
        chassis = form.get("chassis", "").strip()
        mini_type = form.get("type", "").strip()

        if not prefix:
            errors["prefix"] = "Prefix is required"
        if not chassis:
            errors["chassis"] = "Chassis is required"
        if not mini_type:
            errors["type"] = "Type is required"

        if unique_id is not None and "unique_id" not in errors:
            if dup := _duplicate_unique_id_error(series, unique_id):
                errors["unique_id"] = dup

        if errors:
            prefill = {
                "series": series,
                "unique_id": unique_id_raw,
                "prefix": prefix,
                "chassis": chassis,
                "type": mini_type,
                "faction": form.get("faction"),
                "status": form.get("status"),
                "tray_id": form.get("tray_id"),
                "notes": form.get("notes"),
            }
            filter_params = _filter_params_with_defaults(form, prefix="return_")
            available_factions = get_distinct_factions()
            return render_template(
                "miniatures/add.html",
                prefill=prefill,
                errors=errors,
                available_factions=available_factions,
                filter_params=filter_params,
            )

        data = {
            "series": series,
            "unique_id": unique_id,
            "prefix": prefix,
            "chassis": chassis,
            "type": mini_type,
            "faction": form.get("faction"),
            "status": form.get("status"),
            "tray_id": form.get("tray_id"),
            "notes": form.get("notes"),
        }
        add_miniature(data)
        flash("Miniature added", "success")

        return_params = _preserve_filters(form)

        return redirect(url_for("miniatures.list_miniatures", **return_params))

    # Calculate next available unique_id for default series A
    next_id = get_next_unique_id("A")
    available_factions = get_distinct_factions()

    filter_params = _filter_params_with_defaults()

    return render_template(
        "miniatures/add.html",
        next_id=next_id,
        available_factions=available_factions,
        filter_params=filter_params,
    )


@bp.route("/next-id/<series>")
def next_id_for_series(series: str):
    """API endpoint to get the next available unique_id for a given series."""
    from flask import jsonify

    next_id = get_next_unique_id(series)
    return jsonify({"next_id": next_id})


@bp.route("/<int:id>/duplicate")
def duplicate(id: int):  # noqa: A002
    """Open the add form with fields prefilled from an existing miniature.

    The unique_id will be set to the next available integer within the same series
    (max existing unique_id for that series + 1).
    """

    from ..extensions import session_scope
    from ..models.miniature import Miniature

    with session_scope() as session:
        mini = session.get(Miniature, id)
        if not mini:
            flash("Miniature not found", "danger")
            return redirect(url_for("miniatures.list_miniatures"))

        # Compute next unique_id within same series
        series = mini.series
        session.expunge(mini)  # Detach before closing session

    # Calculate next available unique_id (outside session)
    next_unique = get_next_unique_id(series)

    prefill = {
        "series": mini.series,
        "unique_id": next_unique,
        "prefix": mini.prefix,
        "chassis": mini.chassis,
        "type": mini.type,
        "faction": mini.faction,
        "status": mini.status,
        "tray_id": mini.tray_id,
        "notes": mini.notes,
    }
    flash(f"Duplicating {mini.prefix} {mini.chassis} into new entry", "info")
    available_factions = get_distinct_factions()

    filter_params = _filter_params_with_defaults()

    return render_template(
        "miniatures/add.html",
        prefill=prefill,
        duplicate_of=mini,
        available_factions=available_factions,
        filter_params=filter_params,
    )


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id: int):  # noqa: A002
    mini = get_miniature_by_id(id)
    if not mini:
        flash("Miniature not found", "danger")
        return redirect(url_for("miniatures.list_miniatures", **_filter_params_with_defaults()))
    if request.method == "POST":
        form = request.form
        errors: dict[str, str] = {}

        unique_id_raw = form.get("unique_id", "").strip()
        try:
            unique_id = int(unique_id_raw)
            if unique_id < 1:
                errors["unique_id"] = "Unique ID must be a positive integer"
        except (TypeError, ValueError):
            unique_id = None
            errors["unique_id"] = "Unique ID must be an integer"

        series = form.get("series", "A") or "A"
        prefix = form.get("prefix", "").strip()
        chassis = form.get("chassis", "").strip()
        mini_type = form.get("type", "").strip()

        if not prefix:
            errors["prefix"] = "Prefix is required"
        if not chassis:
            errors["chassis"] = "Chassis is required"
        if not mini_type:
            errors["type"] = "Type is required"

        if unique_id is not None and "unique_id" not in errors:
            if dup := _duplicate_unique_id_error(series, unique_id, exclude_id=id):
                errors["unique_id"] = dup

        if errors:
            filter_params = _filter_params_with_defaults(form, prefix="return_")
            # Merge form values into mini object for re-display
            mini.series = series
            mini.unique_id = unique_id_raw  # type: ignore[assignment]
            mini.prefix = prefix
            mini.chassis = chassis
            mini.type = mini_type
            mini.faction = form.get("faction")
            mini.status = form.get("status")
            mini.tray_id = form.get("tray_id")
            mini.notes = form.get("notes")
            available_factions = get_distinct_factions()
            return render_template(
                "miniatures/edit.html",
                mini=mini,
                errors=errors,
                available_factions=available_factions,
                filter_params=filter_params,
            )

        data = {
            "series": series,
            "unique_id": unique_id,
            "prefix": prefix,
            "chassis": chassis,
            "type": mini_type,
            "faction": form.get("faction"),
            "status": form.get("status"),
            "tray_id": form.get("tray_id"),
            "notes": form.get("notes"),
        }
        update_miniature(id, data)
        flash("Miniature updated", "success")

        return_params = _preserve_filters(form)

        return redirect(url_for("miniatures.list_miniatures", **return_params))

    available_factions = get_distinct_factions()

    filter_params = _filter_params_with_defaults()

    return render_template(
        "miniatures/edit.html",
        mini=mini,
        available_factions=available_factions,
        filter_params=filter_params,
    )


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id: int):  # noqa: A002
    # Check if miniature is in any forces
    from ..extensions import session_scope
    from ..models.force import Force
    from ..models.force_miniature import ForceMiniature
    from ..models.lance import Lance

    with session_scope() as session:
        force_assignments = (
            session.query(Force.name, Lance.name)
            .join(Lance)
            .join(ForceMiniature)
            .filter(ForceMiniature.miniature_id == id)
            .all()
        )

        if force_assignments:
            force_names = ", ".join([f"{f[0]}" for f in force_assignments])
            flash(f"Warning: Miniature removed from forces: {force_names}", "warning")

    if delete_miniature(id):
        logger.info("miniature_deleted_via_ui", miniature_id=id)
        flash("Miniature deleted", "info")
    else:
        flash("Miniature not found", "warning")

    return_params = _preserve_filters(request.args, prefix="")

    return redirect(url_for("miniatures.list_miniatures", **return_params))


@bp.route("/bulk-action", methods=["POST"])
def bulk_action():
    """Apply a field update to a set of selected miniatures.

    Expects JSON body: ``{"action": "set_status"|"set_faction", "ids": [...], "value": "..."}``.
    """
    from flask import jsonify

    data = request.get_json(silent=True)
    if not data:
        logger.warning("bulk_action_bad_request", reason="missing action or ids")
        return jsonify({"success": False, "error": "No data"}), 400

    action = data.get("action", "")
    ids = data.get("ids", [])
    value = data.get("value", "")

    if not ids or not isinstance(ids, list):
        logger.warning("bulk_action_bad_request", reason="missing action or ids")
        return jsonify({"success": False, "error": "No miniatures selected"}), 400

    field_map = {"set_status": "status", "set_faction": "faction"}
    if action not in field_map:
        return jsonify({"success": False, "error": "Unknown action"}), 400

    try:
        count = bulk_update_miniatures([int(i) for i in ids], field_map[action], value)
    except (ValueError, TypeError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    flash(f"Updated {count} miniature(s)", "success")
    return jsonify({"success": True, "updated": count})
