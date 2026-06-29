from __future__ import annotations

from unittest.mock import patch

from app.services import alpha_strike_service, force_service
from app.services.force_service import (
    INVENTORY_FACTION_ALL,
    get_force_miniature_assignments,
    get_inventory_candidates,
    set_inventory_faction,
    summarize_inventory_candidates,
)
from app.services.mul_service import batch_chassis_availability, chassis_has_variants


def test_get_force_miniature_assignments(client, minimal_force, sample_miniatures):
    assignments = get_force_miniature_assignments(minimal_force)
    assert len(assignments) == 2
    assert all(a.lance_name == "Alpha Lance" for a in assignments.values())
    assert all(a.lance_color for a in assignments.values())


def test_inventory_list_shows_in_force_label(client, minimal_force, sample_miniatures):
    resp = client.get("/miniatures")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "In force · Alpha Lance" in body
    assert 'title="In force — remove from force builder to reassign"' in body


def test_inventory_candidates_all_factions(client, sample_miniatures):
    force = force_service.create_force("Mixed Force")
    set_inventory_faction(force.id, "All")

    candidates = get_inventory_candidates(force.id)
    assert len(candidates) >= 4
    factions = {c.miniature.faction for c in candidates}
    assert len(factions) > 1


def test_set_inventory_faction(client, sample_miniatures):
    force = force_service.create_force("Test Force")
    updated = set_inventory_faction(force.id, "Jade Falcon")
    assert updated is not None
    assert updated.inventory_faction == "Jade Falcon"

    all_faction = set_inventory_faction(force.id, "all")
    assert all_faction is not None
    assert all_faction.inventory_faction == INVENTORY_FACTION_ALL

    cleared = set_inventory_faction(force.id, None)
    assert cleared is not None
    assert cleared.inventory_faction is None


def test_inventory_candidates_without_mul_filters(client, sample_miniatures):
    force = force_service.create_force("Pool Force")
    set_inventory_faction(force.id, "Jade Falcon")

    candidates = get_inventory_candidates(force.id)
    assert len(candidates) == 4
    assert all(c.miniature.faction == "Jade Falcon" for c in candidates)
    assert all(c.mul_available is None for c in candidates)
    assert all(not c.in_force for c in candidates)


def test_inventory_candidates_in_force_flag(client, minimal_force, sample_miniatures):
    set_inventory_faction(minimal_force, "Jade Falcon")
    candidates = get_inventory_candidates(minimal_force)

    in_force = [c for c in candidates if c.in_force]
    assert len(in_force) == 2
    assert all(c.lance_name == "Alpha Lance" for c in in_force)
    assert all(c.lance_color for c in in_force)
    assert all(c.mul_available is None for c in in_force)


def test_create_empty_lance_assigns_header_color(client, minimal_force):
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    existing = {lance.header_color for lance in force.lances if lance.header_color}

    lance = force_service.create_empty_lance(minimal_force, "Bravo Lance")
    assert lance is not None
    assert lance.header_color
    assert lance.header_color.startswith("#")
    assert lance.header_color not in existing or len(existing) >= 12


@patch("app.services.mul_service.search_variants")
def test_inventory_candidates_with_mul_filters(mock_search, client, sample_miniatures):
    force = force_service.create_force("MUL Pool Force")
    set_inventory_faction(force.id, "Jade Falcon")
    alpha_strike_service.enable_alpha_strike(
        force.id,
        mul_faction_id=34,
        mul_era_id=257,
    )

    def fake_search(name, *, faction_id, era_id, unit_type_id=None):
        if "Warhammer" in name:
            return [{"id": 1}]
        return []

    mock_search.side_effect = fake_search

    candidates = get_inventory_candidates(force.id)
    warhammer = [c for c in candidates if "Warhammer" in c.miniature.chassis]
    other = [c for c in candidates if "Warhammer" not in c.miniature.chassis]

    assert len(warhammer) == 2
    assert all(c.mul_available is True for c in warhammer)
    assert all(c.mul_available is False for c in other)


