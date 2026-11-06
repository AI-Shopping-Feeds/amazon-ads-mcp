"""Sponsored Products budget, bid and keyword recommendations (read-only)."""

from __future__ import annotations

from typing import Any

from ..client import AmazonAdsClient
from ._common import ids_to_strings

BUDGET_MEDIA = "application/vnd.budgetrecommendation.v3+json"
BID_MEDIA = "application/vnd.spthemebasedbidrecommendation.v5+json"
KEYWORD_MEDIA = "application/vnd.spkeywordsrecommendation.v5+json"


def register(mcp, client: AmazonAdsClient) -> None:
    @mcp.tool()
    def amazon_ads_sp_budget_recommendations(
        campaign_ids: list[str], profile_id: str | None = None
    ) -> dict[str, Any]:
        """Suggested daily budgets for existing Sponsored Products campaigns.

        Returns, per campaign, Amazon's suggested budget and an estimate of what
        the campaign missed in the last week by running out of budget. Up to 100
        campaigns per call. Nothing is changed.
        """
        ids = ids_to_strings(campaign_ids)
        if not ids:
            raise ValueError("Pass at least one campaign ID.")
        return client.request(
            "POST",
            "/sp/campaigns/budgetRecommendations",
            json_body={"campaignIds": ids[:100]},
            profile_id=profile_id,
            content_type=BUDGET_MEDIA,
            read_only=True,
        )

    @mcp.tool()
    def amazon_ads_sp_bid_recommendations(
        targeting_expressions: list[dict[str, Any]],
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        asins: list[str] | None = None,
        bidding: dict[str, Any] | None = None,
        include_analysis: bool = False,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        """Suggested bids for keywords or product targets. Nothing is changed.

        Either pass campaign_id and ad_group_id (an existing ad group), or asins
        and bidding (for an ad group you haven't created yet, e.g.
        bidding={"strategy": "LEGACY_FOR_SALES"}).

        targeting_expressions: what to price, e.g.
            [{"type": "KEYWORD_EXACT_MATCH", "value": "running shoes"},
             {"type": "CLOSE_MATCH"}]
        """
        body: dict[str, Any] = {
            "targetingExpressions": targeting_expressions,
            "includeAnalysis": include_analysis,
        }
        if campaign_id and ad_group_id:
            body.update(
                recommendationType="BIDS_FOR_EXISTING_AD_GROUP",
                campaignId=str(campaign_id),
                adGroupId=str(ad_group_id),
            )
        elif asins:
            body.update(
                recommendationType="BIDS_FOR_NEW_AD_GROUP",
                asins=ids_to_strings(asins),
                bidding=bidding or {"strategy": "LEGACY_FOR_SALES"},
            )
        else:
            raise ValueError("Pass campaign_id and ad_group_id, or asins.")
        return client.request(
            "POST",
            "/sp/targets/bid/recommendations",
            json_body=body,
            profile_id=profile_id,
            content_type=BID_MEDIA,
            read_only=True,
        )

    @mcp.tool()
    def amazon_ads_sp_keyword_recommendations(
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        asins: list[str] | None = None,
        max_recommendations: int = 100,
        bids_enabled: bool = True,
        sort_dimension: str = "DEFAULT",
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        """Keyword ideas, ranked, with suggested bids. Nothing is changed.

        Either pass campaign_id and ad_group_id (ideas for an existing ad group),
        or up to 50 asins (ideas for products). max_recommendations is at most 200.
        sort_dimension: DEFAULT, CLICKS or
        CONVERSIONS.
        """
        body: dict[str, Any] = {
            "maxRecommendations": max(0, min(max_recommendations, 200)),
            "bidsEnabled": bids_enabled,
            "sortDimension": sort_dimension,
        }
        if campaign_id and ad_group_id:
            body.update(
                recommendationType="KEYWORDS_FOR_ADGROUP",
                campaignId=str(campaign_id),
                adGroupId=str(ad_group_id),
            )
        elif asins:
            body.update(recommendationType="KEYWORDS_FOR_ASINS", asins=ids_to_strings(asins)[:50])
        else:
            raise ValueError("Pass campaign_id and ad_group_id, or asins.")
        return client.request(
            "POST",
            "/sp/targets/keywords/recommendations",
            json_body=body,
            profile_id=profile_id,
            content_type=KEYWORD_MEDIA,
            read_only=True,
        )
