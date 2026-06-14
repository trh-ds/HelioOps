import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import ErrorBoundary from "@/components/ErrorBoundary"

function ThrowingComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("Test error")
  return <div>Child content</div>
}

function UnrecoverableThrow(): never {
  throw new TypeError("Type error")
}

const consoleError = vi.fn()
vi.stubGlobal("console", { ...console, error: consoleError })

describe("ErrorBoundary", () => {
  beforeEach(() => {
    consoleError.mockClear()
  })

  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={false} />
      </ErrorBoundary>
    )
    expect(screen.getByText("Child content")).toBeInTheDocument()
  })

  it("catches thrown errors and renders fallback", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.getByText("Something went wrong")).toBeInTheDocument()
    expect(screen.getByText("Test error")).toBeInTheDocument()
  })

  it("renders custom fallback when provided", () => {
    render(
      <ErrorBoundary fallback={<div>Custom fallback</div>}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.getByText("Custom fallback")).toBeInTheDocument()
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument()
  })

  it("calls onError callback when error occurs", () => {
    const onError = vi.fn()
    render(
      <ErrorBoundary onError={onError}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Test error" }),
      expect.any(Object)
    )
  })

  it("resets error state when try again is clicked", () => {
    let shouldThrow = true
    function ConditionalThrow() {
      if (shouldThrow) throw new Error("Conditional error")
      return <div>Recovered</div>
    }

    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    )

    expect(screen.getByText("Something went wrong")).toBeInTheDocument()

    shouldThrow = false
    fireEvent.click(screen.getByText("Try again"))

    expect(screen.getByText("Recovered")).toBeInTheDocument()
  })

  it("catches TypeError", () => {
    render(
      <ErrorBoundary>
        <UnrecoverableThrow />
      </ErrorBoundary>
    )
    expect(screen.getByText("Type error")).toBeInTheDocument()
  })

  it("hides child content when error occurs", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.queryByText("Child content")).not.toBeInTheDocument()
  })

  it("shows try again button", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.getByText("Try again")).toBeInTheDocument()
  })
})
