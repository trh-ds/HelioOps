import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import VerifiedAdvisoryCard from "@/components/dashboard/VerifiedAdvisoryCard"
import type { VerifiedAdvisory } from "@/types/storm"

const baseAdvisory: VerifiedAdvisory = {
  advisory_id: "vadv-001",
  storm_id: "2024-10-G4",
  industry: "aviation",
  severity: "HIGH",
  numbered_actions: [
    "Notify pilots of HF blackout risk",
    "Switch to SATCOM backup",
  ],
  timing_window: {
    opens: "2024-10-11T22:00:00Z",
    duration_min: 360,
  },
  technical_details: "Solar wind speed elevated. Bz southward component sustained.",
  cited_procedure: {
    source: "ICAO",
    ref: "Annex 3, §4.2",
  },
  verifier: {
    status: "passed",
    checks: [],
  },
  provenance_ref: "prov-abc",
  requires_human: false,
}

describe("VerifiedAdvisoryCard", () => {
  it("renders verifier status badge", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("Passed")).toBeInTheDocument()
  })

  it("renders industry and severity", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("aviation")).toBeInTheDocument()
    expect(screen.getByText("HIGH")).toBeInTheDocument()
  })

  it("renders numbered actions", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("Notify pilots of HF blackout risk")).toBeInTheDocument()
    expect(screen.getByText("Switch to SATCOM backup")).toBeInTheDocument()
  })

  it("renders timing window", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText(/360min/)).toBeInTheDocument()
  })

  it("renders technical details", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(
      screen.getByText("Solar wind speed elevated. Bz southward component sustained.")
    ).toBeInTheDocument()
  })

  it("renders cited procedure", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText(/ICAO/)).toBeInTheDocument()
    expect(screen.getByText(/Annex 3/)).toBeInTheDocument()
  })

  it("renders provenance ref", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText(/prov-abc/)).toBeInTheDocument()
  })

  it("shows requires human review warning", () => {
    const advisory = { ...baseAdvisory, requires_human: true }
    render(<VerifiedAdvisoryCard advisory={advisory} />)
    expect(screen.getByText(/Requires human review/)).toBeInTheDocument()
  })

  it("hides human review warning when false", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.queryByText(/Requires human review/)).not.toBeInTheDocument()
  })

  it("shows passed with corrections status", () => {
    const advisory: VerifiedAdvisory = {
      ...baseAdvisory,
      verifier: {
        status: "passed_with_corrections",
        checks: [
          {
            field: "severity",
            proposed: "MEDIUM",
            status: "pass",
            corrected_to: "HIGH",
            reason: "Mismatch with G-scale",
          },
        ],
      },
    }
    render(<VerifiedAdvisoryCard advisory={advisory} />)
    expect(screen.getByText("Passed with corrections")).toBeInTheDocument()
  })

  it("shows blocked status", () => {
    const advisory: VerifiedAdvisory = {
      ...baseAdvisory,
      verifier: {
        status: "blocked",
        checks: [],
      },
    }
    render(<VerifiedAdvisoryCard advisory={advisory} />)
    expect(screen.getByText("Blocked")).toBeInTheDocument()
  })

  it("shows corrections when present", () => {
    const advisory: VerifiedAdvisory = {
      ...baseAdvisory,
      verifier: {
        status: "passed_with_corrections",
        checks: [
          {
            field: "severity",
            proposed: "LOW",
            status: "pass",
            corrected_to: "HIGH",
            reason: "G4 requires HIGH",
          },
        ],
      },
    }
    render(<VerifiedAdvisoryCard advisory={advisory} />)
    expect(screen.getByText("Corrections Applied")).toBeInTheDocument()
    expect(screen.getByText("severity")).toBeInTheDocument()
  })

  it("renders advisory id", () => {
    render(<VerifiedAdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("vadv-001")).toBeInTheDocument()
  })
})