@patch("app.services.mul_service.search_variants")
def test_chassis_has_variants(mock_search):
    mock_search.return_value = [{"id": 1}]
    assert chassis_has_variants("Warhammer", faction_id=34, era_id=257, unit_type_id=18) is True

    mock_search.return_value = []
    assert chassis_has_variants("Unknown", faction_id=34, era_id=257) is False


@patch("app.services.mul_service.chassis_has_variants")
def test_batch_chassis_availability_dedupes(mock_has):
    mock_has.return_value = True
    keys = {("Warhammer", 18), ("Atlas", 18)}
    result = batch_chassis_availability(keys, faction_id=34, era_id=257)
    assert result == {("Warhammer", 18): True, ("Atlas", 18): True}
    assert mock_has.call_count == 2


def test_force_detail_type_filter_options(client, sample_miniatures):
    force = force_service.create_force("Type Filter Force")
    set_inventory_faction(force.id, "Jade Falcon")

    resp = client.get(f"/forces/{force.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="inventoryPoolType"' in body
    assert 'data-type-label="Mech"' in body


@patch("app.services.mul_service.search_variants")
def test_force_detail_marks_unavailable_rows(mock_search, client, sample_miniatures):
    force = force_service.create_force("Filter Force")
    set_inventory_faction(force.id, "Jade Falcon")
    alpha_strike_service.enable_alpha_strike(
        force.id,
        mul_faction_id=34,
        mul_era_id=257,
    )

    def fake_search(name, *, faction_id, era_id, unit_type_id=None):
        if "Warhammer" in name:
            return [{"id": 1}]
        return []

    mock_search.side_effect = fake_search

    resp = client.get(f"/forces/{force.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="hideUnavailable"' in body
    assert 'id="inventoryPoolSearch"' in body
    assert 'id="inventoryPoolType"' in body
    assert "data-hide-when-filtered" in body
    assert body.index("Save</button>") < body.index('id="hideUnavailable"')


def test_filter_inventory_candidates_hides_unavailable():
    from app.models.miniature import Miniature

    def mini(chassis: str) -> Miniature:
        return Miniature(
            series="A",
            unique_id=1,
            prefix="X",
            chassis=chassis,
            type="Mech",
            faction="Test",
        )

    candidates = [
        force_service.InventoryCandidate(mini("InForce"), True, "L1", 1, "#dbeafe", False),
        force_service.InventoryCandidate(mini("Available"), False, None, None, None, True),
        force_service.InventoryCandidate(mini("Unavailable"), False, None, None, None, False),
        force_service.InventoryCandidate(mini("Neutral"), False, None, None, None, None),
    ]

    filtered = force_service.filter_inventory_candidates(candidates, hide_unavailable=True)
    assert len(filtered) == 3
    assert {c.miniature.chassis for c in filtered} == {"InForce", "Available", "Neutral"}

    assert len(force_service.filter_inventory_candidates(candidates, hide_unavailable=False)) == 4


def test_summarize_inventory_candidates():
    from app.models.miniature import Miniature

    def mini(chassis: str) -> Miniature:
        return Miniature(
            series="A",
            unique_id=1,
            prefix="X",
            chassis=chassis,
            type="Mech",
            faction="Test",
        )

    candidates = [
        force_service.InventoryCandidate(mini("A"), True, "L1", 1, "#dbeafe", None),
        force_service.InventoryCandidate(mini("B"), False, None, None, None, True),
        force_service.InventoryCandidate(mini("C"), False, None, None, None, False),
        force_service.InventoryCandidate(mini("D"), False, None, None, None, None),
    ]
    summary = summarize_inventory_candidates(candidates)
    assert summary["total"] == 4
    assert summary["in_force"] == 1
    assert summary["mul_available"] == 1
    assert summary["not_in_mul"] == 1
    assert summary["available"] == 2


def test_set_inventory_faction_route(client, sample_miniatures):
    force = force_service.create_force("Route Force")
    resp = client.post(
        f"/forces/{force.id}/inventory-faction",
        data={"inventory_faction": "Jade Falcon"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    refreshed = force_service.get_force_by_id(force.id)
    assert refreshed is not None
    assert refreshed.inventory_faction == "Jade Falcon"
