"""Pure-rule tests for Aces repairs, difficulty and pilot SP distribution (Prompt 6c)."""

from __future__ import annotations

import json

import pytest

from app.services import aces_pilot_rules as rules
from app.services import campaign_rules

P, N, K, D = rules.PARTICIPANT, rules.NON_PARTICIPANT, rules.KILLED, rules.DEAD


# --- repairs -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("damage", "expected"),
    [("armour", 20), ("structure", 40), ("crippled", 60), ("destroyed", 100)],
)
def test_battlemech_repair_is_size_times_tier(damage, expected):
    assert campaign_rules.aces_repair_cost(damage, 1, battlemech=True) == expected
    assert campaign_rules.aces_repair_cost(damage, 4, battlemech=True) == expected * 4


@pytest.mark.parametrize("damage", ["armour", "structure", "crippled", "destroyed"])
def test_non_battlemech_uses_half_size(damage):
    full = campaign_rules.aces_repair_cost(damage, 4, battlemech=True)
    assert campaign_rules.aces_repair_cost(damage, 4, battlemech=False) == full // 2


def test_half_size_is_not_rounded_before_multiplier():
    # Size 3 Combat Vehicle, crippled: 1.5 x 60 = 90 (rounding 1.5 -> 2 first would give 120).
    assert campaign_rules.aces_repair_cost("crippled", 3, battlemech=False) == 90
    assert campaign_rules.aces_repair_cost("armour", 1, battlemech=False) == 10


def test_none_costs_nothing_and_truly_destroyed_cannot_be_repaired():
    assert campaign_rules.aces_repair_cost("none", 3, battlemech=True) == 0
    with pytest.raises(ValueError, match="cannot be repaired"):
        campaign_rules.aces_repair_cost("truly-destroyed", 3, battlemech=True)


def test_unit_size_prefers_bfsize_then_battlemech_tonnage_bands():
    assert campaign_rules.aces_unit_size(json.dumps({"BFSize": 2}), 100, "BattleMech") == 2
    assert campaign_rules.aces_unit_size(None, 20, "BattleMech") == 1
    assert campaign_rules.aces_unit_size(None, 45, "BattleMech") == 2
    assert campaign_rules.aces_unit_size(None, 70, "BattleMech") == 3
    assert campaign_rules.aces_unit_size(None, 100, "BattleMech") == 4
    # Never guess for other unit types.
    assert campaign_rules.aces_unit_size(None, 30, "Combat Vehicle") is None
    assert campaign_rules.aces_unit_size(None, 0, "BattleMech") is None


# --- difficulty ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "pv", "objective"),
    [
        ("Rookie", 20, 120),
        ("standard", 0, 100),
        ("Veteran", -10, 90),
        ("elite", -20, 80),
        ("LEGENDARY", -30, 70),
        (None, 0, 100),
        ("nonsense", 0, 100),
    ],
)
def test_difficulty_modifiers(name, pv, objective):
    assert campaign_rules.force_pv_modifier_percent(name) == pv
    assert campaign_rules.objective_sp_percent(name) == objective


def test_adjusted_objective_sp_rounds_half_up():
    assert campaign_rules.adjusted_objective_sp(100, "rookie") == 120
    assert campaign_rules.adjusted_objective_sp(100, "veteran") == 90
    assert campaign_rules.adjusted_objective_sp(5, "legendary") == 4  # 3.5 -> 4
    assert campaign_rules.adjusted_objective_sp(0, "elite") == 0


# --- pilot SP distribution -----------------------------------------------------------------


def test_caps_by_state():
    assert rules.pilot_sp_cap(P, 50) == 50
    assert rules.pilot_sp_cap(N, 50) == 25
    assert rules.pilot_sp_cap(N, 25) == 12  # floor of the half-share
    assert rules.pilot_sp_cap(K, 50) == 0
    assert rules.pilot_sp_cap(D, 50) == 0


def test_enough_earnings_pays_every_cap():
    awards = rules.distribute_pilot_sp(1000, 50, {1: P, 2: N, 3: K, 4: D})
    assert awards == {1: 50, 2: 25, 3: 0, 4: 0}


def test_insufficient_earnings_keeps_two_to_one_weighting():
    awards = rules.distribute_pilot_sp(30, 100, {1: P, 2: N, 3: K})
    assert awards == {1: 20, 2: 10, 3: 0}


def test_weighting_is_not_an_even_headcount_split():
    awards = rules.distribute_pilot_sp(50, 100, {1: P, 2: P, 3: N})
    assert awards == {1: 20, 2: 20, 3: 10}


def test_whole_sp_remainders_go_to_largest_fraction_then_lower_id():
    # 7 over weights 2,2,1 = 2.8, 2.8, 1.4 -> floors 2,2,1 (5), +1 to ids 1 and 2.
    awards = rules.distribute_pilot_sp(7, 100, {1: P, 2: P, 3: N})
    assert awards == {1: 3, 2: 3, 3: 1}
    # Tie on remainder: lower pilot id wins the odd SP.
    assert rules.distribute_pilot_sp(1, 100, {5: P, 3: P}) == {5: 0, 3: 1}


def test_never_exceeds_cap_or_earnings():
    for earnings in range(0, 120):
        for max_sp in (0, 1, 7, 25, 40):
            states = {1: P, 2: P, 3: N, 4: N, 5: K, 6: D}
            awards = rules.distribute_pilot_sp(earnings, max_sp, states)
            assert sum(awards.values()) <= max(earnings, 0)
            for pid, state in states.items():
                assert 0 <= awards[pid] <= rules.pilot_sp_cap(state, max_sp)
            assert awards[5] == awards[6] == 0


def test_no_positive_earnings_means_no_pilot_sp():
    states = {1: P, 2: N}
    assert rules.distribute_pilot_sp(0, 50, states) == {1: 0, 2: 0}
    assert rules.distribute_pilot_sp(-200, 50, states) == {1: 0, 2: 0}
    assert rules.distribute_pilot_sp(500, 0, states) == {1: 0, 2: 0}


def test_everyone_dead_or_killed_gets_nothing():
    assert rules.distribute_pilot_sp(100, 50, {1: K, 2: D}) == {1: 0, 2: 0}
