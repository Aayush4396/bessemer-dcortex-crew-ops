export function hoursLabel(value) {
  if (value == null) return '—'
  return `${Number(value).toFixed(2)}h`
}

export const riskBadge = {
  critical: 'critical',
  elevated: 'elevated',
  low: 'low',
}
