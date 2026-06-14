"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { api, ApiError } from "@/lib/api"
import type { StormsResponse } from "@/types/storm"
import { AlertTriangle, CheckCircle, Loader2, Zap } from "lucide-react"
import clsx from "clsx"

export default function DashboardPage() {
  const [data, setData] = useState<StormsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        const storms = await api.getStorms()
        if (active) setData(storms)
      } catch (err) {
        if (active) {
          setError(err instanceof ApiError ? err.message : "Failed to load storms")
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-display font-bold text-white/90 tracking-tight">
          Storms
        </h2>
        <p className="text-sm text-white/40 font-body mt-1">
          Available storms and completed pipeline results.
        </p>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 text-white/40 py-12">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm font-body">Loading storms...</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-300 font-body">{error}</span>
        </div>
      )}

      {/* Storm grid */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Available storms */}
          {data.available_storms.map((stormId) => {
            const completed = data.completed[stormId]
            return (
              <StormCard
                key={stormId}
                stormId={stormId}
                completed={completed ?? null}
              />
            )
          })}

          {/* Completed storms not in available list */}
          {Object.keys(data.completed)
            .filter((id) => !data.available_storms.includes(id))
            .map((stormId) => (
              <StormCard
                key={stormId}
                stormId={stormId}
                completed={data.completed[stormId]}
              />
            ))}
        </div>
      )}

      {/* Empty state */}
      {data && data.available_storms.length === 0 && Object.keys(data.completed).length === 0 && (
        <div className="text-center py-16">
          <Zap className="w-8 h-8 text-white/20 mx-auto mb-3" />
          <p className="text-sm text-white/40 font-body">No storms available.</p>
        </div>
      )}
    </div>
  )
}

function StormCard({
  stormId,
  completed,
}: {
  stormId: string
  completed: StormsResponse["completed"][string] | null
}) {
  const isComplete = completed !== null && completed.error_count === 0
  const hasErrors = completed !== null && completed.error_count > 0

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
        <span className="text-sm font-mono font-medium text-white/80">
          {stormId}
        </span>
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
          <div className="pt-2 border-t border-white/[0.06] text-white/30">
            {new Date(completed.completed_at).toLocaleDateString()}
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
