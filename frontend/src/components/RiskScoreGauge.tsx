import { cn } from '../lib/utils'
import type { RiskLevel } from '../types'

interface RiskScoreGaugeProps {
  score: number
  level: RiskLevel
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

const LEVEL_CONFIG: Record<RiskLevel, {
  stroke: string; glow: string; textColor: string; bg: string; label: string; emoji: string
}> = {
  LOW: {
    stroke: '#10b981',
    glow: 'rgba(16, 185, 129, 0.3)',
    textColor: 'text-emerald-600',
    bg: 'text-emerald-900',
    label: 'Low Risk',
    emoji: '✅',
  },
  MEDIUM: {
    stroke: '#f59e0b',
    glow: 'rgba(245, 158, 11, 0.3)',
    textColor: 'text-amber-500',
    bg: 'text-amber-900',
    label: 'Medium Risk',
    emoji: '⚠',
  },
  HIGH: {
    stroke: '#ef4444',
    glow: 'rgba(239, 68, 68, 0.3)',
    textColor: 'text-red-600',
    bg: 'text-red-900',
    label: 'High Risk',
    emoji: '🔴',
  },
}

const SIZES = {
  sm: { dim: 'h-24 w-24', r: 38, strokeW: 8, scoreText: 'text-xl', subText: 'text-[9px]' },
  md: { dim: 'h-36 w-36', r: 58, strokeW: 10, scoreText: 'text-3xl', subText: 'text-[11px]' },
  lg: { dim: 'h-48 w-48', r: 76, strokeW: 12, scoreText: 'text-4xl', subText: 'text-xs' },
}

export function riskLevelStyles(level: RiskLevel) {
  const config = LEVEL_CONFIG[level]
  return { textColor: config.textColor, bg: config.bg }
}

export default function RiskScoreGauge({ score, level, size = 'md', showLabel = true }: RiskScoreGaugeProps) {
  const config = LEVEL_CONFIG[level]
  const { dim, r, strokeW, scoreText, subText } = SIZES[size]
  const circumference = 2 * Math.PI * r
  const dashoffset = circumference * (1 - Math.min(100, Math.max(0, score)) / 100)

  const gradientId = `gauge-grad-${level}-${size}`
  const filterId = `gauge-glow-${level}-${size}`

  return (
    <div className={cn('relative flex flex-col items-center gap-2', dim)}>
      <svg width="100%" height="100%" viewBox="0 0 160 160" className="-rotate-90 drop-shadow-md">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={config.stroke} stopOpacity="0.7" />
            <stop offset="100%" stopColor={config.stroke} stopOpacity="1" />
          </linearGradient>
          <filter id={filterId}>
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feFlood floodColor={config.glow} result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background track */}
        <circle
          cx="80"
          cy="80"
          r={r}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={strokeW}
          strokeLinecap="round"
        />

        {/* Score arc */}
        <circle
          cx="80"
          cy="80"
          r={r}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={strokeW}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashoffset}
          style={{
            transition: 'stroke-dashoffset 1s cubic-bezier(0.22, 1, 0.36, 1)',
            filter: `url(#${filterId})`,
          }}
        />
      </svg>

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('font-black tracking-tight leading-none', scoreText, config.textColor)}>
          {score}
        </span>
        <span className={cn('text-muted-foreground font-medium', subText)}>/100</span>
        {showLabel && (
          <span className={cn('font-semibold mt-1 leading-none', subText, config.textColor)}>
            {config.label}
          </span>
        )}
      </div>
    </div>
  )
}