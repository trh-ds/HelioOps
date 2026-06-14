"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { Filter } from "lucide-react"
import clsx from "clsx"
import type { WsEvent } from "@/types/storm"

export interface LogEntry {
  id: string
  event: WsEvent
  timestamp: string
}

type EventType = "stage" | "advisory" | "verifier" | "error" | "complete"

function classifyEvent(event: WsEvent): EventType {
  if (event.event === "pipeline.stage") return "stage"
  if (event.event === "pipeline.error" || event.event === "error") return "error"
  if (event.event === "pipeline.complete") return "complete"
  if (event.event.startsWith("advisory.")) return "advisory"
  if (event.event.startsWith("verifier.")) return "verifier"
  return "stage"
}

const TYPE_COLORS: Record<EventType, { bg: string; text: string; border: string }> = {
  stage: {
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    border: "border-blue-500/20",
  },
  advisory: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
  },
  verifier: {
    bg: "bg-purple-500/10",
    text: "text-purple-400",
    border: "border-purple-500/20",
  },
  error: {
    bg: "bg-red-500/10",
    text: "text-red-400",
    border: "border-red-500/20",
  },
  complete: {
    bg: "bg-aurora/10",
    text: "text-aurora",
    border: "border-aurora/20",
  },
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  } catch {
    return "--:--:--"
  }
}

function eventLabel(event: WsEvent): string {
  switch (event.event) {
    case "pipeline.stage":
      return `${event.stage.replace(/_/g, " ")} — ${event.status}`
    case "pipeline.error":
      return `Error in ${event.stage}: ${event.error}`
    case "pipeline.complete":
      return `Pipeline complete — ${event.total_advisories} advisories, ${event.total_verified} verified`
    case "advisory.generated":
      return `Advisory generated — ${event.industry}`
    case "advisory.verified":
      return `Advisory verified — ${event.industry} (${event.severity})`
    case "verifier.check":
      return `Verifier check — ${event.field}: ${event.status}`
    case "verifier.error":
      return `Verifier error — ${event.error}`
    case "error":
      return event.message
    default:
      return (event as { event: string }).event
  }
}

export default function StreamLog({ events }: { events: WsEvent[] }) {
  const [filter, setFilter] = useState<EventType | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  const entries: LogEntry[] = events.map((event, i) => ({
    id: `${i}-${event.event}`,
    event,
    timestamp: "timestamp" in event ? (event as { timestamp: string }).timestamp : "",
  }))

  const filtered = filter
    ? entries.filter((e) => classifyEvent(e.event) === filter)
    : entries

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [events.length])

  return (
    <div className="flex flex-col h-full">
      {/* Filters */}
      <div className="flex items-center gap-2 mb-3">
        <Filter className="w-3 h-3 text-white/30" />
        {(["stage", "advisory", "verifier", "error", "complete"] as EventType[]).map(
          (type) => {
            const colors = TYPE_COLORS[type]
            return (
              <button
                key={type}
                onClick={() => setFilter(filter === type ? null : type)}
                className={clsx(
                  "px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-all",
                  filter === type
                    ? `${colors.bg} ${colors.text} ${colors.border}`
                    : "text-white/30 border-white/[0.08] hover:text-white/50"
                )}
              >
                {type}
              </button>
            )
          }
        )}
      </div>

      {/* Log entries */}
      <div
        ref={logRef}
        className="flex-1 overflow-y-auto space-y-1 pr-1"
        data-testid="log-container"
      >
        {filtered.length === 0 && (
          <div className="text-center py-8 text-white/20 text-xs font-body">
            {events.length === 0
              ? "Waiting for pipeline events..."
              : "No events match this filter."}
          </div>
        )}

        {filtered.map((entry) => {
          const colors = TYPE_COLORS[classifyEvent(entry.event)]
          return (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx(
                "px-3 py-2 rounded-lg border text-xs font-body",
                colors.bg,
                colors.border
              )}
            >
              <div className="flex items-start gap-3">
                <span className="text-white/30 font-mono text-[10px] shrink-0 pt-0.5">
                  {formatTimestamp(entry.timestamp)}
                </span>
                <span className={clsx("flex-1", colors.text)}>
                  {eventLabel(entry.event)}
                </span>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
