from __future__ import annotations

from unittest.mock import patch

from app.services import alpha_strike_service, force_service
from app.services.force_service import (
    get_inventory_candidates,
    set_inventory_faction,
    summarize_inventory_candidates,
)
from app.services.mul_service import batch_chassis_availability, chassis_has_variants


def test_set_inventory_faction(client, sample_miniatures):
    force = force_service.create_force("Test Force")
    updated = set_inventory_faction(force.id, "Jade Falcon")
    assert updated is not None
    assert updated.inventory_faction == "Jade Falcon"

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
    assert all(c.mul_available is None for c in in_force)


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
        force_service.InventoryCandidate(mini("A"), True, "L1", None),
        force_service.InventoryCandidate(mini("B"), False, None, True),
        force_service.InventoryCandidate(mini("C"), False, None, False),
        force_service.InventoryCandidate(mini("D"), False, None, None),
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
