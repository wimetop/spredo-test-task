import type { Funnel } from '../types'
import { formatNumber } from '../utils/format'

/** Explains how many coins survived each stage — the answer to "why so few / zero results?". */
export function FunnelSummary({ funnel }: { funnel: Funnel }) {
  const steps = [
    { label: 'Coins scanned (volume-sorted market pages)', value: funnel.markets_scanned },
    { label: 'Passed market cap > 0, max = total supply, FDV < $100M, volume > $50k', value: funnel.passed_market_filters },
    { label: 'Details checked (preview listing + TVL)', value: funnel.details_checked },
    { label: 'Passed all 6 criteria', value: funnel.passed_all },
  ]

  return (
    <div className="funnel">
      <ol>
        {steps.map((step) => (
          <li key={step.label}>
            <strong>{formatNumber(step.value)}</strong> <span>{step.label}</span>
          </li>
        ))}
      </ol>
      {(funnel.details_skipped > 0 || funnel.details_failed > 0) && (
        <p className="muted">
          Not checked yet: {formatNumber(funnel.details_skipped)} · Failed to load: {formatNumber(funnel.details_failed)}
        </p>
      )}
    </div>
  )
}
