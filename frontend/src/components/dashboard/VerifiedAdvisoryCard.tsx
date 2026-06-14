"use client"

import { Shield, ShieldCheck, ShieldX, Clock, AlertTriangle, ExternalLink } from "lucide-react"
import clsx from "clsx"
import type { VerifiedAdvisory, VerifierResult } from "@/types/storm"

const VERIFIER_STYLES: Record<
  VerifierResult["status"],
  { icon: typeof Shield; bg: string; text: string; border: string; label: string }
> = {
  passed: {
    icon: ShieldCheck,
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
    label: "Passed",
  },
  passed_with_corrections: {
    icon: Shield,
    bg: "bg-yellow-500/10",
    text: "text-yellow-400",
    border: "border-yellow-500/20",
    label: "Passed with corrections",
  },
  blocked: {
    icon: ShieldX,
    bg: "bg-red-500/10",
    text: "text-red-400",
    border: "border-red-500/20",
    label: "Blocked",
  },
}

function formatTimingWindow(opens: string, durationMin: number): string {
  try {
    const start = new Date(opens)
    const end = new Date(start.getTime() + durationMin * 60_000)
    return `${start.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })} → ${end.toLocaleString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })} (${durationMin}min)`
  } catch {
    return `${opens} (${durationMin}min)`
  }
}

export default function VerifiedAdvisoryCard({
  advisory,
}: {
  advisory: VerifiedAdvisory
}) {
  const verifier = VERIFIER_STYLES[advisory.verifier.status] ?? VERIFIER_STYLES.blocked
  const VerifierIcon = verifier.icon
  const corrections = advisory.verifier.checks.filter(
    (c) => c.status === "pass" && c.corrected_to !== null
  )

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border",
              verifier.bg,
              verifier.text,
              verifier.border
            )}
          >
            <VerifierIcon className="w-3 h-3 inline mr-1" />
            {verifier.label}
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono text-white/50 border border-white/[0.08]">
            {advisory.industry}
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono text-white/50 border border-white/[0.08]">
            {advisory.severity}
          </span>
        </div>
      </div>

      {/* Requires human review */}
      {advisory.requires_human && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-warm/[0.06] border border-warm/[0.15]">
          <AlertTriangle className="w-3.5 h-3.5 text-warm shrink-0" />
          <span className="text-xs font-body text-warm/80">
            Requires human review before distribution
          </span>
        </div>
      )}

      {/* Numbered actions */}
      <div className="space-y-2">
        <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">
          Actions
        </span>
        <ol className="space-y-1.5">
          {advisory.numbered_actions.map((action, i) => (
            <li key={i} className="flex gap-3 text-xs font-body">
              <span className="text-aurora font-mono shrink-0 w-5 text-right">
                {i + 1}.
              </span>
              <span className="text-white/70">{action}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Timing window */}
      <div className="flex items-center gap-2 text-xs font-body">
        <Clock className="w-3.5 h-3.5 text-white/30" />
        <span className="text-white/40">Timing:</span>
        <span className="text-white/60 font-mono">
          {formatTimingWindow(
            advisory.timing_window.opens,
            advisory.timing_window.duration_min
          )}
        </span>
      </div>

      {/* Technical details */}
      <div className="rounded-lg p-3 bg-white/[0.02] border border-white/[0.06]">
        <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">
          Technical Details
        </span>
        <p className="text-xs font-body text-white/60 mt-1.5 leading-relaxed">
          {advisory.technical_details}
        </p>
      </div>

      {/* Cited procedure */}
      <div className="flex items-center gap-2 text-xs font-body">
        <ExternalLink className="w-3 h-3 text-white/30" />
        <span className="text-white/40">Procedure:</span>
        <span className="text-white/60">
          {advisory.cited_procedure.source} — {advisory.cited_procedure.ref}
        </span>
      </div>

      {/* Corrections */}
      {corrections.length > 0 && (
        <div className="border-t border-white/[0.06] pt-3">
          <span className="text-[10px] font-mono text-yellow-400/60 uppercase tracking-wider">
            Corrections Applied
          </span>
          <div className="mt-1.5 space-y-1">
            {corrections.map((c) => (
              <div
                key={c.field}
                className="text-[10px] font-body text-white/40"
              >
                <span className="font-mono text-white/50">{c.field}</span>
                {": "}
                <span className="line-through text-white/30">
                  {String(c.proposed)}
                </span>
                {" → "}
                <span className="text-yellow-400/70">
                  {String(c.corrected_to)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-[10px] font-mono text-white/20 border-t border-white/[0.06] pt-3">
        <span>{advisory.advisory_id}</span>
        <span>ref: {advisory.provenance_ref}</span>
      </div>
    </div>
  )
}
