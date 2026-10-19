from __future__ import annotations

from datetime import date
from io import BytesIO

import structlog
from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for

from ..services import (
    aces_after_action_service,
    aces_pilot_rules,
    aces_recon_service,
    aces_sortie_service,
    after_action_service,
    campaign_service,
    contract_service,
    jeff_export_service,
)
from ..services.after_action_service import DAMAGE_OUTCOMES
from ..services.contract_service import CONTRACT_STATUSES, SORTIE_OUTCOMES, SORTIE_STATUSES
from ..services.jeff_export_service import JeffExportError

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
    roster_summary = contract_service.contract_roster_summary(contract)
    available_for_roster = []
    if campaign and contract.status in {"draft", "active"}:
        on_roster = {row.campaign_unit_id for row in contract.roster_units}
        available_for_roster = [
            unit
            for unit in campaign.units
            if unit.id not in on_roster and unit.point_value is not None
        ]
    return render_template(
        "contracts/detail.html",
        contract=contract,
        campaign=campaign,
        month_label=campaign_service.campaign_month_label(campaign) if campaign else "",
        statuses=CONTRACT_STATUSES,
        roster_summary=roster_summary,
        available_for_roster=available_for_roster,
        transport_modes=contract_service.TRANSPORT_MODES,
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
        campaign_service.create_travel_event(
            contract.campaign_id,
            request.form.get("origin") or "",
            request.form.get("destination") or "",
            jump_count=_optional_int(request.form.get("jump_count")),
            transport_mode=request.form.get("transport_mode") or "manual",
            standard_amount=_optional_int(request.form.get("standard_amount")),
            employer_payment=_optional_int(request.form.get("employer_payment")),
            actual_expense=_optional_int(request.form.get("actual_expense")),
            gross_cost=_optional_int(request.form.get("gross_cost")),
            covered_amount=_optional_int(request.form.get("covered_amount")),
            notes=request.form.get("notes"),
            contract_id=contract.id,
        )
        flash("Travel started", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid travel values", "danger")
    return redirect(url_for("contracts.detail", id=id))


@bp.route("/contracts/<int:id>/roster/units", methods=["POST"])
def add_roster_unit(id: int):  # noqa: A002
    try:
        lance_id = _optional_int(request.form.get("lance_id"))
        unit_id = _optional_int(request.form.get("campaign_unit_id"))
        if lance_id:
            added = contract_service.add_lance_to_contract_roster(id, lance_id)
            flash(f"Added {len(added)} unit(s) to the Contract roster", "success")
        elif unit_id:
            contract_service.add_unit_to_contract_roster(id, unit_id)
            flash("Unit added to Contract roster", "success")
        else:
            flash("Select a lance or unit", "danger")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid roster unit", "danger")
    return redirect(url_for("contracts.detail", id=id))


@bp.route("/contracts/<int:id>/roster/units/<int:campaign_unit_id>/remove", methods=["POST"])
def remove_roster_unit(id: int, campaign_unit_id: int):  # noqa: A002
    try:
        contract_service.remove_unit_from_contract_roster(id, campaign_unit_id)
        flash("Unit removed from Contract roster", "info")
    except ValueError as exc:
        flash(str(exc), "danger")
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
    contract = (
        contract_service.get_contract_by_id(sortie.contract_id) if sortie.contract_id else None
    )
    eligible_units = contract_service.eligible_campaign_units(
        sortie.campaign_id, contract_id=sortie.contract_id
    )
    selected_ids = {unit.campaign_unit_id for unit in sortie.units}
    available_units = [unit for unit in eligible_units if unit.id not in selected_ids]
    lances = campaign.lances if campaign else []
    # What each lance would add: its available units not already in the Sortie force.
    lance_adds: dict[int, dict[str, int]] = {}
    for unit in available_units:
        if unit.campaign_lance_id is not None:
            entry = lance_adds.setdefault(unit.campaign_lance_id, {"units": 0, "pv": 0})
            entry["units"] += 1
            entry["pv"] += int(unit.point_value or 0)
    pv_limit = contract_service.sortie_pv_limit(sortie.scale)
    unit_limit = contract_service.sortie_unit_limit(sortie.scale)
    is_aces = bool(campaign and campaign.ruleset == "aces")
    pv_context: dict = {}
    if is_aces:
        allowance = campaign_service.aces_sortie_pv_allowance(sortie.campaign_id)
        pv_limit = sortie.max_sortie_pv
        adjusted = None
        if sortie.scenario_pv is not None and sortie.pv_modifier_percent is not None:
            adjusted = max(0, sortie.scenario_pv * (100 + sortie.pv_modifier_percent) // 100)
        parts = []
        if allowance["difficulty_percent"]:
            parts.append(
                f"{campaign.difficulty or 'Standard'} {allowance['difficulty_percent']:+d}%"
            )
        if allowance["experienced_percent"]:
            parts.append(f"experienced force {allowance['experienced_percent']:+d}%")
        pv_context = {
            "pv_percent_now": allowance["difficulty_percent"] + allowance["experienced_percent"],
            "pv_modifier_label": ", ".join(parts) or "no difficulty adjustment",
            "adjusted_pv": adjusted,
            "above_adjusted": adjusted is not None
            and sortie.max_sortie_pv is not None
            and sortie.max_sortie_pv > adjusted,
            "pv_remaining": (sortie.max_sortie_pv - contract_service.sortie_point_total(sortie))
            if sortie.max_sortie_pv is not None
            else None,
        }
    eligible_pilots = contract_service.eligible_named_pilots(sortie.campaign_id)
    aces_context: dict = {"is_aces": is_aces, **pv_context}
    if is_aces:
        typed = [pilot for pilot in eligible_pilots if pilot.pilot_type]
        eligible_pilots = typed
        aces_context.update(
            pv_allowance=allowance,
            recon_actions=aces_recon_service.list_recon_actions(sortie.id),
            recon_units=[
                unit
                for unit in (campaign.units if campaign else [])
                if unit.condition not in aces_recon_service.OUT_OF_SERVICE
            ],
            can_copy_recon=sortie.status == "planning"
            and aces_recon_service.previous_attempt_has_recon(sortie.id)
            and not aces_recon_service.list_recon_actions(sortie.id),
            required_pilot_type={
                unit.id: aces_pilot_rules.pilot_type_for_unit_type(unit.unit_type_name)
                for unit in sortie.units
            },
            pilots_by_unit={
                unit.id: [
                    pilot
                    for pilot in typed
                    if aces_pilot_rules.unit_accepts_pilot(unit.unit_type_name, pilot.pilot_type)
                ]
                for unit in sortie.units
            },
            lineage=aces_sortie_service.get_lineage(sortie.id),
            sortie_keywords=aces_sortie_service.get_sortie_keywords(sortie.id),
            current_keywords=aces_sortie_service.get_current_keywords(sortie.campaign_id),
            keyword_allowed=sortie.status in aces_sortie_service.KEYWORD_ALLOWED_STATUSES
            and sortie.outcome != aces_sortie_service.FAILED_OUTCOME,
            pilot_types=aces_pilot_rules.PILOT_TYPES,
            aces_damage_outcomes=aces_after_action_service.ACES_DAMAGE_OUTCOMES,
            damage_help=aces_after_action_service.DAMAGE_HELP,
            damage_help_note=aces_after_action_service.DAMAGE_HELP_NOTE,
            pilot_thresholds=aces_pilot_rules.thresholds_payload(),
            pending_shares=(
                aces_after_action_service.pending_shares(sortie.id)
                if sortie.status == "after_action"
                else []
            ),
        )
    return render_template(
        "sorties/detail.html",
        **aces_context,
        sortie=sortie,
        campaign=campaign,
        contract=contract,
        pv_total=contract_service.sortie_point_total(sortie),
        pv_limit=pv_limit,
        unit_limit=unit_limit,
        available_units=available_units,
        lances=lances,
        lance_adds=lance_adds,
        pilots=eligible_pilots,
        outcomes=SORTIE_OUTCOMES,
        statuses=SORTIE_STATUSES,
        editable=sortie.status == "planning",
        damage_outcomes=DAMAGE_OUTCOMES,
        named_sortie_pilots=[
            unit for unit in sortie.units if unit.campaign_pilot_id and not unit.is_generic_crew
        ],
    )


@bp.route("/sorties/<int:id>/export/jeff")
def export_sortie_jeff(id: int):  # noqa: A002
    """Download the Sortie force as a Jeff's BT Tools group."""
    try:
        json_string, filename = jeff_export_service.export_jeff_sortie(id)
    except JeffExportError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("contracts.sortie_detail", id=id))
    return send_file(
        BytesIO(json_string.encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


@bp.route("/sorties/<int:id>/update", methods=["POST"])
def update_sortie(id: int):  # noqa: A002
    try:
        extra: dict = {}
        if "date_played" in request.form:
            raw_date = request.form.get("date_played", "").strip()
            extra["date_played"] = date.fromisoformat(raw_date) if raw_date else None
        contract_service.update_sortie(
            id,
            name=request.form.get("name"),
            scale=_optional_int(request.form.get("scale")),
            campaign_month=_optional_int(request.form.get("campaign_month")),
            scenario_type=request.form.get("scenario_type"),
            location=request.form.get("location"),
            notes=request.form.get("notes"),
            **extra,
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
            added, notice = contract_service.add_lance_to_sortie_with_notice(id, lance_id)
            if notice:
                flash(f"Added {len(added)} unit(s). {notice}", "warning")
            else:
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


def _error_text(exc: Exception, fallback: str) -> str:
    return str(exc) if isinstance(exc, ValueError) else fallback


def _recon_form() -> dict:
    return {
        "campaign_unit_id": _optional_int(request.form.get("campaign_unit_id")),
        "sp_cost": request.form.get("sp_cost") or 0,
        "notes": request.form.get("notes"),
    }


@bp.route("/sorties/<int:id>/recon", methods=["POST"])
def add_recon(id: int):  # noqa: A002
    try:
        aces_recon_service.add_recon_action(id, request.form.get("name", ""), **_recon_form())
        flash("Reconnaissance action added", "success")
    except (TypeError, ValueError) as exc:
        flash(_error_text(exc, "Invalid reconnaissance values"), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id) + "#recon")


@bp.route("/sorties/<int:id>/recon/copy", methods=["POST"])
def copy_recon(id: int):  # noqa: A002
    try:
        copied = aces_recon_service.copy_from_previous_attempt(id)
        flash(f"Copied {len(copied)} reconnaissance action(s) from the previous attempt", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id) + "#recon")


@bp.route("/sorties/<int:id>/recon/<int:action_id>/update", methods=["POST"])
def update_recon(id: int, action_id: int):  # noqa: A002
    try:
        aces_recon_service.update_recon_action(
            action_id, request.form.get("name", ""), **_recon_form()
        )
        flash("Reconnaissance action saved", "success")
    except (TypeError, ValueError) as exc:
        flash(_error_text(exc, "Invalid reconnaissance values"), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id) + "#recon")


@bp.route("/sorties/<int:id>/recon/<int:action_id>/delete", methods=["POST"])
def delete_recon(id: int, action_id: int):  # noqa: A002
    try:
        aces_recon_service.delete_recon_action(action_id)
        flash("Reconnaissance action removed", "info")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id) + "#recon")


