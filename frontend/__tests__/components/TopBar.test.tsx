import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import TopBar from "@/components/dashboard/TopBar"

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}))

// Mock the API
const mockGetHealth = vi.fn()
vi.mock("@/lib/api", () => ({
  api: {
    getHealth: () => mockGetHealth(),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

// Mock the WebSocket client
const mockIsConnected = vi.fn(() => false)
vi.mock("@/lib/ws-client", () => ({
  wsClient: {
    isConnected: () => mockIsConnected(),
  },
}))

describe("TopBar", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockGetHealth.mockResolvedValue({ status: "ok" })
    mockIsConnected.mockReturnValue(false)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it("renders the page title", () => {
    render(<TopBar />)
    expect(screen.getByText("Storm List")).toBeInTheDocument()
  })

  it("shows health badge after fetch", async () => {
    render(<TopBar />)

    await waitFor(
      () => {
        expect(screen.getByText("ok")).toBeInTheDocument()
      },
      { timeout: 3000 },
    )
  })

  it("shows offline status on health fetch failure", async () => {
    mockGetHealth.mockRejectedValueOnce(new Error("Network error"))

    render(<TopBar />)

    await waitFor(
      () => {
        expect(screen.getByText("offline")).toBeInTheDocument()
      },
      { timeout: 3000 },
    )
  })

  it("shows WS off when disconnected", () => {
    mockIsConnected.mockReturnValue(false)
    render(<TopBar />)
    expect(screen.getByText("WS off")).toBeInTheDocument()
  })

  it("shows WS live when connected", () => {
    mockIsConnected.mockReturnValue(true)
    render(<TopBar />)
    expect(screen.getByText("WS live")).toBeInTheDocument()
  })
})
