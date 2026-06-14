import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor, act } from "@testing-library/react"
import HealthPage from "@/app/dashboard/health/page"

const mockAddToast = vi.fn()
vi.mock("@/components/Toast", () => ({
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useToast: () => ({ addToast: mockAddToast, dismissToast: vi.fn() }),
}))

const mockGetHealth = vi.fn()
const mockGetHealthReady = vi.fn()
const mockGetMetrics = vi.fn()

vi.mock("@/lib/api", () => ({
  api: {
    getHealth: () => mockGetHealth(),
    getHealthReady: () => mockGetHealthReady(),
    getMetrics: () => mockGetMetrics(),
  },
  parseMetrics: (text: string) => {
    const metrics = new Map<string, number>()
    for (const line of text.split("\n")) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith("#")) continue
      const parts = trimmed.split(/\s+/)
      if (parts.length >= 2) {
        const value = parseFloat(parts[1])
        if (!isNaN(value)) metrics.set(parts[0], value)
      }
    }
    return metrics
  },
}))

const healthResponse = {
  status: "ok",
  version: "0.1.0",
  timestamp: "2024-10-11T20:00:00Z",
}

const readyResponse = {
  status: "ready",
  checks: {
    detection: true,
    ml_models: true,
    genai_module: true,
  },
  version: "0.1.0",
}

const metricsResponse = `
helioops_uptime_seconds 3600.00
helioops_pipeline_requests_total 42
helioops_pipeline_errors_total 3
helioops_pipeline_duration_seconds_avg 15.23
helioops_pipeline_duration_seconds_p99 28.50
helioops_detection_requests_total 20
helioops_advisory_requests_total 15
helioops_ws_connections_total 5
`

describe("HealthPage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockGetHealth.mockResolvedValue(healthResponse)
    mockGetHealthReady.mockResolvedValue(readyResponse)
    mockGetMetrics.mockResolvedValue(metricsResponse)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it("renders page heading", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("Health & Metrics")).toBeInTheDocument()
    })
  })

  it("renders service status section", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("Service Status")).toBeInTheDocument()
      expect(screen.getByText("ok")).toBeInTheDocument()
      expect(screen.getByText("0.1.0")).toBeInTheDocument()
    })
  })

  it("renders dependency checks section", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("Dependency Checks")).toBeInTheDocument()
      expect(screen.getByText("CV Detection")).toBeInTheDocument()
      expect(screen.getByText("ML Models")).toBeInTheDocument()
      expect(screen.getByText("GenAI Module")).toBeInTheDocument()
    })
  })

  it("renders ready status badge", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("ready")).toBeInTheDocument()
    })
  })

  it("renders metrics section", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("Prometheus Metrics")).toBeInTheDocument()
    })
  })

  it("shows healthy status for all checks", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      const healthyLabels = screen.getAllByText("healthy")
      expect(healthyLabels).toHaveLength(3)
    })
  })

  it("shows unhealthy status for failed checks", async () => {
    mockGetHealthReady.mockResolvedValue({
      status: "degraded",
      checks: {
        detection: true,
        ml_models: false,
        genai_module: true,
      },
      version: "0.1.0",
    })

    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("degraded")).toBeInTheDocument()
      expect(screen.getByText("unavailable")).toBeInTheDocument()
    })
  })

  it("shows error when backend is down", async () => {
    mockGetHealth.mockRejectedValue(new Error("Connection refused"))
    mockGetHealthReady.mockRejectedValue(new Error("Connection refused"))
    mockGetMetrics.mockRejectedValue(new Error("Connection refused"))

    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("Backend unreachable")).toBeInTheDocument()
    })
  })

  it("auto-refreshes data", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(mockGetHealth).toHaveBeenCalledTimes(1)
    })

    await act(async () => {
      vi.advanceTimersByTime(10_000)
    })

    await waitFor(() => {
      expect(mockGetHealth).toHaveBeenCalledTimes(2)
    })
  })

  it("shows last refresh timestamp", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText(/Last refresh:/)).toBeInTheDocument()
    })
  })

  it("renders uptime from metrics", async () => {
    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("1h 0m")).toBeInTheDocument()
    })
  })

  it("handles partial API failures gracefully", async () => {
    mockGetHealthReady.mockRejectedValue(new Error("timeout"))

    render(<HealthPage />)
    await waitFor(() => {
      expect(screen.getByText("ok")).toBeInTheDocument()
      expect(screen.getByText("Prometheus Metrics")).toBeInTheDocument()
    })
  })
})
