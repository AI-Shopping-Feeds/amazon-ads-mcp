"""Sponsored Products keywords, product targets and negatives (v3 endpoints)."""

from __future__ import annotations

from ..client import AmazonAdsClient
from ._common import ListStyleEntity, register_list_style

_CAMPAIGN_AND_AD_GROUP = {"campaign_ids": "campaignIdFilter", "ad_group_ids": "adGroupIdFilter"}

KEYWORDS = ListStyleEntity(
    prefix="sp",
    noun="keywords",
    label="Sponsored Products keywords",
    path="/sp/keywords",
    media_type="application/vnd.spKeyword.v3+json",
    items_key="keywords",
    id_field="keywordId",
    id_filter="keywordIdFilter",
    filters=_CAMPAIGN_AND_AD_GROUP,
    money=(("bid", ("bid",)),),
    create_example=(
        'Example: {"campaignId": "123", "adGroupId": "456", "keywordText": "running shoes", '
        '"matchType": "EXACT", "state": "ENABLED", "bid": 0.8}. matchType is EXACT, PHRASE '
        "or BROAD; without bid the ad group's default bid applies."
    ),
    update_example='Only bid and state can change. Example: {"keywordId": "789", "bid": 0.95}.',
)

NEGATIVE_KEYWORDS = ListStyleEntity(
    prefix="sp",
    noun="negative_keywords",
    label="Sponsored Products ad-group negative keywords",
    path="/sp/negativeKeywords",
    media_type="application/vnd.spNegativeKeyword.v3+json",
    items_key="negativeKeywords",
    id_field="keywordId",
    id_filter="negativeKeywordIdFilter",
    filters=_CAMPAIGN_AND_AD_GROUP,
    update=False,
    default_states=("ENABLED",),
    create_example=(
        'Example: {"campaignId": "123", "adGroupId": "456", "keywordText": "free", '
        '"matchType": "NEGATIVE_EXACT", "state": "ENABLED"}. matchType is NEGATIVE_EXACT or '
        "NEGATIVE_PHRASE."
    ),
)

CAMPAIGN_NEGATIVE_KEYWORDS = ListStyleEntity(
    prefix="sp",
    noun="campaign_negative_keywords",
    label="Sponsored Products campaign-level negative keywords",
    path="/sp/campaignNegativeKeywords",
    media_type="application/vnd.spCampaignNegativeKeyword.v3+json",
    items_key="campaignNegativeKeywords",
    id_field="keywordId",
    id_filter="campaignNegativeKeywordIdFilter",
    filters={"campaign_ids": "campaignIdFilter"},
    update=False,
    default_states=("ENABLED",),
    create_example=(
        'Example: {"campaignId": "123", "keywordText": "cheap", "matchType": "NEGATIVE_PHRASE", '
        '"state": "ENABLED"}.'
    ),
)

TARGETS = ListStyleEntity(
    prefix="sp",
    noun="targets",
    label="Sponsored Products product and auto targets",
    path="/sp/targets",
    media_type="application/vnd.spTargetingClause.v3+json",
    items_key="targetingClauses",
    id_field="targetId",
    id_filter="targetIdFilter",
    filters=_CAMPAIGN_AND_AD_GROUP,
    money=(("bid", ("bid",)),),
    create_example=(
        'Example (target an ASIN): {"campaignId": "123", "adGroupId": "456", '
        '"expressionType": "MANUAL", "expression": [{"type": "ASIN_SAME_AS", "value": '
        '"B000000000"}], "state": "ENABLED", "bid": 0.6}.'
    ),
    update_example='Only bid and state can change. Example: {"targetId": "789", "bid": 0.5}.',
)

NEGATIVE_TARGETS = ListStyleEntity(
    prefix="sp",
    noun="negative_targets",
    label="Sponsored Products ad-group negative product targets",
    path="/sp/negativeTargets",
    media_type="application/vnd.spNegativeTargetingClause.v3+json",
    items_key="negativeTargetingClauses",
    id_field="targetId",
    id_filter="negativeTargetIdFilter",
    filters=_CAMPAIGN_AND_AD_GROUP,
    update=False,
    default_states=("ENABLED",),
    create_example=(
        'Example: {"campaignId": "123", "adGroupId": "456", "expression": [{"type": '
        '"ASIN_BRAND_SAME_AS", "value": "12345"}], "state": "ENABLED"}.'
    ),
)

CAMPAIGN_NEGATIVE_TARGETS = ListStyleEntity(
    prefix="sp",
    noun="campaign_negative_targets",
    label="Sponsored Products campaign-level negative product targets",
    path="/sp/campaignNegativeTargets",
    media_type="application/vnd.spCampaignNegativeTargetingClause.v3+json",
    items_key="campaignNegativeTargetingClauses",
    id_field="targetId",
    id_filter="campaignNegativeTargetIdFilter",
    filters={"campaign_ids": "campaignIdFilter"},
    update=False,
    default_states=("ENABLED",),
    create_example=(
        'Example: {"campaignId": "123", "expression": [{"type": "ASIN_SAME_AS", "value": '
        '"B000000000"}], "state": "ENABLED"}.'
    ),
)

ENTITIES = (
    KEYWORDS,
    NEGATIVE_KEYWORDS,
    CAMPAIGN_NEGATIVE_KEYWORDS,
    TARGETS,
    NEGATIVE_TARGETS,
    CAMPAIGN_NEGATIVE_TARGETS,
)


def register(mcp, client: AmazonAdsClient) -> None:
    for spec in ENTITIES:
        register_list_style(mcp, client, spec)
