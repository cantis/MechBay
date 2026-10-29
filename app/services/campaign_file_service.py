"""Save a whole campaign to a ``.mbcampaign`` file and load it back.

The file holds the campaign and everything that belongs to it: lances, the campaign force
(units), pilots, contracts and travel (Chaos), Sorties and their units, reports, pilot
advancement, Story Keywords, reconnaissance, repair/rearm/damage/injury history and the
Warchest ledger. Loading always creates a *new* campaign with new ids, remapping every link
between rows (including the ids stored inside ledger entries and pending ledger lines).

Physical miniatures are not part of the file: they belong to the inventory. A loaded unit is
re-linked to the inventory miniature with the same series and number when there is one;
otherwise it is kept (with its history) and flagged as a missing miniature.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import structlog
from sqlalchemy import select

from ..extensions import Base, session_scope
from ..models.campaign import Campaign
from ..models.miniature import Miniature

logger = structlog.get_logger()

CAMPAIGN_FILE_TYPE = "campaign"
CAMPAIGN_FILE_SCHEMA_VERSION = 1
CAMPAIGN_FILE_EXTENSION = ".mbcampaign"

# Parents before children, so every link can be remapped as rows are inserted.
TABLE_ORDER = (
    "campaigns",
    "campaign_lances",
    "campaign_units",
    "campaign_pilots",
    "contracts",
    "contract_units",
    "travel_events",
    "sorties",
    "sortie_units",
    "damage_events",
    "repair_orders",
    "rearm_orders",
    "pilot_injury_events",
    "unit_configuration_events",
    "pilot_advancement_events",
    "story_keyword_events",
    "aces_sortie_reports",
    "sortie_pilot_shares",
    "sortie_recon_actions",
    "warchest_transactions",
)

# Plain integer columns (no database FK) that still hold another row's id.
EXTRA_ID_REFS: dict[tuple[str, str], str] = {
    ("sorties", "mvp_pilot_id"): "campaign_pilots",
    ("sorties", "force_commander_pilot_id"): "campaign_pilots",
    ("sortie_units", "campaign_lance_id"): "campaign_lances",
    ("sortie_pilot_shares", "advancement_event_id"): "pilot_advancement_events",
}

# Ledger entries point at the thing they are about by (type, id).
ENTITY_TABLES = {
    "sortie": "sorties",
    "rearm_order": "rearm_orders",
    "repair_order": "repair_orders",
    "campaign_unit": "campaign_units",
    "campaign_pilot": "campaign_pilots",
    "contract": "contracts",
    "travel_event": "travel_events",
}


def _models() -> dict[str, Any]:
    from .. import models  # noqa: F401  (register every table)

    return {m.class_.__table__.name: m.class_ for m in Base.registry.mappers}


# --- export --------------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _serialize(model: Any, row: Any) -> dict[str, Any]:
    data = {col.name: _jsonable(getattr(row, col.name)) for col in model.__table__.columns}
    data["id"] = row.id
    return data


def export_campaign(campaign_id: int) -> dict[str, Any]:
    """The whole campaign as a JSON-ready dict."""
    models = _models()
    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        exported_ids: dict[str, list[int]] = {}
        tables: dict[str, list[dict[str, Any]]] = {}
        for name in TABLE_ORDER:
            model = models[name]
            stmt = select(model)
            if name == "campaigns":
                stmt = stmt.where(model.id == campaign_id)
            elif hasattr(model, "campaign_id"):
                stmt = stmt.where(model.campaign_id == campaign_id)
            elif hasattr(model, "sortie_id"):
                stmt = stmt.where(model.sortie_id.in_(exported_ids["sorties"]))
            elif hasattr(model, "contract_id"):
                stmt = stmt.where(model.contract_id.in_(exported_ids["contracts"]))
            rows = list(session.execute(stmt.order_by(model.id)).scalars())
            tables[name] = [_serialize(model, row) for row in rows]
            exported_ids[name] = [row.id for row in rows]
        return {
            "type": CAMPAIGN_FILE_TYPE,
            "schema_version": CAMPAIGN_FILE_SCHEMA_VERSION,
            "app": "MechBay",
            "exported_at": datetime.now(UTC).isoformat(),
            "campaign_name": campaign.name,
            "ruleset": campaign.ruleset,
            "tables": tables,
        }


def export_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_", " ") else "_" for c in name).strip()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"Campaign_{safe or 'campaign'}_{stamp}{CAMPAIGN_FILE_EXTENSION}"


# --- import --------------------------------------------------------------------------------


def validate_campaign_payload(data: Any) -> dict[str, list[dict[str, Any]]]:
    """Check the shape of a campaign file; returns its tables."""
    if not isinstance(data, dict):
        raise ValueError("This is not a MechBay campaign file")
    if data.get("type") != CAMPAIGN_FILE_TYPE:
        raise ValueError("This is not a MechBay campaign file")
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise ValueError("The campaign file has no valid version")
    if version > CAMPAIGN_FILE_SCHEMA_VERSION:
        raise ValueError(
            "This campaign file was saved by a newer version of MechBay. Update MechBay to open it."
        )
    tables = data.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("The campaign file has no data")
    clean: dict[str, list[dict[str, Any]]] = {}
    for name in TABLE_ORDER:
        rows = tables.get(name, [])
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError(f"The campaign file has invalid {name} data")
        if any(not isinstance(r.get("id"), int) for r in rows):
            raise ValueError(f"The campaign file has {name} rows without an id")
        clean[name] = rows
    if len(clean["campaigns"]) != 1:
        raise ValueError("A campaign file must contain exactly one campaign")
    return clean


def _parse(column: Any, value: Any) -> Any:
    if value is None:
        return None
    try:
        python_type = column.type.python_type
    except NotImplementedError:
        return value
    try:
        if python_type is datetime:
            return datetime.fromisoformat(value)
        if python_type is date:
            return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"The campaign file has an invalid date in {column.table.name}") from exc
    return value


def _unique_name(session: Any, name: str) -> str:
    existing = {(row or "").lower() for row in session.execute(select(Campaign.name)).scalars()}
    if name.lower() not in existing:
        return name
    candidate = f"{name} (imported)"
    counter = 2
    while candidate.lower() in existing:
        candidate = f"{name} (imported {counter})"
        counter += 1
    return candidate


def _remap(id_map: dict[str, dict[int, int]], table: str, old: Any, where: str) -> int:
    new = id_map[table].get(old)
    if new is None:
        raise ValueError(f"The campaign file is damaged: {where} refers to a missing row")
    return new


def import_campaign(data: Any, *, activate: bool = True) -> dict[str, Any]:
    """Create a new campaign from a campaign file. All-or-nothing."""
    tables = validate_campaign_payload(data)
    models = _models()
    id_map: dict[str, dict[int, int]] = {name: {} for name in TABLE_ORDER}
    counts: dict[str, int] = {}
    missing_miniatures = 0

    with session_scope() as session:
        deferred_self: list[tuple[Any, int]] = []
        new_campaign_id = 0

        for name in TABLE_ORDER:
            model = models[name]
            table = model.__table__
            fks = {fk.parent.name: fk.column.table.name for fk in table.foreign_keys}
            for row in tables[name]:
                kwargs: dict[str, Any] = {}
                for column in table.columns:
                    if column.name == "id" or column.name not in row:
                        continue
                    kwargs[column.name] = _parse(column, row[column.name])

                self_ref: int | None = None
                for col_name, target in fks.items():
                    value = kwargs.get(col_name)
                    if value is None:
                        continue
                    if name == "campaigns":
                        continue
                    if target == "campaigns":
                        kwargs[col_name] = new_campaign_id
                    elif target == name:
                        self_ref, kwargs[col_name] = value, None
                    elif target == "miniatures":
                        continue  # re-linked below
                    elif target in id_map:
                        kwargs[col_name] = _remap(id_map, target, value, f"{name}.{col_name}")
                    else:
                        raise ValueError(f"The campaign file has an unexpected link in {name}")
                for (table_name, col_name), target in EXTRA_ID_REFS.items():
                    if table_name == name and kwargs.get(col_name) is not None:
                        kwargs[col_name] = _remap(id_map, target, kwargs[col_name], col_name)

                if name == "campaigns":
                    kwargs["name"] = _unique_name(session, str(kwargs.get("name") or "Campaign"))
                    kwargs["is_active"] = False
                elif name == "campaign_units":
                    had_link = kwargs.get("miniature_id") is not None
                    kwargs["miniature_id"] = None
                    if kwargs.get("series") is not None and kwargs.get("unique_id") is not None:
                        found = (
                            session.execute(
                                select(Miniature).where(
                                    Miniature.series == kwargs["series"],
                                    Miniature.unique_id == kwargs["unique_id"],
                                )
                            )
                            .scalars()
                            .first()
                        )
                        if found:
                            kwargs["miniature_id"] = found.id
                            kwargs["miniature_missing"] = False
                    if had_link and kwargs["miniature_id"] is None:
                        kwargs["miniature_missing"] = True
                        missing_miniatures += 1
                elif name == "warchest_transactions":
                    entity = kwargs.get("related_entity_type")
                    old_id = kwargs.get("related_entity_id")
                    if old_id is not None:
                        if entity == "campaign":
                            kwargs["related_entity_id"] = new_campaign_id
                        elif entity in ENTITY_TABLES:
                            kwargs["related_entity_id"] = id_map[ENTITY_TABLES[entity]].get(old_id)
                elif name == "aces_sortie_reports" and kwargs.get("pending_ledger"):
                    try:
                        lines = json.loads(kwargs["pending_ledger"])
                        for line in lines:
                            target_table = ENTITY_TABLES.get(line.get("entity_type"))
                            if target_table and line.get("entity_id") is not None:
                                line["entity_id"] = id_map[target_table].get(line["entity_id"])
                        kwargs["pending_ledger"] = json.dumps(lines)
                    except (TypeError, ValueError, AttributeError) as exc:
                        raise ValueError("The campaign file has a damaged pending ledger") from exc

                try:
                    obj = model(**kwargs)
                    session.add(obj)
                    session.flush()
                except Exception as exc:  # noqa: BLE001 - surface any data problem uniformly
                    session.rollback()
                    raise ValueError(
                        f"The campaign file has invalid {name} data: {exc.__class__.__name__}"
                    ) from exc
                id_map[name][row["id"]] = obj.id
                if name == "campaigns":
                    new_campaign_id = obj.id
                if self_ref is not None:
                    deferred_self.append((obj, self_ref))
            counts[name] = len(tables[name])

        for obj, old_target in deferred_self:  # replay links between Sorties
            obj.replay_of_sortie_id = _remap(id_map, "sorties", old_target, "replay_of_sortie_id")

        if activate:
            session.query(Campaign).update({"is_active": False})
            session.get(Campaign, new_campaign_id).is_active = True
        session.flush()
        campaign = session.get(Campaign, new_campaign_id)
        name = campaign.name

    logger.info("campaign_imported", campaign_id=new_campaign_id, name=name, counts=counts)
    return {
        "campaign_id": new_campaign_id,
        "name": name,
        "counts": counts,
        "missing_miniatures": missing_miniatures,
    }
