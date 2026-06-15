"""Export MechBay lances to Jeff's BT Tools Alpha Strike group JSON."""

from __future__ import annotations

import io
import json
import re
import uuid as uuid_lib
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from ..extensions import session_scope
from ..models.lance import Lance
from . import alpha_strike_service, mul_service
from .force_service import get_force_by_id

logger = structlog.get_logger()

DEFAULT_PILOT_SKILL = 4


@dataclass(frozen=True)
class UnassignedMiniature:
    lance_name: str
    label: str


class JeffExportError(ValueError):
    """Raised when a lance cannot be exported to Jeff's format."""

    def __init__(self, message: str, *, unassigned: list[UnassignedMiniature] | None = None):
        super().__init__(message)
        self.unassigned = unassigned or []


def parse_bf_move(bf_move: str | None) -> tuple[list[dict[str, Any]], int]:
    """Parse MUL BFMove into Jeff move entries and jumpMove."""
    if not bf_move:
        return [], 0

    text = str(bf_move).strip()
    jump_match = re.search(r"(\d+)\s*\"j", text, re.IGNORECASE)
    jump_move = int(jump_match.group(1)) if jump_match else 0

    walk_match = re.match(r"^(\d+)\s*\"", text)
    if walk_match:
        walk = int(walk_match.group(1))
        return [{"move": walk, "currentMove": walk, "type": "Walk"}], jump_move

    return [], jump_move


def parse_abilities(bf_abilities: str | None) -> list[str]:
    if not bf_abilities:
        return []
    return [part.strip() for part in str(bf_abilities).split(",") if part.strip()]


def build_jeff_member(
    *,
    assignment_raw: dict[str, Any],
    lance_name: str,
    miniature_label: str,
) -> dict[str, Any]:
    """Build one Jeff group member from a MUL snapshot and MechBay context."""
    unit = mul_service.parse_mul_unit(assignment_raw)
    card = mul_service.card_from_raw(assignment_raw)
    move, jump_move = parse_bf_move(card.get("bf_move"))

    damage = {
        "short": int(card.get("damage_short") or 0),
        "medium": int(card.get("damage_medium") or 0),
        "long": int(card.get("damage_long") or 0),
        "extreme": int(card.get("damage_extreme") or 0),
    }
    for key, min_key in (
        ("short", "damage_short_min"),
        ("medium", "damage_medium_min"),
        ("long", "damage_long_min"),
        ("extreme", "damage_extreme_min"),
    ):
        if card.get(min_key):
            damage[f"{key}Minimal"] = True

    member: dict[str, Any] = {
        "uuid": str(uuid_lib.uuid4()),
        "class": unit.class_name,
        "variant": unit.variant,
        "name": unit.name,
        "customName": f"{lance_name} · {miniature_label}",
        "tmm": float(card.get("bf_tmm") or 0),
        "tonnage": float(unit.tonnage),
        "role": unit.role or "",
        "threshold": int(card.get("bf_threshold") or 0),
        "mulID": unit.id,
        "basePoints": unit.point_value,
        "currentSkill": DEFAULT_PILOT_SKILL,
        "overheat": int(card.get("bf_overheat") or 0),
        "structure": int(card.get("bf_structure") or 0),
        "armor": int(card.get("bf_armor") or 0),
        "type": card.get("bf_type") or unit.unit_type_name or "",
        "size": int(card.get("bf_size") or 1),
        "showDetails": False,
        "currentHeat": 0,
        "roundHeat": 0,
        "abilities": parse_abilities(card.get("bf_abilities")),
        "move": move,
        "jumpMove": jump_move,
        "damage": damage,
        "pilot": {
            "name": "",
            "piloting": DEFAULT_PILOT_SKILL,
            "gunnery": DEFAULT_PILOT_SKILL,
            "wounds": 0,
        },
    }

    if card.get("tro"):
        member["tro"] = card["tro"]
    if card.get("image_url"):
        member["imageURL"] = card["image_url"]
    if card.get("rs"):
        member["classification"] = card["rs"]

    return member


