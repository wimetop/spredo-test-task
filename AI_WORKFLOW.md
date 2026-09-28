# AI Workflow Log

Tool: Claude Code (Claude Opus 5.5), driven by `CLAUDE.md` as the spec / rules file.

## Phase 0 + 1 — Setup, API verification, backend

**What AI generated**
- Repo skeleton, `.gitignore`, `backend/.env.example`.
- Real CoinGecko calls (`/coins/markets` page 1, `/coins/uniswap`, a 14-request burst) to confirm field names,
  types and rate-limit behavior; results recorded in `CLAUDE.md` → "Verified API facts".
- FastAPI backend: `config.py`, `coingecko.py` (rate limiter + retries), `filters.py` (pure) + `tests/test_filters.py`,
  `service.py` (2-stage pipeline, caches, background refresh), `schemas.py`, `main.py`.

**Key decisions**
- Verified before coding: TVL is `{"btc", "usd"}`, `preview_listing` is a top-level bool, `max_supply` is often null,
  public 429 carries `Retry-After: 59` → the client honors it and pauses the shared limiter.
- Business thresholds are code constants (not env) so criteria can't be silently relaxed; null → fail.
- Stage A pages by `volume_desc` and stops at the first page whose last coin is ≤ $50k volume.
- Stage B detail cache stores only the two fields we need and persists to `backend/.cache/details.json`.
- Without an API key the config falls back to the public plan (10s interval) instead of failing with 401.
- A failing detail call for one coin is counted in `funnel.details_failed` rather than aborting the run.
- First real run showed 698 Stage B candidates (far more than assumed) → per-refresh detail cap +
  incremental coverage via the persisted cache, reported via `details_skipped`; public interval 6s → 10s.
- Live funnel is exposed during the first warm-up (found while manually polling: it showed 0s until the end).

**Verification run (public API, `MAX_DETAIL_REQUESTS=40` override, ~16 min):**
`markets_scanned 2750 → passed_market_filters 697 → details_checked 41 (skipped 656) → passed_all 0`.
Of the 40 fetched details: 16 have TVL > $50k, **0 have `preview_listing == true`** — criterion 2 is the bottleneck.
pytest: 11 passed.

**Manual review:** _(to be filled in by the human)_

## Setup + Phase 2 — Demo key run, spec update, frontend

**What AI generated**
- Checked `backend/.env` without printing the key; found and fixed a typo (`AX_DETAIL_REQUESTS` → `MAX_DETAIL_REQUESTS=700`),
  which would otherwise have silently fallen back to the default cap of 300.
- Started the backend (Demo plan, 2.1s interval) for a full warm-up of all ~700 candidates; no 429s observed.
- Updated `CLAUDE.md` with the Phase 1 changes (incremental coverage, 24h disk cache, 10s public interval,
  `details_failed` / `details_skipped`, `error` field, public-API fallback) and the extra frontend requirements.
- Frontend (Vite + React + TS, plain CSS): `api.ts`, `types.ts`, `App.tsx`, `Controls`, `ProjectsTable`,
  `FunnelSummary`, `utils/format.ts`, `/api` proxy, dev-only mock dataset (`?mock=1`).

**Key decisions**
- Search / max FDV / sort are client-side via `useMemo`, so changing controls makes no extra requests.
- Polling every 5s while `status === "warming"` or while a background refresh is running. After a manual
  Refresh it re-polls once after 1s, because the backend starts the refresh asynchronously.
- The coverage line ("Checked X of Y candidates") is always shown, and highlighted when `details_skipped > 0`.
- Empty state and error state both render the funnel, so the user sees why the result is 0.
- Mock data uses fictional project names (no real coins with fake numbers). The `import.meta.env.DEV` guard
  removes the mock branch and its JSON chunk from the production build (verified in the `vite build` output).
- Max FDV is entered in USD with a live compact hint (e.g. "≤ $50M").

**Verification:** `npm run build` passes. Checked in Chrome: the warming view with live funnel works against the
real backend, and search "ETH" (2/10), max FDV 50M (7/10) and 24h volume ↑ sort work together in `?mock=1`.
No console errors.

**Manual review:** _(to be filled in by the human)_
