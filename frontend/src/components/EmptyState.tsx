"use client"

import type { ReactNode } from "react"
import { Inbox } from "lucide-react"
import clsx from "clsx"

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={clsx("text-center py-16", className)}>
      <div className="text-white/20 mx-auto mb-3">
        {icon ?? <Inbox className="w-8 h-8" />}
      </div>
      <p className="text-sm text-white/50 font-body">{title}</p>
      {description && (
        <p className="text-xs text-white/30 font-body mt-1">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
