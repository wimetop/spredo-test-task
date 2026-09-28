from app.filters import (
    extract_tvl_usd,
    fdv_below,
    has_positive_market_cap,
    passes_detail_filters,
    passes_market_filters,
    should_stop_paging,
    supply_matches,
    volume_above,
)


def market_coin(**overrides):
    coin = {
        "id": "x",
        "market_cap": 10_000_000,
        "fully_diluted_valuation": 20_000_000,
        "total_volume": 100_000,
        "max_supply": 1_000_000.0,
        "total_supply": 1_000_000.0,
    }
    coin.update(overrides)
    return coin


def detail_coin(preview=True, tvl=None):
    return {
        "preview_listing": preview,
        "market_data": {"total_value_locked": {"btc": 1, "usd": 100_000} if tvl is None else tvl},
    }


# --- criterion 1: market cap > 0 ---
def test_market_cap_positive():
    assert has_positive_market_cap(market_coin())
    assert not has_positive_market_cap(market_coin(market_cap=0))
    assert not has_positive_market_cap(market_coin(market_cap=None))
    assert not has_positive_market_cap(market_coin(market_cap=-5))


# --- criterion 3: max supply == total supply ---
def test_supply_equal():
    assert supply_matches(market_coin())


def test_supply_float_noise_tolerated():
    assert supply_matches(market_coin(max_supply=1e9, total_supply=1e9 * (1 + 1e-12)))


def test_supply_mismatch_or_unlimited_fails():
    assert not supply_matches(market_coin(total_supply=999_999.0))
    assert not supply_matches(market_coin(max_supply=None))
    assert not supply_matches(market_coin(max_supply=0, total_supply=0))


# --- criterion 4: FDV < 100M ---
def test_fdv_threshold():
    assert fdv_below(market_coin(fully_diluted_valuation=99_999_999))
    assert not fdv_below(market_coin(fully_diluted_valuation=100_000_000))
    assert not fdv_below(market_coin(fully_diluted_valuation=None))


# --- criterion 5: 24h volume > 50k ---
def test_volume_threshold():
    assert volume_above(market_coin(total_volume=50_001))
    assert not volume_above(market_coin(total_volume=50_000))
    assert not volume_above(market_coin(total_volume=None))


def test_passes_market_filters_combined():
    assert passes_market_filters(market_coin())
    assert not passes_market_filters(market_coin(total_volume=10))


# --- criterion 2 + 6: detail filters ---
def test_extract_tvl_shapes():
    assert extract_tvl_usd({"total_value_locked": {"btc": 1, "usd": 123.0}}) == 123.0
    assert extract_tvl_usd({"total_value_locked": 456}) == 456.0
    assert extract_tvl_usd({"total_value_locked": None}) is None
    assert extract_tvl_usd({}) is None
    assert extract_tvl_usd(None) is None


def test_detail_filters():
    assert passes_detail_filters(detail_coin())
    assert not passes_detail_filters(detail_coin(preview=False))
    assert not passes_detail_filters({"market_data": {"total_value_locked": {"usd": 1e9}}})
    assert not passes_detail_filters(detail_coin(tvl={"usd": 50_000}))
    assert not passes_detail_filters(detail_coin(tvl={"usd": None}))


def test_bool_is_not_a_number():
    assert not has_positive_market_cap(market_coin(market_cap=True))


# --- paging early stop ---
def test_should_stop_paging():
    assert should_stop_paging([])
    assert should_stop_paging([market_coin(total_volume=1e6), market_coin(total_volume=50_000)])
    assert not should_stop_paging([market_coin(total_volume=1e6), market_coin(total_volume=60_000)])
