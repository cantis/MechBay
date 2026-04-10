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


def test_duplicate_prefill(client):
    """Duplicating a miniature should prefill the add form with next unique_id in series."""
    # Add two entries in Series A
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
    client.post(
        "/miniatures/add",
        data={
            "series": "A",
            "unique_id": 2,
            "prefix": "BNC",
            "chassis": "Banshee",
            "type": "Mech",
        },
    )

    from app.services.miniature_service import get_all_miniatures

    minis = get_all_miniatures()
    # Duplicate the second one
    target_id = next(m.id for m in minis if m.unique_id == 2 and m.series == "A")
    resp = client.get(f"/miniatures/{target_id}/duplicate")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Expect next unique id (3) present in value attribute
    assert 'value="3"' in html or ">3<" in html
    # Prefilled chassis
    assert "Banshee" in html


def test_get_next_unique_id_empty_series():
    """Test get_next_unique_id returns 1 for empty series."""
    # Arrange
    from app.services.miniature_service import get_next_unique_id

    # Act
    next_id = get_next_unique_id("Z")  # Series with no miniatures

    # Assert
    assert next_id == 1


def test_get_next_unique_id_sequential():
    """Test get_next_unique_id returns max+1 for sequential IDs."""
    # Arrange
    from app.services.miniature_service import add_miniature, get_next_unique_id

    add_miniature(
        {"series": "B", "unique_id": 1, "prefix": "TEST", "chassis": "Test1", "type": "Mech"}
    )
    add_miniature(
        {"series": "B", "unique_id": 2, "prefix": "TEST", "chassis": "Test2", "type": "Mech"}
    )
    add_miniature(
        {"series": "B", "unique_id": 3, "prefix": "TEST", "chassis": "Test3", "type": "Mech"}
    )

    # Act
    next_id = get_next_unique_id("B")

    # Assert
    assert next_id == 4


def test_get_next_unique_id_with_gap():
    """Test get_next_unique_id fills gaps in sequence."""
    # Arrange
    from app.services.miniature_service import add_miniature, get_next_unique_id

    add_miniature(
        {"series": "C", "unique_id": 1, "prefix": "TEST", "chassis": "Test1", "type": "Mech"}
    )
    add_miniature(
        {"series": "C", "unique_id": 2, "prefix": "TEST", "chassis": "Test2", "type": "Mech"}
    )
    add_miniature(
        {"series": "C", "unique_id": 4, "prefix": "TEST", "chassis": "Test4", "type": "Mech"}
    )
    add_miniature(
        {"series": "C", "unique_id": 5, "prefix": "TEST", "chassis": "Test5", "type": "Mech"}
    )

    # Act
    next_id = get_next_unique_id("C")

    # Assert
    assert next_id == 3  # Fills the gap, not max+1


def test_get_next_unique_id_missing_start():
    """Test get_next_unique_id returns 1 when sequence doesn't start at 1."""
    # Arrange
    from app.services.miniature_service import add_miniature, get_next_unique_id

    add_miniature(
        {"series": "D", "unique_id": 2, "prefix": "TEST", "chassis": "Test2", "type": "Mech"}
    )
    add_miniature(
        {"series": "D", "unique_id": 3, "prefix": "TEST", "chassis": "Test3", "type": "Mech"}
    )
    add_miniature(
        {"series": "D", "unique_id": 4, "prefix": "TEST", "chassis": "Test4", "type": "Mech"}
    )

    # Act
    next_id = get_next_unique_id("D")

    # Assert
    assert next_id == 1  # Fills from the start


def test_get_next_unique_id_multiple_gaps():
    """Test get_next_unique_id returns first gap when multiple exist."""
    # Arrange
    from app.services.miniature_service import add_miniature, get_next_unique_id

    add_miniature(
        {"series": "E", "unique_id": 1, "prefix": "TEST", "chassis": "Test1", "type": "Mech"}
    )
    add_miniature(
        {"series": "E", "unique_id": 3, "prefix": "TEST", "chassis": "Test3", "type": "Mech"}
    )
    add_miniature(
        {"series": "E", "unique_id": 5, "prefix": "TEST", "chassis": "Test5", "type": "Mech"}
    )
    add_miniature(
        {"series": "E", "unique_id": 7, "prefix": "TEST", "chassis": "Test7", "type": "Mech"}
    )

    # Act
    next_id = get_next_unique_id("E")

    # Assert
    assert next_id == 2  # First gap, not any later gap


def test_add_form_prefills_next_id(client):
    """Test add form GET request includes next_id in template."""
    # Arrange
    # Empty database, expect next_id=1 for series A

    # Act
    resp = client.get("/miniatures/add")

    # Assert
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'value="1"' in html  # Default next_id for empty series A
    assert "First available ID" in html  # Helper text


def test_add_miniature_saves_faction(client):
    """Test that faction field is properly saved when adding a miniature."""
    # Arrange
    data = {
        "series": "A",
        "unique_id": 1,
        "prefix": "WHM",
        "chassis": "Warhammer",
        "type": "Mech",
        "faction": "Clan Wolf",
        "status": "Finished",
        "tray_id": "T2",
        "notes": "Test faction save",
    }

    # Act
    resp = client.post("/miniatures/add", data=data, follow_redirects=True)

    # Assert
    assert resp.status_code == 200

    # Verify faction was saved by querying the database
    from app.services.miniature_service import get_all_miniatures

    minis = get_all_miniatures()
    assert len(minis) == 1
    assert minis[0].faction == "Clan Wolf"
    assert minis[0].chassis == "Warhammer"
    assert minis[0].status == "Finished"
