"use client"

import { useEffect, useState } from "react"
import { api, ApiError } from "@/lib/api"
import type { StormsResponse } from "@/types/storm"
import StormCard from "@/components/dashboard/StormCard"
import { AlertTriangle, Loader2, Zap } from "lucide-react"

export default function StormsPage() {
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
      <div>
        <h2 className="text-2xl font-display font-bold text-white/90 tracking-tight">
          Storm List
        </h2>
        <p className="text-sm text-white/40 font-body mt-1">
          Select a storm to view details or run the pipeline.
        </p>
      </div>

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl p-5 border border-white/[0.06] bg-white/[0.02] animate-pulse"
            >
              <div className="flex items-center gap-2.5 mb-3">
                <div className="h-4 w-28 rounded bg-white/[0.06]" />
                <div className="h-4 w-8 rounded bg-white/[0.06]" />
              </div>
              <div className="space-y-2">
                <div className="h-3 w-full rounded bg-white/[0.04]" />
                <div className="h-3 w-2/3 rounded bg-white/[0.04]" />
              </div>
            </div>
          ))}
        </div>
      )}

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
        <div className="text-center py-16">
          <Zap className="w-8 h-8 text-white/20 mx-auto mb-3" />
          <p className="text-sm text-white/40 font-body">No storms available.</p>
        </div>
      )}
    </div>
  )
}
