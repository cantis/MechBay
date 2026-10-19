"""Aces mandatory repairs and the Between Sorties phase (repairs + sales addenda)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import extensions
from app.extensions import Base, session_scope
from app.models.campaign import Campaign
from app.models.campaign_unit import CampaignUnit
from app.models.repair_order import RepairOrder
from app.models.sortie import Sortie
from app.services import aces_after_action_service as svc
from app.services import (
    aces_pilot_service,
    aces_sortie_service,
    after_action_service,
    campaign_service,
    contract_service,
)
from tests.conftest import apply_aces, finalize_aces, finish_aces
from tests.test_aces_after_sortie import _balance, _campaign, _fought, _txs

BOUGHT = {
    "Id": 7563,
    "Name": "Phoenix Hawk PHX-3PL",
    "Class": "Phoenix Hawk",
    "Variant": "PHX-3PL",
    "Tonnage": 45,
    "BFPointValue": 36,
    "Type": {"Id": 18, "Name": "BattleMech"},
}


def _buy(campaign_id):
    with patch("app.services.campaign_service.mul_service.find_unit_in_search_results") as find:
        find.return_value = BOUGHT
        return campaign_service.purchase_campaign_unit(
            campaign_id, 7563, search_name="Phoenix Hawk"
        )


def _set_mul(campaign_id):
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        campaign.mul_faction_id = 29
        campaign.mul_era_id = 14


# --- mandatory repairs ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("damage", "cost"), [("armour", 60), ("structure", 120), ("crippled", 180), ("destroyed", 300)]
)
def test_every_damaged_recoverable_unit_gets_a_required_repair(client, minimal_force, damage, cost):
    campaign, (hawk, ghost) = _campaign(minimal_force, warchest=5000)
    sortie, rows = _fought(campaign, {0: hawk}, units=(0, 1))
    apply_aces(sortie.id, damage, primary_objective_sp=2000)
    orders = after_action_service.get_repair_orders(campaign.id)
    assert len(orders) == 2  # both damaged units
    assert {o.gross_cost for o in orders} == {cost}
    assert all(o.ruleset == "aces" and o.status == "pending" for o in orders)
    assert _report_row(sortie.id).expense_repairs == 2 * cost


def _report_row(sortie_id):
    return svc.get_sortie_report(sortie_id)["report"]


def test_undamaged_units_need_no_repair(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "none")
    assert after_action_service.get_repair_orders(campaign.id) == []


def test_repair_expense_is_part_of_the_sortie_and_posts_at_finalize(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "structure", primary_objective_sp=500)
    report = _report_row(sortie.id)
    assert report.expense_repairs == 120
    assert report.total_expenses >= 120
    assert _txs(campaign.id, "repair") == []  # nothing posted yet
    finalize_aces(sortie.id)
    [repair] = _txs(campaign.id, "repair")
    assert repair.actual_amount == -120
    assert repair.related_entity_type == "repair_order"


def test_units_return_to_service_only_when_finalized(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "crippled", primary_objective_sp=1000)
    unit = campaign_service.get_campaign_by_id(campaign.id).units[0]
    assert (unit.condition, unit.available) == ("damaged", False)
    finalize_aces(sortie.id)
    unit = campaign_service.get_campaign_by_id(campaign.id).units[0]
    assert (unit.condition, unit.damage_category, unit.available) == ("active", "none", True)
    # History is preserved.
    [order] = after_action_service.get_repair_orders(campaign.id)
    assert order.status == "completed"
    assert campaign_service.get_campaign_log(campaign.id)


def test_truly_destroyed_unit_is_not_repaired_or_sold(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id, "truly-destroyed")
    assert after_action_service.get_repair_orders(campaign.id) == []
    unit = campaign_service.get_campaign_by_id(campaign.id).units[0]
    assert (unit.condition, unit.available) == ("truly-destroyed", False)
    with pytest.raises(ValueError, match="active, fully repaired"):
        campaign_service.sell_campaign_unit(campaign.id, unit.id)
    assert unit.id == campaign.units[0].id  # history retained


def test_damaged_unit_cannot_be_sold_before_repair(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "armour", primary_objective_sp=500)
    unit_id = campaign.units[0].id
    # While the Sortie is unresolved, no selling at all.
    with pytest.raises(ValueError, match="Finalize Sortie 1 before you sell units"):
        campaign_service.sell_campaign_unit(campaign.id, unit_id)
    # A unit that is still damaged is not eligible even between Sorties.
    finalize_aces(sortie.id)
    with session_scope() as session:
        unit = session.get(CampaignUnit, unit_id)
        unit.condition, unit.damage_category, unit.available = "damaged", "armour", False
    with pytest.raises(ValueError, match="active, fully repaired"):
        campaign_service.sell_campaign_unit(campaign.id, unit_id)


def test_repaired_unit_sells_for_pv_times_twenty_between_sorties(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id, "structure", primary_objective_sp=1000)
    before = _balance(campaign.id)
    sold = campaign_service.sell_campaign_unit(campaign.id, campaign.units[0].id)
    assert _balance(campaign.id) == before + 40 * 20
    assert sold.condition == "retired"
    assert len(campaign_service.get_campaign_by_id(campaign.id).units) == 2  # history kept


def test_mandatory_repair_can_push_the_warchest_negative(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force, warchest=50)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id, "destroyed", primary_objective_sp=0, max_pilot_sp=100)
    assert _balance(campaign.id) == 50 - 300 - 20
    unit = campaign_service.get_campaign_by_id(campaign.id).units[0]
    assert unit.condition == "active"  # the repair was not skipped
    report = _report_row(sortie.id)
    assert report.pilot_sp_pool == 0  # no positive Earnings, no pilot advancement
    # The campaign continues: the next Sortie can be prepared.
    assert campaign_service.create_aces_sortie(campaign.id, "Next").sortie_number == 2


def test_no_repair_defer_cancel_or_scrap_controls(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, "structure", primary_objective_sp=500)
    pages = [
        client.get(f"/campaigns/{campaign.id}").data.decode(),
        client.get(f"/sorties/{sortie.id}").data.decode(),
        client.get(f"/sorties/{sortie.id}/report").data.decode(),
    ]
    for page in pages:
        for label in (
            "Cancel Repair",
            "Defer Repair",
            "Repair Later",
            "Leave Unavailable",
            "Scrap",
        ):
            assert label not in page, label
        assert "Repair Orders" not in page
    assert "Required Repairs" in pages[2]
    assert "Returns to service when the Sortie is finalized" in pages[2]


def test_aces_unit_condition_is_locked(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    unit_id = campaign.units[0].id
    with pytest.raises(ValueError, match="set by Sortie results"):
        campaign_service.update_campaign_unit(unit_id, condition="retired")
    with pytest.raises(ValueError, match="set by Sortie results"):
        campaign_service.update_campaign_unit(unit_id, available=False)
    assert campaign_service.update_campaign_unit(unit_id, notes="fine").notes == "fine"
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert "Truly destroy" not in page
    assert 'name="condition"' not in page


def test_chaos_repair_orders_still_cancellable(client, minimal_force):
    chaos = campaign_service.create_campaign_from_force(
        minimal_force, "Chaos", starting_bt_year=3151, starting_bt_month=1
    )
    with session_scope() as session:
        unit = session.query(CampaignUnit).filter_by(campaign_id=chaos.id).first()
        order = RepairOrder(
            campaign_id=chaos.id,
            campaign_unit_id=unit.id,
            damage_category="structure",
            ruleset="chaos",
            gross_cost=140,
            campaign_month=1,
            status="pending",
        )
        session.add(order)
        session.flush()
        order_id = order.id
    page = client.get(f"/campaigns/{chaos.id}").data.decode()
    assert "Repair Orders" in page
    assert after_action_service.update_repair_order(order_id, gross_cost=100).gross_cost == 100
    assert after_action_service.cancel_repair_order(order_id).status == "cancelled"


# --- Between Sorties -----------------------------------------------------------------------


def test_between_sorties_state_follows_the_last_sortie(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    assert aces_sortie_service.get_campaign_state(campaign.id)["state"] == "between"

    sortie, _ = _fought(campaign, {0: hawk})
    state = aces_sortie_service.get_campaign_state(campaign.id)
    assert state["state"] == "in_progress" and state["sortie"].id == sortie.id
    assert state["can_change_roster"] is False and state["can_prepare_sortie"] is False

    apply_aces(sortie.id)
    assert aces_sortie_service.get_campaign_state(campaign.id)["state"] == "in_progress"
    finalize_aces(sortie.id)
    state = aces_sortie_service.get_campaign_state(campaign.id)
    assert (state["state"], state["can_prepare_sortie"]) == ("between", True)


def test_failed_sortie_allows_trades_but_requires_replay(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force, warchest=3000)
    _set_mul(campaign.id)
    sortie, _ = _fought(campaign, {0: hawk})
    aces_sortie_service.fail_sortie(sortie.id)
    state = aces_sortie_service.get_campaign_state(campaign.id)
    assert (state["state"], state["can_change_roster"], state["can_prepare_sortie"]) == (
        "replay_required",
        True,
        False,
    )
    bought = _buy(campaign.id)  # fix a gap in the force before the retry
    assert bought.miniature_id is None
    campaign_service.sell_campaign_unit(campaign.id, campaign.units[1].id)
    with pytest.raises(ValueError, match="must be replayed"):
        campaign_service.create_aces_sortie(campaign.id, "New")
    assert aces_sortie_service.create_replay(sortie.id).attempt_label == "Sortie 1R"


def test_all_between_sorties_actions_wait_for_finalize(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force, warchest=3000)
    _set_mul(campaign.id)
    sortie, _ = _fought(campaign, {0: hawk})
    expectations = [
        (lambda: campaign_service.create_aces_sortie(campaign.id, "Next"), "prepare the next"),
        (lambda: _buy(campaign.id), "buy units"),
        (lambda: campaign_service.sell_campaign_unit(campaign.id, campaign.units[1].id), "sell"),
        (
            lambda: aces_pilot_service.create_aces_pilot(
                campaign.id, "New", "BM", skill_sp=150, edge_sp=0, ability_sp=0
            ),
            "add a Named Pilot",
        ),
        (lambda: aces_pilot_service.retire_aces_pilot(ghost.id), "retire a Named Pilot"),
        (lambda: after_action_service.retire_campaign_unit(campaign.units[1].id), "retire units"),
        (
            lambda: campaign_service.add_warchest_transaction(
                campaign.id, transaction_type="adjustment", description="x", actual_amount=5
            ),
            "record Warchest entries",
        ),
    ]
    for action, fragment in expectations:
        with pytest.raises(ValueError, match=f"Finalize Sortie 1 before you .*{fragment}"):
            action()
    finish_aces(sortie.id)
    # ... and every one of them works once the Sortie is finalized.
    assert _buy(campaign.id).id
    aces_pilot_service.create_aces_pilot(
        campaign.id, "New", "BM", skill_sp=150, edge_sp=0, ability_sp=0
    )
    entry = campaign_service.add_warchest_transaction(
        campaign.id, transaction_type="adjustment", description="x", actual_amount=5
    )
    assert entry.campaign_month is None


def test_next_sortie_cannot_become_ready_while_previous_is_unfinished(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force)
    early = campaign_service.create_aces_sortie(campaign.id, "Prepared early")
    contract_service.add_unit_to_sortie(early.id, campaign.units[1].id)
    contract_service.assign_sortie_pilot(
        contract_service.get_sortie_by_id(early.id).units[0].id, ghost.id
    )
    aces_sortie_service.set_force_commander(early.id, ghost.id)

    played, _ = _fought_other(campaign, hawk)
    with pytest.raises(ValueError, match="Finalize Sortie 2 before you prepare the next Sortie"):
        contract_service.mark_sortie_ready(early.id)
    apply_aces(played.id)
    with pytest.raises(ValueError, match="Finalize Sortie 2"):
        contract_service.mark_sortie_ready(early.id)
    finalize_aces(played.id)
    assert contract_service.mark_sortie_ready(early.id).status == "ready"


def _fought_other(campaign, pilot):
    """A second Sortie fought while an earlier one still sits in planning."""
    sortie = Sortie(
        campaign_id=campaign.id,
        name="Played",
        max_sortie_pv=1000,
        status="planning",
        sortie_number=2,
        attempt_number=1,
        date_played=None,
    )
    with session_scope() as session:
        session.add(sortie)
        session.flush()
        sortie_id = sortie.id
    row = contract_service.add_unit_to_sortie(sortie_id, campaign.units[0].id)
    contract_service.assign_sortie_pilot(row.id, pilot.id)
    aces_sortie_service.set_force_commander(sortie_id, pilot.id)
    from datetime import date

    contract_service.update_sortie(sortie_id, date_played=date.today())
    contract_service.mark_sortie_ready(sortie_id)
    contract_service.mark_sortie_fought(sortie_id)
    return contract_service.get_sortie_by_id(sortie_id), row


def test_warchest_only_moves_at_finalize_and_trades_never_change_the_report(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force, warchest=3000)
    _set_mul(campaign.id)
    sortie, _ = _fought(campaign, {0: hawk})
    apply_aces(sortie.id, primary_objective_sp=500, max_pilot_sp=0)
    assert _balance(campaign.id) == 3000
    finalize_aces(sortie.id)
    after_sortie = _balance(campaign.id)
    assert after_sortie == 3000 + 500 - 20
    frozen = _report_row(sortie.id)
    figures = (frozen.total_income, frozen.total_expenses, frozen.earnings)

    _buy(campaign.id)
    campaign_service.sell_campaign_unit(campaign.id, campaign.units[1].id)
    again = _report_row(sortie.id)
    assert again.warchest_after_accounting == after_sortie
    assert (again.total_income, again.total_expenses, again.earnings) == figures
    # Trades are not part of that Sortie's ledger lines either.
    types = {t.transaction_type for t in _txs(campaign.id)}
    assert {"unit_purchase", "unit_sale"} <= types
    sortie_entities = {t.related_entity_type for t in _txs(campaign.id, "objective_income")}
    assert sortie_entities == {"sortie"}


def test_timeline_separates_sortie_results_from_between_sorties_trades(client, minimal_force):
    campaign, (hawk, ghost) = _campaign(minimal_force, warchest=3000)
    _set_mul(campaign.id)
    first, _ = _fought(campaign, {0: hawk})
    finish_aces(first.id, primary_objective_sp=500)
    _buy(campaign.id)
    campaign_service.sell_campaign_unit(campaign.id, campaign.units[1].id)
    second, _ = _fought(campaign, {0: ghost}, name="Second")
    finish_aces(second.id, primary_objective_sp=300)

    timeline = aces_sortie_service.get_campaign_timeline(campaign.id)
    texts = [(e["kind"], e["text"]) for e in timeline]
    kinds = [kind for kind, _ in texts]
    assert kinds[0] == "opening"
    sortie_one_end = texts.index(("warchest_after", f"Warchest after Sortie 1: {3000 + 480:,} SP"))
    purchase = next(i for i, (k, t) in enumerate(texts) if k == "between" and "Purchased" in t)
    sale = next(i for i, (k, t) in enumerate(texts) if k == "between" and "Sold" in t)
    before_two = next(
        i for i, (_, t) in enumerate(texts) if t.startswith("Warchest before Sortie 2")
    )
    assert sortie_one_end < purchase < sale < before_two
    # Sortie-accounting ledger lines (income, rearm, ...) do not appear as trades.
    between = [t for k, t in texts if k == "between"]
    assert len(between) == 2
    assert not any("Primary objective" in t or "Rearm" in t for t in between)

    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert "Campaign Timeline" in page
    assert "Between Sorties" in page
    assert "Warchest before Sortie 2" in page


def test_between_sorties_card_lists_trades_since_the_last_sortie(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force, warchest=3000)
    _set_mul(campaign.id)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id, primary_objective_sp=500)
    assert aces_sortie_service.get_campaign_state(campaign.id)["trades"] == []
    _buy(campaign.id)
    trades = aces_sortie_service.get_campaign_state(campaign.id)["trades"]
    assert len(trades) == 1 and trades[0]["amount"] == -36 * 40
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert "Purchases, sales and hires since the last Sortie" in page
    assert "Purchased Phoenix Hawk" in page
    assert "Create Sortie" in page  # the player chooses when to prepare the next one


def test_in_progress_campaign_page_hides_roster_forms(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert "Sortie in Progress" in page
    assert "Continue Sortie 1" in page
    for hidden in ("Create Sortie", "Purchase Replacement", "New Named Pilot", "Sell ("):
        assert hidden not in page, hidden
    assert "wait until then" in page
    blocked = client.post(
        f"/campaigns/{campaign.id}/sorties", data={"name": "Next"}, follow_redirects=True
    )
    assert b"Finalize Sortie 1 before you prepare the next Sortie" in blocked.data


def test_report_has_no_purchase_or_sale_lines_and_shows_warchest_change(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force, warchest=3000)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id, primary_objective_sp=500)
    page = client.get(f"/sorties/{sortie.id}/report").data.decode()
    assert "Warchest before Sortie" in page
    assert "Warchest change from Sortie" in page
    assert "Warchest after Sortie" in page
    assert "Purchases" not in page and "Sales" not in page


def test_manual_warchest_entry_works_for_aces_without_a_month(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    resp = client.post(
        f"/campaigns/{campaign.id}/warchest",
        data={"transaction_type": "adjustment", "description": "Bonus", "actual_amount": "25"},
        follow_redirects=True,
    )
    assert b"Warchest transaction recorded" in resp.data
    assert _balance(campaign.id) == 1025


# --- upgrade of an existing database -------------------------------------------------------


def test_upgrade_finishes_legacy_aces_repairs_and_drops_report_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", future=True)
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    with engine.connect() as conn:  # the columns the old report table still had
        for column in ("purchases_total", "sales_total", "warchest_after"):
            conn.execute(text(f"ALTER TABLE aces_sortie_reports ADD COLUMN {column} INTEGER"))
        conn.commit()

    with Session(engine) as session:
        campaign = Campaign(name="Old", ruleset="aces", status="active")
        session.add(campaign)
        session.flush()
        units = []
        for index in range(2):
            unit = CampaignUnit(
                campaign_id=campaign.id,
                chassis=f"Mech{index}",
                condition="damaged",
                damage_category="structure",
                available=False,
                order=index,
            )
            session.add(unit)
            units.append(unit)
        closed = Sortie(campaign_id=campaign.id, name="Done", status="closed")
        open_one = Sortie(campaign_id=campaign.id, name="Open", status="after_action")
        session.add_all([closed, open_one])
        session.flush()
        for unit, sortie in zip(units, (closed, open_one), strict=True):
            session.add(
                RepairOrder(
                    campaign_id=campaign.id,
                    sortie_id=sortie.id,
                    campaign_unit_id=unit.id,
                    damage_category="structure",
                    ruleset="aces",
                    gross_cost=120,
                    status="pending",
                )
            )
        session.commit()

    extensions._apply_schema_migrations(engine)
    extensions._apply_schema_migrations(engine)  # idempotent

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(aces_sortie_reports)"))}
        assert not columns & {"purchases_total", "sales_total", "warchest_after"}
        assert "pending_ledger" in columns
        statuses = dict(
            conn.execute(
                text(
                    "SELECT u.chassis, r.status FROM repair_orders r "
                    "JOIN campaign_units u ON u.id = r.campaign_unit_id"
                )
            ).all()
        )
        # Resolved Sortie: finished. The still-open After-Sortie finishes at its own Finalize.
        assert statuses == {"Mech0": "completed", "Mech1": "pending"}
        conditions = dict(conn.execute(text("SELECT chassis, condition FROM campaign_units")).all())
        assert conditions == {"Mech0": "active", "Mech1": "damaged"}
    engine.dispose()


def test_purchase_form_lives_in_the_between_sorties_card(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    between = page.index('id="betweenSorties"')
    summary = page.index("Player Force Summary")
    purchase = page.index("Purchase Replacement / Additional Unit")
    assert between < purchase < summary  # inside the Between Sorties card, above the summary
    assert page.count("Purchase Replacement / Additional Unit") == 1
    assert "acesSearchMul" in page


def test_player_force_card_is_titled_summary_and_create_sortie_is_green(client, minimal_force):
    campaign, _ = _campaign(minimal_force)
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    assert "Player Force Summary" in page
    assert '<h5 class="mb-0">Player Force</h5>' not in page
    button = page[page.index("Create Sortie</button>") - 120 : page.index("Create Sortie</button>")]
    assert "btn-success" in button


def test_sorties_have_their_own_card(client, minimal_force):
    campaign, (hawk, _) = _campaign(minimal_force)
    sortie, _ = _fought(campaign, {0: hawk})
    finish_aces(sortie.id)
    page = client.get(f"/campaigns/{campaign.id}").data.decode()
    sorties_start = page.index('id="sorties"')
    summary_start = page.index("Player Force Summary")
    sorties_card = page[sorties_start:summary_start]
    for expected in ("Create Sortie", "Full Sortie History", "Sortie 1", "Date played"):
        assert expected in sorties_card, expected
    summary_card = page[summary_start : page.index("Roster</h5>")]
    for moved in ("Create Sortie", "Full Sortie History", "Date played"):
        assert moved not in summary_card, moved
    assert "Difficulty:" in summary_card and "Story Keywords:" in summary_card
