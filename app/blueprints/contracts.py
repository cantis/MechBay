from __future__ import annotations

import structlog
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from ..services import campaign_service, contract_service
from ..services.contract_service import CONTRACT_STATUSES, SORTIE_OUTCOMES, SORTIE_STATUSES

logger = structlog.get_logger()

bp = Blueprint("contracts", __name__)


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    return int(cleaned)


@bp.route("/campaigns/<int:campaign_id>/contracts", methods=["POST"])
def create(campaign_id: int):
    try:
        length_months = int(request.form.get("length_months") or 1)
        contract = contract_service.create_contract(
            campaign_id,
            request.form.get("name") or "",
            contract_number=request.form.get("contract_number") or None,
            employer=request.form.get("employer"),
            destination=request.form.get("destination"),
            type_of_action=request.form.get("type_of_action"),
            scale=_optional_int(request.form.get("scale")),
            length_months=length_months,
            start_campaign_month=_optional_int(request.form.get("start_campaign_month")),
            end_campaign_month=_optional_int(request.form.get("end_campaign_month")),
            base_pay_percent=int(request.form.get("base_pay_percent") or 0),
            support_percent=int(request.form.get("support_percent") or 0),
            transportation_percent=int(request.form.get("transportation_percent") or 0),
            salvage_rights=request.form.get("salvage_rights"),
            command_rights=request.form.get("command_rights"),
            notes=request.form.get("notes"),
        )
        flash(f"Contract {contract.contract_number} created", "success")
        return redirect(url_for("contracts.detail", id=contract.id))
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid contract values", "danger")
        return redirect(url_for("campaigns.detail", id=campaign_id))


