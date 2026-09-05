import { Badge } from './ui/Badge'
import type { RiskLevel } from '../types'

export default function RiskLevelBadge({ level }: { level: RiskLevel | null }) {
  if (!level) return <Badge variant="outline">N/A</Badge>

  const map: Record<RiskLevel, { label: string; variant: 'success' | 'warning' | 'danger' }> = {
    LOW: { label: 'LOW RISK', variant: 'success' },
    MEDIUM: { label: 'MEDIUM RISK', variant: 'warning' },
    HIGH: { label: 'HIGH RISK', variant: 'danger' },
    CRITICAL: { label: 'CRITICAL RISK', variant: 'danger' },
  }

  const config = map[level] || { label: String(level), variant: 'danger' }
  return <Badge variant={config.variant}>{config.label}</Badge>
}