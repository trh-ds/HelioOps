"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp, AlertTriangle, ExternalLink } from "lucide-react"
import clsx from "clsx"
import type { AdvisoryOutput, Industry, SeverityTier } from "@/types/storm"

const INDUSTRY_COLORS: Record<Industry, { bg: string; text: string; border: string }> = {
  aviation: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/20" },
  grid: { bg: "bg-warm/10", text: "text-warm", border: "border-warm/20" },
  maritime: { bg: "bg-cyan-500/10", text: "text-cyan-400", border: "border-cyan-500/20" },
  telecom: { bg: "bg-purple-500/10", text: "text-purple-400", border: "border-purple-500/20" },
}

const SEVERITY_COLORS: Record<SeverityTier, { bg: string; text: string; border: string }> = {
  NONE: { bg: "bg-white/[0.04]", text: "text-white/40", border: "border-white/[0.08]" },
  LOW: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  MEDIUM: { bg: "bg-yellow-500/10", text: "text-yellow-400", border: "border-yellow-500/20" },
  HIGH: { bg: "bg-orange-500/10", text: "text-orange-400", border: "border-orange-500/20" },
  CRITICAL: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/20" },
}

export default function AdvisoryCard({ advisory }: { advisory: AdvisoryOutput }) {
  const [expanded, setExpanded] = useState(false)
  const industry = INDUSTRY_COLORS[advisory.industry] ?? INDUSTRY_COLORS.aviation
  const severity = SEVERITY_COLORS[advisory.severity] ?? SEVERITY_COLORS.NONE
  const hasFlags = advisory.safety_flags.length > 0
  const hasErrors = advisory.generation_errors.length > 0

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      {/* Header: industry + severity badges */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border",
              industry.bg,
              industry.text,
              industry.border
            )}
          >
            {advisory.industry}
          </span>
          <span
            className={clsx(
              "px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border",
              severity.bg,
              severity.text,
              severity.border
            )}
          >
            {advisory.severity}
          </span>
        </div>

        <span className="text-[10px] font-mono text-white/30">
          {Math.round(advisory.confidence_score * 100)}% confidence
        </span>
      </div>

      {/* Summary */}
      <p className="text-sm font-body text-white/70 leading-relaxed">
        {advisory.summary}
      </p>

      {/* Impact window */}
      {advisory.estimated_impact_window && (
        <div className="text-xs font-body text-white/40">
          Impact window:{" "}
          <span className="text-white/60 font-mono">
            {advisory.estimated_impact_window}
          </span>
        </div>
      )}

      {/* Safety flags */}
      {hasFlags && (
        <div className="flex flex-wrap gap-1.5">
          {advisory.safety_flags.map((flag) => (
            <span
              key={flag}
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-warm/[0.08] border border-warm/[0.15] text-[10px] font-mono text-warm/80"
            >
              <AlertTriangle className="w-2.5 h-2.5" />
              {flag.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}

      {/* Generation errors */}
      {hasErrors && (
        <div className="space-y-1">
          {advisory.generation_errors.map((err, i) => (
            <div
              key={i}
              className="text-[10px] font-body text-red-400/70 bg-red-500/[0.04] rounded px-2 py-1"
            >
              {err}
            </div>
          ))}
        </div>
      )}

      {/* Action items accordion */}
      {advisory.action_items.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-2 text-xs font-body text-white/50 hover:text-white/70 transition-colors"
          >
            {expanded ? (
              <ChevronUp className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
            {advisory.action_items.length} action items
          </button>

          {expanded && (
            <div className="mt-2 space-y-2">
              {advisory.action_items.map((item) => (
                <div
                  key={item.step}
                  className="flex gap-3 text-xs font-body pl-5"
                >
                  <span className="text-aurora font-mono shrink-0">
                    {item.step}.
                  </span>
                  <div className="space-y-0.5">
                    <p className="text-white/70">{item.action}</p>
                    <p className="text-white/40 text-[10px]">
                      {item.rationale}
                    </p>
                    {item.source_ref && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-mono text-white/30">
                        <ExternalLink className="w-2.5 h-2.5" />
                        {item.source_ref}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sources cited */}
      {advisory.sources_cited.length > 0 && (
        <div className="border-t border-white/[0.06] pt-3">
          <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">
            Sources
          </span>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {advisory.sources_cited.map((src, i) => (
              <span
                key={i}
                className="px-2 py-0.5 rounded bg-white/[0.03] border border-white/[0.06] text-[10px] font-mono text-white/40"
              >
                {src}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-[10px] font-mono text-white/20 border-t border-white/[0.06] pt-3">
        <span>{advisory.advisory_id}</span>
        <span>{advisory.model_used}</span>
      </div>
    </div>
  )
}
