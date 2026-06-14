import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import EmptyState from "@/components/EmptyState"

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState title="No data found" />)
    expect(screen.getByText("No data found")).toBeInTheDocument()
  })

  it("renders description when provided", () => {
    render(
      <EmptyState title="Empty" description="Nothing to show here" />
    )
    expect(screen.getByText("Nothing to show here")).toBeInTheDocument()
  })

  it("does not render description when omitted", () => {
    render(<EmptyState title="Empty" />)
    expect(screen.queryByText("Nothing to show here")).not.toBeInTheDocument()
  })

  it("renders custom icon", () => {
    render(
      <EmptyState title="Empty" icon={<span data-testid="custom-icon">Icon</span>} />
    )
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument()
  })

  it("renders action when provided", () => {
    render(
      <EmptyState
        title="Empty"
        action={<button>Action</button>}
      />
    )
    expect(screen.getByText("Action")).toBeInTheDocument()
  })

  it("does not render action when omitted", () => {
    render(<EmptyState title="Empty" />)
    expect(screen.queryByText("Action")).not.toBeInTheDocument()
  })

  it("applies custom className", () => {
    const { container } = render(
      <EmptyState title="Empty" className="my-custom-class" />
    )
    expect(container.firstChild).toHaveClass("my-custom-class")
  })
})
