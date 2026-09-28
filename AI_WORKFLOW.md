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
