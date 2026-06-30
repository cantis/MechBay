from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import pytest

from app.services import document_service, force_service, inventory_project_service
from app.services.force_service import import_force_from_data
from app.services.lance_template_service import create_template
from app.services.miniature_service import get_all_miniatures

AJAX = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _document_state_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(document_service, "get_app_data_dir", lambda: tmp_path)
    document_service.clear_inventory_dirty()
    document_service.set_inventory_path(None)
    document_service.clear_all_force_documents()
    yield


def test_inventory_project_round_trip(client, sample_miniatures):
    create_template("Scout", ["Warhammer", "Atlas"], description="Test")
    document_service.set_inventory_path(None)
    document_service.clear_inventory_dirty()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "collection.mechbay"
        inventory_project_service.save_project_to_path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema_version"] == 2
        assert data["type"] == "inventory"
        assert len(data["miniatures"]) >= 1
        assert len(data["templates"]) == 1

        force = force_service.create_force("Temp Force")
        lance = force_service.create_empty_lance(force.id, "Alpha")
        force_service.add_miniature_to_lance(sample_miniatures[0], lance.id)
        assert len(force_service.get_all_forces()) == 1

        inventory_project_service.load_project_from_path(path)

    assert force_service.get_all_forces() == []
    assert len(get_all_miniatures()) >= 1
    status = document_service.get_status()
    assert status["inventory_dirty"] is False
    assert status["inventory_path"] == str(path.resolve())


def test_new_inventory_clears_forces(client, minimal_force):
    inventory_project_service.new_inventory_project()
    assert force_service.get_all_forces() == []
    assert get_all_miniatures() == []


def test_force_name_collision_suffix(client):
    force_service.create_force("Collision Test Force")
    payload = {
        "schema_version": 2,
        "force_name": "Collision Test Force",
        "lances": [],
    }
    result = import_force_from_data(payload)
    assert result["force_name"] == "Collision Test Force (2)"


def test_save_force_uses_mbforce_extension(client, minimal_force, tmp_path):
    export_path = tmp_path / "test.mbforce"
    force_service.save_force_to_path(minimal_force, export_path)
    assert export_path.exists()
    assert export_path.suffix == ".mbforce"


def test_import_force_missing_miniatures_dict(client):
    payload = {
        "schema_version": 2,
        "force_name": "Sparse Force",
        "lances": [
            {
                "name": "L1",
                "order": 1,
                "header_color": "#dbeafe",
                "miniatures": [
                    {
                        "series": "Z",
                        "unique_id": 99999,
                        "prefix": "X",
                        "chassis": "Missing",
                        "type": "Mech",
                        "order": 0,
                    }
                ],
            }
        ],
    }
    result = import_force_from_data(payload)
    assert len(result["missing_miniatures"]) == 1
    missing = result["missing_miniatures"][0]
    assert missing["series"] == "Z"
    assert missing["unique_id"] == 99999


def test_file_routes_inventory_save(client, sample_miniatures, tmp_path, monkeypatch):
    monkeypatch.setenv("MECHBAY_NO_NATIVE_DIALOGS", "1")
    path = tmp_path / "route_test.mechbay"
    document_service.set_inventory_path(str(path))
    document_service.mark_inventory_dirty()

    response = client.post("/files/inventory/save", headers=AJAX)
    assert response.status_code == 200
    assert path.exists()
    assert document_service.get_status()["inventory_dirty"] is False


def test_load_legacy_miniature_list_json(client, sample_miniatures):
    payload = [
        {
            "series": "A",
            "unique_id": 42,
            "prefix": "WHM",
            "chassis": "Warhammer",
            "type": "Mech",
        }
    ]
    result = inventory_project_service.load_project_from_data(payload)
    assert result["miniatures"] == 1
    assert len(get_all_miniatures()) == 1


def test_load_legacy_template_json(client):
    payload = {
        "schema_version": 1,
        "templates": [
            {
                "name": "Legacy Lance",
                "description": "Imported templates only",
                "chassis_patterns": ["Atlas", "Warhammer"],
            }
        ],
    }
    result = inventory_project_service.load_project_from_data(payload)
    assert result["templates"] == 1
    assert result["miniatures"] == 0


