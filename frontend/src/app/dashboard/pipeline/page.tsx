"use client"

import { useEffect, useState, useCallback } from "react"
import Link from "next/link"
import { Play, ExternalLink, Loader2, AlertTriangle } from "lucide-react"
import clsx from "clsx"
import { api } from "@/lib/api"
import { wsClient } from "@/lib/ws-client"
import type { WsEvent, PipelineStageEvent } from "@/types/storm"
import PipelineProgress, {
  type PipelineStep,
} from "@/components/dashboard/PipelineProgress"
import StreamLog from "@/components/dashboard/StreamLog"
import DashboardErrorBoundary from "@/components/dashboard/DashboardErrorBoundary"
import { useToast } from "@/components/Toast"

const STAGE_ORDER = [
  "detection",
  "impact_prediction",
  "adaptation",
  "advisory_generation",
  "verification",
] as const

function buildSteps(events: WsEvent[]): PipelineStep[] {
  const steps: PipelineStep[] = STAGE_ORDER.map((id) => ({
    id,
    label: id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    status: "pending",
  }))

  for (const event of events) {
    if (event.event !== "pipeline.stage") continue
    const stageEvent = event as PipelineStageEvent
    const idx = STAGE_ORDER.indexOf(
      stageEvent.stage as (typeof STAGE_ORDER)[number]
    )
    if (idx === -1) continue

    if (stageEvent.status === "started") {
      steps[idx].status = "active"
    } else if (stageEvent.status === "completed") {
      steps[idx].status = "done"
    } else if (stageEvent.status === "failed") {
      steps[idx].status = "error"
    }
  }

  return steps
}

export default function PipelinePage() {
  const [storms, setStorms] = useState<string[]>([])
  const [selected, setSelected] = useState("")
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<WsEvent[]>([])
  const [completed, setCompleted] = useState<{
    stormId: string
    advisories: number
    verified: number
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { addToast } = useToast()

  useEffect(() => {
    api
      .getStorms()
      .then((res) => setStorms(res.available_storms))
      .catch(() => {
        setError("Failed to load storms")
        addToast("Failed to load storms")
      })
  }, [addToast])

  const handleEvent = useCallback(
    (event: WsEvent) => {
      setEvents((prev) => [...prev, event])

      if (event.event === "pipeline.error" || event.event === "error") {
        const msg = event.event === "pipeline.error" ? event.error : event.message
        setError(msg)
        addToast(msg)
      }

      if (event.event === "pipeline.complete") {
        setRunning(false)
        setCompleted({
          stormId: event.storm_id,
          advisories: event.total_advisories,
          verified: event.total_verified,
        })
      }
    },
    [addToast]
  )

  useEffect(() => {
    wsClient.connect()
    const unsubscribe = wsClient.subscribe(handleEvent)
    return () => {
      unsubscribe()
      wsClient.disconnect()
    }
  }, [handleEvent])

  const handleRun = () => {
    if (!selected || running) return

    setRunning(true)
    setEvents([])
    setCompleted(null)
    setError(null)

    try {
      wsClient.send({ action: "run_pipeline", storm_id: selected })
    } catch {
      setError("WebSocket not connected")
      addToast("WebSocket not connected")
      setRunning(false)
    }
  }

  const steps = buildSteps(events)

  return (
    <DashboardErrorBoundary section="Pipeline Runner">
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-display font-bold text-white/90 tracking-tight">
            Pipeline Runner
          </h2>
          <p className="text-sm text-white/40 font-body mt-1">
            Select a storm and run the full CV &rarr; Impact &rarr; Advisory &rarr; Verification pipeline.
          </p>
        </div>

        {/* Storm selector + Run button */}
        <div className="flex items-center gap-4">
          <div className="flex-1 max-w-sm">
            <label className="block text-xs text-white/40 font-body mb-1.5">
              Storm ID
            </label>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={running}
              className={clsx(
                "w-full px-3 py-2.5 rounded-lg text-sm font-body",
                "bg-deep-900 border border-white/[0.08] text-white/80",
                "focus:outline-none focus:border-aurora/40",
                "disabled:opacity-40 disabled:cursor-not-allowed"
              )}
            >
              <option value="">Select a storm...</option>
              {storms.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end gap-2 pt-5">
            <button
              onClick={handleRun}
              disabled={!selected || running}
              className={clsx(
                "flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-body font-medium transition-all",
                selected && !running
                  ? "bg-aurora/15 text-aurora border border-aurora/25 hover:bg-aurora/25 active:scale-[0.98]"
                  : "bg-white/[0.04] text-white/30 border border-white/[0.06] cursor-not-allowed"
              )}
            >
              {running ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {running ? "Running..." : "Run Pipeline"}
            </button>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span className="text-sm text-red-300 font-body">{error}</span>
          </div>
        )}

        {/* Completion banner */}
        {completed && (
          <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-aurora/[0.06] border border-aurora/[0.12]">
            <span className="text-sm text-aurora font-body">
              Pipeline complete &mdash; {completed.advisories} advisories, {completed.verified} verified
            </span>
            <Link
              href={`/dashboard/results/${completed.stormId}`}
              className="flex items-center gap-1.5 text-xs text-aurora/70 hover:text-aurora font-body transition-colors"
            >
              View advisories <ExternalLink className="w-3 h-3" />
            </Link>
          </div>
        )}

        {/* Progress + Log */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Pipeline progress */}
          <div className="lg:col-span-1 glass rounded-xl p-5">
            <h3 className="text-sm font-display font-semibold text-white/70 mb-4">
              Pipeline Progress
            </h3>
            <PipelineProgress steps={steps} />
          </div>

          {/* Event stream */}
          <div className="lg:col-span-2 glass rounded-xl p-5 min-h-[400px]">
            <h3 className="text-sm font-display font-semibold text-white/70 mb-2">
              Event Stream
            </h3>
            <div className="h-[350px]">
              <StreamLog events={events} />
            </div>
          </div>
        </div>
      </div>
    </DashboardErrorBoundary>
  )
}
