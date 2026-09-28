// Mirrors backend/app/schemas.py

export type Status = 'warming' | 'ready' | 'error'
export type Stage = 'idle' | 'markets' | 'details' | 'done'

export interface Project {
  id: string
  name: string
  symbol: string
  image: string | null
  current_price: number | null
  market_cap: number
  fdv: number
  total_volume: number
  tvl: number
  total_supply: number
  max_supply: number
  coingecko_url: string
}

export interface Progress {
  stage: Stage
  done: number
  total: number
}

export interface Funnel {
  markets_scanned: number
  passed_market_filters: number
  details_checked: number
  details_failed: number
  details_skipped: number
  passed_all: number
}

export interface ProjectsResponse {
  status: Status
  updated_at: string | null
  stale: boolean
  error: string | null
  progress: Progress
  funnel: Funnel
  count: number
  items: Project[]
}

export type SortKey = 'market_cap_desc' | 'market_cap_asc' | 'volume_desc' | 'volume_asc'
