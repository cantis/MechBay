from __future__ import annotations

import structlog
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from ..services import after_action_service, campaign_service, contract_service, force_service
from ..services.campaign_service import (
    CAMPAIGN_STATUSES,
    DEFAULT_OPENING_WARCHEST,
    DEFAULT_PILOT_GUNNERY,
    DEFAULT_PILOT_PILOTING,
    PILOT_STATUSES,
    UNIT_CONDITIONS,
)
from ..services.miniature_service import get_all_miniatures

logger = structlog.get_logger()

bp = Blueprint("campaigns", __name__, url_prefix="/campaigns")


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    return int(cleaned)


def _campaign_view_context(campaign) -> dict:
    return {
        "campaign": campaign,
        "month_label": campaign_service.campaign_month_label(campaign),
        "location_label": campaign_service.location_display(campaign),
        "missing_units": campaign_service.missing_miniature_units(campaign),
        "statuses": CAMPAIGN_STATUSES,
        "conditions": UNIT_CONDITIONS,
        "pilot_statuses": PILOT_STATUSES,
        "inventory": get_all_miniatures(),
        "generic_as_skill": campaign_service.GENERIC_AS_SKILL,
        "default_pilot_gunnery": DEFAULT_PILOT_GUNNERY,
        "default_pilot_piloting": DEFAULT_PILOT_PILOTING,
        "contracts": contract_service.get_contracts_for_campaign(campaign.id),
        "active_contract": contract_service.get_active_contract(campaign.id),
        "next_contract_number": contract_service.next_contract_number(campaign.id),
        "repair_orders": after_action_service.get_repair_orders(campaign.id),
        "open_repair_statuses": after_action_service.OPEN_REPAIR_STATUSES,
    }


@bp.route("")
def list_campaigns():
    campaigns = campaign_service.get_all_campaigns()
    active_campaign = campaign_service.get_active_campaign()
    forces = force_service.get_all_forces()
    return render_template(
        "campaigns/list.html",
        campaigns=campaigns,
        active_campaign=active_campaign,
        forces=forces,
        statuses=CAMPAIGN_STATUSES,
        default_opening_warchest=DEFAULT_OPENING_WARCHEST,
    )


