from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest
import structlog

# Ensure project root is on sys.path for 'import app'
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # pragma: no cover - defensive
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


@pytest.fixture(scope="function")
def app():
    """Provide a fresh Flask app backed by an in-memory SQLite database per test.

    Using an in-memory database ensures tests never touch or clear production data.
    The schema is created at app init and discarded automatically when the engine
    is disposed at test end.

    Note: Uses file::memory:?cache=shared to allow multiple connections to share
    the same in-memory database within a single test.
    """
    structlog.reset_defaults()
    test_app = create_app(
        {
            "TESTING": True,
            # Use shared cache mode for in-memory database to allow multiple connections
            "DATABASE_URL": "sqlite+pysqlite:///file::memory:?cache=shared&uri=true",
        }
    )
    return test_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def mini_data():
    return {
        "series": "A",
        "unique_id": 1001,
        "prefix": "WHM",
        "chassis": "Warhammer",
        "type": "Mech",
        "status": "New",
        "tray_id": "T1",
        "notes": "First test mini",
    }


@pytest.fixture(autouse=True)
def clear_seed_data(app):
    """Clear any seed data and test data before each test to ensure clean state."""
    from app.extensions import db_session
    from app.models.force import Force
    from app.models.force_miniature import ForceMiniature
    from app.models.lance import Lance
    from app.models.lance_template import LanceTemplate
    from app.models.lance_template_miniature import LanceTemplateMiniature
    from app.models.miniature import Miniature

    # Use a fresh session for cleanup
    session = db_session()
    try:
        # Delete in reverse dependency order to avoid foreign key issues
        # ForceMiniature references both Lance and Miniature
        session.query(ForceMiniature).delete()
        # Lance references Force
        session.query(Lance).delete()
        # Force is standalone
        session.query(Force).delete()
        # LanceTemplateMiniature references LanceTemplate
        session.query(LanceTemplateMiniature).delete()
        # LanceTemplate is standalone
        session.query(LanceTemplate).delete()
        # Miniature is standalone
        session.query(Miniature).delete()

        session.commit()
        # Expire all cached objects to force fresh reads
        session.expire_all()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture()
