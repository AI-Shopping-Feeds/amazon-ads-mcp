"""Sponsored Products budget rules: scheduled or performance-based budget raises."""

from __future__ import annotations

from typing import Any

from .. import safety
from ..client import AmazonAdsClient
from ._common import check_items, ids_to_strings, path_id


def _rules_decision(client: AmazonAdsClient, count: int) -> safety.Decision:
    d = safety.assess(client.config, count=count)
    d.reasons.append("budget rules raise campaign budgets automatically while active")
    d.required = d.required or safety.APPLY
    return d


def register(mcp, client: AmazonAdsClient) -> None:
    @mcp.tool()
    def amazon_ads_sp_list_budget_rules(
        profile_id: str | None = None, page_size: int = 30, next_token: str | None = None
    ) -> dict[str, Any]:
        """List the advertiser's Sponsored Products budget rules (one page)."""
        params: dict[str, Any] = {"pageSize": max(1, min(page_size, 30))}
        if next_token:
            params["nextToken"] = next_token
        return client.request("GET", "/sp/budgetRules", params=params, profile_id=profile_id)

    @mcp.tool()
    def amazon_ads_sp_get_budget_rule(
        budget_rule_id: str, profile_id: str | None = None
    ) -> dict[str, Any]:
        """Get one Sponsored Products budget rule."""
        rule_id = path_id(budget_rule_id, "budget_rule_id")
        return client.request("GET", f"/sp/budgetRules/{rule_id}", profile_id=profile_id)

    @mcp.tool()
    def amazon_ads_sp_list_campaign_budget_rules(
        campaign_id: str, profile_id: str | None = None
    ) -> dict[str, Any]:
        """List the budget rules attached to one Sponsored Products campaign."""
        cid = path_id(campaign_id, "campaign_id")
        return client.request("GET", f"/sp/campaigns/{cid}/budgetRules", profile_id=profile_id)

    @mcp.tool()
    def amazon_ads_sp_create_budget_rules(
        rules: list[dict[str, Any]], profile_id: str | None = None, confirm: str = ""
    ) -> dict[str, Any]:
        """Create Sponsored Products budget rules. Always needs confirm='APPLY'.

        rules: rule definitions sent under budgetRulesDetails, each with a name,
        ruleType (SCHEDULE or PERFORMANCE), duration, optional recurrence and
        performanceMeasureCondition, and budgetIncreaseBy (e.g.
        {"type": "PERCENT", "value": 20}). A rule does nothing until it is
        attached to a campaign with amazon_ads_sp_attach_budget_rules.
        """
        check_items(rules, "rules", max_items=25)
        decision = _rules_decision(client, len(rules))
        body = {"budgetRulesDetails": rules}
        refused = safety.refusal(client.config, decision, confirm, preview=body)
        if refused:
            return refused
        out = client.request(
            "POST",
            "/sp/budgetRules",
            json_body=body,
            profile_id=profile_id,
            op="sp_create_budget_rules",
        )
        return safety.annotate(out, decision)

    @mcp.tool()
    def amazon_ads_sp_update_budget_rules(
        rules: list[dict[str, Any]], profile_id: str | None = None, confirm: str = ""
    ) -> dict[str, Any]:
        """Update Sponsored Products budget rules (each with its ruleId). Needs confirm='APPLY'."""
        check_items(rules, "rules", max_items=25)
        missing = [i for i, r in enumerate(rules) if not r.get("ruleId")]
        if missing:
            raise ValueError(f"Every rule needs ruleId; missing at index {missing}.")
        rule_ids = [path_id(r["ruleId"], "ruleId") for r in rules]
        before = [
            client.snapshot(client.request, "GET", f"/sp/budgetRules/{rid}", profile_id=profile_id)
            for rid in rule_ids
        ]
        decision = _rules_decision(client, len(rules))
        body = {"budgetRulesDetails": rules}
        refused = safety.refusal(client.config, decision, confirm, preview=body)
        if refused:
            return refused
        out = client.request(
            "PUT",
            "/sp/budgetRules",
            json_body=body,
            profile_id=profile_id,
            op="sp_update_budget_rules",
            before=before,
        )
        return safety.annotate(out, decision)

    @mcp.tool()
    def amazon_ads_sp_attach_budget_rules(
        campaign_id: str,
        budget_rule_ids: list[str],
        profile_id: str | None = None,
        confirm: str = "",
    ) -> dict[str, Any]:
        """Attach budget rules to a Sponsored Products campaign. Needs confirm='APPLY'."""
        cid = path_id(campaign_id, "campaign_id")
        ids = ids_to_strings(budget_rule_ids)
        if not ids:
            raise ValueError("Pass at least one budget rule ID.")
        decision = _rules_decision(client, len(ids))
        body = {"budgetRuleIds": ids}
        refused = safety.refusal(client.config, decision, confirm, preview=body)
        if refused:
            return refused
        out = client.request(
            "POST",
            f"/sp/campaigns/{cid}/budgetRules",
            json_body=body,
            profile_id=profile_id,
            op="sp_attach_budget_rules",
        )
        return safety.annotate(out, decision)

    @mcp.tool()
    def amazon_ads_sp_detach_budget_rule(
        campaign_id: str, budget_rule_id: str, profile_id: str | None = None
    ) -> dict[str, Any]:
        """Detach a budget rule from a Sponsored Products campaign (the rule itself is kept)."""
        cid = path_id(campaign_id, "campaign_id")
        rule_id = path_id(budget_rule_id, "budget_rule_id")
        before = client.snapshot(
            client.request,
            "GET",
            f"/sp/campaigns/{cid}/budgetRules",
            profile_id=profile_id,
        )
        return client.request(
            "DELETE",
            f"/sp/campaigns/{cid}/budgetRules/{rule_id}",
            profile_id=profile_id,
            op="sp_detach_budget_rule",
            before=before,
        )
