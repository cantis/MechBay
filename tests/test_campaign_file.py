"""Saving a whole campaign to a .mbcampaign file and loading it back."""

from __future__ import annotations

import copy
import io
import json
from unittest.mock import patch

import pytest

from app.extensions import session_scope
from app.models.campaign import Campaign
from app.models.campaign_pilot import CampaignPilot
from app.models.campaign_unit import CampaignUnit
from app.models.miniature import Miniature
from app.services import aces_after_action_service as svc
from app.services import (
    aces_recon_service as recon,
)
from app.services import (
    aces_sortie_service,
    campaign_file_service,
    campaign_service,
    contract_service,
    miniature_service,
)
from tests.conftest import apply_aces, finalize_aces, finish_aces
from tests.test_aces_after_sortie import _campaign, _fought

BOUGHT = {
    "Id": 7563,
    "Name": "Phoenix Hawk PHX-3PL",
    "Class": "Phoenix Hawk",
    "Variant": "PHX-3PL",
    "Tonnage": 45,
    "BFPointValue": 36,
    "Type": {"Id": 18, "Name": "BattleMech"},
}


def _rich_campaign(force_id):
    """An Aces campaign with history: a finalized Sortie, a failed one with a replay, trades."""
    campaign, (hawk, ghost) = _campaign(force_id, warchest=3000, difficulty="Veteran")
    with session_scope() as session:
        owner = session.get(Campaign, campaign.id)
        owner.mul_faction_id, owner.mul_era_id = 29, 14
        owner.notes = "Campaign notes survive"
    first, rows = _fought(campaign, {0: hawk}, recon=[("Scout", 12)], units=(0, 1))
    aces_sortie_service.record_story_keyword(first.id, "Betrayal")
    flags = {rows[0].id: {"pilot_wounded": True}}
    finish_aces(first.id, "structure", flags, primary_objective_sp=800, max_pilot_sp=60)

    with patch("app.services.campaign_service.mul_service.find_unit_in_search_results") as find:
        find.return_value = BOUGHT
        campaign_service.purchase_campaign_unit(campaign.id, 7563, search_name="Phoenix Hawk")

    second = campaign_service.create_aces_sortie(campaign.id, "Second", scenario_pv=100)
    row = contract_service.add_unit_to_sortie(second.id, campaign.units[1].id)
    contract_service.assign_sortie_pilot(row.id, ghost.id)
    aces_sortie_service.set_force_commander(second.id, ghost.id)
    recon.add_recon_action(second.id, "Probe", campaign_unit_id=campaign.units[1].id, sp_cost=5)
    contract_service.mark_sortie_ready(second.id)
    aces_sortie_service.fail_sortie(second.id, "Lost it")
    aces_sortie_service.create_replay(second.id)
    return campaign_service.get_campaign_by_id(campaign.id), first, second


def _counts(data):
    return {name: len(rows) for name, rows in data["tables"].items()}


def _import(data, **kwargs):
    return campaign_file_service.import_campaign(copy.deepcopy(data), **kwargs)


# --- round trip ----------------------------------------------------------------------------


def test_export_is_plain_json_with_a_clear_header(client, minimal_force):
    campaign, _, _ = _rich_campaign(minimal_force)
    data = campaign_file_service.export_campaign(campaign.id)
    assert data["type"] == "campaign" and data["schema_version"] == 1
    assert data["ruleset"] == "aces" and data["campaign_name"] == campaign.name
    json.dumps(data)  # fully serializable (dates included)
    counts = _counts(data)
    assert counts["campaigns"] == 1 and counts["campaign_units"] == 3
    assert counts["sorties"] == 3  # played, failed, replay
    assert counts["aces_sortie_reports"] == 1 and counts["story_keyword_events"] == 1
    assert counts["sortie_recon_actions"] == 2 and counts["warchest_transactions"] > 5


