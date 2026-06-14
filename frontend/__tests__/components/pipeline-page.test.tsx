import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import PipelinePage from "@/app/dashboard/pipeline/page"

const mockGetStorms = vi.fn()
const mockSend = vi.fn()
const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
const mockSubscribe = vi.fn()

vi.mock("@/lib/api", () => ({
  api: {
    getStorms: () => mockGetStorms(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

vi.mock("@/lib/ws-client", () => ({
  wsClient: {
    connect: () => mockConnect(),
    disconnect: () => mockDisconnect(),
    send: (data: unknown) => mockSend(data),
    subscribe: (cb: unknown) => mockSubscribe(cb),
  },
}))

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

describe("PipelinePage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockSubscribe.mockReturnValue(() => {})
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it("renders page heading", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: ["2024-10-G4"],
      completed: {},
    })

    render(<PipelinePage />)

    await waitFor(() => {
      expect(screen.getByText("Pipeline Runner")).toBeInTheDocument()
    })
  })

  it("populates storm selector", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: ["2024-10-G4", "2024-05-G5"],
      completed: {},
    })

    render(<PipelinePage />)

    await waitFor(() => {
      const select = screen.getByDisplayValue("Select a storm...")
      expect(select).toBeInTheDocument()
      expect(screen.getByText("2024-10-G4")).toBeInTheDocument()
      expect(screen.getByText("2024-05-G5")).toBeInTheDocument()
    })
  })

  it("shows error when storms fail to load", async () => {
    mockGetStorms.mockRejectedValue(new Error("Network error"))

    render(<PipelinePage />)

    await waitFor(() => {
      expect(screen.getByText("Failed to load storms")).toBeInTheDocument()
    })
  })

  it("disables Run button when no storm selected", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: ["2024-10-G4"],
      completed: {},
    })

    render(<PipelinePage />)

    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /run pipeline/i })
      expect(btn).toBeDisabled()
    })
  })

  it("connects WebSocket on mount", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: [],
      completed: {},
    })

    render(<PipelinePage />)

    await waitFor(() => {
      expect(mockConnect).toHaveBeenCalled()
    })
  })

  it("subscribes to WebSocket events", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: [],
      completed: {},
    })

    render(<PipelinePage />)

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalled()
    })
  })

  it("shows pipeline progress section", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: [],
      completed: {},
    })

    render(<PipelinePage />)

    await waitFor(() => {
      expect(screen.getByText("Pipeline Progress")).toBeInTheDocument()
    })
  })

  it("shows event stream section", async () => {
    mockGetStorms.mockResolvedValue({
      available_storms: [],
      completed: {},
    })

    render(<PipelinePage />)

    await waitFor(() => {
      expect(screen.getByText("Event Stream")).toBeInTheDocument()
    })
  })
})
