"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { api, ApiError } from "@/lib/api"
import type { PipelineResult } from "@/types/storm"
import ImpactDisplay from "@/components/dashboard/ImpactDisplay"
import AdvisoryCard from "@/components/dashboard/AdvisoryCard"
import VerifiedAdvisoryCard from "@/components/dashboard/VerifiedAdvisoryCard"
import ProvenanceChain from "@/components/dashboard/ProvenanceChain"
import DashboardErrorBoundary from "@/components/dashboard/DashboardErrorBoundary"
import { SkeletonGauges } from "@/components/Skeleton"
import EmptyState from "@/components/EmptyState"
import { useToast } from "@/components/Toast"
import { ArrowLeft, AlertTriangle, Satellite, FileWarning, Loader2 } from "lucide-react"

export default function ResultsPage() {
  const { stormId } = useParams<{ stormId: string }>()
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { addToast } = useToast()

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
            const msg = err instanceof ApiError ? err.message : "Failed to load results"
            setError(msg)
            addToast(msg)
          }
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => { active = false }
  }, [stormId, addToast])

  const hasImpact = result?.impact_prediction !== null && result?.impact_prediction !== undefined
  const hasAdvisories = (result?.advisories.length ?? 0) > 0
  const hasVerified = (result?.verified_advisories.length ?? 0) > 0
  const hasProvenance = (result?.provenance_traces.length ?? 0) > 0

  return (
    <DashboardErrorBoundary section={`Results ${stormId}`}>
      <div className="space-y-8">
        {/* Header */}
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
              <h2 className="text-2xl font-display font-bold text-white/90 tracking-tight">
                Results: {stormId}
              </h2>
              {result?.completed_at && (
                <p className="text-xs text-white/30 font-body mt-1">
                  Completed {new Date(result.completed_at).toLocaleString()}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 px-4 py-8 rounded-xl bg-white/[0.02] border border-white/[0.06]">
              <Loader2 className="w-4 h-4 text-white/40 animate-spin" />
              <span className="text-sm text-white/40 font-body">Loading results...</span>
            </div>
            <SkeletonGauges />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span className="text-sm text-red-300 font-body">{error}</span>
          </div>
        )}

        {/* No result */}
        {!loading && !result && !error && (
          <EmptyState
            icon={<Satellite className="w-8 h-8" />}
            title="No results available for this storm."
            description="Run the pipeline first to generate results."
          />
        )}

        {/* Pipeline errors */}
        {result?.errors && result.errors.length > 0 && (
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
        )}

        {/* Impact Prediction */}
        {hasImpact && (
          <section className="space-y-4">
            <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
              Impact Prediction
            </h3>
            <ImpactDisplay prediction={result!.impact_prediction!} />
          </section>
        )}

        {/* Advisories */}
        {hasAdvisories && (
          <section className="space-y-4">
            <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
              Advisories ({result!.advisories.length})
            </h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {result!.advisories.map((advisory) => (
                <AdvisoryCard key={advisory.advisory_id} advisory={advisory} />
              ))}
            </div>
          </section>
        )}

        {!loading && result && !hasAdvisories && (
          <EmptyState
            icon={<FileWarning className="w-8 h-8" />}
            title="No advisories generated"
            description="The pipeline completed but produced no advisories for this storm."
          />
        )}

        {/* Verified Advisories */}
        {hasVerified && (
          <section className="space-y-4">
            <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
              Verified Advisories ({result!.verified_advisories.length})
            </h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {result!.verified_advisories.map((advisory) => (
                <VerifiedAdvisoryCard
                  key={advisory.advisory_id}
                  advisory={advisory}
                />
              ))}
            </div>
          </section>
        )}

        {/* Provenance Traces */}
        {hasProvenance && (
          <section className="space-y-4">
            <h3 className="text-sm font-display font-semibold text-white/70 uppercase tracking-wider">
              Provenance Traces ({result!.provenance_traces.length})
            </h3>
            <div className="space-y-4">
              {result!.provenance_traces.map((trace) => (
                <ProvenanceChain key={trace.trace_id} trace={trace} />
              ))}
            </div>
          </section>
        )}
      </div>
    </DashboardErrorBoundary>
  )
}
