"""File menu routes for inventory projects and force documents."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import structlog
from flask import Blueprint, flash, jsonify, redirect, request, url_for

from ..native_dialog import native_dialogs_enabled, pick_file_path
from ..services import document_service, force_service, inventory_project_service
from ..services.session_restore_service import inventory_has_data

logger = structlog.get_logger()

bp = Blueprint("files", __name__, url_prefix="/files")


def _json_or_redirect(success: bool, payload: dict, *, redirect_to: str):
    """JSON for AJAX file actions; may return needs_client_dialog or client_saved."""
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        status = 200 if success else 400
        return jsonify(payload), status
    if success:
        flash(payload.get("message", "Done"), "success")
        if payload.get("warning"):
            flash(payload["warning"], "warning")
    else:
        flash(payload.get("error", "Request failed"), "danger")
    return redirect(redirect_to)


def _missing_force_warning(result: dict) -> str | None:
    missing = result.get("missing_miniatures") or []
    if not missing:
        return None
    labels = []
    for item in missing[:5]:
        if isinstance(item, dict):
            labels.append(
                f"{item.get('prefix', '')} {item.get('chassis', '')}".strip()
                or f"{item.get('series')}-{item.get('unique_id')}"
            )
        else:
            labels.append(f"{item[0]}-{item[1]}")
    suffix = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
    return f"{len(missing)} miniature slot(s) not found in inventory: {', '.join(labels)}{suffix}"


@bp.route("/status")
def file_status():
    status = document_service.get_status()
    status["native_dialogs"] = native_dialogs_enabled()
    return jsonify(status)


@bp.route("/inventory/export")
def inventory_export():
    """Return current inventory project JSON for browser save dialogs."""
    payload = inventory_project_service.build_project_data()
    return jsonify(payload)


@bp.route("/inventory/new", methods=["POST"])
def inventory_new():
    data = request.get_json(silent=True) or request.form
    if document_service.load_state().inventory_dirty and data.get("confirm") != "1":
        return _json_or_redirect(
            False,
            {"error": "Unsaved inventory changes", "needs_confirm": True},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    inventory_project_service.new_inventory_project()
    return _json_or_redirect(
        True,
        {"message": "New inventory created", "status": document_service.get_status()},
        redirect_to=url_for("miniatures.list_miniatures"),
    )


@bp.route("/inventory/sample-data", methods=["POST"])
def inventory_sample_data():
    data = request.get_json(silent=True) or request.form
    if inventory_has_data() and data.get("confirm") != "1":
        return _json_or_redirect(
            False,
            {
                "error": "Existing inventory data",
                "needs_confirm": True,
                "confirm_message": (
                    "Your inventory already has miniatures, templates, or forces. "
                    "Loading sample data will add example miniatures and lance templates "
                    "(existing entries are kept; duplicates are skipped). Continue?"
                ),
            },
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    created = inventory_project_service.load_sample_data()
    return _json_or_redirect(
        True,
        {
            "message": f"Loaded sample data ({created} new records)",
            "status": document_service.get_status(),
        },
        redirect_to=url_for("miniatures.list_miniatures"),
    )


@bp.route("/inventory/open", methods=["POST"])
def inventory_open():
    data = request.get_json(silent=True) or request.form
    path = data.get("path")
    if not path:
        if not native_dialogs_enabled():
            return _json_or_redirect(
                True,
                {
                    "needs_client_dialog": True,
                    "mode": "open",
                    "kind": "inventory",
                },
                redirect_to=url_for("miniatures.list_miniatures"),
            )
        path = pick_file_path("open", "inventory")

    if not path:
        return _json_or_redirect(
            False,
            {"error": "No file selected", "cancelled": True},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    if document_service.load_state().inventory_dirty and data.get("confirm") != "1":
        return _json_or_redirect(
            False,
            {"error": "Unsaved inventory changes", "needs_confirm": True},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    try:
        result = inventory_project_service.load_project_from_path(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("inventory_open_failed", exc_info=True)
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    return _json_or_redirect(
        True,
        {
            "message": (
                f"Opened inventory ({result['miniatures']} miniatures, "
                f"{result['templates']} templates). All forces were cleared."
            ),
            "status": document_service.get_status(),
            "path": path,
        },
        redirect_to=url_for("miniatures.list_miniatures"),
    )


@bp.route("/inventory/save", methods=["POST"])
def inventory_save():
    state = document_service.load_state()
    if not state.inventory_path:
        return inventory_save_as()

    try:
        inventory_project_service.save_project_to_path(state.inventory_path)
    except OSError as exc:
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    return _json_or_redirect(
        True,
        {
            "message": f"Saved inventory to {Path(state.inventory_path).name}",
            "status": document_service.get_status(),
        },
        redirect_to=url_for("miniatures.list_miniatures"),
    )


@bp.route("/inventory/save-as", methods=["POST"])
def inventory_save_as():
    data = request.get_json(silent=True) or request.form
    path = data.get("path")
    if data.get("client_saved") and path:
        document_service.set_inventory_path(path)
        document_service.clear_inventory_dirty()
        return _json_or_redirect(
            True,
            {
                "message": f"Saved inventory to {Path(path).name}",
                "status": document_service.get_status(),
            },
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    if not path:
        if not native_dialogs_enabled():
            default_name = Path(
                document_service.load_state().inventory_path or "MyCollection"
            ).stem
            return _json_or_redirect(
                True,
                {
                    "needs_client_dialog": True,
                    "mode": "save",
                    "kind": "inventory",
                    "default_name": f"{default_name}.mechbay",
                },
                redirect_to=url_for("miniatures.list_miniatures"),
            )
        default_name = Path(document_service.load_state().inventory_path or "MyCollection").stem
        path = pick_file_path("save", "inventory", default_name=f"{default_name}.mechbay")

    if not path:
        return _json_or_redirect(
            False,
            {"error": "No file selected", "cancelled": True},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    try:
        inventory_project_service.save_project_to_path(path)
    except OSError as exc:
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    return _json_or_redirect(
        True,
        {
            "message": f"Saved inventory to {Path(path).name}",
            "status": document_service.get_status(),
        },
        redirect_to=url_for("miniatures.list_miniatures"),
    )


@bp.route("/force/<int:force_id>/export")
def force_export(force_id: int):
    """Return force JSON for browser save dialogs."""
    try:
        json_string, _ = force_service.export_force_to_json(force_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return json_string, 200, {"Content-Type": "application/json"}


@bp.route("/force/open", methods=["POST"])
def force_open():
    data = request.get_json(silent=True) or request.form
    path = data.get("path")
    if not path:
        if not native_dialogs_enabled():
            return _json_or_redirect(
                True,
                {
                    "needs_client_dialog": True,
                    "mode": "open",
                    "kind": "force",
                },
                redirect_to=url_for("forces.list_forces"),
            )
        path = pick_file_path("open", "force")

    if not path:
        return _json_or_redirect(
            False,
            {"error": "No file selected", "cancelled": True},
            redirect_to=url_for("forces.list_forces"),
        )

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        result = force_service.import_force_from_data(payload)
        force_service.save_force_to_path(result["force_id"], path)
        document_service.clear_force_dirty(result["force_id"])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("force_open_failed", exc_info=True)
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("forces.list_forces"),
        )

    warning = _missing_force_warning(result)
    return _json_or_redirect(
        True,
        {
            "message": f"Opened force '{result['force_name']}'",
            "warning": warning,
            "force_id": result["force_id"],
            "status": document_service.get_status(),
        },
        redirect_to=url_for("forces.detail", id=result["force_id"]),
    )


@bp.route("/force/<int:force_id>/save", methods=["POST"])
def force_save(force_id: int):
    state = document_service.load_state()
    path = state.force_paths.get(str(force_id))
    if not path:
        return force_save_as(force_id)

    try:
        force_service.save_force_to_path(force_id, path)
    except (OSError, ValueError) as exc:
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("forces.detail", id=force_id),
        )

    return _json_or_redirect(
        True,
        {"message": f"Saved force to {Path(path).name}", "status": document_service.get_status()},
        redirect_to=url_for("forces.detail", id=force_id),
    )


@bp.route("/force/<int:force_id>/save-as", methods=["POST"])
def force_save_as(force_id: int):
    data = request.get_json(silent=True) or request.form
    force = force_service.get_force_by_id(force_id)
    if not force:
        return _json_or_redirect(
            False,
            {"error": "Force not found"},
            redirect_to=url_for("forces.list_forces"),
        )

    path = data.get("path")
    if data.get("client_saved") and path:
        document_service.set_force_path(force_id, path)
        document_service.clear_force_dirty(force_id)
        return _json_or_redirect(
            True,
            {
                "message": f"Saved force to {Path(path).name}",
                "status": document_service.get_status(),
            },
            redirect_to=url_for("forces.detail", id=force_id),
        )

    if not path:
        if not native_dialogs_enabled():
            safe = "".join(
                c if c.isalnum() or c in ("-", "_") else "_" for c in force.name
            )
            return _json_or_redirect(
                True,
                {
                    "needs_client_dialog": True,
                    "mode": "save",
                    "kind": "force",
                    "force_id": force_id,
                    "default_name": f"{safe}.mbforce",
                },
                redirect_to=url_for("forces.detail", id=force_id),
            )
        safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in force.name)
        path = pick_file_path("save", "force", default_name=f"{safe}.mbforce")

    if not path:
        return _json_or_redirect(
            False,
            {"error": "No file selected", "cancelled": True},
            redirect_to=url_for("forces.detail", id=force_id),
        )

    try:
        force_service.save_force_to_path(force_id, path)
    except (OSError, ValueError) as exc:
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("forces.detail", id=force_id),
        )

    return _json_or_redirect(
        True,
        {"message": f"Saved force to {Path(path).name}", "status": document_service.get_status()},
        redirect_to=url_for("forces.detail", id=force_id),
    )


@bp.route("/upload/inventory", methods=["POST"])
def upload_inventory():
    """Browser fallback: open inventory from uploaded .mechbay file."""
    uploaded = request.files.get("file")
    if not uploaded or uploaded.filename == "":
        return _json_or_redirect(
            False,
            {"error": "No file selected"},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    if document_service.load_state().inventory_dirty and request.form.get("confirm") != "1":
        return _json_or_redirect(
            False,
            {"error": "Unsaved inventory changes", "needs_confirm": True},
            redirect_to=url_for("miniatures.list_miniatures"),
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mechbay", delete=False) as tmp:
            tmp_path = tmp.name
            uploaded.save(tmp_path)
        result = inventory_project_service.load_project_from_path(tmp_path)
        document_service.set_inventory_path(uploaded.filename)
        document_service.clear_inventory_dirty()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("miniatures.list_miniatures"),
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    return _json_or_redirect(
        True,
        {
            "message": (f"Opened inventory ({result['miniatures']} miniatures). Forces cleared."),
            "status": document_service.get_status(),
        },
        redirect_to=url_for("miniatures.list_miniatures"),
    )


@bp.route("/upload/force", methods=["POST"])
def upload_force():
    """Browser fallback: open force from uploaded .mbforce file."""
    uploaded = request.files.get("file")
    if not uploaded or uploaded.filename == "":
        return _json_or_redirect(
            False,
            {"error": "No file selected"},
            redirect_to=url_for("forces.list_forces"),
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mbforce", delete=False) as tmp:
            tmp_path = tmp.name
            uploaded.save(tmp_path)
        payload = json.loads(Path(tmp_path).read_text(encoding="utf-8"))
        result = force_service.import_force_from_data(payload)
        document_service.set_force_path(result["force_id"], uploaded.filename)
        document_service.clear_force_dirty(result["force_id"])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _json_or_redirect(
            False,
            {"error": str(exc)},
            redirect_to=url_for("forces.list_forces"),
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    warning = _missing_force_warning(result)
    return _json_or_redirect(
        True,
        {
            "message": f"Opened force '{result['force_name']}'",
            "warning": warning,
            "force_id": result["force_id"],
            "status": document_service.get_status(),
        },
        redirect_to=url_for("forces.detail", id=result["force_id"]),
    )
