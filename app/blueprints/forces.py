from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for

from ..services import force_service, lance_template_service

bp = Blueprint("forces", __name__, url_prefix="/forces")


@bp.route("")
def list_forces():
    """List all forces with active indicator."""
    forces = force_service.get_all_forces()
    active_force = force_service.get_active_force()
    return render_template("forces/list.html", forces=forces, active_force=active_force)


@bp.route("/create", methods=["POST"])
def create():
    """Create a new force."""
    name = request.form.get("name", "").strip()
    if not name:
        flash("Force name is required", "danger")
        return redirect(url_for("forces.list_forces"))

    force = force_service.create_force(name)
    flash(f"Force '{force.name}' created and activated", "success")
    return redirect(url_for("forces.detail", id=force.id))


@bp.route("/<int:id>")
def detail(id: int):  # noqa: A002
    """View force detail with lances."""
    force = force_service.get_force_by_id(id)
    if not force:
        flash("Force not found", "danger")
        return redirect(url_for("forces.list_forces"))

    templates = lance_template_service.get_all_templates()

    return render_template("forces/detail.html", force=force, templates=templates)


@bp.route("/<int:id>/activate", methods=["POST"])
def activate(id: int):  # noqa: A002
    """Activate a specific force."""
    force = force_service.switch_force(id)
    if force:
        flash(f"Force '{force.name}' activated", "success")
    else:
        flash("Force not found", "danger")
    return redirect(url_for("forces.list_forces"))


@bp.route("/<int:id>/rename", methods=["POST"])
def rename(id: int):  # noqa: A002
    """Rename a force."""
    data = request.get_json()
    new_name = data.get("name", "").strip()

    if not new_name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    force = force_service.rename_force(id, new_name)
    if force:
        return jsonify({"success": True, "name": force.name}), 200
    else:
        return jsonify({"success": False, "error": "Force not found"}), 404


@bp.route("/<int:id>/add-miniature", methods=["POST"])
def add_miniature(id: int):  # noqa: A002
    """Add a miniature to a lance (JSON API)."""
    data = request.get_json() or request.form
    miniature_id = data.get("miniature_id")
    lance_id = data.get("lance_id")

    if not miniature_id or not lance_id:
        return jsonify({"success": False, "error": "Missing parameters"}), 400

    result = force_service.add_miniature_to_lance(int(miniature_id), int(lance_id))

    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route("/<int:id>/remove-miniature", methods=["POST"])
def remove_miniature(id: int):  # noqa: A002
    """Remove a miniature from the force (JSON API)."""
    data = request.get_json() or request.form
    miniature_id = data.get("miniature_id")

    if not miniature_id:
        return jsonify({"success": False, "error": "Missing miniature_id"}), 400

    success = force_service.remove_miniature_from_force(int(miniature_id), id)

    if success:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"success": False, "error": "Miniature not found in force"}), 404


@bp.route("/<int:id>/lances/create", methods=["POST"])
def create_lance(id: int):  # noqa: A002
    """Create an empty lance in the force."""
    name = request.form.get("name", "").strip() or None

    lance = force_service.create_empty_lance(id, name)
    if lance:
        flash(f"Lance '{lance.name or 'Unnamed'}' created", "success")
    else:
        flash("Force not found", "danger")

    return redirect(url_for("forces.detail", id=id))


@bp.route("/<int:id>/lances/from-template", methods=["POST"])
def create_lance_from_template(id: int):  # noqa: A002
    """Create lance from template with miniature matching."""
    template_id = request.form.get("template_id")
    if not template_id:
        return jsonify({"success": False, "error": "Missing template_id"}), 400

    # Get currently assigned miniatures in this force
    assigned_ids = force_service.get_miniatures_in_force(id)

    # Match template to available miniatures
    match_result = lance_template_service.match_template_miniatures(
        int(template_id), exclude_ids=assigned_ids
    )

    # If all matched or user confirmed partial
    confirm = request.form.get("confirm") == "true"

    if match_result["missing"] and not confirm:
        # Return missing list for confirmation
        return jsonify(
            {
                "success": False,
                "needs_confirmation": True,
                "matched_count": len(match_result["matched"]),
                "missing": match_result["missing"],
                "template_name": match_result["template_name"],
            }
        ), 200

    # Create lance with matched miniatures
    lance_name = request.form.get("name") or match_result["template_name"]
    lance = force_service.create_empty_lance(id, lance_name)

    if not lance:
        return jsonify({"success": False, "error": "Force not found"}), 404

    # Add matched miniatures
    for idx, (pattern, mini_id, miniature) in enumerate(match_result["matched"]):
        force_service.add_miniature_to_lance(mini_id, lance.id, position=idx)

    flash(f"Lance '{lance_name}' created with {len(match_result['matched'])} miniatures", "success")

    if match_result["missing"]:
        flash(f"Missing: {', '.join(match_result['missing'])}", "warning")

    return jsonify({"success": True, "lance_id": lance.id}), 200