@bp.route("/sorties/<int:id>/pv", methods=["POST"])
def set_sortie_pv(id: int):  # noqa: A002
    try:
        result = aces_sortie_service.set_sortie_pv(
            id,
            scenario_pv=request.form.get("scenario_pv"),
            max_pv=request.form.get("max_pv"),
        )
        message = f"Maximum PV set to {result['max_sortie_pv']}"
        if result["above_adjusted"]:
            message += (
                f". Caution: this is above the difficulty-adjusted {result['adjusted_pv']} PV "
                f"for scenario PV {result['scenario_pv']}."
            )
        flash(message, "warning" if result["above_adjusted"] else "success")
    except (TypeError, ValueError) as exc:
        flash(_error_text(exc, "Invalid PV values"), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/force-commander", methods=["POST"])
def set_force_commander(id: int):  # noqa: A002
    try:
        aces_sortie_service.set_force_commander(id, int(request.form.get("pilot_id") or 0))
        flash("Force Commander saved", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid pilot", "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/fail", methods=["POST"])
def fail_sortie(id: int):  # noqa: A002
    try:
        aces_sortie_service.fail_sortie(id, request.form.get("notes"))
        flash("Sortie recorded as failed. It must be replayed.", "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/replay", methods=["POST"])
def replay_sortie(id: int):  # noqa: A002
    try:
        replay = aces_sortie_service.create_replay(id)
        flash(f"{replay.attempt_label} created from the failed attempt", "success")
        return redirect(url_for("contracts.sortie_detail", id=replay.id))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/keywords", methods=["POST"])
def story_keyword(id: int):  # noqa: A002
    try:
        aces_sortie_service.record_story_keyword(
            id,
            request.form.get("keyword", ""),
            request.form.get("action") or "acquired",
        )
        flash("Story Keyword recorded", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


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


@bp.route("/sorties/<int:id>/after-action", methods=["POST"])
def apply_after_action(id: int):  # noqa: A002
    sortie = contract_service.get_sortie_by_id(id)
    if not sortie:
        flash("Sortie not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    try:
        unit_results = []
        for unit in sortie.units:
            unit_results.append(
                {
                    "sortie_unit_id": unit.id,
                    "damage_outcome": request.form.get(f"damage_outcome_{unit.id}") or "none",
                    "pilot_wounded": str(request.form.get(f"pilot_wounded_{unit.id}") or "").lower()
                    in {"1", "true", "on", "yes"},
                    "pilot_killed": str(request.form.get(f"pilot_killed_{unit.id}") or "").lower()
                    in {"1", "true", "on", "yes"},
                }
            )
        after_action_service.apply_after_action(
            id,
            unit_results,
            outcome=request.form.get("outcome") or None,
            objectives_summary=request.form.get("objectives_summary"),
            combat_pay=int(request.form.get("combat_pay") or 0),
            salvage_notes=request.form.get("salvage_notes"),
            salvage_wp=int(request.form.get("salvage_wp") or 0),
            mvp_pilot_id=_optional_int(request.form.get("mvp_pilot_id")),
            after_action_notes=request.form.get("after_action_notes"),
        )
        flash("After Action applied", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid After Action values", "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


def _keyword_lines(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").replace(",", "\n").splitlines() if part.strip()]


def _checked(name: str) -> bool:
    return str(request.form.get(name) or "").lower() in {"1", "true", "on", "yes"}


def _aces_inputs(sortie_id: int) -> dict:
    sortie = contract_service.get_sortie_by_id(sortie_id)
    if not sortie:
        raise ValueError("Sortie not found")
    return {
        "unit_results": [
            {
                "sortie_unit_id": unit.id,
                "damage_outcome": request.form.get(f"damage_outcome_{unit.id}") or "none",
                "pilot_wounded": _checked(f"pilot_wounded_{unit.id}"),
                "pilot_killed": _checked(f"pilot_killed_{unit.id}"),
                "generic_crew_lost": _checked(f"generic_crew_lost_{unit.id}"),
            }
            for unit in sortie.units
        ],
        "primary_objective_sp": request.form.get("primary_objective_sp"),
        "secondary_objective_sp": request.form.get("secondary_objective_sp"),
        "other_income": request.form.get("other_income"),
        "waypoint": request.form.get("waypoint"),
        "other_expense": request.form.get("other_expense"),
        "max_pilot_sp": request.form.get("max_pilot_sp"),
        "mvp_pilot_id": _optional_int(request.form.get("mvp_pilot_id")),
        "keywords_gained": _keyword_lines(request.form.get("keywords_gained")),
        "keywords_removed": _keyword_lines(request.form.get("keywords_removed")),
        "story_notes": request.form.get("story_notes"),
        "after_action_notes": request.form.get("after_action_notes"),
    }


@bp.route("/sorties/<int:id>/aces-after-action", methods=["POST"])
def apply_aces_after_action(id: int):  # noqa: A002
    try:
        aces_after_action_service.apply_aces_after_action(id, _aces_inputs(id))
        flash("After-Sortie applied. Allocate each pilot's improvement SP next.", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid After-Sortie values", "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/aces-preview", methods=["POST"])
def preview_aces_after_action(id: int):  # noqa: A002
    try:
        data = aces_after_action_service.preview_aces_after_action(id, _aces_inputs(id))
        return jsonify({"success": True, "error": None, "data": data}), 200
    except (TypeError, ValueError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Invalid After-Sortie values"
        return jsonify({"success": False, "error": message, "data": None}), 400


@bp.route("/sorties/<int:id>/pilot-share/<int:pilot_id>", methods=["POST"])
def allocate_pilot_share(id: int, pilot_id: int):  # noqa: A002
    try:
        aces_after_action_service.allocate_pilot_share(
            id,
            pilot_id,
            skill_sp=int(request.form.get("skill_sp") or 0),
            edge_sp=int(request.form.get("edge_sp") or 0),
            ability_sp=int(request.form.get("ability_sp") or 0),
            abilities=[a for a in request.form.getlist("abilities") if a],
        )
        flash("Pilot improvement recorded", "success")
    except (TypeError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Invalid allocation", "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/finalize", methods=["POST"])
def finalize_aces_sortie(id: int):  # noqa: A002
    try:
        aces_after_action_service.finalize_aces_sortie(id, request.form.get("next_steps"))
        flash("Sortie Report finalized", "success")
        return redirect(url_for("contracts.sortie_report", id=id))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("contracts.sortie_detail", id=id))


@bp.route("/sorties/<int:id>/report")
def sortie_report(id: int):  # noqa: A002
    data = aces_after_action_service.get_sortie_report(id)
    if not data:
        flash("Sortie Report not found", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    return render_template("sorties/report.html", **data)


@bp.route("/sorties/<int:id>/close", methods=["POST"])
def close_sortie(id: int):  # noqa: A002
    try:
        after_action_service.close_sortie(id)
        flash("Sortie closed", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("contracts.sortie_detail", id=id))
