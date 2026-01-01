"""Integration tests for force_service.py.

Comprehensive tests using realistic force structures (4 lances × 4 mechs).
Focus on:
- Complex multi-lance operations
- Cascade deletion behavior
- Import/Export with full datasets

Uses realistic_force and multiple_forces fixtures.
For fast unit tests, see test_force_service_unit.py.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.services.force_service import (
    add_miniature_to_lance,
    create_empty_lance,
    delete_force,
    delete_lance,
    export_force_to_json,
    get_active_force,
    get_all_forces,
    get_force_by_id,
    get_miniatures_in_force,
    import_force_from_json,
    move_miniature_between_lances,
    remove_miniature_from_force,
    rename_force,
    switch_force,
)
from tests.conftest import (
    assert_force_structure,
    assert_single_active_force,
)

# ============================================================================
# CRUD OPERATIONS - Integration Tests
# ============================================================================


@pytest.mark.slow
def test_get_all_forces_ordering(client, multiple_forces):
    """Test forces are ordered by is_active desc, created_at desc."""
    # Switch active to middle force
    switch_force(multiple_forces["Wolf Hunters"])

    forces = get_all_forces()

    assert len(forces) == 3
    # First should be active Wolf Hunters
    assert forces[0].name == "Wolf Hunters"
    assert forces[0].is_active is True

    # Others should be inactive, ordered by creation (newest first)
    assert forces[1].is_active is False
    assert forces[2].is_active is False


@pytest.mark.slow
def test_delete_force_cascades_to_lances_and_assignments(client, realistic_force):
    """Test deleting force cascades to lances and ForceMiniatures."""
    from app.extensions import session_scope
    from app.models.force_miniature import ForceMiniature
    from app.models.lance import Lance
    from app.models.miniature import Miniature

    # Verify starting state
    force = get_force_by_id(realistic_force)
    assert_force_structure(force, expected_lance_count=4, expected_miniature_count=16)

    # Delete force
    result = delete_force(realistic_force)
    assert result is True

    # Verify cascade deletion
    with session_scope() as session:
        lance_count = session.query(Lance).filter(Lance.force_id == realistic_force).count()
        assert lance_count == 0, "Lances should be deleted"

        fm_count = session.query(ForceMiniature).count()
        assert fm_count == 0, "ForceMiniatures should be deleted"

        # Miniatures themselves should still exist
        mini_count = session.query(Miniature).count()
        assert mini_count >= 16, "Miniatures should not be cascade deleted"


@pytest.mark.slow
def test_switch_active_force_single_active_invariant(client, multiple_forces):
    """Test switching active force maintains single-active invariant."""
    force_ids = list(multiple_forces.values())

    # Switch between forces multiple times
    for force_id in [force_ids[1], force_ids[2], force_ids[0], force_ids[1]]:
        switch_force(force_id)

        forces = get_all_forces()
        assert_single_active_force(forces)


# ============================================================================
# LANCE MANAGEMENT - Integration Tests
# ============================================================================


@pytest.mark.slow
def test_create_lance_auto_calculates_order(client, realistic_force):
    """Test creating new lance calculates correct order."""
    force = get_force_by_id(realistic_force)
    assert len(force.lances) == 4

    # Create 5th lance
    new_lance = create_empty_lance(realistic_force, "Echo Lance")

    assert new_lance.order == 5


@pytest.mark.slow
def test_delete_lance_cascades_to_force_miniatures(client, realistic_force):
    """Test deleting lance removes ForceMiniatures but not Miniatures."""
    from app.extensions import session_scope
    from app.models.force_miniature import ForceMiniature
    from app.models.miniature import Miniature

    force = get_force_by_id(realistic_force)
    lance_to_delete = force.lances[1]  # Second lance
    lance_id = lance_to_delete.id

    # Count ForceMiniatures for this lance
    with session_scope() as session:
        fm_count_before = (
            session.query(ForceMiniature).filter(ForceMiniature.lance_id == lance_id).count()
        )
        assert fm_count_before == 4

    # Delete lance
    result = delete_lance(lance_id)
    assert result is True

    # Verify ForceMiniatures deleted but Miniatures remain
    with session_scope() as session:
        fm_count_after = (
            session.query(ForceMiniature).filter(ForceMiniature.lance_id == lance_id).count()
        )
        assert fm_count_after == 0

        mini_count = session.query(Miniature).count()
        assert mini_count >= 16


# ============================================================================
# MINIATURE ASSIGNMENT - Integration Tests
# ============================================================================


@pytest.mark.slow
def test_add_miniature_duplicate_prevention(client, realistic_force, sample_miniatures):
    """Test adding same miniature to different lance fails."""
    force = get_force_by_id(realistic_force)
    lance1 = force.lances[0]
    lance2 = force.lances[1]

    # Get miniature already in lance1
    from app.extensions import session_scope
    from app.models.force_miniature import ForceMiniature

    with session_scope() as session:
        fm = session.query(ForceMiniature).filter(ForceMiniature.lance_id == lance1.id).first()
        miniature_id = fm.miniature_id

    # Try adding same miniature to lance2
    result = add_miniature_to_lance(miniature_id, lance2.id)

    assert result["success"] is False
    assert "already" in result["error"].lower()


@pytest.mark.slow
def test_remove_miniature_from_force(client, realistic_force):
    """Test removing miniature from realistic force."""
    force = get_force_by_id(realistic_force)

    # Get a miniature from middle lance
    from app.extensions import session_scope
    from app.models.force_miniature import ForceMiniature

    with session_scope() as session:
        fm = (
            session.query(ForceMiniature)
            .filter(ForceMiniature.lance_id == force.lances[1].id)
            .first()
        )
        miniature_id = fm.miniature_id

        # Count before
        count_before = (
            session.query(ForceMiniature)
            .filter(ForceMiniature.lance_id == force.lances[1].id)
            .count()
        )

    # Remove miniature
    result = remove_miniature_from_force(miniature_id, realistic_force)
    assert result is True

    # Verify count decreased
    with session_scope() as session:
        count_after = (
            session.query(ForceMiniature)
            .filter(ForceMiniature.lance_id == force.lances[1].id)
            .count()
        )
        assert count_after == count_before - 1


@pytest.mark.slow
def test_move_miniature_between_lances(client, realistic_force):
    """Test moving miniature from one lance to another."""
    force = get_force_by_id(realistic_force)
    lance1 = force.lances[0]
    lance3 = force.lances[2]

    # Get miniature from lance1 position 2
    from app.extensions import session_scope
    from app.models.force_miniature import ForceMiniature

    with session_scope() as session:
        fm = (
            session.query(ForceMiniature)
            .filter(ForceMiniature.lance_id == lance1.id, ForceMiniature.order == 2)
            .first()
        )
        miniature_id = fm.miniature_id

    # Move to lance3 position 3
    result = move_miniature_between_lances(miniature_id, lance3.id, 3)

    assert result["success"] is True

    # Verify moved
    with session_scope() as session:
        fm = (
            session.query(ForceMiniature)
            .filter(ForceMiniature.miniature_id == miniature_id)
            .first()
        )
        assert fm.lance_id == lance3.id
        assert fm.order == 3


@pytest.mark.slow
def test_get_miniatures_in_force_correct_set(client, realistic_force, sample_miniatures):
    """Test getting set of miniature IDs in force."""
    miniature_ids = get_miniatures_in_force(realistic_force)

    assert isinstance(miniature_ids, set)
    assert len(miniature_ids) == 16

    # All IDs should be from first 16 sample miniatures
    expected_ids = set(sample_miniatures[:16])
    assert miniature_ids == expected_ids


# ============================================================================
# ACTIVE FORCE INVARIANT TESTS
# ============================================================================


@pytest.mark.slow
def test_switch_active_maintains_invariant_with_realistic_forces(client, multiple_forces):
    """Test switching between multiple realistic forces maintains invariant."""
    force_ids = list(multiple_forces.values())

    # Perform 10 switch operations
    for i in range(10):
        target_force = force_ids[i % 3]
        switch_force(target_force)

        forces = get_all_forces()
        assert_single_active_force(forces)

        # Verify correct force is active
        active = get_active_force()
        assert active.id == target_force


@pytest.mark.slow
def test_active_force_unchanged_by_other_operations(client, realistic_force, sample_miniatures):
    """Test active force remains active through other operations."""
    initial_active = get_active_force()
    assert initial_active.id == realistic_force

    # Perform various operations
    create_empty_lance(realistic_force, "New Lance")
    rename_force(realistic_force, "Renamed Force")

    force = get_force_by_id(realistic_force)
    lance = force.lances[0]
    add_miniature_to_lance(sample_miniatures[16], lance.id)

    # Verify still active
    active = get_active_force()
    assert active.id == realistic_force


# ============================================================================
# IMPORT/EXPORT TESTS - Integration Tests
# ============================================================================


@pytest.mark.slow
def test_export_force_json_structure_and_filename(client, realistic_force):
    """Test export generates correct JSON structure and filename."""
    import re

    json_str, filename = export_force_to_json(realistic_force)

    # Validate filename format
    assert re.match(r"Force_.+_\d{8}_\d{6}\.json", filename)

    # Parse and validate JSON structure
    data = json.loads(json_str)

    assert "force_name" in data
    assert data["force_name"] == "Clan Wolf Hunters"

    assert "export_timestamp" in data
    assert "lances" in data
    assert len(data["lances"]) == 4

    # Validate lance structure
    for lance in data["lances"]:
        assert "name" in lance
        assert "miniatures" in lance
        assert len(lance["miniatures"]) == 4

        # Validate miniature structure
        for mini in lance["miniatures"]:
            assert "series" in mini
            assert "unique_id" in mini
            assert "prefix" in mini
            assert "chassis" in mini
            assert "type" in mini
            assert "faction" in mini


@pytest.mark.slow
def test_import_force_creates_inactive(client, realistic_force, sample_miniatures):
    """Test importing force creates it as inactive."""
    # Export
    json_str, filename = export_force_to_json(realistic_force)

    # Delete force
    delete_force(realistic_force)

    # Import from temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        temp_path = f.name

    try:
        result = import_force_from_json(temp_path)

        assert "force_id" in result
        assert result["imported_miniatures"] == 16
        assert result["missing_miniatures"] == []

        # Verify force is inactive
        imported_force = get_force_by_id(result["force_id"])
        assert imported_force.is_active is False
        assert_force_structure(imported_force, expected_lance_count=4, expected_miniature_count=16)
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.slow
def test_import_force_partial_miniatures_available(client, realistic_force, sample_miniatures):
    """Test importing when only some miniatures exist."""
    # Export
    json_str, filename = export_force_to_json(realistic_force)

    # Delete force
    delete_force(realistic_force)

    # Delete half the miniatures
    from app.services.miniature_service import delete_miniature

    for mini_id in sample_miniatures[8:16]:
        delete_miniature(mini_id)

    # Import
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        temp_path = f.name

    try:
        result = import_force_from_json(temp_path)

        assert result["imported_miniatures"] == 8
        assert len(result["missing_miniatures"]) == 8

        # Verify missing miniatures list contains tuples
        for missing in result["missing_miniatures"]:
            assert isinstance(missing, tuple)
            assert len(missing) == 2  # (series, unique_id)
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.slow
def test_import_force_no_miniatures_available(client, realistic_force):
    """Test importing when no miniatures exist creates empty structure."""
    # Export
    json_str, filename = export_force_to_json(realistic_force)

    # Delete force
    delete_force(realistic_force)

    # Delete all miniatures
    from app.extensions import session_scope
    from app.models.miniature import Miniature

    with session_scope() as session:
        session.query(Miniature).delete()

    # Import
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        temp_path = f.name

    try:
        result = import_force_from_json(temp_path)

        assert result["imported_miniatures"] == 0
        assert len(result["missing_miniatures"]) == 16

        # Verify force and lances created but empty
        imported_force = get_force_by_id(result["force_id"])
        assert len(imported_force.lances) == 4

        for lance in imported_force.lances:
            assert len(lance.miniatures) == 0
    finally:
        Path(temp_path).unlink(missing_ok=True)
