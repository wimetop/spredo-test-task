import type { SortKey } from '../types'
import { formatUsdCompact } from '../utils/format'

interface ControlsProps {
  search: string
  onSearchChange: (value: string) => void
  maxFdv: string
  onMaxFdvChange: (value: string) => void
  sort: SortKey
  onSortChange: (value: SortKey) => void
  shown: number
  total: number
}

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'market_cap_desc', label: 'Market cap ↓' },
  { value: 'market_cap_asc', label: 'Market cap ↑' },
  { value: 'volume_desc', label: '24h volume ↓' },
  { value: 'volume_asc', label: '24h volume ↑' },
]

export function Controls(props: ControlsProps) {
  const maxFdvNumber = Number(props.maxFdv)
  const fdvHint =
    props.maxFdv.trim() !== '' && Number.isFinite(maxFdvNumber) ? `≤ ${formatUsdCompact(maxFdvNumber)}` : 'no limit'

  return (
    <div className="controls">
      <label className="field">
        <span>Search</span>
        <input
          type="search"
          placeholder="Name or symbol, e.g. eth"
          value={props.search}
          onChange={(e) => props.onSearchChange(e.target.value)}
        />
      </label>

      <label className="field">
        <span>
          Max FDV (USD) <small className="muted">{fdvHint}</small>
        </span>
        <input
          type="number"
          min={0}
          step={1_000_000}
          placeholder="e.g. 50000000"
          value={props.maxFdv}
          onChange={(e) => props.onMaxFdvChange(e.target.value)}
        />
      </label>

      <label className="field">
        <span>Sort by</span>
        <select value={props.sort} onChange={(e) => props.onSortChange(e.target.value as SortKey)}>
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <p className="count">
        {props.shown} of {props.total} projects
      </p>
    </div>
  )
}
