"use client"

import ErrorBoundary from "@/components/ErrorBoundary"
import { AlertTriangle, RefreshCw } from "lucide-react"

function DashboardFallback({ section }: { section?: string }) {
  return (
    <div className="rounded-xl p-5 bg-red-500/[0.04] border border-red-500/[0.12] space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-red-400" />
        <span className="text-sm font-body font-medium text-red-300">
          {section ? `${section} failed to load` : "Section failed to load"}
        </span>
      </div>
      <p className="text-xs font-body text-red-400/60">
        This section encountered an error. Other sections are unaffected.
      </p>
      <button
        onClick={() => window.location.reload()}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-body text-red-300 hover:text-red-200 bg-red-500/[0.08] hover:bg-red-500/[0.12] border border-red-500/[0.15] transition-colors"
      >
        <RefreshCw className="w-3 h-3" />
        Reload page
      </button>
    </div>
  )
}

export default function DashboardErrorBoundary({
  children,
  section,
}: {
  children: React.ReactNode
  section?: string
}) {
  return (
    <ErrorBoundary fallback={<DashboardFallback section={section} />}>
      {children}
    </ErrorBoundary>
  )
}
