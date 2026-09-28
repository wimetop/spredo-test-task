"""Two-stage pipeline (bulk markets -> per-coin details), result cache and refresh orchestration."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app import filters
from app.coingecko import CoinGeckoClient
from app.config import Settings
from app.schemas import Funnel, Progress, Project, ProjectsResponse, Status

logger = logging.getLogger(__name__)

DETAIL_CACHE_FILE = "details.json"
DETAIL_CACHE_SAVE_EVERY = 10


def _to_project(coin: dict[str, Any], tvl: float) -> Project:
    return Project(
        id=coin["id"],
        name=coin["name"],
        symbol=coin["symbol"].upper(),
        image=coin.get("image"),
        current_price=filters.to_number(coin.get("current_price")),
        market_cap=coin["market_cap"],
        fdv=coin["fully_diluted_valuation"],
        total_volume=coin["total_volume"],
        tvl=tvl,
        total_supply=coin["total_supply"],
        max_supply=coin["max_supply"],
        coingecko_url=f"https://www.coingecko.com/en/coins/{coin['id']}",
    )


class DetailCache:
    """Per-coin cache of the only detail fields we need, persisted to disk to survive dev restarts."""

    def __init__(self, settings: Settings) -> None:
        self._ttl = settings.detail_cache_ttl_seconds
        self._path = settings.cache_dir / DETAIL_CACHE_FILE
        self._entries: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._entries), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not persist detail cache: %s", exc)

    def get(self, coin_id: str) -> dict[str, Any] | None:
        entry = self._entries.get(coin_id)
        if entry and time.time() - entry["fetched_at"] < self._ttl:
            return entry["detail"]
        return None

    def put(self, coin_id: str, detail: dict[str, Any]) -> None:
        # Keep only the fields the filters read, not the whole (large) payload.
        slim = {
            "preview_listing": detail.get("preview_listing"),
            "market_data": {
                "total_value_locked": (detail.get("market_data") or {}).get("total_value_locked")
            },
        }
        self._entries[coin_id] = {"fetched_at": time.time(), "detail": slim}


class ProjectService:
    def __init__(self, client: CoinGeckoClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._details = DetailCache(settings)
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

        self._status: Status = "warming"
        self._items: list[Project] = []
        self._updated_at: datetime | None = None
        self._refreshed_at_monotonic: float | None = None
        self._stale = False
        self._error: str | None = None
        self._progress = Progress()
        self._funnel = Funnel()

    # --- public API ---

    def snapshot(self) -> ProjectsResponse:
        return ProjectsResponse(
            status=self._status,
            updated_at=self._updated_at,
            stale=self._stale,
            error=self._error,
            progress=self._progress,
            funnel=self._funnel,
            count=len(self._items),
            items=self._items,
        )

    def is_expired(self) -> bool:
        if self._refreshed_at_monotonic is None:
            return True
        return time.monotonic() - self._refreshed_at_monotonic > self._settings.cache_ttl_seconds

    def trigger_refresh(self) -> None:
        """Start a background refresh unless one is already running. Never blocks the caller."""
        if self._lock.locked() or (self._task and not self._task.done()):
            return
        self._task = asyncio.create_task(self._refresh())

    async def aclose(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._details.save()

    # --- pipeline ---

    async def _refresh(self) -> None:
        async with self._lock:
            self._error = None
            funnel = Funnel()
            if not self._items:
                # Nothing to serve yet: expose the live funnel so the UI can show progress.
                self._status = "warming"
                self._funnel = funnel
            try:
                candidates = await self._stage_markets(funnel)
                items = await self._stage_details(candidates, funnel)
            except Exception as exc:  # noqa: BLE001 — any upstream failure must not kill the service
                logger.exception("Refresh failed")
                self._error = f"{type(exc).__name__}: {exc}"
                if self._items:
                    self._stale = True
                    self._status = "ready"
                else:
                    self._status = "error"
                return
            finally:
                self._details.save()

            items.sort(key=lambda p: p.market_cap, reverse=True)
            funnel.passed_all = len(items)
            self._items = items
            self._funnel = funnel
            self._updated_at = datetime.now(timezone.utc)
            self._refreshed_at_monotonic = time.monotonic()
            self._stale = False
            self._status = "ready"
            self._progress = Progress(stage="done", done=funnel.details_checked, total=funnel.details_checked)
            logger.info("Refresh done: %s", funnel.model_dump())

    async def _stage_markets(self, funnel: Funnel) -> list[dict[str, Any]]:
        """Stage A: bulk pages sorted by volume desc; stop once volume drops below the threshold."""
        max_pages = self._settings.max_market_pages
        candidates: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for page_no in range(1, max_pages + 1):
            self._progress = Progress(stage="markets", done=page_no - 1, total=max_pages)
            page = await self._client.markets_page(page_no)
            # Rankings shift while we page, so a coin can appear on two pages: keep the first occurrence.
            unique = [c for c in page if c["id"] not in seen_ids]
            seen_ids.update(c["id"] for c in unique)
            funnel.markets_scanned += len(unique)
            candidates.extend(c for c in unique if filters.passes_market_filters(c))
            if filters.should_stop_paging(page):
                break
        funnel.passed_market_filters = len(candidates)
        return candidates

    async def _stage_details(self, candidates: list[dict[str, Any]], funnel: Funnel) -> list[Project]:
        """Stage B: one detail call per surviving coin (cached), capped by MAX_DETAIL_REQUESTS."""
        items: list[Project] = []
        fetched = 0
        for index, coin in enumerate(candidates):
            self._progress = Progress(stage="details", done=index, total=len(candidates))
            detail = self._details.get(coin["id"])
            if detail is None:
                if fetched >= self._settings.max_detail_requests:
                    funnel.details_skipped += 1
                    continue
                fetched += 1
                try:
                    raw = await self._client.coin_detail(coin["id"])
                except Exception as exc:  # noqa: BLE001 — one bad coin shouldn't abort the run
                    logger.warning("Detail fetch failed for %s: %s", coin["id"], exc)
                    funnel.details_failed += 1
                    continue
                self._details.put(coin["id"], raw)
                detail = self._details.get(coin["id"])
                if fetched % DETAIL_CACHE_SAVE_EVERY == 0:
                    self._details.save()

            funnel.details_checked += 1
            if detail is not None and filters.passes_detail_filters(detail):
                tvl = filters.extract_tvl_usd(detail.get("market_data"))
                items.append(_to_project(coin, tvl or 0.0))
        return items
