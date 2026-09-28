import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchProjects, isMockMode } from './api'
import { Controls } from './components/Controls'
import { FunnelSummary } from './components/FunnelSummary'
import { ProjectsTable } from './components/ProjectsTable'
import type { Progress, Project, ProjectsResponse, SortKey } from './types'
import { formatDateTime, formatNumber } from './utils/format'

const POLL_INTERVAL_MS = 5000

const isRunning = (progress: Progress) => progress.stage === 'markets' || progress.stage === 'details'

function sortProjects(projects: Project[], sort: SortKey): Project[] {
  const field = sort.startsWith('market_cap') ? 'market_cap' : 'total_volume'
  const direction = sort.endsWith('desc') ? -1 : 1
  return [...projects].sort((a, b) => (a[field] - b[field]) * direction)
}

function progressLabel(progress: Progress): string {
  if (progress.stage === 'markets') return `Scanning market pages (page ${progress.done + 1}, up to ${progress.total})`
  if (progress.stage === 'details') {
    return `Checking coin details: ${formatNumber(progress.done)} of ${formatNumber(progress.total)}`
  }
  return 'Starting…'
}

export default function App() {
  const mock = isMockMode()
  const [data, setData] = useState<ProjectsResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const [search, setSearch] = useState('')
  const [maxFdv, setMaxFdv] = useState('')
  const [sort, setSort] = useState<SortKey>('market_cap_desc')

  // `loading` starts true; user-triggered reloads set it themselves (polling stays silent).
  const load = useCallback(async (refresh = false) => {
    try {
      setData(await fetchProjects(refresh))
      setLoadError(null)
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : String(error))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // Poll while the backend is warming up or refreshing in the background. Each new response re-arms the timer.
  const busy = data !== null && (data.status === 'warming' || isRunning(data.progress))
  useEffect(() => {
    if (!busy) return
    const timer = window.setTimeout(() => void load(), POLL_INTERVAL_MS)
    return () => window.clearTimeout(timer)
  }, [busy, data, load])

  const retry = () => {
    setLoading(true)
    void load()
  }

  const handleRefresh = () => {
    setLoading(true)
    // The backend starts the refresh in the background; re-poll shortly so the progress state kicks in.
    void load(true).then(() => window.setTimeout(() => void load(), 1000))
  }

  const items = useMemo(() => data?.items ?? [], [data])
  const visible = useMemo(() => {
    const query = search.trim().toLowerCase()
    const limit = maxFdv.trim() === '' ? null : Number(maxFdv)
    const filtered = items.filter(
      (p) =>
        (!query || p.name.toLowerCase().includes(query) || p.symbol.toLowerCase().includes(query)) &&
        (limit === null || !Number.isFinite(limit) || p.fdv <= limit),
    )
    return sortProjects(filtered, sort)
  }, [items, search, maxFdv, sort])

  const clearFilters = () => {
    setSearch('')
    setMaxFdv('')
  }

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>
            Crypto project screener {mock && <span className="badge badge-mock">MOCK DATA</span>}
          </h1>
          <p className="muted">
            CoinGecko projects with market cap &gt; 0, preview listing, max supply = total supply, FDV &lt; $100M,
            24h volume &gt; $50k and TVL &gt; $50k.
          </p>
        </div>
        <div className="header-actions">
          <span className="muted">Last updated: {formatDateTime(data?.updated_at ?? null)}</span>
          <button onClick={handleRefresh} disabled={loading || busy}>
            {busy ? 'Updating…' : 'Refresh'}
          </button>
        </div>
      </header>

      {loadError && data && (
        <div className="banner banner-error">
          Couldn't reach the backend ({loadError}). Showing the last loaded data.{' '}
          <button className="link" onClick={retry}>
            Retry
          </button>
        </div>
      )}
      {data?.error && (
        <div className="banner banner-error">
          Last update failed: <code>{data.error}</code>
        </div>
      )}
      {data?.stale && (
        <div className="banner banner-warning">
          Data may be outdated: the latest refresh failed, showing the previous result.
        </div>
      )}

      <main>{renderBody()}</main>
    </div>
  )

  function renderBody() {
    if (!data) {
      if (loadError) {
        return (
          <div className="panel">
            <h2>Could not load projects</h2>
            <p>{loadError}</p>
            <p className="muted">Is the backend running on port 8000?</p>
            <button onClick={retry}>Retry</button>
          </div>
        )
      }
      return <div className="panel">Loading projects…</div>
    }

    if (data.status === 'error') {
      return (
        <div className="panel">
          <h2>The backend couldn't build the project list</h2>
          <p className="muted">See the error above. The funnel shows how far it got.</p>
          <FunnelSummary funnel={data.funnel} />
          <button onClick={handleRefresh} disabled={loading}>
            Try again
          </button>
        </div>
      )
    }

    if (data.status === 'warming') {
      const percent = data.progress.total ? Math.round((data.progress.done / data.progress.total) * 100) : 0
      return (
        <div className="panel">
          <h2>Warming up the cache…</h2>
          <p>{progressLabel(data.progress)}</p>
          <div className="progress" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
            <div className="progress-bar" style={{ width: `${percent}%` }} />
          </div>
          <p className="muted">
            The first run checks every candidate within CoinGecko's rate limits and can take several minutes. This
            page updates every {POLL_INTERVAL_MS / 1000}s.
          </p>
          <FunnelSummary funnel={data.funnel} />
        </div>
      )
    }

    const { funnel } = data
    return (
      <>
        <p className={funnel.details_skipped > 0 ? 'coverage coverage-partial' : 'coverage'}>
          {funnel.details_skipped > 0
            ? `Checked ${formatNumber(funnel.details_checked)} of ${formatNumber(funnel.passed_market_filters)} candidates. The rest will be checked on the next refresh, so results may be incomplete.`
            : `Checked all ${formatNumber(funnel.details_checked)} candidates.`}
          {isRunning(data.progress) && ` Refreshing in the background: ${progressLabel(data.progress).toLowerCase()}.`}
        </p>

        <Controls
          search={search}
          onSearchChange={setSearch}
          maxFdv={maxFdv}
          onMaxFdvChange={setMaxFdv}
          sort={sort}
          onSortChange={setSort}
          shown={visible.length}
          total={items.length}
        />

        {items.length === 0 ? (
          <div className="panel">
            <h2>No projects match all 6 criteria right now</h2>
            <p className="muted">
              This is a valid result: the criteria are strict, and preview-listed coins with TVL above $50k are rare.
              Here's how many coins made it through each step:
            </p>
            <FunnelSummary funnel={funnel} />
          </div>
        ) : visible.length === 0 ? (
          <div className="panel">
            <p>No projects match your search or FDV limit.</p>
            <button onClick={clearFilters}>Clear filters</button>
          </div>
        ) : (
          <ProjectsTable projects={visible} />
        )}
      </>
    )
  }
}
