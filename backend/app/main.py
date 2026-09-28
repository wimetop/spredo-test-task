import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.coingecko import CoinGeckoClient
from app.config import get_settings
from app.schemas import Health, ProjectsResponse
from app.service import ProjectService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.coingecko_api_key:
        logger.warning("COINGECKO_API_KEY not set — using the public API (slow, strict rate limits)")
    logger.info("CoinGecko plan=%s interval=%.2fs", settings.effective_plan, settings.request_interval)

    client = CoinGeckoClient(settings)
    service = ProjectService(client, settings)
    app.state.service = service
    service.trigger_refresh()  # background warm-up; startup doesn't wait for it
    try:
        yield
    finally:
        await service.aclose()
        await client.aclose()


app = FastAPI(title="Spredo CoinGecko Screener", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=Health)
async def health() -> Health:
    return Health()


@app.get("/api/projects", response_model=ProjectsResponse)
async def projects(request: Request, refresh: bool = False) -> ProjectsResponse:
    service: ProjectService = request.app.state.service
    if refresh or service.is_expired():
        service.trigger_refresh()
    return service.snapshot()
