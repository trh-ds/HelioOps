import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import StormCard from "@/components/dashboard/StormCard"
import type { StormSummary } from "@/types/storm"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

describe("StormCard", () => {
  it("renders storm ID", () => {
    render(<StormCard stormId="2024-10-G4" completed={null} />)
    expect(screen.getByText("2024-10-G4")).toBeInTheDocument()
  })

  it("renders G-scale badge for G4 storm", () => {
    render(<StormCard stormId="2024-10-G4" completed={null} />)
    expect(screen.getByText("G4")).toBeInTheDocument()
  })

  it("renders G-scale badge for G5 storm with red styling", () => {
    render(<StormCard stormId="2024-05-G5" completed={null} />)
    const badge = screen.getByText("G5")
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain("red-400")
  })

  it("renders G-scale badge for G1 storm with neutral styling", () => {
    render(<StormCard stormId="2024-01-G1" completed={null} />)
    const badge = screen.getByText("G1")
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain("white/70")
  })

  it("shows not-processed message when no completed data", () => {
    render(<StormCard stormId="2024-10-G4" completed={null} />)
    expect(screen.getByText(/Not yet processed/)).toBeInTheDocument()
  })

  it("shows advisory count when completed", () => {
    const completed: StormSummary = {
      storm_id: "2024-10-G4",
      completed_at: "2024-10-11T20:00:00Z",
      advisory_count: 4,
      verified_count: 3,
      error_count: 0,
    }
    render(<StormCard stormId="2024-10-G4" completed={completed} />)
    expect(screen.getByText("4")).toBeInTheDocument()
    expect(screen.getByText("3")).toBeInTheDocument()
  })

  it("shows error count when there are errors", () => {
    const completed: StormSummary = {
      storm_id: "2024-10-G4",
      completed_at: "2024-10-11T20:00:00Z",
      advisory_count: 2,
      verified_count: 1,
      error_count: 1,
    }
    render(<StormCard stormId="2024-10-G4" completed={completed} />)
    const errorLabel = screen.getByText("Errors")
    const errorRow = errorLabel.closest("div")
    expect(errorRow).toHaveTextContent("1")
  })

  it("links to storm detail page", () => {
    render(<StormCard stormId="2024-10-G4" completed={null} />)
    const link = screen.getByText("2024-10-G4").closest("a")
    expect(link).toHaveAttribute("href", "/dashboard/storms/2024-10-G4")
  })

  it("renders without G-scale badge for non-standard ID", () => {
    render(<StormCard stormId="custom-storm" completed={null} />)
    expect(screen.getByText("custom-storm")).toBeInTheDocument()
    expect(screen.queryByText(/^G\d$/)).not.toBeInTheDocument()
  })
})
