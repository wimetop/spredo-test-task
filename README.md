# Spredo Test Task — Crypto Project Screener

A small full-stack app that finds CoinGecko projects matching **all six** criteria: market cap > 0,
`preview_listing == true`, max supply == total supply, FDV < $100M, 24h volume > $50k and TVL > $50k.
A **FastAPI** backend fetches and filters the data (using the CoinGecko rate limits carefully), and a
**React + TypeScript** frontend lists the results with search, a max-FDV filter and sorting. The frontend talks
only to the backend; the API key never leaves the server.

## How to run

Requirements: Python 3.11+ and Node 20+.

**CoinGecko Demo key (free):** sign up at <https://www.coingecko.com/en/api/pricing>, choose the *Demo* plan and
create a key in the developer dashboard. Without a key the backend falls back to the public API, which works but is
very slow (~5 requests/min).

### Backend

macOS / Linux:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set COINGECKO_API_KEY=...
uvicorn app.main:app --port 8000
pytest -q                      # unit tests for the filters
```

Windows PowerShell:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env    # then set COINGECKO_API_KEY=...
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
.\.venv\Scripts\python.exe -m pytest -q
```

| `.env` variable | Default | Meaning |
|---|---|---|
| `COINGECKO_PLAN` | `demo` | `public` \| `demo` \| `pro` (falls back to `public` if the key is empty) |
| `COINGECKO_API_KEY` | – | your key; stays in `backend/.env` only |
| `CACHE_TTL_SECONDS` | `600` | how long the final result is served before a background refresh |
| `MAX_MARKET_PAGES` | `20` | safety cap for Stage A pages (the early stop usually ends at ~11) |
| `MAX_DETAIL_REQUESTS` | `300` (`700` in `.env.example`) | new detail calls per refresh (cached coins are free) |
| `MIN_REQUEST_INTERVAL_SECONDS` | per plan | override the rate limiter (public 10s, demo 2.1s, pro 0.15s) |

### Frontend

