"use client"

import { useEffect, useState, use } from "react"
import Link from "next/link"
import { api, ApiError } from "@/lib/api"
import type { PipelineResult } from "@/types/storm"
import ImpactDisplay from "@/components/dashboard/ImpactDisplay"
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Loader2,
  Play,
  Radio,
  Satellite,
  Wind,
  Zap,
} from "lucide-react"
import clsx from "clsx"

function ScaleBadge({
  label,
  value,
  color,
}: {
  label: string
  value: string | number
  color: "aurora" | "warm" | "red"
}) {
  return (
    <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06]">
      <div className="text-[10px] font-body text-white/40 uppercase tracking-wider mb-1">
        {label}
      </div>
      <div
        className={clsx(
          "text-xl font-mono font-semibold",
          color === "aurora"
            ? "text-aurora"
            : color === "warm"
              ? "text-warm"
              : "text-red-400",
        )}
      >
        {value}
      </div>
    </div>
  )
}

export default function StormDetailPage({
  params,
}: {
  params: Promise<{ stormId: string }>
}) {
  const { stormId } = use(params)
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        const data = await api.getResult(stormId)
        if (active) setResult(data)
      } catch (err) {
        if (active) {
          if (err instanceof ApiError && err.status === 404) {
            setResult(null)
          } else {
            setError(err instanceof ApiError ? err.message : "Failed to load result")
          }
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [stormId])

  async function handleRunPipeline() {
    setRunning(true)
    setRunError(null)
    try {
      const data = await api.detect(stormId)
      setResult(data)
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Pipeline failed")
    } finally {
      setRunning(false)
    }
  }

  const cv = result?.cv_event && Object.keys(result.cv_event).length > 0
    ? (result.cv_event as PipelineResult["cv_event"] & Record<string, any>)
    : null
  const impact = result?.impact_prediction
  const gScale = cv?.scales?.G
  const hasResult = result !== null

  return (
    <div className="space-y-6">
      {/* Back + header */}
      <div>
        <Link
          href="/dashboard/storms"
          className="inline-flex items-center gap-1.5 text-xs text-white/40 hover:text-white/70 font-body transition-colors mb-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to storms
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-display font-bold text-white/90 tracking-tight">
                {stormId}
              </h2>
              {gScale != null && (
                <span
                  className={clsx(
                    "px-2.5 py-0.5 rounded text-xs font-mono font-semibold border",
                    gScale >= 5
                      ? "bg-red-500/10 text-red-400 border-red-500/20"
                      : gScale >= 3
                        ? "bg-warm/10 text-warm border-warm/20"
                        : "bg-white/10 text-white/70 border-white/10",
                  )}
                >
                  G{gScale}
                </span>
              )}
            </div>
            {result?.completed_at && (
              <p className="text-xs text-white/30 font-body mt-1">
                Completed {new Date(result.completed_at).toLocaleString()}
              </p>
            )}
          </div>

          <button
            onClick={handleRunPipeline}
            disabled={running}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-display font-medium transition-all duration-200",
              running
                ? "bg-white/[0.04] text-white/30 cursor-not-allowed"
                : "bg-aurora/10 text-aurora border border-aurora/20 hover:bg-aurora/15 active:scale-[0.98]",
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

      {/* Run error */}
      {runError && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-300 font-body">{runError}</span>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="rounded-xl p-4 border border-white/[0.06] bg-white/[0.02] animate-pulse"
            >
              <div className="h-3 w-16 rounded bg-white/[0.06] mb-2" />
              <div className="h-6 w-12 rounded bg-white/[0.06]" />
            </div>
          ))}
        </div>
      )}

      {/* Load error */}
      {error && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-300 font-body">{error}</span>
        </div>
      )}

      {/* No result yet */}
      {!loading && !hasResult && !error && (
        <div className="text-center py-16">
          <Satellite className="w-8 h-8 text-white/20 mx-auto mb-3" />
          <p className="text-sm text-white/40 font-body mb-4">
            No pipeline result yet for this storm.
          </p>
          <button
            onClick={handleRunPipeline}
            disabled={running}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-aurora/10 text-aurora border border-aurora/20 text-sm font-display font-medium hover:bg-aurora/15 transition-all"
          >
            {running ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            Run Pipeline
          </button>
        </div>
      )}

      {/* CV Event scales */}
      {cv && (
        <section className="space-y-4">
          <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
            Detection
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <ScaleBadge
              label="G-Scale"
              value={`G${cv.scales?.G ?? "?"}`}
              color={(cv.scales?.G ?? 0) >= 5 ? "red" : (cv.scales?.G ?? 0) >= 3 ? "warm" : "aurora"}
            />
            <ScaleBadge
              label="R-Scale"
              value={`R${cv.scales?.R ?? "?"}`}
              color={(cv.scales?.R ?? 0) >= 4 ? "warm" : "aurora"}
            />
            <ScaleBadge
              label="S-Scale"
              value={`S${cv.scales?.S ?? "?"}`}
              color="aurora"
            />
            <ScaleBadge
              label="Confidence"
              value={`${Math.round((cv.confidence ?? 0) * 100)}%`}
              color="aurora"
            />
          </div>

          {/* CME data */}
          {cv.cme && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-3.5 h-3.5 text-aurora" />
                  <span className="text-[10px] font-body text-white/40 uppercase tracking-wider">
                    CME Speed
                  </span>
                </div>
                <div className="text-lg font-mono font-medium text-white">
                  {cv.cme.speed_km_s?.toLocaleString() ?? "—"}
                  <span className="text-xs text-white/40 ml-1">km/s</span>
                </div>
              </div>
              <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-2">
                  <Radio className="w-3.5 h-3.5 text-aurora" />
                  <span className="text-[10px] font-body text-white/40 uppercase tracking-wider">
                    Angular Width
                  </span>
                </div>
                <div className="text-lg font-mono font-medium text-white">
                  {cv.cme.angular_width_deg ?? "—"}
                  <span className="text-xs text-white/40 ml-1">deg</span>
                </div>
              </div>
              <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-2">
                  <Wind className="w-3.5 h-3.5 text-aurora" />
                  <span className="text-[10px] font-body text-white/40 uppercase tracking-wider">
                    Direction
                  </span>
                </div>
                <div className="text-lg font-mono font-medium text-white">
                  {cv.cme.direction ?? "—"}
                </div>
              </div>
            </div>
          )}

          {/* Solar wind */}
          {cv.l1_solar_wind && (
            <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06]">
              <div className="flex items-center gap-2 mb-3">
                <Wind className="w-3.5 h-3.5 text-aurora" />
                <span className="text-[10px] font-body text-white/40 uppercase tracking-wider">
                  L1 Solar Wind
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-white/30 font-body block text-xs">Speed</span>
                  <span className="font-mono text-white/80">{cv.l1_solar_wind.speed_km_s} km/s</span>
                </div>
                <div>
                  <span className="text-white/30 font-body block text-xs">Bz</span>
                  <span className="font-mono text-white/80">{cv.l1_solar_wind.bz_nt} nT</span>
                </div>
                <div>
                  <span className="text-white/30 font-body block text-xs">Density</span>
                  <span className="font-mono text-white/80">{cv.l1_solar_wind.density_cm3} cm⁻³</span>
                </div>
                <div>
                  <span className="text-white/30 font-body block text-xs">ETA</span>
                  <span className="font-mono text-white/80">{cv.l1_solar_wind.eta_minutes} min</span>
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Impact Prediction */}
      {impact && (
        <section className="space-y-4">
          <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
            Impact Prediction
          </h3>
          <ImpactDisplay prediction={impact} />
        </section>
      )}

      {/* Timeline */}
      {cv?.timeline && cv.timeline.length > 0 && (
        <section className="space-y-4">
          <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
            Timeline
          </h3>
          <div className="space-y-2">
            {cv.timeline.map((entry: { horizon: string; source: string; t: string }, i: number) => (
              <div
                key={i}
                className="flex items-center gap-4 px-4 py-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06]"
              >
                <CheckCircle className="w-3.5 h-3.5 text-aurora/60 shrink-0" />
                <span className="text-xs font-mono text-white/50 w-20 shrink-0">
                  {entry.horizon}
                </span>
                <span className="text-xs font-body text-white/40 flex-1">
                  {entry.source}
                </span>
                <span className="text-xs font-mono text-white/30">
                  {new Date(entry.t).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Errors */}
      {result?.errors && result.errors.length > 0 && (
        <section className="space-y-4">
          <h3 className="text-sm font-display font-semibold text-warm uppercase tracking-wider">
            Errors
          </h3>
          <div className="space-y-2">
            {result.errors.map((err, i) => (
              <div
                key={i}
                className="flex items-start gap-3 px-4 py-3 rounded-lg bg-warm/[0.04] border border-warm/[0.1]"
              >
                <AlertTriangle className="w-3.5 h-3.5 text-warm shrink-0 mt-0.5" />
                <span className="text-xs font-body text-white/50">{err}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
