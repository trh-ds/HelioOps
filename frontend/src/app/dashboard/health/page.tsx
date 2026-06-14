"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { api } from "@/lib/api"
import type { HealthResponse } from "@/types/storm"
import MetricsDisplay from "@/components/dashboard/MetricsDisplay"
import {
  CheckCircle,
  XCircle,
  Loader2,
  AlertTriangle,
  RefreshCw,
} from "lucide-react"
import clsx from "clsx"

const REFRESH_INTERVAL = 10_000

const CHECK_LABELS: Record<string, string> = {
  detection: "CV Detection",
  ml_models: "ML Models",
  genai_module: "GenAI Module",
}

function StatusDot({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
  ) : (
    <XCircle className="w-4 h-4 text-red-400 shrink-0" />
  )
}

export default function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [ready, setReady] = useState<HealthResponse | null>(null)
  const [metrics, setMetrics] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchAll = useCallback(async () => {
    try {
      const [healthRes, readyRes, metricsRes] = await Promise.allSettled([
        api.getHealth(),
        api.getHealthReady(),
        api.getMetrics(),
      ])

      if (healthRes.status === "fulfilled") setHealth(healthRes.value)
      if (readyRes.status === "fulfilled") setReady(readyRes.value)
      if (metricsRes.status === "fulfilled") setMetrics(metricsRes.value)

      const anyRejected = [healthRes, readyRes, metricsRes].some(
        (r) => r.status === "rejected"
      )
      if (anyRejected && healthRes.status === "rejected") {
        setError("Backend unreachable")
      } else {
        setError(null)
      }

      setLastRefresh(new Date())
    } catch {
      setError("Failed to fetch health data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    intervalRef.current = setInterval(fetchAll, REFRESH_INTERVAL)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchAll])

  const checks = ready?.checks ?? {}
  const checkEntries = Object.entries(checks)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-display font-bold text-white/90 tracking-tight">
            Health &amp; Metrics
          </h2>
          <p className="text-sm text-white/40 font-body mt-1">
            System status, dependency checks, and Prometheus metrics.
            Auto-refreshes every 10s.
          </p>
        </div>
        {lastRefresh && (
          <span className="text-[10px] font-mono text-white/20">
            Last refresh: {lastRefresh.toLocaleTimeString("en-US", { hour12: false })}
          </span>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 px-4 py-8 rounded-xl bg-white/[0.02] border border-white/[0.06]">
          <Loader2 className="w-4 h-4 text-white/40 animate-spin" />
          <span className="text-sm text-white/40 font-body">Loading health data...</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-300 font-body">{error}</span>
        </div>
      )}

      {/* Basic Health */}
      {health && (
        <section className="space-y-4">
          <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
            Service Status
          </h3>
          <div className="glass rounded-xl p-5">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="flex items-center gap-3">
                <StatusDot ok={health.status === "ok"} />
                <div>
                  <div className="text-xs font-body text-white/40">Status</div>
                  <div className="text-sm font-mono text-white/80">{health.status}</div>
                </div>
              </div>
              {health.version && (
                <div>
                  <div className="text-xs font-body text-white/40">Version</div>
                  <div className="text-sm font-mono text-white/80">{health.version}</div>
                </div>
              )}
              {health.timestamp && (
                <div>
                  <div className="text-xs font-body text-white/40">Timestamp</div>
                  <div className="text-sm font-mono text-white/80">
                    {new Date(health.timestamp).toLocaleString()}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Dependency Checks */}
      {checkEntries.length > 0 && (
        <section className="space-y-4">
          <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
            Dependency Checks
          </h3>
          <div className="glass rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <span
                className={clsx(
                  "px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border",
                  ready?.status === "ready"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-red-500/10 text-red-400 border-red-500/20"
                )}
              >
                {ready?.status ?? "unknown"}
              </span>
            </div>

            <div className="space-y-3">
              {checkEntries.map(([name, ok]) => (
                <div key={name} className="flex items-center gap-3">
                  <StatusDot ok={ok} />
                  <span className="text-sm font-body text-white/70">
                    {CHECK_LABELS[name] ?? name}
                  </span>
                  <span
                    className={clsx(
                      "text-[10px] font-mono ml-auto",
                      ok ? "text-emerald-400/60" : "text-red-400/60"
                    )}
                  >
                    {ok ? "healthy" : "unavailable"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Metrics */}
      {metrics && (
        <section className="space-y-4">
          <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
            Prometheus Metrics
          </h3>
          <MetricsDisplay rawMetrics={metrics} />
        </section>
      )}
    </div>
  )
}
