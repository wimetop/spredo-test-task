"""Pure filter functions for the six task criteria. No I/O here.

Rule for every criterion: a missing / null / non-numeric value means we can't verify it, so the coin fails.
"""

import math
from typing import Any

from app.config import FDV_MAX_USD, TVL_MIN_USD, VOLUME_MIN_USD

Coin = dict[str, Any]


def to_number(value: Any) -> float | None:
    """Return value as float, or None if it isn't a real number (bool is rejected explicitly)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


# --- Stage A: fields from /coins/markets ---

def has_positive_market_cap(coin: Coin) -> bool:
    mcap = to_number(coin.get("market_cap"))
    return mcap is not None and mcap > 0


def supply_matches(coin: Coin) -> bool:
    max_supply = to_number(coin.get("max_supply"))
    total_supply = to_number(coin.get("total_supply"))
    if max_supply is None or total_supply is None or max_supply <= 0 or total_supply <= 0:
        return False
    return math.isclose(max_supply, total_supply, rel_tol=1e-9)


def fdv_below(coin: Coin, max_usd: float = FDV_MAX_USD) -> bool:
    fdv = to_number(coin.get("fully_diluted_valuation"))
    return fdv is not None and fdv < max_usd


def volume_above(coin: Coin, min_usd: float = VOLUME_MIN_USD) -> bool:
    volume = to_number(coin.get("total_volume"))
    return volume is not None and volume > min_usd


def passes_market_filters(coin: Coin) -> bool:
    """Criteria 1, 3, 4, 5."""
    return (
        has_positive_market_cap(coin)
        and supply_matches(coin)
        and fdv_below(coin)
        and volume_above(coin)
    )


def should_stop_paging(page: list[Coin], min_usd: float = VOLUME_MIN_USD) -> bool:
    """Pages are sorted by volume desc: once the last coin fails the volume check, all later pages do too."""
    return not page or not volume_above(page[-1], min_usd)


# --- Stage B: fields from /coins/{id} ---

def extract_tvl_usd(market_data: dict[str, Any] | None) -> float | None:
    """TVL is `{"btc": x, "usd": y}` in practice; accept a plain number defensively."""
    if not market_data:
        return None
    tvl = market_data.get("total_value_locked")
    if isinstance(tvl, dict):
        return to_number(tvl.get("usd"))
    return to_number(tvl)


def passes_detail_filters(detail: Coin, tvl_min_usd: float = TVL_MIN_USD) -> bool:
    """Criteria 2 and 6."""
    if detail.get("preview_listing") is not True:
        return False
    tvl = extract_tvl_usd(detail.get("market_data"))
    return tvl is not None and tvl > tvl_min_usd
