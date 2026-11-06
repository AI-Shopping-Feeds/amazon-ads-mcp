"""Amazon Ads API v1: one campaign-management model across ad products.

The v1 endpoints use the same request shape for Sponsored Products, Sponsored
Brands, Sponsored Display, Sponsored Television and DSP: POST
/adsApi/v1/{query|create|update|delete}/{entity}. Field names differ from the
older per-product APIs, so read entities with amazon_ads_v1_query before
writing.
"""

from __future__ import annotations

from typing import Any

from .. import safety
from ..client import AmazonAdsClient
from ._common import check_items, ids_to_strings

ENTITIES = {
    "campaigns": "campaignId",
    "adGroups": "adGroupId",
    "ads": "adId",
    "targets": "targetId",
    "adAssociations": "adAssociationId",
}
AD_PRODUCTS = {
    "SPONSORED_PRODUCTS",
    "SPONSORED_BRANDS",
    "SPONSORED_DISPLAY",
    "SPONSORED_TELEVISION",
    "AMAZON_DSP",
}
_MONEY_KEYS = {"budget", "budgets", "bid", "bids", "defaultBid", "monetaryBudget"}


def _entity(entity: str) -> str:
    if entity not in ENTITIES:
        raise ValueError(f"entity must be one of {', '.join(ENTITIES)}.")
    return entity


def _touches_money(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(k in _MONEY_KEYS or _touches_money(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_touches_money(v) for v in obj)
    return False


def register(mcp, client: AmazonAdsClient) -> None:
    @mcp.tool()
    def amazon_ads_v1_query(
        entity: str,
        ad_product: str = "SPONSORED_PRODUCTS",
        filters: dict[str, Any] | None = None,
        max_results: int = 200,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        """Query entities through Amazon Ads API v1 (read-only).

        entity: campaigns, adGroups, ads, targets or adAssociations.
        ad_product: SPONSORED_PRODUCTS, SPONSORED_BRANDS, SPONSORED_DISPLAY,
        SPONSORED_TELEVISION or AMAZON_DSP (adAssociations takes no ad product).
        filters: extra filter objects, each {"include": [...]}, e.g.
        {"campaignIdFilter": {"include": ["123"]}, "stateFilter": {"include": ["ENABLED"]}}.
        """
        entity = _entity(entity)
        body: dict[str, Any] = dict(filters or {})
        if entity != "adAssociations":
            product = ad_product.upper()
            if product not in AD_PRODUCTS:
                raise ValueError(f"ad_product must be one of {', '.join(sorted(AD_PRODUCTS))}.")
            body["adProductFilter"] = {"include": [product]}
        items, truncated = client.paginate_token(
            f"/adsApi/v1/query/{entity}",
            body,
            items_key=entity,
            content_type="application/json",
            profile_id=profile_id,
            max_results=max_results,
        )
        return {entity: items, "count": len(items), "truncated": truncated}

    def _write(action: str, entity: str, items: list[dict[str, Any]], profile_id, confirm):
        entity = _entity(entity)
        check_items(items, entity)
        decision = safety.assess(client.config, count=len(items), creating=action == "create")
        if _touches_money(items):
            decision.reasons.append(
                "sets bids or budgets; v1 writes aren't compared with current values"
            )
            decision.required = decision.required or safety.APPLY
        body = {entity: items}
        refused = safety.refusal(client.config, decision, confirm, preview=body)
        if refused:
            return refused
        before = None
        if action == "update":
            id_field = ENTITIES[entity]
            ids = [str(i.get(id_field)) for i in items if i.get(id_field)]
            if ids:
                before = client.snapshot(
                    client.request,
                    "POST",
                    f"/adsApi/v1/query/{entity}",
                    json_body={
                        f"{id_field}Filter": {"include": ids},
                        **(
                            {"adProductFilter": {"include": [items[0]["adProduct"]]}}
                            if items[0].get("adProduct")
                            else {}
                        ),
                    },
                    profile_id=profile_id,
                    read_only=True,
                )
        out = client.request(
            "POST",
            f"/adsApi/v1/{action}/{entity}",
            json_body=body,
            profile_id=profile_id,
            op=f"v1_{action}_{entity}",
            before=before,
        )
        return safety.annotate(out, decision)

    @mcp.tool()
    def amazon_ads_v1_create(
        entity: str,
        items: list[dict[str, Any]],
        profile_id: str | None = None,
        confirm: str = "",
    ) -> dict[str, Any]:
        """Create entities through Amazon Ads API v1. Changes the live account.

        entity: campaigns, adGroups, ads, targets or adAssociations. Each item
        needs its adProduct (except adAssociations). Anything that sets a bid or
        budget, and large batches, need confirm='APPLY'. Rehearse in dry-run.
        """
        return _write("create", entity, items, profile_id, confirm)

    @mcp.tool()
    def amazon_ads_v1_update(
        entity: str,
        items: list[dict[str, Any]],
        profile_id: str | None = None,
        confirm: str = "",
    ) -> dict[str, Any]:
        """Update entities through Amazon Ads API v1. Changes the live account.

        Each item needs the entity's ID field (campaignId, adGroupId, adId,
        targetId or adAssociationId) and only the fields to change. Bid or budget
        changes and large batches need confirm='APPLY'.
        """
        return _write("update", entity, items, profile_id, confirm)

    @mcp.tool()
    def amazon_ads_v1_delete(
        entity: str,
        ids: list[str],
        profile_id: str | None = None,
        confirm: str = "",
    ) -> dict[str, Any]:
        """Delete entities through Amazon Ads API v1. Needs confirm='DELETE'.

        Deleting can't be undone; pausing (state PAUSED via amazon_ads_v1_update)
        is usually what the user wants.
        """
        entity = _entity(entity)
        id_list = ids_to_strings(ids)
        if not id_list:
            raise ValueError("Pass at least one ID.")
        decision = safety.assess(client.config, count=len(id_list), destructive=safety.DELETE)
        body = {f"{ENTITIES[entity]}s": id_list}
        refused = safety.refusal(client.config, decision, confirm, preview=body)
        if refused:
            return refused
        out = client.request(
            "POST",
            f"/adsApi/v1/delete/{entity}",
            json_body=body,
            profile_id=profile_id,
            op=f"v1_delete_{entity}",
        )
        return safety.annotate(out, decision)
