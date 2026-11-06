"""Profiles (one per advertiser per marketplace) and manager accounts."""

from __future__ import annotations

from typing import Any

from ..client import AmazonAdsClient

MANAGER_MEDIA = "application/vnd.getmanageraccountsresponse.v1+json"


def register(mcp, client: AmazonAdsClient) -> None:
    @mcp.tool()
    def amazon_ads_list_profiles(
        access_level: str | None = None,
        api_program: str | None = None,
        profile_type: str | None = None,
    ) -> dict[str, Any]:
        """List the advertising profiles this login can use in the configured region.

        Each profile is one advertiser in one marketplace (countryCode, currency,
        timezone, account type seller/vendor/agency). Pass its profileId as
        profile_id to other tools, or set AMAZON_ADS_PROFILE_ID as the default.
        access_level 'view' also includes profiles you can only view;
        profile_type filters by seller, vendor or agency.
        """
        params: dict[str, Any] = {}
        if access_level:
            params["accessLevel"] = access_level
        if api_program:
            params["apiProgram"] = api_program
        if profile_type:
            params["profileTypeFilter"] = profile_type
        profiles = client.request("GET", "/v2/profiles", params=params or None, scoped=False)
        profiles = profiles if isinstance(profiles, list) else []
        return {
            "region": client.config.region,
            "default_profile_id": client.config.profile_id,
            "count": len(profiles),
            "profiles": profiles,
        }

    @mcp.tool()
    def amazon_ads_get_profile(profile_id: str | None = None) -> dict[str, Any]:
        """Get one profile (defaults to AMAZON_ADS_PROFILE_ID)."""
        pid = client.resolve_profile(profile_id)
        return client.request("GET", f"/v2/profiles/{pid}", scoped=False)

    @mcp.tool()
    def amazon_ads_list_manager_accounts() -> dict[str, Any]:
        """List manager accounts this login belongs to, with their linked advertiser accounts.

        Useful for agencies: linked accounts include profile IDs for accounts
        where you only have viewer access (which the profiles list leaves out).
        """
        return client.request("GET", "/managerAccounts", scoped=False, accept=MANAGER_MEDIA)