def sample_miniatures(client):
    """Create 20 realistic mixed mechs with varied factions for testing.

    Function scope ensures isolation. Parallel execution safe via process isolation.
    Cleanup automatic via in-memory DB teardown.

    Returns: List of miniature IDs created
    """
    from app.services.miniature_service import add_miniature

    # Generate unique series for this test run to avoid UNIQUE constraint violations
    test_series = f"TEST_{random.randint(1000, 9999)}"

    miniatures_data = [
        # Jade Falcon - Heavy/Assault
        {
            "series": test_series,
            "unique_id": 1,
            "prefix": "WHM",
            "chassis": "Warhammer WHM-6R",
            "type": "Mech",
            "faction": "Jade Falcon",
        },
        {
            "series": test_series,
            "unique_id": 2,
            "prefix": "WHM",
            "chassis": "Warhammer WHM-7M",
            "type": "Mech",
            "faction": "Jade Falcon",
        },
        # Clan Wolf - Assault
        {
            "series": test_series,
            "unique_id": 3,
            "prefix": "AS7",
            "chassis": "Atlas AS7-D",
            "type": "Mech",
            "faction": "Clan Wolf",
        },
        {
            "series": test_series,
            "unique_id": 4,
            "prefix": "AS7",
            "chassis": "Atlas AS7-K",
            "type": "Mech",
            "faction": "Clan Wolf",
        },
        # Davion - Heavy
        {
            "series": test_series,
            "unique_id": 5,
            "prefix": "TBR",
            "chassis": "Timber Wolf Prime",
            "type": "Mech",
            "faction": "Davion",
        },
        {
            "series": test_series,
            "unique_id": 6,
            "prefix": "TBR",
            "chassis": "Timber Wolf C",
            "type": "Mech",
            "faction": "Davion",
        },
        # Steiner - Heavy
        {
            "series": test_series,
            "unique_id": 7,
            "prefix": "MAD",
            "chassis": "Mad Cat Mk II",
            "type": "Mech",
            "faction": "Steiner",
        },
        {
            "series": "B",
            "unique_id": 8,
            "prefix": "MAD",
            "chassis": "Mad Cat Prime",
            "type": "Mech",
            "faction": "Steiner",
        },
        # Kurita - Assault
        {
            "series": "B",
            "unique_id": 9,
            "prefix": "DWF",
            "chassis": "Direwolf Prime",
            "type": "Mech",
            "faction": "Kurita",
        },
        {
            "series": "B",
            "unique_id": 10,
            "prefix": "DWF",
            "chassis": "Direwolf A",
            "type": "Mech",
            "faction": "Kurita",
        },
        # Jade Falcon - Heavy
        {
            "series": "B",
            "unique_id": 11,
            "prefix": "SUM",
            "chassis": "Summoner Prime",
            "type": "Mech",
            "faction": "Jade Falcon",
        },
        {
            "series": "B",
            "unique_id": 12,
            "prefix": "SUM",
            "chassis": "Summoner B",
            "type": "Mech",
            "faction": "Jade Falcon",
        },
        # Marik - Medium
        {
            "series": "B",
            "unique_id": 13,
            "prefix": "SCR",
            "chassis": "Stormcrow Prime",
            "type": "Mech",
            "faction": "Marik",
        },
        {
            "series": "B",
            "unique_id": 14,
            "prefix": "SCR",
            "chassis": "Stormcrow C",
            "type": "Mech",
            "faction": "Marik",
        },
        # No faction - Light
        {
            "series": test_series,
            "unique_id": 15,
            "prefix": "ADR",
            "chassis": "Adder Prime",
            "type": "Mech",
            "faction": None,
        },
        {
            "series": test_series,
            "unique_id": 16,
            "prefix": "ADR",
            "chassis": "Adder B",
            "type": "Mech",
            "faction": None,
        },
        # Rasalhague - Light
        {
            "series": test_series,
            "unique_id": 17,
            "prefix": "KFX",
            "chassis": "Kit Fox Prime",
            "type": "Mech",
            "faction": "Rasalhague",
        },
        {
            "series": test_series,
            "unique_id": 18,
            "prefix": "KFX",
            "chassis": "Kit Fox C",
            "type": "Mech",
            "faction": "Rasalhague",
        },
        # Liao - Light
        {
            "series": test_series,
            "unique_id": 19,
            "prefix": "MLX",
            "chassis": "Mist Lynx Prime",
            "type": "Mech",
            "faction": "Liao",
        },
        {
            "series": "C",
            "unique_id": 20,
            "prefix": "MLX",
            "chassis": "Mist Lynx B",
            "type": "Mech",
            "faction": "Liao",
        },
    ]

    mini_ids = []
    for data in miniatures_data:
        mini = add_miniature(data)
        mini_ids.append(mini.id)

    yield mini_ids
    # Cleanup handled by function-scoped app context teardown


@pytest.fixture()
def minimal_force(client, sample_miniatures):
    """Create a minimal force (1 lance, 2 mechs) for fast unit tests.

    Returns: Force ID
    """
    from app.services.force_service import add_miniature_to_lance, create_empty_lance, create_force

    force = create_force("Jade Falcon Scout")
    lance = create_empty_lance(force.id, "Alpha Lance")

    # Add 2 Jade Falcon Warhammers
    add_miniature_to_lance(sample_miniatures[0], lance.id)
    add_miniature_to_lance(sample_miniatures[1], lance.id)

    yield force.id
    # Cleanup handled by function-scoped app context teardown


@pytest.fixture()
def realistic_force(client, sample_miniatures):
    """Create a realistic force (4 lances, 4 mechs each) for integration tests.

    All mechs assigned to Clan Wolf faction (realistic single-faction force).
    Uses mixed mech types: Atlas, Timber Wolf, Mad Cat, Direwolf, etc.

    Returns: Force ID
    """
    from app.services.force_service import add_miniature_to_lance, create_empty_lance, create_force
    from app.services.miniature_service import update_miniature

    # Override factions to Clan Wolf for realistic single-faction force
    for mini_id in sample_miniatures[:16]:
        update_miniature(mini_id, {"faction": "Clan Wolf"})

    force = create_force("Clan Wolf Hunters")
    lance_names = ["Alpha Lance", "Bravo Lance", "Charlie Lance", "Delta Lance"]

    for i, lance_name in enumerate(lance_names):
        lance = create_empty_lance(force.id, lance_name)
        # Assign 4 mechs per lance
        for j in range(4):
            mini_idx = i * 4 + j
            add_miniature_to_lance(sample_miniatures[mini_idx], lance.id)

    yield force.id
    # Cleanup handled by function-scoped app context teardown


