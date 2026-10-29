"""Ruleset-dependent campaign calculations (Chaos Campaign vs Aces).

Two rulesets, two small dispatch functions here - not a generic plugin framework.
Ruleset-agnostic logic (rearm cost/ENE, warchest posting, truly-destroyed handling,
pilot wound/retirement states, roster eligibility) already lives in
campaign_service/after_action_service/contract_service and is reused unchanged.
"""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Any

RULESETS = ("chaos", "aces")

# Aces repair: Alpha Strike Size x multiplier (highest applicable category only).
ACES_REPAIR_MULTIPLIERS = {
    "armour": 20,
    "structure": 40,
    "crippled": 60,
    "destroyed": 100,
}
ACES_PURCHASE_MULTIPLIER = 40

# Aces campaign difficulty: (Player Force PV modifier %, Objective SP earned %).
ACES_DIFFICULTIES = {
    "rookie": (20, 120),
    "standard": (0, 100),
    "veteran": (-10, 90),
    "elite": (-20, 80),
    "legendary": (-30, 70),
}


def require_valid_ruleset(ruleset: str) -> None:
    if ruleset not in RULESETS:
        raise ValueError(f"Unknown campaign ruleset: {ruleset}")


def require_ruleset(campaign, expected: str) -> None:
    if campaign.ruleset != expected:
        raise ValueError(f"This action is only available for {expected} campaigns")


def round_half_up(value: Fraction | int) -> int:
    """Whole-SP rounding, half rounds up (never banker's rounding)."""
    fraction = Fraction(value)
    return int((fraction * 2 + 1) // 2)


def aces_unit_size(
    mul_snapshot_json: str | None, tonnage: int | None, unit_type_name: str | None
) -> int | None:
    """Printed Alpha Strike Size from the MUL snapshot (BFSize).

    Only BattleMechs may fall back to the standard tonnage bands; anything else without a
    recorded Size returns None so the caller can ask for it instead of guessing.
    """
    if mul_snapshot_json:
        try:
            raw: Any = json.loads(mul_snapshot_json)
        except (TypeError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict) and raw.get("BFSize"):
            return int(raw["BFSize"])
    if "mech" in (unit_type_name or "").lower() and "proto" not in (unit_type_name or "").lower():
        tons = int(tonnage or 0)
        if tons <= 0:
            return None
        if tons <= 35:
            return 1
        if tons <= 55:
            return 2
        if tons <= 75:
            return 3
        return 4
    return None


def aces_repair_cost(damage: str, size: int, *, battlemech: bool) -> int:
    """Aces repair SP. Non-BattleMechs use half the printed Size, unrounded until the end."""
    if damage == "truly-destroyed":
        raise ValueError("A Truly Destroyed unit cannot be repaired")
    multiplier = ACES_REPAIR_MULTIPLIERS.get(damage)
    if multiplier is None:
        return 0
    effective = Fraction(size) if battlemech else Fraction(size, 2)
    return round_half_up(effective * multiplier)


def repair_cost(
    ruleset: str,
    damage: str,
    tonnage: int | None,
    *,
    size: int | None = None,
    battlemech: bool = True,
) -> int:
    """Gross repair SP for a damage category, dispatched by Campaign ruleset."""
    if ruleset == "aces":
        if damage not in ACES_REPAIR_MULTIPLIERS:
            return 0
        if size is None:
            raise ValueError("Aces repair costs need the unit's Alpha Strike Size")
        return aces_repair_cost(damage, size, battlemech=battlemech)
    from .after_action_service import standard_repair_cost

    return standard_repair_cost(damage, tonnage)


def purchase_cost(point_value: int) -> int:
    """Aces replacement/additional unit purchase cost: PV x 40 SP."""
    return point_value * ACES_PURCHASE_MULTIPLIER


def difficulty_key(difficulty: str | None) -> str:
    """Normalise free-text campaign difficulty; unknown/blank means Standard."""
    key = (difficulty or "").strip().lower()
    return key if key in ACES_DIFFICULTIES else "standard"


def force_pv_modifier_percent(difficulty: str | None) -> int:
    return ACES_DIFFICULTIES[difficulty_key(difficulty)][0]


def objective_sp_percent(difficulty: str | None) -> int:
    return ACES_DIFFICULTIES[difficulty_key(difficulty)][1]


def adjusted_objective_sp(base: int, difficulty: str | None) -> int:
    """Apply the Campaign Difficulty objective-SP multiplier to an objective amount."""
    return round_half_up(Fraction(base * objective_sp_percent(difficulty), 100))


# --- Aces: Player Force sizing, experienced-force modifier, Omni, starting force -----------

ACES_STARTING_FORCE_PV = 400
ACES_MIN_STARTING_UNITS = 8
ACES_UNUSED_PV_WARCHEST_MULTIPLIER = 40
ACES_SALE_MULTIPLIER = 20

# Total SP earned by all Named Pilots of an experienced force -> Player Force PV modifier %.
EXPERIENCED_FORCE_TIERS = ((3000, 0), (6000, -10), (9000, -20), (12000, -30))
EXPERIENCED_FORCE_MAX_PENALTY = -40


def experienced_force_modifier_percent(total_pilot_sp: int) -> int:
    for ceiling, modifier in EXPERIENCED_FORCE_TIERS:
        if total_pilot_sp <= ceiling:
            return modifier
    return EXPERIENCED_FORCE_MAX_PENALTY


def aces_pv_allowance_percent(difficulty: str | None, experienced_sp: int = 0) -> int:
    """Combined Player Force PV modifier. The two modifiers stack additively."""
    return force_pv_modifier_percent(difficulty) + experienced_force_modifier_percent(
        experienced_sp
    )


def aces_allowed_sortie_pv(force_pv: int, difficulty: str | None, experienced_sp: int = 0) -> int:
    """Most PV a Sortie may field: available Player Force PV x (100 + modifiers)%, floored."""
    percent = max(-100, aces_pv_allowance_percent(difficulty, experienced_sp))
    return max(0, (force_pv * (100 + percent)) // 100)


def aces_omni_cost(old_pv: int, new_pv: int, size: int) -> int:
    """Aces Omni reconfiguration: Size x 5 if PV is equal/lower, else PV difference x 40."""
    if new_pv <= old_pv:
        return size * 5
    return (new_pv - old_pv) * 40


def aces_unit_category(unit_type_name: str | None) -> str | None:
    """BM / BA / CV / CI for the unit categories Aces supports; None for anything else."""
    name = (unit_type_name or "").lower()
    if "proto" in name:
        return None
    if "mech" in name:
        return "BM"
    if "battle armor" in name or "battlearmor" in name:
        return "BA"
    if "vehicle" in name:
        return "CV"
    if "infantry" in name:
        return "CI"
    return None


def sale_value(point_value: int) -> int:
    """Aces unit sale value: standard Skill 4 PV x 20 SP."""
    return point_value * ACES_SALE_MULTIPLIER
