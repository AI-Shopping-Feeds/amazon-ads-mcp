"""Shared building blocks for the entity tool modules.

Two API styles cover most entities:

* "list-style" (Sponsored Products v3, Sponsored Brands v4, portfolios): POST
  `<path>/list` with `*Filter` objects and nextToken paging, POST to create,
  PUT to update, POST `<path>/delete` to archive, all with a versioned media type.
* "REST-style" (Sponsored Display, Sponsored Brands keywords): GET with
  comma-separated query filters and startIndex/count paging, POST to create,
  PUT to update and DELETE `<path>/<id>` to archive, one entity at a time.

`register_list_style()` and `register_rest_style()` generate list, create,
update and archive tools for one entity from a small spec, with the same
safety guards, before-snapshots and audit trail for every entity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from mcp.server.mcpserver import Context

from .. import safety
from ..client import AmazonAdsClient
from ._progress import report, run_blocking

MAX_BATCH = 1000
# How many entities to scan when an endpoint can't filter by ID.
ID_SCAN_LIMIT = 5000
ALL_STATES = "ALL"


def ids_to_strings(ids: Sequence[Any] | None) -> list[str]:
    return [str(i).strip() for i in (ids or []) if str(i).strip()]


def include(ids: Sequence[Any]) -> dict[str, list[str]]:
    return {"include": ids_to_strings(ids)}


def check_items(items: list[dict[str, Any]], what: str, max_items: int = MAX_BATCH) -> None:
    if not items:
        raise ValueError(f"Pass at least one {what}.")
    if len(items) > max_items:
        raise ValueError(f"At most {max_items} {what} per call; got {len(items)}.")
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{what}[{i}] must be an object.")


def require_ids(items: list[dict[str, Any]], id_field: str) -> list[str]:
    missing = [i for i, it in enumerate(items) if not it.get(id_field)]
    if missing:
        raise ValueError(f"Every item needs {id_field}; missing at index {missing[:10]}.")
    return [str(it[id_field]) for it in items]


def state_values(states: list[str] | None, default: Sequence[str], upper: bool) -> list[str] | None:
    """Normalise a state filter. None -> default; ['ALL'] -> no filter."""
    chosen = list(states) if states else list(default)
    if any(s.upper() == ALL_STATES for s in chosen):
        return None
    return [s.upper() if upper else s.lower() for s in chosen]


@dataclass(frozen=True)
class ListStyleEntity:
    """One entity on a list-style endpoint family."""

    prefix: str  # tool prefix after amazon_ads_, e.g. "sp"
    noun: str  # plural noun used in tool names, e.g. "keywords"
    label: str  # human label, e.g. "Sponsored Products keywords"
    path: str  # e.g. "/sp/keywords"
    media_type: str
    items_key: str  # key for create/update bodies and list/mutation responses
    id_field: str
    id_filter: str  # filter key used by list and delete, e.g. "keywordIdFilter"
    filters: dict[str, str] = field(default_factory=dict)  # tool arg -> filter key
    money: tuple[tuple[str, tuple[str, ...]], ...] = ()
    create: bool = True
    update: bool = True
    archive: bool = True
    create_example: str = ""
    update_example: str = ""
    default_states: tuple[str, ...] = ("ENABLED", "PAUSED")
    extended_data: bool = True


def list_style_fetch(
    client: AmazonAdsClient,
    spec: ListStyleEntity,
    *,
    profile_id: str | None,
    ids: list[str] | None = None,
    filters: dict[str, list[str] | None] | None = None,
    states: list[str] | None = None,
    extra_filters: dict[str, Any] | None = None,
    max_results: int = 200,
    all_states_for_ids: bool = True,
) -> tuple[list[Any], bool]:
    body: dict[str, Any] = {}
    for arg, values in (filters or {}).items():
        if not values:
            continue
        key = spec.filters.get(arg)
        if key is None:
            supported = ", ".join(sorted(spec.filters)) or "none"
            raise ValueError(f"{spec.label} can't be filtered by {arg} (supported: {supported}).")
        body[key] = include(values)
    if ids:
        body[spec.id_filter] = include(ids)
    # Looking entities up by ID should find them whatever their state.
    wanted = None if (ids and all_states_for_ids and not states) else states
    state_list = (
        state_values(wanted, spec.default_states, upper=True) if wanted or not ids else None
    )
    if state_list:
        body["stateFilter"] = {"include": state_list}
    if spec.extended_data:
        body["includeExtendedDataFields"] = True
    body.update(extra_filters or {})
    return client.paginate_token(
        f"{spec.path}/list",
        body,
        items_key=spec.items_key,
        content_type=spec.media_type,
        profile_id=profile_id,
        max_results=max_results,
    )


def register_list_style(mcp, client: AmazonAdsClient, spec: ListStyleEntity) -> None:
    base = "amazon_ads" + (f"_{spec.prefix}" if spec.prefix else "")
    opp = f"{spec.prefix}_" if spec.prefix else ""
    filter_args = ", ".join(sorted(spec.filters)) or "none"

    @mcp.tool(
        name=f"{base}_list_{spec.noun}",
        description=(
            f"List {spec.label}.\n\n"
            "Filters: ids (this entity's IDs), "
            f"plus {filter_args} where supported. states defaults to "
            f"{' and '.join(spec.default_states)}; "
            "pass ['ARCHIVED'] or ['ALL'] to widen it (IDs are found in any state). "
            "extra_filters is merged into the request body for other filters the API "
            "accepts (e.g. nameFilter). Returns at most max_results items."
        ),
    )
    def list_tool(
        profile_id: str | None = None,
        ids: list[str] | None = None,
        campaign_ids: list[str] | None = None,
        ad_group_ids: list[str] | None = None,
        portfolio_ids: list[str] | None = None,
        states: list[str] | None = None,
        extra_filters: dict[str, Any] | None = None,
        max_results: int = 200,
    ) -> dict[str, Any]:
        items, truncated = list_style_fetch(
            client,
            spec,
            profile_id=profile_id,
            ids=ids,
            filters={
                "campaign_ids": campaign_ids,
                "ad_group_ids": ad_group_ids,
                "portfolio_ids": portfolio_ids,
            },
            states=states,
            extra_filters=extra_filters,
            max_results=max_results,
        )
        return {spec.items_key: items, "count": len(items), "truncated": truncated}

    if spec.create:

        @mcp.tool(
            name=f"{base}_create_{spec.noun}",
            description=(
                f"Create {spec.label} (up to {MAX_BATCH} per call). Changes the live account.\n\n"
                f"items: one object per entity, sent as-is under '{spec.items_key}'. "
                f"{spec.create_example}\n"
                "Large batches and values over AMAZON_ADS_MAX_BUDGET/AMAZON_ADS_MAX_BID need "
                "confirm='APPLY'. Rehearse with dry-run first."
            ),
        )
        def create_tool(
            items: list[dict[str, Any]],
            profile_id: str | None = None,
            confirm: str = "",
        ) -> dict[str, Any]:
            check_items(items, "items")
            decision = safety.assess(
                client.config,
                count=len(items),
                changes=safety.new_values(items, spec.money),
                creating=True,
            )
            body = {spec.items_key: items}
            refused = safety.refusal(client.config, decision, confirm, preview=body)
            if refused:
                return refused
            out = client.request(
                "POST",
                spec.path,
                json_body=body,
                profile_id=profile_id,
                content_type=spec.media_type,
                op=f"{opp}create_{spec.noun}",
            )
            return safety.annotate(out, decision)

    if spec.update:

        @mcp.tool(
            name=f"{base}_update_{spec.noun}",
            description=(
                f"Update {spec.label} (up to {MAX_BATCH} per call). Changes the live account.\n\n"
                f"items: objects with {spec.id_field} plus only the fields to change. "
                f"{spec.update_example}\n"
                "Current values are read first and kept in the audit log. Bid or budget "
                "increases above AMAZON_ADS_MAX_INCREASE_PCT, and large batches, need "
                "confirm='APPLY'."
            ),
        )
        def update_tool(
            items: list[dict[str, Any]],
            profile_id: str | None = None,
            confirm: str = "",
        ) -> dict[str, Any]:
            check_items(items, "items")
            ids = require_ids(items, spec.id_field)
            before = client.snapshot(
                list_style_fetch,
                client,
                spec,
                profile_id=profile_id,
                ids=ids,
                max_results=len(ids),
            )
            current = before[0] if before else None
            decision = safety.assess(
                client.config,
                count=len(items),
                changes=safety.money_changes(
                    items, current, id_field=spec.id_field, fields=spec.money
                ),
            )
            body = {spec.items_key: items}
            refused = safety.refusal(client.config, decision, confirm, preview=body)
            if refused:
                return refused
            out = client.request(
                "PUT",
                spec.path,
                json_body=body,
                profile_id=profile_id,
                content_type=spec.media_type,
                op=f"{opp}update_{spec.noun}",
                before=current,
            )
            return safety.annotate(out, decision)

    if spec.archive:

        @mcp.tool(
            name=f"{base}_archive_{spec.noun}",
            description=(
                f"Archive {spec.label} by ID. Archived entities stop serving and can't be "
                "re-enabled, so this needs confirm='ARCHIVE' after the user agrees. "
                "To stop them temporarily, update their state to PAUSED instead."
            ),
        )
        def archive_tool(
            ids: list[str],
            profile_id: str | None = None,
            confirm: str = "",
        ) -> dict[str, Any]:
            id_list = ids_to_strings(ids)
            if not id_list:
                raise ValueError("Pass at least one ID.")
            if len(id_list) > MAX_BATCH:
                raise ValueError(f"At most {MAX_BATCH} IDs per call.")
            decision = safety.assess(client.config, count=len(id_list), destructive=safety.ARCHIVE)
            body = {spec.id_filter: include(id_list)}
            refused = safety.refusal(client.config, decision, confirm, preview=body)
            if refused:
                return refused
            before = client.snapshot(
                list_style_fetch,
                client,
                spec,
                profile_id=profile_id,
                ids=id_list,
                max_results=len(id_list),
            )
            out = client.request(
                "POST",
                f"{spec.path}/delete",
                json_body=body,
                profile_id=profile_id,
                content_type=spec.media_type,
                op=f"{opp}archive_{spec.noun}",
                before=before[0] if before else None,
            )
            return safety.annotate(out, decision)


@dataclass(frozen=True)
class RestStyleEntity:
    """One entity on a REST-style endpoint family."""

    prefix: str
    noun: str
    label: str
    path: str
    id_field: str
    id_filter: str | None  # query parameter, e.g. "campaignIdFilter"; None if unsupported
    filters: dict[str, str] = field(default_factory=dict)
    money: tuple[tuple[str, tuple[str, ...]], ...] = ()
    list_accept: str | None = None
    write_accept: str | None = None
    create: bool = True
    update: bool = True
    archive: bool = True
    create_example: str = ""
    update_example: str = ""
    default_states: tuple[str, ...] = ("enabled", "paused")
    upper_states: bool = False


def rest_style_fetch(
    client: AmazonAdsClient,
    spec: RestStyleEntity,
    *,
    profile_id: str | None,
    ids: list[str] | None = None,
    filters: dict[str, list[str] | None] | None = None,
    states: list[str] | None = None,
    extra_params: dict[str, Any] | None = None,
    max_results: int = 200,
) -> tuple[list[Any], bool]:
    params: dict[str, Any] = {}
    for arg, values in (filters or {}).items():
        if not values:
            continue
        key = spec.filters.get(arg)
        if key is None:
            supported = ", ".join(sorted(spec.filters)) or "none"
            raise ValueError(f"{spec.label} can't be filtered by {arg} (supported: {supported}).")
        params[key] = ",".join(ids_to_strings(values))
    wanted_ids = set(ids_to_strings(ids))
    if wanted_ids and spec.id_filter:
        params[spec.id_filter] = ",".join(sorted(wanted_ids))
    wanted = states if (states or not ids) else None
    state_list = (
        state_values(wanted, spec.default_states, upper=spec.upper_states)
        if (wanted or not ids)
        else None
    )
    if state_list:
        params["stateFilter"] = ", ".join(state_list)
    params.update(extra_params or {})
    if wanted_ids and not spec.id_filter:
        # No ID filter on this endpoint: page through and keep the wanted IDs.
        everything, _ = client.paginate_offset(
            spec.path,
            params,
            accept=spec.list_accept,
            profile_id=profile_id,
            max_results=ID_SCAN_LIMIT,
        )
        found = [e for e in everything if str(e.get(spec.id_field)) in wanted_ids]
        return found[:max_results], len(found) > max_results
    return client.paginate_offset(
        spec.path,
        params,
        accept=spec.list_accept,
        profile_id=profile_id,
        max_results=max_results,
    )


def register_rest_style(mcp, client: AmazonAdsClient, spec: RestStyleEntity) -> None:
    base = "amazon_ads" + (f"_{spec.prefix}" if spec.prefix else "")
    opp = f"{spec.prefix}_" if spec.prefix else ""
    filter_args = ", ".join(sorted(spec.filters)) or "none"
    default_states = " and ".join(spec.default_states)

    @mcp.tool(
        name=f"{base}_list_{spec.noun}",
        description=(
            f"List {spec.label}.\n\n"
            f"Filters: ids (this entity's IDs), plus {filter_args} where supported. "
            f"states defaults to {default_states}; pass ['archived'] or ['ALL'] to widen it. "
            "extra_params adds other query parameters the API accepts. Returns at most "
            "max_results items."
        ),
    )
    def list_tool(
        profile_id: str | None = None,
        ids: list[str] | None = None,
        campaign_ids: list[str] | None = None,
        ad_group_ids: list[str] | None = None,
        portfolio_ids: list[str] | None = None,
        states: list[str] | None = None,
        extra_params: dict[str, Any] | None = None,
        max_results: int = 200,
    ) -> dict[str, Any]:
        items, truncated = rest_style_fetch(
            client,
            spec,
            profile_id=profile_id,
            ids=ids,
            filters={
                "campaign_ids": campaign_ids,
                "ad_group_ids": ad_group_ids,
                "portfolio_ids": portfolio_ids,
            },
            states=states,
            extra_params=extra_params,
            max_results=max_results,
        )
        return {spec.noun: items, "count": len(items), "truncated": truncated}

    if spec.create:

        @mcp.tool(
            name=f"{base}_create_{spec.noun}",
            description=(
                f"Create {spec.label} (up to 100 per call). Changes the live account.\n\n"
                f"items: one object per entity, sent as a JSON array. {spec.create_example}\n"
                "Large batches and values over AMAZON_ADS_MAX_BUDGET/AMAZON_ADS_MAX_BID need "
                "confirm='APPLY'. Rehearse with dry-run first."
            ),
        )
        def create_tool(
            items: list[dict[str, Any]],
            profile_id: str | None = None,
            confirm: str = "",
        ) -> dict[str, Any]:
            check_items(items, "items", max_items=100)
            decision = safety.assess(
                client.config,
                count=len(items),
                changes=safety.new_values(items, spec.money),
                creating=True,
            )
            refused = safety.refusal(client.config, decision, confirm, preview=items)
            if refused:
                return refused
            out = client.request(
                "POST",
                spec.path,
                json_body=items,
                profile_id=profile_id,
                accept=spec.write_accept,
                op=f"{opp}create_{spec.noun}",
            )
            return safety.annotate(out, decision)

    if spec.update:

        @mcp.tool(
            name=f"{base}_update_{spec.noun}",
            description=(
                f"Update {spec.label} (up to 100 per call). Changes the live account.\n\n"
                f"items: objects with {spec.id_field} plus only the fields to change. "
                f"{spec.update_example}\n"
                "Current values are read first and kept in the audit log. Bid or budget "
                "increases above AMAZON_ADS_MAX_INCREASE_PCT, and large batches, need "
                "confirm='APPLY'."
            ),
        )
        def update_tool(
            items: list[dict[str, Any]],
            profile_id: str | None = None,
            confirm: str = "",
        ) -> dict[str, Any]:
            check_items(items, "items", max_items=100)
            ids = require_ids(items, spec.id_field)
            before = client.snapshot(
                rest_style_fetch,
                client,
                spec,
                profile_id=profile_id,
                ids=ids,
                max_results=len(ids),
            )
            current = before[0] if before else None
            decision = safety.assess(
                client.config,
                count=len(items),
                changes=safety.money_changes(
                    items, current, id_field=spec.id_field, fields=spec.money
                ),
            )
            refused = safety.refusal(client.config, decision, confirm, preview=items)
            if refused:
                return refused
            out = client.request(
                "PUT",
                spec.path,
                json_body=items,
                profile_id=profile_id,
                accept=spec.write_accept,
                op=f"{opp}update_{spec.noun}",
                before=current,
            )
            return safety.annotate(out, decision)

    if spec.archive:

        @mcp.tool(
            name=f"{base}_archive_{spec.noun}",
            description=(
                f"Archive {spec.label} by ID, one request per ID, with progress. Archived "
                "entities stop serving and can't be re-enabled, so this needs "
                "confirm='ARCHIVE' after the user agrees. To stop them temporarily, update "
                "their state to paused instead."
            ),
        )
        async def archive_tool(
            ids: list[str],
            profile_id: str | None = None,
            confirm: str = "",
            ctx: Context | None = None,
        ) -> dict[str, Any]:
            id_list = ids_to_strings(ids)
            if not id_list:
                raise ValueError("Pass at least one ID.")
            if len(id_list) > 100:
                raise ValueError("At most 100 IDs per call.")
            decision = safety.assess(client.config, count=len(id_list), destructive=safety.ARCHIVE)
            refused = safety.refusal(client.config, decision, confirm, preview={"ids": id_list})
            if refused:
                return refused
            before = await run_blocking(
                client.snapshot,
                rest_style_fetch,
                client,
                spec,
                profile_id=profile_id,
                ids=id_list,
                max_results=len(id_list),
            )
            by_id = {str(e.get(spec.id_field)): e for e in (before[0] if before else [])}
            results: list[Any] = []
            failed: list[dict[str, Any]] = []
            total = len(id_list)
            for done, eid in enumerate(id_list, start=1):
                try:
                    out = await run_blocking(
                        client.request,
                        "DELETE",
                        f"{spec.path}/{eid}",
                        profile_id=profile_id,
                        accept=spec.write_accept,
                        op=f"{opp}archive_{spec.noun}",
                        before=by_id.get(eid),
                    )
                    results.append(out)
                    await report(ctx, done, total, f"Archived {eid} ({done} of {total})")
                except Exception as e:
                    failed.append({"id": eid, "reason": str(e)[:300]})
                    await report(ctx, done, total, f"Failed {eid} ({done} of {total})")
            return safety.annotate(
                {
                    "archived_count": len(results),
                    "failed_count": len(failed),
                    "results": results,
                    "failed": failed[:20],
                },
                decision,
            )
