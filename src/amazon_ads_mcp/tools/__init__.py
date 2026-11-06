from . import (
    ads_api_v1,
    budget_rules,
    bulk,
    portfolios,
    profiles,
    reporting,
    request,
    sp_ads,
    sp_campaigns,
    sp_recommendations,
    sp_targeting,
    sponsored_brands,
    sponsored_display,
)

__all__ = [
    "ads_api_v1",
    "budget_rules",
    "bulk",
    "portfolios",
    "profiles",
    "reporting",
    "request",
    "sp_ads",
    "sp_campaigns",
    "sp_recommendations",
    "sp_targeting",
    "sponsored_brands",
    "sponsored_display",
]

# Tool groups (one per module) in registration order, which is also the order of
# tools/list. AMAZON_ADS_TOOL_GROUPS selects a subset by these names.
TOOL_GROUPS: tuple[str, ...] = (
    "profiles",
    "sp_campaigns",
    "sp_ads",
    "sp_targeting",
    "sp_recommendations",
    "bulk",
    "sponsored_brands",
    "sponsored_display",
    "reporting",
    "portfolios",
    "budget_rules",
    "ads_api_v1",
    "request",
)


def resolve_tool_groups(requested: list[str] | tuple[str, ...]) -> list[str]:
    """Validate group names and return them in registration order.

    An empty selection means every group. Raises RuntimeError naming the
    unknown groups and listing the valid ones.
    """
    if not requested:
        return list(TOOL_GROUPS)
    unknown = [g for g in requested if g not in TOOL_GROUPS]
    if unknown:
        raise RuntimeError(
            f"AMAZON_ADS_TOOL_GROUPS has unknown group(s): {', '.join(unknown)}.\n"
            f"Valid groups: {', '.join(sorted(TOOL_GROUPS))}"
        )
    wanted = set(requested)
    return [g for g in TOOL_GROUPS if g in wanted]
