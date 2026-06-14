"use client"

import Link from "next/link"
import { CheckCircle, AlertTriangle } from "lucide-react"
import clsx from "clsx"
import type { StormSummary } from "@/types/storm"

function gScaleBadge(stormId: string): { label: string; className: string } | null {
  const match = stormId.match(/G(\d)$/)
  if (!match) return null
  const g = Number(match[1])
  if (g <= 2) return { label: `G${g}`, className: "bg-white/10 text-white/70 border-white/10" }
  if (g <= 4) return { label: `G${g}`, className: "bg-warm/10 text-warm border-warm/20" }
  return { label: `G${g}`, className: "bg-red-500/10 text-red-400 border-red-500/20" }
}

export interface StormCardProps {
  stormId: string
  completed: StormSummary | null
}

export default function StormCard({ stormId, completed }: StormCardProps) {
  const isComplete = completed !== null && completed.error_count === 0
  const hasErrors = completed !== null && completed.error_count > 0
  const badge = gScaleBadge(stormId)

  return (
    <Link
      href={`/dashboard/storms/${stormId}`}
      className={clsx(
        "group block rounded-xl p-5 border transition-all duration-200",
        "hover:scale-[1.01] active:scale-[0.99]",
        isComplete
          ? "bg-aurora/[0.03] border-aurora/[0.12] hover:border-aurora/[0.25]"
          : hasErrors
            ? "bg-warm/[0.03] border-warm/[0.12] hover:border-warm/[0.25]"
            : "bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]",
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-mono font-medium text-white/80">
            {stormId}
          </span>
          {badge && (
            <span
              className={clsx(
                "px-2 py-0.5 rounded text-[10px] font-mono font-semibold border",
                badge.className,
              )}
            >
              {badge.label}
            </span>
          )}
        </div>
        {isComplete ? (
          <CheckCircle className="w-4 h-4 text-aurora shrink-0" />
        ) : hasErrors ? (
          <AlertTriangle className="w-4 h-4 text-warm shrink-0" />
        ) : (
          <span className="w-4 h-4 rounded-full border border-white/20 shrink-0" />
        )}
      </div>

      {completed ? (
        <div className="space-y-1.5 text-xs font-body text-white/40">
          <div className="flex justify-between">
            <span>Advisories</span>
            <span className="text-white/60 font-mono">{completed.advisory_count}</span>
          </div>
          <div className="flex justify-between">
            <span>Verified</span>
            <span className="text-white/60 font-mono">{completed.verified_count}</span>
          </div>
          {completed.error_count > 0 && (
            <div className="flex justify-between">
              <span>Errors</span>
              <span className="text-warm font-mono">{completed.error_count}</span>
            </div>
          )}
          <div className="pt-2 border-t border-white/[0.06] text-white/30 flex justify-between items-center">
            <span>{new Date(completed.completed_at).toLocaleDateString()}</span>
            {completed.advisory_count > 0 && (
              <Link
                href={`/dashboard/results/${stormId}`}
                onClick={(e) => e.stopPropagation()}
                className="text-aurora/60 hover:text-aurora transition-colors"
              >
                View results &rarr;
              </Link>
            )}
          </div>
        </div>
      ) : (
        <p className="text-xs font-body text-white/30">
          Not yet processed. Click to run pipeline.
        </p>
      )}
    </Link>
  )
}
