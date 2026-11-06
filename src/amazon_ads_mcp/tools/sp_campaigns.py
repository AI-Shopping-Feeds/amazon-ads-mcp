"""Sponsored Products campaigns and ad groups (v3 endpoints)."""

from __future__ import annotations

from ..client import AmazonAdsClient
from ._common import ListStyleEntity, register_list_style

CAMPAIGNS = ListStyleEntity(
    prefix="sp",
    noun="campaigns",
    label="Sponsored Products campaigns",
    path="/sp/campaigns",
    media_type="application/vnd.spCampaign.v3+json",
    items_key="campaigns",
    id_field="campaignId",
    id_filter="campaignIdFilter",
    filters={"portfolio_ids": "portfolioIdFilter"},
    money=(("budget", ("budget", "budget")),),
    create_example=(
        'Example: {"name": "Brand - Exact", "targetingType": "MANUAL", "state": "PAUSED", '
        '"budget": {"budgetType": "DAILY", "budget": 20}, "startDate": "2026-12-01", '
        '"dynamicBidding": {"strategy": "LEGACY_FOR_SALES"}}. Creating campaigns PAUSED '
        "lets the user review them before they spend."
    ),
    update_example=(
        'Example: {"campaignId": "123", "budget": {"budgetType": "DAILY", "budget": 25}} '
        'or {"campaignId": "123", "state": "PAUSED"}.'
    ),
)

AD_GROUPS = ListStyleEntity(
    prefix="sp",
    noun="ad_groups",
    label="Sponsored Products ad groups",
    path="/sp/adGroups",
    media_type="application/vnd.spAdGroup.v3+json",
    items_key="adGroups",
    id_field="adGroupId",
    id_filter="adGroupIdFilter",
    filters={"campaign_ids": "campaignIdFilter"},
    money=(("bid", ("defaultBid",)),),
    create_example=(
        'Example: {"campaignId": "123", "name": "Exact", "state": "ENABLED", "defaultBid": 0.75}.'
    ),
    update_example='Example: {"adGroupId": "456", "defaultBid": 0.9}.',
)


def register(mcp, client: AmazonAdsClient) -> None:
    register_list_style(mcp, client, CAMPAIGNS)
    register_list_style(mcp, client, AD_GROUPS)
