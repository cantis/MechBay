"""Unit tests for force_service.py.

Fast tests using minimal data structures. Focus on:
- Basic CRUD operations with simple fixtures
- Edge cases and error handling
- Single-force operations

Uses minimal_force fixture for speed.
For integration tests with realistic forces, see test_force_service_integration.py.
"""

from __future__ import annotations

import pytest

from app.services.force_service import (
    add_miniature_to_lance,
    create_empty_lance,
    create_force,
    delete_force,
    delete_lance,
    export_force_to_json,
    get_active_force,
    get_all_forces,
    get_force_by_id,
    import_force_from_json,
    remove_miniature_from_force,
    rename_force,
)
from tests.conftest import validate_expunged_object

# ============================================================================
# CRUD OPERATIONS - Unit Tests
# ============================================================================


def test_create_force_becomes_active(client):
    """Test creating a force makes it active."""
    # Act
    force = create_force("Test Force")

    # Assert
    assert force is not None
    assert force.name == "Test Force"
    assert force.is_active is True

    # Validate object accessible after session close
    validate_expunged_object(force, "id", "name", "is_active", "lances")


def test_get_all_forces_empty_list(client):
    """Test getting forces when none exist."""
    # Act
    forces = get_all_forces()

    # Assert
    assert forces == []


def test_get_force_by_id_not_found(client):
    """Test getting non-existent force returns None."""
    # Act
    force = get_force_by_id(99999)

    # Assert
    assert force is None


def test_get_force_by_id_found(client, minimal_force):
    """Test getting force by ID with eager loading."""
    # Arrange - minimal_force fixture provides force ID

    # Act
    force = get_force_by_id(minimal_force)

    # Assert
    assert force is not None
    assert force.id == minimal_force

    # Validate eager loading - lances should be accessible
    validate_expunged_object(force, "id", "name", "lances")
    assert len(force.lances) == 1


def test_rename_force_strips_whitespace(client):
    """Test renaming force strips leading/trailing whitespace."""
    # Arrange
    force = create_force("Test Force")

    # Act
    renamed = rename_force(force.id, "  New Name  ")

    # Assert
    assert renamed is not None
    assert renamed.name == "New Name"


def test_delete_force_returns_false_when_not_found(client):
    """Test deleting non-existent force returns False."""
    # Act
    result = delete_force(99999)

    # Assert
    assert result is False


def test_get_active_force_returns_none_when_no_forces(client):
    """Test getting active force when none exist."""
    # Act
    active = get_active_force()

    # Assert
    assert active is None


# ============================================================================
# LANCE MANAGEMENT - Unit Tests
# ============================================================================


def test_create_lance_first_in_force(client):
    """Test creating first lance gets order=1."""
    # Arrange
    force = create_force("Test Force")

    # Act
    lance = create_empty_lance(force.id, "Alpha Lance")

    # Assert
    assert lance is not None
    assert lance.name == "Alpha Lance"
    assert lance.order == 1
    assert lance.header_color
    assert lance.header_color.startswith("#")
    validate_expunged_object(lance, "id", "name", "order", "header_color")


def test_create_lance_with_custom_name(client):
    """Test creating lance with custom name persists correctly."""
    # Arrange
    force = create_force("Test Force")

    # Act
    lance = create_empty_lance(force.id, "Custom Lance Name")

    # Assert
    assert lance.name == "Custom Lance Name"


def test_delete_lance_not_found_returns_false(client):
    """Test deleting non-existent lance returns False."""
    # Act
    result = delete_lance(99999)

    # Assert
    assert result is False


# ============================================================================
# MINIATURE ASSIGNMENT - Unit Tests
# ============================================================================


def test_add_miniature_to_lance_auto_position(client, minimal_force, sample_miniatures):
    """Test adding miniature auto-calculates position."""
    # Arrange
    force = get_force_by_id(minimal_force)
    lance = force.lances[0]

    # Act - Add 3rd miniature (first 2 added by fixture)
    result = add_miniature_to_lance(sample_miniatures[2], lance.id)

    # Assert
    assert result["success"] is True
    assert result["force_miniature_id"] is not None

    # Verify position is 3
    from app.extensions import session_scope
    from app.models.force_miniature import ForceMiniature

    with session_scope() as session:
        fm = session.get(ForceMiniature, result["force_miniature_id"])
        assert fm.order == 3


def test_add_miniature_with_explicit_position(client, minimal_force, sample_miniatures):
    """Test adding miniature with explicit position."""
    # Arrange
    force = get_force_by_id(minimal_force)
    lance = force.lances[0]

    # Act
    result = add_miniature_to_lance(sample_miniatures[2], lance.id, position=5)

    # Assert
    assert result["success"] is True

    from app.extensions import session_scope
    from app.models.force_miniature import ForceMiniature

    with session_scope() as session:
        fm = session.get(ForceMiniature, result["force_miniature_id"])
        assert fm.order == 5


def test_add_miniature_miniature_not_found(client, minimal_force):
    """Test adding non-existent miniature fails gracefully."""
    # Arrange
    force = get_force_by_id(minimal_force)
    lance = force.lances[0]

    # Act
    result = add_miniature_to_lance(99999, lance.id)

    # Assert
    assert result["success"] is False
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_remove_miniature_not_in_force_returns_false(client, sample_miniatures):
    """Test removing miniature not in any force returns False."""
    # Arrange
    force = create_force("Test Force")

    # Act
    result = remove_miniature_from_force(sample_miniatures[0], force.id)

    # Assert
    assert result is False


# ============================================================================
# ACTIVE FORCE INVARIANT TESTS
# ============================================================================


def test_create_second_force_deactivates_first(client):
    """Test creating second force deactivates first."""
    # Arrange
    force1 = create_force("Force 1")
    assert force1.is_active is True

    # Act
    force2 = create_force("Force 2")

    # Assert
    assert force2.is_active is True
    force1_refreshed = get_force_by_id(force1.id)
    assert force1_refreshed.is_active is False


def test_delete_active_force_no_active_remains(client):
    """Test deleting active force leaves no active force."""
    # Arrange
    force = create_force("Test Force")

    # Act
    delete_force(force.id)

    # Assert
    active = get_active_force()
    assert active is None


# ============================================================================
# IMPORT/EXPORT TESTS - Unit Tests
# ============================================================================


def test_export_force_not_found_raises(client):
    """Test exporting non-existent force raises ValueError."""
    # Act & Assert
    with pytest.raises(ValueError, match="Force not found"):
        export_force_to_json(99999)


def test_import_force_file_not_found_raises(client):
    """Test importing from non-existent file raises ValueError."""
    # Act & Assert
    with pytest.raises(ValueError):
        import_force_from_json("/nonexistent/path.json")