@bp.route("/create", methods=["POST"])
def create():
    name = request.form.get("name", "").strip()
    force_id_raw = request.form.get("force_id", "").strip()
    if not name:
        flash("Campaign name is required", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    if not force_id_raw:
        flash("A saved Force is required to create a Campaign", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    if not (request.form.get("starting_bt_year") or "").strip() or not (
        request.form.get("starting_bt_month") or ""
    ).strip():
        flash("Starting year and month are required", "danger")
        return redirect(url_for("campaigns.list_campaigns"))

    try:
        force_id = int(force_id_raw)
        scale = int(request.form.get("scale") or 1)
        reputation = int(request.form.get("reputation") or 1)
        starting_bt_year = int(request.form.get("starting_bt_year") or "")
        starting_bt_month = int(request.form.get("starting_bt_month") or "")
        opening_warchest = _optional_int(request.form.get("opening_warchest"))
    except (TypeError, ValueError):
        flash("Invalid campaign values", "danger")
        return redirect(url_for("campaigns.list_campaigns"))

    try:
        campaign = campaign_service.create_campaign_from_force(
            force_id,
            name,
            scale=scale,
            reputation=reputation,
            status=request.form.get("status", "planning").strip() or "planning",
            starting_bt_year=starting_bt_year,
            starting_bt_month=starting_bt_month,
            current_location=request.form.get("current_location"),
            notes=request.form.get("notes"),
            opening_warchest=opening_warchest,
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("campaigns.list_campaigns"))

    flash(f"Campaign '{campaign.name}' created from {campaign.source_force_name}", "success")
    return redirect(url_for("campaigns.detail", id=campaign.id))


@bp.route("/<int:id>")
def detail(id: int):  # noqa: A002
    campaign = campaign_service.get_campaign_by_id(id)
    if not campaign:
        flash("Campaign not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    return render_template("campaigns/detail.html", **_campaign_view_context(campaign))


@bp.route("/<int:id>/activate", methods=["POST"])
def activate(id: int):  # noqa: A002
    campaign = campaign_service.switch_campaign(id)
    if campaign:
        flash(f"Campaign '{campaign.name}' loaded", "success")
        if request.form.get("return_to") == "detail":
            return redirect(url_for("campaigns.detail", id=campaign.id))
    else:
        flash("Campaign not found", "danger")
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/<int:id>/update", methods=["POST"])
def update(id: int):  # noqa: A002
    try:
        current_campaign_month = _optional_int(request.form.get("current_campaign_month"))
        starting_bt_year = _optional_int(request.form.get("starting_bt_year"))
        starting_bt_month = _optional_int(request.form.get("starting_bt_month"))
        scale = _optional_int(request.form.get("scale"))
        reputation = _optional_int(request.form.get("reputation"))
    except (TypeError, ValueError):
        flash("Invalid campaign values", "danger")
        return redirect(url_for("campaigns.detail", id=id))

    try:
        campaign = campaign_service.update_campaign(
            id,
            name=request.form.get("name"),
            status=request.form.get("status") or None,
            current_campaign_month=current_campaign_month,
            starting_bt_year=starting_bt_year,
            starting_bt_month=starting_bt_month,
            current_location=request.form.get("current_location"),
            reputation=reputation,
            scale=scale,
            notes=request.form.get("notes"),
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("campaigns.detail", id=id))

    if not campaign:
        flash("Campaign not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    flash("Campaign updated", "success")
    return redirect(url_for("campaigns.detail", id=id))


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id: int):  # noqa: A002
    if campaign_service.delete_campaign(id):
        flash("Campaign deleted", "info")
    else:
        flash("Campaign not found", "warning")
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/<int:id>/lances", methods=["POST"])
def add_lance(id: int):  # noqa: A002
    try:
        campaign_service.add_campaign_lance(
            id,
            request.form.get("name", ""),
            special_rules=request.form.get("special_rules"),
        )
        flash("Lance added", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("campaigns.detail", id=id))


@bp.route("/lances/<int:lance_id>/update", methods=["POST"])
def update_lance(lance_id: int):
    lance = campaign_service.update_campaign_lance(
        lance_id,
        name=request.form.get("name"),
        special_rules=request.form.get("special_rules"),
    )
    campaign_id = request.form.get("campaign_id")
    if not lance:
        flash("Lance not found", "warning")
        return redirect(url_for("campaigns.list_campaigns"))
    flash("Lance updated", "success")
    target_id = lance.campaign_id if not campaign_id else int(campaign_id)
    return redirect(url_for("campaigns.detail", id=target_id))


@bp.route("/<int:id>/units", methods=["POST"])
def add_unit(id: int):  # noqa: A002
    try:
        miniature_id = int(request.form.get("miniature_id"))
        lance_id = _optional_int(request.form.get("lance_id"))
        campaign_service.add_campaign_unit(
            id,
            miniature_id,
            lance_id=lance_id,
            notes=request.form.get("notes"),
        )
        flash("Campaign unit added", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid unit values", "danger")
    return redirect(url_for("campaigns.detail", id=id))


@bp.route("/units/<int:unit_id>/update", methods=["POST"])
def update_unit(unit_id: int):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    available_raw = data.get("available")
    available = None
    if available_raw is not None and available_raw != "":
        available = str(available_raw).lower() in {"1", "true", "on", "yes"}
    is_omni_raw = data.get("is_omni")
    is_omni = None
    if is_omni_raw is not None and is_omni_raw != "":
        is_omni = str(is_omni_raw).lower() in {"1", "true", "on", "yes"}
    lance_id: int | None | object = ...
    if "lance_id" in data:
        try:
            lance_id = _optional_int(str(data.get("lance_id") or ""))
        except (TypeError, ValueError):
            flash("Invalid lance", "danger")
            return redirect(url_for("campaigns.list_campaigns"))

    try:
        unit = campaign_service.update_campaign_unit(
            unit_id,
            condition=data.get("condition") or None,
            available=available,
            notes=data.get("notes") if "notes" in data else ...,
            is_omni=is_omni,
            lance_id=lance_id,
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        if is_json:
            return jsonify({"success": False, "error": str(exc)}), 400
        if campaign_id:
            return redirect(url_for("campaigns.detail", id=int(campaign_id)))
        return redirect(url_for("campaigns.list_campaigns"))

    flash("Unit updated" if unit else "Unit not found", "success" if unit else "warning")
    if is_json:
        if unit:
            return jsonify({"success": True}), 200
        return jsonify({"success": False, "error": "Unit not found"}), 404
    target_id = unit.campaign_id if unit else campaign_id
    return redirect(url_for("campaigns.detail", id=int(target_id)))


@bp.route("/units/<int:unit_id>/delete", methods=["POST"])
def delete_unit(unit_id: int):
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    deleted = campaign_service.delete_campaign_unit(unit_id)
    flash("Unit removed" if deleted else "Unit not found", "info" if deleted else "warning")
    if campaign_id:
        return redirect(url_for("campaigns.detail", id=int(campaign_id)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/<int:id>/pilots", methods=["POST"])
def add_pilot(id: int):  # noqa: A002
    try:
        campaign_service.add_campaign_pilot(
            id,
            request.form.get("name", ""),
            callsign=request.form.get("callsign"),
            gunnery=int(request.form.get("gunnery") or DEFAULT_PILOT_GUNNERY),
            piloting=int(request.form.get("piloting") or DEFAULT_PILOT_PILOTING),
            alpha_strike_skill=int(
                request.form.get("alpha_strike_skill") or campaign_service.GENERIC_AS_SKILL
            ),
            edge_tokens=int(request.form.get("edge_tokens") or 0),
            edge_abilities=request.form.get("edge_abilities"),
            improvement_sp=int(request.form.get("improvement_sp") or 0),
            wounds=int(request.form.get("wounds") or 0),
            status=request.form.get("status") or "alive",
            notes=request.form.get("notes"),
            preferred_unit_id=_optional_int(request.form.get("preferred_unit_id")),
        )
        flash("Pilot added", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid pilot values", "danger")
    return redirect(url_for("campaigns.detail", id=id))


@bp.route("/pilots/<int:pilot_id>/recover-wound", methods=["POST"])
def recover_pilot_wound(pilot_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        pilot = campaign_service.recover_pilot_wound(pilot_id)
        flash(f"{pilot.name} recovered 1 wound ({pilot.wounds} remaining)", "success")
        target = pilot.campaign_id
    except ValueError as exc:
        flash(str(exc), "danger")
        target = int(campaign_id) if campaign_id else None
    if target:
        return redirect(url_for("campaigns.detail", id=int(target)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/pilots/<int:pilot_id>/update", methods=["POST"])
def update_pilot(pilot_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        pilot = campaign_service.update_campaign_pilot(
            pilot_id,
            name=request.form.get("name"),
            callsign=request.form.get("callsign"),
            gunnery=_optional_int(request.form.get("gunnery")),
            piloting=_optional_int(request.form.get("piloting")),
            alpha_strike_skill=_optional_int(request.form.get("alpha_strike_skill")),
            edge_tokens=_optional_int(request.form.get("edge_tokens")),
            edge_abilities=request.form.get("edge_abilities"),
            improvement_sp=_optional_int(request.form.get("improvement_sp")),
            wounds=_optional_int(request.form.get("wounds")),
            status=request.form.get("status") or None,
            notes=request.form.get("notes"),
            preferred_unit_id=_optional_int(request.form.get("preferred_unit_id")),
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        if campaign_id:
            return redirect(url_for("campaigns.detail", id=int(campaign_id)))
        return redirect(url_for("campaigns.list_campaigns"))
    flash("Pilot updated" if pilot else "Pilot not found", "success" if pilot else "warning")
    target = pilot.campaign_id if pilot else campaign_id
    return redirect(url_for("campaigns.detail", id=int(target)))


@bp.route("/pilots/<int:pilot_id>/delete", methods=["POST"])
def delete_pilot(pilot_id: int):
    campaign_id = request.form.get("campaign_id")
    deleted = campaign_service.delete_campaign_pilot(pilot_id)
    flash("Pilot removed" if deleted else "Pilot not found", "info" if deleted else "warning")
    if campaign_id:
        return redirect(url_for("campaigns.detail", id=int(campaign_id)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/<int:id>/warchest", methods=["POST"])
def add_transaction(id: int):  # noqa: A002
    try:
        campaign_service.add_warchest_transaction(
            id,
            transaction_type=request.form.get("transaction_type") or "adjustment",
            description=request.form.get("description") or "",
            actual_amount=int(request.form.get("actual_amount") or 0),
            campaign_month=_optional_int(request.form.get("campaign_month")),
            gross_amount=_optional_int(request.form.get("gross_amount")),
            covered_amount=int(request.form.get("covered_amount") or 0),
            notes=request.form.get("notes"),
        )
        flash("Warchest transaction recorded", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid transaction values", "danger")
    return redirect(url_for("campaigns.detail", id=id))


@bp.route("/<int:id>/travel", methods=["POST"])
def add_travel(id: int):  # noqa: A002
    try:
        campaign_service.create_travel_event(
            id,
            request.form.get("origin") or "",
            request.form.get("destination") or "",
            departure_campaign_month=_optional_int(request.form.get("departure_campaign_month")),
            jump_count=_optional_int(request.form.get("jump_count")),
            transport_mode=request.form.get("transport_mode") or "manual",
            standard_amount=_optional_int(request.form.get("standard_amount")),
            employer_payment=_optional_int(request.form.get("employer_payment")),
            actual_expense=_optional_int(request.form.get("actual_expense")),
            gross_cost=_optional_int(request.form.get("gross_cost")),
            covered_amount=_optional_int(request.form.get("covered_amount")),
            actual_warchest_impact=_optional_int(request.form.get("actual_warchest_impact")),
            notes=request.form.get("notes"),
            contract_id=_optional_int(request.form.get("contract_id")),
        )
        flash("Travel started", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid travel values", "danger")
    return redirect(url_for("campaigns.detail", id=id))


@bp.route("/travel/<int:event_id>/complete", methods=["POST"])
def complete_travel(event_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        arrival = _optional_int(request.form.get("arrival_campaign_month"))
    except (TypeError, ValueError):
        flash("Invalid arrival month", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    event = campaign_service.complete_travel_event(event_id, arrival_campaign_month=arrival)
    if event:
        flash("Travel completed", "success")
    else:
        flash("Travel event not found", "warning")
    target = event.campaign_id if event else campaign_id
    if target:
        return redirect(url_for("campaigns.detail", id=int(target)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/units/<int:unit_id>/truly-destroyed", methods=["POST"])
def mark_truly_destroyed(unit_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        unit = after_action_service.mark_unit_truly_destroyed(unit_id)
        flash(f"{unit.chassis} marked truly destroyed", "info")
        target = unit.campaign_id
    except ValueError as exc:
        flash(str(exc), "danger")
        target = int(campaign_id) if campaign_id else None
    if target:
        return redirect(url_for("campaigns.detail", id=int(target)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/units/<int:unit_id>/omni", methods=["POST"])
def reconfigure_omni(unit_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        cost = int(request.form.get("cost") or 0)
        mul_unit_id = int(request.form.get("mul_unit_id"))
        unit = after_action_service.reconfigure_omni_from_search(unit_id, mul_unit_id, cost=cost)
        flash(f"{unit.chassis} reconfigured to {unit.variant}", "success")
        target = unit.campaign_id
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid Omni configuration", "danger")
        target = int(campaign_id) if campaign_id else None
    if target:
        return redirect(url_for("campaigns.detail", id=int(target)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/repairs/<int:order_id>/update", methods=["POST"])
def update_repair(order_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        order = after_action_service.update_repair_order(
            order_id,
            gross_cost=int(request.form.get("gross_cost") or 0),
            notes=request.form.get("notes"),
        )
        flash("Repair Order updated", "success")
        target = order.campaign_id
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid repair cost", "danger")
        target = int(campaign_id) if campaign_id else None
    if target:
        return redirect(url_for("campaigns.detail", id=int(target)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/repairs/<int:order_id>/complete", methods=["POST"])
def complete_repair(order_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        after_action_service.update_repair_order(
            order_id,
            gross_cost=int(request.form.get("gross_cost") or 0),
            notes=request.form.get("notes"),
        )
        order = after_action_service.complete_repair_order(order_id)
        flash("Repair completed", "success")
        target = order.campaign_id
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid repair", "danger")
        target = int(campaign_id) if campaign_id else None
    if target:
        return redirect(url_for("campaigns.detail", id=int(target)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/repairs/<int:order_id>/cancel", methods=["POST"])
def cancel_repair(order_id: int):
    campaign_id = request.form.get("campaign_id")
    try:
        order = after_action_service.cancel_repair_order(order_id)
        flash("Repair Order cancelled", "info")
        target = order.campaign_id
    except ValueError as exc:
        flash(str(exc), "danger")
        target = int(campaign_id) if campaign_id else None
    if target:
        return redirect(url_for("campaigns.detail", id=int(target)))
    return redirect(url_for("campaigns.list_campaigns"))


@bp.route("/<int:id>/advance-month")
def advance_month_form(id: int):  # noqa: A002
    campaign = campaign_service.get_campaign_by_id(id)
    if not campaign:
        flash("Campaign not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    try:
        preview = after_action_service.preview_month_advance(id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("campaigns.detail", id=id))
    return render_template(
        "campaigns/advance_month.html",
        campaign=campaign,
        preview=preview,
        active_contract=contract_service.get_active_contract(id),
        month_label=campaign_service.campaign_month_label(campaign),
    )


@bp.route("/<int:id>/advance-month", methods=["POST"])
def advance_month(id: int):  # noqa: A002
    try:
        campaign = after_action_service.advance_campaign_month(
            id,
            base_pay=int(request.form.get("base_pay") or 0),
            maintenance=int(request.form.get("maintenance") or 0),
        )
        flash(f"Advanced to {campaign_service.campaign_month_label(campaign)}", "success")
        return redirect(url_for("campaigns.detail", id=campaign.id))
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid month-advance values", "danger")
        return redirect(url_for("campaigns.advance_month_form", id=id))
