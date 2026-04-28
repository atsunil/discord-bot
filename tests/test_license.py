from __future__ import annotations

import pytest

from bot.license import LicenseManager


@pytest.mark.asyncio
async def test_free_tier_blocks_moderation():
    async def fetcher(_: str):
        return False, "free"

    manager = LicenseManager(fetcher=fetcher, ttl_seconds=300)
    assert await manager.is_feature_allowed("1", "moderation") is False


@pytest.mark.asyncio
async def test_pro_tier_allows_moderation():
    async def fetcher(_: str):
        return True, "pro"

    manager = LicenseManager(fetcher=fetcher, ttl_seconds=300)
    assert await manager.is_feature_allowed("1", "moderation") is True


@pytest.mark.asyncio
async def test_premium_tier_allows_agents():
    async def fetcher(_: str):
        return True, "premium"

    manager = LicenseManager(fetcher=fetcher, ttl_seconds=300)
    assert await manager.is_feature_allowed("1", "agents") is True


@pytest.mark.asyncio
async def test_cache_keeps_first_result():
    calls = 0

    async def fetcher(_: str):
        nonlocal calls
        calls += 1
        return True, "pro"

    manager = LicenseManager(fetcher=fetcher, ttl_seconds=300)
    assert await manager.get_plan_tier("1") == "pro"
    assert await manager.get_plan_tier("1") == "pro"
    assert calls == 1