def test_full_round_trip_restores_everything(client, minimal_force):
    campaign, first, second = _rich_campaign(minimal_force)
    original = campaign_file_service.export_campaign(campaign.id)
    balance = campaign.warchest_balance
    pilots = {
        p.callsign: (p.alpha_strike_skill, p.total_sp_earned, p.mvp_count, p.wounds)
        for p in campaign.pilots
    }
    campaign_service.delete_campaign(campaign.id)
    assert campaign_service.get_all_campaigns() == []

    result = _import(original)
    loaded = campaign_service.get_campaign_by_id(result["campaign_id"])
    assert loaded.name == campaign.name and loaded.is_active is True
    assert (loaded.ruleset, loaded.difficulty, loaded.notes) == (
        "aces",
        "Veteran",
        "Campaign notes survive",
    )
    assert loaded.warchest_balance == balance
    assert {
        p.callsign: (p.alpha_strike_skill, p.total_sp_earned, p.mvp_count, p.wounds)
        for p in loaded.pilots
    } == pilots

    again = campaign_file_service.export_campaign(loaded.id)
    assert _counts(again) == _counts(original)

    # Key values come back unchanged.
    report_before = original["tables"]["aces_sortie_reports"][0]
    report_after = again["tables"]["aces_sortie_reports"][0]
    for key in (
        "earnings",
        "total_income",
        "total_expenses",
        "warchest_before",
        "warchest_after_accounting",
        "force_pv",
        "expense_reconnaissance",
        "finalized",
    ):
        assert report_after[key] == report_before[key], key
    assert [t["actual_amount"] for t in again["tables"]["warchest_transactions"]] == [
        t["actual_amount"] for t in original["tables"]["warchest_transactions"]
    ]
    assert [t["resulting_balance"] for t in again["tables"]["warchest_transactions"]] == [
        t["resulting_balance"] for t in original["tables"]["warchest_transactions"]
    ]
    assert [s["max_sortie_pv"] for s in again["tables"]["sorties"]] == [
        s["max_sortie_pv"] for s in original["tables"]["sorties"]
    ]
    assert aces_sortie_service.get_current_keywords(loaded.id) == ["Betrayal"]
    assert [
        a.name
        for a in recon.list_recon_actions(aces_sortie_service.list_aces_sorties(loaded.id)[0]["id"])
    ] == ["Scout"]
    assert result["counts"]["sorties"] == 3


def test_every_link_points_at_the_new_campaigns_own_rows(client, minimal_force):
    campaign, _, _ = _rich_campaign(minimal_force)
    original = campaign_file_service.export_campaign(campaign.id)
    result = _import(original)  # the original stays: both exist at once
    new = campaign_file_service.export_campaign(result["campaign_id"])
    assert result["campaign_id"] != campaign.id

    def ids(data, table):
        return {row["id"] for row in data["tables"][table]}

    assert ids(new, "sorties").isdisjoint(ids(original, "sorties"))
    assert ids(new, "campaign_units").isdisjoint(ids(original, "campaign_units"))
    tables = new["tables"]
    new_units, new_pilots = ids(new, "campaign_units"), ids(new, "campaign_pilots")
    new_sorties, new_lances = ids(new, "sorties"), ids(new, "campaign_lances")
    new_events = ids(new, "pilot_advancement_events")
    assert all(r["campaign_id"] == result["campaign_id"] for r in tables["campaign_units"])
    for row in tables["sortie_units"]:
        assert row["sortie_id"] in new_sorties
        assert row["campaign_unit_id"] in new_units
        assert row["campaign_pilot_id"] is None or row["campaign_pilot_id"] in new_pilots
        assert row["campaign_lance_id"] is None or row["campaign_lance_id"] in new_lances
    for row in tables["sorties"]:
        for key in ("mvp_pilot_id", "force_commander_pilot_id"):
            assert row[key] is None or row[key] in new_pilots
        assert row["replay_of_sortie_id"] is None or row["replay_of_sortie_id"] in new_sorties
    assert any(r["replay_of_sortie_id"] for r in tables["sorties"])  # the replay link survived
    for row in tables["sortie_pilot_shares"]:
        assert row["campaign_pilot_id"] in new_pilots
        assert row["advancement_event_id"] is None or row["advancement_event_id"] in new_events
    for row in tables["sortie_recon_actions"]:
        assert row["campaign_unit_id"] is None or row["campaign_unit_id"] in new_units
    # Ledger entries point at the right kind of new row.
    repair_ids = ids(new, "repair_orders")
    for tx in tables["warchest_transactions"]:
        if tx["related_entity_type"] == "repair_order":
            assert tx["related_entity_id"] in repair_ids
        if tx["related_entity_type"] == "campaign_unit":
            assert tx["related_entity_id"] in new_units
        if tx["related_entity_type"] == "sortie":
            assert tx["related_entity_id"] in new_sorties


def test_loading_next_to_the_original_does_not_cross_wires(client, minimal_force):
    campaign, first, _ = _rich_campaign(minimal_force)
    original = campaign_file_service.export_campaign(campaign.id)
    result = _import(original)
    copy_campaign = campaign_service.get_campaign_by_id(result["campaign_id"])
    assert copy_campaign.name == f"{campaign.name} (imported)"
    assert (
        copy_campaign.is_active and not campaign_service.get_campaign_by_id(campaign.id).is_active
    )

    before = campaign_service.get_campaign_by_id(campaign.id).warchest_balance
    campaign_service.add_warchest_transaction(
        copy_campaign.id,
        transaction_type="adjustment",
        description="Only the copy",
        actual_amount=77,
    )
    assert campaign_service.get_campaign_by_id(campaign.id).warchest_balance == before
    assert campaign_service.get_campaign_by_id(copy_campaign.id).warchest_balance == before + 77

    second_copy = _import(original)
    assert campaign_service.get_campaign_by_id(second_copy["campaign_id"]).name.endswith(
        "(imported 2)"
    )


