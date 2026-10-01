"""Smoke tests that Aces and Chaos campaign templates render without Jinja errors."""

from __future__ import annotations

from app.services import campaign_service


def _create(force_id, **kwargs):
    kwargs.setdefault("starting_bt_year", 3151)
    kwargs.setdefault("starting_bt_month", 1)
    return campaign_service.create_campaign_from_force(force_id, **kwargs)


def test_chaos_campaign_detail_renders(client, minimal_force):
    campaign = _create(minimal_force, name="Chaos Smoke")
    resp = client.get(f"/campaigns/{campaign.id}")
    assert resp.status_code == 200
    assert b"Contracts" in resp.data
    assert b"Player Force" not in resp.data


def test_aces_campaign_detail_renders(client, minimal_force):
    campaign = _create(minimal_force, name="Aces Smoke", ruleset="aces", difficulty="veteran")
    resp = client.get(f"/campaigns/{campaign.id}")
    assert resp.status_code == 200
    assert b"Player Force" in resp.data
    assert b"Campaign Log" in resp.data
    assert b"Contracts" not in resp.data


def test_campaign_list_renders_with_ruleset_select(client, minimal_force):
    resp = client.get("/campaigns")
    assert resp.status_code == 200
    assert b"campaignRulesetSelect" in resp.data


def test_aces_sortie_detail_renders(client, minimal_force):
    campaign = _create(minimal_force, name="Aces Sortie Smoke", ruleset="aces")
    from app.extensions import session_scope
    from app.models.campaign_unit import CampaignUnit

    with session_scope() as session:
        units = session.query(CampaignUnit).filter_by(campaign_id=campaign.id).all()
        for unit in units:
            unit.point_value = 40
            unit.tonnage = 70

    sortie = campaign_service.create_aces_sortie(campaign.id, "Waypoint 1")
    from app.services import contract_service
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)

    resp = client.get(f"/sorties/{sortie.id}")
    assert resp.status_code == 200
    assert b"Direct Campaign Sortie" in resp.data
    assert b"Back to Campaign" in resp.data

    ready = client.post(f"/sorties/{sortie.id}/ready", follow_redirects=True)
    assert ready.status_code == 200
    assert b"ready" in ready.data.lower()


def test_aces_full_sortie_and_purchase_flow_via_routes(client, minimal_force):
    from unittest.mock import patch

    from app.extensions import session_scope
    from app.models.alpha_strike_force import AlphaStrikeForce
    from app.models.campaign_unit import CampaignUnit
    from app.services import contract_service

    with session_scope() as session:
        session.add(
            AlphaStrikeForce(
                force_id=minimal_force,
                mul_faction_id=29,
                mul_era_id=14,
                faction_name="Clan Wolf",
                era_name="ilClan",
            )
        )
    campaign = _create(minimal_force, name="Aces Flow", ruleset="aces", opening_warchest=5000)
    with session_scope() as session:
        units = session.query(CampaignUnit).filter_by(campaign_id=campaign.id).all()
        for unit in units:
            unit.point_value = 40
            unit.tonnage = 70

    sortie = campaign_service.create_aces_sortie(campaign.id, "Waypoint 1")
    contract_service.add_unit_to_sortie(sortie.id, campaign.units[0].id)
    contract_service.mark_sortie_ready(sortie.id)
    contract_service.mark_sortie_fought(sortie.id)

    sortie_unit_id = contract_service.get_sortie_by_id(sortie.id).units[0].id
    aa = client.post(
        f"/sorties/{sortie.id}/after-action",
        data={f"damage_outcome_{sortie_unit_id}": "structure", "outcome": "victory"},
        follow_redirects=True,
    )
    assert aa.status_code == 200

    detail = client.get(f"/campaigns/{campaign.id}")
    assert detail.status_code == 200
    assert b"Repair" in detail.data or b"repair" in detail.data

    with patch(
        "app.services.campaign_service.mul_service.find_unit_in_search_results"
    ) as mock_find:
        mock_find.return_value = {
            "Id": 7563,
            "Name": "Warhammer WHM-8R",
            "Class": "Warhammer",
            "Variant": "WHM-8R",
            "Tonnage": 70,
            "BFPointValue": 40,
            "Type": {"Id": 18, "Name": "BattleMech"},
        }
        purchase = client.post(
            f"/campaigns/{campaign.id}/purchase-unit",
            data={"mul_unit_id": "7563", "search_name": "Warhammer"},
            follow_redirects=True,
        )
    assert purchase.status_code == 200
    assert b"Purchased" in purchase.data

    reloaded = campaign_service.get_campaign_by_id(campaign.id)
    assert len(reloaded.units) == 3  # 2 seeded + 1 purchased
    purchased = next(u for u in reloaded.units if u.miniature_id is None)
    assert purchased.point_value == 40

    retire = client.post(
        f"/campaigns/units/{purchased.id}/retire",
        data={"campaign_id": str(campaign.id)},
        follow_redirects=True,
    )
    assert retire.status_code == 200
    assert b"retired" in retire.data.lower()
