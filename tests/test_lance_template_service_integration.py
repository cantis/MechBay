"""Integration tests for lance_template_service.py.

Comprehensive tests using realistic miniature inventory. Focus on:
- Complex pattern matching scenarios
- Multi-template operations
- Import/Export with full datasets

Uses sample_miniatures fixture with full inventory.
For fast unit tests, see test_lance_template_service_unit.py.
"""

from __future__ import annotations

import pytest

from app.services import inventory_project_service
from app.services.lance_template_service import (
    create_template,
    find_matching_miniature,
    get_all_templates,
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
# Inventory project round-trip for templates
# ============================================================================


@pytest.mark.slow
def test_templates_round_trip_via_inventory_project(client):
    create_template("Lance 1", ["Atlas", "Warhammer", "Timber Wolf"])
    create_template("Lance 2", ["Mad Cat", "Direwolf", "Summoner", "Stormcrow"])

    payload = inventory_project_service.build_project_data()
    assert len(payload["templates"]) == 2

    inventory_project_service.load_project_from_data(payload)
    templates = get_all_templates()
    assert len(templates) == 2
    names = {t.name for t in templates}
    assert names == {"Lance 1", "Lance 2"}