def test_a_half_finished_after_sortie_can_be_finished_after_loading(client, minimal_force):
    """The pending ledger inside the report must be remapped to the loaded copy's own rows."""
    campaign, (hawk, _) = _campaign(minimal_force, warchest=1000)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "crippled", primary_objective_sp=900, max_pilot_sp=0)
    data = campaign_file_service.export_campaign(campaign.id)
    original_balance = campaign_service.get_campaign_by_id(campaign.id).warchest_balance

    result = _import(data)
    loaded_sortie = aces_sortie_service.list_aces_sorties(result["campaign_id"])[0]
    assert loaded_sortie["status"] == "after_action"
    finalize_aces(loaded_sortie["id"])

    loaded = campaign_service.get_campaign_by_id(result["campaign_id"])
    report = svc.get_sortie_report(loaded_sortie["id"])["report"]
    assert loaded.warchest_balance == original_balance + report.earnings
    assert loaded.units[0].condition == "active"  # its own repair order was completed
    repairs = [t for t in loaded.transactions if t.transaction_type == "repair"]
    assert len(repairs) == 1 and repairs[0].related_entity_type == "repair_order"
    # The original campaign is still waiting, untouched.
    assert campaign_service.get_campaign_by_id(campaign.id).warchest_balance == original_balance
    assert contract_service.get_sortie_by_id(sortie.id).status == "after_action"


def test_chaos_campaign_round_trip(client, minimal_force):
    chaos = campaign_service.create_campaign_from_force(
        minimal_force,
        "Chaos run",
        starting_bt_year=3151,
        starting_bt_month=4,
        current_location="Galatea",
    )
    contract = contract_service.create_contract(chaos.id, "Garrison duty", scale=2)
    data = campaign_file_service.export_campaign(chaos.id)
    campaign_service.delete_campaign(chaos.id)
    result = _import(data)
    loaded = campaign_service.get_campaign_by_id(result["campaign_id"])
    assert (loaded.ruleset, loaded.starting_bt_year, loaded.starting_bt_month) == ("chaos", 3151, 4)
    assert (loaded.current_location, loaded.current_campaign_month) == ("Galatea", 1)
    [loaded_contract] = contract_service.get_contracts_for_campaign(loaded.id)
    assert loaded_contract.name == contract.name and loaded_contract.scale == 2
    assert loaded_contract.campaign_id == loaded.id


# --- miniatures ----------------------------------------------------------------------------


