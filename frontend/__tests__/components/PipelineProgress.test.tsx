import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import PipelineProgress from "@/components/dashboard/PipelineProgress"
import type { PipelineStep } from "@/components/dashboard/PipelineProgress"

describe("PipelineProgress", () => {
  const defaultSteps: PipelineStep[] = [
    { id: "detection", label: "Detection", status: "pending" },
    { id: "impact_prediction", label: "Impact Prediction", status: "pending" },
    { id: "adaptation", label: "Adaptation", status: "pending" },
    { id: "advisory_generation", label: "Advisory", status: "pending" },
    { id: "verification", label: "Verification", status: "pending" },
  ]

  it("renders all 5 steps", () => {
    render(<PipelineProgress steps={defaultSteps} />)
    expect(screen.getByText("Detection")).toBeInTheDocument()
    expect(screen.getByText("Impact Prediction")).toBeInTheDocument()
    expect(screen.getByText("Adaptation")).toBeInTheDocument()
    expect(screen.getByText("Advisory")).toBeInTheDocument()
    expect(screen.getByText("Verification")).toBeInTheDocument()
  })

  it("renders all steps as pending by default", () => {
    render(<PipelineProgress steps={[]} />)
    const pendingLabels = screen.getAllByText("pending")
    expect(pendingLabels).toHaveLength(5)
  })

  it("shows done status for completed steps", () => {
    const steps: PipelineStep[] = [
      { id: "detection", label: "Detection", status: "done" },
      { id: "impact_prediction", label: "Impact Prediction", status: "pending" },
      { id: "adaptation", label: "Adaptation", status: "pending" },
      { id: "advisory_generation", label: "Advisory", status: "pending" },
      { id: "verification", label: "Verification", status: "pending" },
    ]
    render(<PipelineProgress steps={steps} />)
    const doneLabels = screen.getAllByText("done")
    expect(doneLabels).toHaveLength(1)
    expect(screen.getByText("Detection").className).toContain("emerald-400")
  })

  it("shows active status for in-progress step", () => {
    const steps: PipelineStep[] = [
      { id: "detection", label: "Detection", status: "done" },
      { id: "impact_prediction", label: "Impact Prediction", status: "active" },
      { id: "adaptation", label: "Adaptation", status: "pending" },
      { id: "advisory_generation", label: "Advisory", status: "pending" },
      { id: "verification", label: "Verification", status: "pending" },
    ]
    render(<PipelineProgress steps={steps} />)
    const activeLabels = screen.getAllByText("active")
    expect(activeLabels).toHaveLength(1)
    expect(screen.getByText("Impact Prediction").className).toContain("aurora")
  })

  it("shows error status for failed step", () => {
    const steps: PipelineStep[] = [
      { id: "detection", label: "Detection", status: "error" },
      { id: "impact_prediction", label: "Impact Prediction", status: "pending" },
      { id: "adaptation", label: "Adaptation", status: "pending" },
      { id: "advisory_generation", label: "Advisory", status: "pending" },
      { id: "verification", label: "Verification", status: "pending" },
    ]
    render(<PipelineProgress steps={steps} />)
    const errorLabels = screen.getAllByText("error")
    expect(errorLabels).toHaveLength(1)
    expect(screen.getByText("Detection").className).toContain("red-400")
  })

  it("handles mixed statuses across steps", () => {
    const steps: PipelineStep[] = [
      { id: "detection", label: "Detection", status: "done" },
      { id: "impact_prediction", label: "Impact Prediction", status: "done" },
      { id: "adaptation", label: "Adaptation", status: "active" },
      { id: "advisory_generation", label: "Advisory", status: "pending" },
      { id: "verification", label: "Verification", status: "pending" },
    ]
    render(<PipelineProgress steps={steps} />)
    expect(screen.getAllByText("done")).toHaveLength(2)
    expect(screen.getAllByText("active")).toHaveLength(1)
    expect(screen.getAllByText("pending")).toHaveLength(2)
  })
})
