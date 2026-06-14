"use client"

import { useEffect, useState } from "react"
import { api, ApiError } from "@/lib/api"
import type { StormsResponse } from "@/types/storm"
import StormCard from "@/components/dashboard/StormCard"
import DashboardErrorBoundary from "@/components/dashboard/DashboardErrorBoundary"
import { SkeletonCard } from "@/components/Skeleton"
import EmptyState from "@/components/EmptyState"
import { useToast } from "@/components/Toast"
import { Zap, AlertTriangle } from "lucide-react"

export default function StormsPage() {
  const [data, setData] = useState<StormsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { addToast } = useToast()

  useEffect(() => {
    let active = true

    async function load() {
      try {
        const storms = await api.getStorms()
        if (active) setData(storms)
      } catch (err) {
        if (active) {
          const msg = err instanceof ApiError ? err.message : "Failed to load storms"
          setError(msg)
          addToast(msg)
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [addToast])

  return (
    <DashboardErrorBoundary section="Storm List">
      <div className="space-y-8">
        <div>
          <h2 className="text-2xl font-display font-bold text-white/90 tracking-tight">
            Storm List
          </h2>
          <p className="text-sm text-white/40 font-body mt-1">
            Select a storm to view details or run the pipeline.
          </p>
        </div>

        {loading && <SkeletonCard />}

        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span className="text-sm text-red-300 font-body">{error}</span>
          </div>
        )}

        {data && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.available_storms.map((stormId) => (
              <StormCard
                key={stormId}
                stormId={stormId}
                completed={data.completed[stormId] ?? null}
              />
            ))}
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

        {data && data.available_storms.length === 0 && Object.keys(data.completed).length === 0 && (
          <EmptyState
            icon={<Zap className="w-8 h-8" />}
            title="No storms available."
            description="Run the detection pipeline to generate storm data."
          />
        )}
      </div>
    </DashboardErrorBoundary>
  )
}
