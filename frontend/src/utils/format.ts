const compactUsd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
})

const numberFormat = new Intl.NumberFormat('en-US')

/** `12345678` → `$12.3M` */
export function formatUsdCompact(value: number | null | undefined): string {
  return value == null ? '—' : compactUsd.format(value)
}

/** Prices span many orders of magnitude, so keep significant digits for tiny values. */
export function formatPrice(value: number | null | undefined): string {
  if (value == null) return '—'
  const digits = value >= 1 ? 2 : Math.min(8, 2 - Math.floor(Math.log10(value)) + 1)
  return `$${value.toLocaleString('en-US', { maximumFractionDigits: digits })}`
}

export function formatNumber(value: number): string {
  return numberFormat.format(value)
}

export function formatDateTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : '—'
}
