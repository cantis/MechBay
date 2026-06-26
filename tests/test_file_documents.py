from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.services import document_service, force_service, inventory_project_service
from app.services.force_service import import_force_from_data
from app.services.lance_template_service import create_template
from app.services.miniature_service import get_all_miniatures


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

    response = client.post(
        "/files/inventory/save",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200
    assert path.exists()
    assert document_service.get_status()["inventory_dirty"] is False
