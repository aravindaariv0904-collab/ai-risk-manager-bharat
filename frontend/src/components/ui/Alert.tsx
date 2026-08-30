import { cn } from '../../lib/utils'
import { ShieldAlert, CheckCircle2, Info, TriangleAlert, type LucideIcon } from 'lucide-react'

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'error'
}

const ICONS: Record<string, LucideIcon> = {
  default: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  error: ShieldAlert,
}

function Alert({ className, variant = 'default', ...props }: AlertProps) {
  const Icon = ICONS[variant]
  return (
    <div
      className={cn(
        'relative w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4',
        variant === 'default' && 'bg-blue-50 border-blue-200 text-blue-800',
        variant === 'success' && 'bg-emerald-50 border-emerald-200 text-emerald-800',
        variant === 'warning' && 'bg-amber-50 border-amber-200 text-amber-800',
        variant === 'error' && 'bg-red-50 border-red-200 text-red-800',
        className,
      )}
      {...props}
    >
      <Icon className="h-4 w-4" />
      {props.children}
    </div>
  )
}

export { Alert }
