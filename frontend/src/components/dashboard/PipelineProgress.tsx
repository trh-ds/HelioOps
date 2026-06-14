"use client"

import { motion } from "framer-motion"
import { Check, Loader2, X, Circle } from "lucide-react"
import clsx from "clsx"

export type StepStatus = "pending" | "active" | "done" | "error"

export interface PipelineStep {
  id: string
  label: string
  status: StepStatus
}

const STAGES: { id: string; label: string }[] = [
  { id: "detection", label: "Detection" },
  { id: "impact_prediction", label: "Impact Prediction" },
  { id: "adaptation", label: "Adaptation" },
  { id: "advisory_generation", label: "Advisory" },
  { id: "verification", label: "Verification" },
]

function StatusIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "done":
      return (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center"
        >
          <Check className="w-3 h-3 text-emerald-400" />
        </motion.div>
      )
    case "active":
      return (
        <div className="w-5 h-5 rounded-full bg-aurora/20 flex items-center justify-center">
          <Loader2 className="w-3 h-3 text-aurora animate-spin" />
        </div>
      )
    case "error":
      return (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center"
        >
          <X className="w-3 h-3 text-red-400" />
        </motion.div>
      )
    default:
      return (
        <div className="w-5 h-5 rounded-full bg-white/[0.06] flex items-center justify-center">
          <Circle className="w-3 h-3 text-white/30" />
        </div>
      )
  }
}

export default function PipelineProgress({
  steps,
}: {
  steps: PipelineStep[]
}) {
  return (
    <div className="space-y-2">
      {STAGES.map((stage, i) => {
        const step = steps.find((s) => s.id === stage.id)
        const status: StepStatus = step?.status ?? "pending"

        return (
          <div key={stage.id} className="flex items-center gap-3">
            <StatusIcon status={status} />

            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={clsx(
                    "text-sm font-body",
                    status === "done" && "text-emerald-400",
                    status === "active" && "text-aurora",
                    status === "error" && "text-red-400",
                    status === "pending" && "text-white/40"
                  )}
                >
                  {stage.label}
                </span>

                {status === "active" && (
                  <motion.div
                    layoutId="active-pulse"
                    className="w-1.5 h-1.5 rounded-full bg-aurora"
                    animate={{ opacity: [1, 0.3, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                )}
              </div>
            </div>

            <span
              className={clsx(
                "text-[10px] font-mono uppercase tracking-wider",
                status === "done" && "text-emerald-500/60",
                status === "active" && "text-aurora/60",
                status === "error" && "text-red-500/60",
                status === "pending" && "text-white/20"
              )}
            >
              {status}
            </span>
          </div>
        )
      })}
    </div>
  )
}
