# AI Workflow Log

Tools: Claude chat (task analysis, writing `CLAUDE.md`) + Claude Code (Claude Opus 5.5) for implementation.
`CLAUDE.md` is the spec / rules file. Work ran phase by phase, and each phase ended with a report and a human review stop.

## Phase summary

| Phase | Result |
|---|---|
| Pre-work | `CLAUDE.md` written together with Claude chat: spec, architecture, 90-min time plan, working rules |
| 0 | Repo skeleton; real CoinGecko calls verified field names, types and rate-limit behavior |
| 1 | FastAPI backend (2-stage pipeline, rate limiter, caches, background warm-up), 11 filter tests |
| Setup + 2 | Demo key + full warm-up running in parallel; React/Vite frontend with all states + mock mode |
| 3 | README, this log, push to a public GitHub repo |


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

**Manual review:**
- Wrote `CLAUDE.md` together with Claude chat before any coding (spec, architecture, time plan, rules).
- Reviewed the phase report before allowing the next phase.
- Caught that the session had been started in the wrong working directory (the VS Code install folder) and
  confirmed the repo lives in its own folder, `~/spredo-test-task`.
- Noticed the first run covered only 41 of 697 candidates, so I added a Demo API key and chose to run the full
  warm-up in parallel with the frontend work.

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

**Manual review:**
- Forbade backend restarts during the warm-up so the in-progress run and cache wouldn't be lost; all testing went
  through the running backend, never directly to CoinGecko.
- Required a mock mode so the filters can be demonstrated even with 0 real results.
- Tested the UI in the browser, both live (warming state) and with `?mock=1`.
- Reviewed the phase report before allowing Phase 3.

## Phase 3 — README, final log, publish

**What AI generated:** `README.md` (run instructions for PowerShell and macOS/Linux, API, checklist, architecture,
assumptions, mock mode, results snapshot, limitations), this summary, the commit and the GitHub push.

**Results at submission (2026-09-28 11:07 UTC):** 2,750 scanned → 698 candidates → 313 of 698 details checked →
0 passed all criteria. No checked coin had `preview_listing == true`. The warm-up was still running.

**Manual review:** Reviewed the README and the results section for honesty (0 results, partial coverage stated
explicitly) before submission.

## Submission form summary

**Tools.** Claude chat and Claude Code (Claude Opus 5.5).

**How I used them.** In Claude chat I analyzed the task and wrote `CLAUDE.md` together with it: spec, architecture
(two-stage pipeline, caching, background warm-up), a 90-minute time plan and working rules. Then Claude Code built
the project phase by phase (setup and API verification → backend → frontend → docs). Each phase ended with a short
report (done / how to verify / next / risks) and a stop, and I reviewed it before allowing the next one.

**Where they helped most.** Verifying the real CoinGecko API before coding (field shapes, the `Retry-After: 59` rate
limit), producing a clean backend with pure, unit-tested filters, and adapting the design when real data showed 698
candidates instead of a handful: incremental coverage via a persisted 24h detail cache and an honest funnel in the
API and UI. It also caught a typo in my `.env` (`AX_DETAIL_REQUESTS`) that would have silently lowered the cap.

**What I reviewed or corrected manually.** I caught that the session started in the wrong working directory. I
noticed the first run checked only 41 of 697 candidates, so I added a Demo key and ran the full warm-up in parallel
with the frontend work. I forbade backend restarts so the warm-up and cache wouldn't be lost, required a mock mode
so the filters can be demonstrated with 0 real results, tested the UI in the browser (live and `?mock=1`), and
checked that the README reports the 0-result outcome and partial coverage honestly.
