"""Bulk Sponsored Products changes: adjust bids by a percentage, or pause/enable many entities."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context

from .. import safety
from ..auth import redact
from ..client import AmazonAdsClient
from ._common import ListStyleEntity, ids_to_strings, list_style_fetch
from ._progress import report, run_blocking
from .sp_ads import PRODUCT_ADS
from .sp_campaigns import AD_GROUPS, CAMPAIGNS
from .sp_targeting import KEYWORDS, TARGETS

CHUNK = 100

BID_ENTITIES: dict[str, tuple[ListStyleEntity, str]] = {
    "keywords": (KEYWORDS, "bid"),
    "targets": (TARGETS, "bid"),
    "ad_groups": (AD_GROUPS, "defaultBid"),
}
STATE_ENTITIES: dict[str, ListStyleEntity] = {
    "campaigns": CAMPAIGNS,
    "ad_groups": AD_GROUPS,
    "product_ads": PRODUCT_ADS,
    "keywords": KEYWORDS,
    "targets": TARGETS,
}


async def _send_chunks(
    client: AmazonAdsClient,
    spec: ListStyleEntity,
    items: list[dict[str, Any]],
    *,
    profile_id: str | None,
    before: list[Any] | None,
    op: str,
    ctx: Context | None,
) -> dict[str, Any]:
    by_id = {str(b.get(spec.id_field)): b for b in (before or [])}
    results: list[Any] = []
    failed: list[dict[str, Any]] = []
    total = len(items)
    done = 0
    for start in range(0, total, CHUNK):
        chunk = items[start : start + CHUNK]
        snap = [by_id[str(i[spec.id_field])] for i in chunk if str(i[spec.id_field]) in by_id]
        try:
            out = await run_blocking(
                client.request,
                "PUT",
                spec.path,
                json_body={spec.items_key: chunk},
                profile_id=profile_id,
                content_type=spec.media_type,
                op=op,
                before=snap or None,
            )
            results.append(out)
        except Exception as e:
            failed.append(
                {"from_index": start, "count": len(chunk), "reason": redact(str(e))[:300]}
            )
        done += len(chunk)
        await report(ctx, done, total, f"Sent {done} of {total}")
    return {"sent": total, "batches": results, "failed_batches": failed}


def register(mcp, client: AmazonAdsClient) -> None:
    @mcp.tool()
    async def amazon_ads_sp_adjust_bids(
        entity: str,
        ids: list[str],
        change_pct: float | None = None,
        set_bid: float | None = None,
        min_bid: float = 0.02,
        max_bid: float | None = None,
        profile_id: str | None = None,
        confirm: str = "",
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Change many Sponsored Products bids at once, with progress.

        entity: 'keywords', 'targets' or 'ad_groups' (the ad group default bid).
        Pass change_pct (e.g. -10 lowers each bid by 10%, 15 raises it by 15%) or
        set_bid (one value for all). New bids are rounded to 2 decimals and kept
        between min_bid and max_bid. Current bids are read first: the result lists
        old and new bids, and the audit log keeps the old ones.

        Needs confirm='APPLY' for more than AMAZON_ADS_BULK_THRESHOLD items or any
        rise above AMAZON_ADS_MAX_INCREASE_PCT. Run in dry-run first and show the
        user the table of changes.
        """
        if entity not in BID_ENTITIES:
            raise ValueError(f"entity must be one of {', '.join(BID_ENTITIES)}.")
        if (change_pct is None) == (set_bid is None):
            raise ValueError("Pass exactly one of change_pct or set_bid.")
        id_list = ids_to_strings(ids)
        if not id_list:
            raise ValueError("Pass at least one ID.")
        if len(id_list) > 5000:
            raise ValueError("At most 5000 IDs per call.")
        spec, field = BID_ENTITIES[entity]
        current, _ = await run_blocking(
            list_style_fetch,
            client,
            spec,
            profile_id=profile_id,
            ids=id_list,
            max_results=len(id_list),
        )
        found = {str(c.get(spec.id_field)): c for c in current}
        missing = [i for i in id_list if i not in found]
        items: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for eid in id_list:
            row = found.get(eid)
            if row is None:
                continue
            old = row.get(field)
            if set_bid is not None:
                new = float(set_bid)
            elif old is None:
                skipped.append({"id": eid, "reason": f"no {field} (uses the ad group default)"})
                continue
            else:
                new = float(old) * (1 + float(change_pct or 0) / 100)
            new = max(min_bid, new)
            if max_bid is not None:
                new = min(max_bid, new)
            new = round(new, 2)
            if old is not None and round(float(old), 2) == new:
                skipped.append({"id": eid, "reason": "unchanged"})
                continue
            items.append({spec.id_field: eid, field: new})

        changes = safety.money_changes(
            items, current, id_field=spec.id_field, fields=(("bid", (field,)),)
        )
        decision = safety.assess(client.config, count=len(items), changes=changes)
        summary = {
            "entity": entity,
            "to_change": len(items),
            "not_found": missing[:50],
            "skipped": skipped[:50],
        }
        if not items:
            return {**summary, "message": "Nothing to change."}
        refused = safety.refusal(client.config, decision, confirm)
        if refused:
            return {**refused, **summary}
        sent = await _send_chunks(
            client,
            spec,
            items,
            profile_id=profile_id,
            before=current,
            op=f"sp_adjust_bids_{entity}",
            ctx=ctx,
        )
        return safety.annotate({**summary, **sent}, decision)

    @mcp.tool()
    async def amazon_ads_sp_set_states(
        entity: str,
        ids: list[str],
        state: str,
        profile_id: str | None = None,
        confirm: str = "",
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Pause or enable many Sponsored Products entities at once, with progress.

        entity: 'campaigns', 'ad_groups', 'product_ads', 'keywords' or 'targets'.
        state: 'PAUSED' or 'ENABLED' (to archive, use the matching archive tool).
        Enabling starts spend again. More than AMAZON_ADS_BULK_THRESHOLD items needs
        confirm='APPLY'. Current states are kept in the audit log.
        """
        if entity not in STATE_ENTITIES:
            raise ValueError(f"entity must be one of {', '.join(STATE_ENTITIES)}.")
        state = state.upper()
        if state not in {"PAUSED", "ENABLED"}:
            raise ValueError("state must be PAUSED or ENABLED.")
        id_list = ids_to_strings(ids)
        if not id_list:
            raise ValueError("Pass at least one ID.")
        if len(id_list) > 5000:
            raise ValueError("At most 5000 IDs per call.")
        spec = STATE_ENTITIES[entity]
        items = [{spec.id_field: eid, "state": state} for eid in id_list]
        decision = safety.assess(client.config, count=len(items))
        refused = safety.refusal(client.config, decision, confirm)
        if refused:
            return {**refused, "entity": entity, "state": state, "count": len(items)}
        before = await run_blocking(
            client.snapshot,
            list_style_fetch,
            client,
            spec,
            profile_id=profile_id,
            ids=id_list,
            max_results=len(id_list),
        )
        sent = await _send_chunks(
            client,
            spec,
            items,
            profile_id=profile_id,
            before=before[0] if before else None,
            op=f"sp_set_state_{entity}",
            ctx=ctx,
        )
        return safety.annotate({"entity": entity, "state": state, **sent}, decision)