def _miniature_label(mini) -> str:
    parts = [p for p in (mini.prefix, mini.chassis) if p]
    return " ".join(parts) if parts else f"{mini.series}-{mini.unique_id}"


def _lance_display_name(lance: Lance) -> str:
    return lance.name or f"Lance {lance.order}"


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", " ") else "_" for c in name).strip()


def build_jeff_group(lance: Lance, assignments_by_fm_id: dict[int, Any]) -> dict[str, Any]:
    """Build Jeff group JSON for one lance, validating all miniatures are assigned."""
    lance_name = _lance_display_name(lance)
    unassigned: list[UnassignedMiniature] = []
    members: list[dict[str, Any]] = []

    for fm in sorted(lance.miniatures, key=lambda row: row.order):
        mini = fm.miniature
        assignment = assignments_by_fm_id.get(fm.id)
        if not assignment:
            unassigned.append(
                UnassignedMiniature(lance_name=lance_name, label=_miniature_label(mini))
            )
            continue

        raw = json.loads(assignment.mul_snapshot_json)
        members.append(
            build_jeff_member(
                assignment_raw=raw,
                lance_name=lance_name,
                miniature_label=_miniature_label(mini),
            )
        )

    if unassigned:
        raise JeffExportError(
            _format_unassigned_message(unassigned),
            unassigned=unassigned,
        )

    return {
        "name": lance_name,
        "uuid": str(uuid_lib.uuid4()),
        "lastUpdated": datetime.now(UTC).isoformat(),
        "formationBonus": "",
        "groupLabel": "",
        "members": members,
    }


def _format_unassigned_message(unassigned: list[UnassignedMiniature]) -> str:
    details = ", ".join(f"{item.label} ({item.lance_name})" for item in unassigned)
    return f"Assign Alpha Strike variants before exporting to Jeff's BT Tools: {details}"


def export_jeff_lance(lance_id: int) -> tuple[str, str]:
    """Export one lance as Jeff group JSON."""
    with session_scope() as session:
        lance = session.get(Lance, lance_id)
        if not lance:
            raise JeffExportError("Lance not found")

        force_id = lance.force_id
        _ = lance.miniatures
        for fm in lance.miniatures:
            _ = fm.miniature
        session.expunge(lance)

    if not alpha_strike_service.get_alpha_strike_force(force_id):
        raise JeffExportError("Enable Alpha Strike on this force before exporting to Jeff's BT Tools.")

    assignments = alpha_strike_service.get_assignments_for_force(force_id)
    group = build_jeff_group(lance, assignments)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"JeffGroup_{_safe_filename(group['name'])}_{timestamp}.json"
    json_string = json.dumps(group, indent=2)

    logger.info("jeff_lance_exported", lance_id=lance_id, force_id=force_id, members=len(group["members"]))
    return json_string, filename


def export_jeff_force_zip(force_id: int) -> tuple[bytes, str]:
    """Export all lances in a force as separate Jeff JSON files in a zip archive."""
    force = get_force_by_id(force_id)
    if not force:
        raise JeffExportError("Force not found")

    if not alpha_strike_service.get_alpha_strike_force(force_id):
        raise JeffExportError("Enable Alpha Strike on this force before exporting to Jeff's BT Tools.")

    assignments = alpha_strike_service.get_assignments_for_force(force_id)
    all_unassigned: list[UnassignedMiniature] = []
    lance_groups: list[tuple[str, dict[str, Any]]] = []

    for lance in force.lances:
        try:
            group = build_jeff_group(lance, assignments)
        except JeffExportError as exc:
            all_unassigned.extend(exc.unassigned)
            continue
        lance_groups.append((_safe_filename(_lance_display_name(lance)), group))

    if all_unassigned:
        raise JeffExportError(
            _format_unassigned_message(all_unassigned),
            unassigned=all_unassigned,
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for lance_name, group in lance_groups:
            archive.writestr(f"{lance_name}.json", json.dumps(group, indent=2))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"JeffExport_{_safe_filename(force.name)}_{timestamp}.zip"

    logger.info(
        "jeff_force_exported",
        force_id=force_id,
        lance_count=len(lance_groups),
    )
    return buffer.getvalue(), zip_filename
