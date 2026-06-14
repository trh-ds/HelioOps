"use client"

import clsx from "clsx"

interface SkeletonProps {
  className?: string
  variant?: "text" | "rect" | "circle" | "card"
  lines?: number
}

function SkeletonPulse({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        "rounded bg-white/[0.06] animate-pulse",
        className
      )}
    />
  )
}

export default function Skeleton({ className, variant = "rect", lines = 1 }: SkeletonProps) {
  if (variant === "circle") {
    return <SkeletonPulse className={clsx("rounded-full", className)} />
  }

  if (variant === "card") {
    return (
      <div className={clsx("rounded-xl p-5 border border-white/[0.06] bg-white/[0.02] space-y-3", className)}>
        <div className="flex items-center gap-2.5">
          <SkeletonPulse className="h-4 w-28" />
          <SkeletonPulse className="h-4 w-8" />
        </div>
        <div className="space-y-2">
          <SkeletonPulse className="h-3 w-full" />
          <SkeletonPulse className="h-3 w-2/3" />
        </div>
      </div>
    )
  }

  if (variant === "text") {
    return (
      <div className={clsx("space-y-2", className)}>
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonPulse
            key={i}
            className={clsx("h-3", i === lines - 1 ? "w-2/3" : "w-full")}
          />
        ))}
      </div>
    )
  }

  return <SkeletonPulse className={className} />
}

export function SkeletonCard({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} variant="card" />
      ))}
    </div>
  )
}

export function SkeletonGauges({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl p-4 border border-white/[0.06] bg-white/[0.02] animate-pulse"
        >
          <SkeletonPulse className="h-3 w-16 mb-2" />
          <SkeletonPulse className="h-6 w-12" />
        </div>
      ))}
    </div>
  )
}