def test_units_relink_to_inventory_miniatures(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    links = {u.chassis: u.miniature_id for u in campaign.units}
    assert all(links.values())
    data = campaign_file_service.export_campaign(campaign.id)
    campaign_service.delete_campaign(campaign.id)
    result = _import(data)
    loaded = campaign_service.get_campaign_by_id(result["campaign_id"])
    assert {u.chassis: u.miniature_id for u in loaded.units} == links
    assert not any(u.miniature_missing for u in loaded.units)
    assert result["missing_miniatures"] == 0


def test_units_without_a_matching_miniature_are_kept_and_flagged(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    data = campaign_file_service.export_campaign(campaign.id)
    gone = [u.miniature_id for u in campaign.units]
    campaign_service.delete_campaign(campaign.id)
    for miniature_id in gone:
        assert miniature_service.delete_miniature(miniature_id)
    with session_scope() as session:
        assert session.query(Miniature).filter(Miniature.id.in_(gone)).count() == 0

    result = _import(data)
    loaded = campaign_service.get_campaign_by_id(result["campaign_id"])
    assert len(loaded.units) == len(gone)
    assert all(u.miniature_id is None and u.miniature_missing for u in loaded.units)
    assert result["missing_miniatures"] == len(gone)


# --- bad files -----------------------------------------------------------------------------


def test_bad_files_are_rejected_and_change_nothing(client, minimal_force):
    campaign, _, _ = _rich_campaign(minimal_force)
    good = campaign_file_service.export_campaign(campaign.id)
    rows_before = _counts(good)

    def broken(mutate):
        data = copy.deepcopy(good)
        mutate(data)
        return data

    bad = [
        ("not a mapping", ["a", "list"], "not a MechBay campaign file"),
        ("wrong type", broken(lambda d: d.update(type="inventory")), "not a MechBay campaign file"),
        ("no version", broken(lambda d: d.pop("schema_version")), "no valid version"),
        ("newer version", broken(lambda d: d.update(schema_version=99)), "newer version"),
        ("no tables", broken(lambda d: d.update(tables=None)), "no data"),
        (
            "two campaigns",
            broken(
                lambda d: d["tables"]["campaigns"].append(dict(d["tables"]["campaigns"][0], id=99))
            ),
            "exactly one campaign",
        ),
        (
            "row without id",
            broken(lambda d: d["tables"]["campaign_units"][0].pop("id")),
            "without an id",
        ),
        (
            "row not an object",
            broken(lambda d: d["tables"]["sorties"].append("x")),
            "invalid sorties",
        ),
        (
            "dangling link",
            broken(lambda d: d["tables"]["sortie_units"][0].update(sortie_id=12345)),
            "damaged",
        ),
        (
            "bad date",
            broken(lambda d: d["tables"]["sorties"][0].update(date_played="not-a-date")),
            "invalid date",
        ),
        (
            "missing required data",
            broken(lambda d: d["tables"]["campaign_units"][0].pop("chassis")),
            "invalid campaign_units data",
        ),
    ]
    for label, payload, message in bad:
        with pytest.raises(ValueError, match=message):
            campaign_file_service.import_campaign(payload)
        assert len(campaign_service.get_all_campaigns()) == 1, label  # nothing half-imported
    with session_scope() as session:
        assert session.query(CampaignUnit).count() == rows_before["campaign_units"]
        assert session.query(CampaignPilot).count() == rows_before["campaign_pilots"]


def test_unknown_extra_columns_and_tables_are_ignored(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    data = campaign_file_service.export_campaign(campaign.id)
    data["tables"]["campaign_units"][0]["future_column"] = "from a later version"
    data["tables"]["something_new"] = [{"id": 1}]
    assert _import(data)["counts"]["campaign_units"] == 2


# --- routes and screens --------------------------------------------------------------------


def test_save_route_downloads_a_mbcampaign_file(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    resp = client.get(f"/files/campaign/{campaign.id}/export")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    disposition = resp.headers["Content-Disposition"]
    assert "attachment" in disposition and ".mbcampaign" in disposition
    payload = json.loads(resp.data)
    assert payload["type"] == "campaign" and payload["campaign_name"] == campaign.name
    missing = client.get("/files/campaign/9999/export", follow_redirects=True)
    assert b"Campaign not found" in missing.data


def test_load_route_creates_the_campaign_and_opens_it(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    body = client.get(f"/files/campaign/{campaign.id}/export").data
    campaign_service.delete_campaign(campaign.id)

    resp = client.post(
        "/files/upload/campaign",
        data={"file": (io.BytesIO(body), "mine.mbcampaign")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Loaded campaign" in resp.data and campaign.name.encode() in resp.data
    [loaded] = campaign_service.get_all_campaigns()
    assert loaded.name == campaign.name and len(loaded.units) == 2


def test_load_route_via_the_file_menu_returns_a_redirect(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    body = client.get(f"/files/campaign/{campaign.id}/export").data
    resp = client.post(
        "/files/upload/campaign",
        data={"file": (io.BytesIO(body), "x.mbcampaign")},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    payload = resp.get_json()
    assert resp.status_code == 200 and payload["redirect"].startswith("/campaigns/")


def test_load_route_reports_bad_files(client, minimal_force):
    for name, content, message in (
        ("empty", b"", b"not valid JSON"),
        ("junk", b"not json at all", b"not valid JSON"),
        ("wrong", json.dumps({"type": "force"}).encode(), b"not a MechBay campaign file"),
    ):
        resp = client.post(
            "/files/upload/campaign",
            data={"file": (io.BytesIO(content), f"{name}.mbcampaign")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert message in resp.data, name
    nothing = client.post("/files/upload/campaign", data={}, follow_redirects=True)
    assert b"No file selected" in nothing.data
    assert campaign_service.get_all_campaigns() == []


def test_screens_offer_save_and_load(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    detail = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert f"/files/campaign/{campaign.id}/export" in detail and "Save to file" in detail
    listing = client.get("/campaigns").data.decode()
    assert "/files/upload/campaign" in listing and "Load from file" in listing
    assert "Open campaign (upload)" in listing  # File menu entry
    assert "openCampaignUpload" in client.get("/static/js/files.js").data.decode()


def test_deleting_a_campaign_leaves_no_rows_behind(client, minimal_force):
    from app.extensions import Base

    campaign, _, _ = _rich_campaign(minimal_force)
    campaign_service.delete_campaign(campaign.id)
    from app import models  # noqa: F401

    leftovers = {}
    with session_scope() as session:
        for name in campaign_file_service.TABLE_ORDER:
            model = next(m.class_ for m in Base.registry.mappers if m.class_.__table__.name == name)
            count = session.query(model).count()
            if count:
                leftovers[name] = count
    assert leftovers == {}