Same on every OS:
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api → http://localhost:8000)
npm run build      # type-check + production build
```

## API

`GET /api/health` → `{"status": "ok"}`

`GET /api/projects` (optional `?refresh=true` starts a background refresh). It never blocks: while the first run is in
progress it returns `status: "warming"` with progress and the funnel so far.

```json
{
  "status": "ready",
  "updated_at": "2026-09-28T11:30:00Z",
  "stale": false,
  "error": null,
  "progress": {"stage": "done", "done": 698, "total": 698},
  "funnel": {
    "markets_scanned": 2750, "passed_market_filters": 698,
    "details_checked": 698, "details_failed": 0, "details_skipped": 0, "passed_all": 0
  },
  "count": 0,
  "items": [
    {"id": "…", "name": "…", "symbol": "…", "image": "…", "current_price": 0.41, "market_cap": 38200000,
     "fdv": 41000000, "total_volume": 1900000, "tvl": 12400000, "total_supply": 1e8, "max_supply": 1e8,
     "coingecko_url": "https://www.coingecko.com/en/coins/…"}
  ]
}
```
`status` is `warming` | `ready` | `error`. `stale: true` means the latest refresh failed and the previous result is
served. Coverage is `details_checked` of `passed_market_filters`.

## What was completed

- [x] Backend REST endpoint returning coins that match all 6 criteria
- [x] Clean structure: config / API client / pure filters / service / schemas / routes
- [x] Unit tests for every criterion and the paging early stop (`pytest`: 11 passed)
- [x] Rate limiting, retries (`Retry-After`), result cache, persisted detail cache, background warm-up
- [x] Frontend: project list, max-FDV filter, partial case-insensitive search (name + symbol), sort by market cap / 24h volume (asc/desc)
- [x] Loading, warming (progress + polling), error (with retry), empty (with funnel), stale and coverage states
- [x] Dev-only mock mode for demoing the controls
- [x] README, setup instructions, documented assumptions, AI workflow log
- [ ] Docker / deployment (out of scope for the time box)

## Architecture & performance decisions

```
backend/app/  config.py  coingecko.py  filters.py  service.py  schemas.py  main.py
frontend/src/ api.ts  types.ts  App.tsx  components/{Controls,ProjectsTable,FunnelSummary}.tsx  utils/format.ts
```

- **Two-stage pipeline.** Stage A uses cheap bulk calls: `/coins/markets` (250 coins/page) applies criteria 1, 3, 4
  and 5. Stage B makes one expensive `/coins/{id}` call per Stage A survivor, only for `preview_listing` and TVL.
- **Volume-desc early stop.** Markets are requested sorted by `volume_desc`. As soon as a page's last coin has volume
  ≤ $50k, every later coin fails criterion 5, so paging stops (≈11 pages / 2,750 coins instead of ~72 pages / 17.8k).
- **Caching.** The final result is kept in memory for `CACHE_TTL_SECONDS`. Per-coin details (only the two fields we
  need) are cached for **24h** and persisted to `backend/.cache/details.json`, so restarts and refreshes don't spend
  the rate limit again.
- **Background warm-up.** A full run starts at startup (FastAPI lifespan). The endpoint returns the current state
  immediately; an `asyncio.Lock` ensures only one refresh runs, so concurrent requests never duplicate upstream calls.
- **Rate limiter + retries.** One shared `httpx.AsyncClient`, a minimum interval between requests per plan, and on
  429/5xx it honors `Retry-After` (observed: 59s) or uses exponential backoff, max 3 retries. One failing coin is
  counted in `details_failed` and doesn't abort the run.
- **Incremental coverage.** `MAX_DETAIL_REQUESTS` caps *new* detail calls per refresh; cached coins don't count. Coins
  beyond the cap are reported as `details_skipped` and checked on the next refresh. The UI shows
  "Checked X of Y candidates".
- **Client-side filtering.** The backend returns the full (small) filtered list; search, max FDV and sorting run in
  the browser with `useMemo`: instant, and no extra requests.

## Assumptions

- **Null handling:** a missing/`null` value for any criterion means it can't be verified, so the coin is **excluded**.
  `max_supply = null` means unlimited supply, which fails criterion 3.
- **Supply equality:** both values must be > 0 and are compared with `math.isclose(rel_tol=1e-9)` to tolerate float noise.
- **TVL:** `market_data.total_value_locked.usd` from `/coins/{id}` (the API returns `{"btc", "usd"}`); USD is used
  everywhere.
- **Criteria are never relaxed.** Thresholds are code constants, not env settings. An empty result is a valid answer.
- The frontend's max-FDV filter is inclusive (`fdv ≤ limit`), applied on top of the backend's `< $100M`.

## Mock mode

`http://localhost:5173/?mock=1` loads `frontend/src/mocks/sample.json` (10 **fictional** projects) and shows a
**MOCK DATA** badge. It exists because the real result can legitimately be empty, and reviewers should still be able
to try search, max FDV and sorting. It is dev-only: the `import.meta.env.DEV` guard removes it from production builds.

## Results (at submission time)

Snapshot from the running backend at **2026-09-28 11:07 UTC** (Demo plan, first full warm-up still in progress):

| Step | Count |
|---|---|
| Coins scanned (Stage A, 11 pages) | 2,750 |
| Passed market cap / supply / FDV / volume | 698 |
| Details checked so far | **313 of 698** |
| Passed all 6 criteria | **0** |

**None of the checked coins had `preview_listing == true`**, while many pass the TVL check (in an earlier sample of
40 coins, 16 had TVL > $50k). So the result was **0 at submission time**. The remaining candidates are still being
checked, and the funnel on the page shows the live numbers. Preview listings are rare and usually tiny, so 0 is a
plausible final answer.

## Limitations & what I'd do next

- Coins outside the volume-sorted market pages (or not in `/coins/markets` at all) can't be checked without one
  detail call per coin across ~17.8k coins, which isn't feasible on free rate limits.
- The first full warm-up takes a while on the Demo plan. Throughput was lower than the 2.1s interval suggests;
  I'd add request timing and 429/timeout metrics to see why.
- Prioritize Stage B: check `preview_listing` candidates first, e.g. via CoinGecko's newly-listed endpoints, instead
  of walking all 698 candidates.
- Stream partial results during warming, plus integration tests for the service with a mocked HTTP client.
- Docker Compose for one-command startup, and deployment.

## AI workflow

This was built with Claude (chat) + Claude Code, phase by phase with human review stops. See
[AI_WORKFLOW.md](AI_WORKFLOW.md).
