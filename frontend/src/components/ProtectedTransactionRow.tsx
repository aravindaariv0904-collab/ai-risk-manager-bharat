import { ShieldCheck } from 'lucide-react'
import type { Transaction } from '../types'

export function ProtectedTransactionRow({ txn }: { txn: Transaction }) {
  if (!txn.risk_score) return null
  return (
    <span className="inline-flex items-center gap-1 text-xs text-emerald-600" title={`Risk score ${txn.risk_score}/100`}>
      <ShieldCheck className="h-3.5 w-3.5" />
      Protected
    </span>
  )
}