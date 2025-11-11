from __future__ import annotations

from .extensions import session_scope
from .models.miniature import Miniature


def run() -> int:
    """Seed the database with a few example miniatures.

    Returns the number of records created.
    """
    examples = [
        {
            "unique_id": "WHM-001",
            "prefix": "WHM",
            "chassis": "Warhammer",
            "type": "Mech",
            "status": "Primed",
            "tray_id": "A1",
        },
        {
            "unique_id": "BNC-002",
            "prefix": "BNC",
            "chassis": "Banshee",
            "type": "Mech",
            "status": "Detail",
            "tray_id": "A2",
        },
    ]
    created = 0
    with session_scope() as session:
        for e in examples:
            if not session.query(Miniature).filter_by(unique_id=e["unique_id"]).first():
                session.add(Miniature(**e))
                created += 1
    return created


if __name__ == "__main__":
    count = run()
    print(f"Seeded {count} miniatures.")
