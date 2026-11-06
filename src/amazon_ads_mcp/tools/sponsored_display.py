"""Sponsored Display campaigns, ad groups, product ads, targets and negative targets."""

from __future__ import annotations

from ..client import AmazonAdsClient
from ._common import RestStyleEntity, register_rest_style

_BY_CAMPAIGN = {"campaign_ids": "campaignIdFilter"}
_BY_CAMPAIGN_AND_AD_GROUP = {"campaign_ids": "campaignIdFilter", "ad_group_ids": "adGroupIdFilter"}

CAMPAIGNS = RestStyleEntity(
    prefix="sd",
    noun="campaigns",
    label="Sponsored Display campaigns",
    path="/sd/campaigns",
    id_field="campaignId",
    id_filter="campaignIdFilter",
    filters={"portfolio_ids": "portfolioIdFilter"},
    money=(("budget", ("budget",)),),
    create_example=(
        'Example: {"name": "Retargeting", "tactic": "T00030", "budgetType": "daily", '
        '"budget": 15, "startDate": "20261201", "costType": "cpc", "state": "paused"}. '
        "Dates are YYYYMMDD; states are lower-case."
    ),
    update_example='Example: {"campaignId": 123, "budget": 20} or {"campaignId": 123, "state": "paused"}.',
)

AD_GROUPS = RestStyleEntity(
    prefix="sd",
    noun="ad_groups",
    label="Sponsored Display ad groups",
    path="/sd/adGroups",
    id_field="adGroupId",
    id_filter="adGroupIdFilter",
    filters=_BY_CAMPAIGN,
    money=(("bid", ("defaultBid",)),),
    create_example=(
        'Example: {"campaignId": 123, "name": "Views", "defaultBid": 0.8, '
        '"bidOptimization": "clicks", "state": "enabled"}.'
    ),
    update_example='Example: {"adGroupId": 456, "defaultBid": 0.9}.',
)

PRODUCT_ADS = RestStyleEntity(
    prefix="sd",
    noun="product_ads",
    label="Sponsored Display product ads",
    path="/sd/productAds",
    id_field="adId",
    id_filter="adIdFilter",
    filters=_BY_CAMPAIGN_AND_AD_GROUP,
    create_example=(
        'Sellers use sku, vendors asin. Example: {"campaignId": 123, "adGroupId": 456, '
        '"sku": "MY-SKU-1", "state": "enabled"}.'
    ),
    update_example='Only state can change. Example: {"adId": 789, "state": "paused"}.',
)

TARGETS = RestStyleEntity(
    prefix="sd",
    noun="targets",
    label="Sponsored Display targets (products, categories and audiences)",
    path="/sd/targets",
    id_field="targetId",
    id_filter="targetIdFilter",
    filters=_BY_CAMPAIGN_AND_AD_GROUP,
    money=(("bid", ("bid",)),),
    create_example=(
        'Example: {"adGroupId": 456, "expressionType": "manual", "expression": '
        '[{"type": "asinSameAs", "value": "B000000000"}], "bid": 0.7, "state": "enabled"}.'
    ),
    update_example='Example: {"targetId": 789, "bid": 0.6} or {"targetId": 789, "state": "paused"}.',
)

NEGATIVE_TARGETS = RestStyleEntity(
    prefix="sd",
    noun="negative_targets",
    label="Sponsored Display negative targets",
    path="/sd/negativeTargets",
    id_field="targetId",
    id_filter=None,
    filters=_BY_CAMPAIGN_AND_AD_GROUP,
    update=False,
    default_states=("enabled",),
    create_example=(
        'Example: {"adGroupId": 456, "expressionType": "manual", "expression": '
        '[{"type": "asinBrandSameAs", "value": "12345"}], "state": "enabled"}.'
    ),
)

ENTITIES = (CAMPAIGNS, AD_GROUPS, PRODUCT_ADS, TARGETS, NEGATIVE_TARGETS)


def register(mcp, client: AmazonAdsClient) -> None:
    for spec in ENTITIES:
        register_rest_style(mcp, client, spec)
