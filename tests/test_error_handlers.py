from __future__ import annotations

from app.services.force_service import get_force_by_id


def test_404_html(client):
    """Test 404 HTML response renders custom error page."""
    resp = client.get("/nonexistent-page")

    assert resp.status_code == 404
    assert "Page Not Found" in resp.get_data(as_text=True)


def test_404_json(client):
    """Test 404 JSON response when request is sent as JSON."""
    resp = client.get(
        "/nonexistent-page",
        headers={"Accept": "application/json"},
        content_type="application/json",
    )

    assert resp.status_code == 404
    assert resp.is_json
    assert resp.get_json() == {"success": False, "error": "Not found"}


def test_health_endpoint(client):
    """Test health endpoint returns OK status JSON."""
    resp = client.get("/health")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    assert payload.get("status") == "ok"


def test_miniature_add_missing_required_fields(client):
    """Test add miniature with missing required fields re-renders form with errors."""
    resp = client.post(
        "/miniatures/add",
        data={"series": "A", "unique_id": 1001},
    )

    assert resp.status_code == 200
    assert "required" in resp.get_data(as_text=True).lower()


def test_miniature_add_invalid_unique_id(client):
    """Test add miniature with non-integer unique_id shows validation error."""
    resp = client.post(
        "/miniatures/add",
        data={
            "series": "A",
            "unique_id": "abc",
            "prefix": "WHM",
            "chassis": "Warhammer",
            "type": "Mech",
        },
    )

    assert resp.status_code == 200
    assert "unique id must be an integer" in resp.get_data(as_text=True).lower()


def test_miniature_add_duplicate_unique_id(client):
    """Test duplicate series+unique_id is rejected with duplicate message."""
    data = {
        "series": "A",
        "unique_id": 1001,
        "prefix": "WHM",
        "chassis": "Warhammer",
        "type": "Mech",
    }

    first = client.post("/miniatures/add", data=data, follow_redirects=True)
    assert first.status_code == 200

    resp = client.post("/miniatures/add", data=data)

    assert resp.status_code == 200
    assert "already exists in series" in resp.get_data(as_text=True).lower()


def test_miniature_edit_duplicate_unique_id(client):
    """Test editing a miniature to a taken series+unique_id is rejected."""
    first_data = {
        "series": "A",
        "unique_id": 1001,
        "prefix": "WHM",
        "chassis": "Warhammer",
        "type": "Mech",
    }
    second_data = {
        "series": "A",
        "unique_id": 1002,
        "prefix": "ATL",
        "chassis": "Atlas",
        "type": "Mech",
    }

    client.post("/miniatures/add", data=first_data, follow_redirects=True)
    client.post("/miniatures/add", data=second_data, follow_redirects=True)

    with client.application.app_context():
        from app.services.miniature_service import get_all_miniatures

        second = next(m for m in get_all_miniatures() if m.unique_id == 1002)

    resp = client.post(
        f"/miniatures/{second.id}/edit",
        data={**second_data, "unique_id": 1001},
    )

    assert resp.status_code == 200
    assert "already exists in series" in resp.get_data(as_text=True).lower()


def test_miniature_edit_not_found(client):
    """Test edit route for missing miniature shows not found message."""
    resp = client.get("/miniatures/99999/edit", follow_redirects=True)

    assert resp.status_code == 200
    assert "not found" in resp.get_data(as_text=True).lower()


def test_miniature_delete_not_found(client):
    """Test delete route for missing miniature shows not found message."""
    resp = client.post("/miniatures/99999/delete", follow_redirects=True)

    assert resp.status_code == 200
    assert "not found" in resp.get_data(as_text=True).lower()


def test_bulk_action_no_data(client):
    """Test bulk action with missing JSON payload returns 400."""
    resp = client.post("/miniatures/bulk-action")

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload is not None
    assert payload.get("success") is False


def test_bulk_action_no_ids(client):
    """Test bulk action with empty ids returns 400."""
    resp = client.post(
        "/miniatures/bulk-action",
        json={"action": "set_status", "ids": [], "value": "Active"},
    )

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload is not None
    assert payload.get("success") is False


def test_bulk_action_unknown_action(client):
    """Test bulk action with unknown action returns 400."""
    resp = client.post(
        "/miniatures/bulk-action",
        json={"action": "invalid", "ids": [1], "value": "Active"},
    )

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload is not None
    assert payload.get("success") is False


def test_force_add_miniature_duplicate(client, minimal_force, sample_miniatures):
    """Test adding a miniature already assigned in force returns duplicate error."""
    force = get_force_by_id(minimal_force)
    assert force is not None
    assert force.lances

    lance_id = force.lances[0].id
    miniature_id = sample_miniatures[0]

    resp = client.post(
        f"/forces/{minimal_force}/add-miniature",
        json={"miniature_id": miniature_id, "lance_id": lance_id},
    )

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload is not None
    assert payload.get("success") is False
    assert "already in force" in payload.get("error", "").lower()


def test_force_rename_not_found_json(client):
    """Test renaming missing force via JSON returns 404."""
    resp = client.post("/forces/99999/rename", json={"name": "Ghost Force"})

    assert resp.status_code == 404
    payload = resp.get_json()
    assert payload is not None
    assert payload.get("success") is False
    assert "not found" in payload.get("error", "").lower()
