import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, act } from "@testing-library/react"
import { ToastProvider, useToast } from "@/components/Toast"

function ToastTrigger({ message, type }: { message: string; type?: "error" | "success" | "info" }) {
  const { addToast } = useToast()
  return (
    <button onClick={() => addToast(message, type)}>
      Show toast
    </button>
  )
}

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders children", () => {
    render(
      <ToastProvider>
        <div>Child content</div>
      </ToastProvider>
    )
    expect(screen.getByText("Child content")).toBeInTheDocument()
  })

  it("shows toast when addToast is called", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Something failed" />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Show toast"))
    expect(screen.getByText("Something failed")).toBeInTheDocument()
  })

  it("shows error toast by default", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Error occurred" />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Show toast"))
    const toast = screen.getByText("Error occurred").closest("div")!
    expect(toast.className).toContain("red-500")
  })

  it("shows success toast when type is success", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Saved!" type="success" />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Show toast"))
    const toast = screen.getByText("Saved!").closest("div")!
    expect(toast.className).toContain("emerald-500")
  })

  it("shows info toast when type is info", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="FYI" type="info" />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Show toast"))
    expect(screen.getByText("FYI")).toBeInTheDocument()
  })

  it("dismisses toast when X is clicked", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Dismissible" />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Show toast"))
    expect(screen.getByText("Dismissible")).toBeInTheDocument()

    const dismissBtn = screen.getByLabelText("Dismiss")
    fireEvent.click(dismissBtn)

    expect(screen.queryByText("Dismissible")).not.toBeInTheDocument()
  })

  it("auto-dismisses after 5 seconds", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Auto dismiss" />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Show toast"))
    expect(screen.getByText("Auto dismiss")).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(5000)
    })

    expect(screen.queryByText("Auto dismiss")).not.toBeInTheDocument()
  })

  it("shows multiple toasts", () => {
    function MultiToast() {
      const { addToast } = useToast()
      return (
        <div>
          <button onClick={() => addToast("Toast msg 1")}>Add 1</button>
          <button onClick={() => addToast("Toast msg 2")}>Add 2</button>
        </div>
      )
    }

    render(
      <ToastProvider>
        <MultiToast />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Add 1"))
    fireEvent.click(screen.getByText("Add 2"))

    expect(screen.getByText("Toast msg 1")).toBeInTheDocument()
    expect(screen.getByText("Toast msg 2")).toBeInTheDocument()
  })

  it("limits toasts to 5", () => {
    function ManyToasts() {
      const { addToast } = useToast()
      return (
        <button onClick={() => {
          for (let i = 0; i < 7; i++) addToast(`Toast ${i}`)
        }}>
          Add many
        </button>
      )
    }

    render(
      <ToastProvider>
        <ManyToasts />
      </ToastProvider>
    )

    fireEvent.click(screen.getByText("Add many"))

    const toasts = screen.getAllByText(/^Toast \d$/)
    expect(toasts.length).toBe(5)
  })
})

describe("useToast", () => {
  it("throws when used outside provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {})

    function BadComponent() {
      useToast()
      return null
    }

    expect(() => render(<BadComponent />)).toThrow("useToast must be used within ToastProvider")
    spy.mockRestore()
  })
})