@bp.route("/<int:id>/lances/<int:lance_id>/delete", methods=["POST"])
def delete_lance(id: int, lance_id: int):  # noqa: A002
    """Delete a lance."""
    success = force_service.delete_lance(lance_id)
    if success:
        flash("Lance deleted", "info")
    else:
        flash("Lance not found", "danger")

    return redirect(url_for("forces.detail", id=id))


@bp.route("/<int:id>/lances/<int:lance_id>/rename", methods=["POST"])
def rename_lance(id: int, lance_id: int):  # noqa: A002
    """Rename a lance (JSON API)."""
    data = request.get_json() or request.form
    new_name = data.get("name", "").strip() or None

    from ..extensions import session_scope
    from ..models.lance import Lance

    with session_scope() as session:
        lance = session.get(Lance, lance_id)
        if not lance or lance.force_id != id:
            return jsonify({"success": False, "error": "Lance not found"}), 404

        lance.name = new_name
        session.flush()

        return jsonify({"success": True, "name": lance.name}), 200


@bp.route("/<int:id>/move-miniature", methods=["POST"])
def move_miniature(id: int):  # noqa: A002
    """Move miniature between lances (drag-drop handler, JSON API)."""
    data = request.get_json() or request.form
    miniature_id = data.get("miniature_id")
    target_lance_id = data.get("target_lance_id")
    position = data.get("position", 0)

    if not miniature_id or not target_lance_id:
        return jsonify({"success": False, "error": "Missing parameters"}), 400

    result = force_service.move_miniature_between_lances(
        int(miniature_id), int(target_lance_id), int(position)
    )

    return jsonify(result), 200 if result["success"] else 400


@bp.route("/<int:id>/export")
def export(id: int):  # noqa: A002
    """Export force to JSON file."""
    try:
        filepath = force_service.export_force_to_json(id)
        return send_file(
            BytesIO(filepath.read_bytes()),
            mimetype="application/json",
            as_attachment=True,
            download_name=filepath.name,
        )
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("forces.list_forces"))


@bp.route("/<int:id>/report")
def print_report(id: int):  # noqa: A002
    """Generate printable force report."""
    force = force_service.get_force_by_id(id)
    if not force:
        flash("Force not found", "danger")
        return redirect(url_for("forces.list_forces"))

    return render_template("forces/report.html", force=force, now=datetime.now())


@bp.route("/import", methods=["GET", "POST"])
def import_route():
    """Import force from JSON file."""
    if request.method == "POST":
        uploaded = request.files.get("file")
        if not uploaded or uploaded.filename == "":
            flash("No file selected", "warning")
            return redirect(url_for("forces.import_route"))

        temp_path = Path("_upload_force.json")
        uploaded.save(temp_path)
        try:
            result = force_service.import_force_from_json(str(temp_path))

            flash(
                f"Imported force '{result['force_name']}' with {result['imported_count']} miniatures",
                "success",
            )

            if result["missing_miniatures"]:
                flash(f"Missing miniatures: {', '.join(result['missing_miniatures'])}", "warning")

            return redirect(url_for("forces.detail", id=result["force_id"]))
        except Exception as exc:  # noqa: BLE001
            flash(f"Import failed: {exc}", "danger")
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return redirect(url_for("forces.import_route"))

    return render_template("forces/import.html")


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id: int):  # noqa: A002
    """Delete a force."""
    success = force_service.delete_force(id)
    if success:
        flash("Force deleted", "info")
    else:
        flash("Force not found", "danger")

    return redirect(url_for("forces.list_forces"))
