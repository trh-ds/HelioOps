"use client"

import { parseMetrics } from "@/lib/api"
import clsx from "clsx"

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function GaugeCard({
  label,
  value,
  unit,
  color = "aurora",
}: {
  label: string
  value: string | number
  unit?: string
  color?: "aurora" | "warm" | "red" | "blue"
}) {
  const colorClasses = {
    aurora: "text-aurora",
    warm: "text-warm",
    red: "text-red-400",
    blue: "text-blue-400",
  }
  return (
    <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06]">
      <div className="text-[10px] font-body text-white/40 uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className={clsx("text-xl font-mono font-medium", colorClasses[color])}>
        {value}
        {unit && (
          <span className="text-xs text-white/40 ml-1">{unit}</span>
        )}
      </div>
    </div>
  )
}

export default function MetricsDisplay({
  rawMetrics,
}: {
  rawMetrics: string
}) {
  const metrics = parseMetrics(rawMetrics)

  const uptime = metrics.get("helioops_uptime_seconds") ?? 0
  const requests = metrics.get("helioops_pipeline_requests_total") ?? 0
  const errors = metrics.get("helioops_pipeline_errors_total") ?? 0
  const avgLatency = metrics.get("helioops_pipeline_duration_seconds_avg") ?? 0
  const p99Latency = metrics.get("helioops_pipeline_duration_seconds_p99") ?? 0
  const connections = metrics.get("helioops_ws_connections_total") ?? 0
  const detection = metrics.get("helioops_detection_requests_total") ?? 0
  const advisory = metrics.get("helioops_advisory_requests_total") ?? 0

  const errorRate = requests > 0 ? ((errors / requests) * 100).toFixed(1) : "0.0"

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <GaugeCard label="Uptime" value={formatUptime(uptime)} color="aurora" />
        <GaugeCard label="Pipeline Requests" value={requests} color="blue" />
        <GaugeCard
          label="Error Rate"
          value={errorRate}
          unit="%"
          color={Number(errorRate) > 5 ? "red" : "aurora"}
        />
        <GaugeCard label="WS Connections" value={connections} color="blue" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <GaugeCard
          label="Avg Latency"
          value={avgLatency > 0 ? avgLatency.toFixed(2) : "—"}
          unit={avgLatency > 0 ? "s" : undefined}
        />
        <GaugeCard
          label="P99 Latency"
          value={p99Latency > 0 ? p99Latency.toFixed(2) : "—"}
          unit={p99Latency > 0 ? "s" : undefined}
        />
        <GaugeCard label="Detection Requests" value={detection} />
        <GaugeCard label="Advisory Requests" value={advisory} />
      </div>
    </div>
  )
}
