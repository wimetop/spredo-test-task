import asyncio

from app.config import Settings
from app.schemas import Funnel
from app.service import ProjectService


def coin(coin_id: str, volume: float) -> dict:
    return {
        "id": coin_id,
        "market_cap": 10_000_000,
        "fully_diluted_valuation": 20_000_000,
        "total_volume": volume,
        "max_supply": 1_000_000.0,
        "total_supply": 1_000_000.0,
    }


class FakeClient:
    """Two volume-sorted pages where "shifted" moved from page 1 to page 2 between requests."""

    def __init__(self) -> None:
        self.pages = {
            1: [coin("a", 5_000_000), coin("shifted", 1_000_000)],
            2: [coin("shifted", 900_000), coin("b", 10_000)],
        }

    async def markets_page(self, page: int, per_page: int = 250) -> list[dict]:
        return self.pages.get(page, [])


def test_stage_markets_dedupes_coins_across_pages(tmp_path):
    settings = Settings(coingecko_api_key="", cache_dir=tmp_path)
    service = ProjectService(FakeClient(), settings)  # type: ignore[arg-type]
    funnel = Funnel()

    candidates = asyncio.run(service._stage_markets(funnel))

    assert [c["id"] for c in candidates] == ["a", "shifted"]
    assert candidates[1]["total_volume"] == 1_000_000  # first occurrence kept
    assert funnel.markets_scanned == 3
    assert funnel.passed_market_filters == 2