@bp.route("/contracts/<int:id>")
def detail(id: int):  # noqa: A002
    contract = contract_service.get_contract_by_id(id)
    if not contract:
        flash("Contract not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    campaign = campaign_service.get_campaign_by_id(contract.campaign_id)
    return render_template(
        "contracts/detail.html",
        contract=contract,
        campaign=campaign,
        month_label=campaign_service.campaign_month_label(campaign) if campaign else "",
        statuses=CONTRACT_STATUSES,
    )


@bp.route("/contracts/<int:id>/update", methods=["POST"])
def update(id: int):  # noqa: A002
    try:
        contract = contract_service.update_contract(
            id,
            name=request.form.get("name"),
            contract_number=request.form.get("contract_number"),
            employer=request.form.get("employer"),
            destination=request.form.get("destination"),
            type_of_action=request.form.get("type_of_action"),
            scale=_optional_int(request.form.get("scale")),
            length_months=_optional_int(request.form.get("length_months")),
            start_campaign_month=_optional_int(request.form.get("start_campaign_month")),
            end_campaign_month=_optional_int(request.form.get("end_campaign_month")),
            base_pay_percent=_optional_int(request.form.get("base_pay_percent")),
            support_percent=_optional_int(request.form.get("support_percent")),
            transportation_percent=_optional_int(request.form.get("transportation_percent")),
            salvage_rights=request.form.get("salvage_rights"),
            command_rights=request.form.get("command_rights"),
            notes=request.form.get("notes"),
        )
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid contract values", "danger")
        return redirect(url_for("contracts.detail", id=id))
    if not contract:
        flash("Contract not found", "warning")
        return redirect(url_for("campaigns.list_campaigns"))
    flash("Contract updated", "success")
    return redirect(url_for("contracts.detail", id=id))


@bp.route("/contracts/<int:id>/activate", methods=["POST"])
def activate(id: int):  # noqa: A002
    try:
        contract = contract_service.activate_contract(id)
        flash(f"Contract {contract.contract_number} is now active", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.detail", id=id))


@bp.route("/contracts/<int:id>/complete", methods=["POST"])
def complete(id: int):  # noqa: A002
    try:
        contract = contract_service.complete_contract(id)
        flash(f"Contract {contract.contract_number} completed", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.detail", id=id))


@bp.route("/contracts/<int:id>/cancel", methods=["POST"])
def cancel(id: int):  # noqa: A002
    try:
        penalty = int(request.form.get("penalty_wp") or 0)
        reputation_delta = int(request.form.get("reputation_delta") or 0)
        contract = contract_service.cancel_contract(
            id, penalty_wp=penalty, reputation_delta=reputation_delta
        )
        flash(f"Contract {contract.contract_number} cancelled", "info")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid cancel values", "danger")
    return redirect(url_for("contracts.detail", id=id))


@bp.route("/contracts/<int:id>/travel", methods=["POST"])
def start_travel(id: int):  # noqa: A002
    contract = contract_service.get_contract_by_id(id)
    if not contract:
        flash("Contract not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    try:
        gross = int(request.form.get("gross_cost") or 0)
        covered_raw = request.form.get("covered_amount")
        if covered_raw is None or str(covered_raw).strip() == "":
            covered = contract_service.transportation_coverage(
                gross, contract.transportation_percent
            )
        else:
            covered = int(covered_raw)
        campaign_service.create_travel_event(
            contract.campaign_id,
            request.form.get("origin") or "",
            request.form.get("destination") or "",
            jump_count=_optional_int(request.form.get("jump_count")),
            gross_cost=gross,
            covered_amount=covered,
            notes=request.form.get("notes"),
            contract_id=contract.id,
        )
        flash("Travel started", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid travel values", "danger")
    return redirect(url_for("contracts.detail", id=id))


@bp.route("/contracts/<int:id>/sorties", methods=["POST"])
def create_sortie(id: int):  # noqa: A002
    try:
        sortie = contract_service.create_sortie(
            id,
            request.form.get("name") or "",
            scale=_optional_int(request.form.get("scale")),
            campaign_month=_optional_int(request.form.get("campaign_month")),
            scenario_type=request.form.get("scenario_type"),
            location=request.form.get("location"),
            notes=request.form.get("notes"),
        )
        flash("Sortie created", "success")
        return redirect(url_for("contracts.sortie_detail", id=sortie.id))
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid Sortie values", "danger")
        return redirect(url_for("contracts.detail", id=id))


@bp.route("/sorties/<int:id>")
def sortie_detail(id: int):  # noqa: A002
    sortie = contract_service.get_sortie_by_id(id)
    if not sortie:
        flash("Sortie not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    campaign = campaign_service.get_campaign_by_id(sortie.campaign_id)
    contract = contract_service.get_contract_by_id(sortie.contract_id)
    eligible_units = contract_service.eligible_campaign_units(sortie.campaign_id)
    selected_ids = {unit.campaign_unit_id for unit in sortie.units}
    available_units = [unit for unit in eligible_units if unit.id not in selected_ids]
    lances = campaign.lances if campaign else []
    return render_template(
        "sorties/detail.html",
        sortie=sortie,
        campaign=campaign,
        contract=contract,
        pv_total=contract_service.sortie_point_total(sortie),
        available_units=available_units,
        lances=lances,
        pilots=contract_service.eligible_named_pilots(sortie.campaign_id),
        outcomes=SORTIE_OUTCOMES,
        statuses=SORTIE_STATUSES,
        editable=sortie.status == "planning",
    )


@bp.route("/sorties/<int:id>/update", methods=["POST"])
def update_sortie(id: int):  # noqa: A002
    try:
        contract_service.update_sortie(
            id,
            name=request.form.get("name"),
            scale=_optional_int(request.form.get("scale")),
            campaign_month=_optional_int(request.form.get("campaign_month")),
            scenario_type=request.form.get("scenario_type"),
            location=request.form.get("location"),
            notes=request.form.get("notes"),
        )
        flash("Sortie updated", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid Sortie values", "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/units", methods=["POST"])
def add_sortie_unit(id: int):  # noqa: A002
    try:
        lance_id = _optional_int(request.form.get("lance_id"))
        unit_id = _optional_int(request.form.get("campaign_unit_id"))
        if lance_id:
            added = contract_service.add_lance_to_sortie(id, lance_id)
            flash(f"Added {len(added)} available unit(s) from the lance", "success")
        elif unit_id:
            contract_service.add_unit_to_sortie(id, unit_id)
            flash("Unit added to Sortie", "success")
        else:
            flash("Select a lance or unit", "danger")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid unit", "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sortie-units/<int:unit_id>/delete", methods=["POST"])
def remove_sortie_unit(unit_id: int):
    data = request.get_json(silent=True) or request.form
    sortie_id = data.get("sortie_id")
    try:
        contract_service.remove_sortie_unit(unit_id)
        flash("Unit removed from Sortie", "info")
    except ValueError as exc:
        flash(str(exc), "danger")
    if sortie_id:
        return redirect(url_for("contracts.sortie_detail", id=int(sortie_id)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/sortie-units/<int:unit_id>/pilot", methods=["POST"])
def assign_pilot(unit_id: int):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form
    sortie_id = data.get("sortie_id")
    try:
        contract_service.assign_sortie_pilot(
            unit_id, _optional_int(str(data.get("campaign_pilot_id") or ""))
        )
        flash("Pilot assignment saved", "success")
        if is_json:
            return jsonify({"success": True}), 200
    except (TypeError, ValueError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Invalid pilot"
        flash(message, "danger")
        if is_json:
            return jsonify({"success": False, "error": message}), 400
    if sortie_id:
        return redirect(url_for("contracts.sortie_detail", id=int(sortie_id)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/sortie-units/<int:unit_id>/configuration", methods=["POST"])
def configure_omni(unit_id: int):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form
    sortie_id = data.get("sortie_id")
    try:
        cost = int(data.get("cost") or 0)
        mul_unit_id = int(data.get("mul_unit_id"))
        contract_service.apply_omni_from_search(unit_id, mul_unit_id, cost=cost)
        flash("Omni configuration updated", "success")
        if is_json:
            return jsonify({"success": True}), 200
    except (TypeError, ValueError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Invalid configuration"
        flash(message, "danger")
        if is_json:
            return jsonify({"success": False, "error": message}), 400
    if sortie_id:
        return redirect(url_for("contracts.sortie_detail", id=int(sortie_id)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/campaigns/<int:campaign_id>/units/<int:unit_id>/omni-variants")
def omni_variants(campaign_id: int, unit_id: int):
    try:
        units = contract_service.search_omni_variants(campaign_id, unit_id)
        return jsonify({"success": True, "data": units}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@bp.route("/sorties/<int:id>/ready", methods=["POST"])
def mark_ready(id: int):  # noqa: A002
    try:
        contract_service.mark_sortie_ready(id)
        flash("Sortie is Ready", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/reopen", methods=["POST"])
def reopen(id: int):  # noqa: A002
    try:
        contract_service.reopen_sortie_planning(id)
        flash("Sortie returned to Planning", "info")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/fought", methods=["POST"])
def mark_fought(id: int):  # noqa: A002
    try:
        outcome = request.form.get("outcome") or None
        contract_service.mark_sortie_fought(id, outcome=outcome)
        flash("Sortie marked as Fought", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))
