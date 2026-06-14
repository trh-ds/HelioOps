"use client"

import type { ImpactPrediction } from "@/types/storm"
import clsx from "clsx"

function isFallback(p: ImpactPrediction): boolean {
  return p.gps_error_m === 20.0 && p.hf_blackout_prob === 0.85
}

function GaugeBar({
  value,
  label,
  color,
}: {
  value: number
  label: string
  color: "aurora" | "warm"
}) {
  const pct = Math.round(value * 100)
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs font-body">
        <span className="text-white/40">{label}</span>
        <span className="font-mono text-white/60">{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={clsx(
            "h-full rounded-full transition-all duration-500",
            color === "aurora" ? "bg-aurora" : "bg-warm",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function CIBar({
  low,
  value,
  high,
  unit,
  max,
}: {
  low: number
  value: number
  high: number
  unit: string
  max: number
}) {
  const lowPct = Math.min((low / max) * 100, 100)
  const valPct = Math.min((value / max) * 100, 100)
  const highPct = Math.min((high / max) * 100, 100)

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs font-body">
        <span className="text-white/40">95% CI</span>
        <span className="font-mono text-white/60">
          {low.toFixed(1)}–{high.toFixed(1)} {unit}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-white/[0.06]">
        {/* CI range */}
        <div
          className="absolute top-0 h-full rounded-full bg-white/[0.08]"
          style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
        />
        {/* Median marker */}
        <div
          className="absolute top-0 h-full w-0.5 bg-aurora rounded-full"
          style={{ left: `${valPct}%` }}
        />
      </div>
    </div>
  )
}

export default function ImpactDisplay({ prediction }: { prediction: ImpactPrediction }) {
  const fallback = isFallback(prediction)

  return (
    <div className="space-y-4">
      {fallback && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-warm/[0.06] border border-warm/[0.12]">
          <span className="text-[10px] font-mono text-warm/80 uppercase tracking-wider">
            Conservative defaults — ML checkpoints not loaded
          </span>
        </div>
      )}

      {/* GPS Error */}
      <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06] space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-body text-white/40 uppercase tracking-wider">
            GPS L1 Error
          </span>
          <span className="text-2xl font-mono font-medium text-white">
            {prediction.gps_error_m.toFixed(1)}
            <span className="text-sm text-white/40 ml-1">m</span>
          </span>
        </div>
        <CIBar
          low={prediction.gps_error_ci_low}
          value={prediction.gps_error_m}
          high={prediction.gps_error_ci_high}
          unit="m"
          max={40}
        />
      </div>

      {/* HF Blackout */}
      <div className="rounded-xl p-4 bg-white/[0.02] border border-white/[0.06] space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-body text-white/40 uppercase tracking-wider">
            HF Blackout Probability
          </span>
          <span className="text-2xl font-mono font-medium text-white">
            {Math.round(prediction.hf_blackout_prob * 100)}
            <span className="text-sm text-white/40 ml-1">%</span>
          </span>
        </div>
        <GaugeBar
          value={prediction.hf_blackout_prob}
          label="Blackout risk"
          color={prediction.hf_blackout_prob > 0.7 ? "warm" : "aurora"}
        />
        <div className="flex justify-between text-[10px] font-mono text-white/30">
          <span>Low: {Math.round(prediction.hf_blackout_ci_low * 100)}%</span>
          <span>High: {Math.round(prediction.hf_blackout_ci_high * 100)}%</span>
        </div>
      </div>
    </div>
  )
}
