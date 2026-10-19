"""Aces campaigns are Sortie-based: no calendar, location, month or Contract (addendum)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import extensions
from app.extensions import Base, session_scope
from app.models.campaign import Campaign
from app.models.campaign_pilot import CampaignPilot
from app.models.damage_event import DamageEvent
from app.models.pilot_injury_event import PilotInjuryEvent
from app.models.repair_order import RepairOrder
from app.models.sortie import Sortie
from app.models.warchest_transaction import WarchestTransaction
from app.services import (
    aces_pilot_service,
    aces_sortie_service,
    campaign_service,
    contract_service,
)
from tests.conftest import apply_aces, finish_aces
from tests.test_aces_after_sortie import _campaign, _fought
from tests.test_aces_force_6d import _assign_all


def _plain_aces(force_id, **kwargs):
    return campaign_service.create_campaign_from_force(
        force_id, kwargs.pop("name", "Sortie Based"), ruleset="aces", **kwargs
    )


# --- creation ------------------------------------------------------------------------------


def test_aces_campaign_created_without_any_calendar_location_or_contract(client, minimal_force):
    campaign = _plain_aces(minimal_force)  # no year, month, location
    assert campaign.starting_bt_year is None
    assert campaign.starting_bt_month is None
    assert campaign.current_location is None
    assert campaign.current_campaign_month is None
    assert campaign.contracts == []
    assert campaign.travel_events == []
    [opening] = [t for t in campaign.transactions if t.transaction_type == "opening_balance"]
    assert opening.campaign_month is None


def test_aces_ignores_calendar_values_if_supplied(client, minimal_force):
    campaign = _plain_aces(
        minimal_force, starting_bt_year=3151, starting_bt_month=4, current_location="Galatea"
    )
    assert (campaign.starting_bt_year, campaign.starting_bt_month) == (None, None)
    assert campaign.current_location is None
    assert campaign.current_campaign_month is None


def test_chaos_still_requires_its_calendar(client, minimal_force):
    with pytest.raises(ValueError, match="Starting year is required"):
        campaign_service.create_campaign_from_force(minimal_force, "Chaos")
    with pytest.raises(ValueError, match="Starting month is required"):
        campaign_service.create_campaign_from_force(minimal_force, "Chaos", starting_bt_year=3151)
    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=4, current_location="Hall"
    )
    assert chaos.current_campaign_month == 1
    assert (chaos.starting_bt_year, chaos.starting_bt_month) == (3151, 4)
    assert chaos.current_location == "Hall"
    [opening] = [t for t in chaos.transactions if t.transaction_type == "opening_balance"]
    assert opening.campaign_month == 1


def test_aces_create_route_needs_no_calendar(client, realistic_force):
    _assign_all(realistic_force, 24)
    resp = client.post(
        "/campaigns/create",
        data={
            "name": "No Calendar Aces",
            "force_id": str(realistic_force),
            "ruleset": "aces",
            "difficulty": "Standard",
        },
        follow_redirects=True,
    )
    assert b"opening Warchest" in resp.data
    [campaign] = campaign_service.get_all_campaigns()
    assert campaign.starting_bt_year is None
    assert campaign.current_campaign_month is None
    assert campaign.current_location is None


def test_chaos_create_route_still_requires_calendar(client, minimal_force):
    resp = client.post(
        "/campaigns/create",
        data={"name": "Chaos", "force_id": str(minimal_force), "ruleset": "chaos"},
        follow_redirects=True,
    )
    assert b"Starting year and month are required" in resp.data
    assert campaign_service.get_all_campaigns() == []


def test_creation_form_hides_chaos_fields_for_aces_and_explains_pilots(client, minimal_force):
    page = client.get("/campaigns").data.decode()
    for label in ("Starting year *", "Starting month *", "Starting location"):
        index = page.index(label)
        assert 'data-ruleset-only="chaos"' in page[max(0, index - 900) : index]
    assert "pilots belong to a campaign" in page


# --- campaign UI ---------------------------------------------------------------------------


def test_aces_detail_shows_no_chaos_time_or_location_controls(client, minimal_force):
    campaign = _plain_aces(minimal_force)
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    for text_ in (
        "Starting year",
        "Starting month",
        "Campaign month",
        "Current location",
        "Travel",
        "Contract",
        "Advance Month",
        "Unknown",
    ):
        assert text_ not in page, text_
    for text_ in ("Story Keywords", "Sortie PV adjustment", "Named Pilots", "Warchest"):
        assert text_ in page


def test_chaos_detail_keeps_time_location_travel_and_contracts(client, minimal_force):
    campaign = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=4, current_location="Hall"
    )
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    for text_ in (
        "Starting year",
        "Campaign month",
        "Current location",
        "Travel",
        "Contracts",
        "Advance Month",
    ):
        assert text_ in page, text_


def test_aces_campaign_can_be_edited_without_calendar_fields(client, minimal_force):
    campaign = _plain_aces(minimal_force)
    resp = client.post(
        f"/campaigns/{campaign.id}/update",
        data={"name": "Renamed", "status": "active", "notes": "hi"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    updated = campaign_service.get_campaign_by_id(campaign.id)
    assert updated.name == "Renamed"
    assert updated.current_campaign_month is None


def test_campaign_list_shows_sortie_progress_for_aces(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id)
    page = client.get("/campaigns").data.decode()
    assert "1 Sortie" in page
    assert date.today().isoformat() in page


def test_aces_sortie_creation_and_page_have_no_month(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    resp = client.post(
        f"/campaigns/{campaign.id}/sorties", data={"name": "Strike"}, follow_redirects=True
    )
    assert resp.status_code == 200
    sortie = aces_sortie_service.list_aces_sorties(campaign.id)[0]
    with session_scope() as session:
        assert session.get(Sortie, sortie["id"]).campaign_month is None
    page = client.get(f"/sorties/{sortie['id']}").data.decode()
    assert "Campaign month" not in page
    assert "Date played" in page


# --- After-Sortie and events need no time/location -----------------------------------------


def test_after_sortie_flow_stores_no_campaign_month(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    assert campaign.current_location is None and campaign.current_campaign_month is None
    sortie, rows = _fought(campaign, {0: hawk})
    flags = {rows[0].id: {"pilot_wounded": True}}
    finish_aces(sortie.id, "structure", flags, primary_objective_sp=500, max_pilot_sp=50)
    aces_pilot_service.create_aces_pilot(
        campaign.id, "Third", "BM", skill_sp=150, edge_sp=0, ability_sp=0, hired=True
    )
    with session_scope() as session:
        assert session.query(WarchestTransaction).count() > 3
        for model in (WarchestTransaction, DamageEvent, PilotInjuryEvent, RepairOrder):
            rows_ = session.query(model).all()
            assert rows_, model
            assert all(r.campaign_month is None for r in rows_), model
        assert session.get(Sortie, sortie.id).campaign_month is None
        assert session.get(Campaign, campaign.id).current_campaign_month is None


# --- chronology ----------------------------------------------------------------------------


def _finish(campaign, pilot, name, played, **flags):
    sortie, rows = _fought(campaign, {0: pilot}, name=name)
    with session_scope() as session:
        session.get(Sortie, sortie.id).date_played = played
    finish_aces(sortie.id, "none", flags or None, primary_objective_sp=300, max_pilot_sp=40)
    return sortie


def test_sortie_history_orders_by_number_and_attempt_and_shows_date_played(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    first = _finish(campaign, hawk, "First", date(2026, 6, 20))
    second = _finish(campaign, ghost, "Second", date(2026, 1, 5))  # played earlier on the calendar
    rows = aces_sortie_service.list_aces_sorties(campaign.id)
    assert [r["id"] for r in rows] == [first.id, second.id]  # sequence, not date
    assert [r["date_played"] for r in rows] == [date(2026, 6, 20), date(2026, 1, 5)]
    page = client.get(f"/campaigns/{campaign.id}/sortie-history").data.decode()
    assert "2026-06-20" in page and "2026-01-05" in page
    report = client.get(f"/sorties/{first.id}/report").data.decode()
    assert "2026-06-20" in report


def test_replay_sorts_after_its_original(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk}, name="Try")
    aces_sortie_service.fail_sortie(sortie.id)
    replay = aces_sortie_service.create_replay(sortie.id)
    rows = aces_sortie_service.list_aces_sorties(campaign.id)
    assert [r["label"] for r in rows] == ["Sortie 1", "Sortie 1R"]
    assert replay.campaign_month is None


def test_pilot_history_orders_by_sortie_sequence_not_creation_time_or_date(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    _finish(campaign, hawk, "One", date(2026, 9, 1), **{})
    second = _finish(campaign, ghost, "Two", date(2026, 2, 1))
    history = aces_pilot_service.get_pilot_service_history(hawk.id)
    kinds = [(i["kind"], getattr(i["event"], "source_type", None)) for i in history["timeline"]]
    # creation first; then Sortie 1 participation and its improvement; then Sortie 2 sit-out.
    assert kinds[0] == ("advancement", "initial")
    assert kinds[1][0] == "sortie"
    assert kinds[2] == ("advancement", "sortie")
    assert all(item["order"][0] in (0, 1, 2) for item in history["timeline"])
    sortie_numbers = [item["order"][1] for item in history["timeline"] if item["order"][0] == 1]
    assert sortie_numbers == sorted(sortie_numbers)
    assert second.id  # Ghost's later Sortie exists but Hawk only sat it out


def test_pilot_history_page_works_without_campaign_month_data(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie = _finish(campaign, hawk, "One", date(2026, 3, 3))
    with session_scope() as session:
        assert session.get(Campaign, campaign.id).current_campaign_month is None
        assert session.get(CampaignPilot, hawk.id)
    page = client.get(f"/campaigns/pilots/{hawk.id}/history")
    assert page.status_code == 200
    assert b"2026-03-03" in page.data
    assert f"/sorties/{sortie.id}/report".encode() in page.data


def test_apply_without_location_or_month_succeeds(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=100)
    assert contract_service.get_sortie_by_id(sortie.id).status == "after_action"


# --- legacy database upgrade ---------------------------------------------------------------


def test_legacy_not_null_schema_is_rebuilt_and_aces_calendar_cleared(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", future=True)
    from app import models  # noqa: F401  (register every table)

    # Recreate the old schema: month columns NOT NULL.
    columns = [
        Base.metadata.tables[table].c[column]
        for table, names in extensions._NULLABLE_COLUMNS.items()
        for column in names
        if column != "contract_id"
    ]
    for column in columns:
        column.nullable = False
    try:
        Base.metadata.create_all(engine)
    finally:
        for column in columns:
            column.nullable = True

    with Session(engine) as session:
        aces = Campaign(
            name="Old Aces",
            ruleset="aces",
            status="active",
            current_campaign_month=3,
            starting_bt_year=3151,
            starting_bt_month=2,
            current_location="Galatea",
        )
        chaos = Campaign(
            name="Chaos",
            ruleset="chaos",
            status="active",
            current_campaign_month=4,
            starting_bt_year=3050,
            starting_bt_month=1,
            current_location="Hall",
        )
        session.add_all([aces, chaos])
        session.flush()
        for campaign, month in ((aces, 3), (chaos, 4)):
            session.add(
                WarchestTransaction(
                    campaign_id=campaign.id,
                    campaign_month=month,
                    transaction_type="opening_balance",
                    description="Opening",
                    gross_amount=10,
                    actual_amount=10,
                    resulting_balance=10,
                )
            )
            session.add(
                Sortie(campaign_id=campaign.id, name="S", campaign_month=month, status="closed")
            )
        session.commit()
        aces_id, chaos_id = aces.id, chaos.id

    extensions._apply_schema_constraints(engine)
    extensions._apply_schema_migrations(engine)
    extensions._apply_schema_constraints(engine)
    extensions._apply_schema_migrations(engine)  # idempotent

    with engine.connect() as conn:
        for table, names in extensions._NULLABLE_COLUMNS.items():
            info = {row[1]: row[3] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))}
            for name in names:
                assert info[name] == 0, (table, name)
        indexes = {row[1] for row in conn.execute(text("PRAGMA index_list(campaigns)"))}
        assert "uix_one_active_campaign" in indexes

        old = conn.execute(
            text(
                "SELECT starting_bt_year, starting_bt_month, current_location, "
                "current_campaign_month FROM campaigns WHERE id = :id"
            ),
            {"id": aces_id},
        ).one()
        assert tuple(old) == (None, None, None, None)
        kept = conn.execute(
            text(
                "SELECT starting_bt_year, starting_bt_month, current_location, "
                "current_campaign_month FROM campaigns WHERE id = :id"
            ),
            {"id": chaos_id},
        ).one()
        assert tuple(kept) == (3050, 1, "Hall", 4)

        month_of = lambda table, cid: conn.execute(  # noqa: E731
            text(f'SELECT campaign_month FROM "{table}" WHERE campaign_id = :id'), {"id": cid}
        ).scalar_one()
        assert month_of("warchest_transactions", aces_id) is None
        assert month_of("sorties", aces_id) is None
        assert month_of("warchest_transactions", chaos_id) == 4
        assert month_of("sorties", chaos_id) == 4
        # Rows survive and the other tables still reference the final table names.
        assert conn.execute(text("SELECT COUNT(*) FROM campaigns")).scalar_one() == 2
        refs = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE name = 'sortie_units'")
        ).scalar_one()
        assert "__rebuild" not in refs and "_old" not in refs
    engine.dispose()
