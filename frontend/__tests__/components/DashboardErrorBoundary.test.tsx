import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import DashboardErrorBoundary from "@/components/dashboard/DashboardErrorBoundary"

function ThrowingChild(): never {
  throw new Error("Dashboard section error")
}

function WorkingChild() {
  return <div>Working content</div>
}

const consoleError = vi.fn()
vi.stubGlobal("console", { ...console, error: consoleError })

describe("DashboardErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <DashboardErrorBoundary>
        <WorkingChild />
      </DashboardErrorBoundary>
    )
    expect(screen.getByText("Working content")).toBeInTheDocument()
  })

  it("catches errors and renders section fallback", () => {
    render(
      <DashboardErrorBoundary>
        <ThrowingChild />
      </DashboardErrorBoundary>
    )
    expect(screen.getByText("Section failed to load")).toBeInTheDocument()
    expect(
      screen.getByText(/This section encountered an error/)
    ).toBeInTheDocument()
  })

  it("includes section name in fallback when provided", () => {
    render(
      <DashboardErrorBoundary section="Advisories">
        <ThrowingChild />
      </DashboardErrorBoundary>
    )
    expect(screen.getByText("Advisories failed to load")).toBeInTheDocument()
  })

  it("shows reload button", () => {
    render(
      <DashboardErrorBoundary>
        <ThrowingChild />
      </DashboardErrorBoundary>
    )
    expect(screen.getByText("Reload page")).toBeInTheDocument()
  })

  it("does not show fallback when children work", () => {
    render(
      <DashboardErrorBoundary section="Metrics">
        <WorkingChild />
      </DashboardErrorBoundary>
    )
    expect(screen.getByText("Working content")).toBeInTheDocument()
    expect(screen.queryByText("Section failed to load")).not.toBeInTheDocument()
  })
})
