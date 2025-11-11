from __future__ import annotations

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

from ..services.miniature_service import (
    add_miniature,
    delete_miniature,
    export_to_json,
    get_all_miniatures,
    import_from_json,
    update_miniature,
)

bp = Blueprint("miniatures", __name__, url_prefix="/miniatures")


@bp.route("")
def list_miniatures():
    q = request.args.get("q")
    sort = request.args.get("sort")
    direction = request.args.get("direction")
    minis = get_all_miniatures(q, sort=sort, direction=direction)
    return render_template(
        "miniatures/list.html",
        miniatures=minis,
        query=q,
        sort=sort,
        direction=direction,
    )


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        form = request.form
        unique_id = form.get("unique_id")
        data = {
            "unique_id": unique_id,
            "prefix": form.get("prefix"),
            "chassis": form.get("chassis"),
            "type": form.get("type"),
            "status": form.get("status"),
            "tray_id": form.get("tray_id"),
            "notes": form.get("notes"),
        }
        # Prevent duplicate unique_id user mistake
        existing = next((m for m in get_all_miniatures() if m.unique_id == unique_id), None)
        if existing:
            flash("Unique ID already exists", "danger")
        else:
            add_miniature(data)
            flash("Miniature added", "success")
            return redirect(url_for("miniatures.list_miniatures"))
    return render_template("miniatures/add.html")


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
        data = {
            "unique_id": form.get("unique_id"),
            "prefix": form.get("prefix"),
            "chassis": form.get("chassis"),
            "type": form.get("type"),
            "status": form.get("status"),
            "tray_id": form.get("tray_id"),
            "notes": form.get("notes"),
        }
        update_miniature(id, data)
        flash("Miniature updated", "success")
        return redirect(url_for("miniatures.list_miniatures"))
    return render_template("miniatures/edit.html", mini=mini)


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id: int):  # noqa: A002
    if delete_miniature(id):
        flash("Miniature deleted", "info")
    else:
        flash("Miniature not found", "warning")
    return redirect(url_for("miniatures.list_miniatures"))


@bp.route("/export")
def export():
    temp_path = Path("miniatures_export.json")
    export_to_json(str(temp_path))
    # Serve as attachment
    return send_file(
        BytesIO(temp_path.read_bytes()),
        mimetype="application/json",
        as_attachment=True,
        download_name="miniatures.json",
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
