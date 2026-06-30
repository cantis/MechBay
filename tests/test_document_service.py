from __future__ import annotations

import json

import pytest

from app.services import document_service


@pytest.fixture(autouse=True)
def _clean_document_state(tmp_path, monkeypatch):
    monkeypatch.setattr(document_service, "get_app_data_dir", lambda: tmp_path)
    yield
    state_file = tmp_path / document_service.STATE_FILENAME
    if state_file.exists():
        state_file.unlink()


def test_load_state_returns_defaults_when_missing():
    state = document_service.load_state()
    assert state.inventory_path is None
    assert state.inventory_dirty is False
    assert state.force_paths == {}
    assert state.dirty_force_ids == []


def test_inventory_dirty_round_trip():
    document_service.mark_inventory_dirty()
    assert document_service.load_state().inventory_dirty is True

    document_service.clear_inventory_dirty()
    assert document_service.load_state().inventory_dirty is False


def test_force_dirty_tracking():
    document_service.mark_force_dirty(7)
    state = document_service.load_state()
    assert 7 in state.dirty_force_ids

    document_service.clear_force_dirty(7)
    assert 7 not in document_service.load_state().dirty_force_ids


def test_set_force_path_and_remove():
    document_service.set_force_path(3, "C:/forces/Alpha.mbforce")
    state = document_service.load_state()
    assert state.force_paths["3"] == "C:/forces/Alpha.mbforce"

    document_service.remove_force_document(3)
    state = document_service.load_state()
    assert "3" not in state.force_paths
    assert 3 not in state.dirty_force_ids


def test_suppress_dirty_tracking_blocks_flags():
    document_service.mark_inventory_dirty()
    with document_service.suppress_dirty_tracking():
        document_service.mark_inventory_dirty()
        document_service.mark_force_dirty(1)
    state = document_service.load_state()
    assert state.inventory_dirty is True
    assert state.dirty_force_ids == []


def test_get_status_labels():
    document_service.set_inventory_path("C:/data/MyStuff.mechbay")
    document_service.mark_inventory_dirty()
    document_service.set_force_path(2, "C:/data/Force.mbforce")
    document_service.mark_force_dirty(2)

    status = document_service.get_status()
    assert status["inventory_label"] == "MyStuff.mechbay *"
    assert status["force_files"][0]["label"] == "Force.mbforce *"


def test_persists_to_documents_json(tmp_path, monkeypatch):
    monkeypatch.setattr(document_service, "get_app_data_dir", lambda: tmp_path)
    document_service.set_inventory_path("collection.mechbay")
    document_service.update_settings({"per_page": 50})

    reloaded = document_service.load_state()
    assert reloaded.inventory_path == "collection.mechbay"
    assert reloaded.settings["per_page"] == 50

    raw = json.loads((tmp_path / document_service.STATE_FILENAME).read_text(encoding="utf-8"))
    assert raw["inventory_path"] == "collection.mechbay"
