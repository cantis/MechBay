from __future__ import annotations

import io
import json

from app.services.miniature_service import add_miniature


def _add_batch(n: int, series: str = "A") -> None:
    """Add *n* miniatures to the DB quickly."""
    for i in range(1, n + 1):
        add_miniature(
            {
                "series": series,
                "unique_id": i,
                "prefix": "WHM",
                "chassis": f"Mech{i:03d}",
                "type": "Mech",
            }
        )


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


def test_legacy_inventory_json_via_file_upload(client, mini_data):
    """Legacy miniature JSON can be opened through File upload inventory."""
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

    one = json.dumps(
        [
            {
                "series": mini_data["series"],
                "unique_id": mini_data["unique_id"],
                "prefix": mini_data["prefix"],
                "chassis": mini_data["chassis"],
                "type": mini_data["type"],
            }
        ]
    ).encode("utf-8")
    data = {"file": (io.BytesIO(one), "legacy.json"), "confirm": "1"}
    import_resp = client.post(
        "/files/upload/inventory",
        data=data,
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"},
        follow_redirects=True,
    )
    assert import_resp.status_code == 200

    list_resp = client.get("/miniatures")
    body = list_resp.get_data(as_text=True)
    assert str(mini_data["unique_id"]) in body
    assert "1002" not in body


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


# ===========================================================================
# Configurable page size (per_page query param + cookie)
# ===========================================================================


def test_per_page_limits_rows_shown(client):
    """?per_page=20 with 25 records shows pagination nav for page 2."""
    _add_batch(25)
    resp = client.get("/miniatures?per_page=20")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Pagination nav should contain a link to page 2
    assert "page=2" in body


def test_list_page_beyond_total_renders_last_page(client):
    """An out-of-range page param clamps to the last page and still shows rows."""
    _add_batch(25)
    resp = client.get("/miniatures?per_page=20&page=99")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Mech021" in body
    assert "Mech025" in body
    assert "page=2" in body


def test_per_page_100_fits_all_on_one_page(client):
    """?per_page=100 with 25 records shows no pagination nav."""
    _add_batch(25)
    resp = client.get("/miniatures?per_page=100")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # No multi-page nav when everything fits — pagination nav element absent
    assert 'aria-label="Inventory pagination"' not in body


def test_per_page_invalid_falls_back_to_50(client):
    """An invalid per_page value falls back to 50 without error."""
    _add_batch(5)
    resp = client.get("/miniatures?per_page=999")
    assert resp.status_code == 200
    # Dropdown should show the fallback value
    assert "Per page: 50" in resp.get_data(as_text=True)


def test_per_page_sets_cookie(client):
    """Selecting a page size sets the mechbay_per_page cookie."""
    resp = client.get("/miniatures?per_page=20")
    assert resp.status_code == 200
    cookie_header = resp.headers.get("Set-Cookie", "")
    assert "mechbay_per_page=20" in cookie_header


def test_per_page_cookie_default_used_when_no_param(client):
    """Without a URL param the cookie value is used as per_page."""
    _add_batch(25)
    # First visit with explicit per_page=20 sets the cookie
    client.get("/miniatures?per_page=20")
    # Second visit without param — cookie should kick in, showing page nav
    resp = client.get("/miniatures")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Per page: 20" in body


def test_per_page_url_param_beats_cookie(client):
    """A URL param overrides the cookie value."""
    _add_batch(5)
    # Set cookie to 20
    client.get("/miniatures?per_page=20")
    # Override with URL param 50
    resp = client.get("/miniatures?per_page=50")
    assert "Per page: 50" in resp.get_data(as_text=True)


def test_per_page_dropdown_visible_in_html(client):
    """The per_page dropdown renders all valid size options."""
    resp = client.get("/miniatures")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    for size in (20, 30, 40, 50, 100):
        assert f"per_page={size}" in body