def test_load_force_json_rejected_as_inventory(client):
    payload = {"schema_version": 2, "force_name": "Wrong file", "lances": []}
    with pytest.raises(ValueError, match="force file"):
        inventory_project_service.load_project_from_data(payload)


def test_files_status_includes_native_flag(client, monkeypatch):
    monkeypatch.setenv("MECHBAY_NO_NATIVE_DIALOGS", "1")
    resp = client.get("/files/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["native_dialogs"] is False
    assert "inventory_label" in data


def test_inventory_new_clears_data(client, sample_miniatures):
    document_service.clear_inventory_dirty()
    resp = client.post("/files/inventory/new", headers=AJAX)
    assert resp.status_code == 200
    assert force_service.get_all_forces() == []
    assert get_all_miniatures() == []


def test_inventory_new_needs_confirm_when_dirty(client, sample_miniatures):
    document_service.mark_inventory_dirty()
    resp = client.post("/files/inventory/new", headers=AJAX)
    assert resp.status_code == 400
    assert resp.get_json()["needs_confirm"] is True

    resp2 = client.post("/files/inventory/new", json={"confirm": "1"}, headers=AJAX)
    assert resp2.status_code == 200


def test_inventory_open_returns_client_dialog_when_native_disabled(client, monkeypatch):
    monkeypatch.setenv("MECHBAY_NO_NATIVE_DIALOGS", "1")
    resp = client.post("/files/inventory/open", headers=AJAX)
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["needs_client_dialog"] is True
    assert payload["mode"] == "open"


def test_inventory_save_as_client_saved(client):
    resp = client.post(
        "/files/inventory/save-as",
        json={"path": "saved.mechbay", "client_saved": True},
        headers=AJAX,
    )
    assert resp.status_code == 200
    status = document_service.get_status()
    assert status["inventory_path"] == "saved.mechbay"
    assert status["inventory_dirty"] is False


def test_inventory_export_route(client, sample_miniatures):
    resp = client.get("/files/inventory/export")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["type"] == "inventory"
    assert len(data["miniatures"]) >= 1


def test_force_save_as_client_saved(client, minimal_force):
    resp = client.post(
        f"/files/force/{minimal_force}/save-as",
        json={"path": "my-force.mbforce", "client_saved": True},
        headers=AJAX,
    )
    assert resp.status_code == 200
    status = document_service.get_status()
    assert status["force_paths"][str(minimal_force)] == "my-force.mbforce"


def test_force_open_client_dialog_when_native_disabled(client, monkeypatch):
    monkeypatch.setenv("MECHBAY_NO_NATIVE_DIALOGS", "1")
    resp = client.post("/files/force/open", headers=AJAX)
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["needs_client_dialog"] is True
    assert payload["kind"] == "force"


def test_upload_force_imports_mbforce(client, minimal_force, sample_miniatures):
    lance = force_service.create_empty_lance(minimal_force, "Upload Lance")
    force_service.add_miniature_to_lance(sample_miniatures[0], lance.id)
    payload = json.loads(force_service.export_force_to_json(minimal_force)[0])
    payload["force_name"] = "Uploaded Force"

    data = {
        "file": (
            io.BytesIO(json.dumps(payload).encode("utf-8")),
            "uploaded.mbforce",
        )
    }
    resp = client.post(
        "/files/upload/force",
        data=data,
        content_type="multipart/form-data",
        headers=AJAX,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "force_id" in body
    assert force_service.get_force_by_id(body["force_id"]) is not None


def test_rename_force_marks_dirty(client, minimal_force):
    document_service.set_force_path(minimal_force, "linked.mbforce")
    document_service.clear_force_dirty(minimal_force)

    force_service.rename_force(minimal_force, "Renamed Force")

    state = document_service.load_state()
    assert minimal_force in state.dirty_force_ids


def test_legacy_routes_removed(client):
    for url in (
        "/miniatures/export",
        "/miniatures/import",
        "/forces/import",
        "/lance-templates/export",
        "/lance-templates/import",
    ):
        assert client.get(url).status_code == 404

    assert client.get("/forces/1/export").status_code == 404
