import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import ProvenanceChain from "@/components/dashboard/ProvenanceChain"
import type { ProvenanceTrace } from "@/types/storm"

const trace: ProvenanceTrace = {
  trace_id: "trace-001",
  advisory_id: "adv-001",
  chain: [
    { step: "raw_data", ref: "nws-alert-123", confidence: 0.95, ci_level: 0.95 },
    { step: "detection", ref: "cv-model-v2", confidence: 0.88, ci_level: null },
    { step: "impact", ref: "ml-gps-v1", confidence: 0.72, ci_level: 0.95 },
    { step: "retrieval", ref: "rag-query-7", confidence: 0.81, ci_level: null },
    { step: "verifier", ref: "rule-engine-v3", confidence: 0.93, ci_level: null },
    { step: "output", ref: "gen-advisory", confidence: 0.85, ci_level: null },
  ],
}

describe("ProvenanceChain", () => {
  it("renders all 6 step labels", () => {
    render(<ProvenanceChain trace={trace} />)
    expect(screen.getByText("Raw Data")).toBeInTheDocument()
    expect(screen.getByText("Detection")).toBeInTheDocument()
    expect(screen.getByText("Impact")).toBeInTheDocument()
    expect(screen.getByText("Retrieval")).toBeInTheDocument()
    expect(screen.getByText("Verifier")).toBeInTheDocument()
    expect(screen.getByText("Output")).toBeInTheDocument()
  })

  it("renders trace id", () => {
    render(<ProvenanceChain trace={trace} />)
    expect(screen.getByText("trace-001")).toBeInTheDocument()
  })

  it("renders confidence percentages", () => {
    render(<ProvenanceChain trace={trace} />)
    expect(screen.getByText("95%")).toBeInTheDocument()
    expect(screen.getByText("88%")).toBeInTheDocument()
    expect(screen.getByText("72%")).toBeInTheDocument()
  })

  it("expands step details on click", () => {
    render(<ProvenanceChain trace={trace} />)
    fireEvent.click(screen.getByText("Raw Data"))
    expect(screen.getByText("Reference")).toBeInTheDocument()
    expect(screen.getByText("nws-alert-123")).toBeInTheDocument()
  })

  it("collapses on second click", () => {
    render(<ProvenanceChain trace={trace} />)
    const buttons = screen.getAllByText("Raw Data")
    fireEvent.click(buttons[0])
    fireEvent.click(buttons[0])
    expect(screen.queryByText("Reference")).not.toBeInTheDocument()
  })

  it("handles trace with fewer steps", () => {
    const partialTrace: ProvenanceTrace = {
      trace_id: "trace-002",
      advisory_id: "adv-002",
      chain: [
        { step: "raw_data", ref: "alert-1", confidence: 0.9, ci_level: null },
        { step: "detection", ref: "cv-1", confidence: 0.8, ci_level: null },
      ],
    }
    render(<ProvenanceChain trace={partialTrace} />)
    expect(screen.getByText("Raw Data")).toBeInTheDocument()
    expect(screen.getByText("Detection")).toBeInTheDocument()
    expect(screen.getByText("90%")).toBeInTheDocument()
    expect(screen.getByText("80%")).toBeInTheDocument()
  })

  it("handles null confidence", () => {
    const traceWithNull: ProvenanceTrace = {
      trace_id: "trace-003",
      advisory_id: "adv-003",
      chain: [
        { step: "raw_data", ref: "alert-1", confidence: null, ci_level: null },
      ],
    }
    render(<ProvenanceChain trace={traceWithNull} />)
    expect(screen.getByText("n/a")).toBeInTheDocument()
  })

  it("shows expand hint", () => {
    render(<ProvenanceChain trace={trace} />)
    expect(screen.getByText("Click a step to expand details")).toBeInTheDocument()
  })
})
