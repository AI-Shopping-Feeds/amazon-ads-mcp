from __future__ import annotations

import dataclasses

from amazon_ads_mcp import safety
from amazon_ads_mcp.config import Config


def test_small_update_without_money_needs_nothing(config: Config) -> None:
    d = safety.assess(config, count=3)
    assert d.required is None
    assert safety.refusal(config, d, "") is None


def test_archive_needs_archive(config: Config) -> None:
    d = safety.assess(config, count=1, destructive=safety.ARCHIVE)
    assert d.required == "ARCHIVE"
    assert safety.refusal(config, d, "APPLY")["refused"] is True
    assert safety.refusal(config, d, "ARCHIVE") is None


def test_bulk_needs_apply(config: Config) -> None:
    d = safety.assess(config, count=config.bulk_threshold + 1)
    assert d.required == "APPLY"


def test_increase_above_limit_needs_apply(config: Config) -> None:
    small = safety.assess(config, count=1, changes=[safety.MoneyChange("1", "bid", 1.0, 1.2)])
    assert small.required is None
    big = safety.assess(config, count=1, changes=[safety.MoneyChange("1", "bid", 1.0, 1.5)])
    assert big.required == "APPLY"
    assert big.changes[0]["change_pct"] == 50.0
    decrease = safety.assess(config, count=1, changes=[safety.MoneyChange("1", "bid", 1.0, 0.2)])
    assert decrease.required is None


def test_unknown_current_value_needs_apply(config: Config) -> None:
    d = safety.assess(config, count=1, changes=[safety.MoneyChange("1", "budget", None, 10)])
    assert d.required == "APPLY"


def test_caps_apply_to_creates(config: Config) -> None:
    capped = dataclasses.replace(config, max_budget=50.0)
    d = safety.assess(
        capped, count=1, changes=[safety.MoneyChange("new[0]", "budget", None, 80)], creating=True
    )
    assert d.required == "APPLY"
    ok = safety.assess(
        capped, count=1, changes=[safety.MoneyChange("new[0]", "budget", None, 20)], creating=True
    )
    assert ok.required is None


def test_dry_run_never_refuses(config: Config) -> None:
    d = safety.assess(config, count=1, destructive=safety.ARCHIVE)
    assert safety.refusal(dataclasses.replace(config, dry_run=True), d, "") is None


def test_money_changes_pairs_with_current() -> None:
    changes = safety.money_changes(
        [{"campaignId": "1", "budget": {"budget": 30}}, {"campaignId": "2", "state": "PAUSED"}],
        [{"campaignId": "1", "budget": {"budget": 20}}],
        id_field="campaignId",
        fields=(("budget", ("budget", "budget")),),
    )
    assert changes == [safety.MoneyChange("1", "budget", 20.0, 30.0)]
