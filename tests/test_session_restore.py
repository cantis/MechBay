from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services import document_service, force_service, inventory_project_service
from app.services.lance_template_service import create_template
from app.services.miniature_service import get_all_miniatures
from app.services.session_restore_service import (
    consume_startup_messages,
    inventory_has_data,
    inventory_matches_file,
    restore_session,
)


@pytest.fixture(autouse=True)
def _document_state_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(document_service, "get_app_data_dir", lambda: tmp_path)
    document_service.clear_inventory_dirty()
    document_service.set_inventory_path(None)
    document_service.clear_all_force_documents()
    consume_startup_messages()
    yield


def test_inventory_has_data_false_on_empty_db():
    inventory_project_service.new_inventory_project()
    assert inventory_has_data() is False


def test_restore_loads_linked_inventory_when_db_empty(client, sample_miniatures):
    create_template("Scout", ["Warhammer"], description="Test")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "saved.mechbay"
        inventory_project_service.save_project_to_path(path)

        inventory_project_service.new_inventory_project()
        assert get_all_miniatures() == []

        document_service.set_inventory_path(str(path.resolve()))
        document_service.mark_inventory_dirty()

        result = restore_session()

    assert result["inventory_restored"] is True
    assert len(get_all_miniatures()) >= 1
    assert document_service.load_state().inventory_dirty is False
    messages = consume_startup_messages()
    assert any("Restored inventory" in message for _, message in messages)


def test_restore_clears_inventory_dirty_when_file_matches_db(client, sample_miniatures):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "saved.mechbay"
        inventory_project_service.save_project_to_path(path)
        document_service.mark_inventory_dirty()

        result = restore_session()

        assert result["dirty_cleared_inventory"] is True
        assert document_service.load_state().inventory_dirty is False
        assert inventory_matches_file(path) is True


def test_restore_prunes_missing_force_path(client, minimal_force):
    document_service.set_force_path(minimal_force, "C:/missing/force.mbforce")
    document_service.mark_force_dirty(minimal_force)

    result = restore_session()

    state = document_service.load_state()
    assert str(minimal_force) not in state.force_paths
    assert minimal_force not in state.dirty_force_ids
    assert result["paths_pruned"] == 1


def test_restore_clears_force_dirty_when_file_matches(client, minimal_force, tmp_path):
    path = tmp_path / "linked.mbforce"
    force_service.save_force_to_path(minimal_force, path)
    document_service.mark_force_dirty(minimal_force)

    result = restore_session()

    assert minimal_force in result["dirty_cleared_force_ids"]
    assert minimal_force not in document_service.load_state().dirty_force_ids


def test_sample_data_requires_confirm_when_inventory_has_data(client, sample_miniatures):
    resp = client.post(
        "/files/inventory/sample-data",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["needs_confirm"] is True
    assert "confirm_message" in body


def test_sample_data_loads_with_confirm(client, sample_miniatures):
    before = len(get_all_miniatures())
    resp = client.post(
        "/files/inventory/sample-data",
        json={"confirm": "1"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    assert len(get_all_miniatures()) >= before
    assert document_service.load_state().inventory_dirty is True


def test_sample_data_loads_on_empty_inventory(client):
    inventory_project_service.new_inventory_project()
    resp = client.post(
        "/files/inventory/sample-data",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    assert len(get_all_miniatures()) >= 2
    assert document_service.load_state().inventory_dirty is True


def test_create_app_does_not_auto_seed(client):
    """Client fixture uses TESTING app; inventory should stay empty without explicit seed."""
    inventory_project_service.new_inventory_project()
    resp = client.get("/miniatures")
    assert resp.status_code == 200
    assert b"Get started" in resp.data
