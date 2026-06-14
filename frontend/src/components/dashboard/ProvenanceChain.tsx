"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import clsx from "clsx"
import type { ProvenanceTrace } from "@/types/storm"

const STEP_LABELS: Record<string, string> = {
  raw_data: "Raw Data",
  detection: "Detection",
  impact: "Impact",
  retrieval: "Retrieval",
  verifier: "Verifier",
  output: "Output",
}

const STEP_ORDER = ["raw_data", "detection", "impact", "retrieval", "verifier", "output"]

function ConfidenceBar({ confidence }: { confidence: number | null }) {
  if (confidence === null) {
    return <span className="text-[10px] font-mono text-white/20">n/a</span>
  }
  const pct = Math.round(confidence * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={clsx(
            "h-full rounded-full",
            pct >= 80
              ? "bg-emerald-400"
              : pct >= 50
                ? "bg-yellow-400"
                : "bg-red-400"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-white/40">{pct}%</span>
    </div>
  )
}

export default function ProvenanceChain({
  trace,
}: {
  trace: ProvenanceTrace
}) {
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">
          Provenance Chain
        </span>
        <span className="text-[10px] font-mono text-white/20">
          {trace.trace_id}
        </span>
      </div>

      {/* Horizontal timeline */}
      <div className="flex items-start gap-0 overflow-x-auto pb-2">
        {STEP_ORDER.map((stepId, i) => {
          const step = trace.chain.find((s) => s.step === stepId)
          const isExpanded = expanded === stepId
          const hasData = step !== undefined

          return (
            <div key={stepId} className="flex items-start">
              {/* Step node */}
              <button
                onClick={() =>
                  setExpanded(isExpanded ? null : stepId)
                }
                className={clsx(
                  "flex flex-col items-center min-w-[72px] group transition-all",
                  hasData ? "opacity-100" : "opacity-30"
                )}
              >
                {/* Circle */}
                <div
                  className={clsx(
                    "w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-mono border transition-all",
                    hasData
                      ? "bg-aurora/10 border-aurora/30 text-aurora group-hover:bg-aurora/20"
                      : "bg-white/[0.04] border-white/[0.08] text-white/30"
                  )}
                >
                  {i + 1}
                </div>

                {/* Label */}
                <span
                  className={clsx(
                    "mt-1.5 text-[10px] font-body text-center leading-tight",
                    hasData ? "text-white/60" : "text-white/20"
                  )}
                >
                  {STEP_LABELS[stepId] ?? stepId}
                </span>

                {/* Confidence */}
                {hasData && (
                  <div className="mt-1">
                    <ConfidenceBar confidence={step!.confidence} />
                  </div>
                )}
              </button>

              {/* Connector line */}
              {i < STEP_ORDER.length - 1 && (
                <div className="flex items-center pt-4 px-0.5">
                  <div
                    className={clsx(
                      "w-6 h-px",
                      hasData && trace.chain.some((s) => s.step === STEP_ORDER[i + 1])
                        ? "bg-aurora/30"
                        : "bg-white/[0.08]"
                    )}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Expanded detail */}
      {expanded && (() => {
        const step = trace.chain.find((s) => s.step === expanded)
        if (!step) return null

        return (
          <div className="rounded-lg p-3 bg-white/[0.02] border border-white/[0.06] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-body text-white/60 font-medium">
                {STEP_LABELS[step.step] ?? step.step}
              </span>
              <button
                onClick={() => setExpanded(null)}
                className="text-white/30 hover:text-white/50"
              >
                <ChevronUp className="w-3 h-3" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-body">
              <div>
                <span className="text-white/30 text-[10px] uppercase tracking-wider">
                  Reference
                </span>
                <p className="text-white/60 font-mono mt-0.5 break-all">
                  {step.ref}
                </p>
              </div>
              <div>
                <span className="text-white/30 text-[10px] uppercase tracking-wider">
                  Confidence
                </span>
                <p className="text-white/60 font-mono mt-0.5">
                  {step.confidence !== null
                    ? `${Math.round(step.confidence * 100)}%`
                    : "n/a"}
                </p>
              </div>
              {step.ci_level !== null && (
                <div>
                  <span className="text-white/30 text-[10px] uppercase tracking-wider">
                    CI Level
                  </span>
                  <p className="text-white/60 font-mono mt-0.5">
                    {Math.round(step.ci_level * 100)}%
                  </p>
                </div>
              )}
            </div>
          </div>
        )
      })()}

      {/* Expand hint */}
      <div className="flex items-center gap-1 text-[10px] text-white/20">
        <ChevronDown className="w-3 h-3" />
        Click a step to expand details
      </div>
    </div>
  )
}
