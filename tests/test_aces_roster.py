"""Aces roster: compact list on the campaign page, drag-and-drop Roster page."""

from __future__ import annotations

import pytest

from app.extensions import session_scope
from app.models.campaign_unit import CampaignUnit
from app.models.sortie import Sortie
from app.services import campaign_service
from tests.test_aces_after_sortie import _campaign


def _two_lances(campaign):
    second = campaign_service.add_campaign_lance(campaign.id, "Bravo Lance")
    return campaign_service.get_campaign_by_id(campaign.id), second


def _move(client, campaign_id, unit_id, lance_id, ordered):
    return client.post(
        f"/campaigns/{campaign_id}/roster/move",
        json={"unit_id": unit_id, "lance_id": lance_id, "ordered_ids": ordered},
    )


# --- campaign page: compact list -----------------------------------------------------------


def test_campaign_page_roster_is_a_compact_list_with_points(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    card = page[page.index('id="rosterSummary"') : page.index('id="acesPilots"')]
    for unit in campaign.units:
        assert unit.chassis in card
    assert "Manage Roster" in card
    assert f"/campaigns/{campaign.id}/roster" in card
    assert "2 units" in card and "80 PV" in card
    for management in ("Save lance", "Add lance", "Add miniature", "Retire", "Remove"):
        assert management not in card, management
    assert "Save lance" not in page and "Add miniature" not in page


def test_compact_list_leaves_out_units_that_are_out_of_service(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    with session_scope() as session:
        session.get(CampaignUnit, campaign.units[1].id).condition = "retired"
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    card = page[page.index('id="rosterSummary"') : page.index('id="acesPilots"')]
    assert "1 unit" in card and "40 PV" in card
    assert "80 PV" not in card


# --- roster page ---------------------------------------------------------------------------


def test_roster_page_shows_lances_totals_and_management_forms(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign, bravo = _two_lances(campaign)
    page = client.get(f"/campaigns/{campaign.id}/roster").data.decode()
    assert "Bravo Lance" in page and "No lance" in page
    assert 'id="rosterTotalPv">80<' in page
    assert "roster.js" in page and "Sortable" in page
    for form in ("Add a lance", "Add a miniature", "Edit lance"):
        assert form in page
    assert 'name="return_to" value="roster"' in page
    assert "Back to Campaign" in page


def test_roster_page_lists_retired_units_separately(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    with session_scope() as session:
        session.get(CampaignUnit, campaign.units[1].id).condition = "retired"
    page = client.get(f"/campaigns/{campaign.id}/roster").data.decode()
    assert "Out of service" in page
    assert 'id="rosterTotalPv">40<' in page  # only the unit still in service counts


# --- drag and drop endpoint ----------------------------------------------------------------


def test_moving_a_unit_to_another_lance_and_order(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign, bravo = _two_lances(campaign)
    first, second = campaign.units[0].id, campaign.units[1].id

    resp = _move(client, campaign.id, second, bravo.id, [second])
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True and body["error"] is None

    units = {u.id: u for u in campaign_service.get_campaign_by_id(campaign.id).units}
    assert units[second].campaign_lance_id == bravo.id
    assert units[first].campaign_lance_id != bravo.id

    # Drag it back above the other unit: order within the lance follows the new list.
    home = units[first].campaign_lance_id
    assert _move(client, campaign.id, second, home, [second, first]).status_code == 200
    units = {u.id: u for u in campaign_service.get_campaign_by_id(campaign.id).units}
    assert units[second].campaign_lance_id == home
    assert (units[second].order, units[first].order) == (0, 1)


def test_unit_can_leave_all_lances(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    unit_id = campaign.units[0].id
    assert _move(client, campaign.id, unit_id, None, [unit_id]).status_code == 200
    moved = {u.id: u for u in campaign_service.get_campaign_by_id(campaign.id).units}[unit_id]
    assert moved.campaign_lance_id is None
    page = client.get(f"/campaigns/{campaign.id}/roster").data.decode()
    no_lance = page[page.index("No lance</h5>") :]
    assert moved.chassis in no_lance


def test_move_rejects_bad_requests(client, minimal_force, multiple_forces):
    campaign, _ = _campaign(minimal_force)
    unit_id = campaign.units[0].id
    other = campaign_service.create_campaign_from_force(
        multiple_forces["Jade Falcon Strikers"],
        "Elsewhere",
        starting_bt_year=3151,
        starting_bt_month=1,
    )
    foreign_lance = other.lances[0].id
    foreign_unit = other.units[0].id

    bad_requests = [
        {"unit_id": "x", "lance_id": None, "ordered_ids": [1]},  # not a number
        {"unit_id": unit_id, "lance_id": None, "ordered_ids": []},  # order must list the unit
        {"unit_id": unit_id, "lance_id": foreign_lance, "ordered_ids": [unit_id]},  # other campaign
        {"unit_id": unit_id, "lance_id": None, "ordered_ids": [unit_id, foreign_unit]},
        {"unit_id": unit_id, "lance_id": None, "ordered_ids": [unit_id, unit_id]},
    ]
    for payload in bad_requests:
        resp = client.post(f"/campaigns/{campaign.id}/roster/move", json=payload)
        assert resp.status_code == 400, payload
        body = resp.get_json()
        assert body["success"] is False and body["error"]
    missing = client.post("/campaigns/9999/roster/move", json={})
    assert missing.status_code == 404 and missing.get_json()["success"] is False


def test_organising_the_roster_is_allowed_while_a_sortie_is_in_progress(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign, bravo = _two_lances(campaign)
    with session_scope() as session:
        session.add(Sortie(campaign_id=campaign.id, name="Live", status="fought"))
    unit_id = campaign.units[0].id
    assert _move(client, campaign.id, unit_id, bravo.id, [unit_id]).status_code == 200


def test_service_validates_the_move(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    unit_id = campaign.units[0].id
    with pytest.raises(ValueError, match="not part of this campaign"):
        campaign_service.move_campaign_unit(campaign.id, 9999, None, [9999])
    with pytest.raises(ValueError, match="Lance not found"):
        campaign_service.move_campaign_unit(campaign.id, unit_id, 9999, [unit_id])


# --- actions started on the roster page come back to it ------------------------------------


def test_roster_actions_return_to_the_roster_page(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    roster_url = f"/campaigns/{campaign.id}/roster"
    unit_id = campaign.units[1].id

    added = client.post(
        f"/campaigns/{campaign.id}/lances", data={"name": "Charlie", "return_to": "roster"}
    )
    assert added.headers["Location"].endswith(roster_url)
    renamed = client.post(
        f"/campaigns/lances/{campaign.lances[0].id}/update",
        data={"name": "Alpha 2", "campaign_id": str(campaign.id), "return_to": "roster"},
    )
    assert renamed.headers["Location"].endswith(roster_url)
    sold = client.post(
        f"/campaigns/{campaign.id}/units/{unit_id}/sell", data={"return_to": "roster"}
    )
    assert sold.headers["Location"].endswith(roster_url)
    retired = client.post(
        f"/campaigns/units/{campaign.units[0].id}/retire",
        data={"campaign_id": str(campaign.id), "return_to": "roster"},
    )
    assert retired.headers["Location"].endswith(roster_url)
    removed = client.post(
        f"/campaigns/units/{unit_id}/delete",
        data={"campaign_id": str(campaign.id), "return_to": "roster"},
    )
    assert removed.headers["Location"].endswith(roster_url)

    # Without return_to the campaign page is still where they go.
    plain = client.post(f"/campaigns/{campaign.id}/lances", data={"name": "Delta"})
    assert plain.headers["Location"].endswith(f"/campaigns/{campaign.id}")


# --- Chaos is untouched --------------------------------------------------------------------


def test_chaos_campaign_page_keeps_its_full_roster_card(client, minimal_force):
    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    page = client.get(f"/campaigns/{chaos.id}").data.decode()
    assert "Save lance" in page and "Add lance" in page and "Add miniature" in page
    assert 'id="rosterSummary"' not in page
    assert client.get(f"/campaigns/{chaos.id}/roster").status_code == 200


# --- deleting an empty lance ---------------------------------------------------------------


def test_empty_lance_can_be_deleted(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign, bravo = _two_lances(campaign)
    deleted = campaign_service.delete_campaign_lance(bravo.id)
    assert deleted.name == "Bravo Lance"
    remaining = campaign_service.get_campaign_by_id(campaign.id)
    assert [lance.name for lance in remaining.lances] == [campaign.lances[0].name]


def test_lance_with_units_cannot_be_deleted(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    lance = campaign.lances[0]
    with pytest.raises(ValueError, match="Move them to another lance first"):
        campaign_service.delete_campaign_lance(lance.id)
    assert len(campaign_service.get_campaign_by_id(campaign.id).lances) == 1
    with pytest.raises(ValueError, match="Lance not found"):
        campaign_service.delete_campaign_lance(9999)


def test_retired_units_are_kept_but_unlinked_when_their_lance_is_deleted(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign, bravo = _two_lances(campaign)
    retired_id = campaign.units[0].id
    assert _move(client, campaign.id, retired_id, bravo.id, [retired_id]).status_code == 200
    with session_scope() as session:
        session.get(CampaignUnit, retired_id).condition = "retired"
    campaign_service.delete_campaign_lance(bravo.id)
    units = {u.id: u for u in campaign_service.get_campaign_by_id(campaign.id).units}
    assert units[retired_id].condition == "retired"  # history kept
    assert units[retired_id].campaign_lance_id is None


def test_delete_lance_route_and_button_state(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    campaign, bravo = _two_lances(campaign)
    page = client.get(f"/campaigns/{campaign.id}/roster").data.decode()
    assert page.count("Delete lance") == 2  # one per real lance, none for "No lance"
    full = page[page.index(campaign.lances[0].name) :]
    assert "disabled" in full[full.index("Delete lance") - 200 : full.index("Delete lance")]

    resp = client.post(
        f"/campaigns/lances/{bravo.id}/delete",
        data={"campaign_id": str(campaign.id), "return_to": "roster"},
    )
    assert resp.headers["Location"].endswith(f"/campaigns/{campaign.id}/roster")
    after = client.get(f"/campaigns/{campaign.id}/roster").data.decode()
    assert after.count("Delete lance") == 1  # only the original lance is left
    assert '<h5 class="mb-0">Bravo Lance</h5>' not in after  # its card is gone

    blocked = client.post(
        f"/campaigns/lances/{campaign.lances[0].id}/delete",
        data={"campaign_id": str(campaign.id), "return_to": "roster"},
        follow_redirects=True,
    )
    assert b"Move them to another lance first" in blocked.data
