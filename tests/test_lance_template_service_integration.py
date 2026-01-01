"""Integration tests for lance_template_service.py.

Comprehensive tests using realistic miniature inventory. Focus on:
- Complex pattern matching scenarios
- Multi-template operations
- Import/Export with full datasets

Uses sample_miniatures fixture with full inventory.
For fast unit tests, see test_lance_template_service_unit.py.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pytest

from app.services.lance_template_service import (
    create_template,
    export_templates_to_json,
    find_matching_miniature,
    get_all_templates,
    import_templates_from_json,
    match_template_miniatures,
    update_template,
)
from tests.conftest import validate_expunged_object

# ============================================================================
# CRUD OPERATIONS - Integration Tests
# ============================================================================


@pytest.mark.slow
def test_get_all_templates_alphabetical(client):
    """Test templates are returned in alphabetical order."""
    # Create templates in non-alphabetical order
    create_template("Zebra Lance", ["Atlas"], "Last alphabetically")
    create_template("Alpha Strike", ["Warhammer"], "First alphabetically")
    create_template("Medium Support", ["Timber Wolf"], "Middle")
    create_template("Beta Company", ["Mad Cat"], "Second")
    create_template("Charlie Scout", ["Direwolf"], "Third")

    templates = get_all_templates()

    assert len(templates) == 5
    assert templates[0].name == "Alpha Strike"
    assert templates[1].name == "Beta Company"
    assert templates[2].name == "Charlie Scout"
    assert templates[3].name == "Medium Support"
    assert templates[4].name == "Zebra Lance"


@pytest.mark.slow
def test_update_template_replaces_patterns_atomically(client, sample_miniatures):
    """Test updating template replaces all patterns atomically."""
    # Create template with 4 patterns
    template = create_template(
        name="Heavy Lance",
        chassis_patterns=["Atlas", "Warhammer", "Timber Wolf", "Mad Cat"],
        description="Original",
    )

    # Update with 3 different patterns
    updated = update_template(
        template_id=template.id,
        name="Heavy Lance",
        chassis_patterns=["Direwolf", "Summoner", "Stormcrow"],
        description="Updated",
    )

    assert updated is not None
    assert updated.description == "Updated"

    # Verify patterns replaced
    from app.extensions import session_scope
    from app.models.lance_template_miniature import LanceTemplateMiniature

    with session_scope() as session:
        patterns = (
            session.query(LanceTemplateMiniature)
            .filter(LanceTemplateMiniature.template_id == template.id)
            .order_by(LanceTemplateMiniature.order)
            .all()
        )

        assert len(patterns) == 3
        assert patterns[0].chassis_pattern == "Direwolf"
        assert patterns[1].chassis_pattern == "Summoner"
        assert patterns[2].chassis_pattern == "Stormcrow"

    validate_expunged_object(updated, "id", "name", "miniatures")


# ============================================================================
# PATTERN MATCHING - Integration Tests
# ============================================================================


@pytest.mark.slow
def test_find_matching_miniature_exact(client, sample_miniatures):
    """Test finding miniature with exact chassis match."""
    result = find_matching_miniature("Atlas AS7-D", set())

    assert result is not None
    assert "Atlas AS7-D" in result.chassis


@pytest.mark.slow
def test_find_matching_miniature_partial_like(client, sample_miniatures):
    """Test finding miniature with partial LIKE match."""
    result = find_matching_miniature("Warhammer", set())

    assert result is not None
    assert "Warhammer" in result.chassis
    # Should match either WHM-6R or WHM-7M


@pytest.mark.slow
def test_find_matching_miniature_excluded_ids(client, sample_miniatures):
    """Test excluded_ids skips first match and finds second."""
    # Find first Warhammer
    first = find_matching_miniature("Warhammer", set())
    assert first is not None

    # Find second Warhammer by excluding first
    second = find_matching_miniature("Warhammer", {first.id})
    assert second is not None
    assert second.id != first.id
    assert "Warhammer" in second.chassis


@pytest.mark.slow
def test_match_template_full_matches(client, sample_miniatures):
    """Test matching template with all patterns available."""
    template = create_template(
        name="Standard Lance", chassis_patterns=["Atlas", "Warhammer", "Timber Wolf", "Mad Cat"]
    )

    result = match_template_miniatures(template.id, set())

    assert len(result["matched"]) == 4
    assert result["missing"] == []

    # Verify matched structure: list of tuples (pattern, mini_id, mini)
    for match in result["matched"]:
        assert isinstance(match, tuple)
        assert len(match) == 3
        pattern, mini_id, mini = match
        assert isinstance(pattern, str)
        assert isinstance(mini_id, int)
        assert mini is not None

        # Validate miniature object accessible
        validate_expunged_object(mini, "id", "chassis", "series", "unique_id")


@pytest.mark.slow
def test_match_template_partial_missing(client, sample_miniatures):
    """Test matching template with some patterns missing."""
    template = create_template(
        name="Mixed Lance",
        chassis_patterns=[
            "Atlas",
            "Warhammer",
            "Nonexistent1",
            "Timber Wolf",
            "Nonexistent2",
            "Mad Cat",
        ],
    )

    result = match_template_miniatures(template.id, set())

    assert len(result["matched"]) == 4
    assert len(result["missing"]) == 2
    assert "Nonexistent1" in result["missing"]
    assert "Nonexistent2" in result["missing"]


# ============================================================================
# IMPORT/EXPORT - Integration Tests
# ============================================================================


@pytest.mark.slow
def test_export_all_templates_structure(client):
    """Test export generates correct JSON structure and filename."""
    # Create templates with varying complexity
    create_template("Light Scout", ["Adder", "Kit Fox", "Mist Lynx"], "Fast recon")
    create_template(
        "Medium Striker", ["Stormcrow", "Summoner", "Mad Cat", "Timber Wolf"], "Balanced"
    )
    create_template(
        "Heavy Assault",
        ["Atlas", "Direwolf", "Warhammer", "Atlas", "Direwolf"],
        "Maximum firepower",
    )

    json_str, filename = export_templates_to_json()

    # Validate filename
    assert re.match(r"LanceTemplates_\d{8}_\d{6}\.json", filename)

    # Parse and validate JSON
    data = json.loads(json_str)

    assert "export_timestamp" in data
    assert data["template_count"] == 3
    assert "templates" in data
    assert len(data["templates"]) == 3

    # Validate template structure
    for template in data["templates"]:
        assert "name" in template
        assert "description" in template
        assert "chassis_patterns" in template
        assert isinstance(template["chassis_patterns"], list)
        assert len(template["chassis_patterns"]) > 0


@pytest.mark.slow
def test_import_creates_from_export(client):
    """Test importing creates templates from exported JSON."""
    # Create and export templates
    create_template("Lance 1", ["Atlas", "Warhammer", "Timber Wolf"])
    create_template("Lance 2", ["Mad Cat", "Direwolf", "Summoner", "Stormcrow"])
    create_template("Lance 3", ["Adder", "Kit Fox"])

    json_str, filename = export_templates_to_json()

    # Clear templates by deleting each one individually
    from app.services.lance_template_service import delete_template

    all_templates = get_all_templates()
    for template in all_templates:
        delete_template(template.id)

    # Import
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        temp_path = f.name

    try:
        result = import_templates_from_json(temp_path)

        templates = get_all_templates()
        assert len(templates) == 3

        # Verify pattern counts
        from app.extensions import session_scope
        from app.models.lance_template_miniature import LanceTemplateMiniature

        with session_scope() as session:
            for template in templates:
                pattern_count = (
                    session.query(LanceTemplateMiniature)
                    .filter(LanceTemplateMiniature.template_id == template.id)
                    .count()
                )

                if template.name == "Lance 1":
                    assert pattern_count == 3
                elif template.name == "Lance 2":
                    assert pattern_count == 4
                elif template.name == "Lance 3":
                    assert pattern_count == 2
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.slow
def test_import_merge_updates_existing(client):
    """Test import merge mode updates existing template by name."""
    # Create initial template
    create_template(
        "Heavy Lance", ["Atlas", "Warhammer", "Timber Wolf", "Mad Cat"], "Original description"
    )
    create_template("Light Lance", ["Adder", "Kit Fox"], "Light mechs")

    # Export and modify
    json_str, _ = export_templates_to_json()
    data = json.loads(json_str)

    # Modify Heavy Lance to have 3 patterns instead of 4
    for template in data["templates"]:
        if template["name"] == "Heavy Lance":
            template["chassis_patterns"] = ["Direwolf", "Summoner", "Stormcrow"]
            template["description"] = "Updated description"

    # Import with merge
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        temp_path = f.name

    try:
        result = import_templates_from_json(temp_path)

        templates = get_all_templates()
        assert len(templates) == 2  # No new templates created

        # Find Heavy Lance and verify update
        heavy_lance = next(t for t in templates if t.name == "Heavy Lance")
        assert heavy_lance.description == "Updated description"

        # Verify pattern count
        from app.extensions import session_scope
        from app.models.lance_template_miniature import LanceTemplateMiniature

        with session_scope() as session:
            pattern_count = (
                session.query(LanceTemplateMiniature)
                .filter(LanceTemplateMiniature.template_id == heavy_lance.id)
                .count()
            )
            assert pattern_count == 3

            # Verify patterns are the new ones
            patterns = (
                session.query(LanceTemplateMiniature)
                .filter(LanceTemplateMiniature.template_id == heavy_lance.id)
                .order_by(LanceTemplateMiniature.order)
                .all()
            )

            assert patterns[0].chassis_pattern == "Direwolf"
            assert patterns[1].chassis_pattern == "Summoner"
            assert patterns[2].chassis_pattern == "Stormcrow"
    finally:
        Path(temp_path).unlink(missing_ok=True)
