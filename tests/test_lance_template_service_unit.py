"""Unit tests for lance_template_service.py.

Fast tests using minimal data. Focus on:
- Basic CRUD operations
- Edge cases and error handling
- Pattern matching with small datasets

For integration tests with realistic inventory, see test_lance_template_service_integration.py.
"""

from __future__ import annotations

from app.services.lance_template_service import (
    create_template,
    delete_template,
    find_matching_miniature,
    get_all_templates,
    get_template_details,
    match_template_miniatures,
)
from tests.conftest import validate_expunged_object

# ============================================================================
# CRUD OPERATIONS - Unit Tests
# ============================================================================


def test_create_template_order_preserved(client):
    """Test creating template preserves chassis pattern order."""
    # Act
    template = create_template(
        name="Test Lance",
        chassis_patterns=["Atlas", "Warhammer", "Timber Wolf", "Mad Cat"],
        description="Test description",
    )

    # Assert
    assert template is not None
    assert template.name == "Test Lance"
    assert template.description == "Test description"

    # Validate order field
    from app.extensions import session_scope
    from app.models.lance_template_miniature import LanceTemplateMiniature

    with session_scope() as session:
        patterns = (
            session.query(LanceTemplateMiniature)
            .filter(LanceTemplateMiniature.template_id == template.id)
            .order_by(LanceTemplateMiniature.order)
            .all()
        )

        assert len(patterns) == 4
        assert patterns[0].chassis_pattern == "Atlas"
        assert patterns[0].order == 0
        assert patterns[1].chassis_pattern == "Warhammer"
        assert patterns[1].order == 1
        assert patterns[2].chassis_pattern == "Timber Wolf"
        assert patterns[2].order == 2
        assert patterns[3].chassis_pattern == "Mad Cat"
        assert patterns[3].order == 3

    validate_expunged_object(template, "id", "name", "description")


def test_get_template_details_not_found(client):
    """Test getting non-existent template returns None."""
    # Act
    template = get_template_details(99999)

    # Assert
    assert template is None


def test_delete_template_not_found(client):
    """Test deleting non-existent template returns False."""
    # Act
    result = delete_template(99999)

    # Assert
    assert result is False


def test_get_all_templates_empty(client):
    """Test getting templates when none exist."""
    # Act
    templates = get_all_templates()

    # Assert
    assert templates == []


# ============================================================================
# PATTERN MATCHING - Unit Tests
# ============================================================================


def test_find_matching_miniature_no_match(client, sample_miniatures):
    """Test finding non-existent pattern returns None."""
    # Act
    result = find_matching_miniature("NonexistentMech", set())

    # Assert
    assert result is None


def test_match_template_empty_inventory(client):
    """Test matching template with no miniatures available."""
    # Arrange
    template = create_template(
        name="Test Lance", chassis_patterns=["Atlas", "Warhammer", "Timber Wolf", "Mad Cat"]
    )

    # Act
    result = match_template_miniatures(template.id, set())

    # Assert
    assert result["matched"] == []
    assert len(result["missing"]) == 4
    assert "Atlas" in result["missing"]
    assert "Warhammer" in result["missing"]
