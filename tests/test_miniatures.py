from __future__ import annotations

import io
import json


def test_add_miniature(client, mini_data):
    resp = client.post("/miniatures/add", data=mini_data, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert str(mini_data["unique_id"]) in body


def test_edit_miniature(client, mini_data):
    # Add first
    client.post("/miniatures/add", data=mini_data)
    # Find id by listing
    list_resp = client.get("/miniatures")
    assert str(mini_data["unique_id"]) in list_resp.get_data(as_text=True)

    # naive parse to get first id present in page
    # In real app, you'd query DB; for test simplicity, update via export/import
    from app.services.miniature_service import get_all_miniatures

    mid = get_all_miniatures()[0].id
    updated = mini_data | {"prefix": "BNC", "chassis": "Banshee", "unique_id": 1003}
    resp = client.post(f"/miniatures/{mid}/edit", data=updated, follow_redirects=True)
    assert resp.status_code == 200
    assert "Banshee" in resp.get_data(as_text=True)


def test_delete_miniature(client, mini_data):
    client.post("/miniatures/add", data=mini_data)
    from app.services.miniature_service import get_all_miniatures

    mid = get_all_miniatures()[0].id
    resp = client.post(f"/miniatures/{mid}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert str(mini_data["unique_id"]) not in resp.get_data(as_text=True)


def test_export_import_json(client, mini_data):
    # Add two entries
    client.post("/miniatures/add", data=mini_data)
    client.post(
        "/miniatures/add",
        data={
            "series": "A",
            "unique_id": 1002,
            "prefix": "BNC",
            "chassis": "Banshee",
            "type": "Mech",
        },
    )

    # Export
    export_resp = client.get("/miniatures/export")
    assert export_resp.status_code == 200
    exported = json.loads(export_resp.data.decode("utf-8"))
    assert any(m["unique_id"] == mini_data["unique_id"] for m in exported)

    # Overwrite import with only one piece
    one = json.dumps([exported[0]]).encode("utf-8")
    data = {"file": (io.BytesIO(one), "import.json")}
    import_resp = client.post(
        "/miniatures/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert import_resp.status_code == 200

    # Now list should have only one record
    list_resp = client.get("/miniatures")
    body = list_resp.get_data(as_text=True)
    assert str(exported[0]["unique_id"]) in body
    assert str(exported[1]["unique_id"]) not in body


def test_series_independence(client):
    """Test that same unique_id can exist in different series."""
    # Add unique_id=1 in Series A
    client.post(
        "/miniatures/add",
        data={
            "series": "A",
            "unique_id": 1,
            "prefix": "WHM",
            "chassis": "Warhammer",
            "type": "Mech",
        },
    )

    # Add unique_id=1 in Series B (should succeed)
    resp = client.post(
        "/miniatures/add",
        data={
            "series": "B",
            "unique_id": 1,
            "prefix": "Vedette",
            "chassis": "Vedette Tank",
            "type": "Vehicle",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"Miniature added" in resp.data

    # Verify both exist
    from app.services.miniature_service import get_all_miniatures

    all_minis = get_all_miniatures()
    assert len(all_minis) == 2
    assert all_minis[0].unique_id == 1
    assert all_minis[1].unique_id == 1
    assert all_minis[0].series != all_minis[1].series
