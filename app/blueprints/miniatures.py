from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from ..services import force_service
from ..services.miniature_service import (
    add_miniature,
    delete_miniature,
    export_to_json,
    get_all_miniatures,
    get_distinct_factions,
    get_next_unique_id,
    import_from_json,
    update_miniature,
)

bp = Blueprint("miniatures", __name__, url_prefix="/miniatures")


@bp.route("")
def list_miniatures():
    q = request.args.get("q")
    sort = request.args.get("sort")
    direction = request.args.get("direction")
    series_filter = request.args.get("series", "All")
    faction_filter = request.args.get("faction", "All")

    # Get available factions for filter UI
    factions = get_distinct_factions()

    minis = get_all_miniatures(
        q,
        sort=sort,
        direction=direction,
        series_filter=series_filter,
        faction_filter=faction_filter,
    )

    # Empty filter fallback: if filtered results are empty but filters are active,
    # reset to "All" and show all miniatures to avoid confusion
    if not minis and (series_filter != "All" or faction_filter != "All"):
        flash("Selected filter returned no results, showing all miniatures", "info")
        series_filter = "All"
        faction_filter = "All"
        minis = get_all_miniatures(
            q,
            sort=sort,
            direction=direction,
            series_filter="All",
            faction_filter="All",
        )

    # Get active force info for UI
    active_force = force_service.get_active_force()
    assigned_miniature_ids = set()
    lances = []

    if active_force:
        assigned_miniature_ids = force_service.get_miniatures_in_force(active_force.id)
        lances = active_force.lances

    return render_template(
        "miniatures/list.html",
        miniatures=minis,
        query=q,
        sort=sort,
        direction=direction,
        series_filter=series_filter,
        faction_filter=faction_filter,
        factions=factions,
        active_force=active_force,
        assigned_miniature_ids=assigned_miniature_ids,
        lances=lances,
    )


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        form = request.form
        unique_id_raw = form.get("unique_id")
        try:
            unique_id = int(unique_id_raw)
        except (TypeError, ValueError):
            flash("Unique ID must be an integer", "danger")
            return redirect(url_for("miniatures.add"))

        series = form.get("series", "A")
        if not series:
            series = "A"

        data = {
            "series": series,
            "unique_id": unique_id,
            "prefix": form.get("prefix"),
            "chassis": form.get("chassis"),
            "type": form.get("type"),
            "faction": form.get("faction"),
            "status": form.get("status"),
            "tray_id": form.get("tray_id"),
            "notes": form.get("notes"),
        }
        # Prevent duplicate (series, unique_id) combination
        from sqlalchemy import and_

        from ..extensions import session_scope
        from ..models.miniature import Miniature

        with session_scope() as session:
            existing = (
                session.query(Miniature)
                .filter(and_(Miniature.series == series, Miniature.unique_id == unique_id))
                .first()
            )
            if existing:
                # Calculate next available unique_id in this series
                next_unique = get_next_unique_id(series)

                # Preserve all form fields and suggest next ID
                prefill = {
                    "series": series,
                    "unique_id": next_unique,
                    "prefix": form.get("prefix"),
                    "chassis": form.get("chassis"),
                    "type": form.get("type"),
                    "faction": form.get("faction"),
                    "status": form.get("status"),
                    "tray_id": form.get("tray_id"),
                    "notes": form.get("notes"),
                }
                flash(
                    f"Unique ID {unique_id} already exists in Series {series}. Suggested next ID: {next_unique}",
                    "danger",
                )
                available_factions = get_distinct_factions()
                return render_template(
                    "miniatures/add.html", prefill=prefill, available_factions=available_factions
                )

        add_miniature(data)
        flash("Miniature added", "success")

        # Preserve filter state from hidden form fields
        return_params = {}
        if form.get("return_series"):
            return_params["series"] = form.get("return_series")
        if form.get("return_faction"):
            return_params["faction"] = form.get("return_faction")
        if form.get("return_q"):
            return_params["q"] = form.get("return_q")
        if form.get("return_sort"):
            return_params["sort"] = form.get("return_sort")
        if form.get("return_direction"):
            return_params["direction"] = form.get("return_direction")

        return redirect(url_for("miniatures.list_miniatures", **return_params))

    # Calculate next available unique_id for default series A
    next_id = get_next_unique_id("A")
    available_factions = get_distinct_factions()

    # Capture filter params to preserve state
    filter_params = {
        "series": request.args.get("series", "All"),
        "faction": request.args.get("faction", "All"),
        "q": request.args.get("q", ""),
        "sort": request.args.get("sort", ""),
        "direction": request.args.get("direction", ""),
    }

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

    # Capture filter params to preserve state
    filter_params = {
        "series": request.args.get("series", "All"),
        "faction": request.args.get("faction", "All"),
        "q": request.args.get("q", ""),
        "sort": request.args.get("sort", ""),
        "direction": request.args.get("direction", ""),
    }

    return render_template(
        "miniatures/add.html",
        prefill=prefill,
        duplicate_of=mini,
        available_factions=available_factions,
        filter_params=filter_params,
    )


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id: int):  # noqa: A002
    from ..services.miniature_service import get_all_miniatures

    # Simple lookup; could optimize with direct get
    mini = next((m for m in get_all_miniatures() if m.id == id), None)
    if not mini:
        flash("Miniature not found", "danger")
        return redirect(url_for("miniatures.list_miniatures"))
    if request.method == "POST":
        form = request.form
        unique_id_raw = form.get("unique_id")
        try:
            unique_id = int(unique_id_raw)
        except (TypeError, ValueError):
            flash("Unique ID must be an integer", "danger")
            return redirect(url_for("miniatures.edit", id=id))

        series = form.get("series", "A")
        if not series:
            series = "A"

        data = {
            "series": series,
            "unique_id": unique_id,
            "prefix": form.get("prefix"),
            "chassis": form.get("chassis"),
            "type": form.get("type"),
            "faction": form.get("faction"),
            "status": form.get("status"),
            "tray_id": form.get("tray_id"),
            "notes": form.get("notes"),
        }
        update_miniature(id, data)
        flash("Miniature updated", "success")

        # Preserve filter state from hidden form fields
        return_params = {}
        if form.get("return_series"):
            return_params["series"] = form.get("return_series")
        if form.get("return_faction"):
            return_params["faction"] = form.get("return_faction")
        if form.get("return_q"):
            return_params["q"] = form.get("return_q")
        if form.get("return_sort"):
            return_params["sort"] = form.get("return_sort")
        if form.get("return_direction"):
            return_params["direction"] = form.get("return_direction")

        return redirect(url_for("miniatures.list_miniatures", **return_params))

    available_factions = get_distinct_factions()

    # Capture filter params to preserve state
    filter_params = {
        "series": request.args.get("series", "All"),
        "faction": request.args.get("faction", "All"),
        "q": request.args.get("q", ""),
        "sort": request.args.get("sort", ""),
        "direction": request.args.get("direction", ""),
    }

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
        flash("Miniature deleted", "info")
    else:
        flash("Miniature not found", "warning")

    # Preserve filter state from query parameters
    return_params = {}
    if request.args.get("series"):
        return_params["series"] = request.args.get("series")
    if request.args.get("faction"):
        return_params["faction"] = request.args.get("faction")
    if request.args.get("q"):
        return_params["q"] = request.args.get("q")
    if request.args.get("sort"):
        return_params["sort"] = request.args.get("sort")
    if request.args.get("direction"):
        return_params["direction"] = request.args.get("direction")

    return redirect(url_for("miniatures.list_miniatures", **return_params))


@bp.route("/export")
def export():
    # Generate JSON in memory
    json_string = export_to_json()
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    download_filename = f"Miniature_Inventory_{timestamp}.json"
    # Serve as attachment
    return send_file(
        BytesIO(json_string.encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name=download_filename,
    )


@bp.route("/import", methods=["GET", "POST"])
def import_route():
    if request.method == "POST":
        uploaded = request.files.get("file")
        merge_flag = request.form.get("merge") == "on"
        if not uploaded or uploaded.filename == "":
            flash("No file selected", "warning")
            return redirect(url_for("miniatures.import_route"))

        temp_path = Path("_upload.json")
        uploaded.save(temp_path)
        try:
            count = import_from_json(str(temp_path), merge=merge_flag)
            flash(f"Imported {count} miniatures", "success")
        except Exception as exc:  # noqa: BLE001
            flash(f"Import failed: {exc}", "danger")
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return redirect(url_for("miniatures.list_miniatures"))
    return render_template("miniatures/import.html")
