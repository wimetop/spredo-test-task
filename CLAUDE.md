# CLAUDE.md — Spredo Test Task (Full Stack Dev Intern)

## 0. Context & mindset

This repo is a **time-boxed hiring test (90 minutes total, including README and submission)**.
Goal: a small, working, clearly documented full-stack app.

**A smaller finished solution beats an over-engineered unfinished one.** Optimize in this order:
1. Works end-to-end (backend → frontend)
2. Readable, well-structured code with clean FE/BE separation
3. Sensible API usage (rate limits, caching, minimal calls)
4. Clear README (how to run, what's done, assumptions, limitations, next steps)

Reviewers evaluate: functionality, code quality, prioritization, performance awareness,
FE/BE structure, AI tool usage, communication, delivery mindset.

---

## 1. Task spec

### Backend (Python)
Fetch crypto project data from the CoinGecko API and return projects matching **ALL** criteria:

| # | Criterion | Source endpoint | Field |
|---|-----------|-----------------|-------|
| 1 | Market cap > 0 | `/coins/markets` | `market_cap` |
| 2 | `preview_listing == true` | `/coins/{id}` | `preview_listing` |
| 3 | Max supply == total supply | `/coins/markets` | `max_supply`, `total_supply` |
| 4 | FDV < $100M | `/coins/markets` | `fully_diluted_valuation` |
| 5 | 24h volume > $50k | `/coins/markets` | `total_volume` |
| 6 | TVL > $50k | `/coins/{id}` | `market_data.total_value_locked` |

Requirements: REST endpoint returning the filtered list, clean structure, setup instructions, documented assumptions.

### Frontend (React)
Talks **only** to our backend (never to CoinGecko directly).
1. Display the list of projects
2. Extra FDV filter: user-defined max FDV
3. Search by project name, partial + case-insensitive (`eth` → Ethereum)
4. Sorting by market cap and by 24h volume (asc/desc)
5. Simple, clean, functional UI (perfect styling not required)

---

## 2. Tech stack (do not change without a strong reason)

- **Backend:** Python 3.11+, FastAPI, Uvicorn, httpx (async), pydantic v2 + pydantic-settings, pytest
- **Frontend:** React + TypeScript + Vite, plain CSS (no UI library, no Redux, no router)
- **Dev networking:** Vite dev-server proxy `/api` → `http://localhost:8000` (plus CORS middleware on backend for safety)

Out of scope (do NOT add): database, auth, Docker (only if everything else is done), state managers,
component libraries, SSR, WebSockets.

---

## 3. Repository structure

```
/
├── CLAUDE.md
├── README.md
├── AI_WORKFLOW.md            # running log for the submission form
├── .gitignore
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, CORS, lifespan (cache warm-up), routes
│   │   ├── config.py         # Settings from env (pydantic-settings)
│   │   ├── coingecko.py      # HTTP client: base URL/header by plan, rate limiter, retries
│   │   ├── filters.py        # PURE filter functions (no I/O) — unit tested
│   │   ├── service.py        # 2-stage pipeline, caching, refresh orchestration
│   │   └── schemas.py        # Pydantic response models
│   ├── tests/
│   │   └── test_filters.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api.ts            # fetch wrapper for /api/projects
    │   ├── types.ts          # mirrors backend schema
    │   ├── App.tsx           # state, data loading, derived list
    │   ├── components/
    │   │   ├── Controls.tsx      # search, max FDV, sort
    │   │   └── ProjectsTable.tsx
    │   └── utils/format.ts   # USD compact formatting
    ├── vite.config.ts        # /api proxy
    └── package.json
```

---

## 4. CoinGecko API — facts & strategy

### Plans / auth (verify in Phase 0)
- **Public (no key)** and **Demo** (free key): base `https://api.coingecko.com/api/v3`, header `x-cg-demo-api-key`.
  Demo ≈ 30 calls/min; public (no key) is lower and less stable.
- **Pro:** base `https://pro-api.coingecko.com/api/v3`, header `x-cg-pro-api-key`.
- Select plan via `COINGECKO_PLAN=public|demo|pro`. API key lives ONLY in `backend/.env`.
- **Public-API fallback:** if `COINGECKO_API_KEY` is empty, the effective plan is `public` regardless of
  `COINGECKO_PLAN` (demo/pro without a key would only return 401). A warning is logged at startup.

### Verified API facts
> Verified 2026-09-28 with real requests (public, no key).
- [x] `/coins/markets` returns a JSON **list** of flat objects. Fields: `id`, `symbol`, `name`, `image`, `current_price`,
  `market_cap` (int, occasionally float), `fully_diluted_valuation` (int, may be null), `total_volume` (int),
  `max_supply` (float or **null** — 87/250 on page 1), `total_supply` (float), `circulating_supply`. Response headers
  include `total: 17841` (coins in universe) and `per-page: 250`. With `order=volume_desc` page 1 ends at ~$10M volume.
- [x] `/coins/{id}` → `preview_listing` is a **top-level boolean** (`false` for uniswap).
- [x] `/coins/{id}` → `market_data.total_value_locked` is an **object `{"btc": number, "usd": number}`**
  (uniswap: usd ≈ 3.9e9); null for coins without TVL. Filter still accepts number/null defensively.
- [x] Rate limits (public, no key): a burst of 14 requests → 3× 200 then `429 Too Many Requests` with
  **`Retry-After: 59`** header. No x-ratelimit-* headers. → honor Retry-After; keep a steady min interval.
- [x] First full Stage A run (public): volume drops to ≤ $50k at **page 11** (~2.7k coins scanned);
  **698 coins pass criteria 1/3/4/5**. Sustained public throughput ≈ 4–6 req/min (429 every ~6 requests at a 6s
  interval) → public interval raised to 10s. Implication: a full Stage B pass is ~25 min on Demo and hours on
  public, so `MAX_DETAIL_REQUESTS` caps new detail calls per refresh; the persisted detail cache makes coverage
  grow across refreshes, and `funnel.details_skipped` reports what was not yet checked.

### Two-stage pipeline (the core performance idea)
Stage B (per-coin detail calls) is expensive, so shrink the candidate set with cheap bulk calls first.

**Stage A — bulk, cheap:** `GET /coins/markets?vs_currency=usd&order=volume_desc&per_page=250&page=N`
- Sorted by **volume desc** → stop paging as soon as a page's last coin has `total_volume <= 50_000`
  (all following coins fail criterion 5). Also stop at `MAX_MARKET_PAGES` or on an empty page.
- Apply criteria 1, 3, 4, 5 here.

**Stage B — per coin, expensive:** for Stage A survivors only
`GET /coins/{id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false`
- Apply criteria 2 and 6.
- Go through the shared rate limiter.
- **Incremental coverage:** `MAX_DETAIL_REQUESTS` caps *new upstream* detail calls per refresh; coins already in the
  detail cache don't count toward the cap. Candidates beyond the cap are counted in `funnel.details_skipped`, and the
  next refresh continues where the previous one stopped. Set `MAX_DETAIL_REQUESTS=700` to cover all ~700 candidates
  in one run (~25 min on Demo).
- **Per-coin detail cache, 24h TTL** (`DETAIL_CACHE_TTL_SECONDS`, default 86400), persisted to
  `backend/.cache/details.json` (saved every 10 fetches and on shutdown). Only `preview_listing` and
  `market_data.total_value_locked` are stored. Restarts don't burn the rate limit.
- A detail call that still fails after retries is counted in `funnel.details_failed` (that coin is excluded) and does
  not abort the run.

**Caching / serving**
- Final result cached in memory with `CACHE_TTL_SECONDS` (default 600).
- Warm-up starts in the background on app startup (FastAPI lifespan). A full run can take minutes on the
  Demo plan, so the endpoint must **never block for minutes**: it returns current state with a `status`
  (`warming` | `ready` | `error`) and progress.
- Only one refresh at a time (`asyncio.Lock`); concurrent requests never trigger duplicate upstream calls.
- If a refresh fails but old data exists → serve it with `stale: true`, plus `error`. With no old data → `status: "error"`.
- During the first warm-up the live funnel is exposed, so the UI can show progress. Later refreshes keep serving
  the previous result (status stays `ready`) until the new one is complete.
- `error` (string | null) holds the last refresh failure message.

**HTTP client rules**
- Single shared `httpx.AsyncClient`, timeout ~15s.
- Simple async rate limiter: minimum interval between requests, derived from plan
  (public **10s**, raised from 6s after observed 429s; demo 2.1s; pro 0.15s), overridable via env.
- On 429/5xx: honor `Retry-After` if present, else exponential backoff; max 3 retries.

### Filter semantics (implement in `filters.py`, cover with tests)
- Missing/`null` value for any criterion → coin **fails** that criterion (can't verify = exclude).
- `max_supply == total_supply`: both non-null and > 0, compared with `math.isclose(rel_tol=1e-9)`.
  `max_supply = null` means unlimited supply → fails.
- TVL: accept object `{"usd": x}`, a plain number, or null (null → fail). Use USD.
- Thresholds are constants in config (`FDV_MAX_USD=100_000_000`, `VOLUME_MIN_USD=50_000`, `TVL_MIN_USD=50_000`).
- **Never silently relax criteria.** An empty result is a valid result; explain it via the funnel stats.

### Known limitation to document
Coins that never appear in `/coins/markets` (or rank outside the scanned pages) can't be checked without
one detail call per coin across the whole ~15k+ list, which is infeasible on free rate limits. The
combination `preview_listing == true` + TVL > $50k may legitimately return very few or zero coins.

---

## 5. Backend API contract

`GET /api/health` → `{"status": "ok"}`

`GET /api/projects` (optional `?refresh=true` to force a background refresh)
```json
{
  "status": "ready",
  "updated_at": "2026-09-28T12:00:00Z",
  "stale": false,
  "error": null,
  "progress": {"stage": "details", "done": 120, "total": 240},
  "funnel": {
    "markets_scanned": 3500,
    "passed_market_filters": 240,
    "details_checked": 240,
    "details_failed": 0,
    "details_skipped": 0,
    "passed_all": 12
  },
  "count": 12,
  "items": [
    {
      "id": "string", "name": "string", "symbol": "string", "image": "url",
      "current_price": 0.0, "market_cap": 0.0, "fdv": 0.0, "total_volume": 0.0,
      "tvl": 0.0, "total_supply": 0.0, "max_supply": 0.0,
      "coingecko_url": "https://www.coingecko.com/en/coins/<id>"
    }
  ]
}
```
`progress.stage` is one of `idle | markets | details | done`. Coverage = `details_checked` of `passed_market_filters`;
when `details_skipped > 0` the result is incomplete and the UI must say so.

Backend returns the full filtered list; search / max-FDV / sort are done **client-side** (the list is small,
interactions are instant, and it avoids extra round trips). Mention this decision in the README.

---

## 6. Frontend spec

- Load `/api/projects` on mount. While `status === "warming"`: show progress and poll every 5s.
- States: loading, error (with retry button), empty (show funnel numbers so the user understands why),
  data, stale warning.
- Controls: search input (name, partial, case-insensitive; also match symbol), max FDV number input
  (empty = no limit), sort select: Market cap ↓/↑, 24h Volume ↓/↑. Show "N of M projects".
- Derived list via `useMemo` (filter → sort). No extra requests on control changes.
- Table columns: #, logo + name + symbol, price, market cap, FDV, 24h volume, TVL (compact USD, e.g. `$12.3M`).
- "Last updated" timestamp + Refresh button.
- Keep CSS minimal and readable; responsive enough that the table scrolls horizontally on small screens.
- Coverage: when `details_skipped > 0` show "Checked X of Y candidates" (result is incomplete).
- Show the response's `error` field when present (error state, or alongside stale data).
- Dev-only mock data: `src/mocks/sample.json` (~10 items), off by default, enabled with `?mock=1`, with a visible
  "MOCK DATA" badge, so search / max FDV / sort can be demoed when the real result is empty.

---

## 7. Commands

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # add COINGECKO_API_KEY
uvicorn app.main:app --reload --port 8000
pytest -q

# Frontend
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

`.env.example` keys: `COINGECKO_PLAN`, `COINGECKO_API_KEY`, `CACHE_TTL_SECONDS`, `MAX_MARKET_PAGES`,
`MAX_DETAIL_REQUESTS`, `MIN_REQUEST_INTERVAL_SECONDS` (optional override).

---

## 8. Time plan (90 min) & priorities

| Phase | Minutes | Content |
|-------|---------|---------|
| 0 | 0–8 | git init, `.gitignore`, folders; real API calls to verify fields → fill "Verified API facts" |
| 1 | 8–40 | Backend: config, client, filters + tests, service, routes; manual run & check funnel |
| 2 | 40–68 | Frontend: scaffold, api/types, table, controls, states |
| 3 | 68–80 | README, AI_WORKFLOW.md, end-to-end check from a clean start |
| 4 | 80–90 | Buffer, final commit, push, submit form |

**P0 (must):** everything in sections 1, 5, 6 + README.
**P1 (if time):** disk cache for details, a few more tests, `?refresh=true`.
**P2 (skip unless done early):** Docker/compose, pagination, deployment.

If running behind schedule: cut P1/P2, simplify UI, and write "What I'd do next" in the README instead.

---

## 9. Working rules for Claude

- **Verify, don't guess:** make real API calls before relying on field names or response shapes.
- Keep business logic in pure functions (`filters.py`); I/O stays in `coingecko.py` / `service.py`.
- Type hints everywhere in Python; TypeScript types mirror backend schemas.
- Never expose the API key to the frontend; never commit `.env`, `.venv`, `node_modules`, `.cache`.
- Small focused commits after each phase, conventional messages (`feat(backend): …`, `docs: …`).
- After each phase, report briefly: **done / how to verify / next / risks**, with elapsed-time estimate.
- Append a short entry to `AI_WORKFLOW.md` after each phase: what AI generated, key decisions,
  and a `Manual review:` line left for the human to fill in.
- Ask the user only when truly blocked (e.g. missing API key, repeated 429s).
- Prefer the simplest thing that works; no speculative abstractions.

---

## 10. README must contain

1. Project overview (1 paragraph)
2. How to run (backend + frontend, env vars, getting a free CoinGecko Demo key)
3. API endpoint(s) with example response
4. What was completed (checklist vs. requirements)
5. Architecture & performance decisions (2-stage pipeline, volume-desc early stop, caching,
   background warm-up, rate limiter, client-side filtering)
6. Assumptions (null handling, supply equality tolerance, TVL source, USD everywhere)
7. Limitations & "What I'd do next"
8. AI workflow summary (link to AI_WORKFLOW.md)

## 11. Definition of done

- [ ] `pytest` passes
- [ ] Backend starts from a clean clone following README only
- [ ] `/api/projects` returns valid JSON with funnel stats (warming → ready)
- [ ] Frontend shows data; search, max FDV and both sorts work together
- [ ] Loading / error / empty states handled
- [ ] No secrets in repo; README complete; pushed to a **public** GitHub repo
