from __future__ import annotations

from sqlalchemy import and_

from .extensions import session_scope
from .models.lance_template import LanceTemplate
from .models.lance_template_miniature import LanceTemplateMiniature
from .models.miniature import Miniature


def run() -> int:
    """Seed the database with example miniatures and lance templates.

    Returns the number of records created.
    """
    # Seed miniatures
    examples = [
        {
            "series": "A",
            "unique_id": 1,
            "prefix": "WHM",
            "chassis": "Warhammer",
            "type": "Mech",
            "status": "Primed",
            "tray_id": "A1",
        },
        {
            "series": "A",
            "unique_id": 2,
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
            if (
                not session.query(Miniature)
                .filter(
                    and_(Miniature.series == e["series"], Miniature.unique_id == e["unique_id"])
                )
                .first()
            ):
                session.add(Miniature(**e))
                created += 1

        # Seed lance templates
        templates = [
            {
                "name": "Command Lance",
                "description": "Heavy command unit with mixed roles",
                "patterns": ["Warhammer", "Atlas", "Marauder", "Archer"],
            },
            {
                "name": "Assault Lance",
                "description": "Heavy assault force",
                "patterns": ["Atlas", "Stalker", "Awesome", "BattleMaster"],
            },
            {
                "name": "Heavy Lance",
                "description": "Balanced heavy lance",
                "patterns": ["Warhammer", "Marauder", "Archer", "Rifleman"],
            },
            {
                "name": "Fire Support Lance",
                "description": "Long-range fire support",
                "patterns": ["Archer", "Catapult", "Trebuchet", "Longbow"],
            },
            {
                "name": "Recon Lance",
                "description": "Fast reconnaissance and skirmish",
                "patterns": ["Locust", "Spider", "Jenner", "Commando"],
            },
            {
                "name": "Battle Lance",
                "description": "Standard medium battle force",
                "patterns": ["Griffin", "Wolverine", "Shadow Hawk", "Phoenix Hawk"],
            },
        ]

        for tpl in templates:
            existing = (
                session.query(LanceTemplate).filter(LanceTemplate.name == tpl["name"]).first()
            )

            if not existing:
                template = LanceTemplate(name=tpl["name"], description=tpl["description"])
                session.add(template)
                session.flush()

                for idx, pattern in enumerate(tpl["patterns"]):
                    mini = LanceTemplateMiniature(
                        template_id=template.id, chassis_pattern=pattern, order=idx
                    )
                    session.add(mini)
                created += 1

    return created


if __name__ == "__main__":
    from flask import Flask

    from .config import Config
    from .extensions import init_db

    # Initialize app and DB
    app = Flask(__name__)
    app.config.from_object(Config())
    init_db(app)

    count = run()
    print(f"Seeded {count} records.")
