"""Ruleset-dependent campaign calculations (Chaos Campaign vs Aces).

Two rulesets, two small dispatch functions here - not a generic plugin framework.
Ruleset-agnostic logic (rearm cost/ENE, warchest posting, truly-destroyed handling,
pilot wound/retirement states, roster eligibility) already lives in
campaign_service/after_action_service/contract_service and is reused unchanged.
"""

from __future__ import annotations

RULESETS = ("chaos", "aces")

ACES_REPAIR_COSTS = {
    "armour": 20,
    "structure": 40,
    "crippled": 50,
    "destroyed": 100,
}
ACES_PURCHASE_MULTIPLIER = 40


def require_valid_ruleset(ruleset: str) -> None:
    if ruleset not in RULESETS:
        raise ValueError(f"Unknown campaign ruleset: {ruleset}")


def require_ruleset(campaign, expected: str) -> None:
    if campaign.ruleset != expected:
        raise ValueError(f"This action is only available for {expected} campaigns")


def repair_cost(ruleset: str, damage: str, tonnage: int | None) -> int:
    """Gross repair SP for a damage category, dispatched by Campaign ruleset."""
    if ruleset == "aces":
        return ACES_REPAIR_COSTS.get(damage, 0)
    from .after_action_service import standard_repair_cost

    return standard_repair_cost(damage, tonnage)


def purchase_cost(point_value: int) -> int:
    """Aces replacement/additional unit purchase cost: PV x 40 SP."""
    return point_value * ACES_PURCHASE_MULTIPLIER
