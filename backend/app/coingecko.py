"""Thin async CoinGecko client: plan-based base URL/auth, a shared rate limiter and retries."""

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 65.0
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class RateLimiter:
    """Guarantees a minimum interval between consecutive requests (shared by all callers)."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._next_allowed - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_allowed = time.monotonic() + self._min_interval

    def pause(self, seconds: float) -> None:
        """Push back the next allowed request, e.g. after a 429 with Retry-After."""
        self._next_allowed = max(self._next_allowed, time.monotonic() + seconds)


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return min(float(retry_after) + 1, MAX_BACKOFF_SECONDS)
    return min(2.0 ** (attempt + 1), MAX_BACKOFF_SECONDS)


class CoinGeckoClient:
    def __init__(self, settings: Settings) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.base_url,
            headers={"accept": "application/json", **settings.auth_headers},
            timeout=settings.request_timeout_seconds,
        )
        self._limiter = RateLimiter(settings.request_interval)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        for attempt in range(MAX_RETRIES + 1):
            await self._limiter.wait()
            response: httpx.Response | None = None
            try:
                response = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == MAX_RETRIES:
                    raise
                logger.warning("GET %s transport error (%s), retrying", path, exc)
            else:
                if response.status_code not in RETRYABLE_STATUSES:
                    response.raise_for_status()
                    return response.json()
                if attempt == MAX_RETRIES:
                    response.raise_for_status()
                logger.warning("GET %s -> %s, retrying", path, response.status_code)
            delay = _retry_delay(response, attempt)
            self._limiter.pause(delay)
        raise RuntimeError("unreachable")

    async def markets_page(self, page: int, per_page: int = 250) -> list[dict[str, Any]]:
        return await self._get(
            "/coins/markets",
            {"vs_currency": "usd", "order": "volume_desc", "per_page": per_page, "page": page},
        )

    async def coin_detail(self, coin_id: str) -> dict[str, Any]:
        return await self._get(
            f"/coins/{coin_id}",
            {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
        )
