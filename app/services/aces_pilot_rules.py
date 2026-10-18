"""Aces Named Pilot rules: cumulative SP thresholds, Edge Ability catalogue, allocation checks.

Pure functions only - no database access. Skill, Edge Tokens and Edge Ability count are
never stored independently during normal play; they are derived from the cumulative SP
invested in each category.
"""

from __future__ import annotations

from fractions import Fraction

PILOT_TYPES = {
    "BM": "BattleMech",
    "CV": "Combat Vehicle",
    "BA": "Battle Armor",
}

MIN_NAMED_PILOTS = 2
MAX_NAMED_PILOTS = 6
RECOMMENDED_NAMED_PILOTS = 4

STARTING_PILOT_SP = 150
MVP_BONUS_SP = 20
WOUND_TREATMENT_COST = 100
NEW_PILOT_COST = 150

# (cumulative SP threshold, resulting value)
SKILL_THRESHOLDS = ((0, 4), (400, 3), (900, 2), (1900, 1), (3400, 0))
EDGE_TOKEN_THRESHOLDS = (
    (0, 1),
    (60, 2),
    (120, 3),
    (200, 4),
    (300, 5),
    (420, 6),
    (560, 7),
    (720, 8),
    (900, 9),
    (1100, 10),
)
EDGE_ABILITY_THRESHOLDS = ((0, 0), (60, 1), (180, 2), (360, 3), (600, 4), (900, 5))

# Centralised catalogue. A plain constant (not a DB enum) so new Aces versions can add
# abilities without a schema migration.
EDGE_ABILITIES = (
    "Marksman",
    "Bulwark",
    "Patient",
    "Cautious",
    "Protector",
    "Coolant Flush",
    "Jumping Jack",
    "Melee Specialist",
    "Nimble",
    "Speed Demon",
    "Assassin",
    "Forward Observer",
)


def _lookup(table: tuple[tuple[int, int], ...], sp: int) -> int:
    value = table[0][1]
    for threshold, result in table:
        if sp >= threshold:
            value = result
    return value


def skill_for_sp(skill_sp: int) -> int:
    return _lookup(SKILL_THRESHOLDS, skill_sp)


def edge_tokens_for_sp(edge_sp: int) -> int:
    return _lookup(EDGE_TOKEN_THRESHOLDS, edge_sp)


def ability_count_for_sp(ability_sp: int) -> int:
    return _lookup(EDGE_ABILITY_THRESHOLDS, ability_sp)


def derive_state(skill_sp: int, edge_sp: int, ability_sp: int) -> dict[str, int]:
    return {
        "skill": skill_for_sp(skill_sp),
        "edge_tokens": edge_tokens_for_sp(edge_sp),
        "ability_count": ability_count_for_sp(ability_sp),
    }


def validate_allocation(total_sp: int, skill_sp: int, edge_sp: int, ability_sp: int) -> None:
    """Every SP received must be allocated, none negative, none left over."""
    if min(skill_sp, edge_sp, ability_sp) < 0:
        raise ValueError("SP allocations cannot be negative")
    allocated = skill_sp + edge_sp + ability_sp
    if allocated != total_sp:
        raise ValueError(
            f"All {total_sp} SP must be allocated (Skill + Edge + Abilities = {allocated})"
        )


def validate_ability_selection(
    existing: list[str], selected: list[str], required_count: int
) -> None:
    """Exactly the newly earned number of unique, unowned, catalogue abilities."""
    if len(selected) != required_count:
        plural = "y" if required_count == 1 else "ies"
        raise ValueError(f"Select exactly {required_count} new Edge Abilit{plural}")
    if len(set(selected)) != len(selected):
        raise ValueError("Edge Abilities cannot be selected twice")
    for name in selected:
        if name not in EDGE_ABILITIES:
            raise ValueError(f"Unknown Edge Ability: {name}")
        if name in existing:
            raise ValueError(f"Pilot already has Edge Ability: {name}")


def thresholds_payload() -> dict:
    """Threshold tables for the client-side allocation preview."""
    return {
        "skill": SKILL_THRESHOLDS,
        "edge": EDGE_TOKEN_THRESHOLDS,
        "ability": EDGE_ABILITY_THRESHOLDS,
        "abilities": EDGE_ABILITIES,
    }


def pilot_type_for_unit_type(unit_type_name: str | None) -> str | None:
    """Map a MUL unit type name to the Named Pilot Type allowed to crew it.

    Conventional Infantry, emplacements and anything unrecognised map to None: they
    cannot have Named Pilots.
    """
    name = (unit_type_name or "").lower()
    if "proto" in name:
        return None
    if "mech" in name:
        return "BM"
    if "vehicle" in name:
        return "CV"
    if "battle armor" in name or "battlearmor" in name:
        return "BA"
    return None


def unit_accepts_pilot(unit_type_name: str | None, pilot_type: str | None) -> bool:
    expected = pilot_type_for_unit_type(unit_type_name)
    return expected is not None and expected == pilot_type


# --- Sortie pilot-improvement SP -----------------------------------------------------------

PARTICIPANT = "participant"
NON_PARTICIPANT = "non_participant"
KILLED = "killed"
DEAD = "dead"


def pilot_sp_cap(state: str, max_sp: int) -> int:
    """Most SP a pilot may receive: full for participants, floor(half) for living sit-outs."""
    if state == PARTICIPANT:
        return max_sp
    if state == NON_PARTICIPANT:
        return max_sp // 2
    return 0


def distribute_pilot_sp(earnings: int, max_sp: int, states: dict[int, str]) -> dict[int, int]:
    """Split a Sortie's positive Earnings among pilots (pilot id -> SP awarded).

    - Never draws from the Warchest: the pool is at most ``earnings``.
    - If Earnings cover everyone's cap, each pilot gets exactly their cap.
    - Otherwise the pool is split by weight (participant 2, living non-participant 1,
      killed/dead 0), i.e. 2:1, not by headcount.
    - Whole SP: each share is floored, then the leftover SP goes one at a time to the
      largest fractional remainders (ties: lower pilot id), skipping pilots at their cap.
      Anything that cannot be placed stays out of the pool (it falls to the Warchest).
    - No pilot ever exceeds their cap and the total never exceeds ``earnings``.
    """
    awards = dict.fromkeys(states, 0)
    if earnings <= 0 or max_sp <= 0:
        return awards
    caps = {pid: pilot_sp_cap(state, max_sp) for pid, state in states.items()}
    if earnings >= sum(caps.values()):
        return caps

    weights = {
        pid: 2 if state == PARTICIPANT else 1 if state == NON_PARTICIPANT else 0
        for pid, state in states.items()
    }
    total_weight = sum(weights.values())
    if total_weight == 0:
        return awards

    exact = {pid: Fraction(earnings * weights[pid], total_weight) for pid in states}
    for pid, value in exact.items():
        awards[pid] = min(int(value), caps[pid])
    leftover = earnings - sum(awards.values())
    by_remainder = sorted(states, key=lambda pid: (-(exact[pid] - int(exact[pid])), pid))
    while leftover > 0:
        placed = False
        for pid in by_remainder:
            if leftover == 0:
                break
            if weights[pid] and awards[pid] < caps[pid]:
                awards[pid] += 1
                leftover -= 1
                placed = True
        if not placed:
            break
    return awards
