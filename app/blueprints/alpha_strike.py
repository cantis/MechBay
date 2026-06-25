from __future__ import annotations

import structlog
from flask import Blueprint, flash, jsonify, redirect, request, url_for

from ..services import alpha_strike_service, force_service, mul_service

logger = structlog.get_logger()

bp = Blueprint("alpha_strike", __name__, url_prefix="/forces")


def _force_or_404(force_id: int):
    force = force_service.get_force_by_id(force_id)
    if not force:
        return None
    return force


@bp.route("/<int:force_id>/alpha-strike/enable", methods=["POST"])
def enable(force_id: int):
    """Enable Alpha Strike mode with era, faction, and optional point budget."""
    force = _force_or_404(force_id)
    if not force:
        flash("Force not found", "danger")
        return redirect(url_for("forces.list_forces"))

    try:
        faction_id = int(request.form.get("mul_faction_id", ""))
        era_id = int(request.form.get("mul_era_id", ""))
    except (TypeError, ValueError):
        flash("Faction and era are required", "danger")
        return redirect(url_for("forces.detail", id=force_id))

    budget_raw = request.form.get("point_budget", "").strip()
    point_budget = None
    if budget_raw:
        try:
            point_budget = int(budget_raw)
            if point_budget < 1:
                raise ValueError
        except ValueError:
            flash("Point budget must be a positive integer", "danger")
            return redirect(url_for("forces.detail", id=force_id))

    try:
        alpha_strike_service.enable_alpha_strike(
            force_id,
            mul_faction_id=faction_id,
            mul_era_id=era_id,
            point_budget=point_budget,
        )
        flash("Alpha Strike configuration saved", "success")
    except ValueError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("forces.detail", id=force_id))


@bp.route("/<int:force_id>/alpha-strike/config", methods=["POST"])
def update_config(force_id: int):
    """Update point budget for an Alpha Strike force."""
    if not _force_or_404(force_id):
        return jsonify({"success": False, "error": "Force not found"}), 404

    data = request.get_json(silent=True) or {}
    point_budget = data.get("point_budget")
    if point_budget is not None:
        try:
            point_budget = int(point_budget)
            if point_budget < 1:
                return jsonify({"success": False, "error": "Invalid point budget"}), 400
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Invalid point budget"}), 400

    row = alpha_strike_service.update_config(force_id, point_budget=point_budget)
    if not row:
        return jsonify({"success": False, "error": "Alpha Strike not configured"}), 404

    summary = alpha_strike_service.get_force_summary(force_id)
    return jsonify({"success": True, "config": row.to_dict(), "summary": summary.to_dict()})


@bp.route("/<int:force_id>/alpha-strike/summary")
def summary(force_id: int):
    """JSON summary of PV totals and budget status."""
    if not _force_or_404(force_id):
        return jsonify({"success": False, "error": "Force not found"}), 404

    as_force = alpha_strike_service.get_alpha_strike_force(force_id)
    if not as_force:
        return jsonify({"success": True, "configured": False})

    budget = alpha_strike_service.get_force_summary(force_id)
    return jsonify(
        {
            "success": True,
            "configured": True,
            "config": as_force.to_dict(),
            "summary": budget.to_dict(),
        }
    )


@bp.route("/<int:force_id>/alpha-strike/variants")
def variants(force_id: int):
    """Search MUL variants for a force miniature slot."""
    if not _force_or_404(force_id):
        return jsonify({"success": False, "error": "Force not found"}), 404

    try:
        fm_id = int(request.args.get("fm_id", ""))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "fm_id required"}), 400

    try:
        units = alpha_strike_service.search_variants_for_slot(force_id, fm_id)
        return jsonify({"success": True, "units": units})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503


@bp.route("/<int:force_id>/alpha-strike/assign", methods=["POST"])
def assign(force_id: int):
    """Assign a MUL variant to a force miniature slot."""
    if not _force_or_404(force_id):
        return jsonify({"success": False, "error": "Force not found"}), 404

    data = request.get_json(silent=True) or {}
    try:
        fm_id = int(data.get("force_miniature_id"))
        mul_unit_id = int(data.get("mul_unit_id"))
        search_name = str(data.get("search_name", "")).strip()
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid parameters"}), 400

    if not search_name:
        return jsonify({"success": False, "error": "search_name required"}), 400

    try:
        assignment = alpha_strike_service.assign_variant(
            force_id,
            fm_id,
            mul_unit_id,
            search_name=search_name,
        )
        summary = alpha_strike_service.get_force_summary(force_id)
        return jsonify(
            {
                "success": True,
                "assignment": assignment.to_dict(),
                "summary": summary.to_dict(),
            }
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503


@bp.route("/<int:force_id>/alpha-strike/assign/<int:fm_id>", methods=["DELETE"])
def clear_assign(force_id: int, fm_id: int):
    """Remove variant assignment from a slot (miniature stays in lance)."""
    if not _force_or_404(force_id):
        return jsonify({"success": False, "error": "Force not found"}), 404

    if alpha_strike_service.clear_assignment(force_id, fm_id):
        summary = alpha_strike_service.get_force_summary(force_id)
        return jsonify({"success": True, "summary": summary.to_dict()})
    return jsonify({"success": False, "error": "Assignment not found"}), 404


@bp.route("/<int:force_id>/alpha-strike/reference")
def reference_data(force_id: int):  # noqa: ARG001
    """Return static faction/era lists for UI dropdowns."""
    return jsonify(
        {
            "success": True,
            "factions": mul_service.get_factions(),
            "eras": mul_service.get_eras(),
        }
    )