@pytest.fixture()
def multiple_forces(client, sample_miniatures):
    """Create 3 forces with different factions and sizes for testing.

    Returns: Dict of {name: force_id}
    """
    from app.services.force_service import add_miniature_to_lance, create_empty_lance, create_force

    forces = {}

    # Small Jade Falcon force (1 lance, 4 mechs)
    force1 = create_force("Jade Falcon Strikers")
    lance1 = create_empty_lance(force1.id, "Alpha Lance")
    for i in range(4):
        add_miniature_to_lance(sample_miniatures[i], lance1.id)
    forces["Jade Falcon Strikers"] = force1.id

    # Medium Clan Wolf force (2 lances, 8 mechs)
    force2 = create_force("Wolf Hunters")
    for i in range(2):
        lance = create_empty_lance(force2.id, f"Lance {i + 1}")
        for j in range(4):
            add_miniature_to_lance(sample_miniatures[4 + i * 4 + j], lance.id)
    forces["Wolf Hunters"] = force2.id

    # Large Steiner force (3 lances, 12 mechs)
    force3 = create_force("Steiner Scouts")
    for i in range(3):
        lance = create_empty_lance(force3.id, f"Lance {i + 1}")
        for j in range(4):
            if (8 + i * 4 + j) < len(sample_miniatures):
                add_miniature_to_lance(sample_miniatures[8 + i * 4 + j], lance.id)
    forces["Steiner Scouts"] = force3.id

    yield forces
    # Cleanup handled by function-scoped app context teardown


@pytest.fixture()
def sample_template(client):
    """Create a standard lance template for testing.

    Returns: Template ID
    """
    from app.services.lance_template_service import create_template

    template = create_template(
        name="Standard Assault Lance",
        chassis_patterns=["Atlas", "Warhammer", "Timber Wolf", "Mad Cat"],
        description="Heavy assault configuration",
    )

    yield template.id
    # Cleanup handled by function-scoped app context teardown


def validate_expunged_object(obj, *attributes):
    """Helper to validate object is accessible outside session (expunged correctly).

    Args:
        obj: SQLAlchemy model instance to test
        *attributes: Attribute names to access (e.g., 'name', 'id', 'lances')

    Raises:
        AssertionError: If object raises DetachedInstanceError
    """
    from sqlalchemy.orm.exc import DetachedInstanceError

    for attr in attributes:
        try:
            _ = getattr(obj, attr)
        except DetachedInstanceError as e:
            raise AssertionError(
                f"Object {obj} not properly expunged - cannot access {attr}: {e}"
            ) from e


def assert_single_active_force(forces):
    """Helper to assert exactly one force is active.

    Args:
        forces: List of Force objects

    Raises:
        AssertionError: If count of active forces != 1
    """
    active_count = sum(1 for f in forces if f.is_active)
    assert active_count == 1, f"Expected 1 active force, found {active_count}"


def assert_force_structure(force, expected_lance_count, expected_miniature_count):
    """Helper to assert force has expected structure.

    Args:
        force: Force object
        expected_lance_count: Expected number of lances
        expected_miniature_count: Expected total miniatures across all lances

    Raises:
        AssertionError: If structure doesn't match expectations
    """
    assert len(force.lances) == expected_lance_count, (
        f"Expected {expected_lance_count} lances, found {len(force.lances)}"
    )

    total_miniatures = sum(len(lance.miniatures) for lance in force.lances)
    assert total_miniatures == expected_miniature_count, (
        f"Expected {expected_miniature_count} miniatures, found {total_miniatures}"
    )
