from __future__ import annotations

from app.services import force_service

# ============================================================================
# BASIC CRUD ROUTES
# ============================================================================


def test_create_force(client):
    """Test creating a force via form POST succeeds and flashes success."""
    resp = client.post("/forces/create", data={"name": "Test Force"}, follow_redirects=True)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "created and activated" in body
    assert "Test Force" in body


def test_create_force_empty_name(client):
    """Test creating a force with empty name redirects and flashes danger."""
    resp = client.post("/forces/create", data={"name": "   "}, follow_redirects=True)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Force name is required" in body


def test_force_detail(client, minimal_force):
    """Test force detail route renders existing force."""
    force = force_service.get_force_by_id(minimal_force)

    resp = client.get(f"/forces/{minimal_force}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert force is not None
    assert force.name in body


def test_force_detail_not_found(client):
    """Test force detail route redirects when force does not exist."""
    resp = client.get("/forces/99999", follow_redirects=True)

    assert resp.status_code == 200
    assert resp.request.path == "/forces"
    assert "Force not found" in resp.get_data(as_text=True)


def test_delete_force(client, minimal_force):
    """Test deleting an existing force redirects and flashes info."""
    resp = client.post(f"/forces/{minimal_force}/delete", follow_redirects=True)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Force deleted" in body


def test_delete_force_not_found(client):
    """Test deleting a non-existent force flashes not found."""
    resp = client.post("/forces/99999/delete", follow_redirects=True)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Force not found" in body


# ============================================================================
# ACTIVATE / DEACTIVATE
# ============================================================================


def test_activate_force(client, minimal_force):
    """Test activating a force flashes activated."""
    resp = client.post(f"/forces/{minimal_force}/activate", follow_redirects=True)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "activated" in body


def test_deactivate_all(client, minimal_force):
    """Test deactivating all forces flashes active force cleared."""
    resp = client.post("/forces/deactivate-all", follow_redirects=True)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Active force cleared" in body


# ============================================================================
# RENAME FORCE (JSON API)
# ============================================================================


def test_rename_force(client, minimal_force):
    """Test renaming a force via JSON API succeeds."""
    resp = client.post(f"/forces/{minimal_force}/rename", json={"name": "New Name"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"success": True, "name": "New Name"}


def test_rename_force_empty(client, minimal_force):
    """Test renaming a force with empty name returns 400."""
    resp = client.post(f"/forces/{minimal_force}/rename", json={"name": "   "})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Name is required"


def test_rename_force_not_found(client):
    """Test renaming non-existent force returns 404."""
    resp = client.post("/forces/99999/rename", json={"name": "Ghost Force"})

    assert resp.status_code == 404
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Force not found"


# ============================================================================
# ADD MINIATURE (DUAL MODE)
# ============================================================================


def test_add_miniature_json(client, minimal_force, sample_miniatures):
    """Test adding miniature via JSON API succeeds."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    lance_id = force.lances[0].id

    resp = client.post(
        f"/forces/{minimal_force}/add-miniature",
        json={"miniature_id": sample_miniatures[2], "lance_id": lance_id},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True


def test_add_miniature_form(client, minimal_force, sample_miniatures):
    """Test adding miniature via form submission succeeds."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    lance_id = force.lances[0].id

    resp = client.post(
        f"/forces/{minimal_force}/add-miniature",
        data={"miniature_id": sample_miniatures[2], "lance_id": lance_id},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Miniature added to lance" in body


def test_add_miniature_form_return_to_force(client, minimal_force, sample_miniatures):
    """Adding from force detail returns to force-building anchor."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    lance_id = force.lances[0].id

    resp = client.post(
        f"/forces/{minimal_force}/add-miniature",
        data={
            "miniature_id": sample_miniatures[2],
            "lance_id": lance_id,
            "return_to_force": "1",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/forces/{minimal_force}#force-building")


def test_add_miniature_missing_params_json(client, minimal_force):
    """Test add miniature JSON with missing params returns 400."""
    resp = client.post(f"/forces/{minimal_force}/add-miniature", json={"lance_id": 1})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Missing parameters"


def test_add_miniature_invalid_id_json(client, minimal_force):
    """Test add miniature JSON with invalid ID values returns 400."""
    resp = client.post(
        f"/forces/{minimal_force}/add-miniature",
        json={"miniature_id": "abc", "lance_id": "1"},
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid miniature or lance ID"


def test_add_miniature_missing_params_form(client, minimal_force):
    """Test add miniature form with missing params redirects with error flash."""
    resp = client.post(
        f"/forces/{minimal_force}/add-miniature",
        data={"lance_id": "1"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Missing parameters" in body


# ============================================================================
# REMOVE MINIATURE (DUAL MODE)
# ============================================================================


def test_remove_miniature_json(client, minimal_force, sample_miniatures):
    """Test removing miniature via JSON API succeeds."""
    resp = client.post(
        f"/forces/{minimal_force}/remove-miniature",
        json={"miniature_id": sample_miniatures[0]},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"success": True}


def test_remove_miniature_not_in_force_json(client, minimal_force, sample_miniatures):
    """Test removing miniature not assigned to force returns 404."""
    resp = client.post(
        f"/forces/{minimal_force}/remove-miniature",
        json={"miniature_id": sample_miniatures[2]},
    )

    assert resp.status_code == 404
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Miniature not found in force"


def test_remove_miniature_invalid_id_json(client, minimal_force):
    """Test removing miniature with invalid ID returns 400."""
    resp = client.post(
        f"/forces/{minimal_force}/remove-miniature",
        json={"miniature_id": "abc"},
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid miniature ID"


# ============================================================================
# MOVE MINIATURE (JSON ONLY)
# ============================================================================


def test_move_miniature(client, minimal_force, sample_miniatures):
    """Test moving miniature between lances via JSON API succeeds."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    source_lance_id = force.lances[0].id

    new_lance = force_service.create_empty_lance(minimal_force, "Bravo Lance")
    assert new_lance is not None

    resp = client.post(
        f"/forces/{minimal_force}/move-miniature",
        json={
            "miniature_id": sample_miniatures[0],
            "target_lance_id": new_lance.id,
            "position": 1,
        },
    )

    assert source_lance_id != new_lance.id
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True


def test_move_miniature_missing_params(client, minimal_force, sample_miniatures):
    """Test move miniature with missing params returns 400."""
    resp = client.post(
        f"/forces/{minimal_force}/move-miniature",
        json={"miniature_id": sample_miniatures[0]},
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Missing parameters"


def test_move_miniature_invalid_params(client, minimal_force, sample_miniatures):
    """Test move miniature with invalid params returns 400."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    lance_id = force.lances[0].id

    resp = client.post(
        f"/forces/{minimal_force}/move-miniature",
        json={
            "miniature_id": sample_miniatures[0],
            "target_lance_id": lance_id,
            "position": "abc",
        },
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"] == "Invalid parameters"


# ============================================================================
# LANCE OPERATIONS
# ============================================================================


def test_create_lance(client, minimal_force):
    """Test creating a lance redirects to force detail with success flash."""
    resp = client.post(
        f"/forces/{minimal_force}/lances/create",
        data={"name": "Bravo Lance"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "created" in body


def test_delete_lance(client, minimal_force):
    """Test deleting a lance redirects to force detail with info flash."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    lance_id = force.lances[0].id

    resp = client.post(
        f"/forces/{minimal_force}/lances/{lance_id}/delete",
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Lance deleted" in body


def test_rename_lance(client, minimal_force):
    """Test renaming a lance via JSON API succeeds."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None
    lance_id = force.lances[0].id

    resp = client.post(
        f"/forces/{minimal_force}/lances/{lance_id}/rename",
        json={"name": "Renamed Lance"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["name"] == "Renamed Lance"


# ============================================================================
# FORCE REPORT
# ============================================================================


def test_force_report(client, minimal_force):
    """Test force report route renders for existing force."""
    force = force_service.get_force_by_id(minimal_force)
    assert force is not None

    resp = client.get(f"/forces/{minimal_force}/report")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert force.name in body
