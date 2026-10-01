"""Unit tests for campaign_rules.py (ruleset-dependent calculations)."""

from __future__ import annotations

import pytest

from app.services import campaign_rules


def test_repair_cost_aces_tiers():
    assert campaign_rules.repair_cost("aces", "armour", 70) == 20
    assert campaign_rules.repair_cost("aces", "structure", 70) == 40
    assert campaign_rules.repair_cost("aces", "crippled", 70) == 50
    assert campaign_rules.repair_cost("aces", "destroyed", 70) == 100
    assert campaign_rules.repair_cost("aces", "none", 70) == 0


def test_repair_cost_chaos_dispatches_to_tonnage_formula():
    assert campaign_rules.repair_cost("chaos", "armour", 70) == 35
    assert campaign_rules.repair_cost("chaos", "destroyed", 70) == 350


def test_purchase_cost_is_pv_times_forty():
    assert campaign_rules.purchase_cost(28) == 1120
    assert campaign_rules.purchase_cost(40) == 1600


def test_require_valid_ruleset_rejects_unknown():
    campaign_rules.require_valid_ruleset("chaos")
    campaign_rules.require_valid_ruleset("aces")
    with pytest.raises(ValueError, match="Unknown campaign ruleset"):
        campaign_rules.require_valid_ruleset("bogus")


class _FakeCampaign:
    def __init__(self, ruleset: str) -> None:
        self.ruleset = ruleset


def test_require_ruleset_rejects_mismatch():
    campaign_rules.require_ruleset(_FakeCampaign("aces"), "aces")
    with pytest.raises(ValueError, match="only available for aces campaigns"):
        campaign_rules.require_ruleset(_FakeCampaign("chaos"), "aces")
