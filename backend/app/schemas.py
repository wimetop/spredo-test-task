from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Status = Literal["warming", "ready", "error"]
Stage = Literal["idle", "markets", "details", "done"]


class Project(BaseModel):
    id: str
    name: str
    symbol: str
    image: str | None
    current_price: float | None
    market_cap: float
    fdv: float
    total_volume: float
    tvl: float
    total_supply: float
    max_supply: float
    coingecko_url: str


class Progress(BaseModel):
    stage: Stage = "idle"
    done: int = 0
    total: int = 0


class Funnel(BaseModel):
    markets_scanned: int = 0
    passed_market_filters: int = 0
    details_checked: int = 0
    details_failed: int = 0
    details_skipped: int = 0
    passed_all: int = 0


class ProjectsResponse(BaseModel):
    status: Status
    updated_at: datetime | None
    stale: bool
    error: str | None = None
    progress: Progress
    funnel: Funnel
    count: int
    items: list[Project]


class Health(BaseModel):
    status: Literal["ok"] = "ok"
