import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AdvisoryCard from "@/components/dashboard/AdvisoryCard"
import type { AdvisoryOutput } from "@/types/storm"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const baseAdvisory: AdvisoryOutput = {
  advisory_id: "adv-001",
  storm_event_id: "2024-10-G4",
  industry: "aviation",
  severity: "HIGH",
  confidence_score: 0.87,
  summary: "HF radio blackouts expected on sunlit side.",
  action_items: [
    {
      step: 1,
      action: "Check HF radio equipment",
      rationale: "Blackout risk",
      source_ref: "ICAO Annex 3",
      time_window: "T+2h",
    },
    {
      step: 2,
      action: "Switch to backup comms",
      rationale: "Redundancy",
      source_ref: null,
      time_window: null,
    },
  ],
  estimated_impact_window: "2024-10-11T22:00Z to 2024-10-12T04:00Z",
  sources_cited: ["NOAA SWPC", "ICAO Annex 3"],
  validation_passed: true,
  generated_at: "2024-10-11T20:00:00Z",
  model_used: "gpt-4o-mini",
  safety_flags: ["LOW_CONFIDENCE"],
  generation_errors: [],
}

describe("AdvisoryCard", () => {
  it("renders industry badge", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("aviation")).toBeInTheDocument()
  })

  it("renders severity badge", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("HIGH")).toBeInTheDocument()
  })

  it("renders confidence score", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("87% confidence")).toBeInTheDocument()
  })

  it("renders summary text", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(
      screen.getByText("HF radio blackouts expected on sunlit side.")
    ).toBeInTheDocument()
  })

  it("renders impact window", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(
      screen.getByText("2024-10-11T22:00Z to 2024-10-12T04:00Z")
    ).toBeInTheDocument()
  })

  it("renders safety flags", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText(/LOW CONFIDENCE/)).toBeInTheDocument()
  })

  it("expands action items on click", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    fireEvent.click(screen.getByText("2 action items"))
    expect(screen.getByText("Check HF radio equipment")).toBeInTheDocument()
    expect(screen.getByText("Switch to backup comms")).toBeInTheDocument()
  })

  it("collapses action items on second click", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    fireEvent.click(screen.getByText("2 action items"))
    fireEvent.click(screen.getByText("2 action items"))
    expect(screen.queryByText("Check HF radio equipment")).not.toBeInTheDocument()
  })

  it("renders sources cited", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("NOAA SWPC")).toBeInTheDocument()
    expect(screen.getByText("ICAO Annex 3")).toBeInTheDocument()
  })

  it("renders advisory id and model", () => {
    render(<AdvisoryCard advisory={baseAdvisory} />)
    expect(screen.getByText("adv-001")).toBeInTheDocument()
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument()
  })

  it("renders generation errors", () => {
    const advisory = {
      ...baseAdvisory,
      generation_errors: ["Model timeout", "Rate limited"],
    }
    render(<AdvisoryCard advisory={advisory} />)
    expect(screen.getByText("Model timeout")).toBeInTheDocument()
    expect(screen.getByText("Rate limited")).toBeInTheDocument()
  })

  it("renders grid industry color", () => {
    const advisory = { ...baseAdvisory, industry: "grid" as const }
    render(<AdvisoryCard advisory={advisory} />)
    const badge = screen.getByText("grid")
    expect(badge.className).toContain("warm")
  })

  it("renders empty action items section gracefully", () => {
    const advisory = { ...baseAdvisory, action_items: [] }
    render(<AdvisoryCard advisory={advisory} />)
    expect(screen.queryByText(/action items/)).not.toBeInTheDocument()
  })
})
