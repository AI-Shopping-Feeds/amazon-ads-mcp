"""Sponsored Products product ads (v3 endpoints)."""

from __future__ import annotations

from ..client import AmazonAdsClient
from ._common import ListStyleEntity, register_list_style

PRODUCT_ADS = ListStyleEntity(
    prefix="sp",
    noun="product_ads",
    label="Sponsored Products product ads",
    path="/sp/productAds",
    media_type="application/vnd.spProductAd.v3+json",
    items_key="productAds",
    id_field="adId",
    id_filter="adIdFilter",
    filters={"campaign_ids": "campaignIdFilter", "ad_group_ids": "adGroupIdFilter"},
    create_example=(
        'Sellers advertise by SKU, vendors by ASIN. Example: {"campaignId": "123", '
        '"adGroupId": "456", "sku": "MY-SKU-1", "state": "ENABLED"}.'
    ),
    update_example='Only state can change. Example: {"adId": "789", "state": "PAUSED"}.',
)


def register(mcp, client: AmazonAdsClient) -> None:
    register_list_style(mcp, client, PRODUCT_ADS)
