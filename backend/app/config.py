from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Business thresholds (task spec) — kept as constants, not env, so criteria can't be relaxed by accident.
FDV_MAX_USD = 100_000_000
VOLUME_MIN_USD = 50_000
TVL_MIN_USD = 50_000

Plan = Literal["public", "demo", "pro"]

_BASE_URLS: dict[str, str] = {
    "public": "https://api.coingecko.com/api/v3",
    "demo": "https://api.coingecko.com/api/v3",
    "pro": "https://pro-api.coingecko.com/api/v3",
}
_KEY_HEADERS: dict[str, str] = {"demo": "x-cg-demo-api-key", "pro": "x-cg-pro-api-key"}
_DEFAULT_INTERVALS: dict[str, float] = {"public": 10.0, "demo": 2.1, "pro": 0.15}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    coingecko_plan: Plan = "demo"
    coingecko_api_key: str = ""
    cache_ttl_seconds: int = 600
    detail_cache_ttl_seconds: int = 24 * 3600
    max_market_pages: int = 20
    max_detail_requests: int = 300
    min_request_interval_seconds: float | None = None
    request_timeout_seconds: float = 15.0
    cache_dir: Path = BACKEND_DIR / ".cache"

    @property
    def effective_plan(self) -> Plan:
        # Without a key, demo/pro would just fail with 401 — fall back to the public API.
        return self.coingecko_plan if self.coingecko_api_key else "public"

    @property
    def base_url(self) -> str:
        return _BASE_URLS[self.effective_plan]

    @property
    def auth_headers(self) -> dict[str, str]:
        header = _KEY_HEADERS.get(self.effective_plan)
        return {header: self.coingecko_api_key} if header else {}

    @property
    def request_interval(self) -> float:
        if self.min_request_interval_seconds is not None:
            return self.min_request_interval_seconds
        return _DEFAULT_INTERVALS[self.effective_plan]


@lru_cache
def get_settings() -> Settings:
    return Settings()
