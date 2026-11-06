"""Sponsored Brands campaigns, ad groups and ads (v4) and keywords (v3)."""

from __future__ import annotations

from typing import Any

from .. import safety
from ..client import AmazonAdsClient
from ._common import (
    ListStyleEntity,
    RestStyleEntity,
    check_items,
    register_list_style,
    register_rest_style,
)

AD_MEDIA = "application/vnd.sbadresource.v4+json"

CAMPAIGNS = ListStyleEntity(
    prefix="sb",
    noun="campaigns",
    label="Sponsored Brands campaigns",
    path="/sb/v4/campaigns",
    media_type="application/vnd.sbcampaignresource.v4+json",
    items_key="campaigns",
    id_field="campaignId",
    id_filter="campaignIdFilter",
    filters={"portfolio_ids": "portfolioIdFilter"},
    money=(("budget", ("budget",)),),
    create_example=(
        'Example: {"name": "Brand video", "state": "PAUSED", "budget": 30, '
        '"budgetType": "DAILY", "startDate": "2026-12-01", "brandEntityId": "ENTITY..."}. '
        "Here budget is a plain number."
    ),
    update_example='Example: {"campaignId": "123", "budget": 40} or {"campaignId": "123", "state": "PAUSED"}.',
)

AD_GROUPS = ListStyleEntity(
    prefix="sb",
    noun="ad_groups",
    label="Sponsored Brands ad groups",
    path="/sb/v4/adGroups",
    media_type="application/vnd.sbadgroupresource.v4+json",
    items_key="adGroups",
    id_field="adGroupId",
    id_filter="adGroupIdFilter",
    filters={"campaign_ids": "campaignIdFilter"},
    create_example='Example: {"campaignId": "123", "name": "Ad group 1", "state": "ENABLED"}.',
    update_example='Only name and state can change. Example: {"adGroupId": "456", "state": "PAUSED"}.',
)

ADS = ListStyleEntity(
    prefix="sb",
    noun="ads",
    label="Sponsored Brands ads",
    path="/sb/v4/ads",
    media_type=AD_MEDIA,
    items_key="ads",
    id_field="adId",
    id_filter="adIdFilter",
    filters={"campaign_ids": "campaignIdFilter", "ad_group_ids": "adGroupIdFilter"},
    create=False,  # creation depends on the ad format: see amazon_ads_sb_create_ads
    update_example='Only name and state can change. Example: {"adId": "789", "state": "PAUSED"}.',
    extended_data=False,
)

KEYWORDS = RestStyleEntity(
    prefix="sb",
    noun="keywords",
    label="Sponsored Brands keywords",
    path="/sb/keywords",
    id_field="keywordId",
    id_filter="keywordIdFilter",
    filters={"campaign_ids": "campaignIdFilter", "ad_group_ids": "adGroupIdFilter"},
    money=(("bid", ("bid",)),),
    list_accept="application/vnd.sbkeyword.v3+json",
    write_accept="application/vnd.sbkeywordresponse.v3+json",
    create_example=(
        'Example: {"campaignId": 123, "adGroupId": 456, "keywordText": "trail shoes", '
        '"matchType": "phrase", "bid": 1.2}. matchType is exact, phrase or broad.'
    ),
    update_example=(
        'Each item needs keywordId, campaignId and adGroupId. Example: {"keywordId": 789, '
        '"campaignId": 123, "adGroupId": 456, "bid": 1.4}.'
    ),
)

AD_FORMATS = {
    "product_collection": "productCollection",
    "product_collection_extended": "productCollectionExtended",
    "store_spotlight": "storeSpotlight",
    "video": "video",
    "brand_video": "brandVideo",
    "auto_collection": "autoCollection",
    "manual_collection": "manualCollection",
}


def register(mcp, client: AmazonAdsClient) -> None:
    register_list_style(mcp, client, CAMPAIGNS)
    register_list_style(mcp, client, AD_GROUPS)
    register_list_style(mcp, client, ADS)
    register_rest_style(mcp, client, KEYWORDS)

    @mcp.tool()
    def amazon_ads_sb_create_ads(
        ad_format: str,
        ads: list[dict[str, Any]],
        profile_id: str | None = None,
        confirm: str = "",
    ) -> dict[str, Any]:
        """Create Sponsored Brands ads of one format. Changes the live account.

        ad_format: product_collection, product_collection_extended,
        store_spotlight, video, brand_video, auto_collection or manual_collection.
        ads: objects with adGroupId, name, state and a format-specific creative
        (product collection and store spotlight also need landingPage). Creative
        assets (logos, images, videos) must already exist in the advertiser's
        asset library. Large batches need confirm='APPLY'.
        """
        fmt = AD_FORMATS.get(ad_format.strip().lower())
        if fmt is None:
            raise ValueError(f"ad_format must be one of {', '.join(AD_FORMATS)}.")
        check_items(ads, "ads", max_items=10)
        decision = safety.assess(client.config, count=len(ads))
        body = {"ads": ads}
        refused = safety.refusal(client.config, decision, confirm, preview=body)
        if refused:
            return refused
        out = client.request(
            "POST",
            f"/sb/v4/ads/{fmt}",
            json_body=body,
            profile_id=profile_id,
            content_type=AD_MEDIA,
            op=f"sb_create_ads_{ad_format}",
        )
        return safety.annotate(out, decision)
