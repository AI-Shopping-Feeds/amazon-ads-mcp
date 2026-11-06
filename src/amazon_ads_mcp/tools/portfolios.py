"""Portfolios: groups of campaigns that can share a budget cap."""

from __future__ import annotations

from ..client import AmazonAdsClient
from ._common import ListStyleEntity, register_list_style

PORTFOLIOS = ListStyleEntity(
    prefix="",
    noun="portfolios",
    label="portfolios",
    path="/portfolios",
    media_type="application/vnd.spPortfolio.v3+json",
    items_key="portfolios",
    id_field="portfolioId",
    id_filter="portfolioIdFilter",
    money=(("budget", ("budget", "amount")),),
    archive=False,
    default_states=("ENABLED",),
    create_example=(
        'Example: {"name": "Brand terms", "state": "ENABLED"}, optionally with a budget cap '
        '{"budget": {"amount": 500, "currencyCode": "GBP", "policy": "MONTHLY_RECURRING"}}.'
    ),
    update_example='Example: {"portfolioId": "123", "name": "Brand terms UK"}.',
)


def register(mcp, client: AmazonAdsClient) -> None:
    register_list_style(mcp, client, PORTFOLIOS)
