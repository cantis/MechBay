from __future__ import annotations

import io
import json


def test_list_templates(client):
    """Test listing lance templates returns 200."""
    resp = client.get("/lance-templates")
    assert resp.status_code == 200


def test_create_template(client):
    """Test creating a lance template via form POST."""
    resp = client.post(
        "/lance-templates/create",
        data={
            "name": "Heavy Lance",
            "description": "Frontline heavy mechs",
            "chassis_0": "Warhammer",
            "chassis_1": "Thunderbolt",
            "chassis_2": "Marauder",
            "chassis_3": "Archer",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "created successfully" in body
    assert "Heavy Lance" in body


def test_create_template_missing_name(client):
    """Test creating a template without a name shows danger flash."""
    resp = client.post(
        "/lance-templates/create",
        data={
            "description": "No name template",
            "chassis_0": "Warhammer",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Template name is required" in resp.get_data(as_text=True)


def test_create_template_missing_patterns(client):
    """Test creating a template without chassis patterns shows danger flash."""
    resp = client.post(
        "/lance-templates/create",
        data={
            "name": "Patternless Lance",
            "description": "No patterns provided",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "At least one chassis pattern is required" in resp.get_data(as_text=True)


def test_create_template_get(client):
    """Test create template form page returns 200."""
    resp = client.get("/lance-templates/create")
    assert resp.status_code == 200


def test_template_detail(client, sample_template):
    """Test viewing template details returns 200 and template name."""
    resp = client.get(f"/lance-templates/{sample_template}")
    assert resp.status_code == 200
    assert "Standard Assault Lance" in resp.get_data(as_text=True)


def test_template_detail_not_found(client):
    """Test viewing non-existent template redirects to list page."""
    resp = client.get("/lance-templates/99999")
    assert resp.status_code in {301, 302}
    assert "/lance-templates" in resp.headers.get("Location", "")


def test_edit_template(client, sample_template):
    """Test editing an existing template via form POST."""
    resp = client.post(
        f"/lance-templates/{sample_template}/edit",
        data={
            "name": "Updated Assault Lance",
            "description": "Updated heavy configuration",
            "chassis_0": "Atlas",
            "chassis_1": "King Crab",
            "chassis_2": "Highlander",
            "chassis_3": "Awesome",
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "updated successfully" in body
    assert "Updated Assault Lance" in body


def test_edit_template_get(client, sample_template):
    """Test edit template form page returns 200."""
    resp = client.get(f"/lance-templates/{sample_template}/edit")
    assert resp.status_code == 200


def test_edit_template_not_found(client):
    """Test editing non-existent template redirects with not found message."""
    resp = client.get("/lance-templates/99999/edit", follow_redirects=True)
    assert resp.status_code == 200
    assert "Template not found" in resp.get_data(as_text=True)


def test_delete_template(client, sample_template):
    """Test deleting an existing template shows info flash."""
    resp = client.post(f"/lance-templates/{sample_template}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert "Template deleted" in resp.get_data(as_text=True)


def test_delete_template_not_found(client):
    """Test deleting non-existent template shows not found message."""
    resp = client.post("/lance-templates/99999/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert "Template not found" in resp.get_data(as_text=True)


def test_export_templates(client, sample_template):
    """Test exporting templates returns JSON payload."""
    resp = client.get("/lance-templates/export")
    assert resp.status_code == 200
    assert "application/json" in resp.content_type

    payload = json.loads(resp.data.decode("utf-8"))
    assert payload["schema_version"] == 1
    assert "templates" in payload
    assert any(t["name"] == "Standard Assault Lance" for t in payload["templates"])


def test_import_templates_get(client):
    """Test import page GET returns 200."""
    resp = client.get("/lance-templates/import")
    assert resp.status_code == 200


def test_import_templates_no_file(client):
    """Test import POST without file shows warning flash."""
    resp = client.post("/lance-templates/import", data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert "No file selected" in resp.get_data(as_text=True)


def test_import_templates_valid_file(client):
    """Test importing a valid templates JSON file succeeds."""
    import_payload = {
        "schema_version": 1,
        "export_timestamp": "2026-04-14T00:00:00",
        "template_count": 1,
        "templates": [
            {
                "name": "Imported Fire Lance",
                "description": "Long-range fire support",
                "chassis_patterns": ["Catapult", "Archer", "Rifleman", "JagerMech"],
            }
        ],
    }

    data = {
        "file": (
            io.BytesIO(json.dumps(import_payload).encode("utf-8")),
            "lance_templates_import.json",
        )
    }

    resp = client.post(
        "/lance-templates/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Imported 1 template(s)." in body
    assert "Imported Fire Lance" in body
